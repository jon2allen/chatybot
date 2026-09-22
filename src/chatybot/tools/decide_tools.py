"""
Decision tools for LLM tool calling in Chatybot.
Evaluates content against structured questions (score, choice, noul) using
the default TypeSafe Jev / OpenRouter decision model.

Disabled by default in tools_config.toml; enable with:
    /tool enable decide_score
    /tool enable decide_choice
    /tool enable decide_noul
    # or all:
    /tool enable decide_*
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import os
import re
from typing import Any

from ..decision_client import DecisionAPIError, evaluate
from ..env_utils import load_project_env_files, resolve_api_key


def _run_async(coro):
    """Run an async coroutine synchronously, handling any existing event loops."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(lambda: asyncio.run(coro))
            return future.result()
    return asyncio.run(coro)


def _resolve_decision_config(model_alias: str | None = None, app: Any = None) -> tuple[dict[str, Any], str]:
    """Resolve the decision model configuration and API key."""
    load_project_env_files()

    decision_model_config = None
    config_manager = getattr(app, "config_manager", None)
    if not config_manager:
        try:
            from ..config_manager import ConfigManager
            config_manager = ConfigManager()
            config_manager.load_config()
        except Exception:
            config_manager = None

    if config_manager:
        if model_alias:
            try:
                cfg = config_manager.get_model_config(model_alias)
                if cfg and cfg.get("type") == "decision":
                    decision_model_config = cfg
            except Exception:
                pass

        if not decision_model_config:
            active_alias = getattr(config_manager, "active_model_alias", None)
            if active_alias:
                try:
                    cfg = config_manager.get_model_config(active_alias)
                    if cfg and cfg.get("type") == "decision":
                        decision_model_config = cfg
                except Exception:
                    pass

        if not decision_model_config:
            for _, cfg in config_manager.config.get("models", {}).items():
                if isinstance(cfg, dict) and cfg.get("type") == "decision":
                    decision_model_config = cfg
                    break

    if not decision_model_config:
        decision_model_config = {
            "name": "typesafe/jev-1.13",
            "type": "decision",
            "base_url": "https://openrouter.ai",
            "endpoint_path": "/api/alpha/decisions",
            "api_key": "OPENROUTER_API_KEY",
        }

    api_key_env = decision_model_config.get("api_key", "OPENROUTER_API_KEY")
    api_key = os.environ.get(api_key_env) if api_key_env else None
    if not api_key:
        api_key = resolve_api_key(api_key_env)

    return decision_model_config, api_key or ""


