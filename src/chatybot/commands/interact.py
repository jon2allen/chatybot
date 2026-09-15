"""Interactive user-prompt command for Chatybot.

Registers the /ask command which presents a yes/no, multiple-choice, or
free-text prompt to the user and stores the answer in a script variable.

Syntax
------
  /ask "Question?"                             -> free-text, no variable stored
  /ask "Question?" -> VARNAME                  -> free-text, stored in VARNAME
  /ask yesno "Continue?" -> VARNAME            -> yes/no choice
  /ask choice "Pick one:" opt1 opt2 -> VARNAME -> numbered list of choices

The command is silently skipped (with a notice) when:
  - stdin is not a TTY (pipe, CI runner, redirected file, etc.)
"""

import re
import shlex
from typing import List, Optional, Tuple

from chatybot.commands.context import CommandContext
from chatybot.commands.registry import CommandResult, command
from chatybot.tools.interact_utils import ask_user

# ---------------------------------------------------------------------------
# Command handler
# ---------------------------------------------------------------------------

@command(
    "/ask",
    help="Prompt user for input (skipped if stdin is not a TTY)",
    args='[yesno|choice] "<question>" [opt1 opt2 ...] [-> VARNAME]',
    category="interact",
)
async def cmd_ask(ctx: CommandContext, parts: list, command: str) -> CommandResult:
    """Interactively prompt the user for yes/no, choice, or free-text input.

    Examples
    --------
    /ask "Continue?"
    /ask "Continue?" -> CONTINUE
    /ask yesno "Overwrite existing file?" -> OVERWRITE
    /ask choice "Select model:" gpt-4 claude gemini -> MODEL
    """
    app = ctx.app

    # Strip the "/ask" verb and parse the remainder
    raw_args = command.split(maxsplit=1)[1].strip() if len(parts) > 1 else ""
    if not raw_args:
        print("Usage: /ask [yesno|choice] \"<question>\" [opt1 opt2 ...] [-> VARNAME]")
        return CommandResult.ok()

    prompt, choices, target_var, question_type = _parse_ask_args(raw_args)

    if not prompt:
        print("Error: /ask requires a question string.")
        return CommandResult.ok()

    result = ask_user(
        prompt=prompt,
        choices=choices,
        question_type=question_type,
        target_variable=target_var,
        app=app,
    )

    if result["status"] == "skipped":
        print(f"[ask] Skipped — {result['reason']}")
    elif result["status"] == "error":
        print(f"[ask] Error — {result['reason']}")
    else:
        answer = result["answer"]
        if target_var:
            print(f"[ask] {answer!r} -> ${target_var} (also in $ASK_RESULT)")
        else:
            print(f"[ask] {answer!r} -> $ASK_RESULT")

    return CommandResult.ok()


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------

def _parse_ask_args(raw: str) -> tuple[str, list[str] | None, str | None, str]:
    """Parse /ask arguments into (prompt, choices, target_var, question_type).

    Grammar (informal):
        [yesno|choice] <quoted-or-word prompt> [opt ...] [-> VARNAME]

    Returns
    -------
    prompt       : str
    choices      : list[str] | None
    target_var   : str | None
    question_type: "yesno" | "choice" | "text"
    """
    # Extract optional "-> VARNAME" at the end
    target_var: str | None = None
    arrow_match = re.search(r"->\s*([a-zA-Z_]\w*)\s*$", raw)
    if arrow_match:
        target_var = arrow_match.group(1)
        raw = raw[: arrow_match.start()].rstrip()

    # Tokenise with shlex so quoted strings stay together
    try:
        tokens = shlex.split(raw)
    except ValueError:
        tokens = raw.split()

    if not tokens:
        return "", None, target_var, "text"

    # Check for explicit type keyword as first token
    question_type = "text"
    if tokens[0].lower() in ("yesno", "choice"):
        question_type = tokens[0].lower()
        tokens = tokens[1:]

    if not tokens:
        return "", None, target_var, question_type

    # First remaining token is the prompt
    prompt = tokens[0]
    extra_tokens = tokens[1:]

    # Remaining tokens become the choices list (overrides yesno if provided)
    choices: list[str] | None = None
    if extra_tokens:
        choices = extra_tokens
        if question_type == "text":
            question_type = "choice"
    elif question_type == "choice":
        # "choice" keyword was given but no options → treat as text
        question_type = "text"

    return prompt, choices, target_var, question_type
