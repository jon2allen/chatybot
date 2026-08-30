"""Debug, inspection, and miscellaneous commands.

Migrated from chatybot_app.handle_escape_command elif chain:
  /trace, /debug, /prompt, /logging, /save, /notemode, /codeonly,
  /codeoff, /multiline, /env, /profile, /mem, /dump, /calc,
  /str_search, /setvar, /reloadmacros, /listmacros
"""

import json
import os
import re
import shlex

from chatybot.commands.registry import command, CommandResult, registry
from chatybot.commands.context import CommandContext
from chatybot.extract_code import process_file


@command("/trace", help="Toggle trace flags", args="<rawpayload|tps|tpsperf|imagedbg|rerank|agentic_loop> <on|off>", category="debug")
async def cmd_trace(ctx: CommandContext, parts: list, command: str) -> CommandResult:
    app = ctx.app
    if len(parts) >= 3:
        subcmd = parts[1].lower()
        state = parts[2].lower().strip()
        # Guard against trailing tokens (e.g. "/trace tps on please")
        # which maxsplit=2 would fold into state, silently disabling.
        extra = command.split()[3:]
        if extra:
            print(f"Error: unexpected argument(s) after '{state}': {' '.join(extra)}")
            print("Usage: /trace <rawpayload|tps|tpsperf|imagedbg|rerank|agentic_loop> <on|off>")
            return CommandResult.ok()
        if state not in ("on", "off"):
            print(f"Error: invalid state '{state}'. Use 'on' or 'off'.")
            print("Usage: /trace <rawpayload|tps|tpsperf|imagedbg|rerank|agentic_loop> <on|off>")
            return CommandResult.ok()
        is_on = state == "on"
        if subcmd == "rawpayload":
            app.trace_raw_payload = is_on
            print(f"Trace rawpayload set to {is_on}")
        elif subcmd == "tps":
            app.trace_tps = is_on
            print(f"Trace tps set to {is_on}")
        elif subcmd == "tpsperf":
            app.trace_tps_perf = is_on
            print(f"Trace tpsperf set to {is_on}")
        elif subcmd == "imagedbg":
            app.image_debug_mode = is_on
            print(f"Trace imagedbg set to {is_on}")
        elif subcmd == "rerank":
            app.trace_rerank = is_on
            print(f"Trace rerank set to {is_on}")
        elif subcmd == "agentic_loop":
            if not is_on:
                app.trace_agentic_loop = False
                print("Agentic loop trace display disabled.")
            else:
                app.trace_agentic_loop = True
                print("Agentic loop trace display enabled.")
        else:
            print("Unknown /trace subcommand. Use rawpayload, tps, tpsperf, imagedbg, rerank, or agentic_loop.")
    else:
        print("Usage: /trace <rawpayload|tps|tpsperf|imagedbg|rerank|agentic_loop> <on|off>")
    return CommandResult.ok()


@command("/debug", help="Debug modes", args="<payload|response [raw]|vmem [start|stop|status]>", category="debug")
async def cmd_debug(ctx: CommandContext, parts: list, command: str) -> CommandResult:
    app = ctx.app
    if len(parts) >= 2:
        subcmd = parts[1].lower()
        if subcmd == "payload":
            app.debug_payload_mode = True
            print("Debug payload mode activated. Next prompt will capture payload for editing.")
            print("After entering your prompt, the payload will be opened in your editor.")
        elif subcmd == "response":
            if len(parts) >= 3 and parts[2].lower() == "raw":
                app.debug_response_raw = True
                app.debug_response_mode = False
                print("Debug response raw mode activated. Next completion will print the raw response.")
            else:
                app.debug_response_mode = True
                app.debug_response_raw = False
                print("Debug response mode activated. Next completion will print a JSON dump of the response.")
        elif subcmd == "vmem":
            action = parts[2].lower() if len(parts) >= 3 else "status"
            if action == "start":
                app.start_vmem_monitoring()
            elif action == "stop":
                app.stop_vmem_monitoring()
            elif action == "status":
                app.show_vmem_status()
            else:
                print("Unknown vmem action. Use /debug vmem <start|stop|status>")
        else:
            print("Unknown /debug subcommand. Use payload, response, response raw, or vmem.")
    else:
        print("Usage: /debug <payload|response [raw]|vmem [start|stop|status]>")
    return CommandResult.ok()


