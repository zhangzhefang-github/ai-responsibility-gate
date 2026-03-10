"""
Evidence Provider Framework - Base Models.

GovernanceEvidence: standard fields consumed by Gate. Gate does not parse payload.
Signal is defined in src.signals.models.
"""
from typing import Optional
from pydantic import BaseModel, Field


class GovernanceEvidence(BaseModel):
    """Standard evidence fields consumed by Gate. Gate does not parse payload."""

    risk_level: Optional[str] = Field(None, description="R0, R1, R2, R3")
    action_type: Optional[str] = Field(None, description="e.g. READ, WRITE")
    scope_level: Optional[str] = Field(None, description="Permission scope")
    verifiability: Optional[str] = Field(None, description="Action verifiability")
    provider: str = Field("unknown", description="Provider that produced this evidence")
