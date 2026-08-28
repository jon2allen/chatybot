"""
session_store_jsonl.py - Directory-based JSONL implementation of BaseSessionStore.
Layout:
    <sessions_dir>/<session_id>/
        ├── meta.json         # Atomic JSON metadata
        └── turns.jsonl       # Append-only turn records (or turns.jsonl.gz if compressed)
"""

import os
import re
import json
import gzip
import time
import shutil
import sys
from datetime import datetime
from typing import Dict, Any, List, Tuple, Optional

from .session_interface import BaseSessionStore


class JsonlSessionStore(BaseSessionStore):
    """
    JSON Lines session storage backend.
    Stores each session as a directory containing meta.json and turns.jsonl.
    """

    def __init__(self, sessions_dir: str):
        super().__init__(sessions_dir)
        os.makedirs(self.sessions_dir, exist_ok=True)
        self._cache_dir_mtime: float = -1.0
        self._summary_cache: List[Dict[str, Any]] = []

    def _session_dir(self, session_id: str) -> str:
        return os.path.join(self.sessions_dir, session_id)

    def _meta_path(self, session_id: str) -> str:
        return os.path.join(self._session_dir(session_id), "meta.json")

    def _turns_path(self, session_id: str) -> str:
        return os.path.join(self._session_dir(session_id), "turns.jsonl")

    def _turns_gz_path(self, session_id: str) -> str:
        return os.path.join(self._session_dir(session_id), "turns.jsonl.gz")

    def _session_lock_path(self, session_id: str) -> str:
        return os.path.join(self.sessions_dir, f"{session_id}.lock")

    def _slugify_text(self, text: str, max_words: int = 6) -> str:
        clean = re.sub(r"[^\w\s-]", "", text.strip())
        words = clean.split()[:max_words]
        slug = "_".join(words).lower()
        return slug if slug else "untitled_session"

    def _invalidate_cache(self) -> None:
        self._cache_dir_mtime = -1.0
        self._summary_cache.clear()

    def _pid_alive(self, pid: int) -> bool:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return False
        except PermissionError:
            return True
        except OSError:
            return False
        return True

    def acquire_lock(self, session_id: str) -> bool:
        lock_path = self._session_lock_path(session_id)
        now_ts = time.time()
        if os.path.exists(lock_path):
            try:
                with open(lock_path, "r") as f:
                    content = f.read().strip()
                lines = content.splitlines()
                pid = int(lines[0]) if lines else 0
                lock_time_str = lines[1] if len(lines) > 1 else None

                if pid == os.getpid():
                    return True

                is_alive = self._pid_alive(pid)
                # Check for stale lock by age (older than 24 hours)
                is_stale = False
                if lock_time_str:
                    try:
                        lock_dt = datetime.fromisoformat(lock_time_str)
                        if (now_ts - lock_dt.timestamp()) > 86400.0:
                            is_stale = True
                    except Exception:
                        pass
                else:
                    # No timestamp: fallback to file mtime
                    if (now_ts - os.path.getmtime(lock_path)) > 86400.0:
                        is_stale = True

                if is_alive and not is_stale:
                    print(
                        f"Warning: Session '{session_id}' is in use by PID {pid}. "
                        f"Concurrent writes may cause divergent history."
                    )
                    return False
                elif is_stale:
                    print(f"Notice: Cleared stale lock file for session '{session_id}' (PID {pid}).")
            except (ValueError, IOError):
                pass

        try:
            now_iso = datetime.now().isoformat()
            with open(lock_path, "w") as f:
                f.write(f"{os.getpid()}\n{now_iso}\n")
            return True
        except IOError:
            return False

    def release_lock(self, session_id: Optional[str] = None) -> None:
        if not session_id:
            return
        lock_path = self._session_lock_path(session_id)
        try:
            if os.path.exists(lock_path):
                with open(lock_path, "r") as f:
                    content = f.read().strip()
                pid = int(content.splitlines()[0]) if content else 0
                if pid == os.getpid():
                    os.remove(lock_path)
        except (ValueError, IOError, OSError):
            pass

    def create_session(
        self,
        session_id: str,
        model_alias: str,
        custom_name: Optional[str] = None,
        initial_prompt: str = "",
        notes: Optional[str] = None,
    ) -> Dict[str, Any]:
        with self._thread_lock:
            s_dir = self._session_dir(session_id)
            os.makedirs(s_dir, exist_ok=True)

            now = datetime.now().isoformat()
            slug = self._slugify_text(initial_prompt) if initial_prompt else "untitled_session"

            meta = {
                "session_id": session_id,
                "model_alias": model_alias,
                "created_at": now,
                "updated_at": now,
                "first_prompt_slug": slug,
                "custom_name": custom_name,
                "notes": notes[:1024] if notes else None,
                "turn_count": 0,
                "compressed": False,
                "format": "jsonl-v1",
            }

            self.save_meta(session_id, meta)
            # Ensure turns.jsonl exists
            turns_file = self._turns_path(session_id)
            if not os.path.exists(turns_file) and not os.path.exists(self._turns_gz_path(session_id)):
                open(turns_file, "a", encoding="utf-8").close()

            self._invalidate_cache()
            return meta

    def save_meta(self, session_id: str, meta_dict: Dict[str, Any]) -> None:
        with self._thread_lock:
            s_dir = self._session_dir(session_id)
            os.makedirs(s_dir, exist_ok=True)
            meta_file = self._meta_path(session_id)
            tmp_file = meta_file + ".tmp"

            with open(tmp_file, "w", encoding="utf-8") as f:
                json.dump(meta_dict, f, indent=2, ensure_ascii=False)
            os.replace(tmp_file, meta_file)
            self._invalidate_cache()

    def _ensure_uncompressed_turns(self, session_id: str) -> str:
        """If turns.jsonl.gz exists, decompress it for appending/reading."""
        turns_file = self._turns_path(session_id)
        gz_file = self._turns_gz_path(session_id)
        if os.path.exists(gz_file) and not os.path.exists(turns_file):
            with gzip.open(gz_file, "rb") as f_in, open(turns_file, "wb") as f_out:
                shutil.copyfileobj(f_in, f_out)
            os.remove(gz_file)
            meta = self._read_meta(session_id)
            if meta and meta.get("compressed"):
                meta["compressed"] = False
                self.save_meta(session_id, meta)
        return turns_file

    def _read_meta(self, session_id: str) -> Optional[Dict[str, Any]]:
        meta_file = self._meta_path(session_id)
        if os.path.exists(meta_file):
            try:
                with open(meta_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return None

    def append_turn(self, session_id: str, turn_data: Dict[str, Any]) -> None:
        with self._thread_lock:
            turns_file = self._ensure_uncompressed_turns(session_id)

            compact_turn = {k: v for k, v in turn_data.items() if v is not None}
            line = json.dumps(compact_turn, ensure_ascii=False)

            with open(turns_file, "a", encoding="utf-8") as f:
                f.write(line + "\n")

            # Update metadata atomically
            meta = self._read_meta(session_id) or {}
            now = datetime.now().isoformat()
            meta["session_id"] = session_id
            meta["updated_at"] = now
            meta["turn_count"] = meta.get("turn_count", 0) + 1
            if not meta.get("first_prompt_slug") or meta.get("first_prompt_slug") == "untitled_session":
                prompt = turn_data.get("prompt", "")
                if prompt:
                    meta["first_prompt_slug"] = self._slugify_text(prompt)
            meta["format"] = "jsonl-v1"
            self.save_meta(session_id, meta)

    def replace_turns(self, session_id: str, turns: List[Dict[str, Any]]) -> None:
        """Atomically overwrite or replace all turns in the session storage."""
        with self._thread_lock:
            s_dir = self._session_dir(session_id)
            os.makedirs(s_dir, exist_ok=True)
            turns_file = self._turns_path(session_id)
            tmp_turns = turns_file + ".tmp"

            with open(tmp_turns, "w", encoding="utf-8") as f:
                for turn in turns:
                    compact_turn = {k: v for k, v in turn.items() if v is not None}
                    f.write(json.dumps(compact_turn, ensure_ascii=False) + "\n")

            os.replace(tmp_turns, turns_file)

            # If a compressed version existed, remove it so the new plain turns are in effect
            gz_file = self._turns_gz_path(session_id)
            if os.path.exists(gz_file):
                try:
                    os.remove(gz_file)
                except OSError:
                    pass

            meta = self._read_meta(session_id) or {}
            now = datetime.now().isoformat()
            meta["session_id"] = session_id
            meta["updated_at"] = now
            meta["turn_count"] = len(turns)
            meta["compressed"] = False
            meta["format"] = "jsonl-v1"
            self.save_meta(session_id, meta)

    def load_session(self, target: str) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
        sid = self.resolve_session(target)
        if not sid:
            raise FileNotFoundError(f"Session '{target}' not found.")

        meta = self._read_meta(sid) or {}
        turns_file = self._turns_path(sid)
        gz_file = self._turns_gz_path(sid)

        turns: List[Dict[str, Any]] = []
        corrupted_lines = 0

        if os.path.exists(turns_file):
            with open(turns_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            turns.append(json.loads(line))
                        except json.JSONDecodeError:
                            corrupted_lines += 1
        elif os.path.exists(gz_file):
            with gzip.open(gz_file, "rt", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            turns.append(json.loads(line))
                        except json.JSONDecodeError:
                            corrupted_lines += 1

        if corrupted_lines > 0:
            print(
                f"Warning: Session '{sid}' had {corrupted_lines} unparseable corrupted line(s) in turns.jsonl.",
                file=sys.stderr,
            )

        expected_count = meta.get("turn_count")
        if expected_count is not None and len(turns) != expected_count:
            # Metadata mismatch warning
            pass

        return meta, turns

    def resolve_session(self, target: str) -> Optional[str]:
        target = target.strip(" \"'")
        # 1. Exact directory match
        direct_path = os.path.join(self.sessions_dir, target)
        if os.path.isdir(direct_path) and os.path.exists(os.path.join(direct_path, "meta.json")):
            return target

        # 2. Check if absolute path
        if os.path.isabs(target) and os.path.isdir(target) and os.path.exists(os.path.join(target, "meta.json")):
            return os.path.basename(target)

        # 3. Match custom_name or session_id across metadata
        if os.path.exists(self.sessions_dir):
            for d in os.listdir(self.sessions_dir):
                dpath = os.path.join(self.sessions_dir, d)
                if os.path.isdir(dpath) and not d.startswith("."):
                    meta = self._read_meta(d)
                    if meta and (meta.get("custom_name") == target or meta.get("session_id") == target):
                        return d
        return None

    def _get_all_summaries(self) -> List[Dict[str, Any]]:
        """Single-pass cache loader across all session directories."""
        if not os.path.exists(self.sessions_dir):
            return []

        try:
            current_mtime = os.path.getmtime(self.sessions_dir)
        except OSError:
            current_mtime = 0.0

        if self._cache_dir_mtime == current_mtime and self._summary_cache:
            return list(self._summary_cache)

        summaries: List[Dict[str, Any]] = []
        for d in os.listdir(self.sessions_dir):
            dpath = os.path.join(self.sessions_dir, d)
            if os.path.isdir(dpath) and not d.startswith("."):
                meta = self._read_meta(d)
                if not meta:
                    continue

                upd = meta.get("updated_at", "")[:16].replace("T", " ")
                compressed = bool(
                    meta.get("compressed") or os.path.exists(self._turns_gz_path(d))
                )
                summaries.append({
                    "sid": meta.get("session_id", d),
                    "cname": meta.get("custom_name"),
                    "slug": meta.get("first_prompt_slug", ""),
                    "turns_cnt": meta.get("turn_count", 0),
                    "upd": upd,
                    "updated_at": meta.get("updated_at", "1970-01-01T00:00:00"),
                    "snote": meta.get("notes"),
                    "compressed": compressed,
                    "model_alias": meta.get("model_alias"),
                })

        summaries.sort(key=lambda x: x["updated_at"], reverse=True)
        self._summary_cache = summaries
        self._cache_dir_mtime = current_mtime
        return list(summaries)

    def list_sessions(
        self,
        offset: int = 0,
        limit: Optional[int] = 10,
        model_filter: Optional[str] = None,
        compressed_filter: Optional[bool] = None,
    ) -> List[Dict[str, Any]]:
        summaries = self._get_all_summaries()

        parsed: List[Dict[str, Any]] = []
        for s in summaries:
            if model_filter and model_filter not in (s.get("model_alias") or "").lower():
                continue
            if compressed_filter is not None and s.get("compressed") != compressed_filter:
                continue
            parsed.append(s)

        if limit is not None:
            return parsed[offset : offset + limit]
        return parsed[offset:]

    def delete_session(self, target: str) -> bool:
        with self._thread_lock:
            sid = self.resolve_session(target)
            if not sid:
                return False
            s_dir = self._session_dir(sid)
            if os.path.exists(s_dir):
                shutil.rmtree(s_dir, ignore_errors=True)
            self.release_lock(sid)
            self._invalidate_cache()
            return True

    def delete_all_sessions(self) -> int:
        with self._thread_lock:
            if not os.path.exists(self.sessions_dir):
                return 0
            count = 0
            for d in os.listdir(self.sessions_dir):
                dpath = os.path.join(self.sessions_dir, d)
                if os.path.isdir(dpath) and not d.startswith("."):
                    shutil.rmtree(dpath, ignore_errors=True)
                    count += 1
                elif d.endswith(".lock"):
                    try:
                        os.remove(dpath)
                    except OSError:
                        pass
            self._invalidate_cache()
            return count

    def merge_sessions(self, target_name: str, source_targets: List[str]) -> str:
        with self._thread_lock:
            merged_turns: List[Dict[str, Any]] = []
            merged_models: List[str] = []
            first_slug: Optional[str] = None
            source_notes: List[str] = []

            for st in source_targets:
                sid = self.resolve_session(st)
                if not sid:
                    raise FileNotFoundError(f"Source session '{st}' not found. Merge aborted.")
                meta, turns = self.load_session(sid)
                if not first_slug:
                    first_slug = meta.get("first_prompt_slug")
                m_alias = meta.get("model_alias", "default")
                if m_alias not in merged_models:
                    merged_models.append(m_alias)
                src_label = meta.get("custom_name") or meta.get("session_id", st)
                src_note = meta.get("notes")
                if src_note:
                    source_notes.append(f"[{src_label}] {src_note}")
                for turn in turns:
                    new_turn = dict(turn)
                    new_turn["turn_id"] = len(merged_turns) + 1
                    merged_turns.append(new_turn)

            now = datetime.now()
            model_alias = "_".join(merged_models)
            timestamp = now.strftime("%Y%m%d_%H%M%S")
            base_new_sid = f"merged_{timestamp}"

            # Collision avoidance loop
            new_sid = base_new_sid
            suffix = 2
            while self.resolve_session(new_sid):
                new_sid = f"{base_new_sid}_{suffix}"
                suffix += 1

            merged_notes = " | ".join(source_notes)[:1024] if source_notes else None

            # Prepare new session directory atomically
            target_dir = self._session_dir(new_sid)
            temp_dir = os.path.join(self.sessions_dir, f".{new_sid}.merge_tmp")
            try:
                os.makedirs(temp_dir, exist_ok=True)

                turns_tmp = os.path.join(temp_dir, "turns.jsonl")
                with open(turns_tmp, "w", encoding="utf-8") as f:
                    for turn in merged_turns:
                        compact_turn = {k: v for k, v in turn.items() if v is not None}
                        f.write(json.dumps(compact_turn, ensure_ascii=False) + "\n")

                meta = {
                    "session_id": new_sid,
                    "model_alias": model_alias,
                    "created_at": now.isoformat(),
                    "updated_at": now.isoformat(),
                    "first_prompt_slug": first_slug or "merged_session",
                    "custom_name": target_name,
                    "notes": merged_notes,
                    "turn_count": len(merged_turns),
                    "compressed": False,
                    "format": "jsonl-v1",
                }
                meta_tmp = os.path.join(temp_dir, "meta.json")
                with open(meta_tmp, "w", encoding="utf-8") as f:
                    json.dump(meta, f, indent=2, ensure_ascii=False)

                if os.path.exists(target_dir):
                    shutil.rmtree(target_dir, ignore_errors=True)
                os.replace(temp_dir, target_dir)
                self._invalidate_cache()
                return new_sid
            except Exception as e:
                if os.path.exists(temp_dir):
                    shutil.rmtree(temp_dir, ignore_errors=True)
                raise RuntimeError(f"Merge sessions failed: {e}") from e

    def _parse_iso_timestamp(self, ts_str: Optional[str]) -> Optional[float]:
        if not ts_str:
            return None
        try:
            dt = datetime.fromisoformat(ts_str)
            return dt.timestamp()
        except Exception:
            return None

    def _get_session_timestamp(self, session_id: str, fallback_mtime: float = 0.0) -> float:
        meta = self._read_meta(session_id)
        if meta:
            ts = self._parse_iso_timestamp(meta.get("updated_at")) or self._parse_iso_timestamp(meta.get("created_at"))
            if ts is not None:
                return ts
        return fallback_mtime

    def compress_sessions(
        self,
        older_than_days: Optional[float] = None,
        target: Optional[str] = None,
        active_session_id: Optional[str] = None,
    ) -> Tuple[int, int]:
        with self._thread_lock:
            if not os.path.exists(self.sessions_dir):
                return 0, 0

            now_ts = time.time()
            count = 0
            saved_bytes = 0
            target_pattern = target.lower() if (target and target.lower() != "all") else None

            for d in os.listdir(self.sessions_dir):
                if d == active_session_id or d.startswith("."):
                    continue
                dpath = os.path.join(self.sessions_dir, d)
                if os.path.isdir(dpath):
                    meta = self._read_meta(d) or {}
                    if target_pattern:
                        import fnmatch
                        cname = (meta.get("custom_name") or "").lower()
                        slug = (meta.get("first_prompt_slug") or "").lower()
                        d_lower = d.lower()
                        if not (fnmatch.fnmatch(d_lower, target_pattern) or (cname and fnmatch.fnmatch(cname, target_pattern)) or (slug and fnmatch.fnmatch(slug, target_pattern))):
                            continue

                    turns_file = self._turns_path(d)
                    gz_file = self._turns_gz_path(d)
                    if os.path.exists(turns_file) and not os.path.exists(gz_file):
                        file_mtime = os.path.getmtime(turns_file)
                        mtime = self._get_session_timestamp(d, fallback_mtime=file_mtime)
                        age_days = (now_ts - mtime) / 86400.0

                        if older_than_days is None or age_days >= older_than_days:
                            orig_sz = os.path.getsize(turns_file)
                            with open(turns_file, "rb") as f_in, gzip.open(gz_file, "wb") as f_out:
                                shutil.copyfileobj(f_in, f_out)
                            new_sz = os.path.getsize(gz_file)
                            saved_bytes += (orig_sz - new_sz)
                            os.remove(turns_file)

                            meta["compressed"] = True
                            self.save_meta(d, meta)
                            count += 1

            self._invalidate_cache()
            return count, saved_bytes

    def uncompress_sessions(self, target: Optional[str] = None) -> int:
        with self._thread_lock:
            if not os.path.exists(self.sessions_dir):
                return 0

            target_sids = []
            if target and target.lower() != "all":
                sid = self.resolve_session(target)
                if sid:
                    target_sids.append(sid)
                else:
                    import fnmatch
                    pattern = target.lower()
                    for d in os.listdir(self.sessions_dir):
                        dpath = os.path.join(self.sessions_dir, d)
                        if os.path.isdir(dpath) and not d.startswith("."):
                            meta = self._read_meta(d) or {}
                            cname = (meta.get("custom_name") or "").lower()
                            slug = (meta.get("first_prompt_slug") or "").lower()
                            d_lower = d.lower()
                            if fnmatch.fnmatch(d_lower, pattern) or (cname and fnmatch.fnmatch(cname, pattern)) or (slug and fnmatch.fnmatch(slug, pattern)):
                                target_sids.append(d)
                    if not target_sids:
                        return 0
            else:
                for d in os.listdir(self.sessions_dir):
                    dpath = os.path.join(self.sessions_dir, d)
                    if os.path.isdir(dpath) and not d.startswith("."):
                        target_sids.append(d)

            count = 0
            for sid in target_sids:
                turns_file = self._turns_path(sid)
                gz_file = self._turns_gz_path(sid)
                if os.path.exists(gz_file):
                    with gzip.open(gz_file, "rb") as f_in, open(turns_file, "wb") as f_out:
                        shutil.copyfileobj(f_in, f_out)
                    os.remove(gz_file)
                    meta = self._read_meta(sid)
                    if meta:
                        meta["compressed"] = False
                        self.save_meta(sid, meta)
                    count += 1

            self._invalidate_cache()
            return count

    def prune_sessions(
        self,
        keep_n: Optional[int] = None,
        max_days: Optional[float] = None,
        max_size_mb: Optional[float] = None,
        active_session_id: Optional[str] = None,
    ) -> int:
        with self._thread_lock:
            if not os.path.exists(self.sessions_dir):
                return 0

            entries: List[Tuple[str, float, int]] = []  # (dir_path, mtime, total_bytes)
            now_ts = time.time()

            for d in os.listdir(self.sessions_dir):
                if d == active_session_id or d.startswith("."):
                    continue
                dpath = os.path.join(self.sessions_dir, d)
                if os.path.isdir(dpath):
                    total_sz = 0
                    max_mtime = 0.0
                    for root, _, files in os.walk(dpath):
                        for f in files:
                            fp = os.path.join(root, f)
                            try:
                                sz = os.path.getsize(fp)
                                mt = os.path.getmtime(fp)
                                total_sz += sz
                                if mt > max_mtime:
                                    max_mtime = mt
                            except OSError:
                                pass
                    session_ts = self._get_session_timestamp(d, fallback_mtime=max_mtime)
                    entries.append((dpath, session_ts, total_sz))

            # Sort newest first
            entries.sort(key=lambda x: x[1], reverse=True)
            to_delete: set = set()

            if keep_n is not None and keep_n >= 0:
                for dpath, _, _ in entries[keep_n:]:
                    to_delete.add(dpath)

            if max_days is not None and max_days > 0:
                cutoff = now_ts - (max_days * 86400.0)
                for dpath, mtime, _ in entries:
                    if mtime < cutoff:
                        to_delete.add(dpath)

            if max_size_mb is not None and max_size_mb > 0:
                max_bytes = max_size_mb * 1024 * 1024
                accum = 0
                for dpath, _, sz in entries:
                    if dpath in to_delete:
                        continue
                    accum += sz
                    if accum > max_bytes:
                        to_delete.add(dpath)

            count = 0
            for dpath in to_delete:
                try:
                    shutil.rmtree(dpath, ignore_errors=True)
                    count += 1
                except OSError:
                    pass

            self._invalidate_cache()
            return count

    def get_workspace_metrics(self) -> Dict[str, Any]:
        if not os.path.exists(self.sessions_dir):
            return {
                "total_count": 0,
                "total_bytes": 0,
                "oldest": (None, 0),
                "newest": (None, 0),
                "largest": (None, 0),
            }

        total_bytes = 0
        oldest_name, oldest_mtime = None, float("inf")
        newest_name, newest_mtime = None, 0.0
        largest_name, largest_bytes = None, 0
        count = 0

        for d in os.listdir(self.sessions_dir):
            dpath = os.path.join(self.sessions_dir, d)
            if os.path.isdir(dpath) and not d.startswith("."):
                dir_sz = 0
                max_mt = 0.0
                for root, _, files in os.walk(dpath):
                    for f in files:
                        fp = os.path.join(root, f)
                        try:
                            sz = os.path.getsize(fp)
                            mt = os.path.getmtime(fp)
                            dir_sz += sz
                            if mt > max_mt:
                                max_mt = mt
                        except OSError:
                            pass

                count += 1
                total_bytes += dir_sz
                session_ts = self._get_session_timestamp(d, fallback_mtime=max_mt)
                if session_ts < oldest_mtime:
                    oldest_mtime = session_ts
                    oldest_name = d
                if session_ts > newest_mtime:
                    newest_mtime = session_ts
                    newest_name = d
                if dir_sz > largest_bytes:
                    largest_bytes = dir_sz
                    largest_name = d

        return {
            "total_count": count,
            "total_bytes": total_bytes,
            "oldest": (oldest_name, oldest_mtime if oldest_name else 0),
            "newest": (newest_name, newest_mtime if newest_name else 0),
            "largest": (largest_name, largest_bytes),
        }
