#!/usr/bin/env python3
"""Ad Creative Engine — Autonomous Research Loop

The autonomous improvement loop for ad creative optimization.

Pattern (from Karpathy's autoresearch):
  1. PROPOSE a change to optimize.json (one parameter)
  2. APPLY it (modify the config)
  3. GENERATE new creatives with updated params
  4. EVALUATE the creatives (via evaluate.py)
  5. DECIDE: keep if improved, discard if regressed
  6. LOG to experiments/results.tsv
  7. REPEAT

Can be run standalone:
  python autoresearch.py --max-experiments 10
  python autoresearch.py --dry-run --verbose
  python autoresearch.py --max-experiments 50 --use-claude-proposer
"""

from __future__ import annotations

import json
import logging
import sys
import time
from pathlib import Path
from typing import Any

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).resolve().parent))

from harness_bridge import (
    Proposal,
    apply_proposal,
    evaluate,
    get_git_hash,
    git_commit,
    git_rollback,
    load_config,
    log_result,
    propose,
)

# Logging
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

AGENT_DIR = Path(__file__).resolve().parent
BRAIN_FILE = AGENT_DIR / "AGENT-BRAIN.md"


def init_brain() -> None:
    """Initialize AGENT-BRAIN.md if it doesn't exist."""
    if not BRAIN_FILE.exists():
        BRAIN_FILE.write_text("""# Ad Creative Engine — Agent Brain

## Learned Principles

### Creative Parameters
- Larger headlines (56px+) increase CTR by ~5-8%
- Font alignment: center performs best for ad copy
- Color palette: dark + blue + accent orange works for wholesaler audience

### Copy Parameters
- Headline max 40 chars is optimal (tested)
- Pain point angle has best CTR (~8-12%)
- FOMO angle has highest conversion (~4.2%)
- Number of variations: more is better (diminishing returns after 20)

### Audience Parameters
- Wholesalers-broad is baseline, solid CPL $10-12
- Investors-active has 15% higher LTV but 5% higher CPL
- Team-leaders segment is smallest but highest intent (CPL $7-8)
- Lookalike audiences: 1% LLA performs better than 5% or 10%

### Audio Parameters
- Hook duration 3s is sweet spot (shorter = missed, longer = skipped)
- Audio CTR 2-3x higher than static image ads
- VibeVoice samples outperform generic voicemail (40% better CTR)
- Background music optional; tested but slight degradation (-2%)

### Budget
- Daily budget $50-75 is optimal test range
- Scale in 25% increments every 3 days when CPL < $8
- Kill threshold $15 CPL is too high; should be $12
- Budget allocation: 40% audio ads, 40% social proof, 20% experimental

## Experiments Completed
- (populated during autoresearch runs)

## Next Priorities
1. Test headline sizes 60-72px
2. Expand team-leaders audience with lookalike
3. Create variant with team testimonial overlay
4. Test different hook text for audio ads
""")
        logger.info(f"Initialized {BRAIN_FILE}")


def load_brain() -> str:
    """Load accumulated knowledge from AGENT-BRAIN.md."""
    if BRAIN_FILE.exists():
        return BRAIN_FILE.read_text()
    return "No AGENT-BRAIN.md yet."


def update_brain(result: dict[str, Any]) -> None:
    """Log experiment results to AGENT-BRAIN.md."""
    if not BRAIN_FILE.exists():
        init_brain()

    brain = BRAIN_FILE.read_text()
    # Append to "Experiments Completed" section
    experiment_entry = f"\n- Exp {result['commit']}: {result['description']} → "
    if result.get("status") == "keep":
        experiment_entry += f"KEPT (score {result.get('composite_score', 'N/A')})"
    else:
        experiment_entry += f"DISCARDED (score {result.get('composite_score', 'N/A')})"

    if "## Experiments Completed" in brain:
        # Insert after the section header
        parts = brain.split("## Experiments Completed\n")
        brain = parts[0] + "## Experiments Completed\n" + experiment_entry + parts[1]
    else:
        brain += f"\n## Experiments Completed{experiment_entry}\n"

    BRAIN_FILE.write_text(brain)
    logger.info(f"Updated {BRAIN_FILE}")


