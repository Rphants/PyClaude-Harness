"""Ad Creative Engine — Harness Bridge

Connects the ad-engine agent to the PyClaude-Harness orchestrator pattern.

Implements the same interface as harness/orchestrator.py but specialized for
ad creative optimization. The proposer, applicator, evaluator, and rollback
functions follow the Meta-Harness pattern.

Pattern:
  1. propose() — read optimize.json + AGENT-BRAIN.md, propose a change
  2. apply(proposal) — modify optimize.json with the proposal
  3. evaluate() — run evaluate.py and return a score dict
  4. rollback() — revert optimize.json to previous state (via git)
  5. log(result) — append to experiments/results.tsv
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

# Paths
AGENT_DIR = Path(__file__).resolve().parent
OPTIMIZE_FILE = AGENT_DIR / "optimize.json"
RESULTS_FILE = AGENT_DIR / "experiments" / "results.tsv"
EXPERIMENTS_DIR = AGENT_DIR / "experiments"
BRAIN_FILE = AGENT_DIR / "AGENT-BRAIN.md"
CREATIVE_TRAINING_FILE = AGENT_DIR / "creative_training.py"


@dataclass
class Proposal:
    """A concrete proposed change to optimize.json."""
    hypothesis: str          # What we think will improve CPL
    change_description: str  # Human-readable description
    section: str             # Which section: creative_params, copy_params, etc.
    old_value: str           # Current value (for rollback)
    new_value: str           # Proposed value
    expected_impact: str     # Predicted effect on CPL or composite_score
    risk_level: str = "low"  # low | medium | high
    priority: int = 5        # 1 (highest) to 10 (lowest)


@dataclass
class ProposalContext:
    """All context the proposer uses."""
    current_config: dict[str, Any]
    recent_results: list[dict[str, Any]]
    best_cpl: float | None
    worst_cpl: float | None
    angles_tried: list[str]
    creative_count: int
    target_metrics: dict[str, Any]


def init_results_file() -> None:
    """Create results.tsv with header if it doesn't exist."""
    EXPERIMENTS_DIR.mkdir(parents=True, exist_ok=True)
    if not RESULTS_FILE.exists():
        RESULTS_FILE.write_text(
            "commit\tcomposite_score\tcpl\tdecision\tdescription\n"
        )


