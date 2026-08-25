"""
Math evaluation tool for LLM tool calling in Chatybot.
Evaluates mathematical expressions using mathparse, with options to return the calculation result directly
or store it in a target script variable.
"""

from typing import Dict, Any, Optional
from decimal import Decimal
import re
import mathparse.mathparse as mp

def ensure_mathparse_patched():
    """
    Patches mathparse module:
    1. Coerces float operands to Decimal in to_number to prevent mixed Decimal/float TypeErrors.
    2. Replaces to_postfix with corrected operator precedence: '^' set to 5 (PEMDAS) and '.' set to 6
       so decimal composition binds tighter than exponentiation.
    """
    if getattr(mp, "_is_patched_for_chatybot", False):
        return

    _orig_to_number = mp.to_number
    def _patched_to_number(val):
        res = _orig_to_number(val)
        if isinstance(res, float):
            return Decimal(str(res))
        return res
    mp.to_number = _patched_to_number

    def _patched_to_postfix(tokens: list) -> list:
        precedence = {
            '.': 6,
            '/': 4,
            '*': 4,
            '+': 3,
            '-': 3,
            '^': 5,
            '(': 1
        }
        unary_precedence = max(precedence.values()) + 1
        postfix = []
        opstack = []
        for token in tokens:
            if mp.is_int(token):
                postfix.append(token)
            elif mp.is_float(token):
                postfix.append(token)
            elif token in mp.mathwords.CONSTANTS:
                postfix.append(token)
            elif mp.is_unary(token):
                opstack.append(token)
            elif token == '(':
                opstack.append(token)
            elif token == ')':
                top_token = opstack.pop()
                while top_token != '(':
                    postfix.append(top_token)
                    top_token = opstack.pop()
            elif mp.is_binary(token):
                while (opstack != []) and (
                    (
                        opstack[-1] in precedence and token in precedence and (
                            precedence[opstack[-1]] >= precedence[token]
                        )
                    ) or
                    (
                        mp.is_unary(opstack[-1]) and unary_precedence >= precedence[token]
                    )
                ):
                    postfix.append(opstack.pop())
                opstack.append(token)
            else:
                raise mp.PostfixTokenEvaluationException(
                    'Unsupported mathematical term: "{}"'.format(token)
                )
        while opstack != []:
            postfix.append(opstack.pop())
        return postfix

    mp.to_postfix = _patched_to_postfix
    mp._is_patched_for_chatybot = True

ensure_mathparse_patched()


def normalize_result(result):
    """Convert a mathparse result to a JSON-serializable type without binary float rounding."""
    if isinstance(result, Decimal):
        return int(result) if result % 1 == 0 else str(result)
    elif isinstance(result, (int, float, str)):
        return result
    else:
        return str(result)


def preprocess_multilingual_expression(expr: str, locale: str) -> str:
    """Preprocesses a mathematical expression for non-English locales (e.g. translating Arabic digits)."""
    if locale == "ar":
        # Eastern Arabic to Western Arabic digits
        arabic_digits = {
            '٠': '0', '١': '1', '٢': '2', '٣': '3', '٤': '4',
            '٥': '5', '٦': '6', '٧': '7', '٨': '8', '٩': '9'
        }
        for a_dig, w_dig in arabic_digits.items():
            expr = expr.replace(a_dig, w_dig)
        # Basic operators
        terms = {
            'زائد': '+',
            'ناقص': '-',
            'في': '*',
            'ضرب': '*',
            'على': '/',
            'قسمة': '/',
            'يساوي': '='
        }
        for term, op in terms.items():
            expr = re.sub(r'(?<!\w)' + re.escape(term) + r'(?!\w)', op, expr)
    return expr


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

        # Resolve language code based on application locale
        lang_code = "ENG"
        locale = "en"
        if app and hasattr(app, "i18n"):
            locale = app.i18n.locale
            lang_code = {
                "en": "ENG",
                "es": "ESP",
                "fr": "FRE",
                "zh": "CHI",
                "it": "ITA"
            }.get(locale, "ENG")

        expr_str = preprocess_multilingual_expression(expr_str, locale)

        # Try parsing with current language fallback
        try:
            result = mathparse.parse(expr_str, language=lang_code)
        except Exception:
            result = mathparse.parse(expr_str)

        hint_msg = "\n\n[TOOL USAGE HINT]: Supported scalar operations: +, -, *, /, ^, sqrt, log, abs. For array/list statistics (mean, median, stddev, sum, min, max), use 'run_command' with Python."
        if result is None:
            return {
                "status": "error",
                "message": f"Could not parse math expression '{expression}'.{hint_msg}",
                "result": None
            }

        if result == 'undefined':
            return {
                "status": "error",
                "message": f"Division by zero in expression '{expression}'.{hint_msg}",
                "result": None
            }

        result = normalize_result(result)

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
        hint_msg = "\n\n[TOOL USAGE HINT]: Supported scalar operations: +, -, *, /, ^, sqrt, log, abs. For array/list statistics (mean, median, stddev, sum, min, max), use 'run_command' with Python."
        return {
            "status": "error",
            "message": f"Error evaluating math expression '{expression}': {str(e)}.{hint_msg}",
            "result": None
        }
