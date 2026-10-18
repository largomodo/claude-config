"""Tests guarding the Serena REPL policy against drift.

Ties together four surfaces that must stay in sync: the two real MCP tool
names and the facade methods Serena's REPL exposes (hardcoded here because
CI has only pytest and hypothesis), the Python constants in
skills.lib.workflow.prompts.serena, the tools: lists in agents/*.md, and the
prose in conventions/code-navigation.md. Also guards that mode_main injects
the right preamble variant at the right step, that orchestrator scripts
never inject, that leaf scripts inject their own preamble, and that
phrasing which routes code reads or edits around Serena is absent from
skill scripts.

The facade-method set is hardcoded from serena/repl/api/*_api.py,
non-optional methods only: claude-env sets no included_apis, so the optional
methods (delete_lines, replace_lines, insert_at_line,
get_diagnostics_for_symbol, restart_language_server) are unavailable.
Names in prose are extracted as s.<facade>.<method> because that is how
Serena's manual names them and one regex needs no YAML parser or Serena
import. The mcp__serena__ scan walks the whole repo root and skips only
.git, __pycache__ and projects/ (the untracked runtime directory Claude
Code keeps in a live checkout, whose session notes may name retired
tools), so every output style and workflow under the root is scanned.

Frontmatter parsing uses a hand-rolled scanner rather than a YAML parser
because the suite runs with only pytest and hypothesis installed. The
mode_main injection tests call the function in-process with a monkeypatched
argv and a stub guidance dict, since its output depends only on module
path, step and guidance and needs no state-dir fixture. Leaf scripts carry
no state requirement, so a subprocess call is cheap and exercises them the
way they actually run. A forbidden-phrase scan catches wording that
instructs an agent to read or search with Read, Glob or Grep directly
instead of the Serena operations.
"""

import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

from skills.lib.workflow.prompts.serena import (
    SERENA_TOOL_PREFIX,
    SERENA_POLICY,
    SERENA_MCP_TOOLS,
    SERENA_READ_METHODS,
    SERENA_EDIT_METHODS,
    SERENA_MEMORY_READ_METHODS,
    SERENA_SUBAGENT_DENIED_METHODS,
    SERENA_HOST_COVERED_METHODS,
    SERENA_READ_ROLE_RULE,
    SERENA_EDIT_ROLE_RULE,
    SERENA_LOAD_HINT,
    SERENA_FALLBACK,
    SERENA_READ_PREAMBLE,
    SERENA_EDIT_PREAMBLE,
)


REPO_ROOT = Path(__file__).resolve().parents[3]

# Source: serena/tools/repl_tools.py. SerenaAgent with the claude-code
# context in single-project REPL mode exposes exactly these two tools.
REAL_SERENA_MCP_TOOLS = frozenset((
    "serena_repl",
    "initial_instructions",
))

# Source: serena/repl/api/{lsp,edit,mem,fs,shell,cfg}_api.py @facade_method
# entries without optional=True. Hardcoded: re-check this set against those
# files whenever claude-env bumps SERENA_VERSION, since a Serena upgrade can
# add, rename or remove facade methods without any change in this repo.
REAL_SERENA_FACADE_METHODS = frozenset((
    "lsp.get_symbols_overview",
    "lsp.find_symbol",
    "lsp.find_referencing_symbols",
    "lsp.find_implementations",
    "lsp.find_declaration",
    "lsp.get_diagnostics_for_file",
    "lsp.rename_symbol",
    "lsp.safe_delete_symbol",
    "edit.replace_content",
    "edit.replace_in_files",
    "edit.replace_symbol_body",
    "edit.insert_after_symbol",
    "edit.insert_before_symbol",
    "mem.list_memories",
    "mem.read_memory",
    "mem.write_memory",
    "mem.edit_memory",
    "mem.rename_memory",
    "mem.delete_memory",
    "mem.onboarding",
    "fs.read_file",
    "fs.create_text_file",
    "fs.list_dir",
    "fs.find_file",
    "fs.search_for_pattern",
    "shell.execute_shell_command",
    "cfg.get_current_config",
    "cfg.open_dashboard",
))
assert len(REAL_SERENA_FACADE_METHODS) == 28

POLICY_METHODS = frozenset(
    SERENA_READ_METHODS
    + SERENA_EDIT_METHODS
    + SERENA_MEMORY_READ_METHODS
    + SERENA_SUBAGENT_DENIED_METHODS
    + SERENA_HOST_COVERED_METHODS
)

