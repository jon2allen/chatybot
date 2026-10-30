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
    is_empty_result,
    make_provider,
    sanitize_batch_name,
    split_text,
)
from chatybot.commands.context import CommandContext
from chatybot.commands.paging import clean_var_name, parse_paging, parse_since
from chatybot.commands.registry import CommandResult, command

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

BATCH_KV_KEYS = {"id", "var", "filebank", "split", "file", "limit", "range",
                 "force", "adopt", "wait", "clear", "prompt", "model",
                 "temp", "temperature", "max_tokens", "top_p",
                 "freq_penalty", "frequency_penalty",
                 "pres_penalty", "presence_penalty"}

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


def _resolve_batch_alias(app: Any, alias: str) -> dict | None:
    """Validate and return config for a requested model alias, or None on error."""
    try:
        config = app.config_manager.get_model_config(alias)
    except ValueError:
        print(f"Error: model alias '{alias}' not found in chat_config.toml.")
        return None
    if not config.get("batch", False):
        print(f"Error: model '{alias}' is not flagged batch-capable (batch = true).")
        return None
    return config


def _opt_bool(opts: dict[str, str], key: str, default: bool = False) -> bool:
    """Extract a boolean option from CLI options dict."""
    val = opts.get(key)
    if val is None:
        return default
    return val.strip().lower() in ("true", "1", "yes")


def _preview(text: str | None, max_len: int = 60) -> str:
    """Truncate text for CLI preview display."""
    if not text:
        return ""
    return text[:max_len] + "..." if len(text) > max_len else text


_parse_paging = parse_paging


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
    trace_raw_payload = getattr(app, "trace_raw_payload", False)
    logging_manager = getattr(app, "logging_manager", None)
    return make_provider(
        model_config,
        api_key,
        trace_raw_payload=trace_raw_payload,
        logging_manager=logging_manager,
    )


# Option keys each consuming subcommand may parse. Keeping these tight per
# subcommand means free text can never lose a token that merely looks like an
# unrelated subcommand's option (e.g. '/batch add ... model=x' stays text).
SAMPLING_KEYS = {"temp", "temperature", "max_tokens", "top_p",
                 "freq_penalty", "frequency_penalty",
                 "pres_penalty", "presence_penalty"}
ADD_OPTS = {"id", "var", "filebank", "split", "file"}
CLONE_OPTS = {"prompt", "model", "force"} | SAMPLING_KEYS
START_OPTS = {"model", "clear"} | SAMPLING_KEYS
PROMPT_OPTS = {"file"}
ITEMS_OPTS = {"limit", "range"}
IDS_OPTS = {"var"}
SHOW_OPTS: set[str] = set()
EDIT_OPTS = {"var", "file"}
DUMP_OPTS = {"var"}
RUN_OPTS = {"force", "adopt"}
CHECK_OPTS = {"wait"}
RESULTS_OPTS = {"limit", "range", "var"}
CANCEL_OPTS = {"force"}


