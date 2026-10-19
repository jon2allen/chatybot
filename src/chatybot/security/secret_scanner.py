"""
Deterministic Secret Scanner Floor
High-performance pattern-based scanning for credentials, private keys, API keys,
connection strings, and authentication tokens in tool outputs.
"""

from __future__ import annotations

import re
from typing import Any
from chatybot.security.models import Verdict


class SecretScanner:
    """Always-on deterministic scanner evaluated at the SecurityManager level."""

    DEFAULT_OUTPUT_RULES: list[dict[str, str]] = [
        {"pattern": r"-----BEGIN [A-Z0-9_-]+ PRIVATE KEY-----", "verdict": "deny", "reason": "Output contains private cryptographic key"},
        {"pattern": r"\b(?:ghp|gho|ghs|github_pat)_[A-Za-z0-9_]{16,}\b", "verdict": "ask", "reason": "Output contains GitHub authentication token"},
        {"pattern": r"\bAKIA[0-9A-Z]{16}\b", "verdict": "ask", "reason": "Output contains AWS Access Key ID"},
        {"pattern": r"\bAIza[0-9A-Za-z-_]{30,}\b", "verdict": "ask", "reason": "Output contains Google / Gemini API key"},
        {"pattern": r"\bgsk_[A-Za-z0-9]{40,}\b", "verdict": "ask", "reason": "Output contains Groq API key"},
        {"pattern": r"\bhf_[A-Za-z0-9]{30,}\b", "verdict": "ask", "reason": "Output contains Hugging Face token"},
        {"pattern": r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b", "verdict": "ask", "reason": "Output contains Slack token"},
        {"pattern": r"\bsk-(?:[A-Za-z0-9]+-){0,2}[A-Za-z0-9]{32,}\b", "verdict": "ask", "reason": "Output contains secret API key"},
        {"pattern": r"\beyJ[A-Za-z0-9-_=]+\.eyJ[A-Za-z0-9-_=]+\.[A-Za-z0-9-_.+/=]+\b", "verdict": "ask", "reason": "Output contains JWT authentication token"},
        {"pattern": r"\b(?:postgres|postgresql|mysql|redis|mongodb|amqp|mssql)://[^/\s:@]+:[^/\s:@]+@", "verdict": "ask", "reason": "Output contains database connection string with credentials"},
        {"pattern": r"(?i)\b(?:bearer\s+[A-Za-z0-9._~+/=-]{20,}|(?:password|passwd)\s*[:=]\s*(?:['\"][^\s'\"]{6,}['\"]|[^\s'\"#;]{6,}))", "verdict": "ask", "reason": "Output contains password or bearer token"},
        {"pattern": r"(?i)\b(?:[A-Z0-9_]*(?:API_KEY|APIKEY|SECRET_KEY|SECRETKEY|AUTH_TOKEN|AUTHTOKEN|ACCESS_TOKEN|TOKEN|SECRET))\s*[:=]\s*(?:['\"][^\s'\"]{8,}['\"]|[^\s'\"#;]{8,})", "verdict": "ask", "reason": "Output contains environment variable credential assignment"},
    ]

    def __init__(self, rules: list[dict[str, str]] | None = None):
        raw_rules = rules if rules is not None else self.DEFAULT_OUTPUT_RULES
        self._compiled_rules: list[tuple[re.Pattern, Verdict, str]] = []
        for r in raw_rules:
            pat_str = r.get("pattern", "")
            if not pat_str:
                continue
            try:
                compiled = re.compile(pat_str)
                v_str = str(r.get("verdict", "ask")).strip().lower()
                verdict = Verdict.DENY if v_str == "deny" else Verdict.ASK
                reason = r.get("reason", "Output matched security pattern")
                self._compiled_rules.append((compiled, verdict, reason))
            except re.error:
                continue

    def scan(self, text: str) -> tuple[Verdict, str] | None:
        """Scan text against compiled rules. Returns (Verdict, reason) or None."""
        if not text or not text.strip():
            return None
        for pattern, verdict, reason in self._compiled_rules:
            if pattern.search(text):
                return verdict, f"Secret scanner: {reason}"
        return None
