# H100 Deployment Plan — ClaudeCodePY + Meta Harness

**Date**: 2026-04-02
**Target**: RunPod H100 SXM (80GB VRAM, 251GB RAM, PyTorch 2.4, CUDA 12.4)
**Cost**: $2.69/hr ($64.56/day)
**Author**: CLAUDE-1 (comprehensive audit + plan)

---

## A. ARCHITECTURE UNDERSTANDING

### A1. What Is ClaudeCodePY?

ClaudeCodePY is a Python rewrite of Claude Code (forked after source maps were released) with three layers:

| Layer | Location | Purpose |
|-------|----------|---------|
| **claw-code** | `src/` (69 modules) | Python port of Claude Code internals — main.py, runtime.py, query_engine.py, tools.py, commands.py, session_store.py, cost_tracker.py, etc. Most modules are placeholder stubs importing from `reference_data/` JSON snapshots. Only `src/coordinator/` is fully implemented. |
| **Meta Harness** | `harness/` (3 modules) | Self-improvement loop: `proposer.py` generates hypotheses, `evaluator.py` runs diagnostics, `orchestrator.py` runs the autonomous experiment loop. Modifies `optimize.json` (the only mutable config). |
| **Agent Fleet** | `agents/` (4 agents) | Domain-specific agents: ad-engine, site-optimizer, vibevoice-producer, lead-nurture. Each has its own autoresearch loop, evaluation system, and AGENT-BRAIN.md. |

### A2. Module Map

```
Root (Harness Core)
├── prepare.py           — READ-ONLY ground truth evaluator (349 lines)
│                          Loads benchmarks, simulates task execution, computes composite_score
│                          Formula: 50% completion + 25% token efficiency + 25% tool accuracy (F1)
├── optimize.json        — THE optimization target (100 lines)
│                          model, temperature, token_budget, max_turns, system_prompt,
│                          tool_definitions (7 tools), context_strategy, routing_rules
├── program.md           — Autonomous loop instructions for Claude
├── results.tsv          — Experiment log (commit, score, status=keep/discard/crash)
│
harness/
├── proposer.py          — Analyzes failures → generates Proposal objects (224 lines)
│                          Rule-based or Claude-driven. Avoids re-proposing failed experiments.
├── evaluator.py         — Wraps prepare.py with richer diagnostics (177 lines)
│                          Returns DetailedEvaluation with per-task results + improvement hints
├── orchestrator.py      — Main loop engine (308 lines)
│                          propose → apply_proposal() → git commit → evaluate → keep/rollback
│
src/coordinator/
├── cmux.py              — JSONL event bus (Envelope, AgentSnapshot, JsonlMux)
│                          publish(), history(), inbox(), snapshots(), pending_handoffs()
├── dispatch.py          — Agent launcher (health check → CMUX publish → shell command)
├── monitor.py           — Health states: healthy/warm/stale/blocked/dead/dark
├── heartbeat.py         — Agent liveness (emit every 300s, statuses: working/waiting/blocked/done/idle)
├── ack.py               — Task acknowledgment (2-minute deadline)
├── secrets.py           — 4-backend secret retrieval: env → Worker → local → GCP
│
agents/ad-engine/
├── autoresearch.py      — Generic autoresearch loop (326 lines) — propose/apply/evaluate/decide
├── harness_bridge.py    — Bridges autoresearch to harness (413 lines) — P0s fixed
├── evaluate.py          — Ad creative scoring (302 lines) — offline + live Meta API modes
├── creative_generator.py — Pillow-based image generation (606 lines)
├── video_composer.py    — FFmpeg 15s video ads (328 lines)
├── meta_ads.py          — Meta Graph API v21.0 integration (367 lines)
├── optimize.json        — Ad-engine specific config (63 lines)
├── config.json          — Meta account IDs, budgets, audiences
├── canva_api.py         — Canva API wrapper (scaffolded, untested)
├── figma_api.py         — Figma API wrapper (scaffolded, untested)
│
agents/site-optimizer/
├── evaluate.py          — Build health + type safety + component coverage (233 lines)
├── config.json          — PostHog config, baseline metrics (all null)
├── program.md           — CRO optimization instructions
│
agents/vibevoice-producer/
├── AGENT-BRAIN.md       — Voice clone ID, quality insights, RunPod cost data
│
agents/lead-nurture/
├── AGENT-BRAIN.md       — Slack webhook intake, founder-led demo strategy
│
benchmarks/tasks/        — 8 evaluation tasks (JSON)
│   01_file_search, 02_code_search, 03_file_edit, 04_multi_file_refactor,
│   05_new_file_create, 06_test_run, 07_debug_error, 08_context_understanding
│
tests/                   — 56 passing tests (pytest, 0.14s)
│   test_prepare.py      — Evaluator correctness (EvalMetrics, composite_score, load_tasks)
│   test_harness.py      — Proposal generation, experiment history, failure analysis
│   test_heartbeat.py    — CMUX heartbeat, ACK, agent_health, is_dispatchable
│   test_cmux.py         — CMUX publish, history, inbox, snapshots, pending_handoffs
```

