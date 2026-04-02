# Harness Autoresearch Report — Meta-Agent Analysis

**Author**: harness-improver (Claude Opus 4.6)
**Date**: 2026-04-02
**Branch**: fix/codex-p0-review
**Proof Level**: idea (analysis only, no code changes applied)

---

## Executive Summary

The PyClaude-Harness has strong architectural bones — CMUX event bus, dispatch engine, heartbeat monitoring, secrets management, and a Karpathy-style autoresearch loop. But it is **not yet a self-improving system**. It is a collection of **scaffolding that could become one**. The gap between "architecture exists" and "system runs autonomously" is significant.

**Bottom line**: The harness can dispatch agents and track their health. It cannot yet learn from their outcomes, propagate improvements across agents, or improve itself without human intervention.

---

## 1. Critical Gaps (What's Missing for Fully Autonomous Operation)

### 1.1 No Feedback Loop from Agent Outcomes to Harness Config — **HIGH**

The autoresearch loop in `agents/ad-engine/autoresearch.py` optimizes `optimize.json` for Claude Code benchmarks. But there is **no equivalent loop for the harness itself**. When agents succeed or fail, nobody learns from it systematically.

**What exists**: CMUX logs `task.done` / `task.failed` events. Monitor renders dashboards.
**What's missing**: Nothing reads those events, computes patterns, and proposes harness improvements.

**Proposed fix**: Create `src/coordinator/feedback.py`:

```python
"""Feedback loop: analyze CMUX outcomes → propose harness improvements."""

from .cmux import JsonlMux

def analyze_outcomes(mux: JsonlMux, window_hours: int = 24) -> dict:
    """Analyze recent task outcomes for patterns."""
    done = mux.history(kind="task.done")
    failed = mux.history(kind="task.failed")
    blocked = mux.history(kind="task.blocked")

    return {
        "success_rate": len(done) / max(len(done) + len(failed), 1),
        "block_rate": len(blocked) / max(len(done) + len(failed) + len(blocked), 1),
        "common_failure_claims": _extract_common_claims(failed),
        "avg_task_duration_s": _avg_duration(done),
        "stale_agent_count": _count_stale(mux),
        "recommendations": _generate_recommendations(done, failed, blocked),
    }

def _generate_recommendations(done, failed, blocked) -> list[str]:
    recs = []
    if len(failed) > len(done):
        recs.append("More tasks failing than succeeding. Review task complexity or agent capability.")
    if len(blocked) > 2:
        recs.append("Multiple blockers active. Check dependency chains.")
    return recs
```

### 1.2 CMUX Is Append-Only JSONL with No Compaction — **HIGH**

`.cmux/events.jsonl` grows forever. Every `history()` call reads the entire file from disk. At 100 events this is fine. At 10,000 events (a few weeks of multi-agent operation), every health check, dispatch readiness check, and monitor refresh will be slow.

**The math**: `snapshots()` iterates all events for every agent. `pending_handoffs()` iterates all events twice (once for pending kinds, once for resolution checks). `is_dispatchable()` calls both. A single monitor refresh with 7 agents = ~21 full file scans.

**Proposed fix**: Add compaction to `JsonlMux`:

```python
def compact(self, keep_last_n: int = 1000) -> int:
    """Compact events.jsonl to last N events. Returns events removed."""
    events = list(self.history())
    if len(events) <= keep_last_n:
        return 0
    removed = len(events) - keep_last_n
    kept = events[-keep_last_n:]
    # Atomic write
    tmp = self.path.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        for e in kept:
            f.write(json.dumps(e.to_dict(), sort_keys=True) + "\n")
    tmp.rename(self.path)
    return removed
```

Also add an in-memory index: cache latest event per agent so `snapshots()` doesn't re-scan.

### 1.3 No Scorecard Implementation — **HIGH**

