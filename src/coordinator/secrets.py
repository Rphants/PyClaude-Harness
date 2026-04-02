"""CMUX Secrets Manager — Secure API key access for agents.

Agents run on the VM and need API keys for external services.
This module provides a unified interface to store and retrieve secrets.

Storage backends (checked in order):
1. Environment variables (override — always checked first)
2. Cloudflare Worker (secrets-manager — production backend with audit trail)
3. Local .agent-secrets/ directory (dev/fallback — gitignored, chmod 600)
4. GCP Secret Manager (legacy — already has SLACK_WEBHOOK_URL)

Usage by agents:
    # Python
    from src.coordinator.secrets import get_secret, list_secrets
    meta_token = get_secret("META_ACCESS_TOKEN")

    # CLI
    python -m src.coordinator.secrets get META_ACCESS_TOKEN
    python -m src.coordinator.secrets list
    python -m src.coordinator.secrets set META_ACCESS_TOKEN <value>
    python -m src.coordinator.secrets set META_ACCESS_TOKEN --from-file /tmp/token.txt

    # In launch.sh (export all secrets for an agent)
    eval $(python -m src.coordinator.secrets export ad-engine)

    # Use Cloudflare Worker backend directly
    python -m src.coordinator.secrets get META_ACCESS_TOKEN --backend worker
"""

from __future__ import annotations

import argparse
import json
import os
import stat
import subprocess
import sys
import urllib.request
import urllib.error
from pathlib import Path
from typing import Any

# --- Constants ---

SECRETS_DIR = Path.home() / ".agent-secrets"
MANIFEST_FILE = Path(__file__).resolve().parent.parent.parent / "secrets-manifest.json"
GCP_PROJECT = "serene-sentinel-487518-c1"

# Cloudflare Worker URLs
WORKER_URL_PROD = "https://secrets-manager.rphants.workers.dev"
WORKER_URL_STAGING = "https://secrets-manager-staging.rphants.workers.dev"
WORKER_URL = os.environ.get("SECRETS_WORKER_URL", WORKER_URL_PROD)

# Agent token file — stores the X-Secret-Token for this agent
AGENT_TOKEN_FILE = SECRETS_DIR / ".agent-token"
BOOTSTRAP_TOKEN_FILE = SECRETS_DIR / ".bootstrap-token"


# --- Manifest ---

def load_manifest() -> dict[str, Any]:
    """Load the secrets manifest defining what each agent needs."""
    if not MANIFEST_FILE.exists():
        return {}
    return json.loads(MANIFEST_FILE.read_text())


def agent_required_secrets(agent: str) -> list[str]:
    """Return the list of secret names an agent needs."""
    manifest = load_manifest()
    agents = manifest.get("agents", {})
    agent_conf = agents.get(agent, {})
    return list(agent_conf.get("secrets", []))


# --- Worker Backend (Cloudflare secrets-manager) ---

def _get_auth_header() -> dict[str, str]:
    """Get the auth header for the Worker. Tries agent token, then bootstrap."""
    # Agent token
    if AGENT_TOKEN_FILE.exists():
        token = AGENT_TOKEN_FILE.read_text().strip()
        return {"X-Secret-Token": token}
    # Bootstrap token (admin)
    if BOOTSTRAP_TOKEN_FILE.exists():
        token = BOOTSTRAP_TOKEN_FILE.read_text().strip()
        return {"X-Bootstrap-Token": token}
    # Env vars
    if os.environ.get("AGENT_SECRET_TOKEN"):
        return {"X-Secret-Token": os.environ["AGENT_SECRET_TOKEN"]}
    if os.environ.get("SECRETS_BOOTSTRAP_TOKEN"):
        return {"X-Bootstrap-Token": os.environ["SECRETS_BOOTSTRAP_TOKEN"]}
    return {}


