---
name: prompt-engineer
description: Invoke IMMEDIATELY via python script when user requests prompt optimization. Do NOT analyze first - invoke this skill immediately.
---

# Prompt Engineer

Run the script first and follow its output; it orchestrates the work, so exploring or analyzing beforehand duplicates its steps.

## Invocation

Start with step 1 (triage) to determine scope:

<invoke working-dir=".claude/skills/scripts" cmd="python3 -m skills.prompt_engineer.optimize --step 1" />

Then continue with determined scope:

<invoke working-dir=".claude/skills/scripts" cmd="python3 -m skills.prompt_engineer.optimize --step 2 --scope <scope>" />

| Argument  | Required | Description                                   |
| --------- | -------- | --------------------------------------------- |
| `--step`  | Yes      | Current step (1 = triage, 2-6 = workflow)     |
| `--scope` | For 2+   | Required for steps 2-6. Determined by step 1. |

### Scopes

- **single-prompt**: One prompt file, general optimization
- **ecosystem**: Multiple related prompts that interact
- **greenfield**: No existing prompt, designing from requirements
- **problem**: Existing prompt(s) with specific issue to fix