def _execute_decision(
    question_type: str,
    state: str,
    instructions: str,
    criteria: Any = None,
    threshold: float = 0.0,
    model_alias: str | None = None,
    target_variable: str | None = None,
    app: Any = None,
) -> dict[str, Any]:
    """Internal runner for structured decision evaluations."""
    model_cfg, api_key = _resolve_decision_config(model_alias=model_alias, app=app)

    if not api_key:
        api_key_env = model_cfg.get("api_key", "OPENROUTER_API_KEY")
        return {
            "status": "error",
            "message": f"API key '{api_key_env}' is not set. Set the environment variable or configure the decision model.",
            "result": None,
        }

    model_name = model_cfg.get("name", "typesafe/jev-1.13")
    base_url = model_cfg.get("base_url", "https://openrouter.ai")
    endpoint_path = model_cfg.get("endpoint_path", "/api/alpha/decisions")

    q_body: dict[str, Any] = {
        "type": question_type,
        "instructions": instructions,
    }
    if criteria is not None:
        q_body["criteria"] = criteria

    questions = {"q": q_body}

    try:
        response = _run_async(
            evaluate(
                state=state,
                questions=questions,
                model_name=model_name,
                base_url=base_url,
                endpoint_path=endpoint_path,
                api_key=api_key,
            )
        )
    except DecisionAPIError as e:
        return {
            "status": "error",
            "message": f"Decision API error ({e.status}): {e.body}",
            "result": None,
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Error calling decision model: {e!s}",
            "result": None,
        }

    answers = response.get("answers", {})
    answer = answers.get("q", {})
    if not answer and answers:
        answer = next(iter(answers.values()))

    ans_type = answer.get("type", question_type)

    if ans_type == "choice":
        raw_result = str(answer.get("choice", ""))
    elif ans_type == "score":
        raw_result = str(answer.get("score", ""))
    elif ans_type == "noul":
        noul_val = answer.get("answer", answer.get("noul", 0.0))
        if isinstance(noul_val, bool):
            raw_result = "true" if noul_val else "false"
        elif isinstance(noul_val, (int, float)):
            raw_result = "true" if float(noul_val) >= 0.5 else "false"
        else:
            raw_result = str(noul_val).lower()
    else:
        raw_result = str(answer.get("choice") or answer.get("answer") or answer or "")

    confidence = answer.get("confidence")
    if confidence is None:
        if ans_type == "noul":
            confidence = float(answer.get("noul", answer.get("answer", 0.0)) or 0.0)
        else:
            confidence = 0.0
    try:
        confidence = float(confidence)
    except (ValueError, TypeError):
        confidence = 0.0

    probabilities = answer.get("probabilities", {})
    if not isinstance(probabilities, dict):
        probabilities = {}

    top_prob = float(probabilities.get(raw_result, confidence)) if probabilities else confidence

    is_fallback = threshold > 0.0 and confidence < threshold and ans_type != "noul"
    final_output = "FALLBACK" if is_fallback else raw_result

    result_payload: dict[str, Any] = {
        "status": "success",
        "type": question_type,
        "result": final_output,
        "raw_answer": raw_result,
        "confidence": round(confidence, 4),
        "top_probability": round(top_prob, 4),
        "probabilities": probabilities,
        "is_fallback": is_fallback,
        "model": model_name,
    }

    if question_type == "score":
        result_payload["score"] = final_output
    elif question_type == "choice":
        result_payload["choice"] = final_output
    elif question_type == "noul":
        result_payload["answer"] = final_output

    target_set = str(target_variable).strip().lstrip("$") if target_variable else None
    if target_set:
        result_payload["target_variable"] = target_set
        if app and hasattr(app, "buffer_manager"):
            app.buffer_manager.set_script_var(target_set, final_output, allow_protected=True)
            app.buffer_manager.set_script_var(f"{target_set}_conf", f"{confidence:.2f}")
            app.buffer_manager.set_script_var(f"{target_set}_prob", f"{top_prob:.2f}")

    return result_payload


def decide_score(
    state: str,
    instructions: str,
    scale: str | None = "1:10",
    levels: list[str] | str | None = None,
    threshold: float = 0.0,
    model: str | None = None,
    target_variable: str | None = None,
    app: Any = None,
) -> dict[str, Any]:
    """
    Evaluate content against a numeric scale or ordered qualitative rubric levels
    using the default TypeSafe Jev decision model.

    Args:
        state: Target content, answer, draft, or context to evaluate.
        instructions: Scoring criteria or rubric prompt.
        scale: Integer scale formatted as 'min:max' (e.g. '1:10', '1:5', '-2:2'). Default '1:10'.
        levels: Optional list of 2-10 ordered qualitative levels (e.g. ['poor', 'fair', 'good', 'excellent']).
                If levels are provided, scale is ignored.
        threshold: Minimum confidence threshold (0.0 to 1.0). If confidence < threshold,
                   result is 'FALLBACK'.
        model: Optional decision model alias from configuration.
        target_variable: Optional variable name to store the winning score.
        app: ChatybotApp instance passed when called within application context.

    Returns:
        Structured JSON dictionary with score, confidence, probabilities, and model.
    """
    if levels:
        if isinstance(levels, str):
            parsed_levels = [lvl.strip() for lvl in levels.split(",") if lvl.strip()]
        elif isinstance(levels, (list, tuple)):
            parsed_levels = [str(lvl).strip() for lvl in levels if str(lvl).strip()]
        else:
            return {
                "status": "error",
                "message": f"Invalid levels format: expected list of strings, got {type(levels).__name__}",
                "result": None,
            }
        if len(parsed_levels) < 2:
            return {
                "status": "error",
                "message": "Score levels must contain at least 2 categories.",
                "result": None,
            }
        if len(parsed_levels) > 10:
            return {
                "status": "error",
                "message": f"Score levels supports at most 10 categories, got {len(parsed_levels)}.",
                "result": None,
            }
        criteria = parsed_levels
    else:
        effective_scale = str(scale or "1:10").strip()
        m = re.match(r"^(-?\d+)\s*:\s*(-?\d+)$", effective_scale)
        if not m:
            return {
                "status": "error",
                "message": f"Invalid scale '{effective_scale}'. Format must be 'min:max' (e.g. '1:10', '1:5').",
                "result": None,
            }
        lo, hi = int(m.group(1)), int(m.group(2))
        if lo >= hi:
            return {
                "status": "error",
                "message": f"Scale min ({lo}) must be less than max ({hi}).",
                "result": None,
            }
        count = hi - lo + 1
        if count < 2:
            return {
                "status": "error",
                "message": "Scale must span at least 2 points.",
                "result": None,
            }
        if count > 10:
            return {
                "status": "error",
                "message": f"Scale span ({count} points) exceeds maximum of 10 points. Use 10 or fewer levels.",
                "result": None,
            }
        criteria = [str(n) for n in range(lo, hi + 1)]

    return _execute_decision(
        question_type="score",
        state=state,
        instructions=instructions,
        criteria=criteria,
        threshold=float(threshold or 0.0),
        model_alias=model,
        target_variable=target_variable,
        app=app,
    )


