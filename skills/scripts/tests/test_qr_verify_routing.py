"""Unit tests for QR verify step routing logic.

Tests the dynamic step calculation: total_steps = 1 + (2 * num_items) + 1
Step 1 is CONTEXT, steps 2..2N+1 alternate ANALYZE/CONFIRM, final step is SUMMARY.
"""

import json

import pytest
from hypothesis import given, strategies as st

from skills.planner.quality_reviewer.prompts import decompose
from skills.planner.quality_reviewer.qr_verify_base import VerifyBase, render_verdict_block
from skills.planner.shared import steps
from skills.planner.shared.constants import DECOMPOSE_TOTAL_STEPS, DECOMPOSE_WRITE_STEP
from skills.planner.shared.qr.types import QRState, LoopState


def get_step_type(step: int, num_items: int) -> tuple[str, int | None]:
    """Standalone copy of _get_step_type for testing without VerifyBase."""
    if step == 1:
        return ("CONTEXT", None)
    final_step = 2 + (2 * num_items)
    if step == final_step:
        return ("SUMMARY", None)
    item_offset = step - 2
    item_index = item_offset // 2
    phase = item_offset % 2
    return ("ANALYZE" if phase == 0 else "CONFIRM", item_index)


def get_total_steps(num_items: int) -> int:
    """Calculate total steps for N items: 1 + (2 * N) + 1."""
    return 2 + (2 * num_items)


class TestStepRouting:
    """Test step routing for various item counts."""

    def test_step_routing_1_item(self):
        """Verify step routing for single item."""
        assert get_step_type(1, 1) == ("CONTEXT", None)
        assert get_step_type(2, 1) == ("ANALYZE", 0)
        assert get_step_type(3, 1) == ("CONFIRM", 0)
        assert get_step_type(4, 1) == ("SUMMARY", None)
        assert get_total_steps(1) == 4

    def test_step_routing_2_items(self):
        """Verify step routing for 2 items."""
        assert get_step_type(1, 2) == ("CONTEXT", None)
        assert get_step_type(2, 2) == ("ANALYZE", 0)
        assert get_step_type(3, 2) == ("CONFIRM", 0)
        assert get_step_type(4, 2) == ("ANALYZE", 1)
        assert get_step_type(5, 2) == ("CONFIRM", 1)
        assert get_step_type(6, 2) == ("SUMMARY", None)
        assert get_total_steps(2) == 6

    def test_step_routing_3_items(self):
        """Verify step routing for 3 items produces correct sequence."""
        assert get_step_type(1, 3) == ("CONTEXT", None)
        assert get_step_type(2, 3) == ("ANALYZE", 0)
        assert get_step_type(3, 3) == ("CONFIRM", 0)
        assert get_step_type(4, 3) == ("ANALYZE", 1)
        assert get_step_type(5, 3) == ("CONFIRM", 1)
        assert get_step_type(6, 3) == ("ANALYZE", 2)
        assert get_step_type(7, 3) == ("CONFIRM", 2)
        assert get_step_type(8, 3) == ("SUMMARY", None)
        assert get_total_steps(3) == 8

    def test_step_routing_5_items(self):
        """Verify step routing for 5 items."""
        assert get_step_type(1, 5) == ("CONTEXT", None)
        # Items 0-4
        for i in range(5):
            analyze_step = 2 + (i * 2)
            confirm_step = 3 + (i * 2)
            assert get_step_type(analyze_step, 5) == ("ANALYZE", i)
            assert get_step_type(confirm_step, 5) == ("CONFIRM", i)
        assert get_step_type(12, 5) == ("SUMMARY", None)
        assert get_total_steps(5) == 12

    def test_total_steps_formula(self):
        """Verify formula: total_steps = 1 + (2 * num_items) + 1 = 2 + 2*N."""
        for n in range(1, 11):
            expected = 2 + (2 * n)
            assert get_total_steps(n) == expected, f"Failed for n={n}"


class TestStepTypeInvariants:
    """Test invariants of step routing."""

    def test_step_1_always_context(self):
        """Step 1 is always CONTEXT regardless of item count."""
        for n in range(1, 20):
            assert get_step_type(1, n) == ("CONTEXT", None)

    def test_final_step_always_summary(self):
        """Final step is always SUMMARY."""
        for n in range(1, 20):
            final = get_total_steps(n)
            assert get_step_type(final, n) == ("SUMMARY", None)

    def test_analyze_before_confirm(self):
        """For each item, ANALYZE comes before CONFIRM."""
        for n in range(1, 10):
            for item_idx in range(n):
                analyze_step = 2 + (item_idx * 2)
                confirm_step = 3 + (item_idx * 2)
                assert get_step_type(analyze_step, n) == ("ANALYZE", item_idx)
                assert get_step_type(confirm_step, n) == ("CONFIRM", item_idx)

    def test_item_indices_sequential(self):
        """Item indices are sequential from 0 to N-1."""
        for n in range(1, 10):
            seen_indices = set()
            for step in range(2, get_total_steps(n)):
                step_type, idx = get_step_type(step, n)
                if idx is not None:
                    seen_indices.add(idx)
            assert seen_indices == set(range(n)), f"Failed for n={n}"

    def test_no_gaps_in_steps(self):
        """All steps from 1 to total are valid (no gaps)."""
        for n in range(1, 10):
            total = get_total_steps(n)
            for step in range(1, total + 1):
                step_type, _ = get_step_type(step, n)
                assert step_type in ("CONTEXT", "ANALYZE", "CONFIRM", "SUMMARY")


