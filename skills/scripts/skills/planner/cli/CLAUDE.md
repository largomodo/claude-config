# cli/

CLI package for plan.json and QR state manipulation.

## Files

| File               | What                                              | When to read                          |
| ------------------ | ------------------------------------------------- | ------------------------------------- |
| `plan.py`          | Entrypoint for plan.json with CAS versioning      | Debugging plan state mutations        |
| `plan_commands.py` | Plan manipulation commands as plain functions     | Adding/modifying plan commands        |
| `qr.py`            | Atomic QR state mutation with file locking        | Debugging QR state mutations          |
| `qr_commands.py`   | QR state manipulation commands as plain functions | Adding/modifying QR commands          |
| `dispatch.py`      | Generic batch RPC dispatch via introspection      | Modifying command dispatch            |
| `output.py`        | Shared output formatting for state mutation CLIs  | Modifying CLI output format           |
| `__init__.py`      | Package marker                                    | -                                     |
