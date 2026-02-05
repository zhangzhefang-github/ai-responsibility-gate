from pydantic import BaseModel, Field, field_validator
from typing import Optional, Literal, Dict, Any
from enum import Enum

class ResponsibilityType(str, Enum):
    Information = "Information"
    RiskNotice = "RiskNotice"
    EntitlementDecision = "EntitlementDecision"

class Decision(str, Enum):
    ALLOW = "ALLOW"
    ONLY_SUGGEST = "ONLY_SUGGEST"
    HITL = "HITL"
    DENY = "DENY"

class DecisionRequest(BaseModel):
    session_id: Optional[str] = None
    user_id: Optional[str] = None
    text: str = Field(..., min_length=1, max_length=10000, description="User input text")
    debug: bool = False
    verbose: bool = False
    context: Optional[Dict[str, Any]] = Field(None, max_length=100)
    
    @field_validator('text')
    @classmethod
    def text_not_empty(cls, v: str) -> str:
        """Ensure text is not empty or whitespace only."""
        if not v or not v.strip():
            raise ValueError('Text cannot be empty or whitespace only')
        return v.strip()

class Evidence(BaseModel):
    provider: str
    available: bool
    data: dict

class ClassifierResult(BaseModel):
    type: ResponsibilityType
    confidence: float
    trigger_spans: list[str]

class GateContext(BaseModel):
    request_id: str
    session_id: Optional[str]
    user_id: Optional[str]
    text: str
    debug: bool
    verbose: bool = False
    context: Optional[Dict[str, Any]] = None

class Explanation(BaseModel):
    summary: str
    evidence_used: list[str]
    trigger_spans: list[str]

class PolicyInfo(BaseModel):
    matrix_version: str
    rules_fired: Optional[list[str]] = None

class DecisionResponse(BaseModel):
    request_id: str
    session_id: Optional[str]
    responsibility_type: ResponsibilityType
    decision: Decision
    primary_reason: str
    suggested_action: str
    explanation: Explanation
    policy: PolicyInfo
    latency_ms: int

class PostcheckIssue(BaseModel):
    code: str
    severity: str
    description: str

class PostcheckResult(BaseModel):
    passed: bool
    issues: list[PostcheckIssue]
