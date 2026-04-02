# Ad Engine — P0 Bug Fixes

**Date**: 2026-04-02
**Agent**: ad-engine (Claude Opus 4.6)
**Branch**: fix/codex-p0-review

---

## P0-1: Stateless proposer loops forever

**File**: `harness_bridge.py`
**Problem**: `propose()` had no memory of what was already tried. After exhausting its 5 hardcoded heuristics (or when conditions no longer triggered), it would either re-propose the same change or return a no-op proposal indefinitely.
**Fix**:
- Added `_load_tried_descriptions()` — reads `experiments/results.tsv` and returns a set of already-tried change descriptions.
- `propose()` now filters out proposals whose `change_description` already appears in results.tsv.
- When all proposals are exhausted, the fallback now says `"No change — proposals exhausted"` (was `"No change (baseline)"`).
- `autoresearch.py` loop now detects the exhaustion sentinel and breaks early instead of spinning.

**Also fixed** (related): `apply_proposal()` now merges dict keys instead of replacing entire sections. If a Claude-based proposer sends a partial dict (e.g. `{"headline_font_size_px": 64}`), it merges into the existing section instead of destroying all other keys.

## P0-2: Duplicate `run_single_experiment()`

**File**: `harness_bridge.py` (removed), `autoresearch.py` (kept)
**Problem**: Both files defined `run_single_experiment()`. The `harness_bridge.py` version (line 329-374) always returned `"status": "keep"` — it never compared against a baseline, making keep/discard logic dead code. `autoresearch.py` imported from `harness_bridge` but defined and used its own correct version.
**Fix**: Removed the broken `run_single_experiment()` from `harness_bridge.py`. The canonical version in `autoresearch.py` (which takes `baseline_score` and does proper comparison) is the only one now.

## P0-3: Wrong color palette in optimize.json

**File**: `optimize.json`
**Problem**: Color palette was `["#1F2937", "#3B82F6", "#FFFFFF", "#F59E0B"]` (Tailwind gray/blue/white/amber). Since `optimize.json` is the autoresearch target, any experiment using it as source-of-truth would generate off-brand creatives.
**Fix**: Changed to brand colors: `["#0a0a0a", "#FF8800", "#FFFFFF", "#FFB84D"]` (dark, orange, white, light orange).

## P0-4: Broken test script

**File**: `test_integration.sh`
**Problem**: Line 20 called `python3 autoresearch.py --propose-only` — this flag doesn't exist. `autoresearch.py` only supports `--max-experiments`, `--dry-run`, `--verbose`.
**Fix**: Changed to `python3 autoresearch.py --max-experiments 1 --dry-run` which exercises the same propose path using existing flags.

## P0-5: Duplicate baseline rows in results.tsv

**File**: `experiments/results.tsv`
**Problem**: Two identical baseline rows (`3f0457e 0.500000 N/A keep baseline`). Pollutes experiment history and would cause `_load_tried_descriptions()` to work correctly but with redundant data.
**Fix**: Removed the duplicate row. One baseline entry remains.

---

## Verification

All 5 fixes are minimal and targeted:
- `harness_bridge.py`: stateful proposer via results.tsv, safe dict merging in apply, removed duplicate function
- `autoresearch.py`: early exit when proposals exhausted
- `optimize.json`: brand-correct color palette
- `test_integration.sh`: valid CLI flags
- `experiments/results.tsv`: deduplicated
