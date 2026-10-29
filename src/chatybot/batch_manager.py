#! /usr/bin/env python3
"""
batch_manager.py — Batch API subsystem storage, state machine, and providers.

Implements Phase 1 of the Batch API proposal (mistral-batch-poc/batch_proposal_v3.md):

* Dedicated instance directory per batch under ``~/.chatybot/batches/`` plus a
  global ``index.jsonl`` catalog (proposal §4.4, Option 1).
* Crash-safe state machine: draft → staged → submitting → submitted →
  in_progress → completed / failed / expired / cancelled / submit_failed,
  with a mandatory pre-POST fsync of ``meta.json`` (proposal §4.4 rule 6).
* OpenRouter backend ported from the validated POC
  (mistral-batch-poc/run_batch_openrouter.py and spike findings §2):
  - endpoint and model must be serialized BEFORE the requests array;
  - no idempotency dedup → the pre-POST sidecar write is mandatory;
  - top-level metadata is silently dropped by OpenRouter (never relied on);
  - results arrive inline in the completed batch object;
  - exact ``usage.cost`` (USD) and host ``provider`` telemetry at completion.

The conversational session history is never touched: batch data lives entirely
in its own directory tree, decoupled from session stores (proposal §4.4).
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import time
from pathlib import Path
from typing import Any

import aiohttp

from .security.secret_scanner import SecretScanner

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_BATCHES_DIR = "~/.chatybot/batches"

# Batch lifecycle states (proposal §4.4 state machine)
STATUS_DRAFT = "draft"
STATUS_STAGED = "staged"
STATUS_SUBMITTING = "submitting"
STATUS_SUBMITTED = "submitted"
STATUS_IN_PROGRESS = "in_progress"
STATUS_COMPLETED = "completed"
STATUS_FAILED = "failed"
STATUS_EXPIRED = "expired"
STATUS_CANCELLED = "cancelled"
STATUS_SUBMIT_FAILED = "submit_failed"

# States in which the local instance may still be modified (draft workflow)
EDITABLE_STATES = {STATUS_DRAFT}
# States that count against the per-provider open-batch concurrency cap
OPEN_STATES = {STATUS_SUBMITTING, STATUS_SUBMITTED, STATUS_IN_PROGRESS}
# Provider terminal states
TERMINAL_STATES = {STATUS_COMPLETED, STATUS_FAILED, STATUS_EXPIRED, STATUS_CANCELLED}

# OpenRouter status → canonical local status
OPENROUTER_STATUS_MAP = {
    "validating": STATUS_SUBMITTED,
    "in_progress": STATUS_IN_PROGRESS,
    "finalizing": STATUS_IN_PROGRESS,
    "completed": STATUS_COMPLETED,
    "failed": STATUS_FAILED,
    "expired": STATUS_EXPIRED,
    "cancelled": STATUS_CANCELLED,
}

OPENROUTER_API_BASE = "https://openrouter.ai/api/v1"
OPENROUTER_ENDPOINT = "/v1/chat/completions"

# Poll backoff (mirrors the validated POC runner)
POLL_START_SECONDS = 10
POLL_MAX_SECONDS = 60
HTTP_TIMEOUT_SECONDS = 120

_NAME_RE = re.compile(r"[^a-zA-Z0-9_-]")


def sanitize_batch_name(name: str) -> str:
    """Reduce a user-supplied batch name to a filesystem-safe slug."""
    slug = _NAME_RE.sub("_", name.strip()).strip("_.-")
    return slug or "batch"


class BatchError(Exception):
    """Raised for user-facing batch subsystem errors (message is printable)."""


class BatchItem(dict):
    """One staged request item: custom_id, text, origin, added_at."""


# ---------------------------------------------------------------------------
# Providers (Phase 1: OpenRouter; Mistral lands in Phase 2 behind this shape)
# ---------------------------------------------------------------------------

class OpenRouterBatchProvider:
    """Async client for the OpenRouter Batch API (spike-validated behaviors).

    See class docstring of batch_manager for the spike findings that drive
    the design here (no idempotency, no server metadata, inline results).
    """

    name = "openrouter"

    def __init__(self, api_key: str, base_url: str | None = None):
        self.api_key = api_key
        self.base_url = (base_url or OPENROUTER_API_BASE).rstrip("/")

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    @staticmethod
    def _http_error(status: int, body: str, url: str) -> BatchError:
        return BatchError(f"HTTP {status} from {url}: {body[:500]}")

    async def _request(self, session: aiohttp.ClientSession, method: str, url: str,
                       json_body: dict | None = None) -> dict:
        async with session.request(method, url, headers=self._headers(),
                                   json=json_body, timeout=aiohttp.ClientTimeout(total=HTTP_TIMEOUT_SECONDS)) as resp:
            text = await resp.text()
            if resp.status >= 400:
                raise self._http_error(resp.status, text, url)
            return json.loads(text) if text else {}

    async def submit(self, requests: list[dict], model_name: str) -> dict:
        """Submit a new batch. Key order matters: endpoint and model must be
        serialized BEFORE the requests array or OpenRouter returns HTTP 400."""
        payload = {
            "endpoint": OPENROUTER_ENDPOINT,
            "model": model_name,
            "requests": requests,
        }
        async with aiohttp.ClientSession() as session:
            return await self._request(session, "POST", f"{self.base_url}/batches", payload)

    async def get(self, provider_id: str, allow_missing: bool = False) -> dict | None:
        """Fetch one batch record. Right after submission the batch may not be
        queryable yet (202 + id precedes eventual consistency) — treat 404 as
        'not yet' when allow_missing."""
        url = f"{self.base_url}/batches/{provider_id}"
        async with aiohttp.ClientSession() as session:
            async with session.request("GET", url, headers=self._headers(),
                                       timeout=aiohttp.ClientTimeout(total=HTTP_TIMEOUT_SECONDS)) as resp:
                if resp.status == 404 and allow_missing:
                    return None
                text = await resp.text()
                if resp.status >= 400:
                    raise self._http_error(resp.status, text, url)
                return json.loads(text) if text else {}

    async def list(self) -> list[dict]:
        """List batches (list items omit results: 'results': null)."""
        async with aiohttp.ClientSession() as session:
            data = await self._request(session, "GET", f"{self.base_url}/batches")
            return data.get("data") or []

    async def cancel(self, provider_id: str) -> dict:
        async with aiohttp.ClientSession() as session:
            return await self._request(session, "POST", f"{self.base_url}/batches/{provider_id}/cancel")

    # -- normalization -----------------------------------------------------

    @staticmethod
    def normalize_status(batch: dict) -> str:
        return OPENROUTER_STATUS_MAP.get(batch.get("status", ""), batch.get("status", ""))

    @staticmethod
    def counts_of(batch: dict) -> tuple[int | None, int | None, int | None]:
        rc = batch.get("request_counts") or {}
        return rc.get("total"), rc.get("completed"), rc.get("failed")

    @staticmethod
    def normalize_result(entry: dict) -> dict:
        """Map an OpenRouter result line onto the canonical local result shape:
        {custom_id, status_code, content, error}. OpenRouter guarantees exactly
        one of response or error per line, but the nesting has varied."""
        out = {"custom_id": entry.get("custom_id")}
        resp = entry.get("response")
        if isinstance(resp, dict) and "body" in resp:
            body = resp["body"]
            out["status_code"] = resp.get("status_code", 200)
            choices = body.get("choices") or []
            out["content"] = choices[0].get("message", {}).get("content") if choices else None
        elif isinstance(resp, dict) and "choices" in resp:
            out["status_code"] = 200
            choices = resp.get("choices") or []
            out["content"] = choices[0].get("message", {}).get("content") if choices else None
        else:
            out["status_code"] = entry.get("status_code", 500)
            out["content"] = None
            out["error"] = entry.get("error") or json.dumps(entry, ensure_ascii=False)[:500]
        if entry.get("error") and "error" not in out:
            out["error"] = entry["error"]
        return out

    @staticmethod
    def telemetry_of(batch: dict) -> dict:
        """Exact billed cost and host backend, populated only at completion."""
        usage = batch.get("usage") or {}
        return {
            "cost_usd": usage.get("cost"),
            "host_backend": batch.get("provider"),
        }


# ---------------------------------------------------------------------------
# BatchManager
# ---------------------------------------------------------------------------

class BatchManager:
    """Owns batch storage: instance directories, the global index catalog,
    item staging, ID sequencing, security inspection, and state transitions.

    All provider I/O is delegated to a BatchProvider (async); storage is
    synchronous and crash-safe (fsync before the network socket opens).
    """

    def __init__(self, batches_dir: str | None = None, workspace: str | None = None):
        self.batches_dir = self._resolve_batches_dir(batches_dir)
        self.workspace = workspace or os.getcwd()
        self._scanner: SecretScanner | None = None

    # -- paths -------------------------------------------------------------

    @staticmethod
    def _resolve_batches_dir(batches_dir: str | None) -> str:
        env_dir = os.environ.get("CHATYBOT_TEST_BATCHES_DIR")
        return os.path.expanduser(env_dir or batches_dir or DEFAULT_BATCHES_DIR)

    def _ensure_root(self) -> None:
        os.makedirs(self.batches_dir, exist_ok=True)

    def index_path(self) -> str:
        return os.path.join(self.batches_dir, "index.jsonl")

    def _instance_dir(self, batch_id: str) -> str:
        return os.path.join(self.batches_dir, batch_id)

    def _meta_path(self, batch_id: str) -> str:
        return os.path.join(self._instance_dir(batch_id), "meta.json")

    def _staging_path(self, batch_id: str) -> str:
        return os.path.join(self._instance_dir(batch_id), "staging.jsonl")

    def _requests_path(self, batch_id: str) -> str:
        return os.path.join(self._instance_dir(batch_id), "requests.json")

    def _results_path(self, batch_id: str) -> str:
        return os.path.join(self._instance_dir(batch_id), "results.jsonl")

    # -- meta / index ------------------------------------------------------

    @staticmethod
    def _fsync_write(path: str, data: str) -> None:
        """Write text and fsync so the state survives a process kill."""
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())

    def _write_meta(self, meta: dict) -> None:
        meta["updated_at"] = int(time.time())
        self._fsync_write(self._meta_path(meta["batch_id"]),
                          json.dumps(meta, ensure_ascii=False, indent=2))
        self._append_index(meta)

    def _append_index(self, meta: dict) -> None:
        """Append the catalog record for this state; /batchlist dedups by id
        keeping the last occurrence."""
        record = {k: meta.get(k) for k in (
            "batch_id", "provider_id", "name", "provider", "host_backend",
            "model_alias", "model", "prompt", "status", "item_count",
            "created_at", "finalized_at", "cost_usd", "workspace",
        )}
        self._ensure_root()
        with open(self.index_path(), "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
            f.flush()
            os.fsync(f.fileno())

    def read_meta(self, batch_id: str) -> dict:
        path = self._meta_path(batch_id)
        if not os.path.exists(path):
            raise BatchError(f"Batch '{batch_id}' not found.")
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def list_index(self) -> list[dict]:
        """All catalog records, newest-wins per batch_id (append-only log)."""
        path = self.index_path()
        if not os.path.exists(path):
            return []
        latest: dict[str, dict] = {}
        order: list[str] = []
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                bid = rec.get("batch_id")
                if bid not in latest:
                    order.append(bid)
                latest[bid] = rec
        return [latest[bid] for bid in order]

    def find_by_name(self, name: str) -> dict | None:
        """Most recent batch record with the given name (case-insensitive)."""
        matches = [r for r in self.list_index() if r.get("name", "").lower() == name.lower()]
        return matches[-1] if matches else None

    def resolve(self, target: str | None) -> dict:
        """Resolve a batch by instance id (btch-...) or by name."""
        if not target:
            # No target: use the most recently touched non-terminal batch
            candidates = [r for r in self.list_index() if r.get("status") not in TERMINAL_STATES]
            if not candidates:
                raise BatchError("No batch specified and no active batch found. "
                                 "Usage: /batch <start|run|check|...> <name>")
            return self.read_meta(candidates[-1]["batch_id"])
        if os.path.isdir(self._instance_dir(target)):
            return self.read_meta(target)
        rec = self.find_by_name(target)
        if rec is None:
            raise BatchError(f"Batch '{target}' not found. Start one with: /batch start {target}")
        return self.read_meta(rec["batch_id"])

    # -- draft lifecycle ---------------------------------------------------

    def start(self, name: str, model_alias: str, model_name: str, provider: str,
              prompt: str | None = None, clear: bool = False) -> dict:
        """Open a new staging session, or reopen an existing draft/staged batch.

        Reopening a 'staged' batch transitions it back to 'draft' so items can
        be appended; a fresh /batch end re-runs the security scan and re-locks
        the manifest (proposal §4.3 reopen workflow)."""
        slug = sanitize_batch_name(name)
        existing = self.find_by_name(slug)
        if existing is not None:
            meta = self.read_meta(existing["batch_id"])
            if meta["status"] in OPEN_STATES:
                raise BatchError(
                    f"Batch '{slug}' is in flight (status: {meta['status']}). "
                    "Submitted batches cannot be modified. Start a new batch with "
                    f"'/batch start <new_name>' until it completes."
                )
            if meta["status"] in TERMINAL_STATES:
                # Terminal batches are immutable, but their name is reusable:
                # instance IDs are timestamped (btch-<ts>-<name>), so a fresh
                # /batch start creates a new independent instance.
                print(f"Note: batch '{slug}' already reached '{meta['status']}'. "
                      "Starting a fresh batch instance (the old one is preserved in "
                      "/batchlist).")
            else:
                if clear:
                    self.clear_items(meta["batch_id"])
                meta["status"] = STATUS_DRAFT
                if prompt is not None:
                    meta["prompt"] = prompt
                self._write_meta(meta)
                return meta

        ts = int(time.time())
        batch_id = f"btch-{ts}-{slug}"
        while os.path.isdir(self._instance_dir(batch_id)):
            ts += 1
            batch_id = f"btch-{ts}-{slug}"
        meta = {
            "batch_id": batch_id,
            "provider_id": None,
            "name": slug,
            "provider": provider,
            "host_backend": None,
            "model_alias": model_alias,
            "model": model_name,
            "prompt": prompt,
            "status": STATUS_DRAFT,
            "item_count": 0,
            "created_at": int(time.time()),
            "finalized_at": None,
            "cost_usd": None,
            "workspace": self.workspace,
        }
        os.makedirs(self._instance_dir(batch_id), exist_ok=True)
        # Empty staging file so item helpers can assume it exists
        open(self._staging_path(batch_id), "w", encoding="utf-8").close()
        self._write_meta(meta)
        return meta

    def set_prompt(self, meta: dict, prompt: str) -> None:
        if meta["status"] not in EDITABLE_STATES and meta["status"] != STATUS_DRAFT:
            raise BatchError(f"Batch '{meta['name']}' is closed (status: {meta['status']}). "
                             "Reopen it with '/batch start "
                             f"{meta['name']}' first.")
        meta["prompt"] = prompt
        self._write_meta(meta)

    # -- staging items -----------------------------------------------------

    def _read_items(self, batch_id: str) -> list[dict]:
        path = self._staging_path(batch_id)
        if not os.path.exists(path):
            return []
        items = []
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    items.append(json.loads(line))
        return items

    def _append_items(self, meta: dict, items: list[dict]) -> int:
        """Append items to staging.jsonl (flushed per line) and update counts."""
        path = self._staging_path(meta["batch_id"])
        with open(path, "a", encoding="utf-8") as f:
            for item in items:
                f.write(json.dumps(item, ensure_ascii=False) + "\n")
                f.flush()
        meta["item_count"] = self._read_items(meta["batch_id"]).__len__()
        self._write_meta(meta)
        return len(items)

    def add_items(self, meta: dict, texts: list[str], *, id_prefix: str,
                  explicit_id: str | None = None, origin: str = "manual") -> list[dict]:
        """Append one or many items with auto-generated sequenced IDs.

        Direct adds use ``<batch_name>_0001``; filebank ingestion uses
        ``fb<N>_line_0001``; script vars use ``<var_name>_0001``
        (proposal §4.3). Explicit colliding IDs are refused."""
        if meta["status"] not in EDITABLE_STATES:
            if meta["status"] == STATUS_STAGED:
                raise BatchError(
                    f"Staging session is closed. Batch '{meta['name']}' is locked "
                    f"(status: staged).\n"
                    f"• To append more items: run '/batch start {meta['name']}' to reopen "
                    "the draft, add items, then '/batch end'.\n"
                    f"• To submit current batch: run '/batch run {meta['name']}'."
                )
            raise BatchError(
                f"Batch '{meta['name']}' has already been submitted (status: {meta['status']}). "
                "Submitted batches cannot be modified. Start a new batch with "
                f"'/batch start <new_name>'."
            )
        items = self._read_items(meta["batch_id"])
        existing_ids = {it["custom_id"] for it in items}
        # Highest sequence number already used for this prefix (computed once,
        # not O(N^2) across bulk ingestion)
        seq_max = 0
        for cid in existing_ids:
            if cid.startswith(id_prefix):
                suffix = cid[len(id_prefix):]
                if suffix.isdigit():
                    seq_max = max(seq_max, int(suffix))
        new_items = []
        for i, text in enumerate(texts):
            if explicit_id is not None and len(texts) == 1:
                custom_id = explicit_id
                if custom_id in existing_ids:
                    raise BatchError(f"Item ID '{custom_id}' already exists in batch "
                                     f"'{meta['name']}'. Choose a different id= or omit it "
                                     "for auto-generation.")
            elif explicit_id is not None:
                custom_id = f"{explicit_id}_{i + 1:04d}"
                if custom_id in existing_ids:
                    raise BatchError(f"Item ID '{custom_id}' already exists in batch "
                                     f"'{meta['name']}'.")
            else:
                seq_max += 1
                custom_id = f"{id_prefix}{seq_max:04d}"
            existing_ids.add(custom_id)
            new_items.append({
                "custom_id": custom_id,
                "text": text,
                "origin": origin,
                "added_at": int(time.time()),
            })
        self._append_items(meta, new_items)
        return new_items

    def list_items(self, meta: dict, offset: int = 0, limit: int | None = None) -> list[dict]:
        items = self._read_items(meta["batch_id"])
        end = len(items) if limit is None else min(offset + limit, len(items))
        return items[offset:end]

    def show_item(self, meta: dict, custom_id: str) -> dict:
        for item in self._read_items(meta["batch_id"]):
            if item["custom_id"] == custom_id:
                return item
        raise BatchError(f"Item '{custom_id}' not found in batch '{meta['name']}'.")

    def edit_item(self, meta: dict, custom_id: str, new_text: str) -> dict:
        if meta["status"] not in EDITABLE_STATES:
            raise BatchError(f"Items can only be edited while the batch is in draft "
                             f"(status: {meta['status']}).")
        items = self._read_items(meta["batch_id"])
        for item in items:
            if item["custom_id"] == custom_id:
                item["text"] = new_text
                self._rewrite_items(meta["batch_id"], items)
                return item
        raise BatchError(f"Item '{custom_id}' not found in batch '{meta['name']}'.")

    def remove_item(self, meta: dict, custom_id: str) -> dict:
        if meta["status"] not in EDITABLE_STATES:
            raise BatchError(f"Items can only be removed while the batch is in draft "
                             f"(status: {meta['status']}).")
        items = self._read_items(meta["batch_id"])
        remaining = [it for it in items if it["custom_id"] != custom_id]
        if len(remaining) == len(items):
            raise BatchError(f"Item '{custom_id}' not found in batch '{meta['name']}'.")
        self._rewrite_items(meta["batch_id"], remaining)
        meta["item_count"] = len(remaining)
        self._write_meta(meta)
        return meta

    def clear_items(self, batch_id: str) -> None:
        """Empty staging.jsonl to 0 bytes, keeping model and prompt config."""
        self._fsync_write(self._staging_path(batch_id), "")

    def _rewrite_items(self, batch_id: str, items: list[dict]) -> None:
        data = "".join(json.dumps(it, ensure_ascii=False) + "\n" for it in items)
        self._fsync_write(self._staging_path(batch_id), data)

    # -- sealing: security scan + payload build ----------------------------

    def _get_scanner(self) -> SecretScanner:
        if self._scanner is None:
            self._scanner = SecretScanner()
        return self._scanner

    def end(self, meta: dict) -> dict:
        """Run the Secret Scanner over every staged item, compile
        staging.jsonl into the provider payload requests.json, and lock the
        manifest (status: staged). Returns {'hits': [(custom_id, reason)]}."""
        if meta["status"] not in EDITABLE_STATES:
            raise BatchError(f"Batch '{meta['name']}' is already closed (status: {meta['status']}).")
        items = self._read_items(meta["batch_id"])
        if not items:
            raise BatchError(f"Batch '{meta['name']}' has no staged items. Add items first: /batch add ...")
        scanner = self._get_scanner()
        hits = []
        for item in items:
            result = scanner.scan(item["text"] or "")
            if result is not None:
                verdict, reason = result
                hits.append((item["custom_id"], str(verdict), reason))
        if hits:
            raise BatchError(
                "Security scan failed — staging remains open (status: draft).\n"
                "Offending items:\n  " + "\n  ".join(
                    f"{cid}: {reason}" for cid, _v, reason in hits
                ) + "\n"
                "Remove or edit the offending items ('/batch remove <id>', "
                "'/batch edit <id> \"...\"') and run '/batch end' again. "
                "Unresolved security hits cannot be submitted."
            )
        payload = self.build_payload(meta, items)
        self._fsync_write(self._requests_path(meta["batch_id"]),
                          json.dumps(payload, ensure_ascii=False, indent=2))
        meta["status"] = STATUS_STAGED
        meta["item_count"] = len(items)
        self._write_meta(meta)
        return {"hits": [], "item_count": len(items)}

    def build_payload(self, meta: dict, items: list[dict]) -> dict:
        """Compile staged items into the OpenRouter request payload.
        Key order matters: endpoint and model precede the requests array."""
        requests = []
        for item in items:
            messages = []
            if meta.get("prompt"):
                messages.append({"role": "system", "content": meta["prompt"]})
            messages.append({"role": "user", "content": item["text"]})
            requests.append({"custom_id": item["custom_id"], "body": {"messages": messages}})
        return {
            "endpoint": OPENROUTER_ENDPOINT,
            "model": meta["model"],
            "requests": requests,
        }

    def dump_payload(self, meta: dict) -> str:
        """The JSON request body that would be submitted (staged payload if
        available, otherwise a live build from staging)."""
        path = self._requests_path(meta["batch_id"])
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return f.read()
        items = self._read_items(meta["batch_id"])
        if not items:
            raise BatchError(f"Batch '{meta['name']}' has no staged items to dump.")
        return json.dumps(self.build_payload(meta, items), ensure_ascii=False, indent=2)

    def abort(self, meta: dict) -> None:
        """Discard an open (never-submitted) staging session entirely."""
        if meta["status"] in OPEN_STATES or meta["status"] in (STATUS_STAGED,) and meta.get("provider_id"):
            raise BatchError(f"Batch '{meta['name']}' was submitted (status: {meta['status']}) "
                             "and cannot be aborted. Use '/batch cancel' instead.")
        if meta["status"] in TERMINAL_STATES:
            raise BatchError(f"Batch '{meta['name']}' already reached terminal state "
                             f"({meta['status']}); nothing to abort.")
        import shutil
        shutil.rmtree(self._instance_dir(meta["batch_id"]), ignore_errors=True)
        # Catalog prune: rewrite the index without this batch_id
        records = [r for r in self.list_index() if r["batch_id"] != meta["batch_id"]]
        self._rewrite_index(records)

    def _rewrite_index(self, records: list[dict]) -> None:
        data = "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in records)
        self._fsync_write(self.index_path(), data)

    # -- cost & concurrency guards (proposal §4.6) -------------------------

    @staticmethod
    def estimate_cost_usd(meta: dict, items: list[dict], max_tokens: int | None,
                           input_cost_per_mtok: float | None) -> float | None:
        """(input_tokens + max_tokens) x batch_rate. Returns None when the
        model lacks pricing info (budget guard is then skipped with a notice)."""
        if not input_cost_per_mtok:
            return None
        prompt_chars = len(meta.get("prompt") or "") * len(items)
        chars = sum(len(it["text"]) for it in items) + prompt_chars
        est_input_tokens = chars // 4
        est_total = est_input_tokens + (max_tokens or 0) * len(items)
        batch_rate = input_cost_per_mtok / 1_000_000 * 0.5  # 50% batch discount
        return est_total * batch_rate

    def count_open_per_provider(self, provider: str) -> int:
        return sum(1 for r in self.list_index()
                   if r.get("provider") == provider and r.get("status") in OPEN_STATES)

    # -- submission (crash-safe) -------------------------------------------

    def _require_staged(self, meta: dict) -> None:
        if meta["status"] == STATUS_DRAFT:
            raise BatchError(f"Batch '{meta['name']}' is still a draft. Run '/batch end' "
                             "to seal and security-scan it first.")
        if meta["status"] != STATUS_STAGED:
            raise BatchError(f"Batch '{meta['name']}' is not in staged state "
                             f"(status: {meta['status']}).")

    async def run(self, meta: dict, provider_obj: Any, *, force: bool = False,
                  max_cost_usd: float = 5.0, max_open_per_provider: int = 3,
                  max_tokens: int | None = None,
                  input_cost_per_mtok: float | None = None) -> dict:
        """Estimate cost, verify the budget and concurrency caps, then submit.

        The pre-POST sidecar write (status='submitting', fsynced) happens
        strictly BEFORE the network socket opens — OpenRouter does not
        deduplicate batch POSTs (spike finding §2.1), so a crash between the
        write and the POST leaves a reconcilable orphan rather than a silent
        duplicate."""
        if meta["status"] == STATUS_SUBMITTING:
            raise BatchError(
                f"Batch '{meta['name']}' is marked as 'submitting' — a previous "
                "submission may have crashed mid-flight. OpenRouter does not "
                "deduplicate, so a new POST could create a duplicate batch.\n"
                "Reconcile first: run '/batch check {0}' or inspect provider "
                "batches with '/batchlist' and adopt the orphan with "
                "'/batch run {0} adopt=<provider_id>'.".format(meta["name"])
            )

        self._require_staged(meta)
        items = self._read_items(meta["batch_id"])
        estimate = self.estimate_cost_usd(meta, items, max_tokens, input_cost_per_mtok)
        if estimate is not None and estimate > max_cost_usd and not force:
            raise BatchError(
                f"Estimated batch cost ${estimate:.4f} exceeds max_cost_usd "
                f"(${max_cost_usd:.2f}). Refusing. Re-run with force=true to override."
            )

        open_count = self.count_open_per_provider(meta["provider"])
        if open_count >= max_open_per_provider:
            raise BatchError(
                f"Concurrency cap reached: {open_count} open batches for provider "
                f"'{meta['provider']}' (max {max_open_per_provider}). "
                "Wait for completion or raise [batch] max_open_per_provider."
            )

        # Pre-POST fsynced sidecar (mandatory)
        meta["status"] = STATUS_SUBMITTING
        self._write_meta(meta)

        try:
            with open(self._requests_path(meta["batch_id"]), "r", encoding="utf-8") as f:
                payload = json.load(f)
            batch = await provider_obj.submit(payload["requests"], meta["model"])
        except Exception as e:
            meta["status"] = STATUS_SUBMIT_FAILED
            self._write_meta(meta)
            raise BatchError(f"Submission failed (status: submit_failed): {e}") from e

        meta["provider_id"] = batch.get("id")
        meta["status"] = STATUS_SUBMITTED
        self._write_meta(meta)
        return meta

    def adopt_orphan(self, meta: dict, provider_id: str) -> dict:
        """Adopt a provider-side batch into a 'submitting' orphan after a crash
        between the sidecar write and the POST (OpenRouter reconciliation,
        proposal §4.4 rule 3: heuristic match presented for confirmation)."""
        if meta["status"] != STATUS_SUBMITTING:
            raise BatchError(f"Batch '{meta['name']}' is not in 'submitting' state "
                             f"(status: {meta['status']}); nothing to adopt.")
        meta["provider_id"] = provider_id
        meta["status"] = STATUS_SUBMITTED
        self._write_meta(meta)
        return meta

    # -- polling / retrieval -------------------------------------------------

    async def check(self, meta: dict, provider_obj: Any, *, wait: bool = False) -> dict:
        """Poll status once (or with backoff until terminal when wait=true) and
        retrieve completed results inline. On completion, writes
        results.jsonl (one record per custom_id) and records the exact
        usage.cost / provider telemetry into meta and the catalog."""
        if not meta.get("provider_id"):
            raise BatchError(f"Batch '{meta['name']}' has no provider id — it has not "
                             "been submitted. Run '/batch run {0}' first.".format(meta["name"]))
        delay = POLL_START_SECONDS
        batch = await provider_obj.get(meta["provider_id"], allow_missing=True)
        if batch is None:
            if not wait:
                print(f"  Batch not queryable yet (404, eventual consistency). "
                      "Retry '/batch check {0}' shortly.".format(meta["name"]))
                return meta
            while batch is None:
                await asyncio.sleep(delay)
                delay = min(delay * 2, POLL_MAX_SECONDS)
                batch = await provider_obj.get(meta["provider_id"], allow_missing=True)

        status = provider_obj.normalize_status(batch)
        while wait and status not in TERMINAL_STATES:
            await asyncio.sleep(delay)
            delay = min(delay * 2, POLL_MAX_SECONDS)
            batch = await provider_obj.get(meta["provider_id"], allow_missing=True)
            if batch is not None:
                status = provider_obj.normalize_status(batch)

        meta["status"] = status
        total, done, failed = provider_obj.counts_of(batch)
        if done is None:
            done = len(batch.get("results") or [])

        results = []
        if status == STATUS_COMPLETED:
            results = batch.get("results") or []
            if not results:
                refetched = await provider_obj.get(meta["provider_id"])
                results = (refetched or {}).get("results") or []
            normalized = [provider_obj.normalize_result(r) for r in results]
            data = "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in normalized)
            self._fsync_write(self._results_path(meta["batch_id"]), data)
            meta["finalized_at"] = int(time.time())
            telemetry = provider_obj.telemetry_of(batch)
            if telemetry.get("cost_usd") is not None:
                meta["cost_usd"] = telemetry["cost_usd"]
            if telemetry.get("host_backend"):
                meta["host_backend"] = telemetry["host_backend"]
            meta["results_count"] = len(normalized)
        elif status in TERMINAL_STATES:
            meta["finalized_at"] = int(time.time())
            meta["failed_count"] = failed or 0

        self._write_meta(meta)
        return meta

    async def cancel(self, meta: dict, provider_obj: Any) -> dict:
        """Cancel an in-flight batch at the provider and locally."""
        if meta["status"] not in OPEN_STATES:
            raise BatchError(f"Batch '{meta['name']}' is not in flight (status: {meta['status']}).")
        if meta.get("provider_id"):
            await provider_obj.cancel(meta["provider_id"])
        meta["status"] = STATUS_CANCELLED
        meta["finalized_at"] = int(time.time())
        self._write_meta(meta)
        return meta

    def read_results(self, batch_id: str) -> list[dict]:
        path = self._results_path(batch_id)
        if not os.path.exists(path):
            return []
        results = []
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    results.append(json.loads(line))
        return results


# ---------------------------------------------------------------------------
# Ingestion helpers shared with the command layer
# ---------------------------------------------------------------------------

def split_text(content: str, mode: str = "lines") -> list[str]:
    """Split text content into batch items (mirrors /rerank's chunk modes)."""
    if mode == "paragraphs":
        chunks = [p.strip() for p in re.split(r"\n\s*\n", content) if p.strip()]
        return chunks
    # default: lines
    return [line.strip() for line in content.split("\n") if line.strip()]


def make_provider(model_config: dict, api_key: str) -> OpenRouterBatchProvider:
    """Build the Phase 1 OpenRouter provider from a chat_config model entry."""
    base_url = model_config.get("base_url") or OPENROUTER_API_BASE
    return OpenRouterBatchProvider(api_key=api_key, base_url=base_url)
