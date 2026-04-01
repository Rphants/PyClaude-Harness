"""
PyClaude-Harness optimization target. THIS IS THE FILE THE AGENT MODIFIES.

Like train.py in autoresearch, this file contains everything the autonomous
agent can change to improve the harness performance. The agent proposes changes,
runs `python prepare.py`, checks composite_score, and keeps or discards.

Sections the agent can modify:
  1. SYSTEM_PROMPT      — The system prompt sent to Claude
  2. TOOL_DEFINITIONS   — Tool schemas, descriptions, parameter hints
  3. CONTEXT_STRATEGY   — How context window is managed (compaction, filtering)
  4. ROUTING_RULES      — How queries are routed to tools/commands
  5. TOKEN_BUDGET       — Per-task token allocation
  6. TEMPERATURE        — Sampling temperature
  7. MODEL              — Which Claude model to use
  8. MAX_TURNS          — Max agent turns per task
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Model configuration
# ---------------------------------------------------------------------------

MODEL = "claude-sonnet-4-20250514"
TEMPERATURE = 0.0
TOKEN_BUDGET = 1
MAX_TURNS = 15

# ---------------------------------------------------------------------------
# System prompt — the core harness optimization surface
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You are Claude, an AI assistant built by Anthropic. You help users
accomplish tasks by using available tools effectively and efficiently.

Guidelines:
- Think step by step before acting
- Use the minimum number of tool calls needed
- Prefer precise, targeted tool use over broad exploration
- When reading files, only read the sections you need
- When searching, use specific patterns rather than broad queries
- Complete the task fully before responding to the user
- If you encounter an error, diagnose it before retrying

Tool usage priorities:
1. Read/Glob/Grep for information gathering
2. Edit for modifying existing files (prefer over Write for changes)
3. Write for creating new files
4. Bash for running commands, tests, builds
5. Agent for complex multi-step subtasks

Context management:
- Keep track of what you've already learned
- Don't re-read files you've already seen
- Summarize findings as you go to stay within context limits
"""

# ---------------------------------------------------------------------------
# Tool definitions — schemas and behavioral hints
# ---------------------------------------------------------------------------

TOOL_DEFINITIONS = {
    "Read": {
        "description": "Read file contents with optional line range",
        "priority": "high",
        "hints": [
            "Use offset/limit for large files",
            "Read once, reference from memory after",
        ],
    },
    "Edit": {
        "description": "Replace exact string matches in files",
        "priority": "high",
        "hints": [
            "Always Read before Edit",
            "Use unique strings for old_string",
            "Preserve exact indentation",
        ],
    },
    "Write": {
        "description": "Create new files or complete rewrites",
        "priority": "medium",
        "hints": [
            "Prefer Edit for modifications",
            "Use for new file creation only",
        ],
    },
    "Bash": {
        "description": "Execute shell commands",
        "priority": "medium",
        "hints": [
            "Prefer Read/Grep/Glob over cat/grep/find",
            "Use && to chain dependent commands",
            "Quote paths with spaces",
        ],
    },
    "Grep": {
        "description": "Search file contents with regex",
        "priority": "high",
        "hints": [
            "Use glob param to filter file types",
            "Use files_with_matches mode for discovery",
            "Use content mode with context for reading",
        ],
    },
    "Glob": {
        "description": "Find files by name patterns",
        "priority": "high",
        "hints": [
            "Use ** for recursive matching",
            "Results sorted by modification time",
        ],
    },
    "Agent": {
        "description": "Launch sub-agents for complex tasks",
        "priority": "low",
        "hints": [
            "Use for multi-step research tasks",
            "Provide complete task description",
            "Launch multiple in parallel when independent",
        ],
    },
}

# ---------------------------------------------------------------------------
# Context strategy — how the context window is managed
# ---------------------------------------------------------------------------

CONTEXT_STRATEGY = {
    "compaction_enabled": True,
    "compaction_threshold_tokens": 20_000,
    "relevance_filtering": True,
    "relevance_window": 5,           # Keep last N turns in full
    "summarize_older_turns": True,
    "max_file_cache_entries": 10,
    "dedup_tool_results": True,
}

# ---------------------------------------------------------------------------
# Routing rules — how queries map to tool strategies
# ---------------------------------------------------------------------------

ROUTING_RULES = {
    "file_search": {
        "triggers": ["find", "locate", "where is", "search for file"],
        "strategy": "Glob first, then Read targeted results",
    },
    "code_search": {
        "triggers": ["search for", "grep", "find usage", "references to"],
        "strategy": "Grep with specific patterns, then Read context",
    },
    "file_edit": {
        "triggers": ["change", "modify", "update", "fix", "edit"],
        "strategy": "Read target file, then Edit with precise old_string",
    },
    "file_create": {
        "triggers": ["create", "write", "new file", "generate"],
        "strategy": "Check if exists with Glob, then Write",
    },
    "run_command": {
        "triggers": ["run", "execute", "test", "build", "install"],
        "strategy": "Bash with appropriate timeout",
    },
}
