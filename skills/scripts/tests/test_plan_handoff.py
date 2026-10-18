"""Tests for plan.md provenance, sidecars and executor --plan-file resolution."""

import os
import subprocess
import sys
from pathlib import Path

import pytest
from hypothesis import given, settings, strategies as st

from skills.planner.shared.provenance import (
    PROVENANCE_PREFIX,
    parse_provenance,
    render_provenance,
    resolve_plan_state,
    sidecar_paths,
)
from skills.planner.orchestrator.planner import format_deliver_instructions

SCRIPTS_DIR = Path(__file__).resolve().parent.parent


def _run(*args, tmpdir=None):
    env = None if tmpdir is None else {**os.environ, "TMPDIR": str(tmpdir)}
    return subprocess.run(
        [sys.executable, "-m", *args], cwd=SCRIPTS_DIR, capture_output=True, text=True,
        env=env)


def _minimal_plan(state_dir):
    r = _run("skills.planner.cli.plan", "--state-dir", str(state_dir), "init", "--task", "t")
    assert r.returncode == 0, r.stdout + r.stderr


@given(
    state_dir=st.text(alphabet=st.characters(min_codepoint=32, max_codepoint=126), min_size=1),
    plan_id=st.uuids().map(str),
    created_at=st.datetimes().map(lambda d: d.isoformat()),
)
@settings(max_examples=50)
def test_render_parse_round_trip(state_dir, plan_id, created_at):
    line = render_provenance(state_dir, plan_id, created_at)
    assert "\n" not in line
    assert line.startswith(PROVENANCE_PREFIX) and line.endswith("-->")
    assert parse_provenance(line + "\n# Plan\n") == {
        "state_dir": state_dir, "plan_id": plan_id, "created_at": created_at}


def test_parse_returns_none_without_header():
    assert parse_provenance("# Plan\n\nbody") is None


# Sidecars outrank the provenance directory because they are copied deliberately
# and outlive /tmp cleanup; a removed directory must fall through to the manual
# instruction instead of raising.
class TestResolve:
    def _plan_md(self, tmp_path, state_dir):
        md = tmp_path / "plan.md"
        md.write_text(render_provenance(str(state_dir), "pid", "2026-01-01T00:00:00") + "\n# Plan\n")
        return md

    def test_sidecar_preferred_over_live_provenance(self, tmp_path):
        live = tmp_path / "live"
        live.mkdir()
        (live / "plan.json").write_text("{}")
        md = self._plan_md(tmp_path, live)
        side_plan, side_ctx = sidecar_paths(md)
        side_plan.write_text("{}")
        side_ctx.write_text("{}")
        res = resolve_plan_state(md)
        assert res.source == "sidecar" and res.context_json == side_ctx

    def test_sidecar_without_context(self, tmp_path):
        md = self._plan_md(tmp_path, tmp_path / "gone")
        sidecar_paths(md)[0].write_text("{}")
        res = resolve_plan_state(md)
        assert res.source == "sidecar" and res.context_json is None

    def test_provenance_when_dir_live(self, tmp_path):
        live = tmp_path / "live"
        live.mkdir()
        (live / "plan.json").write_text("{}")
        res = resolve_plan_state(self._plan_md(tmp_path, live))
        assert res.source == "provenance" and res.plan_id == "pid"

    def test_none_when_dir_removed(self, tmp_path):
        assert resolve_plan_state(self._plan_md(tmp_path, tmp_path / "gone")).source == "none"


def test_translate_prepends_header_only(tmp_path):
    pytest.importorskip("pydantic")
    from skills.planner.cli.plan_commands import PlanContext, _translate
    from skills.planner.cli.plan import translate_to_markdown

    _minimal_plan(tmp_path)
    ctx = PlanContext(state_dir=tmp_path)
    out = tmp_path / "plan.md"
    _translate(ctx, str(out))
    lines = out.read_text().split("\n", 1)
    assert lines[0].startswith(PROVENANCE_PREFIX)
    assert lines[1] == translate_to_markdown(ctx.load_plan())


class TestExecutorStep1:
    def test_plan_file_with_sidecars_copies_into_new_state_dir(self, tmp_path):
        md = tmp_path / "plan.md"
        md.write_text("# Plan\n")
        side_plan, side_ctx = sidecar_paths(md)
        side_plan.write_text("{}")
        side_ctx.write_text("{}")
        r = _run("skills.planner.orchestrator.executor", "--step", "1", "--plan-file", str(md),
               tmpdir=tmp_path)
        assert r.returncode == 0, r.stderr
        line = next(l for l in r.stdout.splitlines() if l.startswith("STATE_DIR="))
        state_dir = Path(line.split("=", 1)[1])
        assert (state_dir / "plan.json").exists() and (state_dir / "context.json").exists()
        assert "source=sidecar" in r.stdout

    def test_existing_state_dir_is_reused(self, tmp_path):
        (tmp_path / "plan.json").write_text("{}")
        md = tmp_path / "other.md"
        md.write_text("# Plan\n")
        r = _run("skills.planner.orchestrator.executor", "--step", "1",
                 "--state-dir", str(tmp_path), "--plan-file", str(md))
        assert "reusing plan.json" in r.stdout

    def test_no_arguments_prints_manual_instruction(self, tmp_path):
        r = _run("skills.planner.orchestrator.executor", "--step", "1", tmpdir=tmp_path)
        assert r.returncode == 0, r.stderr
        assert "copy the plan's plan.json" in r.stdout

    def test_stale_state_dir_yields_state_line(self, tmp_path):
        md = tmp_path / "plan.md"
        md.write_text("# Plan\n")
        sidecar_paths(md)[0].write_text("{}")
        stale = tmp_path / "gone" / "deeper"
        r = _run("skills.planner.orchestrator.executor", "--step", "1",
                 "--state-dir", str(stale), "--plan-file", str(md))
        assert "Traceback" not in r.stderr
        assert "STATE:" in r.stdout


def test_deliver_instructions_content():
    text = format_deliver_instructions("/tmp/s/plan.md", "/tmp/s")
    for needle in (".plan.json", ".context.json", "--plan-file", "optional"):
        assert needle in text.lower()


def test_render_context_or_notice_missing(tmp_path):
    from skills.planner.shared.resources import render_context_or_notice
    assert "not found" in render_context_or_notice(str(tmp_path / "context.json"))
