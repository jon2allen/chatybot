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
        debug: bool = False,
    ):
        self.binary_path = binary_path
        self.timeout_seconds = timeout_seconds
        self.fail_safe = Verdict(fail_safe)
        self.args = list(args or [])
        self.debug = debug
        self._banner_cache: str | None = None

    def _fail_safe_decision(self, reason: str) -> PolicyDecision:
        return PolicyDecision(verdict=self.fail_safe, reason=reason)

    def evaluate(self, request: PolicyRequest) -> PolicyDecision:
        if self.debug and "debug" not in request.context:
            request.context["debug"] = True

        payload = request.to_dict()
        cmd = [self.binary_path] + self.args
        if self.debug and "--debug" not in cmd and "-d" not in cmd:
            cmd.append("--debug")

        try:
            proc = subprocess.run(
                cmd,
                input=json.dumps(payload),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=self.timeout_seconds,
                check=False,
            )
            if self.debug and proc.stderr:
                for line in proc.stderr.strip().splitlines():
                    print(f"[Security Debug] [External Binary] {line}")

            if proc.returncode != 0:
                stderr_snippet = (proc.stderr or "").strip()[:500]
                return self._fail_safe_decision(
                    f"External policy binary exited with code {proc.returncode}: {stderr_snippet}"
                )
            stdout_str = (proc.stdout or "").strip()
            if not stdout_str:
                return self._fail_safe_decision(
                    "External policy binary produced empty output."
                )
            try:
                data = json.loads(stdout_str)
            except json.JSONDecodeError as exc:
                return self._fail_safe_decision(
                    f"External policy binary produced invalid JSON ({exc})."
                )
            if not isinstance(data, dict):
                return self._fail_safe_decision(
                    "External policy binary response was not a JSON object."
                )
            status_raw = data.get("status", self.fail_safe.value)
            if not isinstance(status_raw, str):
                return self._fail_safe_decision(
                    f"External policy binary returned non-string status ({status_raw!r})."
                )
            try:
                verdict = Verdict(status_raw.lower())
            except ValueError:
                return self._fail_safe_decision(
                    f"External policy binary returned unknown status '{status_raw}'."
                )
            reason_raw = data.get("reason", "Evaluated by external binary")
            reason = reason_raw if isinstance(reason_raw, str) else str(reason_raw)
            prompt_details = None
            if verdict == Verdict.ASK:
                prompt_data = data.get("prompt_details") or {}
                if not isinstance(prompt_data, dict):
                    prompt_data = {}
                prompt_details = PolicyPromptDetails(
                    title=prompt_data.get("title", "Permission Request"),
                    message=prompt_data.get("message", "Authorize action?"),
                    risk_level=prompt_data.get("risk_level", "medium"),
                )
            modified_parameters = data.get("modified_parameters")
            if modified_parameters is not None and not isinstance(modified_parameters, dict):
                return self._fail_safe_decision(
                    "External policy binary returned non-object modified_parameters."
                )
            return PolicyDecision(
                verdict=verdict,
                reason=reason,
                prompt_details=prompt_details,
                modified_parameters=modified_parameters,
            )
        except subprocess.TimeoutExpired:
            return self._fail_safe_decision(
                f"External policy evaluation timed out after {self.timeout_seconds}s. Failing safe to {self.fail_safe.value}."
            )
        except (OSError, json.JSONDecodeError) as exc:
            return self._fail_safe_decision(
                f"External policy evaluation failed ({type(exc).__name__}: {exc}). Failing safe to {self.fail_safe.value}."
            )

    def evaluate_output(self, request: PolicyRequest) -> PolicyDecision:
        """Evaluate a tool invocation's output using the external binary."""
        return self.evaluate(request)

    def get_banner(self) -> str:
        """Query the external binary with --banner to retrieve its identification banner.

        The result is cached after the first call to avoid spawning a subprocess
        on every banner query (e.g. once at startup and once per --security debug session).
        """
        if self._banner_cache is not None:
            return self._banner_cache
        cmd = [self.binary_path] + self.args + ["--banner"]
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=1.5,
                check=False,
            )
            if proc.returncode == 0 and proc.stdout.strip():
                self._banner_cache = proc.stdout.strip()
                return self._banner_cache
        except Exception:
            pass
        import os
        self._banner_cache = f"Binary: {os.path.basename(self.binary_path)}"
        return self._banner_cache

