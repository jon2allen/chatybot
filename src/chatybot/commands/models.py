"""Model configuration and sampling parameter commands.

Migrated from chatybot.handle_escape_command elif chain:
  /model, /system, /temp, /maxtokens, /max_tokens, /context_limit,
  /auto_truncate, /top_p, /top_k, /freq_penalty, /pres_penalty,
  /reasoning, /effort, /thinking, /thoughtstyle, /seed, /stream,
  /listmodels
"""

from chatybot.commands.registry import command, CommandResult, registry
from chatybot.commands.context import CommandContext


@command("/model", help="Switch or view the active chat model", args="[alias|info [alias]]", category="models")
async def cmd_model(ctx: CommandContext, parts: list, command: str) -> CommandResult:
    app = ctx.app
    is_info = False
    model_alias = None

    if len(parts) >= 2:
        p1 = parts[1].strip().lower()
        if p1 == "info":
            is_info = True
            model_alias = app.config_manager.active_model_alias
        elif len(parts) >= 3 and parts[2].strip().lower() == "info":
            is_info = True
            model_alias = parts[1].strip()

    if is_info:
        model_config = app.config_manager.get_model_config(model_alias)
        if not model_config:
            print(f"Error: Model alias '{model_alias}' not found in configuration.")
            return CommandResult.ok()

        model_name = model_config.get("name", "Unknown")
        context_window = None
        source = "Local Preset"

        if model_config.get("context_limit"):
            context_window = model_config.get("context_limit")
            source = "Config (Override)"
        else:
            try:
                client = app.get_openai_client(model_alias)
                model_info = await client.models.retrieve(model_name)
                if hasattr(model_info, "context_window"):
                    context_window = getattr(model_info, "context_window")
                    source = "API (Live)"
                elif hasattr(model_info, "max_context_length"):
                    context_window = getattr(model_info, "max_context_length")
                    source = "API (Live)"
                elif isinstance(model_info, dict):
                    context_window = model_info.get("context_window") or model_info.get("max_context_length")
                    source = "API (Live)"
                elif hasattr(model_info, "extra_data") and isinstance(model_info.extra_data, dict):
                    context_window = model_info.extra_data.get("context_window") or model_info.extra_data.get("max_context_length")
                    source = "API (Live)"
            except Exception:
                pass

        if context_window is not None and not isinstance(context_window, (int, float)):
            try:
                context_window = int(context_window)
            except (ValueError, TypeError):
                context_window = None

        # Fallback local presets
        if not context_window:
            presets = {
                "gpt-4o": 128000,
                "gpt-4o-mini": 128000,
                "gpt-4": 8192,
                "gpt-4-turbo": 128000,
                "o1": 200000,
                "o1-mini": 128000,
                "o3-mini": 200000,
                "claude-3-5-sonnet": 200000,
                "claude-3-5-haiku": 200000,
                "claude-3-opus": 200000,
                "gemini-2.5-pro": 2097152,
                "gemini-2.5-flash": 1048576,
                "gemini-1.5-pro": 2097152,
                "gemini-1.5-flash": 1048576,
                "gemini-2.0-flash": 1048576,
                "gemini": 1048576,
                "mistral-large-latest": 128000,
                "mistral-large-2512": 128000,
                "mistral-medium-latest": 32768,
                "mistral-small-latest": 32768,
                "codestral-latest": 32768,
                "devstral_1": 32768,
                "devstral": 32768,
                "nemotron": 128000,
                "kimi": 262144,
                "llama-3.3": 128000,
                "llama-3.2": 128000,
                "llama-3.1": 128000,
                "llama-3": 8192,
                "gemma-2-9b-it": 8192,
                "gemma-2-27b-it": 8192,
                "qwen2.5-coder-32b-instruct": 128000,
                "deepseek-coder": 128000,
                "deepseek-chat": 128000,
                "deepseek-reasoner": 64000
            }
            for key, val in presets.items():
                if key in model_name.lower():
                    context_window = val
                    break

        print(f"\nModel Information: {model_name} (alias: {model_alias})")
        print("-" * (20 + len(model_name) + len(model_alias)))
        print(f"Provider:        {model_config.get('vendor', 'Unknown')}")
        print(f"Base URL:        {model_config.get('base_url', 'Default')}")

        if context_window:
            if context_window >= 1000:
                cw_str = f"{context_window:,} tokens ({context_window // 1000}k)"
            else:
                cw_str = f"{context_window} tokens"
            print(f"Context Limit:   {cw_str} [{source}]")
        else:
            print(f"Context Limit:   Unknown")

        max_tok = model_config.get("max_tokens")
        if max_tok:
            print(f"Max Output:      {max_tok} tokens (Configured)")

        temp = model_config.get("temperature")
        if temp is not None:
            print(f"Temperature:     {temp}")
        print("")
        return CommandResult.ok()

    if len(parts) < 2:
        # Show current model
        model_config = app.config_manager.get_model_config(
            app.config_manager.active_model_alias
        )
        print(
            f"Current model: {model_config['name']} (alias: {app.config_manager.active_model_alias})"
        )
        return CommandResult.ok()

    model_alias = parts[1]
    app.config_manager.set_active_model(model_alias)
    model_config = app.config_manager.get_model_config(model_alias)
    model_limit = model_config.get("context_limit")
    if hasattr(app, "context_limiter"):
        if model_limit:
            if not app.context_limiter._user_set_limit:
                app.context_limiter.set_limit(model_limit, from_user=False)
        else:
            # Model has no context_limit defined in config.
            # Retain any active context_limit (from user or previous model)
            if app.context_limiter.context_limit:
                print(
                    f"[Warning: Context limit is set to {app.context_limiter.context_limit:,} tokens, and that will be used because none is defined in configuration for model '{model_alias}'.]"
                )
    print(f"Switched to model: {model_config['name']} (alias: {model_alias})")
    return CommandResult.ok()


