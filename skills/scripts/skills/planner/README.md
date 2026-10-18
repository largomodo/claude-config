# Planner

Planning and execution workflows with QR (Quality Review) gates, TW (Technical Writer) passes, and Dev (Developer) execution phases.

This document is authoritative for the planner skill architecture.

## Architecture: Python Scripts vs LLM

Python scripts emit workflow prompts and routing. The LLM operates BETWEEN script invocations:

1. Script outputs prompt/guidance for current step
2. LLM reads prompt, performs reasoning/assessment
3. LLM decides outcome (e.g., QR PASS/FAIL)
4. LLM invokes next script based on outcome

QR PASS/FAIL is determined by LLM reading QR output, not Python. Gate routing is LLM's decision based on QR outcome. Python scripts provide structure; LLM provides intelligence.

Per-run guidance for sub-agents lives in script text (step output and dispatch prompts), never in ad-hoc prompts the orchestrator writes. Script text is identical on every run and testable; ad-hoc prompts drift between runs.

## State Files

All state mutations (except initial context.json) happen via Python CLI commands. State directory created via `tempfile.mkdtemp()` in `/tmp`.

| File              | Schema         | Created     | Mutated By     | Lifecycle              |
| ----------------- | -------------- | ----------- | -------------- | ---------------------- |
| `plan.json`       | Pydantic v2    | Step 1 init | CLI commands   | mutable -> frozen      |
| `context.json`    | Loose JSON     | Step 2      | LLM Write tool | frozen after step 2    |
| `qr-{phase}.json` | QA item schema | QR dispatch | LLM during QR  | ephemeral per QR cycle |

### plan.json Schema

```
Plan
  schema_version: 2
  plan_id: UUID
  created_at: timestamp
  frozen_at: Optional[timestamp]

  overview:
    title, problem, approach

  planning_context:
    decision_log[]: id (DL-XXX), decision, reasoning_chain, timestamp
    rejected_alternatives[]: id (RA-XXX), alternative, rejection_reason, decision_ref
    constraints[]: id (C-XXX), type, description, source
    known_risks[]: id (R-XXX), risk, mitigation, anchor?, decision_ref?

  invisible_knowledge:
    architecture: {diagram_ascii, description}
    data_flow: {diagram_ascii, description}
    structure_rationale, invariants[], tradeoffs[]

  milestones[]:
    id (M-XXX), number, name, files[], flags[], requirements[], acceptance_criteria[]
    tests: files[], type?, backing?, scenarios{normal[], edge[], error[]}, skip_reason?
    code_intents[]: id (CI-XXX), file, function?, behavior, decision_refs[], params{}
    code_changes[]: id (CC-XXX), intent_ref, file, diff, context_lines, why_comments[]
    documentation: module_comment?, docstrings[], algorithm_blocks[], inline_comments[]
    is_documentation_only, delegated_to?

  milestone_dependencies:
    diagram_ascii
    waves[]: wave number, milestones[]
```

Reference integrity: code_change.intent_ref -> code_intent.id, decision_refs -> decision_log.id

### context.json Schema

User-provided context captured during planning:

```json
{
  "task_spec": ["goal", "scope", "out-of-scope"],
  "constraints": ["MUST: X", "SHOULD: Y"],
  "entry_points": ["file:function - why"],
  "rejected_alternatives": ["alternative - why dismissed"],
  "current_understanding": ["how system works"],
  "assumptions": ["inference (confidence)"],
  "invisible_knowledge": ["design rationale", "invariants"],
  "user_quotes": ["verbatim quote"]
}
```

### qr-{phase}.json Schema

Phases: `qr-plan-design`, `qr-plan-code`, `qr-plan-docs`, `qr-impl-code`, `qr-impl-docs`

```json
{
  "schema_version": "1.0",
  "phase": "plan-design",
  "iteration": 1,
  "items": [
    {
      "id": "qa-001",
      "scope": "*",
      "check": "...",
      "status": "TODO|PASS|FAIL",
      "finding": null,
      "iteration": 1
    }
  ]
}
```

The file-level `iteration` counts fix cycles. The per-item `iteration` is optional: the file iteration at which `status` was last written.

### QR verdict transitions

