import json
import time
from pathlib import Path
from datetime import datetime
from typing import Optional
from pydantic import BaseModel

FEEDBACK_FILE = Path("data/feedback.jsonl")

class FeedbackRecord(BaseModel):
    trace_id: str
    gate_decision: str
    human_decision: str
    reason_code: str
    timestamp: str
    notes: Optional[str] = None
    context: Optional[dict] = None

def ensure_feedback_dir():
    """Ensure feedback directory exists"""
    FEEDBACK_FILE.parent.mkdir(parents=True, exist_ok=True)

async def save_feedback(record: FeedbackRecord) -> bool:
    """Save feedback record to jsonl file"""
    try:
        ensure_feedback_dir()
        with open(FEEDBACK_FILE, "a", encoding="utf-8") as f:
            f.write(record.model_dump_json() + "\n")
        return True
    except Exception as e:
        print(f"[ERROR] Failed to save feedback: {e}")
        return False

def load_recent_feedback(limit: int = 100) -> list:
    """Load recent feedback records for analysis"""
    if not FEEDBACK_FILE.exists():
        return []

    records = []
    with open(FEEDBACK_FILE, "r", encoding="utf-8") as f:
        for line in f:
            try:
                record = json.loads(line.strip())
                records.append(record)
            except Exception:
                continue

    return records[-limit:]
