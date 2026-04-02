"""
Meta-Harness Proposer Agent.

Uses Claude to analyze current harness performance and propose improvements.
This is the "brain" of the self-improvement loop — it reads evaluation results,
diagnoses weaknesses, and generates concrete changes to optimize.py.

The proposer has access to up to 10M tokens of diagnostic context:
- Full evaluation results with per-task breakdowns
- Historical experiment results (results.tsv)
- The claw-code source for system understanding
- Previous failed experiments (to avoid repeating)
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class ProposalContext:
    """All context the proposer uses to generate a proposal."""
    current_config: dict[str, Any]
    eval_metrics: dict[str, Any]
    experiment_history: list[dict[str, str]]
    failed_experiments: list[dict[str, str]]
    codebase_summary: str
    task_failures: list[dict[str, Any]]


@dataclass
class Proposal:
    """A concrete proposed change to optimize.py."""
    hypothesis: str          # What we think will improve
    change_description: str  # Human-readable description
    section: str             # Which section of optimize.py to modify
    old_value: str           # Current value (for rollback)
    new_value: str           # Proposed value
    expected_impact: str     # Predicted effect on composite_score
    risk_level: str = "low"  # low | medium | high
    priority: int = 5        # 1 (highest) to 10 (lowest)


def load_experiment_history(results_file: Path = Path("results.tsv")) -> list[dict[str, str]]:
    """Load past experiment results from TSV."""
    history = []
    if not results_file.exists():
        return history
    lines = results_file.read_text().strip().split("\n")
    if len(lines) < 2:  # header only
        return history
    headers = lines[0].split("\t")
    for line in lines[1:]:
        values = line.split("\t")
        entry = dict(zip(headers, values))
        history.append(entry)
    return history


def analyze_failures(eval_metrics: dict[str, Any]) -> list[str]:
    """Identify the biggest weaknesses in current harness performance."""
    weaknesses = []
    completion = eval_metrics.get("task_completion_rate", 0)
    efficiency = eval_metrics.get("avg_token_efficiency", 50000)
    accuracy = eval_metrics.get("tool_accuracy", 0)

    if completion < 0.8:
        weaknesses.append(f"Low task completion ({completion:.1%}): system prompt may lack specificity")
    if efficiency > 25000:
        weaknesses.append(f"High token usage ({efficiency:.0f}): context strategy needs tightening")
    if accuracy < 0.9:
        weaknesses.append(f"Poor tool accuracy ({accuracy:.1%}): routing rules need refinement")
    if not weaknesses:
        weaknesses.append("All metrics are strong — try micro-optimizations or radical experiments")
    return weaknesses


def generate_proposals(context: ProposalContext) -> list[Proposal]:
    """
    Generate ranked list of improvement proposals.

    In production, this calls Claude API with full diagnostic context.
    For local development, it uses rule-based heuristics.
    """
    proposals = []
    weaknesses = analyze_failures(context.eval_metrics)

    # Previously tried descriptions (normalized to lowercase for comparison)
    tried = {exp.get("description", "").lower() for exp in context.experiment_history}

    # Proposal generators based on weakness analysis
    for weakness in weaknesses:
        if "completion" in weakness.lower():
            if "add tool usage examples to system_prompt" not in tried:
                proposals.append(Proposal(
                    hypothesis="Adding concrete examples improves task completion",
                    change_description="Add tool usage examples to SYSTEM_PROMPT",
                    section="SYSTEM_PROMPT",
                    old_value="(current prompt)",
                    new_value="(prompt with examples appended)",
                    expected_impact="+5-10% task completion",
                    priority=1,
                ))
            if "add explicit think-then-act structure to prompt" not in tried:
                proposals.append(Proposal(
                    hypothesis="Chain-of-thought scaffolding helps on complex tasks",
                    change_description="Add explicit think-then-act structure to prompt",
                    section="SYSTEM_PROMPT",
                    old_value="(current prompt)",
                    new_value="(prompt with CoT scaffolding)",
                    expected_impact="+3-7% task completion",
                    priority=2,
                ))

        if "token" in weakness.lower():
            proposals.append(Proposal(
                hypothesis="Tighter compaction reduces token waste",
                change_description="Lower compaction_threshold_tokens to 15000",
                section="CONTEXT_STRATEGY",
                old_value="compaction_threshold_tokens: 20000",
                new_value="compaction_threshold_tokens: 15000",
                expected_impact="-15% token usage",
                priority=3,
            ))

        if "accuracy" in weakness.lower() or "routing" in weakness.lower():
            proposals.append(Proposal(
                hypothesis="More specific routing triggers reduce unnecessary tool calls",
                change_description="Add negative triggers to routing rules",
                section="ROUTING_RULES",
                old_value="(current rules)",
                new_value="(rules with negative patterns)",
                expected_impact="+5% tool accuracy",
                priority=2,
            ))

        if "strong" in weakness.lower() or "micro" in weakness.lower():
            if "lower temperature for deterministic output" not in tried:
                proposals.append(Proposal(
                    hypothesis="Lower temperature yields more consistent results",
                    change_description="Lower temperature for deterministic output",
                    section="TEMPERATURE",
                    old_value="0.0",
                    new_value="0.0",
                    expected_impact="+1-2% consistency",
                    risk_level="low",
                    priority=8,
                ))
            if "reduce token budget to improve efficiency" not in tried:
                proposals.append(Proposal(
                    hypothesis="Tighter token budget forces more efficient tool use",
                    change_description="Reduce token budget to improve efficiency",
                    section="TOKEN_BUDGET",
                    old_value="30000",
                    new_value="25000",
                    expected_impact="+2-5% token efficiency",
                    risk_level="medium",
                    priority=7,
                ))

    # Sort by priority (lower = higher priority)
    proposals.sort(key=lambda p: p.priority)
    return proposals


def propose_with_claude(context: ProposalContext, model: str = "claude-sonnet-4-20250514") -> list[Proposal]:
    """
    Use Claude Code as the proposer agent.

    Dispatches a prompt to Claude Code with full diagnostic context,
    asks it to analyze and propose specific changes to optimize.py.
    """
    prompt = f"""You are the Meta-Harness proposer. Analyze the current harness performance
