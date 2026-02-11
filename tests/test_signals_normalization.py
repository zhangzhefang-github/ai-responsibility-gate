import pytest

from examples.pr_gate_ai_review_loop.signal_validation import normalize_signals


@pytest.mark.parametrize(
    "raw, expected",
    [
        (["LOW_VALUE_NITS", "LOW_VALUE_NITS"], ["LOW_VALUE_NITS"]),
        (["", "  ", None, 123], []),
        (["UNKNOWN_SIGNAL"], ["UNKNOWN_SIGNAL"]),
    ],
)
def test_normalize_signals_basic_cases(raw, expected):
    assert normalize_signals(raw) == expected


def test_normalize_signals_unknown_mapped_to_unknown_signal():
    raw = ["LOW_VALUE_NITS", "NOT_IN_ALLOWLIST", "BUG_RISK"]
    normalized = normalize_signals(raw)

    # 必须去重 + 排序
    assert normalized == sorted(set(normalized))

    # 未知 signal 必须被映射为 UNKNOWN_SIGNAL
    assert "UNKNOWN_SIGNAL" in normalized
    assert "NOT_IN_ALLOWLIST" not in normalized


def test_normalize_signals_filters_non_string_and_empty():
    raw = ["LOW_VALUE_NITS", None, "", "  ", 42]
    normalized = normalize_signals(raw)

    assert "LOW_VALUE_NITS" in normalized
    assert "" not in normalized
    assert "  " not in normalized

