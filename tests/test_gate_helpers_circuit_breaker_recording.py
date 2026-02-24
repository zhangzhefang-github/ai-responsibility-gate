"""
Task 2.8: Circuit breaker recording (record_success / record_timeout) after gather.

- flag=False: registry not touched.
- flag=True + call success: record_success called once.
- flag=True + call timeout: record_timeout called once.
- flag=True + skip: no record_* calls for skipped provider.
"""
import os
import time
from unittest.mock import patch, AsyncMock

import pytest

from src.core.models import GateContext, Evidence
from src.core import gate_helpers


def _make_ctx() -> GateContext:
    return GateContext(
        request_id="cb-recording-test",
        session_id=None,
        user_id=None,
        text="test",
        debug=False,
        verbose=False,
        context={},
        structured_input=None,
    )


def _env_off():
    key = "AI_GATE_EVIDENCE_TIMEOUT_GUARD_ENABLED"
    old = os.environ.pop(key, None)
    return key, old


def _env_on():
    key = "AI_GATE_EVIDENCE_TIMEOUT_GUARD_ENABLED"
    old = os.environ.get(key)
    os.environ[key] = "true"
    return key, old


def _restore_env(key, old):
    if old is None:
        os.environ.pop(key, None)
    else:
        os.environ[key] = old


@pytest.mark.asyncio
async def test_flag_false_registry_not_touched():
    """flag=False: do not touch registry; return structure unchanged."""
    gate_helpers._reset_circuit_breaker_registry_for_testing()
    key, old = _env_off()
    try:
        ctx = _make_ctx()
        trace = []
        await gate_helpers.collect_all_evidence(ctx, trace)
        assert len(gate_helpers._circuit_breakers_by_provider) == 0
        result = await gate_helpers.collect_all_evidence(ctx, trace)
        keys = set(result.keys())
        assert {"tool", "routing", "knowledge", "risk", "permission"}.issubset(keys)
        for k in ("tool", "routing", "knowledge", "risk", "permission"):
            ev = result[k]
            assert hasattr(ev, "provider") and hasattr(ev, "available") and hasattr(ev, "data")
    finally:
        _restore_env(key, old)


@pytest.mark.asyncio
async def test_flag_true_call_success_record_success_called():
    """flag=True + call returns available=True: record_success called once."""
    gate_helpers._reset_circuit_breaker_registry_for_testing()
    key, old = _env_on()
    try:
        with patch(
            "src.core.gate_helpers.collect_tool",
            new_callable=AsyncMock,
            return_value=Evidence(provider="tool", available=True, data={"tool_id": "x"}),
        ):
            ctx = _make_ctx()
            trace = []
            await gate_helpers.collect_all_evidence(ctx, trace)
            breaker = gate_helpers._circuit_breakers_by_provider["tool"]
            with patch.object(breaker, "record_success") as spy:
                await gate_helpers.collect_all_evidence(ctx, trace)
                spy.assert_called_once()
    finally:
        _restore_env(key, old)
        gate_helpers._reset_circuit_breaker_registry_for_testing()


@pytest.mark.asyncio
async def test_flag_true_call_timeout_record_timeout_called():
    """flag=True + call times out: record_timeout called once."""
    gate_helpers._reset_circuit_breaker_registry_for_testing()
    key, old = _env_on()
    try:
        async def never_return(_ctx):
            await asyncio.sleep(999)

        import asyncio

        with patch("src.core.gate_helpers.collect_tool", new_callable=AsyncMock, side_effect=never_return):
            ctx = _make_ctx()
            trace = []
            result = await gate_helpers.collect_all_evidence(ctx, trace)
            breaker = gate_helpers._circuit_breakers_by_provider["tool"]
            assert breaker.consecutive_timeouts >= 1
            keys = set(result.keys())
            assert {"tool", "routing", "knowledge", "risk", "permission"}.issubset(keys)
            assert result["tool"].available is False
    finally:
        _restore_env(key, old)
        gate_helpers._reset_circuit_breaker_registry_for_testing()


@pytest.mark.asyncio
async def test_flag_true_skip_no_recording():
    """flag=True + skip: no record_* for skipped provider."""
    gate_helpers._reset_circuit_breaker_registry_for_testing()
    key, old = _env_on()
    try:
        now_ms = int(time.time() * 1000)
        breaker = gate_helpers.get_or_create_circuit_breaker_for_provider("tool")
        for _ in range(3):
            breaker.record_timeout(now_ms)
        assert breaker.state.value == "OPEN"
        with patch("src.core.gate_helpers.collect_tool") as mock_collect:
            with patch.object(breaker, "record_success") as spy_success:
                with patch.object(breaker, "record_timeout") as spy_timeout:
                    ctx = _make_ctx()
                    trace = []
                    await gate_helpers.collect_all_evidence(ctx, trace)
                    mock_collect.assert_not_called()
                    spy_success.assert_not_called()
                    spy_timeout.assert_not_called()
    finally:
        _restore_env(key, old)
        gate_helpers._reset_circuit_breaker_registry_for_testing()
