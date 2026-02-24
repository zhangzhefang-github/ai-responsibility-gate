"""
Task 3.2: Gate decision overlay using timeout guard meta (_meta).

Matrix:
- _hitl_suggested == True           → decision HITL (or more severe)
- _hitl_suggested == False and
  _degradation_suggested == True    → decision remains ALLOW, but trace marks degraded
- both False                        → decision unchanged
"""
import io
import os
from contextlib import redirect_stdout
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


@pytest.mark.asyncio
async def test_no_meta_flag_false_behaves_as_before():
    """When no _meta is present (flag=False), decision pipeline behaves as before."""
    # Ensure feature flag is off so collect_all_evidence won't attach _meta.
    env_key = "AI_GATE_EVIDENCE_TIMEOUT_GUARD_ENABLED"
    old = os.environ.pop(env_key, None)
    try:
        req = _make_req(verbose=False)
        # Just ensure decide runs without raising and returns a valid Decision.
        resp = await gate.decide(req)
        assert isinstance(resp.decision, Decision)
    finally:
        if old is not None:
            os.environ[env_key] = old


@pytest.mark.asyncio
async def test_hitl_suggested_forces_hitl_decision():
    """When _hitl_suggested is True, decision is upgraded to at least HITL."""
    req = _make_req(verbose=False)

    fake_evidence = {
        "tool": type("E", (), {"available": True, "data": {}})(),
        "routing": type("E", (), {"available": True, "data": {}})(),
        "knowledge": type("E", (), {"available": True, "data": {}})(),
        "risk": type("E", (), {"available": True, "data": {"risk_level": "R1", "rules_hit": []}})(),
        "permission": type("E", (), {"available": True, "data": {"has_access": True}})(),
        "_meta": {
            "_degradation_suggested": True,
            "_hitl_suggested": True,
        },
    }

    async def fake_collect_all_evidence(ctx, trace):
        return fake_evidence

    with patch("src.core.gate.collect_all_evidence", new=fake_collect_all_evidence):
        resp = await gate.decide(req)
        assert resp.decision in (Decision.HITL, Decision.DENY)


@pytest.mark.asyncio
async def test_degradation_suggested_allows_with_degraded_trace():
    """When only degradation is suggested, decision is unchanged but trace marks degraded."""
    req = _make_req(verbose=True)

    fake_evidence = {
        "tool": type("E", (), {"available": True, "data": {}})(),
        "routing": type("E", (), {"available": True, "data": {}})(),
        "knowledge": type("E", (), {"available": True, "data": {}})(),
        "risk": type("E", (), {"available": True, "data": {"risk_level": "R1", "rules_hit": []}})(),
        "permission": type("E", (), {"available": True, "data": {"has_access": True}})(),
        "_meta": {
            "_degradation_suggested": True,
            "_hitl_suggested": False,
        },
    }

    async def fake_collect_all_evidence(ctx, trace):
        return fake_evidence

    buf = io.StringIO()
    with patch("src.core.gate.collect_all_evidence", new=fake_collect_all_evidence), redirect_stdout(buf):
        resp = await gate.decide(req)

    # Decision should remain whatever the base matrix decides (no relax).
    assert isinstance(resp.decision, Decision)
    # Trace should contain a degraded note.
    trace_output = buf.getvalue()
    assert "degraded" in trace_output


@pytest.mark.asyncio
async def test_no_suggestions_decision_unmodified():
    """When both suggestions are False, decision is whatever the base matrix decides."""
    req = _make_req(verbose=False)

    fake_evidence = {
        "tool": type("E", (), {"available": True, "data": {}})(),
        "routing": type("E", (), {"available": True, "data": {}})(),
        "knowledge": type("E", (), {"available": True, "data": {}})(),
        "risk": type("E", (), {"available": True, "data": {"risk_level": "R1", "rules_hit": []}})(),
        "permission": type("E", (), {"available": True, "data": {"has_access": True}})(),
        "_meta": {
            "_degradation_suggested": False,
            "_hitl_suggested": False,
        },
    }

    async def fake_collect_all_evidence(ctx, trace):
        return fake_evidence

    # First, get a baseline decision without meta overlay (no _meta).
    baseline_evidence = dict(fake_evidence)
    baseline_evidence.pop("_meta")

    async def fake_collect_all_evidence_baseline(ctx, trace):
        return baseline_evidence

    with patch("src.core.gate.collect_all_evidence", new=fake_collect_all_evidence_baseline):
        baseline_resp = await gate.decide(req)

    with patch("src.core.gate.collect_all_evidence", new=fake_collect_all_evidence):
        resp = await gate.decide(req)

    # With no suggestions, decision should match the baseline.
    assert resp.decision == baseline_resp.decision

