# WAR RULES — Multi-Agent Operating System

**Every agent reads this file before starting work. No exceptions.**

This file exists to solve three problems:

1. Shared goals without duplicated work
2. Fast communication without ambiguity
3. Continual improvement without coordination drift

---

## 1. Command Chain

| Callsign | Role | Primary Responsibility |
|----------|------|------------------------|
| `RONALD` | Human commander | Final say on strategy, spend, risk, and direction |
| `COWORK` | Orchestrator | Routing, dispatch, prioritization, war-room visibility |
| `CLAUDE-*` | Builder | Features, fixes, refactors, implementation |
| `CODEX-*` | Adversarial verifier | Review, falsification, regression checks, strategy |
| `MONITOR` | Passive observer | Logs, CI, board state, visibility |

Rules:

- `RONALD` can override anyone.
- `COWORK` routes work between agents.
- Builders do not self-certify production readiness.
- Reviewers do not silently rewrite ownership; they verify and escalate.

---

## 2. Source Of Truth

### 2.1 CMUX Is Canonical

**Canonical coordination state lives in CMUX**, not in freeform chat and not in memory.

- Transport: `.cmux/events.jsonl`
- API surface: [src/coordinator/cmux.py](/Users/ronaldbigger/Downloads/PyClaude-Harness/src/coordinator/cmux.py)
- Message unit: `Envelope`
- Minimum fields: `sender`, `recipient`, `kind`, `payload`, `timestamp`

Use CMUX for:

- task assignment
- task status
- handoff
- verification result
- blocker escalation
- decision records

### 2.2 Mailbox Is A Human Mirror

[AGENT-MAILBOX.md](/Users/ronaldbigger/Downloads/PyClaude-Harness/AGENT-MAILBOX.md) is for human-readable summaries.

Rules:

- Append-only
- Never rewrite history
- Never delete the mailbox file
- Mirror CMUX state; do not invent a competing truth
- If CMUX and mailbox disagree, CMUX wins

Mailbox format:

`[CALLSIGN] [ISO-8601] [STATUS] — [summary]`

Allowed statuses:

- `STARTING`
- `DONE`
- `VERIFY`
- `BLOCKED`
- `FAILED`
- `HANDOFF`
- `DECISION`

### 2.3 Slack Is An External Mirror

Slack exists for visibility, not truth.

- Post concise status for Ronald and the room
- Never post secrets
- Never treat Slack as the canonical task ledger

### 2.4 Sprint Board Is Ownership State

[SPRINT-BOARD.md](/Users/ronaldbigger/Downloads/PyClaude-Harness/SPRINT-BOARD.md) tracks ownership and queue state.

- Check it before starting
- Claim before coding
- Release when blocked or done

---

## 3. Required Update Packet

Every meaningful update must include these four fields:

1. `branch`
2. `state`
3. `claim`
4. `verification`

Example:

`branch=fix/codex-p0-review | state=worktree-only | claim=fixed tool_accuracy edge case | verification=pytest -q tests/test_prepare.py`

Why:

- “Done” without scope is noise
- “Fixed” without proof is opinion
- “Passing” without state is misleading

---

## 4. Proof Levels

Agents must label the maturity of every claim.

### 4.1 `idea`

- Proposed direction only
- No code changed

### 4.2 `worktree-pass`

- Local edits exist
- Verification ran against uncommitted code

### 4.3 `branch-pass`

- Changes are committed on a named branch
- Verification ran against committed branch state

### 4.4 `merged-pass`

- Changes are merged to target branch
- Post-merge verification passed

**Never call something “done” without naming its proof level.**

---

## 5. Definition Of Done

A task is only `DONE` when all of these are true:

1. Ownership is clear
2. The change is committed or intentionally worktree-only
3. Verification commands are named
4. Known caveats are named
5. The next actor is clear

If any of those is missing, use `HANDOFF`, `VERIFY`, or `BLOCKED` instead of `DONE`.

---

## 6. Standard Workflow

