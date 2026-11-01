#!/usr/bin/env python3
"""Per-completion prompt-cache report for chatybot sessions.

Reads a session's turns.jsonl and reconstructs the cache telemetry of every
API completion in each agentic turn, in order:

  1. the pre-loop completion (the turn's own completion, which issued the
     iteration-1 tool calls),
  2. each in-loop completion (attached to the tool events it requested),
  3. the terminal completion (derived from the turn-level cache_stats totals
     minus the recorded in-loop completions).

Usage examples:
  # Most recent session, per-turn blow-by-blow
  scripts/session_cache_report.py

  # A specific session by directory name (substring match) or full path
  scripts/session_cache_report.py --session mistral_4
  scripts/session_cache_report.py --session ~/.local/share/chatybot/sessions/foo/turns.jsonl

  # 10 most recent Mistral sessions plus the cache-activation floor analysis
  scripts/session_cache_report.py --last 10 --model mistral --floor

  # Machine-readable output
  scripts/session_cache_report.py --session mistral_4 --json

Notes on the data model (see chatybot_app.py process_tool_loop):
  * Each agentic_loop tool record carries a "cache" dict with the telemetry
    of the completion that requested that tool call. Multiple tool calls
    issued by one completion share identical metrics.
  * The turn-level cache_stats accumulates only the in-loop completions:
    the pre-loop re-request (if any), one completion at the end of every
    loop iteration, and the final summary completion. The turn's own
    pre-loop completion is counted only when chatybot had to re-request an
    initial tool call because the previous completion was not a tool call.
  * In streaming mode the provider usage is not parsed, so every counter
    degrades to 0; such turns are reported as telemetry-unavailable.
"""

import argparse
import json
import os
import sys
from dataclasses import dataclass, field
from typing import Any

DEFAULT_SESSIONS_DIR = os.path.expanduser("~/.local/share/chatybot/sessions")

FLOOR_BUCKETS: list[tuple[int, int]] = [
    (0, 2_000),
    (2_000, 4_000),
    (4_000, 8_000),
    (8_000, 12_000),
    (12_000, 16_000),
    (16_000, 24_000),
    (24_000, 40_000),
    (40_000, 1 << 30),
]


@dataclass
class Completion:
    """Cache telemetry of a single API completion."""

    role: str
    prompt_tokens: int
    cached_tokens: int
    source: str  # "recorded" | "derived" | "unavailable"
    notes: str = ""


@dataclass
class TurnReport:
    session: str
    turn_id: Any
    model: str
    timestamp: str
    elapsed_ms: Any
    prompt: str
    prompt_slug: str = ""
    tool_events: int = 0
    iterations: int = 0
    completions: list[Completion] = field(default_factory=list)
    totals: dict[str, Any] = field(default_factory=dict)
    telemetry_available: bool = True
    warnings: list[str] = field(default_factory=list)


def _as_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _hit_pct(cached: int, prompt: int) -> float:
    return 100.0 * cached / prompt if prompt else 0.0


def iter_session_dirs(sessions_dir: str) -> list[str]:
    """Session directory names that contain a turns.jsonl, newest first."""
    entries = []
    for name in os.listdir(sessions_dir):
        path = os.path.join(sessions_dir, name)
        if os.path.isfile(os.path.join(path, "turns.jsonl")):
            entries.append((os.path.getmtime(path), name))
    entries.sort(reverse=True)
    return [name for _, name in entries]


def load_session_names(
    sessions_dir: str, last: int, model_filter: str | None
) -> list[tuple[str, str]]:
    """Return (session_name, turns.jsonl path) for the N most recent sessions,
    optionally filtered by model alias prefix."""
    selected: list[tuple[str, str]] = []
    for name in iter_session_dirs(sessions_dir):
        path = os.path.join(sessions_dir, name, "turns.jsonl")
        if model_filter:
            models = set()
            for line in open(path, encoding="utf-8"):
                try:
                    turn = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(turn, dict) and turn.get("model_alias"):
                    models.add(str(turn["model_alias"]))
            if not any(m.startswith(model_filter) for m in models):
                continue
        selected.append((name, path))
        if len(selected) >= last:
            break
    return selected


