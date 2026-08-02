"""
String search utility for LLM tool calling in Chatybot.
Searches for substring patterns in text with optional case-insensitive matching.
Returns match count or match positions, and optionally stores the result in a script variable.
"""

from typing import Dict, Any, Optional, List, Tuple
import re


def str_search(
    pattern: str,
    text: str,
    mode: str = "c",
    case_sensitive: bool = True,
    target_variable: Optional[str] = None,
    app: Any = None,
) -> Dict[str, Any]:
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
        matches: List[re.Match] = list(re.finditer(re.escape(pattern), text, re_flags))

        if mode == "m":
            positions: List[Tuple[int, int]] = [(m.start(), m.end()) for m in matches]
            result: Any = positions
        else:
            result = len(matches)

        count = len(matches)

        response: Dict[str, Any] = {
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
            "message": f"Error searching for pattern '{pattern}': {str(e)}",
            "result": None,
        }
