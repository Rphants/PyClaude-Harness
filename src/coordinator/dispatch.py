"""CMUX Dispatch — The single entrypoint for all agent work.

COWORK uses this to:
1. Check agent health before dispatching
2. Assign task via CMUX
3. Wrap agent launch with auto-heartbeat
4. Monitor for ACK within deadline

Usage:
    # Dispatch Codex-1 to review heartbeat system
    python -m src.coordinator.dispatch \
        --agent codex-1 \
        --task "Review src/coordinator/heartbeat.py, ack.py, monitor.py" \
        --branch fix/codex-p0-review \
        --runner "codex exec --full-auto" \
        --brief /tmp/codex-review-brief.txt

    # Dispatch Claude-1 to build a feature
    python -m src.coordinator.dispatch \
        --agent claude-1 \
        --task "Add audio demo component to landing page" \
        --branch feat/audio-demo \
        --runner "claude -p" \
        --brief /tmp/claude-brief.txt

    # Check dispatch readiness only (dry run)
    python -m src.coordinator.dispatch \
        --agent claude-1 \
        --task "test" \
        --dry-run

The dispatch wrapper does NOT run the agent itself — it generates
the shell command with heartbeat wrapping for the orchestrator to execute.
"""

from __future__ import annotations

import argparse
import json
import sys
import textwrap
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import shlex

from .cmux import JsonlMux, DEFAULT_CMUX_PATH, _utc_now
from .monitor import is_dispatchable, KNOWN_AGENTS
from .heartbeat import emit_heartbeat


def dispatch(
    mux: JsonlMux,
    agent: str,
    task: str,
    *,
    branch: str | None = None,
    runner: str = "claude -p",
    brief_path: str | None = None,
    force: bool = False,
    dry_run: bool = False,
) -> dict:
    """
    Full dispatch flow:
    1. Health check (skip if force=True)
    2. Publish task.assign to CMUX
    3. Generate wrapped launch command with auto-heartbeat
    """
    correlation_id = f"{task[:30].replace(' ', '-').lower()}-{uuid4().hex[:8]}"
    result: dict = {
        "agent": agent,
        "task": task,
        "correlation_id": correlation_id,
        "dispatched": False,
    }

    # Step 1: Health check
    if not force:
        health = is_dispatchable(mux, agent)
        result["health_check"] = health

        if not health["dispatchable"]:
            # Check if agent is dead/never-seen — that's OK for first dispatch
            cmux_check = health["checks"].get("cmux_presence", {})
            if not cmux_check.get("pass", False):
                # Agent never seen — allow first dispatch
                result["health_check"]["override"] = "first-dispatch: agent never seen, allowing"
            else:
                result["dispatched"] = False
                result["reason"] = "Agent failed health check"
                return result

    if dry_run:
        result["dry_run"] = True
        result["reason"] = "Dry run — no task assigned"
        return result

    # Step 2: Publish task.assign
    envelope = mux.publish(
        sender="cowork",
        recipient=agent,
        kind="task.assign",
        payload={
            "task": task,
            "branch": branch,
            "status": "assigned",
            "proof": "idea",
        },
        correlation_id=correlation_id,
    )
    result["assignment"] = envelope.to_dict()
    result["dispatched"] = True

    # Step 3: Generate launch command with heartbeat wrapping
    result["launch_command"] = generate_launch_command(
        agent=agent,
        runner=runner,
        brief_path=brief_path,
        correlation_id=correlation_id,
        branch=branch,
        task=task,
    )

    return result


