# PyClaude-Harness — Agent Brain

## Multi-Agent System
You are one of THREE agents working on this repo. Know your teammates:

| Agent | Model | Location | CLI | Role |
|-------|-------|----------|-----|------|
| **Cowork** | Claude Opus 4.6 | Cowork desktop app (VM) | N/A — orchestrator | Router, coordinator, Chrome browser access |
| **Claude Code** | Claude Opus 4.6 | Ronald's Mac | `/Users/ronaldbigger/.local/bin/claude` | Code writing, reviews, file edits |
| **Codex** | GPT-5.4 | Ronald's Mac | `/opt/homebrew/bin/codex` | Code review, adversarial testing, web browsing via Chrome DevTools |

## Communication Protocol
- **AGENT-MAILBOX.md** — Shared state file in repo root. Read it FIRST before starting work.
- When you finish a task, append your status: `[AGENT_NAME] [ISO_TIMESTAMP] [STATUS] — [SUMMARY]`
- If another agent left findings for you, acknowledge and respond in the mailbox.
- Cowork acts as the message bus between Claude Code and Codex.

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
optimize.py         — Agent-editable harness config (THE OPTIMIZATION TARGET)
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

## Known Issues (from v1 reviews)
- P0: Evaluator is simulated — scores on heuristics, not real Claude API calls
- P0: TOKEN_BUDGET→1 gives perfect score (trivially gameable)
- P0: load_harness_config() does exec_module() on arbitrary Python
- P1: tool_accuracy always 1.0 (unnecessary_tools list never populated)
- P1: git reset --hard in orchestrator destroys uncommitted results.tsv

## Branch Convention
- `main` — stable, CI must pass
- `optimize/<tag>` — experiment branches (e.g., optimize/apr1)
- `fix/<description>` — bug fix branches
- `feat/<description>` — new features

## Git
- Remote: https://github.com/Rphants/PyClaude-Harness.git
- PAT: [REDACTED — use git credential helper or env var]
- Always push after completing work