def decide_choice(
    state: str,
    instructions: str,
    options: dict[str, str] | list[str] | str,
    threshold: float = 0.0,
    model: str | None = None,
    target_variable: str | None = None,
    app: Any = None,
) -> dict[str, Any]:
    """
    Select the best option from a discrete set of choices with calibrated confidence
    using the default TypeSafe Jev decision model.

    Args:
        state: Target content, draft, context, or code to evaluate.
        instructions: Instructions explaining the decision criteria.
        options: Choices to evaluate. Can be:
                 - A dictionary: {"option_a": "description", "option_b": "description"}
                 - A list of option names: ["option_a", "option_b"]
                 - A string formatted as 'key:desc,key:desc' or 'key,key'
        threshold: Minimum confidence threshold (0.0 to 1.0). If confidence < threshold,
                   result is 'FALLBACK'.
        model: Optional decision model alias from configuration.
        target_variable: Optional variable name to store the winning choice.
        app: ChatybotApp instance passed when called within application context.

    Returns:
        Structured JSON dictionary with choice, confidence, probabilities, and model.
    """
    criteria: dict[str, str] = {}

    if isinstance(options, dict):
        criteria = {str(k).strip(): str(v).strip() for k, v in options.items() if str(k).strip()}
    elif isinstance(options, (list, tuple)):
        for item in options:
            item_str = str(item).strip()
            if not item_str:
                continue
            if ":" in item_str:
                k, v = item_str.split(":", 1)
                criteria[k.strip()] = v.strip()
            else:
                criteria[item_str] = item_str
    elif isinstance(options, str):
        raw_options = options.strip()
        if ";" in raw_options:
            pairs = raw_options.split(";")
        elif "|" in raw_options:
            pairs = raw_options.split("|")
        elif ":" in raw_options:
            pairs = re.split(r",\s*(?=[a-zA-Z0-9_\-]+\s*:)", raw_options)
        else:
            pairs = raw_options.split(",")

        for p in pairs:
            p = p.strip()
            if not p:
                continue
            if ":" in p:
                k, v = p.split(":", 1)
                criteria[k.strip()] = v.strip()
            else:
                criteria[p] = p
    else:
        return {
            "status": "error",
            "message": f"Invalid options format: expected dict or list, got {type(options).__name__}",
            "result": None,
        }

    if not criteria:
        return {
            "status": "error",
            "message": "At least one option must be provided for decide_choice.",
            "result": None,
        }

    return _execute_decision(
        question_type="choice",
        state=state,
        instructions=instructions,
        criteria=criteria,
        threshold=float(threshold or 0.0),
        model_alias=model,
        target_variable=target_variable,
        app=app,
    )


def decide_noul(
    state: str,
    instructions: str,
    threshold: float = 0.0,
    model: str | None = None,
    target_variable: str | None = None,
    app: Any = None,
) -> dict[str, Any]:
    """
    Evaluate a binary proposition or verification check (true/false) with calibrated
    probability and confidence using the default TypeSafe Jev decision model.

    Args:
        state: Target content, assertion, draft, or context to evaluate.
        instructions: The question, proposition, or verification condition to evaluate.
        threshold: Minimum confidence threshold (0.0 to 1.0). If confidence < threshold,
                   result is 'FALLBACK'.
        model: Optional decision model alias from configuration.
        target_variable: Optional variable name to store the boolean result ('true'/'false').
        app: ChatybotApp instance passed when called within application context.

    Returns:
        Structured JSON dictionary with answer ('true'/'false'), confidence, and probability.
    """
    return _execute_decision(
        question_type="noul",
        state=state,
        instructions=instructions,
        criteria=None,
        threshold=float(threshold or 0.0),
        model_alias=model,
        target_variable=target_variable,
        app=app,
    )
