import pytest
import os
from pathlib import Path
from fastapi.testclient import TestClient
from src.api import app
from src.feedback.store import FEEDBACK_FILE, load_recent_feedback

client = TestClient(app)

def test_feedback_smoke():
    """Test feedback endpoint writes successfully"""
    # Clean up existing feedback file
    if FEEDBACK_FILE.exists():
        FEEDBACK_FILE.unlink()

    response = client.post("/feedback", json={
        "trace_id": "test-trace-123",
        "gate_decision": "HITL",
        "human_decision": "ALLOW",
        "reason_code": "TEST_CASE",
        "notes": "Test feedback submission"
    })

    assert response.status_code == 200
    assert response.json()["status"] == "ok"

    # Verify file was created
    assert FEEDBACK_FILE.exists()

    # Verify content
    records = load_recent_feedback(limit=10)
    assert len(records) == 1
    assert records[0]["trace_id"] == "test-trace-123"
    assert records[0]["gate_decision"] == "HITL"
    assert records[0]["human_decision"] == "ALLOW"

def test_feedback_field_validation():
    """Test feedback endpoint validates required fields"""
    response = client.post("/feedback", json={
        "gate_decision": "HITL",
        "human_decision": "ALLOW"
        # Missing: trace_id, reason_code
    })

    assert response.status_code == 422  # Validation error

def test_feedback_optional_fields():
    """Test feedback optional fields work correctly"""
    if FEEDBACK_FILE.exists():
        FEEDBACK_FILE.unlink()

    response = client.post("/feedback", json={
        "trace_id": "test-trace-456",
        "gate_decision": "ONLY_SUGGEST",
        "human_decision": "ONLY_SUGGEST",
        "reason_code": "ALIGNMENT"
        # notes and context omitted
    })

    assert response.status_code == 200

    records = load_recent_feedback(limit=10)
    assert len(records) == 1
    assert records[0]["notes"] is None
    assert records[0]["context"] is None