`DIGITAL-EMPLOYEE-ARCHITECTURE.md` defines an elegant Profitability Quotient (PQ) system with monthly scorecards, automated actions, and Slack dashboards. None of it is implemented. The `generate_scorecard()` function in the architecture doc is pseudocode only.

**What's needed**: `src/coordinator/scorecard.py` that:
1. Reads CMUX events to count task completions/failures per agent
2. Reads agent config.json for cost data
3. Computes PQ = (revenue + savings) / cost
4. Writes scorecard JSON to `agents/{name}/scorecards/YYYY-MM.json`
5. Posts summary to Slack

### 1.4 Dispatch Is Fire-and-Forget — **MEDIUM**

`dispatch.py` publishes `task.assign` and generates a shell command. It does not:
- Wait for ACK and retry/escalate if none comes
- Monitor task progress after dispatch
- Handle timeouts (agent runs for 2 hours with no output)
- Re-dispatch on failure

The ACK deadline (2 minutes) is defined in `monitor.py` but nothing enforces it. `is_dispatchable()` checks for overdue ACKs but nobody calls it on a timer.

**Proposed fix**: Add a dispatch supervisor daemon:

```python
# src/coordinator/supervisor.py
"""Watches dispatched tasks. Escalates on timeout, retries on failure."""

def supervise(mux, correlation_id, timeout_s=1800):
    """Block until task resolves or timeout. Returns outcome."""
    # Poll CMUX for resolution events on this correlation_id
    # Escalate if no progress after timeout_s
    # Re-dispatch if agent goes dark
```

### 1.5 No Cross-Agent Learning — **HIGH**

Each agent has its own `AGENT-BRAIN.md`. Knowledge is siloed. When ad-engine discovers that "FOMO angle has highest conversion", site-optimizer doesn't know. When site-optimizer learns that "hero CTA above fold increases signups 12%", ad-engine can't use that for landing page alignment.

**Proposed fix**: Shared knowledge base at `shared/KNOWLEDGE.md` or structured `shared/learnings.jsonl`:

```json
{"agent": "ad-engine", "domain": "copy", "learning": "FOMO angle has 4.2% conversion, highest of all angles", "confidence": 0.8, "date": "2026-04-01"}
{"agent": "site-optimizer", "domain": "layout", "learning": "CTA above fold increases signup 12% vs below", "confidence": 0.7, "date": "2026-04-02"}
```

Agents read `shared/learnings.jsonl` at startup and incorporate relevant cross-domain learnings.

---

## 2. Inefficiencies in Current Code

### 2.1 `history()` Scans Are O(n) for Everything — **HIGH**

Every query method in `cmux.py` opens the file, reads all lines, and filters in Python. This is the single biggest performance bottleneck.

| Method | Full scans | Called by |
|--------|-----------|----------|
| `snapshots()` | 1 | `render_monitor_view()`, `idle_agents()`, `render_health_dashboard()` |
| `pending_handoffs()` | 1 + 1 per event (resolution check) | `render_monitor_view()`, `render_health_dashboard()`, `is_dispatchable()` |
| `_is_acknowledged()` | 1 per event | `pending_handoffs()` |
| `_is_cancelled()` | 1 per event | `pending_handoffs()` |
| `is_dispatchable()` | 3+ (snapshots + history(sender) + history(kind) + pending_handoffs) | `dispatch()` |

A single `render_health_dashboard()` for 7 agents: ~35+ full file scans minimum.

**Fix**: Add a `LazyIndex` that caches parsed events and only reads new lines since last read (track file offset).

### 2.2 `_is_resolved()` Is O(n^2) — **MEDIUM**

`pending_handoffs()` finds all pending events, then for each, calls `_is_acknowledged()` which calls `self.history(correlation_id=...)` — another full scan. For N pending events with M total events, this is O(N*M).

**Fix**: Build correlation_id index once, then look up.

### 2.3 Heartbeat `watch` Blocks Forever with No Graceful Shutdown — **LOW**

