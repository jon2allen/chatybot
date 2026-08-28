"""
session_store_monolithic.py - Flat JSON implementation of BaseSessionStore for backward compatibility.
Stores each session as a single monolithic JSON file (<session_id>.json or <session_id>.json.gz).
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


class MonolithicJsonSessionStore(BaseSessionStore):
    """
    Legacy monolithic JSON session storage backend.
    Stores each session as a single JSON file (<session_id>.json).
    """

    def __init__(self, sessions_dir: str):
        super().__init__(sessions_dir)
        os.makedirs(self.sessions_dir, exist_ok=True)
        self._cache_dir_mtime: float = -1.0
        self._summary_cache: List[Dict[str, Any]] = []

    def _session_file(self, session_id: str) -> str:
        return os.path.join(self.sessions_dir, f"{session_id}.json")

    def _session_gz_file(self, session_id: str) -> str:
        return os.path.join(self.sessions_dir, f"{session_id}.json.gz")

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
                is_stale = False
                if lock_time_str:
                    try:
                        lock_dt = datetime.fromisoformat(lock_time_str)
                        if (now_ts - lock_dt.timestamp()) > 86400.0:
                            is_stale = True
                    except Exception:
                        pass
                else:
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
            now = datetime.now().isoformat()
            slug = self._slugify_text(initial_prompt) if initial_prompt else "untitled_session"

            payload = {
                "session_id": session_id,
                "model_alias": model_alias,
                "created_at": now,
                "updated_at": now,
                "first_prompt_slug": slug,
                "custom_name": custom_name,
                "notes": notes[:1024] if notes else None,
                "turns": [],
            }

            filepath = self._session_file(session_id)
            tmp_path = filepath + ".tmp"
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2, ensure_ascii=False)
            os.replace(tmp_path, filepath)

            self._invalidate_cache()
            return payload

    def save_meta(self, session_id: str, meta_dict: Dict[str, Any]) -> None:
        with self._thread_lock:
            # Preserve existing turns if already present on disk
            current_turns = []
            filepath = self._session_file(session_id)
            gz_path = self._session_gz_file(session_id)

            if os.path.exists(filepath):
                try:
                    with open(filepath, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        current_turns = data.get("turns", [])
                except Exception:
                    pass
            elif os.path.exists(gz_path):
                try:
                    with gzip.open(gz_path, "rt", encoding="utf-8") as f:
                        data = json.load(f)
                        current_turns = data.get("turns", [])
                    os.remove(gz_path)
                except Exception:
                    pass

            payload = dict(meta_dict)
            if "turns" not in payload:
                payload["turns"] = current_turns

            tmp_path = filepath + ".tmp"
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2, ensure_ascii=False)
            os.replace(tmp_path, filepath)
            self._invalidate_cache()

    def append_turn(self, session_id: str, turn_data: Dict[str, Any]) -> None:
        with self._thread_lock:
            filepath = self._session_file(session_id)
            gz_path = self._session_gz_file(session_id)

            data = {}
            if os.path.exists(gz_path) and not os.path.exists(filepath):
                with gzip.open(gz_path, "rt", encoding="utf-8") as f:
                    data = json.load(f)
                os.remove(gz_path)
            elif os.path.exists(filepath):
                with open(filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)

            if not data:
                data = {
                    "session_id": session_id,
                    "model_alias": "default",
                    "created_at": datetime.now().isoformat(),
                    "turns": [],
                }

            turns = data.setdefault("turns", [])
            compact_turn = {k: v for k, v in turn_data.items() if v is not None}
            turns.append(compact_turn)

            now = datetime.now().isoformat()
            data["updated_at"] = now
            if not data.get("first_prompt_slug") or data.get("first_prompt_slug") == "untitled_session":
                prompt = turn_data.get("prompt", "")
                if prompt:
                    data["first_prompt_slug"] = self._slugify_text(prompt)

            tmp_path = filepath + ".tmp"
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            os.replace(tmp_path, filepath)
            self._invalidate_cache()

    def replace_turns(self, session_id: str, turns: List[Dict[str, Any]]) -> None:
        """Atomically overwrite or replace all turns in the monolithic JSON storage."""
        with self._thread_lock:
            filepath = self._session_file(session_id)
            gz_path = self._session_gz_file(session_id)

            data = {}
            if os.path.exists(gz_path):
                try:
                    with gzip.open(gz_path, "rt", encoding="utf-8") as f:
                        data = json.load(f)
                    os.remove(gz_path)
                except Exception:
                    pass
            elif os.path.exists(filepath):
                try:
                    with open(filepath, "r", encoding="utf-8") as f:
                        data = json.load(f)
                except Exception:
                    pass

            if not data:
                data = {
                    "session_id": session_id,
                    "model_alias": "default",
                    "created_at": datetime.now().isoformat(),
                }

            data["turns"] = turns
            data["updated_at"] = datetime.now().isoformat()

            tmp_path = filepath + ".tmp"
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            os.replace(tmp_path, filepath)
            self._invalidate_cache()

    def load_session(self, target: str) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
        sid = self.resolve_session(target)
        if not sid:
            raise FileNotFoundError(f"Session '{target}' not found.")

        filepath = self._session_file(sid)
        gz_path = self._session_gz_file(sid)

        data = None
        if os.path.exists(filepath):
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
        elif os.path.exists(gz_path):
            with gzip.open(gz_path, "rt", encoding="utf-8") as f:
                data = json.load(f)
        else:
            raise FileNotFoundError(f"Session '{target}' files not found.")

        turns = data.pop("turns", [])
        data["turn_count"] = len(turns)
        return data, turns

    def resolve_session(self, target: str) -> Optional[str]:
        target = target.strip(" \"'")
        clean_target = target.removesuffix(".json.gz").removesuffix(".json")

        # 1. Exact filename check
        for candidate_name in (clean_target, target):
            p_json = os.path.join(self.sessions_dir, f"{candidate_name}.json")
            p_gz = os.path.join(self.sessions_dir, f"{candidate_name}.json.gz")
            if os.path.isfile(p_json):
                return candidate_name
            if os.path.isfile(p_gz):
                return candidate_name

        # 2. Metadata match
        if os.path.exists(self.sessions_dir):
            for fname in os.listdir(self.sessions_dir):
                if (fname.endswith(".json") or fname.endswith(".json.gz")) and not fname.startswith("."):
                    fp = os.path.join(self.sessions_dir, fname)
                    try:
                        open_fn = gzip.open if fname.endswith(".gz") else open
                        with open_fn(fp, "rt", encoding="utf-8") as sf:
                            sdata = json.load(sf)
                            if sdata.get("custom_name") == target or sdata.get("session_id") == target:
                                base = os.path.basename(fp)
                                return base.replace(".json.gz", "").replace(".json", "")
                    except Exception:
                        pass
        return None

    def _get_all_summaries(self) -> List[Dict[str, Any]]:
        """Single-pass cache loader across all monolithic session files."""
        if not os.path.exists(self.sessions_dir):
            return []

        try:
            current_mtime = os.path.getmtime(self.sessions_dir)
        except OSError:
            current_mtime = 0.0

        if self._cache_dir_mtime == current_mtime and self._summary_cache:
            return list(self._summary_cache)

        summaries: List[Dict[str, Any]] = []
        corrupted_files: List[str] = []

        files = [
            f
            for f in os.listdir(self.sessions_dir)
            if (f.endswith(".json") or f.endswith(".json.gz")) and not f.startswith(".")
        ]

        for fname in files:
            is_gz = fname.endswith(".gz")
            fp = os.path.join(self.sessions_dir, fname)
            try:
                open_fn = gzip.open if is_gz else open
                with open_fn(fp, "rt", encoding="utf-8") as sf:
                    sdata = json.load(sf)
                summaries.append({
                    "sid": sdata.get("session_id", fname),
                    "cname": sdata.get("custom_name"),
                    "slug": sdata.get("first_prompt_slug", ""),
                    "turns_cnt": len(sdata.get("turns", [])),
                    "upd": sdata.get("updated_at", "")[:16].replace("T", " "),
                    "updated_at": sdata.get("updated_at", "1970-01-01T00:00:00"),
                    "snote": sdata.get("notes"),
                    "compressed": is_gz,
                    "model_alias": sdata.get("model_alias"),
                })
            except Exception:
                corrupted_files.append(fname)

        if corrupted_files:
            print(
                f"Warning: {len(corrupted_files)} session file(s) could not be parsed: {', '.join(corrupted_files)}",
                file=sys.stderr,
            )

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
            filepath = self._session_file(sid)
            gz_path = self._session_gz_file(sid)
            deleted = False
            for p in (filepath, gz_path):
                if os.path.exists(p):
                    try:
                        os.remove(p)
                        deleted = True
                    except OSError:
                        pass
            self.release_lock(sid)
            self._invalidate_cache()
            return deleted

    def delete_all_sessions(self) -> int:
        with self._thread_lock:
            if not os.path.exists(self.sessions_dir):
                return 0
            count = 0
            for f in os.listdir(self.sessions_dir):
                if (f.endswith(".json") or f.endswith(".json.gz") or f.endswith(".lock")) and not f.startswith("."):
                    try:
                        os.remove(os.path.join(self.sessions_dir, f))
                        if not f.endswith(".lock"):
                            count += 1
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

            payload = {
                "session_id": new_sid,
                "model_alias": model_alias,
                "created_at": now.isoformat(),
                "updated_at": now.isoformat(),
                "first_prompt_slug": first_slug or "merged_session",
                "custom_name": target_name,
                "notes": merged_notes,
                "turns": merged_turns,
            }

            out_path = self._session_file(new_sid)
            tmp_path = out_path + ".tmp"
            try:
                with open(tmp_path, "w", encoding="utf-8") as out_f:
                    json.dump(payload, out_f, indent=2, ensure_ascii=False)
                os.replace(tmp_path, out_path)
                self._invalidate_cache()
                return new_sid
            except Exception as e:
                if os.path.exists(tmp_path):
                    try:
                        os.remove(tmp_path)
                    except OSError:
                        pass
                raise RuntimeError(f"Merge sessions failed: {e}") from e

    def _parse_iso_timestamp(self, ts_str: Optional[str]) -> Optional[float]:
        if not ts_str:
            return None
        try:
            dt = datetime.fromisoformat(ts_str)
            return dt.timestamp()
        except Exception:
            return None

    def _get_session_timestamp(self, file_path: str, fallback_mtime: float = 0.0) -> float:
        try:
            open_fn = gzip.open if file_path.endswith(".gz") else open
            with open_fn(file_path, "rt", encoding="utf-8") as sf:
                sdata = json.load(sf)
                ts = self._parse_iso_timestamp(sdata.get("updated_at")) or self._parse_iso_timestamp(sdata.get("created_at"))
                if ts is not None:
                    return ts
        except Exception:
            pass
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

            active_file = f"{active_session_id}.json" if active_session_id else None

            for fname in os.listdir(self.sessions_dir):
                if fname == active_file or fname.startswith("."):
                    continue
                if fname.endswith(".json") and not fname.endswith(".json.gz"):
                    base_name = fname[:-5]  # remove .json
                    if target_pattern:
                        import fnmatch
                        if not (fnmatch.fnmatch(fname.lower(), target_pattern) or fnmatch.fnmatch(base_name.lower(), target_pattern)):
                            continue

                    fp = os.path.join(self.sessions_dir, fname)
                    file_mtime = os.path.getmtime(fp)
                    mtime = self._get_session_timestamp(fp, fallback_mtime=file_mtime)
                    age_days = (now_ts - mtime) / 86400.0

                    if older_than_days is None or age_days >= older_than_days:
                        gz_path = fp + ".gz"
                        orig_sz = os.path.getsize(fp)
                        with open(fp, "rb") as f_in, gzip.open(gz_path, "wb") as f_out:
                            shutil.copyfileobj(f_in, f_out)
                        new_sz = os.path.getsize(gz_path)
                        saved_bytes += (orig_sz - new_sz)
                        os.remove(fp)
                        count += 1

            self._invalidate_cache()
            return count, saved_bytes

    def uncompress_sessions(self, target: Optional[str] = None) -> int:
        with self._thread_lock:
            if not os.path.exists(self.sessions_dir):
                return 0

            target_files = []
            if target and target.lower() != "all":
                sid = self.resolve_session(target)
                if sid:
                    gz_path = os.path.join(self.sessions_dir, f"{sid}.json.gz")
                    if os.path.exists(gz_path):
                        target_files.append(gz_path)
                else:
                    import fnmatch
                    pattern = target.lower()
                    for fname in os.listdir(self.sessions_dir):
                        if fname.endswith(".json.gz") and not fname.startswith("."):
                            base_name = fname[:-8]
                            if fnmatch.fnmatch(fname.lower(), pattern) or fnmatch.fnmatch(base_name.lower(), pattern):
                                target_files.append(os.path.join(self.sessions_dir, fname))
                    if not target_files:
                        return 0
            else:
                for fname in os.listdir(self.sessions_dir):
                    if fname.endswith(".json.gz") and not fname.startswith("."):
                        target_files.append(os.path.join(self.sessions_dir, fname))

            count = 0
            for gz_fp in target_files:
                json_fp = gz_fp[:-3]  # remove .gz
                try:
                    with gzip.open(gz_fp, "rb") as f_in, open(json_fp, "wb") as f_out:
                        shutil.copyfileobj(f_in, f_out)
                    os.remove(gz_fp)
                    count += 1
                except Exception:
                    pass

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

            active_names = set()
            if active_session_id:
                active_names.add(f"{active_session_id}.json")
                active_names.add(f"{active_session_id}.json.gz")

            entries: List[Tuple[str, float, int]] = []
            now_ts = time.time()

            for fname in os.listdir(self.sessions_dir):
                if fname in active_names or fname.startswith("."):
                    continue
                if (fname.endswith(".json") or fname.endswith(".json.gz")) and not fname.startswith("."):
                    fp = os.path.join(self.sessions_dir, fname)
                    try:
                        sz = os.path.getsize(fp)
                        mt = os.path.getmtime(fp)
                        session_ts = self._get_session_timestamp(fp, fallback_mtime=mt)
                        entries.append((fp, session_ts, sz))
                    except OSError:
                        pass

            entries.sort(key=lambda x: x[1], reverse=True)
            to_delete: set = set()

            if keep_n is not None and keep_n >= 0:
                for fp, _, _ in entries[keep_n:]:
                    to_delete.add(fp)

            if max_days is not None and max_days > 0:
                cutoff = now_ts - (max_days * 86400.0)
                for fp, mt, _ in entries:
                    if mt < cutoff:
                        to_delete.add(fp)

            if max_size_mb is not None and max_size_mb > 0:
                max_bytes = max_size_mb * 1024 * 1024
                accum = 0
                for fp, _, sz in entries:
                    if fp in to_delete:
                        continue
                    accum += sz
                    if accum > max_bytes:
                        to_delete.add(fp)

            count = 0
            for fp in to_delete:
                try:
                    os.remove(fp)
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
        oldest_file, oldest_mtime = None, float("inf")
        newest_file, newest_mtime = None, 0.0
        largest_file, largest_bytes = None, 0
        count = 0

        for fname in os.listdir(self.sessions_dir):
            if (fname.endswith(".json") or fname.endswith(".json.gz")) and not fname.startswith("."):
                fp = os.path.join(self.sessions_dir, fname)
                try:
                    sz = os.path.getsize(fp)
                    mt = os.path.getmtime(fp)
                    session_ts = self._get_session_timestamp(fp, fallback_mtime=mt)
                    count += 1
                    total_bytes += sz
                    if session_ts < oldest_mtime:
                        oldest_mtime = session_ts
                        oldest_file = fname
                    if session_ts > newest_mtime:
                        newest_mtime = session_ts
                        newest_file = fname
                    if sz > largest_bytes:
                        largest_bytes = sz
                        largest_file = fname
                except OSError:
                    pass

        return {
            "total_count": count,
            "total_bytes": total_bytes,
            "oldest": (oldest_file, oldest_mtime if oldest_file else 0),
            "newest": (newest_file, newest_mtime if newest_file else 0),
            "largest": (largest_file, largest_bytes),
        }
