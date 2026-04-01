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


__all__ = ["DEFAULT_CMUX_PATH", "Envelope", "JsonlMux"]