def build_turn_report(session: str, turn: dict[str, Any]) -> TurnReport:
    """Reconstruct the per-completion cache telemetry for one agentic turn."""
    report = TurnReport(
        session=session,
        turn_id=turn.get("turn_id"),
        model=str(turn.get("model_alias", "?")),
        timestamp=str(turn.get("timestamp", "?")),
        elapsed_ms=turn.get("elapsed_ms"),
        prompt=str(turn.get("prompt", "")),
    )
    report.prompt_slug = report.prompt.strip().replace("\n", " ")[:70]
    totals = turn.get("cache_stats")
    report.totals = totals if isinstance(totals, dict) else {}

    loop = turn.get("agentic_loop") or []
    report.tool_events = len(loop)

    # Group tool events by loop iteration; all events of one iteration share
    # the metrics of the completion that requested them.
    by_iteration: dict[int, list[dict[str, Any]]] = {}
    for event in loop:
        if isinstance(event, dict):
            by_iteration.setdefault(_as_int(event.get("turn")), []).append(event)
    if not by_iteration:
        report.telemetry_available = False
        report.warnings.append("no agentic_loop events recorded for this turn")
        return report
    iteration_ids = sorted(by_iteration)
    report.iterations = iteration_ids[-1]
    call_counts = {i: len(evs) for i, evs in by_iteration.items()}

    metrics: dict[int, dict[str, Any] | None] = {}
    for it, events in by_iteration.items():
        distinct = {
            json.dumps(e.get("cache"), sort_keys=True)
            for e in events
            if e.get("cache") is not None
        }
        if len(distinct) > 1:
            report.warnings.append(
                f"iteration {it} has {len(distinct)} distinct cache blocks; using the first"
            )
        first = next((e.get("cache") for e in events if e.get("cache") is not None), None)
        metrics[it] = first

    recorded_values = [m for m in metrics.values() if m is not None]
    if not recorded_values or all(_as_int(m.get("prompt_tokens")) == 0 for m in recorded_values):
        report.telemetry_available = False
        report.completions = [
            Completion(
                role=f"in-loop (issued iter-{it} calls)",
                prompt_tokens=0,
                cached_tokens=0,
                source="unavailable",
                notes="usage not parsed (streaming mode?)",
            )
            for it in iteration_ids
        ]
        return report

    n = report.iterations
    api_calls = _as_int(report.totals.get("api_calls"))
    total_prompt = _as_int(report.totals.get("prompt_tokens"))
    total_cached = _as_int(report.totals.get("cached_tokens"))

    def recorded(it: int) -> tuple[int, int] | None:
        m = metrics.get(it)
        if m is None:
            return None
        return _as_int(m.get("prompt_tokens")), _as_int(m.get("cached_tokens"))

    # Which completions are counted in cache_stats? The turn's own pre-loop
    # completion is counted only when chatybot re-requested an initial tool
    # call (api_calls == n + 1); the in-loop completions (ends of iterations
    # 1..n) always are.
    preloop_counted = api_calls == n + 1
    sums = {"prompt": 0, "cached": 0}

    def add(role: str, prompt_tok: int, cached_tok: int, source: str, notes: str, counted: bool) -> None:
        report.completions.append(
            Completion(role=role, prompt_tokens=prompt_tok, cached_tokens=cached_tok, source=source, notes=notes)
        )
        if counted:
            sums["prompt"] += prompt_tok
            sums["cached"] += cached_tok

    # The completion that issued the iteration-k tool calls is the turn's
    # pre-loop completion for k=1 and the in-loop completion at the end of
    # iteration k-1 for k >= 2.
    for it in iteration_ids:
        m = metrics.get(it)
        if m is None:
            continue
        pt, ct = _as_int(m.get("prompt_tokens")), _as_int(m.get("cached_tokens"))
        calls = call_counts.get(it, 0)
        if it == 1:
            if preloop_counted:
                add(f"pre-loop re-request (issued {calls} iter-1 calls)", pt, ct, "recorded", "", True)
            else:
                add(f"pre-loop (issued {calls} iter-1 calls)", pt, ct, "recorded", "not in turn totals", False)
        else:
            add(f"in-loop (issued {calls} iter-{it} calls)", pt, ct, "recorded", "", True)

    # The terminal completion (end of iteration n: natural-language answer or
    # max-turns summary) produced no tool events, so derive it from the
    # turn-level totals minus the recorded in-loop completions.
    if api_calls >= n:
        term_prompt = total_prompt - sums["prompt"]
        term_cached = total_cached - sums["cached"]
        if term_prompt > 0 or term_cached > 0:
            add(
                "terminal (final answer)",
                term_prompt,
                term_cached,
                "derived",
                "totals minus recorded in-loop completions",
                True,
            )
        if sums["prompt"] != total_prompt or sums["cached"] != total_cached:
            report.warnings.append(
                f"reconciliation mismatch: in-loop sum {sums['prompt']}/{sums['cached']} "
                f"vs totals {total_prompt}/{total_cached}"
            )
    elif api_calls == n - 1:
        report.warnings.append(
            "loop terminated without a terminal completion (refusal or guard break); "
            f"reconciliation: in-loop sum {sums['prompt']}/{sums['cached']} "
            f"vs totals {total_prompt}/{total_cached}"
        )
    else:
        report.warnings.append(
            f"api_calls={api_calls} does not match iterations={n}; per-completion split may be off"
        )
    return report


