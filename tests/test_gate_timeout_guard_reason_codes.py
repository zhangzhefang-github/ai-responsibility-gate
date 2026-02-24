"""
Task 4.3: Structured timeout guard reason codes in gate.py.

We validate that:
- R1 + hitl_suggested → decision HITL and reason=HITL_SUGGESTED.
- R3 + degraded_only → decision HITL and reason=DEGRADED_ONLY.
- R2 + hitl+degraded → decision DENY and reason=HITL_AND_DEGRADED.
- No meta / overlays not triggered → decision ALLOW and no timeout_guard_reason line.
"""
import io
import os
from contextlib import contextmanager, redirect_stdout
from unittest.mock import patch

import pytest

from src.core import gate
from src.core.models import DecisionRequest, Decision


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
def _with_env(overrides):
    """
    Temporarily set environment variables for the duration of the context.

    Value None means "unset".
    """
    old_values = {}
    sentinel = object()
    try:
        for key, value in overrides.items():
            old_values[key] = os.environ.get(key, sentinel)
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        yield
    finally:
        for key, old in old_values.items():
            if old is sentinel:
                os.environ.pop(key, None)
            else:
                os.environ[key] = old


@contextmanager
def _stub_gate_pipeline(decision_index: int = 0):
    """
    Stub matrix/loop/postcheck pipeline to keep a stable base decision_index.

    This isolates the timeout guard overlays so we can assert exact
    ALLOW/HITL/DENY outcomes without relying on matrix YAML contents.
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


def _fake_evidence(meta=None):
    base = {
        "tool": type("E", (), {"available": True, "data": {}})(),
        "routing": type("E", (), {"available": True, "data": {}})(),
        "knowledge": type("E", (), {"available": True, "data": {}})(),
        "risk": type(
            "E", (), {"available": True, "data": {"risk_level": "R1", "rules_hit": []}}
        )(),
        "permission": type(
            "E", (), {"available": True, "data": {"has_access": True}}
        )(),
    }
    if meta is not None:
        base["_meta"] = meta
    return base


@pytest.mark.asyncio
async def test_r1_hitl_suggested_reason_is_hitl_suggested():
    """
    R1 + hitl_suggested should escalate to HITL with HITL_SUGGESTED reason.
    """
    req = _make_req(verbose=True)
    meta = {
        "_hitl_suggested": True,
        "_degradation_suggested": False,
    }

    async def fake_collect_all_evidence(ctx, trace):
        return _fake_evidence(meta)

    buf = io.StringIO()
    with _with_env(
        {
            "AI_GATE_RISK_TIER": "R1",
            "AI_GATE_EVIDENCE_TIMEOUT_GUARD_ENABLED": "true",
            "AI_GATE_TIMEOUT_GUARD_HITL_OVERLAY_ENABLED": "true",
            "AI_GATE_TIMEOUT_GUARD_DENY_OVERLAY_ENABLED": "true",
        }
    ), _stub_gate_pipeline(decision_index=0), patch(
        "src.core.gate.collect_all_evidence", new=fake_collect_all_evidence
    ), redirect_stdout(buf):
        resp = await gate.decide(req)

    assert resp.decision is Decision.HITL
    trace_output = buf.getvalue()
    assert "timeout_guard_reason=HITL_SUGGESTED" in trace_output


@pytest.mark.asyncio
async def test_r3_degraded_only_reason_is_degraded_only():
    """
    R3 + degraded_only (no hitl_suggested) should escalate to HITL with DEGRADED_ONLY reason.
    """
    req = _make_req(verbose=True)
    meta = {
        "_hitl_suggested": False,
        "_degradation_suggested": True,
    }

    async def fake_collect_all_evidence(ctx, trace):
        return _fake_evidence(meta)

    buf = io.StringIO()
    with _with_env(
        {
            "AI_GATE_RISK_TIER": "R3",
            "AI_GATE_EVIDENCE_TIMEOUT_GUARD_ENABLED": "true",
            "AI_GATE_TIMEOUT_GUARD_HITL_OVERLAY_ENABLED": "true",
            "AI_GATE_TIMEOUT_GUARD_DENY_OVERLAY_ENABLED": "true",
        }
    ), _stub_gate_pipeline(decision_index=0), patch(
        "src.core.gate.collect_all_evidence", new=fake_collect_all_evidence
    ), redirect_stdout(buf):
        resp = await gate.decide(req)

    assert resp.decision is Decision.HITL
    trace_output = buf.getvalue()
    assert "timeout_guard_reason=DEGRADED_ONLY" in trace_output


@pytest.mark.asyncio
async def test_r2_hitl_and_degraded_reason_is_hitl_and_degraded():
    """
    R2 + hitl+degraded should escalate to DENY with HITL_AND_DEGRADED reason.
    """
    req = _make_req(verbose=True)
    meta = {
        "_hitl_suggested": True,
        "_degradation_suggested": True,
    }

    async def fake_collect_all_evidence(ctx, trace):
        return _fake_evidence(meta)

    buf = io.StringIO()
    with _with_env(
        {
            "AI_GATE_RISK_TIER": "R2",
            "AI_GATE_EVIDENCE_TIMEOUT_GUARD_ENABLED": "true",
            "AI_GATE_TIMEOUT_GUARD_HITL_OVERLAY_ENABLED": "true",
            "AI_GATE_TIMEOUT_GUARD_DENY_OVERLAY_ENABLED": "true",
        }
    ), _stub_gate_pipeline(decision_index=0), patch(
        "src.core.gate.collect_all_evidence", new=fake_collect_all_evidence
    ), redirect_stdout(buf):
        resp = await gate.decide(req)

    assert resp.decision is Decision.DENY
    trace_output = buf.getvalue()
    assert "timeout_guard_reason=HITL_AND_DEGRADED" in trace_output


@pytest.mark.asyncio
async def test_no_meta_no_timeout_guard_reason_in_trace():
    """
    When there is no _meta and overlays are not triggered,
    decision should remain ALLOW and no timeout_guard_reason line should appear.
    """
    req = _make_req(verbose=True)

    async def fake_collect_all_evidence(ctx, trace):
        return _fake_evidence(meta=None)

    buf = io.StringIO()
    with _with_env(
        {
            "AI_GATE_RISK_TIER": "R2",
            "AI_GATE_EVIDENCE_TIMEOUT_GUARD_ENABLED": "true",
            "AI_GATE_TIMEOUT_GUARD_HITL_OVERLAY_ENABLED": "true",
            "AI_GATE_TIMEOUT_GUARD_DENY_OVERLAY_ENABLED": "true",
        }
    ), _stub_gate_pipeline(decision_index=0), patch(
        "src.core.gate.collect_all_evidence", new=fake_collect_all_evidence
    ), redirect_stdout(buf):
        resp = await gate.decide(req)

    assert resp.decision is Decision.ALLOW
    trace_output = buf.getvalue()
    assert "timeout_guard_reason=" not in trace_output

