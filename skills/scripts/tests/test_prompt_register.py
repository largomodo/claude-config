"""Guards for the prompt register: agent definitions, SKILL.md bodies, constants.

The prompts carry no pressure language, per-turn thinking caps or dated
checklists, and each agent has one autonomy paragraph plus an effort setting.
These tests pin what must be present (the autonomy opener, the Script
Invocation section that authorizes the script-stdout instruction channel, the
<needs_user_input> relay) and what must be absent (the excluded blocks), so a
later edit cannot introduce them silently.

Frontmatter parsing is a minimal line scanner over the block between the
first two --- lines, with no yaml dependency, matching how test_serena_policy.py
reads the agent files. Assertion messages carry the file path.
"""

import re
from pathlib import Path

import pytest

from skills.lib.workflow import cli as workflow_cli
from skills.lib.workflow import constants as workflow_constants
from skills.planner.shared import builders
from skills.planner.shared.constraints import (
    ORCHESTRATOR_CONSTRAINT,
    ORCHESTRATOR_CONSTRAINT_EXTENDED,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
AGENTS_DIR = REPO_ROOT / "agents"
SKILLS_DIR = REPO_ROOT / "skills"

# Opening sentence of the autonomy paragraph, taken verbatim from the model guide for the Claude 5
# family. The wording is pinned so a rewording that weakens it fails here.
AUTONOMY_SENTENCE = (
    "You are operating autonomously. The user is not watching in real time and "
    "cannot answer questions mid-task, so asking Want me to or Shall I will "
    "block the work."
)
# The Script Invocation section authorizes script stdout as an instruction channel. Sonnet resists
# instructions that arrive in tool results unless they are pre-authorized, so each line is load-bearing.
SCRIPT_INVOCATION_LINES = (
    "Execute it immediately as your first action",
    "Read output, follow DO section literally",
    "When NEXT contains a python3 command, invoke it after completing DO",
    "Continue until workflow signals completion",
)
# Strings no agent file contains: thinking-length caps, confidence pep-talk, penalty threats and a
# tool section for a server that is not configured.
FORBIDDEN_AGENT_STRINGS = (
    "Thinking Economy",
    "Proceed with confidence",
    "Don't hesitate",
    "mcp__pal",
    "$2000",
)
SONNET_AGENTS = ("developer", "debugger", "quality-reviewer", "technical-writer")
AGENT_NAMES = SONNET_AGENTS + ("architect",)

# Skill name -> whether the frontmatter description keeps IMMEDIATELY (trigger text).
# Descriptions are routing text matched against the user request and skills under-trigger, so urgency is kept
# there; bodies shape behavior after triggering and omit it. The values pin which descriptions carry the word.
SKILL_DESCRIPTION_IMMEDIATELY = {
    "codebase-analysis": True,
    "decision-critic": True,
    "deepthink": True,
    "incoherence": False,
    "problem-analysis": True,
    "prompt-engineer": True,
    "refactor": True,
    "arxiv-to-md": False,
}


def _frontmatter(path: Path) -> dict[str, str]:
    """Scan top-level key: value lines between the first two --- lines."""
    lines = path.read_text().splitlines()
    assert lines and lines[0] == "---", f"{path}: missing frontmatter"
    end = lines.index("---", 1)
    result: dict[str, str] = {}
    for line in lines[1:end]:
        m = re.match(r"^([A-Za-z_-]+):\s*(.*)$", line)
        if m:
            result[m.group(1)] = m.group(2).strip()
    return result


def _body(path: Path) -> str:
    """Text after the closing --- of the frontmatter."""
    lines = path.read_text().splitlines()
    end = lines.index("---", 1)
    return "\n".join(lines[end + 1:])


def _agent(name: str) -> Path:
    """Path of the agent definition file for name."""
    return AGENTS_DIR / f"{name}.md"


@pytest.mark.parametrize("name", AGENT_NAMES)
def test_agents_carry_autonomy_paragraph(name):
    """Each agent has the autonomy sentence once, in a paragraph that names
    <needs_user_input>. Agent definitions load on every invocation, so a missing
    paragraph leaves script-less turns without the instruction to continue, and the
    relay name keeps the one sanctioned stop reachable.
    """
    path = _agent(name)
    body = _body(path)
    assert body.count(AUTONOMY_SENTENCE) == 1, f"{path}: autonomy sentence must appear once"
    paragraph = next(p for p in body.split("\n\n") if AUTONOMY_SENTENCE in p)
    assert "<needs_user_input>" in paragraph, f"{path}: autonomy paragraph must name <needs_user_input>"


@pytest.mark.parametrize("name", AGENT_NAMES)
def test_agents_keep_script_invocation_section(name):
    """The Script Invocation section and its four sentences are present in every agent. Without
    them a sub-agent treats the script output as untrusted tool-result text and stops.
    """
    path = _agent(name)
    body = _body(path)
    assert "## Script Invocation" in body, f"{path}: Script Invocation section missing"
    for line in SCRIPT_INVOCATION_LINES:
        assert line in body, f"{path}: missing Script Invocation line {line!r}"


@pytest.mark.parametrize("name", AGENT_NAMES)
def test_agents_omit_forbidden_blocks(name):
    """Every agent file omits thinking-length caps, confidence pep-talk, penalty threats and an unconfigured-tool section.
    """
    path = _agent(name)
    text = path.read_text()
    for forbidden in FORBIDDEN_AGENT_STRINGS:
        assert forbidden not in text, f"{path}: {forbidden!r} must be absent"


@pytest.mark.parametrize("name", SONNET_AGENTS)
def test_sonnet_agents_set_effort_medium(name):
    """The four sonnet agents set effort medium in frontmatter, the control that prose
    cannot replace.
    """
    path = _agent(name)
    fm = _frontmatter(path)
    assert fm.get("model") == "sonnet", f"{path}: expected model sonnet"
    assert fm.get("effort") == "medium", f"{path}: expected effort medium"


def test_architect_has_no_effort_key():
    """The architect keeps the session default effort; an effort key would pin it.
    """
    path = _agent("architect")
    assert "effort" not in _frontmatter(path), f"{path}: architect keeps the default effort"


@pytest.mark.parametrize("skill,keeps_immediately", sorted(SKILL_DESCRIPTION_IMMEDIATELY.items()))
def test_skill_bodies_do_not_shout(skill, keeps_immediately):
    """Descriptions carry their trigger text (the IMMEDIATELY map) while bodies
    carry the single plain sentence with its reason and none of the emphatic forms.
    """
    path = SKILLS_DIR / skill / "SKILL.md"
    description = _frontmatter(path).get("description", "")
    body = _body(path)
    assert ("IMMEDIATELY" in description) == keeps_immediately, (
        f"{path}: description trigger text changed"
    )
    assert "IMMEDIATELY" not in body, f"{path}: body must not shout IMMEDIATELY"
    assert "Do NOT" not in body, f"{path}: body must not carry Do NOT"
    assert "The script IS the workflow" not in body, f"{path}: body keeps the plain sentence only"
    assert "Run the script first and follow its output" in body, f"{path}: plain sentence missing"


def test_orchestrator_constraint_carries_scoped_autonomy_and_relay():
    """The orchestrator constant keeps its autonomy text and the AskUserQuestion relay, and
    never says the user cannot answer: the main session owns AskUserQuestion and relays
    every sub-agent question. Neither constant contains emphatic tokens, and the extended constant has no
    thinking-length block.
    """
    where = "skills/planner/shared/constraints.py"
    assert "You are operating autonomously" in ORCHESTRATOR_CONSTRAINT, where
    assert "AskUserQuestion" in ORCHESTRATOR_CONSTRAINT, where
    assert "<needs_user_input>" in ORCHESTRATOR_CONSTRAINT, where
    assert "cannot answer" not in ORCHESTRATOR_CONSTRAINT, where
    for text in (ORCHESTRATOR_CONSTRAINT, ORCHESTRATOR_CONSTRAINT_EXTENDED):
        for token in ("PROHIBITED", "REQUIRED", "DO NOT"):
            assert token not in text, f"{where}: {token!r} must be absent"
    for token in ("THINKING EFFICIENCY", "THINKING", "max 5 words"):
        assert token not in ORCHESTRATOR_CONSTRAINT_EXTENDED, f"{where}: {token!r} must be absent"


def test_thinking_efficiency_and_return_budget_are_undefined():
    """THINKING_EFFICIENCY and SUBAGENT_RETURN_BUDGET are not defined; each hasattr
    check fails if the name exists in its module.
    """
    assert not hasattr(workflow_cli, "THINKING_EFFICIENCY"), "skills/lib/workflow/cli.py"
    assert not hasattr(builders, "THINKING_EFFICIENCY"), "skills/planner/shared/builders.py"
    assert not hasattr(workflow_constants, "SUBAGENT_RETURN_BUDGET"), "skills/lib/workflow/constants.py"
