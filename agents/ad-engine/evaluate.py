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

# Import meta_ads for live API calls (optional — graceful if missing)
try:
    sys.path.insert(0, str(AGENT_DIR))
    from meta_ads import evaluate_campaigns as meta_evaluate_campaigns, get_campaign_insights, api_call
    HAS_META_API = True
except ImportError:
    HAS_META_API = False


def load_config() -> dict[str, Any]:
    with CONFIG_PATH.open() as f:
        return json.load(f)


def evaluate_creative_readiness() -> dict[str, Any]:
    """Check if we have the creative assets needed to launch."""
    experiments = list(EXPERIMENTS_DIR.glob("*.json"))

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
        "launch_ready": audio_ads >= 1 and len(experiments) >= 3,
    }


def evaluate_campaign_performance_live() -> dict[str, Any]:
    """Evaluate campaign performance from live Meta API data.

    Calls meta_ads.evaluate_campaigns() to pull real insights for all
    active campaigns, then aggregates into a single performance dict.
    """
    if not HAS_META_API:
        return evaluate_campaign_performance_offline()

    if not os.environ.get("META_ACCESS_TOKEN"):
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
    performance = evaluate_campaign_performance(live=live)

    # Composite score: 0-1
    # 40% creative readiness, 60% performance (when available)
    creative_score = creative["coverage_pct"] / 100 * 0.3 + (0.1 if creative["has_audio_creative"] else 0)

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
        "campaign_performance": performance,
        "data_source": performance.get("source", "offline"),
        "recommendation": _recommendation(creative, performance),
    }


def _recommendation(creative: dict, performance: dict) -> str:
    if not creative["launch_ready"]:
        missing = creative["angles_missing"]
        return f"NOT READY: Need {3 - creative['total_creatives']} more creatives. Missing angles: {', '.join(missing[:3])}"
    if performance["decision"] == "NO_DATA":
        return "READY TO LAUNCH: Creatives are set. Deploy campaigns and start collecting data."
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
    use_live = not args.mock and (args.live or bool(os.environ.get("META_ACCESS_TOKEN")))
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
