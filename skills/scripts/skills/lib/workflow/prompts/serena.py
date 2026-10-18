"""Serena REPL policy constants for sub-agent Task instructions.

Mirrors conventions/code-navigation.md (Tier 3) as Python constants because
sub-agents obey script stdout during planner runs, not agent prose; loading
the convention via get_convention() would need a REGISTRY.yaml entry per
role and cost ~400 tokens per step. Two precomposed preambles (read, edit)
cover both variants; skills/README.md forbids prompt-fragment builder
functions in the shared lib, so no serena_preamble(edit: bool) function
exists here. tests/test_serena_policy.py enforces the mirror in both
directions: every s.<facade>.<method> name in the tuples below appears in
the convention, and every s.<facade>.<method> name in the convention or the
preambles is one of these constants' entries.

Entries are "facade.method" strings because that matches Serena's own
s.<facade>.<method> naming in its manual and in s.info(); one regex over
that form syncs prose, preambles and tests with no YAML parser and no Serena
import, neither of which CI provides.
"""

# ============================================================================
# CONFIGURATION
# ============================================================================

# Claude Code names an MCP tool mcp__<server>__<tool>; the REPL interface
# registers server "serena".
SERENA_TOOL_PREFIX = "mcp__serena__"

# Serena's REPL interface exposes exactly these two MCP tools; every other
# mcp__serena__ name is a hallucination.
SERENA_MCP_TOOLS = (
    "serena_repl",
    "initial_instructions",
)

# Each entry below is a "facade.method" string reached in REPL code as
# s.<facade>.<method>.
SERENA_READ_METHODS = (
    "lsp.get_symbols_overview",
    "lsp.find_symbol",
    "lsp.find_referencing_symbols",
    "lsp.find_declaration",
    "lsp.find_implementations",
    "lsp.get_diagnostics_for_file",
)

SERENA_EDIT_METHODS = (
    "edit.replace_symbol_body",
    "edit.insert_before_symbol",
    "edit.insert_after_symbol",
    "edit.replace_content",
    "edit.replace_in_files",
    "lsp.rename_symbol",
    "lsp.safe_delete_symbol",
)

SERENA_MEMORY_READ_METHODS = (
    "mem.list_memories",
    "mem.read_memory",
)

# Never called by a sub-agent: parallel sub-agents writing, renaming or
# deleting the same memory would race and corrupt shared project knowledge.
# No allowlist can withhold these from serena_repl, so the rule is stated in
# the convention and repeated in the preamble.
SERENA_SUBAGENT_DENIED_METHODS = (
    "mem.write_memory",
    "mem.edit_memory",
    "mem.rename_memory",
    "mem.delete_memory",
    "mem.onboarding",
)

# Callable in the REPL, but sub-agents use the permission-gated,
# transcript-visible host tools instead, in the order below: Grep, Glob or
# Bash ls, Glob, Read (non-code files only; code is read through s.lsp per
# the Rules), Write, Bash.
# Host tools are permission-gated and each call appears by name in the
# transcript, while a serena_repl call shows only its code; for sub-agent
# reads and shell use, that auditability outweighs REPL composability.
SERENA_HOST_COVERED_METHODS = (
    "fs.search_for_pattern",
    "fs.list_dir",
    "fs.find_file",
    "fs.read_file",
    "fs.create_text_file",
    "shell.execute_shell_command",
)


# ============================================================================
# SHARED PROMPTS
# ============================================================================

