# orchestrator/

Main planner and executor workflows that drive all phases.

## Files

| File          | What                                     | When to read                              |
| ------------- | ---------------------------------------- | ----------------------------------------- |
| `planner.py`  | Plan creation workflow (phases, QR gates) | Modifying planning flow, gate routing    |
| `executor.py` | Plan execution workflow (milestones)      | Modifying execution flow, milestone loop |
| `__init__.py` | Package marker                            | -                                        |
