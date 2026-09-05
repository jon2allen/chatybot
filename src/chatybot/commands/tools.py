"""Shell execution and tool management commands.

Migrated from chatybot_app.handle_escape_command elif chain:
  /run, /run_safe, /run_unsafe, /tool
"""

import fnmatch
import json
import os
import shlex

from chatybot.commands.registry import command, CommandResult
from chatybot.commands.context import CommandContext


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
        processed_cmd, _ = app.buffer_manager.replace_placeholders(stripped_command, include_images=False)
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


@command("/tool", help="Manage tools and tool mode", args="[list|enable|disable|on|off|auto|scratch|loop|max_turns|rate_limit|prompt|history|translate] ...", category="tools")
async def cmd_tool(ctx: CommandContext, parts: list, command: str) -> CommandResult:
    app = ctx.app
    # Handle /tool subcommands: on, off, or dispatch
    if len(parts) < 2:
        # No subcommand - dispatch tool invocation from LAST_COMPLETION
        await app.dispatch_tool()
        return CommandResult.ok()

    subcmd = parts[1].lower()

    if subcmd == "list":
        # Parse detail mode and glob pattern
        detail_mode = False
        glob_pattern = "*"
        if len(parts) > 2:
            sub_parts = parts[2].strip().split()
            if "detail" in [p.lower() for p in sub_parts]:
                detail_mode = True
                remaining_parts = [p for p in sub_parts if p.lower() != "detail"]
                if remaining_parts:
                    glob_pattern = remaining_parts[0]
            else:
                glob_pattern = sub_parts[0]

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
        print("")
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
            import tempfile
            import subprocess

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
        # /tool history                  — list all agentic loops recorded in the active session
        # /tool history <turn_id>         — show detailed tool calls for a specific session turn
        # /tool history current [--verbose] — show the most recent in-memory AGENTIC_LOOP trace
        tokens = parts[2].strip().split() if len(parts) > 2 else []
        verbose = any(t.lower() in ("--verbose", "-v", "verbose") for t in tokens)
        remaining_tokens = [t for t in tokens if t.lower() not in ("--verbose", "-v", "verbose")]
        detail_arg = remaining_tokens[0].strip().lower() if remaining_tokens else ""

        if detail_arg in ("current", "last"):
            app.show_agentic_loop_trace(verbose=verbose)
            return CommandResult.ok()

        if detail_arg == "":
            # Summarize every turn in the active session that has an agentic_loop
            if not app.session_turns:
                print("No active session or no turns recorded.")
                return CommandResult.ok()

            loops = []
            for turn in app.session_turns:
                al = turn.get("agentic_loop")
                if isinstance(al, list) and al:
                    loops.append(turn)

            if not loops:
                print("No agentic tool loops found in the active session.")
                print("Tip: Run '/tool loop' or enable '/tool auto on' to execute agentic loops, then use '/tool history' to review them.")
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

            print("-" * 60)
            print(f"Total: {len(loops)} loop(s), {total_calls} tool calls ({total_success} success, {total_failed} failed)")
            print("Use '/tool history <turn_id>' for per-call details, '/tool history current' for the latest in-memory loop.")
            print("=" * 60)
            return CommandResult.ok()

        # Specific turn_id requested — show detailed tool calls
        try:
            target_id = int(detail_arg)
        except ValueError:
            print(f"Invalid argument '{detail_arg}'. Usage: /tool history [<turn_id>|current] [--verbose]")
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
        if not isinstance(al, list) or not al:
            print(f"Turn {target_id} has no recorded agentic loop data.")
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
        print("-" * 60)

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

        print("=" * 60)
        return CommandResult.ok()

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
