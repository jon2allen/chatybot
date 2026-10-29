#! /usr/bin/env python3
"""
batch.py — /batch and /batchlist commands (Batch API subsystem, Phase 1).

Implements the command surface of mistral-batch-poc/batch_proposal_v3.md §4.3:
a staging lifecycle (start → add → end → run → check) with draft inspection
(items/ids/show/edit/remove/clear), payload dumping with variable binding,
a global catalog query (/batchlist) modeled after /session list, and crash-safe
submission against the OpenRouter Batch API.

Naming rationale ("batch_api"): this subsystem wraps asynchronous *provider*
Batch APIs (OpenRouter now, Mistral in Phase 2) — bulk inference submitted,
polled, and retrieved out-of-band at a 50% discount. It is unrelated to the
pre-existing "batch" concepts in ChatyBot: batch-n / Batched Top-N is the
client-side chunk pre-filter in /rerank (doc/BATCH_N_WALKTHROUGH.md), and the
14.5 cookbook "batch processor" is a sequential foreach loop.
"""

from __future__ import annotations

import os
import shlex
from datetime import datetime, timedelta
from typing import Any

from chatybot.batch_manager import (
    BatchError,
    BatchManager,
    EDITABLE_STATES,
    TERMINAL_STATES,
    make_provider,
    sanitize_batch_name,
    split_text,
)
from chatybot.commands.context import CommandContext
from chatybot.commands.registry import CommandResult, command

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

BATCH_KV_KEYS = {"id", "var", "filebank", "split", "file", "limit", "range",
                 "force", "adopt", "wait", "clear"}

# Built-in prompt templates (proposal §4.2 "Named Template")
BUILTIN_PROMPTS = {
    "translate": ("Translate the input text faithfully. Preserve tone, names, "
                  "and structure. Output only the translation."),
    "summarize": ("Summarize the input text. Capture the key points in "
                  "concise, clear language. Output only the summary."),
    "classify": ("Classify the input text into the most fitting category. "
                 "Output only the category label."),
}

_pending_batch_prompt: dict[str, str] = {}


def get_batch_manager(app: Any) -> BatchManager:
    """Lazily attach a BatchManager to the app (session-decoupled storage)."""
    mgr = getattr(app, "_batch_manager", None)
    if mgr is None:
        mgr = BatchManager(workspace=os.getcwd())
        app._batch_manager = mgr
    return mgr


def _require_batch_model(app: Any) -> tuple[str, dict]:
    """Refuse when the current model is not batch-capable, mirroring /imagine's
    capability gate (proposal §4.1)."""
    alias = app.config_manager.active_model_alias
    config = app.config_manager.get_model_config(alias)
    if not config.get("batch", False):
        batch_models = app.config_manager.list_batch_capable_models()
        print(f"Error: current model '{alias}' does not support batch jobs.")
        if batch_models:
            print(f"  Batch-capable models: {', '.join(batch_models)}")
            print(f"  Switch to one of these first, e.g.: /model {batch_models[0]}")
        else:
            print("  No batch-capable models configured in chat_config.toml "
                  "(models need 'batch = true').")
        raise BatchError("batch model required")
    return alias, config


def _batch_model_config(app: Any, meta: dict) -> dict:
    """Resolve the batch's own model config (from meta, not the active model)
    with friendly errors when the alias was removed from chat_config.toml
    or is no longer flagged batch-capable."""
    alias = meta.get("model_alias")
    try:
        model_config = app.config_manager.get_model_config(alias)
    except ValueError:
        raise BatchError(
            f"Model alias '{alias}' (used by batch '{meta['name']}') no longer "
            "exists in chat_config.toml. Restore the alias or start a new "
            "batch with a configured batch model."
        )
    if not model_config.get("batch", False):
        raise BatchError(f"Model alias '{alias}' is not flagged batch-capable "
                         "(needs 'batch = true' in chat_config.toml).")
    return model_config


