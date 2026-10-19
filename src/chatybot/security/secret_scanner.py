"""
Deterministic Secret Scanner Floor
High-performance pattern-based scanning for credentials, private keys, API keys,
connection strings, and authentication tokens in tool outputs.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any
from chatybot.security.models import Verdict


SENSITIVE_KEY_KEYWORDS = (
    "KEY",
    "TOKEN",
    "SECRET",
    "PASSWORD",
    "PASSWD",
    "AUTH",
    "CREDENTIAL",
    "APIKEY",
    "PRIVATE",
)

IGNORED_KEYS = {
    "SECURITY_EVAL_TIME_MS",
}


def _is_sensitive_key_name(key_name: str) -> bool:
    k_upper = key_name.upper()
    if k_upper in IGNORED_KEYS or k_upper.startswith("SECURITY_EVAL_"):
        return False
    return any(kw in k_upper for kw in SENSITIVE_KEY_KEYWORDS)


def _is_valid_secret_value(value: str) -> bool:
    if not value:
        return False
    v = value.strip().strip("\"'")
    if len(v) < 12:
        return False
    if any(c.isspace() for c in v):
        return False
    if v.startswith(("/", "\\", "http://", "https://")):
        return False
    if v.lower() in {"true", "false", "none", "null", "undefined"}:
        return False
    return True


class SecretScanner:
    """Always-on deterministic scanner evaluated at the SecurityManager level.

    Each rule may carry optional ``literals``: substrings that MUST appear in any
    text the pattern can match. Before running a regex, the scanner does a cheap
    ``in`` check for those literals and skips the regex when none is present.
    ``literals_ci`` works the same way but is checked against ``text.lower()``
    (use it for case-insensitive rules; give the literals in lowercase).
    Rules without literals are always run.
    """

    DEFAULT_OUTPUT_RULES: list[dict[str, Any]] = [
        {"pattern": r"-----BEGIN [A-Z0-9_-]+ PRIVATE KEY-----", "literals": ["PRIVATE KEY-----"],
         "verdict": "deny", "reason": "Output contains private cryptographic key"},
        {"pattern": r"\b(?:ghp|gho|ghs|github_pat)_[A-Za-z0-9_]{16,}\b", "literals": ["ghp_", "gho_", "ghs_", "github_pat_"],
         "verdict": "ask", "reason": "Output contains GitHub authentication token"},
        {"pattern": r"\bAKIA[0-9A-Z]{16}\b", "literals": ["AKIA"],
         "verdict": "ask", "reason": "Output contains AWS Access Key ID"},
        {"pattern": r"\bAIza[0-9A-Za-z\-_]{30,}\b", "literals": ["AIza"],
         "verdict": "ask", "reason": "Output contains Google / Gemini API key"},
        {"pattern": r"\bgsk_[A-Za-z0-9]{40,}\b", "literals": ["gsk_"],
         "verdict": "ask", "reason": "Output contains Groq API key"},
        {"pattern": r"\bhf_[A-Za-z0-9]{30,}\b", "literals": ["hf_"],
         "verdict": "ask", "reason": "Output contains Hugging Face token"},
        {"pattern": r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b", "literals": ["xox"],
         "verdict": "ask", "reason": "Output contains Slack token"},
        {"pattern": r"\bsk-(?:[A-Za-z0-9]+-){0,2}[A-Za-z0-9]{32,}\b", "literals": ["sk-"],
         "verdict": "ask", "reason": "Output contains secret API key"},
        {"pattern": r"\beyJ[A-Za-z0-9\-_=]+\.eyJ[A-Za-z0-9\-_=]+\.[A-Za-z0-9\-_.+/=]+\b", "literals": ["eyJ"],
         "verdict": "ask", "reason": "Output contains JWT authentication token"},
        {"pattern": r"\b(?:postgres|postgresql|mysql|redis|mongodb|amqp|mssql)://[^/\s:@]+:[^/\s:@]+@", "literals": ["://"],
         "verdict": "ask", "reason": "Output contains database connection string with credentials"},
        {"pattern": r"(?i)\b(?:bearer\s+[A-Za-z0-9._~+/=-]{20,}|(?:password|passwd)\s*[:=]\s*(?:['\"][^\s'\"]{6,}['\"]|[^\s'\"#;]{6,}))",
         "literals_ci": ["bearer", "password", "passwd"],
         "verdict": "ask", "reason": "Output contains password or bearer token"},
        {"pattern": r"(?i)(?:API_?KEY|SECRET_?KEY|TOKEN|SECRET)\s*[:=]\s*(?:['\"][^\s'\"]{8,}['\"]|[^\s'\"#;]{8,})",
         "literals_ci": ["key", "token", "secret"],
         "verdict": "ask", "reason": "Output contains environment variable credential assignment"},
    ]

    def __init__(
        self,
        rules: list[dict[str, Any]] | None = None,
        known_secrets: dict[str, str] | None = None,
        config_env_path: str | Path | None = None,
    ):
        raw_rules = rules if rules is not None else self.DEFAULT_OUTPUT_RULES
        self._compiled_rules: list[
            tuple[re.Pattern[str], Verdict, str, tuple[str, ...] | None, tuple[str, ...] | None]
        ] = []
        for r in raw_rules:
            pat_str = r.get("pattern", "")
            if not pat_str:
                continue
            try:
                compiled = re.compile(pat_str)
            except re.error:
                continue
            v_str = str(r.get("verdict", "ask")).strip().lower()
            verdict = Verdict.DENY if v_str == "deny" else Verdict.ASK
            message = f"Secret scanner: {r.get('reason', 'Output matched security pattern')}"
            lits = tuple(r["literals"]) if r.get("literals") else None
            lits_ci = tuple(s.lower() for s in r["literals_ci"]) if r.get("literals_ci") else None
            self._compiled_rules.append((compiled, verdict, message, lits, lits_ci))

        self._custom_known_secrets = known_secrets
        self._config_env_path = config_env_path
        self._cached_file_secrets: dict[str, str] = self._load_file_secrets(config_env_path)
        self._cached_known_secrets: dict[str, str] = {}
        self.refresh_known_secrets()

    @staticmethod
    def _parse_env_file_safely(path: Path) -> dict[str, str]:
        secrets: dict[str, str] = {}
        if not path.is_file():
            return secrets
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if line.startswith(("export ", "export\t")):
                        line = line.split(maxsplit=1)[1].strip()
                    if "=" not in line:
                        continue
                    k, v = line.split("=", 1)
                    k = k.strip()
                    v = v.strip().strip("\"'")
                    if _is_sensitive_key_name(k) and _is_valid_secret_value(v):
                        secrets[v] = k
        except Exception:
            pass
        return secrets

    @classmethod
    def _load_file_secrets(cls, custom_path: str | Path | None = None) -> dict[str, str]:
        secrets: dict[str, str] = {}
        paths = []
        if custom_path:
            paths.append(Path(custom_path).expanduser())
        else:
            paths.append(Path("~/.config/chatybot/.env").expanduser())
            paths.append(Path.cwd() / ".env")

        for p in paths:
            file_sec = cls._parse_env_file_safely(p)
            secrets.update(file_sec)
        return secrets

    @classmethod
    def extract_secrets_from_dict(cls, d: dict[str, str]) -> dict[str, str]:
        """Extract secret values from a dictionary like os.environ. Returns {secret_val: key_name}."""
        secrets: dict[str, str] = {}
        for k, v in d.items():
            if _is_sensitive_key_name(k) and _is_valid_secret_value(v):
                secrets[v.strip().strip("\"'")] = k
        return secrets

    def refresh_known_secrets(self) -> dict[str, str]:
        """Refresh and cache known secrets from custom values, config files, and os.environ."""
        if self._custom_known_secrets is not None:
            combined = dict(self._custom_known_secrets)
        else:
            combined = dict(self._cached_file_secrets)
            env_secrets = self.extract_secrets_from_dict(dict(os.environ))
            combined.update(env_secrets)
        self._cached_known_secrets = dict(sorted(combined.items(), key=lambda item: len(item[0]), reverse=True))
        return self._cached_known_secrets

    def get_known_secrets(self) -> dict[str, str]:
        """Return cached known secrets sorted by length descending."""
        if not self._cached_known_secrets:
            return self.refresh_known_secrets()
        return self._cached_known_secrets

    def scan(self, text: str) -> tuple[Verdict, str] | None:
        """Scan text against compiled rules and known secrets. Returns (Verdict, reason) or None."""
        if not text or text.isspace():
            return None

        lowered: str | None = None

        def _matches_literals(lits: tuple[str, ...] | None, lits_ci: tuple[str, ...] | None) -> bool:
            nonlocal lowered
            if lits is not None and not any(s in text for s in lits):
                return False
            if lits_ci is not None:
                if lowered is None:
                    lowered = text.lower()
                if not any(s in lowered for s in lits_ci):
                    return False
            return True

        # 1. Check DENY rules first (e.g. private cryptographic keys)
        for pattern, verdict, message, lits, lits_ci in self._compiled_rules:
            if verdict == Verdict.DENY:
                if not _matches_literals(lits, lits_ci):
                    continue
                if pattern.search(text):
                    return verdict, message

        # 2. Check known secrets from environment and config files (exact substring match)
        for secret_val, key_name in self._cached_known_secrets.items():
            if secret_val in text:
                return Verdict.ASK, f"Secret scanner: Output contains configured secret ({key_name})"

        # 3. Check remaining pattern rules (e.g. ASK) with literal pre-filtering
        for pattern, verdict, message, lits, lits_ci in self._compiled_rules:
            if verdict != Verdict.DENY:
                if not _matches_literals(lits, lits_ci):
                    continue
                if pattern.search(text):
                    return verdict, message

        return None
