"""
Phase A: AI Coding 模拟器

根据 review comments 生成"修复"动作，并以一定概率引入新的低价值问题（模拟越改越糟）。
"""
import random
from typing import List, Optional
from .models import PRMeta, ReviewComment


def apply_fixes(
    pr_meta: PRMeta,
    comments: List[ReviewComment],
    rng: Optional[random.Random] = None,
) -> PRMeta:
    """
    根据 review comments 应用修复，模拟 AI Coding 的行为。
    
    策略：
    - 修复 bug/security/build 类评论（降低风险）
    - 修复 style/nit 类评论，但有 30% 概率引入新的 nit
    - 模拟"越改越糟"：修复后可能增加文件数量或 LOC
    """
    new_meta = pr_meta.model_copy()
    r = rng or random
    
    # 统计需要修复的评论
    bug_comments = [c for c in comments if c.category == "bug"]
    security_comments = [c for c in comments if c.category == "security"]
    build_comments = [c for c in comments if c.category == "build"]
    nit_comments = [c for c in comments if c.category in ["nit", "style"]]
    
    # 修复 bug/security/build（降低风险）
    if bug_comments:
        # 修复后，风险降低
        new_meta.touches_sensitive_boundary = False  # 假设修复了风险
    
    if security_comments:
        new_meta.touches_sensitive_boundary = False  # 假设修复了安全风险
    
    if build_comments:
        # 修复后，CI 可能变绿
        if r.random() < 0.7:
            new_meta.has_ci_green = True
    
    # 修复 style/nit（但有概率引入新问题）
    if nit_comments:
        # 30% 概率引入新的 nit（模拟越改越糟）
        if r.random() < 0.3:
            # 增加文件数量或 LOC（模拟修改更多文件）
            new_meta.files_changed_count += r.randint(0, 2)
            new_meta.loc_added += r.randint(5, 20)
            new_meta.loc_deleted += r.randint(0, 10)
    
    return new_meta