# Shared core of both preambles. initial_instructions mints a fresh random
# session id per call, and the REPL namespace persists per id, so each
# sub-agent calls it for its own id; a shared id lets parallel agents
# overwrite each other's variables. It also delivers Serena's manual, a cost
# of ~1.5k tokens per run accepted so this text stays compact. The first line
# of SERENA_POLICY is the anchor test_leaf_scripts_inject matches, so it must
# open both preambles. Examples are brace-free keyword calls:
# the preambles are plain strings that are never .format()ed, and
# test_preambles_have_no_braces guards that.
SERENA_POLICY = (
    "SERENA REPL POLICY (code files):\n"
    "  Call mcp__serena__initial_instructions once, first; pass its session id\n"
    "  to every mcp__serena__serena_repl call. Never reuse another agent's id.\n"
    "  Discover with Glob/Grep, including occurrence counts.\n"
    "  Read via s.lsp.get_symbols_overview(path), then\n"
    "    s.lsp.find_symbol(name_path, relative_path=path, include_body=True);\n"
    "    Read only for non-code files or a few lines after an overview.\n"
    "  References via s.lsp.find_referencing_symbols(name_path, path), never Grep.\n"
    "  Memories (s.mem.list_memories, s.mem.read_memory) are read-only,\n"
    "    Tier 3 below CLAUDE.md/README.md; never call an s.mem write method.\n"
    "  Host tools cover s.fs and s.shell: use Glob/Grep/Read/Bash instead.\n"
    "  One serena_repl call per logical step: chain overview, find_symbol and\n"
    "    filtering in code; the trailing expression is the result (no print).\n"
    '  s.info("lsp") documents signatures. Serena line numbers are 0-based.'
)

# serena_repl is one tool for every operation, so a tools: allowlist cannot
# withhold editing from a role and these clauses are the only lever.
# mode_main selects the edit clause for exec_* scripts of developer and
# technical_writer and the read clause for every other script; debugger has
# no planner package and relies on its agent frontmatter plus the convention.
SERENA_READ_ROLE_RULE = (
    "READ-ONLY RUN: no s.edit call, no s.fs.create_text_file, no s.shell;\n"
    "  report findings instead of changing source files."
)

SERENA_EDIT_ROLE_RULE = (
    "EDIT via s.edit.replace_symbol_body / insert_before_symbol /\n"
    "  insert_after_symbol / replace_content (regex needle for small in-symbol\n"
    "  changes); s.edit.replace_in_files(dry_run=True) before cross-file edits;\n"
    "  s.lsp.rename_symbol and s.lsp.safe_delete_symbol are reference-aware.\n"
    "  Edit only for non-code files; s.lsp.get_diagnostics_for_file after edits."
)

# General-purpose leaf sub-agents (deepthink, codebase_analysis, refactor)
# have no tools: allowlist, so Claude Code may hand them MCP tools deferred.
SERENA_LOAD_HINT = (
    "If the Serena tools are deferred: ToolSearch select:"
    + ",".join(SERENA_TOOL_PREFIX + name for name in SERENA_MCP_TOOLS)
)

# This module lives in configuration global to every project Claude Code
# opens; most projects never configure Serena at all, so an unconditional
# Serena-first instruction would leave those sessions stalled or
# hallucinating tool calls that do not exist.
SERENA_FALLBACK = (
    "If mcp__serena__serena_repl is still unavailable (Serena is not "
    "configured for this project): use Read/Grep/Edit and say so once."
)

# Order: policy, role clause, load hint, fallback. The fallback comes last so
# the stop condition is the final instruction after the load attempt.
# Leaf scripts (deepthink, codebase_analysis, refactor) run as general-purpose
# sub-agents with no tools: allowlist, where MCP tools can arrive deferred
# behind ToolSearch, so the load hint names both tools. The fallback keys on
# serena_repl alone: a condition on any mcp__serena__ name would fire
# spuriously because the preamble itself names tools.
SERENA_READ_PREAMBLE = (
    SERENA_POLICY + "\n"
    "\n"
    + SERENA_READ_ROLE_RULE + "\n"
    "\n"
    + SERENA_LOAD_HINT + "\n"
    "\n"
    + SERENA_FALLBACK
)

# Only the role clause differs from the read preamble; policy, load hint and
# fallback are shared so a policy change cannot diverge between roles.
# The read preamble states the prohibition explicitly because an absent rule
# is not one an agent follows.
SERENA_EDIT_PREAMBLE = (
    SERENA_POLICY + "\n"
    "\n"
    + SERENA_EDIT_ROLE_RULE + "\n"
    "\n"
    + SERENA_LOAD_HINT + "\n"
    "\n"
    + SERENA_FALLBACK
)