@command("/system", help="Set or view the system message", args="[<message>]", category="models")
async def cmd_system(ctx: CommandContext, parts: list, command: str) -> CommandResult:
    app = ctx.app
    if len(parts) < 2:
        print(f"Current system message: {app.config_manager.system_message}")
        return CommandResult.ok()

    app.config_manager.system_message = command.split(maxsplit=1)[1].strip(
        " \"'"
    )
    print(f"System message updated: {app.config_manager.system_message}")
    return CommandResult.ok()


@command("/temp", help="Set generation temperature", args="[<0.0-2.0>|default]", category="models")
async def cmd_temp(ctx: CommandContext, parts: list, command: str) -> CommandResult:
    app = ctx.app
    if len(parts) < 2:
        current_temp = (
            app.temperature
            if app.temperature is not None
            else app.config_manager.get_model_config(
                app.config_manager.active_model_alias
            ).get("temperature", 0.7)
        )
        print(f"Current temperature: {current_temp}")
        return CommandResult.ok()

    arg = parts[1].strip().lower()
    if arg in ["default", "reset"]:
        app.temperature = None
        print("Temperature reset to model default")
        return CommandResult.ok()

    try:
        temp = float(arg)
        if not 0.0 <= temp <= 2.0:
            raise ValueError
        app.temperature = temp
        print(f"Temperature set to {temp}")
    except ValueError:
        print(
            "Invalid temperature value. Please provide a number between 0.0 and 2.0, or 'default'."
        )
    return CommandResult.ok()


async def _cmd_maxtokens(ctx: CommandContext, parts: list, command: str) -> CommandResult:
    app = ctx.app
    if len(parts) < 2:
        current_max = (
            app.config_manager.max_tokens
            if app.config_manager.max_tokens is not None
            else app.config_manager.get_model_config(
                app.config_manager.active_model_alias
            ).get("max_tokens", "Default")
        )
        print(f"Current max tokens: {current_max}")
        return CommandResult.ok()

    try:
        max_tokens = int(parts[1])
        if max_tokens <= 0:
            raise ValueError
        app.config_manager.max_tokens = max_tokens
        print(f"Max tokens set to {max_tokens}")
    except ValueError:
        print("Invalid max tokens value. Please provide a positive integer.")
    return CommandResult.ok()


registry.register("/maxtokens", _cmd_maxtokens, help="Set max output tokens", args="[<n>]", category="models")
registry.register("/max_tokens", _cmd_maxtokens, help="Set max output tokens", args="[<n>]", category="models")


@command("/context_limit", help="Set or view the context token limit", args="[<tokens>|off]", category="models")
async def cmd_context_limit(ctx: CommandContext, parts: list, command: str) -> CommandResult:
    app = ctx.app
    if len(parts) < 2:
        curr = app.context_limiter.context_limit
        if curr:
            print(f"Current context limit: {curr} tokens")
        else:
            print("Context limit is disabled (no limit set)")
        return CommandResult.ok()

    val_str = parts[1].strip().lower()
    if val_str in ("off", "0", "none", "disable", "disabled"):
        app.context_limiter.set_limit(None, from_user=True)
        print("Context limit disabled.")
    else:
        try:
            limit_val = int(val_str)
            if limit_val <= 0:
                app.context_limiter.set_limit(None, from_user=True)
                print("Context limit disabled.")
            else:
                app.context_limiter.set_limit(limit_val, from_user=True)
                print(f"Context limit set to {limit_val} tokens.")
        except ValueError:
            print("Invalid context limit. Usage: /context_limit <tokens>|off")

    if app.tool_mode:
        context = app.generate_tool_context()
        if hasattr(app, "buffer_manager"):
            app.buffer_manager.set_script_var('TOOL_CONTEXT', context)
    return CommandResult.ok()


