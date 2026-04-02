#!/usr/bin/env python3
"""Canva Connect API integration for the Ad Creative Engine.

Creates ad creatives programmatically via Canva's Connect API.
Runtime auth supports either:
    - CANVA_ACCESS_TOKEN for short-lived manual testing, or
    - CANVA_CLIENT_ID + CANVA_CLIENT_SECRET + CANVA_REFRESH_TOKEN for
      automatic access-token refresh.

Capabilities:
    - Create designs from templates
    - Autofill templates with ad copy
    - Export designs as PNG/JPG for Meta Ads
    - Search existing designs
    - List available templates

Usage:
    python canva_api.py list-templates
    python canva_api.py create --template-id <id> --data '{"headline": "Stop Cold Calling"}'
    python canva_api.py export --design-id <id> --format png --output /tmp/ad-creative.png
    python canva_api.py search --query "facebook ad"

Setup:
    1. Enable MFA on the Canva account creating the integration.
    2. Create a Canva Connect integration at https://www.canva.com/developers/integrations
    3. Save the Client ID and generate a Client Secret.
    4. Complete OAuth once to obtain a refresh token.
    5. Store CANVA_CLIENT_ID, CANVA_CLIENT_SECRET, and CANVA_REFRESH_TOKEN.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import time
import urllib.parse
import urllib.request
import urllib.error
from pathlib import Path
from typing import Any

BASE_URL = "https://api.canva.com/rest/v1"
TOKEN_URL = f"{BASE_URL}/oauth/token"
TOKEN_REFRESH_SKEW_SECONDS = 60
_TOKEN_CACHE: dict[str, Any] = {"access_token": None, "expires_at": 0.0}


def get_secret_value(name: str) -> str | None:
    """Read a secret from env vars first, then the shared secrets backend."""
    value = os.environ.get(name)
    if value:
        return value

    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
        from src.coordinator.secrets import get_secret
        return get_secret(name)
    except Exception:
        return None


def fail_missing_auth() -> "NoReturn":
    print("ERROR: Canva credentials not set.", file=sys.stderr)
    print(
        "Set CANVA_ACCESS_TOKEN for temporary testing, or store "
        "CANVA_CLIENT_ID, CANVA_CLIENT_SECRET, and CANVA_REFRESH_TOKEN.",
        file=sys.stderr,
    )
    print(
        "Setup docs: https://www.canva.dev/docs/connect/authentication/",
        file=sys.stderr,
    )
    sys.exit(1)


def persist_rotated_refresh_token(refresh_token: str) -> None:
    """Best-effort persistence when Canva rotates the refresh token."""
    os.environ["CANVA_REFRESH_TOKEN"] = refresh_token
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
        from src.coordinator.secrets import set_worker

        if set_worker("CANVA_REFRESH_TOKEN", refresh_token):
            return
    except Exception:
        pass

    print(
        "WARNING: Canva rotated the refresh token, but it could not be "
        "persisted to the shared secrets backend. Update CANVA_REFRESH_TOKEN "
        "manually before the next run.",
        file=sys.stderr,
    )


def refresh_access_token(
    client_id: str,
    client_secret: str,
    refresh_token: str,
) -> dict[str, Any]:
    """Exchange a refresh token for a short-lived access token."""
    credentials = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
    body = urllib.parse.urlencode({
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
    }).encode()
    headers = {
        "Authorization": f"Basic {credentials}",
        "Content-Type": "application/x-www-form-urlencoded",
    }
    req = urllib.request.Request(TOKEN_URL, data=body, headers=headers, method="POST")

    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        error_body = e.read().decode()
        print(f"Canva OAuth Error {e.code}: {error_body}", file=sys.stderr)
        raise


def get_access_token() -> str:
    """Return a valid access token, refreshing it when credentials allow."""
    direct_token = get_secret_value("CANVA_ACCESS_TOKEN")
    if direct_token:
        return direct_token

    now = time.time()
    cached_token = _TOKEN_CACHE.get("access_token")
    expires_at = float(_TOKEN_CACHE.get("expires_at") or 0)
    if cached_token and now < expires_at - TOKEN_REFRESH_SKEW_SECONDS:
        return str(cached_token)

    client_id = get_secret_value("CANVA_CLIENT_ID")
    client_secret = get_secret_value("CANVA_CLIENT_SECRET")
    refresh_token = get_secret_value("CANVA_REFRESH_TOKEN")
    if not (client_id and client_secret and refresh_token):
        fail_missing_auth()

    token_response = refresh_access_token(client_id, client_secret, refresh_token)
    access_token = token_response.get("access_token")
    if not access_token:
        print(f"ERROR: Canva token response missing access_token: {token_response}", file=sys.stderr)
        sys.exit(1)

    expires_in = int(token_response.get("expires_in") or 0)
    _TOKEN_CACHE["access_token"] = access_token
    _TOKEN_CACHE["expires_at"] = now + expires_in if expires_in > 0 else now + 300

    rotated_refresh_token = token_response.get("refresh_token")
    if rotated_refresh_token and rotated_refresh_token != refresh_token:
        persist_rotated_refresh_token(rotated_refresh_token)

    return str(access_token)


def api_call(
    endpoint: str,
    method: str = "GET",
    data: dict | None = None,
    params: dict | None = None,
) -> dict[str, Any]:
    """Make a Canva API call."""
    url = f"{BASE_URL}/{endpoint}"
    if params:
        url += "?" + urllib.parse.urlencode(params)

    headers = {
        "Authorization": f"Bearer {get_access_token()}",
        "Content-Type": "application/json",
    }

    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)

    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        error_body = e.read().decode()
        print(f"Canva API Error {e.code}: {error_body}", file=sys.stderr)
        raise


# --- Design Operations ---

def search_designs(query: str, limit: int = 10) -> dict:
    """Search existing designs."""
    return api_call("designs", params={"query": query, "limit": str(limit)})


def create_design_from_template(
    template_id: str,
    title: str = "AgentRVM Ad Creative",
) -> dict:
    """Create a new design from a Canva template."""
    return api_call("designs", method="POST", data={
        "design_type": {"type": "preset", "name": "doc"},
        "asset_id": template_id,
        "title": title,
    })


def autofill_design(design_id: str, data: dict[str, str]) -> dict:
    """Autofill a design's template fields with data."""
    return api_call(f"autofill/create", method="POST", data={
        "brand_template_id": design_id,
        "data": {k: {"type": "text", "text": v} for k, v in data.items()},
    })


