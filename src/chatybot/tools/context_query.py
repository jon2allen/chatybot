"""
Context query tools for LLM tool calling in Chatybot.
Provides session_search to search session turns, conversation history, notes, and scratchpad.
"""

from typing import Dict, Any, Optional, List
import shlex

from chatybot.query.base import QueryRequest, get_query_engine
from chatybot.query.date_parser import parse_datetime_expr, parse_date_range


def session_search(
    query: str,
    operator: str = "AND",
    since: Optional[str] = None,
    until: Optional[str] = None,
    range: Optional[str] = None,
    include_scratch: bool = True,
    limit: int = 15,
    session_id: Optional[str] = None,
    engine: Optional[str] = None,
    ids_only: bool = False,
    full: bool = False,
    target_variable: Optional[str] = None,
    app: Any = None,
) -> Dict[str, Any]:
    """
    Search past session turns, conversation history, notes, and scratchpad.

    Args:
        query: Space-separated search terms or keywords (e.g. 'migration error').
        operator: Match operator: 'AND' (all terms required) or 'OR' (any term). Default is 'AND'.
        since: Filter messages after this timestamp or relative date (e.g. 'yesterday', '7d', '2026-03-01').
        until: Filter messages before this timestamp (e.g. '2026-05-01').
        range: Date range expression (e.g. '03/01/2026 to 05/01/2026' or '2026-03-01..2026-05-01').
        include_scratch: Whether to also search files in the scratch directory (default True).
        limit: Maximum number of match items to return (default 15).
        session_id: Optional specific session ID to restrict search to.
        engine: Query engine backend name (default 'grep').
        ids_only: If True, only returns matching session IDs (fast discovery).
        full: If True, returns full turn text without 80-character snippet truncation.
        target_variable: Optional script variable name to save results into.
        app: ChatybotApp instance passed when called within application context.

    Returns:
        Dict containing total_matches, matches list, session_ids, and status.
    """
    if not query or not query.strip():
        return {
            "status": "error",
            "message": "Query string cannot be empty",
            "total_matches": 0,
            "matches": [],
            "session_ids": [],
        }

    # Split query into terms, respecting quotes
    try:
        terms = shlex.split(query)
    except ValueError:
        terms = query.split()

    # Parse date constraints
    since_dt = None
    until_dt = None

    if range:
        start_r, end_r = parse_date_range(range)
        if start_r:
            since_dt = start_r
        if end_r:
            until_dt = end_r

    if since and not since_dt:
        since_dt = parse_datetime_expr(since)

    if until and not until_dt:
        until_dt = parse_datetime_expr(until)

    req = QueryRequest(
        terms=terms,
        operator=operator,
        since_dt=since_dt,
        until_dt=until_dt,
        include_scratch=include_scratch,
        limit=max(1, min(limit, 100)),
        session_id=session_id,
        ids_only=ids_only,
        full=full,
    )

    try:
        engine_instance = get_query_engine(engine)
        response = engine_instance.search(app, req)
        res_dict = response.to_dict()
        res_dict["status"] = "success"

        # Populate protected variable SESSION_QUERY and user target_variable
        if app and hasattr(app, "buffer_manager") and app.buffer_manager:
            app.buffer_manager.set_script_var("SESSION_QUERY", res_dict, allow_protected=True)
            if target_variable:
                val_to_save = res_dict["session_ids"] if ids_only else res_dict
                app.buffer_manager.set_script_var(target_variable, val_to_save, allow_protected=True)

        return res_dict
    except Exception as e:
        return {
            "status": "error",
            "message": f"Query execution failed: {e}",
            "total_matches": 0,
            "matches": [],
            "session_ids": [],
        }


