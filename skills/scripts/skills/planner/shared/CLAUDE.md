# shared/

Shared resources, schemas, and utilities for planner scripts.

## Files

| File                    | What                                                  | When to read                                |
| ----------------------- | ----------------------------------------------------- | ------------------------------------------- |
| `schema.py`             | Pydantic schemas for state files, validate_state(); QRItem carries the per-verdict iteration stamp | Modifying plan.json schema, state validation |
| `steps.py`              | Orchestrator step factories (work/decompose/verify/route); decompose dispatch text, verify walkthrough ordering | Modifying QR block behavior in planner/executor |
| `constraints.py`        | Reusable constraint strings for orchestration prompts | Building planner/executor prompts           |
| `gates.py`              | Unified gate output builder (build_gate_output)       | Modifying QR gate logic                     |
| `builders.py`           | Shared string builders for planner output             | Modifying prompt/output assembly            |
| `constants.py`          | Workflow step configuration constants, decompose step-count facts | Changing step counts, phase config          |
| `plan_scope.py`         | Per-milestone file scope from plan.json; scope-check delta report (`python3 -m skills.planner.shared.plan_scope`) | Changing fix-mode scope guidance, debugging out-of-scope edits |
| `provenance.py`         | Render/parse of the plan.md provenance header; sidecar file names | Changing plan.md handoff, executor state resolution |
| `domain.py`             | Domain types for the planner skill                    | Adding planner domain types                 |
| `resources.py`          | Resource loading for planner scripts; render_context_or_notice (context.json block or absent-file notice) | Modifying template/resource injection, context.json rendering |
| `routing.py`            | Centralized routing logic for work phases             | Modifying phase routing                     |
| `temporal_detection.py` | Temporal contamination detection criteria             | Modifying TW/QR temporal checks             |
| `__init__.py`           | Package marker                                        | -                                           |

## Subdirectories

| Directory | What                                | When to read                          |
| --------- | ----------------------------------- | ------------------------------------- |
| `qr/`     | QR domain types, phases, CLI utils  | Modifying QR phases, item tracking    |
