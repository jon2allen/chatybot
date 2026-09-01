"""Debug / inspection commands.

First migrated command: /echo. This is a byte-for-byte port of the legacy
elif branch in chatybot_app.handle_escape_command, chosen as the
proof-of-concept because it exercises the full path (i18n alias resolution ->
registry lookup -> handler -> return-contract adaptation) while being
self-contained.
"""

from chatybot.commands.registry import command, CommandResult
from chatybot.commands.context import CommandContext


@command("/echo", help="Print text with variable substitution", args="<text>", category="debug")
async def cmd_echo(ctx: CommandContext, parts: list, command: str) -> CommandResult:
    if len(parts) < 2:
        print()
        return CommandResult.ok()

    try:
        text = command.split(maxsplit=1)[1]
    except IndexError:
        print()
        return CommandResult.ok()

    processed_text, _ = ctx.buffer_manager.replace_placeholders(text, include_images=False)

    if (processed_text.startswith('"') and processed_text.endswith('"')) or \
       (processed_text.startswith("'") and processed_text.endswith("'")):
        processed_text = processed_text[1:-1]

    print(processed_text)
    return CommandResult.ok()
