"""
Phase A: 最小可用模型定义

这些模型仅用于示例，不改 core。
"""
from pydantic import BaseModel, Field
from typing import List, Optional, Literal, Dict, Any
from enum import Enum, unique


class PRMeta(BaseModel):
    """PR 元数据"""
    files_changed_count: int = Field(..., ge=0)
    loc_added: int = Field(..., ge=0)
    loc_deleted: int = Field(..., ge=0)
    touched_paths: List[str] = Field(default_factory=list)
    has_ci_green: bool = False
    contributor_trust_level: Literal["new", "known"] = "new"
    touches_sensitive_boundary: bool = False


class ReviewComment(BaseModel):
    """AI Reviewer 的评论"""
    category: Literal["style", "nit", "bug", "security", "build", "perf"] = "nit"
    severity: int = Field(..., ge=1, le=5)  # 1-5
    text: str
    evidence_refs: List[str] = Field(default_factory=list)


@unique
class AISignal(str, Enum):
    """从 ReviewComment 提取的归一化信号

    风险等级映射（与 src/evidence/risk.py 一致）：
    - R3 (高风险): SECURITY_BOUNDARY, BUILD_CHAIN, MULTI_SIGNAL
    - R2 (中风险): BUG_RISK
    - R0 (良性): LOW_VALUE_NITS
    - R1 (低风险): UNKNOWN_SIGNAL

    失效安全：
    - UNKNOWN_SIGNAL: 未知信号映射为这个（fail-closed）

    设计原则：
    - 有限集合：所有 AI 输出必须映射到这些信号
    - 可审计：每个信号都有明确的风险等级
    - 失效安全：未知信号不会"钻空子"
    """

    # R3: 高风险 - 永远 HITL
    SECURITY_BOUNDARY = "SECURITY_BOUNDARY"  # 触碰安全边界
    BUILD_CHAIN = "BUILD_CHAIN"            # 触碰构建/部署链
    MULTI_SIGNAL = "MULTI_SIGNAL"          # 多个高风险信号组合

    # R2: 中风险 - 默认保守
    BUG_RISK = "BUG_RISK"                  # 潜在缺陷

    # R0: 良性 - 可自动收敛
    LOW_VALUE_NITS = "LOW_VALUE_NITS"      # 低价值风格建议

    # 失效安全：未知信号
    UNKNOWN_SIGNAL = "UNKNOWN_SIGNAL"      # 未在 allowlist 中的信号


class PRDecision(str, Enum):
    """PR Gate 决策：仅由 PR Gate 单一裁决源发出，严格复用 core 层 Decision 语义，确保自动化流程中的唯一决策权归属。"""
    ALLOW = "ALLOW"
    ONLY_SUGGEST = "ONLY_SUGGEST"
    HITL = "HITL"
    DENY = "DENY"


class PRDecisionResponse(BaseModel):
    """PR Gate 决策响应"""
    decision: PRDecision
    reasons: List[str] = Field(default_factory=list)
    used_signals: List[AISignal] = Field(default_factory=list)
    ignored_signals: List[AISignal] = Field(default_factory=list)
    evidence_summary: Dict[str, Any] = Field(default_factory=dict)
    round_index: int = 0
    stop_condition_applied: bool = False
