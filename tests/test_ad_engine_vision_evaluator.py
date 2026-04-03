from __future__ import annotations

import base64
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
AGENT_DIR = PROJECT_ROOT / "agents" / "ad-engine"
sys.path.insert(0, str(AGENT_DIR))

import vision_evaluator  # type: ignore


PNG_BYTES = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO7Z0z8AAAAASUVORK5CYII="
)


def test_image_to_data_url_preserves_png_mime(tmp_path):
    image_path = tmp_path / "test.png"
    image_path.write_bytes(PNG_BYTES)

    data_url = vision_evaluator.image_to_data_url(image_path)

    assert data_url.startswith("data:image/png;base64,")


def test_build_payload_embeds_spec_context(tmp_path):
    image_path = tmp_path / "creative.png"
    image_path.write_bytes(PNG_BYTES)
    spec_context = {
        "angle": "fomo",
        "headline": "Late outreach loses callbacks.",
        "primary_text": "See which sellers are heating up before your competitors do.",
    }

    payload = vision_evaluator.build_payload(
        image_path=image_path,
        spec_context=spec_context,
        model="qwen/qwen3.6-plus:free",
    )

    message = payload["messages"][0]["content"]
    assert message[0]["type"] == "text"
    assert "Late outreach loses callbacks." in message[0]["text"]
    assert message[1]["type"] == "image_url"


def test_extract_judgement_parses_json_from_response():
    response = {
        "choices": [
            {
                "message": {
                    "content": json.dumps(
                        {
                            "visual_hierarchy_score": 75,
                            "legibility_score": 80,
                            "clutter_score": 70,
                            "proof_visibility_score": 65,
                            "thumbstop_score": 72,
                            "premium_polish_score": 68,
                            "meta_fit_score": 74,
                            "overall_score": 72,
                            "strengths": ["clear headline"],
                            "issues": ["proof is too subtle"],
                            "recommended_changes": ["increase proof contrast"],
                        }
                    )
                }
            }
        ]
    }

    judgement = vision_evaluator.extract_judgement(response)

    assert judgement["overall_score"] == 72
    assert judgement["issues"] == ["proof is too subtle"]
