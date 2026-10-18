# Documentation Conventions

This is the authoritative documentation conventions file. All code-adjacent
documentation (root CLAUDE.md, memory index, README.md) must follow these
principles.

## Core Principles

**Self-contained documentation**: README.md must be self-contained. Do NOT
reference external authoritative sources (doc/ directories, wikis, external
documentation). If knowledge exists in an authoritative source, it must be
summarized locally. Duplication is acceptable; the maintenance burden is the
cost of locality.

**Root CLAUDE.md = launch-loaded commands and top-level index**: the only
CLAUDE.md in a repository. Build/test commands and the top-level file index.

**Memory index (mem:core graph) = navigation aid**: WHAT is in each directory
and WHEN to read each file. Machine-local under `.serena/memories`. All
explanatory content (architecture, decisions, invariants) belongs in
README.md.

**README.md = invisible knowledge**: README.md files capture knowledge NOT
visible from reading source code. If ANY invisible knowledge exists for a
directory, README.md is required.

## Memory Index Specification

The memory index is a Serena project memory graph under `.serena/memories`.
It is machine-local (gitignored, not committed) and is the navigation aid for
directories and files. A `mem:` pointer to a memory that does not exist is
skipped, not an error. Serena-less hosts rely on root CLAUDE.md + README.md.

### Index Format

`mem:core` is the graph root. It lists top-level directories as dense
bullets:

```markdown
- `cache/` -- LRU cache and eviction; read `mem:cache/core` when implementing caching, debugging evictions
- `handlers/` -- HTTP request handlers; read `mem:handlers/core` when adding endpoints, modifying request flow
```

`<project-relative-dir>/core` lists the files of one directory as dense
bullets, and names README.md by path when invisible knowledge exists:

```markdown
- `cache.rs` -- LRU cache with O(1) operations; read when implementing caching, debugging evictions
- `errors.rs` -- error types and Result aliases; read when adding error variants, handling failures
- `README.md` -- eviction design rationale; read when changing eviction policy
```

### Memory Rules

- **Name**: the directory's path relative to the Serena project root (the
  directory holding `.serena/`) plus `/core`. A repository that is a subtree
  of the project keeps its subtree prefix (`claude-config/skills/planner/core`).
- **References**: `mem:name` in backticks, with the when-to-read guidance in
  the referring bullet. A memory never states when to read itself.
- **What**: factual description of contents (nouns, not actions).
- **When to read**: task-oriented triggers using action verbs (implementing,
  debugging, modifying, adding, understanding).
- **Budget**: ~200 tokens per memory.
- **Style**: Serena's built-in `mem:memory_maintenance` conventions (dense
  bullets, topic folders mirroring paths, stable facts only).
  Memories are machine-local: they index the tree, they never replace
  README.md as the committed carrier of invisible knowledge.

### Trigger Quality Test

Given task "add a new validation rule", can an LLM scan the when-to-read
triggers and identify the right file?

### Generated and Vendored Code

The directory memory and README.md MUST flag files/directories that should
not be manually edited, with the regeneration command or upstream source:

```markdown
- `proto/gen/` -- generated from proto/; run `make`; never edit directly
- `vendor/` -- vendored deps, upstream: go.mod; never edit directly
- `third_party/` -- copied from github.com/foo v1.2.3; never edit directly
```

This prevents LLMs from wasting effort analyzing or "improving" auto-generated
code, and prevents edits that will be overwritten or cause merge conflicts.

See also: conventions/code-quality/baseline.md "Generated and Vendored Code Awareness".

### Root CLAUDE.md

The root CLAUDE.md is the only CLAUDE.md in a repository. It loads at launch
and carries commands and the top-level index:

```markdown
# [Project Name]

[One sentence: what this is]

## Files

| File | What | When to read |
| ---- | ---- | ------------ |

## Subdirectories

| Directory | What | When to read |
| --------- | ---- | ------------ |

## Build

[Copy-pasteable command]

## Test

[Copy-pasteable command]

## Development

[Setup instructions, environment requirements, workflow notes]
```

Subdirectory CLAUDE.md files do not exist: Claude Code loads them only when
a host tool touches a file in that directory, which Serena-first navigation
never does. Their role is carried by the memory index above. Explanatory
content (architecture, decisions, invariants) belongs in README.md.

Operational sections in the root CLAUDE.md must be copy-pasteable commands
with minimal context, not explanatory prose about why the build works a
certain way.

## README.md Specification

### Creation Criteria (Invisible Knowledge Test)

Create README.md when the directory contains ANY invisible knowledge --
knowledge NOT visible from reading the code:

