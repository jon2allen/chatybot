"""Shell execution and tool management commands.

Migrated from chatybot_app.handle_escape_command elif chain:
  /run, /run_safe, /run_unsafe, /tool
"""

import dataclasses
import fnmatch
import json
import os
import shlex

from chatybot.commands.context import CommandContext
from chatybot.commands.registry import CommandResult, command
from chatybot.commands.replay import _preview as _replay_preview


@command("/run", help="Execute a shell command", args="<command>", category="tools")
async def cmd_run(ctx: CommandContext, parts: list, command: str) -> CommandResult:
    app = ctx.app
    if len(parts) < 2:
        print("Usage: /run <command>")
        return CommandResult.ok()

    # Check for /run safe and /run unsafe [askfirst]
    if len(parts) >= 2 and parts[1].lower() in ("safe", "unsafe"):
        sub = parts[1].lower()
        if sub == "safe" and len(parts) == 2:
            app.safe_mode = True
            app.safe_mode_askfirst = False
            print("Safe mode enabled - dangerous patterns will be blocked")
            return CommandResult.ok()
        elif sub == "unsafe" and (len(parts) == 2 or (len(parts) == 3 and parts[2].lower().replace("_", "") == "askfirst")):
            app.safe_mode = False
            if len(parts) == 3 and parts[2].lower().replace("_", "") == "askfirst":
                app.safe_mode_askfirst = True
                print("Safe mode disabled with confirmation - dangerous commands will require confirmation (y/N)")
            else:
                app.safe_mode_askfirst = False
                print("Safe mode disabled - dangerous commands allowed without confirmation")
            return CommandResult.ok()

    # Extract the command portion (everything after "/run")
    command_str = command.split(maxsplit=1)[1]

    # Strip only the outermost matching quotes, preserving inner quotes
    stripped_command = command_str
    if len(command_str) >= 2:
        first_char = command_str[0]
        last_char = command_str[-1]
        if first_char == last_char and first_char in ('"', "'"):
            stripped_command = command_str[1:-1]

    # Validate quote balance before processing
    try:
        shlex.split(stripped_command)
    except ValueError as e:
        print(f"Error: {e}")
        print("Tip: Mix quotes: /run find . -name \"*.md\"")
        print("     Or: /run \"find . -name '*.md'\"")
        print("     Escape inner quotes: /run \"find . -name \\\"*.md\\\"\"")
        return CommandResult.ok()

    if stripped_command:
        processed_cmd, _ = app.buffer_manager.replace_placeholders(stripped_command, include_images=False, expand_injections=False)
        app.execute_shell_command(processed_cmd)
    return CommandResult.ok()


@command("/run_safe", help="Enable safe mode for shell commands", args="", category="tools")
async def cmd_run_safe(ctx: CommandContext, parts: list, command: str) -> CommandResult:
    app = ctx.app
    app.safe_mode = True
    app.safe_mode_askfirst = False
    print("Safe mode enabled - dangerous patterns will be blocked")
    return CommandResult.ok()


@command("/run_unsafe", help="Disable safe mode for shell commands", args="[askfirst]", category="tools")
async def cmd_run_unsafe(ctx: CommandContext, parts: list, command: str) -> CommandResult:
    app = ctx.app
    app.safe_mode = False
    if len(parts) >= 2 and parts[1].lower().replace("_", "") == "askfirst":
        app.safe_mode_askfirst = True
        print("Safe mode disabled with confirmation - dangerous commands will require confirmation (y/N)")
    else:
        app.safe_mode_askfirst = False
        print("Safe mode disabled - dangerous commands allowed without confirmation")
    return CommandResult.ok()


@command("/continue", help="Continue agentic loop with last rescued tool result", args="[max_turns]", category="tools")
async def cmd_continue(ctx: CommandContext, parts: list, command: str) -> CommandResult:
    return await _handle_tool_continue(ctx, parts, command)


