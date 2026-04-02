from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

DEFAULT_CMUX_PATH = Path(".cmux") / "events.jsonl"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _parse_timestamp(value: str) -> datetime:
    normalized = value.replace("Z", "+00:00")
    return datetime.fromisoformat(normalized)


@dataclass(frozen=True)
class Envelope:
    message_id: str
    timestamp: str
    sender: str
    recipient: str
    kind: str
    payload: dict[str, Any] = field(default_factory=dict)
    correlation_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "message_id": self.message_id,
            "timestamp": self.timestamp,
            "sender": self.sender,
            "recipient": self.recipient,
            "kind": self.kind,
            "payload": self.payload,
            "correlation_id": self.correlation_id,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Envelope":
        return cls(
            message_id=data["message_id"],
            timestamp=data["timestamp"],
            sender=data["sender"],
            recipient=data["recipient"],
            kind=data["kind"],
            payload=dict(data.get("payload", {})),
            correlation_id=data.get("correlation_id"),
        )


@dataclass(frozen=True)
class AgentSnapshot:
    agent: str
    status: str
    updated_at: str
    kind: str
    branch: str | None = None
    state: str | None = None
    claim: str | None = None
    verification: str | None = None
    proof: str | None = None
    recipient: str | None = None
    correlation_id: str | None = None
    raw_payload: dict[str, Any] = field(default_factory=dict)

    @property
    def updated_dt(self) -> datetime:
        return _parse_timestamp(self.updated_at)