- Planning decisions (from Decision Log during implementation)
- Business context (why the product works this way)
- Architectural rationale (why this structure)
- Trade-offs made (what was sacrificed for what)
- Invariants (rules that must hold but aren't in types)
- Historical context (why not alternatives)
- Performance characteristics (non-obvious efficiency properties)
- Multiple components interact through non-obvious contracts
- The directory's structure encodes domain knowledge
- Failure modes or edge cases aren't apparent from reading individual files
- "Rules" developers must follow that aren't enforced by compiler/linter

**README.md is required if ANY of the above exist.** The trigger is semantic
(presence of invisible knowledge), not structural (file count, complexity).

**DO NOT create README.md when:**

- The directory is purely organizational with no decisions behind its structure
- All knowledge is visible from reading source code
- You'd only be restating what code already shows

### Content Test

For each sentence in README.md, ask: "Could a developer learn this by reading
the source files?"

- If YES: delete the sentence
- If NO: keep it

README.md earns its tokens by providing INVISIBLE knowledge: the reasoning
behind the code, not descriptions of the code.

### README.md Structure

```markdown
# [Component Name]

## Overview

[One paragraph: what problem this solves, high-level approach]

## Architecture

[How sub-components interact; data flow; key abstractions]

## Design Decisions

[Tradeoffs made and why; alternatives considered]

## Invariants

[Rules that must be maintained; constraints not enforced by code]
```

## Architecture Documentation

For cross-cutting concerns and system-wide relationships that span multiple
directories, create dedicated architecture documentation.

### Structure

```markdown
# Architecture: [System/Feature Name]

## Overview

[One paragraph: problem and high-level approach]

## Components

[Each component with its single responsibility and boundaries]

## Data Flow

[Critical paths - prefer diagrams for complex flows]

## Design Decisions

[Key tradeoffs and rationale]

## Boundaries

[What this system does NOT do; where responsibility ends]
```

### Quality Standard

Components must explain relationships, not just list responsibilities.

Wrong -- lists without relationships:

```markdown
## Components

- UserService: Handles user operations
- AuthService: Handles authentication
- Database: Stores data
```

Right -- explains boundaries and flow:

```markdown
## Components

- UserService: User CRUD only. Delegates auth to AuthService. Never queries auth
  state directly.
- AuthService: Token validation, session management. Stateless; all state in
  Redis.
- PostgreSQL: Source of truth for user data. AuthService has no direct access.

Flow: Request -> AuthService (validate) -> UserService (logic) -> Database
```

Prefer diagrams over prose for relationships.

## In-Code Documentation

Code-level documentation captures knowledge at the point where it is most useful.
The principle: knowledge belongs as close as possible to the code it describes.
Cross-cutting knowledge that cannot be localized belongs in README.md.

### Tier 1: Inline Comments

Above statements or expressions where the choice is non-obvious.

Document *why* this approach, never *what* the code does. The reader can see what
the code does: they cannot see why it was chosen over alternatives.

Good:

```python
# Polling: 30% webhook delivery failures observed in production
result = poll_endpoint(url, interval=30)

# Mutex-free: single-writer guarantee from caller contract
counter.fetch_add(1, Ordering::Relaxed)
```

Bad:

```python
# Poll the endpoint
result = poll_endpoint(url, interval=30)

# Increment the counter
counter.fetch_add(1, Ordering::Relaxed)
```

When a decision log entry exists, reference it: `# DL-003: Polling over webhooks`

### Tier 2: Function-Level Explanation Blocks

Near the top of non-trivial functions (after signature, before body logic).
Required when a function has >3 distinct transformation steps, coordinates
multiple subsystems, or implements a non-obvious algorithm.

Content: what the function does, how it does it, how it fits in the overall
architecture, what problem it solves.

```python
def reconcile_state(local, remote):
    # Reconciles local state against remote source of truth. Operates in
    # three phases:
    # 1. Diff local vs remote to find divergent keys
    # 2. For each divergence, apply conflict resolution (remote wins)
    # 3. Write merged state back to local store
    #
    # Called by the sync loop after each heartbeat. Remote state is
    # authoritative -- local is a cache that may lag behind.
    ...
```

Skip for CRUD operations and standard patterns where the code speaks for itself.

### Tier 3: Docstrings

**Private functions**: One-line summary + trigger clause (when to call).

```python
def _normalize_key(k):
    """Strip whitespace and lowercase. Use before cache lookup."""
```

**Public functions**: Summary + trigger clause + parameter semantics + example.
Optimized for LLM consumption -- trigger clauses and examples enable accurate
tool selection.

```python
def validate_config(path, strict=False):
    """Validate configuration file against schema.

    Use when loading user-provided config at startup or after hot-reload.
    In strict mode, unknown keys are errors; otherwise warnings.

    Args:
        path: Absolute path to YAML config file.
        strict: Treat unknown keys as errors.

    Returns:
        Validated Config object.

    Example:
        cfg = validate_config("/etc/app/config.yaml", strict=True)
    """
```

### Tier 4: Module Documentation

Top-of-file comment or module docstring. Documents what the module contains and
why it exists as a separate unit.

```python
"""Rate limiting using sliding window counters.

Provides per-client rate limiting for the API gateway. Sliding window
chosen over fixed window to prevent burst-at-boundary attacks (DL-007).
Token bucket rejected: memory overhead per client unacceptable at
projected scale (>100k concurrent clients).
"""
```

### Tier 5: Invisible Knowledge Placement

Invisible knowledge is knowledge not visible from reading the code: business
context, architectural rationale, tradeoffs, constraints, rejected alternatives.

**Placement hierarchy** (closest viable location wins):

1. **Inline comment**: When knowledge applies to a specific statement
2. **Function-level block**: When knowledge applies to an entire function's
   approach or algorithm
3. **Module docstring**: When knowledge applies to why this module exists or
   its overall design
4. **README.md**: When knowledge is cross-cutting (spans multiple files/modules)
   or cannot be localized to a single code point

What is NOT acceptable: invisible knowledge captured only in planning artifacts
(decision logs, plan documents, conversation history) that are not carried
forward into the codebase. Every decision, constraint, and tradeoff must land
in code or README.md.

### Priority Order

When deciding what to document, prioritize by uncertainty:

| Priority | Code Pattern                 | WHY Question           |
| -------- | ---------------------------- | ---------------------- |
| HIGH     | Multiple valid approaches    | Why this approach?     |
| HIGH     | Thresholds, timeouts, limits | Why these values?      |
| HIGH     | Error handling paths         | Recovery strategy?     |
| HIGH     | External system interactions | What assumptions?      |
| MEDIUM   | Non-standard pattern usage   | Why deviate from norm? |
| MEDIUM   | Performance-critical paths   | Why this optimization? |
| LOW      | Boilerplate/established      | Skip unless unusual    |
| LOW      | Simple CRUD operations       | Skip unless unusual    |
