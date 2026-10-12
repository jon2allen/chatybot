"""
Base Policy Engine Interface
Abstract interface for security policy evaluators.
"""

from abc import ABC, abstractmethod
from typing import Any
from chatybot.security.models import PolicyDecision, PolicyRequest


class BasePolicyEngine(ABC):
    """Abstract base class for all security policy evaluation engines."""

    @abstractmethod
    def evaluate(self, request: PolicyRequest) -> PolicyDecision:
        """Evaluate a tool request and return a tri-state PolicyDecision."""
        raise NotImplementedError
