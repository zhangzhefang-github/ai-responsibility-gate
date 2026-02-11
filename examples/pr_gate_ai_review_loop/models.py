"""
Phase A: 最小可用模型定义

这些模型仅用于示例，不改 core。
"""
from pydantic import BaseModel, Field
from typing import List, Optional, Literal, Dict, Any
from enum import Enum


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


class AISignal(str, Enum):
    """从 ReviewComment 提取的归一化信号"""
    SECURITY_BOUNDARY = "SECURITY_BOUNDARY"
    BUILD_CHAIN = "BUILD_CHAIN"
    API_CHANGE = "API_CHANGE"
    LOW_VALUE_NITS = "LOW_VALUE_NITS"
    PERFORMANCE_ISSUE = "PERFORMANCE_ISSUE"
    BUG_RISK = "BUG_RISK"


class PRDecision(str, Enum):
    """PR Gate 决策（复用 core 的 Decision 语义）"""
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