def _build_provider(app: Any, meta: dict):
    """Build the provider client for a batch's own model entry (Phase 1:
    OpenRouter). The model is taken from the batch meta, not the active
    model, so polling/submitting works after the user switched models."""
    vendor = (meta.get("provider") or "").lower()
    if vendor != "openrouter":
        raise BatchError(f"Batch backend '{vendor or 'unknown'}' is not implemented yet "
                         "(Phase 2 adds the Mistral backend). Configure a model with "
                         "vendor = \"openrouter\" and batch = true.")
    model_config = _batch_model_config(app, meta)
    api_key = None
    api_key_env = model_config.get("api_key", "")
    if api_key_env:
        api_key = os.environ.get(api_key_env)
    if not api_key:
        raise BatchError(f"API key not found: set the {api_key_env or 'provider'} "
                         "environment variable (model config 'api_key' names it).")
    return make_provider(model_config, api_key)


def _parse_args(rest: str) -> tuple[dict[str, str], list[str]]:
    """Split a sub-argument string into key=value options and free tokens.

    Uses shlex so quoted inline prompts and file paths survive intact.
    A token counts as key=value only when its key is a known batch option,
    so item text containing '=' is never swallowed."""
    opts: dict[str, str] = {}
    tokens: list[str] = []
    try:
        parts = shlex.split(rest)
    except ValueError:
        parts = rest.split()
    for tok in parts:
        if "=" in tok:
            key, _, val = tok.partition("=")
            if key.lower() in BATCH_KV_KEYS:
                opts[key.lower()] = val
                continue
        tokens.append(tok)
    return opts, tokens


def _name_token(rest: str, skip: str | None = None) -> str | None:
    """First positional (non key=value) token, skipping an item id."""
    try:
        parts = shlex.split(rest)
    except ValueError:
        parts = rest.split()
    for tok in parts:
        if "=" in tok and tok.partition("=")[0].lower() in BATCH_KV_KEYS:
            continue
        if skip is not None and tok == skip:
            continue
        return tok or None
    return None


def _get_var_value(app: Any, var_name: str) -> Any:
    """Read a script variable's raw value (lists stay lists)."""
    bm = app.buffer_manager
    raw = bm.get_script_var(var_name)
    if raw is None and hasattr(bm, "script_vars"):
        raw = bm.script_vars.get(var_name)
    return raw


def _text_from_tokens(tokens: list[str]) -> str:
    return " ".join(tokens).strip()


def _id_prefix_for_source(source_kind: str, source_name: str, split_mode: str) -> str:
    """Auto-ID prefixes per proposal §4.3: fb1_line_ / <var>_ / <name>_."""
    mode_slug = {"lines": "line", "paragraphs": "paragraph"}.get(split_mode, "item")
    if source_kind == "filebank":
        return f"{source_name}_{mode_slug}_"
    return f"{sanitize_batch_name(source_name)}_"


def _batch_config(app: Any) -> dict:
    return app.config_manager.config.get("batch", {}) or {}


def _print_batch_status(meta: dict) -> None:
    print(f"\nBatch: {meta['name']}  (ID: {meta['batch_id']})")
    print(f"  Status:     {meta['status']}")
    print(f"  Provider:   {meta['provider']}  Model: {meta['model']} "
          f"(alias: {meta.get('model_alias')})")
    print(f"  Items:      {meta.get('item_count', 0)}")
    if meta.get("provider_id"):
        print(f"  Provider ID: {meta['provider_id']}")
    if meta.get("host_backend"):
        print(f"  Host:       {meta['host_backend']}")
    if meta.get("cost_usd") is not None:
        print(f"  Exact cost: ${meta['cost_usd']}")
    if meta.get("prompt"):
        prompt_prev = meta["prompt"][:60] + "..." if len(meta["prompt"]) > 60 else meta["prompt"]
        print(f"  Prompt:     \"{prompt_prev}\"")
    created = datetime.fromtimestamp(meta.get("created_at") or 0)
    print(f"  Created:    {created.strftime('%Y-%m-%d %H:%M')}")
    if meta.get("finalized_at"):
        fin = datetime.fromtimestamp(meta["finalized_at"])
        print(f"  Finalized:  {fin.strftime('%Y-%m-%d %H:%M')}")
    print()