@command("/auto_truncate", help="Enable/disable auto-truncation at context limit", args="[on|off|10-100]", category="models")
async def cmd_auto_truncate(ctx: CommandContext, parts: list, command: str) -> CommandResult:
    app = ctx.app
    if len(parts) < 2:
        if app.context_limiter.auto_truncate:
            pct_str = f" ({int(app.context_limiter.truncate_pct)}%)" if app.context_limiter.truncate_pct != 100.0 else ""
            print(f"Auto-truncation is currently enabled{pct_str}.")
        else:
            print("Auto-truncation is currently disabled.")
        return CommandResult.ok()

    opt = parts[1].strip().lower()
    if opt in ("on", "true", "enable", "yes"):
        app.context_limiter.set_auto_truncate(True, pct=100.0)
        print("Auto-truncation enabled at 100% of context limit.")
    elif opt in ("off", "false", "disable", "no"):
        app.context_limiter.set_auto_truncate(False)
        print("Auto-truncation disabled.")
    else:
        num_str = opt.rstrip("%")
        try:
            pct_val = float(num_str)
            if pct_val > 100.0:
                print("Error: Auto-truncate percentage cannot exceed 100%. Usage: /auto_truncate [on|off|10-100]")
            elif pct_val < 10.0:
                app.context_limiter.set_auto_truncate(False)
                print("Auto-truncation disabled (percentage below 10%).")
            else:
                display_pct = int(pct_val) if pct_val.is_integer() else pct_val
                app.context_limiter.set_auto_truncate(True, pct=pct_val)
                print(f"Auto-truncation enabled at {display_pct}% of context limit.")
        except ValueError:
            print("Invalid option. Usage: /auto_truncate [on|off|10-100]")
    return CommandResult.ok()


@command("/top_p", help="Set or view top_p sampling parameter", args="[<0.0-1.0>|off|default]", category="models")
async def cmd_top_p(ctx: CommandContext, parts: list, command: str) -> CommandResult:
    app = ctx.app
    if len(parts) < 2:
        if app.top_p in ("off", "none", "disable", False):
            current_tp = "Disabled (off)"
        elif app.top_p is not None:
            current_tp = app.top_p
        else:
            cfg_tp = app.config_manager.get_model_config(
                app.config_manager.active_model_alias
            ).get("top_p", "Default")
            current_tp = f"{cfg_tp} (model default)"
        print(f"Current top_p: {current_tp}")
        return CommandResult.ok()

    arg = parts[1].strip().lower()
    if arg in ["off", "none", "disable"]:
        app.top_p = "off"
        print("top_p disabled (will not be sent in payloads)")
    elif arg in ["default", "reset"]:
        app.top_p = None
        print("top_p reset to model default")
    else:
        try:
            val = float(arg)
            if not 0.0 <= val <= 1.0:
                raise ValueError
            app.top_p = val
            print(f"top_p set to {val}")
        except ValueError:
            print("Invalid top_p value. Please enter a float between 0.0 and 1.0, 'off', 'none', or 'default'.")
    return CommandResult.ok()


@command("/top_k", help="Set or view top_k sampling parameter", args="[<int>|off|default]", category="models")
async def cmd_top_k(ctx: CommandContext, parts: list, command: str) -> CommandResult:
    app = ctx.app
    if len(parts) < 2:
        if app.top_k in ("off", "none", "disable", False):
            current_tk = "Disabled (off)"
        elif app.top_k is not None:
            current_tk = app.top_k
        else:
            cfg_tk = app.config_manager.get_model_config(
                app.config_manager.active_model_alias
            ).get("top_k", "Default")
            current_tk = f"{cfg_tk} (model default)"
        print(f"Current top_k: {current_tk}")
        return CommandResult.ok()

    arg = parts[1].strip().lower()
    if arg in ["off", "none", "disable"]:
        app.top_k = "off"
        print("top_k disabled (will not be sent in payloads)")
    elif arg in ["default", "reset"]:
        app.top_k = None
        print("top_k reset to model default")
    else:
        try:
            val = int(arg)
            if val <= 0:
                raise ValueError
            app.top_k = val
            print(f"top_k set to {val}")
        except ValueError:
            print("Invalid top_k value. Please enter a positive integer, 'off', 'none', or 'default'.")
    return CommandResult.ok()