# Minimal concrete VerifyBase: the guidance hook is the only abstract member needed to render confirm and summary steps.
class _StubVerify(VerifyBase):
    PHASE = "plan-code"

    def get_verification_guidance(self, item, state_dir):
        return ["check it"]


def _qr(tmp_path, items):
    (tmp_path / "qr-plan-code.json").write_text(
        json.dumps({"phase": "plan-code", "iteration": 1, "items": items}))


def _item(item_id, status, **extra):
    return {"id": item_id, "scope": "*", "check": "c", "status": status,
            "version": 1, **extra}


def _summary(tmp_path, ids):
    return _StubVerify()._step_summary(str(tmp_path), "m", ids, 2 + 2 * len(ids))


class TestVerdictBlock:
    def test_all_pass_is_sole_line(self, tmp_path):
        _qr(tmp_path, [_item("a", "PASS"), _item("b", "PASS")])
        assert render_verdict_block(json.loads((tmp_path / "qr-plan-code.json").read_text()),
                                    ["a", "b"]) == ["PASS"]
        actions = _summary(tmp_path, ["a", "b"])["actions"]
        assert "PASS" in actions

    def test_fail_lists_id_severity_finding(self, tmp_path):
        _qr(tmp_path, [_item("a", "FAIL", severity="MUST", finding="bad thing")])
        state = json.loads((tmp_path / "qr-plan-code.json").read_text())
        assert render_verdict_block(state, ["a"]) == ["FAIL", "a [MUST]: bad thing"]

    def test_missing_severity_renders_should(self, tmp_path):
        state = {"items": [_item("a", "FAIL", finding="x")]}
        assert render_verdict_block(state, ["a"])[1] == "a [SHOULD]: x"

    def test_multiline_finding_collapsed_and_truncated(self):
        state = {"items": [_item("a", "FAIL", finding="one\ntwo  three"),
                           _item("b", "FAIL", finding="x" * 400)]}
        lines = render_verdict_block(state, ["a", "b"])
        assert lines[1] == "a [SHOULD]: one two three"
        assert lines[2].endswith("...") and len(lines[2]) < 330

    def test_fail_outside_item_ids_absent(self):
        state = {"items": [_item("a", "PASS"), _item("z", "FAIL", finding="x")]}
        assert render_verdict_block(state, ["a"]) == ["PASS"]

    def test_todo_yields_unrecorded(self, tmp_path):
        _qr(tmp_path, [_item("a", "PASS"), _item("b", "TODO")])
        text = "\n".join(_summary(tmp_path, ["a", "b"])["actions"])
        assert "UNRECORDED" in text and "update-item b" in text

    def test_missing_qr_file_yields_error(self, tmp_path):
        actions = _summary(tmp_path, ["a"])["actions"]
        assert actions[0].startswith("ERROR")


class TestConfirmText:
    def test_confirm_has_downgrade_form_and_item_list(self, tmp_path):
        _qr(tmp_path, [_item("a", "TODO"), _item("b", "TODO")])
        step = _StubVerify()._step_confirm(str(tmp_path), "m", ["a", "b"], 1, 6)
        text = "\n".join(step["actions"])
        assert "update-item <earlier-id> --status FAIL" in text
        assert "a, b" in text
        assert "FAIL->PASS is rejected" in text


# Decompose/verify dispatch text and walkthrough ordering.
DISPATCH_PHASE = "plan-code"


def _flat(result):
    out = result.get("actions", [])
    return "\n".join(str(a) for a in out)


def _dispatch_qr_file(tmp_path, items):
    (tmp_path / f"qr-{DISPATCH_PHASE}.json").write_text(
        json.dumps({"phase": DISPATCH_PHASE, "iteration": 1, "items": items}))


def _dispatch_item(item_id, scope="file:a.py:1", **extra):
    return {"id": item_id, "scope": scope, "check": "c", "status": "TODO",
            "version": 1, "severity": "MUST", **extra}


def _verify(tmp_path):
    handler = steps.qr_verify_step("skills.planner.orchestrator.planner", "Verify", DISPATCH_PHASE)
    qr = QRState(iteration=1, state=LoopState.INITIAL)
    return handler({"state_dir": str(tmp_path), "step": 5, "qr": qr})


