"""Tests for the iteration-stamped QR verdict transition rule."""

import json
import subprocess
import sys
from pathlib import Path

import pytest
from hypothesis import HealthCheck, given, settings, strategies as st

from skills.planner.cli import qr_commands
from skills.planner.shared.qr.utils import increment_qr_iteration
from skills.planner.shared.schema import (
    QA_ITEM_OPTIONAL_FIELDS,
    get_qa_state_schema_example,
)

SCRIPTS_DIR = Path(__file__).resolve().parent.parent
ITERATION = 3


def _write_qr(tmp_path, status, stamp, iteration=ITERATION):
    item = {"id": "qa-001", "scope": "*", "check": "c", "status": status, "version": 1}
    if status == "FAIL":
        item["finding"] = "bad"
    if stamp is not None:
        item["iteration"] = stamp
    path = tmp_path / "qr-plan-code.json"
    path.write_text(json.dumps({"phase": "plan-code", "iteration": iteration, "items": [item]}))
    return path


# Restates the rule from scratch without importing check_transition's constants,
# so a change to the implementation fails the matrix rather than moving both sides.
def _expect_accept(current, requested, stamp):
    return not (current == "FAIL" and requested == "PASS"
                and (stamp is None or stamp >= ITERATION))


def _update(tmp_path, requested):
    ctx = qr_commands.QRContext(state_dir=tmp_path, phase="plan-code")
    finding = "still bad" if requested == "FAIL" else None
    return qr_commands.update_item(ctx, "qa-001", requested, finding)


@settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(
    current=st.sampled_from(["TODO", "PASS", "FAIL"]),
    requested=st.sampled_from(["PASS", "FAIL"]),
    stamp=st.sampled_from([None, ITERATION - 1, ITERATION]),
)
def test_transition_matrix(tmp_path_factory, current, requested, stamp):
    tmp_path = tmp_path_factory.mktemp("qr")
    path = _write_qr(tmp_path, current, stamp)
    if not _expect_accept(current, requested, stamp):
        with pytest.raises(ValueError):
            _update(tmp_path, requested)
        return
    result = _update(tmp_path, requested)
    saved = json.loads(path.read_text())["items"][0]
    if current == "PASS" and requested == "PASS":
        assert result["operation"] == "unchanged"
        assert saved["version"] == 1
    else:
        assert result["operation"] == "updated"
        assert saved["iteration"] == ITERATION
        assert saved["status"] == requested


def test_unstamped_fail_released_after_increment(tmp_path):
    path = _write_qr(tmp_path, "FAIL", None, iteration=2)
    with pytest.raises(ValueError):
        _update(tmp_path, "PASS")
    assert increment_qr_iteration(str(tmp_path), "plan-code") == 3
    saved = json.loads(path.read_text())["items"][0]
    assert saved["iteration"] == 2
    assert _update(tmp_path, "PASS")["operation"] == "updated"


@pytest.mark.parametrize("stamp", [None, ITERATION - 1, ITERATION])
@pytest.mark.parametrize("requested", ["PASS", "FAIL"])
@pytest.mark.parametrize("current", ["TODO", "PASS", "FAIL"])
def test_cli_matches_commands(tmp_path, current, requested, stamp):
    path = _write_qr(tmp_path, current, stamp)
    args = ["update-item", "qa-001", "--status", requested]
    if requested == "FAIL":
        args += ["--finding", "late defect"]
    proc = subprocess.run(
        [sys.executable, "-m", "skills.planner.cli.qr", "--state-dir", str(tmp_path),
         "--qr-phase", "plan-code", *args],
        cwd=SCRIPTS_DIR, capture_output=True, text=True,
    )
    accepted = _expect_accept(current, requested, stamp)
    assert (proc.returncode == 0) == accepted
    if accepted and current == "PASS" and requested == "PASS":
        assert "unchanged" in proc.stdout
    if accepted:
        assert json.loads(path.read_text())["items"][0]["status"] == requested


def test_schema_exposes_iteration():
    assert "iteration" in QA_ITEM_OPTIONAL_FIELDS
    assert '"iteration"' in get_qa_state_schema_example("plan-code")


def test_validate_state_accepts_with_and_without_iteration(tmp_path):
    # Skipped, not failed, where pydantic is absent; run with
    # `uvx --with pydantic --with hypothesis pytest tests/ -v` so the skip cannot hide a schema regression.
    pytest.importorskip("pydantic")
    from skills.planner.shared.schema import validate_state
    base = {"id": "qa-001", "scope": "*", "check": "c", "status": "TODO", "version": 1}
    for item in (base, {**base, "iteration": 1}):
        (tmp_path / "qr-plan-code.json").write_text(
            json.dumps({"phase": "plan-code", "iteration": 1, "items": [item]}))
        validate_state(str(tmp_path))
