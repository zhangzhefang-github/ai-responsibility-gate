from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import Optional
from .core.models import DecisionRequest, DecisionResponse
from .core.gate import decide
from .feedback import FeedbackRecord, save_feedback

app = FastAPI(title="AI Responsibility Gate")

class FeedbackRequest(BaseModel):
    trace_id: str = Field(..., description="Request ID from /decision response")
    gate_decision: str = Field(..., description="Decision made by the gate")
    human_decision: str = Field(..., description="Human's actual decision")
    reason_code: str = Field(..., description="Reason for the decision")
    notes: Optional[str] = Field(None, description="Additional notes")
    context: Optional[dict] = Field(None, description="Additional context")

@app.post("/decision", response_model=DecisionResponse)
async def decision(req: DecisionRequest) -> DecisionResponse:
    """
    Make a decision on whether AI can answer the user's request.
    
    Returns a DecisionResponse with:
    - decision: ALLOW, ONLY_SUGGEST, HITL, or DENY
    - explanation: Why this decision was made
    - policy: Matrix version and rules fired
    """
    try:
        return await decide(req)
    except RuntimeError as e:
        # System configuration errors (matrix not found, invalid config, etc.)
        raise HTTPException(
            status_code=500,
            detail=f"System configuration error: {str(e)}"
        ) from e
    except ValueError as e:
        # Input validation errors (handled by Pydantic, but catch for safety)
        raise HTTPException(
            status_code=400,
            detail=f"Invalid request: {str(e)}"
        ) from e

@app.post("/feedback")
async def feedback(req: FeedbackRequest):
    """
    Submit feedback for gate decisions.
    Used for offline analysis and continuous improvement.
    Does NOT affect real-time gate decisions.
    """
    record = FeedbackRecord(
        trace_id=req.trace_id,
        gate_decision=req.gate_decision,
        human_decision=req.human_decision,
        reason_code=req.reason_code,
        timestamp=get_iso_timestamp(),
        notes=req.notes,
        context=req.context
    )

    success = await save_feedback(record)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to save feedback")

    return {"status": "ok", "message": "Feedback recorded"}

def get_iso_timestamp():
    """Helper to get ISO timestamp"""
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
