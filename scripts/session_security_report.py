#!/usr/bin/env python3
"""
Session Security Report

Reads chatybot session data from ~/.local/share/chatybot/sessions/ and
produces a formatted report of security decisions recorded in agentic
loop tool records.

Usage:
  python3 scripts/session_security_report.py                          # all sessions
  python3 scripts/session_security_report.py --days 4                   # past 4 days
  python3 scripts/session_security_report.py --model mistral_1          # filter by model
  python3 scripts/session_security_report.py --phrase "security"       # sessions whose prompts contain a phrase
  python3 scripts/session_security_report.py --days 4 --model mistral_1 --phrase "code review"
  python3 scripts/session_security_report.py --details                 # show every deny/ask
  python3 scripts/session_security_report.py --cross-ref                # join with engine log for scores
  python3 scripts/session_security_report.py --cross-ref --engine-log /path/to/security_chain.jsonl

Requires: Python 3.10+ (no external dependencies).
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path

SESSIONS_DIR = Path.home() / ".local" / "share" / "chatybot" / "sessions"
DEFAULT_ENGINE_LOG = Path.home() / ".config" / "chatybot" / "logs" / "jev_security.jsonl"


def load_sessions(sessions_dir: Path) -> list[dict]:
    """Load all sessions with their meta and turns."""
    sessions = []
    if not sessions_dir.exists():
        return sessions
    for d in sorted(sessions_dir.iterdir()):
        if not d.is_dir():
            continue
        meta_path = d / "meta.json"
        turns_path = d / "turns.jsonl"
        if not meta_path.exists() or not turns_path.exists():
            continue
        try:
            meta = json.loads(meta_path.read_text())
        except (json.JSONDecodeError, OSError):
            continue
        turns = []
        try:
            for line in turns_path.read_text().splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    turns.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        except OSError:
            continue
        sessions.append({"meta": meta, "turns": turns, "dir": d.name})
    return sessions


def filter_sessions(
    sessions: list[dict],
    days: int | None = None,
    model: str | None = None,
    phrase: str | None = None,
) -> list[dict]:
    """Filter sessions by date range, model alias, or prompt phrase."""
    result = []
    cutoff = None
    if days is not None:
        cutoff = datetime.now(UTC).timestamp() - (days * 86400)

    for s in sessions:
        meta = s["meta"]
        # Date filter
        if cutoff is not None:
            created = meta.get("created_at", "")
            try:
                ts = datetime.fromisoformat(created).timestamp()
                if ts < cutoff:
                    continue
            except (ValueError, TypeError):
                continue
        # Model filter
        if model is not None:
            s_model = meta.get("model_alias", "")
            if model.lower() not in s_model.lower():
                continue
        # Phrase filter (search in all turn prompts)
        if phrase is not None:
            found = False
            for t in s["turns"]:
                prompt = t.get("prompt", "")
                if phrase.lower() in prompt.lower():
                    found = True
                    break
            if not found:
                continue
        result.append(s)
    return result


def extract_security_events(sessions: list[dict]) -> list[dict]:
    """Extract security decision records from agentic loop tool records."""
    events = []
    for s in sessions:
        session_id = s["meta"].get("session_id", s["dir"])
        model = s["meta"].get("model_alias", "unknown")
        for t in s["turns"]:
            turn_id = t.get("turn_id", "?")
            prompt = t.get("prompt", "")
            agentic_loop = t.get("agentic_loop", [])
            if not isinstance(agentic_loop, list):
                continue
            for tool_rec in agentic_loop:
                if not isinstance(tool_rec, dict):
                    continue
                sec = tool_rec.get("security")
                if sec is None or not isinstance(sec, dict):
                    continue
                # Phase-separated format: {"input": {...}, "output": {...}}
                # Flatten into one event per phase, or a single event for the old flat format.
                if "input" in sec or "output" in sec:
                    for phase, phase_sec in sec.items():
                        if not isinstance(phase_sec, dict):
                            continue
                        events.append({
                            "session_id": session_id,
                            "model": model,
                            "turn_id": turn_id,
                            "prompt": prompt[:120],
                            "tool": tool_rec.get("tool", "?"),
                            "arguments": tool_rec.get("arguments", {}),
                            "exit_code": tool_rec.get("exit_code"),
                            "status": tool_rec.get("status"),
                            "timestamp": tool_rec.get("timestamp", ""),
                            "phase": phase,
                            "security": phase_sec,
                        })
                else:
                    events.append({
                        "session_id": session_id,
                        "model": model,
                        "turn_id": turn_id,
                        "prompt": prompt[:120],
                        "tool": tool_rec.get("tool", "?"),
                        "arguments": tool_rec.get("arguments", {}),
                        "exit_code": tool_rec.get("exit_code"),
                        "status": tool_rec.get("status"),
                        "timestamp": tool_rec.get("timestamp", ""),
                        "phase": "input",
                        "security": sec,
                    })
    return events


def load_engine_log(log_path: Path) -> list[dict]:
    """Load engine-specific log entries (jev_security.jsonl or security_chain.jsonl)."""
    entries = []
    if not log_path.exists():
        return entries
    for line in log_path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return entries


def cross_reference(events: list[dict], engine_entries: list[dict]) -> list[dict]:
    """Join session security events with engine log entries by request_id.

    Only ``event == "decision"`` entries are indexed, so refusal_repeat and
    outcome lines with the same request_id don't shadow the real decision.
    """
    by_req = {}
    for e in engine_entries:
        if e.get("event") != "decision":
            continue
        rid = e.get("request_id")
        if rid:
            by_req.setdefault(rid, []).append(e)
    enriched = []
    for ev in events:
        rid = ev["security"].get("request_id")
        engine_records = by_req.get(rid, []) if rid else []
        ev["engine_log"] = engine_records
        enriched.append(ev)
    return enriched


def format_report(
    events: list[dict],
    sessions: list[dict],
    show_details: bool = False,
    cross_ref: bool = False,
) -> str:
    """Build the formatted text report."""
    lines = []
    lines.append("=" * 72)
    lines.append("SESSION SECURITY REPORT")
    lines.append("=" * 72)
    lines.append(f"Sessions scanned: {len(sessions)}")
    lines.append(f"Security events found: {len(events)}")
    if not events:
        lines.append("")
        lines.append("No security decisions recorded in session data.")
        lines.append("(Older sessions may predate security logging.)")
        return "\n".join(lines)

    # --- By verdict (exclude cache repeats from totals) ---
    fresh = [ev for ev in events if ev["security"].get("source") != "cache"]
    cached = [ev for ev in events if ev["security"].get("source") == "cache"]
    by_verdict = Counter(ev["security"].get("verdict", "unknown") for ev in fresh)
    lines.append("")
    lines.append("--- By Verdict (fresh evaluations only) ---")
    for v, c in by_verdict.most_common():
        lines.append(f"  {v}: {c} ({c / len(fresh) * 100:.1f}%)")
    if cached:
        lines.append(f"  (plus {len(cached)} cached repeat refusals)")

    # --- By source ---
    by_source = Counter(ev["security"].get("source", "eval") for ev in events)
    lines.append("")
    lines.append("--- By Source ---")
    for s, c in by_source.most_common():
        lines.append(f"  {s}: {c}")

    # --- By engine ---
    by_engine = Counter(ev["security"].get("engine", "unknown") for ev in events)
    lines.append("")
    lines.append("--- By Engine ---")
    for e, c in by_engine.most_common():
        lines.append(f"  {e}: {c}")

    # --- By tool ---
    by_tool = Counter(ev["tool"] for ev in events)
    lines.append("")
    lines.append("--- By Tool ---")
    for t, c in by_tool.most_common():
        lines.append(f"  {t}: {c}")

    # --- By model ---
    by_model = Counter(ev["model"] for ev in events)
    lines.append("")
    lines.append("--- By Model ---")
    for m, c in by_model.most_common():
        lines.append(f"  {m}: {c}")

    # --- By day ---
    by_day: dict[str, int] = defaultdict(int)
    for ev in events:
        ts = ev.get("timestamp", "")
        day = ts[:10] if ts else "unknown"
        by_day[day] += 1
    lines.append("")
    lines.append("--- By Day ---")
    for day in sorted(by_day):
        lines.append(f"  {day}: {by_day[day]}")

    # --- By outcome ---
    by_outcome = Counter(ev["security"].get("outcome", "n/a") for ev in events)
    lines.append("")
    lines.append("--- By Outcome ---")
    for o, c in by_outcome.most_common():
        lines.append(f"  {o}: {c}")

    # --- Denials and asks (details) ---
    blocked = [ev for ev in events if ev["security"].get("verdict") in ("deny", "ask")]
    lines.append("")
    lines.append(f"--- Denials and Asks ({len(blocked)}) ---")
    if not show_details and len(blocked) > 10:
        lines.append("  (showing first 10; use --details for all)")
        blocked = blocked[:10]
    for ev in blocked:
        sec = ev["security"]
        lines.append(f"  [{ev['timestamp'][:19]}] {ev['session_id']} phase={ev['phase']}")
        src = sec.get("source", "eval")
        lines.append(f"    tool={ev['tool']} verdict={sec.get('verdict')} engine={sec.get('engine')} source={src}")
        args_str = json.dumps(ev["arguments"], ensure_ascii=False)
        if len(args_str) > 120:
            args_str = args_str[:117] + "..."
        lines.append(f"    args={args_str}")
        lines.append(f"    reason={sec.get('reason', '')}")
        if sec.get("outcome"):
            lines.append(f"    outcome={sec['outcome']}")
        if cross_ref and sec.get("request_id"):
            engine_logs = ev.get("engine_log", [])
            if engine_logs:
                log = engine_logs[0]
                scores = log.get("scores", {})
                if scores:
                    top_scores = sorted(scores.items(), key=lambda x: -x[1])[:3]
                    score_str = ", ".join(f"{k}={v:.2f}" for k, v in top_scores)
                    lines.append(f"    engine_scores={score_str}")
                if log.get("usage"):
                    lines.append(f"    usage={json.dumps(log['usage'])}")
            else:
                lines.append("    engine_log=not found")
        lines.append("")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Analyze security decisions in chatybot session data."
    )
    parser.add_argument("--days", type=int, default=None, help="Only sessions from past N days")
    parser.add_argument("--model", type=str, default=None, help="Filter by model alias (substring match)")
    parser.add_argument("--phrase", type=str, default=None, help="Only sessions whose prompts contain this phrase")
    parser.add_argument("--details", action="store_true", help="Show all deny/ask entries (not just first 10)")
    parser.add_argument("--cross-ref", action="store_true", help="Join with engine log for scores and usage")
    parser.add_argument("--engine-log", type=str, default=None, help="Override engine log path (default: jev_security.jsonl)")
    parser.add_argument("--sessions-dir", type=str, default=None, help="Override sessions directory")
    args = parser.parse_args()

    sessions_dir = Path(args.sessions_dir) if args.sessions_dir else SESSIONS_DIR
    if not sessions_dir.exists():
        print(f"Sessions directory not found: {sessions_dir}", file=sys.stderr)
        sys.exit(1)

    sessions = load_sessions(sessions_dir)
    sessions = filter_sessions(sessions, days=args.days, model=args.model, phrase=args.phrase)
    events = extract_security_events(sessions)

    if args.cross_ref:
        engine_log_path = Path(args.engine_log) if args.engine_log else DEFAULT_ENGINE_LOG
        engine_entries = load_engine_log(engine_log_path)
        events = cross_reference(events, engine_entries)

    report = format_report(events, sessions, show_details=args.details, cross_ref=args.cross_ref)
    print(report)


if __name__ == "__main__":
    main()
