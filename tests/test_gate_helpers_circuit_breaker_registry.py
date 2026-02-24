"""
Minimal unit tests for Task 2.6: circuit breaker registry wiring in collect_all_evidence.

- flag=False: registry is never touched.
- flag=True: only creates breaker instances; evidence output shape unchanged.
"""
import os
import pytest

from src.core.models import GateContext
from src.core import gate_helpers


def _make_ctx() -> GateContext:
    return GateContext(
        request_id="cb-registry-test",
        session_id=None,
        user_id=None,
        text="test",
        debug=False,
        verbose=False,
        context={},
        structured_input=None,
    )


@pytest.mark.asyncio
async def test_flag_false_registry_not_accessed():
    """With feature flag False, collect_all_evidence must not touch the registry."""
    gate_helpers._reset_circuit_breaker_registry_for_testing()
    # Ensure flag is off (default or explicit)
    env_key = "AI_GATE_EVIDENCE_TIMEOUT_GUARD_ENABLED"
    old = os.environ.pop(env_key, None)
    try:
        ctx = _make_ctx()
        trace = []
        await gate_helpers.collect_all_evidence(ctx, trace)
        assert len(gate_helpers._circuit_breakers_by_provider) == 0
    finally:
        if old is not None:
            os.environ[env_key] = old


@pytest.mark.asyncio
async def test_flag_true_only_creates_instances_output_unchanged():
    """With feature flag True, only create breakers; evidence keys and shape unchanged."""
    gate_helpers._reset_circuit_breaker_registry_for_testing()
    env_key = "AI_GATE_EVIDENCE_TIMEOUT_GUARD_ENABLED"
    old = os.environ.get(env_key)
    os.environ[env_key] = "true"
    try:
        ctx = _make_ctx()
        trace = []
        result = await gate_helpers.collect_all_evidence(ctx, trace)
        keys = set(result.keys())
        assert {"tool", "routing", "knowledge", "risk", "permission"}.issubset(keys)
        assert len(gate_helpers._circuit_breakers_by_provider) == 5
        for key in ("tool", "routing", "knowledge", "risk", "permission"):
            ev = result[key]
            assert hasattr(ev, "provider")
            assert hasattr(ev, "available")
            assert hasattr(ev, "data")
    finally:
        if old is None:
            os.environ.pop(env_key, None)
        else:
            os.environ[env_key] = old
        gate_helpers._reset_circuit_breaker_registry_for_testing()
