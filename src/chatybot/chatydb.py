import json
import os
import re
import shutil
from datetime import datetime
from typing import Any

# Import the CorpusManager from the provided tinydb implementation
from .tinydb1.corpus_manager import CorpusManager

# Global variables
SEARCHBUFFER: list[dict[str, Any]] = []  # Holds the last search results

# Maximum number of rolling snapshot backups to retain per database
MAX_DB_BACKUPS = 5

# Track databases that have already been backed up during this process/session
_session_backed_up_dbs: set[str] = set()

# Internal reference to the active CorpusManager instance
_manager: CorpusManager | None = None
# Storage for the current database path and name
_db_path: str | None = None
_active_db_name: str | None = None

# A database name must be a single safe path component: no slashes, no "..",
# no path separators, no empty/whitespace. This prevents path traversal and
# weird filenames like "db/.json".
_DB_NAME_RE = re.compile(r"^[A-Za-z0-9_.-]+$")


def get_active_db() -> str | None:
    """Return the currently active database name, if any."""
    global _active_db_name
    return _active_db_name or os.environ.get("CHATYBOT_ACTIVE_DB")


def _ensure_db_path(db_name: str) -> str:
    """Ensure the database directory exists and return the full path to the TinyDB file."""
    base_dir = os.path.expanduser("~/.local/share/chatybot")
    db_dir = os.path.join(base_dir, "db")
    os.makedirs(db_dir, exist_ok=True)
    # TinyDB stores data in a JSON file; we use the provided name with .json extension
    return os.path.join(db_dir, f"{db_name}.json")


