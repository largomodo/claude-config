"""Orchestrator step factories shared by planner.py and executor.py.

Both orchestrators run the same QR block pattern per phase:
  N   work        1 agent (router script)        Modified artifacts
  N+1 decompose   1 agent (QR)                   qr-{phase}.json
  N+2 verify      N agents (parallel, expanded)  Each: PASS or FAIL
  N+3 route       0 agents (orchestrator)        Loop to N or proceed

Single implementation keeps the two orchestrators' emitted prompts and
routing in lockstep. The executor previously kept its own copies and
drifted to reference modules that no longer exist; sharing the factories
makes that drift structurally impossible.

Each factory takes module_path (the calling orchestrator's -m path) so
emitted invoke_after commands route back to the correct orchestrator.
Handlers receive ctx: {"step": int, "qr": QRState, "state_dir": str}.
"""

from skills.lib.workflow.prompts import subagent_dispatch, template_dispatch
from skills.planner.shared.gates import build_gate_output, GateResult
from skills.planner.shared.qr.utils import qr_file_exists, increment_qr_iteration
from skills.planner.shared.resources import get_mode_script_path
from skills.planner.shared.builders import format_forbidden
from skills.planner.shared.constraints import (
    ORCHESTRATOR_CONSTRAINT_EXTENDED,
    format_state_banner,
)
from skills.planner.shared.qr.types import LoopState


def build_fix_mode_output(module_path, title, agent, script, qr, ctx,
                          fix_banner="PLAN-FIX"):
    """Build output for a work step in fix mode (QR failures present).

    Dispatches the same router script as first-time execution; the router
    inspects qr-{phase}.json and routes to its qr_fix workflow internally.
    """
    state_dir = ctx["state_dir"]

    action_children = []

    action_children.append(format_state_banner(fix_banner, qr.iteration, "fix"))
    action_children.append("")
    action_children.append("FIX MODE: QR found issues.")
    action_children.append("")

    action_children.append(ORCHESTRATOR_CONSTRAINT_EXTENDED)
    action_children.append("")

    mode_script = get_mode_script_path(script)
    invoke_cmd = f"python3 -m {mode_script} --step 1 --state-dir {state_dir}"

    dispatch_prompt = subagent_dispatch(
        agent_type=agent,
        command=invoke_cmd,
    )
    action_children.append(dispatch_prompt)
    action_children.append("")
    action_children.append(f"{agent.title()} reads QR report and fixes issues.")
    action_children.append("After fixes complete, re-run QR for fresh verification.")

    next_step = ctx["step"] + 1
    next_cmd = f"python3 -m {module_path} --step {next_step} --state-dir {state_dir}"

    return {
        "title": f"{title} - Fix Mode",
        "actions": action_children,
        "next": next_cmd,
    }


def execute_dispatch_step(module_path, title, agent, script, phase=None,
                          post_dispatch=None, fix_banner="PLAN-FIX"):
    """Work execution dispatch step (planner 3/7/11, executor 2/6).

    First run dispatches the router script in execute mode; when
    qr-{phase}.json holds blocking failures the same step re-enters in
    fix mode (detected via file state, not CLI flags).
    """
    def handler(ctx):
        from skills.planner.shared.resources import validate_state_dir_requirement

        state_dir = ctx["state_dir"]
        qr = ctx["qr"]
        step = ctx["step"]

        validate_state_dir_requirement(step, state_dir)

        if qr.state == LoopState.RETRY:
            return build_fix_mode_output(module_path, title, agent, script,
                                         qr, ctx, fix_banner=fix_banner)

        action_children = []

        action_children.append(ORCHESTRATOR_CONSTRAINT_EXTENDED)
        action_children.append("")

        mode_script = get_mode_script_path(script)
        invoke_cmd = f"python3 -m {mode_script} --step 1 --state-dir {state_dir}"

        dispatch_prompt = subagent_dispatch(
            agent_type=agent,
            command=invoke_cmd,
        )
        action_children.append(dispatch_prompt)
        action_children.append("")

        if post_dispatch:
            action_children.extend(post_dispatch)

        next_step = step + 1
        next_cmd = f"python3 -m {module_path} --step {next_step} --state-dir {state_dir}"

        return {
            "title": title,
            "actions": action_children,
            "next": next_cmd,
        }

    handler.phase = phase
    return handler


def qr_decompose_step(module_path, title, phase, script, model=None):
    """QR decomposition dispatch (planner 4/8/12, executor 3/7).

    Dispatches single QR agent to decompose artifact into verification items.
    Agent outputs qr-{phase}.json.

    Decompose runs exactly once per phase. If qr-{phase}.json already exists,
    decomposition is skipped and flow proceeds directly to verify step.
    """
    def handler(ctx):
        state_dir = ctx["state_dir"]
        qr = ctx["qr"]
        step = ctx["step"]

        if qr_file_exists(state_dir, phase):
            verify_step = step + 1
            return {
                "title": f"{title} - Skipped (items already defined)",
                "actions": [
                    f"QR items for {phase} already defined.",
                    "Proceeding to verification of existing items.",
                ],
                "next": f"python3 -m {module_path} --step {verify_step} --state-dir {state_dir}",
            }

        action_children = []

        qr_name = f"QR-{phase.upper()}-DECOMPOSE"
        action_children.append(format_state_banner(qr_name, qr.iteration, "decompose"))
        action_children.append("")

        action_children.append(ORCHESTRATOR_CONSTRAINT_EXTENDED)
        action_children.append("")

        mode_script = get_mode_script_path(script)
        invoke_cmd = f"python3 -m {mode_script} --step 1 --state-dir {state_dir}"

        dispatch_prompt = subagent_dispatch(
            agent_type="quality-reviewer",
            command=invoke_cmd,
            model=model,
        )
        action_children.append(dispatch_prompt)
        action_children.append("")

        action_children.append("Expected output: qr-{phase}.json written to STATE_DIR")
        action_children.append("Orchestrator generates verification dispatch from this file.")

        next_step = step + 1
        next_cmd = f"python3 -m {module_path} --step {next_step} --state-dir {state_dir}"

        return {
            "title": title,
            "actions": action_children,
            "next": next_cmd,
        }

    handler.phase = phase
    return handler


