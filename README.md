# PyClaude-Harness

Self-improving harness optimization for Claude Code, combining:

- **[claw-code](https://github.com/instructkr/claw-code)** — Python rewrite of Claude Code (100K+ stars)
- **[Meta-Harness](https://arxiv.org/html/2603.28052v1)** — Optimize the harness around AI models, not the weights
- **[autoresearch](https://github.com/karpathy/autoresearch)** — Karpathy's autonomous research framework

## The Idea

Traditional ML optimizes model weights. Meta-Harness optimizes everything *around* the model:
system prompts, tool definitions, context management, and routing logic. PyClaude-Harness uses
Claude itself as the optimizer, running autonomous experiment loops that modify the harness,
evaluate against benchmarks, and keep only improvements.

## Architecture

```
PyClaude-Harness/
├── src/                    # claw-code base (Python Claude Code rewrite)
│   ├── query_engine.py     # Query routing and execution
│   ├── tools.py            # Tool definitions and execution
│   ├── runtime.py          # Runtime session management
│   ├── context.py          # Context window management
│   └── ...                 # 40+ modules
├── harness/                # Meta-Harness optimization engine
│   ├── proposer.py         # Proposes changes (uses Claude as optimizer)
│   ├── evaluator.py        # Runs benchmarks, diagnostics
│   └── orchestrator.py     # Autonomous experiment loop
├── benchmarks/
│   └── tasks/              # Evaluation tasks (JSON)
├── prepare.py              # Fixed evaluation harness (READ-ONLY)
├── optimize.py             # Agent-editable harness config (THE OPTIMIZATION TARGET)
└── program.md              # Autonomous agent instructions (autoresearch pattern)
```

## How It Works

1. **`prepare.py`** (read-only) — Fixed evaluation. Runs benchmark tasks against the harness config and computes `composite_score` (0.0–1.0).

2. **`optimize.py`** (agent-editable) — The optimization target. Contains system prompt, tool definitions, context strategy, routing rules, and model parameters.

3. **`program.md`** — Agent instructions. Tells Claude Code to run an autonomous experiment loop: modify optimize.py → evaluate → keep/discard → repeat forever.

4. **`harness/`** — Meta-Harness components that support the optimization loop with intelligent proposal generation and rich diagnostics.

## Quick Start

```bash
# Clone
git clone https://github.com/Rphants/PyClaude-Harness.git
cd PyClaude-Harness

# Establish baseline
python prepare.py

# Run optimization loop (rule-based proposer)
python -m harness.orchestrator --max-experiments 20

# Run with Claude as the proposer (requires Claude Code CLI)
python -m harness.orchestrator --use-claude --max-experiments 50

# Or use Claude Code directly with the program.md instructions
claude -p "$(cat program.md)" --dangerously-skip-permissions
```

## Composite Score

```
composite_score = 0.50 × task_completion + 0.25 × token_efficiency + 0.25 × tool_accuracy
```

The goal is to maximize this score by optimizing the harness configuration.

## Adding Benchmark Tasks

Add JSON files to `benchmarks/tasks/`:

```json
{
  "name": "my_task",
  "description": "What this task tests",
  "prompt": "The prompt given to the agent",
  "expected_tools": ["Read", "Edit"],
  "success_criteria": "How to judge success",
  "category": "edit",
  "difficulty": "medium"
}
```

## License

MIT