def get_git_hash() -> str:
    """Get current short git hash."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, timeout=10, cwd=AGENT_DIR,
        )
        return result.stdout.strip() if result.returncode == 0 else "unknown"
    except Exception:
        return "unknown"


def git_commit(message: str) -> bool:
    """Stage optimize.json and commit."""
    try:
        paths = [str(OPTIMIZE_FILE)]
        for pattern in ("auto-*.json", "auto-*.png", "auto-scene-*.png"):
            paths.extend(str(path) for path in EXPERIMENTS_DIR.glob(pattern))
        subprocess.run(
            ["git", "add", *paths],
            check=True, timeout=10, cwd=AGENT_DIR,
        )
        subprocess.run(
            ["git", "commit", "-m", message],
            check=True, capture_output=True, timeout=10, cwd=AGENT_DIR,
        )
        return True
    except subprocess.CalledProcessError:
        return False


def git_rollback() -> bool:
    """Roll back the last commit, stashing uncommitted work first."""
    try:
        subprocess.run(
            ["git", "stash", "--include-untracked"],
            capture_output=True, timeout=10, cwd=AGENT_DIR,
        )
        subprocess.run(
            ["git", "reset", "--hard", "HEAD~1"],
            check=True, capture_output=True, timeout=10, cwd=AGENT_DIR,
        )
        subprocess.run(
            ["git", "stash", "pop"],
            capture_output=True, timeout=10, cwd=AGENT_DIR,
        )
        return True
    except subprocess.CalledProcessError:
        return False


def load_config() -> dict[str, Any]:
    """Load the current optimize.json."""
    try:
        with OPTIMIZE_FILE.open() as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as exc:
        print(f"Failed to load optimize.json: {exc}", file=sys.stderr)
        return {}


def save_config(config: dict[str, Any]) -> bool:
    """Save config back to optimize.json."""
    try:
        with OPTIMIZE_FILE.open("w") as f:
            json.dump(config, f, indent=2)
        return True
    except Exception as exc:
        print(f"Failed to save optimize.json: {exc}", file=sys.stderr)
        return False


def parse_json_payload(raw: str) -> dict[str, Any]:
    """Extract the last JSON object from noisy stdout."""
    raw = raw.strip()
    if not raw:
        raise json.JSONDecodeError("empty output", raw, 0)

    parsed: dict[str, Any] | None = None
    for line in raw.splitlines():
        candidate = line.strip()
        if not candidate.startswith("{"):
            continue
        try:
            loaded = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(loaded, dict):
            parsed = loaded

    if parsed is not None:
        return parsed

    decoder = json.JSONDecoder()
    best_match = None
    for index, char in enumerate(raw):
        if char != "{":
            continue
        try:
            candidate, end = decoder.raw_decode(raw[index:])
        except json.JSONDecodeError:
            continue
        if isinstance(candidate, dict):
            if best_match is None or end > best_match[0]:
                best_match = (end, candidate)

    if best_match is None:
        raise json.JSONDecodeError("no JSON object found", raw, 0)
    return best_match[1]


def apply_proposal(proposal: Proposal) -> bool:
    """Apply a proposal's changes to optimize.json.

    Updates the section specified by the proposal and writes back.
    """
    config = load_config()
    if not config:
        return False

    section_key = proposal.section.lower()
    if section_key not in config:
        print(f"Unknown config section: {proposal.section}", file=sys.stderr)
        return False

    # Parse new_value as JSON if possible, otherwise use as string
    try:
        new_val = json.loads(proposal.new_value)
    except (json.JSONDecodeError, TypeError):
        new_val = proposal.new_value

    # Merge keys into the section if both are dicts; otherwise replace
    if isinstance(config[section_key], dict) and isinstance(new_val, dict):
        config[section_key].update(new_val)
    else:
        config[section_key] = new_val
    return save_config(config)


def evaluate() -> dict[str, Any]:
    """Run evaluate.py --json and return parsed results.

    Uses --json flag so evaluate.py outputs a single JSON object to stdout.
    If META_ACCESS_TOKEN is set, evaluate.py will pull live Meta API data.

    Returns a dict with:
      - composite_score: 0-1
      - creative_readiness: {...}
      - campaign_performance: {...}
      - data_source: "live" | "offline"
      - recommendation: str
    """
    eval_script = AGENT_DIR / "evaluate.py"
    if not eval_script.exists():
        print(f"evaluate.py not found at {eval_script}", file=sys.stderr)
        return {"composite_score": 0.0, "error": "evaluate.py missing"}

    try:
        result = subprocess.run(
            ["python3", str(eval_script), "--json"],
            capture_output=True, text=True, timeout=60, cwd=AGENT_DIR,
        )

        if result.returncode != 0:
            print(f"evaluate.py failed (exit {result.returncode}): {result.stderr}", file=sys.stderr)
            return {
                "composite_score": 0.0,
                "error": f"evaluate.py exit {result.returncode}",
                "stderr": result.stderr,
            }

        try:
            return parse_json_payload(result.stdout)
        except json.JSONDecodeError as exc:
            print(f"Failed to parse evaluate.py JSON output: {exc}", file=sys.stderr)
            print(f"Raw stdout: {result.stdout[:500]}", file=sys.stderr)
            return {
                "composite_score": 0.0,
                "error": f"JSON parse error: {exc}",
            }

    except subprocess.TimeoutExpired:
        return {"composite_score": 0.0, "error": "evaluation timeout (60s)"}
    except Exception as exc:
        return {"composite_score": 0.0, "error": str(exc)}


def generate_training_batch(render: bool = True) -> dict[str, Any]:
    """Generate an autonomous batch of creative specs/assets for evaluation."""
    if not CREATIVE_TRAINING_FILE.exists():
        return {"ok": False, "error": "creative_training.py missing"}

    cmd = [sys.executable, str(CREATIVE_TRAINING_FILE), "generate", "--json"]
    if not render:
        cmd.append("--no-render")
    if os.environ.get("AD_DISABLE_CLAUDE_COPY", "").strip().lower() in {"1", "true", "yes", "on"}:
        cmd.append("--no-claude")

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,
            cwd=AGENT_DIR,
        )
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "creative batch generation timeout"}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}

    if result.returncode != 0:
        return {
            "ok": False,
            "error": f"creative batch generation exit {result.returncode}",
            "stderr": result.stderr,
        }

    try:
        payload = parse_json_payload(result.stdout)
    except json.JSONDecodeError as exc:
        return {"ok": False, "error": f"creative batch json parse error: {exc}"}

    payload["ok"] = True
    return payload


def load_brain() -> str:
    """Load AGENT-BRAIN.md for context."""
    try:
        return BRAIN_FILE.read_text()
    except FileNotFoundError:
        return "No AGENT-BRAIN.md found yet."


def _load_tried_descriptions() -> set[str]:
    """Read results.tsv and return the set of already-tried change descriptions."""
    tried: set[str] = set()
    if RESULTS_FILE.exists():
        for line in RESULTS_FILE.read_text().splitlines()[1:]:  # skip header
            parts = line.split("\t")
            if len(parts) >= 5:
                tried.add(parts[4])
    return tried


def propose() -> Proposal:
    """Generate a proposal based on current state.

    Reads optimize.json, AGENT-BRAIN.md, and results.tsv (for history).
    Skips proposals whose change_description has already been tried.
    """
    config = load_config()
    brain = load_brain()
    tried = _load_tried_descriptions()

    # Heuristics for proposing changes
    proposals = []

    # Creative parameter tuning
    if config.get("creative_params"):
        cp = config["creative_params"]
        if cp.get("headline_font_size_px", 56) > 48:
            proposals.append(Proposal(
                hypothesis="Larger headlines increase impression and CTR",
                change_description="Increase headline font size from 56px to 64px",
                section="creative_params",
                old_value=json.dumps(cp),
                new_value=json.dumps({**cp, "headline_font_size_px": 64}),
                expected_impact="CTR +5-8%, CPL -3%",
                priority=2,
            ))

    # Copy variation strategy
    if config.get("copy_params"):
        cp_copy = config["copy_params"]
        if cp_copy.get("number_of_variations", 12) < 20:
            proposals.append(Proposal(
                hypothesis="More copy variations discover better performing angles",
                change_description="Increase copy variations from 12 to 20",
                section="copy_params",
                old_value=json.dumps(cp_copy),
                new_value=json.dumps({**cp_copy, "number_of_variations": 20}),
                expected_impact="CPL -2-4% via better angle coverage",
                priority=1,
            ))

    # Audience expansion
    if config.get("audience_params"):
        ap = config["audience_params"]
        if not ap.get("audience_expansion_enabled"):
            proposals.append(Proposal(
                hypothesis="Expanded audiences find cheaper lead sources",
                change_description="Enable audience expansion",
                section="audience_params",
                old_value=json.dumps(ap),
                new_value=json.dumps({**ap, "audience_expansion_enabled": True}),
                expected_impact="Reach +20%, CPL -5%",
                priority=3,
            ))

    # Audio format emphasis
    if config.get("audio_params"):
        audio = config["audio_params"]
        if not audio.get("background_music_enabled"):
            proposals.append(Proposal(
                hypothesis="Background music makes audio ads more engaging",
                change_description="Enable background music in audio ads",
                section="audio_params",
                old_value=json.dumps(audio),
                new_value=json.dumps({**audio, "background_music_enabled": True}),
                expected_impact="Audio CTR +8-12%",
                priority=2,
            ))

    # Budget scaling
    if config.get("budget_params"):
        bp = config["budget_params"]
        if bp.get("daily_budget_usd", 50) < 100:
            proposals.append(Proposal(
                hypothesis="Higher budget enables better statistical learning",
                change_description="Increase daily budget from $50 to $75",
                section="budget_params",
                old_value=json.dumps(bp),
                new_value=json.dumps({**bp, "daily_budget_usd": 75}),
                expected_impact="Lead volume +30%, CPL possibly -2%",
                priority=4,
            ))

    # Sort by priority, then filter out already-tried proposals
    proposals.sort(key=lambda p: p.priority)
    proposals = [p for p in proposals if p.change_description not in tried]

    if proposals:
        return proposals[0]

    # Fallback: no-op proposal (signals exhaustion to the loop)
    return Proposal(
        hypothesis="All heuristic proposals exhausted",
        change_description="No change — proposals exhausted",
        section="prompt_template",
        old_value="(current)",
        new_value="(current)",
        expected_impact="0%",
        priority=10,
    )


def log_result(commit: str, composite_score: float, cpl: float | None,
               decision: str, description: str) -> None:
    """Append a result to experiments/results.tsv."""
    init_results_file()
    cpl_str = f"{cpl:.2f}" if cpl is not None else "N/A"
    line = f"{commit}\t{composite_score:.6f}\t{cpl_str}\t{decision}\t{description}\n"
    with open(RESULTS_FILE, "a") as f:
        f.write(line)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description="Ad Creative Engine — Harness Bridge")
    parser.add_argument("--propose", action="store_true", help="Generate a proposal")
    parser.add_argument("--apply", type=str, help="Apply a proposal (JSON)")
    parser.add_argument("--evaluate", action="store_true", help="Run evaluation")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    if args.propose:
        proposal = propose()
        print(json.dumps(asdict(proposal), indent=2))

    elif args.apply:
        try:
            proposal_dict = json.loads(args.apply)
            proposal = Proposal(**proposal_dict)
            success = apply_proposal(proposal)
            print("OK" if success else "FAILED")
        except (json.JSONDecodeError, TypeError) as exc:
            print(f"Error: {exc}", file=sys.stderr)
            sys.exit(1)

    elif args.evaluate:
        result = evaluate()
        print(json.dumps(result, indent=2))

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
