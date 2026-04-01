"""
Meta-Harness Orchestrator — the autonomous experiment loop.

This is the engine that runs forever, following the autoresearch pattern:
  1. Propose a change (via proposer)
  2. Apply it to optimize.py
  3. Evaluate (via prepare.py)
  4. Keep if improved, discard if not
  5. Log to results.tsv
  6. Repeat

Can be run standalone or dispatched via Claude Code.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from harness.evaluator import DetailedEvaluation, compare_evaluations, run_evaluation
from harness.proposer import (
    Proposal,
    ProposalContext,
    generate_proposals,
    load_experiment_history,
    propose_with_claude,
)
from prepare import evaluate_composite


RESULTS_FILE = Path("results.tsv")
OPTIMIZE_FILE = Path("optimize.py")


def init_results_file() -> None:
    """Create results.tsv with header if it doesn't exist."""
    if not RESULTS_FILE.exists():
        RESULTS_FILE.write_text("commit\tcomposite_score\ttasks_completed\tstatus\tdescription\n")


def get_git_hash() -> str:
    """Get current short git hash."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, timeout=10,
        )
        return result.stdout.strip() if result.returncode == 0 else "unknown"
    except Exception:
        return "unknown"


def git_commit(message: str) -> bool:
    """Stage optimize.py and commit."""
    try:
        subprocess.run(["git", "add", "optimize.py"], check=True, timeout=10)
        subprocess.run(
            ["git", "commit", "-m", message],
            check=True, capture_output=True, timeout=10,
        )
        return True
    except subprocess.CalledProcessError:
        return False


def git_rollback() -> bool:
    """Roll back the last commit (discard experiment)."""
    try:
        subprocess.run(
            ["git", "reset", "--hard", "HEAD~1"],
            check=True, capture_output=True, timeout=10,
        )
        return True
    except subprocess.CalledProcessError:
        return False


def log_result(commit: str, score: float, tasks_completed: str,
               status: str, description: str) -> None:
    """Append a result to results.tsv."""
    line = f"{commit}\t{score:.6f}\t{tasks_completed}\t{status}\t{description}\n"
    with open(RESULTS_FILE, "a") as f:
        f.write(line)


def run_single_experiment(
    proposal: Proposal,
    baseline_score: float,
    use_claude_proposer: bool = False,
) -> dict[str, Any]:
    """
    Run a single experiment: apply proposal, evaluate, keep or discard.

    Returns a dict with experiment results.
    """
    description = proposal.change_description

    # Apply the change (in production, this modifies optimize.py)
    # For now, we assume the caller has already modified optimize.py
    if not git_commit(f"experiment: {description}"):
        return {"status": "error", "message": "Failed to commit"}

    commit = get_git_hash()

    # Evaluate
    try:
        score = evaluate_composite()
    except Exception as exc:
        log_result(commit, 0.0, "0/0", "crash", description)
        git_rollback()
        return {"status": "crash", "error": str(exc), "commit": commit}

    # Get detailed evaluation for logging
    try:
        detailed = run_evaluation()
        tasks_str = f"{detailed.metrics.tasks_completed}/{detailed.metrics.total_tasks}"
    except Exception:
        tasks_str = "?/?"

    # Decision: keep or discard
    if score > baseline_score:
        log_result(commit, score, tasks_str, "keep", description)
        return {
            "status": "keep",
            "commit": commit,
            "score": score,
            "baseline": baseline_score,
            "delta": score - baseline_score,
            "description": description,
        }
    else:
        log_result(commit, score, tasks_str, "discard", description)
        git_rollback()
        return {
            "status": "discard",
            "commit": commit,
            "score": score,
            "baseline": baseline_score,
            "delta": score - baseline_score,
            "description": description,
        }


def run_optimization_loop(
    max_experiments: int = 100,
    use_claude_proposer: bool = False,
    verbose: bool = True,
) -> list[dict[str, Any]]:
    """
    Run the autonomous optimization loop.

    This is the core Meta-Harness loop, following the autoresearch pattern.
    Runs until max_experiments or manual interruption.
    """
    init_results_file()
    results = []

    # Establish baseline
    if verbose:
        print("Establishing baseline...", file=sys.stderr)

    baseline_score = evaluate_composite()
    baseline_eval = run_evaluation()
    baseline_commit = get_git_hash()

    log_result(
        baseline_commit, baseline_score,
        f"{baseline_eval.metrics.tasks_completed}/{baseline_eval.metrics.total_tasks}",
        "keep", "baseline"
    )

    if verbose:
        print(f"Baseline composite_score: {baseline_score:.6f}", file=sys.stderr)

    current_best = baseline_score

    for i in range(max_experiments):
        if verbose:
            print(f"\n--- Experiment {i + 1}/{max_experiments} ---", file=sys.stderr)

        # Build context for proposer
        history = load_experiment_history()
        failed = [e for e in history if e.get("status") in ("discard", "crash")]

        context = ProposalContext(
            current_config={},  # Would load from optimize.py
            eval_metrics=asdict(baseline_eval.metrics),
            experiment_history=history,
            failed_experiments=failed,
            codebase_summary="claw-code Python rewrite of Claude Code",
            task_failures=baseline_eval.failure_analysis,
        )

        # Generate proposals
        if use_claude_proposer:
            proposals = propose_with_claude(context)
        else:
            proposals = generate_proposals(context)

        if not proposals:
            if verbose:
                print("No proposals generated. Stopping.", file=sys.stderr)
            break

        # Take the top proposal
        proposal = proposals[0]
        if verbose:
            print(f"Proposal: {proposal.change_description}", file=sys.stderr)
            print(f"Hypothesis: {proposal.hypothesis}", file=sys.stderr)

        # Run the experiment
        result = run_single_experiment(proposal, current_best, use_claude_proposer)
        results.append(result)

        if result["status"] == "keep":
            current_best = result["score"]
            if verbose:
                print(f"KEPT: {result['score']:.6f} (+{result['delta']:.6f})", file=sys.stderr)
            # Update baseline eval for next iteration
            baseline_eval = run_evaluation()
        elif verbose:
            print(f"DISCARDED: {result['score']:.6f} ({result['delta']:+.6f})", file=sys.stderr)

    if verbose:
        print(f"\nFinal best: {current_best:.6f} (started at {baseline_score:.6f})", file=sys.stderr)
        print(f"Total improvement: {current_best - baseline_score:+.6f}", file=sys.stderr)

    return results


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description="PyClaude-Harness optimization loop")
    parser.add_argument("--max-experiments", type=int, default=100)
    parser.add_argument("--use-claude", action="store_true",
                        help="Use Claude Code as the proposer agent")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()

    results = run_optimization_loop(
        max_experiments=args.max_experiments,
        use_claude_proposer=args.use_claude,
        verbose=not args.quiet,
    )

    # Summary
    kept = [r for r in results if r.get("status") == "keep"]
    discarded = [r for r in results if r.get("status") == "discard"]
    crashed = [r for r in results if r.get("status") == "crash"]

    print(f"\nExperiments: {len(results)} total, {len(kept)} kept, "
          f"{len(discarded)} discarded, {len(crashed)} crashed")


if __name__ == "__main__":
    main()