class JsonlMux:
    def __init__(self, path: Path | str = DEFAULT_CMUX_PATH):
        self.path = Path(path)

    def publish(
        self,
        sender: str,
        recipient: str,
        kind: str,
        payload: dict[str, Any] | None = None,
        *,
        correlation_id: str | None = None,
    ) -> Envelope:
        envelope = Envelope(
            message_id=uuid4().hex,
            timestamp=_utc_now(),
            sender=sender,
            recipient=recipient,
            kind=kind,
            payload=dict(payload or {}),
            correlation_id=correlation_id,
        )
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(envelope.to_dict(), sort_keys=True) + "\n")
        return envelope

    def history(
        self,
        *,
        sender: str | None = None,
        recipient: str | None = None,
        kind: str | None = None,
        correlation_id: str | None = None,
    ) -> tuple[Envelope, ...]:
        if not self.path.exists():
            return ()

        events: list[Envelope] = []
        with self.path.open(encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                envelope = Envelope.from_dict(json.loads(line))
                if sender is not None and envelope.sender != sender:
                    continue
                if recipient is not None and envelope.recipient != recipient:
                    continue
                if kind is not None and envelope.kind != kind:
                    continue
                if correlation_id is not None and envelope.correlation_id != correlation_id:
                    continue
                events.append(envelope)
        return tuple(events)

    def inbox(self, recipient: str, *, since_id: str | None = None) -> tuple[Envelope, ...]:
        events = self.history(recipient=recipient)
        if since_id is None:
            return events

        filtered: list[Envelope] = []
        seen = False
        for envelope in events:
            if seen:
                filtered.append(envelope)
            elif envelope.message_id == since_id:
                seen = True
        return tuple(filtered)

    def latest(self, recipient: str) -> Envelope | None:
        events = self.inbox(recipient)
        return events[-1] if events else None

    def render_thread(self, correlation_id: str) -> str:
        events = self.history(correlation_id=correlation_id)
        if not events:
            return f"# CMUX Thread\n\nNo events for correlation_id `{correlation_id}`."

        lines = ["# CMUX Thread", "", f"Correlation: `{correlation_id}`", ""]
        for envelope in events:
            lines.append(
                f"- `{envelope.timestamp}` {envelope.sender} -> {envelope.recipient} "
                f"[{envelope.kind}] {json.dumps(envelope.payload, sort_keys=True)}"
            )
        return "\n".join(lines)

    def snapshots(self, agents: list[str] | tuple[str, ...] | None = None) -> tuple[AgentSnapshot, ...]:
        latest_by_agent: dict[str, Envelope] = {}
        for envelope in self.history():
            current = latest_by_agent.get(envelope.sender)
            if current is None or _parse_timestamp(envelope.timestamp) >= _parse_timestamp(current.timestamp):
                latest_by_agent[envelope.sender] = envelope

        target_agents = list(agents) if agents is not None else sorted(latest_by_agent)
        snapshots: list[AgentSnapshot] = []
        for agent in target_agents:
            envelope = latest_by_agent.get(agent)
            if envelope is None:
                snapshots.append(
                    AgentSnapshot(
                        agent=agent,
                        status="never-seen",
                        updated_at="",
                        kind="none",
                    )
                )
                continue
            snapshots.append(self._snapshot_from_envelope(envelope))
        return tuple(snapshots)

    def idle_agents(
        self,
        agents: list[str] | tuple[str, ...],
        *,
        idle_seconds: int = 900,
        now: datetime | None = None,
    ) -> tuple[AgentSnapshot, ...]:
        current_time = now or datetime.now(timezone.utc)
        idle: list[AgentSnapshot] = []
        for snapshot in self.snapshots(agents):
            if snapshot.status == "never-seen":
                idle.append(snapshot)
                continue
            if snapshot.updated_at == "":
                idle.append(snapshot)
                continue
            age_seconds = (current_time - snapshot.updated_dt).total_seconds()
            if snapshot.status in {"idle", "waiting", "done", "verify"} or age_seconds >= idle_seconds:
                idle.append(snapshot)
        return tuple(idle)

    def pending_handoffs(self, recipient: str | None = None) -> tuple[Envelope, ...]:
        pending_kinds = {"task.assign", "task.handoff", "task.verify"}
        events = [event for event in self.history() if event.kind in pending_kinds]
        pending: list[Envelope] = []
        for event in events:
            if recipient is not None and event.recipient != recipient:
                continue
            if self._is_resolved(event):
                continue
            pending.append(event)
        return tuple(pending)

    def render_monitor_view(
        self,
        agents: list[str] | tuple[str, ...],
        *,
        idle_seconds: int = 900,
        now: datetime | None = None,
    ) -> str:
        current_time = now or datetime.now(timezone.utc)
        snapshots = self.snapshots(agents)
        blocked = [snap for snap in snapshots if snap.status == "blocked"]
        active = [snap for snap in snapshots if snap.status in {"starting", "working", "in_progress", "handoff"}]
        idle = list(self.idle_agents(list(agents), idle_seconds=idle_seconds, now=current_time))
        pending = self.pending_handoffs()

        lines = [
            "# CMUX Monitor",
            "",
            f"Generated: `{_utc_now()}`",
            f"Tracked agents: `{', '.join(agents)}`",
            "",
            "## Active",
        ]
        if active:
            for snapshot in active:
                lines.append(self._render_snapshot_line(snapshot, current_time))
        else:
            lines.append("- No active agents.")

        lines.append("")
        lines.append("## Blocked")
        if blocked:
            for snapshot in blocked:
                lines.append(self._render_snapshot_line(snapshot, current_time))
        else:
            lines.append("- No blocked agents.")

        lines.append("")
        lines.append("## Idle")
        if idle:
            for snapshot in idle:
                lines.append(self._render_snapshot_line(snapshot, current_time))
        else:
            lines.append("- No idle agents.")

        lines.append("")
        lines.append("## Pending Handoffs")
        if pending:
            for envelope in pending:
                task = envelope.payload.get("task") or envelope.payload.get("claim") or envelope.kind
                lines.append(
                    f"- `{envelope.timestamp}` {envelope.sender} -> {envelope.recipient} "
                    f"[{envelope.kind}] {task}"
                )
        else:
            lines.append("- No pending handoffs.")

        lines.append("")
        lines.append("## Direction")
        if blocked:
            lines.append("- Highest priority: unblock blocked agents before assigning new work.")
        elif pending:
            lines.append("- Highest priority: acknowledge or execute pending handoffs.")
        elif idle and active:
            lines.append("- Highest priority: route idle agents to support active threads.")
        elif idle:
            lines.append("- Highest priority: dispatch new work; capacity is available.")
        else:
            lines.append("- Highest priority: keep active threads moving and update proof levels.")

        return "\n".join(lines)

    def _snapshot_from_envelope(self, envelope: Envelope) -> AgentSnapshot:
        payload = envelope.payload
        status = str(
            payload.get("status")
            or payload.get("state")
            or self._status_from_kind(envelope.kind)
        ).lower()
        return AgentSnapshot(
            agent=envelope.sender,
            status=status,
            updated_at=envelope.timestamp,
            kind=envelope.kind,
            branch=self._maybe_string(payload.get("branch")),
            state=self._maybe_string(payload.get("state")),
            claim=self._maybe_string(payload.get("claim") or payload.get("task") or payload.get("summary")),
            verification=self._maybe_string(payload.get("verification")),
            proof=self._maybe_string(payload.get("proof")),
            recipient=envelope.recipient,
            correlation_id=envelope.correlation_id,
            raw_payload=dict(payload),
        )

    def _is_resolved(self, envelope: Envelope) -> bool:
        return self._is_acknowledged(envelope) or self._is_cancelled(envelope)

    def _is_acknowledged(self, envelope: Envelope) -> bool:
        if envelope.correlation_id is None:
            return False
        thread = self.history(correlation_id=envelope.correlation_id)
        seen = False
        for event in thread:
            if event.message_id == envelope.message_id:
                seen = True
                continue
            if not seen:
                continue
            if event.sender == envelope.recipient:
                return True
        return False

    def _is_cancelled(self, envelope: Envelope) -> bool:
        if envelope.correlation_id is None:
            return False
        thread = self.history(correlation_id=envelope.correlation_id)
        for event in thread:
            if event.kind != "task.cancel":
                continue
            cancel_of = event.payload.get("cancel_of")
            if cancel_of == envelope.message_id:
                return True
        return False

    def _render_snapshot_line(self, snapshot: AgentSnapshot, now: datetime) -> str:
        if snapshot.status == "never-seen":
            return f"- `{snapshot.agent}` never seen in CMUX."
        age_seconds = int((now - snapshot.updated_dt).total_seconds()) if snapshot.updated_at else 0
        branch = f" | branch={snapshot.branch}" if snapshot.branch else ""
        claim = f" | claim={snapshot.claim}" if snapshot.claim else ""
        proof = f" | proof={snapshot.proof}" if snapshot.proof else ""
        return (
            f"- `{snapshot.agent}` status={snapshot.status} age={age_seconds}s "
            f"kind={snapshot.kind}{branch}{claim}{proof}"
        )

    def _status_from_kind(self, kind: str) -> str:
        if kind == "task.assign":
            return "starting"
        if kind == "task.handoff":
            return "handoff"
        if kind == "task.verify":
            return "verify"
        if kind == "task.blocked":
            return "blocked"
        if kind == "task.done":
            return "done"
        return kind.rsplit(".", 1)[-1]

    def _maybe_string(self, value: Any) -> str | None:
        if value is None:
            return None
        return str(value)


__all__ = ["AgentSnapshot", "DEFAULT_CMUX_PATH", "Envelope", "JsonlMux"]
