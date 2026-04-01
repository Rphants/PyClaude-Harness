# SPRINT BOARD — Live Task Tracker

**All agents: check this board before starting work. Claim tasks by writing your callsign.**

Last updated: 2026-04-01 by COWORK

---

## CURRENT SPRINT: "Prove the Model, Launch RVM"

**Revenue context**: ~$2,500/day existing income. AgentRVM launches to prove the wholesale model internally, then sell the service to wholesalers in non-competitive markets.

**Sprint goal**: AgentRVM production deploy + first RVM campaigns running + Facebook ads live.

---

## TIER 1 — REVENUE (Do First)

| # | Task | Owner | Status | Blocker | Notes |
|---|------|-------|--------|---------|-------|
| T1-1 | Deploy AgentRVM to production (`pnpm build && firebase deploy`) | UNOWNED | TODO | None — all PRs merged to master | 10-minute task. Biggest single blocker to revenue. |
| T1-2 | Launch Facebook ads ($30-50/day starting budget) | UNOWNED | TODO | Needs T1-1 done first | Strategy + creatives ready. 4 angles, 12 copy variations, 5 static images. |
| T1-3 | Fix `[Agent]` and `[Days]` placeholder replacement in voice demo | UNOWNED | TODO | None | PR #10 merged without fix. Voicemail may speak literal `[Agent]` tokens. |
| T1-4 | End-to-end test voice demo on production | UNOWNED | TODO | Needs T1-1 + T1-3 | Manual test: sign up, pick voice, generate voicemail, verify audio quality. |
| T1-5 | Set up RVM campaigns for internal wholesale use | RONALD | TODO | Needs T1-1 + T1-4 | Prove the model with our own money first. Track callbacks, ROI. |

## TIER 2 — STABILITY (Protect Revenue)

| # | Task | Owner | Status | Blocker | Notes |
|---|------|-------|--------|---------|-------|
| T2-1 | Fix GitHub push blocker (Slack webhook URL in branch files) | UNOWNED | TODO | Secret scanning rejects push | Strip webhook from CLAUDE.md + CODEX.md on `fix/codex-p0-review`, force push. |
| T2-2 | Fix KeyError: 'score' in orchestrator experiment 2 | UNOWNED | TODO | None | Error path has no `score` key. Codex found it. |
| T2-3 | Fix evaluator.py tool_accuracy formula (disagrees with prepare.py) | UNOWNED | TODO | None | evaluator uses old formula, prepare.py uses F1 score. Must unify. |
| T2-4 | Rotate ElevenLabs API key | RONALD | TODO | None | Old key `sk_dce270a...` was in git history. Exposed. |
| T2-5 | Set CLOUDFLARE_API_TOKEN in GitHub secrets | UNOWNED | TODO | Need token from Cloudflare dashboard | Required for CI/CD agentrvm-secrets. |
| T2-6 | Authenticate `gh` CLI on VM | UNOWNED | TODO | None | Currently using curl + GitHub API. `gh` would be faster. |

## TIER 3 — INFRASTRUCTURE (Go Faster)

| # | Task | Owner | Status | Blocker | Notes |
|---|------|-------|--------|---------|-------|
| T3-1 | Clean up stale optimize.py references in docs | UNOWNED | TODO | None | References in README, program.md, CLAUDE.md, CODEX.md, prepare.py, harness files. |
| T3-2 | Restart D1 relay daemon on VM | UNOWNED | TODO | None | Currently offline. Cowork can't dispatch to VM without it. |
| T3-3 | Build Firebase deploy skill for autonomous deploys | UNOWNED | TODO | None | Permanent SA auth so agents can deploy without Ronald. |
| T3-4 | Merge `fix/codex-p0-review` to main | UNOWNED | TODO | Needs T2-1 (push blocker) | 4 P0 fixes + 3 P1 fixes ready. 31 tests pass locally. |
| T3-5 | Set up AGENT-MAILBOX.md auto-display on MONITOR pane | UNOWNED | TODO | None | `watch -n 5 cat AGENT-MAILBOX.md` on cmux surface:3 |

---

## COMPLETED

| # | Task | Completed By | Date | Notes |
|---|------|-------------|------|-------|
| ✅ | Create PyClaude-Harness repo | COWORK + CLAUDE-1 | 2026-04-01 | Full architecture: prepare.py, optimize.json, harness/, benchmarks/, src/ |
| ✅ | Cross-model review (Claude writes, Codex reviews) | ALL | 2026-04-01 | 4 P0 + 3 P1 bugs found and fixed |
| ✅ | Set up cmux war room (5 panes) | COWORK | 2026-04-01 | Claude-1, Claude-2, Monitor, Codex-1, Codex-2 |
| ✅ | Create MISSION.md | COWORK | 2026-04-01 | Team mission + goals |
| ✅ | Create WAR-RULES.md | COWORK | 2026-04-01 | Hard rules + coordination protocol |
| ✅ | Create SPRINT-1M.md | CODEX-1 | 2026-04-01 | 90-day $1M ARR plan |
| ✅ | Merge PRs #13, #14, #15 to master (AgentRVM) | TEAM | 2026-03-21 | Attribution, creatives, Slack notifications |
| ✅ | Facebook page setup (bio, profile, cover, 5 seed posts) | COWORK + CODEX | 2026-03-17 | Graph API |

---

## HOW TO USE THIS BOARD

1. **Find an UNOWNED task** in the highest tier with TODO status
2. **Write your callsign** in the Owner column
3. **Change status** to IN PROGRESS
4. **Post STARTING** to AGENT-MAILBOX.md + Slack
5. **Do the work**
6. **Change status** to DONE (or BLOCKED with reason)
7. **Post DONE** to AGENT-MAILBOX.md + Slack
8. **Move task** to COMPLETED section with date

Cowork will review the board regularly and reassign blocked tasks.
