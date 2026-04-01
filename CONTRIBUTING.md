# Contributing to PyClaude-Harness

## Running evaluations

Evaluate the current harness configuration against all benchmark tasks:

```bash
python prepare.py
```

Output as JSON:

```bash
python prepare.py --json
```

The composite score (0.0–1.0) is the primary metric. Higher is better.

## Running the optimization loop

The orchestrator runs an autonomous propose-evaluate-keep/discard loop:

```bash
python -m harness.orchestrator --max-experiments 10
```

To use Claude Code as the proposer agent:

```bash
python -m harness.orchestrator --use-claude --max-experiments 10
```

Results are logged to `results.tsv`.

## Adding benchmark tasks

1. Create a JSON file in `benchmarks/tasks/` (e.g., `09_my_task.json`).
2. Follow the naming convention: `NN_description.json` with zero-padded numbers.
3. Required fields:

```json
{
  "name": "unique_task_name",
  "description": "What this task evaluates",
  "prompt": "The prompt given to the agent",
  "expected_tools": ["Read", "Grep"],
  "success_criteria": "How to judge success",
  "category": "search",
  "difficulty": "medium",
  "max_turns": 10
}
```

4. Run `python prepare.py` to verify the task loads and evaluates.

## Writing tests

Tests use pytest and live in `tests/`.

```bash
python -m pytest tests/ -v
```

- `tests/test_prepare.py` — tests for the evaluation harness (`prepare.py`)
- `tests/test_harness.py` — tests for proposer, evaluator, and orchestrator

When adding tests:
- Use plain pytest style (no `unittest.TestCase`)
- Group related tests in classes
- Use `tmp_path` and `monkeypatch` fixtures for isolation
- Tests must pass without network access or API keys

## Branch naming conventions

- `main` — stable baseline with passing CI
- `optimize/<tag>` — experiment branches created by the optimization loop (e.g., `optimize/apr1`)
