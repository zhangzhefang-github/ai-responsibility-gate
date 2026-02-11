import pytest

from src.core.models import GateContext
from src.evidence.risk import collect


@pytest.mark.asyncio
async def test_risk_structured_input_invalid_type_is_safe():
    """
    structured_input 非 dict 时，risk.collect 必须安全：
    - 不抛异常
    - 按默认逻辑处理（视为无 signals）
    """
    for invalid in (None, "not-a-dict", ["signals"], 123):
        ctx = GateContext(
            request_id=f"risk-structured-invalid-{type(invalid).__name__}",
            session_id=None,
            user_id=None,
            text="测试文本",  # 允许 keyword 规则正常工作
            debug=False,
            verbose=False,
            context={},
            structured_input=invalid,
        )

        ev = await collect(ctx)

        assert ev.provider == "risk"
        assert ev.available is True
        assert ev.data.get("risk_level") in {"R0", "R1", "R2", "R3"}

