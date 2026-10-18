"""Tests for fix-mode plan file scope and the git-status scope check."""

import json
import subprocess

import pytest
from hypothesis import given, strategies as st

from skills.planner.developer import exec_implement_qr_fix
from skills.planner.technical_writer import exec_docs_qr_fix
from skills.planner.shared.plan_scope import (
    format_plan_file_scope,
    scope_check_commands,
    format_scope_check,
    baseline_commands,
    parse_porcelain,
    plan_scope_paths,
)


def _plan(files=None, intents=(), changes=(), readme=()):
    return {
        "milestones": [{
            "id": "M-001", "name": "Alpha", "files": files or [],
            "code_intents": [{"file": f} for f in intents],
            "code_changes": [{"file": f} for f in changes],
        }],
        "readme_entries": [{"path": p} for p in readme],
    }


def _write(tmp_path, plan):
    (tmp_path / "plan.json").write_text(json.dumps(plan))


def _qr(tmp_path, phase):
    (tmp_path / f"qr-{phase}.json").write_text(json.dumps({
        "phase": phase, "iteration": 1,
        "items": [{"id": "qa-001", "scope": "*", "check": "c", "status": "FAIL",
                   "version": 2, "finding": "bad"}],
    }))


_PATHS = st.lists(st.sampled_from(["a.py", "b.py", "c.py", "d/e.py"]), max_size=6)


class TestScopePaths:
    @given(_PATHS, _PATHS, _PATHS)
    def test_sorted_unique_union(self, files, intents, changes):
        scope = plan_scope_paths(_plan(files=files, intents=intents, changes=changes))
        assert scope["M-001 Alpha"] == sorted(set(files) | set(intents) | set(changes))

    def test_union_and_dedupe(self):
        scope = plan_scope_paths(_plan(files=["a.py", "a.py"], intents=["b.py"], changes=["c.py", "a.py"]))
        assert scope == {"M-001 Alpha": ["a.py", "b.py", "c.py"]}

    def test_change_only_path_and_empty_files(self):
        scope = plan_scope_paths(_plan(files=[], changes=["only.py"]))
        assert scope["M-001 Alpha"] == ["only.py"]


class TestFormatScope:
    def test_empty_without_plan(self, tmp_path):
        assert format_plan_file_scope(str(tmp_path)) == ""

    def test_header_states_root(self, tmp_path):
        _write(tmp_path, _plan(files=["pkg/a.py"]))
        text = format_plan_file_scope(str(tmp_path))
        assert "target repository root" in text and "pkg/a.py" in text

    def test_doc_companions(self, tmp_path):
        _write(tmp_path, _plan(files=["pkg/a.py"], readme=["other"]))
        text = format_plan_file_scope(str(tmp_path), include_doc_companions=True)
        assert "pkg/CLAUDE.md" in text and "other/README.md" in text


class TestParsePorcelain:
    @given(st.lists(st.sampled_from(["a.py", "dir/b.py", "c d.py"]), max_size=5),
           st.sampled_from([" M", "??", "A ", "MM"]))
    def test_plain_entries_round_trip(self, names, status):
        text = "".join(f"{status} {n}\n" for n in names)
        assert parse_porcelain(text) == set(names)

    def test_status_forms(self):
        text = ' M a.py\n?? b.py\nR  old.py -> new.py\n M "sp ace.py"\n'
        assert parse_porcelain(text) == {"a.py", "b.py", "new.py", "sp ace.py"}


