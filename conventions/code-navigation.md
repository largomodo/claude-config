# Code Navigation

Serena tool policy for reading and editing source files. Applies to the five
sub-agents (architect, developer, debugger, quality-reviewer, technical-writer)
and to general-purpose agents spawned by skills.

## Purpose

Serena provides symbolic (LSP-backed) navigation and editing: it finds
definitions, callers, and implementations by name rather than by text match,
and edits a function or class as a unit rather than as raw lines. Grep/Read/
Edit are text tools with no notion of a symbol; Serena's tools are code-aware.
This document is the canonical policy; `prompts/serena.py` mirrors it as
Python constants for sub-agent Task instructions, and
`tests/test_serena_policy.py` keeps the two in sync.

This policy lives here rather than in `agents/README.md` because agents
already discover conventions through the Convention References rows in
their own files -- a new convention slots into that existing mechanism
with no new path to teach -- and because the knowledge it documents spans
`agents/`, the planner scripts, and the test suite, which is the
cross-cutting scope `conventions/` exists for rather than any one
directory's README.

## Tool Map

Every tool name below carries its full `mcp__serena__` prefix so the sync
test can extract names with one regex.

### Navigate

| Tool                                    | Use when                                                     |
| --------------------------------------- | ------------------------------------------------------------ |
| `mcp__serena__get_symbols_overview`     | Map a file's structure before reading it                     |
| `mcp__serena__find_symbol`              | Read a class/method by name path (`include_body=true`)       |
| `mcp__serena__find_referencing_symbols` | Find callers and impact radius                               |
| `mcp__serena__find_declaration`         | Jump to a definition from a usage site                       |
| `mcp__serena__find_implementations`     | List concrete implementations of an interface/abstract class |
| `mcp__serena__get_diagnostics_for_file` | Read compiler/LSP errors after an edit                       |

### Edit

| Tool                                | Use when                                          |
| ----------------------------------- | ------------------------------------------------- |
| `mcp__serena__replace_symbol_body`  | Rewrite a whole function or class                 |
| `mcp__serena__insert_before_symbol` | Add an import or a new sibling before a symbol    |
| `mcp__serena__insert_after_symbol`  | Add a new member or sibling after a symbol        |
| `mcp__serena__replace_content`      | Make a targeted change inside a symbol            |
| `mcp__serena__replace_in_files`     | Replace the same literal across files             |
| `mcp__serena__rename_symbol`        | Rename with every reference updated               |
| `mcp__serena__safe_delete_symbol`   | Delete after checking nothing still references it |

### Memory

| Tool                            | Use when                                          |
| -------------------------------- | -------------------------------------------------- |
| `mcp__serena__list_memories`     | See what project knowledge the main session saved  |
| `mcp__serena__read_memory`       | Read one memory                                    |

Memories (`.serena/memories/`) are project knowledge written by the main
session. Sub-agents read them but never write them: parallel sub-agents
writing the same memory would race and overwrite each other's notes. Memories
rank Tier 3 in the convention hierarchy, below CLAUDE.md and README.md.

## Rules

- **Read is forbidden for discovery on code files.** Map the file with
  `get_symbols_overview`, then read the specific symbol with `find_symbol`
  (`include_body=true`). Read is for non-code files, and for a few lines of
  context immediately after an overview.
- **Glob/Grep are allowed for discovery**, including occurrence counting.
  Once a candidate file or symbol name is known, the follow-up read is
  Serena's job, not Grep's.
- **Reference searches go through `find_referencing_symbols`**, never Grep --
  a text match on a name misses renamed imports, shadowing, and
  string-only references gets false positives Serena already resolves away.
- **Edit is forbidden on code files.** Use the Serena edit tools above; Edit
  and Write are for non-code files (docs, config, data).
- **Serena line numbers are 0-based.**
- **Batch independent Serena calls in one message** rather than issuing them
  one at a time.
- Do not reason about a symbol from its name alone when its body is one
  `find_symbol` call away.

## Fallback

If no `mcp__serena__` tool exists in the project (Serena is not configured
there), use Read/Grep/Edit and state the fallback once. Do not call
ToolSearch repeatedly hoping a Serena tool appears -- most projects on this
host never configure Serena, and an unconditional Serena-first rule would
otherwise leave those sessions stalled or hallucinating tool calls.

## Sub-Agent Allowlists

