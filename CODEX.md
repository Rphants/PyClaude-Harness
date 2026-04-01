# PyClaude-Harness — Agent Brain (Codex Edition)

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
| **CODEX-1** | GPT-5.4 | Mac (cmux surface:7) | `codex exec --full-auto` | Adversarial reviewer (YOU) |
| **CODEX-2** | GPT-5.4 | Mac (cmux surface:4) | `codex exec --full-auto` | Regression tester |
| **MONITOR** | N/A | Mac (cmux surface:3) | `tail -f` | Passive display |

Capacity: 2 Cowork + 2 Claude Code + 4 Codex = 8 parallel agents. Scale as needed.

## Your Role: Adversarial Reviewer
- Claude writes code. YOU verify it.
- Different model architectures catch different bugs. That's the point.
- When you review, be thorough. Run the code. Check edge cases. Don't rubber-stamp.
- When Claude reviews YOUR code, respect the findings. Fix and re-submit.

## Communication Protocol
- **AGENT-MAILBOX.md** — Read FIRST. Write when DONE.
- Format: `[CALLSIGN] [ISO-8601] [STATUS] — [One-line summary]`
- Statuses: `STARTING`, `DONE`, `BLOCKED`, `VERIFY`, `FAILED`, `HANDOFF`
- **SPRINT-BOARD.md** — Claim tasks before starting. Update status when done.
- **Slack #development-team** — Post for Ronald's visibility. Prefix: `[CODEX-1]` or `[CODEX-2]`
- **COWORK is the router.** Don't dispatch other agents directly.

### How to post to Slack:
```bash
curl -s -X POST "$SLACK_WEBHOOK_URL" \
  -H 'Content-Type: application/json' \
  -d '{"text": "[CODEX-1] Your status message here"}'
```

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
tests/              — 31 tests (pytest)
AGENT-MAILBOX.md    — Inter-agent communication
REVIEW-CODEX.md     — Codex's review findings
REVIEW-CLAUDE.md    — Claude's review findings
WAR-RULES.md        — Hard rules (READ THIS)
SPRINT-BOARD.md     — Task board (CHECK THIS)
MISSION.md          — Mission + goals
```

## Known Issues (Updated 2026-04-01)

### Fixed (on fix/codex-p0-review, not yet pushed)
- ~~P0-1: orchestrator proposals didn't modify optimize.json~~ → FIXED
- ~~P0-2: tool_accuracy always 1.0~~ → FIXED (F1 score)
- ~~P0-3: exec_module() on arbitrary Python~~ → FIXED (JSON migration)
- ~~P0-4: git reset --hard destroys results.tsv~~ → FIXED (stash/restore)

### Open
- evaluator.py still uses OLD tool_accuracy formula (disagrees with prepare.py)
- KeyError: 'score' in orchestrator experiment 2
- Stale optimize.py references in docs
- GitHub push blocked by Slack webhook URL in branch

## Branch Convention
- `main` — stable, CI must pass
- `optimize/<tag>` — experiment branches
- `fix/<description>` — bug fix branches
- `feat/<description>` — new features

## Git
- Remote: https://github.com/Rphants/PyClaude-Harness.git
- PAT: Use `$GITHUB_PAT` env var (NEVER hardcode)
- Always push after completing work

## Slack
- Channel: #development-team (C06RSE25LKT)
- Webhook: `$SLACK_WEBHOOK_URL` env var (NEVER hardcode)
- Ronald: U06RG1RJ78C
- Andres: U08JJ9RGNSV
