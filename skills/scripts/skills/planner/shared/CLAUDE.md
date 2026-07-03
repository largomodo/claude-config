# shared/

Shared resources, schemas, and utilities for planner scripts.

## Files

| File                    | What                                                  | When to read                                |
| ----------------------- | ----------------------------------------------------- | ------------------------------------------- |
| `schema.py`             | Pydantic schemas for state files, validate_state()    | Modifying plan.json schema, state validation |
| `steps.py`              | Orchestrator step factories (work/decompose/verify/route) | Modifying QR block behavior in planner/executor |
| `constraints.py`        | Reusable constraint strings for orchestration prompts | Building planner/executor prompts           |
| `gates.py`              | Unified gate output builder (build_gate_output)       | Modifying QR gate logic                     |
| `builders.py`           | Shared string builders for planner output             | Modifying prompt/output assembly            |
| `constants.py`          | Workflow step configuration constants                 | Changing step counts, phase config          |
| `domain.py`             | Domain types for the planner skill                    | Adding planner domain types                 |
| `resources.py`          | Resource loading for planner scripts                  | Modifying template/resource injection       |
| `routing.py`            | Centralized routing logic for work phases             | Modifying phase routing                     |
| `temporal_detection.py` | Temporal contamination detection criteria             | Modifying TW/QR temporal checks             |
| `__init__.py`           | Package marker                                        | -                                           |

## Subdirectories

| Directory | What                                | When to read                          |
| --------- | ----------------------------------- | ------------------------------------- |
| `qr/`     | QR domain types, phases, CLI utils  | Modifying QR phases, item tracking    |
