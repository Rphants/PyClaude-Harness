# Site Optimizer — Status Report

**Date**: 2026-04-02
**Author**: SITE-OPTIMIZER (status audit)
**Target**: https://agentrvm.com (Next.js / TypeScript / Tailwind / Firebase)

---

## Executive Summary

The site-optimizer agent has a solid **architectural foundation** — program loop, evaluation script, config state, accumulated knowledge, and a launcher. However, **zero experiments have run**. Three hard blockers prevent the autonomous CRO loop from operating: no PostHog integration, no VibeVoice audio sample, and no baseline metrics from production.

**Readiness: ~60% built, 0% operational.**

---

## What's Built

### 1. Agent Program (`program.md`) — COMPLETE
- Full autoresearch loop defined: propose → implement → build → evaluate → decide → repeat
- Clear scope: 7 optimization surfaces mapped to specific files
- 10 seed experiment ideas prioritized
- Branch convention (`optimize/site-<YYYYMMDD>-<NN>`)
- Guard rails: what the agent cannot do (pricing, Firebase config, backend, deploy)
- PostHog A/B testing protocol with code examples
- Output protocol: config.json, AGENT-BRAIN.md, experiments/, mailbox, Slack

### 2. Evaluation Script (`evaluate.py`) — COMPLETE
- 4 metric checks implemented:
  - **Build health**: runs `pnpm run build`, checks exit code
  - **Type safety**: runs `npx tsc --noEmit`, counts TS errors
  - **Component scan**: scans `src/` for 8 conversion-relevant components (hero, waitlist_form, audio_demo, social_proof, roi_calculator, trust_badges, competitor_comparison, video_testimonial)
  - **Audio demo**: checks component file, page wiring, and audio file existence
- Composite scoring with weighted formula (build 0.30, types 0.10, components 0.30, audio 0.30)
- Writes `last_evaluation.json` with full results
- Clean, well-structured code — no obvious bugs

### 3. Config State (`config.json`) — COMPLETE
- Tracks current page state (headline, CTA, component presence, colors)
- Baseline metrics placeholders (all `null` — not yet measured)
- PostHog config stub (project key `null`)
- Priority queue: 6 experiments ordered by expected impact
- VibeVoice integration stubs
- Experiment counters (all 0)

### 4. Agent Brain (`AGENT-BRAIN.md`) — COMPLETE (initial state)
- Product knowledge captured (AgentRVM, VibeVoice, pricing, target audience)
- Site technical details (framework, hosting, design system)
- Conversion psychology for wholesalers documented
- Current hypothesis stated: "Audio demo is the highest-impact change"
- Blockers list maintained
- Experiment log and learnings sections ready (empty)

### 5. Launcher (`launch.sh`) — COMPLETE
- Bash script to dispatch Claude Code with `--dangerously-skip-permissions`
- Reads program.md, config.json, AGENT-BRAIN.md, WAR-RULES.md in order
- Pipes output to `run.log`
- Changes to `~/agentrvm` before launching

---

## What's Missing (Blockers)

### BLOCKER 1: No PostHog Integration (Critical)
- `posthog.project_key` is `null` in config.json
- Without PostHog, no feature flags for A/B tests
- Without A/B tests, no statistical measurement of conversion changes
- **The agent can propose and implement changes but cannot measure real-world impact**
- **Action needed**: Set up PostHog project, get API key, add SDK to agentrvm

### BLOCKER 2: No VibeVoice Audio Sample (Critical)
- `vibevoice.sample_audio_path` is `null` in config.json
- AGENT-BRAIN identifies audio demo as "#1 conversion lever"
- Priority queue's top item is `audio-demo-below-hero`
- The `AudioDemo.tsx` component is referenced but may not exist in the agentrvm repo
- **Action needed**: Generate a sample .mp3 from VibeVoice and place in `~/agentrvm/public/`

### BLOCKER 3: No Baseline Metrics (Critical)
- All `baseline_metrics` are `null` — conversion rate, bounce rate, time on page, etc.
- Config note says: "Baseline not yet measured — site needs production deploy first"
- Without a baseline, the agent cannot determine if changes are improvements or regressions
- **Action needed**: Deploy current site to production, collect 1-2 weeks of data, record baseline

### BLOCKER 4: No `experiments/` Directory
- program.md specifies writing experiment records to `experiments/<id>.json`
- Directory does not exist yet
- Minor — agent can create it on first run

