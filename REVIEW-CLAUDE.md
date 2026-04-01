# PyClaude-Harness — Critical Self-Review (v2)

**Reviewer:** Claude Opus 4.6 (the same model that built this repo)
**Date:** 2026-04-01
**Verdict:** Well-structured scaffolding around a hollow core. The evaluator measures string length, not Claude performance. The optimization loop cannot execute. The claw-code port is 40% dead placeholders. This repo demonstrates the architecture of a self-improving harness but cannot actually self-improve.

---

## P0 — Critical: Broken Core Logic

### P0-1: `evaluate_task()` never calls Claude — scores on heuristics

**`prepare.py:149-210`**

The function that should evaluate Claude's task performance instead scores the *config structure* with arithmetic:

```python
prompt_score = min(len(system_prompt) / 2000, 1.0)       # reward long prompts
tool_coverage = covered / len(task.expected_tools)         # reward matching dict keys
routing_score = min(len(routing) / 5, 1.0) * 0.3          # reward more routing rules
context_score = 0.7 if compaction_enabled else 0.5         # reward toggling a bool
```

**Consequences:**
- `composite_score` measures "how padded is your config" — not how well Claude performs
- The `time.time()` latency (`prepare.py:157,199`) measures ~20 lines of Python math, always <1ms
- The entire optimization loop optimizes for **prompt length and dict size**
- No Claude API call is ever made anywhere in the repo

### P0-2: `unnecessary_tools` always empty → `tool_accuracy` hardcoded to 1.0

**`prepare.py:195-197`**

```python
tools_called = list(task.expected_tools) if tool_coverage > 0.5 else []
unnecessary = [t for t in tools_called if t not in task.expected_tools]
```

`tools_called` is a copy of `expected_tools`. Filtering for items NOT in `expected_tools` always yields `[]`. The 25% composite weight on tool_accuracy (`prepare.py:89`) is dead — it contributes a fixed `0.25` regardless of config quality.

### P0-3: `load_harness_config()` executes arbitrary Python

**`prepare.py:128-132`**

```python
spec.loader.exec_module(module)  # Arbitrary code execution
```

The design encourages an autonomous agent to modify `optimize.py` and then run `prepare.py`. An adversarial or buggy agent could inject `import os; os.system("rm -rf /")` into `optimize.py` and it would execute with full OS permissions.

**Fix:** Parse `optimize.py` as TOML/YAML config data, not executable code.

### P0-4: `git reset --hard` destroys uncommitted work

**`harness/orchestrator.py:74-83`**

The orchestrator logs to `results.tsv` via `log_result()` *before* deciding to rollback. On rollback, `git reset --hard HEAD~1` destroys the uncommitted `results.tsv` changes. Every discarded experiment loses its log entry.

**Fix:** Use `git checkout -- optimize.py` to revert only the target file, or commit `results.tsv` alongside.

### P0-5: `run.log` shows `composite_score: 1.000000` — the evaluator is already gamed

**`run.log:3-4`**

```
composite_score:       1.000000
task_completion_rate:  1.0000
```

The current `optimize.py` already achieves a *perfect score*. The system prompt is >2000 chars (`prompt_score=1.0`), all 7 tool keys exist (`tool_coverage=1.0`), 5 routing rules (`routing_score=0.3`), and `relevance_filtering=True` (`context_score=0.85`). Combined: `completion_prob ≈ 0.77 > 0.5` → all tasks pass. With `TOKEN_BUDGET=30000` and `tool_accuracy=1.0` always, the score is maxed.

**The optimization loop has nowhere to go. It starts at 1.0.**

---

## P1 — Important: The Optimization Loop Cannot Execute

### P1-1: The proposer never modifies `optimize.py`

**`harness/orchestrator.py:106-108`**

```python
# Apply the change (in production, this modifies optimize.py)
# For now, we assume the caller has already modified optimize.py
```

`Proposal.old_value` and `Proposal.new_value` contain placeholder strings like `"(current prompt)"` and `"(prompt with examples appended)"`. No code applies proposals to the file.

### P1-2: The orchestrator crashes on first experiment

**`harness/orchestrator.py:220-230`**

