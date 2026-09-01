"""Procedure, script, and macro commands.

Migrated from chatybot_app.handle_escape_command elif chain:
  /proc, /source, /script
"""

import os
import re

from chatybot.commands.registry import command, CommandResult
from chatybot.commands.context import CommandContext


@command("/proc", help="Execute a procedure", args='<name> [key="value"]...', category="proc_macros")
async def cmd_proc(ctx: CommandContext, parts: list, command: str) -> CommandResult:
    app = ctx.app
    if len(parts) < 2:
        print('Usage: /proc <name> [key="value"]...')
        return CommandResult.ok()

    remaining_command = command[len(parts[0]):].strip()
    name_match = re.match(r'("[^"]*"|\'[^\']*\'|\S+)', remaining_command)
    if name_match:
        proc_name = name_match.group(1).strip('"\'')
        params_string = remaining_command[len(name_match.group(1)):].strip()
    else:
        proc_name = parts[1]
        params_string = ""

    param_pattern = r'(^|\s+)([a-zA-Z_]\w*)\s*=\s*("[^"]*"|\'[^\']*\'|\S+)'
    call_args = {}
    for match in re.finditer(param_pattern, params_string):
        var_name = match.group(2)
        var_value = match.group(3).strip('"\'')
        call_args[var_name] = var_value

    try:
        max_depth = int(app.buffer_manager.script_vars.get("PROC_MAX_DEPTH", 20))
    except (ValueError, TypeError):
        print("Warning: PROC_MAX_DEPTH is not a valid integer; defaulting to 20.")
        max_depth = 20
    if app.proc_depth >= max_depth:
        print(f"Error: Maximum procedure recursion depth of {max_depth} reached.", flush=True)
        return CommandResult.ok()

    body_lines = None
    if proc_name in app.procedures:
        body_lines = app.procedures[proc_name]["body"]
    else:
        search_paths = [
            proc_name,
            f"{proc_name}.chatdsl",
            os.path.join("procs", f"{proc_name}.chatdsl"),
            os.path.expanduser(os.path.join("~/.chatybot/procs", f"{proc_name}.chatdsl"))
        ]
        found_path = None
        for path in search_paths:
            if os.path.exists(path):
                found_path = path
                break
        if found_path:
            try:
                with open(found_path, "r", encoding="utf-8") as f:
                    content = f.read()
                body_lines = content.split("\n")
                if body_lines and re.match(r"\s*defproc\s+\w+", body_lines[0]):
                    body_lines = body_lines[1:]
                    for i in range(len(body_lines) - 1, -1, -1):
                        if body_lines[i].strip() == "endproc":
                            body_lines = body_lines[:i] + body_lines[i + 1:]
                            break
            except Exception as e:
                print(f"Error reading procedure file '{found_path}': {e}")
                return CommandResult.ok()
        else:
            print(f"Error: Procedure '{proc_name}' not found in memory or disk.")
            return CommandResult.ok()

    frame = {"saved_vars": {}, "local_vars": set()}
    app.active_proc_stack.append(frame)

    if proc_name in app.procedures:
        declared = set(app.procedures[proc_name]["params"])
        provided = set(call_args.keys())
        missing = declared - provided
        extra = provided - declared
        if missing:
            print(f"Warning: Procedure '{proc_name}' called without parameter(s): {', '.join(sorted(missing))}.")
        if extra:
            print(f"Warning: Procedure '{proc_name}' called with unknown parameter(s): {', '.join(sorted(extra))}.")

    with app.buffer_manager.script_vars.user_write():
        for k, v in call_args.items():
            if k not in frame["saved_vars"]:
                exists = k in app.buffer_manager.script_vars
                orig_val = app.buffer_manager.script_vars.get(k) if exists else None
                frame["saved_vars"][k] = (exists, orig_val)
            processed_v = app.buffer_manager.replace_placeholders_legacy(v)
            app.buffer_manager.set_script_var(k, processed_v)

    app.proc_depth += 1
    old_script_context = app.script_context
    app.script_context = True
    try:
        await app.execute_command_list(body_lines)
    except Exception as e:
        # Re-raise LoopBreak (and similar control-flow exceptions) without
        # printing an error, so they propagate up to the foreach loop handler.
        # We check by class name to avoid importing LoopBreak (which can be
        # a different class object when src.chatybot redirect is active).
        if type(e).__name__ == "LoopBreak":
            raise
        print(f"Error executing procedure '{proc_name}': {e}")
    finally:
        app.script_context = old_script_context
        app.proc_depth -= 1
        popped_frame = app.active_proc_stack.pop()
        with app.buffer_manager.script_vars.user_write():
            for var_name, (exists, orig_val) in popped_frame["saved_vars"].items():
                if exists:
                    app.buffer_manager.set_script_var(var_name, orig_val)
                else:
                    if var_name in app.buffer_manager.script_vars:
                        del app.buffer_manager.script_vars[var_name]

    return CommandResult.ok()