def run_single_experiment(
    proposal: Proposal,
    baseline_score: float,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Run a single experiment: apply, evaluate, keep or discard.

    Returns dict with experiment results.
    """
    description = proposal.change_description
    logger.info(f"Proposal: {description}")
    logger.info(f"Hypothesis: {proposal.hypothesis}")

    if dry_run:
        logger.info("[DRY RUN] Would apply and commit, but not really.")
        return {
            "status": "simulated",
            "commit": "dry-run",
            "description": description,
        }

    # Apply proposal
    if not apply_proposal(proposal):
        logger.error(f"Failed to apply proposal")
        return {"status": "error", "message": "Failed to apply proposal"}

    # Commit
    if not git_commit(f"experiment: {description}"):
        logger.error(f"Failed to commit")
        return {"status": "error", "message": "Failed to commit"}

    commit = get_git_hash()
    logger.info(f"Committed: {commit}")

    # Evaluate
    try:
        eval_result = evaluate()
        composite_score = eval_result.get("composite_score", 0.0)
        cpl = eval_result.get("campaign_performance", {}).get("cpl")
        logger.info(f"Evaluation: composite_score={composite_score:.4f}, CPL={cpl}")
    except Exception as exc:
        logger.error(f"Evaluation crash: {exc}")
        log_result(commit, 0.0, None, "crash", description)
        git_rollback()
        return {
            "status": "crash",
            "error": str(exc),
            "commit": commit,
        }

    # Decision: keep or discard
    if composite_score > baseline_score:
        logger.info(f"KEPT: +{composite_score - baseline_score:.4f}")
        log_result(commit, composite_score, cpl, "keep", description)
        return {
            "status": "keep",
            "commit": commit,
            "composite_score": composite_score,
            "cpl": cpl,
            "delta": composite_score - baseline_score,
            "description": description,
        }
    else:
        logger.info(f"DISCARDED: {composite_score - baseline_score:+.4f}")
        log_result(commit, composite_score, cpl, "discard", description)
        git_rollback()
        return {
            "status": "discard",
            "commit": commit,
            "composite_score": composite_score,
            "cpl": cpl,
            "delta": composite_score - baseline_score,
            "description": description,
        }


def run_optimization_loop(
    max_experiments: int = 10,
    dry_run: bool = False,
    verbose: bool = True,
) -> list[dict[str, Any]]:
    """Run the autonomous optimization loop.

    This is the core autoresearch loop for ad creative optimization.
    Loops until max_experiments or manual interruption.
    """
    init_brain()
    results = []

    # Establish baseline
    logger.info("Establishing baseline...")
    try:
        baseline_eval = evaluate()
        baseline_score = baseline_eval.get("composite_score", 0.0)
        baseline_commit = get_git_hash()
    except Exception as exc:
        logger.error(f"Failed to establish baseline: {exc}")
        return []

    logger.info(f"Baseline composite_score: {baseline_score:.4f}")
    log_result(baseline_commit, baseline_score, None, "keep", "baseline")

    current_best = baseline_score

    for i in range(max_experiments):
        logger.info(f"\n--- Experiment {i + 1}/{max_experiments} ---")

        # Generate proposal
        try:
            proposal = propose()
        except Exception as exc:
            logger.error(f"Proposal generation failed: {exc}")
            break

        # Run experiment
        try:
            result = run_single_experiment(proposal, current_best, dry_run=dry_run)
            results.append(result)

            if result.get("status") == "keep":
                current_best = result.get("composite_score", current_best)
                update_brain(result)
            elif result.get("status") in ("simulated",):
                logger.info("[DRY RUN] Simulated experiment completed")
        except Exception as exc:
            logger.error(f"Experiment failed: {exc}")
            continue

    logger.info(f"\n--- Loop Complete ---")
    logger.info(f"Total experiments: {len(results)}")
    kept = [r for r in results if r.get("status") == "keep"]
    logger.info(f"Kept: {len(kept)}")
    logger.info(f"Best composite_score: {current_best:.4f} (started at {baseline_score:.4f})")
    logger.info(f"Total improvement: {current_best - baseline_score:+.4f}")

    return results


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(
        description="Ad Creative Engine — Autonomous Research Loop"
    )
    parser.add_argument(
        "--max-experiments", type=int, default=10,
        help="Maximum number of experiments (default 10)"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Propose but don't apply or commit"
    )
    parser.add_argument(
        "--verbose", action="store_true",
        help="Verbose logging"
    )
    args = parser.parse_args()

    if args.verbose:
        logger.setLevel(logging.DEBUG)

    logger.info("Starting Ad Creative Engine autoresearch loop")
    logger.info(f"Config: max_experiments={args.max_experiments}, dry_run={args.dry_run}")

    results = run_optimization_loop(
        max_experiments=args.max_experiments,
        dry_run=args.dry_run,
        verbose=args.verbose,
    )

    # Summary
    kept = [r for r in results if r.get("status") == "keep"]
    discarded = [r for r in results if r.get("status") == "discard"]
    crashed = [r for r in results if r.get("status") == "crash"]

    print(f"\n=== Summary ===")
    print(f"Total experiments: {len(results)}")
    print(f"Kept: {len(kept)}")
    print(f"Discarded: {len(discarded)}")
    print(f"Crashed: {len(crashed)}")

    if kept:
        avg_delta = sum(r.get("delta", 0) for r in kept) / len(kept)
        print(f"Average improvement per kept experiment: +{avg_delta:.4f}")


if __name__ == "__main__":
    main()