`watch_heartbeats()` in `heartbeat.py` sleeps in a tight loop with `time.sleep(interval)`. No signal handling, no way to interrupt cleanly except KeyboardInterrupt. If the parent process dies, the heartbeat loop becomes a zombie.

**Fix**: Use `threading.Event` for cancellation, add SIGTERM handler.

### 2.4 `generate_launch_command()` Has Shell Injection Risk — **MEDIUM**

`dispatch.py:168` interpolates `task` directly into shell script:
```python
f'--claim "{task[:80]}"'
```

If `task` contains `"; rm -rf /; echo "`, it's game over. The `task` comes from dispatch CLI args which could come from CMUX events.

**Fix**: Use `shlex.quote()` for all interpolated values:
```python
import shlex
f'--claim {shlex.quote(task[:80])}'
```

### 2.5 Secrets Manager Makes 4 Network Calls Sequentially — **LOW**

`get_secret()` tries env → Worker → local → GCP. If Worker is down and GCP is slow, every secret lookup takes ~25s (10s Worker timeout + 15s GCP timeout). With 4 secrets per agent, that's 100s at startup.

**Fix**: Parallel backend queries with `concurrent.futures.ThreadPoolExecutor`, or cache after first successful lookup.

---

## 3. Patterns That Should Be Generalized Across All Agents

### 3.1 The Autoresearch Loop Is Agent-Specific — Should Be a Framework

`agents/ad-engine/autoresearch.py` implements: PROPOSE → APPLY → EVALUATE → DECIDE → LOG → REPEAT.

This pattern is identical for every agent. But each agent would need to reimplement it from scratch. The `harness_bridge.py` tries to bridge but is tightly coupled to ad-engine's `optimize.json` structure.

**Proposed**: Extract a generic `AgentLoop` class:

```python
# src/agent_loop.py
class AgentLoop:
    """Generic autoresearch loop for any agent."""

    def __init__(self, agent_name: str, config_path: Path, brain_path: Path):
        self.agent = agent_name
        self.config = config_path
        self.brain = brain_path

    def propose(self) -> Proposal:
        """Override: generate a hypothesis."""
        raise NotImplementedError

    def apply(self, proposal: Proposal) -> bool:
        """Override: apply the proposal to config."""
        raise NotImplementedError

    def evaluate(self) -> dict:
        """Override: measure the result."""
        raise NotImplementedError

    def decide(self, baseline: float, result: float) -> str:
        """Keep or discard. Default: keep if improved."""
        return "keep" if result > baseline else "discard"

    def run(self, max_experiments: int = 10):
        """The loop. Same for every agent."""
        baseline = self.evaluate()
        for i in range(max_experiments):
            proposal = self.propose()
            self.apply(proposal)
            result = self.evaluate()
            decision = self.decide(baseline["score"], result["score"])
            if decision == "keep":
                baseline = result
                self.update_brain(proposal, result)
            else:
                self.rollback()
            self.log(proposal, result, decision)
```

Each agent subclasses and overrides `propose()`, `apply()`, `evaluate()`.

### 3.2 AGENT-BRAIN.md Is Unstructured — Should Be Queryable

Every agent has `AGENT-BRAIN.md` as freeform markdown. This makes it easy to read but impossible to query programmatically. When the feedback loop wants to find "what did ad-engine learn about FOMO copy?", it has to parse markdown.

**Proposed**: Dual format — keep markdown for humans, add `AGENT-BRAIN.jsonl` for machines:

```json
{"category": "copy", "key": "fomo_angle_ctr", "value": 4.2, "unit": "percent", "confidence": 0.8, "source": "experiment-003", "date": "2026-04-01"}
```

### 3.3 Launch Scripts Are Copy-Pasted — Should Be Templated

