# cli/

CLI package for plan.json and QR state manipulation.

## Files

| File               | What                                              | When to read                          |
| ------------------ | ------------------------------------------------- | ------------------------------------- |
| `plan.py`          | Entrypoint for plan.json with CAS versioning      | Debugging plan state mutations        |
| `plan_commands.py` | Plan manipulation commands as plain functions; `translate` prepends the provenance header to plan.md | Adding/modifying plan commands, plan.md output |
| `qr.py`            | Atomic QR state mutation with file locking; iteration-stamped verdict transition error to CLI exit mapping (PASS->FAIL always, FAIL->PASS only in a later iteration) | Debugging QR state mutations, update-item rejections |
| `qr_commands.py`   | QR state manipulation commands as plain functions; iteration-stamped verdict transition check (PASS->FAIL always, FAIL->PASS only in a later iteration) | Adding/modifying QR commands, changing verdict rules |
| `dispatch.py`      | Generic batch RPC dispatch via introspection      | Modifying command dispatch            |
| `output.py`        | Shared output formatting for state mutation CLIs  | Modifying CLI output format           |
| `__init__.py`      | Package marker                                    | -                                     |
