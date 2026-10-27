"""
Deterministic Secret Scanner Floor
High-performance pattern-based scanning for credentials, private keys, API keys,
connection strings, and authentication tokens in tool outputs.
"""

from __future__ import annotations

import math
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


# ---------------------------------------------------------------------------
# Value validation for the generic assignment rules
#
# The generic rules ("*_KEY = ...", "password: ...", "Bearer ...", .netrc) find
# *candidates*; a candidate only counts when its value looks like a real secret
# literal, not code that refers to one. This keeps reads of ordinary source
# files (os.environ[...], getpass(), settings.SECRET_KEY, placeholders) quiet.
# Real keys are still caught exactly by known-secret matching and by the
# provider-specific rules above, so these rules can afford to be strict.
# ---------------------------------------------------------------------------

_PLACEHOLDER_MARKERS = (
    "your_", "your-", "yourkey", "xxx", "changeme", "change_me", "change-me",
    "example", "placeholder", "replace", "dummy", "sample", "redacted",
    "...", "***", "todo", "fixme", "insert", "fake",
)
_CODE_CHARS = frozenset("()[]{}$`<>\\")
_DOTTED_IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)+$")
_IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_NON_SECRET_WORDS = frozenset({
    "true", "false", "none", "null", "nil", "undefined", "required", "optional",
    "str", "string", "int", "bytes", "bool", "any", "env", "secret", "token",
    "password", "passwd", "passphrase", "pass", "pw", "pwd", "user", "username",
})
_PASSWORD_KEY = re.compile(r"(?i)pass(?:word|wd|phrase)|pwd")
MIN_TOKEN_LEN = 16
MIN_PASSWORD_LEN = 8
MIN_ENTROPY_BITS = 3.2


def _shannon_entropy(value: str) -> float:
    counts: dict[str, int] = {}
    for ch in value:
        counts[ch] = counts.get(ch, 0) + 1
    n = len(value)
    return -sum((c / n) * math.log2(c / n) for c in counts.values())


def looks_like_secret_value(raw: str, *, password: bool = False, style: str = "prose") -> bool:
    """True when a matched value looks like a real secret literal, not code or a placeholder.

    Tokens/keys: >= 16 chars, letters and digits, Shannon entropy >= 3.2 bits/char.
    Passwords:   >= 8 chars. A bare word without digits (new_password) is a variable
                 name when the assignment is code-style (``password = x``,
                 ``password=password`` kwargs, ``:=``); in env-style lines
                 (``DB_PASSWORD=hunterhunter``), YAML/prose (``password: x``) and
                 .netrc it counts as a value.
    ``style`` is one of "code", "env", "prose".
    Either kind is rejected when it contains code syntax ( ( [ { $ ` < > \\ ),
    is a dotted name (settings.SECRET_KEY), a path or URL, or a placeholder.
    """
    if not raw:
        return False
    quoted = len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in "\"'"
    value = (raw[1:-1] if quoted else raw).strip()
    if not value or any(c.isspace() for c in value):
        return False
    low = value.lower()
    if low in _NON_SECRET_WORDS:
        return False
    if any(marker in low for marker in _PLACEHOLDER_MARKERS):
        return False
    if any(c in _CODE_CHARS for c in value):
        return False
    if _DOTTED_IDENT.match(value) and not any(c.isdigit() for c in value):
        return False  # settings.SECRET_KEY, os.environ (tokens like eyJ...J9.xyz have digits)
    if value.startswith(("/", "~", "./", "../", "http://", "https://", "file:")):
        return False
    if password:
        if len(value) < MIN_PASSWORD_LEN:
            return False
        if _IDENT.match(value) and not any(c.isdigit() for c in value):
            if quoted and "_" in value:
                return False  # "new_password": a field or variable name in quotes
            if not quoted and style == "code":
                return False  # password = new_password / password=password
        return True
    if len(value) < MIN_TOKEN_LEN:
        return False
    if not (any(c.isalpha() for c in value) and any(c.isdigit() for c in value)):
        return False
    return _shannon_entropy(value) >= MIN_ENTROPY_BITS


MIN_CLI_PASSWORD_LEN = 4
_UPPER_PLACEHOLDER = re.compile(r"^[A-Z_]+[,.;:)]*$")


def looks_like_cli_password(raw: str) -> bool:
    """A password given on a command line in an unambiguous position
    (``curl -u user:VALUE``, ``mysql -pVALUE``, ``sshpass -p VALUE``,
    ``--password=VALUE``). No 8-character minimum: the position already says it
    is a password. Shell expansions ($VAR, ${VAR}, $(cmd), backticks),
    placeholders and option-like values are not counted. A quoted value may
    contain spaces.
    """
    if not raw:
        return False
    quoted = len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in "\"'"
    value = (raw[1:-1] if quoted else raw).strip()
    if len(value) < MIN_CLI_PASSWORD_LEN or (not quoted and any(c.isspace() for c in value)):
        return False
    if value[0] in "-<$`" or "$(" in value or "${" in value or "`" in value:
        return False
    low = value.lower()
    if low in _NON_SECRET_WORDS or any(marker in low for marker in _PLACEHOLDER_MARKERS):
        return False
    if _UPPER_PLACEHOLDER.match(value):
        return False  # documentation placeholders: --password=VALUE, -u USER:PASSWORD
    if value.startswith(("/", "~", "./", "../", "http://", "https://", "file:")):
        return False
    return True


