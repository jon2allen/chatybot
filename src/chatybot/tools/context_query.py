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
        target_variable: Optional script variable name to save results into.
        app: ChatybotApp instance passed when called within application context.

    Returns:
        Dict containing total_matches, matches list, and status.
    """
    if not query or not query.strip():
        return {
            "status": "error",
            "message": "Query string cannot be empty",
            "total_matches": 0,
            "matches": [],
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
                app.buffer_manager.set_script_var(target_variable, res_dict, allow_protected=True)

        return res_dict
    except Exception as e:
        return {
            "status": "error",
            "message": f"Query execution failed: {e}",
            "total_matches": 0,
            "matches": [],
        }
