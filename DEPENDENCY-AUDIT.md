# DEPENDENCY AUDIT — PyClaude-Harness

**Date:** 2026-04-02
**Target Environment:** RunPod H100 (`runpod/pytorch:2.4.0-py3.11-cuda12.4.1-devel-ubuntu`)
**Python:** 3.11+

---

## Files Scanned

| Directory | Files |
|-----------|-------|
| `src/coordinator/` | ack.py, \_\_init\_\_.py, dispatch.py, heartbeat.py, cmux.py, monitor.py, secrets.py |
| `src/` (core) | 35 modules (QueryEngine.py, Tool.py, main.py, commands.py, tools.py, etc.) |
| `agents/ad-engine/` | meta_ads.py, creative_generator.py, video_composer.py, canva_api.py, figma_api.py, evaluate.py, harness_bridge.py, autoresearch.py |
| `agents/site-optimizer/` | evaluate.py |
| `agents/vibevoice-producer/` | No .py files (launch.sh only) |
| `agents/lead-nurture/` | No .py files (launch.sh only) |
| `harness/` | orchestrator.py, evaluator.py, proposer.py |
| `tests/` | test_prepare.py, test_harness.py, test_heartbeat.py, test_cmux.py |
| Root | prepare.py |
| Shell scripts | run-me.sh, launch-template.sh, 4 agent launch.sh files, test_integration.sh |

---

## 1. requirements.txt — Python Third-Party Dependencies

```
# === REQUIRED (imported directly) ===
pytest>=7.0                    # tests/ — test runner
Pillow>=10.0                   # agents/ad-engine/creative_generator.py — PIL Image/ImageDraw/ImageFont (conditional import)

# === REQUIRED BY SHELL SCRIPTS (CLI tools invoked via subprocess) ===
# These are not pip packages but are invoked by subprocess:
#   - claude (Claude Code CLI) — invoked by launch scripts
#   - codex (OpenAI Codex CLI) — invoked by agents/lead-nurture/launch.sh

# === OPTIONAL / INFERRED ===
# None — the codebase is remarkably stdlib-only for Python deps
```

**Notes:**
- The entire `src/` core uses **only stdlib** (`json`, `pathlib`, `dataclasses`, `uuid`, `collections`, `argparse`, `platform`, `sys`, `functools`, `statistics`, `time`, `os`, `stat`, `textwrap`, `logging`, `urllib.request`, `urllib.parse`, `urllib.error`, `subprocess`, `tempfile`)
- `Pillow` is imported conditionally in `creative_generator.py` (line ~60, wrapped in try/except)
- `pytest` is the test runner

---

## 2. system-packages.txt — apt Packages Needed

```
# === REQUIRED ===
git                            # subprocess calls in heartbeat.py, orchestrator.py, harness_bridge.py
python3                        # all Python execution
python3-pip                    # package installation
curl                           # Slack webhook posts (CLAUDE.md protocol)
ffmpeg                         # agents/ad-engine/video_composer.py — video composition + ffprobe

# === FONTS (for Pillow image generation) ===
fonts-dejavu-core              # /usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf
fonts-liberation               # /usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf

# === REQUIRED BY SITE-OPTIMIZER ===
nodejs                         # site-optimizer uses pnpm/npx
npm                            # for installing pnpm

# === OPTIONAL (if using GCP secrets backend) ===
# google-cloud-cli             # gcloud CLI — used by src/coordinator/secrets.py GCP backend
```

**Notes:**
- RunPod pytorch image likely already has `git`, `python3`, `curl`
- `ffmpeg` is critical — `video_composer.py` calls `ffmpeg` and `ffprobe` via subprocess
- Font packages are needed for `creative_generator.py` image generation on Linux

---

## 3. npm-packages.txt — Node.js Packages Needed

```
# === REQUIRED BY site-optimizer/evaluate.py ===
pnpm                           # subprocess: pnpm run build (site-optimizer/evaluate.py:39)
typescript                     # subprocess: npx tsc --noEmit (site-optimizer/evaluate.py:58)

# Installation:
#   npm install -g pnpm
#   (typescript installed in agentrvm project via pnpm)
```

**Notes:**
- Site-optimizer runs `pnpm run build` and `npx tsc --noEmit` against `~/agentrvm`
- The `~/agentrvm` project must be cloned separately with its own `package.json`

---

## 4. network-requirements.txt — External URLs/APIs

