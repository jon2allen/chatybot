"""
String utility functions for Chatybot.
Provides:
  - String search utility (str_search) for tool calling and command execution
  - String modifier transformation engine (apply_string_modifier) for variable expansions
"""

import re
from typing import Any, Callable

# ---------------------------------------------------------------------------
# String Modifiers Engine
# ---------------------------------------------------------------------------

class StringModifierError(ValueError):
    """Raised when an unknown string modifier or invalid modifier arguments are encountered."""
    pass


_TITLE_RE = re.compile(r"[^\W\d_]+('[^\W\d_]+)?")

STRING_MODIFIERS: dict[str, Callable[[str], str]] = {
    "lower": lambda s: s.lower(),
    "upper": lambda s: s.upper(),
    "title": lambda s: _TITLE_RE.sub(lambda m: m.group(0)[0].upper() + m.group(0)[1:].lower(), s),
    "capitalize": lambda s: s.capitalize(),
    "trim": lambda s: s.strip(),
    "strip": lambda s: s.strip(),
    "ltrim": lambda s: s.lstrip(),
    "lstrip": lambda s: s.lstrip(),
    "rtrim": lambda s: s.rstrip(),
    "rstrip": lambda s: s.rstrip(),
    "len": lambda s: str(len(s)),
    "length": lambda s: str(len(s)),
}


def apply_single_modifier(val: str, mod_spec: str) -> str:
    """Apply a single modifier like 'lower', 'upper', or 'slice:0:5'."""
    mod_spec = mod_spec.strip()
    if not mod_spec:
        return val

    mod_lower = mod_spec.lower()

    # Parametric modifier: slice:start:end or sub:start:end (case-insensitive)
    if mod_lower in ("slice", "sub") or mod_lower.startswith(("slice:", "sub:")):
        parts = mod_spec.split(":")
        if len(parts) == 1:
            print(f"Error: Invalid slice parameters in modifier '{mod_spec}'. Usage: slice:start:end")
            raise StringModifierError(f"Invalid slice parameters in modifier '{mod_spec}'. Usage: slice:start:end")
        try:
            start = int(parts[1].strip()) if len(parts) > 1 and parts[1].strip() != "" else None
            end = int(parts[2].strip()) if len(parts) > 2 and parts[2].strip() != "" else None
            return val[start:end]
        except (ValueError, IndexError):
            print(f"Error: Invalid slice parameters in modifier '{mod_spec}'. Usage: slice:start:end")
            raise StringModifierError(f"Invalid slice parameters in modifier '{mod_spec}'. Usage: slice:start:end")

    if mod_lower in STRING_MODIFIERS:
        return STRING_MODIFIERS[mod_lower](val)

    print(f"Error: Unknown string modifier '{mod_spec}'. Supported: {', '.join(sorted(STRING_MODIFIERS.keys()))}, slice:start:end")
    raise StringModifierError(f"Unknown string modifier '{mod_spec}'")


def apply_string_modifier(val: str, modifier_spec: str) -> str:
    """Apply one or more chained string modifiers separated by colons.

    Examples:
        apply_string_modifier("  Hello World  ", "trim:lower") -> "hello world"
        apply_string_modifier("abcdef", "slice:0:3:upper") -> "ABC"
        apply_string_modifier("hello", "upper") -> "HELLO"
    """
    val_str = val if isinstance(val, str) else str(val)
    if not modifier_spec:
        return val_str

    # Tokenize modifier_spec respecting parametric modifiers (slice:start:end)
    tokens: list[str] = []
    raw_parts = [p.strip() for p in modifier_spec.split(":")]
    i = 0
    while i < len(raw_parts):
        part = raw_parts[i]
        if part.lower() in ("slice", "sub"):
            slice_tokens = [part]
            i += 1
            param_count = 0
            while i < len(raw_parts) and param_count < 2:
                if raw_parts[i].lower() in STRING_MODIFIERS or raw_parts[i].lower() in ("slice", "sub"):
                    break
                slice_tokens.append(raw_parts[i])
                i += 1
                param_count += 1
            tokens.append(":".join(slice_tokens))
        else:
            tokens.append(part)
            i += 1

    result = val_str
    for tok in tokens:
        if tok:
            result = apply_single_modifier(result, tok)

    return result


# ---------------------------------------------------------------------------
# String Search Utility
# ---------------------------------------------------------------------------

def str_search(
    pattern: str,
    text: str,
    mode: str = "c",
    case_sensitive: bool = True,
    target_variable: str | None = None,
    app: Any = None,
) -> dict[str, Any]:
    """
    Search for a substring pattern in text.

    Args:
        pattern: The substring pattern to search for.
        text: The text to search within.
        mode: "c" for count (default), "m" for match positions list.
        case_sensitive: Whether the search is case-sensitive (default True).
        target_variable: Optional name of the script variable to save the result to.
        app: ChatybotApp instance passed when called within application context.

    Returns:
        Dict containing status, result (count or positions), and optional variable assignment.
    """
    try:
        if not pattern:
            return {
                "status": "error",
                "message": "Pattern cannot be empty",
                "result": None,
            }

        if not text:
            result = 0 if mode == "c" else []
            response = {
                "status": "success",
                "pattern": pattern,
                "result": result,
                "count": 0,
                "case_insensitive": not case_sensitive,
                "mode": mode,
            }
            if target_variable and app and hasattr(app, "buffer_manager"):
                app.buffer_manager.set_script_var(target_variable, result, allow_protected=True)
                response["target_variable"] = target_variable
                response["message"] = f"No matches. Result ({result}) saved to '{target_variable}'"
            else:
                response["message"] = f"No matches found for '{pattern}'"
            return response

        re_flags = 0 if case_sensitive else re.IGNORECASE
        matches: list[re.Match] = list(re.finditer(re.escape(pattern), text, re_flags))

        if mode == "m":
            positions: list[tuple[int, int]] = [(m.start(), m.end()) for m in matches]
            result: Any = positions
        else:
            result = len(matches)

        count = len(matches)

        response: dict[str, Any] = {
            "status": "success",
            "pattern": pattern,
            "result": result,
            "count": count,
            "case_insensitive": not case_sensitive,
            "mode": mode,
        }

        if target_variable and app and hasattr(app, "buffer_manager"):
            app.buffer_manager.set_script_var(target_variable, result, allow_protected=True)
            response["target_variable"] = target_variable
            response["message"] = f"Found {count} match(es). Result saved to '{target_variable}'"
        else:
            response["message"] = f"Found {count} match(es) for '{pattern}'"

        return response

    except Exception as e:
        return {
            "status": "error",
            "message": f"Error searching for pattern '{pattern}': {e!s}",
            "result": None,
        }