@command("/freq_penalty", help="Set or view frequency penalty", args="[<float>|off|default]", category="models")
async def cmd_freq_penalty(ctx: CommandContext, parts: list, command: str) -> CommandResult:
    app = ctx.app
    if len(parts) < 2:
        if app.freq_penalty in ("off", "none", "disable", False):
            current_fp = "Disabled (off)"
        elif app.freq_penalty is not None:
            current_fp = app.freq_penalty
        else:
            cfg_fp = app.config_manager.get_model_config(
                app.config_manager.active_model_alias
            ).get("frequency_penalty", "Default")
            current_fp = f"{cfg_fp} (model default)"
        print(f"Current frequency penalty: {current_fp}")
        return CommandResult.ok()

    arg = parts[1].strip().lower()
    if arg in ["off", "none", "disable"]:
        app.freq_penalty = "off"
        print("Frequency penalty disabled (will not be sent in payloads)")
    elif arg in ["default", "reset"]:
        app.freq_penalty = None
        print("Frequency penalty reset to model default")
    else:
        try:
            val = float(arg)
            app.freq_penalty = val
            print(f"Frequency penalty set to {val}")
        except ValueError:
            print("Invalid frequency penalty value. Please enter a float, 'off', 'none', or 'default'.")
    return CommandResult.ok()


@command("/pres_penalty", help="Set or view presence penalty", args="[<float>|off|default]", category="models")
async def cmd_pres_penalty(ctx: CommandContext, parts: list, command: str) -> CommandResult:
    app = ctx.app
    if len(parts) < 2:
        if app.pres_penalty in ("off", "none", "disable", False):
            current_pp = "Disabled (off)"
        elif app.pres_penalty is not None:
            current_pp = app.pres_penalty
        else:
            cfg_pp = app.config_manager.get_model_config(
                app.config_manager.active_model_alias
            ).get("presence_penalty", "Default")
            current_pp = f"{cfg_pp} (model default)"
        print(f"Current presence penalty: {current_pp}")
        return CommandResult.ok()

    arg = parts[1].strip().lower()
    if arg in ["off", "none", "disable"]:
        app.pres_penalty = "off"
        print("Presence penalty disabled (will not be sent in payloads)")
    elif arg in ["default", "reset"]:
        app.pres_penalty = None
        print("Presence penalty reset to model default")
    else:
        try:
            val = float(arg)
            app.pres_penalty = val
            print(f"Presence penalty set to {val}")
        except ValueError:
            print("Invalid presence penalty value. Please enter a float, 'off', 'none', or 'default'.")
    return CommandResult.ok()


@command("/reasoning", help="Toggle reasoning mode on/off", args="[on|off]", category="models")
async def cmd_reasoning(ctx: CommandContext, parts: list, command: str) -> CommandResult:
    app = ctx.app
    if len(parts) > 1 and parts[1].lower() in ["on", "off"]:
        if parts[1].lower() == "on":
            app.reasoning_mode = True
        else:
            app.reasoning_mode = False
        print(f"Reasoning mode is now {'ON' if app.reasoning_mode else 'OFF'}")
    else:
        print(
            f"Reasoning mode is currently {'ON' if app.reasoning_mode else 'OFF'}"
        )
    return CommandResult.ok()


