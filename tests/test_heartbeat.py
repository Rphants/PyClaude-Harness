"""Tests for CMUX heartbeat, ACK, and monitor systems."""

from __future__ import annotations

import json
import subprocess
from datetime import datetime, timedelta, timezone

from src.coordinator import JsonlMux
from src.coordinator.heartbeat import emit_heartbeat, infer_branch, VALID_STATUSES, watch_heartbeats
from src.coordinator.ack import ack_assignment, find_unacked_assignments
from src.coordinator.monitor import (
    agent_health,
    is_dispatchable,
    render_health_dashboard,
    HEALTHY_THRESHOLD,
    WARM_THRESHOLD,
    ACK_DEADLINE,
)


# --- Heartbeat Tests ---


def test_emit_heartbeat_writes_to_cmux(tmp_path):
    mux = JsonlMux(tmp_path / "events.jsonl")
    result = emit_heartbeat(
        mux,
        sender="claude-1",
        status="working",
        branch="fix/evaluator",
        claim="unifying metrics",
        proof="worktree-pass",
    )

    assert result["sender"] == "claude-1"
    assert result["recipient"] == "monitor"
    assert result["kind"] == "task.status"
    assert result["payload"]["status"] == "working"
    assert result["payload"]["branch"] == "fix/evaluator"
    assert result["payload"]["claim"] == "unifying metrics"
    assert result["payload"]["proof"] == "worktree-pass"


def test_heartbeat_validates_status(tmp_path):
    mux = JsonlMux(tmp_path / "events.jsonl")
    try:
        emit_heartbeat(mux, sender="claude-1", status="invalid-status")
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "invalid-status" in str(e)


def test_all_valid_statuses_accepted(tmp_path):
    mux = JsonlMux(tmp_path / "events.jsonl")
    for status in VALID_STATUSES:
        result = emit_heartbeat(mux, sender="claude-1", status=status)
        assert result["payload"]["status"] == status


def test_heartbeat_optional_fields(tmp_path):
    mux = JsonlMux(tmp_path / "events.jsonl")
    result = emit_heartbeat(mux, sender="claude-1", status="idle")

    # Only status should be in payload
    assert result["payload"] == {"status": "idle"}


def test_heartbeat_next_action(tmp_path):
    mux = JsonlMux(tmp_path / "events.jsonl")
    result = emit_heartbeat(
        mux,
        sender="codex-1",
        status="waiting",
        next_action="run full test suite",
    )
    assert result["payload"]["next_action"] == "run full test suite"


def test_watch_heartbeats_emits_multiple_events(tmp_path):
    mux = JsonlMux(tmp_path / "events.jsonl")

    emitted = watch_heartbeats(
        mux,
        sender="claude-1",
        status="working",
        claim="deploy loop",
        interval=0.001,
        count=2,
    )

    assert len(emitted) == 2
    history = mux.history(sender="claude-1", kind="task.status")
    assert len(history) == 2
    assert history[-1].payload["claim"] == "deploy loop"


def test_infer_branch_from_git_repo(tmp_path):
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "checkout", "-b", "feat/test-branch"], cwd=tmp_path, check=True, capture_output=True)

    assert infer_branch(str(tmp_path)) == "feat/test-branch"


# --- ACK Tests ---


def test_ack_assignment_writes_to_cmux(tmp_path):
    mux = JsonlMux(tmp_path / "events.jsonl")

    # First, create a task.assign
    assign = mux.publish(
        "cowork", "claude-1", "task.assign",
        {"task": "deploy to prod"},
        correlation_id="thread-1",
    )

    # ACK it
    result = ack_assignment(
        mux,
        sender="claude-1",
        message_id=assign.message_id,
        correlation_id="thread-1",
        status="accepted",
    )

    assert result["sender"] == "claude-1"
    assert result["recipient"] == "cowork"
    assert result["kind"] == "task.ack"
    assert result["payload"]["status"] == "accepted"
    assert result["payload"]["ack_of"] == assign.message_id


def test_ack_rejected_requires_no_special_handling(tmp_path):
    mux = JsonlMux(tmp_path / "events.jsonl")
    result = ack_assignment(
        mux,
        sender="claude-1",
        message_id="fake-id",
        correlation_id="thread-1",
        status="rejected",
        reason="missing context file",
    )
    assert result["payload"]["status"] == "rejected"
    assert result["payload"]["reason"] == "missing context file"


def test_find_unacked_assignments(tmp_path):
    mux = JsonlMux(tmp_path / "events.jsonl")

    # Assign 2 tasks
    mux.publish(
        "cowork", "claude-1", "task.assign",
        {"task": "deploy"},
        correlation_id="t1",
    )
    assign2 = mux.publish(
        "cowork", "claude-1", "task.assign",
        {"task": "review PR"},
        correlation_id="t2",
    )

    # ACK only the second one
    mux.publish(
        "claude-1", "cowork", "task.ack",
        {"status": "accepted", "ack_of": assign2.message_id},
        correlation_id="t2",
    )

    unacked = find_unacked_assignments(mux, "claude-1")
    assert len(unacked) == 1
    assert unacked[0]["task"] == "deploy"


# --- Health State Tests ---


