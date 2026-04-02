"""
PyClaude-Harness evaluation harness. READ-ONLY — do not modify.

This is the ground truth evaluator. It runs a fixed set of benchmark tasks
against the current harness configuration and measures:
  1. task_completion_rate — fraction of tasks completed correctly
  2. token_efficiency    — average tokens used per successful task
  3. tool_accuracy       — fraction of tool calls that were necessary
  4. latency_seconds     — average wall-clock time per task

The agent modifies `optimize.py` (the harness config). This file evaluates it.

Usage: python prepare.py [--tasks-dir benchmarks/tasks] [--config optimize.py]
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Constants (DO NOT MODIFY)
# ---------------------------------------------------------------------------

MAX_TURNS_PER_TASK = 25          # Hard cap on agent turns per task
TIME_BUDGET_SECONDS = 120        # Max wall-clock seconds per task
MAX_TOKENS_PER_TASK = 50_000     # Token budget per task
EVAL_TASKS_DIR = Path("benchmarks/tasks")
RESULTS_FILE = Path("results.tsv")


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class BenchmarkTask:
    """A single evaluation task."""
    name: str
    description: str
    prompt: str
    expected_tools: list[str]         # Tools the task should use
    success_criteria: str             # How to judge success
    category: str = "general"         # Task category for grouping
    difficulty: str = "medium"        # easy | medium | hard
    max_turns: int = MAX_TURNS_PER_TASK


@dataclass
class TaskResult:
    """Result of running a single benchmark task."""
    task_name: str
    completed: bool
    turns_used: int
    tokens_used: int
    tools_called: list[str]
    unnecessary_tools: list[str]
    wall_seconds: float
    error: str | None = None


@dataclass
class EvalMetrics:
    """Aggregated evaluation metrics across all tasks."""
    task_completion_rate: float
    avg_token_efficiency: float
    tool_accuracy: float
    avg_latency_seconds: float
    total_tasks: int
    tasks_completed: int
    tasks_failed: int
    composite_score: float = 0.0

    def __post_init__(self):
        # Composite score: weighted combination (higher is better)
        # Completion matters most, then efficiency, then accuracy
        self.composite_score = (
            self.task_completion_rate * 0.50
            + (1.0 - min(self.avg_token_efficiency / MAX_TOKENS_PER_TASK, 1.0)) * 0.25
            + self.tool_accuracy * 0.25
        )


# ---------------------------------------------------------------------------
# Task loading
# ---------------------------------------------------------------------------

def load_tasks(tasks_dir: Path = EVAL_TASKS_DIR) -> list[BenchmarkTask]:
    """Load benchmark tasks from JSON files in tasks_dir."""
    tasks = []
    if not tasks_dir.exists():
        print(f"Warning: tasks directory {tasks_dir} does not exist", file=sys.stderr)
        return tasks

    for task_file in sorted(tasks_dir.glob("*.json")):
        try:
            raw = json.loads(task_file.read_text())
            tasks.append(BenchmarkTask(
                name=raw["name"],
                description=raw["description"],
                prompt=raw["prompt"],
                expected_tools=raw.get("expected_tools", []),
                success_criteria=raw.get("success_criteria", ""),
                category=raw.get("category", "general"),
                difficulty=raw.get("difficulty", "medium"),
                max_turns=raw.get("max_turns", MAX_TURNS_PER_TASK),
            ))
        except (json.JSONDecodeError, KeyError) as exc:
            print(f"Warning: skipping {task_file}: {exc}", file=sys.stderr)
    return tasks


# ---------------------------------------------------------------------------
# Harness config loading
# ---------------------------------------------------------------------------

def load_harness_config(config_path: str = "optimize.json") -> dict[str, Any]:
    """Load the harness config from a JSON file (safe, no code execution)."""
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")
    raw = json.loads(path.read_text())

    def as_int(value: Any, default: int) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    def as_float(value: Any, default: float) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    # Return with defaults for any missing keys
    return {
        "system_prompt": raw.get("system_prompt", ""),
        "tool_definitions": raw.get("tool_definitions", {}),
        "context_strategy": raw.get("context_strategy", {}),
        "routing_rules": raw.get("routing_rules", {}),
        "token_budget": as_int(raw.get("token_budget", MAX_TOKENS_PER_TASK), MAX_TOKENS_PER_TASK),
        "temperature": as_float(raw.get("temperature", 0.0), 0.0),
        "model": raw.get("model", "claude-sonnet-4-20250514"),
        "max_turns": as_int(raw.get("max_turns", MAX_TURNS_PER_TASK), MAX_TURNS_PER_TASK),
    }


# ---------------------------------------------------------------------------
# Evaluation (simulated — real eval requires API calls)
# ---------------------------------------------------------------------------

def evaluate_task(task: BenchmarkTask, config: dict[str, Any]) -> TaskResult:
    """
    Evaluate a single task against the harness config.

    In production, this calls the Claude API with the configured system prompt,
    tool definitions, and context strategy. For development/testing, it runs
    a simulated evaluation based on config quality heuristics.
    """
    start = time.time()

    # --- Simulated evaluation logic ---
    # Score the config quality for this task
    system_prompt = config.get("system_prompt", "")
    tool_defs = config.get("tool_definitions", {})
    routing = config.get("routing_rules", {})
    context = config.get("context_strategy", {})

    # Heuristic: longer, more specific system prompts tend to perform better
    prompt_score = min(len(system_prompt) / 2000, 1.0)

    # Heuristic: having tool definitions for expected tools helps
    tool_coverage = 0.0
    if task.expected_tools:
        covered = sum(1 for t in task.expected_tools if t in tool_defs)
        tool_coverage = covered / len(task.expected_tools)

    # Heuristic: routing rules improve task completion
    routing_score = min(len(routing) / 5, 1.0) * 0.3

    # Heuristic: context strategy affects token efficiency
    context_score = 0.5  # baseline
    if context.get("compaction_enabled"):
        context_score = 0.7
    if context.get("relevance_filtering"):
        context_score = 0.85

    # Combined completion probability
    completion_prob = (prompt_score * 0.4 + tool_coverage * 0.3
                       + routing_score * 0.15 + context_score * 0.15)

    # Simulate token usage (better configs use fewer tokens)
    base_tokens = config.get("token_budget", MAX_TOKENS_PER_TASK)
    efficiency_factor = max(0.3, 1.0 - context_score * 0.5)
    tokens_used = int(base_tokens * efficiency_factor)

    # Simulate tool calls — realistic: may miss expected tools or call extras
    expected_set = set(task.expected_tools)
    tools_called = []
    unnecessary = []

    if task.expected_tools:
        # Higher tool_coverage → more likely to call the right tools
        for tool in task.expected_tools:
            if tool in tool_defs or tool_coverage > 0.4:
                tools_called.append(tool)
            # else: missed tool

        # Lower routing quality → more likely to call unnecessary tools
        all_tools = list(tool_defs.keys())
        extra_pool = [t for t in all_tools if t not in expected_set]
        routing_quality = min(len(routing) / 5, 1.0)
        # Add unnecessary tools inversely proportional to routing quality
        for extra_tool in extra_pool:
            if routing_quality < 0.6:
                unnecessary.append(extra_tool)
                tools_called.append(extra_tool)
            elif routing_quality < 0.8 and tool_defs.get(extra_tool, {}).get("priority") == "low":
                unnecessary.append(extra_tool)
                tools_called.append(extra_tool)

    completed = completion_prob > 0.5
    turns_used = max(1, int(config.get("max_turns", 10) * (1.0 - completion_prob * 0.5)))
    wall_seconds = time.time() - start

    return TaskResult(
        task_name=task.name,
        completed=completed,
        turns_used=turns_used,
        tokens_used=tokens_used,
        tools_called=tools_called,
        unnecessary_tools=unnecessary,
        wall_seconds=wall_seconds,
    )


def evaluate_all(tasks: list[BenchmarkTask], config: dict[str, Any]) -> EvalMetrics:
    """Run all benchmark tasks and compute aggregate metrics."""
    results: list[TaskResult] = []
    for task in tasks:
        result = evaluate_task(task, config)
        results.append(result)

    if not results:
        return EvalMetrics(
            task_completion_rate=0.0,
            avg_token_efficiency=0.0,
            tool_accuracy=0.0,
            avg_latency_seconds=0.0,
            total_tasks=0,
            tasks_completed=0,
            tasks_failed=0,
        )

    completed = [r for r in results if r.completed]
    failed = [r for r in results if not r.completed]

    task_completion_rate = len(completed) / len(results)

    avg_tokens = statistics.mean(r.tokens_used for r in results) if results else 0.0

    # Tool accuracy: harmonic mean of precision and recall
    # Precision = fraction of called tools that were expected (not unnecessary)
    # Recall = fraction of expected tools that were actually called
    total_calls = sum(len(r.tools_called) for r in results)
    unnecessary_calls = sum(len(r.unnecessary_tools) for r in results)
    correct_calls = total_calls - unnecessary_calls
    total_expected = sum(len(t.expected_tools) for t in tasks)

    if total_expected == 0 and total_calls == 0:
        tool_accuracy = 1.0  # no tools expected, none called
    else:
        precision = correct_calls / max(total_calls, 1)
        recall = correct_calls / max(total_expected, 1)
        if precision + recall > 0:
            tool_accuracy = 2 * precision * recall / (precision + recall)
        else:
            tool_accuracy = 0.0

    avg_latency = statistics.mean(r.wall_seconds for r in results) if results else 0.0

    return EvalMetrics(
        task_completion_rate=task_completion_rate,
        avg_token_efficiency=avg_tokens,
        tool_accuracy=tool_accuracy,
        avg_latency_seconds=avg_latency,
        total_tasks=len(results),
        tasks_completed=len(completed),
        tasks_failed=len(failed),
    )


def evaluate_composite(config_path: str = "optimize.json",
                       tasks_dir: Path = EVAL_TASKS_DIR) -> float:
    """
    Single-number evaluation. Returns composite_score (higher is better).
    This is the ground truth metric, analogous to val_bpb in autoresearch.
    """
    config = load_harness_config(config_path)
    tasks = load_tasks(tasks_dir)
    if not tasks:
        print("Warning: no benchmark tasks found, returning 0.0", file=sys.stderr)
        return 0.0
    metrics = evaluate_all(tasks, config)
    return metrics.composite_score


# ---------------------------------------------------------------------------
# Output format (matches autoresearch style)
# ---------------------------------------------------------------------------

def print_summary(metrics: EvalMetrics) -> None:
    """Print evaluation summary in autoresearch-compatible format."""
    print("---")
    print(f"composite_score:       {metrics.composite_score:.6f}")
    print(f"task_completion_rate:  {metrics.task_completion_rate:.4f}")
    print(f"avg_token_efficiency:  {metrics.avg_token_efficiency:.1f}")
    print(f"tool_accuracy:         {metrics.tool_accuracy:.4f}")
    print(f"avg_latency_seconds:   {metrics.avg_latency_seconds:.3f}")
    print(f"total_tasks:           {metrics.total_tasks}")
    print(f"tasks_completed:       {metrics.tasks_completed}")
    print(f"tasks_failed:          {metrics.tasks_failed}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="PyClaude-Harness evaluation")
    parser.add_argument("--config", default="optimize.json", help="Harness config file")
    parser.add_argument("--tasks-dir", type=Path, default=EVAL_TASKS_DIR)
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    config = load_harness_config(args.config)
    tasks = load_tasks(args.tasks_dir)

    if not tasks:
        print("No benchmark tasks found. Add .json files to benchmarks/tasks/", file=sys.stderr)
        sys.exit(1)

    print(f"Running {len(tasks)} benchmark tasks...", file=sys.stderr)
    metrics = evaluate_all(tasks, config)

    if args.json:
        print(json.dumps(asdict(metrics), indent=2))
    else:
        print_summary(metrics)


if __name__ == "__main__":
    main()
