---
name: refactor
description: Invoke IMMEDIATELY via python script when user requests refactoring analysis, technical debt review, or code quality improvement. Do NOT explore first - the script orchestrates exploration.
---

# Refactor

Run the script first and follow its output; it orchestrates the work, so exploring or analyzing beforehand duplicates its steps.

## Invocation

<invoke working-dir=".claude/skills/scripts" cmd="python3 -m skills.refactor.refactor --step 1 --n 10" />

| Argument | Required | Description                                   |
| -------- | -------- | --------------------------------------------- |
| `--step` | Yes      | Current step (starts at 1)                    |
| `--n`    | No       | Number of categories to explore (default: 10) |

## Determining N (category count)

Default: N = 10

Adjust based on user request scope:

- SMALL (single file, specific concern, "quick look"): N = 5
- MEDIUM (directory, module, standard analysis): N = 10
- LARGE (entire codebase, "thorough", "comprehensive"): N = 25

The script randomly selects N categories from the 38 available code quality categories defined in conventions/code-quality/.
