"""
Signal Layer - Base Models.

Signal: (domain, signal_type, payload) - minimal schema for governance input.
Gate does not parse payload.
"""
from typing import Any
from pydantic import BaseModel, Field


class Signal(BaseModel):
    """Minimal signal schema. Gate does not parse payload."""

    domain: str = Field(..., description="Signal domain, e.g. pr, tool, permission")
    signal_type: str = Field(..., description="Signal type within domain, e.g. review_bug, ci_failure")
    payload: dict[str, Any] = Field(default_factory=dict, description="Domain-specific payload, opaque to Gate")
