# skills/ (Python package)

Skill workflow modules, one package per skill, invoked as `python3 -m skills.<skill_name>.<module>`.

## Files

| File          | What           | When to read |
| ------------- | -------------- | ------------ |
| `__init__.py` | Package marker | -            |

## Subdirectories

| Directory             | What                                       | When to read                              |
| --------------------- | ------------------------------------------ | ----------------------------------------- |
| `lib/`                | Shared utilities and workflow framework    | Adding skills, modifying step handling    |
| `planner/`            | Planning/execution workflows with QR gates | Modifying planner, executor, QR logic     |
| `arxiv_to_md/`        | arXiv paper to markdown conversion         | Debugging paper conversion                |
| `codebase_analysis/`  | Codebase exploration workflow              | Debugging exploration steps               |
| `decision_critic/`    | Decision stress-testing workflow           | Debugging critique steps                  |
| `deepthink/`          | Structured reasoning workflow              | Debugging think/subagent steps            |
| `doc_sync/`           | Empty package marker only (no script)      | - (skill is prompt-only; see skills/doc-sync/) |
| `incoherence/`        | Incoherence detection workflow             | Debugging detection steps                 |
| `leon_writing_style/` | Style-compliance writing workflow          | Debugging writing style steps             |
| `problem_analysis/`   | Root cause analysis workflow               | Debugging analysis steps                  |
| `prompt_engineer/`    | Prompt optimization workflow               | Debugging optimization steps              |
| `refactor/`           | Refactoring analysis workflow              | Debugging dispatch/triage/cluster steps   |
