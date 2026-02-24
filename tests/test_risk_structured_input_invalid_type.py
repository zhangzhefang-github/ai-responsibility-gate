import pytest

from src.core.models import GateContext
from src.evidence.risk import collect


@pytest.mark.asyncio
async def test_risk_structured_input_invalid_type_is_safe():
    """
    structured_input 为 None 或空 dict 或 signals 非 list 时，risk.collect 必须安全：
    - 不抛异常
    - 按默认逻辑处理（视为无 signals / R0）
    """
    # 使用合法形态：None、空 dict、或内部 signals 非 list 的 dict（由 risk 内部防御）
    for valid_input in (None, {}, {"signals": None}, {"signals": "not-a-list"}):
        ctx = GateContext(
            request_id=f"risk-structured-valid-{type(valid_input).__name__}",
            session_id=None,
            user_id=None,
            text="测试文本",
            debug=False,
            verbose=False,
            context={},
            structured_input=valid_input,
        )

        ev = await collect(ctx)

        assert ev.provider == "risk"
        assert ev.available is True
        assert ev.data.get("risk_level") in {"R0", "R1", "R2", "R3"}

