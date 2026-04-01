# PyClaude-Harness — Agent Brain

## MANDATORY READS (before ANY work)
1. **WAR-RULES.md** — Hard rules. Non-negotiable. Defines workflow, priorities, commit rules.
2. **SPRINT-BOARD.md** — Live task board. Check ownership. Claim before starting.
3. **AGENT-MAILBOX.md** — Inter-agent comms. Read first, write when done.
4. **MISSION.md** — Goals, strategy, revenue context (~$2,500/day existing income).

## Multi-Agent System
You are part of an 8-agent team. Know your teammates:

| Callsign | Model | Location | CLI | Role |
|----------|-------|----------|-----|------|
| **COWORK** | Claude Opus 4.6 | Cowork desktop app (VM) | N/A | Orchestrator, router, Chrome/Slack/Cloudflare |
| **CLAUDE-1** | Claude Opus 4.6 | Mac (cmux surface:1) | `claude -p` | Primary coder |
| **CLAUDE-2** | Claude Opus 4.6 | Mac (cmux surface:6) | `claude -p` | Secondary coder |
| **CODEX-1** | GPT-5.4 | Mac (cmux surface:7) | `codex exec --full-auto` | Adversarial reviewer |
| **CODEX-2** | GPT-5.4 | Mac (cmux surface:4) | `codex exec --full-auto` | Regression tester |
| **MONITOR** | N/A | Mac (cmux surface:3) | `tail -f` | Passive display |

Capacity: 2 Cowork + 2 Claude Code + 4 Codex = 8 parallel agents. Scale as needed.

## Communication Protocol
- **AGENT-MAILBOX.md** — Read FIRST. Write when DONE.
- Format: `[CALLSIGN] [ISO-8601] [STATUS] — [One-line summary]`
- Statuses: `STARTING`, `DONE`, `BLOCKED`, `VERIFY`, `FAILED`, `HANDOFF`
- **SPRINT-BOARD.md** — Claim tasks before starting. Update status when done.
- **Slack #development-team** — Post for Ronald's visibility. Prefix: `[CALLSIGN]`
- **COWORK is the router.** Don't dispatch other agents directly.

## Who Is Ronald
- **Name**: Ronald Bigger
- **GitHub**: Rphants
- **Email**: hello@samedayagents.com
- **Company**: Same Day Agents — AI-powered tools for real estate wholesalers & investors

## Project Overview
Self-improving harness optimization for Claude Code, combining:
- **claw-code** — Python rewrite of Claude Code (in `src/`)
- **Meta-Harness** — Optimize the harness around AI models (in `harness/`)
- **autoresearch** — Karpathy's autonomous experiment loops (pattern in `program.md`)

## Architecture
```
prepare.py          — Fixed evaluator (READ-ONLY). Ground truth scoring.
optimize.json       — Agent-editable harness config (THE OPTIMIZATION TARGET)
program.md          — Autonomous loop instructions (autoresearch pattern)
harness/
  proposer.py       — Proposes changes (can use Claude as optimizer)
  evaluator.py      — Runs benchmarks, diagnostics
  orchestrator.py   — Autonomous experiment loop engine
benchmarks/tasks/   — 8 evaluation tasks (JSON)
src/                — claw-code Python base (40+ modules)
tests/              — 28 tests (pytest)
AGENT-MAILBOX.md    — Inter-agent communication
REVIEW-CODEX.md     — Codex's review findings
REVIEW-CLAUDE.md    — Claude's review findings
```

## Known Issues (Updated 2026-04-01)

### Fixed (on fix/codex-p0-review, not yet pushed — secret scanning blocker)
- ~~P0-1: orchestrator proposals didn't modify optimize.json~~ → FIXED (apply_proposal())
- ~~P0-2: tool_accuracy always 1.0~~ → FIXED (F1 score in prepare.py)
- ~~P0-3: exec_module() on arbitrary Python~~ → FIXED (migrated to optimize.json)
- ~~P0-4: git reset --hard destroys results.tsv~~ → FIXED (stash/restore)

### Open
- evaluator.py still uses OLD tool_accuracy formula (disagrees with prepare.py)
- KeyError: 'score' in orchestrator experiment 2 (error path missing score key)
- Stale optimize.py references in README, program.md, harness files
- GitHub push blocked by Slack webhook URL in CLAUDE.md/CODEX.md on branch

## Branch Convention
- `main` — stable, CI must pass
- `optimize/<tag>` — experiment branches (e.g., optimize/apr1)
- `fix/<description>` — bug fix branches
- `feat/<description>` — new features

## Git
- Remote: https://github.com/Rphants/PyClaude-Harness.git
- PAT: [REDACTED — use git credential helper or env var]
- Always push after completing work

## Slack Communication (CRITICAL — always post status updates)
All agents post to **#development-team** (C06RSE25LKT) after completing tasks.

### How to post from Claude Code or Codex:
```bash
curl -s -X POST "$SLACK_WEBHOOK_URL" \
  -H 'Content-Type: application/json' \
  -d '{"text": "[CLAUDE-CODE] Your status message here"}'
```

### Protocol:
1. **Before starting work**: Post what you're about to do
2. **After completing work**: Post summary + results
3. **On errors**: Post what went wrong so other agents can help
4. **Prefix your messages**: `[CLAUDE-CODE]` or `[CODEX]` or `[COWORK]`

### Channel: #development-team
- Webhook: Set SLACK_WEBHOOK_URL env var (see .env or credential store)
- Channel ID: C06RSE25LKT
- Ronald: U06RG1RJ78C
- Andres: U08JJ9RGNSV

### Example workflow:
1. Cowork dispatches Claude Code: "Fix the P0 bugs"
2. Claude Code posts to Slack: "[CLAUDE-CODE] Starting P0 fixes on fix/codex-p0-review"
3. Claude Code finishes, posts: "[CLAUDE-CODE] Done. 4 P0s fixed. 28/28 tests pass. Branch pushed."
4. Cowork reads Slack, dispatches Codex: "Verify the fixes"
5. Codex posts: "[CODEX] Verifying P0 fixes..."
6. Codex finishes: "[CODEX] PASS: All 4 P0s verified. Ready for merge."
7. Ronald sees entire conversation in Slack in real-time.
