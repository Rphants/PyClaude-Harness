from __future__ import annotations

import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
AGENT_DIR = PROJECT_ROOT / "agents" / "ad-engine"
sys.path.insert(0, str(AGENT_DIR))

import harness_bridge  # type: ignore
import creative_training  # type: ignore


def test_proposer_prioritizes_creative_strategy(tmp_path, monkeypatch):
    optimize_path = tmp_path / "optimize.json"
    results_path = tmp_path / "results.tsv"
    experiments_dir = tmp_path / "experiments"
    experiments_dir.mkdir()

    optimize_path.write_text(json.dumps({
        "creative_params": {"headline_font_size_px": 56},
        "copy_params": {"number_of_variations": 12},
        "creative_strategy": {
            "headline_style": "operator",
            "body_style": "operator",
            "proof_style": "signal",
            "cta_style": "listen",
            "scene_style": "documentary",
        },
        "audio_params": {"background_music_enabled": False},
        "budget_params": {"daily_budget_usd": 50},
    }))

    monkeypatch.setattr(harness_bridge, "OPTIMIZE_FILE", optimize_path)
    monkeypatch.setattr(harness_bridge, "RESULTS_FILE", results_path)
    monkeypatch.setattr(harness_bridge, "EXPERIMENTS_DIR", experiments_dir)

    proposal = harness_bridge.propose()

    assert proposal.section == "creative_strategy"
    assert proposal.change_description == "Switch headline style to threat framing"


def test_apply_creative_strategy_mutates_copy_and_scene():
    blueprint = {
        "angle": "pain-point",
        "headline": "Base headline",
        "primary_text": "Base body",
        "description": "Base description",
        "cta": "Base CTA",
        "proof_text": "Base proof",
        "scene_prompt": "Base scene.",
    }
    optimize = {
        "creative_strategy": {
            "headline_style": "threat",
            "body_style": "competitive",
            "proof_style": "callback",
            "cta_style": "speed",
            "scene_style": "war-room",
        }
    }

    result = creative_training.apply_creative_strategy(blueprint, optimize)

    assert result["headline"] == "Late outreach loses callbacks."
    assert "slower competitors react" in result["primary_text"]
    assert result["proof_text"] == "callback proof"
    assert result["cta"] == "Move first"
    assert "war-room energy" in result["scene_prompt"]
