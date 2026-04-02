#!/usr/bin/env python3
"""Preflight checks for the Ad Creative Engine runtime."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import requests

AGENT_DIR = Path(__file__).resolve().parent
REPO_DIR = AGENT_DIR.parent.parent
CONFIG_PATH = AGENT_DIR / "config.json"
KNOWLEDGE_MANIFEST_PATH = REPO_DIR / "knowledge-manifest.json"

sys.path.insert(0, str(REPO_DIR))
from src.coordinator.secrets import get_secret  # noqa: E402

REQUIRED_CORPORA = {
    "claudepy",
    "canva_connect",
    "figma",
    "google_stitch",
    "meta_ads",
}


def command_status(argv: list[str], timeout: int = 15) -> dict[str, Any]:
    try:
        result = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout,
        )
    except FileNotFoundError:
        return {"ok": False, "stdout": "", "stderr": f"{argv[0]} not installed", "returncode": 127}
    except subprocess.TimeoutExpired:
        return {"ok": False, "stdout": "", "stderr": "command timed out", "returncode": 124}

    return {
        "ok": result.returncode == 0,
        "stdout": result.stdout.strip(),
        "stderr": result.stderr.strip(),
        "returncode": result.returncode,
    }


def secret_present(name: str) -> bool:
    return bool(get_secret(name))


def file_present(path: Path) -> bool:
    return path.exists() and path.is_file()


def module_present(name: str) -> bool:
    return importlib.util.find_spec(name) is not None


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text())


def google_stitch_status() -> dict[str, Any]:
    script_path = AGENT_DIR / "stitch_api.py"
    status: dict[str, Any] = {
        "script_present": file_present(script_path),
        "ready": False,
    }
    if not status["script_present"]:
        status["error"] = "stitch_api.py missing"
        return status

    result = command_status([sys.executable, str(script_path), "healthcheck"], timeout=30)
    if not result["ok"] or not result["stdout"]:
        status["error"] = result["stderr"] or "stitch healthcheck failed"
        return status

    try:
        payload = json.loads(result["stdout"])
    except json.JSONDecodeError:
        status["error"] = "stitch healthcheck returned invalid JSON"
        status["raw_output"] = result["stdout"]
        return status

    status.update(
        {
            "ready": bool(payload.get("ready")),
            "configured_project_id": payload.get("configured_project_id"),
            "gcloud_active_account": payload.get("gcloud_active_account"),
            "gcloud_active_project": payload.get("gcloud_active_project"),
            "access_token_ready": payload.get("access_token_ready"),
            "access_token_error": payload.get("access_token_error"),
            "project_access_ready": payload.get("project_access_ready"),
            "project_access_error": payload.get("project_access_error"),
        }
    )
    return status


def local_gpu_scene_status() -> dict[str, Any]:
    script_path = AGENT_DIR / "local_gpu_scene.py"
    status: dict[str, Any] = {
        "script_present": file_present(script_path),
        "ready": False,
    }
    if not status["script_present"]:
        status["error"] = "local_gpu_scene.py missing"
        return status

    result = command_status([sys.executable, str(script_path), "healthcheck"], timeout=30)
    if not result["ok"] or not result["stdout"]:
        status["error"] = result["stderr"] or "local GPU scene healthcheck failed"
        return status

    try:
        payload = json.loads(result["stdout"])
    except json.JSONDecodeError:
        status["error"] = "local GPU scene healthcheck returned invalid JSON"
        status["raw_output"] = result["stdout"]
        return status

    status.update(payload)
    status["ready"] = bool(payload.get("ready"))
    return status


def meta_status(config: dict[str, Any]) -> dict[str, Any]:
    status: dict[str, Any] = {
        "script_present": file_present(AGENT_DIR / "meta_ads.py"),
        "token_present": secret_present("META_ACCESS_TOKEN"),
        "ready": False,
    }
    if not status["script_present"]:
        status["error"] = "meta_ads.py missing"
        return status
    if not status["token_present"]:
        status["error"] = "META_ACCESS_TOKEN missing"
        return status

    token = get_secret("META_ACCESS_TOKEN")
    ad_account = config.get("meta", {}).get("ad_account")
    if not token or not ad_account:
        status["error"] = "Meta token or ad account config missing"
        return status

    try:
        resp = requests.get(
            f"https://graph.facebook.com/v21.0/{ad_account}",
            params={"fields": "id,name,account_status", "access_token": token},
            timeout=20,
        )
        payload = resp.json()
    except Exception as exc:
        status["error"] = f"Meta healthcheck failed: {exc}"
        return status

    if resp.status_code == 200:
        status.update(
            {
                "ready": True,
                "account_id": payload.get("id"),
                "account_name": payload.get("name"),
                "account_status": payload.get("account_status"),
            }
        )
        return status

    error = payload.get("error", {})
    status["error"] = error.get("message") or f"HTTP {resp.status_code}"
    status["error_code"] = error.get("code")
    status["error_subcode"] = error.get("error_subcode")
    return status


def build_report(mode: str) -> dict[str, Any]:
    config = load_json(CONFIG_PATH)
    knowledge_manifest = load_json(KNOWLEDGE_MANIFEST_PATH)
    stitch = google_stitch_status()
    local_gpu_scene = local_gpu_scene_status()
    meta = meta_status(config)
    scene_provider = os.environ.get("AD_SCENE_PROVIDER", "google_stitch").strip().lower()

    gcloud_account = command_status(
        ["gcloud", "auth", "list", "--filter=status:ACTIVE", "--format=value(account)"]
    )
    gcloud_project = command_status(["gcloud", "config", "get-value", "project"])
    gcloud_token = command_status(["gcloud", "auth", "print-access-token"])

    secrets = {
        "ANTHROPIC_API_KEY": secret_present("ANTHROPIC_API_KEY"),
        "META_ACCESS_TOKEN": secret_present("META_ACCESS_TOKEN"),
        "CANVA_CLIENT_ID": secret_present("CANVA_CLIENT_ID"),
        "CANVA_CLIENT_SECRET": secret_present("CANVA_CLIENT_SECRET"),
        "CANVA_REFRESH_TOKEN": secret_present("CANVA_REFRESH_TOKEN"),
        "FIGMA_ACCESS_TOKEN": secret_present("FIGMA_ACCESS_TOKEN"),
        "GOOGLE_STITCH_PROJECT_ID": secret_present("GOOGLE_STITCH_PROJECT_ID"),
        "SLACK_WEBHOOK_URL": secret_present("SLACK_WEBHOOK_URL"),
    }

    tooling = {
        "claude_cli": bool(shutil.which("claude")),
        "ffmpeg": bool(shutil.which("ffmpeg")),
        "nvidia_smi": bool(shutil.which("nvidia-smi")),
        "pillow": module_present("PIL"),
        "gcloud": bool(shutil.which("gcloud")),
        "gcloud_active_account": gcloud_account["stdout"] or None,
        "gcloud_active_project": (
            gcloud_project["stdout"] if gcloud_project["ok"] and gcloud_project["stdout"] != "(unset)" else None
        ),
        "gcloud_access_token_ready": gcloud_token["ok"] and bool(gcloud_token["stdout"]),
        "gcloud_access_token_error": None if gcloud_token["ok"] else (gcloud_token["stderr"] or None),
    }

    providers = {
        "creative_generator": {
            "script_present": file_present(AGENT_DIR / "creative_generator.py"),
            "ready": file_present(AGENT_DIR / "creative_generator.py") and tooling["pillow"],
        },
        "video_composer": {
            "script_present": file_present(AGENT_DIR / "video_composer.py"),
            "ready": file_present(AGENT_DIR / "video_composer.py") and tooling["ffmpeg"],
        },
        "claudepy": {
            "script_present": tooling["claude_cli"],
            "ready": tooling["claude_cli"] and secrets["ANTHROPIC_API_KEY"],
        },
        "canva_connect": {
            "script_present": file_present(AGENT_DIR / "canva_api.py"),
            "ready": (
                file_present(AGENT_DIR / "canva_api.py")
                and secrets["CANVA_CLIENT_ID"]
                and secrets["CANVA_CLIENT_SECRET"]
                and secrets["CANVA_REFRESH_TOKEN"]
            ),
        },
        "figma": {
            "script_present": file_present(AGENT_DIR / "figma_api.py"),
            "ready": file_present(AGENT_DIR / "figma_api.py") and secrets["FIGMA_ACCESS_TOKEN"],
        },
        "google_stitch": stitch,
        "local_gpu_scene": local_gpu_scene,
        "meta_ads": {
            **meta,
        },
        "slack": {
            "script_present": True,
            "ready": secrets["SLACK_WEBHOOK_URL"],
        },
    }

    required_corpora = {
        item.get("id")
        for item in knowledge_manifest.get("required_corpora", [])
        if isinstance(item, dict)
    }
    docs = {
        "manifest_present": KNOWLEDGE_MANIFEST_PATH.exists(),
        "required_corpora_present": sorted(required_corpora),
        "required_corpora_complete": REQUIRED_CORPORA.issubset(required_corpora),
        "first_party_corpora_present": bool(knowledge_manifest.get("first_party_corpora")),
    }

    blockers: list[str] = []
    warnings: list[str] = []

    def require(condition: bool, message: str) -> None:
        if not condition:
            blockers.append(message)

    def warn(condition: bool, message: str) -> None:
        if not condition:
            warnings.append(message)

    if mode == "creatives":
        require(providers["creative_generator"]["ready"], "Local creative generation is not ready.")
        if scene_provider in {"local_gpu", "local-gpu", "gpu"}:
            require(providers["local_gpu_scene"]["ready"], "Local GPU scene generation is not ready.")
        warn(providers["canva_connect"]["ready"], "Canva Connect is not wired for polished export workflows.")
        warn(providers["figma"]["ready"], "Figma runtime access is missing.")
        warn(providers["google_stitch"]["ready"], "Google Stitch / Vertex runtime is missing.")
        warn(providers["video_composer"]["ready"], "Video composer is not ready; ffmpeg is missing.")
    elif mode == "deploy":
        require(providers["meta_ads"]["ready"], "Meta deployment is blocked because META runtime auth is invalid.")
    elif mode == "full":
        require(providers["creative_generator"]["ready"], "Local creative generation is not ready.")
        if scene_provider in {"local_gpu", "local-gpu", "gpu"}:
            require(providers["local_gpu_scene"]["ready"], "Local GPU scene generation is not ready.")
        require(providers["claudepy"]["ready"], "ClaudePY runtime is not ready (missing CLI or ANTHROPIC_API_KEY).")
        warn(providers["meta_ads"]["ready"], "Meta deployment is still offline.")
        warn(providers["canva_connect"]["ready"], "Canva Connect is not fully wired.")
        warn(providers["figma"]["ready"], "Figma runtime access is not wired.")
        warn(providers["google_stitch"]["ready"], "Google Stitch / Vertex runtime is not wired.")
        warn(providers["video_composer"]["ready"], "Video composer is not ready; ffmpeg is missing.")
        warn(providers["slack"]["ready"], "Slack alerting is not configured.")
        warn(docs["required_corpora_complete"], "Knowledge manifest is missing one or more required corpora.")
    elif mode == "production":
        require(providers["creative_generator"]["ready"], "Local creative generation is not ready.")
        if scene_provider in {"local_gpu", "local-gpu", "gpu"}:
            require(providers["local_gpu_scene"]["ready"], "Local GPU scene generation is not ready.")
        require(providers["claudepy"]["ready"], "ClaudePY runtime is not ready.")
        require(providers["meta_ads"]["ready"], "Meta deployment is not ready.")
        require(providers["canva_connect"]["ready"], "Canva Connect runtime is not ready.")
        require(providers["figma"]["ready"], "Figma runtime is not ready.")
        require(providers["google_stitch"]["ready"], "Google Stitch / Vertex runtime is not ready.")
        require(providers["video_composer"]["ready"], "Video composer is not ready.")
        require(providers["slack"]["ready"], "Slack alerting is not ready.")
        require(docs["manifest_present"], "knowledge-manifest.json is missing.")
        require(docs["required_corpora_complete"], "The knowledge manifest is missing required corpora.")
        require(docs["first_party_corpora_present"], "First-party brand context is missing from the knowledge manifest.")
    else:
        raise ValueError(f"Unsupported mode: {mode}")

    stitch_project = secrets["GOOGLE_STITCH_PROJECT_ID"]
    if stitch_project and tooling["gcloud_active_project"]:
        configured_project = get_secret("GOOGLE_STITCH_PROJECT_ID")
        active_project = tooling["gcloud_active_project"]
        if configured_project and active_project and configured_project != active_project:
            warnings.append(
                "The active gcloud project does not match GOOGLE_STITCH_PROJECT_ID."
            )
    if stitch_project and not providers["google_stitch"]["ready"]:
        stitch_error = providers["google_stitch"].get("project_access_error") or providers["google_stitch"].get(
            "access_token_error"
        )
        if stitch_error:
            warnings.append(f"Google Stitch healthcheck failed: {stitch_error}")
    if scene_provider in {"local_gpu", "local-gpu", "gpu"} and not providers["local_gpu_scene"]["ready"]:
        local_gpu_error = providers["local_gpu_scene"].get("error")
        if local_gpu_error:
            warnings.append(f"Local GPU scene healthcheck failed: {local_gpu_error}")

    if tooling["gcloud"] and not tooling["gcloud_access_token_ready"]:
        warnings.append(
            "gcloud is installed but cannot mint an access token non-interactively. "
            "Run gcloud auth login and gcloud auth application-default login."
        )
    if providers["meta_ads"].get("error"):
        warnings.append(f"Meta healthcheck failed: {providers['meta_ads']['error']}")

    creative_stack = config.get("creative_stack", {})
    if creative_stack.get("must_self_generate_ads") is not True:
        warnings.append("config.json does not declare ad-engine self-generation ownership.")

    report = {
        "mode": mode,
        "config": {
            "creative_stack_owner": creative_stack.get("owner"),
            "creative_stack_providers": creative_stack.get("providers", []),
            "must_self_generate_ads": creative_stack.get("must_self_generate_ads"),
            "scene_provider": scene_provider,
        },
        "secrets": secrets,
        "tooling": tooling,
        "providers": providers,
        "docs": docs,
        "summary": {
            "blockers": blockers,
            "warnings": warnings,
            "offline_ready": providers["creative_generator"]["ready"],
            "full_loop_ready": providers["creative_generator"]["ready"] and providers["claudepy"]["ready"],
            "production_ready": not blockers and mode == "production",
        },
    }
    return report


def print_human(report: dict[str, Any]) -> None:
    summary = report["summary"]
    print(f"Preflight mode: {report['mode']}")
    print(f"Offline creative ready: {'yes' if summary['offline_ready'] else 'no'}")
    print(f"Full loop ready: {'yes' if summary['full_loop_ready'] else 'no'}")
    if report["mode"] == "production":
        print(f"Production ready: {'yes' if summary['production_ready'] else 'no'}")

    if summary["blockers"]:
        print("Blockers:")
        for blocker in summary["blockers"]:
            print(f"  - {blocker}")

    if summary["warnings"]:
        print("Warnings:")
        for warning in summary["warnings"]:
            print(f"  - {warning}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Ad Creative Engine preflight checks")
    parser.add_argument(
        "--mode",
        default="production",
        choices=["creatives", "deploy", "full", "production"],
        help="Readiness target to validate",
    )
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON")
    args = parser.parse_args()

    report = build_report(args.mode)
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print_human(report)

    sys.exit(1 if report["summary"]["blockers"] else 0)


if __name__ == "__main__":
    main()
