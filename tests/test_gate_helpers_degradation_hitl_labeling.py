"""
Task 3.1: Degradation / HITL suggestion labels (explain-only, aggregate-level).

Based on _timeout_budget_exceeded (from Task 3.0):
- degradation_suggested: at least 1 provider exceeded budget
- hitl_suggested: at least 2 providers exceeded budget
"""
import os
from unittest.mock import patch, AsyncMock

import pytest

from src.core.models import GateContext, Evidence
from src.core import gate_helpers


def _make_ctx() -> GateContext:
    return GateContext(
        request_id="degradation-hitl-test",
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
async def test_flag_false_has_no_meta_labels():
    """flag=False: no _meta / no degradation / hitl labels."""
    gate_helpers._reset_circuit_breaker_registry_for_testing()
    key, old = _env_off()
    try:
        ctx = _make_ctx()
        trace = []
        result = await gate_helpers.collect_all_evidence(ctx, trace)
        assert "_meta" not in result
    finally:
        _restore(key, old)


@pytest.mark.asyncio
async def test_flag_true_single_timeout_degradation_only():
    """Single TIMEOUT → degradation suggested, but not HITL."""
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

        meta = result.get("_meta") or {}
        assert meta.get("_degradation_suggested") is True
        assert meta.get("_hitl_suggested") is False
    finally:
        _restore(key, old)
        gate_helpers._reset_circuit_breaker_registry_for_testing()


@pytest.mark.asyncio
async def test_flag_true_two_timeouts_trigger_hitl():
    """Two TIMEOUT providers → both degradation and HITL suggested."""
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
        ), patch(
            "src.core.gate_helpers.collect_routing",
            new_callable=AsyncMock,
            side_effect=never,
        ):
            ctx = _make_ctx()
            trace = []
            result = await gate_helpers.collect_all_evidence(ctx, trace)

        meta = result.get("_meta") or {}
        assert meta.get("_degradation_suggested") is True
        assert meta.get("_hitl_suggested") is True
    finally:
        _restore(key, old)
        gate_helpers._reset_circuit_breaker_registry_for_testing()


@pytest.mark.asyncio
async def test_flag_true_ok_and_skip_no_degradation_or_hitl():
    """OK + SKIP only → no degradation and no HITL suggested."""
    gate_helpers._reset_circuit_breaker_registry_for_testing()
    key, old = _env_on()
    try:
        # Make routing always skipped by opening its breaker.
        import time as _time

        now_ms = int(_time.time() * 1000)
        routing_breaker = gate_helpers.get_or_create_circuit_breaker_for_provider("routing")
        for _ in range(3):
            routing_breaker.record_timeout(now_ms)

        # Ensure tool returns OK.
        with patch(
            "src.core.gate_helpers.collect_tool",
            new_callable=AsyncMock,
            return_value=Evidence(provider="tool", available=True, data={"tool_id": "x"}),
        ):
            ctx = _make_ctx()
            trace = []
            result = await gate_helpers.collect_all_evidence(ctx, trace)

        meta = result.get("_meta") or {}
        assert meta.get("_degradation_suggested") is False
        assert meta.get("_hitl_suggested") is False
    finally:
        _restore(key, old)
        gate_helpers._reset_circuit_breaker_registry_for_testing()

