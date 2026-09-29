"""
Query subsystem package for Chatybot.
"""

import chatybot.query.grep_engine  # Registers 'grep' engine
from chatybot.query.base import (
    BaseQueryEngine,
    QueryMatch,
    QueryRequest,
    QueryResponse,
    get_query_engine,
    list_query_engines,
    register_query_engine,
)
from chatybot.query.date_parser import parse_date_range, parse_datetime_expr

__all__ = [
    "BaseQueryEngine",
    "QueryMatch",
    "QueryRequest",
    "QueryResponse",
    "get_query_engine",
    "list_query_engines",
    "parse_date_range",
    "parse_datetime_expr",
    "register_query_engine",
]
