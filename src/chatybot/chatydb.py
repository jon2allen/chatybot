import os
import json
from typing import List, Dict, Any

# Import the CorpusManager from the provided tinydb implementation
from .tinydb1.corpus_manager import CorpusManager

# Global variables
SEARCHBUFFER: List[Dict[str, Any]] = []  # Holds the last search results

# Internal reference to the active CorpusManager instance
_manager: CorpusManager = None

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
    global _manager
    if db_name.lower() == "null":
        _manager = None
        print("Database support deactivated.")
        return
    db_path = _ensure_db_path(db_name)
    _manager = CorpusManager(db_path)
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
            with open(db_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                # Count items in the 'items' table if it exists, else count all documents in default table
                # CorpusManager uses 'items' table
                entries = len(data.get('items', {})) if 'items' in data else len(data.get('_default', {}))
        except Exception:
            entries = "ERR"

        print(f"{db_name:<20} {filename:<25} {entries:>8} {size_kb:>10.2f}")
    print()

def search_db(query: str) -> None:
    """Search all items in the active database for *query*.

    Results are stored in the global ``SEARCHBUFFER`` and printed to the console.
    """
    global SEARCHBUFFER
    if _manager is None:
        print("No database selected. Use /setdb <dbname> first.")
        return
    # Simple case‑insensitive substring search across name and content fields
    all_items = _manager.get_all_items()
    results = []
    q = query.lower()
    for item in all_items:
        name = item.get('name', '')
        content = item.get('content', '')
        if q in name.lower() or q in content.lower():
            results.append(item)
    SEARCHBUFFER.clear()
    SEARCHBUFFER.extend(results)
    if not results:
        print("No matches found.")
        return
    print(f"Found {len(results)} matching document(s):")
    for i, doc in enumerate(results, 1):
        snippet = (doc.get('content') or "")[:100]
        print(f"{i}. id={doc.doc_id if hasattr(doc, 'doc_id') else 'N/A'} type={doc.get('type')} name={doc.get('name')} snippet='{snippet}...'")

def dblog() -> None:
    """Log the last chat completion into the active TinyDB as a ``chat`` item.

    The item stores the raw response text and a timestamp.
    """
    if _manager is None:
        print("No database selected. Use /setdb <dbname> first.")
        return
    # Retrieve CHAT_HISTORY from the running script
    import sys
    # Try to get the ChatybotApp instance first
    chatybot_mod = sys.modules.get('chatybot.chatybot_app') or sys.modules.get('chatybot.main')
    if not chatybot_mod:
        print("Unable to locate the chatybot module. Ensure this function is called after a chat has occurred.")
        return
    
    # In refactored version, get the app instance
    app_instance = getattr(chatybot_mod, 'app', None)
    if app_instance:
        CHAT_HISTORY = app_instance.chat_history
    else:
        # Fallback to old global variable for backward compatibility
        CHAT_HISTORY = getattr(chatybot_mod, 'CHAT_HISTORY', None)
    
    if CHAT_HISTORY is None:
        print("Unable to access chat history. Ensure this function is called after a chat has occurred.")
        return
    if not CHAT_HISTORY:
        print("Chat history is empty – nothing to log.")
        return
    last_response = CHAT_HISTORY[-1][1]
    # Store with a simple metadata dict containing a timestamp
    from datetime import datetime
    metadata = {"timestamp": datetime.now().isoformat()}
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
    chatybot_mod = sys.modules.get('chatybot.chatybot_app') or sys.modules.get('chatybot.main')
    if chatybot_mod:
        # In refactored version, get the app instance
        app_instance = getattr(chatybot_mod, 'app', None)
        if app_instance:
            script_vars = app_instance.buffer_manager.script_vars
        else:
            # Fallback to old global variable for backward compatibility
            script_vars = getattr(chatybot_mod, 'SCRIPT_VARS', None)
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
            print("No database selected. Additional parameters for /loadvar require an active database.")
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
                data_to_load = [item for item in all_items if s_id <= item.doc_id <= e_id]
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
                print(f"Invalid parameter: '{extra}'. Use ALL, an ID, or a range (e.g. 1-5).")
                return

    if not data_to_load:
        print("No records found to load.")
        return

    # Store a JSON representation for easy later retrieval
    script_vars[var_name] = json.dumps(data_to_load, ensure_ascii=False, indent=2)
    print(f"Variable '{var_name}' loaded into SCRIPT_VARS with {len(data_to_load)} record(s).")

def save_var(var_name: str, filename: str) -> None:
    """Save the contents of a SCRIPT_VAR to *filename*.
    """
    import sys
    # Try to get the ChatybotApp instance first
    chatybot_mod = sys.modules.get('chatybot.chatybot_app') or sys.modules.get('chatybot.main')
    if chatybot_mod:
        # In refactored version, get the app instance
        app_instance = getattr(chatybot_mod, 'app', None)
        if app_instance:
            script_vars = app_instance.buffer_manager.script_vars
        else:
            # Fallback to old global variable for backward compatibility
            script_vars = getattr(chatybot_mod, 'SCRIPT_VARS', None)
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
