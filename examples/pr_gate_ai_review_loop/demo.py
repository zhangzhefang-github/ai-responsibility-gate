"""
Phase A: Demo Runner

运行 3 个 PR 场景，模拟 review -> coding -> review 循环，展示：
- 没有 stop condition 时容易陷入低价值 nit 循环
- 利用 LoopState + stop condition 可以收敛

Phase C 之后的额外约束：
- 每一轮只有 **一个权威决策**，来自 core gate 的 Decision（ALLOW / ONLY_SUGGEST / HITL / DENY）
- 示例层（profile）负责：
  - 计算 LoopState（round_index, nit_only_streak）
  - 将 LoopState / PR 信号以 context/structured_input 形式传给 core
  - 根据 core 决策 + LoopState 决定是否继续循环（不生成第二套 Decision 枚举）
"""
import sys
from pathlib import Path
import asyncio
import random

# 添加项目根目录到路径
ROOT_DIR = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT_DIR))

from examples.pr_gate_ai_review_loop.models import PRMeta
from examples.pr_gate_ai_review_loop.ai_reviewer_stub import generate_review_comments
from examples.pr_gate_ai_review_loop.ai_coding_stub import apply_fixes
from examples.pr_gate_ai_review_loop.signal_extractor import extract_signals, is_nit_only
from examples.pr_gate_ai_review_loop.signal_validation import normalize_signals

# 引入 core Gate 以使用 LoopState + Stage 5.5 hook
from src.core.models import DecisionRequest, GateContext
from src.core.gate import decide as core_decide
from src.evidence.risk import collect as collect_risk


def print_decision(
    response,
    round_index: int,
    raw_signals,
    normalized_signals,
    risk_level: str,
):
    """打印治理三层：AI Raw Signals → Normalized Signals → Risk Level → Gate Decision"""
    print(f"\n{'='*60}")
    print(f"Round {round_index + 1}")
    print(f"{'='*60}")
    print(f"AI Raw Signals (extractor): {raw_signals}")
    print(f"AI Normalized Signals (allowlisted): {normalized_signals}")
    print(f"Risk Level (explain-only): {risk_level}")

    decision_val = getattr(getattr(response, "decision", None), "value", "UNKNOWN")
    primary_reason = getattr(response, "primary_reason", "")
    explanation = getattr(response, "explanation", None)
    summary = getattr(explanation, "summary", "") if explanation is not None else ""

    print(f"Gate Decision: {decision_val}")
    print(f"Primary Reason: {primary_reason}")
    print(f"Explanation Summary: {summary}")
    print("(Explain-only) Risk evidence computed for display; "
          "decision authority remains in the core gate.")
    print(f"{'='*60}\n")