def _flags_in_order(text):
    return [t for t in text.replace("\n", " ").split() if t.startswith("qa-")]


def test_decompose_dispatch_names_total_and_output(tmp_path):
    handler = steps.qr_decompose_step(
        "skills.planner.orchestrator.planner", "Decompose", DISPATCH_PHASE, "decompose_plan_code")
    qr = QRState(iteration=1, state=LoopState.INITIAL)
    text = _flat(handler({"state_dir": str(tmp_path), "step": 4, "qr": qr}))
    assert str(DECOMPOSE_TOTAL_STEPS) in text
    assert f"qr-{DISPATCH_PHASE}.json" in text


def test_verify_orders_children_before_parent_and_umbrella(tmp_path):
    _dispatch_qr_file(tmp_path, [
        _dispatch_item("qa-001", scope="*", group_id="g"),
        _dispatch_item("qa-002", group_id="g"),
        _dispatch_item("qa-003", group_id="g", parent_id="qa-002"),
    ])
    text = _flat(_verify(tmp_path))
    assert "Items: qa-003,qa-002,qa-001" in text
    assert "Run all 8 steps" in text


@pytest.mark.parametrize("extra_first,extra_second,expected", [
    ({"parent_id": "elsewhere"}, {}, "Items: qa-001,qa-002"),
    ({}, {}, "Items: qa-002,qa-001"),
])
def test_file_order_kept_without_in_group_relations(tmp_path, extra_first, extra_second, expected):
    ids = ("qa-001", "qa-002") if "parent_id" in extra_first else ("qa-002", "qa-001")
    _dispatch_qr_file(tmp_path, [
        _dispatch_item(ids[0], group_id="g", **extra_first),
        _dispatch_item(ids[1], group_id="g", **extra_second),
    ])
    assert expected in _flat(_verify(tmp_path))


@given(st.permutations(["a", "b", "c", "d"]), st.sampled_from(["a", "b", "c", "d"]),
       st.sampled_from(["a", "b", "c", "d"]))
def test_walkthrough_order_contract(order, umbrella, parent):
    items = [{"id": i, "scope": "*" if i == umbrella else "file:x:1"} for i in order]
    if parent != umbrella:
        for it in items:
            if it["id"] != parent and it["id"] != umbrella:
                it["parent_id"] = parent
    result = [i["id"] for i in steps._walkthrough_order(items)]
    assert sorted(result) == sorted(order)
    assert result[-1] == umbrella
    non_umbrella = [i for i in result if i != umbrella]
    children = [i["id"] for i in items if i.get("parent_id") == parent]
    if children and parent != umbrella:
        assert non_umbrella.index(parent) > max(non_umbrella.index(c) for c in children)


def test_aggregate_tallies_first_line(tmp_path):
    _dispatch_qr_file(tmp_path, [_dispatch_item("qa-001", group_id="g")])
    assert "first line" in _flat(_verify(tmp_path)).lower()


def test_decompose_script_states_workflow(tmp_path):
    (tmp_path / "context.json").write_text("{}")
    prompts = {1: "p1", 2: "p2", 3: "p3", 5: "p5"}
    grouping = {"component_examples": "", "concern_examples": ""}
    text = _flat(decompose.dispatch_step(1, DISPATCH_PHASE, "m", prompts, grouping, str(tmp_path)))
    assert str(DECOMPOSE_TOTAL_STEPS) in text and str(DECOMPOSE_WRITE_STEP) in text


# Pins the constants to the real workflow: adding a decompose step without updating them fails here instead of misleading agents.
def test_decompose_step_titles_match_constants(tmp_path):
    _dispatch_qr_file(tmp_path, [_dispatch_item("qa-001")])
    prompts = {1: "p1", 2: "p2", 3: "p3", 4: "p4", 5: "p5", 6: "p6", 7: "p7"}
    grouping = {"component_examples": "", "concern_examples": ""}
    s = str(tmp_path)
    last = decompose.dispatch_step(DECOMPOSE_TOTAL_STEPS, DISPATCH_PHASE, "m", prompts, grouping, s)
    write = decompose.dispatch_step(DECOMPOSE_WRITE_STEP, DISPATCH_PHASE, "m", prompts, grouping, s)
    assert "Final Validation" in last["title"]
    assert "Finalize" in write["title"]


def test_orchestrators_import():
    import skills.planner.orchestrator.planner  # noqa: F401
    import skills.planner.orchestrator.executor  # noqa: F401


def test_decompose_and_verify_step1_tolerate_missing_context(tmp_path):
    _dispatch_qr_file(tmp_path, [_dispatch_item("qa-001")])
    prompts = {1: "p1"}
    grouping = {"component_examples": "", "concern_examples": ""}
    text = _flat(decompose.dispatch_step(1, DISPATCH_PHASE, "m", prompts, grouping, str(tmp_path)))
    assert "context.json: not found" in text
