"""
TinyDB database tools for LLM tool calling.
Allows the LLM to search databases and list available databases.
Enabled via /tool enable db_search, db_list or tools_config.toml.
"""

import json
import os
from typing import Any

from .. import chatydb


def db_search(
    query: str = "*",
    db_name: str | None = None,
    limit: int = 20,
    full_content: bool = False,
    app: Any = None,
) -> str:
    """
    Search a TinyDB database for items matching a query string.
    Searches across name, content, and metadata fields (case-insensitive substring).

    Args:
        query: Search term. Use '*' or empty string to list all items (default '*').
        db_name: Database name to search. If None, uses active database or CHATYBOT_ACTIVE_DB.
        limit: Maximum number of results to return (default 20).
        full_content: If True, return the complete untruncated content instead of a 500-character preview.
        app: ChatybotApp instance passed when called within application context.

    Returns:
        JSON string with matching items.
    """
    target_db = db_name or os.environ.get("CHATYBOT_ACTIVE_DB")
    if target_db:
        chatydb.set_db(target_db)

    if chatydb._manager is None:
        return json.dumps({
            "error": "No database selected. Use the db_name parameter or /setdb first."
        }, ensure_ascii=False)

    all_items = chatydb._manager.get_all_items()

    effective_query = (query or "").strip()
    if not effective_query or effective_query in ("*", "all"):
        results = list(all_items)
    else:
        q = query.lower()
        results = []
        for item in all_items:
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
            elif metadata and q in str(metadata).lower():
                in_metadata = True

            if q in name.lower() or q in content.lower() or in_metadata:
                results.append(item)

    total_matches = len(results)
    results = results[:limit]

    output = []
    for item in results:
        doc_id = getattr(item, "doc_id", None)
        content = str(item.get("content") or "")
        record = {
            "id": doc_id,
            "type": item.get("type"),
            "name": item.get("name"),
            "content_length": len(content),
            "metadata": item.get("metadata", {}),
        }
        if full_content:
            record["content"] = content
        else:
            record["content_preview"] = content[:500]
        output.append(record)

    return json.dumps({
        "query": query,
        "database": db_name or "active",
        "total_matches": total_matches,
        "returned": len(results),
        "results": output,
    }, ensure_ascii=False, indent=2)


def db_get(
    item_id: int,
    db_name: str | None = None,
    app: Any = None,
) -> str:
    """
    Retrieve a single complete item from a TinyDB database by its integer ID.

    Args:
        item_id: The integer ID (doc_id) of the item to retrieve.
        db_name: Database name to look in. If None, uses the currently active database.
        app: ChatybotApp instance passed when called within application context.

    Returns:
        JSON string with the complete item details or an error message.
    """
    target_db = db_name or os.environ.get("CHATYBOT_ACTIVE_DB")
    if target_db:
        chatydb.set_db(target_db)

    if chatydb._manager is None:
        return json.dumps({
            "error": "No database selected. Use the db_name parameter or /setdb first."
        }, ensure_ascii=False)

    try:
        doc_id = int(item_id)
    except (ValueError, TypeError):
        return json.dumps({
            "error": f"Invalid item_id '{item_id}'. Must be an integer."
        }, ensure_ascii=False)

    item = chatydb._manager.get_item(doc_id)
    if not item:
        return json.dumps({
            "error": f"Item with ID {doc_id} not found in database '{db_name or 'active'}'."
        }, ensure_ascii=False)

    content = str(item.get("content") or "")
    output = {
        "id": getattr(item, "doc_id", doc_id),
        "type": item.get("type"),
        "name": item.get("name"),
        "content": content,
        "content_length": len(content),
        "metadata": item.get("metadata", {}),
    }

    return json.dumps(output, ensure_ascii=False, indent=2)


def db_list(app: Any = None) -> str:
    """
    List all available TinyDB databases with entry counts and file sizes.

    Args:
        app: ChatybotApp instance passed when called within application context.

    Returns:
        JSON string with database list.
    """
    base_dir = os.path.expanduser("~/.local/share/chatybot")
    db_dir = os.path.join(base_dir, "db")

    if not os.path.exists(db_dir):
        return json.dumps({
            "databases": [],
            "message": "No database directory found."
        }, ensure_ascii=False)

    databases = []
    for filename in sorted(os.listdir(db_dir)):
        if not filename.endswith(".json"):
            continue
        db_path = os.path.join(db_dir, filename)
        db_name = os.path.splitext(filename)[0]
        size_kb = round(os.path.getsize(db_path) / 1024, 2)

        try:
            with open(db_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            entries = (
                len(data.get("items", {}))
                if "items" in data
                else len(data.get("_default", {}))
            )
        except Exception:
            entries = -1

        databases.append({
            "name": db_name,
            "entries": entries,
            "size_kb": size_kb,
        })

    return json.dumps({
        "databases": databases
    }, ensure_ascii=False, indent=2)
