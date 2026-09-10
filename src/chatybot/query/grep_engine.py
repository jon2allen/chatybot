"""
Default turn-aware Grep+ query engine for Chatybot.
Scans active and persisted session turns, metadata, and scratchpad areas.
"""

import os
from datetime import datetime
from typing import List, Dict, Any, Tuple, Optional
from pathlib import Path

from chatybot.query.base import (
    BaseQueryEngine,
    QueryRequest,
    QueryMatch,
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
        matches: List[QueryMatch] = []

        def check_text_match(text: str) -> Tuple[bool, List[str]]:
            if not terms:
                return True, []
            text_lower = text.lower()
            matched = [t for t in terms if t in text_lower]
            if op == "AND":
                return len(matched) == len(terms), matched
            else:  # OR
                return len(matched) > 0, matched

        def make_snippet(text: str, matched_terms: List[str], max_len: int = 120) -> str:
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

        def is_within_date(dt_val: Optional[datetime]) -> bool:
            if not dt_val:
                return True
            if request.since_dt and dt_val < request.since_dt:
                return False
            if request.until_dt and dt_val > request.until_dt:
                return False
            return True

        # 1. Search Active Session Turns & Buffer
        active_sid = getattr(app, "active_session_id", None)
        if (not request.session_id or request.session_id == active_sid):
            # Check session turns in memory
            turns = getattr(app, "session_turns", []) or []
            for idx, turn in enumerate(turns, 1):
                if len(matches) >= request.limit:
                    break
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
                    content_parts.append(f"tool_calls: {str(turn['tool_calls'])}")

                full_content = "\n".join(content_parts)
                matched_ok, hit_terms = check_text_match(full_content)
                if matched_ok:
                    matches.append(
                        QueryMatch(
                            source="session",
                            session_id=active_sid or "active",
                            turn_id=idx,
                            role="exchange",
                            timestamp=str(ts_raw) if ts_raw else None,
                            matched_terms=hit_terms,
                            snippet=make_snippet(full_content, hit_terms),
                            metadata={"active": True, "custom_name": getattr(app, "active_session_name", None)},
                        )
                    )

            # Check active session notes
            active_notes = getattr(app, "session_notes", None)
            if active_notes and len(matches) < request.limit:
                matched_ok, hit_terms = check_text_match(active_notes)
                if matched_ok:
                    matches.append(
                        QueryMatch(
                            source="session",
                            session_id=active_sid or "active",
                            turn_id=None,
                            role="note",
                            timestamp=None,
                            matched_terms=hit_terms,
                            snippet=make_snippet(active_notes, hit_terms),
                            metadata={"active": True, "type": "note"},
                        )
                    )

        # 2. Search Persisted Sessions (via Session Store)
        if not request.active_only and hasattr(app, "_get_session_store"):
            try:
                store = app._get_session_store()
                # List sessions; note since_dt can prune entire files if updated before since_dt
                saved_sessions = store.list_sessions(limit=None, since_dt=request.since_dt)
                for s_summary in saved_sessions:
                    if len(matches) >= request.limit:
                        break
                    sid = s_summary.get("sid")
                    # Skip active session if we already searched it in-memory
                    if sid == active_sid:
                        continue
                    if request.session_id and request.session_id != sid:
                        continue

                    # Load full session turns
                    try:
                        meta, loaded_turns = store.load_session(sid)
                    except Exception:
                        continue

                    # Search session notes if present in meta
                    s_notes = meta.get("notes") or meta.get("session_notes")
                    if s_notes and len(matches) < request.limit:
                        matched_ok, hit_terms = check_text_match(str(s_notes))
                        if matched_ok:
                            matches.append(
                                QueryMatch(
                                    source="session",
                                    session_id=sid,
                                    turn_id=None,
                                    role="note",
                                    timestamp=meta.get("updated_at") or meta.get("created_at"),
                                    matched_terms=hit_terms,
                                    snippet=make_snippet(str(s_notes), hit_terms),
                                    metadata={"custom_name": meta.get("custom_name"), "type": "note"},
                                )
                            )

                    # Search loaded turns
                    for t_idx, turn in enumerate(loaded_turns, 1):
                        if len(matches) >= request.limit:
                            break
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
                            content_parts.append(f"tool_calls: {str(turn['tool_calls'])}")

                        full_content = "\n".join(content_parts)
                        matched_ok, hit_terms = check_text_match(full_content)
                        if matched_ok:
                            matches.append(
                                QueryMatch(
                                    source="session",
                                    session_id=sid,
                                    turn_id=turn.get("turn_id") or t_idx,
                                    role=turn.get("role", "exchange"),
                                    timestamp=str(ts_raw) if ts_raw else None,
                                    matched_terms=hit_terms,
                                    snippet=make_snippet(full_content, hit_terms),
                                    metadata={"custom_name": meta.get("custom_name")},
                                )
                            )
            except Exception as e:
                # Silently catch store errors or log them
                pass

        # 3. Search Scratch Area (Files in scratch dir)
        if request.include_scratch and len(matches) < request.limit:
            scratch_dirs = []
            if hasattr(app, "get_scratch_dir"):
                s_dir = app.get_scratch_dir(create=False)
                if s_dir and os.path.exists(s_dir):
                    scratch_dirs.append(s_dir)
            # Also check session-level scratch if different
            session_dir_val = getattr(app, "session_dir", None)
            if session_dir_val:
                global_scratch = Path(session_dir_val).expanduser().resolve().parent / "scratch"
                if global_scratch.exists() and str(global_scratch) not in scratch_dirs:
                    scratch_dirs.append(str(global_scratch))

            for s_dir in scratch_dirs:
                if len(matches) >= request.limit:
                    break
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
                                if not is_within_date(mtime):
                                    continue
                            except OSError:
                                mtime = None

                            try:
                                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                                    lines = f.readlines()
                            except OSError:
                                continue

                            for line_no, line in enumerate(lines, 1):
                                if len(matches) >= request.limit:
                                    break
                                matched_ok, hit_terms = check_text_match(line)
                                if matched_ok:
                                    matches.append(
                                        QueryMatch(
                                            source="scratch",
                                            session_id=None,
                                            turn_id=line_no,
                                            role="file",
                                            timestamp=mtime.isoformat() if mtime else None,
                                            matched_terms=hit_terms,
                                            snippet=make_snippet(line.strip(), hit_terms),
                                            metadata={"file": rel_path, "path": file_path},
                                        )
                                    )
                except Exception:
                    pass

        return QueryResponse(
            total_matches=len(matches),
            matches=matches,
            engine=self.name,
        )