```
# === Cloudflare Workers (Secrets Manager) ===
https://secrets-manager.rphants.workers.dev          # PROD — src/coordinator/secrets.py:50
https://secrets-manager-staging.rphants.workers.dev   # STAGING — src/coordinator/secrets.py:51

# === Meta (Facebook) Graph API ===
https://graph.facebook.com/v21.0                      # agents/ad-engine/meta_ads.py:47

# === Canva REST API ===
https://api.canva.com/rest/v1                         # agents/ad-engine/canva_api.py:40

# === Figma API ===
https://api.figma.com/v1                              # agents/ad-engine/figma_api.py:37

# === GitHub API (via gh CLI) ===
https://api.github.com                                # run-me.sh uses `gh repo list`
https://github.com/Rphants/PyClaude-Harness.git       # git remote

# === GCP Secret Manager (optional backend) ===
https://secretmanager.googleapis.com                   # src/coordinator/secrets.py (gcloud CLI)

# === Slack Webhook ===
# URL stored in $SLACK_WEBHOOK_URL env var             # CLAUDE.md: curl POST for agent status
```

---

## 5. env-vars.txt — All Environment Variables Referenced

```
# === SECRETS / API TOKENS ===
META_ACCESS_TOKEN              # agents/ad-engine/meta_ads.py:64, evaluate.py:96, launch.sh:43
CANVA_CLIENT_ID                # agents/ad-engine/canva_api.py, launch.sh
CANVA_CLIENT_SECRET            # agents/ad-engine/canva_api.py, launch.sh
CANVA_REFRESH_TOKEN            # agents/ad-engine/canva_api.py, launch.sh
CANVA_ACCESS_TOKEN             # agents/ad-engine/canva_api.py — optional manual override
FIGMA_ACCESS_TOKEN             # agents/ad-engine/figma_api.py:41, launch.sh:45
AGENT_SECRET_TOKEN             # src/coordinator/secrets.py:89 — worker auth token
SECRETS_BOOTSTRAP_TOKEN        # src/coordinator/secrets.py:91 — bootstrap auth

# === INFRASTRUCTURE ===
SECRETS_WORKER_URL             # src/coordinator/secrets.py:52 — override secrets-manager URL
SLACK_WEBHOOK_URL              # CLAUDE.md — Slack posting from agents
CLAUDE_CODE_PATH               # harness/proposer.py:202 — path to claude CLI (default: "claude")

# === AGENT LAUNCHER (launch-template.sh) ===
AGENT_CALLSIGN                 # launch-template.sh:23 — e.g. "claude-1", "ad-engine"
AGENT_DIR                      # launch-template.sh:24 — path to agent directory
RUNNER                         # launch-template.sh:25 — "claude -p" or "codex exec --full-auto"
TASK                           # launch-template.sh:26 — one-line task description
BRANCH                         # launch-template.sh:27 — git branch (optional)
CORRELATION_ID                 # launch-template.sh:28 — CMUX thread ID (optional)

# === DYNAMIC (secrets.py loads any env var by name) ===
# src/coordinator/secrets.py:309 — os.environ.get(name) where name is any secret name
# This means ANY secret defined in secrets-manifest.json may be looked up as an env var
```

---

## 6. Subprocess / Shell Commands Called from Python

| File | Command | Purpose |
|------|---------|---------|
| `src/coordinator/heartbeat.py:75` | `git branch --show-current` | Detect current branch |
| `src/coordinator/secrets.py:226` | `gcloud secrets versions access latest` | Read GCP secret |
| `src/coordinator/secrets.py:248` | `gcloud secrets create` | Create GCP secret |
| `src/coordinator/secrets.py:260` | `gcloud secrets versions add` | Write GCP secret |
| `src/coordinator/secrets.py:280` | `gcloud secrets list` | List GCP secrets |
| `harness/orchestrator.py:52` | `git rev-parse --short HEAD` | Get commit hash |
| `harness/orchestrator.py:64` | `git add optimize.json` | Stage changes |
| `harness/orchestrator.py:65` | `git commit -m <msg>` | Commit experiment |
| `harness/orchestrator.py:78` | `git stash --include-untracked` | Stash before rollback |
| `harness/orchestrator.py:82` | `git reset --hard HEAD~1` | Rollback experiment |
| `harness/orchestrator.py:87` | `git stash pop` | Restore stashed files |
| `harness/proposer.py:204` | `claude -p <prompt>` | Invoke Claude Code CLI |
| `agents/ad-engine/video_composer.py:67` | `ffmpeg -version` | Check ffmpeg installed |
| `agents/ad-engine/video_composer.py:80,181,202` | `ffmpeg ...` | Compose video |
| `agents/ad-engine/video_composer.py:85` | `ffprobe ...` | Probe video metadata |
| `agents/ad-engine/harness_bridge.py:71` | `git rev-parse --short HEAD` | Get commit hash |
| `agents/ad-engine/harness_bridge.py:83-110` | `git add/commit/stash/reset/pop` | Git operations |
| `agents/ad-engine/harness_bridge.py:184` | `python3 evaluate.py --json` | Run evaluation |
| `agents/site-optimizer/evaluate.py:39` | `pnpm run build` | Build agentrvm site |
| `agents/site-optimizer/evaluate.py:58` | `npx tsc --noEmit` | TypeScript check |
| `agents/site-optimizer/evaluate.py:214` | `date -Iseconds` | Get ISO timestamp |

