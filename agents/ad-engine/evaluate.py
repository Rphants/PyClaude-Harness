#!/usr/bin/env python3
"""Ad Creative Engine — Evaluator

Objective measurement of ad campaign performance against revenue targets.
This is the ground truth scorer — agents cannot modify this file.

Metrics:
    1. CPL (Cost Per Lead) — primary optimization target
    2. CTR (Click-Through Rate) — creative quality signal
    3. Lead Volume — total leads generated
    4. Budget Efficiency — % of budget producing leads vs wasted
    5. Creative Coverage — are all angles being tested?
    6. Audio Ad Presence — do we have audio-first creatives deployed?

Kill/Keep/Scale thresholds from config.json budget rules.

Usage:
    python evaluate.py                    # Evaluate from Meta API (live)
    python evaluate.py --mock             # Evaluate from experiment files (offline)
    python evaluate.py --report output.json  # Write evaluation report
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

AGENT_DIR = Path(__file__).parent
CONFIG_PATH = AGENT_DIR / "config.json"
EXPERIMENTS_DIR = AGENT_DIR / "experiments"
FORBIDDEN_PRODUCT_CLAIMS = (
    "answers your phone",
    "answers 24/7",
    "answering service",
    "answers calls",
)
PREFERRED_META_TERMS = (
    "seller",
    "signal",
    "callback",
    "outreach",
    "intent",
    "margin",
    "competitor",
    "first",
    "follow-up",
    "dial",
)
PROOF_TERMS = (
    "callback",
    "margin",
    "first",
    "detected",
    "intent",
    "rate",
    "proof",
)
GENERIC_MARKETING_TERMS = (
    "platform",
    "solution",
    "innovative",
    "seamless",
    "smarter teams",
    "used by wholesalers",
    "hear why",
)
META_POLICY_RISK_TERMS = (
    "for sale",
    "rent",
    "mortgage",
    "brokerage",
    "loan",
    "housing",
)

# Import meta_ads for live API calls (optional — graceful if missing)
try:
    sys.path.insert(0, str(AGENT_DIR))
    from meta_ads import (
        api_call,
        evaluate_campaigns as meta_evaluate_campaigns,
        get_campaign_insights,
        get_token_value as get_meta_token_value,
    )
    HAS_META_API = True
except ImportError:
    HAS_META_API = False
    get_meta_token_value = None


def load_config() -> dict[str, Any]:
    with CONFIG_PATH.open() as f:
        return json.load(f)


def creative_spec_paths() -> list[Path]:
    """Prefer autonomous agent-generated specs when they exist."""
    auto_specs = sorted(
        p for p in EXPERIMENTS_DIR.glob("auto-*.json") if p.name != "auto-batch.json"
    )
    if auto_specs:
        return auto_specs
    return sorted(EXPERIMENTS_DIR.glob("*.json"))


def _copy_metrics(spec: dict[str, Any], spec_name: str) -> dict[str, Any]:
    headline = str(spec.get("headline") or spec.get("creative", {}).get("headline", "")).strip()
    primary_text = str(spec.get("primary_text") or spec.get("creative", {}).get("primary_text", "")).strip()
    description = str(spec.get("description") or spec.get("creative", {}).get("description", "")).strip()
    proof_text = str(spec.get("proof_text") or "").strip()
    cta_text = str(spec.get("cta") or spec.get("creative", {}).get("cta", "")).strip()
    cta_type = spec.get("cta_type") or spec.get("creative", {}).get("cta_type")
    url = spec.get("url") or spec.get("creative", {}).get("url")
    hypothesis = spec.get("hypothesis")
    angle = str(spec.get("angle") or "")
    combined_text = " ".join(
        part for part in (headline, primary_text, description, proof_text, cta_text, angle) if part
    ).lower()

    score = 0
    possible = 16
    notes: list[str] = []
    violations: list[str] = []

    if headline:
        score += 1
    else:
        notes.append("missing headline")

    if 14 <= len(headline) <= 40:
        score += 1
    else:
        notes.append("headline not in ideal Meta hook range")

    if 55 <= len(primary_text) <= 125:
        score += 1
    elif primary_text:
        score += 0.5
        notes.append("primary text is present but not in ideal length range")
    else:
        notes.append("missing primary text")

    if cta_text and len(cta_text) <= 18:
        score += 1
    elif cta_type and url:
        score += 0.5
        notes.append("CTA type exists but CTA copy is weak or missing")
    else:
        notes.append("missing usable CTA")

    if hypothesis:
        score += 1

    preferred_hits = sum(1 for term in PREFERRED_META_TERMS if term in combined_text)
    if preferred_hits >= 4:
        score += 2
    elif preferred_hits >= 2:
        score += 1
    else:
        notes.append("copy lacks operator-specific Meta language")

    proof_hits = sum(1 for term in PROOF_TERMS if term in combined_text)
    if proof_text:
        score += 1
    if proof_hits >= 2 or any(ch.isdigit() for ch in combined_text) or "$" in combined_text or "%" in combined_text:
        score += 2
    elif proof_hits >= 1:
        score += 1
    else:
        notes.append("copy lacks strong proof device")

    if any(term in combined_text for term in ("first", "before", "late", "faster", "competitor", "already")):
        score += 2
    else:
        notes.append("copy underplays first-mover advantage")

    if any(term in combined_text for term in ("seller signal", "seller intent", "intent", "signal")):
        score += 2
    elif "seller" in combined_text:
        score += 1
    else:
        notes.append("seller-signal intelligence is not explicit enough")

    if any(bad in combined_text for bad in FORBIDDEN_PRODUCT_CLAIMS):
        violations.extend(
            f"{spec_name}: contains forbidden claim '{bad_claim}'"
            for bad_claim in FORBIDDEN_PRODUCT_CLAIMS
            if bad_claim in combined_text
        )
        score -= 6

    generic_hits = [term for term in GENERIC_MARKETING_TERMS if term in combined_text]
    if generic_hits:
        score -= min(3, len(generic_hits))
        notes.append(f"generic marketing language: {', '.join(generic_hits[:2])}")

    if any(term in combined_text for term in META_POLICY_RISK_TERMS):
        notes.append("review for Meta housing/special-category risk")

    normalized = max(0.0, min(100.0, round((score / possible) * 100, 1)))
    return {
        "score": normalized,
        "headline": headline,
        "primary_text": primary_text,
        "cta": cta_text,
        "proof_text": proof_text,
        "angle": angle,
        "notes": notes,
        "violations": violations,
        "combined_text": combined_text,
    }


def _batch_meta_metrics(copy_metrics: list[dict[str, Any]]) -> dict[str, Any]:
    if not copy_metrics:
        return {
            "batch_score_pct": 0.0,
            "headline_uniqueness_pct": 0.0,
            "concept_separation_pct": 0.0,
            "average_copy_score_pct": 0.0,
        }

    headlines = [m["headline"].strip().lower() for m in copy_metrics if m["headline"].strip()]
    unique_headlines = len(set(headlines))
    headline_uniqueness = round((unique_headlines / max(1, len(copy_metrics))) * 100, 1)

    concept_signatures = []
    for metric in copy_metrics:
        text = metric["combined_text"]
        signature = tuple(
            int(any(term in text for term in group))
            for group in (
                ("callback", "proof"),
                ("first", "before", "late", "competitor", "already"),
                ("seller signal", "seller intent", "intent", "signal"),
                ("margin", "$", "%", "roi", "pay"),
                ("audio", "voice", "voicemail", "play"),
            )
        )
        concept_signatures.append(signature)
    concept_separation = round((len(set(concept_signatures)) / max(1, len(copy_metrics))) * 100, 1)
    average_copy_score = round(sum(m["score"] for m in copy_metrics) / len(copy_metrics), 1)
    batch_score = round((headline_uniqueness * 0.35) + (concept_separation * 0.25) + (average_copy_score * 0.4), 1)
    return {
        "batch_score_pct": batch_score,
        "headline_uniqueness_pct": headline_uniqueness,
        "concept_separation_pct": concept_separation,
        "average_copy_score_pct": average_copy_score,
    }


def evaluate_asset_integrity() -> dict[str, Any]:
    """Verify that experiment specs point to real asset files and sane copy."""
    specs = creative_spec_paths()
    evaluated = 0
    deliverable = 0
    audio_deliverable = 0
    static_deliverable = 0
    missing_assets: list[str] = []
    product_truth_violations: list[str] = []
    copy_metrics: list[dict[str, Any]] = []
    policy_warnings: list[str] = []

    for spec_path in specs:
        try:
            spec = json.loads(spec_path.read_text())
        except json.JSONDecodeError:
            missing_assets.append(f"{spec_path.name}: invalid JSON")
            continue

        evaluated += 1
        metric = _copy_metrics(spec, spec_path.name)
        copy_metrics.append(metric)
        product_truth_violations.extend(metric["violations"])
        policy_warnings.extend(
            f"{spec_path.name}: {note}"
            for note in metric["notes"]
            if "special-category risk" in note
        )
        asset_ready = False

        if spec.get("type") == "audio":
            audio_file = spec.get("creative", {}).get("audio", {}).get("file")
            if audio_file and (EXPERIMENTS_DIR / audio_file).exists():
                asset_ready = True
                audio_deliverable += 1
            else:
                missing_assets.append(f"{spec_path.name}: missing audio file {audio_file}")
        else:
            image_path = spec.get("image_path")
            if image_path and (EXPERIMENTS_DIR / image_path).exists():
                asset_ready = True
                static_deliverable += 1
            else:
                missing_assets.append(f"{spec_path.name}: missing image {image_path}")

        if asset_ready:
            deliverable += 1

    batch_metrics = _batch_meta_metrics(copy_metrics)
    quality_score = batch_metrics["average_copy_score_pct"]
    deliverable_ratio = round(deliverable / evaluated, 3) if evaluated else 0.0

    return {
        "evaluated_creatives": evaluated,
        "deliverable_creatives": deliverable,
        "deliverable_ratio": deliverable_ratio,
        "audio_deliverable": audio_deliverable,
        "static_deliverable": static_deliverable,
        "quality_score_pct": quality_score,
        "meta_batch_score_pct": batch_metrics["batch_score_pct"],
        "headline_uniqueness_pct": batch_metrics["headline_uniqueness_pct"],
        "concept_separation_pct": batch_metrics["concept_separation_pct"],
        "missing_assets": missing_assets,
        "product_truth_violations": product_truth_violations,
        "policy_warnings": policy_warnings,
        "copy_breakdown": [
            {
                "angle": metric["angle"],
                "headline": metric["headline"],
                "score_pct": metric["score"],
                "notes": metric["notes"],
            }
            for metric in copy_metrics
        ],
    }


def evaluate_creative_readiness() -> dict[str, Any]:
    """Check if we have the creative assets needed to launch."""
    experiments = creative_spec_paths()

    # Count by type
    audio_ads = 0
    static_ads = 0
    angles_covered = set()

    for exp_path in experiments:
        try:
            with exp_path.open() as f:
                spec = json.load(f)
            if spec.get("type") == "audio":
                audio_ads += 1
            else:
                static_ads += 1
            if "angle" in spec:
                angles_covered.add(spec["angle"])
        except (json.JSONDecodeError, KeyError):
            continue

    required_angles = {"audio-first", "roi", "pain-point", "fomo", "curiosity", "social-proof"}
    missing_angles = required_angles - angles_covered

    return {
        "total_creatives": len(experiments),
        "audio_ads": audio_ads,
        "static_ads": static_ads,
        "angles_covered": sorted(angles_covered),
        "angles_missing": sorted(missing_angles),
        "has_audio_creative": audio_ads > 0,
        "coverage_pct": round(len(angles_covered) / len(required_angles) * 100, 1),
        "launch_ready": len(experiments) >= 3,
    }


def evaluate_campaign_performance_live() -> dict[str, Any]:
    """Evaluate campaign performance from live Meta API data.

    Calls meta_ads.evaluate_campaigns() to pull real insights for all
    active campaigns, then aggregates into a single performance dict.
    """
    if not HAS_META_API:
        return evaluate_campaign_performance_offline()

    if not get_meta_token_value or not get_meta_token_value():
        return evaluate_campaign_performance_offline()

    config = load_config()
    budget = config["budget"]

    try:
        decisions = meta_evaluate_campaigns()
    except Exception as exc:
        print(f"Meta API call failed, falling back to offline: {exc}", file=sys.stderr)
        return evaluate_campaign_performance_offline()

    if not decisions:
        return evaluate_campaign_performance_offline()

    # Aggregate across all campaigns
    total_spend = sum(d.get("spend", 0) for d in decisions if isinstance(d.get("spend"), (int, float)))
    total_leads = sum(d.get("leads", 0) for d in decisions if isinstance(d.get("leads"), (int, float)))
    cpl = total_spend / total_leads if total_leads > 0 else None

    # Per-campaign breakdown
    campaign_decisions = []
    for d in decisions:
        campaign_decisions.append({
            "campaign_id": d.get("campaign_id"),
            "name": d.get("name"),
            "spend": d.get("spend"),
            "leads": d.get("leads"),
            "cpl": d.get("cpl"),
            "decision": d.get("decision"),
        })

    # Overall decision
    if cpl is None:
        decision = "NO_DATA"
    elif cpl > budget["kill_threshold_cpl"]:
        decision = "KILL"
    elif cpl < budget["scale_threshold_cpl"]:
        decision = "SCALE"
    else:
        decision = "KEEP"

    daily_start = budget.get("daily_start", budget.get("daily_budget_usd", 50))
    efficiency = total_leads / (total_spend / daily_start) if total_spend > 0 else 0

    return {
        "source": "live",
        "total_spend": round(total_spend, 2),
        "total_leads": total_leads,
        "cpl": round(cpl, 2) if cpl else None,
        "decision": decision,
        "kill_threshold": budget["kill_threshold_cpl"],
        "keep_range": budget.get("keep_range_cpl"),
        "scale_threshold": budget["scale_threshold_cpl"],
        "efficiency_score": round(efficiency, 3),
        "campaigns": campaign_decisions,
    }


def evaluate_campaign_performance_offline(insights: list[dict] | None = None) -> dict[str, Any]:
    """Evaluate campaign performance from local config state (mock/offline)."""
    config = load_config()
    budget = config["budget"]

    if insights is None:
        total_spend = config.get("total_spend", 0)
        total_leads = config.get("total_leads", 0)
    else:
        total_spend = sum(float(i.get("spend", 0)) for i in insights)
        total_leads = sum(
            int(a.get("value", 0))
            for i in insights
            for a in i.get("actions", [])
            if a.get("action_type") == "lead"
        )

    cpl = total_spend / total_leads if total_leads > 0 else None
    daily_start = budget.get("daily_start", budget.get("daily_budget_usd", 50))
    efficiency = total_leads / (total_spend / daily_start) if total_spend > 0 else 0

    if cpl is None:
        decision = "NO_DATA"
    elif cpl > budget["kill_threshold_cpl"]:
        decision = "KILL"
    elif cpl < budget["scale_threshold_cpl"]:
        decision = "SCALE"
    else:
        decision = "KEEP"

    return {
        "source": "offline",
        "total_spend": round(total_spend, 2),
        "total_leads": total_leads,
        "cpl": round(cpl, 2) if cpl else None,
        "decision": decision,
        "kill_threshold": budget["kill_threshold_cpl"],
        "keep_range": budget.get("keep_range_cpl"),
        "scale_threshold": budget["scale_threshold_cpl"],
        "efficiency_score": round(efficiency, 3),
    }


def evaluate_campaign_performance(insights: list[dict] | None = None, *, live: bool = False) -> dict[str, Any]:
    """Evaluate campaign performance. Uses live API if available and requested."""
    if live:
        return evaluate_campaign_performance_live()
    return evaluate_campaign_performance_offline(insights)


def evaluate_all(*, live: bool = False) -> dict[str, Any]:
    """Full evaluation: creative readiness + performance.

    Args:
        live: If True, pull real data from Meta API. Otherwise use local files.
    """
    creative = evaluate_creative_readiness()
    asset_integrity = evaluate_asset_integrity()
    performance = evaluate_campaign_performance(live=live)

    # Composite score: 0-1
    # 40% creative system quality, 60% performance (when available)
    creative_score = (
        (creative["coverage_pct"] / 100) * 0.2
        + asset_integrity["deliverable_ratio"] * 0.15
        + (asset_integrity["quality_score_pct"] / 100) * 0.08
        + (asset_integrity["meta_batch_score_pct"] / 100) * 0.07
    )

    if performance["cpl"] is not None:
        # Lower CPL = better. Scale: $0 = 1.0, $15+ = 0.0
        cpl_score = max(0, 1 - performance["cpl"] / performance["kill_threshold"])
        perf_score = cpl_score * 0.6
    else:
        perf_score = 0

    composite = round(creative_score + perf_score, 4)

    return {
        "composite_score": composite,
        "creative_readiness": creative,
        "asset_integrity": asset_integrity,
        "campaign_performance": performance,
        "data_source": performance.get("source", "offline"),
        "recommendation": _recommendation(creative, asset_integrity, performance),
    }


def _recommendation(creative: dict, asset_integrity: dict, performance: dict) -> str:
    if not creative["launch_ready"]:
        missing = creative["angles_missing"]
        return f"NOT READY: Need {3 - creative['total_creatives']} more creatives. Missing angles: {', '.join(missing[:3])}"
    if asset_integrity["product_truth_violations"]:
        first_violation = asset_integrity["product_truth_violations"][0]
        return f"POSITIONING DRIFT: creative copy still violates product truth. First issue: {first_violation}"
    if asset_integrity["missing_assets"]:
        first_missing = asset_integrity["missing_assets"][0]
        return f"ASSETS INCOMPLETE: {asset_integrity['deliverable_creatives']}/{asset_integrity['evaluated_creatives']} creatives are deployable. First missing asset: {first_missing}"
    if asset_integrity.get("meta_batch_score_pct", 0) < 70:
        return "META FIT WEAK: concepts are deployable, but the batch still needs stronger hook variety or proof devices."
    if performance["decision"] == "NO_DATA":
        return "CREATIVES READY: Coverage is broad, but live spend data is still missing."
    if performance["decision"] == "KILL":
        return f"KILL: CPL ${performance['cpl']} exceeds ${performance['kill_threshold']} threshold. Refresh creatives."
    if performance["decision"] == "SCALE":
        return f"SCALE: CPL ${performance['cpl']} below ${performance['scale_threshold']}. Increase budget 25%."
    return f"KEEP: CPL ${performance['cpl']} in range. Continue optimizing."


def main():
    parser = argparse.ArgumentParser(description="Ad Creative Engine Evaluator")
    parser.add_argument("--mock", action="store_true", help="Evaluate from local files only (offline)")
    parser.add_argument("--live", action="store_true", help="Pull real data from Meta API")
    parser.add_argument("--json", action="store_true", help="Output only JSON (for harness bridge)")
    parser.add_argument("--report", type=str, help="Write JSON report to file")
    args = parser.parse_args()

    # --mock forces offline, --live forces live, default = try live then fallback
    use_live = not args.mock and (args.live or bool(get_meta_token_value and get_meta_token_value()))
    result = evaluate_all(live=use_live)

    # JSON-only mode for autoresearch harness bridge
    if args.json:
        print(json.dumps(result))
        sys.exit(0)

    print(f"\n=== Ad Creative Engine Evaluation ===")
    print(f"Composite Score: {result['composite_score']}")
    print(f"Data Source: {result.get('data_source', 'offline')}")
    print(f"\nCreative Readiness:")
    cr = result["creative_readiness"]
    print(f"  Total creatives: {cr['total_creatives']}")
    print(f"  Audio ads: {cr['audio_ads']}")
    print(f"  Angle coverage: {cr['coverage_pct']}% ({', '.join(cr['angles_covered']) or 'none'})")
    print(f"  Launch ready: {'YES' if cr['launch_ready'] else 'NO'}")

    print(f"\nCampaign Performance:")
    cp = result["campaign_performance"]
    print(f"  Source: {cp.get('source', 'offline')}")
    print(f"  Spend: ${cp['total_spend']}")
    print(f"  Leads: {cp['total_leads']}")
    print(f"  CPL: {'$' + str(cp['cpl']) if cp['cpl'] else 'no data'}")
    print(f"  Decision: {cp['decision']}")

    # Show per-campaign breakdown if live data
    if cp.get("campaigns"):
        print(f"\n  Per-Campaign Breakdown:")
        for c in cp["campaigns"]:
            print(f"    {c['name']}: ${c.get('spend', 0):.2f} / {c.get('leads', 0)} leads / CPL={'$' + str(c['cpl']) if c.get('cpl') else 'N/A'} → {c['decision']}")

    print(f"\nRecommendation: {result['recommendation']}")

    if args.report:
        with open(args.report, "w") as f:
            json.dump(result, f, indent=2)
        print(f"\nReport written to {args.report}")

    # Exit code: 0 if launch ready, 1 if not
    sys.exit(0 if cr["launch_ready"] else 1)


if __name__ == "__main__":
    main()
