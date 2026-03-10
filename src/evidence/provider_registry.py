"""
Evidence Provider Framework - Provider Registry.

ProviderRegistry: register providers, resolve by signal, evaluate.
"""
from typing import List

from ..signals.models import Signal
from .provider_models import GovernanceEvidence
from .provider_base import EvidenceProvider


class ProviderRegistry:
    """Register providers, resolve which provider handles a signal, evaluate."""

    def __init__(self) -> None:
        self._providers: List[EvidenceProvider] = []

    def register(self, provider: EvidenceProvider) -> None:
        """Register an evidence provider."""
        self._providers.append(provider)

    def resolve(self, signal: Signal) -> EvidenceProvider | None:
        """Resolve which provider supports the given signal. First match wins."""
        for p in self._providers:
            if p.supports(signal):
                return p
        return None

    def evaluate(self, signal: Signal) -> GovernanceEvidence:
        """
        Evaluate signal through the first matching provider.
        If no provider supports the signal, return minimal default evidence.
        """
        provider = self.resolve(signal)
        if provider:
            ev = provider.evaluate(signal)
            return ev.model_copy(update={"provider": provider.name})
        return GovernanceEvidence(provider="none", risk_level="R1")

    def evaluate_all(self, signals: List[Signal]) -> List[GovernanceEvidence]:
        """Evaluate multiple signals. Returns one evidence per signal."""
        return [self.evaluate(s) for s in signals]