def _extract_sampling_params(opts: dict[str, str],
                             model_config: dict | None = None) -> dict[str, Any]:
    """Extract and validate sampling parameters from CLI options with model_config fallback."""
    out: dict[str, Any] = {}
    cfg = model_config or {}

    # temperature
    temp_val = opts.get("temp") if "temp" in opts else opts.get("temperature")
    if temp_val is not None:
        try:
            t = float(temp_val.strip())
            if not (0.0 <= t <= 2.0):
                print(f"Warning: temperature {t} is outside typical range [0.0, 2.0].")
            out["temperature"] = t
        except ValueError:
            print(f"Warning: invalid temperature '{temp_val}', ignoring.")
    elif cfg.get("temperature") is not None:
        out["temperature"] = float(cfg["temperature"])

    # max_tokens
    mt_val = opts.get("max_tokens")
    if mt_val is not None:
        try:
            out["max_tokens"] = int(mt_val.strip())
        except ValueError:
            print(f"Warning: invalid max_tokens '{mt_val}', ignoring.")
    elif cfg.get("max_tokens") is not None:
        out["max_tokens"] = int(cfg["max_tokens"])

    # top_p
    tp_val = opts.get("top_p")
    if tp_val is not None:
        try:
            tp = float(tp_val.strip())
            if not (0.0 <= tp <= 1.0):
                print(f"Warning: top_p {tp} is outside range [0.0, 1.0].")
            out["top_p"] = tp
        except ValueError:
            print(f"Warning: invalid top_p '{tp_val}', ignoring.")
    elif cfg.get("top_p") is not None:
        out["top_p"] = float(cfg["top_p"])

    # frequency_penalty
    fp_val = opts.get("frequency_penalty") if "frequency_penalty" in opts else opts.get("freq_penalty")
    if fp_val is not None:
        try:
            out["frequency_penalty"] = float(fp_val.strip())
        except ValueError:
            print(f"Warning: invalid frequency_penalty '{fp_val}', ignoring.")
    elif cfg.get("freq_penalty") is not None:
        out["frequency_penalty"] = float(cfg["freq_penalty"])
    elif cfg.get("frequency_penalty") is not None:
        out["frequency_penalty"] = float(cfg["frequency_penalty"])

    # presence_penalty
    pp_val = opts.get("presence_penalty") if "presence_penalty" in opts else opts.get("pres_penalty")
    if pp_val is not None:
        try:
            out["presence_penalty"] = float(pp_val.strip())
        except ValueError:
            print(f"Warning: invalid presence_penalty '{pp_val}', ignoring.")
    elif cfg.get("pres_penalty") is not None:
        out["presence_penalty"] = float(cfg["pres_penalty"])
    elif cfg.get("presence_penalty") is not None:
        out["presence_penalty"] = float(cfg["presence_penalty"])

    return out


def _parse_args(rest: str,
                keys: set[str] | None = None) -> tuple[dict[str, str], list[str]]:
    """Split a sub-argument string into key=value options and free tokens.

    Uses shlex so quoted inline prompts and file paths survive intact.
    A token counts as key=value only when its key is in the allowed option
    set (default: all batch keys, used by name-taking subcommands), so item
    text containing '=' is never swallowed."""
    allowed = keys if keys is not None else BATCH_KV_KEYS
    opts: dict[str, str] = {}
    tokens: list[str] = []
    try:
        parts = shlex.split(rest)
    except ValueError:
        parts = rest.split()
    for tok in parts:
        if "=" in tok:
            key, _, val = tok.partition("=")
            if key.lower() in allowed:
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
    if hasattr(app.config_manager, "get_batch_config"):
        return app.config_manager.get_batch_config()
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
    if meta.get("results_count") is not None:
        empty_note = (f" ({meta['empty_results']} empty)"
                      if meta.get("empty_results") else "")
        print(f"  Results:    {meta['results_count']}{empty_note}")
    if meta.get("prompt"):
        prompt_prev = _preview(meta["prompt"], 60)
        print(f"  Prompt:     \"{prompt_prev}\"")
    sampling_parts = []
    if meta.get("temperature") is not None:
        sampling_parts.append(f"temp={meta['temperature']}")
    if meta.get("top_p") is not None:
        sampling_parts.append(f"top_p={meta['top_p']}")
    if meta.get("max_tokens") is not None:
        sampling_parts.append(f"max_tokens={meta['max_tokens']}")
    if meta.get("frequency_penalty") is not None:
        sampling_parts.append(f"freq_penalty={meta['frequency_penalty']}")
    if meta.get("presence_penalty") is not None:
        sampling_parts.append(f"pres_penalty={meta['presence_penalty']}")
    if sampling_parts:
        print(f"  Sampling:   {', '.join(sampling_parts)}")
    created = datetime.fromtimestamp(meta.get("created_at") or 0)
    print(f"  Created:    {created.strftime('%Y-%m-%d %H:%M')}")
    if meta.get("finalized_at"):
        fin = datetime.fromtimestamp(meta["finalized_at"])
        print(f"  Finalized:  {fin.strftime('%Y-%m-%d %H:%M')}")
    print()


