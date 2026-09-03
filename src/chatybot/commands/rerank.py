"""Semantic reranking commands.

Migrated from chatybot_app.handle_escape_command elif chain:
  /documents, /rerank
"""

import json
import os
import re
import traceback
from urllib.parse import urlparse

from chatybot.commands.registry import command, CommandResult
from chatybot.commands.context import CommandContext


@command("/documents", help="Set the document source for reranking", args="db=<name> | var=<name> | var=file | filebank=<1-5> | dir=\"<path>\"", category="rerank")
async def cmd_documents(ctx: CommandContext, parts: list, command: str) -> CommandResult:
    app = ctx.app
    doc_pattern = r'^/documents\s+(\w+)\s*=\s*(.+)$'
    match = re.match(doc_pattern, command)
    if not match:
        print("Usage: /documents db=<name> | var=<name> | var=file | filebank=<1-5> | dir=\"<path>\"")
        return CommandResult.ok()

    source_type = match.group(1).lower()
    identifier = match.group(2).strip(' "\'')

    if source_type == "db":
        db_file = os.path.expanduser(f"~/.local/share/chatybot/db/{identifier}.json")
        if not os.path.exists(db_file):
            print(f"Warning: Database '{identifier}' does not exist or has no entries in {db_file}.")
        app.rerank_documents_source = {"type": "db", "identifier": identifier}
        print(f"Document source set to database '{identifier}'.")
    elif source_type == "var":
        if identifier == "CHAT_HISTORY":
            app.rerank_documents_source = {"type": "var", "identifier": "CHAT_HISTORY"}
            print("Document source set to live chat history.")
        elif identifier == "file":
            if not app.buffer_manager.file_buffer:
                print("Warning: No file loaded. Use /file <path> first.")
            app.rerank_documents_source = {"type": "var", "identifier": "file"}
            print("Document source set to file buffer.")
        else:
            if identifier not in app.buffer_manager.script_vars:
                print(f"Warning: Variable '${{{identifier}}}' is not currently defined. It must be set before executing /rerank.")
            app.rerank_documents_source = {"type": "var", "identifier": identifier}
            print(f"Document source set to variable '${{{identifier}}}'.")
    elif source_type == "filebank":
        bank_name = f"filebank{identifier}"
        if bank_name not in app.buffer_manager.file_banks:
            print(f"Error: Invalid filebank number '{identifier}'. Use 1-5.")
            return CommandResult.ok()
        if not app.buffer_manager.file_banks[bank_name]:
            print(f"Warning: Filebank{identifier} is empty. Load a file first with /filebank{identifier} <path>.")
        app.rerank_documents_source = {"type": "filebank", "identifier": identifier}
        print(f"Document source set to {bank_name}.")
    elif source_type == "dir":
        if not os.path.exists(identifier) or not os.path.isdir(identifier):
            print(f"Error: Directory '{identifier}' does not exist.")
            return CommandResult.ok()
        app.rerank_documents_source = {"type": "dir", "identifier": identifier}
        print(f"Document source set to directory '{identifier}'.")
    else:
        print("Invalid source type. Use 'db', 'var', 'filebank', or 'dir'.")
    return CommandResult.ok()