Since no file changes occur, `git_commit()` returns `False`, `run_single_experiment()` returns `{"status": "error"}`. The verbose output path then accesses `result["score"]` and `result["delta"]`, which raises `KeyError`.

### P1-3: Proposal de-duplication uses mismatched strings

**`harness/proposer.py:93-110`**

The proposer checks `tried` against strings like `"add examples to system prompt"`, but the orchestrator logs `proposal.change_description` (e.g., `"Add tool usage examples to SYSTEM_PROMPT"`). Case and wording differ. De-duplication never fires — the same failed experiments repeat forever.

### P1-4: `TOKEN_BUDGET = 1` achieves near-perfect efficiency score

**`prepare.py:190-192`**

```python
base_tokens = config.get("token_budget", MAX_TOKENS_PER_TASK)
tokens_used = int(base_tokens * efficiency_factor)
```

Token efficiency = `(1.0 - tokens_used / 50000) * 0.25`. Setting `TOKEN_BUDGET=1` gives `tokens_used=0`, contributing `0.25` to composite score. No floor check exists.

### P1-5: Tasks evaluated 3× per experiment

**`harness/evaluator.py:63-68` + `orchestrator.py:115-123`**

`run_evaluation()` calls `evaluate_task()` per-task, then `evaluate_all()` re-runs all tasks. The orchestrator calls both `evaluate_composite()` and `run_evaluation()`. Total: 3× evaluation per experiment. Harmless with heuristics, catastrophic with real API calls.

### P1-6: `results.tsv` has duplicate baseline entries

**`results.tsv`**

```
8ccabe2	0.913750	8/8	keep	baseline
8ccabe2	0.913750	8/8	keep	baseline
```

Two identical baseline rows. And the score is `0.913750` in the TSV but `1.000000` in `run.log` — they were computed at different times or with different configs. No reconciliation.

---

## P2 — Design: The claw-code Port is 40% Placeholder

### P2-1: 31 package `__init__.py` files are cargo-cult stubs

Every package under `src/` (`assistant/`, `bootstrap/`, `bridge/`, `buddy/`, `cli/`, `components/`, `constants/`, `coordinator/`, `entrypoints/`, `hooks/`, `keybindings/`, `memdir/`, `migrations/`, `moreright/`, `native_ts/`, `outputStyles/`, `plugins/`, `remote/`, `schemas/`, `screens/`, `server/`, `services/`, `skills/`, `state/`, `types/`, `upstreamproxy/`, `utils/`, `vim/`, `voice/`) contains:

```python
ARCHIVE_NAME, MODULE_COUNT, PORTING_NOTE = "...", N, "..."
```

- No functional code in any of them
- `ARCHIVE_NAME`, `MODULE_COUNT`, `PORTING_NOTE` are never imported or used anywhere
- ~496 lines of dead boilerplate that creates a false impression of completeness

### P2-2: Dead code in functional modules

| File | Issue |
|------|-------|
| `src/query.py` | `QueryRequest`, `QueryResponse` dataclasses — never imported |
| `src/replLauncher.py` | `build_repl_banner()` — never called, returns "not interactive yet" |
| `src/interactiveHelpers.py` | `bulletize()` — never imported or called |
| `src/task.py` | Re-exports `PortingTask` but nothing imports from here |

### P2-3: Naive token counting — off by ~30%

**`src/models.py:33-37`**

```python
def add_turn(self, prompt: str, output: str) -> 'UsageSummary':
    return UsageSummary(
        input_tokens=self.input_tokens + len(prompt.split()),
        output_tokens=self.output_tokens + len(output.split()),
    )
```

`len(str.split())` counts whitespace-delimited words, not BPE tokens. Real tokenization averages ~1.3 tokens/word. All cost tracking and budget enforcement is systematically wrong.

### P2-4: Permission system only blocks Bash

**`src/runtime.py:169-174`**

```python
if match.kind == 'tool' and 'bash' in match.name.lower():
    denials.append(PermissionDenial(...))
```

Only tools with "bash" in the name are denied. Write, Edit, Agent, and all other potentially destructive tools pass through unchecked.

### P2-5: Benchmark tasks reference fictional code

