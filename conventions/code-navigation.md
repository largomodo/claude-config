# Code Navigation

Serena REPL policy for reading and editing source files. Applies to the five
sub-agents (architect, developer, debugger, quality-reviewer, technical-writer)
and to general-purpose agents spawned by skills.

## Purpose

Serena provides symbolic (LSP-backed) navigation and editing: it finds
definitions, callers, and implementations by name rather than by text match,
and edits a function or class as a unit rather than as raw lines. Grep/Read/
Edit are text tools with no notion of a symbol; Serena's operations are
code-aware. This document is the canonical policy; `prompts/serena.py`
mirrors it as Python constants for sub-agent Task instructions, and
`tests/test_serena_policy.py` keeps the two in sync.

This policy lives here rather than in `agents/README.md` because agents
already discover conventions through the Convention References rows in
their own files -- a new convention slots into that existing mechanism
with no new path to teach -- and because the knowledge it documents spans
`agents/`, the planner scripts, and the test suite, which is the
cross-cutting scope `conventions/` exists for rather than any one
directory's README.

## Interface

Serena exposes exactly two MCP tools: `mcp__serena__initial_instructions`
(returns Serena's manual, the active-project info and a session id) and
`mcp__serena__serena_repl(session_id, code)`. The code runs like a notebook
cell against the entrypoint `s`, whose facades are `s.lsp`, `s.edit`,
`s.mem`, `s.fs`, `s.shell` and `s.cfg`.

- The trailing expression is the result; `print` returns nothing.
- Top-level variables persist per session id. Every sub-agent run calls
  `initial_instructions` once and uses its own id: a shared id lets parallel
  agents overwrite each other's variables.
- `s.info("lsp")` and `s.info("edit.replace_content")` document signatures
  on demand.
- One `serena_repl` call per logical step: map a file, read the symbol and
  filter the result in one cell rather than one call per operation.
- Methods with `max_answer_chars` cap their output; narrow the query rather
  than raise the cap.

## Operation Map

Every operation is named in full, `s.<facade>.<method>`, so the sync test
can extract names with one regex.

### Navigate

| Operation                           | Use when                                                     |
| ----------------------------------- | ------------------------------------------------------------ |
| `s.lsp.get_symbols_overview`        | Map a file's structure before reading it                     |
| `s.lsp.find_symbol`                 | Read a class/method by name path (`include_body=True`)       |
| `s.lsp.find_referencing_symbols`    | Find callers and impact radius                               |
| `s.lsp.find_declaration`            | Jump to a definition from a usage site                       |
| `s.lsp.find_implementations`        | List concrete implementations of an interface/abstract class |
| `s.lsp.get_diagnostics_for_file`    | Read compiler/LSP errors after an edit                       |

### Edit

| Operation                       | Use when                                                                  |
| ------------------------------- | ------------------------------------------------------------------------- |
| `s.edit.replace_symbol_body`    | Rewrite a whole function or class                                         |
| `s.edit.insert_before_symbol`   | Add an import or a new sibling before a symbol                            |
| `s.edit.insert_after_symbol`    | Add a new member or sibling after a symbol                                |
| `s.edit.replace_content`        | Make a targeted change inside a symbol; a regex needle with wildcards keeps small edits short |
| `s.edit.replace_in_files`       | Replace the same text across files; run with `dry_run=True` first         |
| `s.lsp.rename_symbol`           | Rename with every reference updated                                       |
| `s.lsp.safe_delete_symbol`      | Delete after checking nothing still references it                         |

### Memory

| Operation                | Use when                                          |
| ------------------------ | ------------------------------------------------- |
| `s.mem.list_memories`    | See what project knowledge the main session saved |
| `s.mem.read_memory`      | Read one memory                                   |

Memories (`.serena/memories/`) are project knowledge written by the main
session. Sub-agents read them but never write them: parallel sub-agents
writing the same memory would race. Memories are Tier 3 knowledge, below
CLAUDE.md and README.md.

## Rules

- **Read is forbidden for discovery on code files.** Map the file with
  `s.lsp.get_symbols_overview`, then read the specific symbol with
  `s.lsp.find_symbol` (`include_body=True`). Read is for non-code files, and
  for a few lines of context immediately after an overview.
- **Glob/Grep are allowed for discovery**, including occurrence counting.
  Once a candidate file or symbol name is known, the follow-up read is
  Serena's job, not Grep's.
- **Reference searches go through `s.lsp.find_referencing_symbols`**, never
  Grep -- a text match on a name misses renamed imports, shadowing, and
  string-only references and gets false positives Serena already resolves
  away.
- **Edit is forbidden on code files.** Use the `s.edit` methods above; Edit
  and Write are for non-code files (docs, config, data).
- **Serena line numbers are 0-based.**
- **Compose independent operations in one `serena_repl` call** instead of
  issuing one call per operation.
- Do not reason about a symbol from its name alone when its body is one
  `s.lsp.find_symbol` call away.

## Role Rules

| Role              | Serena use                                              |
| ----------------- | ------------------------------------------------------- |
| architect         | Read-only: no `s.edit` call, no `s.fs.create_text_file`, no `s.shell`; Write only for plan state and reports |
| quality-reviewer  | Read-only: same restrictions as architect               |
| developer         | Edit-capable                                            |
| debugger          | Edit-capable                                            |
| technical-writer  | Edit-capable                                            |

Every role reads memories only. Sub-agents never call `s.mem.write_memory`,
`s.mem.edit_memory`, `s.mem.rename_memory`, `s.mem.delete_memory` or
`s.mem.onboarding`; parallel sub-agents writing shared project memory would
race and corrupt it.

`serena_repl` is one fully privileged tool, so an allowlist cannot withhold
editing or memory writes from a role. These rules are instruction, not
enforcement. The step-1 preamble (`SERENA_READ_ROLE_RULE` /
`SERENA_EDIT_ROLE_RULE`) carries them into every scripted run; debugger has
no planner package and relies on this document.

The read-only clause is written out as an explicit prohibition for the same
reason: an agent follows a stated rule, not the absence of one, and the
allowlist cannot supply the missing restriction.

## Fallback

If `mcp__serena__serena_repl` is unavailable after one ToolSearch (Serena is
not configured for the project), use Read/Grep/Edit and state the fallback
once. Do not call ToolSearch repeatedly hoping the tool appears -- most
projects on this host never configure Serena, and an unconditional
Serena-first rule would otherwise leave those sessions stalled or
hallucinating tool calls.

The fallback keys on `mcp__serena__serena_repl` alone: it is the one tool
that carries every operation, so its absence means no Serena operation is
reachable.

## Sub-Agent Grants

Each of the five agents lists `mcp__serena__serena_repl` and
`mcp__serena__initial_instructions` in its tools, and nothing else from
Serena. `initial_instructions` is granted because it is the only source of a
session id and of Serena's manual, and it writes nothing. The two names are
listed explicitly rather than as a wildcard; a wildcard adds nothing when
only two tools exist.

`ToolSearch` stays in every list because allowlisted MCP tools reach a
sub-agent deferred, not pre-loaded: on its first turn a sub-agent sees
neither Serena tool and needs one `ToolSearch select:` call to load both.
The load hint (`ToolSearch select:` both names) cannot run without it. The
Fallback stops the agent after that single call, so the hint cannot become
a loop.

| Role              | Host tools beyond the common set | Rationale |
| ----------------- | -------------------------------- | --------- |
| architect         | `WebSearch`                      | External research during design |
| quality-reviewer  | none                             | Reviews, does not touch source files |
| developer         | `Edit`, `Agent`                  | Implements; `Agent` (not the legacy `Task` alias -- DL-014) for wave-parallel sub-agent dispatch |
| debugger          | `Edit`, `TodoWrite`              | Fixes bugs in place; `TodoWrite` because its steps require every modification logged before it is made and verified against that log at cleanup |
| technical-writer  | `Edit`                           | Fixes source comments during documentation passes |

Every role keeps `Read`, `Glob`, `Grep`, `Bash`, `Write` and `ToolSearch`.
Glob and Grep are the discovery tools, but some permission modes expose no
Glob or Grep at all -- an unavailable tool name is simply dropped rather
than causing an error -- so Bash covers ad hoc discovery when that happens.
Write lets architect and quality-reviewer create files even though neither
role edits source: quality-reviewer's `exec_reconcile.py` writes
`{tmpdir}/qr.md` and both roles' scripts save relay state before yielding a
question. Edit is withheld from architect and quality-reviewer entirely,
not merely narrowed to non-code files: their scripts write `plan.json`
through the CLI and reports through Write, and never modify an existing
file, so Edit is granted whole to developer, debugger and technical-writer
instead of split by file type across every role.

## Host-Covered Operations

The REPL can call these, but sub-agents use the host tool instead:

| Operation                      | Host tool                                                    |
| ------------------------------ | ------------------------------------------------------------ |
| `s.fs.search_for_pattern`      | Grep                                                         |
| `s.fs.list_dir`                | Glob or Bash `ls`                                            |
| `s.fs.find_file`               | Glob                                                         |
| `s.fs.read_file`               | Read, for non-code files only (code is read through `s.lsp` as the Rules require) |
| `s.fs.create_text_file`        | Write                                                        |
| `s.shell.execute_shell_command` | Bash                                                        |

Host tools are permission-gated and each call is visible by name in the
transcript, while a `serena_repl` call shows only its code.

## Sync

`skills/lib/workflow/prompts/serena.py` mirrors this document as Python
constants (`SERENA_MCP_TOOLS`, `SERENA_READ_METHODS`, `SERENA_EDIT_METHODS`,
`SERENA_MEMORY_READ_METHODS`, `SERENA_SUBAGENT_DENIED_METHODS`,
`SERENA_HOST_COVERED_METHODS`) because sub-agents driven by planner scripts
obey the script's stdout during a run, not this file's prose.
Sections map one-to-one onto the constants: Sub-Agent Grants onto
`SERENA_MCP_TOOLS`, Operation Map and Host-Covered Operations onto the
method tuples, Role Rules onto the role clauses. The sync test and a human
reader therefore see the same structure.
Operations are named `s.<facade>.<method>` because that is how Serena's
own manual names them, and one regex over that form needs no YAML parser
and no Serena import, neither of which CI provides.
`skills/scripts/tests/test_serena_policy.py` extracts every
`s.<facade>.<method>` name here and checks it against those tuples in both
directions, and checks that the only `mcp__serena__` names in any `.md`,
`.py`, `.yml`, `.yaml` or `.json` file under the repo root are the two in
`SERENA_MCP_TOOLS`. The scan skips `.git`, `__pycache__` and `projects/`,
the untracked runtime directory Claude Code keeps in a live checkout, whose
session notes may name retired tools.