### 6.1 Dispatch Loop

`COWORK assigns -> agent claims -> agent posts STARTING -> agent works -> agent posts HANDOFF/DONE -> opposite-model review -> verifier posts VERIFY -> COWORK routes next step`

### 6.2 Cross-Model Review Is Mandatory

- `CLAUDE` writes -> `CODEX` verifies
- `CODEX` writes -> `CLAUDE` verifies
- No self-approval for production claims

### 6.3 Review Must Prioritize Risk

Reviewers focus on:

- bugs
- regressions
- security
- hidden state drift
- missing verification

Not on style unless style creates risk.

---

## 7. Anti-Drift Rules

### 7.1 One Metric Path

If a metric exists in more than one place, agents must prove the implementations agree.

Example:

- ground truth in evaluator
- diagnostic copy in helper code

If they diverge, that is a stop-ship blocker.

### 7.2 One Migration At A Time

If moving from file A to file B, finish the migration atomically or clearly pause it.

- No half-migrations
- No stale runtime references
- No stale docs that contradict runtime

### 7.3 One Priority Stack

Priority order:

1. repo safety and secrets hygiene
2. honest evaluator / metrics integrity
3. orchestrator stability
4. sprint execution and revenue work
5. communication upgrades
6. growth sidecars like X/Twitter agents

When in doubt, move upward on the stack, not downward.

---

## 8. Git Rules

- Never push directly to `main`
- Never hardcode secrets
- Never force-push without explicit approval from `COWORK` or `RONALD`
- Never say “ready” on a branch with known blocker notes still open
- Commit messages should include intent, not just file names

Preferred prefixes:

- `fix:`
- `feat:`
- `docs:`
- `test:`
- `refactor:`
- `chore:`

---

## 9. Escalation Rules

Escalate immediately when:

- a verifier disproves a “done” claim
- the source of truth disappears or is overwritten
- secret exposure is suspected
- CI or deploy is red on the target branch
- two agents are acting on the same task without coordination
- a control loop crashes in a nominal path

Escalation format:

`[CALLSIGN] [TIME] [BLOCKED/FAILED/DECISION] — blocker, impact, recommended next action`

---

## 10. Continual Improvement

At the end of each meaningful cycle, the room should ask:

1. Did we move toward the shared goal?
2. What created confusion?
3. What proof was missing?
4. What rule needs tightening?

If the same confusion happens twice, update this file or CMUX behavior.

**Repeated ambiguity is a process bug, not a personality bug.**

---

## 11. Heartbeat Protocol

Every agent must prove liveness via CMUX heartbeats.

### 11.1 Heartbeat Requirements

- Every agent **must emit a heartbeat every 300 seconds**.
- Heartbeat kind: `task.status`
- Recipient: `monitor`
- CLI: `python -m src.coordinator.heartbeat --sender <callsign> --status <status> [flags]`

### 11.2 Heartbeat Payload

Required fields:

- `status`: one of `working`, `waiting`, `blocked`, `done`, `idle`

Optional fields:

- `branch`: current git branch
- `claim`: what the agent is working on
- `verification`: verification command
- `proof`: proof level (`idea`, `worktree-pass`, `branch-pass`, `merged-pass`)
- `next_action`: what the agent will do next

### 11.3 Health States

| State | Condition | Action |
|-------|-----------|--------|
| `healthy` | heartbeat < 300s, current assignment ACKed | None — keep working |
| `warm` | heartbeat 300-900s old, no blocker | Monitor — nudge if persists |
| `stale` | no heartbeat > 900s | ESCALATE — re-dispatch or mark dead |
| `blocked` | explicit blocker event | ESCALATE — unblock before new work |
| `dark` | pane exists but no CMUX presence | INVESTIGATE — agent may be stuck |
| `dead` | no pane + no CMUX presence | REVIVE or REPLACE |

### 11.4 ACK Discipline

