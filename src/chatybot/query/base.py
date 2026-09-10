"""
Base classes and registry for pluggable session query engines in Chatybot.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Any, List, Optional, Type


@dataclass
class QueryRequest:
    """Standard search request passed to query engines."""
    terms: List[str] = field(default_factory=list)
    operator: str = "AND"  # "AND" | "OR"
    since_dt: Optional[datetime] = None
    until_dt: Optional[datetime] = None
    include_scratch: bool = True
    limit: int = 20
    active_only: bool = False
    session_id: Optional[str] = None  # If specified, restrict to single session
    ids_only: bool = False  # If True, only identify matching session IDs
    full: bool = False      # If True, retrieve full turn content without snippet truncation


@dataclass
class QueryMatch:
    """Individual match result returned by query engine."""
    source: str  # "session" | "scratch"
    session_id: Optional[str] = None
    turn_id: Optional[int] = None
    role: str = "message"  # "user", "assistant", "system", "tool", "scratch"
    timestamp: Optional[str] = None
    matched_terms: List[str] = field(default_factory=list)
    snippet: str = ""
    full_text: Optional[str] = None
    size_bytes: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source": self.source,
            "session_id": self.session_id,
            "turn_id": self.turn_id,
            "role": self.role,
            "timestamp": self.timestamp,
            "matched_terms": self.matched_terms,
            "snippet": self.snippet,
            "full_text": self.full_text,
            "size_bytes": self.size_bytes,
            "metadata": self.metadata,
        }


@dataclass
class QueryResponse:
    """Full response returned by query engine."""
    total_matches: int
    matches: List[QueryMatch]
    session_ids: List[str] = field(default_factory=list)
    sessions: List[Dict[str, Any]] = field(default_factory=list)
    engine: str = "grep"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_matches": self.total_matches,
            "matches": [m.to_dict() for m in self.matches],
            "session_ids": self.session_ids,
            "sessions": self.sessions,
            "engine": self.engine,
        }


class BaseQueryEngine(ABC):
    """Abstract interface for all session query engine backends."""

    name: str = "base"

    @abstractmethod
    def search(self, app: Any, request: QueryRequest) -> QueryResponse:
        """
        Execute search against sessions, turns, and scratchpad areas.

        Args:
            app: The ChatybotApp instance (gives access to session store, turns, scratchpad).
            request: The validated QueryRequest object.

        Returns:
            QueryResponse containing matching items and metadata.
        """
        pass


# Query Engine Registry
_ENGINE_REGISTRY: Dict[str, Type[BaseQueryEngine]] = {}


def register_query_engine(name: str):
    """Decorator to register a query engine class."""
    def decorator(cls: Type[BaseQueryEngine]):
        cls.name = name
        _ENGINE_REGISTRY[name.lower()] = cls
        return cls
    return decorator


def get_query_engine(name: Optional[str] = None) -> BaseQueryEngine:
    """
    Get an instance of a registered query engine.
    Defaults to 'grep'.
    """
    engine_name = (name or "grep").lower().strip()
    if engine_name not in _ENGINE_REGISTRY:
        # Fallback to grep if requested engine is unknown
        engine_cls = _ENGINE_REGISTRY.get("grep")
        if not engine_cls:
            raise KeyError(f"No query engine registered under '{engine_name}' and default 'grep' not found.")
        return engine_cls()
    return _ENGINE_REGISTRY[engine_name]()


def list_query_engines() -> List[str]:
    """Return names of all registered query engines."""
    return sorted(list(_ENGINE_REGISTRY.keys()))
