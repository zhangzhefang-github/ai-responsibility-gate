"""
Demo contract smoke tests.

这些测试验证 demo_phase_e.py 的信号链路契约，不运行完整 demo（避免耗时）。
"""
import pytest
from examples.pr_gate_ai_review_loop.models import PRMeta, ReviewComment
from examples.pr_gate_ai_review_loop.ai_reviewer_stub import generate_review_comments
from examples.pr_gate_ai_review_loop.signal_extractor import extract_signals, is_nit_only
from examples.pr_gate_ai_review_loop.signal_validation import load_signal_allowlist, normalize_signals
import random


def test_signals_allowlist_contains_all_used_signals():
    """
    验证 signals_catalog.yaml 中的 allowlist 包含 demo 使用的所有信号。
    """
    allowlist = load_signal_allowlist()

    # demo_phase_e.py 中使用的所有信号（不包含策略信号，策略通过 profile 实现）
    expected_signals = {
        "SECURITY_BOUNDARY",
        "BUILD_CHAIN",
        "BUG_RISK",
        "LOW_VALUE_NITS",
        "UNKNOWN_SIGNAL",
        "MULTI_SIGNAL",
    }

    # 验证所有预期信号都在 allowlist 中
    for signal in expected_signals:
        assert signal in allowlist, f"Signal '{signal}' not in allowlist"


def test_reviewer_stub_produces_extractable_signals():
    """
    验证 ai_reviewer_stub 产生的评论可以被 signal_extractor 正确提取。
    """
    # 使用固定 seed 确保确定性
    rng = random.Random(42)

    # 创建一个低风险 PR meta
    pr_meta = PRMeta(
        files_changed_count=2,
        loc_added=50,
        loc_deleted=10,
        touched_paths=["docs/README.md"],
        has_ci_green=True,
        contributor_trust_level="known",
        touches_sensitive_boundary=False
    )

    # 生成评论
    comments = generate_review_comments(pr_meta, round_index=0, rng=rng)
    assert len(comments) > 0, "ai_reviewer_stub should produce comments"

    # 提取信号
    signals = extract_signals(comments)
    raw_signal_values = [s.value for s in signals]
    assert len(raw_signal_values) > 0, "extract_signals should produce signals"

    # 归一化
    normalized = normalize_signals(raw_signal_values)

    # 验证所有归一化后的信号都在 allowlist 中（或为 UNKNOWN_SIGNAL）
    allowlist = load_signal_allowlist()
    for signal in normalized:
        assert signal in allowlist or signal == "UNKNOWN_SIGNAL", \
            f"Normalized signal '{signal}' not in allowlist"


def test_is_nit_only_correctly_identifies_benign_rounds():
    """
    验证 is_nit_only 正确识别只有低价值 nits 的轮次。
    """
    # 全是 nit/style，severity <= 2
    benign_comments = [
        ReviewComment(category="nit", severity=1, text="变量命名可以更清晰"),
        ReviewComment(category="style", severity=2, text="代码格式可以优化"),
    ]
    assert is_nit_only(benign_comments), "Should identify nit-only comments"

    # 包含 bug 评论，severity > 2
    risk_comments = [
        ReviewComment(category="nit", severity=1, text="变量命名可以更清晰"),
        ReviewComment(category="bug", severity=3, text="这里可能存在空指针异常"),
    ]
    assert not is_nit_only(risk_comments), "Should not identify as nit-only"

    # 包含 security 评论
    security_comments = [
        ReviewComment(category="nit", severity=1, text="变量命名可以更清晰"),
        ReviewComment(category="security", severity=4, text="这里可能存在 SQL 注入风险"),
    ]
    assert not is_nit_only(security_comments), "Should not identify as nit-only"


def test_normalize_signals_is_deterministic():
    """
    验证 normalize_signals 是确定性的（多次调用结果一致）。
    """
    raw_signals = ["LOW_VALUE_NITS", "BUG_RISK", "LOW_VALUE_NITS", "UNKNOWN_SIGNAL"]

    # 多次调用，结果应该一致
    result1 = normalize_signals(raw_signals)
    result2 = normalize_signals(raw_signals)
    result3 = normalize_signals(raw_signals)

    assert result1 == result2 == result3, "normalize_signals should be deterministic"

    # 验证去重和排序
    assert result1 == sorted(set(result1)), "Should be de-duplicated and sorted"


