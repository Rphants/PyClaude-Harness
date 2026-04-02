# Digital Employee Architecture
## AgentRVM — Self-Improving Agent Army

**Date**: 2026-04-02
**Author**: Ronald Bigger + Claude (Cowork)
**Status**: Architecture v1.0

---

## Vision

Every agent is a **digital employee** — with its own email, Slack identity, Claude/Codex license, and OAuth tokens. The PyClaude-Harness is itself an agent that continuously improves all other agents via autoresearch.

Agents are created one by one, each learning from the last. The harness evolves alongside them.

---

## 1. Identity Model — Agent as Employee

Each agent gets a full identity stack, just like a human hire:

| Layer | Human Employee | Digital Employee |
|-------|---------------|-----------------|
| Email | john@samedayagents.com | ad-engine@samedayagents.com |
| Slack | @john in workspace | @ad-engine bot user in workspace |
| Brain (Claude) | Claude Pro/Max seat | Claude Team Premium seat ($100-150/mo) |
| Brain (Codex) | ChatGPT Pro subscription | ChatGPT Pro subscription ($200/mo) |
| API Access | OAuth tokens | OAuth tokens (auto-refreshing) |
| Permissions | Role-based | Lane-based (AUTONOMY.md) |
| Audit Trail | Activity log | CMUX event log |

### 1.1 Email Accounts (Google Workspace)

**Recommended**: Google Cloud service accounts (free) with domain-wide delegation.

- `ad-engine@samedayagents.com` (service account, not full Workspace seat)
- `site-optimizer@samedayagents.com`
- `vibevoice@samedayagents.com`
- `lead-nurture@samedayagents.com`

**Why service accounts over Workspace seats**: Free, designed for automation, support OAuth 2.0 server-to-server flows, can be granted domain-wide delegation by Workspace admin. No $6/mo/seat cost.

**Alternative**: If agents need full Gmail inbox (to receive notifications, password resets for OAuth), create Workspace Business Starter seats at $6/mo each ($24/mo for 4 agents).

### 1.2 Slack Identity

**Recommended**: Slack App with bot tokens (free/included).

- Single Slack App ("AgentRVM Agents") with bot token
- Each agent posts as itself using the bot identity
- Channels: #agentrvm-leads, #development-team, #agent-heartbeats (new)
- Bot tokens are lightweight — no per-seat billing

**Alternative**: Create full Slack member accounts per agent ($7.25-15/mo each). Only needed if agents must DM external users or join private channels independently.

### 1.3 Claude Licensing (OAuth Seat Model)

Each agent gets its own Claude Pro subscription and logs in via OAuth — just like a human employee.

| Plan | Cost/agent/mo | Claude Code | Capacity | Best For |
|------|--------------|-------------|----------|----------|
| **Claude Pro** | $20 | Yes | 45 prompts/5hr | Agents running a few times/day |
| **Claude Max 5x** | $100 | Yes | 5x Pro | Heavy daily workload |
| **Claude Max 20x** | $200 | Yes | 20x Pro | 24/7 autonomous agents |

**Phase 1**: Claude Pro at $20/seat/mo. Each agent has its own email + OAuth login. Upgrade individual agents to Max when they hit capacity limits.

### 1.4 Codex Licensing (OAuth Seat Model)

Each agent gets its own ChatGPT Business subscription and logs in via OAuth.

| Plan | Cost/agent/mo | Codex | Notes |
|------|--------------|-------|-------|
| **ChatGPT Business** | $25-30 | Yes | Min 2 users, SAML SSO, admin console |
| **ChatGPT Plus** | $20 | Yes | Individual accounts, simpler |
| **ChatGPT Pro** | $200 | Yes | Highest rate limits |

**Phase 1**: ChatGPT Business at $25-30/seat/mo. Includes Codex, admin controls, data not used for training.

### 1.5 Per-Agent Total License Cost

| Tier | Claude | ChatGPT | Total/agent/mo |
|------|--------|---------|---------------|
| **Budget** | Pro ($20) | Plus ($20) | **$40** |
| **Standard** | Pro ($20) | Business ($25-30) | **$45-50** |
| **Power** | Max 5x ($100) | Business ($25-30) | **$125-130** |
| **Unlimited** | Max 20x ($200) | Pro ($200) | **$400** |

**Phase 1 (4 agents at Standard)**: **$180-200/mo total** for full Claude Code + Codex access.

---

## 2. OAuth Token Architecture

### 2.1 Service-Specific Tokens

