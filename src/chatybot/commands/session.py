"""Session management commands.

Migrated from chatybot_app.handle_escape_command elif chain:
  /session (with all subcommands: start, auto, stop, status, history, note,
  save, list, use, show, export, info, delete, merge, compress, uncompress, prune)
"""

import re
from datetime import datetime

from chatybot.commands.context import CommandContext
from chatybot.commands.registry import CommandResult, command
from chatybot.commands.replay import handle_replay_command

MAX_SESSION_NAME_LEN: int = 128


def _sanitize_session_name(name: str) -> str:
    cleaned = re.sub(r"[\r\n\t]+", " ", name.strip(" \"'\r\n\t")).strip()
    if len(cleaned) > MAX_SESSION_NAME_LEN:
        print(f"Warning: Session name exceeds {MAX_SESSION_NAME_LEN} characters ({len(cleaned)} chars). Truncating...")
        cleaned = cleaned[:MAX_SESSION_NAME_LEN].rstrip()
    return cleaned


def _format_size_bytes(bytes_cnt: int) -> str:
    if not bytes_cnt:
        return "0 B"
    if bytes_cnt < 1024:
        return f"{bytes_cnt} B"
    elif bytes_cnt < 1024 * 1024:
        return f"{bytes_cnt / 1024:.1f} KB"
    else:
        return f"{bytes_cnt / (1024 * 1024):.1f} MB"