### BLOCKER 5: `~/agentrvm` Repo Not Local to This Machine
- evaluate.py and launch.sh both reference `~/agentrvm`
- Cannot verify if the agentrvm codebase exists or what state it's in from this repo
- launch.sh will `exit 1` if `~/agentrvm` is missing

---

## What Works Without Blockers (Can Run Today)

Even without PostHog and baseline data, the agent **could** do the following with modifications:

1. **Offline evaluation**: Run `evaluate.py` against `~/agentrvm` to get component scan + build health scores (if the agentrvm repo is present)
2. **Implement changes**: Create branches, modify copy/layout/components, verify builds pass
3. **Heuristic-based decisions**: Use composite score (build + type safety + component coverage) instead of real conversion data
4. **Accumulate learnings**: Log what was tried and what built successfully to AGENT-BRAIN.md

This would be a **dry-run mode** — useful for building out components but not for actual CRO.

---

## Evaluation Script Assessment

### Strengths
- Clean separation of concerns (4 independent checks)
- Composite scoring is reasonable for pre-production phase
- Audio demo check is thorough (component + wiring + file)
- Writes structured JSON results

### Weaknesses / Gaps
- **No Lighthouse integration** — `lighthouse_score` is mentioned in config and docstring but not implemented
- **No PostHog data fetching** — docstring mentions future conversion_rate, bounce_rate, audio_play_rate but no code for it
- **Component scan is naive** — checking if "social" appears in first 500 chars could false-positive on comments or imports
- **No mobile responsiveness check** — program.md lists "mobile vs desktop conversion split" as a secondary metric
- **No page load time measurement** — referenced in program.md but not implemented
- **No diff-based evaluation** — doesn't compare current run to previous run to determine improvement

---

## Architecture Gaps

| Gap | Impact | Effort |
|-----|--------|--------|
| PostHog data pipeline (fetch real metrics) | Cannot do real CRO without it | Medium — API calls + parsing |
| Lighthouse CI integration | No performance regression detection | Low — `npx lighthouse-ci` |
| Experiment history storage | No experiment records exist | Low — mkdir + JSON writes |
| Rollback mechanism | program.md says "git reset" but no safe rollback code | Low — git stash pattern |
| Cross-experiment comparison | No way to compare experiment N vs N-1 | Medium — needs results DB/TSV |
| Deploy trigger | Agent flags for COWORK but no handoff mechanism | Medium — needs mailbox polling |
| Sample size gating | PostHog min 100 visitors check not implemented | Low — API call |

---

## Recommended Action Plan

### Phase 1: Unblock (Before Agent Can Run)
1. **Generate VibeVoice sample .mp3** → place in `~/agentrvm/public/demo-voicemail.mp3`
2. **Set up PostHog** → create project, add SDK to agentrvm, put key in config.json
3. **Deploy current site** → Firebase deploy, collect baseline for 1 week
4. **Record baseline metrics** → fill in `baseline_metrics` in config.json

### Phase 2: Dry-Run Mode (Can Start Now)
1. Create `experiments/` directory
2. Run `evaluate.py` against current agentrvm to get component/build scores
3. Implement audio demo component (even without real .mp3, build the player UI)
4. Implement above-fold form experiment
5. Validate builds pass, accumulate composite scores

### Phase 3: Live CRO Loop (After Phase 1)
1. Add PostHog metric fetching to evaluate.py
2. Add Lighthouse CI to evaluate.py
3. Implement experiment comparison (current vs previous best)
4. Run the full autonomous loop via launch.sh
5. Let it cook

---

## File Inventory

| File | Status | Purpose |
|------|--------|---------|
| `program.md` | Complete | Agent instructions, loop definition |
| `AGENT-BRAIN.md` | Initialized | Knowledge base, empty experiment log |
| `config.json` | Initialized | State tracking, all metrics null |
| `evaluate.py` | Complete (offline) | 4-check evaluation, no live metrics |
| `launch.sh` | Complete | Claude Code dispatcher |
| `experiments/` | Missing | Experiment record storage |
| `last_evaluation.json` | Missing | Created by evaluate.py on first run |
| `run.log` | Missing | Created by launch.sh on first run |

---

## Bottom Line

The site-optimizer is well-designed on paper. The autoresearch loop, evaluation framework, and knowledge accumulation system are all sound. But it's **pre-operational**: zero experiments run, zero data collected, three hard blockers outstanding. The fastest path to value is Phase 2 (dry-run: build components, validate builds) while Phase 1 blockers are resolved in parallel.
