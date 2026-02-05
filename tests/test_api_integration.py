import pytest
import json
from pathlib import Path
from fastapi.testclient import TestClient
from src.api import app

CASES_DIR = Path("cases")

@pytest.fixture
def client():
    return TestClient(app)

def test_decision_smoke(client):
    case_file = CASES_DIR / "allow_basic_info.json"
    with open(case_file, encoding="utf-8") as f:
        case = json.load(f)

    turn = case["turns"][0]
    input_data = turn["input"]

    response = client.post(
        "/decision",
        json={
            "text": input_data["text"],
            "debug": False
        }
    )

    assert response.status_code == 200

    data = response.json()
    assert "request_id" in data
    assert "responsibility_type" in data
    assert "decision" in data
    assert "primary_reason" in data
    assert "suggested_action" in data
    assert "explanation" in data
    assert "trigger_spans" in data["explanation"]
    assert "latency_ms" in data
    assert data["policy"]["rules_fired"] is None

def test_decision_debug_mode(client):
    response = client.post(
        "/decision",
        json={
            "text": "产品保本吗",
            "debug": True
        }
    )

    assert response.status_code == 200
    data = response.json()
    assert data["policy"]["rules_fired"] is not None
    assert isinstance(data["policy"]["rules_fired"], list)
