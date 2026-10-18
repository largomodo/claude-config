#!/usr/bin/env python3
"""Impl docs execution - post-implementation documentation workflow.

6-step workflow for technical-writer sub-agent:
  1. Task Description (POST_IMPL type, deliverables)
  2. Extract Plan Information (IK, modified files, milestones)
  3. Memory Index Update (directory memories and the mem:core reference)
  4. README.md Creation (creation criteria, IK mapping)
  5. Verify Transcribed Comments (spot-check comment transcription)
  6. Output Format (documentation report)

This is the EXECUTE script for first-time post-impl documentation.
For QR fix mode, see exec_docs_qr_fix.py.
Router (exec_docs.py) dispatches to appropriate script.

Step 5 corrections go through Serena's s.edit.replace_content or an
s.edit.insert_before_symbol or s.edit.insert_after_symbol call (serena_repl) for code, Edit for docs -- applied
to the source file, never the plan file.
"""

from skills.planner.shared.constraints import format_state_banner


STEPS = {
    1: "Task Description",
    2: "Extract Plan Information",
    3: "Memory Index Update",
    4: "README.md Creation Criteria",
    5: "Verify Transcribed Comments",
    6: "Output Format",
}


def get_step_guidance(
    step: int, module_path: str = None, **kwargs) -> dict:
    """Return guidance for the given step."""
    MODULE_PATH = module_path or "skills.planner.technical_writer.exec_docs_execute"
    state_dir = kwargs.get("state_dir", "")
    state_dir_arg = f" --state-dir {state_dir}" if state_dir else ""

    if step == 1:
        banner = format_state_banner("TW-POST-IMPL", 1, "work")
        return {
            "title": STEPS[1],
            "actions": [
                banner,
                "",
                "TYPE: POST_IMPL",
                "",
                "TASK: Create documentation AFTER implementation is complete.",
                "",
                "You document what EXISTS. Implementation is done and stable.",
                "Code provided is correct and functional.",
                "",
                "PREREQUISITES:",
                "  - Plan file path (contains Invisible Knowledge, milestone descriptions)",
                "  - Implementation complete (all milestones executed)",
                "  - Quality review passed",
                "",
                "DELIVERABLES:",
                "  1. Memory index entries (<dir>/core and the mem:core reference) for modified directories",
                "  2. README.md if Invisible Knowledge has content",
                "  3. Verification that TW-prepared comments were transcribed",
                "",
                "Read the plan file now to understand what was implemented.",
            ],
            "next": f"python3 -m {MODULE_PATH} --step 2{state_dir_arg}",
        }

    elif step == 2:
        return {
            "title": STEPS[2],
            "actions": [
                "EXTRACT from plan file:",
                "",
                "1. INVISIBLE KNOWLEDGE section (if present):",
                "   - Architecture decisions not visible from code",
                "   - Tradeoffs made and why",
                "   - Invariants that must be maintained",
                "   - Assumptions underlying the design",
                "",
                "2. MODIFIED FILE LIST:",
                "   - From each milestone's ## Files section",
                "   - Group by directory for memory updates",
                "",
                "3. MILESTONE DESCRIPTIONS:",
                "   - What each milestone accomplished",
                "   - Use for the WHAT text of memory bullets",
                "",
                "Write out your extraction before proceeding:",
                "  EXTRACTION:",
                "  - Invisible Knowledge: [summary or 'none']",
                "  - Modified directories: [list]",
                "  - Key changes: [per milestone]",
            ],
            "next": f"python3 -m {MODULE_PATH} --step 3{state_dir_arg}",
        }

    elif step == 3:
        return {
            "title": STEPS[3],
            # Memory writes happen here because the impl-docs dispatch is the
            # single sub-agent memory writer; the docs preamble injected at
            # step 1 carries the grant, so developer runs never see it.
            "actions": [
                "UPDATE the memory index for each modified directory.",
                "",
                "SINGLE WRITER: you are the only agent that writes memories in this",
                "run. Parallel sub-agents writing the shared mem:core and <dir>/core",
                "files would race and overwrite each other, so do not delegate memory",
                "writes and do not expect any other agent to make them.",
                "",
                "MEMORY NAME: the modified directory's path relative to the Serena",
                "project root plus /core. Find the root by walking up from the",
                "directory to the nearest .serena/. When the repository is a subtree",
                "of that root the name carries the subtree prefix, e.g.",
                "claude-config/skills/planner/core.",
                "",
                "PROCEDURE (mcp__serena__serena_repl):",
                "  1. s.mem.list_memories() and s.mem.read_memory('core')",
                "  2. For each modified directory: read <dir>/core if it is listed",
                "  3. s.mem.write_memory (new) or s.mem.edit_memory (existing) <dir>/core",
                "  4. Add or keep a `mem:<dir>/core` bullet in mem:core, with the",
                "     when-to-read guidance in that bullet",
                "",
                "FORMAT (dense bullets in <dir>/core):",
                "```markdown",
                "- `handler.py` -- request handling, validation; read when debugging request flow, adding an endpoint",
                "- `types.py` -- data models, schemas; read when modifying data structures",
                "- `README.md` -- architecture decisions; read when understanding system design",
                "```",
                "",
                "INDEX RULES (from mem:memory_maintenance):",
                "  - WHAT: nouns and actions (handlers, validators, models)",
                "  - WHEN: task-based triggers using action verbs",
                "  - A memory never states when to read itself; the referring bullet does",
                "  - Name README.md by path when invisible knowledge exists",
                "  - ~200 tokens per memory; stable facts only",
                "  - Exclude generated files (build artifacts, caches)",
                "",
                "If mcp__serena__serena_repl is unavailable, skip this step and",
                "report Index: SKIPPED: no Serena.",
            ],
            "next": f"python3 -m {MODULE_PATH} --step 4{state_dir_arg}",
        }

    elif step == 4:
        return {
            "title": STEPS[4],
            "actions": [
                "CREATE README.md ONLY if Invisible Knowledge has content.",
                "",
                "CREATION CRITERIA (create if ANY apply):",
                "  - Planning decisions from Decision Log",
                "  - Business context (why the product works this way)",
                "  - Architectural rationale (why this structure)",
                "  - Trade-offs made (what sacrificed for what)",
                "  - Invariants (rules not enforced by types)",
                "  - Historical context (why not alternatives)",
                "  - Performance characteristics (non-obvious)",
                "  - Non-obvious relationships between files",
                "",
                "DO NOT create README.md if:",
                "  - Directory is purely organizational",
                "  - All knowledge visible from reading source code",
                "  - You would only restate what code already shows",
                "",
                "SELF-CONTAINED PRINCIPLE:",
                "  README.md must be self-contained.",
                "  Do NOT reference external sources (wikis, doc/ directories).",
                "  Summarize external knowledge in README.md.",
                "",
                "CONTENT TEST for each sentence:",
                "  'Could a developer learn this by reading source files?'",
                "  If YES -> delete the sentence",
                "  If NO -> keep it",
            ],
            "next": f"python3 -m {MODULE_PATH} --step 5{state_dir_arg}",
        }

    elif step == 5:
        return {
            "title": STEPS[5],
            "actions": [
                "SPOT-CHECK that Developer transcribed TW-prepared comments.",
                "",
                "Pick 2-3 modified files and verify:",
                "  1. Comments from plan's Code Changes appear in actual files",
                "  2. Comments are verbatim (not paraphrased)",
                "  3. Comments are in correct locations",
                "",
                "COMMON TRANSCRIPTION ISSUES:",
                "  - Comment missing entirely",
                "  - Comment paraphrased (lost precision)",
                "  - Comment in wrong location",
                "  - Temporal contamination introduced (check 5 categories)",
                "",
                "If issues found:",
                "  - Fix the comment in the actual source file",
                # This script runs with the docs preamble, so s.edit calls are permitted here.
                "  - Edit the source file directly, not the plan file (s.edit.replace_content / s.edit.insert_before_symbol / s.edit.insert_after_symbol via serena_repl for code; Edit for docs)",
                "",
                "This is verification, not comprehensive review.",
                "QR already validated; spot-check for transcription accuracy.",
            ],
            "next": f"python3 -m {MODULE_PATH} --step 6{state_dir_arg}",
        }

    elif step == 6:
        return {
            "title": STEPS[6],
            "actions": [
                "OUTPUT FORMAT:",
                "",
                "```",
                "Documented: [directory/] or [file:symbol]",
                "Type: POST_IMPL",
                "Tokens: [count]",
                "Index: [UPDATED | CREATED | VERIFIED | SKIPPED: no Serena]",
                "README: [CREATED | SKIPPED: reason]",
                "```",
                "",
                "Examples:",
                "",
                "```",
                "Documented: src/auth/ (memory: src/auth/core)",
                "Type: POST_IMPL",
                "Tokens: 180",
                "Index: UPDATED",
                "README: CREATED",
                "```",
                "",
                "```",
                "Documented: src/utils/",
                "Type: POST_IMPL",
                "Tokens: 95",
                "Index: CREATED",
                "README: SKIPPED: no invisible knowledge",
                "```",
                "",
                "If implementation unclear, add:",
                "  Missing: [what is needed]",
                "",
                "DO NOT include text before or after the format block.",
                "",
                "When complete, output: PASS",
            ],
            "next": "",
        }

    return {"error": f"Invalid step {step}"}


if __name__ == "__main__":
    from skills.lib.workflow.cli import mode_main

    mode_main(
        __file__,
        get_step_guidance,
        "Exec-Docs-Execute: Post-implementation documentation workflow",
        extra_args=[
            (["--state-dir"], {"type": str, "help": "State directory path"}),
        ],
    )
