"""
Chained Policy Engine (engine = "chain")
Runs several policy engines on every tool call.

Each stage has a mode:
  * "enforce" - its verdict counts; the final verdict is the strictest
                enforcing verdict (deny > ask > allow).
  * "shadow"  - pass-through: evaluated and logged, but never changes the
                outcome. Use it to trial a new engine (e.g. Jev) against the
                one you trust before switching over.

Once an enforcing stage returns DENY, later enforcing stages are skipped (the
outcome cannot get stricter). Shadow stages still run by default
(`shadow_on_deny = true`) so the comparison log covers every call.

Every call can be written to a JSONL log (`log_path`) with each stage's
verdict, reason and latency, plus whether the stages disagreed. A failing
enforcing stage resolves to the manager's fail_safe verdict; a failing shadow
stage is only logged.
"""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from chatybot.security.base import BasePolicyEngine
from chatybot.security.models import PolicyDecision, PolicyRequest, Verdict

logger = logging.getLogger(__name__)

_STRICT = {Verdict.ALLOW: 0, Verdict.ASK: 1, Verdict.DENY: 2}


@dataclass
class ChainStage:
    name: str
    engine: BasePolicyEngine
    mode: str = "enforce"  # "enforce" | "shadow"


class ChainedPolicyEngine(BasePolicyEngine):
    """Combines policy engines; enforcing stages decide, shadow stages only log."""

    def __init__(
        self,
        stages: list[ChainStage],
        fail_safe: Verdict = Verdict.DENY,
        shadow_on_deny: bool = True,
        log_path: str = "",
        redact_log: bool = True,
        debug: bool = False,
    ):
        if not stages:
            raise ValueError("[chain] needs at least one stage")
        for s in stages:
            if s.mode not in ("enforce", "shadow"):
                raise ValueError(f"[chain] stage '{s.name}': mode must be 'enforce' or 'shadow', got {s.mode!r}")
        if not any(s.mode == "enforce" for s in stages):
            raise ValueError("[chain] needs at least one stage with mode = 'enforce'")
        self.stages = stages
        self.fail_safe = fail_safe
        self.shadow_on_deny = shadow_on_deny
        self.log_path = os.path.abspath(os.path.expanduser(log_path)) if log_path else ""
        self._log_dir_ensured = False
        if self.log_path:
            try:
                os.makedirs(os.path.dirname(self.log_path), exist_ok=True)
                self._log_dir_ensured = True
            except OSError:
                pass
        self.redact_log = redact_log
        self.debug = debug

    def _run_stage(self, stage: ChainStage, request: PolicyRequest, output_phase: bool = False) -> tuple[PolicyDecision | None, float, str | None]:
        t0 = time.perf_counter()
        try:
            if output_phase:
                if hasattr(stage.engine, "supports_output_evaluation") and not stage.engine.supports_output_evaluation():
                    return PolicyDecision(verdict=Verdict.ALLOW, reason=f"Stage '{stage.name}' does not inspect output."), 0.0, None
                fn = getattr(stage.engine, "evaluate_output", None)
                if fn is None:
                    return PolicyDecision(verdict=Verdict.ALLOW, reason=f"Stage '{stage.name}' does not implement evaluate_output."), 0.0, None
            else:
                fn = stage.engine.evaluate
            dec = fn(request)

            if not isinstance(dec, PolicyDecision):
                raise TypeError(f"engine returned {type(dec).__name__}, not PolicyDecision")
            return dec, (time.perf_counter() - t0) * 1000, None
        except Exception as e:  # noqa: BLE001
            return None, (time.perf_counter() - t0) * 1000, f"{type(e).__name__}: {e}"

    def evaluate(self, request: PolicyRequest) -> PolicyDecision:
        return self._evaluate_common(request, output_phase=False)

    def evaluate_output(self, request: PolicyRequest) -> PolicyDecision:
        return self._evaluate_common(request, output_phase=True)

    def _evaluate_common(self, request: PolicyRequest, output_phase: bool = False) -> PolicyDecision:
        final: PolicyDecision | None = None
        final_stage = ""
        denied = False
        results: list[dict[str, Any]] = []

        for stage in self.stages:
            if stage.mode == "enforce" and denied:
                results.append({"stage": stage.name, "mode": stage.mode, "skipped": "earlier enforcing stage denied"})
                continue
            if stage.mode == "shadow" and denied and not self.shadow_on_deny:
                results.append({"stage": stage.name, "mode": stage.mode, "skipped": "shadow_on_deny = false"})
                continue

            dec, ms, err = self._run_stage(stage, request, output_phase=output_phase)
            entry: dict[str, Any] = {"stage": stage.name, "mode": stage.mode, "latency_ms": round(ms, 1)}
            if err is not None:
                entry["error"] = err[:300]
                if stage.mode == "enforce":
                    dec = PolicyDecision(
                        verdict=self.fail_safe,
                        reason=f"Chain stage '{stage.name}' failed ({err[:200]}). Failing safe to {self.fail_safe.value}.",
                    )
            if dec is not None:
                entry["verdict"] = dec.verdict.value
                entry["reason"] = dec.reason
            results.append(entry)

            if self.debug:
                tag = "SHADOW" if stage.mode == "shadow" else "ENFORCE"
                shown = entry.get("verdict", "error").upper()
                phase_tag = "[OUTPUT] " if output_phase else ""
                print(f"[Security Debug] [CHAIN] {phase_tag}[{tag}] {stage.name}: {shown} ({ms:.0f} ms) {entry.get('reason') or entry.get('error', '')}")

            if stage.mode == "enforce" and dec is not None:
                if final is None or _STRICT[dec.verdict] > _STRICT[final.verdict]:
                    final, final_stage = dec, stage.name
                if dec.verdict == Verdict.DENY:
                    denied = True

        assert final is not None  # at least one enforcing stage always runs
        out = PolicyDecision(
            verdict=final.verdict,
            reason=f"[{final_stage}] {final.reason}" if len(self.stages) > 1 else final.reason,
            prompt_details=final.prompt_details,
            modified_parameters=final.modified_parameters if final.verdict != Verdict.DENY else None,
        )
        self._log(request, out, final_stage, results)
        return out

    def _log(self, request: PolicyRequest, final: PolicyDecision, decided_by: str, results: list[dict[str, Any]]) -> None:
        if not self.log_path:
            return
        verdicts = {r["verdict"] for r in results if "verdict" in r}
        params: Any = request.parameters
        if self.redact_log:
            from chatybot.security.jev import prepare_for_log

            params = prepare_for_log(request.parameters or {})
        entry = {
            "event": "decision",
            "ts": datetime.now(UTC).isoformat(),
            "request_id": request.request_id,
            "tool": request.tool,
            "parameters": params,
            "interactive": bool(request.context.get("interactive", False)),
            "final": final.verdict.value,
            "decided_by": decided_by,
            "disagreement": len(verdicts) > 1,
            "total_ms": round(sum(r.get("latency_ms", 0.0) for r in results), 1),
            "stages": results,
        }
        self._write(entry)

    def _write(self, entry: dict[str, Any]) -> None:
        try:
            if not self._log_dir_ensured:
                os.makedirs(os.path.dirname(self.log_path), exist_ok=True)
                self._log_dir_ensured = True
            with open(self.log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False, default=str) + "\n")
        except OSError as e:
            logger.warning("[Security Warning] Could not write chain log '%s': %s", self.log_path, e)

    def record_outcome(self, request_id: str, tool: str, outcome: str, detail: str = "") -> None:
        """Append what happened to an ASK (approved, declined, ...) and pass it on to stages that log."""
        if self.log_path:
            self._write({
                "event": "outcome",
                "ts": datetime.now(UTC).isoformat(),
                "request_id": request_id,
                "tool": tool,
                "outcome": outcome,
                "detail": detail,
            })
        for stage in self.stages:
            fn = getattr(stage.engine, "record_outcome", None)
            if fn is not None:
                try:
                    fn(request_id, tool, outcome, detail)
                except Exception as e:  # noqa: BLE001
                    logger.warning("[Security Warning] Stage '%s' could not record outcome: %s", stage.name, e)

    # Loop refusal events describe the tool loop, not a stage, so the chain logs
    # them once in its own log and does not pass them on (that double-counted
    # them when security_chain.jsonl and jev_security.jsonl were read together).
    def record_refusal_repeat(
        self,
        request_id: str,
        tool: str,
        parameters: dict[str, Any] | None = None,
        reason: str = "",
        session_id: str = "",
    ) -> None:
        """Log a repeat tool refusal served from the per-loop memory."""
        if not self.log_path:
            return
        from chatybot.security.jev import refusal_repeat_entry

        self._write(refusal_repeat_entry(request_id, tool, parameters, reason, session_id, redact=self.redact_log))

    def record_refusal_limit(
        self,
        limit: int,
        request_ids: list[str] | None = None,
        refused_calls: list[dict[str, Any]] | None = None,
        session_id: str = "",
    ) -> None:
        """Log a loop ended by reaching the security refusal limit."""
        if not self.log_path:
            return
        from chatybot.security.jev import refusal_limit_entry

        self._write(refusal_limit_entry(limit, request_ids, refused_calls, session_id, redact=self.redact_log))

    def get_banner(self) -> str:
        parts = []
        for s in self.stages:
            try:
                inner = s.engine.get_banner()
            except Exception:  # noqa: BLE001
                inner = type(s.engine).__name__
            parts.append(f"{s.name}[{s.mode}]: {inner}")
        return "Chain: " + " -> ".join(parts)
