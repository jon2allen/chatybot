"""Database and variable persistence commands.

Migrated from chatybot_app.handle_escape_command elif chain:
  /setdb, /dblist, /searchdb, /dblog, /dbprint, /loadvar, /savevar
"""

from chatybot.commands.registry import command, CommandResult
from chatybot.commands.context import CommandContext
from chatybot.chatydb import set_db, search_db, dblog, load_var, save_var, list_dbs, dbprint


@command("/setdb", help="Set the active database", args="<dbname>", category="db")
async def cmd_setdb(ctx: CommandContext, parts: list, command: str) -> CommandResult:
    if len(parts) < 2:
        print("Usage: /setdb <dbname>")
        return CommandResult.ok()
    dbname = parts[1].strip('"')
    set_db(dbname)
    return CommandResult.ok()


@command("/dblist", help="List all databases", args="", category="db")
async def cmd_dblist(ctx: CommandContext, parts: list, command: str) -> CommandResult:
    list_dbs()
    return CommandResult.ok()


@command("/searchdb", help="Search the active database", args="<query>", category="db")
async def cmd_searchdb(ctx: CommandContext, parts: list, command: str) -> CommandResult:
    if len(parts) < 2:
        print("Usage: /searchdb <query>")
        return CommandResult.ok()
    # parts was split with maxsplit=2, so a multi-word query lands in
    # parts[2]. Rejoin so "/searchdb python web framework" searches for
    # the full phrase rather than just "python".
    query = parts[1] if len(parts) < 3 else f"{parts[1]} {parts[2]}"
    search_db(query.strip('"'))
    return CommandResult.ok()


@command("/dblog", help="Log the last response to the database", args="[thinking]", category="db")
async def cmd_dblog(ctx: CommandContext, parts: list, command: str) -> CommandResult:
    # /dblog logs the final answer only (legacy behavior).
    # /dblog thinking (or withthink) also persists the extracted
    # reasoning text and reasoning token count into the item's metadata.
    # Matches the bare-word convention used by /save (nothink/withthink)
    # and /logging (hex) rather than a --prefix flag.
    include_thinking = False
    if len(parts) > 1:
        flags = parts[1].lower() if len(parts) < 3 else f"{parts[1]} {parts[2]}".lower()
        include_thinking = any(w in flags for w in ("thinking", "withthink", "with-think"))
    dblog(include_thinking=include_thinking)
    return CommandResult.ok()


@command("/dbprint", help="Print a database entry", args="[id]", category="db")
async def cmd_dbprint(ctx: CommandContext, parts: list, command: str) -> CommandResult:
    if len(parts) > 1:
        filename = parts[1].strip('"')
        dbprint(filename)
    else:
        dbprint()
    return CommandResult.ok()


@command("/loadvar", help="Load a variable from the database", args="<varname> [ALL | id | range]", category="db")
async def cmd_loadvar(ctx: CommandContext, parts: list, command: str) -> CommandResult:
    if len(parts) < 2:
        print("Usage: /loadvar <varname> [ALL | id | range]")
        return CommandResult.ok()
    varname = parts[1].strip('"')
    extra = parts[2] if len(parts) > 2 else None
    load_var(varname, extra)
    return CommandResult.ok()


@command("/savevar", help="Save a variable to the database", args="<varname> <filename>", category="db")
async def cmd_savevar(ctx: CommandContext, parts: list, command: str) -> CommandResult:
    if len(parts) < 3:
        print("Usage: /savevar <varname> <filename>")
        return CommandResult.ok()
    varname = parts[1].strip('"')
    filename = parts[2].strip('"')
    save_var(varname, filename)
    return CommandResult.ok()
