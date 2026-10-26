"""
Security DSL (Domain-Specific Language) Module
Implements formal tokenizer, AST, parser, and matcher for human-readable
security policy rules.

Grammar Specification:
  Rule          ::= Action ToolTarget Condition (ReasonClause)?
  Action        ::= "ALLOW" | "PERMIT" | "DENY" | "BLOCK" | "ASK" | "PROMPT"
  ToolTarget    ::= "READ" ("FILE"|"FILES")?
                  | "WRITE" ("FILE"|"FILES")?
                  | "DELETE" ("FILE"|"FILES")?
                  | "RUN" ("COMMAND"|"COMMANDS")?
                  | "CALL" ("SKILL"|"SKILLS")?
                  | "ANY" ("TOOL"|"TOOLS")?
                  | IDENTIFIER
  Condition     ::= ("WHERE" | "WITH" | "MATCHING") Predicate
  Predicate     ::= (ParamRef)? Operator Value
  ParamRef      ::= "PATH" | "FILE" | "COMMAND" | "ARG" | "CONTENT" | IDENTIFIER
  Operator      ::= "CONTAINS" | "HAS"
                  | "STARTS" "WITH"
                  | "ENDS" "WITH"
                  | "EQUALS" | "IS"
                  | "MATCHES"
  Value         ::= STRING | IDENTIFIER
  ReasonClause  ::= "BECAUSE" STRING
"""

import fnmatch
import logging
import re
from dataclasses import dataclass
from typing import Any
from chatybot.security.models import PolicyDecision, PolicyPromptDetails, PolicyRequest, Verdict

logger = logging.getLogger(__name__)


