# Ad Creative Engine — Status Report

**Date**: 2026-04-02
**Reviewer**: ad-engine (Claude Opus 4.6)
**Branch**: fix/codex-p0-review

---

## Executive Summary

The ad-engine agent has a solid foundation: 7 Python modules, 3 experiment specs, 3 generated preview images, an autoresearch loop, and full Meta Graph API integration. However, **nothing has been deployed to Meta yet**, several tools have never been run against real APIs, and there are code-level bugs that will break the autoresearch loop on first real execution.

**Readiness**: ~60% for offline/local work, ~20% for live deployment.

---

## What's Built

### Core Pipeline (Working)

| File | LOC | Status | Notes |
|------|-----|--------|-------|
| `evaluate.py` | 302 | WORKING | Composite scorer. Offline + live modes. `--json` flag for harness. |
| `meta_ads.py` | 367 | UNTESTED LIVE | Full CRUD: campaigns, ad sets, ads, insights, evaluate. Uses `urllib` (no deps). |
| `creative_generator.py` | 606 | WORKING | 4 templates (stats-card, before-after, testimonial, single-image). Pillow-based. |
| `video_composer.py` | 328 | UNTESTED | FFmpeg-based 15s video ads with timed text overlays. Requires FFmpeg + audio files. |
| `harness_bridge.py` | 413 | PARTIAL | Proposer, applicator, evaluator, rollback. Has bugs (see below). |
| `autoresearch.py` | 326 | PARTIAL | Full loop skeleton. Imports harness_bridge. Has bugs (see below). |
| `launch.sh` | 160 | SCAFFOLDED | CMUX launcher with secrets loading, heartbeats, 4 modes. |

### Supporting Files

| File | Status | Notes |
|------|--------|-------|
| `canva_api.py` | SCAFFOLDED | Canva Connect API wrapper. Never tested. Now expects OAuth client credentials + refresh token. |
| `figma_api.py` | SCAFFOLDED | Figma REST API wrapper. Never tested. Requires `FIGMA_ACCESS_TOKEN`. |
| `config.json` | CORRECT | Meta account IDs, budget rules, 3 audience segments. |
| `optimize.json` | CORRECT | Autoresearch target config: creative, copy, audience, budget, audio params. |
| `AGENT-BRAIN.md` | SEEDED | Has initial heuristics but no real experiment data. |
| `test_integration.sh` | FRAGILE | Calls `--propose-only` flag that doesn't exist on autoresearch.py. |

### Experiments & Assets

| Asset | Status |
|-------|--------|
| `experiments/audio-first-001.json` | Complete spec. Curiosity angle. References `vibevoice-sample-001.mp3` (missing). |
| `experiments/audio-first-002.json` | Complete spec. ROI angle. References missing audio. |
| `experiments/audio-first-003.json` | Complete spec. FOMO angle. References missing audio. |
| `experiments/preview-stats-card.png` | Generated (45KB). |
| `experiments/preview-testimonial.png` | Generated (30KB). |
| `experiments/preview-fomo.png` | Generated (40KB). |
| `experiments/results.tsv` | Has header + 2 duplicate baseline rows. |
| `experiments/experiments/preview-001.png` | Nested duplicate directory (likely accidental). |

### Research

6 research documents in `research/` covering competitive landscape, creative swipe file, and knowledge base index. These are reference material, not code.

---

## Bugs & Issues

### P0 — Will Break Autoresearch Loop

**1. `harness_bridge.py:apply_proposal()` replaces entire config sections**
- Line 157: `config[section_key] = new_val` overwrites the **entire section** with `proposal.new_value`.
- The `propose()` function (line 238-239) correctly builds `new_value` as the full section dict with one field changed, so this works _for the built-in proposer_.
- But if `new_value` is a single scalar (e.g., from a Claude-based proposer), it would destroy the entire section. The function should merge keys, not replace the whole section.

