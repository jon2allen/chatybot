"""Prompt caching controls: /cachekey.

Implements the ChatDSL command surface of the prompt-caching proposal
(doc/proposal_prompt_caching_and_cache_key_controls.md §5.4):
inspect the active cache key binding, rebind it (session / profile /
custom name), toggle cache-key emission, and view cache telemetry.
"""

from chatybot.commands.context import CommandContext
from chatybot.commands.registry import CommandResult, command
from chatybot.config_model import compute_hit_pct, detect_provider

CACHEKEY_USAGE = "Usage: /cachekey [status|session|reset|profile|set <name>|on|off]"

PROVIDER_DISPLAY_LABELS: dict[str, str] = {
    "openrouter": "OpenRouter",
    "mistral": "Mistral AI",
    "openai": "OpenAI",
    "google": "Google Gemini",
    "nvidia": "NVIDIA NIM",
    "bytez": "Bytez",
    "jina": "Jina AI",
    "ollama": "Local (Ollama)",
    "llama_cpp": "Local (llama.cpp)",
    "local": "Local (vLLM/Ollama)",
    "publicai": "PublicAI",
    "huggingface": "Hugging Face",
    "apple_fm": "Apple Foundation Model",
}


def _detect_provider_label(app) -> str:
    model_config = app.config_manager.get_model_config(app.config_manager.active_model_alias)
    provider = detect_provider(model_config)
    if provider in PROVIDER_DISPLAY_LABELS:
        return PROVIDER_DISPLAY_LABELS[provider]
    base_url = (model_config.get("base_url") or "").lower() if isinstance(model_config, dict) else ""
    return base_url or "unknown"


def _print_cache_status(app, i18n) -> None:
    model_config = app.config_manager.get_model_config(app.config_manager.active_model_alias)
    if app.prompt_caching_disabled:
        status_label = i18n.get_ui_string("ui.cache_status_disabled", "Disabled")
    elif getattr(app, "custom_cache_key", None):
        status_label = i18n.get_ui_string("ui.cache_status_custom", "Custom Key")
    else:
        status_label = i18n.get_ui_string("ui.cache_status_auto", "Enabled (Auto Session)")
    active_key = app._resolve_prompt_cache_key(model_config) or "(off)"

    cached = getattr(app, "last_cached_tokens", 0)
    written = getattr(app, "last_cache_write_tokens", 0)
    print(f"[{i18n.get_ui_string('ui.cache_status', 'Prompt Cache Status')}]")
    print(f"  {i18n.get_ui_string('ui.cache_status_label', 'Status:')}           {status_label}")
    print(f"  {i18n.get_ui_string('ui.cache_active_key', 'Active Key:')}       {active_key}")
    print(f"  {i18n.get_ui_string('ui.cache_provider', 'Provider:')}         {_detect_provider_label(app)}")
    if cached or written:
        last_prompt_tokens = getattr(app, "last_prompt_tokens", 0)
        hit_pct = compute_hit_pct(cached, last_prompt_tokens)
        print(
            f"  {i18n.get_ui_string('ui.cache_cached_tokens', 'Cached Tokens:')}    "
            f"{cached:,} read ({hit_pct:.0f}% last-turn hit rate)"
        )
        print(
            f"  {i18n.get_ui_string('ui.cache_write_tokens', 'Write Tokens:')}     "
            f"{written:,} written to cache (warm-up surcharge factored in net savings)"
        )
        sess_cached = getattr(app, "session_cached_tokens", 0)
        sess_written = getattr(app, "session_cache_write_tokens", 0)
        sess_prompt = getattr(app, "session_prompt_tokens", 0)
        if sess_prompt:
            sess_hit = compute_hit_pct(sess_cached, sess_prompt)
            write_str = f", {sess_written:,} written" if sess_written else ""
            print(
                f"  {i18n.get_ui_string('ui.cache_session_hit', 'Session Hit Rate:')}  "
                f"{sess_cached:,}/{sess_prompt:,} tokens ({sess_hit:.0f}% overall{write_str})"
            )
        savings = app._compute_cache_net_savings(model_config, cached, written)
        if savings is not None:
            print(
                f"  {i18n.get_ui_string('ui.cache_net_savings', 'Est. Net Savings:')} "
                f"${savings:.4f} (last turn, net of warm-up write cost)"
            )
    else:
        print(f"  {i18n.get_ui_string('ui.cache_no_data', 'No cache telemetry yet (no completion reported cached tokens).')}")


@command(
    "/cachekey",
    help="View or control prompt-cache key binding and cache telemetry",
    args="[status|session|reset|profile|set <name>|on|off]",
    category="model",
)
async def cmd_cachekey(ctx: CommandContext, parts: list, command: str) -> CommandResult:
    app = ctx.app
    i18n = ctx.i18n
    sub = parts[1].strip().lower() if len(parts) >= 2 else "status"

    if sub in ("status", ""):
        _print_cache_status(app, i18n)
        return CommandResult.ok()

    if sub in ("session", "reset"):
        app.custom_cache_key = None
        app.prompt_caching_disabled = False
        if app.active_session_id:
            print(
                i18n.get_ui_string(
                    "ui.cache_reset_session",
                    "Cache key reset to the active session: chatybot-{cache_key}",
                    cache_key=app.active_session_id,
                )
            )
        else:
            print(
                i18n.get_ui_string(
                    "ui.cache_reset_no_session",
                    "Custom key cleared. No active session; key will fall back to the active profile.",
                )
            )
        return CommandResult.ok()

    if sub == "profile":
        profile_name = getattr(app, "active_profile_name", None) or "general"
        app.custom_cache_key = f"chatybot-profile-{profile_name}"
        app.prompt_caching_disabled = False
        print(
            i18n.get_ui_string(
                "ui.cache_bound_profile",
                "Cache key bound to active profile: {cache_key}",
                cache_key=app.custom_cache_key,
            )
        )
        return CommandResult.ok()

    if sub == "set":
        if len(parts) < 3 or not parts[2].strip():
            print("Usage: /cachekey set <name>")
            return CommandResult.ok()
        name = parts[2].strip()
        # Cache keys may appear in provider-side logs; refuse obviously
        # secret-shaped values rather than letting them leak.
        lowered = name.lower()
        if any(marker in lowered for marker in ("api_key", "apikey", "secret", "password", "token=", "bearer ")):
            print("Error: cache keys must not contain secrets; use an opaque identifier (see /help cachekey).")
            return CommandResult.error()
        app.custom_cache_key = name
        app.prompt_caching_disabled = False
        print(i18n.get_ui_string("ui.cache_set", "Cache key set to: {cache_key}", cache_key=name))
        return CommandResult.ok()

    if sub == "off":
        app.prompt_caching_disabled = True
        print(i18n.get_ui_string("ui.cache_off", "Prompt cache-key emission disabled (this session only)."))
        return CommandResult.ok()

    if sub == "on":
        app.prompt_caching_disabled = False
        print(i18n.get_ui_string("ui.cache_on", "Prompt cache-key emission enabled."))
        return CommandResult.ok()

    print(f"Unknown subcommand '{sub}'. {CACHEKEY_USAGE}")
    return CommandResult.error()
