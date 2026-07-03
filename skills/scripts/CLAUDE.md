# scripts/

Python package root for all skill workflow code.

## Files

| File                      | What                                              | When to read                            |
| ------------------------- | ------------------------------------------------- | --------------------------------------- |
| `pytest.ini`              | Pytest config (pythonpath, testpaths)             | Debugging test discovery                |
| `validate_conventions.py` | CI check: get_convention() calls vs REGISTRY.yaml | Adding conventions, debugging CI        |

## Subdirectories

| Directory | What                                   | When to read                             |
| --------- | -------------------------------------- | ---------------------------------------- |
| `skills/` | Skill workflow modules and shared lib  | Modifying skill behavior                 |
| `tests/`  | Pytest suite for workflow framework    | Adding tests, debugging test failures    |

## Test

```bash
pytest tests/ -v
```
