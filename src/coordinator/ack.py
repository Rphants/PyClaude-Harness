"""CMUX ACK Helper.

Agents must ACK task.assign events within 2 minutes or be considered non-routable.

Usage:
    python -m src.coordinator.ack \
        --sender claude-1 \
        --message-id <id-of-task.assign> \
        --correlation-id <thread-id> \
        --status accepted

    python -m src.coordinator.ack \
        --sender claude-1 \
        --message-id <id> \
        --correlation-id <thread-id> \
        --status rejected \
        --reason "missing context file"
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .cmux import JsonlMux, DEFAULT_CMUX_PATH

ACK_KIND = "task.ack"
VALID_ACK_STATUSES = {"accepted", "rejected", "blocked"}


def ack_assignment(
    mux: JsonlMux,
    sender: str,
    message_id: str,
    correlation_id: str,
    *,
    status: str = "accepted",
    reason: str | None = None,
) -> dict:
    """ACK a task.assign event. Returns the envelope dict."""
    if status not in VALID_ACK_STATUSES:
        raise ValueError(f"Invalid ACK status '{status}'. Must be one of: {VALID_ACK_STATUSES}")

    payload: dict = {
        "status": status,
        "ack_of": message_id,
    }
    if reason:
        payload["reason"] = reason

    envelope = mux.publish(
        sender=sender,
        recipient="cowork",
        kind=ACK_KIND,
        payload=payload,
        correlation_id=correlation_id,
    )
    return envelope.to_dict()


def find_unacked_assignments(mux: JsonlMux, agent: str) -> list[dict]:
    """Find all task.assign events sent TO this agent that have no ACK."""
    pending = mux.pending_handoffs(recipient=agent)
    return [
        {
            "message_id": e.message_id,
            "sender": e.sender,
            "correlation_id": e.correlation_id,
            "task": e.payload.get("task") or e.payload.get("claim") or "unknown",
            "timestamp": e.timestamp,
        }
        for e in pending
        if e.kind == "task.assign"
    ]


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="ACK a CMUX task assignment.")
    sub = parser.add_subparsers(dest="command", help="Sub-command")

    # ack subcommand
    ack_parser = sub.add_parser("send", help="Send an ACK for a task.assign")
    ack_parser.add_argument("--sender", required=True, help="Agent callsign")
    ack_parser.add_argument("--message-id", required=True, help="message_id of the task.assign to ACK")
    ack_parser.add_argument("--correlation-id", required=True, help="Thread correlation ID")
    ack_parser.add_argument("--status", default="accepted", choices=sorted(VALID_ACK_STATUSES))
    ack_parser.add_argument("--reason", default=None, help="Reason (required for rejected/blocked)")
    ack_parser.add_argument("--cmux-path", default=str(DEFAULT_CMUX_PATH))

    # list subcommand
    list_parser = sub.add_parser("list", help="List unacked assignments for an agent")
    list_parser.add_argument("--agent", required=True, help="Agent callsign")
    list_parser.add_argument("--cmux-path", default=str(DEFAULT_CMUX_PATH))

    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        sys.exit(1)

    mux = JsonlMux(Path(args.cmux_path))

    if args.command == "send":
        envelope = ack_assignment(
            mux,
            sender=args.sender,
            message_id=args.message_id,
            correlation_id=args.correlation_id,
            status=args.status,
            reason=args.reason,
        )
        print(json.dumps(envelope, indent=2))

    elif args.command == "list":
        unacked = find_unacked_assignments(mux, args.agent)
        if not unacked:
            print(f"No unacked assignments for {args.agent}")
        else:
            print(json.dumps(unacked, indent=2))


if __name__ == "__main__":
    main()
