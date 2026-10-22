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
from chatybot.security.allow_all import AllowAllPolicyEngine
from chatybot.security.base import BasePolicyEngine
from chatybot.security.builtin import BuiltinPolicyEngine
from chatybot.security.models import PolicyDecision, PolicyPromptDetails, PolicyRequest, Verdict

logger = logging.getLogger(__name__)


class SecurityManager:
    """Manages policy engine initialization, configuration parsing, and evaluation."""

    DEFAULT_CONFIG_PATH = "~/.config/chatybot/security.toml"
    DEFAULT_EXEMPT_TOOLS: set[str] = {
        # Interactive prompts and decision scoring
        "ask_user",
        "decide_choice",
        "decide_score",
        "decide_noul",
        "get_context_metrics",
        # Filesystem mutation tools (return write acknowledgments, not content)
        "write_file",
        "replace_file_content",
        "patch_file",
        "delete_file",
        "make_directory",
        "remove_directory",
        "change_dir",
    }

    def __init__(self, config_path: str | None = None, enabled: bool = True, debug: bool = False, trace_raw_payload: bool = False):
        self.enabled = enabled
        self.debug = debug
        self.trace_raw_payload = trace_raw_payload
        self.config_path = os.path.abspath(
            os.path.expanduser(config_path or self.DEFAULT_CONFIG_PATH)
        )
        self.config: dict[str, Any] = {}
        self.fail_safe = Verdict.DENY
        self.non_interactive_ask: str = "deny"
        self.max_refusals_per_loop: int = 3
        self.engine: BasePolicyEngine | None = None
        from chatybot.security.secret_scanner import SecretScanner
        self.secret_scanner: SecretScanner = SecretScanner()

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

        sec_section = self.config.get("security", {})
        raw_max_refusals = self.config.get(
            "max_refusals_per_loop",
            sec_section.get("max_refusals_per_loop", 3) if isinstance(sec_section, dict) else 3,
        )
        try:
            self.max_refusals_per_loop = max(0, int(raw_max_refusals))
        except (ValueError, TypeError):
            self.max_refusals_per_loop = 3


        output_cfg = self.config.get("output_security", {})
        self.output_security_enabled = bool(output_cfg.get("enabled", True))
        if "tools" in output_cfg:
            self.output_security_tools: set[str] | None = {str(t).lower() for t in output_cfg["tools"]}
            self.output_security_exempt_tools: set[str] = set()
        else:
            self.output_security_tools = None
            raw_exempt = output_cfg.get("exempt_tools", self.DEFAULT_EXEMPT_TOOLS)
            self.output_security_exempt_tools = {str(t).lower() for t in raw_exempt}

        from chatybot.security.secret_scanner import SecretScanner
        self.secret_scanner = SecretScanner(rules=output_cfg.get("rules"))

        engine_type = str(self.config.get("engine", "builtin")).lower()

        if self.debug:
            print(f"[Security Debug] Loading security configuration from '{config_to_load}'...")
            print(f"[Security Debug] Engine type: '{engine_type}', Fail-safe verdict: '{self.fail_safe.value.upper()}'.")
            scope_desc = f"whitelist: {sorted(self.output_security_tools)}" if self.output_security_tools is not None else f"all except exempt: {sorted(self.output_security_exempt_tools)}"
            print(f"[Security Debug] Output security enabled: {self.output_security_enabled} ({scope_desc})")

        if engine_type not in self.ENGINE_TYPES:
            warn_msg = (
                f"[Security Warning] Unsupported or unknown engine type '{engine_type}'. "
                "Falling back to builtin Python policy engine."
            )
            logger.warning(warn_msg)
            print(warn_msg)
            engine_type = "builtin"

        self.engine = self._build_engine(engine_type, top_level=True)

    ENGINE_TYPES = ("builtin", "binary", "allow", "jev", "chain")
    # Logged by default for the engines whose effectiveness is still being
    # measured; set log_path = "" in [jev] / [chain] to turn logging off.
    DEFAULT_JEV_LOG = "~/.config/chatybot/logs/jev_security.jsonl"
    DEFAULT_CHAIN_LOG = "~/.config/chatybot/logs/security_chain.jsonl"
    ASK_OUTCOMES = (
        "approved",                       # user answered yes at the prompt
        "declined",                       # user answered no
        "auto_approved_yes_flag",         # -y / --yes
        "auto_approved_non_interactive",  # non_interactive_ask = "allow"
        "blocked_non_interactive",        # non_interactive_ask = "deny"
    )

    def _build_engine(self, engine_type: str, top_level: bool = False) -> BasePolicyEngine:
        """Construct one engine from its [section] in the config."""
        if engine_type == "binary":
            bin_cfg = self.config.get("binary", {})
            raw_path = bin_cfg.get("path", "")
            bin_path = os.path.abspath(os.path.expanduser(raw_path)) if raw_path else ""
            if bin_path and os.path.exists(bin_path):
                return StdioBinaryPolicyEngine(
                    binary_path=bin_path,
                    timeout_seconds=float(bin_cfg.get("timeout_seconds", 2.0)),
                    fail_safe=self.fail_safe.value,
                    args=bin_cfg.get("args", []),
                    supports_output=bool(bin_cfg.get("supports_output", False)),
                    debug=self.debug,
                )

            # If binary not found, fallback to builtin engine with a prominent security warning
            warn_msg = (
                f"[Security Warning] Configured binary path not found: '{raw_path}' "
                f"(resolved: '{bin_path}'). Falling back to builtin Python policy engine."
            )
            logger.warning(warn_msg)
            print(warn_msg)
            return self._build_engine("builtin")

        if engine_type == "allow":
            allow_cfg = self.config.get("allow", {})
            protect = bool(allow_cfg.get("protect_security_config", True))
            warn_msg = (
                "[Security Warning] engine = 'allow': tools run WITHOUT policy checks (pre-0.9.0 behavior)"
                + ("; security configuration is still protected." if protect else "; security self-protection is OFF.")
            )
            logger.warning(warn_msg)
            print(warn_msg)
            return AllowAllPolicyEngine(protect_security_config=protect, debug=self.debug)

        if engine_type == "jev":
            from chatybot.security.jev import DEFAULT_RUBRIC_PATH, JevPolicyEngine

            jev_cfg = self.config.get("jev", {})
            return JevPolicyEngine(
                rubric_path=jev_cfg.get("rubric_path", DEFAULT_RUBRIC_PATH),
                model=jev_cfg.get("model", "typesafe/jev-1.13"),
                base_url=jev_cfg.get("base_url", "https://openrouter.ai"),
                endpoint_path=jev_cfg.get("endpoint_path", "/api/alpha/decisions"),
                api_key_env=jev_cfg.get("api_key_env", "OPENROUTER_API_KEY"),
                timeout_seconds=float(jev_cfg.get("timeout_seconds", 2.5)),
                on_error=jev_cfg.get("on_error", "auto"),
                mode=jev_cfg.get("mode", "noul"),
                cache=bool(jev_cfg.get("cache", True)),
                redact_secrets=bool(jev_cfg.get("redact_secrets", True)),
                max_content_chars=int(jev_cfg.get("max_content_chars", 8000)),
                skip_tools=jev_cfg.get("skip_tools"),
                output_scan=bool(jev_cfg.get("output_scan", False)),
                log_path=jev_cfg.get("log_path", self.DEFAULT_JEV_LOG),
                debug=self.debug,
                trace_raw_payload=bool(jev_cfg.get("trace_raw_payload", False)) or self.trace_raw_payload,
            )

        if engine_type == "chain":
            if not top_level:
                raise ValueError("[chain] stages cannot themselves be 'chain'")
            from chatybot.security.chain import ChainedPolicyEngine, ChainStage

            chain_cfg = self.config.get("chain", {})
            raw_stages = chain_cfg.get("stages", [])
            if not isinstance(raw_stages, list) or not raw_stages:
                raise ValueError("[chain] stages must be a non-empty list")
            stages = []
            for item in raw_stages:
                if isinstance(item, str):
                    name, mode = item.strip().lower(), "enforce"
                elif isinstance(item, dict):
                    name = str(item.get("engine", "")).strip().lower()
                    mode = str(item.get("mode", "enforce")).strip().lower()
                else:
                    raise ValueError(f"[chain] invalid stage entry: {item!r}")
                if name not in self.ENGINE_TYPES or name == "chain":
                    raise ValueError(f"[chain] unknown stage engine '{name}' (expected builtin, binary, allow or jev)")
                stages.append(ChainStage(name=name, engine=self._build_engine(name), mode=mode))
            return ChainedPolicyEngine(
                stages=stages,
                fail_safe=self.fail_safe,
                shadow_on_deny=bool(chain_cfg.get("shadow_on_deny", True)),
                log_path=chain_cfg.get("log_path", self.DEFAULT_CHAIN_LOG),
                redact_log=bool(chain_cfg.get("redact_log", True)),
                debug=self.debug,
            )

        # Default: builtin
        builtin_cfg = self.config.get("builtin", {})
        output_rules = self.config.get("output_security", {}).get("rules") or builtin_cfg.get("output_rules")
        return BuiltinPolicyEngine(
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
        # Return a copy stamped with the request id and duration (engines may cache and reuse decisions).
        return dataclasses.replace(decision, request_id=req.request_id, duration_ms=duration_ms)

    def is_tool_scanned(self, tool: str) -> bool:
        """Return True if tool output should be screened by output security."""
        if not getattr(self, "output_security_enabled", True):
            return False
        t = (tool or "").strip().lower()
        tools_whitelist = getattr(self, "output_security_tools", None)
        if tools_whitelist is not None:
            return t in tools_whitelist
        exempt = getattr(self, "output_security_exempt_tools", self.DEFAULT_EXEMPT_TOOLS)
        return t not in exempt

    def evaluate_output(
        self,
        tool: str,
        parameters: dict[str, Any] | None = None,
        output: str = "",
        context: dict[str, Any] | None = None,
    ) -> PolicyDecision:
        """Evaluate a tool invocation's output after I/O has executed."""
        if not self.enabled or not getattr(self, "output_security_enabled", True):
            return PolicyDecision(verdict=Verdict.ALLOW, reason="Output security disabled.", duration_ms=0.0)

        if not self.is_tool_scanned(tool):
            return PolicyDecision(verdict=Verdict.ALLOW, reason=f"Tool '{tool}' exempt from output security.", duration_ms=0.0)

        if not output or not output.strip():
            return PolicyDecision(verdict=Verdict.ALLOW, reason="Empty output.", duration_ms=0.0)

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
            # Deterministic floor check: secret scanner always executes across all engines
            scanner = getattr(self, "secret_scanner", None)
            floor_match = scanner.scan(output) if scanner is not None else None
            if floor_match is not None:
                floor_verdict, floor_reason = floor_match
                prompt_details = None
                if floor_verdict == Verdict.ASK:
                    prompt_details = PolicyPromptDetails(
                        title=f"Sensitive Output in {tool}",
                        message=f"Output from '{tool}' contains potential sensitive data: {floor_reason}. Allow LLM to view?",
                        risk_level="high",
                    )
                decision = PolicyDecision(verdict=floor_verdict, reason=floor_reason, prompt_details=prompt_details)
                if self.debug:
                    print(f"[Security Debug] [OUTPUT FLOOR] '{tool}' matched {floor_reason} -> {floor_verdict.value.upper()}")
            elif hasattr(self.engine, "supports_output_evaluation") and not self.engine.supports_output_evaluation():
                decision = PolicyDecision(verdict=Verdict.ALLOW, reason="Engine does not inspect output.")
            elif isinstance(self.engine, BuiltinPolicyEngine) and not getattr(self.engine, "_custom_output_rules", False):
                # Built-in engine uses default rules already screened by the floor scanner above
                decision = PolicyDecision(verdict=Verdict.ALLOW, reason="No sensitive content detected in output.")
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

    def record_outcome(self, decision: PolicyDecision, outcome: str, tool: str = "", detail: str = "") -> None:
        """Record what happened to an ASK decision (see ASK_OUTCOMES) in the engine's log.

        Engines that keep a decision log (chain, jev) append an outcome line with the
        same request_id as the decision, so the two can be joined later. Never raises.
        """
        if not self.enabled or self.engine is None or not getattr(decision, "request_id", ""):
            return
        fn = getattr(self.engine, "record_outcome", None)
        if fn is None:
            return
        try:
            fn(decision.request_id, tool, outcome, detail)
        except Exception as exc:  # noqa: BLE001
            logger.warning("[Security Warning] Could not record outcome '%s': %s", outcome, exc)

    def record_refusal_repeat(
        self,
        request_id: str,
        tool: str,
        parameters: dict[str, Any] | None = None,
        reason: str = "",
        session_id: str = "",
    ) -> None:
        """Record a repeat tool refusal served from cache to the engine's log. Never raises."""
        if not self.enabled or self.engine is None:
            return
        fn = getattr(self.engine, "record_refusal_repeat", None)
        if fn is None:
            return
        try:
            fn(request_id, tool, parameters=parameters, reason=reason, session_id=session_id)
        except Exception as exc:  # noqa: BLE001
            logger.warning("[Security Warning] Could not record refusal_repeat for '%s': %s", tool, exc)

    def record_refusal_limit(
        self,
        limit: int,
        request_ids: list[str] | None = None,
        refused_calls: list[dict[str, Any]] | None = None,
        session_id: str = "",
    ) -> None:
        """Record a loop refusal limit halt to the engine's log. Never raises."""
        if not self.enabled or self.engine is None:
            return
        fn = getattr(self.engine, "record_refusal_limit", None)
        if fn is None:
            return
        try:
            fn(limit, request_ids=request_ids, refused_calls=refused_calls, session_id=session_id)
        except Exception as exc:  # noqa: BLE001
            logger.warning("[Security Warning] Could not record refusal_limit: %s", exc)

    def get_banner(self) -> str:
        """Return a human-readable banner string describing the active security engine."""
        if not self.enabled:
            return "Disabled"
        if self.engine is not None:
            return self.engine.get_banner()
        return "None"

