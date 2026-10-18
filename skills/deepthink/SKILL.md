---
name: deepthink
description: Invoke IMMEDIATELY via python script when user requests structured reasoning for open-ended analytical questions. Do NOT explore first - the script orchestrates the thinking workflow.
---

# DeepThink

Run the script first and follow its output; it orchestrates the work, so exploring or analyzing beforehand duplicates its steps.

Invoke:

<invoke working-dir=".claude/skills/scripts" cmd="python3 -m skills.deepthink.think --step 1" />
