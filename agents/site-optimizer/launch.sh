#!/bin/bash
# Site Optimizer — Master Agent Launcher
#
# Dispatches Claude Code to run the autonomous optimization loop.
# Run this from the Mac terminal (cmux pane preferred).
#
# Usage:
#   bash agents/site-optimizer/launch.sh
#
# The agent will:
#   1. Read its program.md (instructions)
#   2. Read its config.json (current state)
#   3. Read AGENT-BRAIN.md (accumulated knowledge)
#   4. Run the autoresearch loop: propose → implement → evaluate → keep/discard
#   5. Post status to AGENT-MAILBOX.md and Slack
#   6. Never stop

AGENT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_DIR="$(cd "$AGENT_DIR/../.." && pwd)"

echo "=== Site Optimizer Agent ==="
echo "Agent dir: $AGENT_DIR"
echo "Repo dir:  $REPO_DIR"
echo "Target:    ~/agentrvm"
echo "Launching Claude Code..."

cd ~/agentrvm || { echo "ERROR: ~/agentrvm not found"; exit 1; }

# Build the prompt from program.md
PROMPT="You are the Site Optimizer master agent.

Read these files IN ORDER before doing anything:
1. $AGENT_DIR/program.md — your instructions (the autoresearch loop)
2. $AGENT_DIR/config.json — current optimization state
3. $AGENT_DIR/AGENT-BRAIN.md — accumulated knowledge and learnings
4. $REPO_DIR/WAR-RULES.md — team rules you must follow

Then:
1. Run the evaluation: python3 $AGENT_DIR/evaluate.py
2. Review the score and identify the highest-impact improvement
3. Implement ONE change following the experiment loop in program.md
4. Run evaluation again to measure impact
5. If improved: commit, update config.json and AGENT-BRAIN.md
6. If regressed: revert, log the failure
7. Post status to $REPO_DIR/AGENT-MAILBOX.md
8. Start the next experiment

Current priority from config.json priority_queue: audio-demo-below-hero

GO."

claude -p "$PROMPT" --dangerously-skip-permissions 2>&1 | tee "$AGENT_DIR/run.log"