Every `update-item` write stamps the item with the file's current iteration. Inside one iteration a verdict moves only toward FAIL:

| From | To   | Result                                         |
| ---- | ---- | ---------------------------------------------- |
| TODO | PASS | accepted                                       |
| TODO | FAIL | accepted                                       |
| PASS | FAIL | accepted                                       |
| FAIL | FAIL | accepted                                       |
| PASS | PASS | no-op                                          |
| FAIL | PASS | accepted only when item.iteration < file iteration |

PASS stays downgradable because verify dispatch groups a parent with its children and the walkthrough can expose a child defect after the parent was recorded. The downgrade applies to items in the agent's own `--qr-item` list only: parallel verify agents hold disjoint item sets, and rewriting an item another agent owns would race with that agent's recording and break the rule that a verify agent mutates only assigned items. The transition check itself is item-agnostic; the own-list limit is enforced by the verify prompt text. FAIL stays sticky so a verify agent cannot soften a verdict it already wrote. An item without a stamp counts as recorded in the current iteration: treating it as older would allow FAIL->PASS with no fix cycle and no further evidence. `increment_qr_iteration` stamps unstamped items with the outgoing iteration, which is lower than the incremented one, so unstamped items release after one increment. A mistaken FAIL cannot be corrected inside its iteration; the cost is one extra fix-and-verify round, accepted because a correction path would also be a softening path. `cli/qr_commands.check_transition` is the single implementation, and `cli/qr.py` converts its error to a CLI exit; two copies of the rule would drift apart.

## Workflow Phases and Mutations

### Planner Workflow (14 steps)

Each phase runs a 4-step QR block: work -> decompose -> verify(N parallel) -> route.

| Step | Name                    | Pattern Function          | Mutates              | Agent            |
| ---- | ----------------------- | ------------------------- | -------------------- | ---------------- |
| 1    | plan-init               | `init_step()`             | Creates plan.json    | Orchestrator     |
| 2    | context-verify          | `verify_step()`           | Creates context.json | Orchestrator     |
| 3    | plan-design-work        | `execute_dispatch_step()` | plan.json            | Architect        |
| 4    | plan-design-qr-decompose| `qr_decompose_step()`     | qr-plan-design.json  | QR               |
| 5    | plan-design-qr-verify   | `qr_verify_step()`        | qr-plan-design.json  | QR (N parallel)  |
| 6    | plan-design-qr-route    | `qr_route_step()`         | -                    | Orchestrator     |
| 7    | plan-code-work          | `execute_dispatch_step()` | plan.json            | Developer        |
| 8    | plan-code-qr-decompose  | `qr_decompose_step()`     | qr-plan-code.json    | QR               |
| 9    | plan-code-qr-verify     | `qr_verify_step()`        | qr-plan-code.json    | QR (N parallel)  |
| 10   | plan-code-qr-route      | `qr_route_step()`         | -                    | Orchestrator     |
| 11   | plan-docs-work          | `execute_dispatch_step()` | plan.json            | TW               |
| 12   | plan-docs-qr-decompose  | `qr_decompose_step()`     | qr-plan-docs.json    | QR               |
| 13   | plan-docs-qr-verify     | `qr_verify_step()`        | qr-plan-docs.json    | QR (N parallel)  |
| 14   | plan-docs-qr-route      | `qr_route_step()`         | Renders plan.md      | Orchestrator     |

**Mutation details**:

- Step 3 (Architect): Populates planning_context, milestones[], code_intents[], invisible_knowledge
- Step 7 (Developer): Populates code_changes[] per milestone
- Step 11 (TW): Populates documentation[] per milestone; plan.md rendered on terminal gate pass

### Executor Workflow (10 steps)

Same QR block pattern as the planner, per implementation phase.