**2. `harness_bridge.py:propose()` is deterministic and will loop forever**
- The proposer uses static `if` checks (lines 232-299) with no memory of what was already proposed.
- After the first experiment changes `number_of_variations` to 20, the next call to `propose()` will propose the _same change_ again (since it checks `< 20`, and now it's exactly 20, so it skips — but then proposes the next static item).
- After all 5 hardcoded proposals are exhausted (or their conditions are met), `propose()` returns a no-op fallback proposal forever. The loop won't terminate early because the no-op proposal will be applied, evaluated, and kept/discarded with no score change.

**3. `harness_bridge.py` has duplicate `run_single_experiment()`**
- Both `harness_bridge.py:329` and `autoresearch.py:136` define `run_single_experiment()`.
- `autoresearch.py` imports from `harness_bridge` but defines its own version and uses that one.
- The `harness_bridge` version (line 329-374) always returns `"status": "keep"` (line 369) — it never discards, making the keep/discard logic dead code.

**4. `results.tsv` has duplicate baseline entries**
- Two identical `baseline` rows with the same commit hash. Likely from running the evaluator twice. Not a crash bug, but pollutes experiment history.

**5. `test_integration.sh` references non-existent flag**
- Line 20: `python3 autoresearch.py --propose-only` — this flag doesn't exist. `autoresearch.py` only supports `--max-experiments`, `--dry-run`, `--verbose`.

### P1 — Will Break Live Deployment

**6. `meta_ads.py:create_adset()` sends interest targeting wrong**
- Line 161: `"interests": [{"name": interest}]` — Meta API requires `{"id": ..., "name": ...}` for interest targeting. Without the numeric `id` field, the API will reject the request or silently ignore targeting.
- Fix: Use the Targeting Search API to resolve interest names to IDs, or hardcode known IDs.

**7. `meta_ads.py:create_ad()` doesn't handle audio/video creatives**
- Lines 203-218: Only builds `link_data` with text fields. Audio and video creatives need `video_data` with `video_id` (uploaded video) or `source` URL.
- The 3 experiment specs all specify audio files, but `create_ad()` can't upload or reference them.

**8. `video_composer.py` hardcodes Linux font paths**
- Lines 235-236: Font path `/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf` doesn't exist on macOS.
- `creative_generator.py` handles this correctly (tries multiple paths including macOS), but `video_composer.py` will fail with FFmpeg drawtext errors on Mac.

**9. No META_ACCESS_TOKEN available**
- `config.json` has correct Meta account IDs, but no token is set in the environment.
- `launch.sh` tries to load from secrets-manager, which depends on `src.coordinator.secrets` — unclear if this module exists or has the token stored.

### P2 — Quality / Correctness

**10. `optimize.json` color palette doesn't match brand guidelines**
- Line 8: `["#1F2937", "#3B82F6", "#FFFFFF", "#F59E0B"]` (Tailwind colors: gray, blue, white, amber)
- Should be: `["#0a0a0a", "#FF8800", "#FFFFFF", "#FFB84D"]` (brand dark, orange, white, light orange)
- `creative_generator.py` correctly uses brand colors — but `optimize.json` is the autoresearch target, so any experiment using it as source-of-truth for colors will generate off-brand creatives.

**11. `evaluate.py` creative readiness requires `"audio-first"` angle but experiment specs use it as `"type": "audio"` + `"angle": "audio-first"`**
- Line 72: `required_angles = {"audio-first", "roi", "pain-point", "fomo", "curiosity", "social-proof"}`
- Experiment specs use `"angle": "audio-first"` which matches, but the other 2 experiments also use `"angle": "roi"` and `"angle": "fomo"`.
- The 3 current experiments cover only 3/6 angles → `coverage_pct = 50%`, `launch_ready = False` (needs `audio_ads >= 1` which is 0 since none have actual audio files).

**12. `_escape_text()` in `video_composer.py` escapes backslash after single quote**
- Line 295: `text.replace("\\", "\\\\")` runs after `text.replace("'", "\\'")`, which means the backslash inserted by the single-quote escape gets double-escaped. Should escape backslashes first.

**13. `evaluate.py` efficiency metric is confusing**
- Line 139: `efficiency = total_leads / (total_spend / daily_start)` — this is "leads per budget-day-equivalent", not a standard advertising metric. Fine as internal signal but the name is misleading.

---

## What's Missing

### Critical for Launch

1. **VibeVoice audio samples (.mp3)** — All 3 experiment specs reference audio files that don't exist. The vibevoice-producer agent needs to deliver these.
2. **Video upload to Meta** — `meta_ads.py` can create text/link ads but cannot upload video or audio creative to Meta's asset library.
3. **Interest ID resolution** — Need Meta Targeting Search API integration to convert interest names → numeric IDs for ad set targeting.
4. **Long-lived Meta access token** — Current setup has no token. Need system user token or long-lived page token.

### Important for Autoresearch

5. **Stateful proposer** — Current proposer has no memory of what was already tried. Needs to read `results.tsv` to avoid re-proposing failed experiments.
6. **Claude-based proposer** — `program.md` mentions `--use-claude-proposer` flag but it's not implemented. The current proposer only has 5 hardcoded proposals.
7. **Plateau detection** — `program.md` mentions "stop if improvements < 0.001 for 5+ consecutive experiments" but this exit condition is not implemented in `autoresearch.py`.

### Nice to Have

8. **Landing page variant testing** — `program.md` mentions landing page optimization but no code exists for it.
9. **Lookalike audience creation** — `optimize.json` has `lookalike_source_type` and `lookalike_ratio` but no code creates LLAs.
10. **Creative fatigue detection** — No code tracks creative lifespan or triggers refresh.
11. **Canva/Figma integration** — Both API wrappers exist but are pure scaffolding. No templates configured, no file keys set.

---

## File Tree

```
agents/ad-engine/
  AGENT-BRAIN.md          — Seeded knowledge base (no real experiment data yet)
  BUILD-SUMMARY.md        — Build log from initial creation
  STATUS-REPORT.md        — This file
  config.json             — Meta account IDs + budget rules + audiences
  optimize.json           — Autoresearch tunable parameters
  program.md              — Agent instructions (comprehensive)
  launch.sh               — CMUX-wrapped launcher (4 modes)
  evaluate.py             — Ground truth scorer (offline + live)
  meta_ads.py             — Meta Graph API integration
  creative_generator.py   — Static image generator (Pillow)
  video_composer.py       — Video ad composer (FFmpeg)
  harness_bridge.py       — Autoresearch bridge (propose/apply/evaluate/rollback)
  autoresearch.py         — Autonomous experiment loop
  canva_api.py            — Canva Connect API (scaffold)
  figma_api.py            — Figma REST API (scaffold)
  test_integration.sh     — Integration test (broken — references non-existent flag)
  experiments/
    audio-first-001.json  — Curiosity angle spec
    audio-first-002.json  — ROI angle spec
    audio-first-003.json  — FOMO angle spec
    preview-stats-card.png
    preview-testimonial.png
    preview-fomo.png
    results.tsv           — Experiment log (2 duplicate baseline rows)
    experiments/          — Accidental nested directory
      preview-001.png
  research/               — 6 research/reference documents
```

---

## Recommendations (Priority Order)

1. **Fix `optimize.json` color palette** to match brand guidelines (5 min fix, prevents off-brand output)
2. **Fix `video_composer.py` font paths** for macOS compatibility
3. **Fix `_escape_text()` backslash ordering** in video_composer.py
4. **Add state to proposer** — read `results.tsv` and skip already-tried experiments
5. **Get VibeVoice audio samples** from vibevoice-producer agent
6. **Get/set META_ACCESS_TOKEN** for live API testing
7. **Add video upload capability** to `meta_ads.py`
8. **Add interest ID resolution** to `meta_ads.py`
9. **Fix `test_integration.sh`** — remove `--propose-only` reference
10. **Clean up `results.tsv`** — remove duplicate baseline row
11. **Delete nested `experiments/experiments/` directory**

---

## Verdict

The ad-engine has a well-designed architecture that follows the PyClaude-Harness autoresearch pattern correctly. The evaluate/propose/apply/rollback cycle is sound. The creative generation tools work locally. The Meta API integration is structurally complete.

**Blockers to first live campaign**: Missing audio samples, no Meta access token, video upload not supported, interest targeting IDs not resolved.

**Blockers to autoresearch loop**: Stateless proposer will exhaust 5 proposals then spin on no-ops. Duplicate `run_single_experiment()` creates confusion. These are fixable in ~1-2 hours.

**Bottom line**: Fix the P0 bugs, get the audio samples and Meta token, and this agent can start running real experiments.
