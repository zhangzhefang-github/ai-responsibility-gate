"""
Task 2.7: Circuit breaker call/skip wiring in collect_all_evidence.

- flag=False: registry not touched (stays empty).
- flag=True + should_call_provider=False: that provider's collect_* is not called.
- flag=True + should_call_provider=True: collect_* called once, return structure unchanged.
"""
import os
import time
from unittest.mock import patch, MagicMock, AsyncMock

import pytest

from src.core.models import GateContext, Evidence
from src.core import gate_helpers


def _make_ctx() -> GateContext:
    return GateContext(
        request_id="cb-call-skip-test",
        session_id=None,
        user_id=None,
        text="test",
        debug=False,
        verbose=False,
        context={},
        structured_input=None,
    )


@pytest.mark.asyncio
async def test_flag_false_registry_not_touched():
    """flag=False must not touch registry; it stays empty."""
    gate_helpers._reset_circuit_breaker_registry_for_testing()
    env_key = "AI_GATE_EVIDENCE_TIMEOUT_GUARD_ENABLED"
    old = os.environ.pop(env_key, None)
    try:
        ctx = _make_ctx()
        trace = []
        await gate_helpers.collect_all_evidence(ctx, trace)
        assert len(gate_helpers._circuit_breakers_by_provider) == 0
        result = await gate_helpers.collect_all_evidence(ctx, trace)
        keys = set(result.keys())
        assert {"tool", "routing", "knowledge", "risk", "permission"}.issubset(keys)
        for key in result:
            assert hasattr(result[key], "provider")
            assert hasattr(result[key], "available")
            assert hasattr(result[key], "data")
    finally:
        if old is not None:
            os.environ[env_key] = old


@pytest.mark.asyncio
async def test_flag_true_skip_does_not_call_provider():
    """When breaker says skip, that provider's collect is not called."""
    gate_helpers._reset_circuit_breaker_registry_for_testing()
    env_key = "AI_GATE_EVIDENCE_TIMEOUT_GUARD_ENABLED"
    old = os.environ.get(env_key)
    os.environ[env_key] = "true"
    try:
        now_ms = int(time.time() * 1000)
        breaker = gate_helpers.get_or_create_circuit_breaker_for_provider("tool")
        for _ in range(3):
            breaker.record_timeout(now_ms)
        assert breaker.state.value == "OPEN"

        with patch("src.core.gate_helpers.collect_tool", new_callable=MagicMock) as mock_collect:
            ctx = _make_ctx()
            trace = []
            result = await gate_helpers.collect_all_evidence(ctx, trace)
            mock_collect.assert_not_called()
            assert result["tool"].available is False
            assert result["tool"].provider == "tool"
            assert result["tool"].data == {}
    finally:
        if old is None:
            os.environ.pop(env_key, None)
        else:
            os.environ[env_key] = old
        gate_helpers._reset_circuit_breaker_registry_for_testing()


@pytest.mark.asyncio
async def test_flag_true_call_invokes_provider():
    """When breaker allows, collect_* is called once; return structure is 5 Evidence."""
    gate_helpers._reset_circuit_breaker_registry_for_testing()
    env_key = "AI_GATE_EVIDENCE_TIMEOUT_GUARD_ENABLED"
    old = os.environ.get(env_key)
    os.environ[env_key] = "true"
    try:
        with patch(
            "src.core.gate_helpers.collect_tool",
            new_callable=AsyncMock,
            return_value=Evidence(provider="tool", available=True, data={"tool_id": "x"}),
        ) as mock_collect:
            ctx = _make_ctx()
            trace = []
            result = await gate_helpers.collect_all_evidence(ctx, trace)
            mock_collect.assert_called_once()
            keys = set(result.keys())
            assert {"tool", "routing", "knowledge", "risk", "permission"}.issubset(keys)
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
