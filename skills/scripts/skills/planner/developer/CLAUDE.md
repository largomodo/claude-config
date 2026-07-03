# developer/

Developer sub-agent scripts for plan code filling and implementation.

## Files

| File                        | What                                        | When to read                       |
| --------------------------- | ------------------------------------------- | ---------------------------------- |
| `plan_code.py`              | Router: dispatches to execute or fix        | Debugging plan code routing        |
| `plan_code_execute.py`      | First-time code filling workflow            | Modifying plan code steps          |
| `plan_code_qr_fix.py`       | Targeted repair after plan-code QR failures | Modifying plan code QR fixes       |
| `exec_implement.py`         | Router: dispatches to execute or fix        | Debugging implementation routing   |
| `exec_implement_execute.py` | Wave-aware implementation workflow          | Modifying implementation steps     |
| `exec_implement_qr_fix.py`  | Targeted repair after impl-code QR failures | Modifying impl QR fixes            |
| `__init__.py`               | Package marker                              | -                                  |
