"""CLI utilities for workflow scripts.

Handles argument parsing and mode script entry points. mode_main() also
injects the Serena tool-navigation preamble on step 1, choosing between a
read-only and an edit-capable variant based on the calling script's module
path; router scripts that hand off to another script's step 1 are skipped
so the preamble is not printed twice in the same sub-agent turn.

Orchestrator scripts (planner.py, executor.py) never call mode_main() and
never receive this preamble; they carry ORCHESTRATOR_CONSTRAINT
(skills.planner.shared.constraints) instead, unchanged by this policy.
"""

import argparse
from pathlib import Path
from typing import Callable

from .prompts.step import format_step
from .prompts.serena import SERENA_EDIT_PREAMBLE, SERENA_READ_PREAMBLE
from .types import UserInputResponse


# Injected on step 1 only. Replaces the deleted xml_format_mandate.
THINKING_EFFICIENCY = (
    "THINKING EFFICIENCY:\n"
    "  Max 5 words per step. Symbolic notation preferred.\n"
    '  Good: "Patterns needed -> grep auth -> found 3"\n'
    '  Bad: "For the patterns we need, let me search for auth..."'
)


def _compute_module_path(script_file: str) -> str:
    """Compute module path from script file path.

    Args:
        script_file: Absolute path to script (e.g., ~/.claude/skills/scripts/skills/planner/qr/plan_completeness.py)

    Returns:
        Module path for -m invocation (e.g., skills.planner.qr.plan_completeness)
    """
    path = Path(script_file).resolve()
    parts = path.parts
    # Find 'scripts' in path and extract module path after it
    if "scripts" in parts:
        scripts_idx = parts.index("scripts")
        if scripts_idx + 1 < len(parts):
            module_parts = list(parts[scripts_idx + 1:])
            module_parts[-1] = module_parts[-1].removesuffix(".py")
            return ".".join(module_parts)
    # Fallback: just use filename
    return path.stem


def _serena_preamble_for(module_path: str) -> str:
    """Select the Serena preamble variant for a mode script's module path.

    The edit variant applies only when the module is an exec_* script of
    the developer or technical_writer role package -- those are the only
    scripts that modify source files. Every other script, including the
    planning-only plan_code_* and plan_docs_* scripts of the same two
    roles, gets the read variant.
    """
    parts = module_path.split(".")
    role = parts[-2] if len(parts) >= 2 else ""
    leaf = parts[-1] if parts else ""
    if role in ("developer", "technical_writer") and leaf.startswith("exec_"):
        return SERENA_EDIT_PREAMBLE
    return SERENA_READ_PREAMBLE


def add_standard_args(parser: argparse.ArgumentParser) -> None:
    """Add standard workflow arguments."""
    parser.add_argument("--step", type=int, required=True)
    parser.add_argument("--qr-iteration", type=int, default=1)
    parser.add_argument("--qr-fail", type=str, default=None)
    parser.add_argument(
        "--user-answer-id",
        type=str,
        help="Question ID that was answered"
    )
    parser.add_argument(
        "--user-answer-value",
        type=str,
        help="User's selected option or custom text"
    )


def get_user_answer(args) -> UserInputResponse | None:
    """Extract user answer from parsed args."""
    if args.user_answer_id and args.user_answer_value:
        return UserInputResponse(
            question_id=args.user_answer_id,
            selected=args.user_answer_value,
        )
    return None


def mode_main(
    script_file: str,
    get_step_guidance: Callable[..., dict],
    description: str,
    extra_args: list[tuple[list, dict]] = None,
):
    """Standard entry point for mode scripts.

    Args:
        script_file: Pass __file__ from the calling script
        get_step_guidance: Function that returns guidance dict for each step
        description: Script description for --help
        extra_args: Additional arguments beyond standard QR args
    """
    module_path = _compute_module_path(script_file)

    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("--step", type=int, required=True)
    parser.add_argument("--qr-iteration", type=int, default=1)
    parser.add_argument("--qr-fail", type=str, default=None)
    for args, kwargs in (extra_args or []):
        parser.add_argument(*args, **kwargs)
    parsed = parser.parse_args()

    guidance = get_step_guidance(
        parsed.step, module_path,
        **{k: v for k, v in vars(parsed).items()
           if k not in ('step',)}
    )

    # Handle both dict and dataclass (GuidanceResult) returns
    if hasattr(guidance, '__dataclass_fields__'):
        guidance_dict = {
            "title": guidance.title,
            "actions": guidance.actions,
            "next": guidance.next_command,
        }
    else:
        guidance_dict = guidance

    # Build body from actions list
    body_parts = []
    if parsed.step == 1:
        body_parts.append(THINKING_EFFICIENCY)
        body_parts.append("")

        # Router hand-offs (guidance carries dispatch_to) skip injection
        # here: the execute script's step 1 injects in the same sub-agent
        # turn, so injecting on both would print the preamble twice.
        if "dispatch_to" not in guidance_dict:
            body_parts.append(_serena_preamble_for(module_path))
            body_parts.append("")

    for action in guidance_dict["actions"]:
        body_parts.append(str(action))

    body = "\n".join(body_parts)
    next_cmd = guidance_dict.get("next", "")

    print(format_step(body, next_cmd, title=guidance_dict["title"]))
