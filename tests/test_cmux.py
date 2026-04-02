from __future__ import annotations

from datetime import datetime, timezone

from src.coordinator import JsonlMux


def test_publish_and_read_history(tmp_path):
    mux = JsonlMux(tmp_path / "events.jsonl")

    first = mux.publish(
        "cowork",
        "codex",
        "task.assign",
        {"task": "review evaluator"},
        correlation_id="thread-1",
    )
    second = mux.publish(
        "codex",
        "cowork",
        "task.status",
        {"state": "in_progress"},
        correlation_id="thread-1",
    )

    history = mux.history(correlation_id="thread-1")

    assert [event.message_id for event in history] == [first.message_id, second.message_id]
    assert history[0].payload["task"] == "review evaluator"
    assert history[1].payload["state"] == "in_progress"


def test_inbox_since_id_returns_newer_messages_only(tmp_path):
    mux = JsonlMux(tmp_path / "events.jsonl")

    first = mux.publish("cowork", "claude", "task.assign", {"task": "inspect repo"})
    mux.publish("cowork", "claude", "task.assign", {"task": "write review"})
    mux.publish("codex", "cowork", "task.status", {"state": "done"})

    inbox = mux.inbox("claude", since_id=first.message_id)

    assert len(inbox) == 1
    assert inbox[0].payload["task"] == "write review"


def test_render_thread_is_human_readable(tmp_path):
    mux = JsonlMux(tmp_path / "events.jsonl")
    mux.publish("cowork", "codex", "task.assign", {"task": "build cmux"}, correlation_id="thread-9")
    mux.publish("codex", "cowork", "task.status", {"state": "done"}, correlation_id="thread-9")

    rendered = mux.render_thread("thread-9")

    assert "CMUX Thread" in rendered
    assert "cowork -> codex" in rendered
    assert "codex -> cowork" in rendered
    assert '"state": "done"' in rendered


def test_snapshots_and_idle_detection(tmp_path):
    mux = JsonlMux(tmp_path / "events.jsonl")
    mux.publish(
        "claude-1",
        "cowork",
        "task.status",
        {
            "status": "working",
            "branch": "fix/evaluator",
            "claim": "unifying metrics",
            "proof": "worktree-pass",
        },
    )
    mux.publish(
        "codex-1",
        "cowork",
        "task.status",
        {
            "status": "done",
            "branch": "fix/evaluator",
            "claim": "verified metric path",
            "verification": "pytest -q",
            "proof": "branch-pass",
        },
    )

    snapshots = mux.snapshots(["claude-1", "codex-1", "monitor"])

    assert snapshots[0].status == "working"
    assert snapshots[0].branch == "fix/evaluator"
    assert snapshots[1].verification == "pytest -q"
    assert snapshots[2].status == "never-seen"

    idle = mux.idle_agents(
        ["claude-1", "codex-1", "monitor"],
        now=datetime(2030, 1, 1, tzinfo=timezone.utc),
    )
    assert {snapshot.agent for snapshot in idle} == {"claude-1", "codex-1", "monitor"}


def test_pending_handoffs_and_monitor_view(tmp_path):
    mux = JsonlMux(tmp_path / "events.jsonl")
    mux.publish(
        "cowork",
        "claude-1",
        "task.assign",
        {"task": "fix orchestrator", "branch": "fix/orchestrator"},
        correlation_id="thread-a",
    )
    mux.publish(
        "cowork",
        "codex-1",
        "task.verify",
        {"task": "review evaluator", "branch": "fix/evaluator"},
        correlation_id="thread-b",
    )
    mux.publish(
        "claude-1",
        "cowork",
        "task.blocked",
        {"status": "blocked", "claim": "waiting on failing repro", "proof": "worktree-pass"},
        correlation_id="thread-a",
    )

    pending = mux.pending_handoffs()
    assert len(pending) == 1
    assert pending[0].recipient == "codex-1"

    rendered = mux.render_monitor_view(
        ["cowork", "claude-1", "codex-1"],
        now=datetime(2030, 1, 1, tzinfo=timezone.utc),
    )

    assert "CMUX Monitor" in rendered
    assert "Blocked" in rendered
    assert "claude-1" in rendered
    assert "Pending Handoffs" in rendered
    assert "codex-1" in rendered
    assert "Highest priority: unblock blocked agents" in rendered


def test_pending_handoffs_ignore_cancelled_events(tmp_path):
    mux = JsonlMux(tmp_path / "events.jsonl")
    assign = mux.publish(
        "cowork",
        "claude-1",
        "task.assign",
        {"task": "deploy"},
        correlation_id="thread-cancel",
    )
    mux.publish(
        "codex-1",
        "all",
        "task.cancel",
        {"cancel_of": assign.message_id, "reason": "outage superseded assignment"},
        correlation_id="thread-cancel",
    )

    pending = mux.pending_handoffs()

    assert pending == ()
