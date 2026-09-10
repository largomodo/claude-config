"""Tests guarding the Serena tool policy against drift.

Ties together three surfaces that must stay in sync: the deployed Serena
tool set (REAL_SERENA_TOOLS, hardcoded from claude-code.yml), the Python
constants in skills.lib.workflow.prompts.serena, the tools: allowlists in
agents/*.md, and the prose in conventions/code-navigation.md. Also guards
that mode_main injects the right preamble variant at the right step, that
orchestrator scripts never inject, and that pre-Serena tool phrasing does
not reappear in skill scripts.

Frontmatter parsing uses a hand-rolled scanner rather than a YAML parser
because the suite runs with only pytest and hypothesis installed. The
mode_main injection tests call the function in-process with a monkeypatched
argv and a stub guidance dict, since its output depends only on module
path, step and guidance and needs no state-dir fixture. Leaf scripts carry
no state requirement, so a subprocess call is cheap and exercises them the
way they actually run. A forbidden-phrase scan catches wording that
instructs an agent to read or search with Read, Glob or Grep directly
instead of the Serena tools. (DL-011)
"""

import re
import subprocess
import sys
from pathlib import Path

import pytest

from skills.lib.workflow.prompts.serena import (
    SERENA_TOOL_PREFIX,
    SERENA_POLICY,
    SERENA_READ_TOOLS,
    SERENA_EDIT_TOOLS,
    SERENA_MEMORY_READ_TOOLS,
    SERENA_SUBAGENT_DENIED_TOOLS,
    SERENA_EXCLUDED_TOOLS,
    SERENA_READ_PREAMBLE,
    SERENA_EDIT_PREAMBLE,
    SERENA_FALLBACK,
)


REPO_ROOT = Path(__file__).resolve().parents[3]

# Source: serena/resources/config/contexts/claude-code.yml (excluded_tools)
# plus serena/agent.py SingleProjectExclusions, which removes
# activate_project and get_current_config when single_project mode is set.
# Those two names are deliberately absent below.
REAL_SERENA_TOOLS = frozenset((
    "get_symbols_overview",
    "find_symbol",
    "find_referencing_symbols",
    "find_declaration",
    "find_implementations",
    "get_diagnostics_for_file",
    "replace_symbol_body",
    "insert_before_symbol",
    "insert_after_symbol",
    "replace_content",
    "replace_in_files",
    "rename_symbol",
    "safe_delete_symbol",
    "list_memories",
    "read_memory",
    "write_memory",
    "edit_memory",
    "rename_memory",
    "delete_memory",
    "onboarding",
    "initial_instructions",
))
assert len(REAL_SERENA_TOOLS) == 21

SERENA_POLICY_FIRST_LINE = SERENA_POLICY.splitlines()[0]

FORBIDDEN_PHRASES = (
    "Use Glob, Grep, Read tools directly",
    "Use Read/Glob/Grep",
    "Use Grep to find relevant code",
    "Use Read to examine",
    "Use Edit tool",
    "using Edit tool",
)

EXCLUDED_PATTERN = re.compile(
    r"mcp__serena__(" + "|".join(SERENA_EXCLUDED_TOOLS) + r")\b"
)
SERENA_NAME_PATTERN = re.compile(r"mcp__serena__([a-z_]+)")

EDIT_ROLES = {"developer", "debugger", "technical-writer"}

AGENTS_DIR = REPO_ROOT / "agents"
CONVENTIONS_DIR = REPO_ROOT / "conventions"
SKILLS_DIR = REPO_ROOT / "skills" / "scripts" / "skills"
CONVENTION_FILE = CONVENTIONS_DIR / "code-navigation.md"


def parse_agent_tools(path: Path) -> list[str]:
    """Extract the tools: list from an agent markdown file's frontmatter.

    A hand-rolled scanner instead of a YAML parser: this suite runs with
    only pytest and hypothesis installed, and the frontmatter's tools: list
    is regular enough (one "- name" per line) that a full parser buys
    nothing a few lines of string matching does not already cover.
    """
    text = path.read_text()
    parts = text.split("---")
    if len(parts) < 3:
        return []
    frontmatter = parts[1]
    lines = frontmatter.splitlines()
    tools = []
    in_tools = False
    for line in lines:
        stripped = line.strip()
        if stripped == "tools:":
            in_tools = True
            continue
        if in_tools:
            if not stripped or stripped.startswith("#"):
                continue
            if stripped.startswith("- "):
                tools.append(stripped[2:].strip())
            elif not line.startswith((" ", "-")) and stripped.endswith(":"):
                break
    return tools