### A3. Meta Harness Data Flow

```
                    ┌─────────────────────────────────────────────┐
                    │           AUTONOMOUS LOOP                    │
                    │  (harness/orchestrator.py --max-experiments) │
                    └─────────────┬───────────────────────────────┘
                                  │
    ┌─────────────────────────────▼─────────────────────────────────┐
    │  1. BASELINE: evaluate_composite(optimize.json) → score       │
    │  2. CONTEXT: load history + failures + current config         │
    │  3. PROPOSE: generate_proposals(context) → sorted Proposals   │
    │  4. APPLY: apply_proposal() → mutate optimize.json            │
    │  5. COMMIT: git commit "experiment: {description}"            │
    │  6. EVALUATE: evaluate_composite(optimize.json) → new_score   │
    │  7. DECIDE:                                                   │
    │     • new_score > baseline → KEEP (advance baseline)          │
    │     • new_score ≤ baseline → DISCARD (git rollback)           │
    │  8. LOG: append to results.tsv                                │
    │  9. REPEAT from step 2                                        │
    └───────────────────────────────────────────────────────────────┘

    optimize.json ←→ proposer.py ←→ evaluator.py ←→ prepare.py ←→ benchmarks/tasks/
         ↕                                                              ↕
    results.tsv                                              8 JSON task definitions
```

### A4. Autoresearch + Harness Integration (Ad-Engine Example)

```
agents/ad-engine/autoresearch.py        agents/ad-engine/harness_bridge.py
┌──────────────────────────┐           ┌────────────────────────────────┐
│ AutonomousLoop.run()     │           │ HarnessBridge                  │
│  1. propose()        ────┼──────────►│  .propose() → read results.tsv │
│  2. apply()          ────┼──────────►│  .apply() → mutate config      │
│  3. evaluate()       ────┼──────────►│  .evaluate() → run evaluator   │
│  4. decide()         ────┼──────────►│  .decide() → keep or rollback  │
│  5. log()            ────┼──────────►│  .log() → append results.tsv   │
│  6. REPEAT               │           │  .rollback() → git rollback    │
└──────────────────────────┘           └────────────────────────────────┘
                                                      │
                                        agents/ad-engine/evaluate.py
                                        ┌──────────────────────────────┐
                                        │ Offline: creative_quality()  │
                                        │   • headline scoring         │
                                        │   • image quality heuristics │
                                        │ Live: meta_performance()     │
                                        │   • CTR, CPL, ROAS from API  │
                                        │ Composite: 40% creative +    │
                                        │            60% performance   │
                                        └──────────────────────────────┘
```

### A5. ML/RL Capabilities

**Exists today (functional)**:
- **Simulated evaluation loop**: prepare.py uses string-length heuristics and deterministic scoring. Works but doesn't use real Claude API calls.
- **Rule-based proposer**: Analyzes failure patterns (low completion, high tokens, poor accuracy) → generates targeted proposals. No ML.
- **Experiment tracking**: results.tsv with keep/discard decisions. Basic hill-climbing (accept if better).

**Scaffolded (code exists, not functional)**:
- **Claude-driven proposer**: `propose_with_claude()` shells out to `claude -p` CLI. Would work if Claude CLI is available.
- **Live Meta API evaluation**: ad-engine/evaluate.py can pull real CTR/CPL/ROAS from Meta Graph API. Needs META_ACCESS_TOKEN.
- **Agent performance monitoring (PQ system)**: Profitability Quotient designed in DIGITAL-EMPLOYEE-ARCHITECTURE.md. Never implemented.

**Does NOT exist**:
- No neural network training (no PyTorch/CUDA usage)
- No RL algorithm (no policy gradient, no reward model)
- No gradient-based optimization
- No model fine-tuning
- No GPU-accelerated computation anywhere in the codebase

**CRITICAL FINDING**: The H100's GPU will NOT be utilized by the current codebase. The autoresearch loop is entirely CPU-bound (Python string manipulation, JSON parsing, subprocess calls to Claude CLI). The GPU would only matter if:
1. You add local model inference (e.g., running a local LLM for evaluation)
2. You add RL training loops
3. You use PyTorch for embeddings/similarity search
4. You run VibeVoice TTS locally instead of via API

### A6. Dependencies

**Python** (from pyproject.toml):
```
requires-python = ">=3.11"
# No explicit pip dependencies — stdlib only
# Implicit: Pillow (creative_generator.py), requests (meta_ads.py, secrets.py)
```

**System packages** (implicit from code):
```
git                 — experiment tracking, rollback
ffmpeg              — video_composer.py (15s video ads)
curl                — secrets.py Worker calls, Slack webhooks
python3.11+         — main runtime
```