@command("/tool", help="Manage tools and tool mode", args="[list|enable|disable|on|off|auto|scratch|loop|append_mode|max_turns|rate_limit|prompt|history|replay|retry|continue|inject|translate] ...", category="tools")
async def cmd_tool(ctx: CommandContext, parts: list, command: str) -> CommandResult:
    app = ctx.app
    # Handle /tool subcommands: on, off, or dispatch
    if len(parts) < 2:
        # No subcommand - dispatch tool invocation from LAST_COMPLETION
        await app.dispatch_tool()
        return CommandResult.ok()

    subcmd = parts[1].lower()

    if subcmd == "list":
        # Parse detail mode, glob pattern, and var= / target=
        detail_mode = False
        glob_pattern = "*"
        target_var = None

        raw_tokens = []
        for p in parts[2:]:
            raw_tokens.extend(p.strip().split())

        filtered_tokens = []
        for tok in raw_tokens:
            if tok.lower().startswith("var="):
                target_var = tok[4:].strip().lstrip("$")
            elif tok.lower().startswith("target="):
                target_var = tok[7:].strip().lstrip("$")
            elif tok.lower() == "detail":
                detail_mode = True
            else:
                filtered_tokens.append(tok)

        if filtered_tokens:
            glob_pattern = filtered_tokens[0]

        config = app._load_tools_config()
        tools = config.get('tools', {})

        # Filter local tools
        filtered_local = {}
        for t_name, t_meta in tools.items():
            if fnmatch.fnmatch(t_name.lower(), glob_pattern.lower()):
                filtered_local[t_name] = t_meta

        # Filter MCP tools
        filtered_mcp = {}
        if app.mcp_manager and app.mcp_manager.cached_schemas:
            for server_name, tools_list in app.mcp_manager.cached_schemas.items():
                matching_mcp = []
                for tool in tools_list:
                    mcp_tool_name = f"mcp__{server_name}__{tool.name}"
                    if fnmatch.fnmatch(mcp_tool_name.lower(), glob_pattern.lower()):
                        matching_mcp.append(tool)
                if matching_mcp:
                    filtered_mcp[server_name] = matching_mcp

        # Populate structured tool list data for TOOL_LIST / custom var
        tools_data = []
        for tool_name, tool_meta in filtered_local.items():
            config_enabled = tool_meta.get('enabled', False)
            is_enabled = app.tool_overrides.get(tool_name, config_enabled)
            tools_data.append({
                "name": tool_name,
                "type": "local",
                "enabled": is_enabled,
                "description": tool_meta.get('description', 'No description'),
                "parameters": tool_meta.get('parameters', {}),
                "module": tool_meta.get('module', ''),
                "function": tool_meta.get('function', ''),
            })

        if filtered_mcp:
            for server_name, tools_list in filtered_mcp.items():
                for tool in tools_list:
                    mcp_tool_name = f"mcp__{server_name}__{tool.name}"
                    is_enabled = app.tool_overrides.get(mcp_tool_name, True)
                    desc = getattr(tool, "description", "No description") or "No description"
                    input_schema = getattr(tool, "inputSchema", {})
                    properties = input_schema.get("properties", {}) if hasattr(input_schema, "get") else {}
                    tools_data.append({
                        "name": mcp_tool_name,
                        "type": "mcp",
                        "server": server_name,
                        "enabled": is_enabled,
                        "description": desc,
                        "parameters": properties,
                    })

        if hasattr(app, "buffer_manager") and app.buffer_manager:
            app.buffer_manager.set_script_var('TOOL_LIST', tools_data, allow_protected=True)
            if target_var:
                app.buffer_manager.set_script_var(target_var, tools_data, allow_protected=True)

        if detail_mode:
            if glob_pattern != "*":
                print(f"\nDetailed Tools matching '{glob_pattern}':")
            else:
                print("\nDetailed Tools Configuration:")

            print("\nAvailable Local Tools:")
            if not filtered_local:
                print("  No local tools match pattern." if glob_pattern != "*" else "  No local tools defined in configuration.")
            else:
                for tool_name, tool_meta in filtered_local.items():
                    config_enabled = tool_meta.get('enabled', False)
                    is_enabled = app.tool_overrides.get(tool_name, config_enabled)
                    status = "[ON]" if is_enabled else "[OFF]"
                    desc = tool_meta.get('description', 'No description')
                    print(f"\n**{tool_name}**  {status}")
                    print(f"Description: {desc}")
                    params = tool_meta.get('parameters', {})
                    if params:
                        print("Parameters:")
                        for param_name, param_rules in params.items():
                            param_type = param_rules.get('type', 'string')
                            param_desc = param_rules.get('description', '')
                            optional = param_rules.get('optional', False)
                            required = " (optional)" if optional else " (required)"
                            print(f"   {param_name}: {param_type}{required} {param_desc}")

            # Print MCP Tools if active
            if filtered_mcp:
                print("\nModel Context Protocol (MCP) Tools:")
                for server_name, tools_list in filtered_mcp.items():
                    print(f"  [{server_name}]")
                    for tool in tools_list:
                        mcp_tool_name = f"mcp__{server_name}__{tool.name}"
                        is_enabled = app.tool_overrides.get(mcp_tool_name, True)
                        status = "[ON]" if is_enabled else "[OFF]"
                        desc = getattr(tool, "description", "No description") or "No description"
                        print(f"\n**{mcp_tool_name}**  {status}")
                        print(f"Description: {desc}")

                        # Extract input schema properties
                        input_schema = getattr(tool, "inputSchema", {})
                        if hasattr(input_schema, "get"):
                            properties = input_schema.get("properties", {})
                            required_list = input_schema.get("required", [])
                        else:
                            properties = {}
                            required_list = []

                        if properties:
                            print("Parameters:")
                            for param_name, param_meta in properties.items():
                                if hasattr(param_meta, "get"):
                                    param_type = param_meta.get("type")
                                    if not param_type and "anyOf" in param_meta:
                                        types = [t.get("type") for t in param_meta["anyOf"] if t.get("type") != "null" and t.get("type")]
                                        param_type = "|".join(types) if types else "string"
                                    elif not param_type:
                                        param_type = "string"
                                    param_desc = param_meta.get("description", "")
                                else:
                                    param_type = "string"
                                    param_desc = ""

                                is_optional = param_name not in required_list
                                required_str = " (optional)" if is_optional else " (required)"
                                print(f"   {param_name}: {param_type}{required_str} {param_desc}")
            elif app.mcp_manager and app.mcp_manager.cached_schemas:
                print("\nModel Context Protocol (MCP) Tools:")
                print("  No MCP tools match pattern.")
        else:
            # Columnar layout for single-line view
            if glob_pattern != "*":
                print(f"\nAvailable Tools matching '{glob_pattern}':")

            # Print header
            print(f"\n  {'STATUS':<6} {'TYPE':<6} {'NAME':<45} {'DESCRIPTION':<60}")
            print(f"  {'-'*6} {'-'*6} {'-'*45} {'-'*60}")

            has_local = False
            for tool_name, tool_meta in filtered_local.items():
                has_local = True
                config_enabled = tool_meta.get('enabled', False)
                is_enabled = app.tool_overrides.get(tool_name, config_enabled)
                status_str = "[ON]" if is_enabled else "[OFF]"
                desc = tool_meta.get('description', 'No description').strip().replace("\n", " ")
                print(f"  {status_str:<6} {'LOCAL':<6} {tool_name:<45} {desc[:60]:<60}")

            if not has_local and glob_pattern == "*":
                print("  (No local tools defined)")

            has_mcp = False
            if filtered_mcp:
                for server_name, tools_list in filtered_mcp.items():
                    for tool in tools_list:
                        has_mcp = True
                        mcp_tool_name = f"mcp__{server_name}__{tool.name}"
                        is_enabled = app.tool_overrides.get(mcp_tool_name, True)
                        status_str = "[ON]" if is_enabled else "[OFF]"
                        desc = (getattr(tool, "description", "No description") or "No description").strip().replace("\n", " ")
                        print(f"  {status_str:<6} {'MCP':<6} {mcp_tool_name:<45} {desc[:60]:<60}")

            if not has_mcp and app.mcp_manager and app.mcp_manager.cached_schemas and glob_pattern == "*":
                print("  (No MCP tools active)")
        print()
        return CommandResult.ok()

    elif subcmd in ("enable", "disable"):
        if len(parts) < 3:
            print(f"Usage: /tool {subcmd} <tool_name>|all|<glob_pattern>")
            return CommandResult.ok()

        target = parts[2].strip()
        config = app._load_tools_config()
        tools = config.get('tools', {})

        target_value = (subcmd == "enable")

        # Collect all available tools
        all_tools = []
        for tool_name in tools.keys():
            all_tools.append(tool_name)
        if app.mcp_manager and app.mcp_manager.cached_schemas:
            for server_name, tools_list in app.mcp_manager.cached_schemas.items():
                for tool in tools_list:
                    all_tools.append(f"mcp__{server_name}__{tool.name}")

        if target.lower() == "all":
            matched_tools = all_tools
        else:
            pattern = target.lower()
            matched_tools = [t for t in all_tools if fnmatch.fnmatch(t.lower(), pattern)]

            # Fallback to exact case-insensitive match if target contains no glob chars and wasn't matched
            if not matched_tools and "*" not in target and "?" not in target:
                for t in all_tools:
                    if t.lower() == target.lower():
                        matched_tools = [t]
                        break

        if not matched_tools:
            print(f"Error: No tools matched pattern '{target}'.")
            return CommandResult.ok()

        for t in matched_tools:
            app.tool_overrides[t] = target_value
            print(f"Tool '{t}' {'enabled' if target_value else 'disabled'}.")

        # Regenerate tool context to update in-memory state and refresh variable context if active
        context = app.generate_tool_context()
        if app.tool_mode:
            app.buffer_manager.set_script_var('TOOL_CONTEXT', context)
        print("Prompt context refreshed with updated tools.")
        return CommandResult.ok()

    elif subcmd == "on":
        # Enable tool mode - inject tool definitions into system prompt
        context = app.generate_tool_context()
        if context:
            app.tool_mode = True
            app.buffer_manager.set_script_var('TOOL_CONTEXT', context)
            print("Tool mode enabled - tool definitions loaded")
            print(f"   {len(context.split(chr(10)))} lines of tool context available")
        else:
            print("No tools available to load")
        return CommandResult.ok()

    elif subcmd == "off":
        app.tool_mode = False
        app.tool_context = ""
        app.buffer_manager.set_script_var('TOOL_CONTEXT', '')
        print("Tool mode disabled")
        return CommandResult.ok()

    elif subcmd == "auto":
        if len(parts) > 2:
            auto_arg = parts[2].strip().lower()
            if auto_arg == "on":
                app.tool_auto = True
                context = app.generate_tool_context()
                if context:
                    app.tool_mode = True
                    app.buffer_manager.set_script_var('TOOL_CONTEXT', context)
                    print("Tool auto mode enabled - tool definitions loaded")
                else:
                    print("Tool auto mode enabled (warning: no tools available to load)")
            elif auto_arg == "off":
                app.tool_auto = False
                print("Tool auto mode disabled")
            else:
                print("Invalid option. Usage: /tool auto on|off")
        else:
            state_str = "enabled" if app.tool_auto else "disabled"
            print(f"Tool auto mode is currently {state_str}")
        return CommandResult.ok()

    elif subcmd == "scratch":
        if len(parts) > 2:
            scratch_arg = parts[2].strip().lower()
            if scratch_arg == "on":
                app.tool_scratch = True
                app._tool_scratch_user_set = True
                scratch_dir = app.get_scratch_dir(create=True)
                context = app.generate_tool_context()
                if app.tool_mode and context:
                    app.buffer_manager.set_script_var('TOOL_CONTEXT', context)
                msg = f"Tool scratch mode enabled. Scratch directory: {scratch_dir}"
                if not getattr(app, "tool_mode", False):
                    msg += " (Note: Tool mode is currently OFF. Run '/tool auto' or '/tool on' to enable agentic tool execution)."
                print(msg)
            elif scratch_arg == "off":
                app.tool_scratch = False
                app._tool_scratch_user_set = True
                context = app.generate_tool_context()
                if app.tool_mode and context:
                    app.buffer_manager.set_script_var('TOOL_CONTEXT', context)
                print("Tool scratch mode disabled")
            elif scratch_arg == "clean":
                scratch_dir = app.get_scratch_dir(create=False)
                if scratch_dir and os.path.exists(scratch_dir):
                    count = 0
                    for item in os.listdir(scratch_dir):
                        item_path = os.path.join(scratch_dir, item)
                        try:
                            if os.path.isfile(item_path) or os.path.islink(item_path):
                                os.unlink(item_path)
                                count += 1
                            elif os.path.isdir(item_path):
                                import shutil
                                shutil.rmtree(item_path)
                                count += 1
                        except Exception as e:
                            print(f"Warning: Could not remove '{item}': {e}")
                    print(f"Cleaned scratch directory: removed {count} item(s) from {scratch_dir}")
                else:
                    print(f"Scratch directory does not exist or is already empty: {scratch_dir}")
            elif scratch_arg in ("status", "show", "info"):
                state_str = "enabled" if app.tool_scratch else "disabled"
                scratch_dir = app.get_scratch_dir(create=False)
                print(f"Tool scratch mode is currently {state_str}")
                print(f"Scratch directory: {scratch_dir}")
                if scratch_dir and os.path.exists(scratch_dir):
                    files = [f for f in os.listdir(scratch_dir) if not f.startswith('.')]
                    if files:
                        print(f"Files ({len(files)}):")
                        for f in sorted(files):
                            print(f"  - {f}")
                    else:
                        print("Scratch directory is currently empty.")
                else:
                    print("Scratch directory has not been created yet.")
            else:
                print("Invalid option. Usage: /tool scratch [on|off|clean|status]")
        else:
            state_str = "enabled" if app.tool_scratch else "disabled"
            scratch_dir = app.get_scratch_dir(create=False)
            print(f"Tool scratch mode is currently {state_str}")
            print(f"Scratch directory: {scratch_dir}")
            if os.path.exists(scratch_dir):
                files = [f for f in os.listdir(scratch_dir) if not f.startswith('.')]
                if files:
                    print(f"Files ({len(files)}):")
                    for f in sorted(files):
                        print(f"  - {f}")
                else:
                    print("Scratch directory is currently empty.")
            else:
                print("Scratch directory has not been created yet.")
        return CommandResult.ok()

    elif subcmd == "loop":
        max_turns = app.max_turns
        loop_args = []
        if len(parts) > 2:
            loop_args = [p.lower() for p in parts[2].split()]
        has_force = "force" in loop_args

        count_args = [a for a in loop_args if a != "force"]

        if count_args:
            arg = count_args[0]
            if arg == "max":
                max_turns = 100
            elif arg.startswith("max="):
                try:
                    val = int(arg.split("=")[1])
                    if val > 100 and not has_force:
                        print("Warning: Loop counts greater than 100 require the 'force' flag. Capping at 100.")
                        max_turns = 100
                    else:
                        max_turns = val
                except ValueError:
                    pass
            else:
                try:
                    val = int(arg)
                    if val > 100 and not has_force:
                        print("Warning: Loop counts greater than 100 require the 'force' flag. Capping at 100.")
                        max_turns = 100
                    else:
                        max_turns = val
                except ValueError:
                    pass
        await app.execute_tool_loop(max_turns)
        return CommandResult.ok()

    elif subcmd in ("append_mode", "appendmode"):
        if len(parts) > 2:
            mode = parts[2].strip().lower()
            if mode in ("off", "full", "summary"):
                app.tool_append_mode = mode
                app._tool_append_mode_user_set = True
                print(f"Tool append mode set to: {mode}")
            else:
                print(f"Invalid append mode: '{mode}'. Usage: /tool append_mode <off|full|summary>")
        else:
            cur_mode = getattr(app, "tool_append_mode", "summary")
            print(f"Current tool append mode: {cur_mode} (options: off | full | summary)")
        return CommandResult.ok()

    elif subcmd == "max_turns":
        if len(parts) > 2:
            try:
                app.max_turns = int(parts[2].strip())
                print(f"Max tool turns set to {app.max_turns}")
            except ValueError:
                print("Invalid turn count. Usage: /tool max_turns <int>")
        else:
            print(f"Current max tool turns: {app.max_turns}")
        return CommandResult.ok()

    elif subcmd in ("rate_limit", "ratelimit"):
        if len(parts) > 2:
            raw_val = parts[2].strip()
            try:
                val = float(raw_val)
                if val < 0:
                    print("Error: Rate limit delay cannot be negative. Usage: /tool rate_limit <seconds>")
                else:
                    app.rate_limit_delay = val
                    app._cached_rate_limit_delay = val
                    display_val = int(val) if val.is_integer() else val
                    print(f"rate_limit is now {display_val} seconds")
            except ValueError:
                print("Invalid rate limit value. Usage: /tool rate_limit <seconds>")
        else:
            display_val = int(app.rate_limit_delay) if isinstance(app.rate_limit_delay, (int, float)) and float(app.rate_limit_delay).is_integer() else app.rate_limit_delay
            print(f"rate_limit is currently {display_val} seconds")
        return CommandResult.ok()

    elif subcmd == "prompt":
        sub_arg = ""
        if len(parts) > 2:
            sub_arg = parts[2].strip().lower()

        if sub_arg in ("edit_live", "live_edit"):
            import subprocess
            import tempfile

            context = app.tool_context or app.generate_tool_context()
            current_instr = app.live_agentic_instructions or app.agentic_instructions or app.default_agentic_instructions

            with tempfile.NamedTemporaryFile(suffix=".txt", delete=False, mode="w", encoding="utf-8") as tf:
                tf.write("=== TOOL CONTEXT INJECTED INTO PROMPT ===\n")
                tf.write(context)
                tf.write("\n\n=== AGENTIC LOOP SYSTEM INSTRUCTIONS ===\n")
                tf.write("# Edit the instructions below this line. Changes are only active for this session.\n")
                tf.write("# To clear the live override and revert to tools_config.toml, delete all instructions below this header.\n")
                tf.write(current_instr)
                temp_path = tf.name

            try:
                config = app._load_tools_config()
                config_editor = config.get("config", {}).get("editor")
                default_editor = "notepad.exe" if os.name == "nt" else "vi"
                editor = config_editor or os.environ.get("VISUAL") or os.environ.get("EDITOR") or default_editor

                print(f"Opening live prompt editor using '{editor}'...")
                # Split editor string to support editors with arguments (e.g. "code --wait")
                if os.name == "nt":
                    cmd = shlex.split(editor, posix=False) + [temp_path]
                else:
                    cmd = shlex.split(editor) + [temp_path]
                subprocess.run(cmd)

                with open(temp_path, "r", encoding="utf-8") as f:
                    saved_content = f.read()

                marker = "=== AGENTIC LOOP SYSTEM INSTRUCTIONS ==="
                context_header = "=== TOOL CONTEXT INJECTED INTO PROMPT ==="
                new_context = ""
                new_instr = ""

                if marker in saved_content:
                    parts_split = saved_content.split(marker, 1)
                    context_block = parts_split[0]
                    instr_block = parts_split[1]

                    # Extract tool context: strip the header line if present
                    if context_header in context_block:
                        context_lines = context_block.split(context_header, 1)[1]
                    else:
                        context_lines = context_block
                    new_context = context_lines.strip()

                    # Extract instructions: strip comment lines
                    lines = instr_block.splitlines()
                    filtered_lines = []
                    for line in lines:
                        if line.strip().startswith("#"):
                            continue
                        filtered_lines.append(line)
                    new_instr = "\n".join(filtered_lines).strip()
                else:
                    new_instr = saved_content.strip()

                # Save tool context override (empty means revert to tools_config.toml)
                app.live_tool_context = new_context

                if not new_instr:
                    app.live_agentic_instructions = ""
                    print("Live prompt override cleared. Reset to tools_config.toml settings.")
                else:
                    app.live_agentic_instructions = new_instr
                    print("Active system prompt updated successfully for this session.")
            except Exception as e:
                print(f"Error editing live prompt: {e}")
            finally:
                try:
                    os.unlink(temp_path)
                except Exception:
                    pass
            return CommandResult.ok()

        if sub_arg == "restore":
            had_override = bool(app.live_tool_context or app.live_agentic_instructions)
            app.live_tool_context = ""
            app.live_agentic_instructions = ""
            if had_override:
                print("Live prompt overrides restored to tools_config.toml defaults.")
            else:
                print("No live prompt overrides active.")
            return CommandResult.ok()

        # Show the prompt injected during tool operation
        context = app.live_tool_context or app.tool_context or app.generate_tool_context()
        if context:
            print("\n=== TOOL CONTEXT INJECTED INTO PROMPT ===")
            if app.live_tool_context:
                print(" [Live Edit Override Active]")
            print(context)
            print("\n=== AGENTIC LOOP SYSTEM INSTRUCTIONS ===")
            active_instr = app.live_agentic_instructions or app.agentic_instructions or app.default_agentic_instructions
            if app.live_agentic_instructions:
                print(f" [Live Edit Override Active]\n{active_instr}")
            else:
                print(active_instr)
            print("=========================================\n")
        else:
            print("No tools available or tool context could not be generated.")
        return CommandResult.ok()

    elif subcmd == "history":
        # /tool history [csv [file]] [var=<name>]     — list all agentic loops recorded in the active session
        # /tool history <turn_id> [csv [file]] [var=<name>] — show detailed tool calls for a specific session turn
        # /tool history current [csv [file]] [--verbose] [var=<name>] — show the most recent in-memory AGENTIC_LOOP trace
        tokens = []
        for p in parts[2:]:
            tokens.extend(p.strip().split())

        target_var = None
        var_candidates = [t for t in tokens if t.lower().startswith("var=") or t.lower().startswith("target=")]
        for vc in var_candidates:
            if vc.lower().startswith("var="):
                target_var = vc[4:].strip().lstrip("$")
            elif vc.lower().startswith("target="):
                target_var = vc[7:].strip().lstrip("$")

        tokens = [t for t in tokens if not t.lower().startswith("var=") and not t.lower().startswith("target=")]

        verbose = any(t.lower() in ("--verbose", "-v", "verbose") for t in tokens)
        is_csv = any(t.lower() == "csv" or t.lower().endswith(".csv") for t in tokens)
        remaining_tokens = [t for t in tokens if t.lower() not in ("--verbose", "-v", "verbose")]

        csv_filename = None
        if is_csv:
            csv_candidates = [t for t in remaining_tokens if t.lower().endswith(".csv") or (t.lower() != "csv" and t.lower() not in ("current", "last") and not t.isdigit())]
            if csv_candidates:
                csv_filename = csv_candidates[0].strip(" \"'")
            remaining_tokens = [t for t in remaining_tokens if t.lower() != "csv" and t != csv_filename]

        detail_arg = remaining_tokens[0].strip().lower() if remaining_tokens else ""

        if detail_arg in ("current", "last"):
            loop_data = app.buffer_manager.get_script_var('AGENTIC_LOOP') if hasattr(app, "buffer_manager") and app.buffer_manager else None
            history_data = loop_data if isinstance(loop_data, list) else []
            if hasattr(app, "buffer_manager") and app.buffer_manager:
                app.buffer_manager.set_script_var('TOOL_HISTORY', history_data, allow_protected=True)
                if target_var:
                    app.buffer_manager.set_script_var(target_var, history_data, allow_protected=True)

            if is_csv:
                if not isinstance(loop_data, list) or not loop_data:
                    print("No agentic loop has been run yet.")
                    return CommandResult.ok()
                out_path = csv_filename or "agentic_loop_current.csv"
                import csv
                try:
                    with open(out_path, "w", newline="", encoding="utf-8") as f:
                        writer = csv.writer(f, quoting=csv.QUOTE_ALL)
                        writer.writerow(["step", "tool", "status", "duration_ms", "timestamp", "arguments", "result", "exit_code"])
                        for i, rec in enumerate(loop_data, 1):
                            if not isinstance(rec, dict):
                                continue
                            writer.writerow([
                                rec.get("turn", i),
                                rec.get("tool", "unknown"),
                                rec.get("status", "error"),
                                rec.get("duration_ms", ""),
                                rec.get("timestamp", ""),
                                json.dumps(rec.get("arguments", {}), ensure_ascii=False),
                                rec.get("result", ""),
                                rec.get("exit_code", 0),
                            ])
                    print(f"Exported current agentic loop trace to CSV '{out_path}'.")
                except Exception as e:
                    print(f"Error exporting agentic loop to CSV: {e}")
                return CommandResult.ok()

            app.show_agentic_loop_trace(verbose=verbose)
            return CommandResult.ok()

        if detail_arg == "" or (is_csv and not detail_arg.isdigit()):
            # Summarize every turn in the active session that has an agentic_loop
            loops = []
            for turn in (app.session_turns or []):
                al = turn.get("agentic_loop")
                if isinstance(al, list) and al:
                    loops.append(turn)

            history_data = []
            for turn in loops:
                al = turn.get("agentic_loop", [])
                t_id = turn.get("turn_id", 1)
                count = len(al)
                successes = sum(1 for r in al if isinstance(r, dict) and r.get("status") == "success")
                failures = count - successes
                loop_duration = sum(r.get("duration_ms", 0) for r in al if isinstance(r, dict))
                tool_names = []
                for rec in al:
                    if isinstance(rec, dict):
                        tn = rec.get("tool", "unknown")
                        if tn not in tool_names:
                            tool_names.append(tn)
                history_data.append({
                    "turn_id": t_id,
                    "prompt": turn.get("prompt", ""),
                    "agentic_loop": al,
                    "total_calls": count,
                    "success": successes,
                    "failed": failures,
                    "duration_ms": loop_duration,
                    "tools": tool_names,
                })

            if hasattr(app, "buffer_manager") and app.buffer_manager:
                app.buffer_manager.set_script_var('TOOL_HISTORY', history_data, allow_protected=True)
                if target_var:
                    app.buffer_manager.set_script_var(target_var, history_data, allow_protected=True)

            if not app.session_turns:
                print("No active session or no turns recorded.")
                return CommandResult.ok()

            if not loops:
                print("No agentic tool loops found in the active session.")
                print("Tip: Run '/tool loop' or enable '/tool auto on' to execute agentic loops, then use '/tool history' to review them.")
                return CommandResult.ok()

            if is_csv:
                s_name = app.active_session_name or app.active_session_id or "session"
                out_path = csv_filename or f"{s_name}_tool_history.csv"
                import csv
                try:
                    with open(out_path, "w", newline="", encoding="utf-8") as f:
                        writer = csv.writer(f, quoting=csv.QUOTE_ALL)
                        writer.writerow(["turn_id", "step", "tool", "status", "duration_ms", "timestamp", "arguments", "result", "exit_code"])
                        for turn in loops:
                            t_id = turn.get("turn_id", 1)
                            for i, rec in enumerate(turn.get("agentic_loop", []), 1):
                                if not isinstance(rec, dict):
                                    continue
                                writer.writerow([
                                    t_id,
                                    rec.get("turn", i),
                                    rec.get("tool", "unknown"),
                                    rec.get("status", "error"),
                                    rec.get("duration_ms", ""),
                                    rec.get("timestamp", ""),
                                    json.dumps(rec.get("arguments", {}), ensure_ascii=False),
                                    rec.get("result", ""),
                                    rec.get("exit_code", 0),
                                ])
                    print(f"Exported session agentic tool history to CSV '{out_path}'.")
                except Exception as e:
                    print(f"Error exporting tool history to CSV: {e}")
                return CommandResult.ok()

            session_label = app.active_session_name or app.active_session_id or "unsaved"
            print(f"\n=== AGENTIC LOOP HISTORY (Session: {session_label}) ===")
            total_calls = 0
            total_success = 0
            total_failed = 0
            for turn in loops:
                al = turn["agentic_loop"]
                t_id = turn.get("turn_id", "?")
                count = len(al)
                successes = sum(1 for r in al if isinstance(r, dict) and r.get("status") == "success")
                failures = count - successes
                total_calls += count
                total_success += successes
                total_failed += failures
                tool_names = []
                for rec in al:
                    if isinstance(rec, dict):
                        tn = rec.get("tool", "unknown")
                        if tn not in tool_names:
                            tool_names.append(tn)
                tools_str = ", ".join(tool_names)
                if len(tools_str) > 80:
                    tools_str = tools_str[:77] + "..."
                # Aggregate tool call durations if available
                loop_duration = sum(r.get("duration_ms", 0) for r in al if isinstance(r, dict))
                duration_str = f" [{loop_duration:.0f}ms]" if loop_duration else ""
                print(f"  Turn {t_id}: {count} calls ({successes} ok, {failures} fail){duration_str} — {tools_str}")

            print("-" * 80)
            print(f"Total: {len(loops)} loop(s), {total_calls} tool calls ({total_success} success, {total_failed} failed)")
            print("Use '/tool history <turn_id>' for per-call details, '/tool history current' for the latest in-memory loop.")
            print("=" * 80)
            return CommandResult.ok()

        # Specific turn_id requested — show detailed tool calls
        try:
            target_id = int(detail_arg)
        except ValueError:
            print(f"Invalid argument '{detail_arg}'. Usage: /tool history [<turn_id>|current] [csv [file.csv]] [--verbose]")
            return CommandResult.ok()

        matched_turn = None
        for turn in app.session_turns:
            if turn.get("turn_id") == target_id:
                matched_turn = turn
                break

        if matched_turn is None:
            print(f"No turn {target_id} found in the active session.")
            available = [t.get("turn_id") for t in app.session_turns if t.get("agentic_loop")]
            if available:
                print(f"Turns with agentic loops: {', '.join(str(t) for t in available)}")
            else:
                print("No turns with agentic loops in this session.")
            return CommandResult.ok()

        al = matched_turn.get("agentic_loop")
        history_data = al if isinstance(al, list) else []
        if hasattr(app, "buffer_manager") and app.buffer_manager:
            app.buffer_manager.set_script_var('TOOL_HISTORY', history_data, allow_protected=True)
            if target_var:
                app.buffer_manager.set_script_var(target_var, history_data, allow_protected=True)

        if not isinstance(al, list) or not al:
            print(f"Turn {target_id} has no recorded agentic loop data.")
            return CommandResult.ok()

        if is_csv:
            out_path = csv_filename or f"turn_{target_id}_tool_history.csv"
            import csv
            try:
                with open(out_path, "w", newline="", encoding="utf-8") as f:
                    writer = csv.writer(f, quoting=csv.QUOTE_ALL)
                    writer.writerow(["turn_id", "step", "tool", "status", "duration_ms", "timestamp", "arguments", "result", "exit_code"])
                    for i, rec in enumerate(al, 1):
                        if not isinstance(rec, dict):
                            continue
                        writer.writerow([
                            target_id,
                            rec.get("turn", i),
                            rec.get("tool", "unknown"),
                            rec.get("status", "error"),
                            rec.get("duration_ms", ""),
                            rec.get("timestamp", ""),
                            json.dumps(rec.get("arguments", {}), ensure_ascii=False),
                            rec.get("result", ""),
                            rec.get("exit_code", 0),
                        ])
                print(f"Exported turn {target_id} tool history to CSV '{out_path}'.")
            except Exception as e:
                print(f"Error exporting turn {target_id} tool history to CSV: {e}")
            return CommandResult.ok()

        total = len(al)
        successes = sum(1 for r in al if isinstance(r, dict) and r.get("status") == "success")
        failures = total - successes

        print(f"\n=== AGENTIC LOOP — Turn {target_id} ===")
        prompt_text = matched_turn.get("prompt", "")
        if prompt_text:
            snippet = prompt_text.replace("\n", " ").strip()
            if len(snippet) > 100:
                snippet = snippet[:97] + "..."
            print(f"Prompt: {snippet}")
        print(f"Total tool calls: {total}  ({successes} success, {failures} failed)")
        print("-" * 80)

        for i, rec in enumerate(al, 1):
            if not isinstance(rec, dict):
                print(f"[{i}] (invalid record: {type(rec).__name__}) — SKIPPED")
                continue
            tool_name = rec.get("tool", "unknown")
            step = rec.get("turn", i)
            status = rec.get("status", "error")
            status_label = "SUCCESS" if status == "success" else "FAILED"
            duration_ms = rec.get("duration_ms")
            duration_str = ""
            if duration_ms is not None:
                try:
                    duration_str = f" ({float(duration_ms):.0f}ms)"
                except (ValueError, TypeError):
                    duration_str = f" ({duration_ms}ms)"
            print(f"[{i}] Step {step} · {tool_name} — {status_label}{duration_str}")

            # Show timestamp if available
            ts = rec.get("timestamp")
            if ts:
                print(f"      time: {ts}")

            # Show arguments on detail view
            args = rec.get("arguments", {})
            if args:
                args_str = json.dumps(args, ensure_ascii=False)
                if len(args_str) > 200:
                    args_str = args_str[:197] + "..."
                print(f"      args: {args_str}")

            if status != "success":
                result = rec.get("result", "")
                if isinstance(result, str):
                    snippet = result.replace("\n", " ").strip()
                    if len(snippet) > 120:
                        snippet = snippet[:117] + "..."
                else:
                    snippet = str(result)
                if snippet:
                    print(f"      reason: {snippet}")

        print("=" * 80)
        return CommandResult.ok()

    elif subcmd == "export":
        # /tool export csv <filename.csv>
        raw_args = command.split(maxsplit=2)[2] if len(command.split(maxsplit=2)) > 2 else ""
        words = raw_args.split()
        if not words:
            print("Usage: /tool export csv <filename.csv>")
            return CommandResult.ok()

        is_csv = words[0].lower() == "csv" or words[-1].lower().endswith(".csv")
        if words[0].lower() == "csv":
            words = words[1:]
        out_path = " ".join(words).strip(" \"'")
        if not out_path and is_csv:
            s_name = app.active_session_name or app.active_session_id or "session"
            out_path = f"{s_name}_tool_history.csv"
        elif not out_path:
            print("Usage: /tool export csv <filename.csv>")
            return CommandResult.ok()

        loops = []
        if app.session_turns:
            for turn in app.session_turns:
                al = turn.get("agentic_loop")
                if isinstance(al, list) and al:
                    loops.append(turn)

        if not loops:
            print("No agentic tool loops found in active session to export.")
            return CommandResult.ok()

        import csv
        try:
            with open(out_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f, quoting=csv.QUOTE_ALL)
                writer.writerow(["turn_id", "step", "tool", "status", "duration_ms", "timestamp", "arguments", "result", "exit_code"])
                for turn in loops:
                    t_id = turn.get("turn_id", 1)
                    for i, rec in enumerate(turn.get("agentic_loop", []), 1):
                        if not isinstance(rec, dict):
                            continue
                        writer.writerow([
                            t_id,
                            rec.get("turn", i),
                            rec.get("tool", "unknown"),
                            rec.get("status", "error"),
                            rec.get("duration_ms", ""),
                            rec.get("timestamp", ""),
                            json.dumps(rec.get("arguments", {}), ensure_ascii=False),
                            rec.get("result", ""),
                            rec.get("exit_code", 0),
                        ])
            print(f"Exported session agentic tool history to CSV '{out_path}'.")
        except Exception as e:
            print(f"Error exporting tool history to CSV: {e}")
        return CommandResult.ok()

    elif subcmd == "replay":
        return await _handle_tool_replay(ctx, parts)

    elif subcmd == "retry":
        return await _handle_tool_retry(ctx, parts, command)

    elif subcmd == "continue":
        return await _handle_tool_continue(ctx, parts, command)

    elif subcmd == "inject":
        return await _handle_tool_inject(ctx, parts, command)

    elif subcmd in ("translate", "convert", "parse"):
        raw_text = command.split(maxsplit=2)[2].strip() if len(parts) > 2 else (app.buffer_manager.get_script_var('LAST_COMPLETION') or "")
        if not raw_text:
            print("No text or LAST_COMPLETION available to translate.")
            return CommandResult.ok()

        calls = app.extract_tool_calls(raw_text)
        if not calls:
            print("No valid tool calls extracted from input text.")
            return CommandResult.ok()

        if len(calls) == 1:
            json_output = f"```json\n{json.dumps(calls[0], indent=2)}\n```"
        else:
            json_output = f"```json\n{json.dumps(calls, indent=2)}\n```"

        print(json_output)
        app.buffer_manager.set_script_var('LAST_TOOL_TRANSLATED', json.dumps(calls), allow_protected=True)
        return CommandResult.ok()

    else:
        # Check if argument is a filename (ends with .json)
        arg = command.split(maxsplit=1)[1]
        if arg.endswith('.json') and os.path.exists(arg):
            try:
                with open(arg, 'r') as f:
                    json_str = f.read()
                await app.dispatch_tool(json_str)
            except Exception as e:
                print(f"Error reading file {arg}: {e}")
        else:
            # Provide JSON directly - dispatch it
            await app.dispatch_tool(arg)
        return CommandResult.ok()