def _agent_files():
    return sorted(p for p in AGENTS_DIR.glob("*.md") if p.name != "CLAUDE.md")


# =============================================================================
# Tool tuple partition
# =============================================================================


def test_tool_tuples_partition_real():
    """The four non-excluded tuples partition REAL_SERENA_TOOLS."""
    groups = (
        SERENA_READ_TOOLS,
        SERENA_EDIT_TOOLS,
        SERENA_MEMORY_READ_TOOLS,
        SERENA_SUBAGENT_DENIED_TOOLS,
    )
    seen = set()
    for group in groups:
        overlap = seen & set(group)
        assert not overlap, f"Duplicate tool names across tuples: {overlap}"
        seen |= set(group)
    assert seen == REAL_SERENA_TOOLS
    assert set(SERENA_EXCLUDED_TOOLS).isdisjoint(REAL_SERENA_TOOLS)


# =============================================================================
# Agent allowlists
# =============================================================================


@pytest.mark.parametrize("path", _agent_files(), ids=lambda p: p.stem)
def test_agent_allowlists(path):
    """Every agent's Serena names are grantable; no denied or excluded names."""
    tools = parse_agent_tools(path)
    assert tools, f"{path.name} has no tools: list"
    for required in ("Read", "Glob", "Grep", "Bash", "Write", "ToolSearch"):
        assert required in tools, f"{path.name} missing {required}"

    grantable = set(SERENA_READ_TOOLS) | set(SERENA_EDIT_TOOLS) | set(SERENA_MEMORY_READ_TOOLS)
    for tool in tools:
        if not tool.startswith(SERENA_TOOL_PREFIX):
            continue
        name = tool[len(SERENA_TOOL_PREFIX):]
        assert name in grantable, f"{path.name} lists non-grantable Serena tool {tool}"
        assert name not in SERENA_SUBAGENT_DENIED_TOOLS, f"{path.name} lists denied Serena tool {tool}"
        assert name not in SERENA_EXCLUDED_TOOLS, f"{path.name} lists excluded Serena tool {tool}"


@pytest.mark.parametrize("path", _agent_files(), ids=lambda p: p.stem)
def test_edit_capability(path):
    """Edit and the Serena edit tools appear only for edit-capable roles."""
    tools = parse_agent_tools(path)
    is_edit_role = path.stem in EDIT_ROLES

    assert ("Edit" in tools) == is_edit_role, f"{path.name}: Edit presence mismatch"

    for tool in SERENA_EDIT_TOOLS:
        prefixed = SERENA_TOOL_PREFIX + tool
        assert (prefixed in tools) == is_edit_role, (
            f"{path.name}: {prefixed} presence mismatch"
        )


def test_developer_has_agent_tool():
    """Agent tool is developer-only; TodoWrite is debugger-only."""
    for path in _agent_files():
        tools = parse_agent_tools(path)
        assert ("Agent" in tools) == (path.stem == "developer"), (
            f"{path.name}: Agent tool presence mismatch"
        )
        assert ("TodoWrite" in tools) == (path.stem == "debugger"), (
            f"{path.name}: TodoWrite presence mismatch"
        )


# =============================================================================
# Convention sync (bidirectional)
# =============================================================================


def test_convention_mentions_every_tool():
    """Every real, denied and excluded tool name appears prefixed in the convention."""
    text = CONVENTION_FILE.read_text()
    all_names = (
        set(SERENA_READ_TOOLS)
        | set(SERENA_EDIT_TOOLS)
        | set(SERENA_MEMORY_READ_TOOLS)
        | set(SERENA_SUBAGENT_DENIED_TOOLS)
        | set(SERENA_EXCLUDED_TOOLS)
    )
    for name in all_names:
        prefixed = SERENA_TOOL_PREFIX + name
        assert prefixed in text, f"{prefixed} missing from {CONVENTION_FILE.name}"


