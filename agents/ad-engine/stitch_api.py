#!/usr/bin/env python3
"""Google Stitch / Vertex AI image generation for the Ad Creative Engine.

The current "Stitch" runtime path is implemented through Vertex AI image
generation so the ad-engine has a Google-native creative fallback when Canva
or Figma are unavailable.

Docs reference:
  - https://cloud.google.com/vertex-ai/generative-ai/docs/image/generate-images
  - https://cloud.google.com/vertex-ai/generative-ai/docs/model-reference/imagen-api
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from http_utils import urlopen

AGENT_DIR = Path(__file__).resolve().parent
REPO_DIR = AGENT_DIR.parent.parent
DEFAULT_LOCATION = os.environ.get("GOOGLE_STITCH_LOCATION", "us-central1")
DEFAULT_MODEL = os.environ.get("GOOGLE_STITCH_MODEL", "imagen-4.0-fast-generate-001")


def get_secret_value(name: str) -> str | None:
    value = os.environ.get(name)
    if value:
        return value

    try:
        sys.path.insert(0, str(REPO_DIR))
        from src.coordinator.secrets import get_secret

        return get_secret(name)
    except Exception:
        return None


def get_project_id() -> str | None:
    for name in ("GOOGLE_STITCH_PROJECT_ID", "GOOGLE_CLOUD_PROJECT"):
        value = get_secret_value(name)
        if value:
            return value

    if shutil.which("gcloud"):
        result = subprocess.run(
            ["gcloud", "config", "get-value", "project"],
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
        project_id = result.stdout.strip()
        if result.returncode == 0 and project_id and project_id != "(unset)":
            return project_id
    return None


def get_access_token() -> str:
    env_token = os.environ.get("GOOGLE_OAUTH_ACCESS_TOKEN")
    if env_token:
        return env_token

    if not shutil.which("gcloud"):
        print("ERROR: gcloud CLI is not installed.", file=sys.stderr)
        sys.exit(1)

    result = subprocess.run(
        ["gcloud", "auth", "print-access-token"],
        capture_output=True,
        text=True,
        check=False,
        timeout=15,
    )
    token = result.stdout.strip()
    if result.returncode != 0 or not token:
        detail = result.stderr.strip() or "gcloud could not mint an access token."
        print(f"ERROR: {detail}", file=sys.stderr)
        print(
            "Setup: run `gcloud auth login` and, for local development, "
            "`gcloud auth application-default login`.",
            file=sys.stderr,
        )
        sys.exit(1)
    return token


def api_call(
    *,
    project_id: str,
    location: str,
    model: str,
    prompt: str,
    aspect_ratio: str = "1:1",
    sample_count: int = 1,
    enhance_prompt: bool = True,
) -> dict[str, Any]:
    url = (
        f"https://{location}-aiplatform.googleapis.com/v1/projects/"
        f"{project_id}/locations/{location}/publishers/google/models/{model}:predict"
    )
    payload = {
        "instances": [{"prompt": prompt}],
        "parameters": {
            "sampleCount": sample_count,
            "aspectRatio": aspect_ratio,
            "enhancePrompt": enhance_prompt,
        },
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        headers={
            "Authorization": f"Bearer {get_access_token()}",
            "Content-Type": "application/json; charset=utf-8",
        },
        method="POST",
    )
    try:
        with urlopen(req, timeout=90) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode()
        print(f"Vertex API Error {exc.code}: {error_body}", file=sys.stderr)
        raise


def save_predictions(response: dict[str, Any], output: str) -> list[str]:
    predictions = response.get("predictions", [])
    if not predictions:
        print(f"ERROR: No predictions returned: {response}", file=sys.stderr)
        sys.exit(1)

    output_path = Path(output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    saved_paths: list[str] = []
    for index, prediction in enumerate(predictions, start=1):
        encoded = prediction.get("bytesBase64Encoded")
        if not encoded:
            continue

        target = output_path
        if len(predictions) > 1:
            target = output_path.with_name(
                f"{output_path.stem}-{index}{output_path.suffix or '.png'}"
            )
        elif not target.suffix:
            target = target.with_suffix(".png")

        target.write_bytes(base64.b64decode(encoded))
        saved_paths.append(str(target))

    if not saved_paths:
        print(f"ERROR: Response did not include image bytes: {response}", file=sys.stderr)
        sys.exit(1)
    return saved_paths


def healthcheck() -> dict[str, Any]:
    project_id = get_project_id()
    gcloud_path = shutil.which("gcloud")
    active_account = None
    project_from_gcloud = None
    token_ok = False
    token_error = None
    project_access_ok = False
    project_access_error = None

    if gcloud_path:
        account_result = subprocess.run(
            ["gcloud", "auth", "list", "--filter=status:ACTIVE", "--format=value(account)"],
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
        active_account = account_result.stdout.strip() or None

        project_result = subprocess.run(
            ["gcloud", "config", "get-value", "project"],
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
        value = project_result.stdout.strip()
        if project_result.returncode == 0 and value and value != "(unset)":
            project_from_gcloud = value

        token_result = subprocess.run(
            ["gcloud", "auth", "print-access-token"],
            capture_output=True,
            text=True,
            check=False,
            timeout=15,
        )
        token_ok = token_result.returncode == 0 and bool(token_result.stdout.strip())
        token_error = None if token_ok else (token_result.stderr.strip() or "token mint failed")

        if project_id:
            access_result = subprocess.run(
                [
                    "gcloud",
                    "services",
                    "list",
                    "--enabled",
                    f"--project={project_id}",
                    "--filter=name:aiplatform.googleapis.com",
                    "--format=value(name)",
                ],
                capture_output=True,
                text=True,
                check=False,
                timeout=20,
            )
            project_access_ok = access_result.returncode == 0 and "aiplatform.googleapis.com" in access_result.stdout
            project_access_error = None if project_access_ok else (
                access_result.stderr.strip() or "Vertex AI API unavailable or inaccessible for project"
            )

    return {
        "provider": "google_stitch",
        "configured_project_id": project_id,
        "default_location": DEFAULT_LOCATION,
        "default_model": DEFAULT_MODEL,
        "gcloud_installed": bool(gcloud_path),
        "gcloud_active_account": active_account,
        "gcloud_active_project": project_from_gcloud,
        "access_token_ready": token_ok,
        "access_token_error": token_error,
        "project_access_ready": project_access_ok,
        "project_access_error": project_access_error,
        "ready": bool(project_id and gcloud_path and token_ok and project_access_ok),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Google Stitch / Vertex AI image generation")
    sub = parser.add_subparsers(dest="command")

    health = sub.add_parser("healthcheck", help="Verify project and auth state")

    generate = sub.add_parser("generate", help="Generate one or more images from a prompt")
    generate.add_argument("--prompt", required=True, help="Creative prompt text")
    generate.add_argument("--output", required=True, help="Path to save the generated image")
    generate.add_argument("--project-id", help="Override GOOGLE_STITCH_PROJECT_ID")
    generate.add_argument("--location", default=DEFAULT_LOCATION, help="Vertex AI region")
    generate.add_argument("--model", default=DEFAULT_MODEL, help="Vertex image model")
    generate.add_argument("--aspect-ratio", default="1:1", help="Image aspect ratio")
    generate.add_argument("--sample-count", type=int, default=1, help="Number of images to generate")
    generate.add_argument(
        "--disable-prompt-enhancement",
        action="store_true",
        help="Disable Vertex prompt enhancement",
    )

    args = parser.parse_args()

    if args.command == "healthcheck":
        print(json.dumps(healthcheck(), indent=2))
        return

    if args.command == "generate":
        project_id = args.project_id or get_project_id()
        if not project_id:
            print(
                "ERROR: GOOGLE_STITCH_PROJECT_ID is not set and no gcloud project is active.",
                file=sys.stderr,
            )
            sys.exit(1)

        response = api_call(
            project_id=project_id,
            location=args.location,
            model=args.model,
            prompt=args.prompt,
            aspect_ratio=args.aspect_ratio,
            sample_count=args.sample_count,
            enhance_prompt=not args.disable_prompt_enhancement,
        )
        saved = save_predictions(response, args.output)
        print(json.dumps({"saved": saved, "model": args.model, "location": args.location}, indent=2))
        return

    parser.print_help()


if __name__ == "__main__":
    main()