def session_get(
    session_id: str,
    turn_id: Optional[int] = None,
    part: str = "both",
    target_variable: Optional[str] = None,
    app: Any = None,
) -> Dict[str, Any]:
    """
    Read-only text extraction from a session without altering active session state.

    Args:
        session_id: Session ID or custom name ('active' for current active session).
        turn_id: 1-based turn number to extract. If omitted or None, extracts all turns.
        part: Which turn part to extract: 'both' (default), 'prompt', 'response', or 'thinking'.
        target_variable: Optional script variable name to save extracted text into.
        app: ChatybotApp instance passed when called within application context.

    Returns:
        Dict containing status, session_id, turn_id, extracted text, and metadata.
    """
    if not session_id or not str(session_id).strip():
        return {"status": "error", "message": "session_id is required"}

    target = str(session_id).strip()
    part_norm = part.lower().strip() if part else "both"
    if part_norm not in ("both", "prompt", "response", "thinking"):
        part_norm = "both"

    meta: Dict[str, Any] = {}
    turns: List[Dict[str, Any]] = []

    # 1. Resolve from Active Session
    active_sid = getattr(app, "active_session_id", None)
    active_cname = getattr(app, "active_session_name", None)

    if target.lower() in ("active", "current") or target == active_sid or (active_cname and target == active_cname):
        meta = {
            "session_id": active_sid or "active",
            "custom_name": active_cname,
            "model_alias": getattr(app, "session_model_alias", "default"),
            "notes": getattr(app, "session_notes", None),
            "turn_count": len(getattr(app, "session_turns", []) or []),
        }
        turns = getattr(app, "session_turns", []) or []
    elif app and hasattr(app, "_get_session_store"):
        # 2. Resolve from Persisted Store
        try:
            store = app._get_session_store()
            resolved = store.resolve_session(target)
            if not resolved:
                return {"status": "error", "message": f"Session '{target}' not found."}
            meta, turns = store.load_session(resolved)
        except Exception as e:
            return {"status": "error", "message": f"Could not load session '{target}': {e}"}
    else:
        return {"status": "error", "message": "Session store not available."}

    # Filter to specific turn if requested
    extracted_text = ""
    extracted_turns = []

    def format_turn(t: Dict[str, Any], idx: int) -> str:
        prompt_txt = str(t.get("prompt", "") or "")
        resp_txt = str(t.get("response", "") or "")
        think_txt = str(t.get("thinking", "") or "")
        
        if part_norm == "prompt":
            return prompt_txt
        elif part_norm == "response":
            return resp_txt
        elif part_norm == "thinking":
            return think_txt
        else:
            lines = [f"[Turn {idx}] User: {prompt_txt}"]
            if think_txt:
                lines.append(f"Thinking: {think_txt}")
            lines.append(f"Assistant: {resp_txt}")
            return "\n".join(lines)

    if turn_id is not None:
        try:
            target_idx = int(turn_id)
        except ValueError:
            return {"status": "error", "message": f"Invalid turn_id '{turn_id}'"}

        # Find turn by turn_id attribute or 1-indexed position
        found_turn = None
        found_idx = target_idx
        for i, t in enumerate(turns, 1):
            if t.get("turn_id") == target_idx or i == target_idx:
                found_turn = t
                found_idx = i
                break

        if not found_turn:
            return {
                "status": "error",
                "message": f"Turn {target_idx} not found in session '{target}' ({len(turns)} total turns).",
            }

        extracted_text = format_turn(found_turn, found_idx)
        extracted_turns.append(found_turn)
    else:
        formatted_list = [format_turn(t, i) for i, t in enumerate(turns, 1)]
        extracted_text = "\n\n".join(formatted_list)
        extracted_turns = turns

    result = {
        "status": "success",
        "session_id": meta.get("session_id") or target,
        "custom_name": meta.get("custom_name"),
        "turn_id": turn_id,
        "part": part_norm,
        "total_turns": len(turns),
        "text": extracted_text,
    }

    if target_variable and app and hasattr(app, "buffer_manager") and app.buffer_manager:
        app.buffer_manager.set_script_var(target_variable, extracted_text, allow_protected=True)
        result["target_variable"] = target_variable

    return result