def test_convention_names_are_real():
    """Every mcp__serena__ name in the convention is real or excluded, in the right place."""
    text = CONVENTION_FILE.read_text()
    heading = "## Excluded tools"
    before, _, _ = text.partition(heading)

    all_names = set(REAL_SERENA_TOOLS) | set(SERENA_EXCLUDED_TOOLS)
    for match in SERENA_NAME_PATTERN.finditer(text):
        assert match.group(1) in all_names, f"Unknown Serena tool in convention: {match.group(0)}"

    for match in SERENA_NAME_PATTERN.finditer(before):
        assert match.group(1) in REAL_SERENA_TOOLS, (
            f"Excluded tool named before '{heading}': {match.group(0)}"
        )


# =============================================================================
# Excluded names absent from code
# =============================================================================


def test_excluded_names_absent():
    """Excluded Serena tool names never appear (prefixed) outside their sanctioned homes."""
    for path in AGENTS_DIR.glob("*.md"):
        text = path.read_text()
        assert not EXCLUDED_PATTERN.search(text), f"{path} references an excluded Serena tool"

    for path in CONVENTIONS_DIR.glob("*.md"):
        if path == CONVENTION_FILE:
            continue
        text = path.read_text()
        assert not EXCLUDED_PATTERN.search(text), f"{path} references an excluded Serena tool"

    convention_text = CONVENTION_FILE.read_text()
    before, _, _ = convention_text.partition("## Excluded tools")
    assert not EXCLUDED_PATTERN.search(before), (
        "Excluded Serena tool referenced before the Excluded tools heading"
    )

    serena_module = SKILLS_DIR / "lib" / "workflow" / "prompts" / "serena.py"
    for path in SKILLS_DIR.rglob("*.py"):
        if path == serena_module:
            continue
        text = path.read_text()
        assert not EXCLUDED_PATTERN.search(text), f"{path} references an excluded Serena tool"


# =============================================================================
# Forbidden phrases
# =============================================================================


def test_forbidden_phrases_absent():
    """Pre-Serena tool phrasing does not reappear in skill scripts."""
    for path in SKILLS_DIR.rglob("*.py"):
        text = path.read_text()
        for phrase in FORBIDDEN_PHRASES:
            assert phrase not in text, f"{path} contains forbidden phrase: {phrase!r}"


# =============================================================================
# Preamble shape
# =============================================================================


def test_preambles_have_no_braces():
    """Preambles are plain concatenated strings, never passed through .format()."""
    assert "{" not in SERENA_READ_PREAMBLE
    assert "}" not in SERENA_READ_PREAMBLE
    assert "{" not in SERENA_EDIT_PREAMBLE
    assert "}" not in SERENA_EDIT_PREAMBLE


def test_preambles_contain_load_hint():
    """Each preamble carries its ToolSearch hint and the fallback clause,
    so the policy still works if Claude Code ever defers allowlisted MCP
    tools the way it defers unlisted ones."""
    for preamble in (SERENA_READ_PREAMBLE, SERENA_EDIT_PREAMBLE):
        assert "ToolSearch" in preamble
        assert SERENA_FALLBACK in preamble


# =============================================================================
# mode_main injection
# =============================================================================


def _stub_guidance(**extra):
    """Minimal get_step_guidance() stand-in for in-process mode_main tests."""
    guidance = {"title": "Stub", "actions": ["BODY"], "next": ""}
    guidance.update(extra)
    return guidance


