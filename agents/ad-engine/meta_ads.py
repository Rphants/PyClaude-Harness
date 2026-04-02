#!/usr/bin/env python3
"""Meta Ads API integration for the Ad Creative Engine.

This module handles campaign creation, ad set management, and performance
reporting via the Meta Marketing API v21.0.

Requires:
    - META_ACCESS_TOKEN env var (long-lived page/system user token)
    - Ad Account ID in config.json

Usage:
    # Create a draft campaign
    python meta_ads.py create-campaign --name "Audio-First v1" --objective OUTCOME_LEADS

    # Create an ad set
    python meta_ads.py create-adset --campaign-id 123 --name "Wholesalers Broad" --budget 500

    # Create an ad with audio creative
    python meta_ads.py create-ad --adset-id 456 --creative-spec experiments/audio-first-001.json

    # Pull performance report
    python meta_ads.py report --campaign-id 123 --metrics cpl,ctr,conversions

    # Evaluate all active campaigns against kill/keep/scale thresholds
    python meta_ads.py evaluate
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.request
import urllib.parse
import urllib.error
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

AGENT_DIR = Path(__file__).parent
CONFIG_PATH = AGENT_DIR / "config.json"
BRAIN_PATH = AGENT_DIR / "AGENT-BRAIN.md"
EXPERIMENTS_DIR = AGENT_DIR / "experiments"

API_VERSION = "v21.0"
BASE_URL = f"https://graph.facebook.com/{API_VERSION}"


# --- Config ---

def load_config() -> dict[str, Any]:
    with CONFIG_PATH.open() as f:
        return json.load(f)


def save_config(config: dict[str, Any]) -> None:
    with CONFIG_PATH.open("w") as f:
        json.dump(config, f, indent=2)
        f.write("\n")


def get_token() -> str:
    token = os.environ.get("META_ACCESS_TOKEN")
    if not token:
        print("ERROR: META_ACCESS_TOKEN env var not set.", file=sys.stderr)
        print("Get one at: https://developers.facebook.com/tools/explorer/", file=sys.stderr)
        print("Required permissions: ads_management, pages_manage_posts, pages_read_engagement", file=sys.stderr)
        sys.exit(1)
    return token


# --- API Helpers ---

def api_call(
    endpoint: str,
    method: str = "GET",
    params: dict[str, Any] | None = None,
    data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Make a Meta Graph API call."""
    token = get_token()
    url = f"{BASE_URL}/{endpoint}"

    if params is None:
        params = {}
    params["access_token"] = token

    if method == "GET":
        query = urllib.parse.urlencode(params)
        url = f"{url}?{query}"
        req = urllib.request.Request(url)
    else:
        if data:
            params.update(data)
        body = urllib.parse.urlencode(params).encode()
        req = urllib.request.Request(url, data=body, method=method)

    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        error_body = e.read().decode()
        print(f"API Error {e.code}: {error_body}", file=sys.stderr)
        raise


# --- Campaign Operations ---

def create_campaign(name: str, objective: str = "OUTCOME_LEADS", status: str = "PAUSED") -> dict:
    """Create a campaign in the ad account. Defaults to PAUSED for review."""
    config = load_config()
    ad_account = config["meta"]["ad_account"]

    result = api_call(
        f"{ad_account}/campaigns",
        method="POST",
        data={
            "name": name,
            "objective": objective,
            "status": status,
            "special_ad_categories": "[]",  # No special categories for B2B SaaS
        },
    )
    campaign_id = result.get("id")
    print(f"Campaign created: {campaign_id} (status={status})")

    # Update config
    config.setdefault("active_campaigns", []).append({
        "id": campaign_id,
        "name": name,
        "objective": objective,
        "status": status,
        "created": datetime.utcnow().isoformat() + "Z",
    })
    save_config(config)
    return result


