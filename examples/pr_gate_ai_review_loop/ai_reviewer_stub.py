"""
Phase A: AI Reviewer 模拟器

生成 ReviewComment，刻意混入 70% 的 style/nit，少量真实风险。
"""
import random
from typing import List, Optional
from .models import PRMeta, ReviewComment


# 模拟 AI Reviewer 的评论模板
NIT_TEMPLATES = [
    "变量命名可以更清晰",
    "建议添加空行以提高可读性",
    "这行代码可以提取为函数",
    "建议使用更描述性的变量名",
    "代码格式可以优化",
    "建议添加注释",
    "可以简化这个表达式",
    "建议使用常量而不是魔法数字",
]

STYLE_TEMPLATES = [
    "代码风格不符合项目规范",
    "缩进不一致",
    "行尾有多余空格",
    "建议使用单引号而不是双引号",
    "函数名应该使用 camelCase",
    "建议添加类型注解",
]

BUG_TEMPLATES = [
    "这里可能存在空指针异常",
    "缺少错误处理",
    "边界条件未检查",
    "可能导致内存泄漏",
]

SECURITY_TEMPLATES = [
    "这里可能存在 SQL 注入风险",
    "敏感信息未加密",
    "权限检查不完整",
    "可能存在 XSS 漏洞",
]

BUILD_TEMPLATES = [
    "依赖版本可能不兼容",
    "构建脚本需要更新",
    "缺少必要的依赖",
    "CI 配置可能有问题",
]


def generate_review_comments(
    pr_meta: PRMeta,
    round_index: int = 0,
    rng: Optional[random.Random] = None,
) -> List[ReviewComment]:
    """
    生成 ReviewComment，模拟 AI Reviewer 的行为。

    策略：
    - 70% 概率生成 style/nit 类评论
    - 如果 touching sensitive boundary，增加 security 评论概率
    - round_index 越高，nit 越多（模拟越改越糟）
    - Phase E 增强：确定性确保符合场景类型的信号被产生
      - docs/tests 场景：只产生 nit/style
      - high-risk 场景（touches_sensitive_boundary）：确保至少产生 security
      - build 敏感场景：确保至少产生 build
    """
    comments = []
    r = rng or random

    # 基础评论数量（根据文件数量）
    base_count = min(pr_meta.files_changed_count, 5)
    if base_count == 0:
        base_count = 1

    # round_index 越高，nit 越多
    nit_multiplier = 1 + round_index * 0.5

    is_docs_or_tests = all(
        p.startswith("docs/") or p.startswith("tests/") for p in pr_meta.touched_paths
    ) and pr_meta.touched_paths  # 非空且全在 docs/tests 下

    is_build_sensitive = any(
        "build" in p or "ci" in p.lower() or "deps" in p.lower()
        for p in pr_meta.touched_paths
    )

    # Phase E: 确定性信号调整（保证符合场景类型）
    # 在生成评论后，如果没有产生预期的信号类型，强制添加一条
    has_security = False
    has_build = False

    for i in range(int(base_count * nit_multiplier)):
        rand = r.random()

        if rand < 0.5:  # 50% nit
            comments.append(
                ReviewComment(
                    category="nit",
                    severity=r.randint(1, 2),
                    text=r.choice(NIT_TEMPLATES),
                    evidence_refs=[f"line_{r.randint(1, 100)}"],
                )
            )
        elif rand < 0.7:  # 20% style
            comments.append(
                ReviewComment(
                    category="style",
                    severity=r.randint(1, 2),
                    text=r.choice(STYLE_TEMPLATES),
                    evidence_refs=[f"line_{r.randint(1, 100)}"],
                )
            )
        elif rand < 0.85 and not is_docs_or_tests:  # 15% bug（低风险），docs/tests 场景不产生 bug
            comments.append(
                ReviewComment(
                    category="bug",
                    severity=r.randint(2, 3),
                    text=r.choice(BUG_TEMPLATES),
                    evidence_refs=[f"line_{r.randint(1, 100)}"],
                )
            )
        elif (
            pr_meta.touches_sensitive_boundary
            and rand < 0.95
            and not is_docs_or_tests
        ):  # 10% security（如果 touching sensitive，且非 docs/tests）
            comments.append(
                ReviewComment(
                    category="security",
                    severity=r.randint(4, 5),
                    text=r.choice(SECURITY_TEMPLATES),
                    evidence_refs=[f"line_{r.randint(1, 100)}"],
                )
            )
            has_security = True
        elif is_build_sensitive and not is_docs_or_tests:
            # 如果 touching build/ci/deps，增加 build 评论（高风险场景）
            comments.append(
                ReviewComment(
                    category="build",
                    severity=r.randint(3, 4),
                    text=r.choice(BUILD_TEMPLATES),
                    evidence_refs=[f"line_{r.randint(1, 100)}"],
                )
            )
            has_build = True
        else:
            # 默认还是 nit
            comments.append(
                ReviewComment(
                    category="nit",
                    severity=1,
                    text=r.choice(NIT_TEMPLATES),
                    evidence_refs=[f"line_{r.randint(1, 100)}"],
                )
            )

    # Phase E: 确定性调整（如果未产生预期的信号类型，强制添加）
    # 这确保 demo 场景能够稳定产生预期的信号，不影响架构不变量
    if pr_meta.touches_sensitive_boundary and not has_security and not is_docs_or_tests:
        # 高风险场景：确保至少有一条 security 评论
        comments.append(
            ReviewComment(
                category="security",
                severity=5,
                text=r.choice(SECURITY_TEMPLATES),
                evidence_refs=["line_1"],
            )
        )

    if is_build_sensitive and not has_build and not is_docs_or_tests:
        # build 敏感场景：确保至少有一条 build 评论
        comments.append(
            ReviewComment(
                category="build",
                severity=4,
                text=r.choice(BUILD_TEMPLATES),
                evidence_refs=["line_1"],
            )
        )

    return comments
