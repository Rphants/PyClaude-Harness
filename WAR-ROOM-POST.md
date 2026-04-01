# 8 AI Agents. 2 Models. 1 Mission.

Just built a multi-agent war room where Claude Opus 4.6 and GPT-5.4
coordinate autonomously on the same codebase.

## The Setup
- **2x Claude Code** (Opus 4.6) — writing code, fixing bugs
- **2x Cowork** (Opus 4.6) — orchestrating, routing between agents
- **4x Codex** (GPT-5.4) — adversarial reviews, verification, strategy

All running in **cmux** (Ghostty-based terminal with AI agent notifications).
Each agent has a shared brain file (CLAUDE.md) and a mailbox (AGENT-MAILBOX.md)
for inter-agent communication.

## What Happened in 90 Minutes
1. Created PyClaude-Harness repo from scratch
2. Codex (GPT-5.4) reviewed Claude's code — found 4 critical bugs
3. Claude Code fixed all 4 bugs
4. Codex verified the fixes — 2 passed, 2 failed
5. Claude Code fixed the remaining 2
6. Codex verified again — all pass
7. Meanwhile, another Codex instance built a cmux coordinator module
8. Another Codex is writing the $1M sprint plan

Total human intervention: zero lines of code written manually.

## The Stack
- **PyClaude-Harness**: Self-improving harness optimization (Meta-Harness + autoresearch)
- **cmux**: Terminal multiplexer with AI agent support
- **File relay**: Cowork dispatches commands to Mac terminal agents
- **AGENT-MAILBOX.md**: Shared state for inter-agent communication
- **Cross-model review**: Claude writes, GPT reviews (and vice versa)

## The Vision
An autonomous development system that improves while you sleep.
Claude proposes changes. The evaluator measures. Keep improvements, discard regressions.
100 experiments overnight. Wake up to a better system.

This isn't the future of development. It's today.

---

Built by @Rphants with Claude Opus 4.6 + GPT-5.4
github.com/Rphants/PyClaude-Harness
