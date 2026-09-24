"""Skills management commands.

Registers the /skill command with subcommands:
  list, show, create, edit, delete, enable, disable, search,
  learn, apply, export, import, restore
"""

import os
import shlex
import subprocess
import tempfile

from chatybot.commands.context import CommandContext
from chatybot.commands.registry import CommandResult, command
from chatybot import skillsdb


@command(
    "/skill",
    help="Manage the skills database",
    args="<list|show|create|edit|delete|enable|disable|search|learn|apply|export|import|restore> ...",
    category="skills",
)
async def cmd_skill(ctx: CommandContext, parts: list, command: str) -> CommandResult:
    app = ctx.app
    if len(parts) < 2:
        _print_usage()
        return CommandResult.ok()

    subcmd = parts[1].lower()

    if subcmd == "list":
        return _handle_list(ctx, parts)
    elif subcmd == "show":
        return _handle_show(ctx, parts)
    elif subcmd == "create":
        return await _handle_create(ctx, parts)
    elif subcmd == "edit":
        return _handle_edit(ctx, parts)
    elif subcmd == "delete":
        return _handle_delete(ctx, parts)
    elif subcmd == "enable":
        return _handle_enable(ctx, parts)
    elif subcmd == "disable":
        return _handle_disable(ctx, parts)
    elif subcmd == "search":
        return _handle_search(ctx, parts)
    elif subcmd == "learn":
        return await _handle_learn(ctx, parts)
    elif subcmd == "apply":
        return _handle_apply(ctx, parts)
    elif subcmd == "export":
        return _handle_export(ctx, parts)
    elif subcmd == "import":
        return _handle_import(ctx, parts)
    elif subcmd == "restore":
        return _handle_restore(ctx)
    else:
        print(f"Unknown subcommand '{subcmd}'.")
        _print_usage()
        return CommandResult.ok()


def _print_usage() -> None:
    print("Usage: /skill <list|show|create|edit|delete|enable|disable|search|learn|apply|export|import|restore> ...")
    print("  /skill list [enabled|all]       List skills")
    print("  /skill show <name>              Show skill content")
    print("  /skill create                   Launch interactive wizard")
    print("  /skill edit <name>              Edit skill in $EDITOR")
    print("  /skill delete <name>            Delete a skill")
    print("  /skill enable <name>            Enable a skill")
    print("  /skill disable <name>           Disable a skill")
    print("  /skill search <query>           Search skills by name/content/tags")
    print("  /skill learn [name]             Learn a skill from current session")
    print("  /skill apply <name>             Inject skill into next prompt")
    print("  /skill export <name> <file>     Export to SKILL.md format")
    print("  /skill import <file>            Import from SKILL.md file")
    print("  /skill restore                  Restore previous tool configuration")


def _handle_list(ctx: CommandContext, parts: list) -> CommandResult:
    enabled_only = False
    if len(parts) > 2:
        flag = parts[2].lower()
        if flag in ("enabled", "on"):
            enabled_only = True
        elif flag in ("all", "*"):
            enabled_only = False

    skills = skillsdb.list_skills(enabled_only=enabled_only)
    if not skills:
        print("No skills found.")
        return CommandResult.ok()

    print(f"\n{'#':<4} {'Name':<20} {'Enabled':<10} {'Description':<50}")
    print("-" * 84)
    for skill in skills:
        doc_id = getattr(skill, "doc_id", "?")
        name = skill.get("name", "?")
        enabled = skill.get("metadata", {}).get("enabled", True)
        desc = skill.get("metadata", {}).get("description", "")
        if len(desc) > 48:
            desc = desc[:45] + "..."
        status = "ON" if enabled else "OFF"
        print(f"{doc_id:<4} {name:<20} {status:<10} {desc:<50}")
    print()
    return CommandResult.ok()


