import pytest
import asyncio
from pathlib import Path
from src.core.models import DecisionRequest
from src.core.gate import decide

CASES_DIR = Path("cases")

@pytest.mark.asyncio
async def test_cases_with_v01():
    case_files = list(CASES_DIR.glob("*.json"))

    for cf in case_files:
        with open(cf, encoding="utf-8") as f:
            import json
            case = json.load(f)

        if "turns" in case:
            turns = case["turns"]
        else:
            input_data = case["input"]
            expected = case["expected"]["decision"]
            turns = [{"input": input_data, "expected_decision": expected}]

        for turn in turns:
            input_data = turn["input"]
            expected = turn.get("expected_decision") or turn.get("expected", {}).get("decision")

            req = DecisionRequest(
                session_id=input_data.get("session_id"),
                user_id=input_data.get("user_id"),
                text=input_data["text"],
                debug=input_data.get("debug", False),
                context=input_data.get("context")
            )

            resp = await decide(req, "matrices/v0.1.yaml")

            assert resp.decision.value == expected, (
                f"Case {case['case_id']}: expected {expected}, got {resp.decision.value}"
            )
