from pydantic import BaseModel, Field, field_validator, model_validator
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
    # Phase C: text is no longer the only input channel.
    # It becomes optional to support structured inputs (e.g., PR metadata),
    # while preserving compatibility for existing text-only callers.
    text: Optional[str] = Field(
        None,
        min_length=1,
        max_length=10000,
        description="User input text (optional when structured_input is provided)",
    )
    # Optional structured input payload for non-text scenarios (e.g., PR metadata).
    structured_input: Optional[Dict[str, Any]] = Field(
        None,
        description="Optional structured input payload (domain-specific)",
    )
    debug: bool = False
    verbose: bool = False
    context: Optional[Dict[str, Any]] = Field(None, max_length=100)
    
    @field_validator('text')
    @classmethod
    def text_not_empty(cls, v: Optional[str]) -> Optional[str]:
        """Normalize text: strip whitespace; allow None when structured_input is used."""
        if v is None:
            return None
        if not v.strip():
            # Let root validator decide if this is acceptable based on structured_input.
            return None
        return v.strip()

    @model_validator(mode="after")
    def ensure_some_input(self) -> "DecisionRequest":
        """
        Ensure that at least one input channel is provided:
        - text (non-empty after normalization), or
        - structured_input (non-empty dict).

        This keeps the contract strict for new callers while remaining
        compatible with existing text-only usages.
        """
        has_text = bool(self.text)
        has_structured = bool(self.structured_input)
        if not has_text and not has_structured:
            raise ValueError("Either 'text' or 'structured_input' must be provided")
        return self

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
    # Phase C: allow GateContext to carry optional text plus structured input.
    text: Optional[str]
    debug: bool
    verbose: bool = False
    context: Optional[Dict[str, Any]] = None
    structured_input: Optional[Dict[str, Any]] = None

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