@command("/rerank", help="Rerank documents against a query", args='"<query>" [, top_n=N] [, items=N] [, split=sentence|line|paragraph] [, return=summ|text] [, full_doc=true|false]', category="rerank")
async def cmd_rerank(ctx: CommandContext, parts: list, command: str) -> CommandResult:
    app = ctx.app
    # Dynamically load env keys in case of persistent process startup without them
    for path in [os.path.expanduser("~/.config/chatybot/.env"), "../../.env", "../.env", ".env"]:
        if os.path.exists(path):
            try:
                with open(path, "r") as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#") and "=" in line:
                            k, v = line.split("=", 1)
                            k = k.strip()
                            v = v.strip().strip('"\'')
                            os.environ[k] = v
            except Exception:
                pass

    # Dynamic fallback to jina_api_key.txt
    for key_file in ["jina_api_key.txt", "jina_ai_key.txt", "../jina_api_key.txt", "../jina_ai_key.txt"]:
        if os.path.exists(key_file):
            try:
                with open(key_file, "r") as f:
                    content = f.read().strip()
                    if "JINA_API_KEY=" in content:
                        key = content.split("JINA_API_KEY=")[-1].strip().strip('"\'')
                        os.environ["JINA_API_KEY"] = key
                    elif "export " in content and "=" in content:
                        key = content.split("=")[-1].strip().strip('"\'')
                        os.environ["JINA_API_KEY"] = key
                    else:
                        os.environ["JINA_API_KEY"] = content.strip('"\'')
                break
            except Exception:
                pass

    query_match = re.search(r'^/rerank\s+["\']([^"\']+)["\']', command, re.IGNORECASE)
    if not query_match:
        print('Usage: /rerank "<query>" [, top_n=<number>] [, items=<number>] [, split=<sentence|line|paragraph>] [, return=<summ|text>] [, full_doc=<true|false>]')
        return CommandResult.ok()

    query = query_match.group(1)
    remainder = command[query_match.end():]

    top_n_match = re.search(r'\btop_n\s*=\s*(\d+)', remainder, re.IGNORECASE)
    item_match = re.search(r'\bitem(s)?\s*=\s*(\d+)', remainder, re.IGNORECASE)
    split_match = re.search(r'\bsplit\s*=\s*([a-zA-Z]+)', remainder, re.IGNORECASE)
    return_match = re.search(r'\breturn\s*=\s*([a-zA-Z]+)', remainder, re.IGNORECASE)
    full_doc_match = re.search(r'\bfull_doc\s*=\s*([a-zA-Z]+)', remainder, re.IGNORECASE)

    top_n = int(top_n_match.group(1)) if top_n_match else 2
    item = int(item_match.group(2)) if item_match else 1
    split_mode = split_match.group(1).lower() if split_match else "sentence"
    return_type = return_match.group(1).lower() if return_match else "summ"
    full_doc = (full_doc_match.group(1).lower() == "true") if full_doc_match else False

    if not app.rerank_documents_source:
        print("Error: No document source specified. Set one using /documents <source> first.")
        return CommandResult.ok()

    rerank_model_config = None
    active_alias = app.config_manager.active_model_alias
    if active_alias:
        try:
            active_model_config = app.config_manager.get_model_config(active_alias)
            if active_model_config.get("type") == "reranker":
                rerank_model_config = active_model_config
        except Exception:
            pass

    if not rerank_model_config:
        for alias, config in app.config_manager.config.get("models", {}).items():
            if config.get("type") == "reranker":
                rerank_model_config = config
                break

    if not rerank_model_config:
        jina_key = os.environ.get("JINA_API_KEY")
        if jina_key:
            rerank_model_config = {
                "name": "jina-reranker-v3",
                "type": "reranker",
                "base_url": "https://api.jina.ai/v1/rerank",
                "api_key": "JINA_API_KEY"
            }
        else:
            print("Error: No reranker model is configured, and JINA_API_KEY environment variable is not set.")
            return CommandResult.ok()

    base_url = rerank_model_config.get("base_url", "")
    model_name = rerank_model_config.get("name", "jina-reranker-v3")
    api_key_env = rerank_model_config.get("api_key", "")
    api_key = os.environ.get(api_key_env) if api_key_env else os.environ.get("JINA_API_KEY")

    chunking_mode_map = {"sentence": "sentences", "line": "lines", "paragraph": "paragraphs"}
    chunking_mode = chunking_mode_map.get(split_mode, "sentences")

    if "localhost" in base_url or "127.0.0.1" in base_url:
        backend = "local"
        parsed = urlparse(base_url)
        host = parsed.hostname or "localhost"
        port = parsed.port or 8080
    elif base_url:
        backend = "remote"
        host = "localhost"
        port = 8080
    else:
        backend = "auto"
        host = "localhost"
        port = 8080

    source_type = app.rerank_documents_source["type"]
    source_id = app.rerank_documents_source["identifier"]

    from EasyRerank import EasyRanker, TextParser

    chunked_docs = []
    chunk_mappings = []
    pre_filtered_chunks = []

    if source_type == "db":
        from tinydb import TinyDB
        db_path = os.path.expanduser(f"~/.local/share/chatybot/db/{source_id}.json")
        if not os.path.exists(db_path):
            print(f"Error: Database file not found at {db_path}.")
            return CommandResult.ok()

        try:
            db = TinyDB(db_path)
            if 'items' in db.tables():
                all_items = db.table('items').all()
            else:
                all_items = db.all()
            for item_doc in all_items:
                content = item_doc.get("content") or ""
                doc_id = item_doc.doc_id
                name = item_doc.get("name", "N/A")

                parser = TextParser(content)
                if split_mode == "paragraph":
                    chunks = list(parser.paragraphs())
                    join_str = "\n\n"
                elif split_mode == "line":
                    chunks = list(parser.lines())
                    join_str = "\n"
                else:
                    sentences = [s.strip() for line in content.split('\n') for s in re.split(r'(?<=[.!?])\s+', line) if s.strip()]
                    chunks = sentences
                    join_str = " "

                for i in range(0, len(chunks), item):
                    chunk_text = join_str.join(chunks[i:i+item])
                    if chunk_text:
                        chunked_docs.append(chunk_text)
                        chunk_mappings.append({
                            "parent_id": doc_id,
                            "parent_name": name,
                            "full_text": content
                        })
        except Exception as e:
            print(f"Error reading database {source_id}: {str(e)}")
            return CommandResult.ok()

    elif source_type == "var":
        raw_docs = []
        if source_id == "CHAT_HISTORY":
            for turn_idx, (p, r) in enumerate(app.chat_history):
                for text, role in [(p, "user"), (r, "assistant")]:
                    if not text:
                        continue
                    parser = TextParser(text)
                    if split_mode == "paragraph":
                        chunks = list(parser.paragraphs())
                        join_str = "\n\n"
                    elif split_mode == "line":
                        chunks = list(parser.lines())
                        join_str = "\n"
                    else:
                        sentences = [s.strip() for line in text.split('\n') for s in re.split(r'(?<=[.!?])\s+', line) if s.strip()]
                        chunks = sentences
                        join_str = " "

                    for i in range(0, len(chunks), item):
                        chunk_text = join_str.join(chunks[i:i+item])
                        if chunk_text:
                            chunked_docs.append(chunk_text)
                            chunk_mappings.append({
                                "role": role,
                                "turn": turn_idx,
                                "full_text": text
                            })
        elif source_id == "file":
            var_val = app.buffer_manager.file_buffer
            raw_docs = [var_val] if var_val else []
        else:
            var_val = app.buffer_manager.script_vars.get(source_id, "")
            try:
                parsed = json.loads(var_val)
                if isinstance(parsed, list):
                    for item_val in parsed:
                        if isinstance(item_val, dict):
                            content = item_val.get("content") or item_val.get("text") or item_val.get("value")
                            if content:
                                raw_docs.append(str(content))
                        else:
                            raw_docs.append(str(item_val))
                elif isinstance(parsed, dict):
                    content = parsed.get("content") or parsed.get("text") or parsed.get("value")
                    raw_docs = [str(content)] if content else [str(parsed)]
                else:
                    raw_docs = [str(parsed)]
            except Exception:
                raw_docs = [var_val]

        for doc_idx, doc in enumerate(raw_docs):
            parser = TextParser(doc)
            if split_mode == "paragraph":
                chunks = list(parser.paragraphs())
                join_str = "\n\n"
            elif split_mode == "line":
                chunks = list(parser.lines())
                join_str = "\n"
            else:
                sentences = [s.strip() for line in doc.split('\n') for s in re.split(r'(?<=[.!?])\s+', line) if s.strip()]
                chunks = sentences
                join_str = " "

            for i in range(0, len(chunks), item):
                chunk_text = join_str.join(chunks[i:i+item])
                if chunk_text:
                    chunked_docs.append(chunk_text)
                    chunk_mappings.append({
                        "doc_idx": doc_idx,
                        "full_text": doc
                    })

    elif source_type == "filebank":
        bank_name = f"filebank{source_id}"
        if bank_name in app.buffer_manager.file_banks:
            content = app.buffer_manager.file_banks[bank_name]
            if content:
                parser = TextParser(content)
                if split_mode == "paragraph":
                    chunks = list(parser.paragraphs())
                    join_str = "\n\n"
                elif split_mode == "line":
                    chunks = list(parser.lines())
                    join_str = "\n"
                else:
                    sentences = [s.strip() for line in content.split('\n') for s in re.split(r'(?<=[.!?])\s+', line) if s.strip()]
                    chunks = sentences
                    join_str = " "

                for i in range(0, len(chunks), item):
                    chunk_text = join_str.join(chunks[i:i+item])
                    if chunk_text:
                        chunked_docs.append(chunk_text)
                        chunk_mappings.append({
                            "bank": bank_name,
                            "full_text": content
                        })
        else:
            print(f"Error: Filebank{source_id} not found.")
            return CommandResult.ok()
    elif source_type == "dir":
        from EasyRerank import DirectoryTextProcessor
        processor = DirectoryTextProcessor(source_id)

        limit_batch_size_match = re.search(r'\blimit_batch_size\s*=\s*(\d+)', remainder, re.IGNORECASE)
        limit_top_n_match = re.search(r'\blimit_top_n\s*=\s*(\d+)', remainder, re.IGNORECASE)
        max_limit_match = re.search(r'\bmax_limit\s*=\s*(\d+)', remainder, re.IGNORECASE)

        limit_batch_size = int(limit_batch_size_match.group(1)) if limit_batch_size_match else 64
        limit_top_n = int(limit_top_n_match.group(1)) if limit_top_n_match else 3
        max_limit = int(max_limit_match.group(1)) if max_limit_match else 64

        print(f"Ingesting directory '{source_id}' with Batched Top-N pre-filtering (limit_batch_size={limit_batch_size}, limit_top_n={limit_top_n}, max_limit={max_limit})...")

        pre_filtered_chunks, reached_limit = processor.process_with_batched_top_n(
            chunk_size=item,
            top_n=limit_top_n,
            max_limit=max_limit,
            batch_size=limit_batch_size,
            chunking_mode=chunking_mode
        )
        chunked_docs = [c['chunk'] for c in pre_filtered_chunks]

    print(f"Reranking documents from {source_type}='{source_id}' using {model_name}...")
    try:
        ranker = EasyRanker(
            documents=chunked_docs,
            backend=backend,
            api_key=api_key,
            host=host,
            port=port,
            model=model_name,
            chunk_size=item,
            chunking_mode=chunking_mode
        )
        if backend == "remote" and base_url and hasattr(ranker, "backend_instance") and hasattr(ranker.backend_instance, "base_url"):
            ranker.backend_instance.base_url = base_url

        if app.trace_raw_payload:
            masked_key = f"{api_key[:10]}...{api_key[-5:]}" if api_key and len(api_key) > 15 else "None"
            payload = {
                "model": model_name,
                "query": query,
                "top_n": top_n,
                "documents": chunked_docs
            }
            payload_str = json.dumps(payload, indent=2)
            payload_bytes = payload_str.encode('utf-8')
            size_bytes = len(payload_bytes)
            size_kb = size_bytes / 1024
            est_tokens = max(1, int(size_bytes / 4))
            size_info = f"Size: {size_bytes} bytes ({size_kb:.2f} KB) | Est. Tokens: ~{est_tokens} (industry avg)"

            print("Payload:")
            print("-----------------------------")
            print(f"POST {base_url}")
            print(f"Headers: {{'Authorization': 'Bearer {masked_key}', 'Content-Type': 'application/json'}}")
            print(payload_str)
            print("---- end of payload ---")
            print(size_info)

            log_content = (
                f"Rerank Payload:\n---------------------\n"
                f"POST {base_url}\n"
                f"Headers: {{'Authorization': 'Bearer {masked_key}', 'Content-Type': 'application/json'}}\n"
                f"{payload_str}\n---- end of payload ---\n{size_info}"
            )
            app.logging_manager.log_message(log_content)

        results = ranker.rerank(query=query, top_n=top_n, verbose=False)
        app.latest_rerank_results = results

        resolved_matches = []
        for idx, res in enumerate(results, 1):
            score = res.get('relevance_score', 0.0)

            if source_type == "dir":
                matched_idx = res.get('index', 0)
                if matched_idx < len(pre_filtered_chunks):
                    source_chunk = pre_filtered_chunks[matched_idx]
                    chunk_text = source_chunk.get('chunk', '')
                    filename = source_chunk.get('filename', 'Unknown')
                    chunk_id = source_chunk.get('chunk_id', 0)
                else:
                    chunk_text = res.get('chunk', '')
                    filename = res.get('filename', 'Unknown')
                    chunk_id = res.get('chunk_id', 0)
                ref_line = f"File: {filename} (Chunk: {chunk_id})"
                ref_short = f"File: {filename}"

                if full_doc:
                    file_path = os.path.join(source_id, filename)
                    if os.path.exists(file_path):
                        try:
                            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                                text_to_return = f.read()
                        except Exception:
                            text_to_return = chunk_text
                    else:
                        text_to_return = chunk_text
                else:
                    text_to_return = chunk_text
            else:
                chunk_text = chunked_docs[res.get('index', 0)]
                mapping = chunk_mappings[res.get('index', 0)]
                text_to_return = mapping.get("full_text", chunk_text) if full_doc else chunk_text

                if source_type == "db":
                    ref_line = f"DB Record: ID {mapping['parent_id']} (Name: '{mapping['parent_name']}')"
                    ref_short = f"Database Record ID {mapping['parent_id']} (Name: {mapping['parent_name']})"
                elif source_type == "var" and source_id == "CHAT_HISTORY":
                    ref_line = f"Chat History: Turn {mapping['turn'] + 1} ({mapping['role'].capitalize()})"
                    ref_short = f"Chat Turn {mapping['turn'] + 1} ({mapping['role'].capitalize()})"
                else:
                    ref_line = f"Variable Index: {res.get('index', 0)}"
                    ref_short = f"Variable Index {mapping.get('doc_idx', res.get('index', 0))}"

            resolved_matches.append({
                "score": score,
                "chunk_text": chunk_text,
                "text_to_return": text_to_return,
                "ref_line": ref_line,
                "ref_short": ref_short
            })

        ascii_lines = []
        ascii_lines.append("=" * 90)
        ascii_lines.append(f" EASYRERANK RESULTS FOR QUERY: \"{query}\"")
        ascii_lines.append(f" Backend: {backend.upper()} | Model: {model_name} | Source: {source_type}={source_id}")
        ascii_lines.append("=" * 90)
        ascii_lines.append(" Rank |  Score | Source Reference & Snippet")
        ascii_lines.append("------+--------+----------------------------------------------------------------------------")

        if not resolved_matches:
            ascii_lines.append("      |        | No matching results found.")
        else:
            for idx, match in enumerate(resolved_matches, 1):
                score = match["score"]
                ref_line = match["ref_line"]
                chunk_text = match["chunk_text"]

                snippet = chunk_text.replace('\n', ' ').strip()
                if len(snippet) > 70:
                    snippet = snippet[:67] + "..."

                ascii_lines.append(f"  {idx:2d}  | {score:.4f} | {ref_line}")
                ascii_lines.append(f"      |        | \"{snippet}\"")
                if idx < len(resolved_matches):
                    ascii_lines.append("------+--------+----------------------------------------------------------------------------")
        ascii_lines.append("=" * 90)
        ascii_lines.append(f"Total results: {len(resolved_matches)}")
        ascii_lines.append("=" * 90)

        ascii_table = "\n".join(ascii_lines)

        raw_texts = [match["text_to_return"] for match in resolved_matches]
        concatenated_text = "\n\n".join(raw_texts)

        if return_type == "text":
            if app.trace_rerank:
                print(ascii_table)
                print("\n[Raw Text Output]")
                print("-" * 30)
            print(concatenated_text)
        else:
            print(ascii_table)

        if return_type == "text":
            app.chat_history.append((f"[Rerank Query] {query}", concatenated_text))
        else:
            app.chat_history.append((f"[Rerank Query] {query}", ascii_table))

        rerank_blocks = []
        for idx, match in enumerate(resolved_matches, 1):
            rerank_blocks.append(f"[Rerank Match #{idx} | {match['ref_short']} | Relevance: {match['score']:.4f}]\n{match['text_to_return']}")
        app.buffer_manager.script_vars["latest_rerank"] = "\n\n".join(rerank_blocks)

    except Exception as e:
        print(f"Error executing reranking pipeline: {str(e)}")
        traceback.print_exc()
    return CommandResult.ok()