All 8 tasks reference entities that don't exist in this repo:
- `QueryEngineConfig` class (tasks 03, 04)
- `QueryEnginePort` (task 04 — renaming)
- `load_session` function (task 02)
- `src/cache.py` (task 05 — creating it)
- A test suite that has "failing tests" (task 06)
- A `KeyError: 'session_id'` bug (task 07)

Even with a real evaluator, these tasks can't execute against the actual codebase.

### P2-6: No `__init__.py` in `harness/` — imports use sys.path hacks

**`harness/evaluator.py:18`, `harness/orchestrator.py:26`**

```python
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
```

Fragile path manipulation instead of proper package structure. Will break with standard tooling (`pip install -e .`, etc.).

---

## P3 — Minor Issues

### P3-1: CI doesn't run the optimization loop

**`.github/workflows/ci.yml`** — Runs `pytest` and `python prepare.py` but never `python -m harness.orchestrator`. The orchestrator has never been validated in CI.

### P3-2: `CONTRIBUTING.md` and `LICENSE` exist but no `.editorconfig` or type checking

No `mypy`, `ruff`, or `pyright` config despite 95%+ type hint coverage. The type hints are decorative — never validated.

### P3-3: `run.log` and `results.tsv` are committed but should be gitignored

These are ephemeral run artifacts. Committing them creates merge conflicts between experiment branches.

### P3-4: `program.md` instructs the agent to "NEVER STOP" and "do NOT pause"

This combined with `--dangerously-skip-permissions` in the README quick-start is a recipe for runaway execution against a gameable evaluator.

### P3-5: `pyproject.toml` declares scripts but no dependencies

```toml
[project.scripts]
pyclaude-eval = "prepare:main"
```

No `[project.dependencies]` section. `pip install` would succeed but the entry point might fail if any future dependency is added.

---

## What Works

1. **Architecture decomposition** — proposer → evaluator → orchestrator is the right pattern
2. **Test coverage** — 28 tests covering happy paths for prepare.py, proposer, evaluator, orchestrator
3. **Type hints** — 95%+ annotated, clean dataclass design throughout
4. **`program.md`** — Clear, well-written autonomous loop specification following the autoresearch pattern
5. **Benchmark task format** — JSON schema is clean and extensible
6. **CI pipeline** — Tests, compile checks, and evaluation run on push

---

## What's Needed to Make This Real

### Phase 1: Make it honest (1 day)
1. Replace heuristic `evaluate_task()` with real Claude API calls via `claude -p`
2. Create `fixtures/sample_project/` with the code the benchmark tasks reference
3. Implement programmatic judges for each task's `success_criteria`
4. Decouple token scoring from `TOKEN_BUDGET` config value

### Phase 2: Make it work (1 day)
5. Implement `apply_proposal()` — actually modify `optimize.py` from proposals
6. Convert `optimize.py` to TOML/YAML (eliminate code execution risk)
7. Fix `git_rollback()` to only revert `optimize.py`, not nuke the tree
8. Add `harness/__init__.py`, remove `sys.path` hacks

### Phase 3: Make it smart (2 days)
9. Use Claude as judge for open-ended tasks
10. Add cost tracking and caching (hash config+task → skip re-eval)
11. Implement adaptive task selection (skip tasks the config already passes)
12. Meta-learning: analyze which change types help vs hurt

---

## Comparison with Codex Review (REVIEW-CODEX.md)

Both reviews converge on:
- `git reset --hard` destroys work (P0 in both)
- `tool_accuracy` hardcoded to 1.0 (P1 in both)
- Orchestrator never applies proposals (P1 in both)
- Proposal de-duplication string mismatch (P1 in Codex, confirmed here)

This review additionally covers:
- The evaluator is already gamed to 1.0 (P0-5)
- claw-code src/ analysis (40% dead placeholders, naive tokenization, incomplete permissions)
- Benchmark tasks reference non-existent code
- Triple evaluation per experiment
- Security implications of `exec_module()` in detail

---

*Generated by Claude Opus 4.6 as critical self-review. Findings are consistent with CLAUDE.md known issues and independently corroborated by Codex/GPT-5.4 review.*
