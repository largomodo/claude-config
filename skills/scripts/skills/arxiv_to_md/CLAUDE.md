# arxiv_to_md/

Python workflow scripts for the arxiv-to-md skill.

## Files

| File           | What                                           | When to read                              |
| -------------- | ---------------------------------------------- | ----------------------------------------- |
| `main.py`      | Orchestrator: parse input, dispatch sub-agents | Debugging discovery/dispatch/renaming     |
| `sub_agent.py` | Worker: convert a single arXiv paper           | Debugging single-paper conversion         |
| `tex_utils.py` | Pure Python TeX preprocessing utilities        | Debugging TeX cleanup before pandoc       |
| `__init__.py`  | Package marker                                 | -                                         |
