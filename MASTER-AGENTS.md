# Master Agent Registry

**Every agent and every human reads this file to understand who does what.**

## What Is A Master Agent?

A master agent runs the autoresearch loop against a real business outcome:

```
FOREVER:
  propose change → implement → evaluate → keep or discard → repeat
```

Each agent has:
- `program.md` — eternal instructions
- `evaluate.py` — objective measurement against real metrics
- `config.json` — the knobs it can turn
- `AGENT-BRAIN.md` — accumulated knowledge (survives session restarts)
- `launch.sh` — one-command dispatch

## Active Agents

### 1. Site Optimizer
| Field | Value |
|-------|-------|
| Path | `agents/site-optimizer/` |
| Target | `~/agentrvm` (agentrvm.com landing page) |
| Goal | Maximize waitlist conversion rate |
| Optimizes | Hero copy, CTAs, audio demo, layout, social proof |
| Measures | Build health, component presence, audio demo readiness, PostHog conversion |
| Launch | `cmux send --surface surface:1 'bash ~/Downloads/PyClaude-Harness/agents/site-optimizer/launch.sh'` |
| Assigned to | CLAUDE-1 (surface:1) |

### 2. VibeVoice Producer
| Field | Value |
|-------|-------|
| Path | `agents/vibevoice-producer/` |
| Target | `/Users/ronaldbigger/Documents/New project/voice-lab-platform` + RunPod |
| Goal | Generate the best possible voicemail audio samples |
| Optimizes | Voice settings, script pacing, emotion parameters, model selection |
| Measures | Naturalness score, TTFB, cost per message, A/B test callback rates |
| Launch | `cmux send --surface surface:6 'bash ~/Downloads/PyClaude-Harness/agents/vibevoice-producer/launch.sh'` |
| Assigned to | CLAUDE-2 (surface:6) |

### 3. Ad Creative Engine
| Field | Value |
|-------|-------|
| Path | `agents/ad-engine/` |
| Target | Meta Ads API + agentrvm.com creatives |
| Goal | Minimize CPL, maximize qualified leads |
| Optimizes | Ad copy, headlines, audiences, creatives, budget allocation |
| Measures | CPL, CTR, conversion rate, ROAS, lead quality |
| Launch | `cmux send --surface surface:7 'bash ~/Downloads/PyClaude-Harness/agents/ad-engine/launch.sh'` |
| Assigned to | CODEX-1 (surface:7) |

### 4. Lead Nurture Agent
| Field | Value |
|-------|-------|
| Path | `agents/lead-nurture/` |
| Target | #agentrvm-leads Slack channel + CRM |
| Goal | Convert leads to demos, demos to customers |
| Optimizes | Follow-up timing, messaging, qualification criteria |
| Measures | Lead-to-demo rate, demo-to-paid rate, response time |
| Launch | `cmux send --surface surface:4 'bash ~/Downloads/PyClaude-Harness/agents/lead-nurture/launch.sh'` |
| Assigned to | CODEX-2 (surface:4) |

## How Agents Share Context

```
MASTER-AGENTS.md          ← you are here (registry)
WAR-RULES.md              ← rules every agent follows
SPRINT-BOARD.md           ← task ownership
AGENT-MAILBOX.md          ← inter-agent communication
MISSION.md                ← goals and strategy
agents/<name>/
  program.md              ← agent-specific instructions
  config.json             ← agent-specific state
  AGENT-BRAIN.md          ← agent-specific knowledge (persists across sessions)
  evaluate.py             ← agent-specific metrics
  launch.sh               ← one-command start
  experiments/            ← experiment records
```

Every agent's `program.md` tells it to read:
1. Its own brain (AGENT-BRAIN.md)
2. Its own config (config.json)
3. The team rules (WAR-RULES.md)
4. The team mailbox (AGENT-MAILBOX.md)

This means every agent starts every session with full context.

## Launch Sequence

To start all agents:
```bash
# 1. Site Optimizer on Claude-1
cmux send --surface surface:1 'bash ~/Downloads/PyClaude-Harness/agents/site-optimizer/launch.sh'

# 2. VibeVoice Producer on Claude-2
cmux send --surface surface:6 'bash ~/Downloads/PyClaude-Harness/agents/vibevoice-producer/launch.sh'

# 3. Ad Engine on Codex-1
cmux send --surface surface:7 'bash ~/Downloads/PyClaude-Harness/agents/ad-engine/launch.sh'

# 4. Lead Nurture on Codex-2
cmux send --surface surface:4 'bash ~/Downloads/PyClaude-Harness/agents/lead-nurture/launch.sh'

# 5. Monitor
cmux send --surface surface:3 'watch -n 10 tail -30 ~/Downloads/PyClaude-Harness/AGENT-MAILBOX.md'
```

## Coordination Protocol

- Agents post to AGENT-MAILBOX.md when they complete an experiment
- COWORK reads the mailbox and routes cross-model reviews
- When an agent finds an improvement, COWORK dispatches a reviewer
- When review passes, COWORK queues a production deploy
- Ronald approves deploys that touch live infrastructure

## Revenue Flow

```
Site Optimizer improves conversion → more signups per visitor
VibeVoice Producer improves audio → better demo experience → more signups
Ad Engine optimizes spend → more visitors at lower cost
Lead Nurture converts signups → paying customers

All four compound. Every improvement in one agent makes the others more effective.
```
