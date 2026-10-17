"""
Jev Decision-Model Policy Engine (engine = "jev")
Judges each tool call with the TypeSafe Jev decision model: one noul question
per rubric rule, all sent in a single request; the strictest triggered rule
sets the verdict (see jev_rubric.py and tools/jev-eval/jev_proof_of_concept.md).

Safety properties:
  * Security self-protection floor runs first (no API call for those requests).
  * Secrets are redacted from the action before it leaves the machine.
  * Oversized string parameters are cut to head + tail and the verdict is
    raised to at least ASK, so a padded payload cannot hide past the cut.
  * Any API failure (timeout, HTTP error, bad JSON, missing key) resolves via
    `on_error`: "auto" = ASK when interactive, DENY when not.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import shutil
import time
import urllib.error
import urllib.request
from collections import OrderedDict
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from chatybot.security import self_protect
from chatybot.security.base import BasePolicyEngine
from chatybot.security.jev_rubric import MODES, Rubric, stricter
from chatybot.security.models import (
    PolicyDecision,
    PolicyPromptDetails,
    PolicyRequest,
    Verdict,
)

logger = logging.getLogger(__name__)

DEFAULT_RUBRIC_PATH = "~/.config/chatybot/jev_security.toml"
BUNDLED_RUBRIC = os.path.join(os.path.dirname(__file__), "default_jev_security.toml")

DEFAULT_SKIP_TOOLS = [
    "ask_user", "get_context_metrics", "session_get", "session_search",
    "search_skills", "decide_choice", "decide_score", "decide_noul",
]

_REDACTIONS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"(?i)\b(bearer)\s+[A-Za-z0-9._~+/=-]{8,}"), r"\1 <redacted>"),
    (re.compile(r"""(?i)\b([A-Z0-9_]*(?:api[_-]?key|token|secret|passw(?:or)?d)[A-Z0-9_]*|authorization)\s*([=:])\s*(?:(['"])(.*?)\3|[^\s'\"&;|]+)"""), r"\1\2<redacted>"),
    (re.compile(r"\bsk-[A-Za-z0-9_-]{12,}"), "<redacted-key>"),
    (re.compile(r"\b(?:ghp|gho|ghs|github_pat)_[A-Za-z0-9_]{12,}"), "<redacted-key>"),
    (re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "<redacted-key>"),
    (re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}"), "<redacted-key>"),
    (re.compile(r"(?i)\b([a-z][a-z0-9+.-]*://[^:/\s]+):[^@/\s]+@"), r"\1:<redacted>@"),
]


def redact_text(text: str) -> str:
    for pattern, repl in _REDACTIONS:
        text = pattern.sub(repl, text)
    return text


def _prepare(value: Any, redact: bool, max_chars: int, state: dict[str, bool]) -> Any:
    """Recursively redact secrets and cut oversized strings (head + tail)."""
    if isinstance(value, str):
        out = redact_text(value) if redact else value
        if max_chars and len(out) > max_chars:
            half = max_chars // 2
            omitted = len(out) - 2 * half
            out = f"{out[:half]}\n...[TRUNCATED {omitted} characters]...\n{out[-half:]}"
            state["truncated"] = True
        return out
    if isinstance(value, dict):
        return {k: _prepare(v, redact, max_chars, state) for k, v in value.items()}
    if isinstance(value, list):
        return [_prepare(v, redact, max_chars, state) for v in value]
    return value


def _urllib_post(url: str, body: dict[str, Any], headers: dict[str, str], timeout: float) -> dict[str, Any]:
    req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"), headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:300] if hasattr(e, "read") else ""
        raise RuntimeError(f"HTTP {e.code}: {detail}") from e