_parse_since = parse_since


def _resolve_item_batch(mgr: BatchManager, custom_id: str,
                        tokens: list[str]) -> tuple[dict | None, str | None]:
    """Resolve the batch owning an item ID for show/edit/remove.

    Priority:
      1. An explicit name token that actually contains the item
         (disambiguates duplicate IDs across batches; the token is consumed
         so edit does not treat it as replacement text).
      2. The newest EDITABLE (draft) batch containing the item — edit and
         remove then operate on the draft, while show on a non-draft match
         falls through to (3) and gets a clear lock error.
      3. The newest batch of any status containing the item — this is what
         makes /batch show <item-id> work on completed batches with no name.

    Returns (meta, consumed_name_token) or (None, None) when the item is not
    found anywhere (the caller prints a targeted error)."""
    for tok in tokens:
        if tok == custom_id:
            continue
        rec = mgr.find_by_name(tok)
        if rec is not None:
            meta = mgr.read_meta(rec["batch_id"])
            if any(it["custom_id"] == custom_id
                   for it in mgr.list_items(meta)):
                return meta, tok
    editable = mgr.find_batches_containing(custom_id, editable_only=True)
    if editable:
        return editable[0], None
    any_match = mgr.find_batches_containing(custom_id)
    if any_match:
        return any_match[0], None
    return None, None


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
# ---------------------------------------------------------# ---------------------------------------------------------------------------
# /batch subcommands (modular handlers)
# ---------------------------------------------------------------------------

def _resolve_add_source(app: Any, opts: dict[str, str], tokens: list[str],
                        meta: dict, split_mode: str) -> tuple[list[str], str, str] | None:
    """Resolve texts, origin, and id_prefix from add options or free tokens.

    Returns (texts, origin, id_prefix) or None on validation failure.
    """
    if "filebank" in opts:
        bank_name = f"filebank{opts['filebank']}"
        content = app.buffer_manager.file_banks.get(bank_name, "")
        if not content:
            print(f"Error: {bank_name} is empty. "
                  f"Load it first: /filebank{opts['filebank']} <path>")
            return None
        origin = bank_name
        id_prefix = _id_prefix_for_source("filebank", f"fb{opts['filebank']}", split_mode)
        texts = _split_for_add(content, split_mode)
    elif "var" in opts:
        var_name = clean_var_name(opts["var"])
        value = _get_var_value(app, var_name)
        if value is None:
            print(f"Error: script variable '{var_name}' is not set.")
            return None
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
            return None
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
            return None
        texts = [text]
        origin = "manual"
        id_prefix = f"{sanitize_batch_name(meta['name'])}_"
    if not texts:
        print("Error: no items to add (source was empty after splitting).")
        return None
    return texts, origin, id_prefix


def _print_added_summary(meta: dict, added: list[dict]) -> None:
    """Print confirmation and previews for newly added items."""
    print(f"Added {len(added)} item(s) to '{meta['name']}' "
          f"({meta['item_count']} total):")
    for item in added[:5]:
        preview = (item["text"][:40] + "...") if len(item["text"]) > 40 else item["text"]
        print(f"  {item['custom_id']}: \"{preview}\"")
    if len(added) > 5:
        print(f"  ... and {len(added) - 5} more (list with /batch items)")


async def _sc_status(ctx: CommandContext, mgr: BatchManager, rest: str) -> CommandResult:
    target = _name_token(rest)
    meta = mgr.resolve(target) if target else _try_active_draft(mgr)
    if meta is None:
        print("No batch draft open. Start one with: /batch start <name>")
        print("Catalog: /batchlist")
    else:
        _print_batch_status(meta)
    return CommandResult.ok()


