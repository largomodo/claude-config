"""Tests for the plain-text dispatch prompts in skills.lib.workflow.prompts.subagent.

Covers the invoke block fields and sentences, the one-message parallel rule,
effort rendering across the three dispatch functions, and the absence of the
emphatic register tokens. The tests import the package
surface leaf scripts use, so the EFFORT_LEVELS re-export is checked too.
"""

import pytest

from skills.lib.workflow import constants
from skills.lib.workflow.prompts import (
    EFFORT_LEVELS,
    parallel_constraint,
    roster_dispatch,
    sub_agent_invoke,
    subagent_dispatch,
    task_tool_instruction,
    template_dispatch,
)

CMD = "python3 -m skills.x.y --step 1"
# Emphatic tokens that signal pressure. Their absence from rendered blocks keeps the plain register in
# place; the requirements the plain wording carries are pinned by the tests below.
REGISTER_TOKENS = ("MANDATORY", "VERBATIM", "CRITICAL", "IMMEDIATELY", "FORBIDDEN", "MUST")
OMIT = "omit (agent default)"


def _all_dispatches(effort):
    """Render the three dispatch functions with the same effort.

    Every dispatch variant must treat effort identically, so tests iterate this list
    instead of naming one function.
    """
    return [
        subagent_dispatch("general-purpose", CMD, effort=effort),
        template_dispatch(
            "general-purpose", "Explore $n", [{"n": "a"}, {"n": "b"}],
            "python3 -m skills.x.y --n $n", effort=effort,
        ),
        roster_dispatch("general-purpose", ["one", "two"], CMD, effort=effort),
    ]


def test_effort_levels_come_from_constants():
    """The package re-exports the constants tuple itself, so both dispatch layers share one
    vocabulary; the literal pins the five values the Task tool accepts.
    """
    assert EFFORT_LEVELS is constants.EFFORT_LEVELS
    assert EFFORT_LEVELS == ("low", "medium", "high", "xhigh", "max")


def test_invoke_block_fields_and_sentences():
    """The invoke block keeps what makes the sub-agent run the command first: working
    directory, command, the first-action sentence and the copy-unchanged sentence. Each must be present.
    """
    out = sub_agent_invoke(CMD)
    assert "Working directory:" in out
    assert f"Command: {CMD}" in out
    assert "First action: run this command with the Bash tool before anything else." in out
    assert "including the first-action sentence" in out


def test_parallel_constraint_names_count_in_one_message():
    """The parallel rule keeps the dispatch count and the one-message requirement; Task calls
    issued in separate messages run sequentially.
    """
    out = parallel_constraint(3)
    assert "Send all 3 Task calls in this one response" in out
    assert "One message containing Task call 1 through Task call 3" in out


@pytest.mark.parametrize("effort", EFFORT_LEVELS)
def test_effort_value_rendered_by_every_dispatch(effort):
    """Every valid level renders as an explicit effort line in every dispatch variant.
    """
    assert f"effort: {effort}" in task_tool_instruction("general-purpose", None, effort)
    for out in _all_dispatches(effort):
        assert f"effort: {effort}" in out


def test_unset_effort_renders_omit_by_every_dispatch():
    """An unset effort renders an explicit omit line in every variant, so an effort set in an
    earlier step does not carry forward.
    """
    assert f"effort: {OMIT}" in task_tool_instruction("general-purpose", None)
    for out in _all_dispatches(None):
        assert f"effort: {OMIT}" in out


def test_invalid_effort_raises_naming_the_levels():
    """Each builder rejects an effort outside EFFORT_LEVELS and names the valid set, so a typo
    fails where the dispatch is built.
    """
    expected = "effort must be one of low, medium, high, xhigh, max"
    with pytest.raises(ValueError, match=expected):
        task_tool_instruction("general-purpose", None, "turbo")
    with pytest.raises(ValueError, match=expected):
        subagent_dispatch("general-purpose", CMD, effort="turbo")
    with pytest.raises(ValueError, match=expected):
        template_dispatch("general-purpose", "t $n", [{"n": "a"}], "c $n", effort="turbo")
    with pytest.raises(ValueError, match=expected):
        roster_dispatch("general-purpose", ["one"], CMD, effort="turbo")


def test_run_in_background_rule_is_emphatic():
    """Guards the one emphatic rule: a background agent returns its full session
    transcript through TaskOutput, so the rule is a harness constraint with a stated reason,
    not register.
    """
    assert "run_in_background: NEVER set this." in task_tool_instruction("general-purpose", None)


def test_register_tokens_absent_from_prompt_blocks():
    """Rendered invoke, parallel and preamble text contain no emphatic tokens; the requirements
    are pinned by the tests above, so the register is plain without losing them.
    """
    blocks = [sub_agent_invoke(CMD), parallel_constraint(2)]
    for out in _all_dispatches(None):
        blocks.append(out.split("AGENTS:")[0] if "AGENTS:" in out else out)
    for block in blocks:
        for token in REGISTER_TOKENS:
            assert token not in block, f"{token!r} found in prompt block"
