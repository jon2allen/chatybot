"""Async HTTP client for TypeSafe System One / OpenRouter decisions endpoint.

Both providers accept the same JSON body shape:
    { "state": ..., "model": ..., "questions": { ... } }

They differ only in the endpoint path and auth header. This client is
config-driven: base_url, endpoint_path, model name, and api_key all come
from the model config, so the same code works for both providers.
"""

from __future__ import annotations

import json
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

    Returns:
        Parsed JSON response: ``{"model": ..., "answers": {...}, "usage": {...}}``.

    Raises:
        DecisionAPIError: On non-2xx HTTP status.
    """
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

    async with aiohttp.ClientSession() as session:
        async with session.post(
            url, json=body, headers=headers, timeout=aiohttp.ClientTimeout(total=timeout)
        ) as resp:
            text = await resp.text()
            if resp.status >= 400:
                raise DecisionAPIError(resp.status, text)
            return json.loads(text)