async def _sc_start(ctx: CommandContext, mgr: BatchManager, rest: str) -> CommandResult:
    opts, tokens = _parse_args(rest, keys=START_OPTS)
    if not tokens:
        print("Usage: /batch start <name> [model=<alias>] [temp=<float>] "
              "[max_tokens=<int>] [top_p=<float>] [clear=true]")
        return CommandResult.ok()
    name = tokens[0]

    if "model" in opts:
        req_alias = opts["model"].strip()
        model_config = _resolve_batch_alias(ctx.app, req_alias)
        if model_config is None:
            return CommandResult.ok()
        model_alias = req_alias
    else:
        model_alias, model_config = _require_batch_model(ctx.app)

    # Model-config sampling defaults apply only at CREATION; a
    # plain reopen keeps the batch's existing sampling, and only
    # explicit options on this command line update it.
    will_reopen = mgr.find_by_name(name) is not None
    sampling = _extract_sampling_params(
        opts, None if will_reopen else model_config)
    prompt = _pending_batch_prompt.get("prompt")
    meta = mgr.start(name, model_alias=model_alias,
                     model_name=model_config.get("name", model_alias),
                     provider=(model_config.get("vendor") or "openrouter").lower(),
                     prompt=prompt,
                     clear=_opt_bool(opts, "clear"),
                     **sampling)
    print(f"Opened batch draft '{meta['name']}' (ID: {meta['batch_id']}, "
          f"model: {model_alias})")
    if meta.get("prompt"):
        print(f"  Batch prompt set: \"{_preview(meta['prompt'], 60)}\"")
    if meta.get("temperature") is not None:
        print(f"  Temperature: {meta['temperature']}")
    if _opt_bool(opts, "clear"):
        print("  Staged items cleared.")
    print("  Add items with /batch add, then seal with /batch end.")
    return CommandResult.ok()


async def _sc_clone(ctx: CommandContext, mgr: BatchManager, rest: str) -> CommandResult:
    opts, tokens = _parse_args(rest, keys=CLONE_OPTS)
    if len(tokens) < 2:
        print("Usage: /batch clone <source_batch> <new_name> "
              '[prompt="..."] [model=<alias>] [temp=<float>] [force=true]')
        return CommandResult.ok()
    source_target = tokens[0]
    new_name = tokens[1]

    model_alias = None
    model_name = None
    provider = None
    m_cfg = None
    if "model" in opts:
        req_alias = opts["model"].strip()
        m_cfg = _resolve_batch_alias(ctx.app, req_alias)
        if m_cfg is None:
            return CommandResult.ok()
        model_alias = req_alias
        model_name = m_cfg.get("name", req_alias)
        provider = (m_cfg.get("vendor") or "openrouter").lower()

    prompt = None
    if "prompt" in opts:
        p_raw = opts["prompt"].strip()
        prompt = BUILTIN_PROMPTS.get(p_raw.lower(), p_raw)

    sampling = _extract_sampling_params(opts, m_cfg)
    new_meta = mgr.clone(
        source_target,
        new_name,
        prompt=prompt,
        model_alias=model_alias,
        model_name=model_name,
        provider=provider,
        force=_opt_bool(opts, "force"),
        **sampling,
    )
    print(f"Cloned batch '{source_target}' -> '{new_meta['name']}' "
          f"(ID: {new_meta['batch_id']}, items: {new_meta['item_count']}, "
          f"model: {new_meta['model_alias']}, status: draft)")
    if new_meta.get("prompt"):
        print(f"  Batch prompt: \"{_preview(new_meta['prompt'], 60)}\"")
    if new_meta.get("temperature") is not None:
        print(f"  Temperature: {new_meta['temperature']}")
    print("  Edit items with /batch edit, delete with /batch remove, "
          "add with /batch add, then seal with /batch end.")
    return CommandResult.ok()


async def _sc_prompt(ctx: CommandContext, mgr: BatchManager, rest: str) -> CommandResult:
    if not rest.strip():
        meta = _try_active_draft(mgr)
        current = (meta or {}).get("prompt") or _pending_batch_prompt.get("prompt")
        print(f"Batch prompt: {current!r}" if current
              else "No batch prompt set. Usage: /batch prompt \"<text>\" | "
                   "<template> | file=<path>")
        return CommandResult.ok()
    opts, tokens = _parse_args(rest, keys=PROMPT_OPTS)
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