# ---------------------------------------------------------------------------
# /tool replay — time-travel agentic loop replay
# ---------------------------------------------------------------------------

_TOOL_REPLAY_KEYWORDS = {"at", "diff", "step"}


def _parse_tool_replay_tokens(tokens, ctx):
    """Parse /tool replay tokens into (turn_id, mode, mode_args, limit, target_var).

    turn_id is the session turn whose agentic_loop we replay (None = most
    recent turn with an agentic loop). mode is one of summary/at/diff/step.
    """
    app = ctx.app
    limit = None
    turn_id = None
    mode = "summary"
    mode_args = []
    target_var = None

    filtered = []
    for tok in tokens:
        if tok.lower().startswith("limit="):
            try:
                limit = int(tok.split("=", 1)[1])
            except ValueError:
                pass
        elif tok.lower().startswith("var="):
            target_var = tok[4:].strip().lstrip("$")
        elif tok.lower().startswith("target="):
            target_var = tok[7:].strip().lstrip("$")
        else:
            filtered.append(tok)

    if filtered:
        first = filtered[0]
        if first.lower() not in _TOOL_REPLAY_KEYWORDS:
            # First token is a turn id
            try:
                turn_id = int(first)
            except ValueError:
                turn_id = None
            rest = filtered[1:]
        else:
            rest = filtered
    else:
        rest = []

    if rest:
        head = rest[0].lower()
        if head == "at":
            mode = "at"
            mode_args = rest[1:]
        elif head == "diff":
            mode = "diff"
            mode_args = rest[1:]
        elif head == "step":
            mode = "step"
            mode_args = rest[1:]

    return turn_id, mode, mode_args, limit, target_var


