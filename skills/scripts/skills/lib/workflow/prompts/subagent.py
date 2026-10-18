"""Plain-text dispatch prompt building blocks.

Composition via f-strings. No XML, no AST.

Three dispatch patterns:
- subagent_dispatch: Single agent, optional prompt, mandatory invoke command
- template_dispatch: Parallel agents, template with $var substitution per agent
- roster_dispatch: Parallel agents, shared context + unique tasks, fixed command
"""

from pathlib import Path
from string import Template


# ============================================================================
# CONFIGURATION
# ============================================================================

# The valid efforts are defined in lib/workflow/constants.py: this package and the AST dispatch package are
# siblings, and sharing the tuple through the lib layer keeps either from importing the other.
from skills.lib.workflow.constants import EFFORT_LEVELS, validate_effort

# subagent.py -> prompts -> workflow -> lib -> skills -> scripts
SKILLS_DIR = Path(__file__).resolve().parent.parent.parent.parent.parent


# ============================================================================
# SHARED PROMPTS
# ============================================================================
# Building block templates used by multiple dispatch patterns

# The effort line always renders, with 'omit (agent default)' when unset, so an effort passed in an earlier
# dispatch is not carried into this one.
TASK_TOOL_INSTRUCTION = """\
ACTION: Use the Task tool to spawn this agent.

Task tool parameters:
  - subagent_type: {agent_type}
  - model: {model_param}
  - effort: {effort_param}
  - prompt: Include the task and invoke command below
  - run_in_background: NEVER set this. Always omit or set false.
    Background agents return full session transcripts via TaskOutput,
    flooding the orchestrator context window. Foreground agents return
    only the agent's final text response."""

# Fragile bridge: the sub-agent must run this command first because the script output carries its
# instructions. The block states each requirement (working directory, command, copy-unchanged,
# first-action sentence) with its reason in plain wording: a plain statement with a reason is followed
# reliably, while capitalized emphasis makes the model rigid. test_dispatch_prompts.py pins the requirements.
SUB_AGENT_INVOKE = """\
INVOKE BLOCK - copy into the agent's prompt unchanged:
================================================================================
First action: run this command with the Bash tool before anything else. The script output carries your instructions.

Working directory: {working_dir}
Command: {cmd}
================================================================================
Copy the block unchanged, including the first-action sentence: the sub-agent runs the command as its first action because the script carries its instructions."""

# Task calls issued in separate messages run one after another, so the constraint requires one message and
# states the call count. A single batching sentence gives the independence reason.
PARALLEL_CONSTRAINT = """\
PARALLEL EXECUTION:
    Send all {count} Task calls in this one response; none depends on another's result.
    One message containing Task call 1 through Task call {count}, not one call per message."""


# ============================================================================
# MESSAGE TEMPLATES
# ============================================================================

# --- SUBAGENT DISPATCH (Single Agent) ---------------------------------------

SUBAGENT_TEMPLATE = """\
DISPATCH SUB-AGENT
==================

{task_tool_block}

TASK FOR THE SUB-AGENT:
{task_section}

{invoke_block}

After the sub-agent returns, continue with the next workflow step."""

# --- TEMPLATE DISPATCH (Parallel, Variable Substitution) --------------------

# The prompt rules require the invoke block to be copied whole: the sub-agent keys on the first-action
# sentence to run the command, and the Working directory / Command pair alone does not carry that signal.
TEMPLATE_DISPATCH_TEMPLATE = """\
DISPATCH {count} PARALLEL AGENTS
================================

{parallel_block}

For EACH agent below, use Task tool with:
  - subagent_type: {agent_type}
  - model: {model_display}
  - effort: {effort_display}
  - prompt: Task description + the INVOKE BLOCK, copied unchanged

PROMPT CONSTRUCTION RULES:
  - The INVOKE BLOCK appears unchanged in each prompt, including its first-action sentence
  - It is not reduced to Working directory / Command lines: the sub-agent keys on the first-action sentence to run the command

{instruction_section}AGENTS:
{agents_section}

After ALL {count} agents return, continue with the next workflow step."""