def export_design(design_id: str, format: str = "png") -> dict:
    """Start an export job for a design."""
    result = api_call(f"designs/{design_id}/exports", method="POST", data={
        "format": {"type": format},
    })
    return result


def get_export_status(export_id: str) -> dict:
    """Check export job status."""
    return api_call(f"exports/{export_id}")


def export_and_download(design_id: str, output_path: str, format: str = "png") -> str:
    """Export a design and download the result."""
    # Start export
    export_result = export_design(design_id, format)
    export_id = export_result.get("job", {}).get("id") or export_result.get("id")

    if not export_id:
        print(f"Export started but no job ID returned: {export_result}", file=sys.stderr)
        return ""

    # Poll for completion
    for _ in range(30):
        status = get_export_status(export_id)
        state = status.get("job", {}).get("status") or status.get("status")
        if state == "success":
            urls = status.get("job", {}).get("urls") or status.get("urls", [])
            if urls:
                download_url = urls[0] if isinstance(urls, list) else urls
                # Download
                urllib.request.urlretrieve(download_url, output_path)
                print(f"Exported to: {output_path}")
                return output_path
        elif state == "failed":
            print(f"Export failed: {status}", file=sys.stderr)
            return ""
        time.sleep(2)

    print("Export timed out after 60s", file=sys.stderr)
    return ""


# --- CLI ---

def main():
    parser = argparse.ArgumentParser(description="Canva API for Ad Creative Engine")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("list-templates")

    search_p = sub.add_parser("search")
    search_p.add_argument("--query", required=True)

    create_p = sub.add_parser("create")
    create_p.add_argument("--template-id", required=True)
    create_p.add_argument("--title", default="AgentRVM Ad Creative")

    autofill_p = sub.add_parser("autofill")
    autofill_p.add_argument("--design-id", required=True)
    autofill_p.add_argument("--data", required=True, help="JSON string of field:value pairs")

    export_p = sub.add_parser("export")
    export_p.add_argument("--design-id", required=True)
    export_p.add_argument("--format", default="png", choices=["png", "jpg", "pdf"])
    export_p.add_argument("--output", required=True)

    args = parser.parse_args()

    if args.command == "search":
        result = search_designs(args.query)
        print(json.dumps(result, indent=2))
    elif args.command == "create":
        result = create_design_from_template(args.template_id, args.title)
        print(json.dumps(result, indent=2))
    elif args.command == "autofill":
        data = json.loads(args.data)
        result = autofill_design(args.design_id, data)
        print(json.dumps(result, indent=2))
    elif args.command == "export":
        export_and_download(args.design_id, args.output, args.format)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