Each agent's `launch.sh` is a slight variation of the same pattern:
1. Export secrets
2. Emit STARTING heartbeat
3. Run agent (claude -p or codex exec)
4. Emit DONE/FAILED heartbeat

This is already in `dispatch.py:generate_launch_command()` but agents also have their own `launch.sh`. Two sources of truth.

**Fix**: Delete per-agent `launch.sh` files. Use `dispatch.py` as the single launcher. Agents only need `program.md` + `config.json` + `evaluate.py`.

### 3.4 Evaluation Scripts Are Incompatible

- `prepare.py` scores on `composite_score` (0-1 scale, weighted: 50% completion + 25% efficiency + 25% accuracy)
- `agents/ad-engine/evaluate.py` scores on its own composite (different weights, different metrics)
- `agents/site-optimizer/evaluate.py` scores on another composite (build + types + components + audio)
- `harness/evaluator.py` wraps `prepare.py` but adds its own diagnostics layer

There's no common evaluation interface. The orchestrator can't compare agents or run cross-agent experiments.

**Fix**: Define `EvalResult` protocol:

```python
@dataclass
class EvalResult:
    composite_score: float  # 0.0-1.0, always
    metrics: dict[str, float]  # domain-specific
    failures: list[str]
    timestamp: str
```

All evaluators return `EvalResult`. The harness can then compare across agents.

---

## 4. What's Weak — Brutal Honesty

### 4.1 The Evaluation Is Fake

`prepare.py` doesn't call Claude. It simulates evaluation using string-length heuristics and config inspection. The `evaluate_task()` function at line 147 decides completion based on `len(task.prompt) < 200` and tool coverage ratios. This means:
- **Optimizing `optimize.json` against these benchmarks optimizes for the simulator, not Claude.**
- Any "improvement" in composite_score is an improvement in fooling the heuristic, not in real-world performance.
- The entire autoresearch loop is currently optimizing a mirage.

**Impact**: Every experiment result since inception is meaningless for production. The harness thinks it's improving but it's hill-climbing on a synthetic proxy.

**Fix (hard but necessary)**: Replace simulated evaluation with real Claude Code execution:
1. Run Claude Code against each benchmark task via subprocess
2. Parse actual tool calls from output
3. Score based on real completion, real token usage, real tool accuracy
4. This costs tokens but is the only way to get real signal

### 4.2 No Agent Has Ever Run Autonomously

Despite elaborate dispatch, heartbeat, and monitoring infrastructure, the CMUX event log shows only manual test events. No agent has completed a full autoresearch cycle in production. The harness_bridge.py has known P0 bugs that prevent the loop from running. The site-optimizer can't evaluate because it has no PostHog integration and no audio sample.

**Impact**: All the infrastructure is untested at the system level. Unit tests pass, but end-to-end flow has never executed.

### 4.3 The Harness Can't Improve Itself

The meta-agent concept (harness-improver) is mentioned in architecture docs but doesn't exist as code. There's no automated way for the harness to:
- Detect its own performance issues
- Propose changes to coordinator code
- Test those changes safely
- Deploy improvements

It's turtles all the way down — but the bottom turtle (self-improvement) is missing.

### 4.4 Documentation-Code Drift Is Already Bad

| Doc claim | Reality |
|-----------|---------|
| "optimize.py is the target" (README, program.md) | optimize.py deleted, optimize.json is the target |
| "28 tests" (CLAUDE.md) | 56 tests exist (test_cmux.py and test_heartbeat.py added) |
| "8 parallel agents" (MISSION.md) | 0 agents running autonomously |
| "CMUX is canonical" (WAR-RULES.md) | CMUX has ~20 test events, mailbox has the real conversation |
| Scorecard system (DIGITAL-EMPLOYEE-ARCHITECTURE.md) | No implementation exists |

### 4.5 Agent Cost Model Is Theoretical