@command("/session", help="Manage sessions", args="<start|new|auto|stop|status|history|note|save|list|use|show|export|info|delete|merge|compress|prune|replay|query|get> ...", category="session")
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

    if subcmd in ("start", "new"):
        if len(parts) < 3:
            print("Usage: /session start|new <name>")
            return CommandResult.ok()
        session_name = _sanitize_session_name(" ".join(parts[2:]))
        app._release_session_lock()
        app.chat_history.clear()
        app.session_turns.clear()
        app.session_activity.clear()
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
        store = app._get_session_store()
        try:
            store.create_session(
                session_id=app.active_session_id,
                model_alias=model_alias,
                custom_name=session_name,
                initial_prompt="",
                notes=None
            )
        except OSError as e:
            print(f"Warning: Failed to create session on disk ({e}). Falling back to in-memory session.")
            app.session_mode = "off"
            app.active_session_id = None
            return CommandResult.ok()
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

    elif subcmd in ("save", "name"):
        if len(parts) >= 3:
            custom_name = _sanitize_session_name(" ".join(parts[2:]))
            app.active_session_name = custom_name
            app.buffer_manager.set_script_var('SESSION_NAME', custom_name, allow_protected=True)
        app._ensure_active_session()
        app.save_active_session()
        print(f"Session '{app.active_session_name or app.active_session_id}' saved to disk.")
        return CommandResult.ok()

    elif subcmd == "list":
        limit = 10
        offset = 0
        model_filter = None
        compressed_filter = None
        target_var = None
        since_dt = None
        ids_only = False

        args = parts[2].split() if len(parts) >= 3 else []
        for arg in args:
            param = arg.lower()
            if param == "all":
                limit = None
            elif param == "ids":
                ids_only = True
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
            elif param.startswith("var="):
                target_var = arg[4:].strip().lstrip("$")
            elif param.startswith("target="):
                target_var = arg[7:].strip().lstrip("$")
            elif param.startswith("since="):
                raw = param[6:]
                try:
                    if raw.endswith("d"):
                        from datetime import timedelta
                        delta = timedelta(days=float(raw[:-1]))
                    elif raw.endswith("h"):
                        from datetime import timedelta
                        delta = timedelta(hours=float(raw[:-1]))
                    elif raw.endswith("m"):
                        from datetime import timedelta
                        delta = timedelta(minutes=float(raw[:-1]))
                    else:
                        print(f"Invalid since= unit '{raw}'. Use d (days), h (hours), or m (minutes). E.g. since=7d")
                        delta = None
                    if delta is not None:
                        since_dt = datetime.now() - delta
                except ValueError:
                    print(f"Invalid since= value '{raw}'. Use numeric values like since=7d, since=24h, since=30m")

        store = app._get_session_store()
        parsed_sessions = store.list_sessions(
            offset=offset,
            limit=limit,
            model_filter=model_filter,
            compressed_filter=compressed_filter,
            since_dt=since_dt,
        )

        # Always extract the sid list and populate both protected vars
        session_ids = [s["sid"] for s in parsed_sessions]
        if hasattr(app, "buffer_manager") and app.buffer_manager:
            app.buffer_manager.set_script_var('SESSION_LIST', parsed_sessions, allow_protected=True)
            app.buffer_manager.set_script_var('SESSION_IDS', session_ids, allow_protected=True)
            if target_var:
                # var= targets the sid list when ids_only, full dicts otherwise
                value_for_var = session_ids if ids_only else parsed_sessions
                app.buffer_manager.set_script_var(target_var, value_for_var, allow_protected=True)

        if not parsed_sessions:
            print("No saved sessions found.")
            return CommandResult.ok()

        # Build a compact filter summary for the header
        filter_parts = []
        if model_filter:
            filter_parts.append(f"model={model_filter}")
        if since_dt:
            filter_parts.append(f"since={since_dt.strftime('%Y-%m-%d %H:%M')}")
        if compressed_filter is True:
            filter_parts.append("compressed")
        elif compressed_filter is False:
            filter_parts.append("uncompressed")
        if ids_only:
            filter_parts.append("ids")
        filter_str = f"  [{', '.join(filter_parts)}]" if filter_parts else ""

        if ids_only:
            print(f"\nSession IDs:{filter_str}")
            for sid in session_ids:
                print(f"  {sid}")
            print()
        else:
            print(f"\nAvailable Sessions:{filter_str}")
            for idx, s in enumerate(parsed_sessions, 1):
                name_str = f" (Name: '{s['cname']}')" if s["cname"] else ""
                gz_str = " [compressed]" if s.get("compressed") else ""
                print(f"  {idx}. {s['sid']}{name_str}{gz_str}")
                print(f"     ├─ Prompt: \"{s['slug']}\"")
                if s.get("snote"):
                    short_note = s["snote"][:60] + "..." if len(s["snote"]) > 60 else s["snote"]
                    print(f"     ├─ Notes: \"{short_note}\"")
                print(f"     └─ Turns: {s['turns_cnt']} exchanges (Updated: {s['upd']})")
            print()
        return CommandResult.ok()


    elif subcmd == "use":
        if len(parts) < 3:
            print("Usage: /session use <session_id|custom_name>")
            return CommandResult.ok()
        target = " ".join(parts[2:]).strip(" \"'")
        store = app._get_session_store()

        try:
            sdata, turns = store.load_session(target)
        except Exception:
            print(f"Error: Session '{target}' not found.")
            return CommandResult.ok()

        matched_sid = store.resolve_session(target) or target
        app._release_session_lock()
        app.active_session_id = sdata.get("session_id") or matched_sid
        app.active_session_name = sdata.get("custom_name")
        app.session_model_alias = sdata.get("model_alias")
        app.session_created_at = sdata.get("created_at")
        app.session_first_prompt_slug = sdata.get("first_prompt_slug")
        # Separate LLM turns from command action verb events
        llm_turns = [t for t in turns if t.get("type") != "command" and "prompt" in t]
        app.session_turns = llm_turns
        app.session_activity = []

        # Populate chronological session_activity from turns file
        for item in turns:
            if item.get("type") == "command":
                app.session_activity.append({
                    "type": "command",
                    "text": item.get("text", ""),
                    "verb": item.get("verb", ""),
                    "timestamp": item.get("timestamp")
                })
            elif "prompt" in item:
                app.session_activity.append({
                    "type": "prompt",
                    "text": item.get("prompt", ""),
                    "model": item.get("model_alias", app.session_model_alias or "default"),
                    "timestamp": item.get("timestamp")
                })

        app.chat_history.clear()
        if app.enable_chat_history:
            for turn in app.session_turns:
                app.chat_history.append((turn.get("prompt", ""), turn.get("response", "")))

        app.session_mode = "on" if app.session_mode == "off" else app.session_mode
        app._acquire_session_lock(app.active_session_id)
        app.buffer_manager.set_script_var('SESSION_NAME', app.active_session_name or app.active_session_id, allow_protected=True)
        print(f"Loaded session '{app.active_session_name or app.active_session_id}' ({len(app.session_turns)} exchanges, {len(app.session_activity)} total actions).")
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
            t_type = turn.get("type")

            if t_type == "decision":
                q_type = turn.get("question_type", "choice").upper()
                print(f"[Turn {t_id}] [DECISION:{q_type}]{model_str}")
                print(f"Question: {turn.get('instructions')}")
                print(f"State: {turn.get('state')}")
                conf = turn.get("confidence")
                conf_str = f" (confidence: {conf:.2f})" if isinstance(conf, (int, float)) else ""
                print(f"Decision: {turn.get('response')}{conf_str}")
                probs = turn.get("probabilities")
                if probs and isinstance(probs, dict):
                    prob_summary = ", ".join(f"{k}: {float(v):.2f}" for k, v in probs.items())
                    print(f"Probabilities: {prob_summary}")
            else:
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

        is_csv = False
        if words and words[0].lower() == "csv":
            is_csv = True
            words = words[1:]

        export_path = " ".join(words).strip(" \"'")
        if not export_path and is_csv:
            # Generate default csv filename if omitted, sanitizing for OS filename limits
            s_name = app.active_session_name or app.active_session_id or "session"
            clean_name = re.sub(r"[^\w\-]", "_", s_name.strip())[:64].strip("_")
            export_path = f"{clean_name or 'session'}.csv"
        elif not export_path:
            print("Usage: /session export [csv] <filepath> [--thinking|-t]")
            return CommandResult.ok()

        if export_path.lower().endswith(".csv"):
            is_csv = True

        if not app.session_turns:
            print("No exchanges in active session to export.")
            return CommandResult.ok()

        if is_csv:
            import csv
            try:
                with open(export_path, "w", newline="", encoding="utf-8") as f:
                    writer = csv.writer(f, quoting=csv.QUOTE_ALL)
                    writer.writerow([
                        "turn_id", "timestamp", "model_alias", "prompt", "response",
                        "thinking", "elapsed_ms", "tps_total", "tps_think", "tps_regular",
                        "tool_call_count", "has_agentic_loop"
                    ])
                    for turn in app.session_turns:
                        t_id = turn.get("turn_id", 1)
                        ts = turn.get("timestamp", "")
                        model = turn.get("model_alias", app.session_model_alias or "default")
                        prompt = turn.get("prompt", "")
                        resp = turn.get("response", "")
                        thinking = turn.get("thinking", "") if show_thinking else ""
                        elapsed = turn.get("elapsed_ms", "")
                        tps_dict = turn.get("tps") if isinstance(turn.get("tps"), dict) else {}
                        tps_tot = tps_dict.get("total", "")
                        tps_thk = tps_dict.get("think", "")
                        tps_reg = tps_dict.get("regular", "")
                        al = turn.get("agentic_loop")
                        tool_count = len(al) if isinstance(al, list) else 0
                        has_loop = bool(isinstance(al, list) and al)
                        writer.writerow([
                            t_id, ts, model, prompt, resp,
                            thinking, elapsed, tps_tot, tps_thk, tps_reg,
                            tool_count, has_loop
                        ])
                print(f"Exported session data to CSV '{export_path}'.")
            except Exception as e:
                print(f"Error exporting session to CSV: {e}")
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
            t_type = turn.get("type")
            if t_type == "decision":
                q_type = turn.get("question_type", "choice").upper()
                header = f"## Turn {t_id} [Decision: {q_type}]"
                if t_model:
                    header += f" ({t_model})"
                md_lines.append(f"{header}\n")
                md_lines.append(f"- **Question**: {turn.get('instructions')}")
                md_lines.append(f"- **State**: {turn.get('state')}")
                conf = turn.get("confidence")
                conf_str = f" (confidence: {conf:.2f})" if isinstance(conf, (int, float)) else ""
                md_lines.append(f"- **Decision**: `{turn.get('response')}`{conf_str}")
                probs = turn.get("probabilities")
                if probs and isinstance(probs, dict):
                    prob_summary = ", ".join(f"`{k}`: {float(v):.2f}" for k, v in probs.items())
                    md_lines.append(f"- **Probabilities**: {prob_summary}")
                md_lines.append("\n---\n")
            else:
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

        lines = [
            f"Total Sessions:   {total_cnt}",
            f"Space Consumed:   {size_str}",
            f"Oldest Session:   {oldest_name or 'N/A'} ({oldest_dt})",
            f"Newest Session:   {newest_name or 'N/A'} ({newest_dt})",
            f"Largest Session:  {largest_name or 'N/A'} ({largest_str})",
        ]
        width = max(80, max(len(l) for l in lines))
        sep = "=" * width

        print("\n" + sep)
        print("SESSION WORKSPACE METRICS")
        print(sep)
        for l in lines:
            print(l)
        print(sep + "\n")
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

        target_name = _sanitize_session_name(merge_words[0])
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

    elif subcmd == "replay":
        raw_tokens = parts[2].strip().split() if len(parts) > 2 else []
        return await handle_replay_command(ctx, raw_tokens)

    elif subcmd == "query":
        import shlex

        from chatybot.query.base import QueryRequest, get_query_engine
        from chatybot.query.date_parser import parse_date_range, parse_datetime_expr

        raw_str = parts[2].strip() if len(parts) > 2 else ""
        if not raw_str:
            print("Usage: /session query <terms...> [or|and] [ids] [full] [since=<date>] [until=<date>] [range=<date to date>] [--scratch|--no-scratch] [limit=<N>] [var=<varname>]")
            return CommandResult.ok()

        try:
            raw_args = shlex.split(raw_str)
        except ValueError:
            raw_args = raw_str.split()

        terms = []
        operator = "AND"
        since_dt = None
        until_dt = None
        include_scratch = True
        ids_only = False
        full_mode = False
        limit = 20
        target_var = None
        engine_name = None
        sess_filter = None

        i = 0
        while i < len(raw_args):
            arg = raw_args[i]
            arg_lower = arg.lower()

            if arg_lower in ("or", "--or"):
                operator = "OR"
            elif arg_lower in ("and", "--and"):
                operator = "AND"
            elif arg_lower in ("ids", "--ids", "ids_only", "--ids_only"):
                ids_only = True
            elif arg_lower in ("full", "--full", "-f"):
                full_mode = True
            elif arg_lower in ("--scratch", "scratch"):
                include_scratch = True
            elif arg_lower in ("--no-scratch", "no-scratch"):
                include_scratch = False
            elif arg_lower.startswith("session=") or arg_lower.startswith("session_id=") or arg_lower.startswith("sid="):
                sess_filter = arg.split("=", 1)[1].strip("\"'")
            elif arg_lower.startswith("since="):
                since_val = arg.split("=", 1)[1].strip("\"'")
                since_dt = parse_datetime_expr(since_val)
            elif arg_lower.startswith("until="):
                until_val = arg.split("=", 1)[1].strip("\"'")
                until_dt = parse_datetime_expr(until_val)
            elif arg_lower.startswith("range="):
                range_val = arg.split("=", 1)[1].strip("\"'")
                r_start, r_end = parse_date_range(range_val)
                if r_start:
                    since_dt = r_start
                if r_end:
                    until_dt = r_end
            elif arg_lower.startswith("limit="):
                try:
                    limit = int(arg.split("=", 1)[1])
                except ValueError:
                    pass
            elif arg_lower.startswith("var="):
                target_var = arg.split("=", 1)[1].strip()
            elif arg_lower.startswith("engine="):
                engine_name = arg.split("=", 1)[1].strip()
            elif arg_lower.startswith("terms=") or arg_lower.startswith("text=") or arg_lower.startswith("query="):
                val = arg.split("=", 1)[1].strip("\"'")
                if val:
                    terms.extend(val.split())
            else:
                clean_term = arg.strip("\"'")
                if clean_term and clean_term != "*":
                    terms.append(clean_term)
            i += 1

        if not terms and not (since_dt or until_dt or ids_only or sess_filter):
            print("Error: No search terms specified. Usage: /session query <terms...>")
            return CommandResult.ok()

        req = QueryRequest(
            terms=terms,
            operator=operator,
            since_dt=since_dt,
            until_dt=until_dt,
            include_scratch=include_scratch,
            limit=limit,
            session_id=sess_filter,
            ids_only=ids_only,
            full=full_mode,
        )

        try:
            engine = get_query_engine(engine_name)
            response = engine.search(app, req)
            res_dict = response.to_dict()
        except Exception as e:
            print(f"Query error: {e}")
            return CommandResult.ok()

        if hasattr(app, "buffer_manager") and app.buffer_manager:
            app.buffer_manager.set_script_var("SESSION_QUERY", res_dict, allow_protected=True)
            if target_var:
                val_to_save = response.session_ids if ids_only else res_dict
                app.buffer_manager.set_script_var(target_var, val_to_save, allow_protected=True)

        # Format output
        filter_parts = [f"operator={operator}"]
        if ids_only:
            filter_parts.append("ids")
        if full_mode:
            filter_parts.append("full")
        if since_dt:
            filter_parts.append(f"since={since_dt.strftime('%Y-%m-%d %H:%M')}")
        if until_dt:
            filter_parts.append(f"until={until_dt.strftime('%Y-%m-%d %H:%M')}")
        if sess_filter:
            filter_parts.append(f"session={sess_filter}")
        if include_scratch and not ids_only:
            filter_parts.append("scratch=ON")
        if engine_name:
            filter_parts.append(f"engine={engine_name}")

        filter_str = f" [{', '.join(filter_parts)}]"
        query_desc = f"'{' '.join(terms)}'" if terms else "all sessions"

        if ids_only:
            print(f"\nMatching Sessions for {query_desc}{filter_str}: {len(response.session_ids)} session(s)\n")
            if not response.session_ids:
                print("  No matching sessions found.\n")
                return CommandResult.ok()
            sess_map = {s.get("session_id"): s.get("size_bytes") for s in getattr(response, "sessions", [])}
            for sid in response.session_ids:
                sz = sess_map.get(sid)
                sz_str = f" | {_format_size_bytes(sz)}" if sz else ""
                print(f"  {sid}{sz_str}")
            print()
            return CommandResult.ok()

        print(f"\nQuery Results for {query_desc}{filter_str}: {response.total_matches} match(es)\n")
        if not response.matches:
            print("  No matches found.\n")
            return CommandResult.ok()

        for idx, match in enumerate(response.matches, 1):
            if match.source == "session":
                loc = f"Session: {match.session_id}"
                if match.turn_id:
                    loc += f" | Turn: {match.turn_id}"
                if match.timestamp:
                    loc += f" | {match.timestamp}"
            else:
                loc = f"Scratchpad: {match.metadata.get('file', 'scratch')}"
                if match.turn_id:
                    loc += f" | Line: {match.turn_id}"

            if getattr(match, "size_bytes", None):
                loc += f" | {_format_size_bytes(match.size_bytes)}"

            print(f"  {idx}. [{loc}] ({match.role})")
            if full_mode:
                for line in (match.full_text or match.snippet).splitlines():
                    print(f"     {line}")
                print()
            else:
                print(f"     \"{match.snippet}\"")
        print()
        return CommandResult.ok()

    elif subcmd == "get":
        import shlex

        from chatybot.tools.context_query import session_get

        raw_str = parts[2].strip() if len(parts) > 2 else ""
        if not raw_str:
            print("Usage: /session get <session_id|name|active> [turn=<N>|all] [prompt|response|both|thinking] [var=<varname>]")
            return CommandResult.ok()

        try:
            raw_args = shlex.split(raw_str)
        except ValueError:
            raw_args = raw_str.split()

        target = raw_args[0].strip("\"'")
        turn_id = None
        part_name = "both"
        target_var = None

        for arg in raw_args[1:]:
            arg_lower = arg.lower()
            if arg_lower.startswith("turn="):
                val = arg.split("=", 1)[1].strip()
                if val.lower() != "all":
                    try:
                        turn_id = int(val)
                    except ValueError:
                        print(f"Invalid turn number: '{val}'")
                        return CommandResult.ok()
            elif arg_lower == "all":
                turn_id = None
            elif arg_lower in ("prompt", "response", "both", "thinking"):
                part_name = arg_lower
            elif arg_lower.startswith("var="):
                target_var = arg.split("=", 1)[1].strip()
            elif arg.isdigit():
                turn_id = int(arg)

        res = session_get(
            session_id=target,
            turn_id=turn_id,
            part=part_name,
            target_variable=target_var,
            app=app,
        )

        if res.get("status") != "success":
            print(f"Error: {res.get('message', 'Failed to retrieve session content')}")
            return CommandResult.ok()

        sid_display = res.get("session_id", target)
        cname = res.get("custom_name")
        cname_str = f" ('{cname}')" if cname else ""
        turn_str = f"Turn {turn_id}" if turn_id is not None else f"All Turns ({res.get('total_turns', 0)} total)"
        var_str = f" (Saved to '${target_var}')" if target_var else ""

        size_str = f" | {_format_size_bytes(res.get('size_bytes', 0))}" if res.get("size_bytes") else ""
        print(f"\n--- Extracted from {sid_display}{cname_str} [{turn_str} | {part_name}{size_str}]{var_str} ---")
        print(res.get("text", ""))
        print("--- End of extraction ---\n")
        return CommandResult.ok()

    else:
        print(f"Unknown session subcommand: {subcmd}. Use start, new, auto, stop, status, save, list, use, show, export, info, delete, merge, compress, prune, replay, query, get.")
        return CommandResult.ok()

