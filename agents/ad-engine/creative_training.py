#!/usr/bin/env python3
"""Autonomous creative batch generator for the Ad Creative Engine.

This module converts optimize.json + product truth into a deterministic batch
of deployable creative specs and rendered static assets. The goal is to let the
agent train on its own outputs instead of depending on operator-picked prompts.
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

try:
    from PIL import Image
except ImportError:  # pragma: no cover - preflight should catch missing Pillow
    Image = None

AGENT_DIR = Path(__file__).resolve().parent
EXPERIMENTS_DIR = AGENT_DIR / "experiments"
OPTIMIZE_FILE = AGENT_DIR / "optimize.json"
CONFIG_FILE = AGENT_DIR / "config.json"
STITCH_SCRIPT = AGENT_DIR / "stitch_api.py"
LOCAL_GPU_SCENE_SCRIPT = AGENT_DIR / "local_gpu_scene.py"
GENERATOR_SCRIPT = AGENT_DIR / "creative_generator.py"
MESSAGING_BRIEF_FILE = AGENT_DIR / "MESSAGING-BRIEF.md"
META_ADS_DOMAIN_FILE = AGENT_DIR / "META-ADS-DOMAIN.md"

PRODUCT_TRUTH = (
    "AgentRVM is an automated seller-signal intelligence system for wholesalers. "
    "It detects seller intent and triggers fast outbound voicemail follow-up before "
    "slower competitors react."
)

ANGLE_NOTES = {
    "pain-point": "Make the cost of reacting too late feel expensive and immediate.",
    "fomo": "Emphasize first-mover advantage before another wholesaler gets the callback.",
    "roi": "Show that one good callback can justify months of automated outreach.",
    "curiosity": "Create intrigue around hearing the outbound voicemail without sounding gimmicky.",
    "social-proof": "Sound like experienced operators already use this edge, not generic social hype.",
    "audio-first": "Use the voice as proof, but keep seller-signal detection as the real differentiator.",
}

ANGLE_REQUIRED_TERMS = {
    "pain-point": ("late", "margin", "before", "callback"),
    "fomo": ("first", "before", "competitor", "already"),
    "roi": ("callback", "months", "margin", "pay"),
    "curiosity": ("hear", "play", "first", "before"),
    "social-proof": ("callback", "data", "top", "rate"),
    "audio-first": ("voice", "audio", "play", "callback"),
}

FORBIDDEN_PHRASES = (
    "answers your phone",
    "answers 24/7",
    "answering service",
    "answers calls",
    "cheap ai",
)

GENERIC_PHRASES = (
    "the system",
    "the platform",
    "the solution",
    "used by wholesalers",
    "smarter teams",
    "hear why",
    "hear it",
)

ANGLE_BLUEPRINTS: list[dict[str, str]] = [
    {
        "angle": "pain-point",
        "headline": "Seller signal found. Outreach started.",
        "primary_text": (
            "AgentRVM spots seller intent and starts outbound follow-up before "
            "another wholesaler gets the lead."
        ),
        "description": "Outbound action starts right after seller intent is detected.",
        "cta": "Hear the outreach",
        "proof_text": "seller signals",
        "scene_prompt": (
            "Premium square documentary photo for a Meta ad aimed at real estate "
            "wholesalers. A focused wholesaler working late at a desk, phone in "
            "foreground, handwritten notes, warm desk lamp, dark navy office, "
            "subject on the right third, clean negative space on the left, premium "
            "authentic UGC feel, no text, no logos, no panels, no collage."
        ),
    },
    {
        "angle": "fomo",
        "headline": "First signal. First outreach.",
        "primary_text": (
            "AgentRVM finds seller signals and starts outbound follow-up while your "
            "team keeps working live deals."
        ),
        "description": "Speed-to-outreach beats manual dialing.",
        "cta": "Listen to it",
        "proof_text": "first to outreach",
        "scene_prompt": (
            "Premium square portrait for a Facebook ad. Confident real estate "
            "wholesaler in casual clothes listening to a voicemail on speakerphone, "
            "surprised and energized, desk with notes and coffee, dark navy "
            "background with negative space, editorial lighting, authentic high-end "
            "UGC look, no text, no logos, no labels, no watermarks."
        ),
    },
    {
        "angle": "roi",
        "headline": "One signal can become a callback.",
        "primary_text": (
            "One seller callback can pay for months of data-driven outreach. "
            "AgentRVM turns seller signals into faster follow-up."
        ),
        "description": "Built for wholesaler margin and speed.",
        "cta": "See the leverage",
        "proof_text": "margin leverage",
        "scene_prompt": (
            "Premium cinematic desk scene for a Facebook ad. Real estate wholesaler "
            "reviewing deal numbers and callback notes, smartphone on table, dark "
            "navy background, warm orange practical lighting, lots of clean negative "
            "space, authentic premium ad photography, no text or logos."
        ),
    },
    {
        "angle": "curiosity",
        "headline": "Hear what fast follow-up sounds like.",
        "primary_text": (
            "Most wholesalers never hear what signal-driven follow-up sounds like. "
            "AgentRVM detects seller intent first, then acts on it."
        ),
        "description": "Curiosity-first creative built around the outreach reveal.",
        "cta": "Play it",
        "proof_text": "audio reveal",
        "scene_prompt": (
            "Premium square creative photo for a Meta ad. Real estate wholesaler "
            "leaning toward a phone speaker, curious expression, dark blue studio "
            "background, soft warm key light, clean empty space for typography, "
            "authentic not corporate, no text or logos."
        ),
    },
    {
        "angle": "social-proof",
        "headline": "The smarter teams move first.",
        "primary_text": (
            "The edge is not another dialer. It is detecting seller intent and "
            "triggering follow-up while slower teams are still pulling lists."
        ),
        "description": "Social proof positioned as timing and data advantage.",
        "cta": "Hear why",
        "proof_text": "used by wholesalers",
        "scene_prompt": (
            "Premium square UGC-style photo for a Meta ad. Self-assured wholesaler "
            "smiling after hearing a voicemail on speakerphone, simple desk setup, "
            "dark navy backdrop, warm editorial lighting, lots of negative space, "
            "no text, logos, UI, or watermarks."
        ),
    },
    {
        "angle": "audio-first",
        "headline": "The voice proves the system.",
        "primary_text": (
            "AgentRVM wins because the outreach sounds natural enough to earn the "
            "callback. Hear what happens after seller intent is detected."
        ),
        "description": "Audio-first angle without the fake answering-service story.",
        "cta": "Hear the proof",
        "proof_text": "audio-first",
        "scene_prompt": (
            "Premium square cinematic still for an audio-first Facebook ad. "
            "Phone on desk with waveform lighting, wholesaler nearby reviewing notes, "
            "dark navy office, strong contrast, premium authentic UGC, negative "
            "space on the left, no text or logos."
        ),
    },
]

HEADLINE_STYLE_VARIANTS: dict[str, dict[str, str]] = {
    "operator": {},
    "speed": {
        "pain-point": "Seller signal found. Move first.",
        "fomo": "First signal. Faster callback.",
        "roi": "One callback can cover months.",
        "curiosity": "Hear fast outreach at work.",
        "social-proof": "Top teams move first.",
        "audio-first": "Voice that wins callbacks.",
    },
    "proof": {
        "pain-point": "Seller signal. Callback proof.",
        "fomo": "First outreach. Real callback edge.",
        "roi": "One callback. Real margin lift.",
        "curiosity": "The callback starts here.",
        "social-proof": "Operators trust signal-first outreach.",
        "audio-first": "Natural voice. Faster callback.",
    },
    "threat": {
        "pain-point": "Late outreach loses callbacks.",
        "fomo": "Your competitor moved first.",
        "roi": "Slow follow-up burns margin.",
        "curiosity": "What late teams never hear.",
        "social-proof": "Slow teams lose the lead.",
        "audio-first": "Weak voicemails lose callbacks.",
    },
}

BODY_STYLE_VARIANTS: dict[str, dict[str, str]] = {
    "operator": {},
    "competitive": {
        "pain-point": "When seller intent shows up, AgentRVM starts outbound follow-up before slower competitors react.",
        "fomo": "Seller signals trigger outreach while other wholesalers are still pulling lists.",
        "roi": "One faster callback can cover months of seller-signal-driven outreach.",
        "curiosity": "Hear what happens when seller intent is detected before another team reacts.",
        "social-proof": "The edge is timing: detect seller intent, trigger outreach, win the callback window.",
        "audio-first": "The voicemail sounds natural because the system acts on seller signals at the right moment.",
    },
    "proof": {
        "pain-point": "Seller intent is detected, outbound follow-up starts, and your team keeps working live deals.",
        "fomo": "First-to-outreach matters because callbacks go to the team that reacts before the market does.",
        "roi": "A single callback can justify the cost when your outreach starts from real seller signals.",
        "curiosity": "The difference is not the voice alone; it is the signal that tells you when to move.",
        "social-proof": "Serious operators use seller-signal data to start outreach before slower teams.",
        "audio-first": "Hear the outbound voicemail, then remember the real edge is seller-signal timing.",
    },
    "margin": {
        "pain-point": "Every late callback costs margin, so AgentRVM starts outreach when seller intent appears.",
        "fomo": "A first callback can decide who wins the deal when sellers are already signaling intent.",
        "roi": "One protected callback can pay for weeks of automated outreach and seller-signal triage.",
        "curiosity": "Most teams never hear the outreach that protects margin because they react too late.",
        "social-proof": "Operators protecting margin start with seller signals, not another batch of blind calls.",
        "audio-first": "The voice matters because it lands while the opportunity is still warm.",
    },
}

CTA_STYLE_VARIANTS: dict[str, dict[str, str]] = {
    "listen": {},
    "proof": {
        "pain-point": "See the proof",
        "fomo": "See the edge",
        "roi": "See the margin",
        "curiosity": "See the reveal",
        "social-proof": "See proof",
        "audio-first": "See the proof",
    },
    "speed": {
        "pain-point": "Move first",
        "fomo": "Beat them",
        "roi": "Protect margin",
        "curiosity": "Play it now",
        "social-proof": "Get the edge",
        "audio-first": "Hear it now",
    },
    "operator": {
        "pain-point": "Get the edge",
        "fomo": "See it work",
        "roi": "See it work",
        "curiosity": "Hear the move",
        "social-proof": "See the system",
        "audio-first": "Hear the proof",
    },
}

PROOF_TEXT_VARIANTS: dict[str, dict[str, str]] = {
    "signal": {},
    "callback": {
        "pain-point": "callback proof",
        "fomo": "callback edge",
        "roi": "callback leverage",
        "curiosity": "callback reveal",
        "social-proof": "callback rate",
        "audio-first": "callback proof",
    },
    "speed": {
        "pain-point": "first to outreach",
        "fomo": "moved first",
        "roi": "first callback wins",
        "curiosity": "fast follow-up",
        "social-proof": "speed advantage",
        "audio-first": "fast callback",
    },
    "margin": {
        "pain-point": "margin protection",
        "fomo": "deal margin",
        "roi": "margin leverage",
        "curiosity": "callback economics",
        "social-proof": "margin discipline",
        "audio-first": "margin proof",
    },
}

SCENE_STYLE_SUFFIX: dict[str, str] = {
    "documentary": "documentary realism, tactile workspace detail, authentic operator mood.",
    "editorial": "editorial polish, premium contrast, magazine-grade composition, intentional styling.",
    "ugc": "premium UGC realism, phone-shot intimacy, lived-in details, unpolished authenticity.",
    "war-room": "deal desk war-room energy, multiple monitors, urgent operator workflow, tactical intensity.",
}


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text()) if path.exists() else {}


def load_text(path: Path) -> str:
    return path.read_text() if path.exists() else ""


def fit_text(text: str, max_chars: int) -> str:
    return text if len(text) <= max_chars else text[: max_chars - 1].rstrip() + "…"


def apply_creative_strategy(blueprint: dict[str, str], optimize: dict[str, Any]) -> dict[str, str]:
    strategy = optimize.get("creative_strategy", {})
    if not isinstance(strategy, dict):
        return dict(blueprint)

    angle = blueprint["angle"]
    variant = dict(blueprint)

    headline_style = str(strategy.get("headline_style", "operator")).strip().lower()
    if headline_style in HEADLINE_STYLE_VARIANTS:
        variant["headline"] = HEADLINE_STYLE_VARIANTS[headline_style].get(angle, variant["headline"])

    body_style = str(strategy.get("body_style", "operator")).strip().lower()
    if body_style in BODY_STYLE_VARIANTS:
        variant["primary_text"] = BODY_STYLE_VARIANTS[body_style].get(angle, variant["primary_text"])

    cta_style = str(strategy.get("cta_style", "listen")).strip().lower()
    if cta_style in CTA_STYLE_VARIANTS:
        variant["cta"] = CTA_STYLE_VARIANTS[cta_style].get(angle, variant["cta"])

    proof_style = str(strategy.get("proof_style", "signal")).strip().lower()
    if proof_style in PROOF_TEXT_VARIANTS:
        variant["proof_text"] = PROOF_TEXT_VARIANTS[proof_style].get(angle, variant["proof_text"])

    scene_style = str(strategy.get("scene_style", "documentary")).strip().lower()
    if scene_style in SCENE_STYLE_SUFFIX:
        variant["scene_prompt"] = f"{variant['scene_prompt']} {SCENE_STYLE_SUFFIX[scene_style]}"

    return variant


def render_env(optimize: dict[str, Any]) -> dict[str, str]:
    creative = optimize.get("creative_params", {})
    return {
        "AD_CREATIVE_HEADLINE_SIZE": str(creative.get("headline_font_size_px", 84)),
        "AD_CREATIVE_BODY_SIZE": str(max(18, min(36, creative.get("primary_text_font_size_px", 24)))),
        "AD_CREATIVE_SMALL_SIZE": str(max(14, min(24, creative.get("primary_text_font_size_px", 24) - 6))),
        "AD_CREATIVE_TINY_SIZE": "14",
        "AD_CREATIVE_CTA_SIZE": str(max(22, min(34, creative.get("cta_font_size_px", 28)))),
    }


def reference_examples(limit: int = 3) -> list[dict[str, str]]:
    examples: list[dict[str, str]] = []
    for path in sorted(glob.glob(str(EXPERIMENTS_DIR / "static-*.json")))[:limit]:
        payload = load_json(Path(path))
        if not payload:
            continue
        examples.append(
            {
                "headline": str(payload.get("headline", "")),
                "primary_text": str(payload.get("primary_text", "")),
                "description": str(payload.get("description", "")),
            }
        )
    return examples


def quality_score(headline: str, body: str, cta: str = "", proof_text: str = "") -> int:
    text = f"{headline} {body} {cta} {proof_text}".lower()
    score = 0
    preferred_terms = (
        "seller",
        "signal",
        "callback",
        "voicemail",
        "outreach",
        "lead",
        "wholesaler",
        "first",
        "faster",
        "detect",
        "detected",
        "margin",
        "competitor",
        "dialing",
    )
    headline_terms = headline.lower()
    score += sum(2 if term in headline_terms else 1 for term in preferred_terms if term in text)
    proof_terms = ("callback", "first", "seller signal", "detected", "margin", "15k", "40%")
    score += sum(2 for term in proof_terms if term in text)
    strong_openers = ("seller", "first", "missed", "stop", "one", "your competitor", "callback")
    if headline_terms.startswith(strong_openers):
        score += 3
    if "$" in text or "%" in text or any(ch.isdigit() for ch in text):
        score += 2
    if ":" in headline or "." in headline:
        score += 1
    if len(headline) <= 34:
        score += 2
    if len(body) <= 110:
        score += 2
    if 1 <= len(cta) <= 18:
        score += 1
    elif len(cta) > 18:
        score -= 2
    if any(bad in text for bad in FORBIDDEN_PHRASES):
        score -= 6
    if any(generic in text for generic in GENERIC_PHRASES):
        score -= 3
    if "sounds like" in text or "sounds natural" in text:
        score -= 1
    if "hear what" in headline_terms or "hear why" in text:
        score -= 2
    if "..." in headline or "…" in headline or "..." in body or "…" in body:
        score -= 2
    return score


def angle_quality_score(angle: str, headline: str, body: str, cta: str = "", proof_text: str = "") -> int:
    score = quality_score(headline, body, cta, proof_text)
    text = f"{headline} {body} {cta} {proof_text}".lower()
    required_hits = sum(1 for term in ANGLE_REQUIRED_TERMS.get(angle, ()) if term in text)
    score += required_hits * 2
    if angle == "curiosity" and not any(term in text for term in ("first", "before", "already")):
        score -= 3
    if angle == "audio-first" and not any(term in text for term in ("voice", "audio", "play")):
        score -= 3
    if angle == "social-proof" and not any(term in text for term in ("data", "rate", "top")):
        score -= 3
    if cta and len(cta) > 16:
        score -= 1
    return score


def get_secret_value(name: str) -> str | None:
    value = os.environ.get(name)
    if value:
        return value
    try:
        import sys as _sys

        _sys.path.insert(0, str(AGENT_DIR.parent.parent))
        from src.coordinator.secrets import get_secret

        return get_secret(name)
    except Exception:
        return None


def generate_copy_variants_with_claude(
    *,
    blueprints: list[dict[str, str]],
    optimize: dict[str, Any],
) -> list[dict[str, str]] | None:
    """Use Claude to generate tighter copy variants from the messaging brief."""
    if not get_secret_value("ANTHROPIC_API_KEY"):
        return None

    messaging_brief = load_text(MESSAGING_BRIEF_FILE)
    meta_ads_domain = load_text(META_ADS_DOMAIN_FILE)
    examples = reference_examples()
    copy_params = optimize.get("copy_params", {})
    candidate_count = max(3, min(6, int(copy_params.get("variants_per_angle", 5))))
    prompt = f"""
