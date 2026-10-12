"""
Security Manager Module
Coordinates configuration loading, engine selection, and policy evaluation.
Configuration is loaded from ~/.config/chatybot/security.toml (outside tools_config and chat_config).
"""

import os
from typing import Any
import tomllib

from chatybot.security.base import BasePolicyEngine
from chatybot.security.builtin import BuiltinPolicyEngine
from chatybot.security.adapters.stdio_binary import StdioBinaryPolicyEngine
from chatybot.security.models import PolicyDecision, PolicyRequest, Verdict


class SecurityManager:
    """Manages policy engine initialization, configuration parsing, and evaluation."""

    DEFAULT_CONFIG_PATH = "~/.config/chatybot/security.toml"

    def __init__(self, config_path: str | None = None, enabled: bool = True):
        self.enabled = enabled
        self.config_path = os.path.abspath(
            os.path.expanduser(config_path or self.DEFAULT_CONFIG_PATH)
        )
        self.config: dict[str, Any] = {}
        self.engine: BasePolicyEngine = BuiltinPolicyEngine()
        self.fail_safe = Verdict.DENY

        if self.enabled:
            self._load_config_and_initialize()

    def _load_config_and_initialize(self) -> None:
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "rb") as f:
                    self.config = tomllib.load(f)
            except Exception as e:
                # Log warning and fall back to built-in default engine
                self.config = {}

        self.fail_safe = Verdict(self.config.get("fail_safe", "deny"))
        engine_type = self.config.get("engine", "builtin").lower()

        if engine_type == "binary":
            bin_cfg = self.config.get("binary", {})
            raw_path = bin_cfg.get("path", "")
            bin_path = os.path.abspath(os.path.expanduser(raw_path)) if raw_path else ""
            if bin_path and os.path.exists(bin_path):
                self.engine = StdioBinaryPolicyEngine(
                    binary_path=bin_path,
                    timeout_seconds=float(bin_cfg.get("timeout_seconds", 2.0)),
                    fail_safe=self.fail_safe.value,
                    args=bin_cfg.get("args", []),
                )
                return
            # If binary not found, fallback to builtin engine with a warning
            engine_type = "builtin"

        # Default to builtin
        builtin_cfg = self.config.get("builtin", {})
        self.engine = BuiltinPolicyEngine(
            rules=builtin_cfg.get("rules"),
            dsl_rules=builtin_cfg.get("dsl_rules") or builtin_cfg.get("rules_dsl"),
            default_verdict=builtin_cfg.get("default_verdict", "ask"),
            denied_paths=builtin_cfg.get("path_restrictions", {}).get("denied_paths"),
            denied_command_patterns=builtin_cfg.get("command_rules", {}).get("denied_patterns"),
        )

    def evaluate(
        self,
        tool: str,
        parameters: dict[str, Any] | None = None,
        context: dict[str, Any] | None = None,
    ) -> PolicyDecision:
        """Evaluate a tool invocation against the active policy engine."""
        if not self.enabled:
            return PolicyDecision(verdict=Verdict.ALLOW, reason="Security evaluation disabled.")

        req = PolicyRequest(
            tool=tool,
            parameters=parameters or {},
            context=context or {},
        )
        try:
            return self.engine.evaluate(req)
        except Exception as exc:
            return PolicyDecision(
                verdict=self.fail_safe,
                reason=f"Security manager evaluation failed ({exc}). Failing safe to {self.fail_safe.value}.",
            )