# Includes a real-repository case: without -uall an untracked directory collapses to 'dir/', so classification is exercised against genuine porcelain output.
class TestScopeCheck:
    def test_classification(self, tmp_path):
        _write(tmp_path, _plan(files=["in.py", "new.py"]))
        (tmp_path / "scope-baseline-code.txt").write_text(" M old_dirty.py\n")
        (tmp_path / "scope-current-code.txt").write_text(
            " M old_dirty.py\n M in.py\n?? stray.py\nR  x.py -> new.py\n")
        text = format_scope_check(str(tmp_path), "code")
        assert "IN SCOPE in.py" in text
        assert "OUT OF SCOPE stray.py" in text
        assert "IN SCOPE new.py" in text
        assert "old_dirty.py" not in text

    def test_directory_entry_with_planned_file_is_in_scope(self, tmp_path):
        _write(tmp_path, _plan(files=["newdir/x.py"]))
        (tmp_path / "scope-baseline-code.txt").write_text("")
        (tmp_path / "scope-current-code.txt").write_text("?? newdir/\n?? other/\n")
        text = format_scope_check(str(tmp_path), "code")
        assert "IN SCOPE newdir/" in text and "OUT OF SCOPE other/" in text

    def test_new_directory_in_real_repo(self, tmp_path):
        repo = tmp_path / "repo"
        (repo / "newdir").mkdir(parents=True)
        (repo / "newdir" / "x.py").write_text("x = 1\n")
        (repo / "stray.py").write_text("y = 1\n")
        subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
        plain = subprocess.run(["git", "status", "--porcelain"], cwd=repo,
                               capture_output=True, text=True, check=True).stdout
        assert "newdir/" in parse_porcelain(plain)
        assert "-uall" in "\n".join(baseline_commands(str(tmp_path), "code"))
        full = subprocess.run(["git", "status", "--porcelain", "-uall"], cwd=repo,
                              capture_output=True, text=True, check=True).stdout
        state = tmp_path / "state"
        state.mkdir()
        _write(state, _plan(files=["newdir/x.py"]))
        (state / "scope-baseline-code.txt").write_text("")
        (state / "scope-current-code.txt").write_text(full)
        text = format_scope_check(str(state), "code", root=str(repo))
        assert "IN SCOPE newdir/x.py" in text and "OUT OF SCOPE stray.py" in text

    def test_wrong_root_notice(self, tmp_path):
        _write(tmp_path, _plan(files=["in.py"]))
        (tmp_path / "scope-baseline-code.txt").write_text("")
        (tmp_path / "scope-current-code.txt").write_text("?? stray.py\n")
        text = format_scope_check(str(tmp_path), "code", root=str(tmp_path / "nowhere"))
        assert "UNAVAILABLE" in text and "OUT OF SCOPE" not in text

    def test_scope_check_commands_shared(self):
        text = "\n".join(scope_check_commands("/s", "docs", docs=True))
        assert "--phase docs --docs --root ROOT" in text and "-uall" in text

    def test_missing_baseline_notice(self, tmp_path):
        _write(tmp_path, _plan(files=["in.py"]))
        (tmp_path / "scope-current-code.txt").write_text("")
        assert "scope-baseline-code.txt is missing" in format_scope_check(str(tmp_path), "code")


class TestFixGuidance:
    @pytest.mark.parametrize("module,phase,scope_marker,companion,step3_markers", [
        (exec_implement_qr_fix, "impl-code", "scope-baseline-code.txt", None,
         ["git -C ROOT status --porcelain", "skills.planner.shared.plan_scope", "OUT OF SCOPE"]),
        (exec_docs_qr_fix, "impl-docs", "scope-baseline-docs.txt", "pkg/CLAUDE.md",
         ["--phase docs --docs", "OUT OF SCOPE"]),
    ])
    def test_fix_steps(self, tmp_path, module, phase, scope_marker, companion, step3_markers):
        _write(tmp_path, _plan(files=["pkg/a.py"]))
        _qr(tmp_path, phase)
        s = str(tmp_path)
        step1 = "\n".join(module.get_step_guidance(1, state_dir=s)["actions"])
        assert scope_marker in step1 and (companion or "pkg/a.py") in step1
        if companion is None:
            assert "PLAN FILE SCOPE" in step1
        step3 = "\n".join(module.get_step_guidance(3, state_dir=s)["actions"])
        for marker in step3_markers:
            assert marker in step3