def _render_tool_replay_summary(snapshots, turn_id):
    if not snapshots:
        print("No agentic loop found to replay.")
        return
    print("\n" + "=" * 78)
    print(f"AGENTIC LOOP REPLAY — SUMMARY (turn {turn_id})")
    print("=" * 78)
    header = f"{'Step':<6}{'Tool':<20}{'Msgs':<6}{'Uncut Tok':<12}{'Trunc Tok':<12}{'Evicted':<9}{'AnchorWarn':<11}"
    print(header)
    print("-" * 78)
    for s in snapshots:
        warn = "YES" if s.anchors_alone_exceed_limit else "-"
        tool_disp = s.tool or "(baseline)"
        print(
            f"{s.step:<6}{tool_disp:<20.18}{s.message_count:<6}{s.total_tokens:<12}"
            f"{s.truncated_tokens:<12}{len(s.evicted_indices):<9}{warn:<11}"
        )
    print("=" * 78)
    print("Notes / Column Legend:")
    print("  • Step:       Agentic loop step index (0 = pre-loop baseline state)")
    print("  • Tool:       Tool invoked at this step")
    print("  • Msgs:       Total messages in prompt array before truncation")
    print("  • Uncut Tok:  Raw token count of prompt array before truncation")
    print("  • Trunc Tok:  Token count after auto-truncation/eviction to fit limit")
    print("  • Evicted:    Number of older intermediate messages dropped from prompt")
    print("  • AnchorWarn: YES if system + initial user anchors exceed context limit")
    print()