def _worker_call(
    endpoint: str,
    method: str = "GET",
    data: dict | None = None,
) -> dict | None:
    """Call the secrets-manager Worker API. Returns parsed JSON or None on failure."""
    url = f"{WORKER_URL}/{endpoint}"
    headers = _get_auth_header()
    if not headers:
        return None
    headers["Content-Type"] = "application/json"

    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode())
    except (urllib.error.HTTPError, urllib.error.URLError, OSError, json.JSONDecodeError):
        return None


def get_worker(name: str) -> str | None:
    """Read a secret from the Cloudflare Worker."""
    result = _worker_call(f"secret/{name}")
    if result and "value" in result:
        return result["value"]
    return None


def set_worker(name: str, value: str, **kwargs) -> bool:
    """Write a secret to the Cloudflare Worker (admin only)."""
    data: dict[str, Any] = {"value": value}
    data.update(kwargs)
    result = _worker_call(f"secret/{name}", method="POST", data=data)
    return result is not None and "version_id" in result


def list_worker() -> list[str]:
    """List all secrets from the Cloudflare Worker."""
    result = _worker_call("secrets")
    if result and "secrets" in result:
        return [s["name"] for s in result["secrets"]]
    return []


def register_agent_on_worker(
    agent_id: str,
    allowed_secrets: list[str],
    *,
    agent_name: str | None = None,
    allowed_operations: str = "read,list",
    expires_in_days: int = 90,
) -> dict | None:
    """Register an agent with the Worker and get its access token (admin only)."""
    data = {
        "agent_id": agent_id,
        "allowed_secrets": allowed_secrets,
        "allowed_operations": allowed_operations,
        "expires_in_days": expires_in_days,
    }
    if agent_name:
        data["agent_name"] = agent_name
    return _worker_call("auth/register-agent", method="POST", data=data)


def save_agent_token(token: str) -> None:
    """Save an agent access token locally for future use."""
    _ensure_secrets_dir()
    AGENT_TOKEN_FILE.write_text(token)
    os.chmod(AGENT_TOKEN_FILE, stat.S_IRUSR | stat.S_IWUSR)


def save_bootstrap_token(token: str) -> None:
    """Save the bootstrap token locally for admin operations."""
    _ensure_secrets_dir()
    BOOTSTRAP_TOKEN_FILE.write_text(token)
    os.chmod(BOOTSTRAP_TOKEN_FILE, stat.S_IRUSR | stat.S_IWUSR)


# --- Local Backend ---

def _ensure_secrets_dir() -> Path:
    """Create .agent-secrets/ with restrictive permissions."""
    SECRETS_DIR.mkdir(parents=True, exist_ok=True)
    os.chmod(SECRETS_DIR, stat.S_IRWXU)  # 700 — owner only
    return SECRETS_DIR


def _local_path(name: str) -> Path:
    return SECRETS_DIR / name


def get_local(name: str) -> str | None:
    """Read a secret from local .agent-secrets/ directory."""
    path = _local_path(name)
    if path.exists():
        return path.read_text().strip()
    return None


def set_local(name: str, value: str) -> None:
    """Write a secret to local .agent-secrets/ directory."""
    _ensure_secrets_dir()
    path = _local_path(name)
    path.write_text(value)
    os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)  # 600


def delete_local(name: str) -> bool:
    """Delete a local secret. Returns True if existed."""
    path = _local_path(name)
    if path.exists():
        path.unlink()
        return True
    return False


def list_local() -> list[str]:
    """List all locally stored secret names."""
    if not SECRETS_DIR.exists():
        return []
    return sorted(f.name for f in SECRETS_DIR.iterdir() if f.is_file())


# --- GCP Secret Manager Backend ---

