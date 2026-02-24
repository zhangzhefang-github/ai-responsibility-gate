"""
Task 3.0: Timeout budget labeling via Evidence.data["_timeout_budget_exceeded"].

- flag=False: no _timeout_budget_exceeded anywhere.
- flag=True: derive _timeout_budget_exceeded from _outcome (OK/TIMEOUT/ERROR).
"""
import os
from unittest.mock import patch, AsyncMock

import pytest

from src.core.models import GateContext, Evidence
from src.core import gate_helpers


def _make_ctx() -> GateContext:
    return GateContext(
        request_id="timeout-budget-test",
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


def _restore(key, old):
    if old is None:
        os.environ.pop(key, None)
    else:
        os.environ[key] = old


@pytest.mark.asyncio
async def test_flag_false_no_timeout_budget_labels():
    """flag=False: registry untouched; no _timeout_budget_exceeded labels."""
    gate_helpers._reset_circuit_breaker_registry_for_testing()
    key, old = _env_off()
    try:
        ctx = _make_ctx()
        trace = []
        result = await gate_helpers.collect_all_evidence(ctx, trace)
        assert len(gate_helpers._circuit_breakers_by_provider) == 0
        for ev in result.values():
            assert "_timeout_budget_exceeded" not in ev.data
    finally:
        _restore(key, old)


@pytest.mark.asyncio
async def test_flag_true_ok_budget_not_exceeded():
    """flag=True + OK outcome → _timeout_budget_exceeded is False."""
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
            result = await gate_helpers.collect_all_evidence(ctx, trace)
        tool_ev = result["tool"]
        assert tool_ev.data.get("_outcome") == "OK"
        assert tool_ev.data.get("_timeout_budget_exceeded") is False
    finally:
        _restore(key, old)
        gate_helpers._reset_circuit_breaker_registry_for_testing()


@pytest.mark.asyncio
async def test_flag_true_timeout_budget_exceeded():
    """flag=True + TIMEOUT outcome → _timeout_budget_exceeded is True."""
    gate_helpers._reset_circuit_breaker_registry_for_testing()
    key, old = _env_on()
    try:
        import asyncio

        async def never(_ctx):
            await asyncio.sleep(999)

        with patch(
            "src.core.gate_helpers.collect_tool",
            new_callable=AsyncMock,
            side_effect=never,
        ):
            ctx = _make_ctx()
            trace = []
            result = await gate_helpers.collect_all_evidence(ctx, trace)
        tool_ev = result["tool"]
        assert tool_ev.data.get("_outcome") == "TIMEOUT"
        assert tool_ev.data.get("_timeout_budget_exceeded") is True
    finally:
        _restore(key, old)
        gate_helpers._reset_circuit_breaker_registry_for_testing()


@pytest.mark.asyncio
async def test_flag_true_error_budget_exceeded():
    """flag=True + ERROR outcome → _timeout_budget_exceeded is True."""
    gate_helpers._reset_circuit_breaker_registry_for_testing()
    key, old = _env_on()
    try:
        with patch(
            "src.core.gate_helpers.collect_tool",
            new_callable=AsyncMock,
            side_effect=RuntimeError("fake error"),
        ):
            ctx = _make_ctx()
            trace = []
            result = await gate_helpers.collect_all_evidence(ctx, trace)
        tool_ev = result["tool"]
        assert tool_ev.data.get("_outcome") == "ERROR"
        assert tool_ev.data.get("_timeout_budget_exceeded") is True
    finally:
        _restore(key, old)
        gate_helpers._reset_circuit_breaker_registry_for_testing()


@pytest.mark.asyncio
async def test_flag_true_skip_has_no_timeout_budget_label():
    """flag=True + SKIP: skip keeps data empty (no budget label)."""
    gate_helpers._reset_circuit_breaker_registry_for_testing()
    key, old = _env_on()
    try:
        import time as _time

        now_ms = int(_time.time() * 1000)
        breaker = gate_helpers.get_or_create_circuit_breaker_for_provider("tool")
        for _ in range(3):
            breaker.record_timeout(now_ms)
        with patch("src.core.gate_helpers.collect_tool") as mock_collect:
            ctx = _make_ctx()
            trace = []
            result = await gate_helpers.collect_all_evidence(ctx, trace)
            mock_collect.assert_not_called()
        tool_ev = result["tool"]
        assert tool_ev.available is False
        assert tool_ev.data == {}
    finally:
        _restore(key, old)
        gate_helpers._reset_circuit_breaker_registry_for_testing()

