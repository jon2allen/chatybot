"""
Context metrics tool for LLM tool calling and script execution in Chatybot.
Returns the current size of context in characters, KB, and estimated average tokens
for session history, agentic tool loop, prompt buffers, and total payload context.
"""

from typing import Dict, Any, Optional, List, Union
import json
import math


def calculate_metrics(text: str) -> Dict[str, Any]:
    """Calculate character count, byte size, KB size, and estimated tokens for a given string."""
    chars = len(text)
    encoded_bytes = text.encode("utf-8")
    byte_count = len(encoded_bytes)
    kb = round(byte_count / 1024, 2)
    # Industry standard estimate: ~4 characters/bytes per token for English text
    estimated_tokens = max(1, math.ceil(byte_count / 4)) if byte_count > 0 else 0
    return {
        "characters": chars,
        "bytes": byte_count,
        "kb": kb,
        "estimated_tokens": estimated_tokens,
    }


def get_context_metrics(
    scope: str = "all",
    target_variable: Optional[str] = None,
    app: Any = None,
) -> Dict[str, Any]:
    """
    Get the current size of the context in characters, KB, and estimated average tokens.

    Args:
        scope: Scope to inspect: 'all' (default), 'session' (session history only),
               or 'agentic_loop' (agentic tool loop history only).
        target_variable: Optional script variable name to save the metrics dictionary into.
        app: ChatybotApp instance passed when called within application context.

    Returns:
        Dict containing status, scope, detailed size metrics, and formatted summary.
    """
    valid_scopes = ("all", "session", "agentic_loop", "buffers")
    norm_scope = scope.lower().strip() if scope else "all"
    if norm_scope not in valid_scopes:
        norm_scope = "all"

    # Default empty metrics
    session_text_parts: List[str] = []
    session_turns = 0
    loop_text_parts: List[str] = []
    loop_turns = 0
    buffer_text_parts: List[str] = []

    if app:
        # Extract Session context
        if hasattr(app, "chat_history") and app.chat_history:
            session_turns = len(app.chat_history)
            for p, r in app.chat_history:
                session_text_parts.append(str(p or ""))
                session_text_parts.append(str(r or ""))
        elif hasattr(app, "session_turns") and app.session_turns:
            session_turns = len(app.session_turns)
            for turn in app.session_turns:
                session_text_parts.append(str(turn.get("prompt", "")))
                session_text_parts.append(str(turn.get("response", "")))

        # Extract Agentic Loop context
        if hasattr(app, "buffer_manager") and app.buffer_manager:
            loop_var = app.buffer_manager.get_script_var("AGENTIC_LOOP")
            if isinstance(loop_var, list):
                loop_turns = len(loop_var)
                for item in loop_var:
                    if isinstance(item, dict):
                        loop_text_parts.append(json.dumps(item, default=str))
                    else:
                        loop_text_parts.append(str(item))

            # Prompt & File buffers if available
            if hasattr(app.buffer_manager, "prompt_buffer") and app.buffer_manager.prompt_buffer:
                buffer_text_parts.append(str(app.buffer_manager.prompt_buffer))
            if hasattr(app.buffer_manager, "file_buffer") and app.buffer_manager.file_buffer:
                buffer_text_parts.append(str(app.buffer_manager.file_buffer))
            if hasattr(app.buffer_manager, "file_banks") and app.buffer_manager.file_banks:
                for bank_name, bank_content in app.buffer_manager.file_banks.items():
                    if bank_content:
                        buffer_text_parts.append(str(bank_content))

        # Include System prompt if configured
        if hasattr(app, "config_manager") and app.config_manager:
            sys_msg = getattr(app.config_manager, "system_message", "")
            if sys_msg:
                buffer_text_parts.append(str(sys_msg))

    session_full_text = "\n".join(session_text_parts)
    loop_full_text = "\n".join(loop_text_parts)
    buffer_full_text = "\n".join(buffer_text_parts)
    total_full_text = "\n".join(session_text_parts + loop_text_parts + buffer_text_parts)

    session_metrics = calculate_metrics(session_full_text)
    session_metrics["turns"] = session_turns

    loop_metrics = calculate_metrics(loop_full_text)
    loop_metrics["turns"] = loop_turns
    loop_metrics["records"] = loop_turns

    total_turns = session_turns + loop_turns
    total_metrics = calculate_metrics(total_full_text)
    total_metrics["total_turns"] = total_turns
    total_metrics["session_turns"] = session_turns
    total_metrics["agentic_loop_turns"] = loop_turns

    response: Dict[str, Any] = {
        "status": "success",
        "scope": norm_scope,
    }

    # Extract context limit settings if configured on app
    context_limit_info: Optional[Dict[str, Any]] = None
    if app:
        effective_limit = None
        auto_truncate = False
        truncate_pct = 100.0
        if hasattr(app, "context_limiter") and app.context_limiter:
            effective_limit = app.context_limiter.context_limit
            auto_truncate = app.context_limiter.auto_truncate
            truncate_pct = app.context_limiter.truncate_pct

        if not effective_limit and hasattr(app, "config_manager") and app.config_manager:
            try:
                active_alias = app.config_manager.active_model_alias
                m_cfg = app.config_manager.get_model_config(active_alias)
                if m_cfg and m_cfg.get("context_limit"):
                    effective_limit = m_cfg.get("context_limit")
            except Exception:
                pass

        if effective_limit and effective_limit > 0:
            used_tokens = total_metrics["estimated_tokens"]
            rem_tokens = max(0, effective_limit - used_tokens)
            usage_pct = round((used_tokens / effective_limit) * 100.0, 1)
            context_limit_info = {
                "limit_tokens": effective_limit,
                "used_tokens": used_tokens,
                "remaining_tokens": rem_tokens,
                "usage_percent": usage_pct,
                "auto_truncate": auto_truncate,
                "truncate_percent": truncate_pct if auto_truncate else None,
            }

    if context_limit_info:
        response["context_limit"] = context_limit_info

    limit_suffix = ""
    if context_limit_info:
        eff_lim = context_limit_info["limit_tokens"]
        u_pct = context_limit_info["usage_percent"]
        r_tok = context_limit_info["remaining_tokens"]
        a_trunc = context_limit_info["auto_truncate"]
        t_pct = context_limit_info["truncate_percent"]
        trunc_str = f"ON ({int(t_pct)}%)" if a_trunc and t_pct else ("ON" if a_trunc else "OFF")
        limit_suffix = f" | Context Limit: {eff_lim:,} tokens ({u_pct}% used, {r_tok:,} tokens remaining, auto-truncate: {trunc_str})"

    if norm_scope == "session":
        response["session"] = session_metrics
        response["summary"] = (
            f"Session History: {session_metrics['characters']} chars, "
            f"{session_metrics['kb']} KB, ~{session_metrics['estimated_tokens']} tokens ({session_turns} turns){limit_suffix}"
        )
    elif norm_scope == "agentic_loop":
        response["agentic_loop"] = loop_metrics
        response["summary"] = (
            f"Agentic Loop: {loop_metrics['characters']} chars, "
            f"{loop_metrics['kb']} KB, ~{loop_metrics['estimated_tokens']} tokens ({loop_turns} turns){limit_suffix}"
        )
    elif norm_scope == "buffers":
        buffer_metrics = calculate_metrics(buffer_full_text)
        response["buffers"] = buffer_metrics
        response["summary"] = (
            f"Buffers & System: {buffer_metrics['characters']} chars, "
            f"{buffer_metrics['kb']} KB, ~{buffer_metrics['estimated_tokens']} tokens{limit_suffix}"
        )
    else:  # 'all'
        response["session"] = session_metrics
        response["agentic_loop"] = loop_metrics
        response["buffers"] = calculate_metrics(buffer_full_text)
        response["total"] = total_metrics
        response["summary"] = (
            f"Total Context: {total_metrics['characters']} chars, "
            f"{total_metrics['kb']} KB, ~{total_metrics['estimated_tokens']} estimated tokens across {total_turns} total turns "
            f"(Session: {session_metrics['kb']} KB / ~{session_metrics['estimated_tokens']} tokens [{session_turns} turns], "
            f"Agentic Loop: {loop_metrics['kb']} KB / ~{loop_metrics['estimated_tokens']} tokens [{loop_turns} turns]){limit_suffix}"
        )

    # Save to target variable if requested
    if target_variable and app and hasattr(app, "buffer_manager"):
        app.buffer_manager.set_script_var(str(target_variable).strip(), response, allow_protected=True)
        response["target_variable"] = str(target_variable).strip()

    return response