def _render_tool_replay_at(snapshot, system_prompt):
    print("\n" + "=" * 78)
    label = f"STEP {snapshot.step}" if snapshot.step else "STEP 0 (pre-loop baseline)"
    print(f"AGENTIC LOOP — {label} (turn {snapshot.turn_id})")
    print("=" * 78)
    print(f"Tool: {snapshot.tool or '-'}  |  Status: {snapshot.status or '-'}  "
          f"|  Duration: {snapshot.duration_ms:.0f}ms" if snapshot.step else
          "Tool: -  |  Status: -  |  Duration: -")
    print(f"Messages: {snapshot.message_count}  |  Uncut tokens: {snapshot.total_tokens}  "
          f"|  Truncated tokens: {snapshot.truncated_tokens}")
    print(f"Evicted indices: {snapshot.evicted_indices or 'none'}")
    print(f"Anchor overflow: {'YES (anchors alone exceed limit)' if snapshot.anchors_alone_exceed_limit else 'no'}")
    print(f"System prompt (approximate): {_replay_preview(system_prompt, 70)}")
    print("-" * 78)

    surviving_keys = {(m.get("role"), m.get("content")) for m in snapshot.truncated_messages}
    evicted_set = set(snapshot.evicted_indices)
    # Determine anchor indices (system at 0 if present, first user after it)
    anchor_idxs = set()
    rem_idx = 0
    if len(snapshot.messages) > 0 and snapshot.messages[0].get("role") == "system":
        anchor_idxs.add(0)
        rem_idx = 1
    if len(snapshot.messages) > rem_idx and snapshot.messages[rem_idx].get("role") == "user":
        anchor_idxs.add(rem_idx)

    for i, m in enumerate(snapshot.messages):
        role = m.get("role", "?")
        content = m.get("content", "")
        clen = len(content) if isinstance(content, str) else 0
        tags = []
        if i in anchor_idxs:
            tags.append("ANCHOR")
        if i in evicted_set or (m.get("role"), m.get("content")) not in surviving_keys and snapshot.did_truncate:
            tags.append("EVICTED")
        tag_str = f" [{', '.join(tags)}]" if tags else ""
        print(f"  [{i}] {role:<10} ({clen} chars){tag_str}")
        print(f"      {_replay_preview(content, 72)}")
    print("=" * 78 + "\n")


def _render_tool_replay_diff(diff):
    print("\n" + "=" * 78)
    print(f"AGENTIC LOOP DIFF: STEP {diff.step_a} -> STEP {diff.step_b}")
    print("=" * 78)
    print(f"Token delta (pre-truncation): {diff.token_delta:+d}")
    print(f"Evicted-count delta: {diff.truncation_evicted_delta:+d}")
    print(f"Anchor overflow changed: {'yes' if diff.anchor_overflow_changed else 'no'}")
    print("-" * 78)

    print(f"Added messages ({len(diff.added_messages)}):")
    if diff.added_messages:
        for m in diff.added_messages:
            print(f"  + {m.get('role', '?'):<10} {_replay_preview(m.get('content', ''), 64)}")
    else:
        print("  (none)")

    print(f"Newly evicted messages ({len(diff.newly_evicted)}):")
    if diff.newly_evicted:
        for m in diff.newly_evicted:
            print(f"  - {m.get('role', '?'):<10} {_replay_preview(m.get('content', ''), 64)}")
    else:
        print("  (none)")
    print("=" * 78 + "\n")


