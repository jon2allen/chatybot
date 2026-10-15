"""
Builtin Python Policy Engine
Default in-process policy engine evaluating baseline tool permissions,
path restrictions, and dangerous command patterns.
"""

import logging
import os
import re
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

    # Matches direct or wrapper execution of Chatybot or Python module/script invocation
    _ENV_PREFIX = r"(?:[a-zA-Z_][a-zA-Z0-9_]*=[^\s;&|`\n\r]*\s+)*"
    _WRAPPER_PREFIX = (
        r"(?:(?:exec|env|nohup|sudo|xargs|nice|timeout|ionice|taskset|time|strace|ltrace|chroot|"
        r"(?:ba|z|k|c)?sh\s+-c)\b(?:\s+-[^\s;&|`\n\r]+|\s+[0-9]+|\s+[^\s;&|`\n\r\'\"]+)*\s*['\"]?\s*)*"
    )
    _CHATYBOT_BIN = r"(?:[^\s;&|`\n\r\'\"]*/)?chatybot(?:\.py)?(?:\s+|['\"`;&|]|$)"
    _PYTHON_MODULE = (
        r"python[0-9.]*\s+(?:-m\s+chatybot(?:\s+|$)|[^\s;&|`\n\r]*/chatybot\.py(?:\s+|$)|"
        r"-c\s+['\"][^'\"]*\bchatybot\b)"
    )
    _PREFIX = r"(?:^|[;&|`\n\r]|\$\()\s*" + _ENV_PREFIX + _WRAPPER_PREFIX

    CHATYBOT_EXEC_PATTERN = re.compile(
        f"{_PREFIX}(?:{_CHATYBOT_BIN}|{_PYTHON_MODULE})",
        re.IGNORECASE,
    )

    DEFAULT_TOOL_RULES: dict[str, str] = {
        "read_file": "allow",
        "file_info": "allow",
        "list_directory": "allow",
        "search_skills": "allow",
        "extract_code": "allow",
        "get_context_metrics": "allow",
        "decide_choice": "allow",
        "decide_score": "allow",
        "session_search": "allow",
        "find_files": "allow",
        "session_get": "allow",
        "replace_file_content": "ask",
        "patch_file": "ask",
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
        self.rules = {k.lower(): str(v).lower() for k, v in self.DEFAULT_TOOL_RULES.items()}
        if rules:
            self.rules.update({k.lower(): str(v).lower() for k, v in rules.items()})

        raw_default = str(default_verdict or "ask").strip().lower()
        try:
            self.default_verdict = Verdict(raw_default)
        except ValueError:
            self.default_verdict = Verdict.ASK
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
        tool_raw = request.tool or ""
        tool = tool_raw.strip().lower()
        params = request.parameters or {}

        decision: PolicyDecision
        cmd = ""
        if tool == "run_command":
            cmd_raw = params.get("command") if params.get("command") is not None else params.get("cmd")
            if cmd_raw is not None:
                cmd = str(cmd_raw).strip()
            else:
                for k, v in params.items():
                    if k.lower() in ("command", "cmd") and v is not None:
                        cmd = str(v).strip()
                        break
        # Tier 0: System Protections (Protected Paths & Dangerous Command Patterns)
        if tool in (
            "read_file",
            "write_file",
            "delete_file",
            "list_directory",
            "file_info",
            "make_directory",
            "remove_directory",
            "replace_file_content",
            "patch_file",
            "find_files",
        ):
            candidate_paths: list[str] = []
            path_keys = {
                "path", "file", "target", "dir", "directory",
                "filename", "filepath", "targetpath", "targetfile",
                "source", "destination", "dest", "sourcefile", "destfile",
                "sourcepath", "destpath",
            }
            for k, v in params.items():
                k_clean = k.lower().replace("_", "").replace("-", "")
                if (
                    k_clean in path_keys
                    or k_clean.endswith("path")
                    or k_clean.endswith("file")
                    or k_clean.endswith("dir")
                ) and isinstance(v, str):
                    candidate_paths.append(v)

            for target_path in candidate_paths:
                abs_path = os.path.abspath(os.path.expanduser(target_path))
                try:
                    real_path = os.path.realpath(abs_path)
                except Exception:
                    real_path = abs_path

                paths_to_check = set()
                for p in [abs_path, real_path]:
                    p_lower = p.lower()
                    if p_lower.startswith("/system/volumes/data/"):
                        paths_to_check.add(p_lower[len("/system/volumes/data"):])
                    else:
                        paths_to_check.add(p_lower)
                    if p_lower.startswith("/private/"):
                        paths_to_check.add(p_lower[len("/private"):])
                        paths_to_check.add(p_lower)

                for check_p_lower in paths_to_check:
                    # Mandatory Security Policy File Protection: block read/write/delete to security.toml or RACF policy files
                    base_name = os.path.basename(check_p_lower)
                    is_policy_file = (
                        base_name == "security.toml"
                        or "security.toml" in base_name
                        or check_p_lower.endswith(".racf")
                        or (
                            "racf" in base_name
                            and any(k in base_name for k in ("rule", "policy", "config", "guard", "security"))
                            and not base_name.endswith((".rs", ".py", ".c", ".h", ".lock", ".md"))
                        )
                    )
                    if is_policy_file:
                        decision = PolicyDecision(
                            verdict=Verdict.DENY,
                            reason=f"Access to security policy configuration '{target_path}' is strictly denied.",
                        )
                        if self.debug:
                            print(f"[Security Debug] [SPECIAL DENY] Tier 0 Security Policy Protection: '{target_path}' -> {decision.reason}")
                        return decision

                    for denied in self.denied_paths:
                        denied_targets = set()
                        d_abs = os.path.abspath(os.path.expanduser(denied)).lower()
                        denied_targets.add(d_abs)
                        try:
                            d_real = os.path.realpath(d_abs).lower()
                            if d_real.startswith("/system/volumes/data/"):
                                denied_targets.add(d_real[len("/system/volumes/data"):])
                            else:
                                denied_targets.add(d_real)
                            if d_real.startswith("/private/"):
                                denied_targets.add(d_real[len("/private"):])
                                denied_targets.add(d_real)
                        except Exception:
                            pass

                        for d_target in denied_targets:
                            if check_p_lower == d_target or check_p_lower.startswith(d_target + os.sep):
                                decision = PolicyDecision(
                                    verdict=Verdict.DENY,
                                    reason=f"Access to protected path '{target_path}' is denied by policy.",
                                )
                                if self.debug:
                                    print(f"[Security Debug] [SPECIAL DENY] Tier 0 Protected Path: '{target_path}' -> {decision.reason}")
                                return decision

        if tool == "run_command":
            # Tier 0: Direct check against Chatybot sub-process execution
            if self.CHATYBOT_EXEC_PATTERN.search(cmd):
                decision = PolicyDecision(
                    verdict=Verdict.DENY,
                    reason="Execution of Chatybot sub-process is strictly denied by policy to prevent recursive privilege escalation.",
                )
                if self.debug:
                    print(f"[Security Debug] [SPECIAL DENY] Tier 0 Chatybot Execution: '{cmd}' -> {decision.reason}")
                return decision

            cmd_lower = cmd.lower()
            cmd_collapsed = re.sub(r"\s+", " ", cmd_lower).strip()

            for pattern in self.denied_command_patterns:
                pat_lower = pattern.lower()
                pat_collapsed = re.sub(r"\s+", " ", pat_lower).strip()
                if (pat_lower in cmd_lower) or (pat_collapsed and pat_collapsed in cmd_collapsed):
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

        # Tier 2.5: Multiline / newline command separation guard for run_command
        if tool == "run_command" and ("\n" in cmd or "\r" in cmd):
            decision = PolicyDecision(
                verdict=Verdict.ASK,
                reason="Multiline command containing newline separator requires user confirmation.",
                prompt_details=PolicyPromptDetails(
                    title="Security Policy: Multiline Command",
                    message=f"Command contains newline separator: '{cmd}'. Proceed with execution?",
                    risk_level="high",
                ),
            )
            if self.debug:
                print(f"[Security Debug] [CHAINING ASK] Multiline command separator in '{cmd}' -> {decision.reason}")
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
        if rule_val:
            try:
                verdict = Verdict(rule_val.lower())
            except ValueError:
                verdict = self.default_verdict
        else:
            verdict = self.default_verdict

        if verdict == Verdict.ALLOW:
            decision = PolicyDecision(
                verdict=Verdict.ALLOW,
                reason=f"Tool '{tool_raw}' is permitted by policy.",
            )
        elif verdict == Verdict.DENY:
            decision = PolicyDecision(
                verdict=Verdict.DENY,
                reason=f"Tool '{tool_raw}' is denied by policy.",
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
                reason=f"Execution of '{tool_raw}' requires user confirmation.",
                prompt_details=PolicyPromptDetails(
                    title=f"Authorize Tool: {tool_raw}",
                    message=f"The assistant is requesting to run '{tool_raw}'.",
                    risk_level=risk,
                ),
            )

        if self.debug:
            tag = "ACCEPT" if decision.verdict == Verdict.ALLOW else decision.verdict.value.upper()
            print(f"[Security Debug] [{tag}] Tier 4 Baseline Tool: {tool_raw} -> {decision.reason}")
        return decision

    def get_banner(self) -> str:
        rule_count = len(self.dsl_rules)
        return f"Builtin Python Engine ({rule_count} DSL rules, {len(self.rules)} tool defaults)"