def get_gcp(name: str) -> str | None:
    """Read a secret from GCP Secret Manager."""
    try:
        result = subprocess.run(
            [
                "gcloud", "secrets", "versions", "access", "latest",
                f"--secret={name}",
                f"--project={GCP_PROJECT}",
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=15,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return None


def set_gcp(name: str, value: str) -> bool:
    """Write a secret to GCP Secret Manager. Creates if doesn't exist."""
    try:
        # Try to create the secret first
        subprocess.run(
            [
                "gcloud", "secrets", "create", name,
                "--replication-policy=automatic",
                f"--project={GCP_PROJECT}",
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=15,
        )
        # Add a version with the value
        result = subprocess.run(
            [
                "gcloud", "secrets", "versions", "add", name,
                f"--project={GCP_PROJECT}",
                "--data-file=-",
            ],
            input=value,
            capture_output=True,
            text=True,
            check=False,
            timeout=15,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def list_gcp() -> list[str]:
    """List all secrets in GCP Secret Manager."""
    try:
        result = subprocess.run(
            [
                "gcloud", "secrets", "list",
                f"--project={GCP_PROJECT}",
                "--format=value(name)",
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=15,
        )
        if result.returncode == 0:
            return [line.strip() for line in result.stdout.strip().split("\n") if line.strip()]
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return []


# --- Unified Interface ---

def get_secret(name: str) -> str | None:
    """
    Get a secret by name. Checks in order:
    1. Environment variable
    2. Cloudflare Worker (secrets-manager)
    3. Local .agent-secrets/
    4. GCP Secret Manager
    """
    # 1. Env var (always wins)
    env_val = os.environ.get(name)
    if env_val:
        return env_val

    # 2. Cloudflare Worker
    worker_val = get_worker(name)
    if worker_val:
        return worker_val

    # 3. Local file
    local_val = get_local(name)
    if local_val:
        return local_val

    # 4. GCP Secret Manager
    gcp_val = get_gcp(name)
    if gcp_val:
        return gcp_val

    return None


def set_secret(name: str, value: str, *, backend: str = "worker", **kwargs) -> dict[str, bool]:
    """
    Set a secret. Backend can be 'local', 'gcp', 'worker', or 'all'.
    Returns dict of {backend: success}.
    """
    results = {}
    if backend in ("worker", "all"):
        results["worker"] = set_worker(name, value, **kwargs)
    if backend in ("local", "all"):
        set_local(name, value)
        results["local"] = True
    if backend in ("gcp", "all"):
        results["gcp"] = set_gcp(name, value)
    return results


def list_secrets() -> dict[str, list[str]]:
    """List all secrets from all backends."""
    return {
        "worker": list_worker(),
        "local": list_local(),
        "gcp": list_gcp(),
    }


def export_for_agent(agent: str) -> str:
    """
    Generate shell export statements for all secrets an agent needs.
    Usage in launch.sh: eval $(python -m src.coordinator.secrets export ad-engine)
    """
    required = agent_required_secrets(agent)
    lines = []
    for name in required:
        value = get_secret(name)
        if value:
            # Shell-escape the value
            escaped = value.replace("'", "'\"'\"'")
            lines.append(f"export {name}='{escaped}'")
        else:
            lines.append(f"# WARNING: {name} not found in any backend")
    return "\n".join(lines)


# --- CLI ---

def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="CMUX Secrets Manager")
    sub = parser.add_subparsers(dest="command")

    # get
    get_parser = sub.add_parser("get", help="Get a secret value")
    get_parser.add_argument("name", help="Secret name")

    # set
    set_parser = sub.add_parser("set", help="Set a secret")
    set_parser.add_argument("name", help="Secret name")
    set_parser.add_argument("value", nargs="?", default=None, help="Secret value")
    set_parser.add_argument("--from-file", default=None, help="Read value from file")
    set_parser.add_argument("--backend", default="worker", choices=["local", "gcp", "worker", "all"])
    set_parser.add_argument("--type", default="api_key", help="Secret type")
    set_parser.add_argument("--description", default=None, help="Description")
    set_parser.add_argument("--rotation-strategy", default="manual",
                            choices=["manual", "never", "auto"], help="Rotation strategy")
    set_parser.add_argument("--critical", action="store_true", help="Mark as critical")

    # delete
    del_parser = sub.add_parser("delete", help="Delete a local secret")
    del_parser.add_argument("name", help="Secret name")

    # list
    sub.add_parser("list", help="List all secrets")

    # export
    export_parser = sub.add_parser("export", help="Export secrets for an agent as shell vars")
    export_parser.add_argument("agent", help="Agent name from manifest")

    # check
    check_parser = sub.add_parser("check", help="Check if an agent has all required secrets")
    check_parser.add_argument("agent", help="Agent name from manifest")

    # bootstrap — save bootstrap token for admin operations
    boot_parser = sub.add_parser("bootstrap", help="Save bootstrap token for admin operations")
    boot_parser.add_argument("token", help="Bootstrap token value")

    # register — register an agent with the Worker
    reg_parser = sub.add_parser("register", help="Register an agent with the secrets-manager Worker")
    reg_parser.add_argument("agent", help="Agent ID (e.g. ad-engine)")
    reg_parser.add_argument("--name", default=None, help="Human-readable agent name")
    reg_parser.add_argument("--operations", default="read,list", help="Allowed operations")
    reg_parser.add_argument("--expires-days", type=int, default=90, help="Token expiry in days")

    # save-token — save agent access token
    tok_parser = sub.add_parser("save-token", help="Save agent access token locally")
    tok_parser.add_argument("token", help="Agent access token from register")

    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        sys.exit(1)

    if args.command == "get":
        value = get_secret(args.name)
        if value:
            print(value)
        else:
            print(f"SECRET NOT FOUND: {args.name}", file=sys.stderr)
            sys.exit(1)

    elif args.command == "set":
        if args.from_file:
            value = Path(args.from_file).read_text().strip()
        elif args.value:
            value = args.value
        else:
            print("ERROR: provide value or --from-file", file=sys.stderr)
            sys.exit(1)
        extra: dict[str, Any] = {"type": args.type}
        if args.description:
            extra["description"] = args.description
        extra["rotation_strategy"] = args.rotation_strategy
        extra["is_critical"] = args.critical
        results = set_secret(args.name, value, backend=args.backend, **extra)
        print(json.dumps(results))

    elif args.command == "delete":
        if delete_local(args.name):
            print(f"Deleted: {args.name}")
        else:
            print(f"Not found locally: {args.name}")

    elif args.command == "list":
        secrets = list_secrets()
        print(json.dumps(secrets, indent=2))

    elif args.command == "export":
        print(export_for_agent(args.agent))

    elif args.command == "check":
        required = agent_required_secrets(args.agent)
        if not required:
            print(f"No secrets defined for agent '{args.agent}' in manifest")
            sys.exit(1)
        missing = []
        found = []
        for name in required:
            if get_secret(name):
                found.append(name)
            else:
                missing.append(name)
        print(json.dumps({"agent": args.agent, "found": found, "missing": missing}, indent=2))
        sys.exit(1 if missing else 0)

    elif args.command == "bootstrap":
        save_bootstrap_token(args.token)
        print(f"Bootstrap token saved to {BOOTSTRAP_TOKEN_FILE}")

    elif args.command == "register":
        required = agent_required_secrets(args.agent)
        if not required:
            # Fall back to wildcard
            required = ["*"]
        result = register_agent_on_worker(
            agent_id=args.agent,
            allowed_secrets=required,
            agent_name=args.name,
            allowed_operations=args.operations,
            expires_in_days=args.expires_days,
        )
        if result and "access_token" in result:
            print(json.dumps(result, indent=2))
            print(f"\nSave this token: python -m src.coordinator.secrets save-token '{result['access_token']}'")
        else:
            print(f"Registration failed: {result}", file=sys.stderr)
            sys.exit(1)

    elif args.command == "save-token":
        save_agent_token(args.token)
        print(f"Agent token saved to {AGENT_TOKEN_FILE}")


if __name__ == "__main__":
    main()