| Step | Name                    | Pattern Function          | Mutates           | Agent            |
| ---- | ----------------------- | ------------------------- | ----------------- | ---------------- |
| 1    | exec-init               | `exec_init_step()`        | Creates state dir | Orchestrator     |
| 2    | impl-code-work          | `execute_dispatch_step()` | Codebase files    | Developer        |
| 3    | impl-code-qr-decompose  | `qr_decompose_step()`     | qr-impl-code.json | QR               |
| 4    | impl-code-qr-verify     | `qr_verify_step()`        | qr-impl-code.json | QR (N parallel)  |
| 5    | impl-code-qr-route      | `qr_route_step()`         | -                 | Orchestrator     |
| 6    | impl-docs-work          | `execute_dispatch_step()` | Codebase docs     | TW               |
| 7    | impl-docs-qr-decompose  | `qr_decompose_step()`     | qr-impl-docs.json | QR               |
| 8    | impl-docs-qr-verify     | `qr_verify_step()`        | qr-impl-docs.json | QR (N parallel)  |
| 9    | impl-docs-qr-route      | `qr_route_step()`         | -                 | Orchestrator     |
| 10   | wave-next               | `wave_next_step()`        | -                 | Orchestrator     |

The TW phase (step 6) updates the memory index (`<dir>/core`, `mem:core`) and README.md. The impl-docs dispatch is the single memory writer. Without Serena, root CLAUDE.md + README.md suffice: the step skips the memory index, reports `Index: SKIPPED: no Serena`, and does not stall.

Step 9 routes a failing impl-docs QR back to step 6, so fix mode re-enters the
same single dispatch and a second writer never exists.

Reconciliation (validating existing code against the plan before executing)
is not a numbered step: step 1 re-invoked with `--reconciliation-check`
emits a per-milestone `exec_reconcile.py` dispatch block.

## Components

```
orchestrator/
  planner.py      14-step planning workflow
  executor.py     10-step execution workflow

architect/
  plan_design.py  Router; plan_design_execute.py / plan_design_qr_fix.py

developer/
  plan_code.py       Router; plan_code_execute.py / plan_code_qr_fix.py
  exec_implement.py  Router; exec_implement_execute.py / exec_implement_qr_fix.py

technical_writer/
  plan_docs.py    Router; plan_docs_execute.py / plan_docs_qr_fix.py
  exec_docs.py    Router; exec_docs_execute.py / exec_docs_qr_fix.py

quality_reviewer/
  {phase}_qr_decompose.py  Per-phase item generation (plan-design, plan-code,
  {phase}_qr_verify.py     plan-docs, impl-code, impl-docs)
  qr_verify_base.py        Shared verify base class
  exec_reconcile.py        Plan vs implementation reconciliation

shared/
  steps.py        Orchestrator step factories (work/decompose/verify/route),
                  shared by planner.py and executor.py
  gates.py        Unified gate output builder
  schema.py       Pydantic v2 schemas for state files, validate_state()
  routing.py      Work-phase router registry (execute vs qr_fix)
  resources.py    Path derivation, context loading
  builders.py     Shared string builders
  constraints.py  Orchestrator constraint builders
  qr/             QR utilities (types, constants, phases, utils, cli)

cli/
  plan.py         plan.json manipulation commands (CAS versioning)
  qr.py           qr-{phase}.json mutation commands (file locking)
```

## QR Gate Mechanics

QR gates use LoopState enum: INITIAL -> RETRY -> COMPLETE

```
INITIAL -> PASS -> COMPLETE (terminal)
INITIAL -> FAIL -> RETRY (iteration++)
RETRY   -> FAIL -> RETRY (iteration++)
RETRY   -> PASS -> COMPLETE (terminal)
```

Blocking severity by iteration:

| Iteration | Blocks              |
| --------- | ------------------- |
| 1-2       | MUST, SHOULD, COULD |
| 3-4       | MUST, SHOULD        |
| 5+        | MUST only           |

## Step Handler Architecture

Closures capture static config, handlers receive dynamic state:

```python
def execute_dispatch_step(title, agent, script, ...):
    def handler(ctx):  # Receives state_dir, qr, qr_fail
        return {"title": ..., "actions": ..., "next": ...}
    return handler

STEPS = {
    1: init_step("plan-init", ...),
    3: execute_dispatch_step("plan-design-work", agent="architect", ...),
    4: qr_decompose_step("plan-design-qr-decompose", phase="plan-design", ...),
    5: qr_verify_step("plan-design-qr-verify", phase="plan-design"),
    6: qr_route_step("plan-design-qr-route", work_step=3, pass_step=7, ...),
}
```

