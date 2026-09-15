"""
session_interface.py - Abstract Base Class for Chatybot session storage providers.
Defines the contract for all pluggable session store implementations.
"""

import threading
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any


class BaseSessionStore(ABC):
    """Abstract interface that all session storage engines must implement."""

    def __init__(self, sessions_dir: str):
        self.sessions_dir = sessions_dir
        self._thread_lock = threading.RLock()

    @abstractmethod
    def create_session(
        self,
        session_id: str,
        model_alias: str,
        custom_name: str | None = None,
        initial_prompt: str = "",
        notes: str | None = None,
    ) -> dict[str, Any]:
        """Initialize and persist initial session state."""

    @abstractmethod
    def append_turn(self, session_id: str, turn_data: dict[str, Any]) -> None:
        """Append a completed interaction turn to session storage."""

    @abstractmethod
    def replace_turns(self, session_id: str, turns: list[dict[str, Any]]) -> None:
        """Atomically overwrite or replace all turns in the session storage."""

    @abstractmethod
    def save_meta(self, session_id: str, meta_dict: dict[str, Any]) -> None:
        """Update session-level metadata (custom_name, notes, updated_at, etc.)."""

    @abstractmethod
    def load_session(self, target: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        """
        Load session metadata and all associated turns.
        Returns:
            Tuple of (meta_dict, list_of_turns)
        """

    @abstractmethod
    def resolve_session(self, target: str) -> str | None:
        """
        Resolve a session identifier, custom name, or path to a canonical session ID.
        Returns:
            Canonical session_id or None if not found.
        """

    @abstractmethod
    def list_sessions(
        self,
        offset: int = 0,
        limit: int | None = 10,
        model_filter: str | None = None,
        compressed_filter: bool | None = None,
        since_dt: datetime | None = None,
    ) -> list[dict[str, Any]]:
        """
        List all saved sessions sorted by most recently updated.
        Returns lightweight summaries:
            [{'sid': ..., 'cname': ..., 'slug': ..., 'turns_cnt': ..., 'upd': ..., 'snote': ..., 'compressed': ...}, ...]

        Args:
            since_dt: If provided, only include sessions whose updated_at >= this datetime.
                      Accepts a datetime object (naive = local time).
        """

    def get_session_size(self, target: str) -> int:
        """
        Return the total storage size in bytes of the session on disk, or 0 if not found.
        """
        return 0

    @abstractmethod
    def delete_session(self, target: str) -> bool:
        """Delete a single session by ID, custom name, or path. Returns True if deleted."""

    @abstractmethod
    def delete_all_sessions(self) -> int:
        """Delete all saved sessions. Returns count of deleted sessions."""

    @abstractmethod
    def merge_sessions(self, target_name: str, source_targets: list[str]) -> str:
        """
        Merge multiple source sessions sequentially into a new session.
        Returns the new session_id.
        """

    @abstractmethod
    def compress_sessions(
        self,
        older_than_days: float | None = None,
        target: str | None = None,
        active_session_id: str | None = None,
    ) -> tuple[int, int]:
        """
        Compress session turn files (e.g. gzip).
        Args:
            older_than_days: Only compress sessions older than N days.
            target: Optional specific session ID/name, or wildcard pattern (e.g. 'mistral*').
            active_session_id: Active session to exclude from compression.
        Returns:
            Tuple of (compressed_count, saved_bytes)
        """

    @abstractmethod
    def uncompress_sessions(self, target: str | None = None) -> int:
        """
        Decompress compressed session files.
        Args:
            target: Specific session ID/name to uncompress, or 'all'/None to uncompress all.
        Returns:
            Count of uncompressed sessions.
        """

    @abstractmethod
    def prune_sessions(
        self,
        keep_n: int | None = None,
        max_days: float | None = None,
        max_size_mb: float | None = None,
        active_session_id: str | None = None,
    ) -> int:
        """
        Prune sessions by count, age, or storage quota.
        Returns count of pruned sessions.
        """

    @abstractmethod
    def get_workspace_metrics(self) -> dict[str, Any]:
        """
        Aggregate workspace metrics.
        Returns:
            {'total_count': int, 'total_bytes': int, 'oldest': tuple, 'newest': tuple, 'largest': tuple}
        """

    @abstractmethod
    def acquire_lock(self, session_id: str) -> bool:
        """
        Attempt to acquire an advisory concurrency lock file for the session.
        Returns True if lock acquired or already owned, False if held by another active process.
        """

    @abstractmethod
    def release_lock(self, session_id: str | None = None) -> None:
        """Release the advisory concurrency lock file for the session."""
