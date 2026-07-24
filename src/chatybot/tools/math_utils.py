"""
Math evaluation tool for LLM tool calling in Chatybot.
Evaluates mathematical expressions using mathparse, with options to return the calculation result directly
or store it in a target script variable.
"""

from typing import Dict, Any, Optional
from decimal import Decimal
import mathparse.mathparse as mp

# Patch mathparse.to_number to coerce float operands into Decimal,
# preventing TypeError: unsupported operand type(s) for *: 'decimal.Decimal' and 'float'
_orig_to_number = mp.to_number
def _patched_to_number(val):
    res = _orig_to_number(val)
    if isinstance(res, float):
        return Decimal(str(res))
    return res

mp.to_number = _patched_to_number


def calculate(expression: str, target_variable: Optional[str] = None, app: Any = None) -> Dict[str, Any]:
    """
    Evaluates a mathematical or natural language math expression.

    Args:
        expression: The mathematical expression to parse and evaluate (e.g., "100 * 4", "fifty times two", "2 + ${val}").
        target_variable: Optional name of the script variable to save the result to.
        app: ChatybotApp instance passed when called within application context.

    Returns:
        Dict containing status, result, and optional variable assignment target.
    """
    try:
        from mathparse import mathparse
        
        expr_str = expression
        # Resolve any variable placeholders inside the expression if app/buffer_manager is available
        if app and hasattr(app, "buffer_manager"):
            expr_str = app.buffer_manager.replace_placeholders_legacy(expr_str, clear_unresolved=False)

        # Try parsing with ENG language fallback
        try:
            result = mathparse.parse(expr_str, language='ENG')
        except Exception:
            result = mathparse.parse(expr_str)

        if result is None:
            return {
                "status": "error",
                "message": f"Could not parse math expression '{expression}'",
                "result": None
            }

        # Convert Decimal or numeric types to exact string or int for JSON serialization without binary float rounding
        from decimal import Decimal
        if isinstance(result, Decimal):
            result = int(result) if result % 1 == 0 else str(result)
        elif isinstance(result, (int, float, str)):
            pass
        else:
            result = str(result)

        target_set = str(target_variable).strip() if target_variable else None
        if target_set and app and hasattr(app, "buffer_manager"):
            app.buffer_manager.set_script_var(target_set, result, allow_protected=True)

        response = {
            "status": "success",
            "expression": expression,
            "result": result
        }
        if target_set:
            response["target_variable"] = target_set
            response["message"] = f"Result {result} saved to variable '{target_set}'"
        else:
            response["message"] = f"Result: {result}"

        return response

    except Exception as e:
        return {
            "status": "error",
            "message": f"Error evaluating math expression '{expression}': {str(e)}",
            "result": None
        }
