"""
Tool Argument Normalization
One rule, shared by the security check and every execution path, for models
that wrap tool arguments in an envelope such as {"parameters": {...}}.

Keeping this in a side-effect-free module (dispatcher.py edits sys.path when
imported) lets security code depend on it safely.
"""

from __future__ import annotations

from typing import Any

ENVELOPE_KEYS = ("parameters", "args", "arguments")


def unwrap_tool_args(parameters: Any) -> Any:
    """Unwrap {"parameters"|"args"|"arguments": {...}} only when that key is the
    sole key, repeating while a lone envelope remains.

    An envelope that sits beside other keys is left alone: unwrapping it would let
    a decoy ({"path": "/etc/passwd", "args": {"path": "README.md"}}) be judged by
    security while the real arguments run. Security and execution must call this
    same function so the arguments judged are the arguments executed.
    """
    params = parameters
    while isinstance(params, dict) and len(params) == 1:
        key = next(iter(params))
        inner = params[key]
        if key not in ENVELOPE_KEYS or not isinstance(inner, dict):
            break
        params = inner
    return params
