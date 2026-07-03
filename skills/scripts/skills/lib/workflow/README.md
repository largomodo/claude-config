# Workflow Framework

## Overview

Framework for defining skill workflows and generating the plain-text step
prompts that drive them. Skills are Python scripts invoked step-by-step from
the CLI; the framework provides workflow metadata for introspection and
testing (`Workflow`/`StepDef`/`Arg`), discovery, prompt building blocks, and
shared prompt constants. The LLM -- not Python -- executes the workflow.

## Architecture

```
Skills Layer (per-skill packages)
       |
       v
Prompt Building (prompts/ plain text; ast/ XML for older skills)
       |
       v
Workflow Metadata (Workflow / StepDef / Arg)
       |
       v
Discovery (importlib scanning) ---> Test Harness (pytest)
```

### Execution Model

```
CLI: python3 -m skills.<skill>.<module> --step N
      |
      v
main() -> format_output(step, ...) -> print()
      |
      v
LLM reads step output, performs the actions
      |
      v
LLM executes the printed NEXT STEP command (step N+1)
```

Python scripts emit prompts and routing; the LLM operates BETWEEN script
invocations. It reads the printed step output, performs reasoning, decides
outcomes (e.g., QR PASS/FAIL), and invokes the next script. Scripts provide
structure; the LLM provides intelligence.

**Why no execution engine**: An earlier design had `Workflow.run()`, an
`Outcome` enum, and `StepContext` handlers executing steps in Python. It was
removed as dead code: step logic runs in the LLM's context, so Python-side
handlers had nothing to do. `Workflow`/`StepDef` survive as metadata
containers because the test harness needs an introspectable step inventory
(step count, order, CLI parameters) to exhaustively invoke every step.

### Prompt Layers: prompts/ vs ast/

Two prompt-generation generations coexist:

