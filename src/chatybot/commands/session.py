"""Session management commands.

Migrated from chatybot_app.handle_escape_command elif chain:
  /session (with all subcommands: start, auto, stop, status, history, note,
  save, list, use, show, export, info, delete, merge, compress, uncompress, prune)
"""

from datetime import datetime

from chatybot.commands.registry import command, CommandResult
from chatybot.commands.context import CommandContext


@command("/session", help="Manage sessions", args="<start|auto|stop|status|history|note|save|list|use|show|export|info|delete|merge|compress|prune> ...", category="session")
async def cmd_session(ctx: CommandContext, parts: list, command: str) -> CommandResult:
    app = ctx.app
    if len(parts) < 2:
        print(f"Active Session ID: {app.active_session_id or 'None'}")
        print(f"Custom Name: {app.active_session_name or 'None'}")
        print(f"Session Mode: {app.session_mode}")
        print(f"Chat History: {'ON' if app.enable_chat_history else 'OFF'}")
        print(f"Turn Count: {len(app.session_turns)}")
        print(f"Session Directory: {app.get_sessions_dir()}")
        return CommandResult.ok()

    subcmd = parts[1].lower()

    if subcmd == "start":
        if len(parts) < 3:
            print("Usage: /session start <name>")
            return CommandResult.ok()
        session_name = " ".join(parts[2:]).strip(" \"'")
        app._release_session_lock()
        app.chat_history.clear()
        app.session_turns.clear()
        now = datetime.now()
        model_alias = getattr(app.config_manager, "active_model_alias", None) or "default"
        app.session_model_alias = model_alias
        app.active_session_id = app._generate_session_id(model_alias)
        app.active_session_name = session_name
        app.session_created_at = now.isoformat()
        app.session_first_prompt_slug = None
        app.session_notes = None
        app.session_mode = "on" if app.session_mode == "off" else app.session_mode
        app._acquire_session_lock(app.active_session_id)
        app.save_active_session()
        app.buffer_manager.set_script_var('SESSION_NAME', session_name, allow_protected=True)
        print(f"Started new session '{session_name}' (ID: {app.active_session_id})")
        return CommandResult.ok()

    elif subcmd == "auto":
        if len(parts) < 3:
            print(f"Auto Session Mode is currently: {'ON' if app.session_mode in ('on', 'auto') else 'OFF'}")
            return CommandResult.ok()
        action = parts[2].lower()
        if action in ("on", "1", "true"):
            app.session_mode = "auto"
            print("Auto session mode enabled.")
        elif action in ("off", "0", "false"):
            app.session_mode = "off"
            print("Auto session mode disabled.")
        else:
            print("Invalid action. Use 'on' or 'off'.")
        return CommandResult.ok()

    elif subcmd in ("stop", "off"):
        app._release_session_lock()
        app.session_mode = "off"
        print("Session recording paused.")
        return CommandResult.ok()

    elif subcmd == "status":
        print(f"Active Session ID: {app.active_session_id or 'None'}")
        print(f"Custom Name: {app.active_session_name or 'None'}")
        print(f"Session Mode: {app.session_mode}")
        print(f"Chat History: {'ON' if app.enable_chat_history else 'OFF'}")
        print(f"Turn Count: {len(app.session_turns)}")
        print(f"Session Directory: {app.get_sessions_dir()}")
        if app.session_notes:
            print(f"Notes: {app.session_notes}")
        return CommandResult.ok()

    elif subcmd == "history":
        if len(parts) < 3:
            print(f"Chat History Collection is currently: {'ON' if app.enable_chat_history else 'OFF'}")
            return CommandResult.ok()
        action = parts[2].lower()
        if action in ("on", "1", "true"):
            app.enable_chat_history = True
            print("Chat history collection enabled.")
        elif action in ("off", "0", "false"):
            app.enable_chat_history = False
            print("Chat history collection disabled. Note: Agentic tool loops are also disabled in this mode.")
        else:
            print("Invalid action. Use 'on' or 'off'.")
        return CommandResult.ok()

    elif subcmd == "note":
        if len(parts) < 3:
            if app.session_notes:
                print(f"Active Session Notes:\n{app.session_notes}")
            else:
                print("No notes set for active session. Usage: /session note <text>")
            return CommandResult.ok()
        raw_note = command.split(maxsplit=2)[2] if len(command.split(maxsplit=2)) > 2 else ""
        note_text = raw_note.strip(" \"'")
        if len(note_text) > 1024:
            print(f"Warning: Note exceeds 1024 characters ({len(note_text)} chars). Truncating...")
            note_text = note_text[:1024]
        app._ensure_active_session()
        app.session_notes = note_text
        app.save_active_session()
        print(f"Session notes updated ({len(note_text)} chars).")
        return CommandResult.ok()

    elif subcmd == "save":
        if len(parts) >= 3:
            custom_name = " ".join(parts[2:]).strip(" \"'")
            app.active_session_name = custom_name
        app._ensure_active_session()
        app.save_active_session()
        print(f"Session '{app.active_session_name or app.active_session_id}' saved to disk.")
        return CommandResult.ok()

    elif subcmd == "list":
        limit = 10
        offset = 0
        model_filter = None
        compressed_filter = None

        args = parts[2].split() if len(parts) >= 3 else []
        for arg in args:
            param = arg.lower()
            if param == "all":
                limit = None
            elif param in ("compressed", "status=compressed"):
                compressed_filter = True
            elif param in ("uncompressed", "status=uncompressed"):
                compressed_filter = False
            elif param.startswith("limit="):
                try:
                    limit = int(param[6:])
                except ValueError:
                    print("Invalid limit value. Using default limit of 10.")
            elif param.startswith("range="):
                try:
                    range_raw = param[6:]
                    if ":" in range_raw:
                        r_start, r_end = range_raw.split(":", 1)
                        offset = int(r_start) if r_start != "" else 0
                        limit = (int(r_end) - offset) if r_end != "" else None
                    else:
                        offset = int(range_raw)
                except ValueError:
                    print("Invalid range format. Use range=start:end, range=:end, or range=start:. Using default limit of 10.")
            elif param.startswith("model="):
                model_filter = param[6:].lower()

        store = app._get_session_store()
        parsed_sessions = store.list_sessions(
            offset=offset,
            limit=limit,
            model_filter=model_filter,
            compressed_filter=compressed_filter,
        )
        if not parsed_sessions:
            print("No saved sessions found.")
            return CommandResult.ok()

        print("\nAvailable Sessions:")
        for idx, s in enumerate(parsed_sessions, 1):
            name_str = f" (Name: '{s['cname']}')" if s["cname"] else ""
            gz_str = " [compressed]" if s.get("compressed") else ""
            print(f"  {idx}. {s['sid']}{name_str}{gz_str}")
            print(f"     ├─ Prompt: \"{s['slug']}\"")
            if s.get("snote"):
                short_note = s["snote"][:60] + "..." if len(s["snote"]) > 60 else s["snote"]
                print(f"     ├─ Notes: \"{short_note}\"")
            print(f"     └─ Turns: {s['turns_cnt']} exchanges (Updated: {s['upd']})")
        print("")
        return CommandResult.ok()

    elif subcmd == "use":
        if len(parts) < 3:
            print("Usage: /session use <session_id|custom_name>")
            return CommandResult.ok()
        target = " ".join(parts[2:]).strip(" \"'")
        store = app._get_session_store()

        try:
            sdata, turns = store.load_session(target)
        except Exception as e:
            print(f"Error: Session '{target}' not found.")
            return CommandResult.ok()

        matched_sid = store.resolve_session(target) or target
        app._release_session_lock()
        app.active_session_id = sdata.get("session_id") or matched_sid
        app.active_session_name = sdata.get("custom_name")
        app.session_model_alias = sdata.get("model_alias")
        app.session_created_at = sdata.get("created_at")
        app.session_first_prompt_slug = sdata.get("first_prompt_slug")
        app.session_notes = sdata.get("notes")
        app.session_turns = turns

        app.chat_history.clear()
        if app.enable_chat_history:
            for turn in app.session_turns:
                app.chat_history.append((turn.get("prompt", ""), turn.get("response", "")))

        app.session_mode = "on" if app.session_mode == "off" else app.session_mode
        app._acquire_session_lock(app.active_session_id)
        app.buffer_manager.set_script_var('SESSION_NAME', app.active_session_name or app.active_session_id, allow_protected=True)
        print(f"Loaded session '{app.active_session_name or app.active_session_id}' ({len(app.session_turns)} exchanges).")
        return CommandResult.ok()

    elif subcmd == "show":
        show_thinking = False
        if len(parts) >= 3 and parts[2].lower() in ("--thinking", "-t"):
            show_thinking = True

        if not app.session_turns:
            print("No exchanges in active session.")
            return CommandResult.ok()

        print("\n" + "=" * 80)
        name_str = f" (Name: {app.active_session_name})" if app.active_session_name else ""
        model_alias = app.session_model_alias or "default"
        print(f"SESSION: {app.active_session_id or 'Unsaved'}{name_str}")
        print(f"Model: {model_alias} | Created: {app.session_created_at or 'N/A'} | Total Turns: {len(app.session_turns)}")
        if app.session_notes:
            print(f"Notes: {app.session_notes}")
        print("=" * 80 + "\n")

        for turn in app.session_turns:
            t_id = turn.get("turn_id", 1)
            t_model = turn.get("model_alias")
            model_str = f" ({t_model})" if t_model else ""
            print(f"[Turn {t_id}]{model_str}")
            print(f"User: {turn.get('prompt')}")
            if show_thinking and "thinking" in turn:
                print("Thinking:")
                for t_line in turn["thinking"].splitlines():
                    print(f"  {t_line}")
            print(f"Assistant: {turn.get('response')}")
            if "agentic_loop" in turn:
                t_count = len(turn["agentic_loop"])
                print(f"(Tools executed: {t_count})")
            print("\n" + "-" * 80 + "\n")
        print("=" * 80 + "\n")
        return CommandResult.ok()

    elif subcmd == "export":
        if len(parts) < 3:
            print("Usage: /session export <filepath.md> [--thinking|-t]")
            return CommandResult.ok()

        show_thinking = False
        raw_args = command.split(maxsplit=2)[2] if len(command.split(maxsplit=2)) > 2 else ""
        words = raw_args.split()
        if words and words[-1].lower() in ("--thinking", "-t"):
            show_thinking = True
            words.pop()

        export_path = " ".join(words).strip(" \"'")
        if not app.session_turns:
            print("No exchanges in active session to export.")
            return CommandResult.ok()

        md_lines = []
        name_title = app.active_session_name or app.active_session_id or "Session Transcript"
        model_alias = app.session_model_alias or "default"
        md_lines.append(f"# Session Transcript: {name_title}\n")
        md_lines.append(f"- **Session ID**: `{app.active_session_id or 'N/A'}`")
        md_lines.append(f"- **Model**: `{model_alias}`")
        md_lines.append(f"- **Created**: {app.session_created_at or 'N/A'}")
        md_lines.append(f"- **Total Exchanges**: {len(app.session_turns)}")
        if app.session_notes:
            md_lines.append(f"- **Notes**: {app.session_notes}")
        md_lines.append("\n---\n")

        for turn in app.session_turns:
            t_id = turn.get("turn_id", 1)
            t_model = turn.get("model_alias")
            header = f"## Turn {t_id}"
            if t_model:
                header += f" ({t_model})"
            md_lines.append(f"{header}\n")
            md_lines.append("### User")
            md_lines.append(f"{turn.get('prompt')}\n")
            if show_thinking and "thinking" in turn:
                md_lines.append("### Reasoning Trace")
                for t_line in turn["thinking"].splitlines():
                    md_lines.append(f"> {t_line}")
                md_lines.append("")
            md_lines.append("### Assistant")
            md_lines.append(f"{turn.get('response')}\n")
            if "agentic_loop" in turn:
                md_lines.append("#### Tools Executed")
                for step in turn["agentic_loop"]:
                    if isinstance(step, dict):
                        tname = step.get("tool", "unknown_tool")
                        md_lines.append(f"- `{tname}`")
                    else:
                        md_lines.append(f"- `{step}`")
                md_lines.append("")
            md_lines.append("---\n")

        try:
            with open(export_path, "w", encoding="utf-8") as f:
                f.write("\n".join(md_lines))
            print(f"Exported session transcript to '{export_path}'.")
        except Exception as e:
            print(f"Error exporting session: {e}")
        return CommandResult.ok()

    elif subcmd in ("info", "stats"):
        metrics = app._get_session_store().get_workspace_metrics()
        total_cnt = metrics["total_count"]
        if total_cnt == 0:
            print("No saved sessions.")
            return CommandResult.ok()

        total_bytes = metrics["total_bytes"]
        kb = total_bytes / 1024.0
        mb = kb / 1024.0
        size_str = f"{mb:.2f} MB ({kb:.1f} KB)" if mb >= 1.0 else f"{kb:.2f} KB"

        oldest_name, oldest_mtime = metrics["oldest"]
        newest_name, newest_mtime = metrics["newest"]
        largest_name, largest_bytes = metrics["largest"]

        largest_kb = largest_bytes / 1024.0
        largest_mb = largest_kb / 1024.0
        largest_str = f"{largest_mb:.2f} MB" if largest_mb >= 1.0 else f"{largest_kb:.2f} KB"

        oldest_dt = datetime.fromtimestamp(oldest_mtime).strftime("%Y-%m-%d %H:%M:%S") if oldest_name else "N/A"
        newest_dt = datetime.fromtimestamp(newest_mtime).strftime("%Y-%m-%d %H:%M:%S") if newest_name else "N/A"

        print("\n" + "=" * 60)
        print("SESSION WORKSPACE METRICS")
        print("=" * 60)
        print(f"Total Sessions:   {total_cnt}")
        print(f"Space Consumed:   {size_str}")
        print(f"Oldest Session:   {oldest_name or 'N/A'} ({oldest_dt})")
        print(f"Newest Session:   {newest_name or 'N/A'} ({newest_dt})")
        print(f"Largest Session:  {largest_name or 'N/A'} ({largest_str})")
        print("=" * 60 + "\n")
        return CommandResult.ok()

    elif subcmd == "delete":
        if len(parts) < 3:
            print("Usage: /session delete <name|id|--all>")
            return CommandResult.ok()
        raw_target = parts[2].strip(" \"'")
        target_lower = raw_target.lower()

        store = app._get_session_store()
        if target_lower == "--all":
            try:
                confirm = input("Are you sure you want to delete ALL saved sessions? (y/N): ").strip().lower()
            except EOFError:
                print("Delete all cancelled (non-interactive input).")
                return CommandResult.ok()
            if confirm in ("y", "yes"):
                count = store.delete_all_sessions()
                app._release_session_lock()
                app.active_session_id = None
                app.active_session_name = None
                app.session_turns.clear()
                app.chat_history.clear()
                print(f"Deleted all {count} saved sessions.")
            else:
                print("Delete all cancelled.")
            return CommandResult.ok()

        matched_sid = store.resolve_session(raw_target)
        if not matched_sid:
            print(f"Error: Session '{raw_target}' not found.")
            return CommandResult.ok()

        deleted = store.delete_session(matched_sid)
        if deleted:
            if app.active_session_id and app.active_session_id == matched_sid:
                app._release_session_lock()
                app.active_session_id = None
                app.active_session_name = None
                app.session_turns.clear()
                app.chat_history.clear()
            print(f"Deleted session '{matched_sid}'.")
        else:
            print(f"Error deleting session '{raw_target}'.")
        return CommandResult.ok()

    elif subcmd == "merge":
        raw_merge_args = command.split(maxsplit=2)[2] if len(command.split(maxsplit=2)) > 2 else ""
        merge_words = raw_merge_args.split()
        if len(merge_words) < 3:
            print("Usage: /session merge <target_name> <session_a> <session_b> [session_c ...]")
            return CommandResult.ok()

        target_name = merge_words[0].strip(" \"'")
        source_targets = merge_words[1:]

        store = app._get_session_store()
        try:
            new_session_id = store.merge_sessions(target_name, source_targets)
            _, turns = store.load_session(new_session_id)
            print(f"Merged {len(source_targets)} sessions into '{target_name}' (ID: {new_session_id}) with {len(turns)} exchanges.")
        except Exception as e:
            print(f"Error: {e}")
        return CommandResult.ok()

    elif subcmd == "compress":
        older_than_days = None
        target = None

        args = parts[2].split() if len(parts) >= 3 else []
        store = app._get_session_store()
        for arg in args:
            arg_l = arg.lower()
            if arg_l == "all":
                target = "all"
            elif arg_l.startswith("days="):
                try:
                    older_than_days = float(arg_l.split("=", 1)[1])
                except ValueError:
                    pass
            elif arg_l.startswith("target="):
                target = arg[7:]
            else:
                is_number = False
                try:
                    val = float(arg)
                    is_number = True
                except ValueError:
                    is_number = False

                if is_number and not store.resolve_session(arg):
                    older_than_days = val
                else:
                    target = arg

        count, saved_bytes = store.compress_sessions(
            older_than_days=older_than_days,
            target=target,
            active_session_id=app.active_session_id,
        )
        saved_kb = saved_bytes / 1024.0
        print(f"Compressed {count} session file(s). Saved {saved_kb:.1f} KB of disk space.")
        return CommandResult.ok()

    elif subcmd in ("uncompress", "decompress"):
        target = parts[2] if len(parts) >= 3 else "all"
        store = app._get_session_store()
        count = store.uncompress_sessions(target)
        if count > 0:
            print(f"Uncompressed {count} session file(s).")
        else:
            if target.lower() == "all":
                print("No compressed sessions found to uncompress.")
            else:
                print(f"Session '{target}' was not compressed or not found.")
        return CommandResult.ok()

    elif subcmd == "prune":
        keep_n = None
        max_days = None
        max_size_mb = None

        raw_prune_args = parts[2].split() if len(parts) >= 3 else []
        for arg in raw_prune_args:
            arg_l = arg.lower()
            if arg_l.startswith("keep="):
                try:
                    keep_n = int(arg_l.split("=", 1)[1])
                except ValueError:
                    pass
            elif arg_l.startswith("days="):
                try:
                    max_days = float(arg_l.split("=", 1)[1])
                except ValueError:
                    pass
            elif arg_l.startswith("size="):
                try:
                    max_size_mb = float(arg_l.split("=", 1)[1])
                except ValueError:
                    pass

        if keep_n is None and max_days is None and max_size_mb is None:
            print("Usage: /session prune [keep=N] [days=D] [size=M]")
            print("Example: /session prune keep=10 days=30 size=50")
            return CommandResult.ok()

        if keep_n == 0:
            try:
                confirm = input("Warning: keep=0 will prune ALL non-active sessions. Confirm? (y/N): ").strip().lower()
            except EOFError:
                print("Prune cancelled (non-interactive input).")
                return CommandResult.ok()
            if confirm not in ("y", "yes"):
                print("Prune cancelled.")
                return CommandResult.ok()

        store = app._get_session_store()
        deleted_count = store.prune_sessions(
            keep_n=keep_n,
            max_days=max_days,
            max_size_mb=max_size_mb,
            active_session_id=app.active_session_id,
        )
        print(f"Pruned {deleted_count} session file(s).")
        return CommandResult.ok()

    else:
        print(f"Unknown session subcommand: {subcmd}. Use start, auto, stop, status, save, list, use, show, export, info, delete, merge, compress, prune.")
        return CommandResult.ok()