async def _sc_add(ctx: CommandContext, mgr: BatchManager, rest: str) -> CommandResult:
    opts, tokens = _parse_args(rest, keys=ADD_OPTS)
    # /batch add operates on the active draft (or a sealed staged batch so add_items
    # can informatively instruct how to reopen it with /batch start <name>)
    meta = _try_active_draft(mgr)
    if meta is None:
        candidate = mgr.resolve(None)
        if candidate is not None and candidate.get("status") == "staged":
            meta = candidate
        else:
            print("Error: no batch specified and no active draft found. "
                  "Start one with: /batch start <name>")
            return CommandResult.ok()

    split_mode = opts.get("split", "lines").lower()
    if split_mode not in ("lines", "paragraphs", "none"):
        print(f"Invalid split= mode '{split_mode}'. Use lines, paragraphs, or none.")
        return CommandResult.ok()

    resolved = _resolve_add_source(ctx.app, opts, tokens, meta, split_mode)
    if resolved is None:
        return CommandResult.ok()
    texts, origin, id_prefix = resolved

    added = mgr.add_items(meta, texts, id_prefix=id_prefix,
                          explicit_id=opts.get("id"), origin=origin)
    _print_added_summary(meta, added)
    return CommandResult.ok()


async def _sc_items(ctx: CommandContext, mgr: BatchManager, rest: str) -> CommandResult:
    opts, tokens = _parse_args(rest, keys=ITEMS_OPTS)
    meta = mgr.resolve(_name_token(rest))
    offset, limit = parse_paging(opts)
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


async def _sc_ids(ctx: CommandContext, mgr: BatchManager, rest: str) -> CommandResult:
    opts, tokens = _parse_args(rest, keys=IDS_OPTS)
    meta = mgr.resolve(_name_token(rest))
    items = mgr.list_items(meta)
    ids = [it["custom_id"] for it in items]
    bound = clean_var_name(opts.get("var"), default="BATCH_ITEM_IDS")
    ctx.app.buffer_manager.set_script_var(bound, ids, allow_protected=True)
    print(f"\nItem IDs ({meta['name']}, {len(ids)}):")
    for i in ids:
        print(f"  {i}")
    print(f"(exported to ${{{bound}}})\n")
    return CommandResult.ok()


async def _sc_show(ctx: CommandContext, mgr: BatchManager, rest: str) -> CommandResult:
    opts, tokens = _parse_args(rest, keys=SHOW_OPTS)
    if not tokens:
        print("Usage: /batch show <item-id> [batch-name]  "
              "(or /batch show <batch-name> for a batch overview)")
        return CommandResult.ok()
    first = tokens[0]
    # Name-only form: batch overview + its item IDs
    if len(tokens) == 1 and mgr.find_by_name(first) is not None:
        meta = mgr.resolve(first)
        _print_batch_status(meta)
        ids = [it["custom_id"] for it in mgr.list_items(meta)]
        print(f"Staged item IDs: {', '.join(ids)}" if ids else "No staged items.")
        print("Inspect one with: /batch show <item-id>")
        return CommandResult.ok()
    custom_id = first
    meta, _consumed = _resolve_item_batch(mgr, custom_id, tokens[1:])
    if meta is None:
        active = _try_active_draft(mgr)
        if active is not None and any(
                it["custom_id"] == custom_id
                for it in mgr.list_items(active)):
            meta = active
        else:
            print(f"Error: item '{custom_id}' not found in any batch. "
                  "List a batch's items with: /batch items <name>")
            return CommandResult.ok()
    item = mgr.show_item(meta, custom_id)
    result = mgr.get_result(meta["batch_id"], custom_id)
    status_note = (f"   Status: {result['status_code']}"
                   if result is not None else "")
    print(f"\nItem: {item['custom_id']}  (batch: {meta['name']})")
    print(f"Origin: {item.get('origin', 'manual')}   "
          f"Chars: {len(item['text'])}{status_note}")
    print("-" * 60)
    print("[Input]:")
    print(item["text"])
    if result is not None:
        print("-" * 60)
        if result.get("error"):
            print("[Error]:")
            print(result["error"])
        else:
            print(f"[Result]:   (status {result['status_code']})")
            print(result.get("content") or "(empty completion)")
    elif mgr.read_results(meta["batch_id"]):
        print("-" * 60)
        print(f"[Result]: not retrieved for this item "
              "(no record in results.jsonl).")
    else:
        print(f"\n(No results yet — batch status: {meta['status']}. "
              f"Run '/batch check {meta['name']}' to poll/retrieve.)")
    print()
    return CommandResult.ok()


