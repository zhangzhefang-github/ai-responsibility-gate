"""
Phase E: Governance Demonstration

运行 3 个 PR 场景，证明：
1. Gate 是唯一的决策源（所有决策来自 core_decide）
2. 收敛点是策略层可配置的（通过 matrix 切换）
3. 即使 AI 在"自嗨"地互相挑刺，系统也不会失控

关键设计（完全不修改 src/core/* 或 src/evidence/*）：
- Demo 层根据 nit_only_streak 切换 matrix_path
- Round 1-2: matrix_path="matrices/pr_loop_demo.yaml" → ONLY_SUGGEST (默认)
- Round 3+: matrix_path="matrices/pr_loop_phase_e.yaml" → ALLOW
- 所有决策来自 core gate，demo 层不产生第二套 Decision 枚举
"""
import sys
from pathlib import Path
import asyncio
import random
import json

# 添加项目根目录到路径
ROOT_DIR = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT_DIR))

from examples.pr_gate_ai_review_loop.models import PRMeta
from examples.pr_gate_ai_review_loop.ai_reviewer_stub import generate_review_comments
from examples.pr_gate_ai_review_loop.ai_coding_stub import apply_fixes
from examples.pr_gate_ai_review_loop.signal_extractor import extract_signals, is_nit_only
from examples.pr_gate_ai_review_loop.signal_validation import normalize_signals
from examples.pr_gate_ai_review_loop.loop_state_validator import validate_loop_state, LoopStateValidationError

# 引入 core Gate 以使用 LoopState + Stage 5.5 hook
from src.core.models import DecisionRequest, GateContext
from src.core.gate import decide as core_decide
from src.evidence.risk import collect as collect_risk


# ============================================================================
# Configuration (可配置的收敛策略)
# ============================================================================

# 连续多少轮 benign 后才允许（可配置）
BENIGN_STREAK_THRESHOLD = 3

# 矩阵路径配置
MATRIX_PATH_DEFAULT = "matrices/pr_loop_demo.yaml"
MATRIX_PATH_CONVERGED = "matrices/pr_loop_phase_e.yaml"
MATRIX_PATH_CHURN = "matrices/pr_loop_churn.yaml"


# ============================================================================
# Print Functions (固定格式输出)
# ============================================================================

def print_decision(
    response,
    round_index: int,
    raw_signals,
    normalized_signals,
    risk_level: str,
    matrix_path: str,
):
    """
    打印治理三层：AI Raw Signals → Normalized Signals → Risk Level → Gate Decision

    固定免责声明：Risk explain-only；决策权唯一来源=core gate
    """
    print(f"\n{'='*60}")
    print(f"Round {round_index + 1}")
    print(f"{'='*60}")
    print(f"Matrix: {matrix_path}")
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


def log_round_state(
    scenario_name: str,
    round_index: int,
    signals: list,
    risk_level: str,
    benign_streak: int,
    matrix_path: str,
    decision: str,
    primary_reason: str,
):
    """
    输出结构化 JSON 日志，用于可审计性。

    设计原则：
    - Deterministic：相同输入 → 相同 JSON 输出（sorted keys）
    - 不改变决策来源，仅记录
    - 包含所有关键维度（signals, risk, convergence, policy, decision）
    """
    log_entry = {
        "scenario": scenario_name,
        "round_index": round_index,
        "signals": sorted(signals) if signals else [],
        "computed_risk": risk_level,
        "benign_streak": benign_streak,
        "chosen_matrix_path": matrix_path,
        "final_decision": decision,
        "primary_reason": primary_reason,
        "_invariants": {
            "risk_convergence_orthogonal": True,
            "decision_from_core_gate": True,
        },
    }

    # 输出单行 JSON（便于日志解析）
    print(f"[AUDIT] {json.dumps(log_entry, sort_keys=True)}")


def print_scenario_header(name: str, initial_pr_meta: PRMeta):
    """打印场景头部信息"""
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


# ============================================================================
# Demo Scenario Runner
# ============================================================================

