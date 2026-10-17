"""
Jev Rubric
Shared rubric loading, request building, and verdict scoring for the Jev
decision-model security engine (`engine = "jev"`) and the evaluation harness
in tools/jev-eval/. Keeping one implementation means the harness tests the
exact scoring code the engine runs.

A rubric is a TOML file with:
  [scoring]  trigger_threshold, ask_threshold, default_verdict
  [state]    preamble (text placed before the action in the Jev state)
  [[rules]]  id, verdict ("deny" | "ask"), question  -> one noul question each
  [choice]   optional choice-question variants (generic / rubric) and thresholds
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    import tomllib  # Python 3.11+
except ModuleNotFoundError:  # pragma: no cover - harness may run on older Pythons
    import tomli as tomllib  # type: ignore

STRICTNESS = {"allow": 0, "ask": 1, "deny": 2}
MODES = ("noul", "choice-generic", "choice-rubric", "combined")
CHOICE_KEY = "verdict_choice"  # question key for the choice question


def stricter(a: str, b: str) -> str:
    return a if STRICTNESS[a] >= STRICTNESS[b] else b


@dataclass
class Rule:
    id: str
    verdict: str
    question: str


@dataclass
class Rubric:
    rules: list[Rule]
    trigger: float
    ask: float
    default_verdict: str
    preamble: str
    choice_variants: dict[str, dict[str, Any]] = field(default_factory=dict)
    deny_threshold: float = 0.5
    unsafe_threshold: float = 0.5
    version: str = ""

    @classmethod
    def load(cls, path: str | Path) -> Rubric:
        with open(path, "rb") as f:
            cfg = tomllib.load(f)
        return cls.from_dict(cfg)

    @classmethod
    def from_dict(cls, cfg: dict[str, Any]) -> Rubric:
        scoring = cfg.get("scoring", {})
        rules = [Rule(r["id"], str(r["verdict"]).lower(), str(r["question"]).strip()) for r in cfg.get("rules", [])]
        if not rules:
            raise ValueError("rubric has no [[rules]]")
        seen: set[str] = set()
        for r in rules:
            if r.verdict not in ("ask", "deny"):
                raise ValueError(f"rule {r.id}: verdict must be 'ask' or 'deny', got {r.verdict!r}")
            if r.id == CHOICE_KEY:
                raise ValueError(f"rule id {CHOICE_KEY!r} is reserved")
            if r.id in seen:
                raise ValueError(f"duplicate rule id {r.id!r}")
            seen.add(r.id)
        choice = cfg.get("choice", {})
        variants = {k: v for k, v in choice.items() if isinstance(v, dict)}
        default_verdict = str(scoring.get("default_verdict", "allow")).lower()
        if default_verdict not in STRICTNESS:
            raise ValueError(f"default_verdict must be allow/ask/deny, got {default_verdict!r}")
        return cls(
            rules=rules,
            trigger=float(scoring.get("trigger_threshold", 0.7)),
            ask=float(scoring.get("ask_threshold", 0.3)),
            default_verdict=default_verdict,
            preamble=str(cfg.get("state", {}).get("preamble", "")).strip(),
            choice_variants=variants,
            deny_threshold=float(choice.get("deny_threshold", 0.5)),
            unsafe_threshold=float(choice.get("unsafe_threshold", 0.5)),
            version=str(cfg.get("version", "")),
        )

    # ------------------------------------------------------------------ requests

    def _choice_question(self, variant: str) -> dict[str, Any]:
        v = self.choice_variants.get(variant)
        if not v:
            raise ValueError(f"rubric has no [choice.{variant}] section")
        return {"type": "choice", "instructions": str(v["instructions"]).strip(), "criteria": dict(v["criteria"])}

    def questions(self, mode: str = "noul") -> dict[str, dict[str, Any]]:
        if mode not in MODES:
            raise ValueError(f"unknown mode {mode!r}; expected one of {MODES}")
        q: dict[str, dict[str, Any]] = {}
        if mode in ("noul", "combined"):
            q.update({r.id: {"type": "noul", "instructions": r.question} for r in self.rules})
        if mode == "choice-generic":
            q[CHOICE_KEY] = self._choice_question("generic")
        elif mode in ("choice-rubric", "combined"):
            q[CHOICE_KEY] = self._choice_question("rubric")
        return q

    def build_state(self, tool: str, parameters: dict[str, Any], context: dict[str, Any] | None = None) -> str:
        action = {"tool": tool, "parameters": parameters, "context": context or {}}
        return f"{self.preamble}\n\nACTION:\n{json.dumps(action, indent=2, ensure_ascii=False)}"

    # ------------------------------------------------------------------ verdicts

    def noul_verdict(self, scores: dict[str, float | None]) -> tuple[str, list[str]]:
        """Return (verdict, [reasons]) from per-rule probabilities; strictest rule wins."""
        verdict = self.default_verdict
        reasons: list[str] = []
        for r in self.rules:
            p = scores.get(r.id)
            if p is None or math.isnan(p):  # missing or invalid answer -> treat as uncertain
                v = "ask"
                reasons.append(f"{r.id}=missing->ask")
            elif p >= self.trigger:
                v = r.verdict
                reasons.append(f"{r.id}={p:.2f}->{v}")
            elif p >= self.ask:
                v = "ask"
                reasons.append(f"{r.id}={p:.2f}->ask(uncertain)")
            else:
                continue
            verdict = stricter(verdict, v)
        return verdict, reasons

    def choice_verdict(self, ch: dict[str, Any] | None) -> tuple[str, list[str]]:
        if not ch or ch.get("choice") not in STRICTNESS:
            return "ask", ["choice=missing->ask"]
        probs = ch.get("probabilities") or {}
        p_deny = probs.get("deny", 0.0)
        p_unsafe = p_deny + probs.get("ask", 0.0)
        verdict = ch["choice"]
        reasons = [f"choice={verdict} (allow {probs.get('allow', 0):.2f} / ask {probs.get('ask', 0):.2f} / deny {p_deny:.2f})"]
        if p_deny >= self.deny_threshold and verdict != "deny":
            verdict = "deny"
            reasons.append(f"P(deny)={p_deny:.2f}->deny")
        elif p_unsafe >= self.unsafe_threshold and verdict == "allow":
            verdict = "ask"
            reasons.append(f"P(ask+deny)={p_unsafe:.2f}->ask")
        return verdict, reasons

    def evaluate(self, rec: dict[str, Any], mode: str) -> tuple[str, list[str]]:
        """Verdict for a parsed record {"scores": {...}, "choice": {...}} under a mode.

        `mode` may also be "choice" (either choice variant) to grade one half of
        a combined record.
        """
        if mode == "noul":
            return self.noul_verdict(rec.get("scores") or {})
        if mode in ("choice-generic", "choice-rubric", "choice"):
            return self.choice_verdict(rec.get("choice"))
        if mode == "combined":
            v1, r1 = self.noul_verdict(rec.get("scores") or {})
            v2, r2 = self.choice_verdict(rec.get("choice"))
            return stricter(v1, v2), r1 + r2
        raise ValueError(mode)

    def parse_answers(self, answers: dict[str, Any], mode: str) -> dict[str, Any]:
        """Turn a raw API `answers` object into {"scores": ..., "choice": ...}."""
        rec: dict[str, Any] = {}
        if mode in ("noul", "combined"):
            rec["scores"] = {r.id: parse_noul(answers.get(r.id)) for r in self.rules}
        if mode != "noul":
            rec["choice"] = parse_choice(answers.get(CHOICE_KEY))
        return rec


def parse_noul(answer: dict[str, Any] | None) -> float | None:
    if not isinstance(answer, dict):
        return None
    val = answer.get("noul")
    if isinstance(val, (int, float)) and not isinstance(val, bool):
        return float(val)
    # Fallback shape: {"answer": bool, "confidence": float}
    ans = answer.get("answer")
    conf = answer.get("confidence")
    if isinstance(ans, bool) and isinstance(conf, (int, float)):
        return float(conf) if ans else 1.0 - float(conf)
    if isinstance(ans, (int, float)) and not isinstance(ans, bool):
        return float(ans)
    return None


def parse_choice(answer: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(answer, dict):
        return None
    choice = str(answer.get("choice") or answer.get("answer") or "").strip().lower()
    probs_raw = answer.get("probabilities") or {}
    probs: dict[str, float] = {}
    if isinstance(probs_raw, dict):
        for k, v in probs_raw.items():
            try:
                probs[str(k).strip().lower()] = float(v)
            except (TypeError, ValueError):
                pass
    conf = answer.get("confidence")
    if not probs and choice in STRICTNESS and isinstance(conf, (int, float)):
        probs = {choice: float(conf)}
    return {"choice": choice, "probabilities": probs, "confidence": conf}