| Service | Token Type | Lifetime | Refresh Strategy |
|---------|-----------|----------|-----------------|
| **Meta Ads** | System User token | **Never expires** | None needed (monitor for revocation) |
| **Canva** | OAuth 2.0 + PKCE | Access: 4 hrs, Refresh: months+ | Auto-refresh every 3.5 hrs |
| **ElevenLabs** | API key | Permanent until rotated | Quarterly rotation |
| **Figma** | OAuth 2.0 | Access: short-lived, Refresh: long-lived | Auto-refresh on 401 |
| **GitHub** | PAT (fine-grained) | Configurable (90 days recommended) | Auto-rotate quarterly |
| **Firebase** | CI token | Permanent | Rotate on compromise |

### 2.2 Meta System Users (Non-Expiring Tokens)

This is the **killer feature** for ad automation. System Users in Meta Business Manager:

1. Go to Business Manager → Users → System Users
2. Create "ad-engine-bot" (Employee role)
3. Generate token with scopes: `ads_management`, `ads_read`, `pages_manage_posts`
4. Token **never expires** — no refresh needed
5. Store in secrets-manager Worker

### 2.3 Canva OAuth Flow (One-Time Human Authorization)

Each agent needs one-time browser authorization, then auto-refreshes forever:

```
1. Register Canva app in Developer Portal
2. Agent requests authorization URL (with PKCE code_challenge)
3. Ronald clicks "Authorize" in browser (one time per agent)
4. Agent receives auth code → exchanges for access_token + refresh_token
5. Agent stores refresh_token in secrets-manager
6. Every 3.5 hours: agent refreshes access_token automatically
```

**Canva Plan Impact**:
- Free/Pro: generate, search, export, upload, resize (Pro only)
- Enterprise: autofill brand templates (killer feature for ad creative at scale)
- **Start with Pro**, upgrade to Enterprise when ad volume justifies it

### 2.4 Token Storage & Security

All tokens stored in the **agentrvm-secrets Cloudflare Worker**:

```
Backend priority (from src/coordinator/secrets.py):
1. Environment variables (override for testing)
2. Cloudflare Worker (secrets-manager.rphants.workers.dev)
3. Local .agent-secrets/ directory (.gitignored)
4. GCP Secret Manager (fallback)
```

**Security rules**:
- Tokens NEVER in git, NEVER in shell history
- Quarterly rotation for all rotatable tokens
- Alert on anomalous usage (rate spikes, off-hours, geographic anomalies)
- Immediate revocation on compromise detection
- Audit log for all token refreshes (agent ID, service, timestamp)

---

## 3. Agent Hosting — Single VM (Phase 1)

### 3.1 Why Single VM Wins for Now

All 4 agents on `openclaw-prod-vm` (existing GCP VM):

- **$0 incremental cost** (VM already running)
- CMUX event log is local (no network latency)
- All secrets accessible via Worker HTTPS
- Pane ownership maps to tmux sessions
- Simple dispatch daemon via systemd timer

### 3.2 Dispatch Daemon

```bash
# /etc/systemd/system/agent-dispatch.timer
[Timer]
OnBootSec=60s
OnUnitActiveSec=300s    # Check every 5 minutes
Persistent=true

# /etc/systemd/system/agent-dispatch.service
[Service]
Type=oneshot
User=hello
WorkingDirectory=/home/hello/PyClaude-Harness
ExecStart=/usr/bin/python3 -m src.coordinator.dispatch \
  --agent auto \
  --runner "claude -p" \
  --dangerously-skip-permissions
```

### 3.3 Scale Triggers (When to Move Beyond Single VM)

Migrate to multi-VM + Cloudflare D1 for CMUX when:
- Ad spend exceeds $500/day (ad-engine needs 24/7 operation)
- CPU/RAM on VM consistently >80%
- Multiple agents need to run simultaneously for >30 minutes
- Token costs justify dedicated infrastructure

---

## 4. Self-Improving Architecture (Autoresearch Loop)

### 4.1 The Meta-Agent: PyClaude-Harness as Agent

The harness itself is the 5th agent — it improves all other agents:

```
┌─────────────────────────────────────────────────────┐
│                  HARNESS (Meta-Agent)                │
│                                                      │
│  ┌──────────┐  ┌──────────┐  ┌─────────────────┐   │
│  │ CMUX     │  │ Monitor  │  │ Autoresearch    │   │
│  │ Event Bus│  │ Health   │  │ (Karpathy loop) │   │
│  └──────────┘  └──────────┘  └─────────────────┘   │
│        │              │               │              │
│  ┌─────┴──────────────┴───────────────┴──────┐      │
│  │              Dispatch Engine               │      │
│  └────────┬──────────┬───────────┬───────────┘      │
│           │          │           │                    │
│     ┌─────▼───┐ ┌───▼────┐ ┌───▼──────┐            │
│     │ad-engine│ │site-opt│ │vibevoice │ ...more     │
│     └─────────┘ └────────┘ └──────────┘             │
└─────────────────────────────────────────────────────┘
```