def _parse_since(raw: str) -> datetime | None:
    try:
        if raw.endswith("d"):
            delta = timedelta(days=float(raw[:-1]))
        elif raw.endswith("h"):
            delta = timedelta(hours=float(raw[:-1]))
        elif raw.endswith("m"):
            delta = timedelta(minutes=float(raw[:-1]))
        else:
            print(f"Invalid since= unit '{raw}'. Use d (days), h (hours), or m (minutes). "
                  "E.g. since=7d")
            return None
        return datetime.now() - delta
    except ValueError:
        print(f"Invalid since= value '{raw}'. Use numeric values like since=7d, "
              "since=24h, since=30m")
        return None


def _try_active_draft(mgr: BatchManager) -> dict | None:
    candidates = [r for r in mgr.list_index() if r.get("status") in EDITABLE_STATES]
    if not candidates:
        return None
    try:
        return mgr.read_meta(candidates[-1]["batch_id"])
    except BatchError:
        return None


# ---------------------------------------------------------------------------
# /batch
# ---------------------------------------------------------------------------

@command("/batch", help="Batch API jobs: stage, seal, submit, poll, retrieve",
         args="<status|start|prompt|add|items|ids|show|edit|remove|clear|dump|end|abort|run|check|retry|list|cancel> [name] [key=value ...]",
         category="batch")