@command("/prompt", help="Load a prompt from a file", args="<file>", category="debug")
async def cmd_prompt(ctx: CommandContext, parts: list, command: str) -> CommandResult:
    app = ctx.app
    if len(parts) < 2:
        print("Usage: /prompt <file>")
        return CommandResult.ok()

    file_path = command.split(maxsplit=1)[1].strip()
    # Strip a single matching pair of surrounding quotes only.
    if len(file_path) >= 2 and file_path[0] in "\"'" and file_path[-1] == file_path[0]:
        file_path = file_path[1:-1]
    expanded_path = os.path.expanduser(file_path)
    if not os.path.exists(expanded_path):
        print(f"Error: Prompt file not found: {expanded_path}")
        return CommandResult.ok()

    try:
        # Hard byte cap to catch accidental huge/binary loads.
        MAX_PROMPT_BYTES = 256 * 1024
        with open(expanded_path, "r", encoding="utf-8") as f:
            content = f.read()
        content_bytes = len(content.encode("utf-8"))
        if content_bytes > MAX_PROMPT_BYTES:
            print(
                f"Error: Prompt file '{expanded_path}' is {content_bytes:,} bytes, "
                f"exceeds the {MAX_PROMPT_BYTES:,}-byte limit."
            )
            return CommandResult.ok()

        # Cross-check against context_limit if known.
        if hasattr(app, "context_limiter") and app.context_limiter.context_limit:
            prompt_tokens = app.context_limiter.count_tokens_text(content)
            ctx_limit = app.context_limiter.context_limit
            if prompt_tokens > ctx_limit:
                print(
                    f"Error: Prompt file '{expanded_path}' is ~{prompt_tokens:,} tokens, "
                    f"exceeds the context limit of {ctx_limit:,} tokens."
                )
                return CommandResult.ok()
            if prompt_tokens > ctx_limit * 0.5:
                pct = (prompt_tokens / ctx_limit) * 100.0
                print(
                    f"Warning: Prompt is ~{prompt_tokens:,} tokens "
                    f"({pct:.0f}% of context limit {ctx_limit:,})."
                )

        if not content.strip():
            print(f"Error: Prompt file '{expanded_path}' is empty or whitespace-only.")
            return CommandResult.ok()

        app.buffer_manager.prompt_buffer = content
        print(f"\nPrompt loaded from '{expanded_path}':")
        print("-" * 40)
        preview_limit = 500
        if len(content) > preview_limit:
            print(content[:preview_limit] + f"\n... [{len(content) - preview_limit} more chars]")
        else:
            print(content)
        print("-" * 40)

        # Ask for confirmation only if not in script context
        if not app.script_context:
            try:
                while True:
                    confirm = (
                        input("\nExecute this prompt? (Y/N): ").strip().lower()
                    )
                    if confirm in ["y", "yes"]:
                        print("\nExecuting prompt...")
                        return CommandResult.execute_prompt(content)
                    elif confirm in ["n", "no"]:
                        app.buffer_manager.prompt_buffer = ""
                        print("Prompt discarded.")
                        return CommandResult.ok()
                    else:
                        print("Please enter Y or N.")
            except (EOFError, KeyboardInterrupt):
                app.buffer_manager.prompt_buffer = ""
                print("\nPrompt discarded.")
                return CommandResult.ok()
        else:
            # In script context, assume confirmation and return flag
            return CommandResult.execute_prompt(content)
    except Exception as e:
        app.buffer_manager.prompt_buffer = ""
        print(f"Error reading prompt file: {str(e)}")
    return CommandResult.ok()


