"""CMUX Monitor — Continuous health check and dispatch readiness.

Renders a live view of agent health states and enforces dispatch discipline.

Usage:
    # One-shot monitor view
    python -m src.coordinator.monitor

    # Check if a specific agent is dispatchable
    python -m src.coordinator.monitor dispatch --agent claude-1

    # Continuous monitor (refresh every 10s)
    python -m src.coordinator.monitor watch --interval 10

Health States:
    healthy  — heartbeat < 300s, current assignment ACKed
    warm     — heartbeat 300-900s, no blocker
    stale    — no heartbeat > 900s
    blocked  — explicit blocker event
    dark     — pane exists but no CMUX presence (never emitted)
    dead     — no pane + no CMUX presence
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .cmux import JsonlMux, AgentSnapshot, DEFAULT_CMUX_PATH, _utc_now, _parse_timestamp

# --- Constants ---

HEALTHY_THRESHOLD = 300    # seconds
WARM_THRESHOLD = 900       # seconds
ACK_DEADLINE = 120         # 2 minutes to ACK task.assign
KNOWN_AGENTS = ["cowork-relief", "cowork", "claude-1", "claude-2", "codex-1", "codex-2", "monitor"]


# --- Health State Engine ---

def agent_health(
    snapshot: AgentSnapshot,
    *,
    now: datetime | None = None,
    has_unacked_assign: bool = False,
) -> dict[str, Any]:
    """Compute health state for a single agent. Returns a rich dict."""
    current = now or datetime.now(timezone.utc)

    # Never seen in CMUX
    if snapshot.status == "never-seen" or not snapshot.updated_at:
        return {
            "agent": snapshot.agent,
            "health": "dead",
            "age_seconds": None,
            "status": snapshot.status,
            "reason": "No CMUX presence — never emitted an event",
        }

    age = int((current - snapshot.updated_dt).total_seconds())

    # Explicit blocker
    if snapshot.status == "blocked":
        return {
            "agent": snapshot.agent,
            "health": "blocked",
            "age_seconds": age,
            "status": snapshot.status,
            "claim": snapshot.claim,
            "reason": f"Explicit blocker: {snapshot.claim or 'unknown'}",
        }

    # Stale — no heartbeat for > 900s
    if age > WARM_THRESHOLD:
        return {
            "agent": snapshot.agent,
            "health": "stale",
            "age_seconds": age,
            "status": snapshot.status,
            "reason": f"No heartbeat for {age}s (threshold: {WARM_THRESHOLD}s)",
        }

    # Warm — heartbeat between 300-900s, no blocker
    if age > HEALTHY_THRESHOLD:
        return {
            "agent": snapshot.agent,
            "health": "warm",
            "age_seconds": age,
            "status": snapshot.status,
            "reason": f"Heartbeat {age}s old (> {HEALTHY_THRESHOLD}s)",
        }

    # Healthy — heartbeat < 300s
    health = "healthy"
    reason = f"Heartbeat {age}s old, status={snapshot.status}"

    # Downgrade if unacked assignment exists
    if has_unacked_assign:
        health = "warm"
        reason += " (WARN: unacked task.assign pending)"

    return {
        "agent": snapshot.agent,
        "health": health,
        "age_seconds": age,
        "status": snapshot.status,
        "branch": snapshot.branch,
        "claim": snapshot.claim,
        "proof": snapshot.proof,
        "reason": reason,
    }


# --- Dispatch Readiness ---

def is_dispatchable(
    mux: JsonlMux,
    agent: str,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    """
    Check all 5 dispatch conditions:
    1. Agent has emitted to CMUX (exists)
    2. Agent status is active (working/waiting/idle)
    3. Heartbeat within 900s
    4. No unacknowledged blocker
    5. Agent ACKs within 2 minutes (checked via pending_handoffs)

    Returns dict with dispatchable=True/False and reasons.
    """
    current = now or datetime.now(timezone.utc)
    snapshots = mux.snapshots([agent])
    snapshot = snapshots[0] if snapshots else None

    result: dict[str, Any] = {
        "agent": agent,
        "dispatchable": False,
        "checks": {},
    }

    # Check 1: CMUX presence
    if snapshot is None or snapshot.status == "never-seen":
        result["checks"]["cmux_presence"] = {"pass": False, "reason": "Never seen in CMUX"}
        return result
    result["checks"]["cmux_presence"] = {"pass": True}

    # Check 2: Status is routable
    routable_statuses = {"working", "waiting", "idle", "done", "starting", "accepted"}
    is_routable = snapshot.status in routable_statuses
    result["checks"]["routable_status"] = {
        "pass": is_routable,
        "status": snapshot.status,
        "reason": f"Status '{snapshot.status}' {'is' if is_routable else 'is NOT'} routable",
    }

    # Check 3: Heartbeat within 900s
    if snapshot.updated_at:
        age = (current - snapshot.updated_dt).total_seconds()
        heartbeat_ok = age <= WARM_THRESHOLD
        result["checks"]["heartbeat_fresh"] = {
            "pass": heartbeat_ok,
            "age_seconds": int(age),
            "reason": f"Last event {int(age)}s ago (threshold: {WARM_THRESHOLD}s)",
        }
    else:
        result["checks"]["heartbeat_fresh"] = {"pass": False, "reason": "No timestamp"}

    # Check 4: No unacknowledged blocker
    blockers = [
        e for e in mux.history(sender=agent, kind="task.blocked")
        if not _is_blocker_resolved(mux, e)
    ]
    no_blockers = len(blockers) == 0
    result["checks"]["no_blockers"] = {
        "pass": no_blockers,
        "active_blockers": len(blockers),
        "reason": f"{'No' if no_blockers else len(blockers)} active blocker(s)",
    }

    # Check 5: No overdue unacked task.assign
    pending = mux.pending_handoffs(recipient=agent)
    overdue_assigns = []
    for e in pending:
        if e.kind == "task.assign":
            assign_age = (current - _parse_timestamp(e.timestamp)).total_seconds()
            if assign_age > ACK_DEADLINE:
                overdue_assigns.append({"message_id": e.message_id, "age_seconds": int(assign_age)})
    no_overdue = len(overdue_assigns) == 0
    result["checks"]["ack_discipline"] = {
        "pass": no_overdue,
        "overdue_assigns": overdue_assigns,
        "reason": f"{'No' if no_overdue else len(overdue_assigns)} overdue unacked assignment(s)",
    }

    # Final verdict
    all_pass = all(check["pass"] for check in result["checks"].values())
    result["dispatchable"] = all_pass

    return result


def _is_blocker_resolved(mux: JsonlMux, blocker_event) -> bool:
    """Check if a blocker was followed by a non-blocked status from the same agent."""
    if blocker_event.correlation_id is None:
        return False
    thread = mux.history(correlation_id=blocker_event.correlation_id)
    seen = False
    for e in thread:
        if e.message_id == blocker_event.message_id:
            seen = True
            continue
        if not seen:
            continue
        if e.sender == blocker_event.sender and e.payload.get("status") not in (None, "blocked"):
            return True
    return False


# --- Render ---

def render_health_dashboard(
    mux: JsonlMux,
    agents: list[str],
    *,
    now: datetime | None = None,
) -> str:
    """Render the full CMUX monitor dashboard with health states."""
    current = now or datetime.now(timezone.utc)
    snapshots = mux.snapshots(agents)

    # Compute health for each agent
    health_data = []
    for snap in snapshots:
        has_unacked = len(mux.pending_handoffs(recipient=snap.agent)) > 0
        health = agent_health(snap, now=current, has_unacked_assign=has_unacked)
        health_data.append(health)

    # Group by health state
    healthy = [h for h in health_data if h["health"] == "healthy"]
    warm = [h for h in health_data if h["health"] == "warm"]
    stale = [h for h in health_data if h["health"] == "stale"]
    blocked = [h for h in health_data if h["health"] == "blocked"]
    dark = [h for h in health_data if h["health"] == "dark"]
    dead = [h for h in health_data if h["health"] == "dead"]

    # Pending handoffs
    pending = mux.pending_handoffs()

    lines = [
        "# CMUX Monitor — Health Dashboard",
        "",
        f"Generated: `{_utc_now()}`",
        f"Agents: `{', '.join(agents)}`",
        "",
    ]

    # Health summary bar
    counts = {
        "healthy": len(healthy),
        "warm": len(warm),
        "stale": len(stale),
        "blocked": len(blocked),
        "dark": len(dark),
        "dead": len(dead),
    }
    summary = " | ".join(f"{k}: {v}" for k, v in counts.items() if v > 0)
    lines.append(f"**Status**: {summary}")
    lines.append("")

    # Healthy agents
    lines.append("## Healthy")
    if healthy:
        for h in healthy:
            lines.append(_render_health_line(h))
    else:
        lines.append("- None")

    # Warm agents
    lines.append("")
    lines.append("## Warm")
    if warm:
        for h in warm:
            lines.append(_render_health_line(h))
    else:
        lines.append("- None")

    # Stale agents — ESCALATE
    lines.append("")
    lines.append("## Stale (ESCALATE)")
    if stale:
        for h in stale:
            lines.append(_render_health_line(h))
    else:
        lines.append("- None")

    # Blocked agents — ESCALATE
    lines.append("")
    lines.append("## Blocked (ESCALATE)")
    if blocked:
        for h in blocked:
            lines.append(_render_health_line(h))
    else:
        lines.append("- None")

    # Dead agents
    lines.append("")
    lines.append("## Dead / Dark")
    if dead or dark:
        for h in dead + dark:
            lines.append(_render_health_line(h))
    else:
        lines.append("- None")

    # Pending handoffs
    lines.append("")
    lines.append("## Pending Handoffs")
    if pending:
        for e in pending:
            task = e.payload.get("task") or e.payload.get("claim") or e.kind
            age = int((current - _parse_timestamp(e.timestamp)).total_seconds())
            overdue = " **OVERDUE**" if age > ACK_DEADLINE else ""
            lines.append(
                f"- `{e.sender}` → `{e.recipient}` [{e.kind}] \"{task}\" ({age}s ago){overdue}"
            )
    else:
        lines.append("- None")

    # Direction
    lines.append("")
    lines.append("## Direction")
    if blocked:
        lines.append(f"**UNBLOCK** {', '.join(h['agent'] for h in blocked)} before any new dispatch.")
    elif stale:
        lines.append(f"**RECOVER** stale agents: {', '.join(h['agent'] for h in stale)}. Re-dispatch or mark dead.")
    elif pending:
        lines.append(f"**ACK** {len(pending)} pending handoff(s) — no new work until queue clears.")
    elif dead:
        lines.append(f"**REVIVE** dead agents: {', '.join(h['agent'] for h in dead)}. Capacity wasted.")
    elif warm:
        lines.append(f"**MONITOR** warm agents: {', '.join(h['agent'] for h in warm)}. Heartbeats drifting.")
    else:
        lines.append("All agents healthy. Keep active threads moving.")

    return "\n".join(lines)


def _render_health_line(h: dict) -> str:
    """Render a single agent health line."""
    agent = h["agent"]
    health = h["health"]
    age = h.get("age_seconds")
    status = h.get("status", "?")
    claim = h.get("claim")
    branch = h.get("branch")
    proof = h.get("proof")

    parts = [f"- `{agent}` [{health}]"]
    if age is not None:
        parts.append(f"age={age}s")
    parts.append(f"status={status}")
    if branch:
        parts.append(f"branch={branch}")
    if claim:
        parts.append(f'claim="{claim}"')
    if proof:
        parts.append(f"proof={proof}")
    return " ".join(parts)


# --- CLI ---

def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="CMUX Monitor — agent health dashboard")
    sub = parser.add_subparsers(dest="command")

    # Default: one-shot dashboard
    view_parser = sub.add_parser("view", help="Render health dashboard (default)")
    view_parser.add_argument("--agents", nargs="+", default=KNOWN_AGENTS)
    view_parser.add_argument("--cmux-path", default=str(DEFAULT_CMUX_PATH))

    # Dispatch check
    dispatch_parser = sub.add_parser("dispatch", help="Check if agent is dispatchable")
    dispatch_parser.add_argument("--agent", required=True, help="Agent to check")
    dispatch_parser.add_argument("--cmux-path", default=str(DEFAULT_CMUX_PATH))

    # Watch mode
    watch_parser = sub.add_parser("watch", help="Continuous monitor refresh")
    watch_parser.add_argument("--interval", type=int, default=10, help="Refresh interval in seconds")
    watch_parser.add_argument("--agents", nargs="+", default=KNOWN_AGENTS)
    watch_parser.add_argument("--cmux-path", default=str(DEFAULT_CMUX_PATH))

    args = parser.parse_args(argv)
    command = args.command or "view"

    if command == "view":
        mux = JsonlMux(Path(args.cmux_path))
        print(render_health_dashboard(mux, args.agents))

    elif command == "dispatch":
        mux = JsonlMux(Path(args.cmux_path))
        result = is_dispatchable(mux, args.agent)
        print(json.dumps(result, indent=2))
        sys.exit(0 if result["dispatchable"] else 1)

    elif command == "watch":
        mux = JsonlMux(Path(args.cmux_path))
        try:
            while True:
                print("\033[2J\033[H", end="")  # clear screen
                print(render_health_dashboard(mux, args.agents))
                time.sleep(args.interval)
        except KeyboardInterrupt:
            print("\nMonitor stopped.")


if __name__ == "__main__":
    main()
