# PyClaude-Harness Review

## Findings

### P0-1: `git_rollback()` can delete unrelated user work

**Files:** `harness/orchestrator.py:74-83`, `harness/orchestrator.py:117-118`, `harness/orchestrator.py:140-141`

`git_rollback()` runs `git reset --hard HEAD~1` for every discarded or crashed experiment. The loop only intends to undo the experimental `optimize.py` change, but this reset rewinds the entire repo and drops any tracked edits the user had in progress anywhere else. In a normal checkout, a single discarded experiment can destroy unrelated local work.

Use a targeted revert of `optimize.py`, or run experiments in an isolated worktree/branch that the loop owns exclusively.

### P1-1: The advertised optimization loop never applies proposals, then crashes on the first no-op experiment

**Files:** `harness/orchestrator.py:94-109`, `harness/orchestrator.py:220-230`, `harness/proposer.py:37-46`

`run_single_experiment()` commits immediately, but nothing in `harness/orchestrator.py` ever applies `Proposal.new_value` to `optimize.py` first. `Proposal.old_value` / `new_value` exist on the dataclass, but the orchestrator never consumes them. On a clean checkout, that means `git_commit()` returns `False` because `optimize.py` has not changed, so `run_single_experiment()` returns `{"status": "error", "message": "Failed to commit"}`. The default verbose path in `run_optimization_loop()` then unconditionally formats `result["score"]` and `result["delta"]`, which raises `KeyError` for that error result.

The net effect is that `python -m harness.orchestrator` cannot complete its first experiment unless some outside process edits `optimize.py` first and the caller also avoids the error path.

### P1-2: `tool_accuracy` is effectively hardcoded to `1.0`

**Files:** `prepare.py:195-197`, `prepare.py:238-241`

`evaluate_task()` sets `tools_called` to either `list(task.expected_tools)` or `[]`. `unnecessary_tools` is then computed by filtering `tools_called` for entries not in `task.expected_tools`, which can never produce anything except `[]`. `evaluate_all()` therefore computes `tool_accuracy` as `1.0` for every configuration, including ones with zero tool definitions.

That breaks a full 25% of the composite score and makes the optimizer blind to bad routing/tool-choice regressions.

### P1-3: Proposal de-duplication never matches the strings the loop actually logs

**Files:** `harness/proposer.py:93-110`, `harness/orchestrator.py:104`, `harness/orchestrator.py:137-148`

The proposer tries to avoid repeats by building `tried = {exp.get("description", "") ...}` from `results.tsv`, but the guards compare against different hard-coded strings: `"add examples to system prompt"` and `"add chain of thought"`. The orchestrator logs `proposal.change_description` instead, e.g. `Add tool usage examples to SYSTEM_PROMPT`.

Because those strings never match, previously discarded experiments are proposed again as if they were new. In a long-running optimization loop, that wastes iterations on the same failed edits instead of exploring new changes.