def load_turn_reports(path: str, session: str) -> list[TurnReport]:
    reports = []
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                turn = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(turn, dict) or "agentic_loop" not in turn:
                continue
            reports.append(build_turn_report(session, turn))
    return reports


def print_turn_report(report: TurnReport) -> None:
    print("=" * 100)
    elapsed = report.elapsed_ms
    elapsed_str = f"{elapsed}ms" if elapsed is not None else "?"
    print(
        f"TURN {report.turn_id}  model={report.model}  ts={report.timestamp}  "
        f"elapsed={elapsed_str}  session={report.session}"
    )
    print(f"  prompt: {report.prompt_slug!r}")
    totals = report.totals
    print(
        f"  tool events: {report.tool_events}, loop iterations: {report.iterations}, "
        f"api_calls: {totals.get('api_calls', '?')}"
    )
    if not report.telemetry_available:
        print("  cache telemetry unavailable (usage not parsed - streaming mode?)")
        for warning in report.warnings:
            print(f"  [warn] {warning}")
        return
    print(
        f"  {'#':>2}  {'role':38} {'prompt':>8} {'cached':>8} {'hit%':>6}  {'source':<11} notes"
    )
    for idx, comp in enumerate(report.completions, 1):
        hit = _hit_pct(comp.cached_tokens, comp.prompt_tokens)
        print(
            f"  {idx:>2}  {comp.role:38} {comp.prompt_tokens:>8} {comp.cached_tokens:>8} "
            f"{hit:>6.1f}  {comp.source:<11} {comp.notes}"
        )
    total_prompt = _as_int(totals.get("prompt_tokens"))
    total_cached = _as_int(totals.get("cached_tokens"))
    write = _as_int(totals.get("cache_write_tokens"))
    if total_prompt:
        print(
            f"  turn totals: prompt={total_prompt} cached={total_cached} "
            f"write={write} hit={_hit_pct(total_cached, total_prompt):.1f}%"
        )
    for warning in report.warnings:
        print(f"  [warn] {warning}")


def collect_completions(reports: list[TurnReport]) -> list[dict[str, Any]]:
    rows = []
    for report in reports:
        if not report.telemetry_available:
            continue
        for idx, comp in enumerate(report.completions, 1):
            if comp.source == "unavailable" or comp.prompt_tokens == 0:
                continue
            rows.append(
                {
                    "session": report.session,
                    "turn": report.turn_id,
                    "seq": idx,
                    "role": comp.role,
                    "prompt_tokens": comp.prompt_tokens,
                    "cached_tokens": comp.cached_tokens,
                }
            )
    return rows


