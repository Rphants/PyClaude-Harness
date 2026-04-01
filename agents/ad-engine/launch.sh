#!/bin/bash
AGENT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_DIR="$(cd "$AGENT_DIR/../.." && pwd)"

echo "=== Ad Creative Engine ==="
cd "$REPO_DIR" || exit 1

codex exec --full-auto "You are the Ad Creative Engine master agent.

Read these files IN ORDER:
1. $AGENT_DIR/program.md
2. $AGENT_DIR/config.json
3. $AGENT_DIR/AGENT-BRAIN.md
4. $REPO_DIR/WAR-RULES.md
5. $REPO_DIR/agents/vibevoice-producer/AGENT-BRAIN.md (for latest audio samples)

Then design 6 audio-focused ad concepts and save to $AGENT_DIR/experiments/batch-001.json.
Update $AGENT_DIR/AGENT-BRAIN.md with findings.
Post status to $REPO_DIR/AGENT-MAILBOX.md.

GO." 2>&1 | tee "$AGENT_DIR/run.log"
