---
name: incoherence
description: Detect and resolve incoherence in documentation, code, specs vs implementation.
---

# Incoherence Detector

Run the script first and follow its output; it orchestrates the work, so exploring or analyzing beforehand duplicates its steps.

## Invocation

<invoke working-dir=".claude/skills/scripts" cmd="python3 -m skills.incoherence.incoherence --step-number 1 --thoughts '<context>'" />

| Argument        | Required | Description                               |
| --------------- | -------- | ----------------------------------------- |
| `--step-number` | Yes      | Current step (starts at 1)                |
| `--thoughts`    | Yes      | Accumulated state from all previous steps |

## Workflow Phases

1. **Detection (steps 1-12)**: Survey codebase, explore dimensions, verify
   candidates
2. **Resolution (steps 13-15)**: Present issues via AskUserQuestion, collect
   user decisions
3. **Application (steps 16-21)**: Apply resolutions, present final report

Resolution is interactive - user answers structured questions inline. No manual
file editing required.