@dataclass
class SecurityRuleAST:
    raw_text: str
    action: Verdict
    tool: str | None           # Canonical tool name (e.g. 'read_file'), or None for wildcard/any
    param_name: str            # Parameter to inspect ('path', 'command', etc.)
    operator: str              # 'contains', 'endswith', 'startswith', 'equals', 'matches'
    value: str                 # Pattern or string value
    reason: str | None = None  # Optional explicit explanation
    line_scope: str | None = None  # None (whole-value), 'any_line' (line-by-line), 'first_line' (header/shebang)
    compiled_regex: re.Pattern | None = None

    def __post_init__(self):
        if self.operator == "matches" and self.compiled_regex is None and self.value:
            try:
                self.compiled_regex = re.compile(self.value, re.IGNORECASE)
            except re.error:
                self.compiled_regex = None

    def format_definition(self) -> str:
        """Format parsed AST details into a readable string representation."""
        action_name = self.action.value.upper()
        scope_desc = f"{self.line_scope} " if self.line_scope else ""
        match_desc = f"{scope_desc}{self.param_name} {self.operator} '{self.value}'" if self.operator != "always" else "always"
        reason_desc = f", reason='{self.reason}'" if self.reason else ""
        return f"action={action_name}, tool={self.tool or '*'}, match=({match_desc}){reason_desc}"

    def matches(self, request: PolicyRequest) -> bool:
        req_tool = (request.tool or "").strip().lower()
        rule_tool = (self.tool or "").strip().lower()

        WRITE_TOOL_GROUP = {
            "write_file", "replace_file_content", "patch_file", "multi_replace_file_content"
        }
        READ_TOOL_GROUP = {
            "read_file", "file_info", "grep_search", "read_url"
        }

        # 1. Match tool (case-insensitive, with glob, tool groups, and base tool suffix support)
        if rule_tool and rule_tool not in ("any", "*", "all"):
            matched_tool = False
            if req_tool == rule_tool:
                matched_tool = True
            elif rule_tool == "write_file" and (req_tool in WRITE_TOOL_GROUP or any(req_tool.endswith("__" + w) for w in WRITE_TOOL_GROUP) or fnmatch.fnmatch(req_tool, "*write*")):
                matched_tool = True
            elif rule_tool == "read_file" and (req_tool in READ_TOOL_GROUP or any(req_tool.endswith("__" + r) for r in READ_TOOL_GROUP) or fnmatch.fnmatch(req_tool, "*read*")):
                matched_tool = True
            elif fnmatch.fnmatch(req_tool, rule_tool):
                matched_tool = True
            elif req_tool.endswith("__" + rule_tool) or req_tool.endswith(":" + rule_tool) or req_tool.endswith("." + rule_tool):
                matched_tool = True

            if not matched_tool:
                return False

        if self.operator == "always":
            return True

        # 2. Extract parameter candidate values recursively across payload
        params = request.parameters or {}

        path_synonyms = {
            "path", "file", "target", "dir", "directory",
            "filename", "filepath", "targetpath", "targetfile",
            "source", "destination", "dest", "sourcefile", "destfile",
            "sourcepath", "destpath", "cwd", "workdir", "workingdir", "paths",
        }
        content_synonyms = {
            "content", "contents", "body", "text", "data", "code",
            "codecontent", "replacementcontent", "targetcontent", "patch", "diff",
            "payload", "output", "result", "stdout", "response", "query",
            "sql", "statement", "document", "message", "filecontent", "stdin",
        }
        command_synonyms = {
            "command", "cmd", "commandline", "script",
        }

        def extract_values(data: Any, target_field: str, depth: int = 0) -> list[str]:
            if depth > 15:
                return []
            results: list[str] = []
            target_clean = target_field.lower().replace("_", "").replace("-", "")

            if isinstance(data, dict):
                for k, v in data.items():
                    k_clean = k.lower().replace("_", "").replace("-", "")
                    is_match = False
                    if target_clean in ("*", "any"):
                        is_match = True
                    elif k_clean == target_clean:
                        is_match = True
                    elif target_clean in content_synonyms:
                        if (
                            k_clean in content_synonyms
                            or k_clean.endswith("content")
                            or k_clean.endswith("text")
                            or k_clean.endswith("payload")
                            or k_clean.endswith("code")
                            or k_clean.endswith("data")
                            or k_clean.endswith("body")
                        ):
                            is_match = True
                    elif target_clean in ("path", "file", "dir", "directory"):
                        if (
                            k_clean in path_synonyms
                            or k_clean.endswith("path")
                            or k_clean.endswith("file")
                            or k_clean.endswith("dir")
                            or k_clean.endswith("target")
                        ):
                            is_match = True
                    elif target_clean in ("command", "cmd"):
                        if (
                            k_clean in command_synonyms
                            or k_clean.endswith("command")
                            or k_clean.endswith("cmd")
                        ):
                            is_match = True

                    if is_match:
                        if isinstance(v, (str, int, float, bool)):
                            results.append(str(v))
                        elif isinstance(v, (dict, list)):
                            results.extend(extract_values(v, "*", depth + 1))

                    # Also search inside nested dictionaries/lists when looking for a specific target_field
                    if isinstance(v, (dict, list)) and target_clean not in ("*", "any") and not is_match:
                        results.extend(extract_values(v, target_field, depth + 1))
            elif isinstance(data, list):
                for item in data:
                    results.extend(extract_values(item, target_field, depth + 1))
            elif isinstance(data, (str, int, float, bool)) and target_clean in ("*", "any"):
                results.append(str(data))
            return results

        candidate_values = extract_values(params, self.param_name)
        # If output is present (e.g. read_file output or post-execution tool egress), include it
        if request.output:
            target_clean = self.param_name.lower().replace("_", "").replace("-", "")
            if target_clean in ("*", "any", "output") or target_clean in content_synonyms:
                candidate_values.append(str(request.output))

        if not candidate_values:
            return False

        pat = "\n" if self.value in ("\\n", "\n") else ("\r" if self.value in ("\\r", "\r") else self.value)
        pat_lower = pat.lower()
        pat_collapsed = re.sub(r"\s+", " ", pat_lower).strip()

        # Helper to evaluate an individual line
        def match_single_line(line_str: str) -> bool:
            line_clean = line_str.strip()
            line_lower = line_clean.lower()
            line_collapsed = re.sub(r"\s+", " ", line_lower).strip()

            if self.operator == "contains":
                return (pat_lower in line_lower) or (bool(pat_collapsed) and pat_collapsed in line_collapsed)
            elif self.operator == "startswith":
                if line_lower.startswith(pat_lower) or (bool(pat_collapsed) and line_collapsed.startswith(pat_collapsed)):
                    return True
                if pat_collapsed == "rm -rf":
                    if re.search(
                        r"^\s*rm\s+(?:-[a-zA-Z]*r[a-zA-Z]*f\b|-[a-zA-Z]*f[a-zA-Z]*r\b|-[a-zA-Z]*r\s+-[a-zA-Z]*f\b|-[a-zA-Z]*f\s+-[a-zA-Z]*r\b)",
                        line_collapsed,
                    ):
                        return True
                return False
            elif self.operator == "endswith":
                return line_lower.endswith(pat_lower) or (bool(pat_collapsed) and line_collapsed.endswith(pat_collapsed))
            elif self.operator == "equals":
                return line_lower == pat_lower or line_collapsed == pat_collapsed
            elif self.operator == "matches":
                if self.compiled_regex is not None:
                    return bool(self.compiled_regex.search(line_str))
                else:
                    try:
                        return bool(re.search(self.value, line_str, re.IGNORECASE))
                    except re.error:
                        return False
            return False

        # 3. Match operator across all candidate values
        for val_str in candidate_values:
            val_lower = val_str.lower()
            val_collapsed = re.sub(r"\s+", " ", val_lower).strip()

            # 3A. First-line inspection (header / shebang check)
            if self.line_scope == "first_line":
                first_line = None
                for raw_l in val_str.splitlines():
                    s_l = raw_l.strip()
                    if s_l:
                        first_line = s_l
                        break
                if first_line and match_single_line(first_line):
                    return True
                continue

            # 3B. Any-line inspection (line-by-line scanning)
            if self.line_scope == "any_line":
                # Fast-path check: if simple substring not in the whole text at all, skip line splitting
                if self.operator in ("contains", "startswith", "endswith", "equals") and pat_lower:
                    if pat_lower not in val_lower and (not pat_collapsed or pat_collapsed not in val_collapsed) and pat_collapsed != "rm -rf":
                        continue

                for raw_l in val_str.splitlines():
                    if not raw_l.strip():
                        continue
                    if match_single_line(raw_l):
                        return True
                continue

            # 3C. Whole-string matching (default when line_scope is None)
            if self.operator == "contains":
                if pat_lower in val_lower or (pat_collapsed and pat_collapsed in val_collapsed):
                    return True
                # Special check for destructive rm flag permutations (rm -rf, rm -r -f, rm -fr)
                if pat_collapsed == "rm -rf":
                    if re.search(
                        r"\brm\s+(?:-[a-zA-Z]*r[a-zA-Z]*f\b|-[a-zA-Z]*f[a-zA-Z]*r\b|-[a-zA-Z]*r\s+-[a-zA-Z]*f\b|-[a-zA-Z]*f\s+-[a-zA-Z]*r\b)",
                        val_collapsed,
                    ):
                        return True

            elif self.operator == "endswith":
                if val_lower.endswith(pat_lower) or (pat_collapsed and val_collapsed.endswith(pat_collapsed)):
                    return True
            elif self.operator == "startswith":
                if val_lower.startswith(pat_lower) or (pat_collapsed and val_collapsed.startswith(pat_collapsed)):
                    return True
            elif self.operator == "equals":
                if val_lower == pat_lower or val_collapsed == pat_collapsed:
                    return True
            elif self.operator == "matches":
                if self.compiled_regex is not None:
                    if bool(self.compiled_regex.search(val_str)):
                        return True
                else:
                    try:
                        if bool(re.search(self.value, val_str, re.IGNORECASE)):
                            return True
                    except re.error as exc:
                        logger.warning(
                            "[Security Warning] Regex evaluation error with pattern '%s': %s",
                            self.value,
                            exc,
                        )

        return False


