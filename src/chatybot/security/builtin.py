"""
Builtin Python Policy Engine
Default in-process policy engine evaluating baseline tool permissions,
path restrictions, and dangerous command patterns.
"""

import logging
import os
from typing import Any
from chatybot.security.base import BasePolicyEngine
from chatybot.security.models import (
    PolicyDecision,
    PolicyPromptDetails,
    PolicyRequest,
    Verdict,
)
from chatybot.security.dsl import SecurityDSLParser, SecurityRuleAST

logger = logging.getLogger(__name__)


class BuiltinPolicyEngine(BasePolicyEngine):
    """
    Default in-process policy engine with Security DSL evaluation,
    baseline tri-state rules, path traversal guards, and command filtering.
    """

    DEFAULT_TOOL_RULES: dict[str, str] = {
        "read_file": "allow",
        "file_info": "allow",
        "list_directory": "allow",
        "search_skills": "allow",
        "extract_code": "allow",
        "write_file": "ask",
        "delete_file": "ask",
        "make_directory": "ask",
        "remove_directory": "ask",
        "call_skill": "ask",
        "run_command": "ask",
        "read_url": "ask",
        "ask_user": "allow",
    }

    DEFAULT_DENIED_PATHS: list[str] = [
        "/etc",
        "/var/root",
        "/boot",
        "/System",
        "~/.ssh",
        "~/.gnupg",
        "~/.aws",
    ]

    DEFAULT_DENIED_COMMAND_PATTERNS: list[str] = [
        "rm -rf /",
        "rm -rf /*",
        ":(){ :|:& };:",
        "mkfs",
        "dd if=/dev/zero",
        "> /dev/sda",
        "> /dev/disk",
    ]

    def __init__(
        self,
        rules: dict[str, str] | None = None,
        dsl_rules: list[str] | None = None,
        default_verdict: str = "ask",
        denied_paths: list[str] | None = None,
        denied_command_patterns: list[str] | None = None,
        debug: bool = False,
    ):
        self.debug = debug
        self.rules = dict(self.DEFAULT_TOOL_RULES)
        if rules:
            self.rules.update(rules)

        self.default_verdict = Verdict(default_verdict)
        self.denied_paths = [
            os.path.abspath(os.path.expanduser(p))
            for p in (denied_paths or self.DEFAULT_DENIED_PATHS)
        ]
        self.denied_command_patterns = (
            denied_command_patterns or self.DEFAULT_DENIED_COMMAND_PATTERNS
        )

        if self.debug:
            print(f"[Security Debug] Loaded {len(self.denied_paths)} protected path definitions (special DENY):")
            for p in self.denied_paths:
                print(f"  [Definition: Path] [SPECIAL DENY] Path prefix: {p}")
            print(f"[Security Debug] Loaded {len(self.denied_command_patterns)} dangerous command pattern definitions (special DENY):")
            for cp in self.denied_command_patterns:
                print(f"  [Definition: Command Pattern] [SPECIAL DENY] Pattern: {cp}")

        self.deny_dsl_rules: list[SecurityRuleAST] = []
        self.ask_dsl_rules: list[SecurityRuleAST] = []
        self.allow_dsl_rules: list[SecurityRuleAST] = []
        self.dsl_rules: list[SecurityRuleAST] = []

        if dsl_rules:
            if self.debug:
                print(f"[Security Debug] Parsing and compiling {len(dsl_rules)} Security DSL rule definitions...")
            for idx, r_str in enumerate(dsl_rules, start=1):
                raw_trimmed = r_str.strip()
                if not raw_trimmed or raw_trimmed.startswith("#") or raw_trimmed.startswith("//"):
                    continue
                parsed = SecurityDSLParser.parse_rule(raw_trimmed)
                if parsed:
                    self.dsl_rules.append(parsed)
                    if parsed.action == Verdict.DENY:
                        self.deny_dsl_rules.append(parsed)
                        action_tag = "SPECIAL DENY (Tier 1)"
                    elif parsed.action == Verdict.ASK:
                        self.ask_dsl_rules.append(parsed)
                        action_tag = "SPECIAL ASK (Tier 2)"
                    else:
                        self.allow_dsl_rules.append(parsed)
                        action_tag = "SPECIAL ACCEPT (Tier 3)"

                    if self.debug:
                        print(f"  [Definition #{idx}] [{action_tag}] Raw: '{parsed.raw_text}'")
                        print(f"    -> Parsed: {parsed.format_definition()}")
                else:
                    logger.warning(
                        "[Security Warning] Failed to parse rule #%d in security policy: '%s'. Rule will be skipped.",
                        idx,
                        raw_trimmed,
                    )
                    if self.debug:
                        print(f"  [Definition #{idx}] [FAILED TO PARSE] '{raw_trimmed}'")

        if self.debug:
            print(f"[Security Debug] Loaded {len(self.rules)} baseline tool rule definitions (Default: {self.default_verdict.value.upper()}):")
            for t_name, t_verdict in sorted(self.rules.items()):
                action_tag = "ACCEPT" if str(t_verdict).lower() == "allow" else str(t_verdict).upper()
                print(f"  [Definition: Baseline Tool] [{action_tag}] '{t_name}' -> verdict={t_verdict}")

    def evaluate(self, request: PolicyRequest) -> PolicyDecision:
        tool = request.tool
        params = request.parameters or {}

        decision: PolicyDecision
        # Tier 0: System Protections (Protected Paths & Dangerous Command Patterns)
        if tool in ("read_file", "write_file", "delete_file", "list_directory", "file_info"):
            target_path = params.get("path") or params.get("target") or params.get("dir")
            if target_path and isinstance(target_path, str):
                abs_path = os.path.abspath(os.path.expanduser(target_path))
                for denied in self.denied_paths:
                    if abs_path == denied or abs_path.startswith(denied + os.sep):
                        decision = PolicyDecision(
                            verdict=Verdict.DENY,
                            reason=f"Access to protected path '{target_path}' is denied by policy.",
                        )
                        if self.debug:
                            print(f"[Security Debug] [SPECIAL DENY] Tier 0 Protected Path: '{target_path}' -> {decision.reason}")
                        return decision

        if tool == "run_command":
            cmd = str(params.get("command", "")).strip()
            for pattern in self.denied_command_patterns:
                if pattern in cmd:
                    decision = PolicyDecision(
                        verdict=Verdict.DENY,
                        reason=f"Dangerous command pattern '{pattern}' is strictly denied by policy.",
                    )
                    if self.debug:
                        print(f"[Security Debug] [SPECIAL DENY] Tier 0 Dangerous Command: '{pattern}' in '{cmd}' -> {decision.reason}")
                    return decision

        # Tier 1: Deny-Overrides Evaluation (All DENY DSL rules evaluated first)
        for dsl_rule in self.deny_dsl_rules:
            if dsl_rule.matches(request):
                reason = dsl_rule.reason or f"Matched security DSL rule: '{dsl_rule.raw_text}'"
                decision = PolicyDecision(
                    verdict=Verdict.DENY,
                    reason=reason,
                )
                if self.debug:
                    print(f"[Security Debug] [SPECIAL DENY] Tier 1 Rule: '{dsl_rule.raw_text}' -> {reason}")
                return decision

        # Tier 2: Ask Rules (Check all ASK DSL rules)
        for dsl_rule in self.ask_dsl_rules:
            if dsl_rule.matches(request):
                reason = dsl_rule.reason or f"Matched security DSL rule: '{dsl_rule.raw_text}'"
                prompt_details = PolicyPromptDetails(
                    title=f"Security Policy: {dsl_rule.action.value.upper()}",
                    message=f"Action matched rule: '{dsl_rule.raw_text}'",
                    risk_level="high" if tool == "run_command" else "medium",
                )
                decision = PolicyDecision(
                    verdict=Verdict.ASK,
                    reason=reason,
                    prompt_details=prompt_details,
                )
                if self.debug:
                    print(f"[Security Debug] [SPECIAL ASK] Tier 2 Rule: '{dsl_rule.raw_text}' -> {reason}")
                return decision

        # Tier 3: Allow Rules (Check all ALLOW DSL rules)
        for dsl_rule in self.allow_dsl_rules:
            if dsl_rule.matches(request):
                reason = dsl_rule.reason or f"Matched security DSL rule: '{dsl_rule.raw_text}'"
                decision = PolicyDecision(
                    verdict=Verdict.ALLOW,
                    reason=reason,
                )
                if self.debug:
                    print(f"[Security Debug] [SPECIAL ACCEPT] Tier 3 Rule: '{dsl_rule.raw_text}' -> {reason}")
                return decision

        # Tier 4: Baseline Tool Defaults
        rule_val = self.rules.get(tool)
        verdict = Verdict(rule_val) if rule_val else self.default_verdict

        if verdict == Verdict.ALLOW:
            decision = PolicyDecision(
                verdict=Verdict.ALLOW,
                reason=f"Tool '{tool}' is permitted by policy.",
            )
        elif verdict == Verdict.DENY:
            decision = PolicyDecision(
                verdict=Verdict.DENY,
                reason=f"Tool '{tool}' is denied by policy.",
            )
        else:
            # Verdict.ASK
            risk = "medium"
            if tool == "run_command":
                risk = "high"
            elif tool in ("delete_file", "remove_directory"):
                risk = "high"
            elif tool == "read_file":
                risk = "low"

            decision = PolicyDecision(
                verdict=Verdict.ASK,
                reason=f"Execution of '{tool}' requires user confirmation.",
                prompt_details=PolicyPromptDetails(
                    title=f"Authorize Tool: {tool}",
                    message=f"The assistant is requesting to run '{tool}'.",
                    risk_level=risk,
                ),
            )

        if self.debug:
            tag = "ACCEPT" if decision.verdict == Verdict.ALLOW else decision.verdict.value.upper()
            print(f"[Security Debug] [{tag}] Tier 4 Baseline Tool: {tool} -> {decision.reason}")
        return decision