class JevPolicyEngine(BasePolicyEngine):
    """Policy engine backed by the Jev decision model and a rubric file."""

    def __init__(
        self,
        rubric_path: str = DEFAULT_RUBRIC_PATH,
        model: str = "typesafe/jev-1.13",
        base_url: str = "https://openrouter.ai",
        endpoint_path: str = "/api/alpha/decisions",
        api_key_env: str = "OPENROUTER_API_KEY",
        timeout_seconds: float = 2.5,
        on_error: str = "auto",
        mode: str = "noul",
        cache: bool = True,
        cache_size: int = 512,
        redact_secrets: bool = True,
        max_content_chars: int = 8000,
        skip_tools: list[str] | None = None,
        log_path: str = "",
        debug: bool = False,
        http_post: Callable[[str, dict[str, Any], dict[str, str], float], dict[str, Any]] | None = None,
    ):
        self.debug = debug
        self.rubric_path = os.path.abspath(os.path.expanduser(rubric_path or DEFAULT_RUBRIC_PATH))
        self._seed_rubric()
        self.rubric = Rubric.load(self.rubric_path)
        if mode not in MODES:
            raise ValueError(f"[jev] mode must be one of {MODES}, got {mode!r}")
        self.mode = mode
        self.questions = self.rubric.questions(mode)  # validates choice sections early
        self.model = model
        self.url = f"{base_url.rstrip('/')}{endpoint_path}"
        self.api_key_env = api_key_env
        self.timeout_seconds = float(timeout_seconds)
        self.on_error = str(on_error).lower()
        if self.on_error not in ("auto", "ask", "deny"):
            raise ValueError(f"[jev] on_error must be auto/ask/deny, got {on_error!r}")
        self.cache_enabled = cache
        self.cache_size = max(1, int(cache_size))
        self._cache: OrderedDict[str, PolicyDecision] = OrderedDict()
        self.redact_secrets = redact_secrets
        self.max_content_chars = int(max_content_chars)
        self.skip_tools = {t.lower() for t in (DEFAULT_SKIP_TOOLS if skip_tools is None else skip_tools)}
        self.log_path = os.path.abspath(os.path.expanduser(log_path)) if log_path else ""
        self._http_post = http_post or _urllib_post
        self._api_key: str | None = None

        if self.debug:
            print(f"[Security Debug] [JEV] Rubric '{self.rubric_path}': {len(self.rubric.rules)} rules, "
                  f"trigger >= {self.rubric.trigger}, ask >= {self.rubric.ask}, mode {self.mode}, model {self.model}")
            for r in self.rubric.rules:
                print(f"  [Definition: Jev Rule] [{r.verdict.upper()}] {r.id}: {r.question[:90]}")

    # ------------------------------------------------------------------ setup

    def _seed_rubric(self) -> None:
        if os.path.exists(self.rubric_path):
            return
        try:
            os.makedirs(os.path.dirname(self.rubric_path), exist_ok=True)
            shutil.copy2(BUNDLED_RUBRIC, self.rubric_path)
            print(f"[Security Sync] Initialized Jev rubric at '{self.rubric_path}'")
        except OSError as e:
            logger.warning("[Security Warning] Could not seed Jev rubric to '%s': %s. Using bundled default.", self.rubric_path, e)
            self.rubric_path = BUNDLED_RUBRIC

    def _get_api_key(self) -> str:
        if self._api_key:
            return self._api_key
        key = os.environ.get(self.api_key_env, "")
        if not key:
            try:
                from chatybot.env_utils import load_project_env_files, resolve_api_key

                load_project_env_files()
                key = resolve_api_key(self.api_key_env) or ""
            except Exception as e:  # noqa: BLE001
                logger.warning("[Security Warning] Jev API key resolution failed: %s", e)
        self._api_key = key or None
        return key

    # ------------------------------------------------------------------ evaluate

    def _error_decision(self, request: PolicyRequest, why: str) -> PolicyDecision:
        if self.on_error == "auto":
            verdict = Verdict.ASK if request.context.get("interactive", False) else Verdict.DENY
        else:
            verdict = Verdict(self.on_error)
        reason = f"Jev security check unavailable ({why}); failing safe to {verdict.value}."
        details = None
        if verdict == Verdict.ASK:
            details = PolicyPromptDetails(title="Jev Security Check Unavailable",
                                          message=f"Could not reach the Jev decision model. Authorize '{request.tool}' anyway?",
                                          risk_level="high")
        return PolicyDecision(verdict=verdict, reason=reason, prompt_details=details)

    def evaluate(self, request: PolicyRequest) -> PolicyDecision:
        tool = (request.tool or "").strip()
        blocked = self_protect.check(request)
        if blocked is not None:
            if self.debug:
                print(f"[Security Debug] [JEV] [SPECIAL DENY] {blocked.reason}")
            return blocked
        if tool.lower() in self.skip_tools:
            return PolicyDecision(verdict=Verdict.ALLOW, reason=f"Jev: '{tool}' is not checked (skip_tools).")

        trunc_state = {"truncated": False}
        params = _prepare(request.parameters or {}, self.redact_secrets, self.max_content_chars, trunc_state)
        cache_key = hashlib.sha256(
            json.dumps(
                [tool, request.parameters or {}, self.mode, os.getcwd(), bool(request.context.get("interactive", False))],
                sort_keys=True,
                default=str,
            ).encode()
        ).hexdigest()
        if self.cache_enabled and cache_key in self._cache:
            self._cache.move_to_end(cache_key)
            cached = self._cache[cache_key]
            if self.debug:
                print(f"[Security Debug] [JEV] Cache hit for '{tool}': {cached.verdict.value}")
            return cached

        api_key = self._get_api_key()
        if not api_key:
            return self._error_decision(request, f"API key '{self.api_key_env}' is not set")

        context = {"working_directory": os.getcwd(), "interactive": bool(request.context.get("interactive", False))}
        body = {"state": self.rubric.build_state(tool, params, context), "model": self.model, "questions": self.questions}
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

        t0 = time.perf_counter()
        try:
            resp = self._http_post(self.url, body, headers, self.timeout_seconds)
            answers = resp.get("answers") if isinstance(resp, dict) else None
            if not isinstance(answers, dict) or not answers:
                raise ValueError("response has no answers")
        except Exception as e:  # noqa: BLE001
            ms = (time.perf_counter() - t0) * 1000
            if self.debug:
                print(f"[Security Debug] [JEV] Request failed after {ms:.0f} ms: {e}")
            decision = self._error_decision(request, f"{type(e).__name__}: {str(e)[:200]}")
            self._log(request, params, None, decision, ms, error=str(e)[:300])
            return decision
        ms = (time.perf_counter() - t0) * 1000

        rec = self.rubric.parse_answers(answers, self.mode)
        verdict, reasons = self.rubric.evaluate(rec, self.mode)
        if trunc_state["truncated"]:
            if verdict != "deny":
                verdict = stricter(verdict, "ask")
            reasons.append("parameters truncated before review->at least ask")

        decision = self._decision(tool, verdict, reasons)
        if self.debug:
            print(f"[Security Debug] [JEV] '{tool}' -> {verdict.upper()} in {ms:.0f} ms: {decision.reason}")
        self._log(request, params, rec, decision, ms, usage=resp.get("usage"))
        if self.cache_enabled:
            self._cache[cache_key] = decision
            if len(self._cache) > self.cache_size:
                self._cache.popitem(last=False)
        return decision

    def _decision(self, tool: str, verdict: str, reasons: list[str]) -> PolicyDecision:
        reason = "Jev: " + ("; ".join(reasons) if reasons else "no rule triggered")
        v = Verdict(verdict)
        details = None
        if v == Verdict.ASK:
            fired = [r for r in reasons if "->ask" in r or "->deny" in r]
            uncertain_only = all("uncertain" in r or "truncated" in r or "missing" in r for r in fired) if fired else True
            details = PolicyPromptDetails(
                title="Jev Security Review",
                message=f"Jev flagged '{tool}': " + ("; ".join(fired[:3]) if fired else "review requested"),
                risk_level="medium" if uncertain_only else "high",
            )
        return PolicyDecision(verdict=v, reason=reason, prompt_details=details)

    def _log(self, request, params, rec, decision, ms, usage=None, error=None) -> None:
        if not self.log_path:
            return
        entry = {
            "ts": datetime.now(UTC).isoformat(),
            "request_id": request.request_id,
            "tool": request.tool,
            "parameters": params,
            "verdict": decision.verdict.value,
            "reason": decision.reason,
            "latency_ms": round(ms, 1),
            "model": self.model,
            "mode": self.mode,
            "rubric_version": self.rubric.version,
        }
        if rec is not None:
            entry.update(rec)
        if usage:
            entry["usage"] = usage
        if error:
            entry["error"] = error
        try:
            os.makedirs(os.path.dirname(self.log_path), exist_ok=True)
            with open(self.log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False, default=str) + "\n")
        except OSError as e:
            logger.warning("[Security Warning] Could not write Jev log '%s': %s", self.log_path, e)

    def get_banner(self) -> str:
        return f"Jev ({self.model}, {len(self.rubric.rules)} rules, mode {self.mode})"