def print_floor_analysis(rows: list[dict[str, Any]]) -> None:
    active = [r for r in rows if r["cached_tokens"] > 0]
    inactive = [r for r in rows if r["cached_tokens"] == 0]
    print("=" * 100)
    print("CACHE-ACTIVATION FLOOR ANALYSIS")
    print(f"completions with telemetry: {len(rows)}  cache-active: {len(active)}  zero-hit: {len(inactive)}")
    if active:
        print(f"min prompt_tokens with a hit: {min(r['prompt_tokens'] for r in active)}")
    if inactive:
        print(f"max prompt_tokens with zero hit: {max(r['prompt_tokens'] for r in inactive)}")
    print()
    print(f"  {'prompt tokens':>18}  {'completions':>11}  {'cache-active':>12}")
    for lo, hi in FLOOR_BUCKETS:
        bucket = [r for r in rows if lo <= r["prompt_tokens"] < hi]
        if not bucket:
            continue
        hits = len([r for r in bucket if r["cached_tokens"] > 0])
        print(f"  {lo:>8}-{hi:<9}  {len(bucket):>11}  {hits:>12}")
    if active:
        cached_values = sorted({r["cached_tokens"] for r in active})
        non_multiples = [v for v in cached_values if v % 128]
        print()
        print(f"distinct cached values: {cached_values}")
        print(
            "all cached values are multiples of 128 (provider cache-block granularity)"
            if not non_multiples
            else f"values not divisible by 128: {non_multiples}"
        )
    print()
    print("zero-hit completions above 12,000 tokens (size alone does not gate the cache):")
    outliers = [r for r in inactive if r["prompt_tokens"] > 12_000]
    if not outliers:
        print("  none")
    for r in sorted(outliers, key=lambda r: r["prompt_tokens"]):
        print(
            f"  {r['session']} turn {r['turn']} seq {r['seq']} ({r['role']}): "
            f"prompt={r['prompt_tokens']} cached=0"
        )


def print_json(reports: list[TurnReport]) -> None:
    payload = []
    for report in reports:
        payload.append(
            {
                "session": report.session,
                "turn_id": report.turn_id,
                "model": report.model,
                "timestamp": report.timestamp,
                "elapsed_ms": report.elapsed_ms,
                "prompt": report.prompt,
                "tool_events": report.tool_events,
                "iterations": report.iterations,
                "telemetry_available": report.telemetry_available,
                "totals": report.totals,
                "warnings": report.warnings,
                "completions": [
                    {
                        "role": c.role,
                        "prompt_tokens": c.prompt_tokens,
                        "cached_tokens": c.cached_tokens,
                        "hit_pct": round(_hit_pct(c.cached_tokens, c.prompt_tokens), 1),
                        "source": c.source,
                        "notes": c.notes,
                    }
                    for c in report.completions
                ],
            }
        )
    print(json.dumps(payload, indent=2, default=str))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Per-completion prompt-cache report for chatybot sessions."
    )
    parser.add_argument(
        "--session",
        help="session directory name (substring match) or path to turns.jsonl; default: most recent",
    )
    parser.add_argument(
        "--last", type=int, default=1,
        help="number of most recent sessions to report on (default: 1)",
    )
    parser.add_argument(
        "--model", help="only include sessions whose model_alias starts with this prefix",
    )
    parser.add_argument(
        "--sessions-dir", default=DEFAULT_SESSIONS_DIR,
        help=f"sessions directory (default: {DEFAULT_SESSIONS_DIR})",
    )
    parser.add_argument(
        "--floor", action="store_true",
        help="print the cache-activation floor analysis across all selected completions",
    )
    parser.add_argument(
        "--json", action="store_true", help="emit machine-readable JSON instead of tables",
    )
    args = parser.parse_args()

    if not os.path.isdir(args.sessions_dir):
        print(f"error: sessions directory not found: {args.sessions_dir}", file=sys.stderr)
        return 1

    selected: list[tuple[str, str]] = []
    if args.session:
        if os.path.isfile(args.session):
            name = os.path.basename(os.path.dirname(os.path.abspath(args.session)))
            selected.append((name, os.path.abspath(args.session)))
        else:
            for name in iter_session_dirs(args.sessions_dir):
                if args.session in name:
                    selected.append((name, os.path.join(args.sessions_dir, name, "turns.jsonl")))
                    break
            if not selected:
                print(f"error: no session matching {args.session!r}", file=sys.stderr)
                return 1
    else:
        selected = load_session_names(args.sessions_dir, args.last, args.model)
    if not selected:
        print("error: no sessions selected", file=sys.stderr)
        return 1

    reports: list[TurnReport] = []
    for name, path in selected:
        reports.extend(load_turn_reports(path, name))

    if args.json:
        print_json(reports)
        return 0

    for report in reports:
        print_turn_report(report)

    if args.floor:
        print_floor_analysis(collect_completions(reports))
    if not reports:
        print("no agentic turns found in the selected session(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
