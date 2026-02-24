"""
Task 4.0: Configurable timeout guard overlays (HITL / DENY) in gate.py.

We validate that:
- Default config (all overlays enabled) matches Task 3.3 behavior.
- Disabling DENY overlay prevents HITL+degraded from escalating to DENY.
- Disabling HITL overlay also disables DENY overlay (no direct ALLOW → DENY).
- Disabling both overlays makes _meta have no effect on the decision.
"""
import os
from contextlib import contextmanager
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
async def test_default_config_behaves_like_task_3_3():
    """
    With default config (feature flag + both overlays enabled),
    HITL+degraded should escalate to DENY as in Task 3.3.
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
            # Global feature flag ON, overlays use their default=True behavior.
            "AI_GATE_EVIDENCE_TIMEOUT_GUARD_ENABLED": "true",
            "AI_GATE_TIMEOUT_GUARD_HITL_OVERLAY_ENABLED": None,
            "AI_GATE_TIMEOUT_GUARD_DENY_OVERLAY_ENABLED": None,
        }
    ), _stub_gate_pipeline(decision_index=0), patch(
        "src.core.gate.collect_all_evidence", new=fake_collect_all_evidence
    ):
        resp = await gate.decide(req)
        assert resp.decision is Decision.DENY


@pytest.mark.asyncio
async def test_disabling_deny_overlay_limits_to_hitl():
    """
    When DENY overlay is disabled but HITL overlay is enabled,
    HITL+degraded may only tighten to HITL, not DENY.
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
            "AI_GATE_EVIDENCE_TIMEOUT_GUARD_ENABLED": "true",
            "AI_GATE_TIMEOUT_GUARD_HITL_OVERLAY_ENABLED": "true",
            "AI_GATE_TIMEOUT_GUARD_DENY_OVERLAY_ENABLED": "false",
        }
    ), _stub_gate_pipeline(decision_index=0), patch(
        "src.core.gate.collect_all_evidence", new=fake_collect_all_evidence
    ):
        resp = await gate.decide(req)
        assert resp.decision is Decision.HITL


@pytest.mark.asyncio
async def test_disabling_hitl_overlay_prevents_deny_overlay():
    """
    When HITL overlay is disabled, DENY overlay must also effectively be disabled
    to avoid ALLOW → DENY without human-in-the-loop escalation.
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
            "AI_GATE_EVIDENCE_TIMEOUT_GUARD_ENABLED": "true",
            "AI_GATE_TIMEOUT_GUARD_HITL_OVERLAY_ENABLED": "false",
            "AI_GATE_TIMEOUT_GUARD_DENY_OVERLAY_ENABLED": "true",
        }
    ), _stub_gate_pipeline(decision_index=0), patch(
        "src.core.gate.collect_all_evidence", new=fake_collect_all_evidence
    ):
        resp = await gate.decide(req)
        assert resp.decision is Decision.ALLOW


@pytest.mark.asyncio
async def test_disabling_both_overlays_makes_meta_noop():
    """
    When both overlays are disabled, _meta should not affect the decision
    (behavior matches the baseline matrix decision).
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
            "AI_GATE_EVIDENCE_TIMEOUT_GUARD_ENABLED": "true",
            "AI_GATE_TIMEOUT_GUARD_HITL_OVERLAY_ENABLED": "false",
            "AI_GATE_TIMEOUT_GUARD_DENY_OVERLAY_ENABLED": "false",
        }
    ), _stub_gate_pipeline(decision_index=0), patch(
        "src.core.gate.collect_all_evidence", new=fake_collect_all_evidence
    ):
        resp = await gate.decide(req)
        assert resp.decision is Decision.ALLOW


@pytest.mark.asyncio
async def test_global_feature_flag_off_disables_all_timeout_overlays():
    """
    When the global evidence timeout guard feature flag is OFF,
    HITL/DENY overlays must not have any effect.
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
            "AI_GATE_EVIDENCE_TIMEOUT_GUARD_ENABLED": "false",
            "AI_GATE_TIMEOUT_GUARD_HITL_OVERLAY_ENABLED": "true",
            "AI_GATE_TIMEOUT_GUARD_DENY_OVERLAY_ENABLED": "true",
        }
    ), _stub_gate_pipeline(decision_index=0), patch(
        "src.core.gate.collect_all_evidence", new=fake_collect_all_evidence
    ):
        resp = await gate.decide(req)
        assert resp.decision is Decision.ALLOW

