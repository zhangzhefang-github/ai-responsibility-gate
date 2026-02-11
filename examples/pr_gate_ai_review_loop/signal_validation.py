"""
Signal validation and normalization utilities for PR Gate demo.

Phase E goal:
- Keep the set of signals finite, auditable, and controllable.
- Ensure all signals passed into core/evidence come from an allowlist
  (or are mapped to UNKNOWN_SIGNAL).
"""
from __future__ import annotations

from pathlib import Path
from typing import List, Set

import yaml

_ROOT = Path(__file__).parent
_CATALOG_PATH = _ROOT / "signals_catalog.yaml"


def load_signal_allowlist() -> Set[str]:
    """Load the signal names from signals_catalog.yaml as an allowlist."""
    with open(_CATALOG_PATH, encoding="utf-8") as f:
        data = yaml.safe_load(f)

    items = data.get("signals", []) or []
    names = {item.get("name") for item in items if isinstance(item, dict) and item.get("name")}
    return names


def normalize_signals(raw: List[object]) -> List[str]:
    """
    Normalize a raw list of signals into a deterministic, allowlisted form.

    Rules:
    1) Filter only non-empty strings.
    2) Map any signal not in allowlist to "UNKNOWN_SIGNAL".
    3) De-duplicate and sort for determinism.
    """
    allowlist = load_signal_allowlist()
    normalized: Set[str] = set()

    for s in raw:
        if not isinstance(s, str):
            continue
        value = s.strip()
        if not value:
            continue
        if value not in allowlist:
            value = "UNKNOWN_SIGNAL"
        normalized.add(value)

    return sorted(normalized)


def assert_signals_allowlisted(raw: List[object]) -> None:
    """
    Assert that all string signals are within the allowlist (after normalization).
    Useful for stricter modes or tests.
    """
    normalized = normalize_signals(raw)
    allowlist = load_signal_allowlist()

    for s in normalized:
        if s not in allowlist:
            raise AssertionError(f"Signal '{s}' is not in allowlist")

