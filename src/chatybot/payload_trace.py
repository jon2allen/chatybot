"""Shared raw-payload tracing for decision/jev HTTP requests.

Prints the outgoing JSON body and the incoming response to stdout (and an
optional logging manager) so the exact payload sent to a decision endpoint
can be inspected on screen. Reused by both the async decision client
(``chatybot.decision_client``) and the Jev security engine
(``chatybot.security.jev``) so the two paths share one trace format.

Enablement is caller-driven: each call site decides whether tracing is on
(typically via the ``trace_raw_payload`` profile toggle or the
``CHATYBOT_TRACE_RAW_PAYLOAD`` environment variable).
"""

from __future__ import annotations

import json
import os
from typing import Any

TRACE_ENV_VAR = "CHATYBOT_TRACE_RAW_PAYLOAD"


def trace_enabled(explicit: bool = False) -> bool:
    """True if raw-payload tracing should run.

    Honors an explicit per-call flag first, then the shared environment
    variable so a single toggle covers every call site.
    """
    return bool(explicit) or os.environ.get(TRACE_ENV_VAR) == "1"


def _mask_key(api_key: str | None) -> str:
    if not api_key:
        return "None"
    if len(api_key) > 15:
        return f"{api_key[:10]}...{api_key[-5:]}"
    return "***"


def _size_info(text: str) -> str:
    size_bytes = len(text.encode("utf-8"))
    size_kb = size_bytes / 1024
    est_tokens = max(1, int(size_bytes / 4))
    return f"Size: {size_bytes} bytes ({size_kb:.2f} KB) | Est. Tokens: ~{est_tokens} (industry avg)"


def _log(logging_manager: Any, content: str) -> None:
    if logging_manager and hasattr(logging_manager, "log_message"):
        try:
            logging_manager.log_message(content)
        except Exception:  # noqa: BLE001, S110
            pass


def print_request_payload(
    url: str,
    body: dict[str, Any],
    api_key: str | None,
    *,
    logging_manager: Any = None,
    label: str = "Decision Request Payload:",
) -> None:
    """Print the outgoing request body (and headers, with a masked key)."""
    masked_key = _mask_key(api_key)
    body_str = json.dumps(body, indent=2, ensure_ascii=False)
    size_info = _size_info(body_str)
    header_line = f"Headers: {{'Authorization': 'Bearer {masked_key}', 'Content-Type': 'application/json'}}"

    print(label)
    print("-----------------------------")
    print(f"POST {url}")
    print(header_line)
    print(body_str)
    print("---- end of payload ---")
    print(size_info)

    _log(
        logging_manager,
        f"{label}:\n---------------------\nPOST {url}\n{header_line}\n{body_str}\n---- end of payload ---\n{size_info}",
    )


def print_response_payload(
    status: int | str,
    text: str,
    *,
    logging_manager: Any = None,
    label: str = "Decision Response Payload:",
) -> None:
    """Print the incoming response body with size info."""
    try:
        resp_parsed = json.loads(text)
        resp_str = json.dumps(resp_parsed, indent=2, ensure_ascii=False)
    except Exception:  # noqa: BLE001
        resp_str = text

    size_info = _size_info(resp_str)

    print(label)
    print("-----------------------------")
    print(f"HTTP {status}")
    print(resp_str)
    print("---- end of payload ---")
    print(size_info)

    _log(
        logging_manager,
        f"{label}:\n---------------------\nHTTP {status}\n{resp_str}\n---- end of payload ---\n{size_info}",
    )
