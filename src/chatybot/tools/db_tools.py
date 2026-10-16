"""
TinyDB database tools for LLM tool calling.
Allows the LLM to search databases and list available databases.
Enabled via /tool enable db_search, db_list or tools_config.toml.
"""

import json
import os
from collections.abc import Iterator
from contextlib import contextmanager, suppress
from typing import Any

from .. import chatydb
from ..tinydb1.corpus_manager import CorpusManager


@contextmanager
def _scoped_corpus_manager(
    db_name: str | None = None,
) -> Iterator[tuple[CorpusManager | None, str | None, str]]:
    """
    Context manager that yields a (CorpusManager | None, error_message | None, resolved_db_name) tuple.

    If db_name is provided, opens a dedicated CorpusManager for that database
    without mutating the global session active database (chatydb._manager / CHATYBOT_ACTIVE_DB).
    If db_name is None, uses the active session database.
    """
    if db_name:
        name = db_name.strip()
        if not name or not chatydb._DB_NAME_RE.match(name):
            yield None, f"Invalid database name '{db_name}'. Use letters, digits, '.', '_', or '-'.", db_name
            return

        # If it's already active in the current process, reuse it safely without closing
        if chatydb._active_db_name == name and chatydb._manager is not None:
            yield chatydb._manager, None, name
            return

        db_path = chatydb._get_db_path(name)
        if not os.path.exists(db_path):
            yield None, f"Database '{name}' not found.", name
            return

        try:
            scoped_mgr = CorpusManager(db_path)
            # Verify database JSON is well-formed immediately
            _ = scoped_mgr.items.all()
        except Exception as err:
            yield None, f"Failed to open database '{name}': {err}", name
            return

        try:
            yield scoped_mgr, None, name
        finally:
            with suppress(Exception):
                scoped_mgr.close()
    else:
        # Fall back to active database or CHATYBOT_ACTIVE_DB env var
        active_env = os.environ.get("CHATYBOT_ACTIVE_DB")
        if chatydb._manager is None and active_env:
            active_name = active_env.strip()
            active_path = chatydb._get_db_path(active_name)
            if os.path.exists(active_path):
                chatydb.set_db(active_name, quiet=True)
            else:
                yield None, f"Active database '{active_name}' not found.", active_name
                return

        if chatydb._manager is None:
            yield None, "No database selected. Use the db_name parameter or /setdb first.", "active"
        else:
            yield chatydb._manager, None, chatydb._active_db_name or "active"