**NOT required** (despite H100 having them):
```
PyTorch 2.4         — NOT USED by current codebase
CUDA 12.4           — NOT USED by current codebase
```

**CLI tools needed**:
```
claude              — Claude Code CLI (for Claude-driven proposer + agent execution)
codex               — Codex CLI (for adversarial review, optional)
```

**npm packages**: None required for core harness. Claude Code CLI install may need npm/node.

---

## B. CURRENT STATE AUDIT

### B1. What Works TODAY (Verified)

| Component | Status | Evidence |
|-----------|--------|----------|
| `prepare.py` (evaluator) | ✅ WORKING | Imports clean, 56 tests pass |
| `optimize.json` (config) | ✅ WORKING | Valid JSON, all sections populated |
| `harness/proposer.py` | ✅ WORKING | Tests pass, rule-based proposals generate correctly |
| `harness/evaluator.py` | ⚠️ PARTIAL | Works but tool_accuracy disagrees with prepare.py |
| `harness/orchestrator.py` | ⚠️ PARTIAL | Experiment 1 works, experiment 2 crashes (KeyError: 'score') |
| `src/coordinator/cmux.py` | ✅ WORKING | Tests pass, JSONL read/write verified |
| `src/coordinator/heartbeat.py` | ✅ WORKING | Tests pass |
| `src/coordinator/ack.py` | ✅ WORKING | Tests pass |
| `src/coordinator/monitor.py` | ✅ WORKING | Tests pass |
| `src/coordinator/dispatch.py` | ⚠️ SECURITY | Shell injection risk (line 168) |
| `src/coordinator/secrets.py` | ⚠️ UNTESTED | No tests, 4-backend cascade untested live |
| `agents/ad-engine/autoresearch.py` | ⚠️ NEVER RUN | Code exists, P0s fixed, never executed end-to-end |
| `agents/ad-engine/harness_bridge.py` | ⚠️ FIXED BUT UNTESTED | P0 bugs fixed on fix/codex-p0-review, not integration tested |
| `agents/ad-engine/evaluate.py` | ⚠️ OFFLINE ONLY | Offline scoring works, live Meta scoring needs token |
| `agents/ad-engine/creative_generator.py` | ✅ WORKING | Generated 3 preview PNGs |
| `agents/ad-engine/video_composer.py` | ⚠️ NEEDS FFMPEG | Tested with ffmpeg, needs audio files |
| `agents/ad-engine/meta_ads.py` | ⚠️ SCAFFOLDED | Code complete, needs META_ACCESS_TOKEN |
| `agents/site-optimizer/` | ❌ NOT OPERATIONAL | All baselines null, PostHog not configured, target repo missing |
| `agents/vibevoice-producer/` | ❌ NOT OPERATIONAL | Knowledge only, no execution code |
| `agents/lead-nurture/` | ❌ NOT OPERATIONAL | Knowledge only, no execution code |
| Benchmark tasks | ✅ WORKING | 8 JSON tasks in benchmarks/tasks/ |
| Test suite | ✅ PASSING | 56/56 pass in 0.14s |
| Experiment history | ⚠️ DUPLICATE | results.tsv has duplicate baseline row |

### B2. Critical Bugs

**From HARNESS-AUTORESEARCH-REPORT.md**:

| ID | Severity | Bug | Status |
|----|----------|-----|--------|
| H1 | **CRITICAL** | Shell injection in dispatch.py line 168 — task string interpolated into shell command | OPEN |
| P0-2 | HIGH | evaluator.py tool_accuracy (1-unnecessary/total) disagrees with prepare.py F1 score | OPEN |
| T2-2 | HIGH | KeyError: 'score' in orchestrator experiment 2 — error path missing score key | OPEN |
| — | MEDIUM | CMUX append-only with no compaction — O(n) degradation | OPEN |
| — | MEDIUM | ElevenLabs API key needs rotation (old key in git history) | OPEN |
| — | MEDIUM | GitHub PAT embedded in git URL instead of secrets | OPEN |
| — | LOW | Duplicate baseline row in results.tsv | OPEN |
| — | LOW | Stale optimize.py references in docs | OPEN |

**From P0-FIXES.md (FIXED on fix/codex-p0-review)**:

| ID | Bug | Fix |
|----|-----|-----|
| P0-1 | orchestrator proposals didn't modify optimize.json | apply_proposal() implemented |
| P0-4 | git reset --hard destroys results.tsv | stash/restore in git_rollback() |
| P1-1 | "already tried" filter case-sensitive | normalized to lowercase |
| P1-2 | evaluator double-evaluates tasks | _metrics_from_results() |

### B3. Gap Analysis: Code vs. Functional