### 4.2 Karpathy Autoresearch Pattern

From `agents/ad-engine/autoresearch.py`:

```
LOOP:
  1. PROPOSE — Generate hypothesis (new copy angle, audience, creative variant)
  2. APPLY   — Create the experiment (Meta API, Canva, ElevenLabs)
  3. EVALUATE — Measure results (CPL, CTR, ROAS from Meta Insights API)
  4. DECIDE  — Keep winner, kill loser, propose next experiment
  5. LOG     — Write results to AGENT-BRAIN.md + experiments/
  GOTO LOOP
```

Each cycle makes the agent smarter. Knowledge persists in AGENT-BRAIN.md.

### 4.3 Harness Self-Improvement

The harness improves itself by:

1. **Monitoring agent performance** — Which agents succeed? Which get stuck?
2. **Analyzing dispatch patterns** — Are heartbeats reliable? ACK times improving?
3. **Refactoring coordinator code** — Better CMUX queries, smarter health detection
4. **Upgrading WAR-RULES** — Based on real operational incidents
5. **Creating new agents** — When a new capability is needed, scaffold from template

### 4.4 Agent Creation Pipeline (One by One)

```
CREATE NEW AGENT:
  1. Identify capability gap (manual task that should be automated)
  2. Copy agents/launch-template.sh → agents/{new-agent}/launch.sh
  3. Write program.md (mission, optimization surfaces, constraints)
  4. Create AGENT-BRAIN.md (seed with initial knowledge)
  5. Configure config.json (API IDs, thresholds, initial state)
  6. Register in secrets-manifest.json (which secrets it needs)
  7. Register identity: email, Slack, Claude/Codex seat, OAuth tokens
  8. Register in secrets-manager: python -m src.coordinator.secrets register {name}
  9. Assign lane in AUTONOMY.md
  10. Test manually via dispatch
  11. Enable autonomous loop
```

---

## 5. Current Agents + Future Roster

### 5.1 Built (Ready for Identity Setup)

| Agent | Mission | Lane Owner | Key APIs |
|-------|---------|-----------|----------|
| **ad-engine** | Turn ad spend into leads at lowest CPL | CODEX-2 | Meta, Canva, Figma, ElevenLabs |
| **site-optimizer** | Maximize conversion rate on agentrvm.com | CLAUDE-1 | Figma, Firebase, GitHub |
| **vibevoice-producer** | Generate highest-quality AI voicemail audio | CLAUDE-2 | ElevenLabs |
| **lead-nurture** | Follow up with voice demo leads | Unassigned | Slack, (future: CRM) |

### 5.2 Planned (Create One by One)

| Agent | Mission | Key APIs |
|-------|---------|----------|
| **content-engine** | Produce blog posts, social content, SEO pages | WordPress/Ghost, Canva |
| **seo-optimizer** | Monitor and improve organic search rankings | Google Search Console, Ahrefs/SEMrush |
| **competitor-watcher** | Track competitor pricing, features, ads | Web scraping, Meta Ad Library |
| **email-nurture** | Automated email sequences for leads | SendGrid/Mailchimp |
| **analytics-agent** | Dashboard creation, anomaly detection | GA4, BigQuery, Mixpanel |
| **support-agent** | Handle inbound support questions | Intercom/Zendesk, knowledge base |
| **billing-agent** | Invoice generation, payment follow-up | Stripe |
| **deploy-agent** | CI/CD, preview deploys, production rollouts | GitHub Actions, Firebase, GCP |

### 5.3 Harness Agents (Meta-Level)

| Agent | Mission | Key APIs |
|-------|---------|----------|
| **harness-improver** | Refactor PyClaude-Harness code, improve CMUX | GitHub |
| **autoresearch-meta** | Run autoresearch on autoresearch itself | Internal metrics |
| **security-auditor** | Scan for leaked secrets, permission drift | GitHub, GCP IAM |

---

## 6. Cost Model (OAuth Seat Model)

### 6.1 Phase 1 — 4 Agents (Current)

| Component | Monthly Cost | Notes |
|-----------|-------------|-------|
| VM (existing) | $0 | Already running |
| 4x Claude Pro seats | $80 | $20/seat, OAuth login |
| 4x ChatGPT Business seats | $100-120 | $25-30/seat, Codex included |
| Google service accounts | $0 | Free Cloud service accounts |
| Slack bot token | $0 | Included in workspace |
| Canva (Pro) | $13 | 1 seat, shared by agents |
| Secrets Worker (Cloudflare) | $0 | Free tier |
| **Phase 1 Total** | **$193-213/mo** | |