async def _sc_edit(ctx: CommandContext, mgr: BatchManager, rest: str) -> CommandResult:
    opts, tokens = _parse_args(rest, keys=EDIT_OPTS)
    if not tokens:
        print("Usage: /batch edit <id> <text | var=NAME | file=PATH> [name]")
        return CommandResult.ok()
    custom_id = tokens[0]
    meta, consumed = _resolve_item_batch(mgr, custom_id, tokens[1:])
    if meta is None:
        print(f"Error: item '{custom_id}' not found in any batch. "
              "List a batch's items with: /batch items <name>")
        return CommandResult.ok()
    if "var" in opts:
        value = _get_var_value(ctx.app, clean_var_name(opts["var"]))
        new_text = "" if value is None else str(value)
    elif "file" in opts:
        with open(os.path.expanduser(opts["file"]), "r", encoding="utf-8") as f:
            new_text = f.read().strip()
    else:
        text_tokens = [t for t in tokens[1:] if t != consumed]
        new_text = _text_from_tokens(text_tokens)
    if not new_text:
        print("Error: empty replacement text.")
        return CommandResult.ok()
    mgr.edit_item(meta, custom_id, new_text)
    print(f"Updated item '{custom_id}' in '{meta['name']}'.")
    return CommandResult.ok()


async def _sc_remove(ctx: CommandContext, mgr: BatchManager, rest: str) -> CommandResult:
    opts, tokens = _parse_args(rest, keys=SHOW_OPTS)
    if not tokens:
        print("Usage: /batch remove <id> [name]")
        return CommandResult.ok()
    custom_id = tokens[0]
    meta, _consumed = _resolve_item_batch(mgr, custom_id, tokens[1:])
    if meta is None:
        print(f"Error: item '{custom_id}' not found in any batch. "
              "List a batch's items with: /batch items <name>")
        return CommandResult.ok()
    mgr.remove_item(meta, custom_id)
    print(f"Removed item '{custom_id}' from '{meta['name']}' "
          f"({meta['item_count']} items remain).")
    return CommandResult.ok()


async def _sc_clear(ctx: CommandContext, mgr: BatchManager, rest: str) -> CommandResult:
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


async def _sc_dump(ctx: CommandContext, mgr: BatchManager, rest: str) -> CommandResult:
    opts, tokens = _parse_args(rest, keys=DUMP_OPTS)
    meta = mgr.resolve(_name_token(rest))
    payload = mgr.dump_payload(meta)
    print(f"\nBatch payload for '{meta['name']}':")
    print(payload)
    bound = clean_var_name(opts.get("var"), default="BATCH_PAYLOAD")
    ctx.app.buffer_manager.set_script_var(bound, payload, allow_protected=True)
    print(f"\n(payload bound to ${{{bound}}})\n")
    return CommandResult.ok()


async def _sc_end(ctx: CommandContext, mgr: BatchManager, rest: str) -> CommandResult:
    meta = mgr.resolve(_name_token(rest))
    result = mgr.end(meta)
    print(f"Sealed batch '{meta['name']}': {result['item_count']} items scanned "
          "(no security hits), payload compiled to requests.json.")
    print(f"Status: staged. Submit with /batch run {meta['name']}")
    return CommandResult.ok()


async def _sc_abort(ctx: CommandContext, mgr: BatchManager, rest: str) -> CommandResult:
    meta = mgr.resolve(_name_token(rest))
    mgr.abort(meta)
    print(f"Aborted and deleted batch '{meta['name']}'.")
    return CommandResult.ok()


