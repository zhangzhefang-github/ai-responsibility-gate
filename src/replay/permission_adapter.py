"""
Permission Case Adapter.

Case round -> permission Signal -> project_signals via EvidenceProvider.
Reuses merge/round logic from pr_loop_adapter.
"""
from typing import List

from ..core.models import DecisionRequest
from ..signals.models import Signal
from ..evidence.provider_registry import ProviderRegistry
from ..evidence.permission_provider import PermissionEvidenceProvider

from .pr_loop_adapter import (
    _merge_risk_level,
    _governance_evidence_to_project_signals,
)

_PERMISSION_REGISTRY: ProviderRegistry | None = None


def _get_permission_registry() -> ProviderRegistry:
    global _PERMISSION_REGISTRY
    if _PERMISSION_REGISTRY is None:
        _PERMISSION_REGISTRY = ProviderRegistry()
        _PERMISSION_REGISTRY.register(PermissionEvidenceProvider())
    return _PERMISSION_REGISTRY


def scope_request_to_signal(scope: str) -> Signal:
    """Build permission Signal from scope_request."""
    return Signal(
        domain="permission",
        signal_type="scope_request",
        payload={"scope": scope.strip().lower() if scope else ""},
    )


def permission_signals_to_project_signals(signals: List[Signal]) -> List[str]:
    """Signal -> PermissionEvidenceProvider -> project_signals for Gate."""
    registry = _get_permission_registry()
    evidence_list = registry.evaluate_all(signals)
    merged_risk = _merge_risk_level(evidence_list)
    return _governance_evidence_to_project_signals(merged_risk)


def permission_round_to_decision_request(
    round_data: dict,
    case_id: str,
    round_index: int,
    project_signals: List[str],
    verbose: bool = False,
) -> DecisionRequest:
    """Build DecisionRequest for permission round (no loop_state)."""
    loop_state = round_data.get("loop_state") or {}
    if not isinstance(loop_state, dict):
        loop_state = {}
    return DecisionRequest(
        text="permission_replay",
        structured_input={"signals": project_signals},
        context={"loop_state": loop_state},
        debug=False,
        verbose=verbose,
    )