The PQ (Profitability Quotient) system assumes revenue attribution is possible. For ad-engine, this is tractable (Meta conversion tracking). For site-optimizer, it requires PostHog + attribution modeling. For vibevoice-producer, there's no revenue path yet. For lead-nurture, there's no CRM.

Without real revenue data, PQ is always 0/cost = 0. Every agent is "unprofitable" and the automated action table says "alert Ronald, pause non-critical tasks, diagnose."

---

## 5. Proposed Continuous Improvement Loop for the Harness

### The Harness Meta-Loop

```
┌─────────────────────────────────────────────────────┐
│                 HARNESS META-LOOP                     │
│                 (runs weekly)                          │
│                                                       │
│  1. MEASURE                                           │
│     - Count CMUX events by kind (done/failed/blocked) │
│     - Compute per-agent success rate                  │
│     - Measure dispatch→completion latency             │
│     - Measure heartbeat reliability                   │
│     - Measure CMUX file size & query time             │
│                                                       │
│  2. ANALYZE                                           │
│     - Which agents are stuck most often?              │
│     - Which task types fail most?                     │
│     - Where are the bottlenecks?                      │
│     - What escalations went unresolved?               │
│                                                       │
│  3. PROPOSE                                           │
│     - Generate improvement hypotheses                 │
│     - Rank by impact × feasibility                    │
│     - Write proposals to harness-proposals.jsonl      │
│                                                       │
│  4. APPLY (with human approval for L1/L2 changes)     │
│     - L0: Config changes (thresholds, intervals)      │
│     - L1: Code changes (new coordinator features)     │
│     - L2: Architecture changes (new modules, patterns)│
│                                                       │
│  5. VERIFY                                            │
│     - Run test suite                                  │
│     - Run dispatch dry-run                            │
│     - Compare metrics to previous week                │
│                                                       │
│  6. COMMIT & LOG                                      │
│     - Commit improvements to git                      │
│     - Log to harness-experiments.tsv                  │
│     - Post summary to Slack                           │
│                                                       │
│  GOTO 1                                               │
└─────────────────────────────────────────────────────┘
```

### Implementation: `src/coordinator/meta_loop.py`

```python
"""Meta-loop: the harness improves itself."""

from .cmux import JsonlMux
from .monitor import KNOWN_AGENTS, agent_health
from datetime import datetime, timezone, timedelta

def measure(mux: JsonlMux, window_hours: int = 168) -> dict:
    """Measure harness health over the last window_hours."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=window_hours)
    all_events = mux.history()
    recent = [e for e in all_events if _parse_ts(e.timestamp) > cutoff]

    done = [e for e in recent if e.kind == "task.done"]
    failed = [e for e in recent if e.kind == "task.failed"]
    blocked = [e for e in recent if e.kind == "task.blocked"]
    heartbeats = [e for e in recent if e.kind == "task.status"]

    return {
        "window_hours": window_hours,
        "total_events": len(recent),
        "tasks_done": len(done),
        "tasks_failed": len(failed),
        "tasks_blocked": len(blocked),
        "success_rate": len(done) / max(len(done) + len(failed), 1),
        "heartbeat_count": len(heartbeats),
        "unique_agents": len(set(e.sender for e in recent)),
        "cmux_file_size_kb": mux.path.stat().st_size / 1024 if mux.path.exists() else 0,
    }

def analyze(metrics: dict) -> list[dict]:
    """Generate improvement hypotheses from metrics."""
    issues = []

    if metrics["success_rate"] < 0.7:
        issues.append({
            "issue": "Low success rate",
            "severity": "HIGH",
            "hypothesis": "Tasks are too complex or agents lack capability",
            "action": "Break tasks into smaller units, add pre-flight checks",
        })

    if metrics["cmux_file_size_kb"] > 1000:
        issues.append({
            "issue": "CMUX file growing large",
            "severity": "MEDIUM",
            "hypothesis": "No compaction running",
            "action": "Enable weekly CMUX compaction",
        })

    if metrics["unique_agents"] < 2:
        issues.append({
            "issue": "Low agent utilization",
            "severity": "HIGH",
            "hypothesis": "Most agents are not running",
            "action": "Check dispatch daemon, verify agent health",
        })

    if metrics["heartbeat_count"] < metrics["unique_agents"] * 24:
        issues.append({
            "issue": "Low heartbeat density",
            "severity": "MEDIUM",
            "hypothesis": "Agents not heartbeating reliably",
            "action": "Check heartbeat wrappers in launch commands",
        })

    return issues
```

