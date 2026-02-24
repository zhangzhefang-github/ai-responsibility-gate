"""
Task 4.1: timeout_guard_policy_version tracing in gate.py.

We validate that:
- When AI_GATE_TIMEOUT_GUARD_POLICY_VERSION is set, verbose trace includes it.
- When unset, default version \"v1\" is used in trace.
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

    This isolates the timeout guard policy version tracing from matrix details.
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


def _fake_evidence_without_meta():
    """Minimal evidence payload without _meta; only to let gate.decide run."""
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
    }


@pytest.mark.asyncio
async def test_policy_version_trace_uses_env_value_when_set():
    """
    When AI_GATE_TIMEOUT_GUARD_POLICY_VERSION is set, trace should include it.
    """
    req = _make_req(verbose=True)

    async def fake_collect_all_evidence(ctx, trace):
        return _fake_evidence_without_meta()

    buf = io.StringIO()
    with _with_env({"AI_GATE_TIMEOUT_GUARD_POLICY_VERSION": "vX"}), _stub_gate_pipeline(
        decision_index=0
    ), patch(
        "src.core.gate.collect_all_evidence", new=fake_collect_all_evidence
    ), redirect_stdout(buf):
        resp = await gate.decide(req)

    assert isinstance(resp.decision, Decision)
    trace_output = buf.getvalue()
    assert "timeout_guard_policy_version=vX" in trace_output


@pytest.mark.asyncio
async def test_policy_version_trace_defaults_to_v1_when_unset():
    """
    When AI_GATE_TIMEOUT_GUARD_POLICY_VERSION is unset, trace should default to v1.
    """
    req = _make_req(verbose=True)

    async def fake_collect_all_evidence(ctx, trace):
        return _fake_evidence_without_meta()

    buf = io.StringIO()
    with _with_env({"AI_GATE_TIMEOUT_GUARD_POLICY_VERSION": None}), _stub_gate_pipeline(
        decision_index=0
    ), patch(
        "src.core.gate.collect_all_evidence", new=fake_collect_all_evidence
    ), redirect_stdout(buf):
        resp = await gate.decide(req)

    assert isinstance(resp.decision, Decision)
    trace_output = buf.getvalue()
    assert "timeout_guard_policy_version=v1" in trace_output

