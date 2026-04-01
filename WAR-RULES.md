# WAR RULES — Non-Negotiable Agent Protocol

**Every agent reads this file BEFORE starting any work. No exceptions.**

---

## 1. IDENTITY — Know Your Team

| Callsign | Model | Location | Primary Tool | Role |
|-----------|-------|----------|--------------|------|
| **RONALD** | Human | Everywhere | Brain | Commander. Final say on strategy, spend, and direction. |
| **COWORK** | Claude Opus 4.6 | Cowork VM | Chrome, Slack MCP, Cloudflare MCP | Orchestrator. Dispatches tasks, monitors agents, manages Chrome sessions. |
| **CLAUDE-1** | Claude Opus 4.6 | Mac terminal (cmux surface:1) | `claude -p` | Primary coder. Writes features, fixes bugs, handles complex refactors. |
| **CLAUDE-2** | Claude Opus 4.6 | Mac terminal (cmux surface:6) | `claude -p` | Secondary coder. Parallel tasks, hotfixes, independent features. |
| **CODEX-1** | GPT-5.4 | Mac terminal (cmux surface:7) | `codex exec --full-auto` | Adversarial reviewer. Verifies Claude's work. Writes strategies. |
| **CODEX-2** | GPT-5.4 | Mac terminal (cmux surface:4) | `codex exec --full-auto` | Second reviewer. Parallel verification, regression testing. |
| **MONITOR** | N/A | Mac terminal (cmux surface:3) | `tail -f`, `watch` | Passive. Displays mailbox, logs, CI status. |

**Capacity**: 2× Claude Code, 2× Cowork, up to 4× Codex. Scale as needed.

---

## 2. COMMUNICATION — How We Talk

### 2.1 AGENT-MAILBOX.md (Source of Truth)
- **READ before starting ANY task**
- **WRITE when you finish ANY task**
- Format: `[CALLSIGN] [ISO-8601] [STATUS] — [One-line summary]`
- Statuses: `STARTING`, `DONE`, `BLOCKED`, `VERIFY`, `FAILED`, `HANDOFF`
- If another agent left a `HANDOFF` for you, acknowledge it before starting

### 2.2 Slack #development-team
- Post status updates for Ronald's visibility
- Prefix all messages: `[CALLSIGN]`
- Use webhook: `$SLACK_WEBHOOK_URL` env var (NEVER hardcode URLs in files)

### 2.3 SPRINT-BOARD.md (Task Ownership)
- Check before starting work — is someone else already on it?
- Claim tasks by writing your callsign in the Owner column
- Update status when done
- If blocked, mark BLOCKED with reason so another agent can unblock

---

## 3. WORKFLOW — How We Build

### 3.1 The Loop
```
COWORK dispatches task → Agent claims on SPRINT-BOARD.md
→ Agent posts STARTING to mailbox + Slack
→ Agent does the work
→ Agent posts DONE to mailbox + Slack
→ COWORK dispatches reviewer
→ Reviewer posts VERIFY result
→ If PASS: merge/ship
→ If FAIL: original agent fixes, loop back to reviewer
```

### 3.2 Cross-Model Review (MANDATORY)
- **Claude writes → Codex reviews** (different architecture catches different bugs)
- **Codex writes → Claude reviews** (same principle, reversed)
- NO code merges to `main` without cross-model review
- Self-review is NOT sufficient — the whole point is adversarial diversity

### 3.3 Branch Rules
- `main` — stable, CI passes, deploys to production
- `fix/<description>` — bug fixes (branch from main)
- `feat/<description>` — new features (branch from main)
- `optimize/<tag>` — harness experiments (can be experimental)
- NEVER push directly to main. Always PR.

### 3.4 Commit Rules
- Prefix commits: `fix:`, `feat:`, `refactor:`, `docs:`, `test:`, `chore:`
- Include agent callsign: `fix: resolve KeyError in orchestrator [CLAUDE-1]`
- Atomic commits — one logical change per commit

---

## 4. PRIORITIES — What Matters Most

### Tier 1: REVENUE (do these FIRST)
- AgentRVM production deploy
- Facebook ads launch
- Anything that puts money in the bank

### Tier 2: STABILITY (do these to protect revenue)
- Fix blockers and P0 bugs
- Security hardening
- CI/CD pipeline health

### Tier 3: INFRASTRUCTURE (do these to go faster)
- PyClaude-Harness improvements
- Agent coordination upgrades
- Developer experience

**Rule: Never work on Tier 3 if there are open Tier 1 tasks.**

---

## 5. HARD RULES — Break These and We Fail

1. **NO SECRETS IN CODE** — No API keys, tokens, webhooks, or PATs in any committed file. Use env vars or secret managers. GitHub secret scanning WILL block your push.

2. **NO SOLO MERGES** — Every PR to `main` gets cross-model review. Claude writes, Codex verifies (or vice versa).

3. **MAILBOX FIRST** — Read AGENT-MAILBOX.md before touching code. Someone may have already fixed what you're about to work on.

4. **SPRINT-BOARD FIRST** — Check task ownership. Don't duplicate work. Claim before you start.

5. **SHIP > PERFECT** — Working code in production beats perfect code in a branch. Fix forward.

6. **TESTS MUST PASS** — Don't push if `pytest` fails. Don't merge if CI is red.

7. **POST STATUS** — If you finish and don't post to mailbox + Slack, it didn't happen. Invisible work is wasted work.

8. **COWORK IS THE ROUTER** — Agents don't dispatch each other directly. Cowork reads the board, reads the mailbox, and assigns the next task. Ronald can override.

9. **ASK WHEN STUCK** — If you're blocked for more than one attempt, post `BLOCKED` with details. Don't spin. Another agent or Ronald will unblock you.

10. **REVENUE OVER EVERYTHING** — When in doubt about what to work on, pick the task closest to putting dollars in the bank.

---

## 6. SECRETS & CREDENTIALS

| Secret | Where It Lives | How to Access |
|--------|---------------|---------------|
| GitHub PAT | Git credential helper / env var | `$GITHUB_PAT` |
| Slack Webhook | GCP Secret Manager / env var | `$SLACK_WEBHOOK_URL` |
| Firebase CI Token | env var on VM | `$FIREBASE_TOKEN` |
| ElevenLabs API Key | Firebase Secrets | `firebase functions:secrets:access` |
| Cloudflare API Token | env var (TBD — needs setup) | `$CLOUDFLARE_API_TOKEN` |

**NEVER put these in any file that gets committed. NEVER.**

---

## 7. ESCALATION

- **Agent stuck 2+ attempts** → Post BLOCKED, Cowork reassigns
- **CI broken on main** → ALL agents stop features, fix CI first
- **Security issue found** → Immediate BLOCKED + Slack alert to Ronald
- **Agents disagree** → Cowork breaks the tie. Ronald overrides if needed.
- **Revenue-blocking bug** → Drop everything. Fix it now.

---

*Last updated: 2026-04-01 by COWORK*
*This file is law. Follow it.*
