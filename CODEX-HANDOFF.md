# Codex Handoff Brief — H100 Deployment + Ad-Engine

**Date**: 2026-04-02
**From**: Cowork (Opus 4.6)
**To**: Codex (GPT-5.4) on Mac or VM

---

## Current State

### H100 Pod (RUNNING — $2.70/hr clock is ticking)
- **Pod**: `rphants-autoresearch-migration` (i453wiax6h1kgq)
- **Web Terminal**: Running on RunPod console
- **Location**: `/workspace/PyClaude-Harness` on branch `fix/codex-p0-review`
- **Node.js**: v20.20.2, Claude Code CLI v2.1.90 at `/usr/bin/claude`
- **Python**: 3.11, pytest + Pillow installed
- **ANTHROPIC_API_KEY**: Set (but ephemeral — export again if session lost)
- **Data migration**: 98% complete from old pod

### What's Broken Right Now
The code on the H100 has **4 bugs** that are already fixed on Ronald's Mac (`~/Downloads/PyClaude-Harness/`) but NOT pushed to GitHub:

1. **KeyError: 'score'** — `harness/orchestrator.py` line 270. When experiment returns status "error" or "crash", there's no `score`/`delta` key. Fix: use `.get("score", 0.0)` and add separate handling for "error" and "crash" status.

2. **Shell injection** — `src/coordinator/dispatch.py` lines 151-178. User-supplied `task` string interpolated directly into shell commands. Fix: `import shlex` and wrap all user inputs in `shlex.quote()`.

3. **Evaluator formula mismatch** — `harness/evaluator.py` line 112. Uses simple precision for tool_accuracy, but `prepare.py` uses F1 (harmonic mean of precision+recall). Fix: match the F1 formula.

4. **Proposer parsing** — `harness/proposer.py` line 210. `json.loads(result.stdout)` gets Claude Code's envelope `{"type":"result","result":"..."}`, not the inner JSON. Fix: extract `envelope.get("result")`, strip ```json blocks, then parse.

### GitHub Push Blocked
The push to `fix/codex-p0-review` was rejected because `deploy-h100.sh` contained the GitHub PAT. The PAT has been removed from the file on the Mac. To push:

```bash
cd ~/Downloads/PyClaude-Harness
git add -A
git commit --amend --no-edit
git push origin fix/codex-p0-review --force
```

Then on H100:
```bash
cd /workspace/PyClaude-Harness
git pull origin fix/codex-p0-review
```

---

## Task 1: Fix Bugs on H100 (5 min)

**Option A** (preferred): Push from Mac, pull on H100.

**Option B** (if push still blocked): Apply fixes directly on H100. The key fix is in `harness/orchestrator.py` around line 270. Replace:

```python
        elif verbose:
            print(f"DISCARDED: {result['score']:.6f} ({result['delta']:+.6f})", file=sys.stderr)
```

With:

```python
        elif result["status"] == "error":
            if verbose:
                print(f"ERROR: {result.get('message', 'unknown error')}", file=sys.stderr)
        elif result["status"] == "crash":
            if verbose:
                print(f"CRASHED: {result.get('error', 'unknown')} — rolled back", file=sys.stderr)
        elif verbose:
            print(f"DISCARDED: {result.get('score', 0.0):.6f} ({result.get('delta', 0.0):+.6f})", file=sys.stderr)
```

---

## Task 2: Run Autoresearch Smoke Test (2 min)

```bash
cd /workspace/PyClaude-Harness
export ANTHROPIC_API_KEY="..."
rm -f results.tsv
python3 -m harness.orchestrator --max-experiments 1 --use-claude
```

Expected output: Baseline ~0.913750, 1 experiment proposed by Claude, evaluated, kept or discarded, no crashes.

---

## Task 3: Build Facebook Ads Agent on H100 (THE GOAL)

The ad-engine agent is at `agents/ad-engine/`. Key files:
- `meta_ads.py` — Full Meta Graph API (campaigns, adsets, ads, insights)
- `autoresearch.py` — Autonomous propose→apply→evaluate→decide loop
- `evaluate.py` — Supports `--live` (real Meta API), `--mock`, `--json`
- `harness_bridge.py` — Bridges autoresearch to PyClaude harness
- `optimize.json` — Config with creative, copy, audience, budget params
- `launch.sh` — Launch script with CMUX heartbeats

**What's needed to go live:**
1. `META_ACCESS_TOKEN` — Create a System User token in Meta Business Manager (non-expiring)
2. Ad Account ID: `act_125821642`
3. Facebook Page ID: `1087752787745473`
4. Meta Pixel: `1606520033988956`

**To run the ad-engine autoresearch loop:**
```bash
cd /workspace/PyClaude-Harness
export META_ACCESS_TOKEN="<token>"
python3 agents/ad-engine/autoresearch.py
```

Or via the harness:
```bash
python3 -m src.coordinator.dispatch \
  --agent ad-engine \
  --task "Create and optimize Facebook ad campaigns for agentrvm.com targeting real estate wholesalers" \
  --runner "claude -p" \
  --force
```

---

## Key Architecture Notes

- **ClaudeCodePY is a FORK** of Claude Code (post source maps). The `src/` directory is the full Python port (~72 files). The `harness/` directory is the Meta Harness addition.
- **The fork cannot self-improve on the closed model** — long-term, `proposer.py` should call the Anthropic API directly via `anthropic` Python SDK instead of shelling out to `claude` CLI.
- **Autoresearch pattern**: PROPOSE → APPLY → EVALUATE → DECIDE → LOG → repeat (Karpathy style)
- **The H100 GPU will sit at 0% utilization** — this codebase is CPU-bound. The H100 is overkill but gives us fast CPU + lots of RAM.

---

## Files Modified This Session (on Mac, not yet on H100)

| File | Change |
|------|--------|
| `harness/orchestrator.py` | KeyError fix, crash handling, duplicate baseline prevention |
| `harness/evaluator.py` | F1 formula matching prepare.py |
| `harness/proposer.py` | Parse Claude Code envelope correctly |
| `src/coordinator/dispatch.py` | shlex.quote() for all user inputs |
| `deploy-h100.sh` | Deployment script (PAT removed) |
| `AUTH-VALIDATION-REPORT.md` | Auth test results |
| `CODEX-HANDOFF.md` | This file |

---

## Stop the H100 When Done
The pod is $2.70/hr. When finished testing:
- RunPod Console → Pods → rphants-autoresearch-migration → Stop
- Or keep it running if doing extended autoresearch (budget: ~$167 available)