@command("/logging", help="Control logging", args="<start [hex]|end|hex [on|off]>", category="debug")
async def cmd_logging(ctx: CommandContext, parts: list, command: str) -> CommandResult:
    app = ctx.app
    if len(parts) < 2:
        status = "active" if app.logging_manager.logging_active else "inactive"
        hex_status = "on" if app.logging_manager.hex_mode else "off"
        print(f"Logging is {status} (hex mode: {hex_status}). Usage: /logging <start [hex]|end|hex [on|off]>")
        return CommandResult.ok()

    action = parts[1].lower()
    sub_args = parts[2].split() if len(parts) > 2 else []

    if action == "start":
        hex_aliases = ("hex", "raw", "on")
        hex_mode = any(a.lower() in hex_aliases for a in sub_args)
        app.logging_manager.start_logging(hex_mode=hex_mode)
    elif action in ("hex", "hexmode"):
        off_aliases = ("off", "false", "disable")
        on_aliases = ("on", "true", "enable")
        if sub_args and sub_args[0].lower() in off_aliases:
            app.logging_manager.hex_mode = False
            print("Logging hex mode disabled.")
        elif sub_args and sub_args[0].lower() in on_aliases:
            app.logging_manager.hex_mode = True
            if not app.logging_manager.logging_active:
                app.logging_manager.start_logging(hex_mode=True)
            else:
                print("Logging hex mode enabled.")
        elif not sub_args:
            app.logging_manager.hex_mode = True
            if not app.logging_manager.logging_active:
                app.logging_manager.start_logging(hex_mode=True)
            else:
                print("Logging hex mode enabled.")
        else:
            print(f"Invalid hex mode argument '{sub_args[0]}'. Use 'on' or 'off'.")
    elif action in ("end", "stop"):
        app.logging_manager.stop_logging()
    else:
        print("Invalid logging action. Use 'start [hex]', 'hex [on|off]', or 'end'.")
    return CommandResult.ok()


@command("/save", help="Save chat history to a file", args="<file> [all] [nothink|withthink]", category="debug")
async def cmd_save(ctx: CommandContext, parts: list, command: str) -> CommandResult:
    app = ctx.app
    if len(parts) < 2:
        print("Usage: /save <file> [all] [nothink]")
        print("  /save file.txt - Save last response (omits thinking if /thinking is OFF)")
        print("  /save file.txt all - Save all chat history")
        print("  /save file.txt nothink - Force exclude thinking blocks")
        print("  /save file.txt withthink - Force include thinking blocks")
        return CommandResult.ok()

    save_all = False
    strip_thinking = not app.show_thinking

    words = command.split()
    while len(words) > 2:
        last_word = words[-1].lower().strip(" \"'")
        if last_word == "all":
            save_all = True
            words.pop()
        elif last_word in ("nothink", "no-think", "nothinking", "no-thinking"):
            strip_thinking = True
            words.pop()
        elif last_word in ("withthink", "with-think", "withthinking", "with-thinking"):
            strip_thinking = False
            words.pop()
        else:
            break

    file_path = " ".join(words[1:]).strip(" \"'")

    if not app.chat_history:
        print("No chat history to save.")
        return CommandResult.ok()

    def clean_thinking(text: str) -> str:
        return re.sub(
            r"<think>.*?</think>\s*|<thought>.*?</thought>\s*", "", text, flags=re.DOTALL
        )

    try:
        directory = os.path.dirname(file_path)
        if directory and not os.path.exists(directory):
            os.makedirs(directory, exist_ok=True)
            print(f"Created directory path: '{directory}'")

        if save_all:
            with open(file_path, "w") as f:
                for i, (prompt, response) in enumerate(app.chat_history, 1):
                    res_to_save = clean_thinking(response) if strip_thinking else response
                    f.write(f"=== Conversation {i} ===\n")
                    f.write(f"PROMPT: {prompt}\n\n")
                    f.write(f"RESPONSE: {res_to_save}\n\n")
                    f.write("---\n\n")
            print(f"All chat history ({len(app.chat_history)} conversations) saved to '{file_path}'.")
        else:
            last_response = app.chat_history[-1][1]
            res_to_save = clean_thinking(last_response) if strip_thinking else last_response
            with open(file_path, "w") as f:
                f.write(res_to_save)
            print(f"Last chat completion saved to '{file_path}'.")

            if app.note_mode:
                print(f"Note mode is ON. Processing file '{file_path}'...")
                process_file(file_path)
    except Exception as e:
        print(f"Error saving file: {str(e)}")
    return CommandResult.ok()


