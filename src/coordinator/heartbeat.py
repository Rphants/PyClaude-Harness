"""CMUX Heartbeat CLI.

Agents emit heartbeats to prove liveness. Every agent must heartbeat every 300s.
Any agent silent for 900s is STALE.

Usage:
    python -m src.coordinator.heartbeat \
        --sender claude-1 \
        --status working \
        --branch fix/evaluator \
        --claim "unifying metrics" \
        --proof worktree-pass \
        --verification "pytest -q tests/" \
        --next-action "run full suite"

All flags except --sender and --status are optional.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

from .cmux import JsonlMux, DEFAULT_CMUX_PATH

HEARTBEAT_KIND = "task.status"
VALID_STATUSES = {"working", "waiting", "blocked", "done", "idle"}


def emit_heartbeat(
    mux: JsonlMux,
    sender: str,
    status: str,
    *,
    branch: str | None = None,
    claim: str | None = None,
    verification: str | None = None,
    proof: str | None = None,
    next_action: str | None = None,
    correlation_id: str | None = None,
) -> dict:
    """Emit a heartbeat event to CMUX. Returns the envelope dict."""
    if status not in VALID_STATUSES:
        raise ValueError(f"Invalid status '{status}'. Must be one of: {VALID_STATUSES}")

    payload: dict = {"status": status}
    if branch:
        payload["branch"] = branch
    if claim:
        payload["claim"] = claim
    if verification:
        payload["verification"] = verification
    if proof:
        payload["proof"] = proof
    if next_action:
        payload["next_action"] = next_action

    envelope = mux.publish(
        sender=sender,
        recipient="monitor",
        kind=HEARTBEAT_KIND,
        payload=payload,
        correlation_id=correlation_id,
    )
    return envelope.to_dict()


def infer_branch(cwd: str | None = None) -> str | None:
    """Best-effort git branch inference for convenience."""
    try:
        result = subprocess.run(
            ["git", "branch", "--show-current"],
            cwd=cwd,
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
    except Exception:
        return None

    branch = result.stdout.strip()
    return branch or None


def watch_heartbeats(
    mux: JsonlMux,
    sender: str,
    status: str,
    *,
    branch: str | None = None,
    claim: str | None = None,
    verification: str | None = None,
    proof: str | None = None,
    next_action: str | None = None,
    correlation_id: str | None = None,
    interval: int = 300,
    count: int | None = None,
    cwd: str | None = None,
) -> list[dict]:
    """Emit recurring heartbeats. Primarily for long-lived agent panes."""
    if interval <= 0:
        raise ValueError("interval must be > 0")

    emitted: list[dict] = []
    remaining = count
    while remaining is None or remaining > 0:
        resolved_branch = branch or infer_branch(cwd)
        emitted.append(
            emit_heartbeat(
                mux,
                sender=sender,
                status=status,
                branch=resolved_branch,
                claim=claim,
                verification=verification,
                proof=proof,
                next_action=next_action,
                correlation_id=correlation_id,
            )
        )
        if remaining is not None:
            remaining -= 1
            if remaining <= 0:
                break
        time.sleep(interval)
    return emitted


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Emit CMUX heartbeats for an agent.")
    sub = parser.add_subparsers(dest="command")

    def add_shared_args(target) -> None:
        target.add_argument("--sender", required=True, help="Agent callsign (e.g. claude-1)")
        target.add_argument("--status", required=True, choices=sorted(VALID_STATUSES),
                            help="Current agent status")
        target.add_argument("--branch", default=None, help="Current git branch; inferred if omitted")
        target.add_argument("--claim", default=None, help="What the agent is working on")
        target.add_argument("--verification", default=None, help="Verification command")
        target.add_argument("--proof", default=None,
                            choices=["idea", "worktree-pass", "branch-pass", "merged-pass"],
                            help="Proof level")
        target.add_argument("--next-action", default=None, help="What the agent will do next")
        target.add_argument("--correlation-id", default=None, help="Thread correlation ID")
        target.add_argument("--cmux-path", default=str(DEFAULT_CMUX_PATH),
                            help="Path to CMUX events.jsonl")
        target.add_argument("--cwd", default=None, help="Working directory for branch inference")

    send_parser = sub.add_parser("send", help="Emit a single heartbeat")
    add_shared_args(send_parser)

    watch_parser = sub.add_parser("watch", help="Emit recurring heartbeats")
    add_shared_args(watch_parser)
    watch_parser.add_argument("--interval", type=int, default=300,
                              help="Heartbeat interval in seconds (default: 300)")
    watch_parser.add_argument("--count", type=int, default=None,
                              help="Optional number of heartbeats to emit before exiting")

    # Backward-compatible no-subcommand mode.
    parsed_argv = argv if argv is not None else sys.argv[1:]
    if parsed_argv and not parsed_argv[0].startswith("-") and parsed_argv[0] not in {"send", "watch"}:
        parsed_argv = ["send", *parsed_argv]
    elif parsed_argv and parsed_argv[0].startswith("-"):
        parsed_argv = ["send", *parsed_argv]

    args = parser.parse_args(parsed_argv)
    mux = JsonlMux(Path(args.cmux_path))

    if args.command in (None, "send"):
        envelope = emit_heartbeat(
            mux,
            sender=args.sender,
            status=args.status,
            branch=args.branch or infer_branch(args.cwd),
            claim=args.claim,
            verification=args.verification,
            proof=args.proof,
            next_action=args.next_action,
            correlation_id=args.correlation_id,
        )
        print(json.dumps(envelope, indent=2))
        return

    emitted = watch_heartbeats(
        mux,
        sender=args.sender,
        status=args.status,
        branch=args.branch,
        claim=args.claim,
        verification=args.verification,
        proof=args.proof,
        next_action=args.next_action,
        correlation_id=args.correlation_id,
        interval=args.interval,
        count=args.count,
        cwd=args.cwd,
    )
    print(json.dumps(emitted[-1], indent=2))


if __name__ == "__main__":
    main()