---

## 6. Improvement Proposals — Ranked by Impact

### Tier 1: HIGH Impact (Do This Week)

| # | Proposal | Files | Effort | Why |
|---|----------|-------|--------|-----|
| H1 | Fix shell injection in dispatch.py | `src/coordinator/dispatch.py` | 30 min | Security vulnerability — task strings from CMUX are user-controlled |
| H2 | Add CMUX compaction | `src/coordinator/cmux.py` | 2 hrs | Prevents O(n) degradation as events accumulate |
| H3 | Add `shlex.quote()` to all shell interpolations | `src/coordinator/dispatch.py` | 30 min | Same as H1, comprehensive pass |
| H4 | Extract generic `AgentLoop` base class | `src/agent_loop.py` | 4 hrs | Enables every agent to run autoresearch without reimplementing |
| H5 | Fix remaining P0s (KeyError: 'score', stale doc refs) | `harness/orchestrator.py`, docs | 2 hrs | Unblocks the first real experiment run |
| H6 | Add CMUX in-memory caching layer | `src/coordinator/cmux.py` | 3 hrs | 10-30x speedup for monitor/dispatch |

### Tier 2: MEDIUM Impact (Do This Month)

| # | Proposal | Files | Effort | Why |
|---|----------|-------|--------|-----|
| M1 | Implement scorecard generator | `src/coordinator/scorecard.py` | 8 hrs | Enables PQ tracking, automated license decisions |
| M2 | Add dispatch supervisor daemon | `src/coordinator/supervisor.py` | 6 hrs | Catch stuck agents, enforce ACK deadlines |
| M3 | Standardize EvalResult protocol | `src/eval_protocol.py` | 4 hrs | Enable cross-agent comparison |
| M4 | Add cross-agent knowledge sharing | `shared/learnings.jsonl` | 6 hrs | Break knowledge silos |
| M5 | Replace simulated eval with real Claude execution | `prepare.py` | 16 hrs | Make benchmark results meaningful (HIGH impact but HIGH effort) |
| M6 | Add structured AGENT-BRAIN.jsonl alongside .md | All agents | 4 hrs | Machine-queryable agent knowledge |
| M7 | Implement feedback loop (CMUX outcomes → proposals) | `src/coordinator/feedback.py` | 8 hrs | Close the self-improvement loop |

### Tier 3: LOW Impact / Future

| # | Proposal | Files | Effort | Why |
|---|----------|-------|--------|-----|
| L1 | Migrate CMUX to SQLite for indexed queries | `src/coordinator/cmux.py` | 12 hrs | Eliminates O(n) entirely |
| L2 | Add Prometheus metrics endpoint | `src/coordinator/metrics.py` | 8 hrs | Grafana dashboards for agent ops |
| L3 | Implement token refresh daemon | `src/coordinator/token_refresh.py` | 8 hrs | Canva/OAuth tokens auto-refresh |
| L4 | Add multi-VM CMUX sync via Cloudflare D1 | `src/coordinator/cmux.py` | 20 hrs | Scale beyond single VM |
| L5 | Implement security auditor agent | `agents/security-auditor/` | 12 hrs | Detect leaked secrets, permission drift |

---

## 7. The Single Most Important Thing to Do Next

**Get one agent running a real autoresearch cycle end-to-end.**