def create_adset(
    campaign_id: str,
    name: str,
    daily_budget_cents: int = 500,  # $5.00
    audience: dict | None = None,
    status: str = "PAUSED",
) -> dict:
    """Create an ad set with targeting and budget."""
    config = load_config()
    ad_account = config["meta"]["ad_account"]
    pixel_id = config["meta"]["pixel_id"]

    # Default audience: wholesalers broad
    if audience is None:
        audience = config["audiences"][0]

    targeting = {
        "geo_locations": {"countries": ["US"]},
        "age_min": int(audience.get("age", "25-55").split("-")[0]),
        "age_max": int(audience.get("age", "25-55").split("-")[1]),
        "flexible_spec": [
            {"interests": [{"name": interest} for interest in audience.get("interests", [])]}
        ],
    }

    result = api_call(
        f"{ad_account}/adsets",
        method="POST",
        data={
            "name": name,
            "campaign_id": campaign_id,
            "daily_budget": str(daily_budget_cents),
            "billing_event": "IMPRESSIONS",
            "optimization_goal": "LEAD_GENERATION",
            "bid_strategy": "LOWEST_COST_WITHOUT_CAP",
            "targeting": json.dumps(targeting),
            "promoted_object": json.dumps({"pixel_id": pixel_id, "custom_event_type": "LEAD"}),
            "status": status,
            "start_time": (datetime.utcnow() + timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%S+0000"),
        },
    )
    print(f"Ad Set created: {result.get('id')} (budget=${daily_budget_cents/100:.2f}/day, status={status})")
    return result


def create_ad(
    adset_id: str,
    creative_spec_path: str,
    status: str = "PAUSED",
) -> dict:
    """Create an ad from a creative spec JSON file."""
    config = load_config()
    ad_account = config["meta"]["ad_account"]
    page_id = config["meta"]["page_id"]

    spec_path = Path(creative_spec_path)
    if not spec_path.is_absolute():
        spec_path = EXPERIMENTS_DIR / spec_path

    with spec_path.open() as f:
        spec = json.load(f)

    # Build ad creative
    creative_data = {
        "name": spec.get("name", "Ad Creative"),
        "object_story_spec": json.dumps({
            "page_id": page_id,
            "link_data": {
                "message": spec["primary_text"],
                "link": spec.get("url", "https://agentrvm.com"),
                "name": spec["headline"],
                "description": spec.get("description", ""),
                "call_to_action": {
                    "type": spec.get("cta_type", "LEARN_MORE"),
                    "value": {"link": spec.get("url", "https://agentrvm.com")},
                },
            },
        }),
    }

    # Create the ad creative first
    creative_result = api_call(
        f"{ad_account}/adcreatives",
        method="POST",
        data=creative_data,
    )
    creative_id = creative_result.get("id")
    print(f"Creative created: {creative_id}")

    # Then create the ad using that creative
    ad_result = api_call(
        f"{ad_account}/ads",
        method="POST",
        data={
            "name": spec.get("name", "Ad"),
            "adset_id": adset_id,
            "creative": json.dumps({"creative_id": creative_id}),
            "status": status,
        },
    )
    print(f"Ad created: {ad_result.get('id')} (status={status})")
    return ad_result


# --- Reporting ---

def get_campaign_insights(campaign_id: str, days: int = 7) -> dict:
    """Pull performance metrics for a campaign."""
    since = (datetime.utcnow() - timedelta(days=days)).strftime("%Y-%m-%d")
    until = datetime.utcnow().strftime("%Y-%m-%d")

    result = api_call(
        f"{campaign_id}/insights",
        params={
            "fields": "campaign_name,spend,impressions,clicks,ctr,cpc,actions,cost_per_action_type",
            "time_range": json.dumps({"since": since, "until": until}),
        },
    )
    return result


def evaluate_campaigns() -> list[dict]:
    """Evaluate all active campaigns against kill/keep/scale thresholds."""
    config = load_config()
    budget_rules = config["budget"]
    kill_cpl = budget_rules["kill_threshold_cpl"]
    keep_range = budget_rules["keep_range_cpl"]
    scale_cpl = budget_rules["scale_threshold_cpl"]

    decisions = []
    for campaign in config.get("active_campaigns", []):
        cid = campaign["id"]
        try:
            insights = get_campaign_insights(cid, days=3)
            data = insights.get("data", [{}])[0] if insights.get("data") else {}

            spend = float(data.get("spend", 0))
            leads = 0
            for action in data.get("actions", []):
                if action.get("action_type") == "lead":
                    leads = int(action.get("value", 0))

            cpl = spend / leads if leads > 0 else float("inf")

            if cpl > kill_cpl:
                decision = "KILL"
            elif cpl < scale_cpl:
                decision = "SCALE"
            else:
                decision = "KEEP"

            decisions.append({
                "campaign_id": cid,
                "name": campaign["name"],
                "spend": spend,
                "leads": leads,
                "cpl": round(cpl, 2) if cpl != float("inf") else "no_leads",
                "decision": decision,
            })
            print(f"  {campaign['name']}: ${spend:.2f} spent, {leads} leads, CPL=${cpl:.2f} → {decision}")

        except Exception as e:
            decisions.append({
                "campaign_id": cid,
                "name": campaign["name"],
                "error": str(e),
                "decision": "CHECK",
            })
            print(f"  {campaign['name']}: ERROR — {e}")

    return decisions


# --- CLI ---

def main():
    parser = argparse.ArgumentParser(description="Meta Ads API for Ad Creative Engine")
    sub = parser.add_subparsers(dest="command")

    # create-campaign
    cc = sub.add_parser("create-campaign")
    cc.add_argument("--name", required=True)
    cc.add_argument("--objective", default="OUTCOME_LEADS")
    cc.add_argument("--status", default="PAUSED", choices=["PAUSED", "ACTIVE"])

    # create-adset
    ca = sub.add_parser("create-adset")
    ca.add_argument("--campaign-id", required=True)
    ca.add_argument("--name", required=True)
    ca.add_argument("--budget", type=int, default=500, help="Daily budget in cents (default: 500 = $5)")
    ca.add_argument("--audience", default="wholesalers-broad")
    ca.add_argument("--status", default="PAUSED")

    # create-ad
    cad = sub.add_parser("create-ad")
    cad.add_argument("--adset-id", required=True)
    cad.add_argument("--creative-spec", required=True, help="Path to creative spec JSON")
    cad.add_argument("--status", default="PAUSED")

    # report
    rp = sub.add_parser("report")
    rp.add_argument("--campaign-id", required=True)
    rp.add_argument("--days", type=int, default=7)

    # evaluate
    sub.add_parser("evaluate")

    args = parser.parse_args()

    if args.command == "create-campaign":
        create_campaign(args.name, args.objective, args.status)
    elif args.command == "create-adset":
        config = load_config()
        audience = next((a for a in config["audiences"] if a["name"] == args.audience), None)
        create_adset(args.campaign_id, args.name, args.budget, audience, args.status)
    elif args.command == "create-ad":
        create_ad(args.adset_id, args.creative_spec, args.status)
    elif args.command == "report":
        result = get_campaign_insights(args.campaign_id, args.days)
        print(json.dumps(result, indent=2))
    elif args.command == "evaluate":
        evaluate_campaigns()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