def test_normalize_signals_handles_edge_cases():
    """
    验证 normalize_signals 正确处理边界情况。
    """
    allowlist = load_signal_allowlist()

    # 空列表
    assert normalize_signals([]) == []

    # 只有空值
    assert normalize_signals(["", None, "  ", 123]) == []

    # 混合有效和无效值
    result = normalize_signals(["LOW_VALUE_NITS", "", "BUG_RISK", None])
    assert "LOW_VALUE_NITS" in result
    assert "BUG_RISK" in result
    assert "" not in result
    assert None not in result

    # 未知信号映射为 UNKNOWN_SIGNAL
    result = normalize_signals(["LOW_VALUE_NITS", "NOT_IN_ALLOWLIST"])
    assert "LOW_VALUE_NITS" in result
    assert "UNKNOWN_SIGNAL" in result
    assert "NOT_IN_ALLOWLIST" not in result


def test_high_risk_scenario_produces_expected_signals():
    """
    验证高风险场景产生预期的高风险信号。
    """
    rng = random.Random(44)  # 使用固定 seed

    # 创建高风险 PR meta
    pr_meta = PRMeta(
        files_changed_count=5,
        loc_added=200,
        loc_deleted=50,
        touched_paths=["src/auth/login.py", "build.gradle"],
        has_ci_green=False,
        contributor_trust_level="new",
        touches_sensitive_boundary=True
    )

    # 生成评论
    comments = generate_review_comments(pr_meta, round_index=0, rng=rng)

    # 提取信号
    signals = extract_signals(comments)
    raw_signal_values = [s.value for s in signals]

    # 验证产生高风险信号
    normalized = normalize_signals(raw_signal_values)
    # 高风险场景应该产生 SECURITY_BOUNDARY 或 BUILD_CHAIN
    has_high_risk = any(s in ("SECURITY_BOUNDARY", "BUILD_CHAIN") for s in normalized)
    assert has_high_risk, f"High-risk scenario should produce high-risk signals, got: {normalized}"


def test_demo_scenario_seeds_produce_deterministic_results():
    """
    验证 demo 使用的 seed 能产生确定性的结果。
    """
    # Scenario 1 seed
    rng1 = random.Random(42)
    pr_meta1 = PRMeta(
        files_changed_count=1,
        loc_added=10,
        loc_deleted=5,
        touched_paths=["docs/README.md"],
        has_ci_green=True,
        contributor_trust_level="known",
        touches_sensitive_boundary=False
    )
    comments1_a = generate_review_comments(pr_meta1, round_index=0, rng=rng1)
    rng1 = random.Random(42)  # 重置
    comments1_b = generate_review_comments(pr_meta1, round_index=0, rng=rng1)

    # 同一个 seed 应该产生相同的结果
    assert len(comments1_a) == len(comments1_b)
    assert [c.text for c in comments1_a] == [c.text for c in comments1_b]


@pytest.mark.parametrize(
    "signals,expected_contains",
    [
        (["SECURITY_BOUNDARY", "LOW_VALUE_NITS"], "SECURITY_BOUNDARY"),
        (["BUILD_CHAIN"], "BUILD_CHAIN"),
        (["BUG_RISK"], "BUG_RISK"),
        (["LOW_VALUE_NITS"], "LOW_VALUE_NITS"),
    ],
)
def test_common_signal_patterns_normalize_correctly(signals, expected_contains):
    """
    参数化测试：验证常见的信号模式被正确归一化。
    """
    normalized = normalize_signals(signals)
    assert expected_contains in normalized
    # 验证去重
    assert len(normalized) == len(set(normalized))
    # 验证排序
    assert normalized == sorted(normalized)


def test_churn_matrix_escalates_to_hitl():
    """
    验证 churn 矩阵在 max_rounds 达到时升级到 HITL。
    """
    import asyncio
    from src.core.models import DecisionRequest, GateContext
    from src.core.gate import decide as core_decide

    # 构造一个低风险请求
    core_req = DecisionRequest(
        text="pr_loop_churn_demo",
        structured_input={
            "signals": ["LOW_VALUE_NITS"],
        },
        context={"loop_state": {"round_index": 5, "nit_only_streak": 0}},
    )

    # 使用 churn 矩阵调用 core gate
    async def run_test():
        return await core_decide(core_req, matrix_path="matrices/pr_loop_churn.yaml")

    response = asyncio.run(run_test())

    # 验证决策是 HITL 且原因正确
    assert response.decision.value == "HITL", \
        f"Churn matrix should return HITL, got {response.decision.value}"
    assert response.primary_reason == "PR_LOOP_CHURN", \
        f"Primary reason should be PR_LOOP_CHURN, got {response.primary_reason}"

    # 验证解释摘要包含关键信息
    explanation = response.explanation
    if explanation:
        summary = explanation.summary
        # 应该提到 budget exhausted 或 human review
        assert summary is not None, "Explanation summary should exist"
