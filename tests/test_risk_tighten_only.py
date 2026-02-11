import asyncio

from src.core.models import GateContext
from src.evidence.risk import collect as collect_risk


def _risk_level_rank(level: str) -> int:
    order = {"R0": 0, "R1": 1, "R2": 2, "R3": 3}
    return order.get(level, -1)


def test_risk_tighten_only_monotonic_with_signals():
    """
    Verify that risk.collect only tightens (never relaxes) when evidence/signals increase.
    Sequence:
    - base: no signals        → R0
    - low:  LOW_VALUE_NITS    → R0 (benign, stays lowest)
    - bug:  BUG_RISK          → >= R2
    - high: BUILD_CHAIN       → >= R3
    """
    base_ctx = GateContext(
        request_id="risk-base",
        session_id=None,
        user_id=None,
        text=None,
        debug=False,
        verbose=False,
        context={},
        structured_input=None,
    )

    low_ctx = base_ctx.model_copy()
    low_ctx.structured_input = {"signals": ["LOW_VALUE_NITS"]}

    bug_ctx = base_ctx.model_copy()
    bug_ctx.structured_input = {"signals": ["BUG_RISK"]}

    high_ctx = base_ctx.model_copy()
    high_ctx.structured_input = {"signals": ["BUILD_CHAIN"]}

    base_ev = asyncio.run(collect_risk(base_ctx))
    low_ev = asyncio.run(collect_risk(low_ctx))
    bug_ev = asyncio.run(collect_risk(bug_ctx))
    high_ev = asyncio.run(collect_risk(high_ctx))

    base_level = base_ev.data["risk_level"]
    low_level = low_ev.data["risk_level"]
    bug_level = bug_ev.data["risk_level"]
    high_level = high_ev.data["risk_level"]

    # Monotonic (tighten-only) ordering by rank
    assert _risk_level_rank(base_level) <= _risk_level_rank(low_level)
    assert _risk_level_rank(low_level) <= _risk_level_rank(bug_level)
    assert _risk_level_rank(bug_level) <= _risk_level_rank(high_level)


def test_risk_tighten_only_idempotent_for_same_ctx():
    """
    For the same context, multiple calls to risk.collect return the same level
    (no hidden state, and thus no implicit relax across calls).
    """
    ctx = GateContext(
        request_id="risk-idempotent",
        session_id=None,
        user_id=None,
        text=None,
        debug=False,
        verbose=False,
        context={},
        structured_input={"signals": ["BUG_RISK"]},
    )

    ev1 = asyncio.run(collect_risk(ctx))
    ev2 = asyncio.run(collect_risk(ctx))

    assert ev1.data["risk_level"] == ev2.data["risk_level"]

import asyncio

from src.core.models import GateContext
from src.evidence.risk import collect


def _make_ctx(text: str) -> GateContext:
    return GateContext(
        request_id="risk-tighten-test",
        session_id=None,
        user_id=None,
        text=text,
        debug=False,
        verbose=False,
        context={},
        structured_input=None,
    )


def test_risk_tighten_only_same_ctx_multiple_calls():
    """
    同一 ctx，多次调用 risk.collect，risk_level 不应“波动”或下降。

    这里使用包含高风险关键词的文本，预期 risk_level 始终为 R3。
    """
    ctx = _make_ctx("这是一个保证收益的理财产品")

    ev1 = asyncio.run(collect(ctx))
    ev2 = asyncio.run(collect(ctx))

    level1 = ev1.data.get("risk_level")
    level2 = ev2.data.get("risk_level")

    assert level1 == "R3"
    assert level2 == "R3"


def test_risk_tighten_only_signals_never_downgrade():
    """
    检查 structured_input.signals 只会“上调”风险，不会把已有较高风险降级。

    - 第一种 ctx：包含 SECURITY_BOUNDARY → 至少 R3
    - 第二种 ctx：仅 LOW_VALUE_NITS → 至多 R0
    """
    # 高风险信号
    ctx_high = GateContext(
        request_id="risk-signals-high",
        session_id=None,
        user_id=None,
        text="随便什么文本",
        debug=False,
        verbose=False,
        context={},
        structured_input={"signals": ["SECURITY_BOUNDARY"]},
    )
    ev_high = asyncio.run(collect(ctx_high))
    level_high = ev_high.data.get("risk_level")
    assert level_high == "R3"

    # 低风险信号
    ctx_low = GateContext(
        request_id="risk-signals-low",
        session_id=None,
        user_id=None,
        text="随便什么文本",
        debug=False,
        verbose=False,
        context={},
        structured_input={"signals": ["LOW_VALUE_NITS"]},
    )
    ev_low = asyncio.run(collect(ctx_low))
    level_low = ev_low.data.get("risk_level")
    assert level_low in {"R0", "R1"}  # 只能保持低风险，不可能从高风险降回低

