"""
Task 3.3: Fail-closed DENY overlay using timeout guard meta (_meta).

Decision table (fail-closed, explain-only → gate overlay):
- _hitl_suggested == True  and _degradation_suggested == True   → DENY
- _hitl_suggested == True  and _degradation_suggested == False  → HITL
- _hitl_suggested == False and _degradation_suggested == True   → ALLOW (degraded trace)
- both False                                                    → ALLOW
"""
import io
import os
from contextlib import contextmanager, redirect_stdout
from unittest.mock import patch

import pytest

from src.core.models import DecisionRequest, Decision
from src.core import gate


def _make_req(verbose: bool = True) -> DecisionRequest:
    return DecisionRequest(
        session_id=None,
        user_id=None,
        text="test",
        debug=False,
        verbose=verbose,
        context={},
    )


@contextmanager
def _stub_gate_pipeline(decision_index: int = 0):
    """
    Stub matrix/loop/postcheck pipeline to keep a stable base decision_index.

    This isolates the timeout guard overlays so we can assert exact ALLOW/HITL/DENY
    outcomes without relying on matrix YAML contents.
    """

    class _Matrix:
        version = "test-matrix"
        data = {}

    def fake_load_matrix(_path):
        return _Matrix()

    def fake_lookup_matrix(
        matrix,
        final_resp_type,
        action_type,
        risk_level,
        risk_rules,
        permission_ok,
        trace,
    ):
        # Use STRICT_ORDER to map index → config_decision_str.
        decision_str = gate.STRICT_ORDER[decision_index]
        return {
            "config_decision_str": decision_str,
            "primary_reason": "TEST_BASE",
            "rules_fired": [],
        }

    def fake_apply_missing_evidence_policy(decision_idx, primary_reason, evidence, matrix, trace):
        return {"decision_index": decision_idx, "primary_reason": primary_reason}

    def fake_apply_conflict_resolution_and_overrides(
        decision_idx,
        primary_reason,
        matrix,
        classifier_result,
        final_resp_type,
        action_type,
        risk_level,
        permission_ok,
        routing_data,
        trace,
    ):
        return {"decision_index": decision_idx, "primary_reason": primary_reason}

    def fake_evaluate_loop_guard(decision_idx, loop_state, trace):
        return decision_idx

    class _PCResult:
        def __init__(self):
            self.passed = True
            self.issues = []

    def fake_postcheck(*_args, **_kwargs):
        return _PCResult()

    with patch("src.core.gate.load_matrix", new=fake_load_matrix), patch(
        "src.core.gate.lookup_matrix", new=fake_lookup_matrix
    ), patch(
        "src.core.gate.apply_missing_evidence_policy", new=fake_apply_missing_evidence_policy
    ), patch(
        "src.core.gate.apply_conflict_resolution_and_overrides",
        new=fake_apply_conflict_resolution_and_overrides,
    ), patch(
        "src.core.gate.evaluate_loop_guard", new=fake_evaluate_loop_guard
    ), patch(
        "src.core.gate.postcheck", new=fake_postcheck
    ):
        yield


@pytest.mark.asyncio
async def test_no_meta_flag_false_behaves_as_before_with_deny_overlay():
    """
    When no _meta is present (flag=False), decision pipeline behaves as before
    even with the DENY overlay in place.
    """
    env_key = "AI_GATE_EVIDENCE_TIMEOUT_GUARD_ENABLED"
    old = os.environ.pop(env_key, None)
    try:
        req = _make_req(verbose=False)
        resp = await gate.decide(req)
        assert isinstance(resp.decision, Decision)
    finally:
        if old is not None:
            os.environ[env_key] = old


