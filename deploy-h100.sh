#!/bin/bash
# =============================================================================
# H100 Deployment Script — ClaudeCodePY + Meta Harness + Ad-Engine
# Run this on the RunPod H100 pod after SSH'ing in
# =============================================================================
set -euo pipefail

echo "=========================================="
echo " H100 DEPLOYMENT: ClaudeCodePY + Ad-Engine"
echo "=========================================="

# --- 1. System packages ---
echo "[1/7] Installing system packages..."
apt-get update -qq
apt-get install -y -qq git nodejs npm ffmpeg fonts-dejavu-core fonts-liberation curl jq

# Upgrade npm and install pnpm
npm install -g npm@latest pnpm 2>/dev/null || true

# --- 2. Claude Code CLI ---
echo "[2/7] Installing Claude Code CLI..."
npm install -g @anthropic-ai/claude-code
CLAUDE_PATH=$(which claude)
echo "Claude Code installed at: $CLAUDE_PATH"
claude --version

# --- 3. Clone PyClaude-Harness ---
echo "[3/7] Cloning PyClaude-Harness..."
cd /workspace
if [ -d "PyClaude-Harness" ]; then
    echo "Repo exists, pulling latest..."
    cd PyClaude-Harness
    git pull origin fix/codex-p0-review || git pull origin main || true
else
    git clone https://github.com/Rphants/PyClaude-Harness.git || {
        echo "Private repo — set GH_PAT env var and retry:"
        echo "  GH_PAT=ghp_xxx git clone https://Rphants:\$GH_PAT@github.com/Rphants/PyClaude-Harness.git"
        exit 1
    }
    cd PyClaude-Harness
    git checkout fix/codex-p0-review 2>/dev/null || git checkout main
fi

# --- 4. Python deps ---
echo "[4/7] Installing Python dependencies..."
COMMON_PY_DEPS=(pytest Pillow requests certifi)
GPU_PY_DEPS=(diffusers==0.30.3 accelerate transformers==4.44.2 safetensors sentencepiece)

pip install "${COMMON_PY_DEPS[@]}" --break-system-packages 2>/dev/null || pip install "${COMMON_PY_DEPS[@]}"

if command -v nvidia-smi >/dev/null 2>&1; then
    echo "Detected NVIDIA runtime — installing local GPU creative deps..."
    pip install "${GPU_PY_DEPS[@]}" --break-system-packages 2>/dev/null || pip install "${GPU_PY_DEPS[@]}"
fi

# --- 5. Validate module loading ---
echo "[5/7] Validating module imports..."
python3 -c "
modules = [
    'src.coordinator.cmux',
    'src.coordinator.heartbeat',
    'src.coordinator.dispatch',
    'src.coordinator.secrets',
    'src.coordinator.monitor',
    'src.coordinator.ack',
    'harness.orchestrator',
    'harness.evaluator',
    'harness.proposer',
    'src.main',
]
failed = []
for m in modules:
    try:
        __import__(m)
        print(f'  OK  {m}')
    except Exception as e:
        print(f'  FAIL {m}: {e}')
        failed.append(m)
if failed:
    print(f'\nFAILED: {len(failed)} modules')
    exit(1)
print('\nAll modules loaded successfully!')
"

if command -v nvidia-smi >/dev/null 2>&1; then
    echo "Checking local GPU scene provider..."
    python3 agents/ad-engine/local_gpu_scene.py healthcheck
fi

# --- 6. Run tests ---
echo "[6/7] Running test suite..."
python3 -m pytest tests/ -v --tb=short 2>&1 | tail -30 || echo "Some tests failed (non-blocking)"

# --- 7. Auth check ---
echo "[7/7] Checking Claude Code authentication..."
if [ -n "${ANTHROPIC_API_KEY:-}" ]; then
    echo "ANTHROPIC_API_KEY is set — using API key auth"
    claude -p "Respond with only: AUTHENTICATED" --output-format json 2>&1 | head -5
else
    echo ""
    echo "=============================================="
    echo " ACTION REQUIRED: Set your Anthropic API key"
    echo "=============================================="
    echo ""
    echo "  export ANTHROPIC_API_KEY='sk-ant-api03-...'"
    echo ""
    echo "Then run the ad-engine:"
    echo "  cd /workspace/PyClaude-Harness"
    echo "  python3 -m harness.orchestrator --max-experiments 5 --use-claude"
    echo ""
fi

echo ""
echo "=========================================="
echo " DEPLOYMENT COMPLETE"
echo "=========================================="
echo ""
echo "Next steps:"
echo "  1. Set ANTHROPIC_API_KEY if not already set"
echo "  2. Run: cd /workspace/PyClaude-Harness"
echo "  3. Run: python3 -m harness.orchestrator --max-experiments 10 --use-claude"
echo "  4. For ad-engine: python3 agents/ad-engine/autoresearch.py"
echo ""