@command("/notemode", help="Toggle note mode for code extraction", args="[on|off]", category="debug")
async def cmd_notemode(ctx: CommandContext, parts: list, command: str) -> CommandResult:
    app = ctx.app
    if len(parts) < 2:
        print(f"Note mode is currently {'ON' if app.note_mode else 'OFF'}")
        return CommandResult.ok()

    action = parts[1].lower()
    if action == "on":
        app.note_mode = True
        print("Note mode enabled. Code blocks will be extracted when using /save.")
    elif action == "off":
        app.note_mode = False
        print("Note mode disabled.")
    else:
        print("Invalid note mode action. Use 'on' or 'off'.")
    return CommandResult.ok()


@command("/codeonly", help="Enable code-only output mode", args="", category="debug")
async def cmd_codeonly(ctx: CommandContext, parts: list, command: str) -> CommandResult:
    ctx.app.code_only_flag = True
    print("Code-only mode enabled.")
    return CommandResult.ok()


@command("/codeoff", help="Disable code-only output mode", args="", category="debug")
async def cmd_codeoff(ctx: CommandContext, parts: list, command: str) -> CommandResult:
    ctx.app.code_only_flag = False
    print("Code-only mode disabled.")
    return CommandResult.ok()


@command("/multiline", help="Toggle multi-line input mode", args="", category="debug")
async def cmd_multiline(ctx: CommandContext, parts: list, command: str) -> CommandResult:
    app = ctx.app
    app.multi_line_mode = not app.multi_line_mode
    print(
        f"Multi-line mode {'enabled' if app.multi_line_mode else 'disabled'}. "
        f"{'Use ;; to end input' if app.multi_line_mode else ''}"
    )
    return CommandResult.ok()


@command("/env", help="Show environment variables and API key status", args="[set|unset|<filter>]", category="debug")
async def cmd_env(ctx: CommandContext, parts: list, command: str) -> CommandResult:
    app = ctx.app
    filter_term = parts[1].lower() if len(parts) > 1 else None
    from chatybot.vendors import get_env_status

    models_dict = {}
    if app.config_manager and hasattr(app.config_manager, "config") and isinstance(app.config_manager.config, dict) and "models" in app.config_manager.config:
        models_dict = app.config_manager.config["models"]

    env_data = get_env_status(models_dict)

    if filter_term:
        if filter_term == "set":
            env_data = [e for e in env_data if e["is_set"]]
        elif filter_term in ("unset", "missing"):
            env_data = [e for e in env_data if not e["is_set"]]
        else:
            env_data = [
                e for e in env_data
                if filter_term in e["name"].lower() or filter_term in e["source"].lower()
            ]

    print("=" * 88)
    print(" ENVIRONMENT VARIABLES & API KEYS (set | grep -i api)")
    print("=" * 88)
    print(f" {'Status':<9} | {'Variable Name':<24} | {'Masked Value':<18} | {'Len':<4} | {'Source':<20}")
    print("-" * 10 + "+" + "-" * 26 + "+" + "-" * 20 + "+" + "-" * 6 + "+" + "-" * 22)

    if not env_data:
        print(" No matching environment variables found.")
    else:
        for item in env_data:
            status = "[SET]" if item["is_set"] else "[NOT SET]"
            name = item["name"]
            masked = item["masked"]
            len_str = str(item["length"]) if item["is_set"] else "-"
            source = item["source"]
            print(f" {status:<9} | {name:<24} | {masked:<18} | {len_str:>4} | {source:<20}")

    print("=" * 88)
    num_set = sum(1 for e in env_data if e["is_set"])
    num_total = len(env_data)
    print(f" Total: {num_total} variables ({num_set} set, {num_total - num_set} not set)")
    print("=" * 88)
    return CommandResult.ok()


@command("/profile", help="Manage profiles", args="<list|edit|use|delete> [name]", category="debug")
async def cmd_profile(ctx: CommandContext, parts: list, command: str) -> CommandResult:
    app = ctx.app
    try:
        cmd_parts = shlex.split(command)
    except ValueError:
        cmd_parts = command.split()
    await app.handle_profile_command(cmd_parts[1:])
    return CommandResult.ok()