| Capability | Code Exists | Actually Works | Gap |
|------------|-------------|----------------|-----|
| Core harness loop | ✅ | ⚠️ (crashes exp 2) | Fix KeyError: 'score' |
| Simulated evaluation | ✅ | ✅ | None (but evaluates fake scenarios) |
| Real Claude evaluation | ⚠️ (propose_with_claude) | ❌ | Needs Claude CLI on pod |
| CMUX coordination | ✅ | ✅ (tested) | CMUX compaction missing |
| Agent dispatch | ✅ | ⚠️ (shell injection) | Fix shlex.quote |
| Secrets management | ✅ | ❌ (never tested live) | Need Worker URL + tokens |
| Ad creative generation | ✅ | ✅ (3 PNGs generated) | None |
| Video composition | ✅ | ⚠️ (needs audio) | Missing VibeVoice .mp3s |
| Meta ad deployment | ✅ | ❌ (no token) | META_ACCESS_TOKEN needed |
| Site optimization | ✅ | ❌ (all baselines null) | PostHog + baseline data |
| Agent self-improvement | ✅ (scaffolded) | ❌ | No feedback loop implemented |
| PQ scorecard | Designed only | ❌ | Not implemented |
| Cross-agent learning | Designed only | ❌ | Knowledge siloed in AGENT-BRAIN.md |

### B4. Security Issues for Deployment

1. **CRITICAL**: Shell injection in `dispatch.py:168` — `f'--claim "{task[:80]}"'`. Must add `shlex.quote()`.
2. **HIGH**: ElevenLabs API key in git history — rotate before deployment.
3. **HIGH**: GitHub PAT in git remote URL — move to secrets.
4. **MEDIUM**: secrets.py uses `subprocess` for `curl` calls to Worker — should use `urllib` to avoid shell.
5. **MEDIUM**: No input validation on CMUX events — malformed JSON could crash monitor.
6. **LOW**: `.agent-secrets/` directory permissions (chmod 600) not enforced programmatically.

---

## C. H100 DEPLOYMENT PLAN

### C1. Why an H100?

**Honest assessment**: The current codebase does NOT use GPU. The H100 is useful for:
- Future: local LLM inference for evaluation (replacing simulated eval)
- Future: RL training loops for agent optimization
- Future: local VibeVoice TTS synthesis (vs API calls)
- Present: 251GB RAM is useful for running multiple Claude CLI instances concurrently
- Present: RunPod provides a stable, always-on Linux environment

**Recommendation**: If the goal is just running the autoresearch loop, a CPU-only pod ($0.30-0.50/hr) would suffice. Use the H100 only if planning to add local model inference within this sprint.

### C2. Pre-Deployment Checklist (Do on Mac BEFORE starting pod)

```bash
# 1. Fix critical bugs on fix/codex-p0-review
# Already fixed: P0-1, P0-4, P1-1, P1-2
# Still need:
#   - Fix shell injection in dispatch.py (add shlex.quote)
#   - Fix KeyError: 'score' in orchestrator.py
#   - Fix evaluator.py tool_accuracy formula

# 2. Merge fix/codex-p0-review to main (after cross-model review)
git checkout main
git merge fix/codex-p0-review
git push origin main

# 3. Rotate ElevenLabs key (Ronald TODO)
# 4. Remove GitHub PAT from git remote URL
# 5. Verify Cloudflare Worker is reachable
curl -s https://agentrvm-secrets.<your-domain>.workers.dev/health

# 6. Prepare secrets for pod deployment
# Collect all secrets from secrets-manifest.json:
#   - META_ACCESS_TOKEN, META_APP_SECRET
#   - CANVA_CLIENT_ID, CANVA_CLIENT_SECRET, CANVA_REFRESH_TOKEN (optional)
#   - FIGMA_ACCESS_TOKEN (optional)
#   - ELEVENLABS_API_KEY (rotated)
#   - SLACK_WEBHOOK_URL
#   - GITHUB_PAT
#   - FIREBASE_TOKEN
#   - ANTHROPIC_API_KEY (for Claude CLI)
```

### C3. Pod Setup (Step by Step)

#### Step 1: Start Pod
- Template: PyTorch 2.4 + CUDA 12.4
- GPU: 1x H100 SXM 80GB
- Disk: 50GB /workspace volume (persistent across restarts)
- Region: Any US region (lowest latency to Anthropic API + Meta API)

#### Step 2: System Setup
```bash
# SSH into pod
ssh root@<pod-ip> -p <port>  # or use RunPod web terminal

# Update system
apt-get update && apt-get install -y \
  git \
  ffmpeg \
  curl \
  jq \
  tmux \
  zsh

# Python 3.11 should already be available (RunPod PyTorch image)
python3 --version  # Verify >=3.11

# Install pip packages (not in pyproject.toml but used by agent code)
pip install Pillow requests

# Install Node.js (for Claude Code CLI)
curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
apt-get install -y nodejs

# Install Claude Code CLI
npm install -g @anthropic-ai/claude-code

# (Optional) Install Codex CLI
npm install -g @openai/codex
```

