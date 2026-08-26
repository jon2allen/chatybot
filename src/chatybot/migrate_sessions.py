#!/usr/bin/env python3
"""
migrate_sessions.py - Standalone utility to convert legacy monolithic JSON sessions
into directory-based JSONL sessions.

Usage:
    python -m chatybot.migrate_sessions [--sessions-dir <path>] [--backup-dir <path>] [--dry-run] [--quiet]
"""

import os
import sys
import json
import gzip
import shutil
import argparse
from typing import List, Dict, Any, Tuple, Optional


def find_legacy_sessions(sessions_dir: str) -> List[str]:
    """Find all top-level .json and .json.gz legacy session files in sessions_dir."""
    if not os.path.exists(sessions_dir):
        return []

    legacy_files = []
    for f in os.listdir(sessions_dir):
        # Ignore subdirectories, hidden files, lock files, and tmp files
        if f.startswith(".") or f.endswith(".lock") or f.endswith(".tmp"):
            continue
        fp = os.path.join(sessions_dir, f)
        if os.path.isfile(fp) and (f.endswith(".json") or f.endswith(".json.gz")):
            legacy_files.append(fp)

    return sorted(legacy_files)


def convert_single_session(
    legacy_file: str,
    sessions_dir: str,
    backup_dir: str,
    dry_run: bool = False,
) -> Tuple[bool, str, int, str]:
    """
    Convert a single legacy session file to directory-based JSONL.

    Returns:
        Tuple: (success: bool, session_id: str, turn_count: int, message: str)
    """
    open_fn = gzip.open if legacy_file.endswith(".gz") else open
    try:
        with open_fn(legacy_file, "rt", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        return False, os.path.basename(legacy_file), 0, f"JSON parse error: {e}"

    session_id = data.get("session_id")
    if not session_id:
        base = os.path.basename(legacy_file)
        session_id = base.replace(".json.gz", "").replace(".json", "")

    turns = data.pop("turns", [])
    turn_count = len(turns)

    # Build meta.json
    meta = {
        "session_id": session_id,
        "model_alias": data.get("model_alias", "default"),
        "created_at": data.get("created_at"),
        "updated_at": data.get("updated_at"),
        "first_prompt_slug": data.get("first_prompt_slug", "untitled_session"),
        "custom_name": data.get("custom_name"),
        "notes": data.get("notes"),
        "turn_count": turn_count,
        "compressed": legacy_file.endswith(".gz"),
        "format": "jsonl-v1",
    }

    if dry_run:
        return True, session_id, turn_count, "Dry-run (no changes written)"

    target_dir = os.path.join(sessions_dir, session_id)
    temp_dir = os.path.join(sessions_dir, f".{session_id}.migrate_tmp")

    try:
        os.makedirs(temp_dir, exist_ok=True)
        meta_file = os.path.join(temp_dir, "meta.json")
        with open(meta_file, "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2, ensure_ascii=False)

        turns_file = os.path.join(temp_dir, "turns.jsonl")
        with open(turns_file, "w", encoding="utf-8") as f:
            for turn in turns:
                compact_turn = {k: v for k, v in turn.items() if v is not None}
                f.write(json.dumps(compact_turn, ensure_ascii=False) + "\n")

        # If original was compressed, compress turns.jsonl too
        if legacy_file.endswith(".gz"):
            gz_turns_file = os.path.join(temp_dir, "turns.jsonl.gz")
            with open(turns_file, "rb") as f_in, gzip.open(gz_turns_file, "wb") as f_out:
                shutil.copyfileobj(f_in, f_out)
            os.remove(turns_file)

        # Preserve original timestamp if available
        file_ts = None
        upd_str = meta.get("updated_at") or meta.get("created_at")
        if upd_str:
            try:
                from datetime import datetime
                file_ts = datetime.fromisoformat(upd_str).timestamp()
            except Exception:
                pass
        if file_ts is None:
            try:
                file_ts = os.path.getmtime(legacy_file)
            except OSError:
                pass

        if file_ts:
            for p in (meta_file, turns_file, os.path.join(temp_dir, "turns.jsonl.gz")):
                if os.path.exists(p):
                    try:
                        os.utime(p, (file_ts, file_ts))
                    except OSError:
                        pass

        # Move to target dir
        if os.path.exists(target_dir):
            shutil.rmtree(target_dir, ignore_errors=True)
        os.replace(temp_dir, target_dir)

        if file_ts:
            try:
                os.utime(target_dir, (file_ts, file_ts))
            except OSError:
                pass

        # Backup legacy file
        os.makedirs(backup_dir, exist_ok=True)
        dest_backup = os.path.join(backup_dir, os.path.basename(legacy_file))
        shutil.move(legacy_file, dest_backup)

        return True, session_id, turn_count, "Successfully migrated"
    except Exception as e:
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)
        return False, session_id, turn_count, f"Migration failed: {e}"


def run_migration(
    sessions_dir: str,
    backup_dir: Optional[str] = None,
    dry_run: bool = False,
    quiet: bool = False,
) -> Tuple[int, int]:
    """
    Run session migration on all discovered legacy session files.

    Returns:
        Tuple: (migrated_count, error_count)
    """
    sessions_dir = os.path.expanduser(sessions_dir)
    backup_dir = (
        os.path.expanduser(backup_dir)
        if backup_dir
        else os.path.join(sessions_dir, ".backup_v1_monolithic")
    )

    legacy_files = find_legacy_sessions(sessions_dir)
    total = len(legacy_files)

    if total == 0:
        if not quiet:
            print(f"[Session Migration] No legacy session files found in '{sessions_dir}'.")
        return 0, 0

    if not quiet:
        print("=" * 68)
        print(" Chatybot Session Migration Utility: Monolithic JSON -> JSONL")
        print("=" * 68)
        print(f" Sessions directory : {sessions_dir}")
        print(f" Backup directory   : {backup_dir}")
        print(f" Mode               : {'DRY RUN (preview only)' if dry_run else 'LIVE MIGRATION'}")
        print(f" Found {total} legacy session(s) to convert.")
        print("-" * 68)
        print(" Starting migration...")

    migrated_count = 0
    error_count = 0

    for idx, fpath in enumerate(legacy_files, 1):
        success, sid, tcount, msg = convert_single_session(
            fpath, sessions_dir, backup_dir, dry_run=dry_run
        )
        prefix = "└─" if idx == total else "├─"
        if success:
            migrated_count += 1
            if not quiet:
                print(f"  {prefix} [{idx:>{len(str(total))}}/{total}] Migrated '{sid}' ({tcount} turns)")
        else:
            error_count += 1
            if not quiet:
                print(f"  {prefix} [{idx:>{len(str(total))}}/{total}] ERROR '{sid}': {msg}")

    if not quiet:
        print("=" * 68)
        status = "DRY RUN COMPLETE" if dry_run else "MIGRATION COMPLETE"
        print(f" {status}: {migrated_count} session(s) successfully converted, {error_count} error(s).")
        if not dry_run and migrated_count > 0:
            print(f" Original files archived to: {backup_dir}")
        print("=" * 68)

    return migrated_count, error_count


def main():
    parser = argparse.ArgumentParser(
        description="Migrate Chatybot sessions from monolithic JSON to JSONL directory format."
    )
    parser.add_argument(
        "--sessions-dir",
        default="~/.local/share/chatybot/sessions",
        help="Path to sessions directory (default: ~/.local/share/chatybot/sessions)",
    )
    parser.add_argument(
        "--backup-dir",
        default=None,
        help="Path to archive original files (default: <sessions-dir>/.backup_v1_monolithic)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview migration without modifying or moving any files",
    )
    parser.add_argument(
        "--quiet",
        "-q",
        action="store_true",
        help="Suppress banner and non-error output",
    )

    args = parser.parse_args()
    migrated, errors = run_migration(
        sessions_dir=args.sessions_dir,
        backup_dir=args.backup_dir,
        dry_run=args.dry_run,
        quiet=args.quiet,
    )
    sys.exit(0 if errors == 0 else 1)


if __name__ == "__main__":
    main()