async def _sc_run(ctx: CommandContext, mgr: BatchManager, rest: str) -> CommandResult:
    opts, tokens = _parse_args(rest, keys=RUN_OPTS)
    meta = mgr.resolve(_name_token(rest))
    if "adopt" in opts:
        mgr.adopt_orphan(meta, opts["adopt"])
        print(f"Adopted provider batch {opts['adopt']} into '{meta['name']}' "
              "(status: submitted). Poll with /batch check.")
        return CommandResult.ok()
    batch_model_config = _batch_model_config(ctx.app, meta)
    provider_obj = _build_provider(ctx.app, meta)
    batch_cfg = _batch_config(ctx.app)
    force = _opt_bool(opts, "force")

    items = mgr.list_items(meta)
    effective_max_tokens = (meta.get("max_tokens")
                            if meta.get("max_tokens") is not None
                            else batch_model_config.get("max_tokens"))
    estimate = mgr.estimate_cost_usd(meta, items,
                                     effective_max_tokens,
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
        max_tokens=effective_max_tokens,
        input_cost_per_mtok=batch_model_config.get("input_cost_per_mtok"),
        precomputed_estimate=estimate,
    )
    print(f"Submitted batch '{meta['name']}' to {meta['provider']} "
          f"(provider id: {meta['provider_id']}, status: {meta['status']}).")
    print(f"Poll with: /batch check {meta['name']}")
    return CommandResult.ok()


async def _sc_check(ctx: CommandContext, mgr: BatchManager, rest: str) -> CommandResult:
    opts, tokens = _parse_args(rest, keys=CHECK_OPTS)
    meta = mgr.resolve(_name_token(rest))
    results_path = os.path.join(mgr.batches_dir, meta["batch_id"], "results.jsonl")
    if meta["status"] in TERMINAL_STATES and os.path.exists(results_path):
        _print_batch_status(meta)
        print("Results already retrieved (results.jsonl).")
        return CommandResult.ok()
    if meta["status"] == "cancelled":
        print(f"Batch '{meta['name']}' was cancelled locally and is not "
              "polled anymore. The remote job may still have run to "
              "completion and billed at batch rates.")
        return CommandResult.ok()
    provider_obj = _build_provider(ctx.app, meta)
    wait = _opt_bool(opts, "wait")
    meta = await mgr.check(meta, provider_obj, wait=wait)
    extra = ""
    if meta.get("results_count"):
        extra = f"  results: {meta['results_count']} written to results.jsonl"
        if meta.get("empty_results"):
            extra += f" ({meta['empty_results']} empty)"
    if meta.get("cost_usd") is not None:
        extra += f"  exact cost: ${meta['cost_usd']}"
    print(f"Batch '{meta['name']}': status={meta['status']}{extra}")
    return CommandResult.ok()


async def _sc_results(ctx: CommandContext, mgr: BatchManager, rest: str) -> CommandResult:
    opts, tokens = _parse_args(rest, keys=RESULTS_OPTS)
    meta = mgr.resolve(_name_token(rest))
    records = mgr.read_results(meta["batch_id"])
    if not records:
        print(f"No results retrieved yet for '{meta['name']}' "
              f"(status: {meta['status']}).")
        print("Run '/batch check {0}' to poll/retrieve.".format(meta["name"]))
        return CommandResult.ok()
    offset, limit = parse_paging(opts)
    end = len(records) if limit is None else min(offset + limit, len(records))
    page = records[offset:end]

    bound = clean_var_name(opts.get("var"), default="BATCH_RESULTS")
    ctx.app.buffer_manager.set_script_var(bound, records, allow_protected=True)

    empty_now = sum(1 for record in records if is_empty_result(record))
    empty_note = f", {empty_now} empty" if empty_now else ""
    print(f"\n[Results: {meta['name']} — showing {len(page)} of "
          f"{len(records)} records{empty_note}, status: {meta['status']}]")
    for i, record in enumerate(page, offset + 1):
        print("-" * 60)
        status = record.get("status_code", "?")
        print(f"#{i}  {record.get('custom_id')}   [{status}]")
        if record.get("error"):
            print(f"[Error]: {record['error']}")
        else:
            print(record.get("content") or "(empty completion)")
    print("-" * 60)
    print(f"(all {len(records)} records exported to ${{{bound}}})\n")
    return CommandResult.ok()


