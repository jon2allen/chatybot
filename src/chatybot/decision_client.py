"""Async HTTP client for TypeSafe System One / OpenRouter decisions endpoint.

Both providers accept the same JSON body shape:
    { "state": ..., "model": ..., "questions": { ... } }

They differ only in the endpoint path and auth header. This client is
config-driven: base_url, endpoint_path, model name, and api_key all come
from the model config, so the same code works for both providers.
"""

from __future__ import annotations

import json
import os
from typing import Any

import aiohttp


class DecisionAPIError(Exception):
    """Raised when the decisions endpoint returns an error."""

    def __init__(self, status: int, body: str):
        self.status = status
        self.body = body
        super().__init__(f"Decision API error {status}: {body}")


async def evaluate(
    state: str,
    questions: dict[str, dict[str, Any]],
    model_name: str,
    base_url: str,
    endpoint_path: str,
    api_key: str,
    timeout: float = 30.0,
    trace_raw_payload: bool = False,
    logging_manager: Any = None,
) -> dict[str, Any]:
    """POST to the decisions endpoint and return the parsed JSON response.

    Args:
        state: The content to evaluate (text, JSON string, etc.).
        questions: Map of question-id to question dict. Each question has
            ``type`` ("choice", "score", or "noul"), ``instructions``, and
            ``criteria``.
        model_name: Model identifier (e.g. "typesafe/jev-1.13").
        base_url: API root URL (e.g. "https://openrouter.ai").
        endpoint_path: Path appended to base_url (e.g. "/api/alpha/decisions").
        api_key: Bearer token for the Authorization header.
        timeout: Request timeout in seconds.
        trace_raw_payload: If True, prints and logs raw outgoing and incoming JSON payloads.
        logging_manager: Optional LoggingManager instance to record payload logs.

    Returns:
        Parsed JSON response: ``{"model": ..., "answers": {...}, "usage": {...}}``.

    Raises:
        DecisionAPIError: On non-2xx HTTP status.
    """
    trace_enabled = trace_raw_payload or os.environ.get("CHATYBOT_TRACE_RAW_PAYLOAD") == "1"
    url = f"{base_url.rstrip('/')}{endpoint_path}"
    body = {
        "state": state,
        "model": model_name,
        "questions": questions,
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    if trace_enabled:
        masked_key = f"{api_key[:10]}...{api_key[-5:]}" if api_key and len(api_key) > 15 else "None"
        body_str = json.dumps(body, indent=2, ensure_ascii=False)
        body_bytes = body_str.encode("utf-8")
        size_bytes = len(body_bytes)
        size_kb = size_bytes / 1024
        est_tokens = max(1, int(size_bytes / 4))
        size_info = f"Size: {size_bytes} bytes ({size_kb:.2f} KB) | Est. Tokens: ~{est_tokens} (industry avg)"

        print("Decision Request Payload:")
        print("-----------------------------")
        print(f"POST {url}")
        print(f"Headers: {{'Authorization': 'Bearer {masked_key}', 'Content-Type': 'application/json'}}")
        print(body_str)
        print("---- end of payload ---")
        print(size_info)

        if logging_manager and hasattr(logging_manager, "log_message"):
            log_content = (
                f"Decision Request Payload:\n---------------------\n"
                f"POST {url}\n"
                f"Headers: {{'Authorization': 'Bearer {masked_key}', 'Content-Type': 'application/json'}}\n"
                f"{body_str}\n---- end of payload ---\n{size_info}"
            )
            try:
                logging_manager.log_message(log_content)
            except Exception:
                pass

    async with aiohttp.ClientSession() as session:
        async with session.post(
            url, json=body, headers=headers, timeout=aiohttp.ClientTimeout(total=timeout)
        ) as resp:
            text = await resp.text()

            if trace_enabled:
                try:
                    resp_parsed = json.loads(text)
                    resp_str = json.dumps(resp_parsed, indent=2, ensure_ascii=False)
                except Exception:
                    resp_str = text

                resp_bytes = resp_str.encode("utf-8")
                resp_size_bytes = len(resp_bytes)
                resp_size_kb = resp_size_bytes / 1024
                resp_est_tokens = max(1, int(resp_size_bytes / 4))
                resp_size_info = f"Size: {resp_size_bytes} bytes ({resp_size_kb:.2f} KB) | Est. Tokens: ~{resp_est_tokens} (industry avg)"

                print("Decision Response Payload:")
                print("-----------------------------")
                print(f"HTTP {resp.status}")
                print(resp_str)
                print("---- end of payload ---")
                print(resp_size_info)

                if logging_manager and hasattr(logging_manager, "log_message"):
                    resp_log = (
                        f"Decision Response Payload:\n---------------------\n"
                        f"HTTP {resp.status}\n{resp_str}\n---- end of payload ---\n{resp_size_info}"
                    )
                    try:
                        logging_manager.log_message(resp_log)
                    except Exception:
                        pass

            if resp.status >= 400:
                raise DecisionAPIError(resp.status, text)
            return json.loads(text)

