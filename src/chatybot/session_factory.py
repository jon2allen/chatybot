"""
session_factory.py - Registry and factory for creating BaseSessionStore instances.
"""

from typing import Dict, Type, Optional
from .session_interface import BaseSessionStore
from .session_store_jsonl import JsonlSessionStore
from .session_store_monolithic import MonolithicJsonSessionStore

# Registry of supported storage engines
_SESSION_ENGINES: Dict[str, Type[BaseSessionStore]] = {
    "jsonl": JsonlSessionStore,
    "monolithic": MonolithicJsonSessionStore,
    "json": MonolithicJsonSessionStore,
}


def register_session_engine(name: str, engine_cls: Type[BaseSessionStore]) -> None:
    """Register a custom session storage provider."""
    _SESSION_ENGINES[name.lower()] = engine_cls


def get_session_store(
    engine: str = "jsonl",
    sessions_dir: str = "~/.local/share/chatybot/sessions",
) -> BaseSessionStore:
    """
    Factory function to instantiate a session store backend.

    Args:
        engine: Engine name ('jsonl', 'monolithic', or custom registered engine).
        sessions_dir: Path to directory storing session files.

    Returns:
        Instance of BaseSessionStore.
    """
    import os

    resolved_dir = os.path.expanduser(sessions_dir)
    engine_key = engine.lower()

    if engine_key not in _SESSION_ENGINES:
        raise ValueError(
            f"Unknown session storage engine '{engine}'. "
            f"Supported engines: {list(_SESSION_ENGINES.keys())}"
        )

    store_cls = _SESSION_ENGINES[engine_key]
    return store_cls(resolved_dir)
