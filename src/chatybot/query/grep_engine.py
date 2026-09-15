"""
Default turn-aware Grep+ query engine for Chatybot.
Scans active and persisted session turns, metadata, and scratchpad areas.
"""

import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from chatybot.query.base import (
    BaseQueryEngine,
    QueryMatch,
    QueryRequest,
    QueryResponse,
    register_query_engine,
)
from chatybot.query.date_parser import parse_datetime_expr


@register_query_engine("grep")
class GrepQueryEngine(BaseQueryEngine):
    """
    Pure-Python turn-aware grep engine.
    Matches text across session turns, tool calls, notes, and scratchpad files.
    """

    name = "grep"

    def search(self, app: Any, request: QueryRequest) -> QueryResponse:
        terms = [t.lower() for t in request.terms if t.strip()]
        op = request.operator.upper() if request.operator else "AND"
        matches: list[QueryMatch] = []

        def check_text_match(text: str) -> tuple[bool, list[str]]:
            if not terms:
                return True, []
            text_lower = text.lower()
            matched = [t for t in terms if t in text_lower]
            if op == "AND":
                return len(matched) == len(terms), matched
            else:  # OR
                return len(matched) > 0, matched

        def make_snippet(text: str, matched_terms: list[str], max_len: int = 120) -> str:
            clean_text = " ".join(text.split())
            if not matched_terms or not clean_text:
                return clean_text[:max_len] + ("..." if len(clean_text) > max_len else "")
            
            # Find earliest occurrence of any matched term
            first_idx = -1
            clean_lower = clean_text.lower()
            for t in matched_terms:
                idx = clean_lower.find(t)
                if idx != -1 and (first_idx == -1 or idx < first_idx):
                    first_idx = idx

            if first_idx == -1:
                first_idx = 0

            start = max(0, first_idx - 40)
            end = min(len(clean_text), first_idx + max_len - 40)
            prefix = "..." if start > 0 else ""
            suffix = "..." if end < len(clean_text) else ""
            return f"{prefix}{clean_text[start:end]}{suffix}"

        def is_within_date(dt_val: datetime | None) -> bool:
            # If a date filter is active, items lacking a timestamp cannot satisfy it
            if dt_val is None:
                return not (request.since_dt or request.until_dt)
            if request.since_dt and dt_val < request.since_dt:
                return False
            if request.until_dt and dt_val > request.until_dt:
                return False
            return True

        matched_session_ids = set()
        total_matches_count = 0

        # Resolve Session Store if available
        store = None
        if hasattr(app, "_get_session_store"):
            store = app._get_session_store()
        elif hasattr(app, "get_session_store"):
            store = app.get_session_store()
        elif hasattr(app, "session_store"):
            store = getattr(app, "session_store", None)
        elif hasattr(app, "session_dir"):
            from chatybot.session_factory import get_session_store
            store = get_session_store(sessions_dir=app.session_dir)
        else:
            try:
                from chatybot.session_factory import get_session_store
                store = get_session_store()
            except Exception:
                store = None

        session_size_cache: dict[str, int] = {}
        scratch_size_cache: dict[str, int] = {}

        def get_session_size_bytes(
            sid_or_target: str,
            turns_fallback: list[dict[str, Any]] | None = None,
            notes_fallback: str | None = None,
            cached_summary: dict[str, Any] | None = None,
        ) -> int:
            if sid_or_target in session_size_cache:
                return session_size_cache[sid_or_target]
            if cached_summary and "size_bytes" in cached_summary and cached_summary["size_bytes"] > 0:
                sz = cached_summary["size_bytes"]
                session_size_cache[sid_or_target] = sz
                return sz
            if store and hasattr(store, "get_session_size"):
                sz = store.get_session_size(sid_or_target)
                if sz > 0:
                    session_size_cache[sid_or_target] = sz
                    return sz
            # If not found on disk or store unavailable, compute total size from text content (prompt, response, thinking) and notes
            total = 0
            if notes_fallback:
                total += len(str(notes_fallback).encode("utf-8"))
            if turns_fallback:
                for t in turns_fallback:
                    for field in ("prompt", "response", "thinking"):
                        val = t.get(field)
                        if val and isinstance(val, str):
                            total += len(val.encode("utf-8"))
            session_size_cache[sid_or_target] = total
            return total

        # 1. Search Active Session Turns & Buffer
        active_sid = getattr(app, "active_session_id", None)
        if (not request.session_id or request.session_id == active_sid):
            # Check session turns in memory
            turns = getattr(app, "session_turns", []) or []
            active_notes = getattr(app, "session_notes", None)
            active_session_size: int | None = None
            active_session_has_match = False
            for idx, turn in enumerate(turns, 1):
                # Timestamp check
                ts_raw = turn.get("timestamp") or turn.get("created_at")
                turn_dt = parse_datetime_expr(str(ts_raw)) if ts_raw else None
                if not is_within_date(turn_dt):
                    continue

                # Content check (prompt + response + tool outputs)
                content_parts = []
                if turn.get("prompt"):
                    content_parts.append(f"user: {turn['prompt']}")
                if turn.get("response"):
                    content_parts.append(f"assistant: {turn['response']}")
                if turn.get("tool_calls"):
                    content_parts.append(f"tool_calls: {turn['tool_calls']!s}")

                full_content = "\n".join(content_parts)
                matched_ok, hit_terms = check_text_match(full_content)
                if matched_ok:
                    total_matches_count += 1
                    sess_key = active_sid or "active"
                    matched_session_ids.add(sess_key)
                    active_session_has_match = True

                    if len(matches) < request.limit and not request.ids_only:
                        if active_session_size is None:
                            active_session_size = get_session_size_bytes(active_sid or "active", turns_fallback=turns, notes_fallback=active_notes)
                        snippet_text = full_content if request.full else make_snippet(full_content, hit_terms)
                        matches.append(
                            QueryMatch(
                                source="session",
                                session_id=sess_key,
                                turn_id=idx,
                                role="exchange",
                                timestamp=str(ts_raw) if ts_raw else None,
                                matched_terms=hit_terms,
                                snippet=snippet_text,
                                full_text=full_content,
                                size_bytes=active_session_size,
                                metadata={"active": True, "custom_name": getattr(app, "active_session_name", None)},
                            )
                        )
                    if request.ids_only:
                        break

            # Check active session notes
            if active_notes and (not request.ids_only or not active_session_has_match):
                matched_ok, hit_terms = check_text_match(active_notes)
                if matched_ok:
                    total_matches_count += 1
                    sess_key = active_sid or "active"
                    matched_session_ids.add(sess_key)
                    if len(matches) < request.limit and not request.ids_only:
                        if active_session_size is None:
                            active_session_size = get_session_size_bytes(active_sid or "active", turns_fallback=turns, notes_fallback=active_notes)
                        snippet_text = active_notes if request.full else make_snippet(active_notes, hit_terms)
                        matches.append(
                            QueryMatch(
                                source="session",
                                session_id=sess_key,
                                turn_id=None,
                                role="note",
                                timestamp=None,
                                matched_terms=hit_terms,
                                snippet=snippet_text,
                                full_text=active_notes,
                                size_bytes=active_session_size,
                                metadata={"active": True, "type": "note"},
                            )
                        )

        # 2. Search Persisted Sessions (via Session Store)
        if not request.active_only:
            if store:
                try:
                    saved_sessions = store.list_sessions(limit=None, since_dt=request.since_dt)
                except Exception:
                    saved_sessions = []

                for s_summary in saved_sessions:
                    sid = s_summary.get("sid")
                    # Skip active session if we already searched it in-memory
                    if sid == active_sid:
                        continue
                    if request.session_id and request.session_id != sid:
                        continue
                    if request.ids_only and sid in matched_session_ids:
                        continue

                    # Load full session turns with per-session error isolation
                    try:
                        meta, loaded_turns = store.load_session(sid)
                    except Exception:
                        continue

                    # Search session notes if present in meta
                    s_notes = meta.get("notes") or meta.get("session_notes")
                    persisted_session_size: int | None = None

                    if s_notes:
                        matched_ok, hit_terms = check_text_match(str(s_notes))
                        if matched_ok:
                            total_matches_count += 1
                            matched_session_ids.add(sid)
                            if len(matches) < request.limit and not request.ids_only:
                                if persisted_session_size is None:
                                    persisted_session_size = get_session_size_bytes(sid, turns_fallback=loaded_turns, notes_fallback=s_notes, cached_summary=s_summary)
                                snippet_text = str(s_notes) if request.full else make_snippet(str(s_notes), hit_terms)
                                matches.append(
                                    QueryMatch(
                                        source="session",
                                        session_id=sid,
                                        turn_id=None,
                                        role="note",
                                        timestamp=meta.get("updated_at") or meta.get("created_at"),
                                        matched_terms=hit_terms,
                                        snippet=snippet_text,
                                        full_text=str(s_notes),
                                        size_bytes=persisted_session_size,
                                        metadata={"custom_name": meta.get("custom_name"), "type": "note"},
                                    )
                                )
                            if request.ids_only:
                                continue

                    # Search loaded turns
                    for t_idx, turn in enumerate(loaded_turns, 1):
                        ts_raw = turn.get("timestamp") or turn.get("created_at")
                        turn_dt = parse_datetime_expr(str(ts_raw)) if ts_raw else None
                        if not is_within_date(turn_dt):
                            continue

                        # Extract text
                        content_parts = []
                        if turn.get("prompt"):
                            content_parts.append(f"user: {turn['prompt']}")
                        if turn.get("response"):
                            content_parts.append(f"assistant: {turn['response']}")
                        if turn.get("text"):
                            content_parts.append(str(turn['text']))
                        if turn.get("tool_calls"):
                            content_parts.append(f"tool_calls: {turn['tool_calls']!s}")

                        full_content = "\n".join(content_parts)
                        matched_ok, hit_terms = check_text_match(full_content)
                        if matched_ok:
                            total_matches_count += 1
                            matched_session_ids.add(sid)
                            if len(matches) < request.limit and not request.ids_only:
                                if persisted_session_size is None:
                                    persisted_session_size = get_session_size_bytes(sid, turns_fallback=loaded_turns, notes_fallback=s_notes, cached_summary=s_summary)
                                snippet_text = full_content if request.full else make_snippet(full_content, hit_terms)
                                matches.append(
                                    QueryMatch(
                                        source="session",
                                        session_id=sid,
                                        turn_id=turn.get("turn_id") or t_idx,
                                        role=turn.get("role", "exchange"),
                                        timestamp=str(ts_raw) if ts_raw else None,
                                        matched_terms=hit_terms,
                                        snippet=snippet_text,
                                        full_text=full_content,
                                        size_bytes=persisted_session_size,
                                        metadata={"custom_name": meta.get("custom_name")},
                                    )
                                )
                            if request.ids_only:
                                break

        # 3. Search Scratch Area (Files in scratch dir) - skip if ids_only is strictly for sessions
        if request.include_scratch and not request.ids_only:
            scratch_dirs = []
            if hasattr(app, "get_scratch_dir"):
                s_dir = app.get_scratch_dir(create=False)
                if s_dir and os.path.exists(s_dir):
                    scratch_dirs.append(os.path.realpath(s_dir))
            # Also check session-level scratch if different
            session_dir_val = getattr(app, "session_dir", None)
            if session_dir_val:
                global_scratch = Path(session_dir_val).expanduser().resolve().parent / "scratch"
                if global_scratch.exists():
                    canon_global = os.path.realpath(str(global_scratch))
                    if canon_global not in scratch_dirs:
                        scratch_dirs.append(canon_global)

            for s_dir in scratch_dirs:
                try:
                    for root, _, files in os.walk(s_dir):
                        for fname in files:
                            if fname.startswith("."):
                                continue
                            file_path = os.path.join(root, fname)
                            rel_path = os.path.relpath(file_path, s_dir)
                            # Check file mtime for date filters
                            try:
                                mtime = datetime.fromtimestamp(os.path.getmtime(file_path))
                            except OSError:
                                mtime = None

                            if not is_within_date(mtime):
                                continue

                            file_size = scratch_size_cache.get(file_path)
                            if file_size is None:
                                try:
                                    file_size = os.path.getsize(file_path)
                                except OSError:
                                    file_size = 0
                                scratch_size_cache[file_path] = file_size

                            try:
                                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                                    lines = f.readlines()
                            except OSError:
                                continue

                            for line_no, line in enumerate(lines, 1):
                                matched_ok, hit_terms = check_text_match(line)
                                if matched_ok:
                                    total_matches_count += 1
                                    if len(matches) < request.limit:
                                        snippet_text = line.rstrip() if request.full else make_snippet(line.strip(), hit_terms)
                                        matches.append(
                                            QueryMatch(
                                                source="scratch",
                                                session_id=None,
                                                turn_id=line_no,
                                                role="file",
                                                timestamp=mtime.isoformat() if mtime else None,
                                                matched_terms=hit_terms,
                                                snippet=snippet_text,
                                                full_text=line.rstrip(),
                                                size_bytes=file_size or len(line.encode("utf-8")),
                                                metadata={"file": rel_path, "path": file_path},
                                            )
                                        )
                except Exception:
                    pass

        sessions_list = []
        for sid in sorted(list(matched_session_ids)):
            sz = get_session_size_bytes(sid)
            sessions_list.append({
                "session_id": sid,
                "size_bytes": sz,
            })

        return QueryResponse(
            total_matches=total_matches_count if not request.ids_only else len(matched_session_ids),
            matches=matches,
            session_ids=sorted(list(matched_session_ids)),
            sessions=sessions_list,
            engine=self.name,
        )