def _assignment_style(key: str, sep: str) -> str:
    """'env' for KEY=value, 'prose' for key: value, otherwise 'code'."""
    op = sep.strip()
    if op == ":":
        return "prose"
    if op == "=" and sep == "=" and key == key.upper():
        return "env"  # UPPER_KEY=value with no spaces around '='
    return "code"


def _validate_match(name: str, match: re.Match[str]) -> bool:
    groups = match.groupdict()
    raw = groups.get("val") or (match.group(1) if match.lastindex else match.group(0))
    if name == "credential_value":
        key = groups.get("key") or ""
        return looks_like_secret_value(
            raw, password=bool(_PASSWORD_KEY.search(key)), style=_assignment_style(key, groups.get("sep") or "")
        )
    if name == "token_value":
        return looks_like_secret_value(raw, password=False)
    if name == "password_value":
        return looks_like_secret_value(raw, password=True)
    if name == "cli_password":
        return looks_like_cli_password(raw)
    if name == "flag_credential":
        key = groups.get("key") or ""
        if _PASSWORD_KEY.search(key):
            # --password=VALUE is unambiguous; with a space the flag may take no value
            # (mysql --password prompts) and the next word may be anything, so keep
            # the stricter password check there.
            if (groups.get("sep") or "").strip() == "=":
                return looks_like_cli_password(raw)
            return looks_like_secret_value(raw, password=True, style="prose")
        return looks_like_secret_value(raw, password=False)
    return True


