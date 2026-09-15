"""
Interactive user-prompt utilities for Chatybot.

Provides a single ask_user() entry point that is shared by:
  - The /ask slash command  (commands/interact.py)
  - The LLM tool dispatch   (chatybot_app.dispatch_tool / tool name "ask_user")

Batch-mode guard
----------------
The function returns {"status": "skipped"} without blocking only when
sys.stdin.isatty() is False (redirected input, piped stdin, CI runner,
etc.). When stdin is attached to a real TTY, interactive prompts will
always prompt the user, even during script execution.

Supported question types
------------------------
  "yesno"   — numbered list [1. yes  2. no]; accepts "1", "2", "yes", "no"
  "choice"  — numbered list from the supplied *choices*; accepts index or text
  "text"    — free-form input(), no validation
"""

import os
import sys
from typing import Any

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def ask_user(
    prompt: str,
    choices: list[str] | None = None,
    question_type: str = "text",
    target_variable: str | None = None,
    app: Any = None,
) -> dict[str, Any]:
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
    Batch-mode guard
    ----------------
    The function returns {"status": "skipped"} without blocking only when
    sys.stdin.isatty() is False (non-interactive stdin, pipes, CI runners,
    redirected input, etc.). If stdin is a TTY, it prompts the user even
    during script execution.
    """
    if not _is_interactive(app):
        reason = "background process" if sys.stdin.isatty() else "non-interactive stdin"
        return {"status": "skipped", "reason": reason}

    try:
        answer = _prompt_user(prompt, choices, question_type)
    except (EOFError, KeyboardInterrupt):
        return {"status": "error", "reason": "input interrupted"}

    # Always set the reserved/protected script variable ASK_RESULT
    if app is not None and hasattr(app, "buffer_manager") and app.buffer_manager:
        try:
            app.buffer_manager.set_script_var("ASK_RESULT", answer, allow_protected=True)
        except Exception:  # pragma: no cover
            pass

    if target_variable and app is not None:
        try:
            app.buffer_manager.set_script_var(target_variable, answer)
        except Exception as exc:  # pragma: no cover
            return {"status": "error", "reason": f"Failed to set variable: {exc}"}

    return {
        "status": "success",
        "answer": answer,
        "target_variable": target_variable,
        "reserved_variable": "ASK_RESULT",
    }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _is_interactive(app: Any = None) -> bool:
    """Return True only when stdin is a TTY and the process is in the foreground.

    If a process is placed in the background (e.g. ``cmd &``), reading from stdin
    triggers SIGTTIN and causes the process to be suspended by the OS.
    Checking ``os.getpgrp() == os.tcgetpgrp(sys.stdin.fileno())`` detects background
    jobs and skips interactive prompts cleanly without suspension.
    """
    if not sys.stdin.isatty():
        return False
    try:
        # Check if current process group is the terminal's foreground process group
        return os.getpgrp() == os.tcgetpgrp(sys.stdin.fileno())
    except (OSError, AttributeError, ValueError):
        # Platform does not support tcgetpgrp or fileno is not available
        return True


def _prompt_user(prompt: str, choices: list[str] | None, question_type: str) -> str:
    """Display the prompt and read a validated answer from stdin."""
    if question_type == "yesno":
        choices = ["yes", "no"]
        question_type = "choice"

    if question_type == "choice" and choices:
        return _prompt_choice(prompt, choices)

    # Free-text
    print(f"\n{prompt}")
    return input("Answer: ").strip()


def _prompt_choice(prompt: str, choices: list[str]) -> str:
    """Display a numbered menu and return the chosen text value."""
    print(f"\n{prompt}\n")
    for i, option in enumerate(choices, 1):
        print(f"  [{i}] {option}")

    print()
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

