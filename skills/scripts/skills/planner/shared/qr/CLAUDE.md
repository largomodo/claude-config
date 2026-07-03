# qr/

QR (Quality Review) domain types and utilities shared across QR scripts.

## Files

| File           | What                                             | When to read                          |
| -------------- | ------------------------------------------------ | ------------------------------------- |
| `phases.py`    | Single source of truth for QR phase configs      | Adding QR phases, changing phase config |
| `types.py`     | QR domain types                                  | Modifying QR item/state types         |
| `constants.py` | QR workflow constants and routing configuration  | Changing QR limits, routing           |
| `cli.py`       | CLI utilities for QR workflows                   | Modifying QR CLI behavior             |
| `utils.py`     | State utilities for item verification and fixes  | Debugging item-level QR state         |
| `__init__.py`  | Package exports                                  | Importing QR types                    |