---

## 7. File Paths Referenced

### Critical paths that must exist at deploy time:
| Path | Referenced By | Purpose |
|------|--------------|---------|
| `benchmarks/tasks/` | prepare.py, tests | 8 evaluation task JSON files |
| `optimize.json` | orchestrator.py, harness_bridge.py, tests | Harness config (optimization target) |
| `results.tsv` | orchestrator.py, harness_bridge.py | Experiment results log |
| `.cmux/events.jsonl` | src/coordinator/cmux.py | CMUX event bus |
| `~/.agent-secrets/` | src/coordinator/secrets.py | Local secret cache |
| `secrets-manifest.json` | src/coordinator/secrets.py | Secret definitions |
| `~/agentrvm/` | site-optimizer/evaluate.py, launch scripts | Target website project |
| `src/reference_data/` | commands.py, tools.py, parity_audit.py | JSON snapshots |
| `/usr/share/fonts/truetype/dejavu/` | creative_generator.py | Linux fonts |
| `/usr/share/fonts/truetype/liberation/` | creative_generator.py | Linux fonts |

---

## 8. RunPod Deploy Checklist

```bash
# 1. System packages
apt-get update && apt-get install -y \
    git curl ffmpeg \
    fonts-dejavu-core fonts-liberation \
    nodejs npm

# 2. Node.js tools
npm install -g pnpm

# 3. Python packages
pip install pytest Pillow

# 4. Clone repo
git clone https://github.com/Rphants/PyClaude-Harness.git
cd PyClaude-Harness

# 5. Clone target site (if running site-optimizer)
git clone <agentrvm-repo-url> ~/agentrvm
cd ~/agentrvm && pnpm install && cd -

# 6. Set environment variables
export META_ACCESS_TOKEN="..."
export CANVA_CLIENT_ID="..."
export CANVA_CLIENT_SECRET="..."
export CANVA_REFRESH_TOKEN="..."
export FIGMA_ACCESS_TOKEN="..."
export AGENT_SECRET_TOKEN="..."
export SECRETS_BOOTSTRAP_TOKEN="..."
export SLACK_WEBHOOK_URL="..."
export CLAUDE_CODE_PATH="claude"  # or path to claude binary

# 7. Create required directories
mkdir -p .cmux
mkdir -p agents/ad-engine/experiments
mkdir -p agents/site-optimizer/experiments

# 8. Verify
python3 -m pytest tests/ -v
python3 prepare.py --help
ffmpeg -version
```

---

## 9. Risk Summary

| Risk | Severity | Detail |
|------|----------|--------|
| Missing `ffmpeg` | **HIGH** | video_composer.py will crash on first call |
| Missing fonts | **MEDIUM** | creative_generator.py falls back but may fail on RunPod (no system fonts) |
| Missing `pnpm`/`node` | **HIGH** (site-optimizer only) | evaluate.py subprocess calls will fail |
| Missing `~/agentrvm` | **HIGH** (site-optimizer only) | Entire site-optimizer agent non-functional |
| Missing secrets | **MEDIUM** | Agents degrade gracefully (most check before calling APIs) |
| Missing `claude` CLI | **HIGH** (proposer only) | harness/proposer.py can't generate AI proposals |
| Missing `gcloud` CLI | **LOW** | Only affects GCP secrets backend; Cloudflare Worker is primary |
| Missing `gh` CLI | **LOW** | Only used in run-me.sh (not core functionality) |