#### Step 3: Clone Repository
```bash
cd /workspace

# Clone using HTTPS + PAT (or SSH key)
git clone https://<GITHUB_PAT>@github.com/Rphants/PyClaude-Harness.git
cd PyClaude-Harness

# Verify
python3 -m pytest tests/ -q
# Expected: 56 passed
```

#### Step 4: Configure Secrets
```bash
# Option A: Environment variables (simplest for single pod)
cat > /workspace/.env << 'EOF'
export ANTHROPIC_API_KEY="sk-ant-..."
export META_ACCESS_TOKEN="EAA..."
export META_APP_SECRET="..."
export SLACK_WEBHOOK_URL="https://hooks.slack.com/services/..."
export GITHUB_PAT="ghp_..."
export ELEVENLABS_API_KEY="..."
export FIREBASE_TOKEN="..."
EOF
chmod 600 /workspace/.env
source /workspace/.env

# Option B: Use secrets.py local backend
mkdir -p ~/.agent-secrets && chmod 700 ~/.agent-secrets
python3 -m src.coordinator.secrets set ANTHROPIC_API_KEY "sk-ant-..." --backend local
python3 -m src.coordinator.secrets set META_ACCESS_TOKEN "EAA..." --backend local
# ... repeat for all secrets

# Option C: Connect to Cloudflare Worker (production)
python3 -m src.coordinator.secrets save-token "<agent-access-token>"
python3 -m src.coordinator.secrets save-token "<bootstrap-token>" --bootstrap
python3 -m src.coordinator.secrets check --agent ad-engine
# Should report all required secrets available
```

#### Step 5: Configure Claude Code Auth
```bash
# Option A: API key (recommended for pods — no browser needed)
export ANTHROPIC_API_KEY="sk-ant-api03-..."
claude --version  # Verify CLI works

# Option B: OAuth (requires browser — NOT recommended for headless pods)
# Would need SSH tunnel + browser forwarding

# Test Claude CLI
echo "What is 2+2?" | claude -p --model claude-sonnet-4-20250514
# Should return "4" or similar

# Set Claude as non-interactive for automation
export CLAUDE_CODE_NON_INTERACTIVE=1
```

#### Step 6: Initialize CMUX
```bash
cd /workspace/PyClaude-Harness
mkdir -p .cmux
python3 -c "
from src.coordinator.heartbeat import emit_heartbeat
emit_heartbeat('h100-pod', 'idle', branch='main', claim='pod initialized')
print('CMUX initialized')
"
```

### C4. Network Requirements

The pod needs outbound HTTPS (443) to:

| Endpoint | Purpose | Required? |
|----------|---------|-----------|
| `api.anthropic.com` | Claude API (for Claude CLI) | YES |
| `github.com` | Git push/pull | YES |
| `graph.facebook.com` | Meta Ads API (ad-engine) | For ad-engine only |
| `hooks.slack.com` | Slack status updates | Recommended |
| `agentrvm-secrets.*.workers.dev` | Cloudflare secrets Worker | If using Worker backend |
| `secretmanager.googleapis.com` | GCP Secret Manager | If using GCP backend |
| `api.elevenlabs.io` | ElevenLabs TTS | For vibevoice only |
| `api.canva.com` | Canva API | Optional |
| `api.figma.com` | Figma API | Optional |
| `api.runpod.ai` | RunPod API (if self-managing) | Optional |

RunPod H100 pods have unrestricted outbound by default. No firewall changes needed.

### C5. Volume Layout (/workspace — 50GB persistent)

```
/workspace/                              # Persistent across pod restarts
├── PyClaude-Harness/                    # ~50MB — the repo
│   ├── .cmux/events.jsonl               # CMUX event log (grows ~1KB/event)
│   ├── results.tsv                      # Experiment history
│   ├── run.log                          # Latest evaluation output
│   ├── agents/ad-engine/experiments/    # Experiment specs + generated assets
│   └── ...
├── .env                                 # Secrets (chmod 600)
├── logs/                                # Agent run logs (archive periodically)
│   ├── autoresearch-YYYY-MM-DD.log
│   └── ...
└── backups/                             # Pre-experiment snapshots
    └── optimize-YYYY-MM-DD-HHMM.json
```

**Storage estimate**: 50GB is MORE than enough. Repo is ~50MB. Each experiment adds ~1KB to results.tsv + ~1KB to CMUX. Generated images are ~50KB each. Even 10,000 experiments would use <1GB.

### C6. Environment Variables

