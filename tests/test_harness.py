"""Tests for the harness modules (proposer, evaluator, orchestrator)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from harness.proposer import (
    Proposal,
    ProposalContext,
    analyze_failures,
    generate_proposals,
    load_experiment_history,
)
from harness.evaluator import DetailedEvaluation, run_evaluation
from harness.orchestrator import RESULTS_FILE, apply_proposal, init_results_file


# ---------------------------------------------------------------------------
# proposer — load_experiment_history
# ---------------------------------------------------------------------------

class TestLoadExperimentHistory:
    def test_returns_empty_for_missing_file(self, tmp_path):
        history = load_experiment_history(tmp_path / "nope.tsv")
        assert history == []

    def test_returns_empty_for_header_only(self, tmp_path):
        f = tmp_path / "results.tsv"
        f.write_text("commit\tscore\tstatus\n")
        history = load_experiment_history(f)
        assert history == []

    def test_parses_tsv_rows(self, tmp_path):
        f = tmp_path / "results.tsv"
        f.write_text("commit\tscore\tstatus\nabc123\t0.75\tkeep\n")
        history = load_experiment_history(f)
        assert len(history) == 1
        assert history[0]["commit"] == "abc123"
        assert history[0]["score"] == "0.75"


# ---------------------------------------------------------------------------
# proposer — analyze_failures
# ---------------------------------------------------------------------------

class TestAnalyzeFailures:
    def test_identifies_low_completion(self):
        result = analyze_failures({"task_completion_rate": 0.5})
        assert any("completion" in w.lower() for w in result)

    def test_identifies_high_token_usage(self):
        result = analyze_failures({"avg_token_efficiency": 40000})
        assert any("token" in w.lower() for w in result)

    def test_identifies_poor_accuracy(self):
        result = analyze_failures({"tool_accuracy": 0.7})
        assert any("accuracy" in w.lower() for w in result)

    def test_strong_metrics_suggest_micro_optimizations(self):
        result = analyze_failures({
            "task_completion_rate": 0.95,
            "avg_token_efficiency": 10000,
            "tool_accuracy": 0.95,
        })
        assert any("strong" in w.lower() or "micro" in w.lower() for w in result)


# ---------------------------------------------------------------------------
# proposer — generate_proposals
# ---------------------------------------------------------------------------

class TestGenerateProposals:
    def _make_context(self, **metric_overrides):
        metrics = {
            "task_completion_rate": 0.5,
            "avg_token_efficiency": 30000,
            "tool_accuracy": 0.8,
        }
        metrics.update(metric_overrides)
        return ProposalContext(
            current_config={},
            eval_metrics=metrics,
            experiment_history=[],
            failed_experiments=[],
            codebase_summary="test",
            task_failures=[],
        )

    def test_returns_proposals(self):
        ctx = self._make_context()
        proposals = generate_proposals(ctx)
        assert len(proposals) > 0
        assert all(isinstance(p, Proposal) for p in proposals)

    def test_proposals_sorted_by_priority(self):
        ctx = self._make_context()
        proposals = generate_proposals(ctx)
        priorities = [p.priority for p in proposals]
        assert priorities == sorted(priorities)

    def test_avoids_already_tried(self):
        ctx = self._make_context()
        ctx.experiment_history = [
            {"description": "Add tool usage examples to SYSTEM_PROMPT"},
            {"description": "Add explicit think-then-act structure to prompt"},
        ]
        proposals = generate_proposals(ctx)
        descs = {p.change_description for p in proposals}
        assert "Add tool usage examples to SYSTEM_PROMPT" not in descs
        assert "Add explicit think-then-act structure to prompt" not in descs


# ---------------------------------------------------------------------------
# evaluator — run_evaluation
# ---------------------------------------------------------------------------

class TestRunEvaluation:
    def test_returns_detailed_evaluation(self):
        result = run_evaluation("optimize.json", Path("benchmarks/tasks"))
        assert isinstance(result, DetailedEvaluation)
        assert result.metrics.total_tasks > 0
        assert isinstance(result.task_results, list)

    def test_empty_tasks_dir(self, tmp_path):
        result = run_evaluation("optimize.json", tmp_path)
        assert result.metrics.total_tasks == 0
        assert result.improvement_hints == ["Add benchmark tasks to benchmarks/tasks/"]


# ---------------------------------------------------------------------------
# orchestrator — init_results_file
# ---------------------------------------------------------------------------

class TestInitResultsFile:
    def test_creates_results_file(self, tmp_path, monkeypatch):
        target = tmp_path / "results.tsv"
        monkeypatch.setattr("harness.orchestrator.RESULTS_FILE", target)
        init_results_file()
        assert target.exists()
        content = target.read_text()
        assert "commit" in content
        assert "composite_score" in content

    def test_does_not_overwrite_existing(self, tmp_path, monkeypatch):
        target = tmp_path / "results.tsv"
        target.write_text("existing data\n")
        monkeypatch.setattr("harness.orchestrator.RESULTS_FILE", target)
        init_results_file()
        assert target.read_text() == "existing data\n"


# ---------------------------------------------------------------------------
# orchestrator — apply_proposal
# ---------------------------------------------------------------------------

class TestApplyProposal:
    def test_coerces_numeric_string_for_scalar_sections(self, tmp_path):
        config_path = tmp_path / "optimize.json"
        config_path.write_text('{"token_budget": 30000, "temperature": 0.0, "max_turns": 15}\n')
        proposal = Proposal(
            hypothesis="Reduce tokens",
            change_description="Lower token budget",
            section="TOKEN_BUDGET",
            old_value="30000",
            new_value='"20000"',
            expected_impact="+efficiency",
        )

        assert apply_proposal(proposal, config_path=config_path) is True

        updated = __import__("json").loads(config_path.read_text())
        assert updated["token_budget"] == 20000
        assert isinstance(updated["token_budget"], int)