class SecurityDSLParser:
    """Parses Security DSL statements into executable SecurityRuleAST nodes."""

    ACTION_MAP = {
        "allow": Verdict.ALLOW,
        "permit": Verdict.ALLOW,
        "deny": Verdict.DENY,
        "block": Verdict.DENY,
        "do not": Verdict.DENY,
        "never": Verdict.DENY,
        "ask": Verdict.ASK,
        "prompt": Verdict.ASK,
        "require confirmation": Verdict.ASK,
    }

    TOOL_MAP = {
        "read": "read_file",
        "read file": "read_file",
        "read files": "read_file",
        "write": "write_file",
        "write file": "write_file",
        "write files": "write_file",
        "delete": "delete_file",
        "delete file": "delete_file",
        "delete files": "delete_file",
        "run": "run_command",
        "run command": "run_command",
        "run commands": "run_command",
        "command": "run_command",
        "commands": "run_command",
        "call skill": "call_skill",
        "call skills": "call_skill",
        "list directory": "list_directory",
        "remove directory": "remove_directory",
        "remove directories": "remove_directory",
        "any": None,
        "any tool": None,
        "any tools": None,
        "*": None,
    }

    @classmethod
    def parse_rule(cls, line: str) -> SecurityRuleAST | None:
        """Parse a single Security DSL line into a SecurityRuleAST node."""
        raw_line = line.strip()
        if not raw_line or raw_line.startswith("#") or raw_line.startswith("//"):
            return None

        # Check for optional 'because "<reason>"'
        reason = None
        m_reason = re.search(r'\bbecause\s+["\']([^"\']+)["\']\s*$', raw_line, re.IGNORECASE)
        working_line = raw_line
        if m_reason:
            reason = m_reason.group(1).strip()
            working_line = working_line[:m_reason.start()].strip()

        # Normalize spaces
        working_line = re.sub(r'\s+', ' ', working_line)

        # 1. Parse Action
        action_match = None
        action_len = 0
        sorted_actions = sorted(cls.ACTION_MAP.keys(), key=lambda k: -len(k))
        for act in sorted_actions:
            pattern = rf'^{re.escape(act)}\b'
            if re.match(pattern, working_line, re.IGNORECASE):
                action_match = cls.ACTION_MAP[act]
                action_len = len(act)
                break

        if not action_match:
            return None

        rest = working_line[action_len:].strip()

        # Strip optional connector words like "before", "to", "on", "tool", "call", "mcp"
        rest = re.sub(r'^(?:before|to|on)\s+', '', rest, flags=re.IGNORECASE)
        rest = re.sub(r'^(?:tool|call|mcp)\s+', '', rest, flags=re.IGNORECASE)

        # 2. Parse ToolTarget
        tool_target = None
        sorted_tools = sorted(cls.TOOL_MAP.keys(), key=lambda k: -len(k))
        tool_matched_key = None
        for t_phrase in sorted_tools:
            pattern = rf'^{re.escape(t_phrase)}\b'
            if re.match(pattern, rest, re.IGNORECASE):
                tool_target = cls.TOOL_MAP[t_phrase]
                tool_matched_key = t_phrase
                break

        if tool_matched_key:
            rest = rest[len(tool_matched_key):].strip()
        else:
            # Check for direct tool identifier or pattern (e.g. mcp__postgres__query, mcp__*, *postgres*, create_issue)
            m_direct = re.match(r'^([a-zA-Z0-9_\-\*\:\.]+)(?:\s+|$)', rest)
            if m_direct:
                tool_target = m_direct.group(1)
                rest = rest[m_direct.end():].strip()

        # Default parameter name based on resolved tool
        if tool_target == "run_command":
            default_param = "command"
        elif tool_target in ("read_file", "delete_file", "file_info"):
            default_param = "path"
        else:
            default_param = "*"

        # 3. Parse Condition & Operator
        operator = "contains"
        val = ""
        param_name = default_param
        line_scope = None

        # Check line-scoped qualifier:
        # e.g.: "where line starts with 'rm '", "where any line contains 'abc'",
        # "where first line starts with '#!'", "where header contains 'RESTRICTED'",
        # "where line in content starts with 'rm '", "with line containing 'foo'"
        m_line_scoped = re.match(
            r'^(?:where|with|if|that|which)?\s*'
            r'(any\s+line|first\s+line|header|line)\s+'
            r'(?:in\s+([a-zA-Z0-9_\.\-]+)\s+)?'
            r'(contains|containing|ends\s+with|ending\s+with|starts\s+with|starting\s+with|equals|is|matches|matching)\s+'
            r'(?:["\']([^"\']+)["\']|(\S+))',
            rest,
            re.IGNORECASE,
        )
        if m_line_scoped:
            scope_raw = m_line_scoped.group(1).lower()
            line_scope = "first_line" if ("first" in scope_raw or "header" in scope_raw) else "any_line"
            in_field = m_line_scoped.group(2)
            param_name = in_field.lower() if in_field else ("content" if default_param in ("*", "path") else default_param)
            op_raw = m_line_scoped.group(3).lower()
            val = (m_line_scoped.group(4) or m_line_scoped.group(5)).strip()
            if "starts" in op_raw or "starting" in op_raw:
                operator = "startswith"
            elif "ends" in op_raw or "ending" in op_raw:
                operator = "endswith"
            elif "matches" in op_raw or "matching" in op_raw:
                operator = "matches"
            elif op_raw in ("equals", "is"):
                operator = "equals"
            else:
                operator = "contains"
        # Check explicit parameter name:
        # - where <param> contains ..., where any field contains ..., where * contains ...
        elif re.match(
            r'^(?:where|with|if|that|which)?\s*(?:(?:the\s+)?(?:field|parameter|param|arg|argument)\s+)?'
            r'(any\s+(?:field|parameter|param|arg|argument)|\*|(?!that\b|which\b|where\b|with\b|if\b|the\b|field\b|param\b|parameter\b|arg\b|argument\b|contains\b|containing\b|ends\b|ending\b|starts\b|starting\b|equals\b|matches\b|is\b)[a-zA-Z0-9_\.\-]+)\s+'
            r'(contains|ends with|ending with|starts with|starting with|equals|is|matches)\s+'
            r'(?:["\']([^"\']+)["\']|(\S+))',
            rest,
            re.IGNORECASE,
        ):
            m_param_explicit = re.match(
                r'^(?:where|with|if|that|which)?\s*(?:(?:the\s+)?(?:field|parameter|param|arg|argument)\s+)?'
                r'(any\s+(?:field|parameter|param|arg|argument)|\*|(?!that\b|which\b|where\b|with\b|if\b|the\b|field\b|param\b|parameter\b|arg\b|argument\b|contains\b|containing\b|ends\b|ending\b|starts\b|starting\b|equals\b|matches\b|is\b)[a-zA-Z0-9_\.\-]+)\s+'
                r'(contains|ends with|ending with|starts with|starting with|equals|is|matches)\s+'
                r'(?:["\']([^"\']+)["\']|(\S+))',
                rest,
                re.IGNORECASE,
            )
            raw_param = m_param_explicit.group(1).lower()
            if raw_param.startswith("any") or raw_param == "*":
                param_name = "*"
            else:
                param_name = raw_param
            op_raw = m_param_explicit.group(2).lower()
            val = (m_param_explicit.group(3) or m_param_explicit.group(4)).strip()
            if "ends" in op_raw or "ending" in op_raw:
                operator = "endswith"
            elif "starts" in op_raw or "starting" in op_raw:
                operator = "startswith"
            elif "matches" in op_raw:
                operator = "matches"
            elif op_raw in ("equals", "is"):
                operator = "equals"
            else:
                operator = "contains"
        else:
            # Pattern matching without explicit param name:
            # - "with <val> in <field>", "with <val> in it", "contains <val>", "containing <val>"
            # - "ending with <val>", "ends with <val>", "with extension <val>"
            # - "starting with <val>", "under <val>", "in <val>"
            m_with_in_field = re.search(
                r'\b(?:that\s+|which\s+|where\s+)?(?:with|containing|contains|has|having)\s+(?:["\']([^"\']+)["\']|(\S+))\s+in\s+([a-zA-Z0-9_\.\-]+)\b',
                rest,
                re.IGNORECASE,
            )
            m_end = re.search(r'\b(?:that\s+|which\s+|where\s+)?(?:ending with|ends with|with extension)\s+(?:["\']([^"\']+)["\']|(\S+))', rest, re.IGNORECASE)
            m_start = re.search(r'\b(?:that\s+|which\s+|where\s+)?(?:starting with|starts with|under)\s+(?:["\']([^"\']+)["\']|(\S+))', rest, re.IGNORECASE)
            m_in_path = re.search(r'\bin\s+(?:["\']([^"\']+)["\']|(\S+))', rest, re.IGNORECASE)
            m_match = re.search(r'\b(?:that\s+|which\s+|where\s+)?matching\s+(?:["\']([^"\']+)["\']|(\S+))', rest, re.IGNORECASE)
            m_contains = re.search(r'\b(?:that\s+|which\s+|where\s+)?(?:contains|containing|with|has|having)\s+(?:["\']([^"\']+)["\']|(\S+))', rest, re.IGNORECASE)

            if m_with_in_field:
                operator = "contains"
                val = (m_with_in_field.group(1) or m_with_in_field.group(2)).strip()
                in_target = m_with_in_field.group(3).lower()
                if in_target in ("it", "this"):
                    param_name = default_param
                elif in_target in ("any", "any_field", "all"):
                    param_name = "*"
                else:
                    param_name = in_target
            elif m_end:
                operator = "endswith"
                val = (m_end.group(1) or m_end.group(2)).strip()
            elif m_start:
                operator = "startswith"
                val = (m_start.group(1) or m_start.group(2)).strip()
            elif m_in_path:
                in_cand = (m_in_path.group(1) or m_in_path.group(2)).strip()
                if in_cand.lower() in ("it", "this"):
                    return None
                operator = "startswith"
                val = in_cand
            elif m_match:
                operator = "matches"
                val = (m_match.group(1) or m_match.group(2)).strip()
            elif m_contains:
                operator = "contains"
                val = (m_contains.group(1) or m_contains.group(2)).strip()
            elif not rest:
                # Unconditional rule on a specific tool (e.g. "ask before delete file", "ask before remove directory")
                operator = "always"
                val = ""
            else:
                return None

        # Clean trailing "in it" or quotes if any
        val = re.sub(r'\s+in\s+it$', '', val, flags=re.IGNORECASE).strip().strip('"\'')

        if operator == "matches":
            try:
                re.compile(val)
            except re.error as exc:
                logger.warning(
                    "[Security Warning] Invalid regex pattern '%s' in rule '%s': %s",
                    val,
                    raw_line,
                    exc,
                )
                return None

        return SecurityRuleAST(
            raw_text=raw_line,
            action=action_match,
            tool=tool_target,
            param_name=param_name,
            operator=operator,
            value=val,
            reason=reason,
            line_scope=line_scope,
        )