### 6.2 Phase 2 — 8 Agents (Post-PMF)

| Component | Monthly Cost | Notes |
|-----------|-------------|-------|
| VM (existing) | $0 | Same VM |
| 8x Claude Pro seats | $160 | $20/seat |
| 2x Claude Max upgrades | $160-360 | High-traffic agents upgraded |
| 8x ChatGPT Business seats | $200-240 | $25-30/seat |
| Google Workspace (optional) | $0-48 | If agents need full inboxes |
| Canva (Pro) | $13 | Shared |
| Additional APIs | $50-100 | SendGrid, Ahrefs, etc. |
| **Phase 2 Total** | **$583-921/mo** | |

### 6.3 Phase 3 — 12+ Agents (Scale)

| Component | Monthly Cost | Notes |
|-----------|-------------|-------|
| Dedicated VMs (3) | $75-150 | Agent clusters |
| 12x Claude seats (mixed tiers) | $440-1,040 | Pro + Max mix based on workload |
| 12x ChatGPT Business seats | $300-360 | $25-30/seat |
| Full identity stack | $50-100 | Workspace, Slack, APIs |
| **Phase 3 Total** | **$865-1,650/mo** | |

---

## 7. Immediate Action Plan

### Week 1: Identity Foundation
- [ ] Create Google Cloud service accounts for 4 agents
- [ ] Set up domain-wide delegation in Google Workspace admin
- [ ] Create Slack App "AgentRVM Agents" with bot token
- [ ] Set BOOTSTRAP_TOKEN on secrets-manager Worker
- [ ] Register 4 agents in secrets-manager

### Week 2: OAuth Token Setup
- [ ] Create Meta System User "ad-engine-bot" with non-expiring token
- [ ] Register Canva app in Developer Portal
- [ ] Complete Canva OAuth flow (Ronald authorizes once per agent)
- [ ] Store all tokens in secrets-manager
- [ ] Rotate ElevenLabs API key (old key in git history)

### Week 3: Autonomous Activation
- [ ] Deploy dispatch daemon (systemd timer on VM)
- [ ] Test ad-engine autoresearch loop end-to-end
- [ ] Enable heartbeat monitoring → Slack alerts
- [ ] Manual dispatch test for each agent

### Week 4: Self-Improvement
- [ ] Enable autoresearch loop on ad-engine
- [ ] Create harness-improver agent (meta-level)
- [ ] First autonomous ad creative generation
- [ ] First autonomous A/B test launch

---

## 8. Agent Performance Monitoring

Every digital employee gets measured like a real employee — effectiveness, productivity, and profitability.

### 8.1 The Profitability Quotient (PQ)

Each agent has a **Profitability Quotient** — the ratio of value generated to total cost:

```
PQ = (Revenue Attributed + Cost Savings) / (License Cost + API Costs + Compute Cost)
```

- **PQ > 1.0** = Agent is profitable (generating more value than it costs)
- **PQ = 1.0** = Break-even
- **PQ < 1.0** = Agent is costing more than it produces — needs optimization or termination

**Example**: ad-engine spends $50/mo in licenses, generates 20 leads at $8 CPL = $160 value → PQ = 3.2

### 8.2 Per-Agent Metrics

| Agent | Effectiveness KPIs | Productivity KPIs | Revenue Attribution |
|-------|-------------------|-------------------|-------------------|
| **ad-engine** | CPL, CTR, ROAS, conversion rate | Campaigns created/day, A/B tests run/week | Direct: ad-attributed signups × LTV |
| **site-optimizer** | Conversion rate lift, bounce rate delta | CRO tests run/week, pages optimized | Indirect: conversion lift × traffic × LTV |
| **vibevoice-producer** | Audio quality score, demo completion rate | Samples generated/day, settings tested | Indirect: demo-to-signup rate × LTV |
| **lead-nurture** | Response rate, follow-up speed, lead-to-close | Leads contacted/day, sequences sent | Direct: nurtured leads that convert × LTV |

### 8.3 Agent Scorecard (Monthly Review)

Each agent produces a monthly scorecard logged to `agents/{name}/scorecards/YYYY-MM.json`:

