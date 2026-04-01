#!/bin/bash
AGENT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_DIR="$(cd "$AGENT_DIR/../.." && pwd)"
TARGET_DIR="/Users/ronaldbigger/Documents/New project/voice-lab-platform"

echo "=== VibeVoice Producer Agent ==="
echo "Agent dir: $AGENT_DIR"
echo "Target:    $TARGET_DIR"
echo "Launching Claude Code..."

cd "$TARGET_DIR" || { echo "ERROR: voice-lab-platform not found"; exit 1; }

claude -p "You are the VibeVoice Producer master agent.

Read these files IN ORDER:
1. $AGENT_DIR/program.md — your instructions
2. $AGENT_DIR/config.json — current state and settings
3. $AGENT_DIR/AGENT-BRAIN.md — accumulated knowledge
4. $REPO_DIR/WAR-RULES.md — team rules

Then:
1. Explore this voice-lab-platform repo structure
2. Find any existing audio samples (.wav, .mp3, .webm)
3. Check API endpoints and presets available
4. Generate your first sample using the motivated wholesale script template
5. If API/RunPod is unavailable, create a test script that can be run when worker is healthy
6. Save results to $AGENT_DIR/experiments/
7. If you produce a good sample, copy to ~/agentrvm/public/demo-voicemail.mp3
8. Update $AGENT_DIR/AGENT-BRAIN.md with findings
9. Post status to $REPO_DIR/AGENT-MAILBOX.md

GO." --dangerously-skip-permissions 2>&1 | tee "$AGENT_DIR/run.log"
