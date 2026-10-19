"""
Base Policy Engine Interface
Abstract interface for security policy evaluators.
"""

from abc import ABC, abstractmethod
from typing import Any
from chatybot.security.models import PolicyDecision, PolicyRequest, Verdict


class BasePolicyEngine(ABC):
    """Abstract base class for all security policy evaluation engines."""

    @abstractmethod
    def evaluate(self, request: PolicyRequest) -> PolicyDecision:
        """Evaluate a tool request and return a tri-state PolicyDecision."""
        raise NotImplementedError

    def supports_output_evaluation(self) -> bool:
        """Return True if this engine explicitly implements output screening."""
        return type(self).evaluate_output is not BasePolicyEngine.evaluate_output

    def evaluate_output(self, request: PolicyRequest) -> PolicyDecision:
        """Evaluate a tool's output after I/O execution. Default allows output."""
        return PolicyDecision(verdict=Verdict.ALLOW, reason="Output allowed by default.")

    def get_banner(self) -> str:
        """Return a concise identification banner describing this engine."""
        return type(self).__name__