def _format_qr_item_flags(item_ids: list[str]) -> str:
    """Format item IDs as repeated --qr-item flags."""
    return " ".join(f"--qr-item {id}" for id in item_ids)


def qr_verify_step(module_path, title, phase):
    """Parallel QR verification with group-aware dispatch (planner 5/9/13, executor 4/8).

    Reads qr-{phase}.json and generates expanded dispatch.
    Decompose agent outputs item data. Orchestrator transforms this data
    into template_dispatch format. LLM sees ready-to-execute agent
    blocks, not substitution instructions.

    Uses repeated --qr-item flags (argparse action="append") instead of
    comma-separated --qr-items to avoid parsing ambiguity.
    """
    def handler(ctx):
        from skills.planner.shared.qr.utils import load_qr_state, query_items, by_status, by_blocking_severity
        from skills.planner.shared.qr.phases import get_phase_config

        state_dir = ctx["state_dir"]
        step = ctx["step"]
        qr = ctx["qr"]

        qr_state = load_qr_state(state_dir, phase)
        if not qr_state or "items" not in qr_state:
            return {"error": f"qr-{phase}.json not found or malformed in {state_dir}"}

        if qr.state == LoopState.RETRY:
            increment_qr_iteration(state_dir, phase)

        # Dispatch only items at blocking severity for current iteration.
        iteration = qr_state.get("iteration", 1)
        items = query_items(qr_state, by_status("TODO", "FAIL"), by_blocking_severity(iteration))
        if not items:
            next_step = step + 1
            return {
                "title": title,
                "actions": ["All items already verified. Proceeding with pass."],
                "if_pass": f"python3 -m {module_path} --step {next_step} --state-dir {state_dir} --qr-status pass",
                "if_fail": f"python3 -m {module_path} --step {next_step} --state-dir {state_dir} --qr-status pass",
            }

        config = get_phase_config(phase)
        verify_script = config["verify_script"]

        # Group items by group_id for batch verification.
        groups = {}
        for item in items:
            gid = item.get("group_id") or item["id"]
            groups.setdefault(gid, []).append(item)

        targets = [
            {
                "group_id": gid,
                "item_ids": ",".join(i["id"] for i in group_items),
                "qr_item_flags": _format_qr_item_flags([i["id"] for i in group_items]),
                "item_count": str(len(group_items)),
                "checks_summary": "; ".join(i.get("check", "")[:40] for i in group_items[:3]),
            }
            for gid, group_items in groups.items()
        ]

        tmpl = f"""Verify QR group: $group_id ($item_count items)
Items: $item_ids
Checks: $checks_summary

Start: python3 -m {verify_script} --step 1 --state-dir {state_dir} $qr_item_flags"""

        command = f"python3 -m {verify_script} --step 1 --state-dir {state_dir} $qr_item_flags"

        dispatch_text = template_dispatch(
            agent_type="quality-reviewer",
            template=tmpl,
            targets=targets,
            command=command,
            instruction=f"Verify {len(groups)} groups ({len(items)} items) in parallel.",
        )

        action_children = [
            ORCHESTRATOR_CONSTRAINT_EXTENDED,
            "",
            f"=== PHASE 1: DISPATCH (delegate to sub-agents) ===",
            "",
            f"VERIFY: {len(items)} items",
            "",
            dispatch_text,
            "",
            f"=== PHASE 2: AGGREGATE (your action after all agents return) ===",
            "",
            f"After ALL {len(groups)} agents return, tally results mechanically:",
            f"  ALL agents returned PASS  ->  invoke next step with --qr-status pass",
            f"  ANY agent returned FAIL   ->  invoke next step with --qr-status fail",
            "",
            format_forbidden(
                "Interpreting results beyond PASS/FAIL tallying",
                "Claiming 'diminishing returns' or 'comprehensive enough'",
                "Reading plan.json or any state files",
                "Writing, rendering, or summarizing the plan",
                "Skipping the next step command",
                "Proceeding to a later step without QR PASS",
            ),
        ]

        next_step = step + 1
        base_cmd = f"python3 -m {module_path} --step {next_step} --state-dir {state_dir}"

        return {
            "title": title,
            "actions": action_children,
            "if_pass": f"{base_cmd} --qr-status pass",
            "if_fail": f"{base_cmd} --qr-status fail",
        }

    handler.phase = phase
    return handler


def qr_route_step(module_path, script_name, title, phase, work_step, pass_step,
                  pass_message, fix_target=None):
    """Route based on aggregated QR results (planner 6/10/14, executor 5/9).

    PASS: proceed to pass_step
    FAIL: loop to work_step (fix mode detected via qr-{phase}.json inspection)
    """
    def handler(ctx):
        qr = ctx["qr"]
        state_dir = ctx.get("state_dir", "")
        step = ctx["step"]

        return build_gate_output(
            module_path=module_path,
            script_name=script_name,
            qr_name=title,
            qr=qr,
            step=step,
            work_step=work_step,
            pass_step=pass_step,
            pass_message=pass_message,
            fix_target=fix_target,
            state_dir=state_dir,
        )

    handler.phase = phase
    return handler
