import pytest
import asyncio

from src.core.models import GateContext
from src.evidence.risk import collect


@pytest.mark.asyncio
async def test_risk_collect_with_none_text_is_safe():
    """
    Ensure risk.collect does not crash when ctx.text is None, and that it
    still returns a valid Evidence object with a risk_level.
    """
    ctx = GateContext(
        request_id="test-none-text",
        session_id=None,
        user_id=None,
        text=None,  # Explicitly pass None to exercise the normalization path
        debug=False,
        verbose=False,
        context={},
        structured_input=None,
    )

    ev = await collect(ctx)

    assert ev.provider == "risk"
    assert ev.available is True
    # risk_level should be present and one of the configured levels
    assert ev.data.get("risk_level") in {"R0", "R1", "R2", "R3"}