@command("/effort", help="Set or view reasoning effort level", args="[low|medium|high|xhigh|none]", category="models")
async def cmd_effort(ctx: CommandContext, parts: list, command: str) -> CommandResult:
    app = ctx.app
    active_alias = app.config_manager.active_model_alias
    active_config = (
        app.config_manager.get_model_config(active_alias) if active_alias else {}
    )
    model_name = active_config.get("name", active_alias or "").lower()
    active_alias_lower = (active_alias or "").lower()
    is_muse = (
        any(x in model_name for x in ["muse", "glimmer"])
        or any(x in active_alias_lower for x in ["muse", "glimmer"])
    )

    if len(parts) > 1:
        effort = parts[1].lower()
        allowed_efforts = ["low", "medium", "high", "xhigh", "none"]
        if effort in allowed_efforts:
            app.reasoning_effort = effort if effort != "none" else None
            if is_muse:
                if app.reasoning_effort is None:
                    print("Reasoning effort disabled for Muse (reasoning_strength cleared).")
                else:
                    print(
                        f"Active model is Muse Glimmer: setting reasoning_strength to '{effort}' (via chat_template_kwargs)."
                    )
            else:
                if app.reasoning_effort is None:
                    print("Reasoning effort set to none (disabled).")
                else:
                    print(f"Reasoning effort set to {effort}")
        else:
            if is_muse:
                print("Invalid effort level for Muse. Use: low, medium, high, xhigh, or none")
            else:
                print("Invalid effort level. Use: low, medium, high, xhigh, or none")
    else:
        if is_muse:
            if app.reasoning_effort:
                print(
                    f"Active model is Muse Glimmer: reasoning_strength is currently '{app.reasoning_effort}'"
                )
            else:
                print(
                    "Active model is Muse Glimmer: reasoning_strength is currently not set (default)"
                )
        else:
            if app.reasoning_effort:
                print(f"Reasoning effort is currently: {app.reasoning_effort}")
            else:
                print("Reasoning effort is currently: none (not set)")
    return CommandResult.ok()


@command("/thinking", help="Toggle thinking display on/off", args="[on|off]", category="models")
async def cmd_thinking(ctx: CommandContext, parts: list, command: str) -> CommandResult:
    app = ctx.app
    if len(parts) > 1 and parts[1].lower() in ["on", "off"]:
        if parts[1].lower() == "on":
            app.show_thinking = True
        else:
            app.show_thinking = False
        print(
            f"Thinking display is now {'ON' if app.show_thinking else 'OFF'}"
        )
    else:
        print(
            f"Thinking display is currently {'ON' if app.show_thinking else 'OFF'}"
        )
    return CommandResult.ok()


@command("/thoughtstyle", help="Set or view thought style", args="[none|gemma4|nanbeige|nanbeige_code]", category="models")
async def cmd_thoughtstyle(ctx: CommandContext, parts: list, command: str) -> CommandResult:
    app = ctx.app
    if len(parts) > 1:
        style = parts[1].lower()
        if style in ["none", "gemma4", "nanbeige", "nanbeige_code"]:
            app.thoughtstyle = style
            print(f"Thought style set to: {style}")
        else:
            print("Invalid thought style. Use 'none', 'gemma4', 'nanbeige', or 'nanbeige_code'.")
    else:
        print(f"Current thought style: {app.thoughtstyle}")
    return CommandResult.ok()


@command("/seed", help="Set or view the random seed", args="[<int>|time|random <min>,<max>|clear]", category="models")
async def cmd_seed(ctx: CommandContext, parts: list, command: str) -> CommandResult:
    app = ctx.app
    if len(parts) < 2:
        print(f"Current seed setting: {app.seed_config}")
        return CommandResult.ok()

    arg = parts[1].lower()
    if arg in ["clear", "none", "off"]:
        app.seed_config = None
        print("Seed cleared.")
    elif arg == "time":
        app.seed_config = "time"
        print("Seed set to 'time' (uses Unix timestamp per completion).")
    elif arg == "random":
        if len(parts) < 3:
            print("Usage: /seed random <min>, <max>")
            return CommandResult.ok()
        try:
            # Handle both "random 1,999" and "random 1, 999"
            range_str = parts[2]
            if "," not in range_str:
                print("Usage: /seed random <min>, <max>")
                return CommandResult.ok()
            v1_str, v2_str = range_str.split(",", 1)
            v1 = int(v1_str.strip())
            v2 = int(v2_str.strip())
            app.seed_config = ("random", v1, v2)
            print(f"Seed set to random range: {v1} to {v2}")
        except ValueError:
            print("Invalid range. Use: /seed random <min>, <max>")
    else:
        try:
            seed_val = int(parts[1])
            app.seed_config = seed_val
            print(f"Seed set to fixed value: {seed_val}")
        except ValueError:
            print(
                "Invalid seed. Use an integer, 'time', or 'random <min>, <max>'."
            )
    return CommandResult.ok()


@command("/stream", help="Toggle streaming responses on/off", args="", category="models")
async def cmd_stream(ctx: CommandContext, parts: list, command: str) -> CommandResult:
    app = ctx.app
    app.streaming_enabled = not app.streaming_enabled
    print(
        f"Streaming responses {'enabled' if app.streaming_enabled else 'disabled'}"
    )
    return CommandResult.ok()


@command("/listmodels", help="List all configured models", args="", category="models")
async def cmd_listmodels(ctx: CommandContext, parts: list, command: str) -> CommandResult:
    ctx.app.config_manager.list_models()
    return CommandResult.ok()