async def run_scenario(name: str, initial_pr_meta: PRMeta, max_rounds: int = 5):
    """
    运行一个 PR 场景，模拟 review -> coding -> review 循环。

    关键设计（完全不修改 src/core/* 或 src/evidence/*）：
    - Demo 层根据 nit_only_streak 切换 matrix_path
    - Round 1-2: matrix_path="matrices/pr_loop_demo.yaml" → ONLY_SUGGEST
    - Round 3+: matrix_path="matrices/pr_loop_phase_e.yaml" → ALLOW
    - 所有决策来自 core gate，demo 层不产生第二套 Decision 枚举或"本地放行"
    """
    print_scenario_header(name, initial_pr_meta)

    pr_meta = initial_pr_meta
    nit_only_streak = 0

    # 为每个场景构造独立的可重复随机源（demo-level，确保行为可复现）
    scenario_seed = {
        "1) Benign: docs-only rename, 3+ rounds to ALLOW": 42,
        "2) Loop-churn: AI oscillates, stops at max_rounds": 43,
        "3) High-risk: touches build/auth, HITL in 2 rounds": 44,
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

        # Step 2: 提取 PR 层信号（原始 → 归一化）
        signals = extract_signals(comments)
        raw_signal_values = [s.value for s in signals]

        # 计算当前轮次是否为「benign round」（只有低价值 nits）
        is_benign_round = is_nit_only(comments)

        # 更新 nit_only_streak（连续 benign 轮次）
        if is_benign_round:
            nit_only_streak += 1
        else:
            nit_only_streak = 0

        normalized_signals = normalize_signals(raw_signal_values)

        # === 增强要求：根据 nit_only_streak 切换 matrix_path ===
        # 收敛策略通过 matrix 切换表达，不添加任何"策略信号"或 profile 切换
        if nit_only_streak >= BENIGN_STREAK_THRESHOLD:
            matrix_path = MATRIX_PATH_CONVERGED
        else:
            matrix_path = MATRIX_PATH_DEFAULT

        # Step 3: 构造 LoopState + 结构化信号
        loop_state = {
            "round_index": round_index,
            "nit_only_streak": nit_only_streak,
        }

        # 校验 loop_state 结构（examples 层校验，不修改 core）
        try:
            validate_loop_state(loop_state, max_rounds=max_rounds)
        except LoopStateValidationError as e:
            print(f"[ERROR] Invalid loop_state in scenario '{name}', round {round_index + 1}: {e}")
            # 为了 demo 连续性，修复后继续（生产环境可能需要不同处理）
            loop_state["round_index"] = max(0, min(loop_state.get("round_index", 0), max_rounds))
            loop_state["nit_only_streak"] = max(0, loop_state.get("nit_only_streak", 0))

        structured_input = {
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

        # Step 4: 调用 core Gate（唯一权威决策），传入 matrix_path
        core_req = DecisionRequest(
            text="pr_loop_guard_demo",
            structured_input=structured_input,
            context={"loop_state": loop_state},
        )

        try:
            response = await core_decide(core_req, matrix_path=matrix_path)
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
            matrix_path,
        )

        # 审计日志：记录本轮决策（deterministic, sorted keys）
        decision_val = response.decision.value
        primary_reason = getattr(response, "primary_reason", "")

        log_round_state(
            scenario_name=name,
            round_index=round_index,
            signals=normalized_signals,
            risk_level=risk_level,
            benign_streak=nit_only_streak,
            matrix_path=matrix_path,
            decision=decision_val,
            primary_reason=primary_reason,
        )

        # Step 5: 根据决策判断是否终止循环

        if decision_val == "ALLOW":
            print(f"✅ Gate Decision: ALLOW - Gate terminated the loop")
            print(f"   (Converged after {nit_only_streak} benign rounds, matrix: {matrix_path})")
            return response

        if decision_val == "DENY":
            print(f"❌ Gate Decision: DENY - Gate terminated the loop")
            return response

        if decision_val == "HITL":
            print(f"⚠️  Gate Decision: HITL - Gate terminated the loop")
            print(f"   (High-risk signals detected, human intervention required)")
            return response

        # Step 6: 如果决策是 ONLY_SUGGEST，让 AI Coding 应用修复并继续
        if decision_val == "ONLY_SUGGEST":
            print(f"[Round {round_index + 1}] AI Coding applying fixes...")
            pr_meta = apply_fixes(pr_meta, comments, rng=rng)
            # 继续下一轮

    # Max rounds reached: escalate via core gate using churn matrix
    print(f"\n⚠️  Max rounds ({max_rounds}) reached. Escalating via core gate...")

    # 构造最终请求
    loop_state_final = {
        "round_index": max_rounds,
        "nit_only_streak": nit_only_streak,
    }

    # 校验 loop_state 结构（examples 层校验，不修改 core）
    try:
        validate_loop_state(loop_state_final, max_rounds=max_rounds + 1)  # +1 因为 round_index 可以等于 max_rounds
    except LoopStateValidationError as e:
        print(f"[ERROR] Invalid loop_state_final in scenario '{name}' escalation: {e}")
        # 修复后继续
        loop_state_final["round_index"] = max(0, min(loop_state_final.get("round_index", 0), max_rounds))
        loop_state_final["nit_only_streak"] = max(0, loop_state_final.get("nit_only_streak", 0))

    structured_input_final = {
        "signals": normalized_signals,
    }

    core_req_final = DecisionRequest(
        text="pr_loop_guard_demo",
        structured_input=structured_input_final,
        context={"loop_state": loop_state_final},
    )

    try:
        response = await core_decide(core_req_final, matrix_path=MATRIX_PATH_CHURN)
    except Exception as e:
        print(f"[WARN] core_decide failed in scenario '{name}' escalation: {e}")
        class DummyResp:
            decision = type("D", (), {"value": "HITL"})()
            primary_reason = "CORE_ERROR"
            explanation = type("E", (), {"summary": f"core_decide error: {e}"})()
        response = DummyResp()

    print_decision(
        response,
        max_rounds - 1,
        raw_signal_values,
        normalized_signals,
        risk_level,
        MATRIX_PATH_CHURN,
    )

    # 审计日志：记录 churn escalation
    decision_val = response.decision.value
    primary_reason = getattr(response, "primary_reason", "")

    log_round_state(
        scenario_name=name,
        round_index=max_rounds,
        signals=normalized_signals,
        risk_level=risk_level,
        benign_streak=nit_only_streak,
        matrix_path=MATRIX_PATH_CHURN,
        decision=decision_val,
        primary_reason=primary_reason,
    )

    if decision_val == "HITL":
        print(f"⚠️  Gate escalated due to churn (max_rounds reached).")
    else:
        print(f"[WARN] Unexpected decision: {decision_val}")

    return response


# ============================================================================
# Main
# ============================================================================

async def main():
    """运行 3 个场景"""

    # Scenario 1: Benign - docs-only rename，需要 3+ 轮才 ALLOW
    scenario_1 = PRMeta(
        files_changed_count=1,
        loc_added=10,
        loc_deleted=5,
        touched_paths=["docs/README.md"],
        has_ci_green=True,
        contributor_trust_level="known",
        touches_sensitive_boundary=False
    )
    await run_scenario("1) Benign: docs-only rename, 3+ rounds to ALLOW", scenario_1)

    # Scenario 2: Loop-churn - AI 来回但无高风险信号，max_rounds 停止
    scenario_2 = PRMeta(
        files_changed_count=3,
        loc_added=80,
        loc_deleted=30,
        touched_paths=["src/utils/helper.py", "src/service/user.py"],
        has_ci_green=True,
        contributor_trust_level="known",
        touches_sensitive_boundary=False
    )
    await run_scenario("2) Loop-churn: AI oscillates, stops at max_rounds", scenario_2)

    # Scenario 3: High-risk - 触碰 build/auth 边界，≤2 轮内 HITL
    scenario_3 = PRMeta(
        files_changed_count=5,
        loc_added=200,
        loc_deleted=50,
        touched_paths=["src/auth/login.py", "build.gradle", "package.json"],
        has_ci_green=False,
        contributor_trust_level="new",
        touches_sensitive_boundary=True
    )
    await run_scenario("3) High-risk: touches build/auth, HITL in 2 rounds", scenario_3)

    print(f"\n{'#'*60}")
    print("# Phase E Demo Complete")
    print(f"{'#'*60}")
    print("\nKey Takeaways:")
    print("1. Gate is the ONLY decision authority - all decisions from core_decide")
    print("2. Convergence is policy-configurable via matrix path switching")
    print("3. NO modifications to src/core/* or src/evidence/* - all policy in examples/ layer")
    print("4. System remains stable even when AI oscillates - Gate controls termination")
    print()


if __name__ == "__main__":
    asyncio.run(main())