```json
{
  "agent": "ad-engine",
  "period": "2026-04",
  "license_cost": 45.00,
  "api_costs": 12.50,
  "compute_cost": 0,
  "total_cost": 57.50,
  "tasks_completed": 142,
  "tasks_failed": 8,
  "uptime_pct": 94.4,
  "effectiveness": {
    "cpl": 7.20,
    "ctr": 2.8,
    "roas": 3.4,
    "leads_generated": 28
  },
  "revenue_attributed": 196.00,
  "cost_savings": 0,
  "profitability_quotient": 3.41,
  "trend": "improving",
  "recommendation": "upgrade_to_max"
}
```

### 8.4 Automated Performance Actions

Based on PQ and trends, the harness takes automatic action:

| PQ Range | Trend | Action |
|----------|-------|--------|
| **PQ > 3.0** | Improving | Upgrade license tier (Pro → Max), increase budget |
| **PQ 2.0-3.0** | Stable | Maintain current allocation |
| **PQ 1.0-2.0** | Stable | Monitor closely, optimize parameters |
| **PQ 1.0-2.0** | Declining | Run autoresearch loop to find improvements |
| **PQ < 1.0** | Any | Alert Ronald, pause non-critical tasks, diagnose |
| **PQ < 0.5** for 2 months | Declining | Recommend agent termination or restructuring |

### 8.5 Dashboard & Alerts

Performance data flows to Slack and CMUX:

- **Daily**: Task count + pass/fail ratio posted to #agent-heartbeats
- **Weekly**: PQ summary for all agents posted to #development-team
- **Monthly**: Full scorecard review → Ronald reviews, approves upgrades/downgrades
- **Instant alert**: PQ drops below 1.0, agent goes dark >30min, budget overspend

### 8.6 Implementation

The scorecard system integrates with existing infrastructure:

1. **CMUX events** → raw data (tasks, heartbeats, completions, failures)
2. **Meta Insights API** → ad performance metrics (CPL, CTR, ROAS)
3. **Firebase Analytics** → site metrics (conversion rate, bounce rate)
4. **Secrets-manager audit log** → API usage costs
5. **License costs** → fixed per-agent from config.json
6. **Scorecard generator** → Python script aggregates all sources into monthly JSON
7. **Slack bot** → posts daily/weekly/monthly summaries

```python
# agents/{name}/scorecard.py
# Generates monthly profitability scorecard
# Sources: CMUX events + Meta API + Firebase Analytics + secrets audit

def generate_scorecard(agent_name: str, period: str) -> dict:
    tasks = count_cmux_events(agent_name, period, kind="task.done")
    failures = count_cmux_events(agent_name, period, kind="task.failed")
    costs = calculate_agent_costs(agent_name, period)
    revenue = attribute_revenue(agent_name, period)

    pq = (revenue["attributed"] + revenue["cost_savings"]) / costs["total"]

    return {
        "agent": agent_name,
        "period": period,
        "total_cost": costs["total"],
        "tasks_completed": tasks,
        "tasks_failed": failures,
        "revenue_attributed": revenue["attributed"],
        "profitability_quotient": round(pq, 2),
        "trend": calculate_trend(agent_name, period),
        "recommendation": recommend_action(pq, trend)
    }
```

---

## 9. Security & Compliance

### NIST AI Agent Standards (Incoming)
- NIST launched AI Agent Standards Initiative (Feb 2026)
- Public comment deadline: April 2, 2026
- Formal standards expected late 2026
- **Action**: Design system to be standards-ready (identity governance, audit trails, scoped authority)

### Agent Authority Scope
Each agent gets a written authority document:
```
AGENT: ad-engine
ACTS ON BEHALF OF: Ronald Bigger / Same Day Agents LLC
SCOPE: Manage Facebook ad campaigns within Ad Account act_125821642
BUDGET LIMIT: $50/day without approval, $500/day with COWORK approval
PERMISSIONS: Create campaigns, modify targeting, pause ads, export reports
CANNOT: Delete ad account, change payment method, access other business assets
```

### Audit Requirements
- All agent actions logged to CMUX event log
- Token refresh events logged with timestamp + agent ID
- Quarterly access review (which agents have which tokens)
- Immediate revocation protocol for compromised tokens

---

## 9. GitHub Repository Status

### PyClaude-Harness
- **Branch**: `fix/codex-p0-review` (43 uncommitted files)
- **Remote**: `github.com/Rphants/PyClaude-Harness.git`
- **Action needed**: Commit + push all changes, then merge to main

### agentrvm-secrets
- **Branch**: `main` (clean, up to date)
- **Remote**: `github.com/Rphants/agentrvm-secrets.git`
- **Status**: Ready

### Next Git Actions
1. Commit 43 files on PyClaude-Harness
2. Push to origin
3. Create PR or merge to main
4. Tag release: `v0.2.0-digital-employees`