VALIDATORS = ("credential_value", "token_value", "password_value", "cli_password", "flag_credential")


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
        {"pattern": r"\b(?:postgres|postgresql|mysql|redis|mongodb|amqp|mssql)://[^/\s:@]+:(?P<val>[^/\s:@]+)@", "literals": ["://"], "validator": "password_value",
         "verdict": "ask", "reason": "Output contains database connection string with credentials"},
        {"pattern": r"(?i)\bbearer\s+(?P<val>[A-Za-z0-9._~+/=-]{20,})",
         "literals_ci": ["bearer"], "validator": "token_value",
         "verdict": "ask", "reason": "Output contains bearer token"},
        {"pattern": r"(?i)\bbasic\s+(?P<val>[A-Za-z0-9+/]{12,}={0,2})",
         "literals_ci": ["basic"], "validator": "token_value",
         "verdict": "ask", "reason": "Output contains HTTP Basic credentials"},
        {"pattern": r"(?i)\blogin\s+\S+\s+password\s+(?P<val>\S+)",
         "literals_ci": ["password"], "validator": "password_value",
         "verdict": "ask", "reason": "Output contains .netrc-style login password"},
        {"pattern": (
            r"(?i)(?<![\w-])--?(?P<key>[a-z0-9-]*(?:api-?key|access-?key|secret-?key|auth-?token|access-?token|token|secret"
            r"|password|passwd|passphrase|key))(?![a-z0-9-])(?P<sep>[= ]+)(?P<val>\"[^\"\n]*\"|'[^'\n]*'|[^\s'\"]+)"
         ),
         "literals": ["-"], "validator": "flag_credential",
         "verdict": "ask", "reason": "Output contains credential passed as a command-line flag"},
        {"pattern": (
            r"(?i:\bcurl\b)[^\n|;&]*?\s(?:-u\s*|-U\s*|--(?:proxy-)?user(?:\s+|=))"
            r"(?P<q>[\"']?)[^\s:'\"]*:(?P<val>[^\s'\"]+)"
         ),
         "literals_ci": ["curl"], "validator": "cli_password",
         "verdict": "ask", "reason": "Output contains password passed to curl as user:password"},
        {"pattern": r"(?i:\b(?:mysql|mysqldump|mysqladmin|mariadb)\b)[^\n|;&]*?\s-p(?P<val>[^\s'\"-][^\s'\"]*)",
         "literals_ci": ["mysql", "mariadb"], "validator": "cli_password",
         "verdict": "ask", "reason": "Output contains MySQL password passed with -p"},
        {"pattern": r"\bsshpass\s+-p\s*(?P<val>\"[^\"\n]*\"|'[^'\n]*'|[^\s'\"]+)",
         "literals": ["sshpass"], "validator": "cli_password",
         "verdict": "ask", "reason": "Output contains password passed to sshpass"},
        {"pattern": (
            r"(?i)\b(?P<key>[A-Z0-9_.-]*?(?:API_?KEY|SECRET_?KEY|ACCESS_?KEY|PRIVATE_?KEY|AUTH_?TOKEN|ACCESS_?TOKEN"
            r"|REFRESH_?TOKEN|TOKEN|SECRET|PASSWORD|PASSWD|PASSPHRASE|PWD|CREDENTIALS?)[A-Z0-9_]*)"
            r"[\"']?(?P<sep>\s*(?::=|[:=])\s*)(?P<val>\"[^\"\n]*\"|'[^'\n]*'|[^\s'\"#;,]+)"
         ),
         "literals_ci": ["key", "token", "secret", "pass", "pwd", "credential"], "validator": "credential_value",
         "verdict": "ask", "reason": "Output contains credential assignment"},
    ]

    def __init__(
        self,
        rules: list[dict[str, Any]] | None = None,
        known_secrets: dict[str, str] | None = None,
        config_env_path: str | Path | None = None,
    ):
        raw_rules = rules if rules is not None else self.DEFAULT_OUTPUT_RULES
        self._compiled_rules: list[
            tuple[re.Pattern[str], Verdict, str, tuple[str, ...] | None, tuple[str, ...] | None, str | None]
        ] = []
        self._deny_rules: list[
            tuple[re.Pattern[str], Verdict, str, tuple[str, ...] | None, tuple[str, ...] | None, str | None]
        ] = []
        self._ask_rules: list[
            tuple[re.Pattern[str], Verdict, str, tuple[str, ...] | None, tuple[str, ...] | None, str | None]
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
            validator = r.get("validator")
            if validator is not None and validator not in VALIDATORS:
                validator = None
            rule_entry = (compiled, verdict, message, lits, lits_ci, validator)
            self._compiled_rules.append(rule_entry)
            if verdict == Verdict.DENY:
                self._deny_rules.append(rule_entry)
            else:
                self._ask_rules.append(rule_entry)

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

    _PEM_BLOCK = re.compile(
        r"-----BEGIN [A-Z0-9 _-]*PRIVATE KEY-----[\s\S]*?(?:-----END [A-Z0-9 _-]*PRIVATE KEY-----|\Z)"
    )

    def redact(self, text: str) -> tuple[str, int]:
        """Return (text with secrets replaced, number of replacements).

        Uses the same knowledge as scan(): exact known secrets (your keys from the
        environment and .env files), whole private-key blocks, and every pattern
        rule. For rules with a 'val' group only the value is replaced
        (``api_key=<redacted>``, ``postgres://user:<redacted>@host``); rules with a
        validator only redact values that pass it, so code like ``os.environ[...]``
        is left readable.
        """
        if not text or text.isspace():
            return text, 0
        count = 0
        for secret_val, key_name in self._cached_known_secrets.items():
            if secret_val in text:
                count += text.count(secret_val)
                text = text.replace(secret_val, f"<redacted:{key_name}>")
        text, n = self._PEM_BLOCK.subn("<redacted-private-key>", text)
        count += n

        lowered_text: str | None = None
        for pattern, _verdict, _message, lits, lits_ci, validator in self._compiled_rules:
            if lits is not None and not any(lit in text for lit in lits):
                continue
            if lits_ci is not None:
                if lowered_text is None:
                    lowered_text = text.lower()
                if not any(lit in lowered_text for lit in lits_ci):
                    continue
            hits = 0

            def _replace(m: re.Match[str]) -> str:
                nonlocal hits
                if validator is not None and not _validate_match(validator, m):
                    return m.group(0)
                whole = m.group(0)
                if "val" in m.groupdict() and m.group("val") is not None:
                    start, end = m.span("val")
                    if whole[start - m.start():end - m.start()].startswith("<redacted"):
                        return whole
                    hits += 1
                    return whole[: start - m.start()] + "<redacted>" + whole[end - m.start():]
                if whole.startswith("<redacted"):
                    return whole
                hits += 1
                return "<redacted>"

            prev_text = text
            text = pattern.sub(_replace, text)
            count += hits
            if hits > 0 and text != prev_text:
                lowered_text = None
        return text, count

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

        def _rule_hits(pattern: re.Pattern[str], validator: str | None) -> bool:
            if validator is None:
                return pattern.search(text) is not None
            return any(_validate_match(validator, m) for m in pattern.finditer(text))

        # 1. Check DENY rules first (e.g. private cryptographic keys)
        for pattern, verdict, message, lits, lits_ci, validator in self._deny_rules:
            if not _matches_literals(lits, lits_ci):
                continue
            if _rule_hits(pattern, validator):
                return verdict, message

        # 2. Check known secrets from environment and config files (exact substring match)
        for secret_val, key_name in self._cached_known_secrets.items():
            if secret_val in text:
                return Verdict.ASK, f"Secret scanner: Output contains configured secret ({key_name})"

        # 3. Check remaining pattern rules (e.g. ASK) with literal pre-filtering
        for pattern, verdict, message, lits, lits_ci, validator in self._ask_rules:
            if not _matches_literals(lits, lits_ci):
                continue
            if _rule_hits(pattern, validator):
                return verdict, message

        return None
