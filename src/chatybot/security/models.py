"""
Security Models
Defines data structures and enums for the pluggable tri-state security engine.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any
import uuid
from datetime import datetime, timezone


class Verdict(str, Enum):
    """Tri-state policy verdict."""
    ALLOW = "allow"
    DENY = "deny"
    ASK = "ask"


@dataclass
class PolicyPromptDetails:
    """UI presentation metadata when verdict is ASK."""
    title: str = "Permission Required"
    message: str = "Authorize tool execution?"
    risk_level: str = "medium"  # "low", "medium", "high", "critical"

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "message": self.message,
            "risk_level": self.risk_level,
        }


@dataclass
class PolicyRequest:
    """Protocol request sent to a policy evaluation engine."""
    tool: str
    parameters: dict[str, Any] = field(default_factory=dict)
    context: dict[str, Any] = field(default_factory=dict)
    version: str = "1.0"
    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = field(default_factory=lambda: datetime.now(tz=timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "request_id": self.request_id,
            "timestamp": self.timestamp,
            "tool": self.tool,
            "parameters": self.parameters,
            "context": self.context,
        }


@dataclass
class PolicyDecision:
    """Verdict result from a policy engine."""
    verdict: Verdict
    reason: str = ""
    prompt_details: PolicyPromptDetails | None = None
    modified_parameters: dict[str, Any] | None = None
    duration_ms: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "status": self.verdict.value,
            "reason": self.reason,
            "duration_ms": self.duration_ms,
        }
        if self.prompt_details:
            d["prompt_details"] = self.prompt_details.to_dict()
        if self.modified_parameters is not None:
            d["modified_parameters"] = self.modified_parameters
        return d