TEMPLATE_AGENT_ENTRY = """\
--- Agent {index} ---
Task: {prompt}

{invoke_block}"""

# --- ROSTER DISPATCH (Parallel, Unique Tasks) -------------------------------

# Same invoke-block rule as the template dispatch; the shared context is repeated in every agent's prompt
# because the agents do not see each other's prompts.
ROSTER_DISPATCH_TEMPLATE = """\
DISPATCH {count} PARALLEL AGENTS
================================

{parallel_block}

For EACH agent below, use Task tool with:
  - subagent_type: {agent_type}
  - model: {model_display}
  - effort: {effort_display}
  - prompt: Shared context + agent's unique task + the INVOKE BLOCK, copied unchanged

PROMPT CONSTRUCTION RULES:
  - The INVOKE BLOCK appears unchanged in each prompt, including its first-action sentence
  - It is not reduced to Working directory / Command lines: the sub-agent keys on the first-action sentence to run the command

{instruction_section}{shared_context_section}AGENTS:
{agents_section}

After ALL {count} agents return, continue with the next workflow step."""

ROSTER_AGENT_ENTRY = """\
--- Agent {index} ---
Unique Task: {task}

{invoke_block}"""


# ============================================================================
# MESSAGE BUILDERS
# ============================================================================

# --- Building block functions -----------------------------------------------

def _effort_display(effort: str | None) -> str:
    """Validate effort and return its Task tool display value.

    None renders as an explicit omit line rather than as nothing: silence lets the orchestrator reuse an
    effort from an earlier dispatch. The valid set is closed because the Task tool accepts exactly
    EFFORT_LEVELS.

    Raises:
        ValueError: If effort is set and not in EFFORT_LEVELS
    """
    validate_effort(effort)
    if effort is None:
        return "omit (agent default)"
    return effort


def task_tool_instruction(
    agent_type: str,
    model: str | None,
    effort: str | None = None,
) -> str:
    """Tell main agent how to spawn sub-agent via Task tool.

    effort None renders "omit (agent default)"; any other value must be in EFFORT_LEVELS.

    Raises:
        ValueError: If effort is set and not in EFFORT_LEVELS
    """
    model_param = model if model else "omit (use default)"
    return TASK_TOOL_INSTRUCTION.format(
        agent_type=agent_type,
        model_param=model_param,
        effort_param=_effort_display(effort),
    )


def sub_agent_invoke(cmd: str) -> str:
    """Tell sub-agent what command to run after spawning."""
    return SUB_AGENT_INVOKE.format(working_dir=SKILLS_DIR, cmd=cmd)


def parallel_constraint(count: int) -> str:
    """One-message dispatch rule for multiple agents.

    The Task calls are independent, so issuing them together lets them run concurrently.
    """
    return PARALLEL_CONSTRAINT.format(count=count)


# --- Dispatch pattern functions ---------------------------------------------

def subagent_dispatch(
    agent_type: str,
    command: str,
    prompt: str = "",
    model: str | None = None,
    effort: str | None = None,
) -> str:
    """Generate prompt for single sub-agent dispatch.

    Args:
        agent_type: Task tool subagent_type (e.g., "general-purpose", "Explore")
        command: Shell command sub-agent must run after spawning
        prompt: Optional task description for sub-agent
        model: Optional model override ("haiku", "sonnet", "opus", "fable")
        effort: Optional effort override ("low", "medium", "high", "xhigh", "max")
            None omits the parameter (agent default).

    Returns:
        Complete dispatch prompt as plain text

    Raises:
        ValueError: If effort is set and not in EFFORT_LEVELS
    """
    task_section = prompt if prompt else "(No additional task - agent follows invoke command)"

    return SUBAGENT_TEMPLATE.format(
        task_tool_block=task_tool_instruction(agent_type, model, effort),
        task_section=task_section,
        invoke_block=sub_agent_invoke(command),
    )