def db_search(
    query: str = "*",
    db_name: str | None = None,
    limit: int = 20,
    full_content: bool = False,
    app: Any = None,
) -> dict[str, Any]:
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
        Dictionary with matching items or error message.
    """
    with _scoped_corpus_manager(db_name) as (manager, err, resolved_db):
        if err or manager is None:
            return {"error": err or "No database selected. Use the db_name parameter or /setdb first."}

        all_items = manager.get_all_items()

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

        return {
            "query": query,
            "database": resolved_db,
            "total_matches": total_matches,
            "returned": len(results),
            "results": output,
        }


def db_get(
    item_id: int,
    db_name: str | None = None,
    app: Any = None,
) -> dict[str, Any]:
    """
    Retrieve a single complete item from a TinyDB database by its integer ID.

    Args:
        item_id: The integer ID (doc_id) of the item to retrieve.
        db_name: Database name to look in. If None, uses the currently active database.
        app: ChatybotApp instance passed when called within application context.

    Returns:
        Dictionary with the complete item details or an error message.
    """
    with _scoped_corpus_manager(db_name) as (manager, err, resolved_db):
        if err or manager is None:
            return {"error": err or "No database selected. Use the db_name parameter or /setdb first."}

        try:
            doc_id = int(item_id)
        except (ValueError, TypeError):
            return {
                "error": f"Invalid item_id '{item_id}'. Must be an integer."
            }

        item = manager.get_item(doc_id)
        if not item:
            return {
                "error": f"Item with ID {doc_id} not found in database '{resolved_db}'."
            }

        content = str(item.get("content") or "")
        output = {
            "id": getattr(item, "doc_id", doc_id),
            "type": item.get("type"),
            "name": item.get("name"),
            "content": content,
            "content_length": len(content),
            "metadata": item.get("metadata", {}),
        }

        return output


def db_list(app: Any = None) -> dict[str, Any]:
    """
    List all available TinyDB databases with entry counts and file sizes.

    Args:
        app: ChatybotApp instance passed when called within application context.

    Returns:
        Dictionary with database list.
    """
    base_dir = os.path.expanduser("~/.local/share/chatybot")
    db_dir = os.path.join(base_dir, "db")

    if not os.path.exists(db_dir):
        return {
            "databases": [],
            "message": "No database directory found."
        }

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

    return {
        "databases": databases
    }


def db_summary(
    db_name: str | None = None,
    item_range: str | None = None,
    limit: int = 50,
    format: str = "table",
    app: Any = None,
) -> dict[str, Any] | str:
    """
    Get a concise summary table or JSON list of items in a TinyDB database.
    Provides ID, timestamp, model, prompt snippet, thinking status, and token counts
    without returning heavy content payloads.

    Args:
        db_name: Database name to summarize. If None, uses active database or CHATYBOT_ACTIVE_DB.
        item_range: Optional item ID (e.g. '5') or start-end range (e.g. '1-10', '21-31').
        limit: Maximum number of items to return (default 50).
        format: Output format: 'table' for a compact ASCII table, or 'json' for structured JSON array.
        app: ChatybotApp instance passed when called within application context.

    Returns:
        Formatted ASCII summary table or dictionary.
    """
    with _scoped_corpus_manager(db_name) as (manager, err, resolved_db):
        if err or manager is None:
            return {"error": err or "No database selected. Use the db_name parameter or /setdb first."}

        all_items = manager.get_all_items()
        if not all_items:
            return {
                "database": resolved_db,
                "items": [],
                "message": "Database is empty."
            }

        # Apply range / ID filtering
        items = all_items
        range_label = "ALL"
        if item_range:
            raw_range = str(item_range).strip()
            if "-" in raw_range:
                try:
                    s_str, e_str = raw_range.split("-", 1)
                    s_id = int(s_str.strip())
                    e_id = int(e_str.strip())
                    items = [it for it in all_items if s_id <= getattr(it, "doc_id", 0) <= e_id]
                    range_label = f"{s_id}-{e_id}"
                except ValueError:
                    return {"error": f"Invalid range '{item_range}'. Use e.g. '1-10'."}
            else:
                try:
                    t_id = int(raw_range)
                    items = [it for it in all_items if getattr(it, "doc_id", 0) == t_id]
                    range_label = f"ID {t_id}"
                except ValueError:
                    return {"error": f"Invalid item filter '{item_range}'. Use e.g. '5' or '1-10'."}

        total_matched = len(items)
        items = items[:limit]

        records = []
        for it in items:
            doc_id = getattr(it, "doc_id", "N/A")
            meta = it.get("metadata") or {}
            raw_ts = meta.get("timestamp") or ""
            ts_str = raw_ts[:19].replace("T", " ") if len(raw_ts) >= 19 else raw_ts

            model_alias = str(meta.get("model_alias") or "unknown")
            prompt = str(meta.get("prompt") or "")
            clean_prompt = " ".join(prompt.split())
            prompt_snippet = clean_prompt[:40] + ("..." if len(clean_prompt) > 40 else "")

            content_str = str(it.get("content") or "")
            has_think_tag = any(tag in content_str for tag in ("<think>", "<thought>", "<thinking>"))
            if meta.get("thinking_content"):
                think_status = "metadata"
            elif has_think_tag:
                think_status = "in content"
            else:
                think_status = "stripped"

            tokens = meta.get("thinking_tokens", 0) or 0

            records.append({
                "id": doc_id,
                "timestamp": ts_str,
                "model": model_alias,
                "prompt": prompt_snippet,
                "thinking": think_status,
                "thinking_tokens": tokens,
                "type": it.get("type", "chat"),
                "name": it.get("name", "last_chat"),
            })

        if format.lower() == "json":
            return {
                "database": resolved_db,
                "range": range_label,
                "total_matched": total_matched,
                "returned": len(records),
                "items": records,
            }

        # Table format
        db_label = resolved_db
        hdr_title = f"DATABASE SUMMARY TABLE: {db_label} ({total_matched} items, range: {range_label})"
        line_width = 110
        lines = [
            "=" * line_width,
            hdr_title,
            "=" * line_width,
            f" {'ID':<4} {'Timestamp':<19} {'Model':<14} {'Prompt':<42} {'Thinking':<12} {'Tokens':>8}",
            "-" * line_width,
        ]
        for r in records:
            t_str = f"{r['thinking_tokens']:,}" if r['thinking_tokens'] > 0 else "0"
            lines.append(
                f" {r['id']:<4} {r['timestamp']:<19} {r['model'][:14]:<14} {r['prompt']:<42} {r['thinking']:<12} {t_str:>8}"
            )
        lines.append("=" * line_width)
        return "\n".join(lines)
