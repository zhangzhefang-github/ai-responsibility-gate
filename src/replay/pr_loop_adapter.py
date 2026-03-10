"""
PR Loop Real Case Adapter.

Maps PR-domain signals to project-recognized signals (signals_catalog).
Converts case rounds to DecisionRequest for core_decide.
"""
from typing import List

from ..core.models import DecisionRequest

# PR signal -> project signal (signals_catalog names)
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
