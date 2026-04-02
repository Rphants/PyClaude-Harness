"""
Meta-Harness Evaluator.

Wraps prepare.py evaluation and provides richer diagnostics for the proposer.
Runs benchmark tasks, collects per-task results, identifies failure patterns.
"""

from __future__ import annotations

import json
import statistics
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

# Import from the fixed evaluation harness
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from prepare import (
    EVAL_TASKS_DIR,
    EvalMetrics,
    TaskResult,
    evaluate_all,
    evaluate_task,
    load_harness_config,
    load_tasks,
)


@dataclass
class DetailedEvaluation:
    """Rich evaluation results with per-task diagnostics."""
    metrics: EvalMetrics
    task_results: list[TaskResult]
    failure_analysis: list[dict[str, Any]]
    improvement_hints: list[str]


def run_evaluation(config_path: str = "optimize.json",
                   tasks_dir: Path = EVAL_TASKS_DIR) -> DetailedEvaluation:
    """Run full evaluation with detailed diagnostics."""
    config = load_harness_config(config_path)
    tasks = load_tasks(tasks_dir)

    if not tasks:
        empty_metrics = EvalMetrics(
            task_completion_rate=0.0,
            avg_token_efficiency=0.0,
            tool_accuracy=0.0,
            avg_latency_seconds=0.0,
            total_tasks=0,
            tasks_completed=0,
            tasks_failed=0,
        )
        return DetailedEvaluation(
            metrics=empty_metrics,
            task_results=[],
            failure_analysis=[],
            improvement_hints=["Add benchmark tasks to benchmarks/tasks/"],
        )

    # Run each task individually for per-task diagnostics
    task_results = []
    for task in tasks:
        result = evaluate_task(task, config)
        task_results.append(result)

    # Compute metrics from already-collected results (avoid evaluating twice)
    # Pass tasks so F1 recall denominator uses expected_tools correctly
    metrics = _metrics_from_results(task_results, tasks=tasks)

    # Analyze failures
    failure_analysis = []
    for task, result in zip(tasks, task_results):
        if not result.completed:
            failure_analysis.append({
                "task": task.name,
                "category": task.category,
                "difficulty": task.difficulty,
                "expected_tools": task.expected_tools,
                "tools_called": result.tools_called,
                "tokens_used": result.tokens_used,
                "turns_used": result.turns_used,
                "error": result.error,
            })

    # Generate improvement hints
    hints = _generate_hints(metrics, failure_analysis, config)

    return DetailedEvaluation(
        metrics=metrics,
        task_results=task_results,
        failure_analysis=failure_analysis,
        improvement_hints=hints,
    )


def _metrics_from_results(results: list[TaskResult],
                          tasks: list[Any] | None = None) -> EvalMetrics:
    """Compute EvalMetrics from already-collected TaskResults (no re-evaluation).

    Uses the same F1 (harmonic mean of precision + recall) formula as
    prepare.evaluate_all() to avoid score disagreement between evaluator
    and ground truth.
    """
    if not results:
        return EvalMetrics(
            task_completion_rate=0.0, avg_token_efficiency=0.0,
            tool_accuracy=0.0, avg_latency_seconds=0.0,
            total_tasks=0, tasks_completed=0, tasks_failed=0,
        )
    completed = [r for r in results if r.completed]
    failed = [r for r in results if not r.completed]
    task_completion_rate = len(completed) / len(results)
    avg_tokens = statistics.mean(r.tokens_used for r in results)

    # Tool accuracy: F1 (harmonic mean of precision and recall)
    # — matches prepare.evaluate_all() exactly
    total_calls = sum(len(r.tools_called) for r in results)
    unnecessary_calls = sum(len(r.unnecessary_tools) for r in results)
    correct_calls = total_calls - unnecessary_calls

    # If tasks are provided, use their expected_tools for recall denominator
    if tasks is not None:
        total_expected = sum(
            len(t.expected_tools) if hasattr(t, 'expected_tools') else 0
            for t in tasks
        )
    else:
        # Fallback: approximate from tools_called (assume all non-unnecessary were expected)
        total_expected = correct_calls

    if total_expected == 0 and total_calls == 0:
        tool_accuracy = 1.0
    else:
        precision = correct_calls / max(total_calls, 1)
        recall = correct_calls / max(total_expected, 1)
        if precision + recall > 0:
            tool_accuracy = 2 * precision * recall / (precision + recall)
        else:
            tool_accuracy = 0.0

    avg_latency = statistics.mean(r.wall_seconds for r in results)
    return EvalMetrics(
        task_completion_rate=task_completion_rate,
        avg_token_efficiency=avg_tokens,
        tool_accuracy=tool_accuracy,
        avg_latency_seconds=avg_latency,
        total_tasks=len(results),
        tasks_completed=len(completed),
        tasks_failed=len(failed),
    )


def _generate_hints(metrics: EvalMetrics,
                    failures: list[dict[str, Any]],
                    config: dict[str, Any]) -> list[str]:
    """Generate actionable improvement hints from evaluation results."""
    hints = []

    # Completion hints
    if metrics.task_completion_rate < 0.9:
        failed_categories = [f.get("category", "unknown") for f in failures]
        category_counts = {}
        for cat in failed_categories:
            category_counts[cat] = category_counts.get(cat, 0) + 1
        worst_category = max(category_counts, key=category_counts.get) if category_counts else None
        if worst_category:
            hints.append(f"Worst category: '{worst_category}' — add specific routing/prompt guidance")

    # Token efficiency hints
    if metrics.avg_token_efficiency > 20_000:
        strategy = config.get("context_strategy", {})
        if not strategy.get("compaction_enabled"):
            hints.append("Enable context compaction to reduce token usage")
        if not strategy.get("relevance_filtering"):
            hints.append("Enable relevance filtering to reduce noise in context")
        threshold = strategy.get("compaction_threshold_tokens", 20_000)
        if threshold > 15_000:
            hints.append(f"Lower compaction threshold from {threshold} to ~15000")

    # Tool accuracy hints
    if metrics.tool_accuracy < 0.9:
        hints.append("Review ROUTING_RULES — some queries may be triggering wrong tools")
        hints.append("Add negative patterns to routing rules to prevent false matches")

    # General hints
    if metrics.composite_score > 0.8:
        hints.append("High baseline — try micro-optimizations or ablation studies")
    elif metrics.composite_score < 0.4:
        hints.append("Low baseline — focus on system prompt clarity and tool coverage")

    return hints


def compare_evaluations(before: DetailedEvaluation,
                        after: DetailedEvaluation) -> dict[str, Any]:
    """Compare two evaluations and summarize the delta."""
    return {
        "composite_delta": after.metrics.composite_score - before.metrics.composite_score,
        "completion_delta": after.metrics.task_completion_rate - before.metrics.task_completion_rate,
        "efficiency_delta": after.metrics.avg_token_efficiency - before.metrics.avg_token_efficiency,
        "accuracy_delta": after.metrics.tool_accuracy - before.metrics.tool_accuracy,
        "improved": after.metrics.composite_score > before.metrics.composite_score,
        "before_score": before.metrics.composite_score,
        "after_score": after.metrics.composite_score,
    }
