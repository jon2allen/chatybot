"""
Security Manager Module
Coordinates configuration loading, engine selection, and policy evaluation.
Configuration is loaded from ~/.config/chatybot/security.toml (outside tools_config and chat_config).
"""

import dataclasses
import logging
import os
import shutil
import time
import tomllib
from typing import Any

from chatybot.tool_args import unwrap_tool_args
from chatybot.security.adapters.stdio_binary import StdioBinaryPolicyEngine
from chatybot.security.base import BasePolicyEngine
from chatybot.security.builtin import BuiltinPolicyEngine
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
        if raw_non_interactive not in ("allow", "deny"):
            warn_msg = (
                f"[Security Warning] Unsupported non_interactive_ask setting '{raw_non_interactive}' "
                "(expected 'allow' or 'deny'). Defaulting to 'deny'."
            )
            logger.warning(warn_msg)
            if self.debug:
                print(warn_msg)
        self.non_interactive_ask = "allow" if raw_non_interactive == "allow" else "deny"

        output_cfg = self.config.get("output_security", {})
        self.output_security_enabled = bool(output_cfg.get("enabled", True))
        self.output_security_tools = set(
            output_cfg.get("tools", ["read_file", "run_command", "str_search", "read_url"])
        )

        engine_type = self.config.get("engine", "builtin").lower()

        if self.debug:
            print(f"[Security Debug] Loading security configuration from '{config_to_load}'...")
            print(f"[Security Debug] Engine type: '{engine_type}', Fail-safe verdict: '{self.fail_safe.value.upper()}'.")
            print(f"[Security Debug] Output security enabled: {self.output_security_enabled} on tools: {sorted(self.output_security_tools)}")

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
                    supports_output=bool(bin_cfg.get("supports_output", False)),
                    debug=self.debug,
                )

                return
            # If binary not found, fallback to builtin engine with a prominent security warning
            warn_msg = (
                f"[Security Warning] Configured binary path not found: '{raw_path}' "
                f"(resolved: '{bin_path}'). Failing back to builtin Python policy engine."
            )
            logger.warning(warn_msg)
            print(warn_msg)
            engine_type = "builtin"
        elif engine_type != "builtin":
            warn_msg = (
                f"[Security Warning] Unsupported or unknown engine type '{engine_type}'. "
                "Falling back to builtin Python policy engine."
            )
            logger.warning(warn_msg)
            print(warn_msg)
            engine_type = "builtin"

        # Default to builtin
        builtin_cfg = self.config.get("builtin", {})
        output_rules = self.config.get("output_security", {}).get("rules") or builtin_cfg.get("output_rules")
        self.engine = BuiltinPolicyEngine(
            rules=builtin_cfg.get("rules"),
            dsl_rules=builtin_cfg.get("dsl_rules") or builtin_cfg.get("rules_dsl"),
            default_verdict=builtin_cfg.get("default_verdict", "ask"),
            denied_paths=builtin_cfg.get("path_restrictions", {}).get("denied_paths"),
            denied_command_patterns=builtin_cfg.get("command_rules", {}).get("denied_patterns"),
            output_rules=output_rules,
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
            return PolicyDecision(verdict=Verdict.ALLOW, reason="Security evaluation disabled.", duration_ms=0.0)

        ctx = dict(context or {})
        if self.debug and "debug" not in ctx:
            ctx["debug"] = True

        params = unwrap_tool_args(dict(parameters or {}))

        req = PolicyRequest(
            tool=tool,
            parameters=params,
            context=ctx,
        )
        t0 = time.perf_counter()
        try:
            decision = self.engine.evaluate(req)
        except Exception as exc:
            decision = PolicyDecision(
                verdict=self.fail_safe,
                reason=f"Security manager evaluation failed ({exc}). Failing safe to {self.fail_safe.value}.",
            )
        duration_ms = round((time.perf_counter() - t0) * 1000, 2)
        if self.debug:
            print(
                f"[Security Debug] [TIME] Security evaluation for '{tool}' completed in "
                f"{duration_ms:.2f} ms ({decision.verdict.value})"
            )
        return dataclasses.replace(decision, duration_ms=duration_ms)

    def evaluate_output(
        self,
        tool: str,
        output: str,
        parameters: dict[str, Any] | None = None,
        context: dict[str, Any] | None = None,
    ) -> PolicyDecision:
        """Evaluate a tool invocation's post-I/O output against the active security engine."""
        if not self.enabled or not self.output_security_enabled:
            return PolicyDecision(verdict=Verdict.ALLOW, reason="Output security disabled.", duration_ms=0.0)

        tool_norm = (tool or "").strip().lower()
        if tool_norm not in self.output_security_tools:
            return PolicyDecision(verdict=Verdict.ALLOW, reason=f"Tool '{tool}' not in output security scope.", duration_ms=0.0)

        ctx = dict(context or {})
        if self.debug and "debug" not in ctx:
            ctx["debug"] = True

        params = unwrap_tool_args(dict(parameters or {}))

        req = PolicyRequest(
            tool=tool,
            parameters=params,
            context=ctx,
            output=output,
            phase="output",
        )
        t0 = time.perf_counter()
        try:
            if hasattr(self.engine, "supports_output_evaluation") and not self.engine.supports_output_evaluation():
                decision = PolicyDecision(verdict=Verdict.ALLOW, reason="Engine does not inspect output.")
            elif hasattr(self.engine, "evaluate_output"):
                decision = self.engine.evaluate_output(req)
            else:
                decision = PolicyDecision(verdict=Verdict.ALLOW, reason="Engine does not implement evaluate_output.")
        except Exception as exc:
            decision = PolicyDecision(
                verdict=self.fail_safe,
                reason=f"Security manager output evaluation failed ({exc}). Failing safe to {self.fail_safe.value}.",
            )
        duration_ms = round((time.perf_counter() - t0) * 1000, 2)
        if self.debug:
            print(
                f"[Security Debug] [TIME] Post-I/O security evaluation for '{tool}' completed in "
                f"{duration_ms:.2f} ms ({decision.verdict.value})"
            )
        return dataclasses.replace(decision, request_id=req.request_id, duration_ms=duration_ms)


    def get_banner(self) -> str:
        """Return a human-readable banner string describing the active security engine."""
        if not self.enabled:
            return "Disabled"
        if self.engine is not None:
            return self.engine.get_banner()
        return "None"

