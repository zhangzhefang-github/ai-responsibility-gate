"""
Evidence Provider Framework - PermissionEvidenceProvider.

Maps permission-domain scope_request to risk_level for Gate consumption.
"""
from ..signals.models import Signal
from .provider_models import GovernanceEvidence
from .provider_base import EvidenceProvider

# scope -> (risk_level, scope_level)
SCOPE_EVIDENCE_MAP = {
    "read": ("R0", "READ"),
    "write": ("R2", "WRITE"),
    "admin": ("R3", "ADMIN"),
}


class PermissionEvidenceProvider(EvidenceProvider):
    """Permission domain: scope_request -> risk_level, scope_level."""

    @property
    def name(self) -> str:
        return "permission"

    def supports(self, signal: Signal) -> bool:
        return signal.domain == "permission"

    def evaluate(self, signal: Signal) -> GovernanceEvidence:
        scope = (signal.payload or {}).get("scope", "")
        if isinstance(scope, str):
            scope = scope.strip().lower()
        risk_level, scope_level = SCOPE_EVIDENCE_MAP.get(scope, ("R1", "UNKNOWN"))

        action_type = scope_level if scope_level != "UNKNOWN" else "READ"
        return GovernanceEvidence(
            risk_level=risk_level,
            scope_level=scope_level,
            action_type=action_type,
            provider=self.name,
        )
