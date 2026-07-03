# planner/

Planning and execution workflows with QR gates, TW passes, and Dev execution.

## Files

| File          | What                                                | When to read                                     |
| ------------- | --------------------------------------------------- | ------------------------------------------------ |
| `README.md`   | Architecture, state file schemas, QR gates, design decisions | Understanding planner architecture, state files, QR workflows |
| `__init__.py` | Package marker                                      | -                                                |

## Subdirectories

| Directory           | What                                       | When to read                               |
| ------------------- | ------------------------------------------ | ------------------------------------------ |
| `orchestrator/`     | Main workflows (planner, executor)         | Creating/executing plans                   |
| `architect/`        | Plan design sub-agent scripts              | Understanding planning workflow            |
| `developer/`        | Code filling and implementation scripts    | Dev execution, diff creation               |
| `technical_writer/` | Documentation generation scripts           | TW passes, temporal cleanup                |
| `quality_reviewer/` | Per-phase QR decompose/verify scripts      | QR logic, validation, understanding gates  |
| `cli/`              | plan.json and QR state manipulation CLIs   | Debugging state mutations, CAS versioning  |
| `shared/`           | Schemas, constraints, gates, routing, QR types | Modifying schemas, gate logic, routing |
