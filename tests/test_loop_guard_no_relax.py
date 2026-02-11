import asyncio
from copy import deepcopy

from src.core.models import DecisionRequest
from src.core.gate import decide
import src.core.loop_guard as loop_guard


def test_loop_guard_cannot_relax_decision_index(capsys):
    """
    Verify that even if LoopGuard returns a \"more relaxed\" decision_index,
    gate.py ignores the relax and keeps the original decision.

    Strategy:
    - Call decide once to get baseline Decision.
    - Monkeypatch loop_guard.evaluate_loop_guard to always return index-1.
    - Call decide again with verbose=True.
    - Assert that the Decision is unchanged and trace contains
      \"LoopGuard: attempted relax ignored\".
    """
    req = DecisionRequest(
        text="我要退款，金额有点大，帮我直接退。",
        debug=False,
        verbose=False,
        context={"tool_id": "refund.create", "amount": 8000, "role": "normal_user"},
    )

    # Baseline decision
    base_resp = asyncio.run(decide(req))

    original_eval = loop_guard.evaluate_loop_guard

    def patched_evaluate(decision_index: int, loop_state, trace):
        # Attempt to relax by one step (towards ALLOW)
        return max(0, decision_index - 1)

    try:
        loop_guard.evaluate_loop_guard = patched_evaluate  # type: ignore[assignment]

        # Use a verbose request to capture trace
        req_verbose = deepcopy(req)
        req_verbose.verbose = True

        _ = asyncio.run(decide(req_verbose))
        captured = capsys.readouterr().out
    finally:
        loop_guard.evaluate_loop_guard = original_eval  # restore

    # After attempted relax, the effective Decision must remain the same
    patched_resp = asyncio.run(decide(req))
    assert patched_resp.decision == base_resp.decision

    # Trace should show that relax was attempted and ignored
    assert "LoopGuard: attempted relax ignored" in captured

import asyncio
from typing import Any, Dict

from src.core.models import DecisionRequest
from src.core import gate as gate_module


async def _call_decide() -> str:
    """Helper to call core gate once and return decision value."""
    req = DecisionRequest(
        text="普通查询",
        debug=False,
        verbose=True,
        context={},
        structured_input=None,
    )
    resp = await gate_module.decide(req)
    return resp.decision.value


def test_loop_guard_cannot_relax(monkeypatch, capsys):
    """
    验证：即使 LoopGuard 尝试返回更宽松的 decision_index，gate.call-site 也会拦截：
    - Decision 不会被放松（保持与正常路径一致）
    - verbose=True 时 trace 中包含 \"attempted relax ignored\"。
    """
    # baseline: 决策结果（未打补丁）
    baseline_decision = asyncio.run(_call_decide())

    def fake_evaluate_loop_guard(decision_index: int, loop_state: Any, trace: Any) -> int:
        # 恶意实现：总是尝试把 decision_index - 1（放松）
        return max(decision_index - 1, 0)

    # 打补丁到 gate 模块内部引用的 evaluate_loop_guard
    monkeypatch.setattr("src.core.gate.evaluate_loop_guard", fake_evaluate_loop_guard)

    # 再次调用 decide
    decision_after_patch = asyncio.run(_call_decide())

    # Decision 不应被放松，仍然与 baseline 一致
    assert decision_after_patch == baseline_decision

    # trace 中应出现 attempted relax ignored 提示
    captured = capsys.readouterr()
    assert "LoopGuard: attempted relax ignored" in captured.out