def generate_launch_command(
    agent: str,
    runner: str,
    brief_path: str | None,
    correlation_id: str,
    branch: str | None,
    task: str,
) -> str:
    """
    Generate a shell command that:
    1. Emits a STARTING heartbeat
    2. Runs the agent
    3. Emits a DONE/FAILED heartbeat based on exit code

    All user-supplied strings are shell-escaped via shlex.quote().
    """
    # Sanitize all user-controlled inputs
    safe_agent = shlex.quote(agent)
    safe_task = shlex.quote(task)
    safe_task_short = shlex.quote(task[:80])
    safe_task_shorter = shlex.quote(f"EXIT $EXIT_CODE: {task[:60]}")
    safe_corr = shlex.quote(correlation_id)

    hb_base = (
        f'python -m src.coordinator.heartbeat '
        f'--sender {safe_agent} '
        f'--correlation-id {safe_corr}'
    )

    branch_flag = f" --branch {shlex.quote(branch)}" if branch else ""

    # Build the agent command
    if brief_path:
        safe_brief = shlex.quote(brief_path)
        if "codex" in runner:
            agent_cmd = f'{runner} "$(cat {safe_brief})"'
        else:
            agent_cmd = f'{runner} "$(cat {safe_brief})" --dangerously-skip-permissions'
    else:
        if "codex" in runner:
            agent_cmd = f'{runner} {safe_task}'
        else:
            agent_cmd = f'{runner} {safe_task} --dangerously-skip-permissions'

    # Comment-safe versions (strip shell metacharacters for comments only)
    comment_task = task[:80].replace('\n', ' ').replace('"', "'")
    comment_agent = agent.replace('\n', ' ')

    script = textwrap.dedent(f"""\
        # === COWORK DISPATCH: {comment_agent} ===
        # Task: {comment_task}
        # Correlation: {correlation_id}
        # Runner: {runner}
        cd ~/Downloads/PyClaude-Harness

        # Heartbeat: STARTING
        {hb_base} --status working --claim {safe_task_short}{branch_flag} --proof idea

        # Run agent
        {agent_cmd} 2>&1 | tee /tmp/{safe_agent}-run.log
        EXIT_CODE=$?

        # Heartbeat: DONE or FAILED
        if [ $EXIT_CODE -eq 0 ]; then
            {hb_base} --status done --claim {safe_task_short}{branch_flag} --proof worktree-pass
        else
            {hb_base} --status blocked --claim {safe_task_shorter}{branch_flag}
        fi

        echo "=== {comment_agent} dispatch complete (exit $EXIT_CODE) ==="
    """)

    return script


# --- Batch Dispatch ---

def dispatch_plan(
    mux: JsonlMux,
    assignments: list[dict],
    *,
    force: bool = False,
) -> list[dict]:
    """
    Dispatch multiple agents in parallel.
    Each assignment dict needs: agent, task, and optionally branch, runner, brief_path.
    Returns list of dispatch results.
    """
    results = []
    for assignment in assignments:
        result = dispatch(
            mux,
            agent=assignment["agent"],
            task=assignment["task"],
            branch=assignment.get("branch"),
            runner=assignment.get("runner", "claude -p"),
            brief_path=assignment.get("brief_path"),
            force=force,
        )
        results.append(result)
    return results


# --- CLI ---

def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="CMUX Dispatch — assign and launch agents")
    parser.add_argument("--agent", required=True, help="Agent callsign")
    parser.add_argument("--task", required=True, help="Task description")
    parser.add_argument("--branch", default=None, help="Git branch")
    parser.add_argument("--runner", default="claude -p", help="Agent runner command")
    parser.add_argument("--brief", default=None, help="Path to brief file")
    parser.add_argument("--force", action="store_true", help="Skip health check")
    parser.add_argument("--dry-run", action="store_true", help="Check only, don't dispatch")
    parser.add_argument("--cmux-path", default=str(DEFAULT_CMUX_PATH))

    args = parser.parse_args(argv)
    mux = JsonlMux(Path(args.cmux_path))

    result = dispatch(
        mux,
        agent=args.agent,
        task=args.task,
        branch=args.branch,
        runner=args.runner,
        brief_path=args.brief,
        force=args.force,
        dry_run=args.dry_run,
    )

    print(json.dumps(result, indent=2))
    if not result["dispatched"] and not result.get("dry_run"):
        sys.exit(1)


if __name__ == "__main__":
    main()
