"""
Security Manager Module
Coordinates configuration loading, engine selection, and policy evaluation.
Configuration is loaded from ~/.config/chatybot/security.toml (outside tools_config and chat_config).
"""

import logging
import os
import shutil
from typing import Any
import tomllib

from chatybot.security.base import BasePolicyEngine
from chatybot.security.builtin import BuiltinPolicyEngine
from chatybot.security.adapters.stdio_binary import StdioBinaryPolicyEngine
from chatybot.security.models import PolicyDecision, PolicyRequest, Verdict

logger = logging.getLogger(__name__)


class SecurityManager:
    """Manages policy engine initialization, configuration parsing, and evaluation."""

    DEFAULT_CONFIG_PATH = "~/.config/chatybot/security.toml"

    def __init__(self, config_path: str | None = None, enabled: bool = True, debug: bool = False):
        self.enabled = enabled
        self.debug = debug
        self.config_path = os.path.abspath(
            os.path.expanduser(config_path or self.DEFAULT_CONFIG_PATH)
        )
        self.config: dict[str, Any] = {}
        self.fail_safe = Verdict.DENY
        self.non_interactive_ask: str = "deny"
        self.engine: BasePolicyEngine | None = None

        if self.enabled:
            self._load_config_and_initialize()

    def _load_config_and_initialize(self) -> None:
        bundled_default = os.path.join(os.path.dirname(__file__), "default_security.toml")

        # First run seed: if user config does not exist, copy from bundled default template
        if not os.path.exists(self.config_path):
            try:
                os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
                if os.path.exists(bundled_default):
                    shutil.copy2(bundled_default, self.config_path)
                    print(f"[Security Sync] Initialized local 'security.toml' at '{self.config_path}'")
                    logger.info("[Security Sync] Initialized local security policy at '%s'", self.config_path)
            except Exception as e:
                logger.warning("[Security Sync] Could not seed default security policy to '%s': %s", self.config_path, e)

        config_to_load = self.config_path if os.path.exists(self.config_path) else bundled_default

        if os.path.exists(config_to_load):
            try:
                with open(config_to_load, "rb") as f:
                    self.config = tomllib.load(f)
            except Exception as e:
                logger.warning(
                    "[Security Config] Failed to parse security policy file '%s': %s. Falling back to defaults.",
                    config_to_load,
                    e,
                )
                if self.debug:
                    print(f"[Security Warning] Failed to parse security policy file '{config_to_load}': {e}. Falling back to defaults.")
                self.config = {}

        raw_fail_safe = str(self.config.get("fail_safe", "deny")).strip().lower()
        try:
            self.fail_safe = Verdict(raw_fail_safe)
        except ValueError:
            self.fail_safe = Verdict.DENY

        raw_non_interactive = str(self.config.get("non_interactive_ask", "deny")).strip().lower()
        self.non_interactive_ask = "allow" if raw_non_interactive == "allow" else "deny"

        engine_type = self.config.get("engine", "builtin").lower()

        if self.debug:
            print(f"[Security Debug] Loading security configuration from '{config_to_load}'...")
            print(f"[Security Debug] Engine type: '{engine_type}', Fail-safe verdict: '{self.fail_safe.value.upper()}'.")

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
                    debug=self.debug,
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
            debug=self.debug,
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

        ctx = dict(context or {})
        if self.debug and "debug" not in ctx:
            ctx["debug"] = True

        req = PolicyRequest(
            tool=tool,
            parameters=parameters or {},
            context=ctx,
        )
        try:
            return self.engine.evaluate(req)
        except Exception as exc:
            return PolicyDecision(
                verdict=self.fail_safe,
                reason=f"Security manager evaluation failed ({exc}). Failing safe to {self.fail_safe.value}.",
            )
