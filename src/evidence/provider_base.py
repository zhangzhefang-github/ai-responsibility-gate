"""
Evidence Provider Framework - Base Interface.

EvidenceProvider: plugin interface for Signal → GovernanceEvidence.
"""
from abc import ABC, abstractmethod

from ..signals.models import Signal
from .provider_models import GovernanceEvidence


class EvidenceProvider(ABC):
    """Plugin interface. Providers evaluate Signal and return GovernanceEvidence."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider identifier."""
        ...

    def supports(self, signal: Signal) -> bool:
        """Whether this provider can evaluate the given signal."""
        raise NotImplementedError

    @abstractmethod
    def evaluate(self, signal: Signal) -> GovernanceEvidence:
        """Evaluate signal and return governance evidence."""
        ...