def _handle_show(ctx: CommandContext, parts: list) -> CommandResult:
    if len(parts) < 3:
        print("Usage: /skill show <name>")
        return CommandResult.ok()
    name = parts[2].strip('"')
    skill = skillsdb.get_skill_by_name(name)
    if not skill:
        print(f"Skill '{name}' not found.")
        return CommandResult.ok()

    meta = skill.get("metadata", {})
    print(f"\n{'=' * 60}")
    print(f"Skill: {skill.get('name')}")
    print(f"ID: {getattr(skill, 'doc_id', '?')}")
    print(f"Description: {meta.get('description', '')}")
    print(f"Enabled: {meta.get('enabled', True)}")
    print(f"Triggers: {', '.join(meta.get('triggers', []))}")
    print(f"Tags: {', '.join(meta.get('tags', []))}")
    print(f"Source: {meta.get('source', 'manual')}")
    print(f"Created: {meta.get('created_at', 'unknown')}")
    tc = meta.get("tool_config")
    if tc:
        print(f"Tool Config: mode={tc.get('mode', 'on')}")
        if tc.get("enable_tools"):
            print(f"  Enable: {', '.join(tc['enable_tools'])}")
        if tc.get("disable_tools"):
            print(f"  Disable: {', '.join(tc['disable_tools'])}")
        print(f"  Auto-loop: {tc.get('auto_loop', False)}, max_turns: {tc.get('max_turns', 25)}")
    else:
        print("Tool Config: (none — guidance only)")
    print(f"{'=' * 60}")
    print(f"\n{skill.get('content', '')}\n")
    return CommandResult.ok()


async def _handle_create(ctx: CommandContext, parts: list) -> CommandResult:
    print("\n--- Skill Creation Wizard ---\n")

    try:
        name = input("Skill name: ").strip()
        if not name:
            print("Skill name is required. Aborting.")
            return CommandResult.ok()

        description = input("Description (used for trigger matching): ").strip()
        if not description:
            description = ""

        triggers_input = input("Trigger phrases (comma-separated, 2+ words recommended): ").strip()
        triggers = [t.strip() for t in triggers_input.split(",") if t.strip()] if triggers_input else []

        tags_input = input("Tags for organization (comma-separated, no behavioral effect): ").strip()
        tags = [t.strip() for t in tags_input.split(",") if t.strip()] if tags_input else []

        print("\nEnter skill content (type --- on a line by itself to finish):")
        content_lines = []
        while True:
            line = input()
            if line.strip() == "---":
                break
            content_lines.append(line)
        content = "\n".join(content_lines).strip()
        if not content:
            print("Content is required. Aborting.")
            return CommandResult.ok()

        # Tool configuration (optional)
        tool_config = None
        tc_input = input(
            "\nTool configuration (optional).\n"
            "  Press Enter to skip (pure guidance skill).\n"
            "  Or enter: mode=on|off enable=tool1,tool2 disable=tool3 auto=y max=25\n"
            "  > "
        ).strip()
        if tc_input:
            tool_config = _parse_tool_config(tc_input)

    except (EOFError, KeyboardInterrupt):
        print("\nSkill creation cancelled.")
        return CommandResult.ok()

    doc_id = skillsdb.create_skill(
        name=name,
        content=content,
        description=description,
        triggers=triggers,
        tags=tags,
        tool_config=tool_config,
        source="manual",
    )
    print(f"\nSkill '{name}' created (ID: {doc_id}).")
    return CommandResult.ok()


def _parse_tool_config(text: str) -> dict | None:
    """Parse a tool configuration string into a tool_config dict."""
    config: dict = {}
    tokens = text.split()
    for token in tokens:
        if "=" not in token:
            continue
        key, val = token.split("=", 1)
        key = key.lower().strip()
        val = val.strip()
        if key == "mode":
            config["mode"] = val.lower()
        elif key == "enable":
            config["enable_tools"] = [t.strip() for t in val.split(",") if t.strip()]
        elif key == "disable":
            config["disable_tools"] = [t.strip() for t in val.split(",") if t.strip()]
        elif key == "auto":
            config["auto_loop"] = val.lower() in ("y", "yes", "true", "on")
        elif key == "max":
            try:
                config["max_turns"] = int(val)
            except ValueError:
                pass
    return config if config else None


