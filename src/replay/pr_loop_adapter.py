"""
PR Loop Real Case Adapter.

Signal Layer: PR-domain signals → Signal(domain, signal_type, payload).
Legacy: PR-domain signals → project signals (signals_catalog) for backward compat.
Converts case rounds to DecisionRequest for core_decide.
"""
from typing import List

from ..core.models import DecisionRequest
from ..signals.models import Signal
from ..evidence.provider_registry import ProviderRegistry
from ..evidence.risk_provider import RiskProvider

# PR signal -> Signal Layer (domain, signal_type)
PR_SIGNAL_TO_SIGNAL_TYPE = {
    "FUNCTIONAL_CORRECTNESS": "review_bug",
    "REVIEW_LOGIC_BUG": "review_bug",
    "TEST_MISSING": "review_bug",
    "CI_FAILURE": "ci_failure",
    "HUMAN_OVERRIDE": "maintainer_intervention",
    "MAINTAINER_INTERVENTION": "maintainer_intervention",
    "LOW_VALUE_NITS": "nit_only",
}

# PR signal -> project signal (signals_catalog names) - legacy
PR_SIGNAL_MAP = {
    "FUNCTIONAL_CORRECTNESS": "BUG_RISK",
    "REVIEW_LOGIC_BUG": "BUG_RISK",
    "TEST_MISSING": "BUG_RISK",
    "CI_FAILURE": "BUG_RISK",
    "HUMAN_OVERRIDE": "BUILD_CHAIN",
    "MAINTAINER_INTERVENTION": "BUILD_CHAIN",
}

PROJECT_SIGNALS_ALLOWLIST = frozenset(
    {"SECURITY_BOUNDARY", "BUILD_CHAIN", "BUG_RISK", "LOW_VALUE_NITS", "UNKNOWN_SIGNAL", "MULTI_SIGNAL"}
)


def map_pr_signals_to_signals(
    pr_signals: List[str],
    maintainer_intervened: bool = False,
    ci_status: str | None = None,
) -> List[Signal]:
    """
    Map PR-domain signals to Signal Layer.

    - pr_signals: signals from case round
    - maintainer_intervened: if True, inject maintainer_intervention signal
    - ci_status: optional, reserved for future use

    Returns:
        List[Signal] for EvidenceProvider consumption.
    """
    result: List[Signal] = []
    seen: set[str] = set()
    for s in pr_signals or []:
        if not isinstance(s, str) or not s.strip():
            continue
        signal_type = PR_SIGNAL_TO_SIGNAL_TYPE.get(s.strip(), "unknown")
        if signal_type not in seen:
            seen.add(signal_type)
            result.append(Signal(domain="pr", signal_type=signal_type, payload={}))

    if maintainer_intervened and "maintainer_intervention" not in seen:
        result.append(Signal(domain="pr", signal_type="maintainer_intervention", payload={}))

    return result if result else [Signal(domain="pr", signal_type="unknown", payload={})]


def map_pr_signals_to_project_signals(
    pr_signals: List[str],
    maintainer_intervened: bool = False,
    ci_status: str | None = None,
) -> List[str]:
    """
    Map PR-domain signals to project-recognized signals.

    - pr_signals: signals from case round
    - maintainer_intervened: if True, inject BUILD_CHAIN to trigger HITL
    - ci_status: optional, reserved for future use

    Returns:
        Mapped signals, all from signals_catalog. Sorted, deduplicated.
    """
    result: set[str] = set()
    for s in pr_signals or []:
        if not isinstance(s, str) or not s.strip():
            continue
        mapped = PR_SIGNAL_MAP.get(s.strip(), "UNKNOWN_SIGNAL")
        if mapped in PROJECT_SIGNALS_ALLOWLIST:
            result.add(mapped)
        else:
            result.add("UNKNOWN_SIGNAL")

    if maintainer_intervened:
        result.add("BUILD_CHAIN")

    return sorted(result) if result else ["UNKNOWN_SIGNAL"]


RISK_ORDER = {"R0": 0, "R1": 1, "R2": 2, "R3": 3}


def _merge_risk_level(evidence_list: list) -> str:
    """Take highest risk_level from evidence list."""
    levels = [e.risk_level for e in evidence_list if e.risk_level]
    if not levels:
        return "R1"
    return max(levels, key=lambda L: RISK_ORDER.get(L, 0))


def _governance_evidence_to_project_signals(risk_level: str | None) -> List[str]:
    """Map GovernanceEvidence.risk_level to project signals for Gate's risk.py."""
    if risk_level == "R3":
        return ["BUILD_CHAIN"]
    if risk_level == "R2":
        return ["BUG_RISK"]
    if risk_level == "R0":
        return ["LOW_VALUE_NITS"]
    return ["UNKNOWN_SIGNAL"]


# Default registry with RiskProvider for PR replay
_default_registry: ProviderRegistry | None = None


def _get_registry() -> ProviderRegistry:
    global _default_registry
    if _default_registry is None:
        _default_registry = ProviderRegistry()
        _default_registry.register(RiskProvider())
    return _default_registry


def signals_to_project_signals_via_evidence(signals: List[Signal]) -> List[str]:
    """
    Signal → EvidenceProvider → project signals for Gate.
    Uses ProviderRegistry.evaluate_all, merges risk_level, maps to Gate format.
    """
    registry = _get_registry()
    evidence_list = registry.evaluate_all(signals)
    merged_risk = _merge_risk_level(evidence_list)
    return _governance_evidence_to_project_signals(merged_risk)


def round_to_decision_request(
    round_data: dict,
    case_id: str,
    round_index: int,
    project_signals: List[str],
    verbose: bool = False,
) -> DecisionRequest:
    """
    Build DecisionRequest from a case round.

    - round_data: round dict (loop_state, signals, etc.)
    - case_id: case identifier
    - round_index: 0-based round index
    - project_signals: already-mapped signals (from map_pr_signals_to_project_signals)
    - verbose: pass through to request

    Returns:
        DecisionRequest ready for core_decide
    """
    loop_state = round_data.get("loop_state") or {}
    if not isinstance(loop_state, dict):
        loop_state = {}

    req = DecisionRequest(
        text="pr_loop_replay",
        structured_input={"signals": project_signals},
        context={"loop_state": loop_state},
        debug=False,
        verbose=verbose,
    )
    return req
