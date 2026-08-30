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