@command("/source", help="Execute a script file", args="<file>", category="proc_macros")
async def cmd_source(ctx: CommandContext, parts: list, command: str) -> CommandResult:
    app = ctx.app
    if len(parts) < 2:
        print("Usage: /source <file>")
        return CommandResult.ok()
    file_path = command.split(maxsplit=1)[1].strip(" \"'")
    expanded_path = os.path.expanduser(file_path)
    if not os.path.exists(expanded_path):
        print(f"Error: Script file not found: {expanded_path}")
        return CommandResult.ok()
    await app.execute_script(expanded_path)
    return CommandResult.ok()


@command("/script", help="Execute a script with parameters", args='<file> [key="value"]...', category="proc_macros")
async def cmd_script(ctx: CommandContext, parts: list, command: str) -> CommandResult:
    app = ctx.app
    if len(parts) < 2:
        print('Usage: /script <file> [key="value"]...')
        return CommandResult.ok()

    script_path = parts[1]

    param_pattern = r'(^|\s+)([a-zA-Z_]\w*)\s*=\s*("[^"]*"|\'[^\']*\'|\S+)'

    remaining_command = command[len(parts[0]):].strip()

    script_path_match = re.match(r'("[^"]*"|\'[^\']*\'|\S+)', remaining_command)
    if script_path_match:
        actual_script_path = script_path_match.group(1).strip('"\'')
        params_string = remaining_command[len(script_path_match.group(1)):].strip()
    else:
        actual_script_path = script_path
        params_string = ""

    params = {}
    for match in re.finditer(param_pattern, params_string):
        var_name = match.group(2)
        var_value = match.group(3).strip('"\'')
        params[var_name] = var_value
        print(f"Setting parameter {var_name} = {var_value}")

    with app.buffer_manager.script_vars.user_write():
        for var_name, var_value in params.items():
            app.buffer_manager.set_script_var(var_name, var_value)

    print("command /script with ", actual_script_path)
    await app.execute_script(actual_script_path)
    return CommandResult.ok()


def _parse_selection_indices(selection_str: str, total_count: int) -> list:
    """Parse comma/hyphen separated selection string (e.g. '1,3,5-7', 'all', 'last 5')."""
    selected_indices = set()
    cleaned = selection_str.strip().lower()

    if cleaned == "all" or cleaned == "*":
        return list(range(total_count))

    if cleaned.startswith("last"):
        parts = cleaned.split()
        if len(parts) >= 2 and parts[1].isdigit():
            n = int(parts[1])
            start_idx = max(0, total_count - n)
            return list(range(start_idx, total_count))
        return list(range(max(0, total_count - 5), total_count))

    for chunk in cleaned.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        if "-" in chunk:
            bounds = chunk.split("-", 1)
            if bounds[0].strip().isdigit() and bounds[1].strip().isdigit():
                start = int(bounds[0].strip())
                end = int(bounds[1].strip())
                for i in range(min(start, end), max(start, end) + 1):
                    if 1 <= i <= total_count:
                        selected_indices.add(i - 1)
        elif chunk.isdigit():
            val = int(chunk)
            if 1 <= val <= total_count:
                selected_indices.add(val - 1)

    return sorted(list(selected_indices))


def _extract_session_items(app) -> list:
    """Extract list of historical commands and prompts from active session activity, session turns, or chat history."""
    items = []
    # 1. If chronological session_activity exists (captures slash commands and prompts), use it
    if getattr(app, "session_activity", None):
        for idx, act in enumerate(app.session_activity, 1):
            text = act.get("text", "").strip()
            act_type = act.get("type", "prompt")
            model = act.get("model", getattr(app.config_manager, "active_model_alias", "default"))
            items.append({
                "index": idx,
                "prompt": text,
                "model": model,
                "type": act_type
            })
    # 2. Fallback to session_turns if session_activity is empty
    elif getattr(app, "session_turns", None):
        for idx, turn in enumerate(app.session_turns, 1):
            p = turn.get("prompt", "").strip()
            model = turn.get("model_alias", "")
            items.append({
                "index": idx,
                "prompt": p,
                "model": model,
                "type": "turn"
            })
    # 3. Fallback to chat_history
    elif getattr(app, "chat_history", None):
        for idx, (p, _) in enumerate(app.chat_history, 1):
            items.append({
                "index": idx,
                "prompt": p.strip(),
                "model": getattr(app.config_manager, "active_model_alias", "default"),
                "type": "history"
            })
    return items


