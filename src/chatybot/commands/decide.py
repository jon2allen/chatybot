"""Structured decision command: /decide

Evaluates content against a typed question (choice, score, or noul) using
a TypeSafe Jev / OpenRouter decisions model. Stores the scalar answer in
the DECIDE protected variable (and an optional user-named var), and the
full structured response in DECIDE_FULL.
"""

import os
import re
import traceback

from chatybot.commands.context import CommandContext
from chatybot.commands.registry import CommandResult, command


@command(
    "/decide",
    help="Evaluate content with a structured decision model (TypeSafe Jev)",
    args='"<state>" <choice|score|noul> "<instructions>" [, options="key:desc,..."] [, levels="lvl0,lvl1,..."] [, var=<name>] [, model=<alias>]',
    category="decision",
)
async def cmd_decide(ctx: CommandContext, parts: list, command: str) -> CommandResult:
    app = ctx.app
    from ..env_utils import load_project_env_files
    load_project_env_files()

    # ── Parse: state (first quoted string) ──────────────────────────
    state_match = re.search(r'^/decide\s+["\']([^"\']+)["\']', command, re.IGNORECASE)
    if not state_match:
        print(
            'Usage: /decide "<state>" <choice|score|noul> "<instructions>" '
            '[, options="key:desc,..."] [, levels="lvl0,lvl1,..."] [, var=<name>] [, model=<alias>]'
        )
        return CommandResult.ok()

    state = state_match.group(1)
    remainder = command[state_match.end():].strip()

    # ── Parse: question type (bare word) ─────────────────────────────
    type_match = re.match(r'(\w+)', remainder)
    if not type_match:
        print("Error: specify question type: choice, score, or noul")
        return CommandResult.ok()

    question_type = type_match.group(1).lower()
    if question_type not in ("choice", "score", "noul"):
        print(f"Error: unknown question type '{question_type}'. Use: choice, score, or noul")
        return CommandResult.ok()

    remainder = remainder[type_match.end():].strip()

    # ── Parse: instructions (second quoted string) ──────────────────
    instr_match = re.match(r'["\']([^"\']+)["\']', remainder)
    if not instr_match:
        print("Error: provide instructions as a quoted string after the question type")
        return CommandResult.ok()

    instructions = instr_match.group(1)
    remainder = remainder[instr_match.end():].strip()

    # ── Parse: key=value options ────────────────────────────────────
    options_match = re.search(r'\boptions\s*=\s*["\']([^"\']+)["\']', remainder, re.IGNORECASE)
    levels_match = re.search(r'\blevels\s*=\s*["\']([^"\']+)["\']', remainder, re.IGNORECASE)
    var_match = re.search(r'\bvar\s*=\s*(\S+)', remainder, re.IGNORECASE)
    model_match = re.search(r'\bmodel\s*=\s*(\S+)', remainder, re.IGNORECASE)

    target_var = var_match.group(1).strip().lstrip("$") if var_match else None
    model_alias = model_match.group(1).strip() if model_match else None

    # ── Build the question body ────────────────────────────────────
    question_key = "q"
    question_body: dict = {"type": question_type, "instructions": instructions}

    if question_type == "choice":
        if not options_match:
            print('Error: choice questions require options="key:desc,key:desc,..."')
            return CommandResult.ok()
        criteria: dict[str, str | None] = {}
        for pair in options_match.group(1).split(","):
            pair = pair.strip()
            if not pair:
                continue
            if ":" in pair:
                k, v = pair.split(":", 1)
                criteria[k.strip()] = v.strip()
            else:
                criteria[pair] = None
        if not criteria:
            print("Error: no valid options parsed from options= parameter")
            return CommandResult.ok()
        question_body["criteria"] = criteria

    elif question_type == "score":
        if not levels_match:
            print('Error: score questions require levels="lvl0,lvl1,lvl2,..."')
            return CommandResult.ok()
        levels = [lvl.strip() for lvl in levels_match.group(1).split(",") if lvl.strip()]
        if len(levels) < 2:
            print("Error: score questions need at least 2 levels")
            return CommandResult.ok()
        question_body["criteria"] = levels

    # noul needs no criteria

    questions = {question_key: question_body}

    # ── Resolve model config ───────────────────────────────────────
    decision_model_config = None

    if model_alias:
        try:
            decision_model_config = app.config_manager.get_model_config(model_alias)
            if decision_model_config and decision_model_config.get("type") != "decision":
                print(f"Error: model '{model_alias}' is type '{decision_model_config.get('type')}', not 'decision'")
                return CommandResult.ok()
        except Exception:
            print(f"Error: model '{model_alias}' not found")
            return CommandResult.ok()

    if not decision_model_config:
        active_alias = app.config_manager.active_model_alias
        if active_alias:
            try:
                active_model_config = app.config_manager.get_model_config(active_alias)
                if active_model_config and active_model_config.get("type") == "decision":
                    decision_model_config = active_model_config
            except Exception:
                pass

    if not decision_model_config:
        for alias, config in app.config_manager.config.get("models", {}).items():
            if config.get("type") == "decision":
                decision_model_config = config
                break

    if not decision_model_config:
        print("Error: No decision model is configured. Add a model with type=\"decision\" to your config.")
        return CommandResult.ok()

    model_name = decision_model_config.get("name", "typesafe/jev-1.13")
    base_url = decision_model_config.get("base_url", "https://openrouter.ai")
    endpoint_path = decision_model_config.get("endpoint_path", "/api/alpha/decisions")
    api_key_env = decision_model_config.get("api_key", "")
    api_key = os.environ.get(api_key_env) if api_key_env else None

    if not api_key:
        from ..env_utils import resolve_api_key
        api_key = resolve_api_key(api_key_env)

    if not api_key:
        print(f"Error: API key '{api_key_env}' is not set. Set the environment variable or provide a raw key.")
        return CommandResult.ok()

    # ── Call the API ───────────────────────────────────────────────
    from ..decision_client import evaluate, DecisionAPIError

    print(f"Evaluating with {model_name}...")
    try:
        response = await evaluate(
            state=state,
            questions=questions,
            model_name=model_name,
            base_url=base_url,
            endpoint_path=endpoint_path,
            api_key=api_key,
        )
    except DecisionAPIError as e:
        print(f"Decision API error ({e.status}): {e.body}")
        return CommandResult.ok()
    except Exception as e:
        print(f"Error calling decision model: {e!s}")
        traceback.print_exc()
        return CommandResult.ok()

    # ── Extract scalar answer ──────────────────────────────────────
    answers = response.get("answers", {})
    answer = answers.get(question_key, {})
    ans_type = answer.get("type", question_type)

    if ans_type == "choice":
        scalar = answer.get("choice", "")
    elif ans_type == "score":
        scalar = str(answer.get("score", 0.0))
    elif ans_type == "noul":
        scalar = str(answer.get("noul", 0.0))
    else:
        scalar = str(answer)

    # ── Store variables ─────────────────────────────────────────────
    app.buffer_manager.set_script_var("DECIDE", scalar, allow_protected=True)
    app.buffer_manager.set_script_var("DECIDE_FULL", response, allow_protected=True)
    if target_var:
        app.buffer_manager.set_script_var(target_var, scalar, allow_protected=True)

    # ── Display ────────────────────────────────────────────────────
    confidence = answer.get("confidence")
    print()
    print(f"  Question:  {instructions}")
    if ans_type == "choice":
        print(f"  Answer:     {scalar}", end="")
        if confidence is not None:
            print(f"  (confidence: {confidence:.2f})")
        else:
            print()
        probs = answer.get("probabilities", {})
        if probs:
            print()
            print("  Probabilities:")
            for opt, prob in sorted(probs.items(), key=lambda x: x[1], reverse=True):
                print(f"    {opt:<20} {prob:.2f}")
    elif ans_type == "score":
        print(f"  Score:      {scalar}", end="")
        if confidence is not None:
            print(f"  (confidence: {confidence:.2f})")
        else:
            print()
        probs = answer.get("probabilities", {})
        legend = answer.get("legend", {})
        if probs:
            print()
            print("  Probabilities:")
            for lvl, prob in sorted(probs.items(), key=lambda x: int(x[0])):
                label = legend.get(lvl, lvl)
                print(f"    {label:<30} {prob:.2f}")
    elif ans_type == "noul":
        print(f"  Probability: {scalar}", end="")
        if confidence is not None:
            print(f"  (confidence: {confidence:.2f})")
        else:
            print()

    usage = response.get("usage", {})
    if usage:
        print()
        print(f"  Tokens: {usage.get('input_tokens', 0)} in / {usage.get('output_tokens', 0)} out")

    saved_to = "DECIDE"
    if target_var:
        saved_to += f", ${target_var}"
    print(f"  Saved to {saved_to}")
    print()

    return CommandResult.ok()
