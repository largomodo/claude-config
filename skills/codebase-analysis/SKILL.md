---
name: codebase-analysis
description: Invoke IMMEDIATELY via python script when user requests codebase understanding, architecture comprehension, repository orientation, or to bootstrap project memories. Do NOT explore first - the script orchestrates exploration.
---

# Codebase Analysis

Understanding-focused skill that builds foundational comprehension of codebase structure, patterns, flows, decisions, and context. Serves as foundation for downstream analysis skills (problem-analysis, refactor, etc.).

Run the script first and follow its output; it orchestrates the work, so exploring or analyzing beforehand duplicates its steps. The synthesize step persists findings as Serena memories (mem:core graph) when Serena is configured, which is how a repository's navigation index is bootstrapped.

Invoke:

<invoke working-dir=".claude/skills/scripts" cmd="python3 -m skills.codebase_analysis.analyze --step 1" />
