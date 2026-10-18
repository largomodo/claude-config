---
name: arxiv-to-md
description: Convert arXiv papers to LLM-consumable markdown. Invoke when user provides an arXiv ID or URL, or when syncing academic papers from a PDF folder to a markdown destination.
---

# arXiv to Markdown

Convert arXiv papers (TeX source) to clean markdown for LLM consumption.

## Invocation

<invoke working-dir=".claude/skills/scripts" cmd="python3 -m skills.arxiv_to_md.main --step 1" />

Run the script first and follow its output; it orchestrates the work, so exploring or analyzing beforehand duplicates its steps.