def template_dispatch(
    agent_type: str,
    template: str,
    targets: list[dict[str, str]],
    command: str,
    model: str | None = None,
    instruction: str | None = None,
    effort: str | None = None,
) -> str:
    """Generate prompt for parallel dispatch with variable substitution.

    Template and command use $var syntax. Variables are substituted per-target
    before the LLM sees the prompt (expansion happens here, not at runtime).

    Args:
        agent_type: Task tool subagent_type for all agents
        template: Prompt template with $var placeholders
        targets: List of dicts, each providing variable bindings for one agent
        command: Command template with $var placeholders
        model: Optional model override for all agents
        instruction: Optional instruction text
        effort: Optional effort override for all agents ("low", "medium",
            "high", "xhigh", "max")
            None omits the parameter (agent default).

    Returns:
        Complete dispatch prompt with expanded agent entries

    Raises:
        KeyError: If template contains $var not present in target dict
        ValueError: If effort is not one of EFFORT_LEVELS
    """
    expanded = []
    for t in targets:
        expanded.append({
            "prompt": Template(template).substitute(t),
            "command": Template(command).substitute(t),
        })

    count = len(expanded)
    model_display = model if model else "default (omit parameter)"
    effort_display = _effort_display(effort)
    instruction_section = f"NOTE: {instruction}\n\n" if instruction else ""

    agents_lines = []
    for i, e in enumerate(expanded, 1):
        agents_lines.append(TEMPLATE_AGENT_ENTRY.format(
            index=i,
            prompt=e["prompt"],
            invoke_block=sub_agent_invoke(e["command"]),
        ))

    return TEMPLATE_DISPATCH_TEMPLATE.format(
        count=count,
        agent_type=agent_type,
        model_display=model_display,
        effort_display=effort_display,
        parallel_block=parallel_constraint(count),
        instruction_section=instruction_section,
        agents_section="\n\n".join(agents_lines),
    )


def roster_dispatch(
    agent_type: str,
    agents: list[str],
    command: str,
    shared_context: str = "",
    model: str | None = None,
    instruction: str | None = None,
    effort: str | None = None,
) -> str:
    """Generate prompt for parallel dispatch with unique tasks per agent.

    Each agent receives shared_context + their unique task + the fixed command.
    Use when agents have fundamentally different roles (MIMD pattern).

    Args:
        agent_type: Task tool subagent_type for all agents
        agents: List of unique task descriptions, one per agent
        command: Fixed command all agents run (same for all)
        shared_context: Optional context included in every agent's prompt
        model: Optional model override for all agents
        instruction: Optional instruction text
        effort: Optional effort override for all agents ("low", "medium",
            "high", "xhigh", "max")
            None omits the parameter (agent default).

    Returns:
        Complete dispatch prompt with agent entries

    Raises:
        ValueError: If effort is not one of EFFORT_LEVELS
    """
    count = len(agents)
    model_display = model if model else "default (omit parameter)"
    effort_display = _effort_display(effort)
    instruction_section = f"NOTE: {instruction}\n\n" if instruction else ""
    shared_context_section = f"SHARED CONTEXT (include in every agent's prompt):\n{shared_context}\n\n" if shared_context else ""

    agents_lines = []
    for i, task in enumerate(agents, 1):
        agents_lines.append(ROSTER_AGENT_ENTRY.format(
            index=i,
            task=task,
            invoke_block=sub_agent_invoke(command),
        ))

    return ROSTER_DISPATCH_TEMPLATE.format(
        count=count,
        agent_type=agent_type,
        model_display=model_display,
        effort_display=effort_display,
        parallel_block=parallel_constraint(count),
        instruction_section=instruction_section,
        shared_context_section=shared_context_section,
        agents_section="\n\n".join(agents_lines),
    )


__all__ = [
    # Configuration
    # EFFORT_LEVELS is exported so scripts validate against the vocabulary the builders enforce.
    "EFFORT_LEVELS",
    # Building blocks
    "task_tool_instruction",
    "sub_agent_invoke",
    "parallel_constraint",
    # Dispatch templates
    "subagent_dispatch",
    "template_dispatch",
    "roster_dispatch",
]
