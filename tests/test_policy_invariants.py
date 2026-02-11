"""
Policy Invariant Tests (repo-agnostic)

这些测试验证所有矩阵文件的安全不变量：
- R3 在任何矩阵下必须返回 HITL（绝不 ALLOW）
- R2 默认保守（除非矩阵显式配置 ALLOW）
- tighten-only 原则不被破坏

关键设计：不依赖仓库具体代码，仅通过 core_decide API 测试矩阵逻辑。
"""
import pytest
import asyncio
from pathlib import Path


# ============================================================================
# Test Utilities
# ============================================================================

async def decide_with_matrix(
    signals: list,
    matrix_path: str,
):
    """
    调用 core_decide 的辅助函数（repo-agnostic）。

    Args:
        signals: 归一化后的信号列表（如 ["SECURITY_BOUNDARY", "BUG_RISK"]）
        matrix_path: 矩阵文件路径

    Returns:
        DecisionResponse 对象
    """
    from src.core.models import DecisionRequest
    from src.core.gate import decide as core_decide

    req = DecisionRequest(
        text="policy_invariant_test",
        structured_input={"signals": signals},
        context={"loop_state": {"round_index": 0, "nit_only_streak": 0}},
    )

    return await core_decide(req, matrix_path=matrix_path)


# ============================================================================
# Invariant: R3 Never Allows
# ============================================================================

@pytest.mark.asyncio
async def test_r3_never_allows_in_demo_matrix():
    """
    验证：R3 风险在 pr_loop_demo.yaml 中永不返回 ALLOW。
    """
    # R3 信号：SECURITY_BOUNDARY 或 BUILD_CHAIN
    r3_signals = ["SECURITY_BOUNDARY"]

    response = await decide_with_matrix(
        signals=r3_signals,
        matrix_path="matrices/pr_loop_demo.yaml",
    )

    decision_val = response.decision.value
    assert decision_val != "ALLOW", \
        f"R3 risk should NEVER return ALLOW in demo matrix, got {decision_val}"
    assert decision_val in ("HITL", "DENY", "ONLY_SUGGEST"), \
        f"R3 risk should return conservative decision, got {decision_val}"


@pytest.mark.asyncio
async def test_r3_never_allows_in_converged_matrix():
    """
    验证：R3 风险在 pr_loop_phase_e.yaml 中永不返回 ALLOW。
    即使是收敛状态矩阵，高风险仍需人工审查。
    """
    r3_signals = ["BUILD_CHAIN"]

    response = await decide_with_matrix(
        signals=r3_signals,
        matrix_path="matrices/pr_loop_phase_e.yaml",
    )

    decision_val = response.decision.value
    assert decision_val != "ALLOW", \
        f"R3 risk should NEVER return ALLOW even in converged matrix, got {decision_val}"


@pytest.mark.asyncio
async def test_r3_never_allows_in_churn_matrix():
    """
    验证：R3 风险在 pr_loop_churn.yaml 中永不返回 ALLOW。
    """
    r3_signals = ["SECURITY_BOUNDARY", "BUILD_CHAIN"]

    response = await decide_with_matrix(
        signals=r3_signals,
        matrix_path="matrices/pr_loop_churn.yaml",
    )

    decision_val = response.decision.value
    assert decision_val != "ALLOW", \
        f"R3 risk should NEVER return ALLOW in churn matrix, got {decision_val}"


# ============================================================================
# Invariant: R2 Default Conservative
# ============================================================================

@pytest.mark.asyncio
async def test_r2_default_conservative_in_demo_matrix():
    """
    验证：R2 风险在默认矩阵中返回保守决策（不自动 ALLOW）。
    """
    # R2 信号：BUG_RISK
    r2_signals = ["BUG_RISK"]

    response = await decide_with_matrix(
        signals=r2_signals,
        matrix_path="matrices/pr_loop_demo.yaml",
    )

    decision_val = response.decision.value
    assert decision_val != "ALLOW", \
        f"R2 risk should NOT auto-allow in demo matrix, got {decision_val}"


@pytest.mark.asyncio
async def test_r2_default_conservative_in_churn_matrix():
    """
    验证：R2 风险在 churn 矩阵中返回保守决策。
    """
    r2_signals = ["BUG_RISK"]

    response = await decide_with_matrix(
        signals=r2_signals,
        matrix_path="matrices/pr_loop_churn.yaml",
    )

    decision_val = response.decision.value
    # Churn matrix escalates to HITL regardless
    assert decision_val in ("HITL", "ONLY_SUGGEST"), \
        f"R2 risk in churn matrix should be conservative, got {decision_val}"


# ============================================================================
# Invariant: R0 Can Allow (Only in Converged Matrix)
# ============================================================================

