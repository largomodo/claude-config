"""Serena tool policy constants for sub-agent Task instructions.

Mirrors conventions/code-navigation.md (Tier 3) as Python constants because
sub-agents obey script stdout during planner runs, not agent prose; loading
the convention via get_convention() would need a REGISTRY.yaml entry per
role and cost ~400 tokens per step. Two precomposed preambles (read, edit)
cover both variants; skills/README.md forbids prompt-fragment builder
functions in the shared lib, so no serena_preamble(edit: bool) function
exists here. tests/test_serena_policy.py enforces the mirror in both
directions: every tool name in the tuples below appears in the convention,
prefixed, and every mcp__serena__-prefixed name in the convention resolves
to one of these constants' real tool names.
"""

# ============================================================================
# CONFIGURATION
# ============================================================================

# The four tuples below partition the 21 mcp__serena__ tool names deployed
# by Serena's claude-code context (6 + 7 + 2 + 6). Source: serena/resources/
# config/contexts/claude-code.yml (excluded_tools) and serena/agent.py
# SingleProjectExclusions, which removes activate_project and
# get_current_config when single_project mode is set (it is, here) -- those
# two names are never listed anywhere in this module.

SERENA_TOOL_PREFIX = "mcp__serena__"

SERENA_READ_TOOLS = (
    "get_symbols_overview",
    "find_symbol",
    "find_referencing_symbols",
    "find_declaration",
    "find_implementations",
    "get_diagnostics_for_file",
)

SERENA_EDIT_TOOLS = (
    "replace_symbol_body",
    "insert_before_symbol",
    "insert_after_symbol",
    "replace_content",
    "replace_in_files",
    "rename_symbol",
    "safe_delete_symbol",
)

SERENA_MEMORY_READ_TOOLS = (
    "list_memories",
    "read_memory",
)

# Never granted to a sub-agent: these drive the main session's own Serena
# setup, and parallel sub-agents writing/renaming/deleting the same memory
# would race and corrupt shared project knowledge.
SERENA_SUBAGENT_DENIED_TOOLS = (
    "write_memory",
    "edit_memory",
    "rename_memory",
    "delete_memory",
    "onboarding",
    "initial_instructions",
)

# Naming one of these in an agent's tools: allowlist is a silent no-op, not
# an error: Serena's claude-code context removes them because Claude Code's
# own built-ins already cover the same need (Grep, Glob/Bash ls, Glob,
# Read, Write, Bash in the order below).
SERENA_EXCLUDED_TOOLS = (
    "search_for_pattern",
    "list_dir",
    "find_file",
    "read_file",
    "create_text_file",
    "execute_shell_command",
)


# ============================================================================
# SHARED PROMPTS
# ============================================================================

SERENA_POLICY = (
    "SERENA TOOL POLICY (code files):\n"
    "  Discover with Glob/Grep, including occurrence counts.\n"
    "  Read via mcp__serena__get_symbols_overview then mcp__serena__find_symbol\n"
    "    (include_body=true); Read only for non-code files or a few lines\n"
    "    after an overview.\n"
    "  References via mcp__serena__find_referencing_symbols, never Grep.\n"
    "  Edit via mcp__serena__replace_symbol_body / insert_before_symbol /\n"
    "    insert_after_symbol / replace_content; Edit only for non-code files.\n"
    "  Memories (mcp__serena__list_memories, read_memory) are read-only,\n"
    "    Tier 3 below CLAUDE.md/README.md.\n"
    "  Batch independent calls in one message.\n"
    "  Serena line numbers are 0-based."
)

# Load hint tool sets equal the role allowlists exactly for the two roles
# whose exec_* scripts flow through mode_main: developer and
# technical-writer get the edit variant here, architect and
# quality-reviewer get the read variant. debugger holds the same
# edit-capable Serena allowlist directly in its agent frontmatter -- it
# has no planner package and never calls mode_main, so this selection
# does not cover it. A load hint naming a tool the role's allowlist omits
# would send the agent to ToolSearch for a tool it can never hold.
_READ_HINT_TOOLS = SERENA_READ_TOOLS + SERENA_MEMORY_READ_TOOLS
_EDIT_HINT_TOOLS = SERENA_READ_TOOLS + SERENA_EDIT_TOOLS + SERENA_MEMORY_READ_TOOLS

SERENA_READ_LOAD_HINT = (
    "If Serena tools are deferred: ToolSearch select:"
    + ",".join(SERENA_TOOL_PREFIX + name for name in _READ_HINT_TOOLS)
)

SERENA_EDIT_LOAD_HINT = (
    "If Serena tools are deferred: ToolSearch select:"
    + ",".join(SERENA_TOOL_PREFIX + name for name in _EDIT_HINT_TOOLS)
)

# This module lives in configuration global to every project Claude Code
# opens; most projects never configure Serena at all, so an unconditional
# Serena-first instruction would leave those sessions stalled or
# hallucinating tool calls that do not exist.
SERENA_FALLBACK = (
    "If no mcp__serena__ tool exists in this project: use Read/Grep/Edit "
    "and say so once."
)

SERENA_READ_PREAMBLE = (
    SERENA_POLICY + "\n"
    "\n"
    + SERENA_READ_LOAD_HINT + "\n"
    "\n"
    + SERENA_FALLBACK
)

SERENA_EDIT_PREAMBLE = (
    SERENA_POLICY + "\n"
    "\n"
    + SERENA_EDIT_LOAD_HINT + "\n"
    "\n"
    + SERENA_FALLBACK
)