The QR block factories live in `shared/steps.py`, parameterized by the
calling orchestrator's module path, so planner.py and executor.py emit
identical QR block prompts and cannot drift apart.

## Design Decisions

**Closure-based step dispatch**: STEPS dict maps step numbers to handler closures. Pattern functions capture static config (title, agent, script), handlers receive dynamic state via ctx. Replaces magic keys with explicit patterns.

**Convention-based paths**: Sub-agents receive --state-dir, derive file paths via get_context_path(). Changing context.json location requires only updating resources.py.

**LLM-managed state**: State files written by LLM agents reading step guidance, not Python scripts. Leverages LLM capabilities for understanding context and following formats.

**JSON-IR-First**: plan.json is authoritative; plan.md derived from it.

**QR iteration blocking**: Severity thresholds vary by iteration. Early iterations block all severities. Later iterations block only MUST to prevent infinite loops.

**No temp directory cleanup**: OS handles /tmp cleanup on reboot.

**Plan handoff**: `plan.md` is a rendering of `plan.json`. The first line of the rendered file is an HTML comment, `<!-- planner-state: state_dir=<v> plan_id=<v> created_at=<v> -->`, with percent-encoded values and an absolute `/tmp` state_dir; it survives a plain file copy and is invisible when rendered. The line may be removed and execution still works through the other stages. The planner's terminal pass prints a DELIVER block naming the plan copy, optional sidecar copies named `<stem>.plan.json` and `<stem>.context.json` beside the delivered plan, and the executor `--plan-file` command. The executor resolves state in order: existing `plan.json` in STATE_DIR (never overwritten), sidecars, the provenance `state_dir` when it still holds `plan.json`, then a printed manual instruction. `context.json` is optional at every stage: execution runs from `plan.json`, and `context.json` only supplements the QR agents, so a missing one produces a notice instead of blocking. Plans rendered without the header take the manual path.

**Fix-mode file scope**: Fix-mode scripts print a PLAN FILE SCOPE block: per milestone, the union of `files`, `code_intents[].file` and `code_changes[].file`, as repo-root-relative paths (documentation companions included for the technical writer). The union is wider than `Milestone.files` alone because a milestone's file list can omit a path its intents or changes name, and a list that is visibly too narrow gets ignored; the union is still bounded by the plan, since it holds only paths the plan mentions. The fix agent, not the script, saves `git status --porcelain -uall` from the target repository root before editing and again before returning. Two snapshots keep uncommitted work that existed before the fix from being reverted: `python3 -m skills.planner.shared.plan_scope` classifies only paths absent from the baseline, and the agent reverts out-of-scope paths that appear only in the second snapshot unless a finding names them. The scripts run from the install directory, which usually belongs to a different repository than the plan's target, so the agent names the root (target-root rule) and a wrong root yields a notice, not a revert.

## Invariants

1. Every skill entry point defines exactly ONE Workflow
2. discover_workflows() finds all Workflows without import errors
3. plan.json is self-contained for execution
4. Frozen plan.json is immutable (frozen_at timestamp means no writes)
5. qr-{phase}.json files are ephemeral (exist only during QR cycle)
6. QR iteration blocking: iter 1-2 all; iter 3-4 MUST/SHOULD; iter 5+ MUST only
7. Wave coordination assumes sub-agents can spawn sub-agents (Claude Code
   v2.1.172+): executor step 2 dispatches one developer that coordinates
   parallel Task(developer) calls per wave
8. The first line of a verify agent's final response is exactly PASS or FAIL; the orchestrator tallies that line. After FAIL, the script-rendered `<id> [<severity>]: <finding>` lines (one per failing item) tell the orchestrator why. An item left TODO yields UNRECORDED record-and-rerun instructions instead of any verdict block; they print outside the BEGIN/END RESPONSE markers and do not reach the orchestrator.
9. Decompose agents run every step until `qr-{phase}.json` exists; the dispatch prompt and the decompose step 1 text both state this, quoting the step counts from `shared/constants.py`.
10. Verify walkthrough order per group: children before parents, umbrella (scope `*`) last. A parent whose `parent_id` lies outside the group counts as a child.
