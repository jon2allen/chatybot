"""
session_interface.py - Abstract Base Class for Chatybot session storage providers.
Defines the contract for all pluggable session store implementations.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Tuple, Optional


class BaseSessionStore(ABC):
    """Abstract interface that all session storage engines must implement."""

    def __init__(self, sessions_dir: str):
        self.sessions_dir = sessions_dir

    @abstractmethod
    def create_session(
        self,
        session_id: str,
        model_alias: str,
        custom_name: Optional[str] = None,
        initial_prompt: str = "",
        notes: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Initialize and persist initial session state."""
        pass

    @abstractmethod
    def append_turn(self, session_id: str, turn_data: Dict[str, Any]) -> None:
        """Append a completed interaction turn to session storage."""
        pass

    @abstractmethod
    def save_meta(self, session_id: str, meta_dict: Dict[str, Any]) -> None:
        """Update session-level metadata (custom_name, notes, updated_at, etc.)."""
        pass

    @abstractmethod
    def load_session(self, target: str) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
        """
        Load session metadata and all associated turns.
        Returns:
            Tuple of (meta_dict, list_of_turns)
        """
        pass

    @abstractmethod
    def resolve_session(self, target: str) -> Optional[str]:
        """
        Resolve a session identifier, custom name, or path to a canonical session ID.
        Returns:
            Canonical session_id or None if not found.
        """
        pass

    @abstractmethod
    def list_sessions(
        self,
        offset: int = 0,
        limit: Optional[int] = 10,
        model_filter: Optional[str] = None,
        compressed_filter: Optional[bool] = None,
    ) -> List[Dict[str, Any]]:
        """
        List all saved sessions sorted by most recently updated.
        Returns lightweight summaries:
            [{'sid': ..., 'cname': ..., 'slug': ..., 'turns_cnt': ..., 'upd': ..., 'snote': ..., 'compressed': ...}, ...]
        """
        pass

    @abstractmethod
    def delete_session(self, target: str) -> bool:
        """Delete a single session by ID, custom name, or path. Returns True if deleted."""
        pass

    @abstractmethod
    def delete_all_sessions(self) -> int:
        """Delete all saved sessions. Returns count of deleted sessions."""
        pass

    @abstractmethod
    def merge_sessions(self, target_name: str, source_targets: List[str]) -> str:
        """
        Merge multiple source sessions sequentially into a new session.
        Returns the new session_id.
        """
        pass

    @abstractmethod
    def compress_sessions(
        self,
        older_than_days: Optional[float] = None,
        target: Optional[str] = None,
        active_session_id: Optional[str] = None,
    ) -> Tuple[int, int]:
        """
        Compress session turn files (e.g. gzip).
        Args:
            older_than_days: Only compress sessions older than N days.
            target: Optional specific session ID/name, or wildcard pattern (e.g. 'mistral*').
            active_session_id: Active session to exclude from compression.
        Returns:
            Tuple of (compressed_count, saved_bytes)
        """
        pass

    @abstractmethod
    def uncompress_sessions(self, target: Optional[str] = None) -> int:
        """
        Decompress compressed session files.
        Args:
            target: Specific session ID/name to uncompress, or 'all'/None to uncompress all.
        Returns:
            Count of uncompressed sessions.
        """
        pass

    @abstractmethod
    def prune_sessions(
        self,
        keep_n: Optional[int] = None,
        max_days: Optional[float] = None,
        max_size_mb: Optional[float] = None,
        active_session_id: Optional[str] = None,
    ) -> int:
        """
        Prune sessions by count, age, or storage quota.
        Returns count of pruned sessions.
        """
        pass

    @abstractmethod
    def get_workspace_metrics(self) -> Dict[str, Any]:
        """
        Aggregate workspace metrics.
        Returns:
            {'total_count': int, 'total_bytes': int, 'oldest': tuple, 'newest': tuple, 'largest': tuple}
        """
        pass

    @abstractmethod
    def acquire_lock(self, session_id: str) -> bool:
        """Acquire a concurrency lock file for the session."""
        pass

    @abstractmethod
    def release_lock(self, session_id: Optional[str] = None) -> None:
        """Release the concurrency lock file for the session."""
        pass
