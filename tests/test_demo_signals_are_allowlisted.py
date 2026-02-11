from examples.pr_gate_ai_review_loop.models import PRMeta
from examples.pr_gate_ai_review_loop.ai_reviewer_stub import generate_review_comments
from examples.pr_gate_ai_review_loop.signal_extractor import extract_signals
from examples.pr_gate_ai_review_loop.signal_validation import (
    normalize_signals,
    load_signal_allowlist,
)


def test_demo_signal_chain_produces_allowlisted_signals():
    """
    通过 reviewer_stub + signal_extractor + normalize_signals 这条链路，
    确保最终输出的 signals 只包含 allowlist 或 UNKNOWN_SIGNAL。

    不运行完整 demo 循环，只验证信号处理链路。
    """
    # 构造一个典型的高风险 PRMeta（触发多种评论）
    pr_meta = PRMeta(
        files_changed_count=3,
        loc_added=120,
        loc_deleted=10,
        touched_paths=["src/auth/login.py", "build.gradle"],
        has_ci_green=False,
        contributor_trust_level="new",
        touches_sensitive_boundary=True,
    )

    rng_seed = 123
    import random

    rng = random.Random(rng_seed)
    comments = generate_review_comments(pr_meta, round_index=0, rng=rng)
    raw_signals = extract_signals(comments)
    raw_values = [s.value for s in raw_signals]

    normalized = normalize_signals(raw_values)
    allowlist = load_signal_allowlist()

    for s in normalized:
        assert s in allowlist or s == "UNKNOWN_SIGNAL"