@pytest.mark.asyncio
async def test_hitl_and_degradation_suggested_forces_deny_decision():
    """
    When both _hitl_suggested and _degradation_suggested are True,
    gate decision must be DENY (fail-closed).
    """
    req = _make_req(verbose=False)

    fake_evidence = {
        "tool": type("E", (), {"available": True, "data": {}})(),
        "routing": type("E", (), {"available": True, "data": {}})(),
        "knowledge": type("E", (), {"available": True, "data": {}})(),
        "risk": type(
            "E", (), {"available": True, "data": {"risk_level": "R1", "rules_hit": []}}
        )(),
        "permission": type(
            "E", (), {"available": True, "data": {"has_access": True}}
        )(),
        "_meta": {
            "_degradation_suggested": True,
            "_hitl_suggested": True,
        },
    }

    async def fake_collect_all_evidence(ctx, trace):
        return fake_evidence

    with _stub_gate_pipeline(decision_index=0), patch(
        "src.core.gate.collect_all_evidence", new=fake_collect_all_evidence
    ):
        resp = await gate.decide(req)
        assert resp.decision is Decision.DENY


@pytest.mark.asyncio
async def test_hitl_suggested_without_degradation_results_in_hitl():
    """
    When _hitl_suggested is True and _degradation_suggested is False,
    gate decision should be HITL (tighten-only overlay).
    """
    req = _make_req(verbose=False)

    fake_evidence = {
        "tool": type("E", (), {"available": True, "data": {}})(),
        "routing": type("E", (), {"available": True, "data": {}})(),
        "knowledge": type("E", (), {"available": True, "data": {}})(),
        "risk": type(
            "E", (), {"available": True, "data": {"risk_level": "R1", "rules_hit": []}}
        )(),
        "permission": type(
            "E", (), {"available": True, "data": {"has_access": True}}
        )(),
        "_meta": {
            "_degradation_suggested": False,
            "_hitl_suggested": True,
        },
    }

    async def fake_collect_all_evidence(ctx, trace):
        return fake_evidence

    with _stub_gate_pipeline(decision_index=0), patch(
        "src.core.gate.collect_all_evidence", new=fake_collect_all_evidence
    ):
        resp = await gate.decide(req)
        assert resp.decision is Decision.HITL


@pytest.mark.asyncio
async def test_degradation_suggested_without_hitl_results_in_allow_and_degraded_trace():
    """
    When only degradation is suggested, decision remains ALLOW but trace
    must contain degraded explanation.
    """
    req = _make_req(verbose=True)

    fake_evidence = {
        "tool": type("E", (), {"available": True, "data": {}})(),
        "routing": type("E", (), {"available": True, "data": {}})(),
        "knowledge": type("E", (), {"available": True, "data": {}})(),
        "risk": type(
            "E", (), {"available": True, "data": {"risk_level": "R1", "rules_hit": []}}
        )(),
        "permission": type(
            "E", (), {"available": True, "data": {"has_access": True}}
        )(),
        "_meta": {
            "_degradation_suggested": True,
            "_hitl_suggested": False,
        },
    }

    async def fake_collect_all_evidence(ctx, trace):
        return fake_evidence

    buf = io.StringIO()
    with _stub_gate_pipeline(decision_index=0), patch(
        "src.core.gate.collect_all_evidence", new=fake_collect_all_evidence
    ), redirect_stdout(buf):
        resp = await gate.decide(req)

    assert resp.decision is Decision.ALLOW
    trace_output = buf.getvalue()
    assert "degraded" in trace_output


@pytest.mark.asyncio
async def test_no_suggestions_results_in_allow_matching_baseline():
    """
    When both suggestions are False, decision should match the baseline ALLOW
    produced by the matrix (no overlay effect).
    """
    req = _make_req(verbose=False)

    fake_evidence = {
        "tool": type("E", (), {"available": True, "data": {}})(),
        "routing": type("E", (), {"available": True, "data": {}})(),
        "knowledge": type("E", (), {"available": True, "data": {}})(),
        "risk": type(
            "E", (), {"available": True, "data": {"risk_level": "R1", "rules_hit": []}}
        )(),
        "permission": type(
            "E", (), {"available": True, "data": {"has_access": True}}
        )(),
        "_meta": {
            "_degradation_suggested": False,
            "_hitl_suggested": False,
        },
    }

    async def fake_collect_all_evidence(ctx, trace):
        return fake_evidence

    with _stub_gate_pipeline(decision_index=0), patch(
        "src.core.gate.collect_all_evidence", new=fake_collect_all_evidence
    ):
        resp = await gate.decide(req)

    assert resp.decision is Decision.ALLOW

