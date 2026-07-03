# technical_writer/

Technical writer sub-agent scripts for plan and implementation documentation phases.

## Files

| File                   | What                                        | When to read                     |
| ---------------------- | ------------------------------------------- | -------------------------------- |
| `plan_docs.py`         | Router: dispatches to execute or fix        | Debugging plan docs routing      |
| `plan_docs_execute.py` | First-time documentation workflow           | Modifying plan docs steps        |
| `plan_docs_qr_fix.py`  | Targeted repair after plan-docs QR failures | Modifying plan docs QR fixes     |
| `exec_docs.py`         | Router: dispatches to execute or fix        | Debugging impl docs routing      |
| `exec_docs_execute.py` | Post-implementation documentation workflow  | Modifying impl docs steps        |
| `exec_docs_qr_fix.py`  | Targeted repair after impl-docs QR failures | Modifying impl docs QR fixes     |
| `__init__.py`          | Package marker                              | -                                |
