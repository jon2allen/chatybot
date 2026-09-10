"""
Query subsystem package for Chatybot.
"""

from chatybot.query.base import (
    BaseQueryEngine,
    QueryRequest,
    QueryMatch,
    QueryResponse,
    register_query_engine,
    get_query_engine,
    list_query_engines,
)
from chatybot.query.date_parser import parse_datetime_expr, parse_date_range
import chatybot.query.grep_engine  # Registers 'grep' engine

__all__ = [
    "BaseQueryEngine",
    "QueryRequest",
    "QueryMatch",
    "QueryResponse",
    "register_query_engine",
    "get_query_engine",
    "list_query_engines",
    "parse_datetime_expr",
    "parse_date_range",
]
