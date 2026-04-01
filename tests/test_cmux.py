from __future__ import annotations

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