@command("/mem", help="Show memory usage", args="[detail|debug]", category="debug")
async def cmd_mem(ctx: CommandContext, parts: list, command: str) -> CommandResult:
    app = ctx.app
    from chatybot.chatydb import SEARCHBUFFER
    subcmd = parts[1].lower() if len(parts) > 1 else ""
    detail = subcmd == "detail"
    debug = subcmd == "debug"
    app.buffer_manager.show_memory_usage(SEARCHBUFFER, detail=detail, debug=debug)
    if hasattr(app.image_generator, 'last_generated_image') and app.image_generator.last_generated_image is not None:
        file_path, image_data = app.image_generator.last_generated_image
        image_size_kb = len(image_data.encode('utf-8')) / 1024
        print(f"{'LAST_IMAGE':<20} {image_size_kb:>10.2f}")
        if detail:
            print(f"  -> File path: {file_path}")
            print(f"  -> Data size: {len(image_data)} chars")
    if app.chat_history:
        total_ch_size = sum(
            len(p.encode('utf-8')) + len(r.encode('utf-8'))
            for p, r in app.chat_history
        ) / 1024
        print(f"{'CHAT_HISTORY':<20} {total_ch_size:>10.2f}")
        if detail:
            print(f"  -> Total exchanges: {len(app.chat_history)}")
            for idx, (p, r) in enumerate(app.chat_history, 1):
                p_size = len(p.encode('utf-8')) / 1024
                r_size = len(r.encode('utf-8')) / 1024
                p_snip = p.strip().replace('\n', ' ')[:40]
                r_snip = r.strip().replace('\n', ' ')[:40]
                print(f"    [{idx}] User: {p_size:.2f} KB | {p_snip}...")
                print(f"        Bot:  {r_size:.2f} KB | {r_snip}...")
    return CommandResult.ok()


@command("/dump", help="Dump all variables", args="[varname]", category="debug")
async def cmd_dump(ctx: CommandContext, parts: list, command: str) -> CommandResult:
    app = ctx.app
    from chatybot.chatydb import SEARCHBUFFER
    var_name = parts[1] if len(parts) > 1 else "all"
    app.buffer_manager.dump_variables(var_name, SEARCHBUFFER, app.chat_history)
    return CommandResult.ok()


@command("/calc", help="Evaluate a math expression", args='"<expression>" [var_name]', category="debug")
async def cmd_calc(ctx: CommandContext, parts: list, command: str) -> CommandResult:
    app = ctx.app
    rem_str = command[len(parts[0]):].strip()
    if not rem_str:
        print('Usage: /calc "<expression>" [var_name] or /calc "<expression>"')
        return CommandResult.ok()

    expr_str = ""
    var_target = "CALC"

    if rem_str.startswith('"') or rem_str.startswith("'"):
        q = rem_str[0]
        end_q = rem_str.rfind(q)
        if end_q > 0:
            expr_str = rem_str[1:end_q]
            after_q = rem_str[end_q + 1:].strip()
            if after_q:
                var_target = after_q.split()[0]
        else:
            expr_str = rem_str.strip('"\'')
    else:
        try:
            tokens = shlex.split(rem_str)
        except Exception:
            tokens = rem_str.split()

        if len(tokens) == 1:
            expr_str = tokens[0]
        elif len(tokens) >= 2:
            last = tokens[-1].strip()
            try:
                float(last)
                is_number = True
            except ValueError:
                is_number = False
            if not any(op in last for op in "+-*/^()") and not is_number:
                var_target = last
                expr_str = " ".join(tokens[:-1])
            else:
                expr_str = " ".join(tokens)

    expr_str = app.buffer_manager.replace_placeholders_legacy(expr_str, clear_unresolved=False)

    try:
        from chatybot.tools.math_utils import ensure_mathparse_patched, preprocess_multilingual_expression, normalize_result
        ensure_mathparse_patched()
        from mathparse import mathparse
        lang_code = {
            "en": "ENG",
            "es": "ESP",
            "fr": "FRE",
            "zh": "CHI",
            "it": "ITA"
        }.get(app.i18n.locale, "ENG")
        expr_str = preprocess_multilingual_expression(expr_str, app.i18n.locale)
        try:
            result = mathparse.parse(expr_str, language=lang_code)
        except Exception:
            result = mathparse.parse(expr_str)
        if result is None:
            print(f"Error: Could not parse math expression '{expr_str}'.")
        elif result == 'undefined':
            print(f"Error: Division by zero in expression '{expr_str}'.")
        else:
            result = normalize_result(result)
            app.buffer_manager.set_script_var(var_target, result, allow_protected=True)
            print(f"{var_target} = {result}")
    except Exception as e:
        print(f"Error evaluating math expression '{expr_str}': {e}")
    return CommandResult.ok()