- `prompts/` -- plain-text building blocks composed via f-strings ("No XML,
  no AST"). Current direction; most skills and the planner use it.
- `ast/` -- typed nodes rendered to XML. Predates `prompts/`; still used by
  incoherence, leon-writing-style, and refactor.

New skills should use `prompts/`. Migration off `ast/` happens per-skill; the
XML wrapping added indirection without measurably improving LLM compliance,
which is why plain text won.

### Step Output Contract

`prompts/step.py:format_step()` assembles every step: optional title header,
body, then exactly one of:

- `NEXT STEP:` + working directory + command -- the LLM must execute it
  verbatim.
- Branching form (`if_pass`/`if_fail`) for QR gates -- the LLM counts PASS vs
  FAIL across agents and executes the matching command. Phrased as a
  mechanical routing decision to stop the LLM from re-litigating QR results.
- `WORKFLOW COMPLETE` when there is no next command.

The working directory is printed explicitly because CLI execution context
varies between sessions; the LLM cannot infer it.

## Core Types

### Workflow / StepDef / Arg (core.py)

Metadata only. `StepDef` is id/title/actions; `Workflow` validates duplicate
step IDs and entry-point existence at construction and exposes
`_step_order`/`total_steps` for the test harness. `Arg` annotates CLI
parameters (bounds, choices, required) so tests can generate valid inputs.

### Discovery (discovery.py)

`discover_workflows(package)` scans for module-level `WORKFLOW` constants via
importlib without executing skills' step logic.

- **Pull-based**: skills declare a constant; nothing registers itself at
  import time. Eliminates import-time side effects and enables isolated
  testing.
- **lib/ is skipped**: framework code would otherwise be registered as
  skills.
- **Errors aggregate**: all malformed modules are reported in one exception,
  preventing sequential fix-test cycles.

### CLI Entry (cli.py)

`mode_main()` is the standard entry point for mode scripts: parses `--step`
plus QR args, calls the script's `get_step_guidance()`, and prints via
`format_step()`. It injects `THINKING_EFFICIENCY` (terse-thinking mandate) on
step 1 only -- once per workflow is enough; repeating it every step wastes
tokens.

**Separate CLI entry points per script**: running modules as `__main__`
causes module identity issues (imported by `__init__.py` vs executed as
`__main__`), so each script is its own `-m` target.

### Domain Types (types.py)

Shared enums and dataclasses: `AgentRole`, `Confidence`, `Phase`/`Mode` (+
`PHASE_TO_MODE`), routing types (`LinearRouting`/`BranchRouting`/
`TerminalRouting`, `FlatCommand`/`BranchCommand`), `Dispatch`,
`StepGuidance`, and `BoundedInt` (test input domain).

`ResourceProvider` is a Protocol rather than a concrete import: QR/TW/Dev
modules receive it instead of importing `skills.planner.shared.resources`
directly, breaking a 3-layer circular dependency and enabling mock
implementations in unit tests.

### Prompt Constants (constants.py)

QR-related and dispatch-related prompt constants live in the lib layer so
prompt builders can use them without depending on planner. Includes the HITL
question-batching guidance, the sub-agent return token budget, and the
question relay constants below.

### Quality Docs (quality_docs.py)

`extract_content()` parses the machine-parseable code-quality documents
(HTML-comment metadata, `<design-mode>`/`<code-mode>` tags) and returns only
the content applicable to a given `Phase`. Stdlib-only by design -- no
markdown dependency.

## Question Relay Protocol

Sub-agents can request user clarification via the main agent. The protocol is
pure prompt coordination -- no Python interception.

### Design Decisions

**Task Reinvocation (not Resume)**: When a sub-agent yields with questions,
the orchestrator REINVOKES it fresh (new Task, no resume parameter) after
getting user answers. The sub-agent saves state to plan.json before yielding,
then reads it back after reinvocation. This was chosen over resume because:

- Resume semantics are unreliable (0 tokens, 0 tool uses failures)
- State file reading is explicit and auditable
- Clean slate avoids stale context issues
- Sub-agent scripts can detect continuation (plan.json exists)

**Questions-only output**: When a sub-agent needs clarification, it emits ONLY
the `<needs_user_input>` XML block. Nothing else. This makes detection
unambiguous -- no heuristic parsing of natural language.

**Explicit XML markers**: Structured XML tags rather than detecting question
marks in prose. This prevents false positives from rhetorical questions in
analysis output.

**Max 3 questions, 2-3 options**: Constraints match AskUserQuestion tool
schema. Batching reduces round-trips. Options should be distinct and
actionable.

**State saving before yield**: Sub-agents MUST save all progress to plan.json
before emitting `<needs_user_input>`. The reinvoked instance reads this state.

### Flow

1. Sub-agent saves current state to plan.json
2. Sub-agent emits `<needs_user_input>` XML as entire response
3. Main agent extracts questions, calls AskUserQuestion
4. Main agent REINVOKES sub-agent fresh with answers and STATE_DIR
5. New sub-agent instance reads plan.json, continues from saved state

### Constants

| Constant                    | Purpose                                  |
| --------------------------- | ---------------------------------------- |
| `SUB_AGENT_QUESTION_FORMAT` | Tells sub-agent how to emit questions    |
| `QUESTION_RELAY_HANDLER`    | Tells main agent how to detect and relay |

## Common Patterns

### Hybrid Static/Dynamic Steps

Workflows with mostly constant steps and a few parameterized steps (e.g.,
deepthink) use two dicts dispatched from one `format_output()`:

```python
# Static steps: (title, instructions) tuples -- one line per step
STATIC_STEPS = {
    1: ("Context Clarification", CONTEXT_CLARIFICATION_INSTRUCTIONS),
    2: ("Abstraction", ABSTRACTION_INSTRUCTIONS),
}

# Dynamic formatter functions -- defined BEFORE DYNAMIC_STEPS dict
def _format_step_9(mode: str, confidence: str, iteration: int) -> tuple[str, str]:
    return ("Dispatch", build_dispatch_body())

DYNAMIC_STEPS = {9: _format_step_9}

def format_output(step: int, mode: str, confidence: str, iteration: int) -> str:
    if step in STATIC_STEPS:
        title, instructions = STATIC_STEPS[step]
    elif step in DYNAMIC_STEPS:
        title, instructions = DYNAMIC_STEPS[step](mode, confidence, iteration)
    else:
        return f"ERROR: Invalid step {step}"
    next_cmd = build_next_command(step, mode, confidence, iteration)
    return format_step(instructions, next_cmd or "", title=f"WORKFLOW - {title}")
```

**Ordering constraint (book pattern)**: dynamic formatter functions that call
MESSAGE BUILDERS must appear AFTER those builders; the `DYNAMIC_STEPS` dict
must appear AFTER all `_format_step_*` functions it references. All
references resolve to definitions above.

Use when many steps share the same structure and only a few need parameters
for title or body construction.

## Design Decisions

**Why frozen dataclasses?** Workflows and StepDefs are immutable
specifications. Frozen dataclasses prevent accidental mutation and make them
safe to share.

**Centralized enums vs local**: One more place to update, in exchange for
discoverability and shared understanding. Shared enums make state machines
explicit and enable property-based testing.

**Clean break vs dual-path**: When the execution engine was removed, no
compatibility shim was kept. Refactoring scope was internal (no external
callers), so a clean break reduced total work and eliminated transition bugs.

## Invariants

- Every testable skill module appears in `SKILL_MODULES` in
  `tests/conftest.py`
- Step IDs within a Workflow are unique; `entry_point` must be a valid step
  (both enforced at construction)
- `Workflow._step_order` is the authoritative step index mapping:
  `len(_step_order) == total_steps` and indices correspond to CLI `--step`
  values
- The `NEXT STEP` / branching invoke directives printed by `format_step()`
  must remain mechanically executable -- the LLM copies them verbatim

## Testing

Exhaustive step testing is driven by the workflow metadata: parameter domains
are extracted from `Arg` annotations and enumerated as Cartesian products
(domain sizes are small, so exhaustive beats sampling). See `tests/` for the
framework.

All tests use pytest. Run from `skills/scripts/`:

```bash
# Run all tests
pytest tests/ -v

# Test specific workflow
pytest tests/ -k deepthink -v

# Test categories
pytest tests/test_workflow_import.py -v     # Import tests
pytest tests/test_workflow_structure.py -v  # Structure validation
pytest tests/test_workflow_steps.py -v      # Step invocability (exhaustive)
pytest tests/test_domain_types.py -v        # Domain type unit tests
```