```bash
# Required
ANTHROPIC_API_KEY=sk-ant-...          # Claude API access
GITHUB_PAT=ghp_...                    # Git push access

# Agent-specific (load per agent)
META_ACCESS_TOKEN=EAA...              # ad-engine
META_APP_SECRET=...                   # ad-engine
SLACK_WEBHOOK_URL=https://...         # all agents (status updates)
ELEVENLABS_API_KEY=...                # vibevoice-producer
FIREBASE_TOKEN=...                    # site-optimizer

# System
CLAUDE_CODE_NON_INTERACTIVE=1         # Headless Claude CLI
AGENT_CALLSIGN=h100-pod               # Default callsign for pod
CMUX_PATH=/workspace/PyClaude-Harness/.cmux/events.jsonl
```

---

## D. FIRST RUN PLAN

### D1. Sequence

**Phase 0: Smoke Test (5 min, $0.22)**
```bash
cd /workspace/PyClaude-Harness

# 1. Run test suite
python3 -m pytest tests/ -q
# Expected: 56 passed

# 2. Run single evaluation (no Claude API needed)
python3 -c "
from prepare import evaluate_composite
score = evaluate_composite('optimize.json')
print(f'Composite score: {score:.6f}')
"
# Expected: ~0.928130

# 3. Verify CMUX works
python3 -c "
from src.coordinator.cmux import JsonlMux
mux = JsonlMux()
mux.publish('test', 'test', 'test.ping', {'msg': 'hello from H100'})
print(mux.history())
"
```

**Phase 1: Harness Loop — Simulated (15-30 min, $0.67-1.35)**
```bash
# Run the core autoresearch loop with simulated evaluation
# This does NOT call Claude API — uses rule-based proposer + simulated evaluator
python3 -m harness.orchestrator --max-experiments 3

# Expected output:
#   Baseline score: 0.928130
#   Experiment 1: [proposal] → score X → keep/discard
#   Experiment 2: [proposal] → score Y → keep/discard  ← MAY CRASH (KeyError: 'score')
#   Experiment 3: [proposal] → score Z → keep/discard

# Check results
cat results.tsv
git log --oneline -10
```

**Phase 2: Harness Loop — Claude-Driven (30-60 min, $1.35-2.69 + API costs)**
```bash
# Use Claude CLI as the proposer (generates smarter hypotheses)
python3 -m harness.orchestrator --max-experiments 3 --use-claude

# This calls Claude API via CLI for each proposal
# API cost: ~$0.05-0.10 per proposal (Sonnet)
# Total API cost for 3 experiments: ~$0.15-0.30
```

**Phase 3: Ad-Engine Autoresearch (1-2 hrs, $2.69-5.38 + API costs)**
```bash
cd /workspace/PyClaude-Harness/agents/ad-engine

# Source secrets
source /workspace/.env

# Run ad-engine autoresearch loop (offline mode — no Meta API)
python3 autoresearch.py --max-cycles 3 --offline

# This uses harness_bridge.py → evaluate.py (offline scoring)
# No META_ACCESS_TOKEN needed for offline mode
```

### D2. Which Agent First and Why

**Start with the core harness loop** (`harness/orchestrator.py`), NOT an agent. Reasons:
1. It has the most test coverage (56 tests)
2. It doesn't need external API keys (simulated evaluation)
3. It validates the full propose → apply → evaluate → decide loop
4. If it works, you've proven the autoresearch pattern
5. Cost: $0 in API fees (simulated mode)

**Second**: Ad-engine in offline mode (creative quality scoring only)
**Third**: Ad-engine in live mode (requires META_ACCESS_TOKEN)
**Never on H100**: Site-optimizer (needs agentrvm.com repo + PostHog, not relevant to GPU)

### D3. Minimum Viable Test (Before Burning H100 Time)

**Run this on Mac first** (free):
```bash
cd /Users/ronaldbigger/Downloads/PyClaude-Harness

# 1. Fix remaining bugs
# Fix KeyError: 'score' in orchestrator.py
# Fix shell injection in dispatch.py

# 2. Run orchestrator locally
python3 -m harness.orchestrator --max-experiments 3

# 3. If it completes 3 experiments without crashing → ready for pod
# 4. If it crashes → fix bugs locally (free) before burning $2.69/hr
```

### D4. Expected Runtime & Cost

| Phase | Duration | Pod Cost | API Cost | Total |
|-------|----------|----------|----------|-------|
| Smoke test | 5 min | $0.22 | $0 | $0.22 |
| Simulated loop (3 exp) | 15 min | $0.67 | $0 | $0.67 |
| Claude-driven loop (3 exp) | 30 min | $1.35 | $0.30 | $1.65 |
| Ad-engine offline (3 cycles) | 1 hr | $2.69 | $0.15 | $2.84 |
| Ad-engine live (3 cycles) | 2 hrs | $5.38 | $0.30 + Meta spend | $5.68+ |
| **Total first day** | **~4 hrs** | **$10.76** | **$0.75** | **$11.51** |

### D5. Success Criteria