Each of the five agents enumerates its tools explicitly rather than granting
`mcp__serena__*` as a wildcard: an allowlisted MCP tool arrives pre-loaded and
callable from the agent's first turn, while an unlisted one sits deferred
behind ToolSearch with no manual delivered until something loads it -- next
to Read from turn one is the strongest nudge available. A wildcard would also
hand every sub-agent `write_memory`/`delete_memory`/`onboarding`, which
parallel quality-reviewer agents would then race on.

| Role              | Serena tools granted                          | Rationale |
| ----------------- | ---------------------------------------------- | --------- |
| architect          | Navigate + memory-read (8)                     | Designs, does not touch source files; also gets `WebSearch` for external research during design |
| quality-reviewer   | Navigate + memory-read (8)                     | Reviews, does not touch source files |
| developer          | Navigate + Edit + memory-read (15)             | Implements; also gets `Agent` (not the legacy `Task` alias -- DL-014) for wave-parallel sub-agent dispatch |
| debugger           | Navigate + Edit + memory-read (15)             | Fixes bugs in place; also gets `TodoWrite` because its steps require every modification logged before it is made and verified against that log at cleanup |
| technical-writer   | Navigate + Edit + memory-read (15)             | Fixes source comments during documentation passes |

Every role also keeps `Read`, `Glob`, `Grep`, `Bash`, `Write` and
`ToolSearch`; architect additionally keeps `WebSearch` for research the
other four roles have no need for. Glob and Grep are the discovery tools,
but some permission modes expose no Glob or Grep at all -- an unavailable
tool name is simply dropped rather than causing an error -- so Bash covers
ad hoc discovery when that happens. Write lets architect and
quality-reviewer create files even though neither role edits source:
quality-reviewer's `exec_reconcile.py` writes `{tmpdir}/qr.md` and both
roles' scripts save relay state before yielding a question. Edit is
withheld from architect and quality-reviewer entirely, not merely narrowed
to non-code files: their scripts write `plan.json` through the CLI and
reports through Write, and never modify an existing file, so Edit is
granted whole to developer, debugger and technical-writer instead of
split by file type across every role. ToolSearch is assumed to load a
Serena tool that arrives deferred (unverified: allowlisted MCP tools have
only been observed pre-loaded, never deferred, so this path is untested).

technical-writer receives the identical seven-tool edit set as developer and
debugger, not a narrower one limited to the edit tools it uses most: the
edit-capable preamble's ToolSearch load hint lists one fixed set of Serena
edit tools, so every role it applies to must actually hold every tool named
in it.

Memory access is `mcp__serena__list_memories` and `mcp__serena__read_memory`
only, for every role. The remaining six Serena tools --
`mcp__serena__write_memory`, `mcp__serena__edit_memory`,
`mcp__serena__rename_memory`, `mcp__serena__delete_memory`,
`mcp__serena__onboarding`, and `mcp__serena__initial_instructions` -- are
never granted to a sub-agent; they drive the main session's own Serena setup
and would let parallel sub-agents corrupt shared project memory.

`get_current_config` and `activate_project` are
disabled by Serena's single-project mode and are not part of any allowlist or
of the 21-tool deployed set below.

## Excluded tools

Serena's claude-code context removes six tools because Claude Code's own
built-ins already cover the same need; naming any of them in an allowlist is
a silent no-op, not an error:

- `mcp__serena__search_for_pattern` -- use Grep
- `mcp__serena__list_dir` -- use Glob or Bash `ls`
- `mcp__serena__find_file` -- use Glob
- `mcp__serena__read_file` -- use Read
- `mcp__serena__create_text_file` -- use Write
- `mcp__serena__execute_shell_command` -- use Bash

Together with the 6 navigate + 7 edit + 2 memory-read tools in Tool Map
above and the 6 tools denied to sub-agents in Sub-Agent Allowlists above
(`write_memory`, `edit_memory`, `rename_memory`, `delete_memory`,
`onboarding`, `initial_instructions` -- not the 6 excluded tools just
listed), this accounts for the full 21-tool set Serena's claude-code
context deploys.

## Sync

`skills/lib/workflow/prompts/serena.py` mirrors this document as Python
constants (`SERENA_READ_TOOLS`, `SERENA_EDIT_TOOLS`,
`SERENA_MEMORY_READ_TOOLS`, `SERENA_SUBAGENT_DENIED_TOOLS`,
`SERENA_EXCLUDED_TOOLS`) because sub-agents driven by planner scripts obey
the script's stdout during a run, not this file's prose.
`skills/scripts/tests/test_serena_policy.py` enforces the sync in both
directions: every tool name in those constants appears here, prefixed, and
every `mcp__serena__`-prefixed name that appears here is one of those
constants' real tool names.