# Serena's manual names operations s.<facade>.<method>; one regex over that
# form keeps prose, preambles and this test in sync without a YAML parser or
# a Serena import, which CI lacks. The alternation lists the six facades.
FACADE_METHOD_PATTERN = re.compile(r"\bs\.(lsp|edit|mem|fs|shell|cfg)\.([a-z_]+)")

SERENA_POLICY_FIRST_LINE = SERENA_POLICY.splitlines()[0]

# Skill-script wording changes only where it names a per-operation mechanism
# ("Serena symbol tools", bare operation names). Phrases that describe the
# operation class without a mechanism ("Serena symbol reads") stay as written:
# the preamble supplies the mechanism, and rewriting them adds no instruction.
FORBIDDEN_PHRASES = (
    "Use Glob, Grep, Read tools directly",
    "Use Read/Glob/Grep",
    "Use Grep to find relevant code",
    "Use Read to examine",
    "Use Edit tool",
    "using Edit tool",
)

SERENA_NAME_PATTERN = re.compile(r"mcp__serena__([a-z_]+)")

EDIT_ROLES = {"developer", "debugger", "technical-writer"}

AGENTS_DIR = REPO_ROOT / "agents"
CONVENTIONS_DIR = REPO_ROOT / "conventions"
SKILLS_DIR = REPO_ROOT / "skills" / "scripts" / "skills"
CONVENTION_FILE = CONVENTIONS_DIR / "code-navigation.md"

SCAN_SUFFIXES = (".md", ".py", ".yml", ".yaml", ".json")
# Only these three are pruned: skipping every dot-prefixed directory would
# exclude .github/ from the scan. projects/ is the untracked runtime
# directory Claude Code keeps in a live checkout; its session notes may
# legitimately name retired tools.
SCAN_PRUNED_DIRS = (".git", "__pycache__", "projects")


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
# Tool and method partition
# =============================================================================


def test_mcp_tools_match_real():
    """SERENA_MCP_TOOLS is exactly the two tools the REPL interface exposes."""
    assert set(SERENA_MCP_TOOLS) == REAL_SERENA_MCP_TOOLS


def test_method_tuples_partition_real():
    """The five method tuples are disjoint facade.method names; only cfg is unnamed."""
    groups = (
        SERENA_READ_METHODS,
        SERENA_EDIT_METHODS,
        SERENA_MEMORY_READ_METHODS,
        SERENA_SUBAGENT_DENIED_METHODS,
        SERENA_HOST_COVERED_METHODS,
    )
    seen = set()
    for group in groups:
        for entry in group:
            assert re.match(r"^(lsp|edit|mem|fs|shell)\.[a-z_]+$", entry), entry
        overlap = seen & set(group)
        assert not overlap, f"Duplicate method names across tuples: {overlap}"
        seen |= set(group)
    assert seen <= REAL_SERENA_FACADE_METHODS
    assert REAL_SERENA_FACADE_METHODS - seen == {
        "cfg.get_current_config",
        "cfg.open_dashboard",
    }


# =============================================================================
# Agent grants
# =============================================================================


@pytest.mark.parametrize("path", _agent_files(), ids=lambda p: p.stem)
def test_agent_grants(path):
    """Every agent grants exactly the two Serena MCP tools and the host basics."""
    tools = parse_agent_tools(path)
    assert tools, f"{path.name} has no tools: list"
    for required in ("Read", "Glob", "Grep", "Bash", "Write", "ToolSearch"):
        assert required in tools, f"{path.name} missing {required}"

    serena_tools = {t for t in tools if t.startswith(SERENA_TOOL_PREFIX)}
    expected = {SERENA_TOOL_PREFIX + name for name in SERENA_MCP_TOOLS}
    assert serena_tools == expected, f"{path.name}: Serena grants {serena_tools}"


@pytest.mark.parametrize("path", _agent_files(), ids=lambda p: p.stem)
def test_edit_capability(path):
    """Edit appears only for edit-capable roles."""
    tools = parse_agent_tools(path)
    is_edit_role = path.stem in EDIT_ROLES
    assert ("Edit" in tools) == is_edit_role, f"{path.name}: Edit presence mismatch"


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


