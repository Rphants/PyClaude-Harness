# PyClaude-Harness — Autonomous Optimization

This is a Meta-Harness experiment: instead of optimizing model weights,
we optimize the **harness** around Claude — system prompts, tool definitions,
context management, and routing logic — using Claude itself as the optimizer.

Based on [Karpathy's autoresearch](https://github.com/karpathy/autoresearch)
pattern and the [Meta-Harness](https://arxiv.org/html/2603.28052v1) framework.

## Setup

To set up a new optimization run, work with the user to:

1. **Agree on a run tag**: propose a tag based on today's date (e.g. `apr1`). The branch `optimize/<tag>` must not already exist.
2. **Create the branch**: `git checkout -b optimize/<tag>` from current main.
3. **Read the in-scope files**:
   - `README.md` — project context
   - `prepare.py` — fixed evaluation harness. **Do not modify.**
   - `optimize.py` — the file you modify. System prompt, tool defs, context strategy, routing rules.
   - `src/` — the claw-code base (Python Claude Code rewrite). Read to understand the system you're optimizing.
   - `benchmarks/tasks/*.json` — the evaluation tasks
4. **Verify benchmark tasks exist**: Check `benchmarks/tasks/` has `.json` files. If empty, tell the human.
5. **Initialize results.tsv**: Create `results.tsv` with just the header row.
6. **Establish baseline**: Run `python prepare.py` on the current `optimize.py` without changes.
7. **Confirm and go**: Confirm setup looks good.

## What You're Optimizing

Unlike autoresearch (which optimizes model architecture), you optimize the **harness**:

| Surface | File Section | What It Controls |
|---------|-------------|-----------------|
| System prompt | `SYSTEM_PROMPT` | Instructions, guidelines, priorities |
| Tool definitions | `TOOL_DEFINITIONS` | Schemas, hints, priority ordering |
| Context strategy | `CONTEXT_STRATEGY` | Compaction, filtering, caching |
| Routing rules | `ROUTING_RULES` | Query → tool strategy mapping |
| Model params | `MODEL`, `TEMPERATURE`, `TOKEN_BUDGET`, `MAX_TURNS` | API config |

The goal: **maximize composite_score** (higher is better, range 0.0–1.0).

Composite score = 0.50 × task_completion + 0.25 × token_efficiency + 0.25 × tool_accuracy

## What You CAN Do

- Modify `optimize.py` — this is the only file you edit. Everything is fair game:
  system prompt wording, tool hints, context strategy params, routing rules, model selection.
- Read any file in the repo for context (especially `src/` to understand the claw-code system).
- Read `harness/` for Meta-Harness components that support the optimization loop.

## What You CANNOT Do

- Modify `prepare.py`. It is read-only. It contains the fixed evaluation.
- Modify benchmark task files in `benchmarks/tasks/`.
- Install new packages or add dependencies.
- Modify the composite_score formula.

## Output Format

After `python prepare.py`, you'll see:

```
---
composite_score:       0.625000
task_completion_rate:  0.7500
avg_token_efficiency:  22500.0
tool_accuracy:         0.8500
avg_latency_seconds:   0.002
total_tasks:           8
tasks_completed:       6
tasks_failed:          2
```

Extract the key metric: `grep "^composite_score:" run.log`

## Logging Results

Log every experiment to `results.tsv` (tab-separated):

```
commit	composite_score	tasks_completed	status	description
```

1. git commit hash (short, 7 chars)
2. composite_score (e.g. 0.625000) — use 0.000000 for crashes
3. tasks_completed / total_tasks (e.g. 6/8)
4. status: `keep`, `discard`, or `crash`
5. short description of what you tried

## The Experiment Loop

LOOP FOREVER:

1. Look at git state and results.tsv — understand what's been tried
2. Form a hypothesis about what might improve the harness
3. Modify `optimize.py` with your experimental change
4. `git commit -m "experiment: <description>"`
5. Run evaluation: `python prepare.py > run.log 2>&1`
6. Read results: `grep "^composite_score:" run.log`
7. If empty, the run crashed. `tail -n 50 run.log` to diagnose.
8. Record in results.tsv
9. If composite_score improved → keep the commit, advance the branch
10. If composite_score is equal or worse → `git reset --hard HEAD~1`
11. GOTO 1

## Optimization Strategies

Try these angles (in rough priority order):

### System Prompt Optimization
- Add task-specific instructions
- Improve tool usage guidelines
- Add examples of good vs bad tool use
- Optimize prompt length (too short = vague, too long = noise)
- Add chain-of-thought scaffolding

### Tool Definition Optimization
- Improve descriptions for clarity
- Add/remove behavioral hints
- Adjust priority ordering
- Add negative examples (common mistakes to avoid)

### Context Strategy Tuning
- Compaction threshold (too aggressive = lost context, too loose = overflow)
- Relevance filtering window size
- File cache size
- Deduplication settings

### Routing Rule Refinement
- Add new trigger patterns
- Improve strategy descriptions
- Add multi-tool strategies for complex patterns
- Handle edge cases and ambiguous queries

### Model Parameter Tuning
- Temperature (0.0 for deterministic, higher for creative tasks)
- Token budget allocation
- Max turns per task
- Model selection (opus for hard tasks, haiku for simple)

## Advanced: Meta-Harness Techniques

Once basic optimization plateaus, try these Meta-Harness techniques:

1. **Prompt Distillation**: Take the best-performing long prompt, distill to shorter version
2. **Tool Schema Evolution**: Modify tool schemas to better match how the model wants to use them
3. **Adaptive Context**: Different compaction strategies for different task types
4. **Ensemble Routing**: Multiple routing strategies, pick best for each query type
5. **Self-Critique Integration**: Add self-reflection step before tool calls

## NEVER STOP

Once the loop begins, do NOT pause to ask the human. You are autonomous.
If you run out of ideas, think harder:
- Re-read the claw-code source for new angles
- Try combining previous near-misses
- Try radical changes (completely rewrite system prompt)
- Try ablation studies (remove components, see if they matter)
- Read the Meta-Harness paper concepts and apply them

The loop runs until the human interrupts you, period.