Not the fanciest agent. Not the most valuable. The one that's closest to working. That's the **harness itself** running against `optimize.json` via `harness/orchestrator.py`.

Steps:
1. Fix KeyError: 'score' in orchestrator.py (30 min)
2. Fix stale doc references (30 min)
3. Run `python -m harness.orchestrator --max-experiments 3 --verbose` (10 min)
4. Verify results.tsv has 3 experiments logged
5. Verify optimize.json was modified and reverted correctly

Once this works, the pattern is proven. Then replicate it to ad-engine, then site-optimizer.

**The harness that has never improved itself cannot credibly improve other agents.**

---

## 8. Concrete Code Changes Ready to Implement

### 8.1 Shell Injection Fix (dispatch.py)

```python
# Line 2: add import
import shlex

# Line 168: fix claim interpolation
f'--claim {shlex.quote(task[:80])}'

# Line 176: fix claim interpolation
f'--claim {shlex.quote(task[:80])}'

# Line 178: fix claim interpolation
f'--claim {shlex.quote("EXIT " + str(exit_code) + ": " + task[:60])}'
```

### 8.2 CMUX Compaction (cmux.py)

Add method to `JsonlMux`:

```python
def compact(self, keep_last_n: int = 1000) -> int:
    """Remove old events, keeping the last N. Returns count removed."""
    if not self.path.exists():
        return 0
    events = list(self.history())
    if len(events) <= keep_last_n:
        return 0
    removed = len(events) - keep_last_n
    kept = events[-keep_last_n:]
    tmp = self.path.with_suffix(".jsonl.tmp")
    with tmp.open("w", encoding="utf-8") as f:
        for e in kept:
            f.write(json.dumps(e.to_dict(), sort_keys=True) + "\n")
    tmp.rename(self.path)
    return removed
```

### 8.3 KeyError: 'score' Fix (orchestrator.py)

In `run_single_experiment()`, the error path returns a dict without `score`. Wherever results are consumed, use `.get("composite_score", 0.0)` instead of `["score"]`.

---

## 9. Architecture Diagram — Current vs. Target

### Current State
```
                    CMUX (events.jsonl)
                         │
            ┌────────────┼────────────┐
            │            │            │
        dispatch     heartbeat    monitor
            │            │            │
            ▼            ▼            ▼
    [fire & forget] [append-only] [read-only dashboard]

    NO FEEDBACK ◄──────────────── NO LEARNING
```

### Target State
```
                    CMUX (events.jsonl + index)
                         │
     ┌──────────┬────────┼────────┬──────────┐
     │          │        │        │          │
 dispatch  heartbeat  monitor  feedback  scorecard
     │          │        │        │          │
     ▼          ▼        ▼        ▼          ▼
 [supervised] [reliable] [alerts] [learns]  [measures]
     │                            │          │
     └────────────────────────────┤          │
                                  ▼          │
                           meta-loop ◄───────┘
                              │
                              ▼
                    harness improvements
                    (propose → test → commit)
```

---

## 10. Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Agents optimize for fake evaluator forever | HIGH | HIGH | Implement real Claude evaluation (M5) |
| CMUX file grows unbounded, slows everything | HIGH | MEDIUM | Add compaction (H2) |
| Shell injection via task string in dispatch | MEDIUM | HIGH | Add shlex.quote (H1) |
| Knowledge silos between agents | HIGH | MEDIUM | Shared learnings (M4) |
| No human in the loop for code changes | LOW | HIGH | Trust levels in AUTONOMY.md already handle this |
| Agent goes rogue with Meta Ads budget | LOW | HIGH | Budget limits in agent authority scope (already designed) |

---

*This report is a snapshot. The harness should re-run this analysis monthly and track which proposals were implemented and what impact they had. That tracking IS the meta-loop.*

*harness-improver signing off. Next action: implement H1 (shell injection fix) and H2 (CMUX compaction) as the lowest-risk, highest-value changes.*
