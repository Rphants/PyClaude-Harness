#!/bin/bash
# === CMUX-Wrapped Agent Launcher Template ===
#
# This template shows how every agent launch should work.
# Copy and customize for each agent.
#
# What it does:
#   1. Emits STARTING heartbeat to CMUX
#   2. Runs the agent
#   3. Emits DONE or FAILED heartbeat based on exit code
#   4. Logs output for post-mortem
#
# Required env vars:
#   AGENT_CALLSIGN  — e.g. "claude-1", "codex-1"
#   AGENT_DIR       — path to agent directory (has program.md, config.json, etc.)
#   RUNNER          — "claude -p" or "codex exec --full-auto"
#   TASK            — one-line task description
#   BRANCH          — git branch (optional)
#   CORRELATION_ID  — CMUX thread ID (optional, auto-generated if empty)

set -euo pipefail

AGENT_CALLSIGN="${AGENT_CALLSIGN:?Set AGENT_CALLSIGN}"
AGENT_DIR="${AGENT_DIR:?Set AGENT_DIR}"
RUNNER="${RUNNER:-claude -p}"
TASK="${TASK:-autonomous loop}"
BRANCH="${BRANCH:-}"
CORRELATION_ID="${CORRELATION_ID:-${TASK// /-}-$$}"
REPO_DIR="$(cd "$AGENT_DIR/../.." && pwd)"

# --- Heartbeat helper ---
heartbeat() {
    local status="$1"
    local claim="${2:-$TASK}"
    local proof="${3:-idea}"
    local branch_flag=""
    [ -n "$BRANCH" ] && branch_flag="--branch $BRANCH"

    cd "$REPO_DIR"
    python -m src.coordinator.heartbeat \
        --sender "$AGENT_CALLSIGN" \
        --status "$status" \
        --claim "$claim" \
        --proof "$proof" \
        --correlation-id "$CORRELATION_ID" \
        $branch_flag \
        2>/dev/null || true
}

# --- Pane label ---
echo "=== $AGENT_CALLSIGN | $(echo $RUNNER | cut -d' ' -f1 | tr '[:lower:]' '[:upper:]') ==="
echo "Task: $TASK"
echo "Correlation: $CORRELATION_ID"
echo "Agent dir: $AGENT_DIR"
echo ""

# --- Step 1: STARTING heartbeat ---
heartbeat "working" "$TASK" "idea"

# --- Step 2: Build prompt from agent files ---
BRIEF_FILE="/tmp/${AGENT_CALLSIGN}-brief.txt"
cat > "$BRIEF_FILE" << BRIEF
You are the $AGENT_CALLSIGN agent.

Read these files IN ORDER before doing anything:
1. $AGENT_DIR/program.md — your instructions
2. $AGENT_DIR/config.json — current state
3. $AGENT_DIR/AGENT-BRAIN.md — accumulated knowledge
4. $REPO_DIR/WAR-RULES.md — team rules
5. $REPO_DIR/AUTONOMY.md — your freedoms and boundaries

Your task: $TASK

After completing your task:
- Update $AGENT_DIR/AGENT-BRAIN.md with what you learned
- Update $AGENT_DIR/config.json if state changed
- Emit a heartbeat: python -m src.coordinator.heartbeat --sender $AGENT_CALLSIGN --status done --claim "<what you did>" --proof worktree-pass

GO.
BRIEF

# --- Step 3: Run agent ---
cd ~/agentrvm 2>/dev/null || cd "$REPO_DIR"

if [[ "$RUNNER" == *"codex"* ]]; then
    $RUNNER "$(cat $BRIEF_FILE)" 2>&1 | tee "$AGENT_DIR/run.log"
else
    $RUNNER "$(cat $BRIEF_FILE)" --dangerously-skip-permissions 2>&1 | tee "$AGENT_DIR/run.log"
fi
EXIT_CODE=${PIPESTATUS[0]}

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
