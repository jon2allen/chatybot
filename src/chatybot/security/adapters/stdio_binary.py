"""
Stdio Binary Policy Engine Adapter
Communicates with an external binary or executable script via stdin/stdout using JSON.
"""

import json
import subprocess
from typing import Any
from chatybot.security.base import BasePolicyEngine
from chatybot.security.models import (
    PolicyDecision,
    PolicyPromptDetails,
    PolicyRequest,
    Verdict,
)


class StdioBinaryPolicyEngine(BasePolicyEngine):
    """External binary adapter communicating over stdin/stdout."""

    def __init__(
        self,
        binary_path: str,
        timeout_seconds: float = 2.0,
        fail_safe: str = "deny",
        args: list[str] | None = None,
    ):
        self.binary_path = binary_path
        self.timeout_seconds = timeout_seconds
        self.fail_safe = Verdict(fail_safe)
        self.args = args or []

    def evaluate(self, request: PolicyRequest) -> PolicyDecision:
        payload = request.to_dict()
        cmd = [self.binary_path] + self.args

        try:
            proc = subprocess.run(
                cmd,
                input=json.dumps(payload),
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
                check=False,
            )
            if proc.returncode != 0:
                return PolicyDecision(
                    verdict=self.fail_safe,
                    reason=f"External policy binary exited with code {proc.returncode}: {proc.stderr.strip()}",
                )

            stdout_str = proc.stdout.strip()
            if not stdout_str:
                return PolicyDecision(
                    verdict=self.fail_safe,
                    reason="External policy binary produced empty output.",
                )

            data = json.loads(stdout_str)
            status_str = data.get("status", self.fail_safe.value).lower()
            verdict = Verdict(status_str)

            prompt_data = data.get("prompt_details")
            prompt_details = None
            if prompt_data and isinstance(prompt_data, dict):
                prompt_details = PolicyPromptDetails(
                    title=prompt_data.get("title", "Permission Request"),
                    message=prompt_data.get("message", "Authorize action?"),
                    risk_level=prompt_data.get("risk_level", "medium"),
                )

            return PolicyDecision(
                verdict=verdict,
                reason=data.get("reason", "Evaluated by external binary"),
                prompt_details=prompt_details,
                modified_parameters=data.get("modified_parameters"),
            )

        except subprocess.TimeoutExpired:
            return PolicyDecision(
                verdict=self.fail_safe,
                reason=f"External policy evaluation timed out after {self.timeout_seconds}s. Failing safe to {self.fail_safe.value}.",
            )
        except (json.JSONDecodeError, Exception) as exc:
            return PolicyDecision(
                verdict=self.fail_safe,
                reason=f"External policy evaluation failed ({type(exc).__name__}: {exc}). Failing safe to {self.fail_safe.value}.",
            )