async def run_scenario(name: str, initial_pr_meta: PRMeta, max_rounds: int = 5):
    """
    运行一个 PR 场景，模拟 review -> coding -> review 循环。
    """
    print(f"\n{'#'*60}")
    print(f"# Scenario: {name}")
    print(f"{'#'*60}")
    print(f"Initial PR Meta:")
    print(f"  - Files changed: {initial_pr_meta.files_changed_count}")
    print(f"  - LOC added: {initial_pr_meta.loc_added}")
    print(f"  - Touched paths: {initial_pr_meta.touched_paths}")
    print(f"  - Touches sensitive boundary: {initial_pr_meta.touches_sensitive_boundary}")
    print(f"  - Has CI green: {initial_pr_meta.has_ci_green}")
    print(f"  - Contributor trust level: {initial_pr_meta.contributor_trust_level}")
    
    pr_meta = initial_pr_meta
    nit_only_streak = 0

    # 为每个场景构造独立的可重复随机源（demo-level，确保行为可复现）
    # 注意：seed 选取在 README 中有说明，便于行为级回归测试。
    scenario_seed = {
        "A) Low Risk: docs/test-only PR": 42,
        "B) Medium Risk: small change, non-sensitive": 43,
        "C) High Risk: touching auth/build/CI/deps": 44,
    }.get(name, 0)
    rng = random.Random(scenario_seed)
    
    for round_index in range(max_rounds):
        # Step 1: AI Reviewer 生成评论
        comments = generate_review_comments(pr_meta, round_index, rng=rng)
        print(f"\n[Round {round_index + 1}] AI Reviewer generated {len(comments)} comments:")
        for i, comment in enumerate(comments[:5], 1):  # 只显示前 5 个
            print(f"  {i}. [{comment.category}] (severity={comment.severity}) {comment.text}")
        if len(comments) > 5:
            print(f"  ... and {len(comments) - 5} more comments")
        
        # Step 2: 提取 PR 层信号（原始 → 归一化，用于 profile / core / explain-only risk）
        signals = extract_signals(comments)
        raw_signal_values = [s.value for s in signals]
        normalized_signals = normalize_signals(raw_signal_values)

        # 计算当前轮次是否为「benign round」（只有低价值 nits）
        is_benign_round = is_nit_only(comments)

        # 预测下一轮的 nit_only_streak，用于传给 core（LoopState）
        projected_streak = nit_only_streak + 1 if is_benign_round else 0

        # Step 3: 构造 LoopState + 结构化信号，并调用 core Gate（唯一权威决策）
        loop_state = {
            "round_index": round_index,
            "nit_only_streak": projected_streak,
        }

        structured_input = {
            # Profile 名称仅在示例层使用，core 只看到一个字符串
            "profile": "pr_review_loop",
            # 通用信号，core 仅作为字符串处理，不知道 PR 概念
            "signals": normalized_signals,
        }

        # 为解释层单独计算一次 risk（Explain-only，不参与控制流）
        risk_ctx = GateContext(
            request_id=f"demo-risk-{name}-{round_index}",
            session_id=None,
            user_id=None,
            text="pr_loop_guard_demo",
            debug=False,
            verbose=False,
            context={},
            structured_input={"signals": normalized_signals},
        )
        risk_ev = await collect_risk(risk_ctx)
        risk_level = risk_ev.data.get("risk_level", "?")

        core_req = DecisionRequest(
            text="pr_loop_guard_demo",  # 与 risk_ctx.text 保持一致
            structured_input=structured_input,
            context={"loop_state": loop_state},
        )

        try:
            # 使用 profile → matrix 解析（Phase D），不再手动传 matrix_path
            response = await core_decide(core_req)
        except Exception as e:
            print(f"[WARN] core_decide failed in scenario '{name}', round {round_index + 1}: {e}")
            # 为了 demo 连续性，视为 ONLY_SUGGEST 再试一轮
            class DummyResp:
                decision = type("D", (), {"value": "ONLY_SUGGEST"})()
                primary_reason = "CORE_ERROR"
                explanation = type("E", (), {"summary": f"core_decide error: {e}"})()

            response = DummyResp()

        print_decision(
            response,
            round_index,
            raw_signal_values,
            normalized_signals,
            risk_level,
        )

        # Step 4: 如果决策是 ALLOW，结束循环（由 core Gate 决定收敛）
        if response.decision.value == "ALLOW":
            print(f"✅ PR Approved! Stopping after {round_index + 1} rounds.")
            return response

        # Step 5: 如果决策是 DENY，结束循环
        if response.decision.value == "DENY":
            print(f"❌ PR Denied! Stopping after {round_index + 1} rounds.")
            return response

        # Step 6: 如果决策是 HITL，结束循环（需要人工介入）
        if response.decision.value == "HITL":
            print(
                "System has taken over decision authority. "
                "AI loop terminated (HITL)."
            )
            return response

        # Step 7: 如果决策是 ONLY_SUGGEST，更新 streak 并让 AI Coding 应用修复
        nit_only_streak = projected_streak
        if response.decision.value == "ONLY_SUGGEST":
            print(f"[Round {round_index + 1}] AI Coding applying fixes...")
            pr_meta = apply_fixes(pr_meta, comments, rng=rng)
    
    print(f"⚠️  Max rounds ({max_rounds}) reached. PR still pending.")
    return None


async def main():
    """运行 3 个场景"""
    
    # Scenario A: 低风险 docs/test-only PR
    scenario_a = PRMeta(
        files_changed_count=2,
        loc_added=50,
        loc_deleted=10,
        touched_paths=["docs/README.md", "tests/test_example.py"],
        has_ci_green=True,
        contributor_trust_level="known",
        touches_sensitive_boundary=False
    )
    await run_scenario("A) Low Risk: docs/test-only PR", scenario_a)
    
    # Scenario B: 中风险 small change 但 touching non-sensitive
    scenario_b = PRMeta(
        files_changed_count=3,
        loc_added=100,
        loc_deleted=20,
        touched_paths=["src/utils/helper.py", "src/utils/validator.py"],
        has_ci_green=True,
        contributor_trust_level="known",
        touches_sensitive_boundary=False
    )
    await run_scenario("B) Medium Risk: small change, non-sensitive", scenario_b)
    
    # Scenario C: 高风险 touching auth/build/CI/deps
    scenario_c = PRMeta(
        files_changed_count=5,
        loc_added=200,
        loc_deleted=50,
        touched_paths=["src/auth/login.py", "build.gradle", "ci/config.yml", "package.json"],
        has_ci_green=False,
        contributor_trust_level="new",
        touches_sensitive_boundary=True
    )
    await run_scenario("C) High Risk: touching auth/build/CI/deps", scenario_c)
    
    print(f"\n{'#'*60}")
    print("# Demo Complete")
    print(f"{'#'*60}\n")


if __name__ == "__main__":
    asyncio.run(main())