def _handle_edit(ctx: CommandContext, parts: list) -> CommandResult:
    if len(parts) < 3:
        print("Usage: /skill edit <name>")
        return CommandResult.ok()
    name = parts[2].strip('"')
    skill = skillsdb.get_skill_by_name(name)
    if not skill:
        print(f"Skill '{name}' not found.")
        return CommandResult.ok()

    skill_id = getattr(skill, "doc_id", skill.get("doc_id"))
    meta = skill.get("metadata", {})

    with tempfile.NamedTemporaryFile(
        suffix=".md", delete=False, mode="w", encoding="utf-8"
    ) as tf:
        tf.write(f"# Skill: {skill['name']}\n")
        tf.write(f"# Description: {meta.get('description', '')}\n")
        tf.write(f"# Triggers: {', '.join(meta.get('triggers', []))}\n")
        tf.write(f"# Tags: {', '.join(meta.get('tags', []))}\n")
        tf.write(f"# Enabled: {meta.get('enabled', True)}\n")
        tf.write("# --- Edit content below this line ---\n")
        tf.write(skill.get("content", ""))
        temp_path = tf.name

    # Resolve editor (same precedence as /tool edit_live)
    config = ctx.app._load_tools_config()
    config_editor = config.get("config", {}).get("editor") if config else None
    default_editor = "notepad.exe" if os.name == "nt" else "vi"
    editor = (
        config_editor
        or os.environ.get("VISUAL")
        or os.environ.get("EDITOR")
        or default_editor
    )

    print(f"Opening skill editor using '{editor}'...")
    if os.name == "nt":
        cmd = shlex.split(editor, posix=False) + [temp_path]
    else:
        cmd = shlex.split(editor) + [temp_path]
    subprocess.run(cmd)

    with open(temp_path, "r", encoding="utf-8") as f:
        saved = f.read()
    os.unlink(temp_path)

    # Parse header fields and content
    lines = saved.splitlines()
    content_lines = []
    header_parsed = False
    parsed_desc = None
    parsed_triggers = None
    parsed_tags = None
    parsed_enabled = None

    for line in lines:
        if not header_parsed:
            if line.startswith("# ---"):
                header_parsed = True
                continue
            if line.startswith("# Description:"):
                parsed_desc = line[len("# Description:"):].strip()
            elif line.startswith("# Triggers:"):
                val = line[len("# Triggers:"):].strip()
                parsed_triggers = [t.strip() for t in val.split(",") if t.strip()]
            elif line.startswith("# Tags:"):
                val = line[len("# Tags:"):].strip()
                parsed_tags = [t.strip() for t in val.split(",") if t.strip()]
            elif line.startswith("# Enabled:"):
                parsed_enabled = line[len("# Enabled:"):].strip().lower() in ("true", "1", "yes", "on")
            elif line.startswith("# Skill:"):
                pass  # skip header
        else:
            content_lines.append(line)

    new_content = "\n".join(content_lines).strip()
    if not new_content:
        print("Content is empty. Aborting edit.")
        return CommandResult.ok()

    # Build updated metadata
    new_meta = dict(meta)
    if parsed_desc is not None:
        new_meta["description"] = parsed_desc
    if parsed_triggers is not None:
        new_meta["triggers"] = parsed_triggers
    if parsed_tags is not None:
        new_meta["tags"] = parsed_tags
    if parsed_enabled is not None:
        new_meta["enabled"] = parsed_enabled

    skillsdb.update_skill(skill_id, content=new_content, metadata=new_meta)
    print(f"Skill '{name}' updated.")
    return CommandResult.ok()