@pytest.mark.asyncio
async def test_r0_continues_loop_in_default_matrix():
    """
    验证：R0 风险在默认矩阵中继续循环（ONLY_SUGGEST），不直接 ALLOW。
    这确保需要达到收敛阈值才能终止。
    """
    r0_signals = ["LOW_VALUE_NITS"]

    response = await decide_with_matrix(
        signals=r0_signals,
        matrix_path="matrices/pr_loop_demo.yaml",
    )

    decision_val = response.decision.value
    assert decision_val == "ONLY_SUGGEST", \
        f"R0 in default matrix should continue loop, got {decision_val}"


@pytest.mark.asyncio
async def test_r0_allows_in_converged_matrix():
    """
    验证：R0 风险在收敛矩阵中可以 ALLOW。
    这是收敛策略的最终目标。
    """
    r0_signals = ["LOW_VALUE_NITS"]

    response = await decide_with_matrix(
        signals=r0_signals,
        matrix_path="matrices/pr_loop_phase_e.yaml",
    )

    decision_val = response.decision.value
    assert decision_val == "ALLOW", \
        f"R0 in converged matrix should allow, got {decision_val}"


# ============================================================================
# Invariant: Tighten-Only is Preserved
# ============================================================================

@pytest.mark.asyncio
async def test_matrix_switching_does_not_relax_risk():
    """
    验证：矩阵切换不会放松风险判断。

    测试策略：
    1. 用 R3 信号调用默认矩阵 → 记录决策
    2. 用 R3 信号调用收敛矩阵 → 记录决策
    3. 两者都不应该是 ALLOW

    这确保 matrix_path 是 policy 选择，不是 risk 替代。
    """
    r3_signals = ["SECURITY_BOUNDARY"]

    response_default = await decide_with_matrix(
        signals=r3_signals,
        matrix_path="matrices/pr_loop_demo.yaml",
    )

    response_converged = await decide_with_matrix(
        signals=r3_signals,
        matrix_path="matrices/pr_loop_phase_e.yaml",
    )

    # 两者都不应该 ALLOW
    assert response_default.decision.value != "ALLOW", \
        "Default matrix should not ALLOW R3"
    assert response_converged.decision.value != "ALLOW", \
        "Converged matrix should not ALLOW R3"

    # 两者都应该是保守决策
    conservative_decisions = ("HITL", "DENY", "ONLY_SUGGEST")
    assert response_default.decision.value in conservative_decisions
    assert response_converged.decision.value in conservative_decisions


# ============================================================================
# Invariant: Max Rounds is Efficiency Threshold (Not Quality Proof)
# ============================================================================

@pytest.mark.asyncio
async def test_churn_matrix_escapes_r0():
    """
    验证：即使 R0（低风险），churn 矩阵也会升级到 HITL。

    这证明 max_rounds 是效率阈值，不是质量证明：
    - R0 表示"当前轮次低风险"
    - 但如果达到 max_rounds，说明自动化效率不足
    - 因此仍需人工介入，而非自动批准
    """
    r0_signals = ["LOW_VALUE_NITS"]

    response = await decide_with_matrix(
        signals=r0_signals,
        matrix_path="matrices/pr_loop_churn.yaml",
    )

    decision_val = response.decision.value
    # Churn matrix should escalate, not allow
    assert decision_val == "HITL", \
        f"Churn matrix should escalate even R0 to HITL, got {decision_val}"
    assert response.primary_reason == "PR_LOOP_CHURN", \
        f"Primary reason should be PR_LOOP_CHURN, got {response.primary_reason}"


# ============================================================================
# Matrix Existence Tests
# ============================================================================

@pytest.mark.parametrize(
    "matrix_path",
    [
        "matrices/pr_loop_demo.yaml",
        "matrices/pr_loop_phase_e.yaml",
        "matrices/pr_loop_churn.yaml",
    ],
)
def test_matrix_files_exist(matrix_path):
    """
    验证：所有 Phase E 矩阵文件都存在。
    """
    from pathlib import Path

    root = Path(__file__).parent.parent
    matrix_file = root / matrix_path

    assert matrix_file.exists(), \
        f"Matrix file {matrix_path} does not exist"


def test_matrix_files_are_valid_yaml():
    """
    验证：所有 Phase E 矩阵文件都是有效的 YAML。
    """
    import yaml
    from pathlib import Path

    root = Path(__file__).parent.parent
    matrix_paths = [
        "matrices/pr_loop_demo.yaml",
        "matrices/pr_loop_phase_e.yaml",
        "matrices/pr_loop_churn.yaml",
    ]

    for matrix_path in matrix_paths:
        matrix_file = root / matrix_path
        assert matrix_file.exists(), f"Matrix file {matrix_path} does not exist"

        with open(matrix_file) as f:
            try:
                data = yaml.safe_load(f)
                assert data is not None, f"Matrix file {matrix_path} is empty"
                assert "version" in data, f"Matrix file {matrix_path} missing 'version'"
            except yaml.YAMLError as e:
                pytest.fail(f"Matrix file {matrix_path} is invalid YAML: {e}")
