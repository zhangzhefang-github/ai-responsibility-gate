import pytest
from src.core.postcheck import postcheck

def test_only_suggest_missing_disclaimer():
    result = postcheck("some text", requires_disclaimer=True, is_input=False)
    assert not result.passed
    assert any(i.code == "MISSING_DISCLAIMER" for i in result.issues)

def test_guarantee_keyword_in_text():
    result = postcheck("这个产品保本", requires_disclaimer=False, is_input=False)
    assert not result.passed
    assert any(i.code == "GUARANTEE_KEYWORD_IN_TEXT" for i in result.issues)

def test_postcheck_passed():
    text_with_disclaimer = "some text\n仅供参考，不构成任何承诺或投资建议。"
    result = postcheck(text_with_disclaimer, requires_disclaimer=True, is_input=False)
    assert result.passed
