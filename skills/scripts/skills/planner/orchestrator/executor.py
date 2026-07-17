#!/usr/bin/env python3
"""
Plan Executor - Execute approved plans through delegation.

10-step execution workflow per INTENT.md:

Flow:
  1. exec-init (wave analysis; optional reconciliation of existing code)
  2. impl-code-work (developer sub-agent, wave-aware parallel)
  3. impl-code-qr-decompose -> 4. verify(N) -> 5. route
  6. impl-docs-work (technical-writer)
  7. impl-docs-qr-decompose -> 8. verify(N) -> 9. route
  10. wave-next (loop to 2 for next wave, or EXECUTION COMPLETE)

QR Block Pattern (4 steps per phase):
  N   work        1 agent (dev/TW router)        Modified files
  N+1 decompose   1 agent (QR)                   qr-{phase}.json
  N+2 verify      N agents (parallel, expanded)  Each: PASS or FAIL
  N+3 route       0 agents (orchestrator)        Loop to N or proceed to N+4
"""

import argparse
import sys
import tempfile

from skills.lib.workflow.types import AgentRole
from skills.lib.workflow.constants import QUESTION_RELAY_HANDLER
from skills.lib.workflow.prompts import subagent_dispatch
from skills.lib.workflow.prompts.step import format_step
from skills.planner.shared.qr.types import QRState, QRStatus, LoopState
from skills.planner.shared.gates import GateResult
from skills.planner.shared.qr.cli import add_qr_args
from skills.planner.shared.resources import get_mode_script_path
from skills.planner.shared.builders import THINKING_EFFICIENCY
from skills.planner.shared.constants import (
    EXECUTOR_TOTAL_STEPS,
    EXECUTOR_GATE_STEPS,
    validate_step_count,
)
from skills.planner.shared.steps import (
    execute_dispatch_step as shared_execute_dispatch_step,
    qr_decompose_step as shared_qr_decompose_step,
    qr_verify_step as shared_qr_verify_step,
    qr_route_step as shared_qr_route_step,
)


MODULE_PATH = "skills.planner.orchestrator.executor"

# Signals in the user request that suggest existing code may already
# satisfy milestones. Surfaced in step 1 output so the LLM knows when
# to re-invoke with --reconciliation-check.
RECONCILIATION_SIGNALS = (
    "already implemented", "resume", "partially complete",
    "existing code", "continue from",
)


# =============================================================================
# Step Pattern Functions
# =============================================================================
#
# QR block factories (work/decompose/verify/route) live in shared/steps.py,
# shared with planner.py. Wrappers below bind this orchestrator's MODULE_PATH.
# Only exec_init_step and wave_next_step are executor-specific.

def execute_dispatch_step(title, agent, script, phase=None, post_dispatch=None):
    """Steps 2, 6: work execution dispatch."""
    return shared_execute_dispatch_step(
        MODULE_PATH, title, agent, script, phase=phase,
        post_dispatch=post_dispatch, fix_banner="IMPL-FIX")


def qr_decompose_step(title, phase, script, model=None):
    """Steps 3, 7: QR decomposition dispatch."""
    return shared_qr_decompose_step(MODULE_PATH, title, phase, script, model=model)


def qr_verify_step(title, phase):
    """Steps 4, 8: Parallel QR verification with group-aware dispatch."""
    return shared_qr_verify_step(MODULE_PATH, title, phase)


def qr_route_step(title, phase, work_step, pass_step, pass_message, fix_target=None):
    """Steps 5, 9: Route based on aggregated QR results."""
    return shared_qr_route_step(
        MODULE_PATH, "executor", title, phase, work_step, pass_step,
        pass_message, fix_target=fix_target)


def _reconciliation_actions() -> list[str]:
    """Reconciliation dispatch block for step 1 (--reconciliation-check)."""
    reconcile_script = get_mode_script_path("quality_reviewer/exec_reconcile.py")
    dispatch = subagent_dispatch(
        agent_type="quality-reviewer",
        command=f"python3 -m {reconcile_script} --step 1 --milestone N",
    )
    return [
        "",
        "RECONCILIATION: Validate existing code against plan requirements",
        "BEFORE executing.",
        "",
        "For EACH milestone, launch quality-reviewer agent (substitute N):",
        "",
        dispatch,
        "",
        "Expected output per milestone: SATISFIED | NOT_SATISFIED | PARTIALLY_SATISFIED",
        "",
        "ROUTING:",
        "  SATISFIED           -> Mark milestone complete, skip execution",
        "  NOT_SATISFIED       -> Execute milestone normally",
        "  PARTIALLY_SATISFIED -> Execute only missing parts",
        "",
        "Parallel execution: May run reconciliation for multiple milestones",
        "in parallel (multiple Task calls in single response) when milestones",
        "are independent.",
    ]