def test_convention_mentions_every_method():
    """Every policy method appears as s.<facade>.<method> in the convention."""
    text = CONVENTION_FILE.read_text()
    for entry in POLICY_METHODS:
        assert "s." + entry in text, f"s.{entry} missing from {CONVENTION_FILE.name}"


def test_convention_methods_are_known():
    """Every s.<facade>.<method> name in the convention is a policy method."""
    text = CONVENTION_FILE.read_text()
    for match in FACADE_METHOD_PATTERN.finditer(text):
        entry = f"{match.group(1)}.{match.group(2)}"
        assert entry in POLICY_METHODS, (
            f"Unknown Serena method in convention: {match.group(0)}"
        )


def test_convention_names_both_mcp_tools():
    """Both MCP tool names appear prefixed in the convention."""
    text = CONVENTION_FILE.read_text()
    for name in SERENA_MCP_TOOLS:
        prefixed = SERENA_TOOL_PREFIX + name
        assert prefixed in text, f"{prefixed} missing from {CONVENTION_FILE.name}"


def test_no_hallucinated_mcp_names():
    """No file under the repo root names an mcp__serena__ tool the REPL lacks."""
    visited = set()
    for dirpath, dirnames, filenames in os.walk(REPO_ROOT):
        dirnames[:] = [d for d in dirnames if d not in SCAN_PRUNED_DIRS]
        for filename in filenames:
            path = Path(dirpath) / filename
            if path.suffix not in SCAN_SUFFIXES:
                continue
            visited.add(path)
            text = path.read_text(errors="replace")
            for match in SERENA_NAME_PATTERN.finditer(text):
                assert match.group(1) in REAL_SERENA_MCP_TOOLS, (
                    f"{path} names unknown Serena tool {match.group(0)}"
                )
    assert CONVENTION_FILE in visited, "repo walk missed the convention file"


def test_preamble_methods_are_known():
    """Every s.<facade>.<method> name in a preamble is a policy method."""
    for preamble in (SERENA_READ_PREAMBLE, SERENA_EDIT_PREAMBLE):
        for match in FACADE_METHOD_PATTERN.finditer(preamble):
            entry = f"{match.group(1)}.{match.group(2)}"
            assert entry in POLICY_METHODS, f"Unknown method in preamble: {match.group(0)}"


# =============================================================================
# Forbidden phrases
# =============================================================================


def test_forbidden_phrases_absent():
    """Phrasing that routes code reads or edits around Serena is absent from skill scripts."""
    for path in SKILLS_DIR.rglob("*.py"):
        text = path.read_text()
        for phrase in FORBIDDEN_PHRASES:
            assert phrase not in text, f"{path} contains forbidden phrase: {phrase!r}"


# =============================================================================
# Preamble shape
# =============================================================================


def test_preambles_have_no_braces():
    """Preambles are plain concatenated strings, never passed through .format()."""
    # REPL examples in the preambles are keyword calls, never dict or set
    # literals, so no brace can appear.
    assert "{" not in SERENA_READ_PREAMBLE
    assert "}" not in SERENA_READ_PREAMBLE
    assert "{" not in SERENA_EDIT_PREAMBLE
    assert "}" not in SERENA_EDIT_PREAMBLE


def test_role_clauses_select_variant():
    """Each preamble carries its own role clause and not the other's."""
    assert SERENA_READ_ROLE_RULE in SERENA_READ_PREAMBLE
    assert SERENA_READ_ROLE_RULE not in SERENA_EDIT_PREAMBLE
    assert SERENA_EDIT_ROLE_RULE in SERENA_EDIT_PREAMBLE
    assert SERENA_EDIT_ROLE_RULE not in SERENA_READ_PREAMBLE
    assert "no s.edit" in SERENA_READ_ROLE_RULE


def test_preambles_contain_load_hint_and_fallback():
    """Each preamble carries its ToolSearch hint and the fallback clause,
    so the policy still works if Claude Code defers the MCP tools."""
    for preamble in (SERENA_READ_PREAMBLE, SERENA_EDIT_PREAMBLE):
        assert SERENA_LOAD_HINT in preamble
        assert SERENA_FALLBACK in preamble
    assert "ToolSearch" in SERENA_LOAD_HINT
    for name in SERENA_MCP_TOOLS:
        assert SERENA_TOOL_PREFIX + name in SERENA_LOAD_HINT
    assert SERENA_TOOL_PREFIX + "serena_repl" in SERENA_FALLBACK


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