- Every agent **must ACK `task.assign` within 2 minutes**.
- CLI: `python -m src.coordinator.ack send --sender <callsign> --message-id <id> --correlation-id <thread>`
- Unacked assignments after 2 minutes = agent is **not dispatchable**.
- COWORK must not mark tasks `IN PROGRESS` on the sprint board unless a CMUX ACK exists.

### 11.5 Dispatch Health Check

An agent is dispatchable **only if ALL are true**:

1. Agent has emitted at least one CMUX event (exists)
2. Agent status is routable (`working`, `waiting`, `idle`, `done`, `starting`, `accepted`)
3. Last heartbeat within 900 seconds
4. No unacknowledged blocker
5. No overdue (>2min) unacked `task.assign`

CLI: `python -m src.coordinator.monitor dispatch --agent <callsign>` (exit 0 = dispatchable, exit 1 = not)

---

## 12. Pane Ownership & Context Protection

Agents run in labeled panes. Pane hijacking destroys context and wastes tokens.

### 12.1 Pane Self-Labeling

Every pane **must be labeled** with: `CALLSIGN | LANE`

Examples: `CLAUDE-1 | BUILDER`, `CODEX-1 | VERIFIER`, `MONITOR | OBSERVER`

### 12.2 Pane Lock Rules

1. **One agent per pane.** No agent may take over another agent's pane.
2. **COWORK is the only dispatcher.** Only COWORK may assign agents to panes.
3. **Context is sacred.** An agent's pane context (scrollback, state, working directory) must not be destroyed by another process.
4. **No hostile takeover.** If Codex or Claude takes over a pane that belongs to another agent, MONITOR must escalate immediately.
5. **Graceful replacement only.** To replace an agent in a pane:
   a. Current agent must be declared `stale` or `dead` by MONITOR
   b. COWORK issues `task.reassign` event to CMUX
   c. New agent starts fresh in the pane with full context handoff
   d. Context handoff = new agent reads: AGENT-BRAIN.md, config.json, last 5 CMUX events for the correlation thread

### 12.3 Context Handoff Protocol

When replacing a stale/dead agent:

1. MONITOR declares agent stale/dead in CMUX (`kind=agent.stale` or `kind=agent.dead`)
2. COWORK reads the dead agent's last CMUX events and AGENT-BRAIN.md
3. COWORK writes a context brief to `/tmp/<callsign>-handoff.txt`
4. COWORK dispatches new agent with: the context brief + program.md + config.json + AGENT-BRAIN.md
5. New agent emits first heartbeat within 60 seconds of launch
6. New agent ACKs assignment within 2 minutes

### 12.4 Anti-Hijack Monitoring

MONITOR must check every 30 seconds:

- Is each labeled pane running the expected agent process?
- Has any pane's process changed without a COWORK `task.reassign`?
- If yes: escalate with `kind=agent.hijack` event

---

## 13. Monitor Duties

MONITOR is a passive observer with escalation authority.

1. Render CMUX health dashboard continuously (`python -m src.coordinator.monitor watch`)
2. List stale agents (no heartbeat > 900s)
3. List pending handoffs (unacked task.assign, task.handoff, task.verify)
4. List blocked agents (explicit blocker events)
5. Surface **one line of direction**: the single highest-priority next action
6. Escalate: stale agents, blocked agents, unacknowledged assignments, pane hijacks

---

## 14. Immediate Non-Negotiables

Right now, these are active operating rules:

1. CMUX is the canonical bus.
2. Mailbox and Slack are mirrors.
3. Every claim must name its proof level.
4. Every agent must heartbeat every 300 seconds.
5. Every agent must ACK task.assign within 2 minutes.
6. No task marked IN PROGRESS without a CMUX ACK.
7. No pane takeover without COWORK task.reassign.
8. No “done” push while evaluator and diagnostics disagree.
9. No “done” push while orchestrator has a known nominal crash path.
10. No half-finished config migrations presented as complete.
11. Context is sacred — handoff protocol required for all agent replacements.

---

*Last updated: 2026-04-01 by COWORK*
*This file is law until replaced by a stricter one.*
