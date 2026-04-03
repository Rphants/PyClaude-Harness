#!/usr/bin/env python3
"""Vision evaluator for ad creatives via OpenRouter-compatible multimodal models."""

from __future__ import annotations

import argparse
import base64
import json
import mimetypes
import os
import sys
import urllib.request
from pathlib import Path
from typing import Any

from http_utils import urlopen

AGENT_DIR = Path(__file__).resolve().parent
DEFAULT_MODEL = "qwen/qwen3.6-plus:free"
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"


def get_openrouter_api_key() -> str | None:
    token = os.environ.get("OPENROUTER_API_KEY")
    if token:
        return token

    try:
        sys.path.insert(0, str(AGENT_DIR.parent.parent))
        from src.coordinator.secrets import get_secret

        return get_secret("OPENROUTER_API_KEY")
    except Exception:
        return None


def image_to_data_url(image_path: Path) -> str:
    mime_type, _ = mimetypes.guess_type(str(image_path))
    if not mime_type:
        mime_type = "image/png"
    raw = image_path.read_bytes()
    encoded = base64.b64encode(raw).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"


def load_spec_context(spec_path: Path | None) -> dict[str, Any] | None:
    if spec_path is None:
        return None
    return json.loads(spec_path.read_text())


def parse_json_payload(raw: str) -> dict[str, Any]:
    raw = raw.strip()
    if not raw:
        raise json.JSONDecodeError("empty output", raw, 0)

    try:
        data = json.loads(raw)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        pass

    decoder = json.JSONDecoder()
    best_match: tuple[int, dict[str, Any]] | None = None
    for index, char in enumerate(raw):
        if char != "{":
            continue
        try:
            candidate, end = decoder.raw_decode(raw[index:])
        except json.JSONDecodeError:
            continue
        if isinstance(candidate, dict):
            if best_match is None or end > best_match[0]:
                best_match = (end, candidate)

    if best_match is None:
        raise json.JSONDecodeError("no JSON object found", raw, 0)
    return best_match[1]


def build_user_prompt(spec_context: dict[str, Any] | None) -> str:
    context_lines = []
    if spec_context:
        for key in ("angle", "headline", "primary_text", "description", "cta", "proof_text", "hypothesis"):
            value = spec_context.get(key)
            if value:
                context_lines.append(f"- {key}: {value}")

    context_block = "\n".join(context_lines) if context_lines else "- no structured spec context provided"
    return (
        "You are evaluating a Facebook ad creative for a real-estate-wholesaler audience.\n"
        "Judge only what is visible in the image plus the provided spec context.\n"
        "Be strict and commercially realistic.\n\n"
        "Return one JSON object with exactly these keys:\n"
        "{\n"
        '  "visual_hierarchy_score": 0-100,\n'
        '  "legibility_score": 0-100,\n'
        '  "clutter_score": 0-100,\n'
        '  "proof_visibility_score": 0-100,\n'
        '  "thumbstop_score": 0-100,\n'
        '  "premium_polish_score": 0-100,\n'
        '  "meta_fit_score": 0-100,\n'
        '  "overall_score": 0-100,\n'
        '  "strengths": ["..."],\n'
        '  "issues": ["..."],\n'
        '  "recommended_changes": ["..."]\n'
        "}\n\n"
        "Scoring guidance:\n"
        "- visual_hierarchy_score: headline/subhead/proof/CTA clarity and order\n"
        "- legibility_score: readability at mobile-feed size\n"
        "- clutter_score: higher means cleaner and less overloaded\n"
        "- proof_visibility_score: numbers, screenshots, evidence, or trust markers are easy to notice\n"
        "- thumbstop_score: likelihood it catches attention in-feed\n"
        "- premium_polish_score: design quality, typography, composition, confidence\n"
        "- meta_fit_score: how native and effective this feels for a Meta ad\n\n"
        "Spec context:\n"
        f"{context_block}\n"
    )


def build_payload(
    *,
    image_path: Path,
    spec_context: dict[str, Any] | None,
    model: str,
) -> dict[str, Any]:
    return {
        "model": model,
        "temperature": 0.1,
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": build_user_prompt(spec_context),
                    },
                    {
                        "type": "image_url",
                        "image_url": {"url": image_to_data_url(image_path)},
                    },
                ],
            }
        ],
    }


def call_openrouter(payload: dict[str, Any]) -> dict[str, Any]:
    api_key = get_openrouter_api_key()
    if not api_key:
        raise RuntimeError("OPENROUTER_API_KEY missing")

    req = urllib.request.Request(
        OPENROUTER_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://agentrvm.com",
            "X-Title": "PyClaude-Harness Vision Evaluator",
        },
        method="POST",
    )
    with urlopen(req, timeout=120) as resp:
        return json.loads(resp.read().decode("utf-8"))


def extract_judgement(response: dict[str, Any]) -> dict[str, Any]:
    choices = response.get("choices") or []
    if not choices:
        raise RuntimeError("OpenRouter returned no choices")
    message = choices[0].get("message") or {}
    content = message.get("content")
    if isinstance(content, list):
        text_parts = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                text_parts.append(item.get("text", ""))
        content = "\n".join(text_parts)
    if not isinstance(content, str):
        raise RuntimeError("OpenRouter response did not contain text content")
    return parse_json_payload(content)


def score_image(
    *,
    image_path: Path,
    spec_path: Path | None,
    model: str,
) -> dict[str, Any]:
    if not image_path.exists():
        raise FileNotFoundError(f"image not found: {image_path}")
    spec_context = load_spec_context(spec_path)
    payload = build_payload(image_path=image_path, spec_context=spec_context, model=model)
    response = call_openrouter(payload)
    judgement = extract_judgement(response)
    return {
        "model": model,
        "image_path": str(image_path),
        "spec_path": str(spec_path) if spec_path else None,
        "judgement": judgement,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Vision evaluator for ad creatives via OpenRouter")
    parser.add_argument("--image", required=True, help="Path to image creative")
    parser.add_argument("--spec", help="Optional JSON spec file for extra context")
    parser.add_argument("--model", default=DEFAULT_MODEL, help=f"OpenRouter model (default: {DEFAULT_MODEL})")
    parser.add_argument("--json", action="store_true", help="Output JSON only")
    args = parser.parse_args()

    try:
        result = score_image(
            image_path=Path(args.image),
            spec_path=Path(args.spec) if args.spec else None,
            model=args.model,
        )
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        print(
            "Setup: export OPENROUTER_API_KEY=... or store it via "
            "python -m src.coordinator.secrets set OPENROUTER_API_KEY <value>",
            file=sys.stderr,
        )
        sys.exit(1)

    if args.json:
        print(json.dumps(result))
        return

    judgement = result["judgement"]
    print(f"Model: {result['model']}")
    print(f"Image: {result['image_path']}")
    print(f"Overall score: {judgement.get('overall_score')}")
    print(f"Strengths: {judgement.get('strengths')}")
    print(f"Issues: {judgement.get('issues')}")
    print(f"Recommended changes: {judgement.get('recommended_changes')}")


if __name__ == "__main__":
    main()
