"""Structured decision command: /decide

Evaluates content against a typed question (choice, score, or noul) using
a TypeSafe Jev / OpenRouter decisions model. Stores the scalar answer in
the DECIDE protected variable (and an optional user-named var), and the
full structured response in DECIDE_FULL.

Calibration unpacking: confidence and per-option probabilities are flattened
into dedicated script variables so ChatDSL scripts can gate actions on
uncertainty without JSON traversal.

Global registers:
  DECIDE       — latest choice/answer/score (or "FALLBACK" if below threshold)
  DECIDE_CONF  — calibrated confidence (0.00–1.00)
  DECIDE_PROB  — winning option probability
  DECIDE_FULL  — unmodified API payload

Per-var registers (when var=<name> is given):
  <name>              — decision result (or "FALLBACK")
  <name>_choice       — raw winning choice/boolean/score
  <name>_conf         — calibrated confidence
  <name>_confidence   — verbose alias for _conf
  <name>_prob         — probability of the selected option
  <name>_prob_<opt>   — probability per candidate option
"""

import os
import re
import traceback

from chatybot.commands.context import CommandContext
from chatybot.commands.registry import CommandResult, command


@command(
    "/decide",
    help="Evaluate content with a structured decision model (TypeSafe Jev)",
    args='"<state>" <choice|score|noul> "<instructions>" [, options="key:desc,..."] [, levels="lvl0,lvl1,..."] [, scale="min:max"] [, threshold=<float>] [, var=<name>] [, model=<alias>]',
    category="decision",
)
async def cmd_decide(ctx: CommandContext, parts: list, command: str) -> CommandResult:
    app = ctx.app
    from ..env_utils import load_project_env_files
    load_project_env_files()

    # ── Parse: state, question type, and instructions ─────────────
    # Split the command into positional arguments (state, type, instructions)
    # and optional key=value remainder. This allows instructions to contain
    # nested quotes without breaking regex capture.
    kw_match = re.search(r'\s+(?:options|levels|scale|var|model|threshold)\s*=', command, re.IGNORECASE)
    if kw_match:
        head = command[:kw_match.start()].strip()
        remainder = command[kw_match.start():].strip()
    else:
        head = command.strip()
        remainder = ""

    combined_match = re.match(
        r'^/\S+\s+["\'](.+?)["\']\s+(choice|score|noul)\s+["\'](.+?)["\']\s*$',
        head, re.IGNORECASE | re.DOTALL,
    )
    if not combined_match:
        # Fallback to direct prefix match for backwards compatibility
        combined_match = re.match(
            r'^/\S+\s+["\'](.+?)["\']\s+(choice|score|noul)\s+["\'](.+?)["\']',
            command, re.IGNORECASE | re.DOTALL,
        )
        if combined_match:
            remainder = command[combined_match.end():].strip()

    if not combined_match:
        print(
            'Usage: /decide "<state>" <choice|score|noul> "<instructions>" '
            '[, options="key:desc,..."] [, levels="lvl0,lvl1,..."] '
            '[, scale="min:max"] [, threshold=<float>] [, var=<name>] [, model=<alias>]'
        )
        return CommandResult.ok()

    state = combined_match.group(1)
    question_type = combined_match.group(2).lower()
    instructions = combined_match.group(3)

    # Resolve variables and placeholders in state and instructions
    if hasattr(app, "buffer_manager") and app.buffer_manager:
        bm = app.buffer_manager
        state_var = state.strip()
        if (state_var.startswith("${") and state_var.endswith("}")) or (state_var.startswith("$") and re.match(r'^\$[a-zA-Z_]\w*$', state_var)):
            clean_var = state_var[2:-1] if state_var.startswith("${") else state_var[1:]
            if clean_var in bm.script_vars:
                raw_val = bm.script_vars[clean_var]
                if isinstance(raw_val, str):
                    state = raw_val
                elif raw_val is not None:
                    state = str(raw_val)
            else:
                state, _ = bm.replace_placeholders(state, include_images=False, clear_unresolved=False)
        elif "$" in state or "{" in state:
            # Replace defined variables and placeholders while preserving exact whitespace
            keys_to_resolve = list(bm.script_vars.keys()) + ["LAST_RESPONSE", "CHAT_HISTORY"] + list(bm.file_banks.keys())
            sorted_keys = sorted(list(set(keys_to_resolve)), key=len, reverse=True)
            for k in sorted_keys:
                val = bm.resolve_text_variable(k)
                if val is not None:
                    flags = re.IGNORECASE if k.upper() in bm.script_vars.protected_vars or k.upper() in ("CHAT_HISTORY", "LAST_RESPONSE") else 0
                    state = re.sub(rf"\$?\{{{re.escape(k)}\}}", str(val), state, flags=flags)
                    state = re.sub(rf"\${re.escape(k)}\b", str(val), state, flags=flags)

        if "$" in instructions or "{" in instructions:
            instructions, _ = bm.replace_placeholders(instructions, include_images=False, clear_unresolved=False)

    if question_type not in ("choice", "score", "noul"):
        print(f"Error: unknown question type '{question_type}'. Use: choice, score, or noul")
        return CommandResult.ok()

    # ── Parse: key=value options ────────────────────────────────────
    options_match = re.search(r'\boptions\s*=\s*["\']([^"\']+)["\']', remainder, re.IGNORECASE)
    levels_match = re.search(r'\blevels\s*=\s*["\']([^"\']+)["\']', remainder, re.IGNORECASE)
    scale_match = re.search(r'\bscale\s*=\s*["\']?(\d+)\s*:\s*(\d+)["\']?', remainder, re.IGNORECASE)
    var_match = re.search(r'\bvar\s*=\s*(\S+)', remainder, re.IGNORECASE)
    model_match = re.search(r'\bmodel\s*=\s*(\S+)', remainder, re.IGNORECASE)
    threshold_match = re.search(r'\bthreshold\s*=\s*([0-9]*\.?[0-9]+)', remainder, re.IGNORECASE)

    target_var = var_match.group(1).strip().lstrip("$") if var_match else None
    model_alias = model_match.group(1).strip() if model_match else None
    threshold = float(threshold_match.group(1)) if threshold_match else 0.0
    if threshold > 0.0 and not (0.0 <= threshold <= 1.0):
        print(f"Error: threshold must be between 0.0 and 1.0, got {threshold}")
        return CommandResult.ok()

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
        if scale_match and not levels_match:
            # scale="min:max" — generate integer levels automatically
            lo, hi = int(scale_match.group(1)), int(scale_match.group(2))
            if lo >= hi:
                print(f"Error: scale min ({lo}) must be less than max ({hi})")
                return CommandResult.ok()
            levels = [str(n) for n in range(lo, hi + 1)]
        elif levels_match:
            levels = [lvl.strip() for lvl in levels_match.group(1).split(",") if lvl.strip()]
        else:
            print('Error: score questions require levels="lvl0,lvl1,..." or scale="min:max"')
            return CommandResult.ok()
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

    # ── Extract scalar answer and calibration metrics ─────────────
    answers = response.get("answers", {})
    answer = answers.get(question_key, {})
    if not answer and answers:
        answer = next(iter(answers.values()))
    ans_type = answer.get("type", question_type)

    if ans_type == "choice":
        raw_result = str(answer.get("choice", ""))
    elif ans_type == "score":
        raw_result = str(answer.get("score", ""))
    elif ans_type == "noul":
        # API may return "answer" (bool/str) or "noul" (float probability).
        # The noul probability serves as both the answer and the confidence
        # when no separate "confidence" field is present.
        noul_val = answer.get("answer", answer.get("noul", 0.0))
        if isinstance(noul_val, bool):
            raw_result = "true" if noul_val else "false"
        elif isinstance(noul_val, (int, float)):
            raw_result = "true" if float(noul_val) >= 0.5 else "false"
        else:
            raw_result = str(noul_val).lower()
    else:
        raw_result = str(answer.get("choice") or answer.get("answer") or answer)

    # Confidence: use explicit "confidence" field if present, otherwise
    # fall back to the noul probability for noul-type questions.
    confidence = answer.get("confidence")
    if confidence is None:
        if ans_type == "noul":
            confidence = float(answer.get("noul", answer.get("answer", 0.0)) or 0.0)
        else:
            confidence = 0.0
    confidence = float(confidence)
    probabilities = answer.get("probabilities", {})
    if not isinstance(probabilities, dict):
        probabilities = {}
    top_prob = float(probabilities.get(raw_result, confidence)) if probabilities else confidence

    # Evaluate optional fallback threshold.
    # Noul always returns true/false — the user can gate on _conf in
    # their script.  Threshold gating applies to choice and score only.
    is_fallback = threshold > 0.0 and confidence < threshold and ans_type != "noul"
    final_output = "FALLBACK" if is_fallback else raw_result

    # ── Store global registers ─────────────────────────────────────
    app.buffer_manager.set_script_var("DECIDE", final_output, allow_protected=True)
    app.buffer_manager.set_script_var("DECIDE_CONF", f"{confidence:.2f}", allow_protected=True)
    app.buffer_manager.set_script_var("DECIDE_PROB", f"{top_prob:.2f}", allow_protected=True)
    app.buffer_manager.set_script_var("DECIDE_FULL", response, allow_protected=True)

    # ── Store per-var flattened registers ──────────────────────────
    if target_var:
        app.buffer_manager.set_script_var(target_var, final_output, allow_protected=True)
        app.buffer_manager.set_script_var(f"{target_var}_choice", raw_result)
        app.buffer_manager.set_script_var(f"{target_var}_conf", f"{confidence:.2f}")
        app.buffer_manager.set_script_var(f"{target_var}_confidence", f"{confidence:.2f}")
        app.buffer_manager.set_script_var(f"{target_var}_prob", f"{top_prob:.2f}")

        # Flatten individual option probabilities
        for opt_name, opt_val in probabilities.items():
            clean_opt = str(opt_name).replace(" ", "_").replace("-", "_").lower()
            try:
                numeric_val = float(opt_val)
                app.buffer_manager.set_script_var(f"{target_var}_prob_{clean_opt}", f"{numeric_val:.2f}")
            except (ValueError, TypeError):
                continue

    # ── Display ────────────────────────────────────────────────────
    print()
    print(f"  Question:  {instructions}")
    if ans_type == "choice":
        print(f"  Answer:     {final_output}", end="")
        if is_fallback:
            print(f"  [FALLBACK — confidence {confidence:.2f} < threshold {threshold:.2f}]")
        elif confidence is not None:
            print(f"  (confidence: {confidence:.2f})")
        else:
            print()
        if probabilities:
            print()
            print("  Probabilities:")
            for opt, prob in sorted(probabilities.items(), key=lambda x: x[1], reverse=True):
                print(f"    {opt:<20} {prob:.2f}")
    elif ans_type == "score":
        print(f"  Score:      {final_output}", end="")
        if is_fallback:
            print(f"  [FALLBACK — confidence {confidence:.2f} < threshold {threshold:.2f}]")
        elif confidence is not None:
            print(f"  (confidence: {confidence:.2f})")
        else:
            print()
        probs = answer.get("probabilities", {})
        legend = answer.get("legend", {})
        if probs:
            print()
            print("  Probabilities:")
            for lvl, prob in sorted(probs.items(), key=lambda x: int(x[0]) if str(x[0]).isdigit() else 0):
                label = legend.get(lvl, lvl)
                print(f"    {label:<30} {prob:.2f}")
    elif ans_type == "noul":
        print(f"  Answer:     {final_output}", end="")
        if confidence is not None:
            print(f"  (confidence: {confidence:.2f})")
        else:
            print()

    usage = response.get("usage", {})
    if usage:
        print()
        print(f"  Tokens: {usage.get('input_tokens', 0)} in / {usage.get('output_tokens', 0)} out")

    saved_to = "DECIDE, DECIDE_CONF, DECIDE_PROB, DECIDE_FULL"
    if target_var:
        saved_to += f", ${target_var}, ${target_var}_choice, ${target_var}_conf, ${target_var}_prob"
    print(f"  Saved to {saved_to}")
    print()

    return CommandResult.ok()
