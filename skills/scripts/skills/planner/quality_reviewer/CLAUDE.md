# quality_reviewer/

Quality Review scripts: per-phase decompose/verify pairs plus reconciliation.

## Files

| File                         | What                                           | When to read                              |
| ---------------------------- | ---------------------------------------------- | ----------------------------------------- |
| `README.md`                  | QR architecture, QA integration, decisions     | Understanding QR workflow, state tracking |
| `qr_verify_base.py`          | Base class for QR verify scripts               | Modifying shared verify behavior          |
| `plan_design_qr_decompose.py`| QR decomposition for plan-design phase         | Modifying plan design review items        |
| `plan_design_qr_verify.py`   | QR verification for plan-design phase          | Modifying plan design verification        |
| `plan_code_qr_decompose.py`  | QR decomposition for plan-code phase           | Modifying plan code review items          |
| `plan_code_qr_verify.py`     | QR verification for plan-code phase            | Modifying plan code verification          |
| `plan_docs_qr_decompose.py`  | QR decomposition for plan-docs phase           | Modifying plan docs review items          |
| `plan_docs_qr_verify.py`     | QR verification for plan-docs phase            | Modifying plan docs verification          |
| `impl_code_qr_decompose.py`  | QR decomposition for impl-code phase           | Modifying impl code review items          |
| `impl_code_qr_verify.py`     | QR verification for impl-code phase            | Modifying impl code verification          |
| `impl_docs_qr_decompose.py`  | QR decomposition for impl-docs phase           | Modifying impl docs review items          |
| `impl_docs_qr_verify.py`     | QR verification for impl-docs phase            | Modifying impl docs verification          |
| `exec_reconcile.py`          | Plan vs implementation reconciliation          | Modifying reconciliation logic            |
| `__init__.py`                | Package marker                                 | -                                         |

## Subdirectories

| Directory  | What                                     | When to read                            |
| ---------- | ---------------------------------------- | --------------------------------------- |
| `prompts/` | Shared decomposition prompts and utils   | Modifying decomposition prompt assembly |