and propose a SINGLE concrete change to optimize.py that will improve composite_score.

Current metrics:
{json.dumps(context.eval_metrics, indent=2)}

Experiment history (what's been tried):
{json.dumps(context.experiment_history, indent=2)}

Weaknesses identified:
{json.dumps(analyze_failures(context.eval_metrics))}

Current config sections available to modify:
- SYSTEM_PROMPT (instructions to Claude)
- TOOL_DEFINITIONS (tool schemas and hints)
- CONTEXT_STRATEGY (context window management)
- ROUTING_RULES (query to tool mapping)
- MODEL, TEMPERATURE, TOKEN_BUDGET, MAX_TURNS

Output a JSON object with:
{{"section": "...", "change": "...", "hypothesis": "...", "code_diff": "..."}}
"""

    # Dispatch to Claude Code on local machine
    claude_path = os.environ.get("CLAUDE_CODE_PATH", "claude")
    try:
        result = subprocess.run(
            [claude_path, "-p", prompt, "--output-format", "json"],
            capture_output=True, text=True, timeout=120,
        )
        if result.returncode == 0:
            # Claude Code --output-format json returns an envelope:
            #   {"type":"result", "result":"<claude's text response>", ...}
            # The actual proposal JSON is inside the "result" string field.
            envelope = json.loads(result.stdout)
            inner_text = envelope.get("result", "")

            # Extract JSON from Claude's response (may be wrapped in ```json blocks)
            inner_text = inner_text.strip()
            if "```json" in inner_text:
                inner_text = inner_text.split("```json", 1)[1]
                inner_text = inner_text.split("```", 1)[0]
            elif "```" in inner_text:
                inner_text = inner_text.split("```", 1)[1]
                inner_text = inner_text.split("```", 1)[0]

            response = json.loads(inner_text.strip())
            return [Proposal(
                hypothesis=response.get("hypothesis", "Claude-proposed change"),
                change_description=response.get("change", response.get("change_description", "")),
                section=response.get("section", "SYSTEM_PROMPT"),
                old_value="",
                new_value=response.get("code_diff", response.get("new_value", "")),
                expected_impact=response.get("expected_impact", "Claude-estimated"),
                priority=1,
            )]
    except (subprocess.TimeoutExpired, json.JSONDecodeError, FileNotFoundError, KeyError) as exc:
        print(f"Claude proposer failed: {exc}", file=sys.stderr)

    # Fall back to rule-based proposals
    return generate_proposals(context)
