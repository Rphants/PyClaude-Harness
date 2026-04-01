#!/bin/bash
AGENT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_DIR="$(cd "$AGENT_DIR/../.." && pwd)"

echo "=== Lead Nurture Agent ==="
cd "$REPO_DIR" || exit 1

codex exec --full-auto "You are the Lead Nurture master agent.

Read these files IN ORDER:
1. $AGENT_DIR/program.md
2. $AGENT_DIR/config.json
3. $AGENT_DIR/AGENT-BRAIN.md
4. $REPO_DIR/WAR-RULES.md

Then analyze the #agentrvm-leads channel structure and design the lead scoring model.
Save to $AGENT_DIR/experiments/scoring-model-v1.json.
Update $AGENT_DIR/AGENT-BRAIN.md.
Post status to $REPO_DIR/AGENT-MAILBOX.md.

GO." 2>&1 | tee "$AGENT_DIR/run.log"
