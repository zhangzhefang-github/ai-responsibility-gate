"""
Phase A: 从 ReviewComment 提取 AISignal

将 ReviewComment 归一化为 Gate 可消费的信号。
"""
from typing import List
from .models import ReviewComment, AISignal


def extract_signals(comments: List[ReviewComment]) -> List[AISignal]:
    """
    从 ReviewComment 提取归一化的 AISignal。
    
    规则：
    - security 评论 → SECURITY_BOUNDARY
    - build 评论 → BUILD_CHAIN
    - bug 评论（高 severity） → BUG_RISK
    - perf 评论 → PERFORMANCE_ISSUE
    - style/nit 评论 → LOW_VALUE_NITS
    """
    signals = []
    
    for comment in comments:
        if comment.category == "security":
            signals.append(AISignal.SECURITY_BOUNDARY)
        elif comment.category == "build":
            signals.append(AISignal.BUILD_CHAIN)
        elif comment.category == "bug":
            signals.append(AISignal.BUG_RISK)
        elif comment.category == "perf":
            signals.append(AISignal.PERFORMANCE_ISSUE)
        elif comment.category in ["style", "nit"]:
            signals.append(AISignal.LOW_VALUE_NITS)
    
    # 去重
    return list(set(signals))


def is_nit_only(comments: List[ReviewComment]) -> bool:
    """判断是否只有低价值的 nit/style 评论"""
    if not comments:
        return False
    
    # 检查是否所有评论都是 style/nit，且 severity <= 2
    return all(
        c.category in ["style", "nit"] and c.severity <= 2
        for c in comments
    )
