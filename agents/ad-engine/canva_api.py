#!/usr/bin/env python3
"""Canva Connect API integration for the Ad Creative Engine.

Creates ad creatives programmatically via Canva's API.
Requires CANVA_API_KEY env var.

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
    1. Go to https://www.canva.dev/docs/connect/quick-start/
    2. Create a Canva Connect app
    3. Get API key from app settings
    4. python -m src.coordinator.secrets set CANVA_API_KEY <your-key>
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.request
import urllib.parse
import urllib.error
from pathlib import Path
from typing import Any

BASE_URL = "https://api.canva.com/rest/v1"


def get_api_key() -> str:
    key = os.environ.get("CANVA_API_KEY")
    if not key:
        # Try secrets manager
        try:
            sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
            from src.coordinator.secrets import get_secret
            key = get_secret("CANVA_API_KEY")
        except Exception:
            pass
    if not key:
        print("ERROR: CANVA_API_KEY not set.", file=sys.stderr)
        print("Setup: python -m src.coordinator.secrets set CANVA_API_KEY <key>", file=sys.stderr)
        sys.exit(1)
    return key


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
        "Authorization": f"Bearer {get_api_key()}",
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