@command("/str_search", help="Search a string variable for a pattern", args='"<pattern>" <text_var> [flags] [var_name]', category="debug")
async def cmd_str_search(ctx: CommandContext, parts: list, command: str) -> CommandResult:
    app = ctx.app
    rem_str = command[len(parts[0]):].strip()
    if not rem_str:
        print('Usage: /str_search "<pattern>" <text_var> [flags] [var_name]')
        print('  flags: c=count (default), m=match positions, i=case-insensitive')
        print('  examples:')
        print('    /str_search "error" ${LOG}')
        print('    /str_search "error" ${LOG} i')
        print('    /str_search "error" ${LOG} ic my_count')
        print('    /str_search "error" ${LOG} m')
        return CommandResult.ok()

    pattern_str = ""
    text_var = ""
    flags_str = "c"
    var_target = "STR_SEARCH"

    try:
        tokens = shlex.split(rem_str)
    except Exception:
        tokens = rem_str.split()

    if len(tokens) < 2:
        print('Usage: /str_search "<pattern>" <text_var> [flags] [var_name]')
        return CommandResult.ok()

    pattern_str = tokens[0]
    text_var = tokens[1]

    if len(tokens) >= 3:
        candidate = tokens[2].strip()
        valid_flags = set("cmigCMIG")
        if candidate and all(ch in valid_flags for ch in candidate):
            flags_str = candidate
            if len(tokens) >= 4:
                var_target = tokens[3].strip()
        else:
            var_target = candidate

    pattern_str = app.buffer_manager.replace_placeholders_legacy(pattern_str, clear_unresolved=False)

    case_sensitive = "i" not in flags_str.lower()
    mode = "m" if "m" in flags_str.lower() else "c"

    var_name = text_var
    if var_name.startswith("${") and var_name.endswith("}"):
        var_name = var_name[2:-1]
    text_value = app.buffer_manager.get_script_var(var_name)
    if text_value is None:
        print(f"Error: Variable '{var_name}' is not set.")
        return CommandResult.ok()
    text_value = str(text_value)

    try:
        from chatybot.tools.str_utils import str_search
        result = str_search(
            pattern=pattern_str,
            text=text_value,
            mode=mode,
            case_sensitive=case_sensitive,
            target_variable=var_target,
            app=app,
        )
        if result.get("status") == "error":
            print(f"Error: {result.get('message')}")
        else:
            print(result.get("message", ""))
    except Exception as e:
        print(f"Error in str_search: {e}")
    return CommandResult.ok()


