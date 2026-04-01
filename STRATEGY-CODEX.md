# PyClaude-Harness Strategy Session

## What Claude Says

Claude's self-review in `REVIEW-CLAUDE.md` is directionally right on the biggest issue:
the current loop is optimizing a simulated score, not Claude's real behavior.

Key points I agree with:

- `prepare.py` uses heuristic scoring instead of actually running Claude.
- `tool_accuracy` is effectively pinned to `1.0`.
- `load_harness_config()` executes arbitrary Python from `optimize.py`.
- `git reset --hard HEAD~1` is too destructive for an autonomous loop.

## What Codex Adds

The repo is not as hollow as the harshest version of that review suggests.

- The benchmark tasks are mostly aligned with real symbols in `src/`.
  `QueryEngineConfig`, `QueryEnginePort`, and `load_session` do exist.
- The task set is only partially synthetic. `src/cache.py` is intentionally absent
  because one task is explicitly about creating it.
- The real structural gap is not "the tasks are fake". The real gap is that
  the evaluator never observes real task execution.

## Comparison To Autoresearch

The adjacent clone at `../autoresearch` makes the core contrast obvious.

Autoresearch works because it has:

1. One mutable surface: `train.py`
2. One fixed evaluator: real training + real validation metric
3. One honest score: `val_bpb`

PyClaude-Harness copied the outer form:

1. One mutable surface: `optimize.py`
2. One fixed evaluator: `prepare.py`
3. One optimization loop: `harness/orchestrator.py`

But it missed the critical part:

- `prepare.py` does not run Claude or judge actual outputs.
- The loop therefore optimizes prompt length, dictionary coverage, and token budget heuristics.

## Brilliant Move

Do not "improve the prompt" yet.

First, pivot the repo so it becomes the harness analogue of autoresearch:
an honest measurement loop around a single mutable harness file.

That means:

1. Keep `optimize.py` as the only editable optimization surface.
2. Turn `prepare.py` into a real evaluator that runs Claude Code on benchmark tasks.
3. Score actual task success, actual token usage, and actual tool behavior.

## Concrete Plan

### Phase 1: Make The Evaluator Honest

- Create a small fixture project under `fixtures/sample_project/`.
- Make benchmark tasks run against that fixture project, not against heuristics.
- Execute Claude Code in a subprocess for each task.
- Record:
  - success/failure
  - token usage
  - tool calls
  - wall time

### Phase 2: Make The Loop Safe

- Replace `exec_module()` config loading with a data-only config format, or at least
  sandbox config evaluation in a subprocess.
- Replace `git reset --hard HEAD~1` with a targeted revert of `optimize.py`.
- Persist experiment logs in a way that survives failed experiments.

### Phase 3: Make It Truly Autoresearch-Like

- Freeze the evaluator contract.
- Keep only one mutable harness file.
- Run many short experiments over real Claude behavior.
- Let the optimization loop search the harness space, not a toy scoring function.

## Immediate Recommendation

Ignore prompt tuning for now.

The highest-leverage next milestone is:

**Replace the simulated evaluator with a real Claude Code benchmark runner over a fixture repo.**

Until that exists, every improvement is suspect, because the current `0.913750`
baseline is mostly an artifact of heuristic scoring rather than evidence of better agent performance.

## Evidence

- `prepare.py` heuristic evaluation: lines 149-210
- `prepare.py` arbitrary code execution: lines 126-132
- `harness/orchestrator.py` destructive rollback: lines 74-83 and 139-141
- `src/query_engine.py` contains `QueryEngineConfig` and `QueryEnginePort`: lines 15-38
- `src/session_store.py` contains `load_session`: lines 27-35
- `benchmarks/tasks/03_file_edit.json` targets `QueryEngineConfig`
- `benchmarks/tasks/04_multi_file_refactor.json` targets `QueryEnginePort`
- `benchmarks/tasks/05_new_file_create.json` intentionally targets missing `src/cache.py`
