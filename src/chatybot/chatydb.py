import os
import re
import json
from typing import List, Dict, Any, Optional
from datetime import datetime

# Import the CorpusManager from the provided tinydb implementation
from .tinydb1.corpus_manager import CorpusManager

# Global variables
SEARCHBUFFER: List[Dict[str, Any]] = []  # Holds the last search results

# Internal reference to the active CorpusManager instance
_manager: Optional[CorpusManager] = None
# Storage for the current database path
_db_path: Optional[str] = None

# A database name must be a single safe path component: no slashes, no "..",
# no path separators, no empty/whitespace. This prevents path traversal and
# weird filenames like "db/.json".
_DB_NAME_RE = re.compile(r"^[A-Za-z0-9_.-]+$")


def _ensure_db_path(db_name: str) -> str:
    """Ensure the database directory exists and return the full path to the TinyDB file."""
    base_dir = os.path.expanduser("~/.local/share/chatybot")
    db_dir = os.path.join(base_dir, "db")
    os.makedirs(db_dir, exist_ok=True)
    # TinyDB stores data in a JSON file; we use the provided name with .json extension
    return os.path.join(db_dir, f"{db_name}.json")


def set_db(db_name: str) -> None:
    """Create (if needed) and activate a TinyDB database with the given name.

    The database file is placed under the project's ``db`` directory.
    If db_name is 'Null' (case-insensitive), deactivate database support.
    """
    global _manager, _db_path
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
        print("Database support deactivated.")
        return

    name = db_name.strip()
    if not name or not _DB_NAME_RE.match(name):
        print(
            f"Invalid database name '{db_name}'. Use letters, digits, '.', '_', or '-' "
            "(no slashes, spaces, or '..')."
        )
        return

    db_path = _ensure_db_path(name)
    # Close the previous manager before opening a new one so its file handle
    # is released rather than leaked across repeated /setdb calls.
    if _manager is not None:
        try:
            _manager.close()
        except Exception:
            pass
    _manager = CorpusManager(db_path)
    _db_path = db_path
    print(f"Database set to '{db_path}'.")


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

    print(f"\n{'DB Name':<20} {'Filename':<25} {'Entries':>8} {'Size (KB)':>10}")
    print("-" * 65)

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

        print(f"{db_name:<20} {filename:<25} {entries:>8} {size_kb:>10.2f}")
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


def dblog() -> None:
    """Log the last chat completion into the active TinyDB as a ``chat`` item.

    The item stores the raw response text and a timestamp.

    - type: "chat"
    - name: "last_chat"
    - content: The AI response text
      - metadata: A dictionary containing:
       - timestamp: When the chat occurred
       - model_alias: The short alias used (e.g., "mistral_1")
       - model_name: The full model name (e.g., "mistral-large-2512")
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
        print("Chat history is empty – nothing to log.")
        return
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
    _manager.add_item("chat", "last_chat", last_response, metadata)

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
                report_lines.append(f"    Metadata:")
                for key, value in metadata.items():
                    report_lines.append(f"      {key}: {value}")
            else:
                report_lines.append(f"    Metadata: [None]")

            report_lines.append(f"    Type: {item.get('type', 'N/A')}")
            report_lines.append(f"    Name: {item.get('name', 'N/A')}")
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
                report_lines.append(f"    Content: [Empty]")
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