def _generate_chatdsl_script(selected_items: list, output_filename: str) -> str:
    """Generate ChatDSL script content from selected items."""
    lines = [
        f"# Generated ChatDSL workflow: {output_filename}",
        f"# Codified from active session ({len(selected_items)} steps)",
        ""
    ]

    for step_num, item in enumerate(selected_items, 1):
        prompt_text = item["prompt"]
        if not prompt_text:
            continue
        lines.append(f"# Step {step_num}")
        # If it's already a slash command, write directly
        if prompt_text.startswith("/"):
            lines.append(prompt_text)
        else:
            # Check if multiline
            if "\n" in prompt_text:
                lines.append("/multiline")
                lines.append(prompt_text)
                lines.append(";;")
                lines.append("/multiline")
            else:
                lines.append(prompt_text)
        lines.append("")

    return "\n".join(lines)


@command("/chatdsl", help="Create or manage ChatDSL scripts from session history", args="history [range|last N] [filename.chatdsl]", category="proc_macros")
async def cmd_chatdsl(ctx: CommandContext, parts: list, command: str) -> CommandResult:
    app = ctx.app
    tokens = command.strip().split()
    if len(tokens) < 2:
        print("Usage: /chatdsl history [range|last N] [output.chatdsl]")
        print("Examples:")
        print("  /chatdsl history                     (interactive picklist from session)")
        print("  /chatdsl history 1-3 workflow.chatdsl (export steps 1 to 3)")
        print("  /chatdsl history last 5 quick.chatdsl (export last 5 steps)")
        return CommandResult.ok()

    subcmd = tokens[1].lower()
    if subcmd != "history":
        print(f"Unknown /chatdsl subcommand: '{tokens[1]}'. Did you mean '/chatdsl history'?")
        print("Usage: /chatdsl history [range|last N] [output.chatdsl]")
        return CommandResult.ok()

    items = _extract_session_items(app)
    if not items:
        print("No exchanges or commands found in the active session history to export.")
        return CommandResult.ok()

    target_file = None
    selection_str = None

    # Parse remaining arguments: e.g. /chatdsl history 1-3 script.chatdsl or /chatdsl history last 5 script.chatdsl
    rem_tokens = tokens[2:]
    if len(rem_tokens) == 1:
        if rem_tokens[0].endswith(".chatdsl") or ("." in rem_tokens[0] and not any(c.isdigit() for c in rem_tokens[0])):
            target_file = rem_tokens[0]
        else:
            selection_str = rem_tokens[0]
    elif len(rem_tokens) == 2:
        selection_str = rem_tokens[0]
        target_file = rem_tokens[1]
    elif len(rem_tokens) >= 3 and rem_tokens[0].lower() == "last":
        selection_str = f"last {rem_tokens[1]}"
        target_file = rem_tokens[2]

    # If no selection provided, display interactive picklist
    if selection_str is None:
        print("\n" + "=" * 60)
        print("  Active Session History (Codify to ChatDSL)")
        print("=" * 60)
        for itm in items:
            idx = itm["index"]
            prompt_preview = itm["prompt"].replace("\n", " ")
            if len(prompt_preview) > 65:
                prompt_preview = prompt_preview[:62] + "..."
            print(f"  [{idx:>2}] {prompt_preview}")
        print("-" * 60)
        print("Select items (e.g. '1,3,5-7', 'last 3', 'all', or 'q' to cancel):")
        try:
            user_sel = input("Selection> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nOperation cancelled.")
            return CommandResult.ok()

        if not user_sel or user_sel.lower() in ("q", "quit", "cancel"):
            print("Operation cancelled.")
            return CommandResult.ok()
        selection_str = user_sel

    indices = _parse_selection_indices(selection_str, len(items))
    if not indices:
        print(f"No valid items matched selection '{selection_str}'.")
        return CommandResult.ok()

    if not target_file:
        try:
            default_name = "session_workflow.chatdsl"
            user_fname = input(f"Output script filename [{default_name}]: ").strip()
            target_file = user_fname if user_fname else default_name
        except (EOFError, KeyboardInterrupt):
            print("\nOperation cancelled.")
            return CommandResult.ok()

    if not target_file.endswith(".chatdsl"):
        target_file += ".chatdsl"

    selected_items = [items[i] for i in indices]
    script_content = _generate_chatdsl_script(selected_items, target_file)

    try:
        with open(target_file, "w", encoding="utf-8") as f:
            f.write(script_content)
        print(f"Successfully generated ChatDSL script '{target_file}' with {len(selected_items)} steps.")
        print(f"To run this script: /script {target_file}")
    except Exception as e:
        print(f"Error writing ChatDSL script to '{target_file}': {e}")

    return CommandResult.ok()