def exec_init_step(title):
    """Step 1: wave analysis; creates state_dir when not provided.

    The state directory holds plan.json (the approved plan) and the
    qr-{phase}.json files written by QR decompose/verify. When execution
    follows planning in the same session, pass the planner's STATE_DIR
    so the frozen plan.json is reused directly.
    """
    def handler(ctx):
        state_dir = ctx["state_dir"]
        if not state_dir:
            state_dir = tempfile.mkdtemp(prefix="executor-")
            print(f"STATE_DIR={state_dir}")

        actions = [
            "Plan file: $PLAN_FILE (substitute from context)",
            "",
            "STATE: Ensure STATE_DIR holds plan.json (approved plan) and",
            "context.json (planning context). QR verify agents read both.",
            "  - Executing right after planning: pass the planner's STATE_DIR",
            "    (both files already present).",
            "  - Fresh session from a plan file: copy the plan's plan.json and",
            "    context.json into STATE_DIR before step 2.",
            "",
            "ANALYZE plan:",
            "  - Count milestones and parse dependency diagram",
            "  - Group milestones into WAVES for execution",
            "  - Set up TodoWrite tracking",
            "",
            "WAVE ANALYSIS:",
            "  Parse the plan's 'Milestone Dependencies' diagram.",
            "  Group into waves: milestones at same depth = one wave.",
            "",
            "  Example diagram:",
            "    M0 (foundation)",
            "     |",
            "     +---> M1 (auth)     \\",
            "     |                    } Wave 2 (parallel)",
            "     +---> M2 (users)    /",
            "     |",
            "     +---> M3 (posts) ----> M4 (feed)",
            "            Wave 3          Wave 4",
            "",
            "  Output format:",
            "    Wave 1: [0]       (foundation, sequential)",
            "    Wave 2: [1, 2]    (parallel)",
            "    Wave 3: [3]       (sequential)",
            "    Wave 4: [4]       (sequential)",
        ]

        if ctx.get("reconciliation_check"):
            actions.extend(_reconciliation_actions())
        else:
            actions.extend([
                "",
                "RECONCILIATION CHECK:",
                f"  IF the user request signals existing work ({', '.join(RECONCILIATION_SIGNALS)}):",
                f"  re-invoke: python3 -m {MODULE_PATH} --step 1 --state-dir {state_dir} --reconciliation-check",
            ])

        actions.extend([
            "",
            "WORKFLOW:",
            "  This step is ANALYSIS ONLY. Do NOT delegate implementation yet.",
            "  Record wave groupings for step 2 (Implementation).",
        ])

        return {
            "title": title,
            "actions": actions,
            "next": f"python3 -m {MODULE_PATH} --step 2 --state-dir {state_dir}",
        }

    return handler


def wave_next_step(title):
    """Step 10: advance to next wave or complete execution."""
    def handler(ctx):
        state_dir = ctx["state_dir"]

        actions = [
            "CHECK wave progress against the wave list from step 1:",
            "",
            "IF unimplemented waves remain:",
            f"  invoke: python3 -m {MODULE_PATH} --step 2 --state-dir {state_dir}",
            "",
            "IF ALL waves complete: EXECUTION COMPLETE.",
            "",
            "PRESENT retrospective to user (do not write to file):",
            "",
            "EXECUTION RETROSPECTIVE",
            "=======================",
            "Plan: [path]",
            "Status: COMPLETED | BLOCKED | ABORTED",
            "",
            "Milestone Outcomes: | Milestone | Status | Notes |",
            "Reconciliation Summary: [if run]",
            "Plan Accuracy Issues: [if any]",
            "Deviations from Plan: [if any]",
            "Quality Review Summary: [counts by category]",
            "Feedback for Future Plans: [actionable suggestions]",
        ]

        return {
            "title": title,
            "actions": actions,
            "next": "",
        }

    return handler


# =============================================================================
# Step Definitions (1-10)
# =============================================================================

STEPS = {
    1: exec_init_step(
        title="exec-init",
    ),
    # Impl-code phase (steps 2-5)
    2: execute_dispatch_step(
        title="impl-code-work",
        agent="developer",
        script="developer/exec_implement.py",
        phase="impl-code",
        post_dispatch=[
            "The sub-agent executes milestones wave-aware:",
            "  - Milestones within same wave: PARALLEL dispatch",
            "  - Waves: SEQUENTIAL",
            "Use waves identified in step 1.",
            QUESTION_RELAY_HANDLER,
        ],
    ),
    3: qr_decompose_step(
        title="impl-code-qr-decompose",
        phase="impl-code",
        script="quality_reviewer/impl_code_qr_decompose.py",
        model="fable",
    ),
    4: qr_verify_step(
        title="impl-code-qr-verify",
        phase="impl-code",
    ),
    5: qr_route_step(
        title="impl-code-qr-route",
        phase="impl-code",
        work_step=2,
        pass_step=6,
        pass_message="Code quality verified. Proceed to step 6 (impl-docs-work).",
        fix_target=AgentRole.DEVELOPER,
    ),
    # Impl-docs phase (steps 6-9)
    6: execute_dispatch_step(
        title="impl-docs-work",
        agent="technical-writer",
        script="technical_writer/exec_docs.py",
        phase="impl-docs",
        post_dispatch=[
            QUESTION_RELAY_HANDLER,
        ],
    ),
    7: qr_decompose_step(
        title="impl-docs-qr-decompose",
        phase="impl-docs",
        script="quality_reviewer/impl_docs_qr_decompose.py",
        model="fable",
    ),
    8: qr_verify_step(
        title="impl-docs-qr-verify",
        phase="impl-docs",
    ),
    9: qr_route_step(
        title="impl-docs-qr-route",
        phase="impl-docs",
        work_step=6,
        pass_step=10,
        pass_message="Documentation verified. Proceed to step 10 (wave-next).",
        fix_target=AgentRole.TECHNICAL_WRITER,
    ),
    10: wave_next_step(
        title="wave-next",
    ),
}

