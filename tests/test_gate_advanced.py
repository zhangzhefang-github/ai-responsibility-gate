import pytest
import asyncio
from pathlib import Path
from src.core.models import DecisionRequest, Decision, ClassifierResult, ResponsibilityType
from src.core.gate import decide

CASES_DIR = Path("cases")

@pytest.mark.asyncio
async def test_low_confidence_tightening(monkeypatch):
    from src.core import gate

    async def low_conf_classifier(text):
        return ClassifierResult(
            type=ResponsibilityType.Information,
            confidence=0.5,
            trigger_spans=["low_conf"]
        )

    monkeypatch.setattr(gate, "classify", low_conf_classifier)

    req = DecisionRequest(text="普通查询", debug=False)
    resp = await decide(req, "matrices/v0.1.yaml")

    assert "CLASSIFIER_LOW_CONFIDENCE" in resp.primary_reason

@pytest.mark.asyncio
async def test_debug_flag_switch():
    req_debug = DecisionRequest(text="产品收益率", debug=True)
    resp_debug = await decide(req_debug, "matrices/v0.1.yaml")

    assert resp_debug.policy.rules_fired is not None
    assert isinstance(resp_debug.policy.rules_fired, list)

    req_no_debug = DecisionRequest(text="产品收益率", debug=False)
    resp_no_debug = await decide(req_no_debug, "matrices/v0.1.yaml")

    assert resp_no_debug.policy.rules_fired is None

@pytest.mark.asyncio
async def test_replay_diff_smoke(monkeypatch, tmp_path):
    import sys

    test_args = [
        "--base", "matrices/v0.1.yaml",
        "--cand", "matrices/v0.2.yaml",
        "--cases", "cases/"
    ]

    monkeypatch.setattr(sys, "argv", ["diff"] + test_args)

    from src.replay import diff
    original_path = diff.REPORT_PATH
    diff.REPORT_PATH = tmp_path / "test_diff_report.md"

    try:
        await diff.main()

        content = (tmp_path / "test_diff_report.md").read_text(encoding="utf-8")
        assert "decision_change_rate" in content
        assert "False Accept" in content or "False Reject" in content
    finally:
        diff.REPORT_PATH = original_path
