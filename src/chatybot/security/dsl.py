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

import re
from dataclasses import dataclass
from typing import Any
from chatybot.security.models import PolicyDecision, PolicyPromptDetails, PolicyRequest, Verdict


@dataclass
class SecurityRuleAST:
    raw_text: str
    action: Verdict
    tool: str | None           # Canonical tool name (e.g. 'read_file'), or None for wildcard/any
    param_name: str            # Parameter to inspect ('path', 'command', etc.)
    operator: str              # 'contains', 'endswith', 'startswith', 'equals', 'matches'
    value: str                 # Pattern or string value
    reason: str | None = None  # Optional explicit explanation

    def format_definition(self) -> str:
        """Format parsed AST details into a readable string representation."""
        action_name = self.action.value.upper()
        match_desc = f"{self.param_name} {self.operator} '{self.value}'" if self.operator != "always" else "always"
        reason_desc = f", reason='{self.reason}'" if self.reason else ""
        return f"action={action_name}, tool={self.tool or '*'}, match=({match_desc}){reason_desc}"

    def matches(self, request: PolicyRequest) -> bool:
        # 1. Match tool
        if self.tool and self.tool != "any" and request.tool != self.tool:
            return False

        if self.operator == "always":
            return True

        # 2. Extract parameter value
        params = request.parameters or {}
        candidate_val = params.get(self.param_name)

        # Fallback aliases for common parameter keys
        if candidate_val is None:
            if self.param_name == "path":
                candidate_val = params.get("target") or params.get("file") or params.get("dir")
            elif self.param_name == "command":
                candidate_val = params.get("cmd")

        if candidate_val is None:
            return False

        val_str = str(candidate_val).strip()
        val_lower = val_str.lower()
        pat_lower = self.value.lower()

        # 3. Match operator
        if self.operator == "contains":
            return pat_lower in val_lower
        elif self.operator == "endswith":
            return val_lower.endswith(pat_lower)
        elif self.operator == "startswith":
            return val_lower.startswith(pat_lower)
        elif self.operator == "equals":
            return val_lower == pat_lower
        elif self.operator == "matches":
            try:
                return bool(re.search(self.value, val_str, re.IGNORECASE))
            except re.error:
                return False

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

        # Strip optional connector words like "before" ("ask before run command...")
        rest = re.sub(r'^(?:before|to|on)\s+', '', rest, flags=re.IGNORECASE)

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
            # Check for direct single-word tool identifier
            m_direct = re.match(r'^([a-zA-Z0-9_\-\*]+)\b', rest)
            if m_direct:
                tool_target = m_direct.group(1)
                rest = rest[m_direct.end():].strip()

        # Default parameter name based on resolved tool
        default_param = "command" if tool_target == "run_command" else "path"

        # 3. Parse Condition & Operator
        # Normalize connectors: "where", "with", "containing", "matching"
        # Syntax examples:
        # - with api_key in it / containing api_key
        # - ending with .env / with extension .env
        # - starting with /etc
        # - equals /tmp/foo
        # - matching regex r"..."
        
        # Check operator variants
        operator = "contains"
        val = ""
        param_name = default_param

        # Check explicit parameter name: where path contains ..., where command contains ...
        m_param_explicit = re.match(r'^(?:where|with|if)?\s*(path|command|file|content|url)\s+(contains|ends with|ending with|starts with|starting with|equals|is|matches)\s+["\']?([^"\']+)["\']?', rest, re.IGNORECASE)
        if m_param_explicit:
            param_name = m_param_explicit.group(1).lower()
            op_raw = m_param_explicit.group(2).lower()
            val = m_param_explicit.group(3).strip()
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
            # Pattern: ending with <val> / with extension <val>
            # Check "with <val> in it" or "containing <val>" or "with <val>"
            m_with_in_it = re.search(r'\b(?:with|containing|has|having)\s+(?:["\']([^"\']+)["\']|(\S+))\s+in\s+it\b', rest, re.IGNORECASE)
            m_end = re.search(r'\b(?:ending with|with extension)\s+(?:["\']([^"\']+)["\']|(\S+))', rest, re.IGNORECASE)
            m_start = re.search(r'\b(?:starting with|under)\s+(?:["\']([^"\']+)["\']|(\S+))', rest, re.IGNORECASE)
            m_in_path = re.search(r'\bin\s+(?:["\']([^"\']+)["\']|(\S+))', rest, re.IGNORECASE)
            m_match = re.search(r'\bmatching\s+(?:["\']([^"\']+)["\']|(\S+))', rest, re.IGNORECASE)
            m_contains = re.search(r'\b(?:with|containing|has|having)\s+(?:["\']([^"\']+)["\']|(\S+))', rest, re.IGNORECASE)

            if m_with_in_it:
                operator = "contains"
                val = (m_with_in_it.group(1) or m_with_in_it.group(2)).strip()
            elif m_end:
                operator = "endswith"
                val = (m_end.group(1) or m_end.group(2)).strip()
            elif m_start:
                operator = "startswith"
                val = (m_start.group(1) or m_start.group(2)).strip()
            elif m_in_path:
                operator = "startswith"
                val = (m_in_path.group(1) or m_in_path.group(2)).strip()
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

        return SecurityRuleAST(
            raw_text=raw_line,
            action=action_match,
            tool=tool_target,
            param_name=param_name,
            operator=operator,
            value=val,
            reason=reason,
        )
