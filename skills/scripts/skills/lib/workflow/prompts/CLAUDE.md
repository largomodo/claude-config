# prompts/

Plain-text prompt building blocks for workflows (f-string composition; no XML, no AST).

## Files

| File          | What                                                    | When to read                            |
| ------------- | ------------------------------------------------------- | --------------------------------------- |
| `step.py`     | format_step(): sole step output assembler               | Modifying step output, invoke_after     |
| `subagent.py` | Dispatch prompt building blocks (3 dispatch patterns)   | Modifying sub-agent dispatch prompts    |
| `file.py`     | File content embedding (4-backtick fences)              | Embedding file content in prompts       |
| `__init__.py` | Package exports                                         | Importing prompt helpers                |
