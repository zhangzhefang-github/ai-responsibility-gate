"""
Task 2.9: Evidence outcome labeling (_outcome in data: OK / TIMEOUT / ERROR).

- flag=False: no registry touch, no _outcome (regression).
- flag=True: OK / TIMEOUT / ERROR labeled via data["_outcome"]; skip stays data={}.
"""
import os
import time
from unittest.mock import patch, AsyncMock

import pytest

from src.core.models import GateContext, Evidence
from src.core import gate_helpers


def _make_ctx():
    return GateContext(
        request_id="outcome-label-test",
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
async def test_flag_false_registry_not_touched_no_outcome():
    """flag=False: registry not touched; no _outcome in evidence data."""
    gate_helpers._reset_circuit_breaker_registry_for_testing()
    key, old = _env_off()
    try:
        ctx = _make_ctx()
        trace = []
        result = await gate_helpers.collect_all_evidence(ctx, trace)
        assert len(gate_helpers._circuit_breakers_by_provider) == 0
        for k in result:
            assert "_outcome" not in result[k].data
    finally:
        _restore(key, old)


@pytest.mark.asyncio
async def test_flag_true_ok_outcome():
    """flag=True + collect returns available=True → data['_outcome']='OK'."""
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
        assert result["tool"].data.get("_outcome") == "OK"
        assert result["tool"].available is True
    finally:
        _restore(key, old)
        gate_helpers._reset_circuit_breaker_registry_for_testing()


@pytest.mark.asyncio
async def test_flag_true_timeout_outcome():
    """flag=True + collect times out → data['_outcome']='TIMEOUT'."""
    gate_helpers._reset_circuit_breaker_registry_for_testing()
    key, old = _env_on()
    try:
        import asyncio

        async def never(_ctx):
            await asyncio.sleep(999)

        with patch("src.core.gate_helpers.collect_tool", new_callable=AsyncMock, side_effect=never):
            ctx = _make_ctx()
            trace = []
            result = await gate_helpers.collect_all_evidence(ctx, trace)
        assert result["tool"].data.get("_outcome") == "TIMEOUT"
        assert result["tool"].available is False
    finally:
        _restore(key, old)
        gate_helpers._reset_circuit_breaker_registry_for_testing()


@pytest.mark.asyncio
async def test_flag_true_error_outcome():
    """flag=True + collect raises → data['_outcome']='ERROR'."""
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
        assert result["tool"].data.get("_outcome") == "ERROR"
        assert result["tool"].available is False
    finally:
        _restore(key, old)
        gate_helpers._reset_circuit_breaker_registry_for_testing()


@pytest.mark.asyncio
async def test_flag_true_skip_no_outcome():
    """flag=True + skip: collect not called; data remains empty (no _outcome)."""
    gate_helpers._reset_circuit_breaker_registry_for_testing()
    key, old = _env_on()
    try:
        now_ms = int(time.time() * 1000)
        breaker = gate_helpers.get_or_create_circuit_breaker_for_provider("tool")
        for _ in range(3):
            breaker.record_timeout(now_ms)
        with patch("src.core.gate_helpers.collect_tool") as mock_collect:
            ctx = _make_ctx()
            trace = []
            result = await gate_helpers.collect_all_evidence(ctx, trace)
            mock_collect.assert_not_called()
        assert result["tool"].available is False
        assert result["tool"].data == {}
    finally:
        _restore(key, old)
        gate_helpers._reset_circuit_breaker_registry_for_testing()
