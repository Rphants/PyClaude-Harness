"""Tests for the evaluation harness (prepare.py)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

# Ensure project root is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from prepare import (
    BenchmarkTask,
    EvalMetrics,
    TaskResult,
    evaluate_all,
    evaluate_composite,
    evaluate_task,
    load_harness_config,
    load_tasks,
)


# ---------------------------------------------------------------------------
# load_tasks
# ---------------------------------------------------------------------------

class TestLoadTasks:
    def test_loads_from_benchmarks_dir(self):
        tasks = load_tasks(Path("benchmarks/tasks"))
        assert len(tasks) > 0
        assert all(isinstance(t, BenchmarkTask) for t in tasks)

    def test_returns_empty_for_missing_dir(self, tmp_path):
        tasks = load_tasks(tmp_path / "nonexistent")
        assert tasks == []

    def test_skips_invalid_json(self, tmp_path):
        (tmp_path / "bad.json").write_text("NOT JSON")
        tasks = load_tasks(tmp_path)
        assert tasks == []

    def test_skips_missing_required_fields(self, tmp_path):
        (tmp_path / "missing.json").write_text(json.dumps({"name": "x"}))
        tasks = load_tasks(tmp_path)
        assert tasks == []

    def test_parses_all_fields(self, tmp_path):
        task_data = {
            "name": "t1",
            "description": "desc",
            "prompt": "do something",
            "expected_tools": ["Read"],
            "success_criteria": "works",
            "category": "test",
            "difficulty": "easy",
            "max_turns": 3,
        }
        (tmp_path / "task.json").write_text(json.dumps(task_data))
        tasks = load_tasks(tmp_path)
        assert len(tasks) == 1
        t = tasks[0]
        assert t.name == "t1"
        assert t.expected_tools == ["Read"]
        assert t.category == "test"
        assert t.max_turns == 3


# ---------------------------------------------------------------------------
# EvalMetrics
# ---------------------------------------------------------------------------

class TestEvalMetrics:
    def test_composite_score_computed(self):
        m = EvalMetrics(
            task_completion_rate=1.0,
            avg_token_efficiency=0.0,
            tool_accuracy=1.0,
            avg_latency_seconds=0.1,
            total_tasks=8,
            tasks_completed=8,
            tasks_failed=0,
        )
        # 1.0 * 0.50 + (1.0 - 0/50000) * 0.25 + 1.0 * 0.25 = 1.0
        assert m.composite_score == pytest.approx(1.0)

    def test_composite_score_partial(self):
        m = EvalMetrics(
            task_completion_rate=0.5,
            avg_token_efficiency=25_000,
            tool_accuracy=0.5,
            avg_latency_seconds=1.0,
            total_tasks=10,
            tasks_completed=5,
            tasks_failed=5,
        )
        expected = 0.5 * 0.50 + (1.0 - 25000 / 50000) * 0.25 + 0.5 * 0.25
        assert m.composite_score == pytest.approx(expected)

    def test_zero_metrics(self):
        m = EvalMetrics(
            task_completion_rate=0.0,
            avg_token_efficiency=50_000,
            tool_accuracy=0.0,
            avg_latency_seconds=0.0,
            total_tasks=0,
            tasks_completed=0,
            tasks_failed=0,
        )
        assert m.composite_score == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# evaluate_composite
# ---------------------------------------------------------------------------

class TestEvaluateComposite:
    def test_returns_float(self):
        score = evaluate_composite("optimize.json", Path("benchmarks/tasks"))
        assert isinstance(score, float)
        assert 0.0 <= score <= 1.0

    def test_empty_tasks_returns_zero(self, tmp_path):
        score = evaluate_composite("optimize.json", tmp_path)
        assert score == 0.0


# ---------------------------------------------------------------------------
# load_harness_config
# ---------------------------------------------------------------------------

class TestLoadHarnessConfig:
    def test_loads_optimize_py(self):
        config = load_harness_config("optimize.json")
        assert "system_prompt" in config
        assert "tool_definitions" in config
        assert "token_budget" in config
        assert isinstance(config["system_prompt"], str)
        assert len(config["system_prompt"]) > 0

    def test_raises_for_missing_file(self):
        with pytest.raises(FileNotFoundError):
            load_harness_config("nonexistent.json")

    def test_coerces_numeric_string_fields(self, tmp_path):
        config_path = tmp_path / "optimize.json"
        config_path.write_text(json.dumps({
            "system_prompt": "test",
            "tool_definitions": {},
            "context_strategy": {},
            "routing_rules": {},
            "token_budget": "20000",
            "temperature": "0.2",
            "model": "claude-sonnet-4-20250514",
            "max_turns": "12",
        }))

        config = load_harness_config(str(config_path))

        assert config["token_budget"] == 20000
        assert isinstance(config["token_budget"], int)
        assert config["temperature"] == 0.2
        assert isinstance(config["temperature"], float)
        assert config["max_turns"] == 12
        assert isinstance(config["max_turns"], int)


# ---------------------------------------------------------------------------
# evaluate_all
# ---------------------------------------------------------------------------

class TestEvaluateAll:
    def test_empty_tasks_returns_zeros(self):
        config = load_harness_config("optimize.json")
        metrics = evaluate_all([], config)
        assert metrics.total_tasks == 0
        assert metrics.task_completion_rate == 0.0

    def test_returns_eval_metrics(self):
        tasks = load_tasks(Path("benchmarks/tasks"))
        config = load_harness_config("optimize.json")
        metrics = evaluate_all(tasks, config)
        assert isinstance(metrics, EvalMetrics)
        assert metrics.total_tasks == len(tasks)
        assert metrics.tasks_completed + metrics.tasks_failed == metrics.total_tasks
