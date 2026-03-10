"""
Evidence Provider Framework - RiskProvider.

Maps PR-domain signal types to risk_level for Gate consumption.
"""
from ..signals.models import Signal
from .provider_models import GovernanceEvidence
from .provider_base import EvidenceProvider

# signal_type -> risk_level (R0=benign, R1=low, R2=medium, R3=high)
PR_SIGNAL_RISK_MAP = {
    "review_bug": "R2",
    "ci_failure": "R2",
    "maintainer_intervention": "R3",
    "nit_only": "R0",
    "unknown": "R1",
}


class RiskProvider(EvidenceProvider):
    """PR domain: signal_type → risk_level."""

    @property
    def name(self) -> str:
        return "risk"

    def supports(self, signal: Signal) -> bool:
        return signal.domain == "pr"

    def evaluate(self, signal: Signal) -> GovernanceEvidence:
        risk_level = PR_SIGNAL_RISK_MAP.get(signal.signal_type, "R1")
        return GovernanceEvidence(
            risk_level=risk_level,
            action_type="READ",
            provider=self.name,
        )