async def _handle_tool_replay(ctx: CommandContext, parts: list) -> CommandResult:
    """Handle /tool replay [<turn_id>] [at <N> | diff <A> <B> | step] [limit=<N>] [var=<name>]."""
    from chatybot.agentic_replayer import AgenticReplayer

    app = ctx.app
    # Tokens after "/tool replay"
    raw_tokens = []
    for p in parts[2:]:
        raw_tokens.extend(p.strip().split())
    turn_id, mode, mode_args, limit, target_var = _parse_tool_replay_tokens(raw_tokens, ctx)

    target = app.active_session_id or app.active_session_name
    if not target:
        print("No active session. Usage: /tool replay [<turn_id>] [at <N> | diff <A> <B> | step] [limit=<N>]")
        return CommandResult.ok()

    replayer = AgenticReplayer(app)
    try:
        meta, turns = replayer._load_turns(target)
    except Exception as e:
        print(f"Error: could not load session '{target}': {e}")
        return CommandResult.ok()

    system_prompt = replayer._session_replayer.reconstruct_system_prompt(meta, turns)
    agentic_turn = replayer._find_agentic_turn(turns, turn_id)
    if agentic_turn is None:
        if turn_id is not None:
            print(f"No agentic loop found on turn {turn_id}.")
        else:
            print("No agentic tool loops found in the active session.")
            print("Tip: Run '/tool loop' or enable '/tool auto on' to execute agentic loops, then use '/tool replay' to review them.")
        return CommandResult.ok()

    resolved_turn_id = agentic_turn.get("turn_id")
    loop = agentic_turn.get("agentic_loop") or []
    n_steps = len(loop) if isinstance(loop, list) else 0

    if mode == "summary":
        snapshots = replayer.replay_loop(
            target, turn_id=resolved_turn_id, limit=limit, turns=turns, system_prompt=system_prompt
        )
        data = [dataclasses.asdict(s) for s in snapshots] if snapshots else []
        if hasattr(app, "buffer_manager") and app.buffer_manager:
            app.buffer_manager.set_script_var('TOOL_REPLAY', data, allow_protected=True)
            if target_var:
                app.buffer_manager.set_script_var(target_var, data, allow_protected=True)
        _render_tool_replay_summary(snapshots, resolved_turn_id)
        return CommandResult.ok()

    if mode == "at":
        if not mode_args:
            print("Usage: /tool replay [<turn_id>] at <N>")
            return CommandResult.ok()
        try:
            step_n = int(mode_args[0])
        except ValueError:
            print(f"Invalid step number: {mode_args[0]}")
            return CommandResult.ok()
        snap = replayer.snapshot_at_step(turns, resolved_turn_id, system_prompt, step_n, limit=limit)
        if snap is None:
            print(f"Step {step_n} not found. Valid steps: 0..{n_steps}")
            return CommandResult.ok()
        data = dataclasses.asdict(snap)
        if hasattr(app, "buffer_manager") and app.buffer_manager:
            app.buffer_manager.set_script_var('TOOL_REPLAY', data, allow_protected=True)
            if target_var:
                app.buffer_manager.set_script_var(target_var, data, allow_protected=True)
        _render_tool_replay_at(snap, system_prompt)
        return CommandResult.ok()

    if mode == "diff":
        if len(mode_args) < 2:
            print("Usage: /tool replay [<turn_id>] diff <A> <B>")
            return CommandResult.ok()
        try:
            step_a = int(mode_args[0])
            step_b = int(mode_args[1])
        except ValueError:
            print(f"Invalid step numbers: {mode_args[:2]}")
            return CommandResult.ok()
        diff = replayer.diff_steps(
            target, resolved_turn_id, step_a, step_b, limit=limit, turns=turns, system_prompt=system_prompt
        )
        if diff is None:
            print(f"Could not build diff for steps {step_a} / {step_b}. Valid steps: 0..{n_steps}")
            return CommandResult.ok()
        data = dataclasses.asdict(diff)
        if hasattr(app, "buffer_manager") and app.buffer_manager:
            app.buffer_manager.set_script_var('TOOL_REPLAY', data, allow_protected=True)
            if target_var:
                app.buffer_manager.set_script_var(target_var, data, allow_protected=True)
        _render_tool_replay_diff(diff)
        return CommandResult.ok()

    if mode == "step":
        snapshots = replayer.replay_loop(
            target, turn_id=resolved_turn_id, limit=limit, turns=turns, system_prompt=system_prompt
        )
        if not snapshots:
            print("No steps to step through.")
            return CommandResult.ok()
        data = [dataclasses.asdict(s) for s in snapshots] if snapshots else []
        if hasattr(app, "buffer_manager") and app.buffer_manager:
            app.buffer_manager.set_script_var('TOOL_REPLAY', data, allow_protected=True)
            if target_var:
                app.buffer_manager.set_script_var(target_var, data, allow_protected=True)
        print("\nInteractive agentic loop stepper. Press Enter to advance, 'q' to quit, 'show' for full dump.")
        for s in snapshots:
            print("\n" + "-" * 78)
            tool_disp = s.tool or "(baseline)"
            print(f"Step {s.step} | {tool_disp} | msgs={s.message_count} uncut={s.total_tokens} "
                  f"trunc={s.truncated_tokens} evicted={len(s.evicted_indices)} "
                  f"anchor_warn={'YES' if s.anchors_alone_exceed_limit else '-'}")
            try:
                cmd = input("[Enter]=next q=quit show=full> ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                print("\nStepper exited.")
                break
            if cmd in ("q", "quit", "exit"):
                break
            if cmd in ("show", "s", "full"):
                _render_tool_replay_at(s, system_prompt)
        print("\nStepper finished.")
        return CommandResult.ok()

    return CommandResult.ok()


# ---------------------------------------------------------------------------
# /tool retry — live tool rescue and repair
# ---------------------------------------------------------------------------

def _extract_retry_candidate(raw_text: str, app) -> dict:
    """Analyze raw completion text to extract or infer candidate tool calls and arguments.

    Returns a dict with keys:
      'tool': detected tool name (or None/candidate)
      'arguments': dict of harvested arguments
      'raw_match': raw matched text snippet
      'is_valid': bool indicating if tool is in known enabled tools
    """
    import re

    known_tools = app.get_known_tool_names() if hasattr(app, "get_known_tool_names") else set()

    # 1. First, check if standard extract_tool_calls finds any valid call
    calls = app.extract_tool_calls(raw_text) if hasattr(app, "extract_tool_calls") else []
    if calls:
        first = calls[0]
        tool_name = first.get("tool", "")
        return {
            "tool": tool_name,
            "arguments": first.get("arguments", {}),
            "raw_match": json.dumps(first, indent=2),
            "is_valid": tool_name in known_tools or tool_name.startswith("mcp__"),
        }

    detected_tool = None
    args: dict = {}
    normalized_text = raw_text.replace('\\n', '\n')

    # Primary parameter lookup for single-argument shorthand
    primary_params = {
        "read_file": "path",
        "list_directory": "path",
        "change_dir": "path",
        "delete_file": "path",
        "find_files": "pattern",
        "run_command": "command",
        "grep_search": "query",
        "calculate": "expression",
        "read_url": "url",
        "ask_user": "prompt",
    }

    # 2. Check for XML tag variants: <invoke="name">, <invoke="=" name">, <function=name>, <tool name="name">, <invokename="name">
    tag_name_match = re.search(
        r'<(?:invoke|function|tool|call|dots_function_call|action)(?:=|\s*name=|\s*=|\s+)["\'=\s]*([a-zA-Z0-9_\-\.]+)["\'\s]*',
        raw_text,
        re.IGNORECASE,
    )
    if tag_name_match:
        cand_name = tag_name_match.group(1).strip()
        if cand_name.lower() not in ("dots_function_call", "action", "tool_call"):
            detected_tool = cand_name

    # Check for direct tool XML tags: <read_file> ... </read_file>
    if not detected_tool:
        for t in known_tools:
            if re.search(rf'<({re.escape(t)})\b[^>]*>', raw_text, re.IGNORECASE):
                detected_tool = t
                break

    # Check for parameter blocks: <parameter name="key">val</parameter> or <param=key>val</param>
    param_matches = list(re.finditer(
        r'<(?:parameter|param)\s+name=["\']([^"\']+)["\'][^>]*>(.*?)</(?:parameter|param)>',
        raw_text,
        re.IGNORECASE | re.DOTALL,
    ))
    if not param_matches:
        param_matches = list(re.finditer(
            r'<(?:parameter|param)=["\']?([a-zA-Z0-9_\-\.]+)["\']?[^>]*>(.*?)</(?:parameter|param)>',
            raw_text,
            re.IGNORECASE | re.DOTALL,
        ))
    for pm in param_matches:
        k = pm.group(1).strip()
        v = pm.group(2).strip()
        args[k] = v

    # If direct tool XML tag matched (<read_file><path>...</path></read_file>), extract inner parameter tags
    if detected_tool and not args:
        inner_tag_match = re.search(rf'<({re.escape(detected_tool)})\b[^>]*>(.*?)</\1>', raw_text, re.IGNORECASE | re.DOTALL)
        if inner_tag_match:
            inner_body = inner_tag_match.group(2)
            for m_inner in re.finditer(r'<([a-zA-Z0-9_]+)[^>]*>(.*?)</\1>', inner_body, re.DOTALL):
                args[m_inner.group(1).strip()] = m_inner.group(2).strip()

    # 3. Check for Python / functional invocation syntax: tool_name(arg="val", ...) or tool_name("val")
    if not detected_tool:
        fn_call_match = re.search(r'\b([a-zA-Z0-9_]+)\s*\(([^)]*)\)', normalized_text)
        if fn_call_match and (fn_call_match.group(1) in known_tools or fn_call_match.group(1).startswith("mcp__")):
            detected_tool = fn_call_match.group(1)
            raw_args = fn_call_match.group(2).strip()
            kv_pairs = re.findall(r'([a-zA-Z0-9_]+)\s*=\s*["\']([^"\']*)["\']', raw_args)
            if kv_pairs:
                for k, v in kv_pairs:
                    args[k] = v
            elif raw_args:
                m_lit = re.match(r'^["\']([^"\']*)["\']$', raw_args)
                arg_val = m_lit.group(1) if m_lit else raw_args
                p_name = primary_params.get(detected_tool, "path")
                args[p_name] = arg_val

    # 4. Check for Action / Tool prefix lines or direct tool_name: argument
    if not detected_tool:
        action_match = re.search(r'^\s*(?:action|tool|tool_call)\s*:\s*["\']?([a-zA-Z0-9_\-\.]+)["\']?', normalized_text, re.IGNORECASE | re.MULTILINE)
        if action_match and (action_match.group(1) in known_tools or action_match.group(1).startswith("mcp__")):
            detected_tool = action_match.group(1)

        action_input_match = re.search(r'^\s*(?:action input|tool input|input|args|arguments)\s*:\s*(.+)$', normalized_text, re.IGNORECASE | re.MULTILINE)
        if action_input_match:
            raw_inp = action_input_match.group(1).strip()
            try:
                parsed_inp = json.loads(raw_inp)
                if isinstance(parsed_inp, dict):
                    args.update(parsed_inp)
            except Exception:
                kv_pairs = re.findall(r'([a-zA-Z0-9_]+)\s*=\s*["\']([^"\']*)["\']', raw_inp)
                for k, v in kv_pairs:
                    args[k] = v

    if not detected_tool:
        # Check for tool_name: <argument> (e.g. read_file: 3kingdoms_culture.chatdsl)
        for t in known_tools:
            m_direct = re.search(rf'^\s*{re.escape(t)}\s*:\s*(.+)$', normalized_text, re.IGNORECASE | re.MULTILINE)
            if m_direct:
                detected_tool = t
                val = m_direct.group(1).strip().strip('"\'`')
                p_name = primary_params.get(t, "path")
                args[p_name] = val
                break

    # 5. Check for any standalone mention of a known tool in text (preferring text outside <think> blocks)
    if not detected_tool:
        text_outside_think = re.sub(r'<think>.*?</think>', '', normalized_text, flags=re.DOTALL | re.IGNORECASE).strip()
        search_target = text_outside_think or normalized_text
        for t in known_tools:
            if re.search(rf'\b{re.escape(t)}\b', search_target):
                detected_tool = t
                break

    # 6. If a known tool was detected, extract parameters suited to that tool
    if detected_tool in ("read_file", "write_file", "replace_file_content", "delete_file", "list_directory", "change_dir") and "path" not in args:
        path_match = re.search(r'(/[\w\.\-/]+\.(?:chatdsl|dsl|py|sh|txt|json|md))', normalized_text)
        if not path_match:
            path_match = re.search(r'\b([\w\-]+\.(?:chatdsl|dsl|py|sh|txt|json|md))\b', normalized_text)
        if path_match:
            args["path"] = path_match.group(1)

    # 7. Fallback heuristics ONLY if no known tool has been identified
    if not detected_tool:
        # Check markdown code blocks
        fence_matches = list(re.finditer(r'```([a-zA-Z0-9_\-\.]*)\b[\s:]*(.*?)```', normalized_text, re.DOTALL))
        for fm in fence_matches:
            f_lang = fm.group(1).strip().lower()
            f_body = fm.group(2).strip()

            if f_lang in ("bash", "sh", "zsh"):
                detected_tool = "run_command"
                args["command"] = f_body
                break
            elif any(w in normalized_text.lower() for w in ("write to", "save to", "create file", "write this out")):
                detected_tool = "write_file"
                if "content" not in args:
                    args["content"] = f_body
                break

    if not detected_tool and not args:
        shell_match = re.search(r'(?:^|\n)\s*((?:find|ls|grep|cat|mkdir|touch|cp|mv|git|python|pytest|sh|bash)\s+[^\n]+)', normalized_text, re.IGNORECASE)
        if shell_match:
            detected_tool = "run_command"
            args["command"] = shell_match.group(1).strip()

    # Populate default scratchpad path for write_file if needed
    if detected_tool == "write_file" and "path" not in args and hasattr(app, "get_scratch_dir"):
        scratch = app.get_scratch_dir(create=False)
        if scratch:
            args["path"] = os.path.join(scratch, "script.chatdsl")

    # Final validity determination
    is_valid = bool(detected_tool and (detected_tool in known_tools or detected_tool.startswith("mcp__")))
    return {
        "tool": detected_tool or "CHANGE_ME",
        "arguments": args,
        "raw_match": raw_text[:500],
        "is_valid": is_valid,
    }


def _build_tool_retry_buffer(candidate: dict, app, raw_text: str = "") -> str:
    """Build the template file for $EDITOR with header comments, original raw completion, schema hints, and pre-filled JSON."""
    config = app._load_tools_config() if hasattr(app, "_load_tools_config") else {}
    tools_section = config.get("tools", {}) if config else {}
    known_tools = app.get_known_tool_names() if hasattr(app, "get_known_tool_names") else set()

    tool_name = candidate.get("tool") or "CHANGE_ME"
    is_valid = (candidate.get("is_valid", False) or (tool_name in known_tools or tool_name.startswith("mcp__"))) and tool_name != "CHANGE_ME"
    args = candidate.get("arguments") or {}

    lines = []
    lines.append("# ==============================================================================")
    lines.append("# TOOL RETRY LIVE EDITOR")
    lines.append("# ==============================================================================")

    # 1. Include Original Raw Completion from LAST_COMPLETION in comments
    if raw_text and raw_text.strip():
        lines.append("# ORIGINAL COMPLETION / RAW TOOL CALL (LAST_COMPLETION):")
        lines.append("# ------------------------------------------------------------------------------")
        for r_line in raw_text.strip().splitlines():
            lines.append(f"# {r_line}")
        lines.append("# ------------------------------------------------------------------------------")
        lines.append("#")

    # 2. Schema or Warning
    if is_valid:
        lines.append(f"# Target Tool: {tool_name}")
        meta = tools_section.get(tool_name, {})
        desc = meta.get("description", "No description available")
        lines.append(f"# Description: {desc}")
        lines.append("#")
        params = meta.get("parameters", {})
        if params:
            lines.append("# PARAMETER SCHEMA:")
            for p_name, p_rules in params.items():
                p_type = p_rules.get("type", "string")
                p_desc = p_rules.get("description", "")
                p_opt = "optional" if p_rules.get("optional") else "required"
                lines.append(f"#   - {p_name} ({p_type}, {p_opt}): {p_desc}")
        else:
            lines.append("# (No parameters declared)")
    else:
        lines.append(f"# ⚠️  WARNING: '{tool_name}' is NOT a recognized/enabled tool name!")
        lines.append("# Please edit the \"tool\" property below to a valid tool name.")
        lines.append("#")
        lines.append("# AVAILABLE ENABLED TOOLS:")
        enabled_count = 0
        for t_name, t_meta in tools_section.items():
            is_enabled = app.tool_overrides.get(t_name, t_meta.get("enabled", False)) if hasattr(app, "tool_overrides") else t_meta.get("enabled", False)
            if is_enabled:
                t_desc = t_meta.get("description", "")[:70]
                lines.append(f"#   - {t_name:<22}: {t_desc}")
                enabled_count += 1
        if enabled_count == 0:
            for t_name in sorted(known_tools):
                lines.append(f"#   - {t_name}")

    lines.append("#")
    lines.append("# INSTRUCTIONS:")
    lines.append("#   - Edit the JSON payload below (copy/paste from the raw completion above).")
    lines.append("#   - Save and exit your editor to dispatch the tool call.")
    lines.append("#   - To cancel execution, delete the contents or leave an empty object {}.")
    lines.append("# ==============================================================================")

    payload = {
        "tool": tool_name if is_valid else (tool_name or "CHANGE_ME"),
        "arguments": args,
    }
    lines.append(json.dumps(payload, indent=2, ensure_ascii=False))
    return "\n".join(lines)


def _record_rescued_tool_execution(app, tool_name: str, args: dict, result_str: str) -> None:
    """Format and display tool output banner and record rescued tool execution in session history."""
    from datetime import datetime

    chars_cnt = len(result_str or "")
    lines_cnt = len((result_str or "").splitlines())
    kb_size = chars_cnt / 1024.0

    preview_lines = (result_str or "").strip().splitlines()
    preview_snippet = "\n".join(preview_lines[:15])
    if len(preview_lines) > 15:
        preview_snippet += f"\n... ({len(preview_lines) - 15} more lines) ..."

    exit_code_str = (app.buffer_manager.get_script_var('TOOL_DISPATCH_EXIT_CODE') or "0") if hasattr(app, "buffer_manager") else "0"
    is_success = str(exit_code_str) == "0" and not (result_str or "").startswith("Error:")

    status_icon = "✔" if is_success else "✖"
    status_label = "SUCCESS" if is_success else "FAILED / ERROR"

    print("\n" + "=" * 80)
    print(f"{status_icon} TOOL RESCUE {status_label}: {tool_name} ({chars_cnt} chars, {lines_cnt} lines, {kb_size:.1f} KB)")
    print("=" * 80)
    if preview_snippet:
        print(preview_snippet)
    else:
        print("(No output returned)")
    print("=" * 80)
    print("Tip: Run '/tool continue' (or '/continue') to hand this result to the model and resume the agentic loop.\n")

    tool_rec = {
        "turn": 1,
        "tool": tool_name,
        "arguments": args,
        "result": result_str,
        "exit_code": 0 if is_success else 1,
        "status": "success" if is_success else "error",
        "timestamp": datetime.now().isoformat(),
        "duration_ms": 0.0,
    }

    if hasattr(app, "buffer_manager") and app.buffer_manager:
        app.buffer_manager.set_script_var('LAST_TOOL_RESCUED', tool_rec, allow_protected=True)
        current_loop = app.buffer_manager.get_script_var('AGENTIC_LOOP') or []
        if not isinstance(current_loop, list):
            current_loop = []
        current_loop.append(tool_rec)
        app.buffer_manager.set_script_var('AGENTIC_LOOP', current_loop, allow_protected=True)

    if hasattr(app, "session_turns") and app.session_turns and getattr(app, "session_mode", "") != "off":
        last_turn = app.session_turns[-1]
        turn_loop = last_turn.get("agentic_loop") or []
        if not isinstance(turn_loop, list):
            turn_loop = []
        tool_rec["turn"] = len(turn_loop) + 1
        turn_loop.append(tool_rec)
        last_turn["agentic_loop"] = turn_loop


async def _handle_tool_retry(ctx: CommandContext, parts: list, command: str) -> CommandResult:
    """Handle /tool retry [edit|fix|run] [--continue] command."""
    app = ctx.app
    import subprocess
    import tempfile

    should_continue = any(p.lower() in ("--continue", "-c", "continue") for p in parts[2:])
    clean_parts = [p for p in parts[2:] if p.lower() not in ("--continue", "-c", "continue")]

    mode = "edit"
    if clean_parts:
        mode = clean_parts[0].strip().lower()

    # Retrieve last completion text
    raw_text = (app.buffer_manager.get_script_var('LAST_COMPLETION') or "") if hasattr(app, "buffer_manager") else ""
    if not raw_text and hasattr(app, "chat_history") and app.chat_history:
        raw_text = app.chat_history[-1][1] or ""

    if not raw_text.strip():
        print("Error: No completion available in LAST_COMPLETION or chat history to retry.")
        return CommandResult.ok()

    candidate = _extract_retry_candidate(raw_text, app)

    # -------------------------------------------------------------------------
    # Mode: 'run' (Dispatch directly without opening editor if already valid)
    # -------------------------------------------------------------------------
    if mode == "run":
        if candidate.get("is_valid") and candidate.get("arguments"):
            payload_str = json.dumps({"tool": candidate["tool"], "arguments": candidate["arguments"]})
            print(f"Directly dispatching detected tool '{candidate['tool']}'...")
            res = await app.dispatch_tool(payload_str)
            _record_rescued_tool_execution(app, candidate["tool"], candidate["arguments"], res)
            if should_continue:
                await _handle_tool_continue(ctx, ["/tool", "continue"], "/tool continue")
            return CommandResult.ok()
        print(f"Tool candidate '{candidate.get('tool')}' requires inspection. Opening editor...")
        mode = "edit"

    # -------------------------------------------------------------------------
    # Mode: 'fix' (Fast interactive CLI wizard in terminal)
    # -------------------------------------------------------------------------
    if mode == "fix":
        tool_name = candidate.get("tool", "")
        print("\n=== TOOL RETRY QUICK FIX WIZARD ===")
        print(f"Detected Tool: {tool_name}{'' if candidate.get('is_valid') else ' [INVALID]'}")

        if not candidate.get("is_valid"):
            try:
                new_name = input(f"Enter valid tool name (or [Enter] for '{tool_name}'): ").strip()
                if new_name:
                    tool_name = new_name
            except (EOFError, KeyboardInterrupt):
                print("\nAborted.")
                return CommandResult.ok()

        args = dict(candidate.get("arguments", {}))
        config = app._load_tools_config() if hasattr(app, "_load_tools_config") else {}
        meta = config.get("tools", {}).get(tool_name, {}) if config else {}
        declared_params = meta.get("parameters", {})

        # Prompt for parameters
        for p_name, p_rules in declared_params.items():
            curr_val = args.get(p_name)
            p_opt = "(optional)" if p_rules.get("optional") else "(required)"
            disp_curr = f" [current: {str(curr_val)[:40]}...]" if curr_val is not None else " [not set]"
            try:
                user_inp = input(f"Parameter '{p_name}' {p_opt}{disp_curr}: ").strip()
                if user_inp:
                    args[p_name] = user_inp
            except (EOFError, KeyboardInterrupt):
                print("\nAborted.")
                return CommandResult.ok()

        final_payload = {"tool": tool_name, "arguments": args}
        print(f"\nDispatching tool: {tool_name}...")
        res = await app.dispatch_tool(json.dumps(final_payload))
        _record_rescued_tool_execution(app, tool_name, args, res)
        if should_continue:
            await _handle_tool_continue(ctx, ["/tool", "continue"], "/tool continue")
        return CommandResult.ok()

    # -------------------------------------------------------------------------
    # Mode: 'edit' (Open scaffold in $EDITOR)
    # -------------------------------------------------------------------------
    buffer_content = _build_tool_retry_buffer(candidate, app, raw_text=raw_text)

    with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w", encoding="utf-8") as tf:
        tf.write(buffer_content)
        temp_path = tf.name

    try:
        config = app._load_tools_config() if hasattr(app, "_load_tools_config") else {}
        config_editor = config.get("config", {}).get("editor") if config else None
        default_editor = "notepad.exe" if os.name == "nt" else "vi"
        editor = config_editor or os.environ.get("VISUAL") or os.environ.get("EDITOR") or default_editor

        print(f"Opening tool rescue editor using '{editor}'...")
        if os.name == "nt":
            cmd = shlex.split(editor, posix=False) + [temp_path]
        else:
            cmd = shlex.split(editor) + [temp_path]
        subprocess.run(cmd)

        with open(temp_path, "r", encoding="utf-8") as f:
            saved_content = f.read()

        # Parse JSON ignoring comment lines
        non_comment_lines = [
            line for line in saved_content.splitlines()
            if not line.strip().startswith("#")
        ]
        cleaned_json_str = "\n".join(non_comment_lines).strip()

        if not cleaned_json_str or cleaned_json_str == "{}":
            print("Tool retry cancelled (empty buffer).")
            return CommandResult.ok()

        try:
            parsed = json.loads(cleaned_json_str)
        except json.JSONDecodeError as jde:
            print(f"Error parsing edited tool JSON: {jde}")
            print("Tip: Run '/tool retry edit' to reopen and correct the JSON syntax.")
            return CommandResult.ok()

        if not isinstance(parsed, dict) or "tool" not in parsed:
            print("Error: JSON must be an object with at least a 'tool' property.")
            return CommandResult.ok()

        chosen_tool = parsed.get("tool", "")
        known_tools = app.get_known_tool_names() if hasattr(app, "get_known_tool_names") else set()
        if chosen_tool not in known_tools and not chosen_tool.startswith("mcp__"):
            print(f"Error: '{chosen_tool}' is not a recognized enabled tool.")
            print("Available tools: " + ", ".join(sorted(known_tools)))
            print("Run '/tool retry edit' to select a valid tool name.")
            return CommandResult.ok()

        print(f"Dispatching rescued tool '{chosen_tool}'...")
        res = await app.dispatch_tool(cleaned_json_str)
        _record_rescued_tool_execution(app, chosen_tool, parsed.get("arguments", {}), res)
        if should_continue:
            await _handle_tool_continue(ctx, ["/tool", "continue"], "/tool continue")
    except Exception as exc:
        print(f"Error in tool retry editor: {exc}")
    finally:
        try:
            os.unlink(temp_path)
        except Exception:
            pass

    return CommandResult.ok()


async def _handle_tool_continue(ctx: CommandContext, parts: list, command: str) -> CommandResult:
    """Handle /tool continue [max_turns] or /continue to hand rescued tool results back to LLM."""
    app = ctx.app

    max_turns = getattr(app, "max_turns", 25)
    for p in parts[1:]:
        if p.isdigit():
            try:
                max_turns = int(p)
                break
            except ValueError:
                pass

    # Retrieve last rescued tool record or TOOL_DISPATCH_RESULT
    rescued_rec = app.buffer_manager.get_script_var('LAST_TOOL_RESCUED') if hasattr(app, "buffer_manager") else None
    result_str = (app.buffer_manager.get_script_var('TOOL_DISPATCH_RESULT') or "") if hasattr(app, "buffer_manager") else ""

    if not rescued_rec and not result_str:
        print("No pending rescued tool execution found. Run '/tool retry' first, or execute a new prompt.")
        return CommandResult.ok()

    tool_name = rescued_rec.get("tool", "unknown") if isinstance(rescued_rec, dict) else "rescued_tool"
    tool_args = rescued_rec.get("arguments", {}) if isinstance(rescued_rec, dict) else {}
    if isinstance(rescued_rec, dict) and "result" in rescued_rec:
        result_str = rescued_rec["result"]

    formatted_result = f"Tool: {tool_name}\nArguments: {json.dumps(tool_args, ensure_ascii=False)}\nResult: {result_str}"

    print(f"Continuing agentic loop with result from '{tool_name}'...")
    if hasattr(app, "run_tool_loop"):
        await app.run_tool_loop(max_turns=max_turns, initial_tool_results=formatted_result)
    else:
        print("Agentic loop runner not available.")
    return CommandResult.ok()


async def _handle_tool_inject(ctx: CommandContext, parts: list, command: str) -> CommandResult:
    """Handle /tool inject [file=<path> | <payload>] command to seed LAST_COMPLETION."""
    app = ctx.app
    if len(parts) < 3 and not command.strip().startswith("/tool inject "):
        print("Usage: /tool inject <payload text> | file=<filepath>")
        return CommandResult.ok()

    # Extract everything after '/tool inject'
    raw_arg = command.split(maxsplit=2)[2].strip() if len(parts) > 2 else ""
    if not raw_arg:
        print("Usage: /tool inject <payload text> | file=<filepath>")
        return CommandResult.ok()

    payload = ""
    source_desc = "literal text"

    # Check for file=<path> argument
    if raw_arg.lower().startswith("file="):
        file_target = raw_arg[5:].strip().strip("\"'")
        expanded = os.path.expanduser(file_target)
        if not os.path.exists(expanded):
            print(f"Error: Specified file not found: {file_target}")
            return CommandResult.ok()
        try:
            with open(expanded, "r", encoding="utf-8", errors="replace") as f:
                payload = f.read()
            source_desc = f"file '{file_target}'"
        except Exception as e:
            print(f"Error reading file '{file_target}': {e}")
            return CommandResult.ok()
    else:
        payload = raw_arg

    if not payload:
        print("Warning: Injected payload is empty.")

    # Store into LAST_COMPLETION buffer variable
    if hasattr(app, "buffer_manager") and app.buffer_manager:
        app.buffer_manager.set_script_var('LAST_COMPLETION', payload, allow_protected=True)

    # Synchronize chat_history
    if hasattr(app, "chat_history"):
        app.chat_history.append(("assistant", payload))

    lines_cnt = len(payload.splitlines())
    chars_cnt = len(payload)
    preview = payload.strip().splitlines()[0][:60] if payload.strip() else "(empty)"
    if len(preview) == 60:
        preview += "..."

    print(f"Successfully injected mock completion from {source_desc} ({chars_cnt} chars, {lines_cnt} lines).")
    print(f"Preview: {preview}")
    print("Tip: Run '/tool retry edit', '/tool retry fix', or '/tool retry run' to test rescue.")
    return CommandResult.ok()


