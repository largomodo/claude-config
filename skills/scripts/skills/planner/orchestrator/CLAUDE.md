# orchestrator/

Main planner and executor workflows that drive all phases.

## Files

| File          | What                                     | When to read                              |
| ------------- | ---------------------------------------- | ----------------------------------------- |
| `planner.py`  | Plan creation workflow (phases, QR gates); terminal pass renders plan.md with provenance header and prints the DELIVER block | Modifying planning flow, gate routing, plan delivery |
| `executor.py` | Plan execution workflow (milestones); `--plan-file` resolves plan.json/context.json into STATE_DIR | Modifying execution flow, milestone loop, state resolution |
| `__init__.py` | Package marker                            | -                                        |
