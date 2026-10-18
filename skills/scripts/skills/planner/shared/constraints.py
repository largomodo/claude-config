"""Reusable constraint strings for planner orchestration.

Constants for static constraints, functions for parameterized output.
"""


# Orchestrator-scoped autonomy. The sub-agent wording says the user cannot answer mid-task: true for a
# sub-agent, whose only channel is the <needs_user_input> relay, and false for the main session, which
# owns AskUserQuestion and relays every <needs_user_input> a sub-agent returns. Saying the user cannot
# answer would make the orchestrator swallow relayed questions. This text gives the reason for not
# asking (the workflow is deterministic) and names the one channel that remains.
# Every line of the constant is plain register: a constant that is half emphatic and half plain sends
# mixed signal.
ORCHESTRATOR_CONSTRAINT = (
    "You are the ORCHESTRATOR: you delegate and never implement, so Read, Edit "
    "and Write are not used in this role; work reaches the codebase through "
    "Task tool dispatch.\n"
    "You are operating autonomously: the workflow is deterministic, so do not "
    "ask whether to proceed with the next step. For reversible actions that "
    "follow from the original request, proceed without asking.\n"
    "The user is reachable only through AskUserQuestion: use it when a "
    "sub-agent returns <needs_user_input> (relay the question, then reinvoke "
    "it fresh) or when a step tells you to gather missing context, and only "
    "for a decision the user must make.\n"
    "Your agents handle any issue a step raises; hand the issue to them "
    "instead of working around them."
)

# SCRIPT-MODE DISPATCH gives its reason: the script supplies the sub-agent's instructions, so extra task
# text in the prompt competes with them.
ORCHESTRATOR_CONSTRAINT_EXTENDED = (
    ORCHESTRATOR_CONSTRAINT + "\n"
    "\n"
    "SCRIPT-MODE DISPATCH: the Task prompt carries the invoke command and the "
    "context variable values, nothing else; the script gives the sub-agent its "
    "instructions, so added descriptions or goals compete with them."
)


def format_state_banner(checkpoint: str, iteration: int, mode: str) -> str:
    """QR state context banner.

    WHY needed: Fix/review steps need workflow position context. LLM sees
    which phase, iteration count (for convergence tracking), and mode.
    """
    return f"STATE: {checkpoint} | iteration={iteration} | mode={mode}"
