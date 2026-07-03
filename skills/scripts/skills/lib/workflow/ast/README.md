# AST Module

Typed AST for workflow XML output with a fluent builder and an XML renderer.

Status: `ast/` is the older of the two prompt layers -- new skills use
`lib/workflow/prompts/` (plain text). Current users: incoherence,
leon-writing-style, refactor.

## Architecture

```
Skills (incoherence, leon-writing-style, refactor)
       |
       v
+---------------------------+
| Builder API               |
| W.el(tag, *children,      |
|      **attrs)             |
+---------------------------+
       |
       v
+------------------------------------------------+
|                  AST Nodes                     |
| TextNode | CodeNode | ElementNode              |
| FileContentNode | StepHeaderNode               |
| CurrentActionNode | InvokeAfterNode            |
+------------------------------------------------+
       |
       v
+------------------+     +--------------------------+
| XMLRenderer      |     | Dispatch nodes rendered  |
| via render()     |     | by standalone functions  |
+------------------+     +--------------------------+
       |
       v
    str output
```

Dispatch nodes (`SubagentDispatchNode`, `TemplateDispatchNode`,
`RosterDispatchNode`) sit outside the `Node` union: they render through
dedicated `render_*_dispatch()` functions in `dispatch_renderer.py`, not
through `XMLRenderer`.

## Usage

```python
from skills.lib.workflow.ast import W, render, XMLRenderer, TextNode

# Build step header
doc = W.el("step_header", TextNode("Title"),
           script="myskill", step="1", total="5").build()
output = render(doc, XMLRenderer())

# Build current_action block
action_nodes = [TextNode(a) for a in actions]
doc = W.el("current_action", *action_nodes).build()

# Build invoke_after
doc = W.el("invoke_after", TextNode(next_command)).build()
```

`W.el()` attribute values are strings (`step="1"`, not `step=1`).
`W.el(...).node()` returns the single accumulated node when a bare `Node` is
needed instead of a `Document`.

## Node Types

| Type                | Purpose                                                |
| ------------------- | ------------------------------------------------------ |
| `TextNode`          | Plain text content                                     |
| `CodeNode`          | Code block with optional language                      |
| `ElementNode`       | Generic XML element (via W.el())                       |
| `FileContentNode`   | Embed file content, CDATA-wrapped                      |
| `StepHeaderNode`    | Step boundary; typed int step/total                    |
| `CurrentActionNode` | Action list auto-wrapped as element children           |
| `InvokeAfterNode`   | Next-step command, single or if_pass/if_fail branching |

The original design had 11 node types with one specialized builder method
each (`W.header()`, `W.text_output()`, ...). All specialized builder methods
were removed in favor of the generic `W.el("tag_name", ...)`; the surviving
semantic nodes above earn their place through typed fields and
construction-time validation, not builder convenience.

**Why FileContentNode is distinct from CodeNode**: CodeNode is for code
examples with syntax-highlighting hints; FileContentNode embeds reference
material the LLM should read. Embedding avoids the latency and context cost
of having the LLM explore files itself. Content is CDATA-wrapped to prevent
XML injection from content containing `</file>`.

## Dispatch Node Types

| Type                   | Pattern | Use case                                     |
| ---------------------- | ------- | -------------------------------------------- |
| `SubagentDispatchNode` | Single  | Sequential workflows (plan -> dev -> QR)     |
| `TemplateDispatchNode` | SIMD    | Same template, N targets ($var substitution) |
| `RosterDispatchNode`   | MIMD    | Shared context, unique prompts per agent     |

```python
from skills.lib.workflow.ast import (
    TemplateDispatchNode, render_template_dispatch,
    RosterDispatchNode, render_roster_dispatch,
)

# Template dispatch: $var substituted per-target
node = TemplateDispatchNode(
    agent_type="general-purpose",
    template="Explore $category in $mode mode",
    targets=({"category": "Naming", "mode": "code"}, ...),
    command='python3 -m skills.explore --category $category',
    model="haiku",
)
xml = render_template_dispatch(node)

# Roster dispatch: unique prompts, fixed command
node = RosterDispatchNode(
    agent_type="general-purpose",
    shared_context="Background...",
    agents=("Task 1...", "Task 2...", "Task 3..."),
    command='python3 -m skills.subagent --step 1',
    model="sonnet",
)
xml = render_roster_dispatch(node)
```

`targets` and `agents` are tuples (frozen dataclass fields). Substitution
happens at render time via `string.Template`, so the LLM sees N final
prompts, not substitution instructions.

**Why 3 dispatch types instead of 1 with a discriminator field**: separate
types make illegal states unrepresentable at construction time -- no Optional
fields with mutual-exclusivity validation.

## Why This Structure

### Module Organization

- **nodes.py**: Node definitions isolated from construction logic. Enables
  importing types without builder dependency.
- **builder.py**: Fluent API separate from types. Builder can evolve without
  changing node structure.
- **renderer.py**: Rendering decoupled from AST. `Renderer` is a Protocol;
  `XMLRenderer` is the only implementation (`render()` raises
  `NotImplementedError` for others).
- **dispatch.py / dispatch_renderer.py**: Dispatch prompts have their own
  vocabulary (agent rosters, parallel constraints) that doesn't fit the
  generic node/renderer pipeline.

### Design Choices

**Frozen dataclasses**: Immutability prevents accidental mutation and enables
safe sharing of nodes between renders.

**Flat union**: Workflow output is sequential composition, not nested prose.
Flat `children: list[Node]` matches actual patterns better than a layered
inline/block distinction.

**Separate dataclass per type**: Type-safe field access with IDE
autocomplete. More explicit than a shared attrs dict; standard discriminated
union pattern.

**Immutable builder**: Each builder method returns a NEW builder instance
with the accumulated node. No mutable state shared between calls; final
`.build()` returns a `Document`.

**External render() function**: Document doesn't know about renderers.
New renderers can be added without modifying node classes.

**Typed int step/total on StepHeaderNode**: The type system catches
construction errors before XML rendering; the renderer converts to string.

**InvokeAfterNode validates in __post_init__**: Invalid construction fails
immediately instead of at render time, so an invalid node never reaches the
renderer. Its `working_dir` default centralizes a path that was previously
hardcoded at 47+ call sites.

## Invariants

1. **Node types are frozen dataclasses**: immutable after construction.
2. **`Node` = union of 7 node types**: discriminated by class type. New node
   types MUST be added to the union AND to `_render_node()`'s match statement
   -- an unhandled type falls through silently (no assertNever).
3. **`children` is always `list[Node]`, never None**: empty list for leaf
   nodes.
4. **`InvokeAfterNode` requires `cmd` or both `if_pass`/`if_fail`**: enforced
   at construction.
5. **FileContentNode content containing `]]>` must survive CDATA wrapping**:
   the renderer splits into multiple CDATA sections
   (`foo]]>bar` -> `foo]]]]><![CDATA[>bar`).
6. **Builder methods return NEW builder instances**: the module-level `W` is
   shared and must never accumulate state.

## Extending the AST

To add a new node type:

1. Add frozen dataclass to `nodes.py` with typed fields
2. Add to the `Node` union and `__all__` in `nodes.py`
3. Add a `render_*` method to `Renderer` protocol and `XMLRenderer`
4. Add a case to `_render_node()`'s match statement
5. Export from `__init__.py`
6. Update tests to cover the new node type

Prefer `W.el()` with a generic `ElementNode` unless the node needs typed
fields or construction-time validation -- that's the bar the surviving
semantic nodes met.
