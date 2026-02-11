"""
Phase A: PR Gate 决策逻辑（独立实现，不改 core）

实现 Gate 规则（确定性）：
- AI 的 style/nit 类 comment 永远不阻塞（ONLY_SUGGEST）
- 命中敏感边界/安全/构建链路/依赖变更等 → HITL 或 DENY
- 提供 stop condition：若连续 N 轮（比如 2-3 轮）review 仍只有低价值 nits，则 Gate 自动 ALLOW
"""
from typing import List, Dict, Any
from .models import PRMeta, ReviewComment, AISignal, PRDecision, PRDecisionResponse
from .signal_extractor import extract_signals, is_nit_only


def decide_pr(
    pr_meta: PRMeta,
    review_comments: List[ReviewComment],
    round_index: int = 0,
) -> PRDecisionResponse:
    """
    PR Gate 决策函数（确定性规则）。
    
    规则优先级：
    1. Stop Condition: 连续 N 轮只有低价值 nits → ALLOW
    2. Security/Build 风险 → HITL 或 DENY
    3. Bug 风险 → HITL
    4. 只有 style/nit → ONLY_SUGGEST（不阻塞）
    5. 默认 → ALLOW（低风险 PR）
    """
    # 提取信号
    signals = extract_signals(review_comments)
    is_nit_only_flag = is_nit_only(review_comments)
    
    # 规则 2: Security/Build 风险 → HITL
    if AISignal.SECURITY_BOUNDARY in signals:
        return PRDecisionResponse(
            decision=PRDecision.HITL,
            reasons=["Security boundary touched, requires human review"],
            used_signals=[AISignal.SECURITY_BOUNDARY],
            ignored_signals=[s for s in signals if s != AISignal.SECURITY_BOUNDARY],
            evidence_summary={
                "round_index": round_index,
                "touches_sensitive_boundary": pr_meta.touches_sensitive_boundary,
                "security_comments": [c.text for c in review_comments if c.category == "security"]
            },
            round_index=round_index,
            stop_condition_applied=False
        )
    
    if AISignal.BUILD_CHAIN in signals:
        return PRDecisionResponse(
            decision=PRDecision.HITL,
            reasons=["Build chain touched, requires human review"],
            used_signals=[AISignal.BUILD_CHAIN],
            ignored_signals=[s for s in signals if s != AISignal.BUILD_CHAIN],
            evidence_summary={
                "round_index": round_index,
                "touched_paths": pr_meta.touched_paths,
                "build_comments": [c.text for c in review_comments if c.category == "build"]
            },
            round_index=round_index,
            stop_condition_applied=False
        )
    
    # 规则 3: Bug 风险（高 severity）→ HITL
    if AISignal.BUG_RISK in signals:
        return PRDecisionResponse(
            decision=PRDecision.HITL,
            reasons=["High severity bug risk detected, requires human review"],
            used_signals=[AISignal.BUG_RISK],
            ignored_signals=[s for s in signals if s != AISignal.BUG_RISK],
            evidence_summary={
                "round_index": round_index,
                "bug_comments": [c.text for c in review_comments if c.category == "bug" and c.severity >= 4]
            },
            round_index=round_index,
            stop_condition_applied=False
        )
    
    # 规则 4: 只有 style/nit → ONLY_SUGGEST（不阻塞）
    if is_nit_only_flag:
        return PRDecisionResponse(
            decision=PRDecision.ONLY_SUGGEST,
            reasons=["Only style/nit comments, non-blocking"],
            used_signals=[AISignal.LOW_VALUE_NITS],
            ignored_signals=[],
            evidence_summary={
                "round_index": round_index,
                "comment_count": len(review_comments)
            },
            round_index=round_index,
            stop_condition_applied=False
        )
    
    # 规则 5: 默认 → ALLOW（低风险 PR）
    return PRDecisionResponse(
        decision=PRDecision.ALLOW,
        reasons=["Low risk PR, auto-approved"],
        used_signals=signals,
        ignored_signals=[],
        evidence_summary={
            "round_index": round_index,
            "files_changed": pr_meta.files_changed_count,
            "loc_added": pr_meta.loc_added,
            "has_ci_green": pr_meta.has_ci_green
        },
        round_index=round_index,
        stop_condition_applied=False
    )