async def cmd_batch(ctx: CommandContext, parts: list, command: str) -> CommandResult:
    app = ctx.app
    mgr = get_batch_manager(app)
    rest_all = command.split(maxsplit=2)
    subcmd = (parts[1].lower() if len(parts) > 1 else "status")
    rest = rest_all[2] if len(rest_all) > 2 else ""

    try:
        # ---- status (default) -------------------------------------------
        if subcmd in ("status", ""):
            target = _name_token(rest)
            meta = mgr.resolve(target) if target else _try_active_draft(mgr)
            if meta is None:
                print("No batch draft open. Start one with: /batch start <name>")
                print("Catalog: /batchlist")
            else:
                _print_batch_status(meta)
            return CommandResult.ok()

        # ---- start ------------------------------------------------------
        elif subcmd == "start":
            opts, tokens = _parse_args(rest)
            if not tokens:
                print("Usage: /batch start <name> [clear=true]")
                return CommandResult.ok()
            name = tokens[0]
            model_alias, model_config = _require_batch_model(app)
            prompt = _pending_batch_prompt.get("prompt")
            meta = mgr.start(name, model_alias=model_alias,
                             model_name=model_config.get("name", model_alias),
                             provider=(model_config.get("vendor") or "openrouter").lower(),
                             prompt=prompt,
                             clear=opts.get("clear", "").lower() in ("true", "1", "yes"))
            print(f"Opened batch draft '{meta['name']}' (ID: {meta['batch_id']}, "
                  f"model: {model_alias})")
            if meta.get("prompt"):
                shown = meta["prompt"] if len(meta["prompt"]) <= 60 else meta["prompt"][:60] + "..."
                print(f"  Batch prompt set: \"{shown}\"")
            if opts.get("clear", "").lower() in ("true", "1", "yes"):
                print("  Staged items cleared.")
            print("  Add items with /batch add, then seal with /batch end.")
            return CommandResult.ok()

        # ---- prompt ------------------------------------------------------
        elif subcmd == "prompt":
            if not rest.strip():
                meta = _try_active_draft(mgr)
                current = (meta or {}).get("prompt") or _pending_batch_prompt.get("prompt")
                print(f"Batch prompt: {current!r}" if current
                      else "No batch prompt set. Usage: /batch prompt \"<text>\" | "
                           "<template> | file=<path>")
                return CommandResult.ok()
            opts, tokens = _parse_args(rest)
            if "file" in opts:
                path = os.path.expanduser(opts["file"])
                if not os.path.isfile(path):
                    print(f"Error: prompt file not found: {path}")
                    return CommandResult.ok()
                with open(path, "r", encoding="utf-8") as f:
                    prompt = f.read().strip()
            else:
                text = _text_from_tokens(tokens)
                prompt = BUILTIN_PROMPTS.get(text.strip().lower(), text)
            if not prompt:
                print("Error: empty batch prompt.")
                return CommandResult.ok()
            meta = _try_active_draft(mgr)
            if meta is not None:
                mgr.set_prompt(meta, prompt)
                print(f"Batch prompt set on '{meta['name']}'.")
            else:
                _pending_batch_prompt["prompt"] = prompt
                print("Batch prompt set (applies to the next /batch start).")
            return CommandResult.ok()

        # ---- add ----------------------------------------------------------
        elif subcmd == "add":
            opts, tokens = _parse_args(rest)
            # /batch add always operates on the active draft (proposal §4.3
            # has no name argument for add). Guessing a leading batch name
            # from the first token would corrupt text that happens to start
            # with a word matching an existing batch name.
            meta = mgr.resolve(None)
            if meta is None:
                print("Error: no batch specified and no active draft found. "
                      "Start one with: /batch start <name>")
                return CommandResult.ok()

            split_mode = opts.get("split", "lines").lower()
            if split_mode not in ("lines", "paragraphs", "none"):
                print(f"Invalid split= mode '{split_mode}'. Use lines, paragraphs, or none.")
                return CommandResult.ok()
            explicit_id = opts.get("id")
            id_prefix = f"{sanitize_batch_name(meta['name'])}_"
            origin = "manual"

            if "filebank" in opts:
                bank_name = f"filebank{opts['filebank']}"
                content = app.buffer_manager.file_banks.get(bank_name, "")
                if not content:
                    print(f"Error: {bank_name} is empty. "
                          f"Load it first: /filebank{opts['filebank']} <path>")
                    return CommandResult.ok()
                origin = bank_name
                id_prefix = _id_prefix_for_source("filebank", f"fb{opts['filebank']}", split_mode)
                texts = _split_for_add(content, split_mode)
            elif "var" in opts:
                var_name = opts["var"].strip().lstrip("$")
                value = _get_var_value(app, var_name)
                if value is None:
                    print(f"Error: script variable '{var_name}' is not set.")
                    return CommandResult.ok()
                origin = f"var:{var_name}"
                id_prefix = _id_prefix_for_source("var", var_name, split_mode)
                if isinstance(value, (list, tuple)):
                    texts = [str(v) for v in value]
                else:
                    texts = _split_for_add(str(value), split_mode)
            elif "file" in opts:
                path = os.path.expanduser(opts["file"])
                if not os.path.isfile(path):
                    print(f"Error: file not found: {path}")
                    return CommandResult.ok()
                with open(path, "r", encoding="utf-8") as f:
                    content = f.read()
                stem = os.path.splitext(os.path.basename(path))[0]
                origin = f"file:{path}"
                id_prefix = _id_prefix_for_source("file", stem, split_mode)
                texts = _split_for_add(content, split_mode)
            else:
                text = _text_from_tokens(tokens)
                if not text:
                    print("Usage: /batch add <text | filebank=N | var=NAME | file=PATH> "
                          "[id=<id>] [split=lines|paragraphs]")
                    return CommandResult.ok()
                texts = [text]
            if not texts:
                print("Error: no items to add (source was empty after splitting).")
                return CommandResult.ok()
            added = mgr.add_items(meta, texts, id_prefix=id_prefix,
                                  explicit_id=explicit_id, origin=origin)
            print(f"Added {len(added)} item(s) to '{meta['name']}' "
                  f"({meta['item_count']} total):")
            for item in added[:5]:
                preview = (item["text"][:40] + "...") if len(item["text"]) > 40 else item["text"]
                print(f"  {item['custom_id']}: \"{preview}\"")
            if len(added) > 5:
                print(f"  ... and {len(added) - 5} more (list with /batch items)")
            return CommandResult.ok()

        # ---- items ---------------------------------------------------------
        elif subcmd == "items":
            opts, tokens = _parse_args(rest)
            meta = mgr.resolve(_name_token(rest))
            offset, limit = 0, 10
            if "limit" in opts:
                try:
                    limit = int(opts["limit"])
                except ValueError:
                    print("Invalid limit value. Using default limit of 10.")
            if "range" in opts:
                try:
                    r = opts["range"]
                    if ":" in r:
                        s, e = r.split(":", 1)
                        offset = int(s) if s else 0
                        limit = (int(e) - offset) if e else None
                    else:
                        offset = int(r)
                except ValueError:
                    print("Invalid range format. Use range=start:end. Using default limit of 10.")
            items = mgr.list_items(meta, offset=offset, limit=limit)
            print(f"\n[Staged Items: {meta['name']} ({meta['item_count']} items, "
                  f"status: {meta['status']})]")
            for i, item in enumerate(items, offset + 1):
                preview = (item["text"][:40] + "...") if len(item["text"]) > 40 else item["text"]
                print(f"  #{i}  {item['custom_id']}   \"{preview}\"")
            if not items:
                print("  (no items)")
            print()
            return CommandResult.ok()

        # ---- ids ------------------------------------------------------------
        elif subcmd == "ids":
            opts, tokens = _parse_args(rest)
            meta = mgr.resolve(_name_token(rest))
            items = mgr.list_items(meta)
            ids = [it["custom_id"] for it in items]
            target = opts.get("var")
            bound = (target or "BATCH_ITEM_IDS").strip().lstrip("$")
            app.buffer_manager.set_script_var(bound, ids, allow_protected=True)
            print(f"\nItem IDs ({meta['name']}, {len(ids)}):")
            for i in ids:
                print(f"  {i}")
            print(f"(exported to ${{{bound}}})\n")
            return CommandResult.ok()

        # ---- show -------------------------------------------------------------
        elif subcmd == "show":
            opts, tokens = _parse_args(rest)
            if not tokens:
                print("Usage: /batch show <item-id> [name]")
                return CommandResult.ok()
            custom_id = tokens[0]
            meta = mgr.resolve(_name_token(rest, skip=custom_id))
            item = mgr.show_item(meta, custom_id)
            print(f"\nItem: {item['custom_id']}  (batch: {meta['name']})")
            print(f"Origin: {item.get('origin', 'manual')}   Chars: {len(item['text'])}")
            print("-" * 60)
            print(item["text"])
            print()
            return CommandResult.ok()

        # ---- edit ----------------------------------------------------------
        elif subcmd == "edit":
            opts, tokens = _parse_args(rest)
            if not tokens:
                print("Usage: /batch edit <id> <text | var=NAME | file=PATH> [name]")
                return CommandResult.ok()
            custom_id = tokens[0]
            meta = mgr.resolve(_name_token(rest, skip=custom_id))
            if "var" in opts:
                value = _get_var_value(app, opts["var"].strip().lstrip("$"))
                new_text = "" if value is None else str(value)
            elif "file" in opts:
                with open(os.path.expanduser(opts["file"]), "r", encoding="utf-8") as f:
                    new_text = f.read().strip()
            else:
                new_text = _text_from_tokens(tokens[1:])
            if not new_text:
                print("Error: empty replacement text.")
                return CommandResult.ok()
            mgr.edit_item(meta, custom_id, new_text)
            print(f"Updated item '{custom_id}' in '{meta['name']}'.")
            return CommandResult.ok()

        # ---- remove / del ----------------------------------------------------
        elif subcmd in ("remove", "del", "delete"):
            opts, tokens = _parse_args(rest)
            if not tokens:
                print("Usage: /batch remove <id> [name]")
                return CommandResult.ok()
            custom_id = tokens[0]
            meta = mgr.resolve(_name_token(rest, skip=custom_id))
            mgr.remove_item(meta, custom_id)
            print(f"Removed item '{custom_id}' from '{meta['name']}' "
                  f"({meta['item_count']} items remain).")
            return CommandResult.ok()

        # ---- clear / reset -----------------------------------------------------
        elif subcmd in ("clear", "reset"):
            meta = mgr.resolve(_name_token(rest))
            if meta["status"] not in EDITABLE_STATES:
                print(f"Error: items can only be cleared while in draft "
                      f"(status: {meta['status']}).")
                return CommandResult.ok()
            mgr.clear_items(meta["batch_id"])
            meta["item_count"] = 0
            mgr._write_meta(meta)
            print(f"Cleared staged items of '{meta['name']}' (model and prompt kept, "
                  "status: draft).")
            return CommandResult.ok()

        # ---- dump ----------------------------------------------------------------
        elif subcmd == "dump":
            opts, tokens = _parse_args(rest)
            meta = mgr.resolve(_name_token(rest))
            payload = mgr.dump_payload(meta)
            print(f"\nBatch payload for '{meta['name']}':")
            print(payload)
            bound = opts.get("var", "BATCH_PAYLOAD").strip().lstrip("$")
            app.buffer_manager.set_script_var(bound, payload, allow_protected=True)
            print(f"\n(payload bound to ${{{bound}}})\n")
            return CommandResult.ok()

        # ---- end -------------------------------------------------------------------
        elif subcmd == "end":
            meta = mgr.resolve(_name_token(rest))
            result = mgr.end(meta)
            print(f"Sealed batch '{meta['name']}': {result['item_count']} items scanned "
                  "(no security hits), payload compiled to requests.json.")
            print(f"Status: staged. Submit with /batch run {meta['name']}")
            return CommandResult.ok()

        # ---- abort --------------------------------------------------------------------
        elif subcmd == "abort":
            meta = mgr.resolve(_name_token(rest))
            mgr.abort(meta)
            print(f"Aborted and deleted batch '{meta['name']}'.")
            return CommandResult.ok()

        # ---- run ------------------------------------------------------------------------
        elif subcmd == "run":
            opts, tokens = _parse_args(rest)
            meta = mgr.resolve(_name_token(rest))
            if "adopt" in opts:
                mgr.adopt_orphan(meta, opts["adopt"])
                print(f"Adopted provider batch {opts['adopt']} into '{meta['name']}' "
                      "(status: submitted). Poll with /batch check.")
                return CommandResult.ok()
            # Validate and price against the BATCH's model (meta), not the
            # active interactive model — /batch run must work after the user
            # switched their chat model back to a non-batch alias.
            batch_model_config = _batch_model_config(app, meta)
            provider_obj = _build_provider(app, meta)
            batch_cfg = _batch_config(app)
            force = opts.get("force", "").lower() in ("true", "1", "yes")

            items = mgr.list_items(meta)
            estimate = mgr.estimate_cost_usd(meta, items,
                                             batch_model_config.get("max_tokens"),
                                             batch_model_config.get("input_cost_per_mtok"))
            if estimate is None:
                print("  Note: cost estimate unavailable (model lacks "
                     "input_cost_per_mtok); budget guard skipped.")
            else:
                print(f"  Pre-submit cost estimate: ${estimate:.4f}")

            meta = await mgr.run(
                meta, provider_obj,
                force=force,
                max_cost_usd=float(batch_cfg.get("max_cost_usd", 5.0)),
                max_open_per_provider=int(batch_cfg.get("max_open_per_provider", 3)),
                max_tokens=batch_model_config.get("max_tokens"),
                input_cost_per_mtok=batch_model_config.get("input_cost_per_mtok"),
            )
            print(f"Submitted batch '{meta['name']}' to {meta['provider']} "
                  f"(provider id: {meta['provider_id']}, status: {meta['status']}).")
            print(f"Poll with: /batch check {meta['name']}")
            return CommandResult.ok()

        # ---- check ----------------------------------------------------------------------
        elif subcmd == "check":
            opts, tokens = _parse_args(rest)
            meta = mgr.resolve(_name_token(rest))
            results_path = os.path.join(mgr.batches_dir, meta["batch_id"], "results.jsonl")
            if meta["status"] in TERMINAL_STATES and os.path.exists(results_path):
                _print_batch_status(meta)
                print("Results already retrieved (results.jsonl).")
                return CommandResult.ok()
            provider_obj = _build_provider(app, meta)
            wait = opts.get("wait", "false").lower() in ("true", "1", "yes")
            meta = await mgr.check(meta, provider_obj, wait=wait)
            extra = ""
            if meta.get("results_count"):
                extra = f"  results: {meta['results_count']} written to results.jsonl"
            if meta.get("cost_usd") is not None:
                extra += f"  exact cost: ${meta['cost_usd']}"
            print(f"Batch '{meta['name']}': status={meta['status']}{extra}")
            return CommandResult.ok()

        # ---- cancel ------------------------------------------------------------------------
        elif subcmd == "cancel":
            meta = mgr.resolve(_name_token(rest))
            provider_obj = _build_provider(app, meta) if meta.get("provider_id") else None
            meta = await mgr.cancel(meta, provider_obj)
            print(f"Cancelled batch '{meta['name']}' (status: {meta['status']}).")
            return CommandResult.ok()

        # ---- retry (Phase 3) -------------------------------------------------------------------
        elif subcmd == "retry":
            print("'/batch retry' is scheduled for Phase 3 (new batch from failed/"
                  "invalid items). For now, extract failed items from results.jsonl "
                  "and stage a new batch with /batch start.")
            return CommandResult.ok()

        # ---- list (alias for /batchlist) ---------------------------------------------------------
        elif subcmd == "list":
            rest_str = command.split(maxsplit=2)[2] if len(command.split(maxsplit=2)) > 2 else ""
            return await cmd_batchlist(ctx, ["/batchlist", *rest_str.split()],
                                       "/batchlist " + rest_str)

        else:
            print(f"Unknown batch subcommand: {subcmd}. Use start, prompt, add, items, "
                  "ids, show, edit, remove, clear, dump, end, abort, run, check, retry, "
                  "list, cancel, or status.")
            return CommandResult.ok()

    except BatchError as e:
        if str(e) == "batch model required":
            return CommandResult.ok()  # capability message already printed
        print(f"Error: {e}")
        return CommandResult.ok()