def _backup_db(db_path: str, db_name: str, max_backups: int = MAX_DB_BACKUPS) -> tuple[str, int, int] | None:
    """Create a rolling snapshot of an existing non-empty database file.

    Saves backups into a hidden subdirectory:
        <db_dir>/.backups/<db_name>/<db_name>.<timestamp>.bak.json

    Maintains up to `max_backups` recent snapshots, pruning the oldest ones.

    Returns:
        tuple (backup_path, remaining_count, max_backups) on success, or None if skipped/failed.
    """
    if not os.path.exists(db_path) or os.path.getsize(db_path) == 0:
        return None

    try:
        db_dir = os.path.dirname(db_path)
        backup_dir = os.path.join(db_dir, ".backups", db_name)
        os.makedirs(backup_dir, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_filename = f"{db_name}.{timestamp}.bak.json"
        backup_path = os.path.join(backup_dir, backup_filename)

        # If a backup with the exact same timestamp already exists, append counter
        counter = 1
        while os.path.exists(backup_path):
            backup_filename = f"{db_name}.{timestamp}_{counter}.bak.json"
            backup_path = os.path.join(backup_dir, backup_filename)
            counter += 1

        shutil.copy2(db_path, backup_path)

        # Rotate: keep at most max_backups files, deleting oldest by mtime
        existing_backups = [
            os.path.join(backup_dir, f)
            for f in os.listdir(backup_dir)
            if f.startswith(f"{db_name}.") and f.endswith(".bak.json")
        ]
        # Sort backups: sort primarily by ctime (creation/change time) and filename
        # Note: shutil.copy2 preserves source mtime, so sorting by mtime can cause all
        # copies from the same source file to share the exact same timestamp.
        existing_backups.sort(key=lambda p: (os.path.getctime(p), os.path.basename(p)))

        while len(existing_backups) > max_backups:
            oldest = existing_backups.pop(0)
            try:
                os.unlink(oldest)
            except OSError:
                pass

        return backup_path, len(existing_backups), max_backups
    except Exception as e:
        # Non-fatal: backup failure should warn but never prevent opening the DB
        print(f"[backup warning] Failed to create snapshot for '{db_name}': {e}")
        return None


def set_db(db_name: str) -> None:
    """Create (if needed) and activate a TinyDB database with the given name.

    The database file is placed under the project's ``db`` directory.
    If db_name is 'Null' (case-insensitive), deactivate database support.
    """
    global _manager, _db_path, _active_db_name, _session_backed_up_dbs
    if db_name.lower() == "null":
        # Close the previous manager before deactivating so its file handle
        # is released.
        if _manager is not None:
            try:
                _manager.close()
            except Exception:
                pass
        _manager = None
        _db_path = None
        _active_db_name = None
        os.environ.pop("CHATYBOT_ACTIVE_DB", None)
        print("Database support deactivated.")
        return

    name = db_name.strip()
    if not name or not _DB_NAME_RE.match(name):
        print(
            f"Invalid database name '{db_name}'. Use letters, digits, '.', '_', or '-' "
            "(no slashes, spaces, or '..')."
        )
        return

    # If this database is already open and active in the current process, reuse it
    # without re-running backups or reloading the manager.
    if _active_db_name == name and _manager is not None:
        return

    db_path = _ensure_db_path(name)

    # Automatic snapshot backup on initial open in this session
    backup_info = None
    if name not in _session_backed_up_dbs:
        backup_info = _backup_db(db_path, name)
        _session_backed_up_dbs.add(name)

    # Close the previous manager before opening a new one so its file handle
    # is released rather than leaked across repeated /setdb calls.
    if _manager is not None:
        try:
            _manager.close()
        except Exception:
            pass
    _manager = CorpusManager(db_path)
    _db_path = db_path
    _active_db_name = name
    os.environ["CHATYBOT_ACTIVE_DB"] = name
    print(f"Database set to '{db_path}'.")
    if backup_info:
        backup_path, count, max_count = backup_info
        rel_backup = os.path.relpath(backup_path, os.path.dirname(db_path))
        print(f"[backup] Snapshot saved: {rel_backup} ({count}/{max_count})")


def list_dbs() -> None:
    """List all TinyDB JSON files in the 'db' directory with details."""
    base_dir = os.path.expanduser("~/.local/share/chatybot")
    db_dir = os.path.join(base_dir, "db")
    if not os.path.exists(db_dir):
        print(f"No database directory found at '{db_dir}'.")
        return

    json_files = [f for f in os.listdir(db_dir) if f.endswith(".json")]
    if not json_files:
        print("No database files found in 'db/'.")
        return

    print(f"\n{'DB Name':<24} {'Filename':<30} {'Entries':>10} {'Size (KB)':>13}")
    print("-" * 80)

    for filename in sorted(json_files):
        db_path = os.path.join(db_dir, filename)
        db_name = os.path.splitext(filename)[0]
        size_kb = os.path.getsize(db_path) / 1024

        try:
            with open(db_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                # Count items in the 'items' table if it exists, else count all documents in default table
                # CorpusManager uses 'items' table
                entries = (
                    len(data.get("items", {}))
                    if "items" in data
                    else len(data.get("_default", {}))
                )
        except Exception:
            entries = "ERR"

        print(f"{db_name:<24} {filename:<30} {entries:>10} {size_kb:>13.2f}")
    print()


def search_db(query: str) -> None:
    """Search all items in the active database for *query*.

    Results are stored in the global ``SEARCHBUFFER`` and printed to the console.

    An empty query, ``*``, or ``all`` is an explicit "list all" shorthand.
    """
    global SEARCHBUFFER
    if _manager is None:
        print("No database selected. Use /setdb <dbname> first.")
        return

    all_items = _manager.get_all_items()

    # Empty/whitespace, "*", or "all" is an explicit "list all" shorthand
    # rather than an emergent property of substring matching.
    if not query.strip() or query.strip() in ("*", "all"):
        results = list(all_items)
        SEARCHBUFFER.clear()
        SEARCHBUFFER.extend(results)
        if not results:
            print("No documents in database.")
            return
        print(f"Empty query — showing all {len(results)} document(s):")
        for i, doc in enumerate(results, 1):
            snippet = (doc.get("content") or "")[:100]
            print(
                f"{i}. id={doc.doc_id if hasattr(doc, 'doc_id') else 'N/A'} "
                f"type={doc.get('type')} name={doc.get('name')} snippet='{snippet}...'"
            )
        return

    # Simple case-insensitive substring search across name, content, and metadata fields
    q = query.lower()
    results = []
    for item in all_items:
        # Coerce to str so None values (possible via direct TinyDB writes) don't
        # crash on .lower(); the .get(..., "") default only fires when the key
        # is absent, not when it's present with value None.
        name = str(item.get("name") or "")
        content = str(item.get("content") or "")
        metadata = item.get("metadata", {})

        in_metadata = False
        if isinstance(metadata, dict):
            for k, val in metadata.items():
                if q in str(k).lower() or q in str(val).lower():
                    in_metadata = True
                    break
        elif isinstance(metadata, list):
            for val in metadata:
                if q in str(val).lower():
                    in_metadata = True
                    break
        elif metadata:
            if q in str(metadata).lower():
                in_metadata = True

        if q in name.lower() or q in content.lower() or in_metadata:
            results.append(item)
    SEARCHBUFFER.clear()
    SEARCHBUFFER.extend(results)
    if not results:
        print("No matches found.")
        return
    print(f"Found {len(results)} matching document(s):")
    for i, doc in enumerate(results, 1):
        snippet = (doc.get("content") or "")[:100]
        print(
            f"{i}. id={doc.doc_id if hasattr(doc, 'doc_id') else 'N/A'} type={doc.get('type')} name={doc.get('name')} snippet='{snippet}...'"
        )


def dblog(include_thinking: bool = False) -> None:
    """Log the last chat completion into the active TinyDB as a ``chat`` item.

    The item stores the raw response text and a timestamp.

    - type: "chat"
    - name: "last_chat"
    - content: The AI response text (clean final answer with thinking tags stripped,
      or with thinking tags intact when include_thinking=True)
      - metadata: A dictionary containing:
       - timestamp: When the chat occurred
       - model_alias: The short alias used (e.g., "mistral_1")
       - model_name: The full model name (e.g., "mistral-large-2512")
       - prompt: The user prompt for this turn
       - thinking_content: Extracted reasoning text, or None when not requested
         (only present when include_thinking=True)
       - thinking_tokens: Reasoning token count from the API, or 0 when unknown
       - reasoning_effort: The active reasoning effort setting, or None
    """
    if _manager is None:
        print("No database selected. Use /setdb <dbname> first.")
        return
    # Retrieve CHAT_HISTORY from the running script
    import sys

    # Try to get the ChatybotApp instance first
    chatybot_mod = sys.modules.get("chatybot.chatybot_app") or sys.modules.get(
        "chatybot.main"
    )
    if not chatybot_mod:
        print(
            "Unable to locate the chatybot module. Ensure this function is called after a chat has occurred."
        )
        return

    # In refactored version, get the app instance
    app_instance = getattr(chatybot_mod, "app", None)
    if app_instance:
        CHAT_HISTORY = app_instance.chat_history
    else:
        # Fallback to old global variable for backward compatibility
        CHAT_HISTORY = getattr(chatybot_mod, "CHAT_HISTORY", None)

    if CHAT_HISTORY is None:
        print(
            "Unable to access chat history. Ensure this function is called after a chat has occurred."
        )
        return
    if not CHAT_HISTORY:
        if app_instance and getattr(app_instance, "last_response", None):
            last_response = app_instance.last_response
            last_prompt = getattr(app_instance, "last_prompt", "User Prompt") or "User Prompt"
        else:
            print("Chat history is empty – nothing to log.")
            return
    else:
        last_response = CHAT_HISTORY[-1][1]
        last_prompt = CHAT_HISTORY[-1][0]
    # Store with a simple metadata dict containing a timestamp
    metadata = {"timestamp": datetime.now().isoformat()}

    # Gather model alias/name when the app instance is available. These are
    # secondary metadata; a missing or invalid alias must never abort the log.
    if app_instance:
        metadata["model_alias"] = getattr(
            app_instance.config_manager, "active_model_alias", "unknown"
        )
        try:
            model_config = app_instance.config_manager.get_model_config(
                app_instance.config_manager.active_model_alias
            )
            metadata["model_name"] = (
                model_config["name"] if model_config else "unknown"
            )
        except Exception:
            metadata["model_name"] = "unknown"
    else:
        metadata["model_alias"] = "unknown"
        metadata["model_name"] = "unknown"

    metadata["prompt"] = last_prompt

    # Thinking/reasoning awareness. The thinking text is embedded in
    # the stored response as <think>...</think> tags (standardized at
    # completion time).
    # When include_thinking=True:
    #   - Keep thinking tags intact in item content.
    #   - Extract and populate metadata["thinking_content"] and token counts.
    # When include_thinking=False (default):
    #   - Strip <think>...</think> tags from item content so only the final answer is logged.
    #   - Set metadata thinking fields to None / 0.
    if include_thinking:
        thinking_content = None
        if app_instance is not None:
            extractor = getattr(app_instance, "_extract_thinking_tokens", None)
            if callable(extractor):
                thinking_content, _ = extractor(last_response)
        metadata["thinking_content"] = thinking_content
        metadata["thinking_tokens"] = getattr(app_instance, "last_reasoning_tokens", 0) if app_instance else 0
        metadata["reasoning_effort"] = getattr(app_instance, "reasoning_effort", None) if app_instance else None
        logged_content = last_response
    else:
        # Strip thinking tags from content for clean answer logging
        if app_instance is not None:
            extractor = getattr(app_instance, "_extract_thinking_tokens", None)
            if callable(extractor):
                _, clean_text = extractor(last_response)
                logged_content = clean_text
            else:
                logged_content = last_response
        else:
            # Fallback regex strip if app_instance is unavailable
            import re
            logged_content = re.sub(
                r"<(?:think|thought|thinking)>.*?</(?:think|thought|thinking)>\s*",
                "",
                last_response,
                flags=re.DOTALL | re.IGNORECASE,
            ).strip()

        metadata["thinking_content"] = None
        metadata["thinking_tokens"] = 0
        metadata["reasoning_effort"] = getattr(app_instance, "reasoning_effort", None) if app_instance else None

    _manager.add_item("chat", "last_chat", logged_content, metadata)

    if include_thinking and metadata["thinking_content"]:
        print("Last chat completion logged to the database (with thinking).")
    else:
        print("Last chat completion logged to the database.")


def load_var(var_name: str, extra: str = None) -> None:
    """Load content into a SCRIPT_VAR in chatybot.

    If 'extra' is None, use current ``SEARCHBUFFER``.
    If 'extra' is 'ALL', use all items from database.
    If 'extra' is an ID (e.g. '1'), use that document.
    If 'extra' is a range (e.g. '1-5'), use documents in that ID range.
    """
    import sys

    # Try to get the ChatybotApp instance first
    chatybot_mod = sys.modules.get("chatybot.chatybot_app") or sys.modules.get(
        "chatybot.main"
    )
    if chatybot_mod:
        # In refactored version, get the app instance
        app_instance = getattr(chatybot_mod, "app", None)
        if app_instance:
            script_vars = app_instance.buffer_manager.script_vars
        else:
            # Fallback to old global variable for backward compatibility
            script_vars = getattr(chatybot_mod, "SCRIPT_VARS", None)
    else:
        script_vars = None

    if script_vars is None:
        print("Error: Could not access SCRIPT_VARS in chatybot.")
        return

    data_to_load = []
    if extra is None:
        if not SEARCHBUFFER:
            print("SEARCHBUFFER is empty – nothing to load.")
            return
        data_to_load = SEARCHBUFFER
    else:
        if _manager is None:
            print(
                "No database selected. Additional parameters for /loadvar require an active database."
            )
            return

        arg = extra.strip().upper()
        if arg == "ALL":
            data_to_load = _manager.get_all_items()
        elif "-" in arg:
            try:
                start_str, end_str = arg.split("-", 1)
                s_id = int(start_str.strip())
                e_id = int(end_str.strip())
                all_items = _manager.get_all_items()
                # TinyDB Document objects have a doc_id property
                data_to_load = [
                    item for item in all_items if s_id <= item.doc_id <= e_id
                ]
            except ValueError:
                print(f"Invalid range format: '{extra}'. Use e.g. 1-5")
                return
        else:
            try:
                doc_id = int(arg)
                item = _manager.items.get(doc_id=doc_id)
                if item:
                    data_to_load = [item]
                else:
                    print(f"Document with ID {doc_id} not found.")
                    return
            except ValueError:
                print(
                    f"Invalid parameter: '{extra}'. Use ALL, an ID, or a range (e.g. 1-5)."
                )
                return

    if not data_to_load:
        print("No records found to load.")
        return

    # Store a JSON representation for easy later retrieval
    script_vars[var_name] = json.dumps(data_to_load, ensure_ascii=False, indent=2)
    print(
        f"Variable '{var_name}' loaded into SCRIPT_VARS with {len(data_to_load)} record(s)."
    )


def save_var(var_name: str, filename: str) -> None:
    """Save the contents of a SCRIPT_VAR to *filename`."""
    import sys

    # Try to get the ChatybotApp instance first
    chatybot_mod = sys.modules.get("chatybot.chatybot_app") or sys.modules.get(
        "chatybot.main"
    )
    if chatybot_mod:
        # In refactored version, get the app instance
        app_instance = getattr(chatybot_mod, "app", None)
        if app_instance:
            script_vars = app_instance.buffer_manager.script_vars
        else:
            # Fallback to old global variable for backward compatibility
            script_vars = getattr(chatybot_mod, "SCRIPT_VARS", None)
    else:
        script_vars = None

    if script_vars is None:
        print("Error: Could not access SCRIPT_VARS in chatybot.")
        return

    if var_name not in script_vars:
        print(f"Variable '{var_name}' not found in SCRIPT_VARS.")
        return

    try:
        os.makedirs(os.path.dirname(filename) or ".", exist_ok=True)
        with open(filename, "w", encoding="utf-8") as f:
            f.write(str(script_vars[var_name]))
        print(f"Variable '{var_name}' saved to '{filename}'.")
    except Exception as e:
        print(f"Error saving variable to file: {e}")


def dbprint(target_file: str = None) -> None:
    """Print the entire database contents in a formatted report.

    Args:
        target_file: Optional filename to save the report to. If None, prints to screen.
    """
    if _manager is None:
        print("No database selected. Use /setdb <dbname> first.")
        return

    # Helper function to duplicate line feeds (add extra blank lines)
    def duplicate_linefeeds(text):
        if not text:
            return ""
        # Replace each newline with two newlines to create extra spacing
        return text.replace("\n", "\n\n")

    # Generate the report content
    report_lines = []
    report_lines.append("=" * 80)
    report_lines.append("DATABASE REPORT")
    report_lines.append("=" * 80)
    if _db_path:
        report_lines.append(f"Database path: {_db_path}")
    report_lines.append("")

    # Print items
    items = _manager.get_all_items()
    report_lines.append(f"ITEMS ({len(items)} total):")
    report_lines.append("-" * 80)
    if items:
        for i, item in enumerate(items, 1):
            # Get doc_id safely
            doc_id = getattr(item, "doc_id", "N/A")
            report_lines.append(f"[{i}] ID: {doc_id}")

            # Move metadata to top
            metadata = item.get("metadata", {})
            if metadata:
                report_lines.append("    Metadata:")
                for key, value in metadata.items():
                    # Skip the verbose thinking_content here; it gets its own
                    # styled section below when present.
                    if key == "thinking_content":
                        continue
                    report_lines.append(f"      {key}: {value}")
            else:
                report_lines.append("    Metadata: [None]")

            report_lines.append(f"    Type: {item.get('type', 'N/A')}")
            report_lines.append(f"    Name: {item.get('name', 'N/A')}")

            # Styled thinking section (only when thinking was logged)
            thinking = metadata.get("thinking_content") if metadata else None
            if thinking:
                report_lines.append("    -- Thinking --")
                formatted_thinking = duplicate_linefeeds(thinking)
                for part in formatted_thinking.split("\n\n"):
                    if part.strip():
                        report_lines.append(f"    {part}")
                tok = metadata.get("thinking_tokens", 0) if metadata else 0
                if tok:
                    report_lines.append(f"    [thinking tokens: {tok}]")
                report_lines.append("    -- End Thinking --")

            content = item.get("content", "")
            if content:
                # Duplicate line feeds in content for better readability
                formatted_content = duplicate_linefeeds(content)
                # Split by double newlines and indent each part
                content_parts = formatted_content.split("\n\n")
                for part in content_parts:
                    if part.strip():  # Only add non-empty parts
                        report_lines.append(f"    {part}")
            else:
                report_lines.append("    Content: [Empty]")
            report_lines.append("")
    else:
        report_lines.append("No items found.")

    report_lines.append("=" * 80)
    report_lines.append("END OF REPORT")
    report_lines.append("=" * 80)

    # Output the report
    report_content = "\n".join(report_lines)
    if target_file:
        try:
            import os

            os.makedirs(os.path.dirname(target_file) or ".", exist_ok=True)
            with open(target_file, "w", encoding="utf-8") as f:
                f.write(report_content)
            print(f"Database report saved to '{target_file}'.")
        except Exception as e:
            print(f"Error saving database report to file: {e}")
    else:
        print(report_content)
    print("END OF REPORT")
    print("=" * 80)
