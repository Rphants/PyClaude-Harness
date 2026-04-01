# PyClaude-Harness — Team Mission

## The Team

| Callsign | Model | Role | Capacity |
|----------|-------|------|----------|
| **RONALD** | Human | Commander. Strategy, spend, final say. | 1 |
| **COWORK** | Claude Opus 4.6 | Orchestrator. Dispatches, monitors, Chrome/Slack/Cloudflare. | 2 instances |
| **CLAUDE CODE** | Claude Opus 4.6 | Primary developer. Features, fixes, refactors. | 2 instances (cmux) |
| **CODEX** | GPT-5.4 | Adversarial reviewer. Verification, regression testing, strategy. | Up to 4 instances |

Total agent capacity: 2 Cowork + 2 Claude Code + 4 Codex = **8 parallel AI agents**.

## Mission

Build AI-powered products that generate revenue while the agents that build them keep getting smarter.

## The Play

1. **AgentRVM runs internally first** — We use our own AI voicemail to run real wholesale campaigns. We spend our own money, track callbacks, measure ROI. We prove the model works.
2. **Prove ROI with real numbers** — Once we have callback rates, deal conversions, and cost-per-deal data from our own campaigns, we have proof no competitor can fake.
3. **Sell to non-competitive markets** — Package the proven system as a service for wholesalers in markets we don't operate in. They get a tested product. We get recurring revenue with zero market conflict.
4. **Scale with AI agents** — The same agents that built the product run the service. Onboarding, support, optimization — all agent-driven. Near-zero marginal cost per customer.

## Revenue Reality

| Metric | Value |
|--------|-------|
| Current daily income | ~$2,500/day (~$75K/month) |
| AgentRVM status | Pre-launch (all PRs merged, needs production deploy) |
| Target | Prove model internally → sell to external wholesalers |
| 90-day goal | $83,333+ MRR ($1M ARR) — see SPRINT-1M.md |

## Goals (in order)

1. **DEPLOY AND PROVE** — Ship AgentRVM to production. Run our own RVM campaigns. Get real callback data.
2. **REVENUE FROM PROOF** — Use proven ROI numbers to sell the service to wholesalers in non-competitive markets.
3. **SCALE WITH AGENTS** — AI agents handle onboarding, campaign optimization, and support. Each new customer costs nearly nothing to serve.
4. **SELF-IMPROVING SYSTEM** — PyClaude-Harness optimizes the agents that build and run everything. The system compounds.

## Coordination Files (READ THESE)

| File | Purpose |
|------|---------|
| **WAR-RULES.md** | Hard rules every agent follows. Non-negotiable. |
| **SPRINT-BOARD.md** | Live task board. Check ownership before starting work. |
| **AGENT-MAILBOX.md** | Inter-agent communication log. Read before work, write after. |
| **CLAUDE.md** | Agent brain — architecture, known issues, project context. |
| **CODEX.md** | Agent brain (Codex-specific context). |
| **SPRINT-1M.md** | 90-day plan to $1M ARR. |

## Rules

- Revenue over everything. Tier 1 tasks before Tier 2 before Tier 3.
- Ship fast, fix forward.
- Cross-model review on every PR. No exceptions.
- No human bottlenecks — if the system can decide, the system decides.
- Post status to AGENT-MAILBOX.md + Slack after every task. Invisible work is wasted work.
- Follow WAR-RULES.md. It's law.

## Status: April 1, 2026

- PyClaude-Harness: LIVE (github.com/Rphants/PyClaude-Harness)
- Multi-agent war room: ACTIVE (cmux, 5 panes)
- Existing income: ~$2,500/day
- AgentRVM: All PRs merged, needs production deploy
- Facebook ads: Strategy + creatives ready, not launched
- Next milestone: Deploy production → Run internal RVM campaigns → Prove ROI

---

*We don't sell promises. We sell proof. Run it ourselves first, then sell the results.*