def test_healthy_agent(tmp_path):
    mux = JsonlMux(tmp_path / "events.jsonl")
    now = datetime(2026, 4, 1, 12, 0, 0, tzinfo=timezone.utc)

    emit_heartbeat(mux, sender="claude-1", status="working", branch="fix/hero")

    snapshots = mux.snapshots(["claude-1"])
    health = agent_health(snapshots[0], now=now, has_unacked_assign=False)

    assert health["health"] == "healthy"
    assert health["agent"] == "claude-1"


def test_stale_agent(tmp_path):
    mux = JsonlMux(tmp_path / "events.jsonl")
    emit_heartbeat(mux, sender="claude-1", status="working")

    # Fast forward 20 minutes
    far_future = datetime.now(timezone.utc) + timedelta(seconds=1200)
    snapshots = mux.snapshots(["claude-1"])
    health = agent_health(snapshots[0], now=far_future)

    assert health["health"] == "stale"


def test_blocked_agent(tmp_path):
    mux = JsonlMux(tmp_path / "events.jsonl")
    emit_heartbeat(mux, sender="claude-1", status="blocked", claim="RunPod worker down")

    snapshots = mux.snapshots(["claude-1"])
    health = agent_health(snapshots[0], now=datetime.now(timezone.utc))

    assert health["health"] == "blocked"
    assert "RunPod worker down" in health["reason"]


def test_dead_agent(tmp_path):
    mux = JsonlMux(tmp_path / "events.jsonl")
    # Never emit anything
    snapshots = mux.snapshots(["ghost-agent"])
    health = agent_health(snapshots[0])

    assert health["health"] == "dead"


def test_warm_agent_with_unacked(tmp_path):
    mux = JsonlMux(tmp_path / "events.jsonl")
    emit_heartbeat(mux, sender="claude-1", status="working")

    snapshots = mux.snapshots(["claude-1"])
    health = agent_health(snapshots[0], now=datetime.now(timezone.utc), has_unacked_assign=True)

    assert health["health"] == "warm"
    assert "unacked" in health["reason"]


# --- Dispatch Health Check Tests ---


def test_dispatchable_healthy_agent(tmp_path):
    mux = JsonlMux(tmp_path / "events.jsonl")
    emit_heartbeat(mux, sender="claude-1", status="idle")

    result = is_dispatchable(mux, "claude-1")

    assert result["dispatchable"] is True
    assert all(check["pass"] for check in result["checks"].values())


def test_not_dispatchable_dead_agent(tmp_path):
    mux = JsonlMux(tmp_path / "events.jsonl")

    result = is_dispatchable(mux, "ghost-agent")

    assert result["dispatchable"] is False
    assert result["checks"]["cmux_presence"]["pass"] is False


def test_not_dispatchable_stale_agent(tmp_path):
    mux = JsonlMux(tmp_path / "events.jsonl")
    emit_heartbeat(mux, sender="claude-1", status="working")

    far_future = datetime.now(timezone.utc) + timedelta(seconds=1200)
    result = is_dispatchable(mux, "claude-1", now=far_future)

    assert result["dispatchable"] is False
    assert result["checks"]["heartbeat_fresh"]["pass"] is False


def test_not_dispatchable_blocked_agent(tmp_path):
    mux = JsonlMux(tmp_path / "events.jsonl")

    # Emit a blocker with correlation
    mux.publish(
        "claude-1", "cowork", "task.blocked",
        {"status": "blocked", "claim": "API down"},
        correlation_id="thread-block",
    )

    result = is_dispatchable(mux, "claude-1")

    assert result["dispatchable"] is False


def test_not_dispatchable_overdue_ack(tmp_path):
    mux = JsonlMux(tmp_path / "events.jsonl")

    # Agent emits a heartbeat first (so it exists in CMUX)
    emit_heartbeat(mux, sender="claude-1", status="idle")

    # Assign a task
    mux.publish(
        "cowork", "claude-1", "task.assign",
        {"task": "deploy"},
        correlation_id="thread-assign",
    )

    # Wait past ACK deadline
    future = datetime.now(timezone.utc) + timedelta(seconds=ACK_DEADLINE + 10)
    result = is_dispatchable(mux, "claude-1", now=future)

    assert result["dispatchable"] is False
    assert result["checks"]["ack_discipline"]["pass"] is False


# --- Dashboard Render Tests ---


def test_render_health_dashboard(tmp_path):
    mux = JsonlMux(tmp_path / "events.jsonl")
    now = datetime.now(timezone.utc)

    emit_heartbeat(mux, sender="claude-1", status="working", branch="fix/hero")
    emit_heartbeat(mux, sender="codex-1", status="blocked", claim="RunPod down")

    dashboard = render_health_dashboard(mux, ["claude-1", "codex-1", "monitor"], now=now)

    assert "CMUX Monitor" in dashboard
    assert "Healthy" in dashboard
    assert "claude-1" in dashboard
    assert "Blocked (ESCALATE)" in dashboard
    assert "codex-1" in dashboard
    assert "Dead / Dark" in dashboard
    assert "monitor" in dashboard
    assert "Direction" in dashboard


def test_dashboard_direction_prioritizes_blocked(tmp_path):
    mux = JsonlMux(tmp_path / "events.jsonl")
    emit_heartbeat(mux, sender="claude-1", status="blocked", claim="API down")
    emit_heartbeat(mux, sender="codex-1", status="working")

    dashboard = render_health_dashboard(mux, ["claude-1", "codex-1"])

    assert "UNBLOCK" in dashboard
