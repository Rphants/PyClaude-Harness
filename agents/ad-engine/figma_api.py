#!/usr/bin/env python3
"""Figma REST API integration for the Ad Creative Engine.

Reads design context, screenshots, and design system rules from Figma.
Requires FIGMA_ACCESS_TOKEN env var.

Capabilities:
    - Get file/frame metadata
    - Export frames as PNG/SVG/PDF
    - Read design tokens (colors, typography, spacing)
    - Get component screenshots for reference

Usage:
    python figma_api.py get-file --file-key <key>
    python figma_api.py export --file-key <key> --node-id <id> --format png --output /tmp/frame.png
    python figma_api.py get-styles --file-key <key>
    python figma_api.py get-components --file-key <key>

Setup:
    1. Go to Figma > Settings > Account > Personal access tokens
    2. Generate a token
    3. python -m src.coordinator.secrets set FIGMA_ACCESS_TOKEN <your-token>
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.request
import urllib.parse
import urllib.error
from pathlib import Path
from typing import Any

from http_utils import urlopen

BASE_URL = "https://api.figma.com/v1"


def get_token() -> str:
    token = os.environ.get("FIGMA_ACCESS_TOKEN")
    if not token:
        try:
            sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
            from src.coordinator.secrets import get_secret
            token = get_secret("FIGMA_ACCESS_TOKEN")
        except Exception:
            pass
    if not token:
        print("ERROR: FIGMA_ACCESS_TOKEN not set.", file=sys.stderr)
        print("Setup: python -m src.coordinator.secrets set FIGMA_ACCESS_TOKEN <token>", file=sys.stderr)
        sys.exit(1)
    return token


def api_call(endpoint: str, params: dict | None = None) -> dict[str, Any]:
    """Make a Figma API call."""
    url = f"{BASE_URL}/{endpoint}"
    if params:
        url += "?" + urllib.parse.urlencode(params)

    headers = {"X-Figma-Token": get_token()}
    req = urllib.request.Request(url, headers=headers)

    try:
        with urlopen(req) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        error_body = e.read().decode()
        print(f"Figma API Error {e.code}: {error_body}", file=sys.stderr)
        raise


# --- File Operations ---

def get_file(file_key: str, depth: int = 2) -> dict:
    """Get Figma file structure."""
    return api_call(f"files/{file_key}", params={"depth": str(depth)})


def get_file_nodes(file_key: str, node_ids: list[str]) -> dict:
    """Get specific nodes from a Figma file."""
    ids = ",".join(node_ids)
    return api_call(f"files/{file_key}/nodes", params={"ids": ids})


def get_images(file_key: str, node_ids: list[str], format: str = "png", scale: int = 2) -> dict:
    """Export nodes as images. Returns URLs."""
    ids = ",".join(node_ids)
    return api_call(f"images/{file_key}", params={
        "ids": ids,
        "format": format,
        "scale": str(scale),
    })


def export_and_download(file_key: str, node_id: str, output_path: str, format: str = "png") -> str:
    """Export a node and download it."""
    result = get_images(file_key, [node_id], format=format)
    images = result.get("images", {})
    url = images.get(node_id)
    if url:
        with urlopen(url) as resp:
            Path(output_path).write_bytes(resp.read())
        print(f"Exported to: {output_path}")
        return output_path
    else:
        print(f"No image URL for node {node_id}: {result}", file=sys.stderr)
        return ""


# --- Design System ---

def get_styles(file_key: str) -> dict:
    """Get published styles (colors, text, effects) from a file."""
    return api_call(f"files/{file_key}/styles")


def get_components(file_key: str) -> dict:
    """Get published components from a file."""
    return api_call(f"files/{file_key}/components")


def extract_colors(file_data: dict) -> list[dict]:
    """Extract color styles from a Figma file response."""
    colors = []
    styles = file_data.get("styles", {})
    for style_id, style_info in styles.items():
        if style_info.get("styleType") == "FILL":
            colors.append({
                "name": style_info.get("name"),
                "key": style_info.get("key"),
                "description": style_info.get("description", ""),
            })
    return colors


# --- CLI ---

def main():
    parser = argparse.ArgumentParser(description="Figma API for Ad Creative Engine")
    sub = parser.add_subparsers(dest="command")

    gf = sub.add_parser("get-file")
    gf.add_argument("--file-key", required=True)
    gf.add_argument("--depth", type=int, default=2)

    ex = sub.add_parser("export")
    ex.add_argument("--file-key", required=True)
    ex.add_argument("--node-id", required=True)
    ex.add_argument("--format", default="png", choices=["png", "svg", "pdf", "jpg"])
    ex.add_argument("--output", required=True)

    gs = sub.add_parser("get-styles")
    gs.add_argument("--file-key", required=True)

    gc = sub.add_parser("get-components")
    gc.add_argument("--file-key", required=True)

    args = parser.parse_args()

    if args.command == "get-file":
        result = get_file(args.file_key, args.depth)
        print(json.dumps(result, indent=2))
    elif args.command == "export":
        export_and_download(args.file_key, args.node_id, args.output, args.format)
    elif args.command == "get-styles":
        result = get_styles(args.file_key)
        print(json.dumps(result, indent=2))
    elif args.command == "get-components":
        result = get_components(args.file_key)
        print(json.dumps(result, indent=2))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