validate_step_count(STEPS, EXECUTOR_TOTAL_STEPS, "executor")


def get_step_guidance(step: int, qr_status, state_dir, reconciliation_check=False) -> dict | str:
    """Returns guidance for a step.

    Iteration and fix mode derived from qr-{phase}.json file state.
    Phase derived from handler attribute set by step factory.
    """
    from skills.planner.shared.qr.utils import get_qr_iteration, has_qr_failures

    handler = STEPS.get(step)
    if not handler:
        return {"error": f"Invalid step {step}"}

    # Phase stored as handler attribute by step factory.
    # None for non-QR steps (1, 10).
    phase = getattr(handler, 'phase', None)
    iteration = get_qr_iteration(state_dir, phase) if state_dir and phase else 1

    status = QRStatus(qr_status) if qr_status else None
    is_fix_mode = state_dir and phase and has_qr_failures(state_dir, phase)
    state = LoopState.RETRY if is_fix_mode else LoopState.INITIAL
    qr = QRState(iteration=iteration, state=state, status=status)

    ctx = {
        "step": step,
        "qr": qr,
        "state_dir": state_dir,
        "reconciliation_check": reconciliation_check,
    }

    return handler(ctx)


def format_output(step: int, qr_status, state_dir, reconciliation_check=False) -> str | GateResult:
    """Format output for display."""
    guidance = get_step_guidance(step, qr_status, state_dir=state_dir,
                                 reconciliation_check=reconciliation_check)

    if isinstance(guidance, GateResult):
        return guidance
    if isinstance(guidance, str):
        return guidance
    if "error" in guidance:
        return f"Error: {guidance['error']}"

    body_parts = []
    if step == 1:
        body_parts.append(THINKING_EFFICIENCY)
        body_parts.append("")

    for action in guidance["actions"]:
        body_parts.append(str(action))

    body = "\n".join(body_parts)
    title = guidance["title"]

    if_pass = guidance.get("if_pass")
    if_fail = guidance.get("if_fail")
    next_cmd = guidance.get("next", "")

    if if_pass and if_fail:
        return format_step(body, title=title, if_pass=if_pass, if_fail=if_fail)
    return format_step(body, next_cmd, title=title)


def main():
    """CLI entry point for executor orchestration."""
    parser = argparse.ArgumentParser(
        description="Plan Executor (10-step orchestration workflow)",
        epilog="Step 1: exec-init | Steps 2-9: work + QR phases | Step 10: wave-next",
    )

    parser.add_argument("--step", type=int, required=True)
    parser.add_argument("--state-dir", type=str, default=None,
                        help="State directory path (holds plan.json and qr-{phase}.json)")
    parser.add_argument("--reconciliation-check", action="store_true",
                        help="Include reconciliation dispatch in step 1 output")
    add_qr_args(parser)

    args = parser.parse_args()

    if args.step < 1 or args.step > EXECUTOR_TOTAL_STEPS:
        sys.exit(f"Error: step must be 1-{EXECUTOR_TOTAL_STEPS}")

    # Validate state before running step (skip for step 1 which may create state)
    if args.step > 1 and args.state_dir:
        from skills.planner.shared.schema import validate_state, SchemaValidationError
        try:
            validate_state(args.state_dir)
        except SchemaValidationError as e:
            sys.exit(f"Schema validation failed: {e}")

    # Route steps require --qr-status; provide helpful output if missing
    if args.step in EXECUTOR_GATE_STEPS and not args.qr_status:
        gate_names = {5: "impl-code-qr-route", 9: "impl-docs-qr-route"}
        print(f"EXECUTOR - Step {args.step}/{EXECUTOR_TOTAL_STEPS}: {gate_names[args.step]}")
        print()
        print("This is a route step. Re-invoke with --qr-status pass or --qr-status fail")
        print("based on the aggregated QR output from the previous step.")
        sys.exit(0)

    result = format_output(args.step, args.qr_status, state_dir=args.state_dir,
                           reconciliation_check=args.reconciliation_check)

    if isinstance(result, GateResult):
        print(result.output)
    else:
        print(result)


if __name__ == "__main__":
    main()
