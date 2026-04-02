#!/bin/bash
# === Ad Creative Engine — CMUX-Wrapped Launch ===
#
# Modes:
#   launch.sh                      — full autonomous loop (autoresearch)
#   launch.sh --creatives          — generate creatives only
#   launch.sh --evaluate           — run evaluation only
#   launch.sh --deploy             — deploy to Meta only
#
# Secrets loaded via secrets-manager Worker (or env var override).
# Heartbeats emitted to CMUX for health monitoring.

set -euo pipefail

AGENT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_DIR="$(cd "$AGENT_DIR/../.." && pwd)"
AGENT_CALLSIGN="${AGENT_CALLSIGN:-ad-engine}"
TASK="${TASK:-autonomous ad creative loop}"
BRANCH="${BRANCH:-}"
CORRELATION_ID="${CORRELATION_ID:-ad-engine-$$}"
MODE="${1:-full}"

echo "=== Ad Creative Engine | $AGENT_CALLSIGN ==="
echo "Time: $(date -u +'%Y-%m-%d %H:%M:%S UTC')"
echo "Mode: $MODE"
echo "Correlation: $CORRELATION_ID"
echo ""

# --- Step 1: Load secrets from secrets-manager ---
echo "Step 1: Loading secrets..."
cd "$REPO_DIR"

# Export all secrets this agent needs (from secrets-manifest.json)
SECRETS_EXPORT=$(python3 -m src.coordinator.secrets export ad-engine 2>/dev/null || echo "")
if [ -n "$SECRETS_EXPORT" ]; then
    eval "$SECRETS_EXPORT"
    echo "  Loaded secrets from secrets-manager"
else
    echo "  WARNING: No secrets loaded from secrets-manager (env vars or local fallback)"
fi

# Verify critical secrets
echo "  META_ACCESS_TOKEN: ${META_ACCESS_TOKEN:+set (${#META_ACCESS_TOKEN} chars)}${META_ACCESS_TOKEN:-NOT SET}"
echo "  CANVA_CLIENT_ID: ${CANVA_CLIENT_ID:+set}${CANVA_CLIENT_ID:-NOT SET}"
echo "  CANVA_CLIENT_SECRET: ${CANVA_CLIENT_SECRET:+set}${CANVA_CLIENT_SECRET:-NOT SET}"
echo "  CANVA_REFRESH_TOKEN: ${CANVA_REFRESH_TOKEN:+set}${CANVA_REFRESH_TOKEN:-NOT SET}"
echo "  CANVA_ACCESS_TOKEN: ${CANVA_ACCESS_TOKEN:+set}${CANVA_ACCESS_TOKEN:-NOT SET}"
echo "  FIGMA_ACCESS_TOKEN: ${FIGMA_ACCESS_TOKEN:+set}${FIGMA_ACCESS_TOKEN:-NOT SET}"
echo ""

# --- Step 2: Heartbeat — STARTING ---
heartbeat() {
    local status="$1"
    local claim="${2:-$TASK}"
    local proof="${3:-idea}"
    local branch_flag=""
    [ -n "${BRANCH:-}" ] && branch_flag="--branch $BRANCH"

    cd "$REPO_DIR"
    python3 -m src.coordinator.heartbeat send \
        --sender "$AGENT_CALLSIGN" \
        --status "$status" \
        --claim "$claim" \
        --proof "$proof" \
        --correlation-id "$CORRELATION_ID" \
        $branch_flag \
        2>/dev/null || true
}

heartbeat "working" "$TASK" "idea"

# --- Step 3: Execute based on mode ---
cd "$AGENT_DIR"
EXIT_CODE=0

case "$MODE" in
    --creatives)
        echo "Step 3: Generating creatives..."
        python3 creative_generator.py \
            --template stats-card \
            --headline "10,000 Voicemails. Zero Phone Calls." \
            --stats '[["Callback Rate", "40%"], ["Cost Per Message", "$0.001"]]' \
            --cta "Get Early Access" \
            --output experiments/preview-stats-card.png || true

        python3 creative_generator.py \
            --template testimonial \
            --headline "40% callback rate." \
            --quote "This is the best tool I have used." \
            --author "Sarah, Texas Wholesaler" \
            --cta "Get Early Access" \
            --output experiments/preview-testimonial.png || true

        python3 creative_generator.py \
            --template single-image \
            --headline "While you dial, your competitor's AI left 500 voicemails." \
            --body "Press play. Hear why 47 wholesalers already switched." \
            --cta "Join the Waitlist" \
            --output experiments/preview-fomo.png || true
        echo "  Creatives generated"
        ;;

    --evaluate)
        echo "Step 3: Running evaluation..."
        python3 evaluate.py --report experiments/latest-eval.json
        EXIT_CODE=$?
        ;;

    --deploy)
        echo "Step 3: Deploying to Meta..."
        if [ -z "${META_ACCESS_TOKEN:-}" ]; then
            echo "  ERROR: META_ACCESS_TOKEN not set. Cannot deploy."
            EXIT_CODE=1
        else
            python3 meta_ads.py evaluate
            echo "  Campaign evaluation complete"
        fi
        ;;

    full|--full)
        echo "Step 3: Running full autonomous loop..."

        # 3a: Evaluate current state
        echo "  3a: Baseline evaluation..."
        python3 evaluate.py --json > /tmp/ad-engine-baseline.json 2>/dev/null || true
        heartbeat "working" "baseline evaluation complete" "idea"

        # 3b: Run autoresearch loop
        echo "  3b: Starting autoresearch loop..."
        python3 autoresearch.py --max-experiments 10 2>&1 | tee "$AGENT_DIR/run.log"
        EXIT_CODE=${PIPESTATUS[0]}

        # 3c: Final evaluation
        echo "  3c: Final evaluation..."
        python3 evaluate.py --report experiments/latest-eval.json || true
        heartbeat "working" "autoresearch loop finished" "worktree-pass"

        # 3d: Deploy winners (if we have a token and campaigns improved)
        if [ -n "${META_ACCESS_TOKEN:-}" ] && [ $EXIT_CODE -eq 0 ]; then
            echo "  3d: Evaluating active campaigns..."
            python3 meta_ads.py evaluate || true
        fi
        ;;

    *)
        echo "Unknown mode: $MODE"
        echo "Usage: launch.sh [--creatives|--evaluate|--deploy|--full]"
        EXIT_CODE=1
        ;;
esac

# --- Step 4: Result heartbeat ---
if [ $EXIT_CODE -eq 0 ]; then
    heartbeat "done" "Completed: $TASK" "worktree-pass"
    echo ""
    echo "=== $AGENT_CALLSIGN DONE (exit 0) ==="
else
    heartbeat "blocked" "FAILED (exit $EXIT_CODE): $TASK" "idea"
    echo ""
    echo "=== $AGENT_CALLSIGN FAILED (exit $EXIT_CODE) ==="
fi

exit $EXIT_CODE
