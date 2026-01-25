import os
import json
from typing import List, Dict, Any

# Import the CorpusManager from the provided tinydb implementation
from tinydb1.corpus_manager import CorpusManager

# Global variables
SEARCHBUFFER: List[Dict[str, Any]] = []  # Holds the last search results

# Internal reference to the active CorpusManager instance
_manager: CorpusManager = None

def _ensure_db_path(db_name: str) -> str:
    """Ensure the database directory exists and return the full path to the TinyDB file."""
    db_dir = os.path.join(os.getcwd(), "db")
    os.makedirs(db_dir, exist_ok=True)
    # TinyDB stores data in a JSON file; we use the provided name with .json extension
    return os.path.join(db_dir, f"{db_name}.json")

def set_db(db_name: str) -> None:
    """Create (if needed) and activate a TinyDB database with the given name.

    The database file is placed under the project's ``db`` directory.
    """
    global _manager
    db_path = _ensure_db_path(db_name)
    _manager = CorpusManager(db_path)
    print(f"Database set to '{db_path}'.")

def list_dbs() -> None:
    """List all TinyDB JSON files in the 'db' directory with details."""
    db_dir = os.path.join(os.getcwd(), "db")
    if not os.path.exists(db_dir):
        print("No database directory found at 'db/'.")
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
    SEARCHBUFFER = results
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
    # Retrieve CHAT_HISTORY from the running script (could be __main__ when executed directly)
    import sys
    chatybot_mod = sys.modules.get('chatybot') or sys.modules.get('__main__')
    if not chatybot_mod:
        print("Unable to locate the chatybot module. Ensure this function is called after a chat has occurred.")
        return
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
    

def load_var(var_name: str) -> None:
    """Load the current ``SEARCHBUFFER`` content into a SCRIPT_VAR in chatybot.
    """
    import sys
    main_mod = sys.modules.get('__main__')
    script_vars = getattr(main_mod, 'SCRIPT_VARS', None)
    if script_vars is None:
        print("Error: Could not access SCRIPT_VARS in chatybot.")
        return

    if not SEARCHBUFFER:
        print("SEARCHBUFFER is empty – nothing to load.")
        return

    # Store a JSON representation for easy later retrieval
    script_vars[var_name] = json.dumps(SEARCHBUFFER, ensure_ascii=False, indent=2)
    print(f"Variable '{var_name}' loaded into SCRIPT_VARS with {len(SEARCHBUFFER)} record(s).")

def save_var(var_name: str, filename: str) -> None:
    """Save the contents of a SCRIPT_VAR to *filename*.
    """
    import sys
    main_mod = sys.modules.get('__main__')
    script_vars = getattr(main_mod, 'SCRIPT_VARS', None)
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
