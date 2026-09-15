"""
TinyDB database tools for LLM tool calling.
Allows the LLM to search databases and list available databases.
Enabled via /tool enable db_search, db_list or tools_config.toml.
"""

import json
import os
from typing import Any, Optional


def db_search(
    query: str,
    db_name: str | None = None,
    limit: int = 20,
    app: Any = None,
) -> str:
    """
    Search a TinyDB database for items matching a query string.
    Searches across name, content, and metadata fields (case-insensitive substring).

    Args:
        query: Search term. Use '*' or empty string to list all items.
        db_name: Database name to search. If None, uses the currently active database.
        limit: Maximum number of results to return (default 20).
        app: ChatybotApp instance passed when called within application context.

    Returns:
        JSON string with matching items.
    """
    from chatybot import chatydb

    if db_name:
        chatydb.set_db(db_name)

    if chatydb._manager is None:
        return json.dumps({
            "error": "No database selected. Use the db_name parameter or /setdb first."
        }, ensure_ascii=False)

    all_items = chatydb._manager.get_all_items()

    if not query.strip() or query.strip() in ("*", "all"):
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
        output.append({
            "id": doc_id,
            "type": item.get("type"),
            "name": item.get("name"),
            "content_preview": content[:500],
            "content_length": len(content),
            "metadata": item.get("metadata", {}),
        })

    return json.dumps({
        "query": query,
        "database": db_name or "active",
        "total_matches": total_matches,
        "returned": len(results),
        "results": output,
    }, ensure_ascii=False, indent=2)


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
