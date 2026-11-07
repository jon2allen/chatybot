#! /usr/bin/env python3
"""
batch_manager.py - Batch API subsystem storage, state machine, and providers.

Implements Phase 1 (OpenRouter) and Phase 2 (Mistral inline batching) of the
Batch API proposal (mistral-batch-poc/batch_proposal_v3.md):

* Dedicated instance directory per batch under ``~/.local/share/chatybot/batches/`` plus a
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
import errno
import json
import os
import re
import time
from typing import Any

import aiohttp

from .payload_trace import (
    _mask_key,
    print_request_payload,
    print_response_payload,
    trace_enabled,
)
from .security.secret_scanner import SecretScanner

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_BATCHES_DIR = "~/.local/share/chatybot/batches"

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
STATUS_SUBMIT_UNKNOWN = "submit_unknown"

# States in which the local instance may still be modified (draft workflow)
EDITABLE_STATES = {STATUS_DRAFT}
# States that count against the per-provider open-batch concurrency cap
OPEN_STATES = {STATUS_SUBMITTED, STATUS_IN_PROGRESS}
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

# Mistral status -> canonical local status (proposal §3; CANCELLATION_REQUESTED
# is an intermediate state after POST .../cancel while workers shut down).
MISTRAL_STATUS_MAP = {
    "QUEUED": STATUS_SUBMITTED,
    "RUNNING": STATUS_IN_PROGRESS,
    "SUCCESS": STATUS_COMPLETED,
    "FAILED": STATUS_FAILED,
    "TIMEOUT_EXCEEDED": STATUS_EXPIRED,
    "CANCELLATION_REQUESTED": STATUS_IN_PROGRESS,
    "CANCELLED": STATUS_CANCELLED,
}

MISTRAL_API_BASE = "https://api.mistral.ai/v1"
MISTRAL_CHAT_ENDPOINT = "/v1/chat/completions"
MISTRAL_INLINE_LIMIT = 10_000

# Provider payload limits and warning thresholds (bytes)
# OpenRouter enforces a hard 200 MB limit (HTTP 413) on inline batch payloads.
OPENROUTER_PAYLOAD_LIMIT_BYTES = 200 * 1024 * 1024
OPENROUTER_PAYLOAD_WARN_BYTES = 100 * 1024 * 1024

# Mistral inline batch endpoint (POST /v1/batch/jobs) is subject to edge reverse proxy
# body size limits (~2-4 MB). Uncompressed base64 payloads over ~2 MB are at risk of
# edge HTTP 400 Bad Request rejection.
MISTRAL_INLINE_WARN_BYTES = 2 * 1024 * 1024
MISTRAL_INLINE_MAX_RECOMMENDED_BYTES = 4 * 1024 * 1024

# Poll backoff and timeout caps
POLL_START_SECONDS = 10
POLL_MAX_SECONDS = 60
HTTP_TIMEOUT_SECONDS = 120
MAX_CONSECUTIVE_404 = 5
MAX_WAIT_SECONDS = 86_400  # 24 hours
DEFAULT_BATCH_OUTPUT_TOKENS = 1000

_NAME_RE = re.compile(r"[^a-zA-Z0-9_-]")


def sanitize_batch_name(name: str) -> str:
    """Reduce a user-supplied batch name to a filesystem-safe slug."""
    slug = _NAME_RE.sub("_", name.strip()).strip("_.-")
    return slug or "batch"


class BatchError(Exception):
    """Raised for user-facing batch subsystem errors (message is printable)."""


class BatchItem(dict):
    """One staged request item: custom_id, text, origin, added_at."""


def is_empty_result(record: dict) -> bool:
    """True when a completion record succeeded (status 200) but returned no content."""
    return not record.get("error") and not (record.get("content") or "").strip()


# ---------------------------------------------------------------------------
# Providers (Phase 1: OpenRouter; Mistral lands in Phase 2 behind this shape)
# ---------------------------------------------------------------------------

async def _provider_call(fn: Any, *args: Any, session: aiohttp.ClientSession | None = None, **kwargs: Any) -> Any:
    """Invoke provider method passing session if accepted, otherwise omitting it."""
    import inspect
    sig = inspect.signature(fn)
    call_kwargs = dict(kwargs)
    if session is not None and ("session" in sig.parameters or any(p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values())):
        call_kwargs["session"] = session
    return await fn(*args, **call_kwargs)


class BaseBatchProvider:
    """Base client for batch providers with shared networking, headers,
    request tracing, error formatting, and result normalization."""

    name: str = ""
    supports_cancel: bool = False
    DEFAULT_BASE_URL: str = ""

    def __init__(self, api_key: str, base_url: str | None = None, *,
                 trace_raw_payload: bool = False,
                 logging_manager: Any = None):
        self.api_key = api_key
        self.base_url = (base_url or self.DEFAULT_BASE_URL).rstrip("/")
        self.trace_raw_payload = trace_raw_payload
        self.logging_manager = logging_manager

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    @classmethod
    def _http_error(cls, status: int, body: str, url: str) -> BatchError:
        extra_hint = ""
        if cls.name == "mistral" and status == 400 and ("<html" in body.lower() or "<!doctype" in body.lower()):
            extra_hint = (
                "\nHint: Mistral's edge gateway rejected the request with HTML 400 Bad Request. "
                "This usually indicates the inline batch payload exceeded the HTTP POST size limit "
                "(typically caused by embedding large or uncompressed base64 images). "
                "Ensure images are compressed (e.g., JPEG under ~1.5 MB) or reduce batch size."
            )
        return BatchError(f"HTTP {status} from {url}: {body[:500]}{extra_hint}")

    async def _request(self, session: aiohttp.ClientSession, method: str, url: str,
                       json_body: dict | None = None,
                       allow_missing_404: bool = False) -> dict | None:
        if trace_enabled(self.trace_raw_payload):
            if json_body is not None:
                print_request_payload(
                    url,
                    json_body,
                    self.api_key,
                    logging_manager=self.logging_manager,
                    label=f"Batch API Request Payload ({method}):",
                )
            else:
                masked_key = _mask_key(self.api_key)
                header_line = f"Headers: {{'Authorization': 'Bearer {masked_key}', 'Content-Type': 'application/json'}}"
                trace_text = (
                    f"Batch API Request ({method}):\n"
                    f"-----------------------------\n"
                    f"{method} {url}\n"
                    f"{header_line}\n"
                    f"---- end of payload ---"
                )
                print(trace_text)
                if self.logging_manager and hasattr(self.logging_manager, "log_message"):
                    try:
                        self.logging_manager.log_message(trace_text)
                    except Exception:
                        pass

        async with session.request(method, url, headers=self._headers(),
                                   json=json_body, timeout=aiohttp.ClientTimeout(total=HTTP_TIMEOUT_SECONDS)) as resp:
            if resp.status == 404 and allow_missing_404:
                if trace_enabled(self.trace_raw_payload):
                    print_response_payload(
                        resp.status,
                        "(404 Not Found - batch not queryable yet)",
                        logging_manager=self.logging_manager,
                        label=f"Batch API Response Payload ({method} {url}):",
                    )
                return None

            text = await resp.text()
            if trace_enabled(self.trace_raw_payload):
                print_response_payload(
                    resp.status,
                    text,
                    logging_manager=self.logging_manager,
                    label=f"Batch API Response Payload ({method} {url}):",
                )
            if resp.status >= 400:
                raise self._http_error(resp.status, text, url)
            return json.loads(text) if text else {}

    async def _download_text(self, url: str, session: aiohttp.ClientSession | None = None) -> str:
        """Download raw text content (e.g. from Files API) with tracing and error handling."""
        if trace_enabled(self.trace_raw_payload):
            masked_key = _mask_key(self.api_key)
            trace_text = (
                f"Batch API Request (GET):\n"
                f"-----------------------------\n"
                f"GET {url}\n"
                f"Headers: {{'Authorization': 'Bearer {masked_key}', 'Content-Type': 'application/json'}}\n"
                f"---- end of payload ---"
            )
            print(trace_text)
            if self.logging_manager and hasattr(self.logging_manager, "log_message"):
                try:
                    self.logging_manager.log_message(trace_text)
                except Exception:
                    pass

        async def _do_download(s: aiohttp.ClientSession) -> str:
            async with s.get(url, headers=self._headers(),
                             timeout=aiohttp.ClientTimeout(total=HTTP_TIMEOUT_SECONDS)) as resp:
                text = await resp.text()
                if trace_enabled(self.trace_raw_payload):
                    print_response_payload(
                        resp.status,
                        text,
                        logging_manager=self.logging_manager,
                        label=f"Batch API Response Payload (GET {url}):",
                    )
                if resp.status >= 400:
                    raise self._http_error(resp.status, text, url)
                return text

        if session is not None:
            return await _do_download(session)
        async with aiohttp.ClientSession() as s:
            return await _do_download(s)

    @staticmethod
    def normalize_result(entry: dict) -> dict:
        """Map a provider result line onto the canonical local result shape:
        {custom_id, status_code, content, error}."""
        out: dict[str, Any] = {"custom_id": entry.get("custom_id")}
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
            output = entry.get("output")
            if isinstance(output, dict):
                choices = output.get("choices") or []
                out["status_code"] = 200
                out["content"] = choices[0].get("message", {}).get("content") if choices else None
            else:
                out["status_code"] = entry.get("status_code", 500)
                out["content"] = None
                out["error"] = entry.get("error") or json.dumps(entry, ensure_ascii=False)[:500]
        if entry.get("error") and "error" not in out:
            out["error"] = entry["error"]
        return out


class OpenRouterBatchProvider(BaseBatchProvider):
    """Async client for the OpenRouter Batch API (spike-validated behaviors).

    See class docstring of batch_manager for the spike findings that drive
    the design here (no idempotency, no server metadata, inline results).
    """

    name = "openrouter"
    DEFAULT_BASE_URL = OPENROUTER_API_BASE
    supports_cancel = False

    async def submit(self, requests: list[dict], model_name: str, *,
                     session: aiohttp.ClientSession | None = None) -> dict:
        """Submit a new batch. Key order matters: endpoint and model must be
        serialized BEFORE the requests array or OpenRouter returns HTTP 400."""
        payload = {
            "endpoint": OPENROUTER_ENDPOINT,
            "model": model_name,
            "requests": requests,
        }
        if session is not None:
            return await self._request(session, "POST", f"{self.base_url}/batches", payload)
        async with aiohttp.ClientSession() as s:
            return await self._request(s, "POST", f"{self.base_url}/batches", payload)

    async def get(self, provider_id: str, allow_missing: bool = False,
                  session: aiohttp.ClientSession | None = None) -> dict | None:
        """Fetch one batch record. Right after submission the batch may not be
        queryable yet (202 + id precedes eventual consistency) - treat 404 as
        'not yet' when allow_missing."""
        url = f"{self.base_url}/batches/{provider_id}"
        if session is not None:
            return await self._request(session, "GET", url, allow_missing_404=allow_missing)
        async with aiohttp.ClientSession() as s:
            return await self._request(s, "GET", url, allow_missing_404=allow_missing)

    async def list(self, session: aiohttp.ClientSession | None = None) -> list[dict]:
        """List batches (list items omit results: 'results': null)."""
        if session is not None:
            data = await self._request(session, "GET", f"{self.base_url}/batches")
            return data.get("data") or []
        async with aiohttp.ClientSession() as s:
            data = await self._request(s, "GET", f"{self.base_url}/batches")
            return data.get("data") or []

    async def cancel(self, provider_id: str | None = None,
                     session: aiohttp.ClientSession | None = None) -> dict:
        raise BatchError(
            "OpenRouter does not support cancelling a submitted batch - it "
            "runs to completion (or expires within 24 hours) and bills at "
            "batch rates. Use '/batch cancel <name> force=true' to disown it "
            "locally."
        )

    # -- normalization -----------------------------------------------------

    @staticmethod
    def normalize_status(batch: dict) -> str:
        return OPENROUTER_STATUS_MAP.get(batch.get("status", ""), batch.get("status", ""))

    @staticmethod
    def counts_of(batch: dict) -> tuple[int | None, int | None, int | None]:
        rc = batch.get("request_counts") or {}
        return rc.get("total"), rc.get("completed"), rc.get("failed")

    @staticmethod
    def telemetry_of(batch: dict) -> dict:
        """Exact billed cost and host backend, populated only at completion."""
        usage = batch.get("usage") or {}
        return {
            "cost_usd": usage.get("cost"),
            "host_backend": batch.get("provider"),
        }

    async def fetch_results(self, batch: dict, provider_id: str | None = None,
                            session: aiohttp.ClientSession | None = None) -> list[dict]:
        """Return inline results from the batch object, re-fetching if empty.

        OpenRouter embeds results directly in the completed batch object;
        a second GET is needed when the first poll caught completion before
        the results array was populated (spike finding §2.3)."""
        results = batch.get("results") or []
        if not results:
            bid = batch.get("id") or provider_id
            if bid:
                refetched = await self.get(bid, session=session)
                results = (refetched or {}).get("results") or []
        return results


# ---------------------------------------------------------------------------
# Mistral Batch provider (Phase 2 - inline batching only)
# ---------------------------------------------------------------------------

class MistralBatchProvider(BaseBatchProvider):
    """Async client for the Mistral Batch API (inline batching, Phase 2).

    Mistral differs from OpenRouter in several ways (proposal §3, verified
    2026-11-04 against live docs):

    - Dual ingestion: inline (<10k items) or file upload (up to ~1M).
      Phase 2 implements **inline only**; file upload is deferred. Batches
      exceeding ``MISTRAL_INLINE_LIMIT`` are refused with a clear message.
    - Results are retrieved via the Files API (``output_file`` / ``error_file``
      file IDs), not inline in the batch object. ``fetch_results`` downloads
      and parses them.
    - Cancellation is supported (``POST /v1/batch/jobs/{id}/cancel``); the
      job transitions through ``CANCELLATION_REQUESTED`` before ``CANCELLED``.
    - Metadata is persisted server-side (enables ``client_token``-based
      orphan reconciliation, unlike OpenRouter's heuristic match).
    - No exact ``usage.cost``; token counts are returned in result lines but
      cost must be computed from rates (future enhancement - returns None).
    """

    name = "mistral"
    DEFAULT_BASE_URL = MISTRAL_API_BASE
    supports_cancel = True

    async def submit(self, requests: list[dict], model_name: str, *,
                     metadata: dict | None = None,
                     session: aiohttp.ClientSession | None = None) -> dict:
        """Submit a new inline batch job.

        Mistral supports inline batching for fewer than 10,000 requests;
        larger batches require the file-upload path (not yet implemented).
        Metadata is persisted server-side, enabling client_token reconciliation.
        """
        if len(requests) > MISTRAL_INLINE_LIMIT:
            raise BatchError(
                f"Inline batch limit exceeded: {len(requests)} items (max "
                f"{MISTRAL_INLINE_LIMIT}). The file-upload path is not yet "
                "implemented (Phase 2b). Split the batch into smaller runs "
                "or use fewer items."
            )
        payload: dict[str, Any] = {
            "model": model_name,
            "endpoint": MISTRAL_CHAT_ENDPOINT,
            "requests": requests,
        }
        if metadata:
            payload["metadata"] = metadata
        if session is not None:
            return await self._request(session, "POST",
                                        f"{self.base_url}/batch/jobs", payload)
        async with aiohttp.ClientSession() as s:
            return await self._request(s, "POST",
                                        f"{self.base_url}/batch/jobs", payload)

    async def get(self, provider_id: str, allow_missing: bool = False,
                  session: aiohttp.ClientSession | None = None) -> dict | None:
        """Fetch one batch job record by its UUID."""
        url = f"{self.base_url}/batch/jobs/{provider_id}"
        if session is not None:
            return await self._request(session, "GET", url,
                                        allow_missing_404=allow_missing)
        async with aiohttp.ClientSession() as s:
            return await self._request(s, "GET", url,
                                        allow_missing_404=allow_missing)

    async def list(self, session: aiohttp.ClientSession | None = None) -> list[dict]:
        """List batch jobs (supports metadata-based filtering server-side)."""
        if session is not None:
            data = await self._request(session, "GET",
                                        f"{self.base_url}/batch/jobs")
            return data.get("data") or []
        async with aiohttp.ClientSession() as s:
            data = await self._request(s, "GET",
                                        f"{self.base_url}/batch/jobs")
            return data.get("data") or []

    async def cancel(self, provider_id: str,
                     session: aiohttp.ClientSession | None = None) -> dict:
        """Request cancellation of a running batch job.

        The job transitions to CANCELLATION_REQUESTED then CANCELLED.
        """
        url = f"{self.base_url}/batch/jobs/{provider_id}/cancel"
        if session is not None:
            return await self._request(session, "POST", url)
        async with aiohttp.ClientSession() as s:
            return await self._request(s, "POST", url)

    async def _download_file(self, file_id: str,
                             session: aiohttp.ClientSession | None = None) -> str:
        """Download a file's text content via the Mistral Files API."""
        url = f"{self.base_url}/files/{file_id}/content"
        return await self._download_text(url, session=session)

    async def fetch_results(self, batch: dict, provider_id: str | None = None,
                            session: aiohttp.ClientSession | None = None) -> list[dict]:
        """Download results from the Mistral Files API.

        Mistral returns results via ``output_file`` and ``error_file`` (file
        IDs), not inline in the batch object like OpenRouter. Each file is
        JSONL - one result record per line, joined by ``custom_id``.
        """
        output_file_id = batch.get("output_file")
        if not output_file_id:
            return []
        content = await self._download_file(output_file_id, session=session)
        results = []
        for raw_line in content.splitlines():
            line = raw_line.strip()
            if line:
                results.append(json.loads(line))
        # Include error records if a separate error file exists
        error_file_id = batch.get("error_file")
        if error_file_id:
            error_content = await self._download_file(error_file_id, session=session)
            for raw_line in error_content.splitlines():
                line = raw_line.strip()
                if line:
                    results.append(json.loads(line))
        return results

    # -- normalization -----------------------------------------------------

    @staticmethod
    def normalize_status(batch: dict) -> str:
        return MISTRAL_STATUS_MAP.get(batch.get("status", ""),
                                       batch.get("status", ""))

    @staticmethod
    def counts_of(batch: dict) -> tuple[int | None, int | None, int | None]:
        return (batch.get("total_requests"),
                batch.get("succeeded_requests"),
                batch.get("failed_requests"))

    @staticmethod
    def telemetry_of(batch: dict) -> dict:
        """Mistral does not return exact ``usage.cost``; token counts are in
        individual result lines and cost must be computed from rates. Returns
        None for both fields until per-model pricing is wired in."""
        return {"cost_usd": None, "host_backend": None}


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

    def _write_meta(self, meta: dict, *, update_index: bool = True) -> None:
        meta["updated_at"] = int(time.time())
        self._fsync_write(self._meta_path(meta["batch_id"]),
                          json.dumps(meta, ensure_ascii=False, indent=2))
        if update_index:
            self._append_index(meta)

    def compact_index(self) -> None:
        """Compact index.jsonl to keep only the latest record per batch."""
        self._rewrite_index(self.list_index())

    def _append_index(self, meta: dict) -> None:
        """Append the catalog record for this state; /batchlist dedups by id
        keeping the last occurrence."""
        record = {k: meta.get(k) for k in (
            "batch_id", "provider_id", "name", "provider", "host_backend",
            "model_alias", "model", "prompt", "status", "item_count",
            "payload_bytes",
            "temperature", "max_tokens", "top_p", "frequency_penalty", "presence_penalty",
            "results_count", "empty_results",
            "created_at", "updated_at", "finalized_at", "cost_usd", "workspace",
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
                if bid in latest:
                    order.remove(bid)
                order.append(bid)
                latest[bid] = rec
        records = [latest[bid] for bid in order]
        for r in records:
            if r.get("status") in EDITABLE_STATES:
                try:
                    meta = self.read_meta(r["batch_id"])
                    if "item_count" in meta:
                        r["item_count"] = meta["item_count"]
                except Exception:
                    pass
        return records

    def find_by_name(self, name: str) -> dict | None:
        """Most recent batch record with the given name (case-insensitive)."""
        matches = [r for r in self.list_index() if r.get("name", "").lower() == name.lower()]
        return matches[-1] if matches else None

    def get_active_draft(self) -> dict | None:
        """Return the most recently touched editable draft meta, or None."""
        candidates = [r for r in self.list_index() if r.get("status") in EDITABLE_STATES]
        if not candidates:
            return None
        candidates.sort(key=lambda r: (r.get("updated_at") or 0, r.get("created_at") or 0))
        try:
            return self.read_meta(candidates[-1]["batch_id"])
        except BatchError:
            return None

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
              prompt: str | None = None, clear: bool = False,
              temperature: float | None = None,
              max_tokens: int | None = None,
              top_p: float | None = None,
              frequency_penalty: float | None = None,
              presence_penalty: float | None = None) -> dict:
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
                if model_alias is not None and meta.get("model_alias") and model_alias != meta.get("model_alias"):
                    raise BatchError(
                        f"Batch '{slug}' uses model '{meta.get('model_alias')}'; clone it to change models."
                    )
                if clear:
                    self.clear_items(meta["batch_id"])
                requests_path = self._requests_path(meta["batch_id"])
                if os.path.exists(requests_path):
                    try:
                        os.remove(requests_path)
                    except OSError:
                        pass
                meta["status"] = STATUS_DRAFT
                meta.pop("payload_bytes", None)
                if prompt is not None:
                    meta["prompt"] = prompt
                if temperature is not None:
                    meta["temperature"] = temperature
                if max_tokens is not None:
                    meta["max_tokens"] = max_tokens
                if top_p is not None:
                    meta["top_p"] = top_p
                if frequency_penalty is not None:
                    meta["frequency_penalty"] = frequency_penalty
                if presence_penalty is not None:
                    meta["presence_penalty"] = presence_penalty
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
            "temperature": temperature,
            "max_tokens": max_tokens,
            "top_p": top_p,
            "frequency_penalty": frequency_penalty,
            "presence_penalty": presence_penalty,
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
        if meta["status"] not in EDITABLE_STATES:
            raise BatchError(f"Batch '{meta['name']}' is closed (status: {meta['status']}). "
                             "Reopen it with '/batch start "
                             f"{meta['name']}' first.")
        meta["prompt"] = prompt
        self._write_meta(meta)

    def clone(self, source_target: str, new_name: str, *,
              prompt: str | None = None,
              model_alias: str | None = None,
              model_name: str | None = None,
              provider: str | None = None,
              temperature: float | None = None,
              max_tokens: int | None = None,
              top_p: float | None = None,
              frequency_penalty: float | None = None,
              presence_penalty: float | None = None,
              force: bool = False) -> dict:
        """Clone an existing batch into a new draft staging session.

        Copies all staged items and configuration from source_target into a fresh
        instance directory (status: draft). If prompt, model, or sampling settings
        are supplied, they override the source batch's configuration. The cloned draft
        is fully editable (items can be edited, added, or removed) and must be sealed
        with /batch end before submission.

        Refuses when new_name already belongs to an editable batch (draft/staged)
        unless force=True - start() would reopen and clear that batch, silently
        destroying its staged items (and un-sealing it if staged)."""
        existing = self.find_by_name(sanitize_batch_name(new_name))
        if existing is not None:
            existing_meta = self.read_meta(existing["batch_id"])
            if (existing_meta["status"] in EDITABLE_STATES
                    or existing_meta["status"] == STATUS_STAGED) and not force:
                raise BatchError(
                    f"Batch '{new_name}' already exists (status: "
                    f"{existing_meta['status']}) and would be overwritten. "
                    "Choose a different name, or re-run with force=true to "
                    "replace its staged items."
                )
        source_meta = self.resolve(source_target)
        items = self._read_items(source_meta["batch_id"])

        chosen_alias = model_alias or source_meta.get("model_alias") or ""
        chosen_name = model_name or source_meta.get("model") or chosen_alias
        chosen_provider = provider or source_meta.get("provider") or "openrouter"
        chosen_prompt = prompt if prompt is not None else source_meta.get("prompt")
        chosen_temp = temperature if temperature is not None else source_meta.get("temperature")
        chosen_max_tokens = max_tokens if max_tokens is not None else source_meta.get("max_tokens")
        chosen_top_p = top_p if top_p is not None else source_meta.get("top_p")
        chosen_freq_pen = frequency_penalty if frequency_penalty is not None else source_meta.get("frequency_penalty")
        chosen_pres_pen = presence_penalty if presence_penalty is not None else source_meta.get("presence_penalty")

        new_meta = self.start(
            new_name,
            model_alias=chosen_alias,
            model_name=chosen_name,
            provider=chosen_provider,
            prompt=chosen_prompt,
            clear=True,
            temperature=chosen_temp,
            max_tokens=chosen_max_tokens,
            top_p=chosen_top_p,
            frequency_penalty=chosen_freq_pen,
            presence_penalty=chosen_pres_pen,
        )

        if items:
            self._rewrite_items(new_meta["batch_id"], items)
            new_meta["item_count"] = len(items)
            self._write_meta(new_meta)

        return new_meta

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

    def _append_items(self, meta: dict, items: list[dict], total_count: int | None = None) -> int:
        """Append items to staging.jsonl (flushed per line) and update counts."""
        path = self._staging_path(meta["batch_id"])
        with open(path, "a", encoding="utf-8") as f:
            for item in items:
                f.write(json.dumps(item, ensure_ascii=False) + "\n")
                f.flush()
        if total_count is not None:
            meta["item_count"] = total_count
        else:
            meta["item_count"] = meta.get("item_count", 0) + len(items)
        self._write_meta(meta, update_index=False)
        return len(items)

    def add_items(self, meta: dict, texts: list[str], *, id_prefix: str,
                  explicit_id: str | None = None, origin: str = "manual",
                  image: str | None = None) -> list[dict]:
        """Append one or many items with auto-generated sequenced IDs.

        Direct adds use ``<batch_name>_0001``; filebank ingestion uses
        ``fb<N>_line_0001``; imagebank ingestion uses ``ib<N>_0001``;
        script vars use ``<var_name>_0001`` (proposal §4.3). Explicit colliding
        IDs are refused."""
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
            item_data = {
                "custom_id": custom_id,
                "text": text,
                "origin": origin,
                "added_at": int(time.time()),
            }
            if image:
                item_data["image"] = image
            new_items.append(item_data)
        self._append_items(meta, new_items, total_count=len(items) + len(new_items))
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
        self._write_meta(meta, update_index=False)
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

    def check_payload_limits(self, meta: dict, items: list[dict], payload_bytes: int) -> list[str]:
        """Check payload size and item count against provider limits and return warnings."""
        warnings: list[str] = []
        provider = (meta.get("provider") or "").lower()
        size_mb = payload_bytes / (1024 * 1024)
        has_images = any(bool(item.get("image")) for item in items)

        if provider == "mistral":
            if len(items) > MISTRAL_INLINE_LIMIT:
                warnings.append(
                    f"Item count ({len(items):,}) exceeds Mistral's inline limit "
                    f"({MISTRAL_INLINE_LIMIT:,} items). Mistral will reject this submission."
                )
            if payload_bytes >= MISTRAL_INLINE_MAX_RECOMMENDED_BYTES:
                img_hint = " Compress attached images (e.g., JPEG under 1.5 MB) or reduce items." if has_images else " Split the batch into smaller runs."
                warnings.append(
                    f"Payload size ({size_mb:.2f} MB) exceeds Mistral's inline body limit (~2-4 MB). "
                    f"Mistral's edge gateway is very likely to reject the submission with an HTTP 400 Bad Request.{img_hint}"
                )
            elif payload_bytes >= MISTRAL_INLINE_WARN_BYTES:
                img_hint = " If submission fails with HTTP 400, compress attached images." if has_images else " If submission fails with HTTP 400, split the batch into smaller runs."
                warnings.append(
                    f"Payload size ({size_mb:.2f} MB) approaches Mistral's inline body limit (~2-4 MB).{img_hint}"
                )

        elif provider == "openrouter":
            if payload_bytes >= OPENROUTER_PAYLOAD_LIMIT_BYTES:
                warnings.append(
                    f"Payload size ({size_mb:.2f} MB) exceeds OpenRouter's 200 MB batch limit. "
                    "OpenRouter will reject this submission with HTTP 413. Split the batch into smaller runs."
                )
            elif payload_bytes >= OPENROUTER_PAYLOAD_WARN_BYTES:
                warnings.append(
                    f"Payload size ({size_mb:.2f} MB) is large and approaching OpenRouter's 200 MB limit. "
                    "Consider splitting the batch if timeouts or submission issues occur."
                )
        else:
            if payload_bytes >= OPENROUTER_PAYLOAD_LIMIT_BYTES:
                warnings.append(
                    f"Payload size ({size_mb:.2f} MB) is unusually large (>200 MB). "
                    "Verify provider batch request size limits before submitting."
                )

        return warnings

    def end(self, meta: dict) -> dict:
        """Run the Secret Scanner over every staged item, compile
        staging.jsonl into the provider payload requests.json, and lock the
        manifest (status: staged). Returns {'hits': [(custom_id, reason)], 'item_count': N, 'payload_bytes': N, 'warnings': [...]}."""
        if meta["status"] not in EDITABLE_STATES:
            raise BatchError(f"Batch '{meta['name']}' is already closed (status: {meta['status']}).")
        items = self._read_items(meta["batch_id"])
        if not items:
            raise BatchError(f"Batch '{meta['name']}' has no staged items. Add items first: /batch add ...")
        scanner = self._get_scanner()
        hits = []
        # Security scan batch prompt template if configured
        prompt_text = meta.get("prompt") or ""
        if prompt_text:
            p_res = scanner.scan(prompt_text)
            if p_res is not None:
                verdict, reason = p_res
                hits.append(("prompt", str(verdict), reason))

        for item in items:
            scan_text = item.get("text") or ""
            if scan_text:
                result = scanner.scan(scan_text)
                if result is not None:
                    verdict, reason = result
                    hits.append((item["custom_id"], str(verdict), reason))
        if hits:
            raise BatchError(
                "Security scan failed - staging remains open (status: draft).\n"
                "Offending items:\n  " + "\n  ".join(
                    f"{cid}: {reason}" for cid, _v, reason in hits
                ) + "\n"
                "Remove or edit the offending items ('/batch remove <id>', "
                "'/batch edit <id> \"...\"') and run '/batch end' again. "
                "Unresolved security hits cannot be submitted."
            )
        payload = self.build_payload(meta, items)
        payload_json = json.dumps(payload, ensure_ascii=False, indent=2)
        self._fsync_write(self._requests_path(meta["batch_id"]), payload_json)
        # Calculate true wire payload size (compact serialization matching HTTP clients)
        compact_json = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        payload_bytes = len(compact_json.encode("utf-8"))
        warnings = self.check_payload_limits(meta, items, payload_bytes)
        meta["status"] = STATUS_STAGED
        meta["item_count"] = len(items)
        meta["payload_bytes"] = payload_bytes
        self._write_meta(meta)
        self.compact_index()
        return {
            "hits": [],
            "item_count": len(items),
            "payload_bytes": payload_bytes,
            "warnings": warnings,
        }

    def build_payload(self, meta: dict, items: list[dict]) -> dict:
        """Compile staged items into the OpenRouter request payload.
        Key order matters: endpoint and model precede the requests array."""
        requests = []
        for item in items:
            messages = []
            if meta.get("prompt"):
                messages.append({"role": "system", "content": meta["prompt"]})
            if item.get("image"):
                content_parts = []
                if item.get("text"):
                    content_parts.append({"type": "text", "text": item["text"]})
                content_parts.append({
                    "type": "image_url",
                    "image_url": {"url": item["image"]}
                })
                messages.append({"role": "user", "content": content_parts})
            else:
                messages.append({"role": "user", "content": item.get("text") or ""})
            body: dict[str, Any] = {"messages": messages}
            if meta.get("temperature") is not None:
                body["temperature"] = meta["temperature"]
            if meta.get("max_tokens") is not None:
                body["max_tokens"] = meta["max_tokens"]
            if meta.get("top_p") is not None:
                body["top_p"] = meta["top_p"]
            if meta.get("frequency_penalty") is not None:
                body["frequency_penalty"] = meta["frequency_penalty"]
            if meta.get("presence_penalty") is not None:
                body["presence_penalty"] = meta["presence_penalty"]
            requests.append({"custom_id": item["custom_id"], "body": body})
        return {
            "endpoint": OPENROUTER_ENDPOINT,
            "model": meta["model"],
            "requests": requests,
        }

    def dump_payload(self, meta: dict) -> str:
        """The JSON request body that would be submitted (staged payload if
        available, otherwise a live build from staging)."""
        path = self._requests_path(meta["batch_id"])
        if meta.get("status") != STATUS_DRAFT and os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return f.read()
        items = self._read_items(meta["batch_id"])
        if not items:
            raise BatchError(f"Batch '{meta['name']}' has no staged items to dump.")
        return json.dumps(self.build_payload(meta, items), ensure_ascii=False, indent=2)

    def abort(self, meta: dict) -> None:
        """Discard an open (never-submitted) staging session entirely."""
        if (meta["status"] in OPEN_STATES or meta["status"] == STATUS_STAGED) and meta.get("provider_id"):
            raise BatchError(f"Batch '{meta['name']}' was submitted (status: {meta['status']}) "
                             "and cannot be aborted. Use '/batch cancel' instead.")
        if meta["status"] in TERMINAL_STATES:
            raise BatchError(f"Batch '{meta['name']}' already reached terminal state "
                             f"({meta['status']}); nothing to abort.")
        if meta["status"] == STATUS_SUBMIT_FAILED:
            raise BatchError(f"Batch '{meta['name']}' failed to submit (status: submit_failed). "
                             "Retry with '/batch run', or delete it with '/batch purge'.")
        if meta["status"] == STATUS_SUBMITTING and meta.get("provider_id"):
            raise BatchError(f"Batch '{meta['name']}' was submitted (status: submitting) "
                             "and cannot be aborted. Use '/batch cancel' instead.")
        import shutil
        shutil.rmtree(self._instance_dir(meta["batch_id"]), ignore_errors=True)
        # Catalog prune: rewrite the index without this batch_id
        records = [r for r in self.list_index() if r["batch_id"] != meta["batch_id"]]
        self._rewrite_index(records)

    def purge(self, meta: dict) -> None:
        """Permanently delete a batch from disk and catalog.

        Local-only states (draft, staged, submit_unknown), terminal states
        (completed, failed, expired, cancelled, submit_failed), and unconfirmed
        submitting batches without provider IDs can be purged. Active batches
        with provider IDs (submitted, in_progress) are refused unconditionally.
        """
        purgable = EDITABLE_STATES | {STATUS_STAGED} | TERMINAL_STATES | {STATUS_SUBMIT_FAILED, STATUS_SUBMIT_UNKNOWN}
        is_stale_submitting = (meta.get("status") == STATUS_SUBMITTING and not meta.get("provider_id"))
        if meta.get("status") not in purgable and not is_stale_submitting:
            raise BatchError(
                f"Batch '{meta['name']}' is still active (status: {meta['status']}). "
                "Only local, unconfirmed, or terminal batches can be purged. Cancel it first with "
                f"'/batch cancel {meta['name']}', then purge the result."
            )
        import shutil
        shutil.rmtree(self._instance_dir(meta["batch_id"]), ignore_errors=True)
        records = [r for r in self.list_index() if r["batch_id"] != meta["batch_id"]]
        self._rewrite_index(records)

    def _rewrite_index(self, records: list[dict]) -> None:
        data = "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in records)
        self._fsync_write(self.index_path(), data)

    # -- cost & concurrency guards (proposal §4.6) -------------------------

    @staticmethod
    def estimate_cost_usd(meta: dict, items: list[dict], max_tokens: int | None,
                           input_cost_per_mtok: float | None,
                           output_cost_per_mtok: float | None = None,
                           default_output_tokens: int = DEFAULT_BATCH_OUTPUT_TOKENS) -> float | None:
        """Estimate batch cost in USD.

        Uses input_cost_per_mtok for input tokens (50% batch discount) and
        output_cost_per_mtok (or input_cost_per_mtok if omitted) for estimated
        output tokens (50% batch discount). When max_tokens is None, falls back
        to default_output_tokens. When max_tokens is explicitly 0, output tokens
        are counted as 0.
        Returns None when the model lacks input pricing info (budget guard is
        then skipped with a notice)."""
        if not input_cost_per_mtok:
            return None
        prompt_chars = len(meta.get("prompt") or "") * len(items)
        chars = sum(len(it.get("text") or "") for it in items) + prompt_chars
        est_input_tokens = chars // 4
        effective_max = max_tokens if max_tokens is not None else default_output_tokens
        est_output_tokens = effective_max * len(items)
        effective_out_rate = output_cost_per_mtok if output_cost_per_mtok is not None else input_cost_per_mtok
        input_cost = (est_input_tokens * input_cost_per_mtok / 1_000_000) * 0.5
        output_cost = (est_output_tokens * effective_out_rate / 1_000_000) * 0.5
        return input_cost + output_cost

    def count_open_per_provider(self, provider: str) -> int:
        return sum(1 for r in self.list_index()
                   if r.get("provider") == provider and r.get("status") in OPEN_STATES)

    # -- submission (crash-safe) -------------------------------------------

    def _require_staged(self, meta: dict, resubmit: bool = False) -> None:
        if meta["status"] == STATUS_DRAFT:
            raise BatchError(f"Batch '{meta['name']}' is still a draft. Run '/batch end' "
                             "to seal and security-scan it first.")
        valid_states = (STATUS_STAGED, STATUS_SUBMIT_FAILED, STATUS_SUBMIT_UNKNOWN)
        is_stale_submitting = (meta["status"] == STATUS_SUBMITTING and not meta.get("provider_id"))
        if meta["status"] not in valid_states and not is_stale_submitting:
            raise BatchError(f"Batch '{meta['name']}' is not in staged state "
                             f"(status: {meta['status']}).")
        if (meta["status"] == STATUS_SUBMIT_UNKNOWN or is_stale_submitting) and not resubmit:
            raise BatchError(
                f"Batch '{meta['name']}' has unconfirmed submission status ({meta['status']}). "
                "The request may have reached the provider. Check your provider dashboard before resubmitting.\n"
                f"To resubmit anyway, add resubmit=true: '/batch run {meta['name']} resubmit=true'."
            )

    @staticmethod
    def _is_definitive_submit_rejection(e: Exception) -> bool:
        """Determine whether a submit failure is definitively client-side / rejected
        by provider with HTTP 4xx, meaning the job was certainly never accepted remotely.
        Everything else (timeouts, disconnects, 5xx, unreadable bodies) is treated
        as unconfirmed (submit_unknown)."""
        if isinstance(e, (ValueError, TypeError, FileNotFoundError)):
            return not isinstance(e, json.JSONDecodeError)
        if isinstance(e, ConnectionRefusedError):
            return True
        if isinstance(e, aiohttp.ClientConnectorError):
            os_err = getattr(e, "os_error", None)
            if isinstance(os_err, ConnectionRefusedError) or getattr(os_err, "errno", None) in (errno.ECONNREFUSED,):
                return True
        status = getattr(e, "status", None) or getattr(e, "status_code", None)
        if isinstance(status, int) and 400 <= status < 500:
            return True
        if re.search(r"\bHTTP\s+4\d\d\b", str(e), re.IGNORECASE):
            return True
        return False

    async def run(self, meta: dict, provider_obj: Any, *, force: bool = False,
                  resubmit: bool = False,
                  max_cost_usd: float = 5.0, max_open_per_provider: int = 3,
                  max_tokens: int | None = None,
                  input_cost_per_mtok: float | None = None,
                  output_cost_per_mtok: float | None = None,
                  precomputed_estimate: float | None = None,
                  session: aiohttp.ClientSession | None = None) -> dict:
        """Estimate cost, verify the budget and concurrency caps, then submit.

        The pre-POST sidecar write (status='submitting', fsynced) happens
        strictly BEFORE the network socket opens - OpenRouter does not
        deduplicate batch POSTs, so a crash between the write and the POST
        leaves an unconfirmed batch rather than a silent duplicate."""
        if session is None:
            async with aiohttp.ClientSession() as s:
                return await self.run(meta, provider_obj, force=force,
                                      resubmit=resubmit,
                                      max_cost_usd=max_cost_usd,
                                      max_open_per_provider=max_open_per_provider,
                                      max_tokens=max_tokens,
                                      input_cost_per_mtok=input_cost_per_mtok,
                                      output_cost_per_mtok=output_cost_per_mtok,
                                      precomputed_estimate=precomputed_estimate,
                                      session=s)

        self._require_staged(meta, resubmit=resubmit)
        if precomputed_estimate is not None:
            estimate = precomputed_estimate
        else:
            items = self._read_items(meta["batch_id"])
            estimate = self.estimate_cost_usd(
                meta, items, max_tokens,
                input_cost_per_mtok=input_cost_per_mtok,
                output_cost_per_mtok=output_cost_per_mtok,
            )
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
            batch = await _provider_call(
                provider_obj.submit,
                payload["requests"], meta["model"],
                metadata={"client_token": meta["batch_id"]},
                session=session,
            )
        except Exception as e:
            if self._is_definitive_submit_rejection(e):
                meta["status"] = STATUS_SUBMIT_FAILED
                self._write_meta(meta)
                raise BatchError(f"Submission failed (status: submit_failed): {e}") from e
            else:
                meta["status"] = STATUS_SUBMIT_UNKNOWN
                self._write_meta(meta)
                raise BatchError(
                    f"Submission unconfirmed (status: submit_unknown). The request may have reached the provider.\n"
                    f"Check your provider dashboard before resubmitting with '/batch run {meta['name']} resubmit=true': {e}"
                ) from e

        meta["provider_id"] = batch.get("id")
        meta["status"] = STATUS_SUBMITTED
        self._write_meta(meta)
        self.compact_index()
        return meta

    # -- polling / retrieval -------------------------------------------------

    async def check(self, meta: dict, provider_obj: Any, *, wait: bool = False,
                    max_wait_seconds: float = MAX_WAIT_SECONDS,
                    max_consecutive_404: int = MAX_CONSECUTIVE_404,
                    poll_start_seconds: float = POLL_START_SECONDS,
                    session: aiohttp.ClientSession | None = None) -> dict:
        """Poll status once (or with backoff until terminal when wait=true) and
        retrieve completed results inline. On completion, writes
        results.jsonl (one record per custom_id) and records the exact
        usage.cost / provider telemetry into meta and the catalog."""
        if session is None:
            async with aiohttp.ClientSession() as s:
                return await self.check(meta, provider_obj, wait=wait,
                                        max_wait_seconds=max_wait_seconds,
                                        max_consecutive_404=max_consecutive_404,
                                        poll_start_seconds=poll_start_seconds,
                                        session=s)

        if not meta.get("provider_id"):
            if meta.get("status") in (STATUS_SUBMIT_UNKNOWN, STATUS_SUBMITTING):
                raise BatchError(
                    f"Batch '{meta['name']}' has unconfirmed submission status ({meta['status']}) with no provider ID.\n"
                    f"Check your provider dashboard before resubmitting with '/batch run {meta['name']} resubmit=true', "
                    f"or discard this record with '/batch purge {meta['name']}'."
                )
            if meta.get("status") == STATUS_SUBMIT_FAILED:
                raise BatchError(
                    f"Batch '{meta['name']}' failed to submit (status: submit_failed). "
                    f"Retry with '/batch run {meta['name']}'."
                )
            raise BatchError(f"Batch '{meta['name']}' has no provider id - it has not "
                             "been submitted. Run '/batch run {0}' first.".format(meta["name"]))
        delay = poll_start_seconds
        start_time = time.time()
        consecutive_404 = 0

        batch = await _provider_call(provider_obj.get, meta["provider_id"], allow_missing=True, session=session)
        if batch is None:
            consecutive_404 += 1
            if not wait:
                print(f"  Batch not queryable yet (404, eventual consistency). "
                       "Retry '/batch check {0}' shortly.".format(meta["name"]))
                return meta
            while batch is None:
                if consecutive_404 >= max_consecutive_404:
                    raise BatchError(
                        f"Batch '{meta['name']}' (provider id: {meta['provider_id']}) returned "
                        f"404 Not Found {consecutive_404} consecutive times; polling aborted."
                    )
                if time.time() - start_time > max_wait_seconds:
                    raise BatchError(
                        f"Polling timeout reached for batch '{meta['name']}' after "
                        f"{max_wait_seconds:.0f}s. The batch may still be running remotely; "
                        f"check again later with '/batch check {meta['name']}'."
                    )
                await asyncio.sleep(delay)
                delay = min(delay * 2, POLL_MAX_SECONDS)
                batch = await _provider_call(provider_obj.get, meta["provider_id"], allow_missing=True, session=session)
                if batch is None:
                    consecutive_404 += 1
                else:
                    consecutive_404 = 0

        status = provider_obj.normalize_status(batch)
        while wait and status not in TERMINAL_STATES:
            if time.time() - start_time > max_wait_seconds:
                raise BatchError(
                    f"Polling timeout reached for batch '{meta['name']}' after "
                    f"{max_wait_seconds:.0f}s. The batch may still be running remotely; "
                    f"check again later with '/batch check {meta['name']}'."
                )
            await asyncio.sleep(delay)
            delay = min(delay * 2, POLL_MAX_SECONDS)
            batch = await _provider_call(provider_obj.get, meta["provider_id"], allow_missing=True, session=session)
            if batch is None:
                consecutive_404 += 1
                if consecutive_404 >= max_consecutive_404:
                    raise BatchError(
                        f"Batch '{meta['name']}' (provider id: {meta['provider_id']}) returned "
                        f"404 Not Found {consecutive_404} consecutive times; polling aborted."
                    )
            else:
                consecutive_404 = 0
                status = provider_obj.normalize_status(batch)

        meta["status"] = status
        total, done, failed = provider_obj.counts_of(batch)
        if done is None and batch is not None:
            done = len(batch.get("results") or [])

        results = []
        if status in (STATUS_COMPLETED, STATUS_CANCELLED, STATUS_EXPIRED):
            if hasattr(provider_obj, "fetch_results"):
                try:
                    results = await _provider_call(provider_obj.fetch_results, batch, meta["provider_id"], session=session)
                except Exception as e:
                    print(f"Error fetching batch results for '{meta['name']}': {e}")
                    print(f"Batch results could not be downloaded. Retry with '/batch check {meta['name']}'.")
                    self._write_meta(meta)
                    return meta
            else:
                results = batch.get("results") or []
                if not results and status == STATUS_COMPLETED:
                    try:
                        refetched = await _provider_call(provider_obj.get, meta["provider_id"], session=session)
                        results = (refetched or {}).get("results") or []
                    except Exception as e:
                        print(f"Error refetching batch results for '{meta['name']}': {e}")
                        print(f"Batch results could not be downloaded. Retry with '/batch check {meta['name']}'.")
                        self._write_meta(meta)
                        return meta
            if results:
                normalized = [provider_obj.normalize_result(r) for r in results]
                # Providers return results in COMPLETION order, which is arbitrary
                # and varies run to run. Sort into the staging (submission) order
                # so results.jsonl and /batch results are predictable; the
                # custom_id is the join key either way.
                staged_order = {it["custom_id"]: i for i, it
                                in enumerate(self._read_items(meta["batch_id"]))}
                normalized.sort(key=lambda r: staged_order.get(
                    r.get("custom_id"), len(staged_order)))
                data = "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in normalized)
                self._fsync_write(self._results_path(meta["batch_id"]), data)
                # Batch providers count empty completions (status 200, no
                # content) as successes and never retry them; surface them so
                # users can spot flaky runs and re-queue just those items.
                meta["empty_results"] = sum(1 for r in normalized if is_empty_result(r))
                meta["results_count"] = len(normalized)
            meta["finalized_at"] = int(time.time())
            telemetry = provider_obj.telemetry_of(batch) if batch else {}
            if telemetry.get("cost_usd") is not None:
                meta["cost_usd"] = telemetry["cost_usd"]
            if telemetry.get("host_backend"):
                meta["host_backend"] = telemetry["host_backend"]
            if failed is not None:
                meta["failed_count"] = failed
        elif status in TERMINAL_STATES:
            meta["finalized_at"] = int(time.time())
            meta["failed_count"] = failed or 0

        self._write_meta(meta)
        return meta

    async def cancel(self, meta: dict, provider_obj: Any,
                     force: bool = False,
                     session: aiohttp.ClientSession | None = None) -> dict:
        """Cancel an in-flight batch at the provider and locally.

        Providers without a cancel endpoint (OpenRouter) cannot stop a
        submitted job: refuse unless force=True, which marks the batch
        cancelled locally while the remote job still runs to completion."""
        if session is None:
            async with aiohttp.ClientSession() as s:
                return await self.cancel(meta, provider_obj, force=force, session=s)

        if meta["status"] not in OPEN_STATES:
            raise BatchError(f"Batch '{meta['name']}' is not in flight (status: {meta['status']}).")
        if provider_obj is not None and getattr(provider_obj, "supports_cancel", False):
            await _provider_call(provider_obj.cancel, meta["provider_id"], session=session)
        else:
            if not force:
                raise BatchError(
                    f"Provider '{meta.get('provider', 'unknown')}' cannot cancel a "
                    "submitted batch - it will run to completion (or expire within "
                    "24 hours) and bill at batch rates.\n"
                    "To remove it from your active batches anyway, re-run with "
                    f"force=true: '/batch cancel {meta['name']} force=true' "
                    "(marks it cancelled locally; the remote job is not stopped)."
                )
            print(f"Note: cancelling '{meta['name']}' locally only - the remote "
                  "job will still run to completion and bill at batch rates.")
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

    def get_result(self, batch_id: str, custom_id: str) -> dict | None:
        """One retrieved result record by custom_id, or None before retrieval."""
        for record in self.read_results(batch_id):
            if record.get("custom_id") == custom_id:
                return record
        return None

    def find_batches_containing(self, custom_id: str,
                                editable_only: bool = False) -> list[dict]:
        """Batches (newest first) whose staging contains custom_id.

        Used by /batch show|edit|remove when the batch name is not given:
        the item ID itself identifies the batch. With editable_only, only
        draft batches are considered (edit/remove operate on drafts)."""
        active = self.get_active_draft()
        if active is not None:
            if not editable_only or active.get("status") in EDITABLE_STATES:
                if any(it["custom_id"] == custom_id for it in self._read_items(active["batch_id"])):
                    return [active]

        if "_" in custom_id:
            cand_name = custom_id.rsplit("_", 1)[0]
            rec = self.find_by_name(cand_name)
            if rec is not None:
                if not editable_only or rec.get("status") in EDITABLE_STATES:
                    try:
                        cand_meta = self.read_meta(rec["batch_id"])
                        if any(it["custom_id"] == custom_id for it in self._read_items(cand_meta["batch_id"])):
                            return [cand_meta]
                    except BatchError:
                        pass

        matches = []
        for rec in reversed(self.list_index()):
            if editable_only and rec.get("status") not in EDITABLE_STATES:
                continue
            if active and rec["batch_id"] == active["batch_id"]:
                continue
            try:
                meta = self.read_meta(rec["batch_id"])
            except BatchError:
                continue
            if editable_only and meta.get("status") not in EDITABLE_STATES:
                continue
            if any(it["custom_id"] == custom_id
                   for it in self._read_items(meta["batch_id"])):
                matches.append(meta)
        return matches


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


def make_provider(model_config: dict, api_key: str, *,
                  trace_raw_payload: bool = False,
                  logging_manager: Any = None) -> Any:
    """Build the batch provider from a chat_config model entry.

    Dispatches on the ``vendor`` field or detected provider via ``detect_provider``:
    ``openrouter`` (Phase 1) or ``mistral`` (Phase 2, inline batching only).
    """
    from .config_model import detect_provider
    detected = detect_provider(model_config)
    vendor = (model_config.get("vendor") or (detected if detected not in ("other", "local") else None) or "openrouter").lower()
    base_url = model_config.get("base_url")
    if vendor == "mistral":
        return MistralBatchProvider(
            api_key=api_key,
            base_url=base_url or MISTRAL_API_BASE,
            trace_raw_payload=trace_raw_payload,
            logging_manager=logging_manager,
        )
    # Default: OpenRouter (Phase 1)
    return OpenRouterBatchProvider(
        api_key=api_key,
        base_url=base_url or OPENROUTER_API_BASE,
        trace_raw_payload=trace_raw_payload,
        logging_manager=logging_manager,
    )