| Criterion | How to Verify |
|-----------|---------------|
| Tests pass on pod | `pytest tests/ -q` → 56 passed |
| Simulated eval runs | `evaluate_composite()` returns score 0.8-1.0 |
| Orchestrator completes 3 experiments | `results.tsv` has 4+ rows (baseline + 3 experiments) |
| At least 1 experiment kept | `grep "keep" results.tsv | wc -l` > 1 |
| No crashes | Exit code 0, no Python tracebacks in run.log |
| CMUX records experiments | `.cmux/events.jsonl` has experiment events |
| Git history clean | `git log --oneline` shows experiment commits |
| Score improved | Final composite_score > baseline (0.928130) |

---

## E. RISKS AND MITIGATIONS

### E1. Deployment Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| **KeyError: 'score' crashes loop** | HIGH | HIGH | Fix before deploying — add `result.get('score', 0.0)` fallback in orchestrator.py |
| **Claude CLI auth fails on pod** | MEDIUM | HIGH | Use API key auth (not OAuth). Test with `echo "test" \| claude -p` before starting loop |
| **Missing pip packages** | MEDIUM | MEDIUM | `pip install Pillow requests` — these aren't in pyproject.toml but are imported |
| **optimize.json gets corrupted** | LOW | HIGH | Back up before each experiment: `cp optimize.json backups/` |
| **CMUX grows unbounded** | LOW (short-term) | MEDIUM | For first run, not an issue. Add compaction for production use. |
| **Pod loses /workspace data** | LOW | HIGH | Git push after each successful experiment. RunPod persistent volumes survive restarts but not pod deletion. |
| **results.tsv duplicate rows** | LOW | LOW | Clean up duplicate baseline row before starting |

### E2. Claude Code Auth on Pod

**Most likely failure**: Claude CLI requires interactive OAuth login, which doesn't work on headless pods.

**Solution**: Use API key authentication:
```bash
export ANTHROPIC_API_KEY="sk-ant-api03-..."
claude --print-access-token 2>/dev/null  # Should not be needed with API key
echo "test" | claude -p  # Should work immediately
```

**If API key auth doesn't work with CLI**:
1. Fall back to direct API calls via `requests` (modify `propose_with_claude()` in proposer.py)
2. Or use the Anthropic Python SDK: `pip install anthropic`

**If OAuth is required**:
1. Set up SSH tunnel: `ssh -L 8080:localhost:8080 root@pod`
2. Run `claude login` and open `http://localhost:8080` in local browser
3. Complete OAuth flow, token saved to pod's `~/.claude/`

### E3. Secrets Manager Worker Unreachable

**Symptoms**: `secrets.py` hangs for ~100s (sequential fallback: env → Worker → local → GCP)

**Mitigation**: Use environment variables directly (Option A in C4). Skip the Worker entirely:
```bash
source /workspace/.env  # All secrets as env vars
# secrets.py checks env first (instant) and never hits Worker
```

**If you NEED the Worker**:
```bash
# Test Worker health
curl -s https://agentrvm-secrets.<domain>.workers.dev/health
# If 200 → Worker is up
# If timeout → use env vars or local backend
```

### E4. GPU Utilization

**Will the autoresearch loop use the H100?** NO.

The current codebase is 100% CPU-bound:
- `prepare.py` — Python string operations, JSON parsing
- `orchestrator.py` — subprocess calls, file I/O
- `proposer.py` — rule-based logic, no ML
- `evaluator.py` — wraps prepare.py
- `cmux.py` — JSONL file operations
- `autoresearch.py` — orchestration logic
- `creative_generator.py` — Pillow (CPU-based image generation)

**GPU utilization will be 0%** unless you add:

| Future Capability | GPU Usage | Effort |
|-------------------|-----------|--------|
| Local LLM for evaluation (e.g., Llama 3) | 80GB VRAM → full | 2-4 days |
| Embedding-based code search | 2-4GB VRAM | 1 day |
| Local VibeVoice TTS (vs API) | 4-8GB VRAM | 1-2 days |
| RL training for agent optimization | Variable | 1-2 weeks |
| Fine-tuning evaluation model | Full VRAM | 1 week |

**Recommendation**: For the first sprint, the H100 is expensive overkill. Consider:
- **CPU pod** ($0.30-0.50/hr) for autoresearch loop testing
- **H100 pod** only when adding local model inference
- **Savings**: ~$50-60/day by using CPU pod instead

### E5. Cost Risk

| Scenario | Duration | Pod Cost | API Cost | Total |
|----------|----------|----------|----------|-------|
| Quick test (2 hrs) | 2 hrs | $5.38 | $0.50 | $5.88 |
| Full day testing | 8 hrs | $21.52 | $2.00 | $23.52 |
| Left running overnight | 24 hrs | $64.56 | $5.00 | $69.56 |
| Left running weekend | 72 hrs | $193.68 | $15.00 | $208.68 |
| **Forgot to stop** (1 week) | 168 hrs | **$451.92** | $35.00 | **$486.92** |