@pytest.mark.parametrize(
    "script_file,expect",
    [
        ("/r/scripts/skills/planner/developer/exec_implement_execute.py", "edit"),
        ("/r/scripts/skills/planner/technical_writer/exec_docs_qr_fix.py", "edit"),
        ("/r/scripts/skills/planner/developer/plan_code_execute.py", "read"),
        ("/r/scripts/skills/planner/technical_writer/plan_docs_execute.py", "read"),
        ("/r/scripts/skills/planner/architect/plan_design_execute.py", "read"),
    ],
)
def test_mode_main_injection(monkeypatch, capsys, script_file, expect):
    """Step 1 injects the edit variant only for exec_* scripts of the
    developer and technical_writer packages; every other script gets the
    read variant."""
    from skills.lib.workflow.cli import mode_main

    monkeypatch.setattr(sys, "argv", ["x", "--step", "1"])
    mode_main(script_file, lambda step, module_path, **kw: _stub_guidance(), "stub")
    out = capsys.readouterr().out

    if expect == "edit":
        assert out.count(SERENA_EDIT_PREAMBLE) == 1
    else:
        assert SERENA_READ_PREAMBLE in out
        assert SERENA_EDIT_PREAMBLE not in out


def test_mode_main_injection_step_2_neither(monkeypatch, capsys):
    """Step 2 and later never carry the preamble."""
    from skills.lib.workflow.cli import mode_main

    monkeypatch.setattr(sys, "argv", ["x", "--step", "2"])
    mode_main(
        "/r/scripts/skills/planner/developer/plan_code_execute.py",
        lambda step, module_path, **kw: _stub_guidance(),
        "stub",
    )
    out = capsys.readouterr().out
    assert SERENA_READ_PREAMBLE not in out
    assert SERENA_EDIT_PREAMBLE not in out


def test_mode_main_injection_dispatch_to_neither(monkeypatch, capsys):
    """Router hand-offs (guidance carrying dispatch_to) skip the preamble."""
    from skills.lib.workflow.cli import mode_main

    monkeypatch.setattr(sys, "argv", ["x", "--step", "1"])
    mode_main(
        "/r/scripts/skills/planner/developer/exec_implement_execute.py",
        lambda step, module_path, **kw: _stub_guidance(dispatch_to="skills.planner.developer.exec_implement_execute"),
        "stub",
    )
    out = capsys.readouterr().out
    assert SERENA_READ_PREAMBLE not in out
    assert SERENA_EDIT_PREAMBLE not in out


def test_orchestrators_do_not_inject():
    """Orchestrator scripts never use mode_main and never reference Serena."""
    for name in ("planner.py", "executor.py"):
        path = SKILLS_DIR / "planner" / "orchestrator" / name
        text = path.read_text()
        assert "mode_main" not in text
        assert "SERENA_" not in text


# =============================================================================
# Leaf sub-agent scripts inject their own preamble
# =============================================================================


@pytest.mark.parametrize(
    "module,extra_args,title",
    [
        ("skills.deepthink.subagent", [], "DEEPTHINK SUB-AGENT - Context Grounding"),
        ("skills.codebase_analysis.subagent", [], "CODEBASE EXPLORE - Orient"),
        ("skills.refactor.explore", ["--category", "01-naming-and-types.md:5-13"], None),
    ],
)
def test_leaf_scripts_inject(module, extra_args, title):
    """general-purpose leaf scripts inject SERENA_POLICY at step 1 only.

    format_step prepends a title header before the body, so
    deepthink.subagent and codebase_analysis.subagent (mode_main-style
    title wrapping) place the preamble right after that header; explore.py
    builds step 1 without a title wrapper, so its preamble starts the
    output directly.
    """
    scripts_dir = REPO_ROOT / "skills" / "scripts"

    step1 = subprocess.run(
        [sys.executable, "-m", module, "--step", "1", *extra_args],
        capture_output=True, text=True, cwd=scripts_dir, timeout=30,
    )
    assert step1.returncode == 0, step1.stderr
    if title:
        header = f"{title}\n{'=' * len(title)}\n\n"
        assert step1.stdout.startswith(header)
        assert step1.stdout[len(header):].startswith(SERENA_POLICY_FIRST_LINE)
    else:
        assert step1.stdout.startswith(SERENA_POLICY_FIRST_LINE)

    step2 = subprocess.run(
        [sys.executable, "-m", module, "--step", "2", *extra_args],
        capture_output=True, text=True, cwd=scripts_dir, timeout=30,
    )
    assert step2.returncode == 0, step2.stderr
    assert SERENA_POLICY_FIRST_LINE not in step2.stdout
