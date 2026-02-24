"""
Task 4.2: Risk-tier-specific timeout guard overlays in gate.py.

We validate that:
- R0: hitl+degraded does NOT escalate (remains ALLOW).
- R1: hitl_suggested → HITL, but hitl+degraded does NOT DENY.
- R2: hitl+degraded → DENY (matches existing behavior).
- R3: degraded_only → HITL (tighten-only enhancement).
- Risk tier and policy selection are visible in verbose trace.
"""
import io
import os
from contextlib import contextmanager, redirect_stdout
from unittest.mock import patch

import pytest

from src.core import gate
from src.core.models import DecisionRequest, Decision


def _make_req(verbose: bool = False) -> DecisionRequest:
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


def _fake_evidence(meta):
    return {
        "tool": type("E", (), {"available": True, "data": {}})(),
        "routing": type("E", (), {"available": True, "data": {}})(),
        "knowledge": type("E", (), {"available": True, "data": {}})(),
        "risk": type(
            "E", (), {"available": True, "data": {"risk_level": "R1", "rules_hit": []}}
        )(),
        "permission": type(
            "E", (), {"available": True, "data": {"has_access": True}}
        )(),
        "_meta": meta,
    }


@pytest.mark.asyncio
async def test_r0_hitl_and_degraded_does_not_escalate():
    """
    R0: even when hitl+degraded, overlays should not escalate (remain ALLOW).
    """
    req = _make_req()
    meta = {
        "_hitl_suggested": True,
        "_degradation_suggested": True,
    }

    async def fake_collect_all_evidence(ctx, trace):
        return _fake_evidence(meta)

    with _with_env(
        {
            "AI_GATE_RISK_TIER": "R0",
            "AI_GATE_EVIDENCE_TIMEOUT_GUARD_ENABLED": "true",
            "AI_GATE_TIMEOUT_GUARD_HITL_OVERLAY_ENABLED": "true",
            "AI_GATE_TIMEOUT_GUARD_DENY_OVERLAY_ENABLED": "true",
        }
    ), _stub_gate_pipeline(decision_index=0), patch(
        "src.core.gate.collect_all_evidence", new=fake_collect_all_evidence
    ):
        resp = await gate.decide(req)
        assert resp.decision is Decision.ALLOW


@pytest.mark.asyncio
async def test_r1_hitl_suggested_to_hitl_but_no_deny():
    """
    R1: hitl_suggested should escalate to HITL, but hitl+degraded must not DENY.
    """
    req = _make_req()
    meta = {
        "_hitl_suggested": True,
        "_degradation_suggested": True,
    }

    async def fake_collect_all_evidence(ctx, trace):
        return _fake_evidence(meta)

    with _with_env(
        {
            "AI_GATE_RISK_TIER": "R1",
            "AI_GATE_EVIDENCE_TIMEOUT_GUARD_ENABLED": "true",
            "AI_GATE_TIMEOUT_GUARD_HITL_OVERLAY_ENABLED": "true",
            "AI_GATE_TIMEOUT_GUARD_DENY_OVERLAY_ENABLED": "true",
        }
    ), _stub_gate_pipeline(decision_index=0), patch(
        "src.core.gate.collect_all_evidence", new=fake_collect_all_evidence
    ):
        resp = await gate.decide(req)
        assert resp.decision is Decision.HITL


@pytest.mark.asyncio
async def test_r2_hitl_and_degraded_escalates_to_deny():
    """
    R2: hitl+degraded should escalate to DENY (preserving Task 3.3 behavior).
    """
    req = _make_req()
    meta = {
        "_hitl_suggested": True,
        "_degradation_suggested": True,
    }

    async def fake_collect_all_evidence(ctx, trace):
        return _fake_evidence(meta)

    with _with_env(
        {
            "AI_GATE_RISK_TIER": "R2",
            "AI_GATE_EVIDENCE_TIMEOUT_GUARD_ENABLED": "true",
            "AI_GATE_TIMEOUT_GUARD_HITL_OVERLAY_ENABLED": "true",
            "AI_GATE_TIMEOUT_GUARD_DENY_OVERLAY_ENABLED": "true",
        }
    ), _stub_gate_pipeline(decision_index=0), patch(
        "src.core.gate.collect_all_evidence", new=fake_collect_all_evidence
    ):
        resp = await gate.decide(req)
        assert resp.decision is Decision.DENY


@pytest.mark.asyncio
async def test_r3_degraded_only_escalates_to_hitl():
    """
    R3: degraded-only (no hitl_suggested) should tighten to HITL.
    """
    req = _make_req()
    meta = {
        "_hitl_suggested": False,
        "_degradation_suggested": True,
    }

    async def fake_collect_all_evidence(ctx, trace):
        return _fake_evidence(meta)

    with _with_env(
        {
            "AI_GATE_RISK_TIER": "R3",
            "AI_GATE_EVIDENCE_TIMEOUT_GUARD_ENABLED": "true",
            "AI_GATE_TIMEOUT_GUARD_HITL_OVERLAY_ENABLED": "true",
            "AI_GATE_TIMEOUT_GUARD_DENY_OVERLAY_ENABLED": "true",
        }
    ), _stub_gate_pipeline(decision_index=0), patch(
        "src.core.gate.collect_all_evidence", new=fake_collect_all_evidence
    ):
        resp = await gate.decide(req)
        assert resp.decision is Decision.HITL


@pytest.mark.asyncio
async def test_risk_tier_and_policy_visible_in_trace():
    """
    Risk tier source and timeout_guard_policy label should be visible in verbose trace.
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
            "AI_GATE_TIMEOUT_GUARD_POLICY_VERSION": "v2",
            "AI_GATE_EVIDENCE_TIMEOUT_GUARD_ENABLED": "true",
            "AI_GATE_TIMEOUT_GUARD_HITL_OVERLAY_ENABLED": "true",
            "AI_GATE_TIMEOUT_GUARD_DENY_OVERLAY_ENABLED": "true",
        }
    ), _stub_gate_pipeline(decision_index=0), patch(
        "src.core.gate.collect_all_evidence", new=fake_collect_all_evidence
    ), redirect_stdout(buf):
        resp = await gate.decide(req)

    assert isinstance(resp.decision, Decision)
    trace_output = buf.getvalue()
    assert "risk_tier=R2 (source=env)" in trace_output
    assert "timeout_guard_policy=v2 (risk_tier=R2)" in trace_output

