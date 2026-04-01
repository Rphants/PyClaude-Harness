#!/usr/bin/env python3
"""
Site Optimizer — Evaluation Script

Measures the real-world performance of agentrvm.com landing page variants.
This is the agent's prepare.py equivalent — READ ONLY, never modify.

Metrics:
  - build_health: Does `pnpm run build` pass? (binary)
  - lighthouse_score: Performance score from Lighthouse CI
  - type_safety: Zero TypeScript errors (binary)
  - component_count: Number of conversion-relevant components present
  - audio_demo_present: Is the VibeVoice audio player on the page?

Future (requires production + PostHog):
  - conversion_rate: waitlist_signup / unique_visitors
  - bounce_rate: single-page sessions / total sessions
  - audio_play_rate: audio_demo_played / page_views
"""

import json
import subprocess
import sys
import os
from pathlib import Path

AGENTRVM_DIR = os.path.expanduser("~/agentrvm")
CONFIG_PATH = Path(__file__).parent / "config.json"


def load_config():
    with open(CONFIG_PATH) as f:
        return json.load(f)


def check_build_health():
    """Run pnpm build and check exit code."""
    try:
        result = subprocess.run(
            ["pnpm", "run", "build"],
            cwd=AGENTRVM_DIR,
            capture_output=True,
            text=True,
            timeout=120
        )
        return {
            "passes": result.returncode == 0,
            "exit_code": result.returncode,
            "errors": result.stderr[-500:] if result.returncode != 0 else None
        }
    except Exception as e:
        return {"passes": False, "exit_code": -1, "errors": str(e)}


def check_type_safety():
    """Run TypeScript compiler in check mode."""
    try:
        result = subprocess.run(
            ["npx", "tsc", "--noEmit"],
            cwd=AGENTRVM_DIR,
            capture_output=True,
            text=True,
            timeout=60
        )
        error_count = result.stdout.count("error TS")
        return {
            "passes": result.returncode == 0,
            "error_count": error_count,
            "sample_errors": result.stdout[:500] if error_count > 0 else None
        }
    except Exception as e:
        return {"passes": False, "error_count": -1, "sample_errors": str(e)}


def check_components():
    """Scan for conversion-relevant components."""
    components = {
        "hero": False,
        "waitlist_form": False,
        "audio_demo": False,
        "social_proof": False,
        "roi_calculator": False,
        "trust_badges": False,
        "competitor_comparison": False,
        "video_testimonial": False,
    }

    src_dir = Path(AGENTRVM_DIR) / "src"
    if not src_dir.exists():
        return {"components": components, "score": 0.0}

    # Scan all tsx/ts files for component indicators
    for f in src_dir.rglob("*.tsx"):
        content = f.read_text(errors="ignore").lower()
        if "hero" in f.name.lower() or "hero" in content[:200]:
            components["hero"] = True
        if "waitlist" in f.name.lower() or "waitlist" in content[:200]:
            components["waitlist_form"] = True
        if "audio" in f.name.lower() or "audiodemo" in content[:500]:
            components["audio_demo"] = True
        if "social" in content[:500] or "proof" in content[:500]:
            components["social_proof"] = True
        if "roi" in f.name.lower() or "calculator" in content[:500]:
            components["roi_calculator"] = True
        if "trust" in content[:500] or "badge" in content[:500]:
            components["trust_badges"] = True
        if "competitor" in content[:500] or "comparison" in content[:500]:
            components["competitor_comparison"] = True
        if "testimonial" in content[:500] or "video" in f.name.lower():
            components["video_testimonial"] = True

    present = sum(1 for v in components.values() if v)
    total = len(components)
    return {"components": components, "score": present / total}


def check_audio_demo():
    """Check if VibeVoice audio demo exists and is wired up."""
    audio_component = Path(AGENTRVM_DIR) / "src" / "components" / "AudioDemo.tsx"
    audio_in_page = False
    audio_file_exists = False

    # Check if component file exists
    component_exists = audio_component.exists()

    # Check if it's imported in page.tsx
    page_file = Path(AGENTRVM_DIR) / "src" / "app" / "page.tsx"
    if page_file.exists():
        page_content = page_file.read_text(errors="ignore")
        audio_in_page = "AudioDemo" in page_content or "audio" in page_content.lower()

    # Check for audio files in public/
    public_dir = Path(AGENTRVM_DIR) / "public"
    if public_dir.exists():
        audio_extensions = {".mp3", ".wav", ".ogg", ".webm"}
        for f in public_dir.iterdir():
            if f.suffix.lower() in audio_extensions and "demo" in f.name.lower():
                audio_file_exists = True
                break

    return {
        "component_exists": component_exists,
        "wired_to_page": audio_in_page,
        "audio_file_exists": audio_file_exists,
        "fully_ready": component_exists and audio_in_page and audio_file_exists
    }


def compute_composite(build, types, components, audio):
    """
    Composite score — weighted combination of all metrics.

    Weights:
      - Build health: 0.30 (must work or nothing else matters)
      - Type safety: 0.10 (code quality)
      - Component richness: 0.30 (more conversion elements = better)
      - Audio demo: 0.30 (highest-impact single feature)
    """
    build_score = 1.0 if build["passes"] else 0.0
    type_score = 1.0 if types["passes"] else 0.5  # Partial credit
    component_score = components["score"]
    audio_score = (
        0.33 * audio["component_exists"] +
        0.33 * audio["wired_to_page"] +
        0.34 * audio["audio_file_exists"]
    )

    composite = (
        0.30 * build_score +
        0.10 * type_score +
        0.30 * component_score +
        0.30 * audio_score
    )
    return round(composite, 4)


def evaluate():
    """Run full evaluation and print results."""
    config = load_config()

    print("=" * 60)
    print("SITE OPTIMIZER — Evaluation Report")
    print("=" * 60)

    print("\n[1/4] Build Health...")
    build = check_build_health()
    print(f"  Pass: {build['passes']}  Exit: {build['exit_code']}")

    print("\n[2/4] Type Safety...")
    types = check_type_safety()
    print(f"  Pass: {types['passes']}  Errors: {types['error_count']}")

    print("\n[3/4] Component Scan...")
    components = check_components()
    for name, present in components["components"].items():
        status = "✓" if present else "✗"
        print(f"  {status} {name}")
    print(f"  Score: {components['score']:.2f}")

    print("\n[4/4] Audio Demo...")
    audio = check_audio_demo()
    print(f"  Component exists: {audio['component_exists']}")
    print(f"  Wired to page:   {audio['wired_to_page']}")
    print(f"  Audio file:      {audio['audio_file_exists']}")
    print(f"  Fully ready:     {audio['fully_ready']}")

    composite = compute_composite(build, types, components, audio)
    print(f"\n{'=' * 60}")
    print(f"COMPOSITE SCORE: {composite}")
    print(f"{'=' * 60}")

    # Write results
    results = {
        "timestamp": subprocess.check_output(["date", "-Iseconds"]).decode().strip(),
        "experiment": config.get("experiment_count", 0),
        "composite_score": composite,
        "build_health": build,
        "type_safety": types,
        "components": components,
        "audio_demo": audio
    }

    results_file = Path(__file__).parent / "last_evaluation.json"
    with open(results_file, "w") as f:
        json.dump(results, f, indent=2)

    return composite


if __name__ == "__main__":
    score = evaluate()
    sys.exit(0 if score > 0 else 1)