**Budget guard rails**:
1. Set RunPod auto-stop: `runpodctl stop --after 4h` (or use RunPod UI)
2. Set Anthropic API spend limit in dashboard
3. Add `--max-experiments N` to orchestrator (never run without limit)
4. Add cost tracking: `echo "$(date): pod running" >> /workspace/cost-log.txt`

**Recommended budget for first test**: $25 (covers ~8 hrs of H100 time + API calls). Set RunPod auto-stop at 8 hours.

---

## F. RECOMMENDED EXECUTION ORDER

### Before Starting Pod (Free — Do on Mac)

```
□ 1. Fix KeyError: 'score' in harness/orchestrator.py
□ 2. Fix shell injection in src/coordinator/dispatch.py (shlex.quote)
□ 3. Fix evaluator.py tool_accuracy formula
□ 4. Clean duplicate baseline from results.tsv
□ 5. Run: python3 -m harness.orchestrator --max-experiments 3
□ 6. Verify: 3 experiments complete without crash
□ 7. Merge fix/codex-p0-review to main
□ 8. Push to GitHub
□ 9. Collect all API keys into a secure note
□ 10. Rotate ElevenLabs key
```

### On Pod — First Hour

```
□ 11. Start H100 pod (set auto-stop: 4 hours)
□ 12. System setup (apt + pip + node + claude CLI)
□ 13. Clone repo + verify tests pass (56/56)
□ 14. Configure secrets (env vars or local backend)
□ 15. Verify Claude CLI works: echo "test" | claude -p
□ 16. Run smoke test (Phase 0)
□ 17. Run simulated loop: python3 -m harness.orchestrator --max-experiments 5
□ 18. Verify results.tsv has 6 rows (baseline + 5 experiments)
□ 19. Git push results
```

### On Pod — Second Hour

```
□ 20. Run Claude-driven loop: --max-experiments 5 --use-claude
□ 21. Compare: Claude proposals vs rule-based (which scores higher?)
□ 22. Run ad-engine offline: cd agents/ad-engine && python3 autoresearch.py --max-cycles 3 --offline
□ 23. Review: experiments/ directory for new assets
□ 24. Git push all results
□ 25. Post to Slack: "[H100-POD] First autoresearch cycle complete"
```

### Decision Point (After 2 Hours)

Based on results, decide:
- **If simulated loop works but scores plateau** → Need real Claude evaluation (invest in replacing prepare.py simulator)
- **If Claude-driven proposals are better** → Default to `--use-claude` for all future runs
- **If ad-engine offline works** → Ready for live mode (needs META_ACCESS_TOKEN)
- **If GPU is idle at 0%** → Switch to CPU pod to save $50+/day
- **If everything works** → Run overnight with `--max-experiments 100` and auto-stop at 8 hrs

---

## G. WHAT'S NOT IN THIS PLAN (Acknowledged Gaps)

1. **No RL training loop** — No code exists for GPU-accelerated learning. The H100 GPU is currently unused.
2. **No real Claude evaluation** — prepare.py simulates via heuristics. Replacing this is the single highest-impact improvement but requires ~16 hours of work.
3. **No multi-agent coordination on pod** — Running multiple agents concurrently (CLAUDE-1, CLAUDE-2, CODEX-1, CODEX-2) on a single pod requires tmux/screen panes and careful CMUX coordination. Not attempted in first run.
4. **No auto-scaling** — Single pod, single loop. Scaling to multiple concurrent experiments requires work.
5. **No monitoring dashboard** — CMUX monitor.py exists but no web UI. Would need to add Flask/FastAPI endpoint for remote monitoring.
6. **No data persistence beyond git** — results.tsv and CMUX events are in git. If pod is deleted before push, data is lost.

---

## H. TL;DR — THE HONEST PICTURE

**What you have**: A well-designed multi-agent coordination system (CMUX, heartbeat, dispatch, secrets) with a Karpathy-style autoresearch loop that can modify its own configuration and track experiments. 56 tests pass. The architecture is sound.

**What you don't have**: A system that has ever run autonomously end-to-end. The evaluation is simulated (not real Claude). The GPU will sit at 0% utilization. Two critical bugs (KeyError + shell injection) need fixing before the loop will run past experiment 1.

**What to do**:
1. Fix 3 bugs on Mac (free, ~2 hours)
2. Run the loop locally to prove it works (free, ~30 min)
3. Start a **CPU pod** ($0.30-0.50/hr) — not H100 — for the first real test
4. Save the H100 for when you add local model inference or RL training
5. Budget: $25 for first test day, with auto-stop enabled

**The autoresearch loop itself is the product.** The H100 is infrastructure for a future version that doesn't exist yet.
