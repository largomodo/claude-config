#!/usr/bin/env python3
"""QR verification for plan-docs phase.

Single-item verification mode for parallel QR dispatch.
Each verify agent receives --qr-item and validates ONE check.

Scope: Documentation quality only -- verifying that planning knowledge is
captured in documentation fields. This is NOT code review.

In scope:
- Invisible knowledge coverage (decisions documented somewhere)
- Temporal contamination in documentation strings
- WHY-not-WHAT quality in comments
- Structural completeness of documentation{} fields
- decision_ref validity

Out of scope (verified in plan-code phase):
- Code correctness (compilation, exports, types)
- Diff format validity
- Whether planned files exist on disk

For decomposition (generating items), see plan_docs_qr_decompose.py.
"""

from skills.planner.shared.qr.utils import (
    get_qr_iteration,
    has_qr_failures,
    format_qr_result,
)
from skills.planner.shared.schema import get_qa_state_schema_example
from .qr_verify_base import VerifyBase


PHASE = "plan-docs"


class PlanDocsVerify(VerifyBase):
    """QR verification for plan-docs phase."""

    PHASE = "plan-docs"

    def get_verification_guidance(self, item: dict, state_dir: str) -> list[str]:
        """Plan-docs-specific verification instructions."""
        scope = item.get("scope", "*")
        check = item.get("check", "")

        guidance = [
            "SCOPE CONSTRAINT: Verify doc_diff content ONLY.",
            "  - Review doc_diff fields, NOT diff fields",
            "  - diff field is OUT OF SCOPE (verified in plan-code)",
            "  - Verify against plan.json content, NOT filesystem",
            "",
            "EXTRACT doc_diffs:",
            f"  cat {state_dir}/plan.json | jq '[.milestones[].code_changes[] | {{id, file, doc_diff}}]'",
            "",
        ]

        if scope == "*":
            guidance.extend([
                "MACRO CHECK - Verify doc_diff across entire plan.json:",
                "",
                f"  Extract all doc_diffs:",
                f"    cat {state_dir}/plan.json | jq '[.milestones[].code_changes[] | {{id, file, diff: (.diff != \"\"), doc_diff: (.doc_diff != \"\")}}]'",
                "",
            ])
        elif scope.startswith("decision:"):
            dl_id = scope.split(":")[1]
            guidance.extend([
                f"DECISION COVERAGE CHECK - Focus on {dl_id}:",
                "",
                f"  Extract decision:",
                f"    cat {state_dir}/plan.json | jq '.planning_context.decisions[] | select(.id == \"{dl_id}\")'",
                "",
                f"  Verify this decision's rationale is EXPRESSED in at least one",
                f"  doc_diff as self-contained timeless prose: read the decision's",
                f"  reasoning above, then read doc_diff additions for content that",
                f"  carries the same WHY (semantic match, not id grep).",
                "",
                f"  NEGATIVE CHECK -- the DL id itself must NOT appear in doc_diff",
                f"  content (plan-artifact reference; the plan does not ship with",
                f"  the code, so the ref dangles for readers):",
                f"    cat {state_dir}/plan.json | jq -r '.milestones[].code_changes[].doc_diff' | grep -in '{dl_id}'   # expect no output",
                "",
            ])
        elif scope.startswith("change:"):
            cc_id = scope.split(":")[1]
            guidance.extend([
                f"CODE_CHANGE DOC_DIFF CHECK - Focus on {cc_id}:",
                "",
                f"  Extract code_change:",
                f"    cat {state_dir}/plan.json | jq '.milestones[].code_changes[] | select(.id == \"{cc_id}\")'",
                "",
                "  Verify:",
                "  - If diff is non-empty, doc_diff should be non-empty",
                "  - doc_diff should be valid unified diff format",
                "  - No temporal contamination in doc_diff additions",
                "",
            ])
        elif scope.startswith("milestone:"):
            ms_id = scope.split(":")[1]
            guidance.extend([
                f"MILESTONE DOC_DIFF CHECK - Focus on {ms_id}:",
                "",
                f"  Extract milestone code_changes with doc_diff status:",
                f"    cat {state_dir}/plan.json | jq '.milestones[] | select(.id == \"{ms_id}\") | .code_changes[] | {{id, file, has_diff: (.diff != \"\"), has_doc_diff: (.doc_diff != \"\")}}'",
                "",
                "  Verify each code_change with diff has doc_diff.",
                "",
            ])
        else:
            # Generic scope -- still constrain to plan.json
            guidance.extend([
                f"SCOPED CHECK - Scope: {scope}",
                "",
                f"  Extract doc_diffs:",
                f"    cat {state_dir}/plan.json | jq '[.milestones[].code_changes[] | {{id, file, doc_diff}}]'",
                "",
                "  Find the relevant doc_diff and verify.",
                "",
            ])

        # Add check-specific guidance
        if "temporal" in check.lower():
            guidance.extend([
                "TEMPORAL CONTAMINATION CHECK in doc_diff:",
                "  Scan doc_diff additions (lines starting with +) for:",
                "  - CHANGE_RELATIVE: 'Added', 'Replaced', 'Changed', 'Now uses'",
                "  - BASELINE_REFERENCE: 'instead of', 'previously', 'replaces'",
                "  - LOCATION_DIRECTIVE: 'After X', 'Before Y', 'Insert'",
                "  - PLANNING_ARTIFACT: 'TODO', 'Will', 'Planned'",
                "  - INTENT_LEAKAGE: 'intentionally', 'deliberately', 'chose'",
                "  - PLAN_ARTIFACT_REFERENCE: '(ref: DL-XXX)', DL-/CI-/CC-/M- ids,",
                "    plan file names, dates -- pointers to planning documents that",
                "    do not ship with the code",
                "",
                "  Mechanical scan for plan-artifact refs:",
                f"    cat {state_dir}/plan.json | jq -r '.milestones[].code_changes[].doc_diff' | grep -nE '\\(ref:|DL-[0-9]|CC-M-|CI-M-'   # expect no output",
                "",
            ])
        elif "baseline" in check.lower():
            guidance.extend([
                "BASELINE REFERENCE CHECK in doc_diff:",
                "  Look for references to removed/replaced code in doc_diff additions:",
                "  - 'Previously', 'Instead of', 'Replaces', 'Used to'",
                "  - 'Before this change', 'Old approach', 'Former'",
                "  Documentation should stand alone without knowing prior state.",
                "",
            ])
        elif "code_without_docs" in check.lower() or "missing doc_diff" in check.lower():
            guidance.extend([
                "CODE WITHOUT DOCS CHECK:",
                "  Verify code_changes with non-empty diff have non-empty doc_diff:",
                f"    cat {state_dir}/plan.json | jq '.milestones[].code_changes[] | select(.diff != \"\" and .doc_diff == \"\") | .id'",
                "",
                "  If any IDs returned, those code_changes need doc_diff.",
                "",
            ])
        elif "invalid" in check.lower() and "diff" in check.lower():
            guidance.extend([
                "INVALID DIFF FORMAT CHECK:",
                "  doc_diff must be valid unified diff format:",
                "  - Should start with '---', '@@', or 'diff'",
                "  - Should have proper hunk headers",
                "  - Lines should start with +, -, or space (context)",
                "",
            ])
        elif "decision" in check.lower() and ("coverage" in check.lower() or "uncovered" in check.lower()):
            guidance.extend([
                "DECISION COVERAGE CHECK:",
                "  Each decision's rationale must be EXPRESSED in at least one",
                "  doc_diff as self-contained timeless prose. The DL-XXX id itself",
                "  must NOT appear in doc_diff content -- the decision log is a",
                "  planning artifact that does not ship with the code.",
                "",
                "  List all decisions with reasoning:",
                f"    cat {state_dir}/plan.json | jq '.planning_context.decisions[] | {{id, decision, reasoning}}'",
                "",
                "  For each decision, read doc_diff additions and confirm the",
                "  rationale content appears (semantic match, not id grep).",
                "",
                "  NEGATIVE CHECK -- no DL ids leaked into doc_diffs:",
                f"    cat {state_dir}/plan.json | jq -r '.milestones[].code_changes[].doc_diff' | grep -o 'DL-[0-9]\\+' | sort -u   # expect empty",
                "",
            ])
        elif "why" in check.lower() and "what" in check.lower():
            guidance.extend([
                "WHY-NOT-WHAT VERIFICATION in doc_diff:",
                "  Comments in doc_diff additions should explain reasoning, not describe code.",
                "  BAD: '// Added a new function' (describes action)",
                "  GOOD: '// Mutex serializes cache access' (explains purpose)",
                "",
            ])
        elif "docstring" in check.lower():
            guidance.extend([
                "MISSING DOCSTRING CHECK:",
                "  For functions added/modified in diff, verify doc_diff",
                "  includes docstring additions.",
                "",
                "  Look for function definitions in diff, then verify doc_diff",
                "  has corresponding documentation comments.",
                "",
            ])
        elif "coverage" in check.lower() or "captured" in check.lower():
            guidance.extend([
                "DECISION COVERAGE CHECK:",
                "  Verify planning knowledge appears in doc_diff fields:",
                "  - Each decision's rationale is expressed in at least one",
                "    doc_diff as self-contained timeless prose",
                "  - The DL-XXX id itself must NOT appear in doc_diff content",
                "    (plan-artifact reference; the plan does not ship with the code)",
                "",
                "  NEGATIVE CHECK -- no DL ids leaked into doc_diffs:",
                f"    cat {state_dir}/plan.json | jq -r '.milestones[].code_changes[].doc_diff' | grep -o 'DL-[0-9]\\+' | sort -u   # expect empty",
                "",
            ])

        return guidance


def get_step_guidance(step: int, module_path: str = None, **kwargs) -> dict:
    """Gateway normalizes input and delegates to base class."""
    module_path = module_path or "skills.planner.quality_reviewer.plan_docs_qr_verify"
    qr_item = kwargs.get("qr_item")
    state_dir = kwargs.get("state_dir", "")

    if qr_item:
        # Normalize to list (backwards compat if single string passed)
        items = qr_item if isinstance(qr_item, list) else [qr_item]
        kwargs["qr_item"] = items
        verifier = PlanDocsVerify()
        return verifier.get_step_guidance(step, module_path, **kwargs)

    return {
        "title": "Error: No Items",
        "actions": ["--qr-item required. Use: --qr-item a --qr-item b"],
        "next": "",
    }


if __name__ == "__main__":
    from skills.lib.workflow.cli import mode_main
    mode_main(
        __file__,
        get_step_guidance,
        "QR-Plan-Docs: Documentation quality validation workflow",
        extra_args=[
            (["--state-dir"], {"type": str, "help": "State directory path"}),
            (["--qr-item"], {"action": "append", "help": "Item ID (repeatable)"}),
        ],
    )
