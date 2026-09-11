"""
Interactive user-prompt utilities for Chatybot.

Provides a single ask_user() entry point that is shared by:
  - The /ask slash command  (commands/interact.py)
  - The LLM tool dispatch   (chatybot_app.dispatch_tool / tool name "ask_user")

Batch-mode guard
----------------
The function returns {"status": "skipped"} without blocking when either of the
following conditions is true:

  1. app.script_context is True  — a .chatdsl file is being executed via
     execute_script() / the --script CLI flag.
  2. sys.stdin.isatty() is False — stdin has been redirected (pipe, CI runner,
     etc.).  This covers cases where the script context flag is not set but the
     process is clearly non-interactive.

Supported question types
------------------------
  "yesno"   — numbered list [1. yes  2. no]; accepts "1", "2", "yes", "no"
  "choice"  — numbered list from the supplied *choices*; accepts index or text
  "text"    — free-form input(), no validation
"""

import sys
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def ask_user(
    prompt: str,
    choices: Optional[List[str]] = None,
    question_type: str = "text",
    target_variable: Optional[str] = None,
    app: Any = None,
) -> Dict[str, Any]:
    """Prompt the user for interactive input.

    Parameters
    ----------
    prompt:
        The question or instruction displayed to the user.
    choices:
        For "choice" questions, the list of valid answers.  For "yesno"
        questions this is ignored (yes/no are always the options).
        Leave *None* for free-text input.
    question_type:
        "yesno" | "choice" | "text"  (default "text").
    target_variable:
        If provided, the answer is saved into ``app.buffer_manager`` under
        this script-variable name.
    app:
        The running ``ChatybotApp`` instance.  Pass *None* only in tests.

    Returns
    -------
    dict
        ``{"status": "success", "answer": <str>, "target_variable": <str|None>}``
        or
        ``{"status": "skipped", "reason": <str>}``
        or
        ``{"status": "error",   "reason": <str>}``
    """
    if not _is_interactive(app):
        reason = (
            "running in script/batch mode" if _in_script(app) else "non-interactive stdin"
        )
        return {"status": "skipped", "reason": reason}

    try:
        answer = _prompt_user(prompt, choices, question_type)
    except (EOFError, KeyboardInterrupt):
        return {"status": "error", "reason": "input interrupted"}

    if target_variable and app is not None:
        try:
            app.buffer_manager.set_script_var(target_variable, answer)
        except Exception as exc:  # pragma: no cover
            return {"status": "error", "reason": f"Failed to set variable: {exc}"}

    return {"status": "success", "answer": answer, "target_variable": target_variable}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _in_script(app: Any) -> bool:
    """Return True when a .chatdsl script is currently executing."""
    return bool(app and getattr(app, "script_context", False))


def _is_interactive(app: Any) -> bool:
    """Return True only when a human is likely at the keyboard."""
    if _in_script(app):
        return False
    if not sys.stdin.isatty():
        return False
    return True


def _prompt_user(prompt: str, choices: Optional[List[str]], question_type: str) -> str:
    """Display the prompt and read a validated answer from stdin."""
    if question_type == "yesno":
        choices = ["yes", "no"]
        question_type = "choice"

    if question_type == "choice" and choices:
        return _prompt_choice(prompt, choices)

    # Free-text
    return input(f"{prompt}: ").strip()


def _prompt_choice(prompt: str, choices: List[str]) -> str:
    """Display a numbered menu and return the chosen text value."""
    print(f"\n{prompt}")
    for i, option in enumerate(choices, 1):
        print(f"  {i}. {option}")

    choices_lower = [c.lower() for c in choices]
    while True:
        raw = input(f"Enter choice (1-{len(choices)}): ").strip().lower()
        if raw.isdigit():
            idx = int(raw)
            if 1 <= idx <= len(choices):
                return choices[idx - 1]
        elif raw in choices_lower:
            # Return with the original casing
            return choices[choices_lower.index(raw)]
        print(f"  Invalid — enter a number (1-{len(choices)}) or one of: {', '.join(choices)}")
