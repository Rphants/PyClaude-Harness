# SPRINT BOARD — Live Task Tracker

**All agents: check this board before starting work. Claim tasks by writing your callsign.**

Last updated: 2026-04-01 17:30 by COWORK

---

## CURRENT SPRINT: "VibeVoice on the Landing Page + Ship to Production"

**Revenue context**: ~$2,500/day existing income. AgentRVM launches to prove the wholesale model internally, then sell the service to wholesalers in non-competitive markets.

**Sprint goal**: Production deploy + VibeVoice audio on landing page + audio-focused ad creatives live.

**VibeVoice context**: Self-hosted TTS on RunPod A100s. 18/18 concurrent sessions. ~$0.0016/msg. 4x cheaper than Cartesia. Repo: `agentrvm-voice-lab` (branch: `codex/candidate-wave-1`). Voice-lab platform: `/Users/ronaldbigger/Documents/New project/voice-lab-platform`.

---

## TIER 1 — REVENUE (Do First)

| # | Task | Owner | Status | Blocker | Notes |
|---|------|-------|--------|---------|-------|
| T1-1 | Deploy AgentRVM to production | RONALD + CLAUDE-2 | ✅ DONE | — | Deployed 2026-04-01. agentrvm.com live. Hosting-only; functions/firestore TBD. |
| T1-2 | PostHog A/B test: VibeVoice audio player on landing page | CLAUDE-1 | IN PROGRESS | None | Branch: feat/landing-audio-ab-test. Play sample below hero CTA. Track audio_demo_played + conversions. |
| T1-3 | Audio ad creatives featuring VibeVoice samples | COWORK-RELIEF | ✅ DONE | — | Full agent built: 2,218 lines Python, 3 preview images, 3 experiment specs, autoresearch loop. agents/ad-engine/ |
| T1-4 | Launch Facebook ads with audio creatives ($5/ad set) | UNOWNED | TODO | Needs META_ACCESS_TOKEN + VibeVoice .mp3s | Agent ready. Run: bash agents/ad-engine/launch.sh. Ronald reviews PAUSED campaigns before activating. |
| T1-5 | Fix `[Agent]` and `[Days]` placeholder replacement | UNOWNED | TODO | None | PR #10 merged without fix. Voicemail speaks literal tokens. |
| T1-6 | End-to-end test voice demo on production | UNOWNED | TODO | Needs T1-1 + T1-5 | Manual test: sign up, pick voice, generate voicemail, verify quality. |
| T1-7 | Generate VibeVoice sample audio for landing page | UNOWNED | TODO | Needs voice-lab worker healthy | Use motivated script template + best voice settings. Save as .mp3 for web. |
| T1-8 | Set up RVM campaigns for internal wholesale use | RONALD | TODO | Needs T1-1 + T1-6 | Prove the model with our own money. Track callbacks, ROI. |

## TIER 2 — STABILITY (Protect Revenue)

| # | Task | Owner | Status | Blocker | Notes |
|---|------|-------|--------|---------|-------|
| T2-1 | Fix GitHub push blocker on fix/codex-p0-review | COWORK | DONE | ✅ Resolved | Pushed successfully 2026-04-01. |
| T2-2 | Fix KeyError: 'score' in orchestrator experiment 2 | UNOWNED | TODO | None | Error path missing score key. |
| T2-3 | Fix evaluator.py tool_accuracy formula | UNOWNED | TODO | None | Disagrees with prepare.py F1 score. |
| T2-4 | Rotate ElevenLabs API key | RONALD | TODO | None | Old key was in git history. |
| T2-5 | Set CLOUDFLARE_API_TOKEN in GitHub secrets | UNOWNED | TODO | Need Cloudflare dashboard | Required for CI/CD. |
| T2-6 | Merge fix/codex-p0-review to main | UNOWNED | TODO | Needs cross-model review | 4 P0 + 3 P1 fixes. 31 tests pass. |

## TIER 3 — INFRASTRUCTURE (Go Faster)

| # | Task | Owner | Status | Blocker | Notes |
|---|------|-------|--------|---------|-------|
| T3-1 | Clean up stale optimize.py references | UNOWNED | TODO | None | Docs still reference deleted file. |
| T3-2 | Restart D1 relay daemon on VM | UNOWNED | TODO | None | Offline. Blocks VM dispatch from Cowork. |
| T3-3 | Build Firebase deploy skill | UNOWNED | TODO | None | Autonomous deploys without Ronald. |
| T3-4 | Set up MONITOR pane with live mailbox | UNOWNED | TODO | None | `watch -n 5 cat AGENT-MAILBOX.md` on surface:3 |
| T3-5 | Integrate CMUX as canonical bus per WAR-RULES.md | UNOWNED | TODO | None | events.jsonl, Envelope format, cmux.py coordinator |

---

## COMPLETED

| # | Task | Completed By | Date | Notes |
|---|------|-------------|------|-------|
| ✅ | Create PyClaude-Harness repo | COWORK + CLAUDE-1 | 2026-04-01 | Full architecture |
| ✅ | Cross-model review pipeline | ALL | 2026-04-01 | 4 P0 + 3 P1 bugs found and fixed |
| ✅ | Set up cmux war room (5 panes) | COWORK | 2026-04-01 | Claude-1, Claude-2, Monitor, Codex-1, Codex-2 |
| ✅ | Create coordination system | COWORK | 2026-04-01 | WAR-RULES.md, SPRINT-BOARD.md, MISSION.md |
| ✅ | WAR-RULES.md v2 (CMUX canonical) | CODEX | 2026-04-01 | Proof levels, anti-drift rules, escalation |
| ✅ | Create SPRINT-1M.md | CODEX-1 | 2026-04-01 | 90-day $1M ARR plan |
| ✅ | Fix GitHub push blocker | COWORK | 2026-04-01 | Secret scanning resolved |
| ✅ | Merge PRs #13-15 to master | TEAM | 2026-03-21 | Attribution, creatives, Slack notifications |
| ✅ | Facebook page setup | COWORK + CODEX | 2026-03-17 | Bio, profile, cover, 5 seed posts |
| ✅ | VibeVoice benchmarking | RONALD + CODEX | 2026-03-31 | 18/18 sessions, $0.0016/msg, pooled server |

---

## HOW TO USE THIS BOARD

1. Find an UNOWNED task in the highest tier
2. Write your callsign in the Owner column
3. Change status to IN PROGRESS
4. Post STARTING to AGENT-MAILBOX.md + Slack #war-room
5. Do the work
6. Change status to DONE with proof level per WAR-RULES.md
7. Post DONE to mailbox + Slack
8. Move to COMPLETED section

Cowork monitors and reassigns blocked tasks.