async def _sc_cancel(ctx: CommandContext, mgr: BatchManager, rest: str) -> CommandResult:
    opts, tokens = _parse_args(rest, keys=CANCEL_OPTS)
    meta = mgr.resolve(_name_token(rest))
    provider_obj = _build_provider(ctx.app, meta) if meta.get("provider_id") else None
    force = _opt_bool(opts, "force")
    meta = await mgr.cancel(meta, provider_obj, force=force)
    print(f"Cancelled batch '{meta['name']}' (status: {meta['status']}).")
    return CommandResult.ok()


async def _sc_retry(ctx: CommandContext, mgr: BatchManager, rest: str) -> CommandResult:
    print("'/batch retry' is scheduled for Phase 3 (new batch from failed/"
          "invalid items). For now, extract failed items from results.jsonl "
          "and stage a new batch with /batch start.")
    return CommandResult.ok()


async def _sc_list(ctx: CommandContext, mgr: BatchManager, rest: str) -> CommandResult:
    return await cmd_batchlist(ctx, ["/batchlist", *rest.split()],
                               "/batchlist " + rest)


_SUBCOMMAND_DISPATCH = {
    "status": _sc_status,
    "": _sc_status,
    "start": _sc_start,
    "clone": _sc_clone,
    "prompt": _sc_prompt,
    "add": _sc_add,
    "items": _sc_items,
    "ids": _sc_ids,
    "show": _sc_show,
    "edit": _sc_edit,
    "remove": _sc_remove,
    "del": _sc_remove,
    "delete": _sc_remove,
    "clear": _sc_clear,
    "reset": _sc_clear,
    "dump": _sc_dump,
    "end": _sc_end,
    "abort": _sc_abort,
    "run": _sc_run,
    "check": _sc_check,
    "results": _sc_results,
    "cancel": _sc_cancel,
    "retry": _sc_retry,
    "list": _sc_list,
}


@command("/batch", help="Batch API jobs: stage, seal, submit, poll, retrieve",
         args="<status|start|clone|prompt|add|items|ids|show|edit|remove|clear|dump|end|abort|run|check|results|retry|list|cancel> [name] [key=value ...]",
         category="batch")
async def cmd_batch(ctx: CommandContext, parts: list, command: str) -> CommandResult:
    app = ctx.app
    mgr = get_batch_manager(app)
    rest_all = command.split(maxsplit=2)
    subcmd = (parts[1].lower() if len(parts) > 1 else "status")
    rest = rest_all[2] if len(rest_all) > 2 else ""

    handler = _SUBCOMMAND_DISPATCH.get(subcmd)
    if not handler:
        print(f"Unknown batch subcommand: {subcmd}. Use start, clone, prompt, add, items, "
              "ids, show, edit, remove, clear, dump, end, abort, run, check, "
              "results, retry, list, cancel, or status.")
        return CommandResult.ok()

    try:
        return await handler(ctx, mgr, rest)
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
            _, limit = parse_paging({"limit": arg[6:]}, default_limit=limit)
        elif param.startswith("range="):
            offset, limit = parse_paging({"range": arg[6:]}, default_limit=limit)
        elif param.startswith("model="):
            model_filter = param[6:].lower()
        elif param.startswith("status="):
            status_filter = param[7:].lower()
        elif param.startswith("var="):
            target_var = clean_var_name(arg[4:])
        elif param.startswith("target="):
            target_var = clean_var_name(arg[7:])
        elif param.startswith("since="):
            since_dt = parse_since(arg[6:])

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
            empty = (f"  {r['empty_results']} empty"
                     if r.get("empty_results") else "")
            print(f"  {idx}. {r['batch_id']}  [{r.get('status')}]  "
                  f"items={r.get('item_count', 0)}{empty}{cost}{host}")
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