def _handle_delete(ctx: CommandContext, parts: list) -> CommandResult:
    if len(parts) < 3:
        print("Usage: /skill delete <name>")
        return CommandResult.ok()
    name = parts[2].strip('"')
    skill = skillsdb.get_skill_by_name(name)
    if not skill:
        print(f"Skill '{name}' not found.")
        return CommandResult.ok()

    try:
        confirm = input(f"Delete skill '{name}'? (y/N): ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print("\nDelete cancelled.")
        return CommandResult.ok()

    if confirm not in ("y", "yes"):
        print("Delete cancelled.")
        return CommandResult.ok()

    skillsdb.delete_skill(getattr(skill, "doc_id", skill.get("doc_id")))
    print(f"Skill '{name}' deleted.")
    return CommandResult.ok()


def _handle_enable(ctx: CommandContext, parts: list) -> CommandResult:
    if len(parts) < 3:
        print("Usage: /skill enable <name>")
        return CommandResult.ok()
    name = parts[2].strip('"')
    skill = skillsdb.get_skill_by_name(name)
    if not skill:
        print(f"Skill '{name}' not found.")
        return CommandResult.ok()
    skillsdb.patch_skill_metadata(getattr(skill, "doc_id", skill.get("doc_id")), "enabled", True)
    print(f"Skill '{name}' enabled.")
    return CommandResult.ok()


def _handle_disable(ctx: CommandContext, parts: list) -> CommandResult:
    if len(parts) < 3:
        print("Usage: /skill disable <name>")
        return CommandResult.ok()
    name = parts[2].strip('"')
    skill = skillsdb.get_skill_by_name(name)
    if not skill:
        print(f"Skill '{name}' not found.")
        return CommandResult.ok()
    skillsdb.patch_skill_metadata(getattr(skill, "doc_id", skill.get("doc_id")), "enabled", False)
    print(f"Skill '{name}' disabled.")
    return CommandResult.ok()


def _handle_search(ctx: CommandContext, parts: list) -> CommandResult:
    if len(parts) < 3:
        print("Usage: /skill search <query>")
        return CommandResult.ok()
    query = parts[2] if len(parts) < 4 else " ".join(parts[2:])
    query = query.strip('"')
    results = skillsdb.search_skills(query)
    if not results:
        print("No matching skills found.")
        return CommandResult.ok()
    print(f"Found {len(results)} matching skill(s):")
    for skill in results:
        doc_id = getattr(skill, "doc_id", "?")
        name = skill.get("name", "?")
        desc = skill.get("metadata", {}).get("description", "")
        if len(desc) > 60:
            desc = desc[:57] + "..."
        print(f"  {doc_id}. {name} — {desc}")
    return CommandResult.ok()


async def _handle_learn(ctx: CommandContext, parts: list) -> CommandResult:
    app = ctx.app
    if not app.session_turns:
        print("No active session turns to learn from. Run some prompts first.")
        return CommandResult.ok()

    name = ""
    if len(parts) > 2:
        name = parts[2].strip('"')
    else:
        try:
            name = input("Skill name: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nLearn cancelled.")
            return CommandResult.ok()

    if not name:
        print("Skill name is required.")
        return CommandResult.ok()

    # Build skill content from session turns
    last_turn = app.session_turns[-1]
    prompt = last_turn.get("prompt", "")
    response = last_turn.get("response", "")

    content = (
        f"Learned from session. The user asked:\n{prompt}\n\n"
        f"The successful approach was:\n{response}\n\n"
        f"Follow this pattern when similar requests arise."
    )

    description = f"Learned from session on {app.active_session_id or 'unknown'}"

    try:
        triggers_input = input(
            "Trigger phrases (comma-separated, or press Enter to skip): "
        ).strip()
    except (EOFError, KeyboardInterrupt):
        print("\nLearn cancelled.")
        return CommandResult.ok()

    triggers = [t.strip() for t in triggers_input.split(",") if t.strip()] if triggers_input else []

    doc_id = skillsdb.create_skill(
        name=name,
        content=content,
        description=description,
        triggers=triggers,
        tags=["learned"],
        source=f"session:{app.active_session_id or 'unknown'}",
    )
    print(f"Skill '{name}' learned from session (ID: {doc_id}).")
    return CommandResult.ok()


def _handle_apply(ctx: CommandContext, parts: list) -> CommandResult:
    if len(parts) < 3:
        print("Usage: /skill apply <name>")
        return CommandResult.ok()
    name = parts[2].strip('"')
    skill = skillsdb.get_skill_by_name(name)
    if not skill:
        print(f"Skill '{name}' not found.")
        return CommandResult.ok()

    # Store the skill for manual injection on next prompt
    ctx.app.buffer_manager.set_script_var(
        "_PENDING_SKILL", skill, allow_protected=True
    )
    print(f"Skill '{name}' will be applied to the next prompt.")
    return CommandResult.ok()


def _handle_export(ctx: CommandContext, parts: list) -> CommandResult:
    if len(parts) < 4:
        print("Usage: /skill export <name> <file>")
        return CommandResult.ok()
    name = parts[2].strip('"')
    filepath = parts[3].strip('"')
    if skillsdb.export_skill_to_skillmd(name, filepath):
        print(f"Skill '{name}' exported to '{filepath}'.")
    else:
        print(f"Failed to export skill '{name}'. Skill not found or write error.")
    return CommandResult.ok()


def _handle_import(ctx: CommandContext, parts: list) -> CommandResult:
    if len(parts) < 3:
        print("Usage: /skill import <file>")
        return CommandResult.ok()
    filepath = parts[2].strip('"')
    doc_id = skillsdb.import_skill_from_skillmd(filepath)
    if doc_id is not None:
        print(f"Skill imported from '{filepath}' (ID: {doc_id}).")
    else:
        print(f"Failed to import skill from '{filepath}'. File not found or invalid format.")
    return CommandResult.ok()


def _handle_restore(ctx: CommandContext) -> CommandResult:
    app = ctx.app
    if not hasattr(app, "_restore_tool_state_snapshot") or not callable(app._restore_tool_state_snapshot):
        print("No tool state snapshot available to restore.")
        return CommandResult.ok()
    if app._restore_tool_state_snapshot():
        print("Tool configuration restored to previous state.")
    else:
        print("No tool state snapshot available to restore.")
    return CommandResult.ok()
