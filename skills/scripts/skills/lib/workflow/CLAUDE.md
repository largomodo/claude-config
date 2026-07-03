# workflow/

Workflow orchestration framework: metadata types, discovery, and prompt/output generation.

## Files

| File              | What                                        | When to read                                        |
| ----------------- | ------------------------------------------- | --------------------------------------------------- |
| `README.md`       | Execution model, architecture, decisions    | Understanding framework design, prompt layers       |
| `core.py`         | Workflow, StepDef, Arg (metadata only)      | Defining new skills, workflow structure             |
| `discovery.py`    | Workflow discovery via importlib scanning   | Understanding pull-based discovery, troubleshooting |
| `cli.py`          | CLI helpers for workflow entry points       | Adding CLI arguments, step output helpers           |
| `constants.py`    | Shared constants, QR constants re-exports   | Adding new constants                                |
| `types.py`        | Domain types: Dispatch, AgentRole, etc.     | QR gates, sub-agent dispatch, test domains          |
| `quality_docs.py` | Content extraction from code quality docs   | Modifying quality doc parsing                       |
| `__init__.py`     | Public API exports                          | Importing workflow types                            |

## Subdirectories

| Directory     | What                                              | When to read                              |
| ------------- | ------------------------------------------------- | ----------------------------------------- |
| `prompts/`    | Plain-text prompt building blocks (current)       | Building step output, dispatch prompts    |
| `ast/`        | AST nodes, builder, renderer (older XML layer)    | Maintaining skills still using XML output |

## Test

```bash
pytest tests/ -v
pytest tests/ -k deepthink -v
```