You are generating ad copy variants for the AgentRVM Facebook Ad Super Agent.

Product truth:
{PRODUCT_TRUTH}

Messaging brief:
{messaging_brief}

Meta Ads domain playbook:
{meta_ads_domain}

Angle guidance:
{json.dumps(ANGLE_NOTES, indent=2)}

Reference examples from stronger earlier assets. Learn the specificity and hook style, but do not copy them verbatim:
{json.dumps(examples, indent=2)}

Output JSON only as an array of objects. One object per requested angle.
For each object return:
{{
  "angle": "...",
  "variants": [
    {{
      "headline": "...",
      "primary_text": "...",
      "description": "...",
      "cta": "...",
      "proof_text": "..."
    }}
  ]
}}

Rules:
- Make the message about seller-signal intelligence, speed to first outreach, callback quality, and team leverage.
- Do NOT frame the offer as per-voicemail pricing, an answering service, or generic cheap AI.
- Headline max {copy_params.get("headline_max_length_chars", 40)} chars.
- Primary text max {copy_params.get("primary_text_max_length_chars", 125)} chars.
- Keep CTA short and direct.
- Give exactly {candidate_count} variants per angle.
- Favor punchy, premium, operator-minded language over generic SaaS copy.
- At least one variant per angle should include concrete proof language like callback, first, speed, seller signal, or margin.
- Favor hooks that make reacting late feel expensive.
- Avoid vague phrases like "the system", "the platform", "hear why", or "used by wholesalers".
- Angles requested: {json.dumps([{k: b[k] for k in ('angle','headline','primary_text','description','cta','proof_text')} for b in blueprints], indent=2)}
"""

    try:
        result = subprocess.run(
            ["claude", "-p", prompt, "--output-format", "json"],
            capture_output=True,
            text=True,
            timeout=180,
            cwd=AGENT_DIR,
            env=os.environ | {"ANTHROPIC_API_KEY": get_secret_value("ANTHROPIC_API_KEY") or ""},
        )
    except Exception:
        return None

    if result.returncode != 0:
        return None

    try:
        envelope = json.loads(result.stdout)
        inner = envelope.get("result", "").strip()
        if "```json" in inner:
            inner = inner.split("```json", 1)[1].split("```", 1)[0]
        elif "```" in inner:
            inner = inner.split("```", 1)[1].split("```", 1)[0]
        payload = json.loads(inner.strip())
    except Exception:
        return None

    if not isinstance(payload, list):
        return None
    normalized = []
    by_angle = {item.get("angle"): item for item in payload if isinstance(item, dict)}
    for blueprint in blueprints:
        variant = dict(blueprint)
        candidate = by_angle.get(blueprint["angle"])
        if candidate:
            best_score = quality_score(
                variant["headline"],
                variant["primary_text"],
                variant.get("cta", ""),
                variant.get("proof_text", ""),
            )
            best_score = angle_quality_score(
                blueprint["angle"],
                variant["headline"],
                variant["primary_text"],
                variant.get("cta", ""),
                variant.get("proof_text", ""),
            )
            variants = candidate.get("variants", [])
            if isinstance(variants, list):
                for candidate_variant in variants:
                    if not isinstance(candidate_variant, dict):
                        continue
                    trial = dict(variant)
                    for key in ("headline", "primary_text", "description", "cta", "proof_text"):
                        if isinstance(candidate_variant.get(key), str) and candidate_variant[key].strip():
                            trial[key] = candidate_variant[key].strip()
                    trial["headline"] = fit_text(
                        trial["headline"],
                        int(optimize.get("copy_params", {}).get("headline_max_length_chars", 40)),
                    )
                    trial["primary_text"] = fit_text(
                        trial["primary_text"],
                        int(optimize.get("copy_params", {}).get("primary_text_max_length_chars", 125)),
                    )
                    trial_score = quality_score(
                        trial["headline"],
                        trial["primary_text"],
                        trial.get("cta", ""),
                        trial.get("proof_text", ""),
                    )
                    trial_score = angle_quality_score(
                        blueprint["angle"],
                        trial["headline"],
                        trial["primary_text"],
                        trial.get("cta", ""),
                        trial.get("proof_text", ""),
                    )
                    if trial_score > best_score:
                        variant = trial
                        best_score = trial_score
        normalized.append(variant)
    return normalized


def generate_scene(scene_prompt: str, output_path: Path) -> None:
    if output_path.exists():
        if Image is None:
            if output_path.stat().st_size > 1024:
                return
        else:
            try:
                with Image.open(output_path) as existing:
                    existing.verify()
                return
            except Exception:
                output_path.unlink(missing_ok=True)
    provider = os.environ.get("AD_SCENE_PROVIDER", "google_stitch").strip().lower()
    if provider in {"local_gpu", "local-gpu", "gpu"}:
        script_path = LOCAL_GPU_SCENE_SCRIPT
    else:
        script_path = STITCH_SCRIPT

    subprocess.run(
        [
            sys.executable,
            str(script_path),
            "generate",
            "--prompt",
            scene_prompt,
            "--output",
            str(output_path),
        ],
        check=True,
        cwd=AGENT_DIR,
        timeout=300,
        capture_output=True,
        text=True,
    )


def render_creative(
    *,
    headline: str,
    body: str,
    cta: str,
    proof_text: str,
    background_image: Path,
    output_path: Path,
    optimize: dict[str, Any],
) -> None:
    env = os.environ.copy()
    env.update(render_env(optimize))
    subprocess.run(
        [
            sys.executable,
            str(GENERATOR_SCRIPT),
            "--template",
            "hybrid-ugc",
            "--headline",
            headline,
            "--body",
            body,
            "--cta",
            cta,
            "--brand-label",
            "AgentRVM",
            "--proof-text",
            proof_text,
            "--background-image",
            str(background_image),
            "--output",
            str(output_path),
        ],
        check=True,
        cwd=AGENT_DIR,
        env=env,
        timeout=180,
        capture_output=True,
        text=True,
    )


def spec_paths(angle: str) -> tuple[Path, Path, Path]:
    return (
        EXPERIMENTS_DIR / f"auto-scene-{angle}.png",
        EXPERIMENTS_DIR / f"auto-{angle}.png",
        EXPERIMENTS_DIR / f"auto-{angle}.json",
    )


def generate_batch(
    *,
    render: bool = True,
    refresh_scenes: bool = False,
    limit: int = 6,
    use_claude: bool = True,
) -> dict[str, Any]:
    optimize = load_json(OPTIMIZE_FILE)
    config = load_json(CONFIG_FILE)
    copy_params = optimize.get("copy_params", {})
    headline_max = int(copy_params.get("headline_max_length_chars", 52))
    body_max = int(copy_params.get("primary_text_max_length_chars", 140))
    url = "https://agentrvm.com"
    generated: list[dict[str, Any]] = []
    blueprints = [apply_creative_strategy(blueprint, optimize) for blueprint in ANGLE_BLUEPRINTS[:limit]]
    if use_claude:
        claude_variants = generate_copy_variants_with_claude(blueprints=blueprints, optimize=optimize)
        if claude_variants:
            blueprints = claude_variants

    EXPERIMENTS_DIR.mkdir(parents=True, exist_ok=True)

    for blueprint in blueprints:
        angle = blueprint["angle"]
        scene_path, image_path, spec_path = spec_paths(angle)
        if refresh_scenes and scene_path.exists():
            scene_path.unlink()

        headline = fit_text(blueprint["headline"], headline_max)
        body = fit_text(blueprint["primary_text"], body_max)
        score = angle_quality_score(angle, headline, body, blueprint["cta"], blueprint["proof_text"])

        if render:
            generate_scene(blueprint["scene_prompt"], scene_path)
            render_creative(
                headline=headline,
                body=body,
                cta=blueprint["cta"],
                proof_text=blueprint["proof_text"],
                background_image=scene_path,
                output_path=image_path,
                optimize=optimize,
            )

        spec = {
            "id": f"auto-{angle}",
            "type": "static",
            "angle": angle,
            "created_by": "creative_training.py",
            "canonical_product_truth": PRODUCT_TRUTH,
            "hypothesis": (
                f"{angle} angle framed around sell-signal detection plus outbound "
                "voicemail speed should outperform generic AI call-handling claims."
            ),
            "headline": headline,
            "primary_text": body,
            "description": blueprint["description"],
            "cta": blueprint["cta"],
            "cta_type": "LEARN_MORE",
            "url": url,
            "image_path": image_path.name,
            "audience": config.get("audiences", [{}])[0].get("name", "wholesalers-broad"),
            "proof_text": blueprint["proof_text"],
            "quality_score": score,
            "render_plan": {
                "scene_provider": os.environ.get("AD_SCENE_PROVIDER", "google_stitch"),
                "template": "hybrid-ugc",
                "scene_path": scene_path.name,
                "scene_prompt": blueprint["scene_prompt"],
            },
        }
        spec_path.write_text(json.dumps(spec, indent=2) + "\n")
        generated.append(
            {
                "angle": angle,
                "spec": str(spec_path),
                "image": str(image_path),
                "scene": str(scene_path),
                "quality_score": score,
                "copy_source": "claude" if use_claude else "static",
            }
        )

    manifest = {
        "product_truth": PRODUCT_TRUTH,
        "generated_count": len(generated),
        "rendered": render,
        "copy_source": "claude" if use_claude else "static",
        "items": generated,
    }
    (EXPERIMENTS_DIR / "auto-batch.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Autonomous creative batch generator")
    sub = parser.add_subparsers(dest="command")

    gen = sub.add_parser("generate", help="Generate a training batch of creative specs")
    gen.add_argument("--limit", type=int, default=6, help="Number of angle blueprints to generate")
    gen.add_argument("--no-render", action="store_true", help="Write specs only without rendering assets")
    gen.add_argument("--refresh-scenes", action="store_true", help="Force regeneration of source scenes")
    gen.add_argument("--no-claude", action="store_true", help="Skip Claude-generated copy variants")
    gen.add_argument("--json", action="store_true", help="Print machine-readable output")

    args = parser.parse_args()
    if args.command != "generate":
        parser.print_help()
        return

    result = generate_batch(
        render=not args.no_render,
        refresh_scenes=args.refresh_scenes,
        limit=args.limit,
        use_claude=not args.no_claude,
    )
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"Generated {result['generated_count']} autonomous creative specs.")


if __name__ == "__main__":
    main()
