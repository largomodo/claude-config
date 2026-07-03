# ast/

AST module for workflow XML generation.

## Files

| File                   | What                                                          | When to read                    |
| ---------------------- | ------------------------------------------------------------- | ------------------------------- |
| `README.md`            | Architecture, usage examples, node inventory, decisions       | Constructing/rendering AST output |
| `nodes.py`             | Node types (Text, Code, Element, FileContent, StepHeader, CurrentAction, InvokeAfter) | Understanding node structure |
| `builder.py`           | Fluent builder API (`W.el()`)                                 | Constructing AST nodes          |
| `renderer.py`          | XMLRenderer, render(), step header/action/invoke renderers    | Rendering AST to XML output     |
| `dispatch.py`          | Dispatch node types (Subagent, Template, Roster)              | Subagent orchestration patterns |
| `dispatch_renderer.py` | Render functions for dispatch nodes                           | Rendering dispatch XML          |
| `__init__.py`          | Public API exports                                            | Importing AST types             |
