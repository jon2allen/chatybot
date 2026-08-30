"""File buffer and bank commands.

Migrated from chatybot_app.handle_escape_command elif chain:
  /file, /clearfile, /showfile, /filebank1-5, /imagebank1-5

The filebank and imagebank commands use a factory pattern: each numbered
variant (1-5) is registered as a separate exact-match entry, all pointing
to handlers that close over the bank number. i18n aliases (e.g.
/banco_arch1 -> /filebank1) are resolved before registry lookup, so the
canonical names are all the registry needs.
"""

from chatybot.commands.registry import command, CommandResult, registry
from chatybot.commands.context import CommandContext


@command("/file", help="Load a text file into the buffer", args="<path>", category="buffer")
async def cmd_file(ctx: CommandContext, parts: list, command: str) -> CommandResult:
    app = ctx.app
    if len(parts) < 2:
        print("Usage: /file <path>")
        return CommandResult.ok()

    file_path = command.split(maxsplit=1)[1].strip(" \"'")
    try:
        app.buffer_manager.load_file_to_buffer(file_path)
    except Exception as e:
        print(f"Error reading file: {str(e)}")
    return CommandResult.ok()


@command("/clearfile", help="Clear the file buffer", args="", category="buffer")
async def cmd_clearfile(ctx: CommandContext, parts: list, command: str) -> CommandResult:
    ctx.app.buffer_manager.clear_file_buffer()
    return CommandResult.ok()


@command("/showfile", help="Show the file buffer contents", args="[all]", category="buffer")
async def cmd_showfile(ctx: CommandContext, parts: list, command: str) -> CommandResult:
    app = ctx.app
    show_all = len(parts) > 1 and parts[1].lower() == "all"
    app.buffer_manager.show_file_buffer(show_all)
    return CommandResult.ok()


def _make_filebank_handler(bank_num: int):
    async def handler(ctx: CommandContext, parts: list, command: str) -> CommandResult:
        app = ctx.app
        if len(parts) < 2:
            print(f"Usage: /filebank{bank_num} <file> or /filebank{bank_num} clear or /filebank{bank_num} show [all]")
            return CommandResult.ok()

        subcommand = parts[1].lower()

        if subcommand == "clear":
            app.buffer_manager.clear_file_bank(bank_num)
            return CommandResult.ok()
        elif subcommand == "show":
            show_all = len(parts) > 2 and parts[2].lower() == "all"
            app.buffer_manager.show_file_bank(bank_num, show_all)
            return CommandResult.ok()
        else:
            # Assume it's a file path
            file_path = command.split(maxsplit=1)[1].strip(" \"'")
            try:
                app.buffer_manager.load_file_to_bank(bank_num, file_path)
            except Exception as e:
                print(f"Error reading file: {str(e)}")
            return CommandResult.ok()
    return handler


def _make_imagebank_handler(bank_num: int):
    async def handler(ctx: CommandContext, parts: list, command: str) -> CommandResult:
        app = ctx.app
        if len(parts) < 2:
            print(f"Usage: /imagebank{bank_num} <file> or /imagebank{bank_num} clear or /imagebank{bank_num} show")
            return CommandResult.ok()

        subcommand = parts[1].lower()

        if subcommand == "clear":
            app.buffer_manager.clear_image_bank(bank_num)
            return CommandResult.ok()
        elif subcommand == "show":
            show_all = len(parts) > 2 and parts[2].lower() == "all"
            app.buffer_manager.show_image_bank(bank_num, show_all)
            return CommandResult.ok()
        else:
            # Assume it's a file path
            file_path = command.split(maxsplit=1)[1].strip(" \"'")
            try:
                app.buffer_manager.load_image_to_bank(bank_num, file_path)
            except Exception as e:
                print(f"Error reading image file: {str(e)}")
            return CommandResult.ok()
    return handler


# Register numbered filebank and imagebank variants (1-5)
for _i in range(1, 6):
    registry.register(
        f"/filebank{_i}",
        _make_filebank_handler(_i),
        help=f"Load a file into filebank{_i}",
        args="<file> | clear | show [all]",
        category="buffer",
    )
    registry.register(
        f"/imagebank{_i}",
        _make_imagebank_handler(_i),
        help=f"Load an image into imagebank{_i}",
        args="<file> | clear | show",
        category="buffer",
    )