@command("/setvar", help="Set a script variable", args="<varname> <value>", category="debug")
async def cmd_setvar(ctx: CommandContext, parts: list, command: str) -> CommandResult:
    app = ctx.app
    setvar_parts = command.split(maxsplit=2)
    if len(setvar_parts) < 3:
        print("Usage: /setvar <varname> <value>")
        return CommandResult.ok()

    with app.buffer_manager.script_vars.user_write():
        raw_var_name = setvar_parts[1].strip("\"'")
        raw_value = setvar_parts[2].strip()

        is_array = raw_var_name.endswith("[]")
        var_name = raw_var_name[:-2] if is_array else raw_var_name

        if not re.match(r'^[a-zA-Z_]\w*$', var_name):
            print(f"Error: Invalid variable name '{var_name}'. Variable names must start with a letter or underscore and contain only alphanumeric characters and underscores.")
            return CommandResult.ok()

        if raw_value.startswith('='):
            raw_value = raw_value[1:].strip()

        if "\\" in raw_value:
            print(f"Error: Escape character '\\' is not allowed in setvar command for '{var_name}'.")
            return CommandResult.ok()

        if (raw_value.startswith('"') and raw_value.endswith('"')) or (raw_value.startswith("'") and raw_value.endswith("'")):
            if len(raw_value) >= 2:
                raw_value = raw_value[1:-1].strip()

        if var_name in app.buffer_manager.script_vars:
            existing_type = app.buffer_manager.script_vars.get_type(var_name)
            if existing_type in ("image", "json", "audio"):
                raw_val_stripped = raw_value.strip()
                is_new_image = (
                    raw_val_stripped.startswith("data:image/") or
                    any(raw_val_stripped.startswith(p) for p in ["iVBOR", "/9j/", "UklGR"])
                )
                is_new_json = False
                if raw_val_stripped.startswith("{") or raw_val_stripped.startswith("["):
                    try:
                        json.loads(raw_val_stripped)
                        is_new_json = True
                    except Exception:
                        is_new_json = False
                is_new_audio = (
                    raw_val_stripped.startswith("data:audio/") or
                    any(raw_val_stripped.startswith(p) for p in ["SUQz", "UklGR_audio"])
                )

                blocked = False
                if existing_type == "image" and not is_new_image:
                    print(f"Warning: Variable '{var_name}' already contains image data. Not overwritten.")
                    blocked = True
                elif existing_type == "json" and not is_new_json:
                    print(f"Warning: Variable '{var_name}' already contains JSON. Not overwritten.")
                    blocked = True
                elif existing_type == "audio" and not is_new_audio:
                    print(f"Warning: Variable '{var_name}' already contains audio data. Not overwritten.")
                    blocked = True

                if blocked:
                    return CommandResult.ok()

        if is_array:
            try:
                string_list = app.parse_array_value(raw_value)
            except Exception as e:
                print(f"Error: Invalid array format for '{var_name}': {e}")
                return CommandResult.ok()

            success = app.buffer_manager.set_script_var(var_name, string_list)
            if not success:
                return CommandResult.ok()
            print(f"Variable '{var_name}' set.")
            return CommandResult.ok()

        for i in range(1, 6):
            bank_name = f"imagebank{i}"
            if bank_name in app.buffer_manager.image_banks:
                image_data = app.buffer_manager.image_banks[bank_name]
                if image_data:
                    raw_value = raw_value.replace(f"{{{bank_name}}}", image_data)
                    raw_value = raw_value.replace(f"${{{bank_name}}}", image_data)

        var_value, _ = app.buffer_manager.replace_placeholders(raw_value, include_images=False, clear_unresolved=False)

        success = app.buffer_manager.set_script_var(var_name, var_value)
        if not success:
            return CommandResult.ok()
        print(f"Variable '{var_name}' set.")
    return CommandResult.ok()


@command("/reloadmacros", help="Reload macros from file", args="[filename]", category="debug")
async def cmd_reloadmacros(ctx: CommandContext, parts: list, command: str) -> CommandResult:
    app = ctx.app
    # Preserve legacy behavior: the original code re-split `cmd` (the command
    # name only, e.g. "/reloadmacros"), so parts[1] never existed and the
    # default-file path was always taken. We replicate that here.
    legacy_parts = parts[0].split()
    if len(legacy_parts) > 1:
        macro_file = legacy_parts[1]
        app.load_macros(macro_file)
        print(f"Reloaded macros from '{macro_file}'. {len(app.macros)} macros available.")
    else:
        app.load_macros()
        print(f"Reloaded macros from default file. {len(app.macros)} macros available.")
    return CommandResult.ok()


@command("/listmacros", help="List available macros", args="[filter]", category="debug")
async def cmd_listmacros(ctx: CommandContext, parts: list, command: str) -> CommandResult:
    app = ctx.app
    list_parts = command.split(maxsplit=1)
    filter_term = list_parts[1].strip() if len(list_parts) > 1 else None
    app.list_macros(filter_term=filter_term)
    return CommandResult.ok()