# ---------------------------------------------------------------------------
# /batchlist — global catalog query (mirrors /session list filters)
# ---------------------------------------------------------------------------

@command("/batchlist", help="List batches from the global catalog",
         args="[all] [ids] [limit=N] [range=start:end] [model=<alias>] [status=<s>] [since=<Nd|Nh|Nm>] [here=true] [var=<varname>]",
         category="batch")
async def cmd_batchlist(ctx: CommandContext, parts: list, command: str) -> CommandResult:
    app = ctx.app
    mgr = get_batch_manager(app)

    limit = 10
    offset = 0
    model_filter = None
    status_filter = None
    target_var = None
    since_dt = None
    ids_only = False
    here_only = False

    args = command.split(maxsplit=1)[1].split() if len(command.split(maxsplit=1)) > 1 else []
    for arg in args:
        param = arg.lower()
        if param == "all":
            limit = None
        elif param == "ids":
            ids_only = True
        elif param in ("here", "here=true"):
            here_only = True
        elif param.startswith("limit="):
            try:
                limit = int(param[6:])
            except ValueError:
                print("Invalid limit value. Using default limit of 10.")
        elif param.startswith("range="):
            try:
                range_raw = param[6:]
                if ":" in range_raw:
                    r_start, r_end = range_raw.split(":", 1)
                    offset = int(r_start) if r_start != "" else 0
                    limit = (int(r_end) - offset) if r_end != "" else None
                else:
                    offset = int(range_raw)
            except ValueError:
                print("Invalid range format. Use range=start:end, range=:end, or "
                      "range=start:. Using default limit of 10.")
        elif param.startswith("model="):
            model_filter = param[6:].lower()
        elif param.startswith("status="):
            status_filter = param[7:].lower()
        elif param.startswith("var="):
            target_var = arg[4:].strip().lstrip("$")
        elif param.startswith("target="):
            target_var = arg[7:].strip().lstrip("$")
        elif param.startswith("since="):
            since_dt = _parse_since(arg[6:])

    records = mgr.list_index()

    # Most recent first, then filters
    records = list(reversed(records))
    if model_filter:
        records = [r for r in records
                   if model_filter in (r.get("model_alias") or "").lower()
                   or model_filter in (r.get("model") or "").lower()]
    if status_filter:
        records = [r for r in records if (r.get("status") or "").lower() == status_filter]
    if since_dt is not None:
        cutoff = since_dt.timestamp()
        records = [r for r in records if (r.get("created_at") or 0) >= cutoff]
    if here_only:
        records = [r for r in records if r.get("workspace") == os.getcwd()]

    total_matched = len(records)
    end = len(records) if limit is None else min(offset + limit, len(records))
    records = records[offset:end]

    batch_ids = [r["batch_id"] for r in records]
    if hasattr(app, "buffer_manager") and app.buffer_manager:
        app.buffer_manager.set_script_var("BATCH_LIST", records, allow_protected=True)
        app.buffer_manager.set_script_var("BATCH_IDS", batch_ids, allow_protected=True)
        if target_var:
            value_for_var = batch_ids if ids_only else records
            app.buffer_manager.set_script_var(target_var, value_for_var, allow_protected=True)

    if not records:
        print("No batches found.")
        return CommandResult.ok()

    filter_parts = []
    if model_filter:
        filter_parts.append(f"model={model_filter}")
    if status_filter:
        filter_parts.append(f"status={status_filter}")
    if since_dt:
        filter_parts.append(f"since={since_dt.strftime('%Y-%m-%d %H:%M')}")
    if here_only:
        filter_parts.append("here")
    if ids_only:
        filter_parts.append("ids")
    filter_str = f"  [{', '.join(filter_parts)}]" if filter_parts else ""

    if ids_only:
        print(f"\nBatch IDs:{filter_str}")
        for bid in batch_ids:
            print(f"  {bid}")
        print()
    else:
        print(f"\nBatches (showing {len(records)} of {total_matched} matched):{filter_str}")
        for idx, r in enumerate(records, 1):
            cost = f"  ${r['cost_usd']:.6f}" if r.get("cost_usd") is not None else ""
            host = f"  via {r['host_backend']}" if r.get("host_backend") else ""
            print(f"  {idx}. {r['batch_id']}  [{r.get('status')}]  "
                  f"items={r.get('item_count', 0)}{cost}{host}")
            print(f"     ├─ name: {r.get('name')}   model: {r.get('model_alias')} "
                  f"({r.get('model')})")
            created = datetime.fromtimestamp(r.get("created_at") or 0)
            print(f"     └─ created: {created.strftime('%Y-%m-%d %H:%M')}")
        print()
    return CommandResult.ok()


def _split_for_add(content: str, split_mode: str) -> list[str]:
    if split_mode == "none":
        return [content.strip()] if content.strip() else []
    return split_text(content, split_mode)
