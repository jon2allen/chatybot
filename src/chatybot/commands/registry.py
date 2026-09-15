"""Command registry, decorator, and typed result for the modular command system.

This module provides the infrastructure for the "sweet spot" command
architecture: a decorator-based registry with typed CommandResult values
that eliminates the fragile ``"EXECUTE_PROMPT"`` string sentinel.

Design notes (deviations from the original blueprint, made to preserve
existing behavior exactly):

1. Handlers receive ``(ctx, parts, command)`` rather than ``(ctx, args)``.
   ``parts`` is ``command.split(maxsplit=2)`` and ``command`` is the raw
   string. Several legacy commands (e.g. ``/echo``) use
   ``command.split(maxsplit=1)[1]`` to preserve internal whitespace, which
   differs from ``parts[1]``. Passing both lets migrated commands replicate
   the original logic byte-for-byte.

2. The registry does NOT perform i18n alias resolution. Localization is
   handled by ``LocalizationManager.resolve_command`` in
   ``handle_escape_command`` BEFORE the registry is consulted, so the
   registry only stores canonical English command names. This preserves the
   existing localization flow for all locales.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any, Awaitable, Callable, Dict, List, Optional

if TYPE_CHECKING:
    from chatybot.commands.context import CommandContext


class CommandAction(Enum):
    """Outcome of a command handler invocation."""
    HANDLED = "handled"            # command ran successfully, stop here
    EXECUTE_PROMPT = "execute_prompt"  # handler set prompt_buffer; caller must run completion
    EXIT = "exit"                  # request application exit
    ERROR = "error"                # handler reported an error (already printed)


@dataclass
class CommandResult:
    """Strongly-typed return value replacing the ``Union[bool, str]`` contract."""
    action: CommandAction
    message: str | None = None
    prompt_to_execute: str | None = None

    @classmethod
    def ok(cls, msg: str | None = None) -> "CommandResult":
        return cls(action=CommandAction.HANDLED, message=msg)

    @classmethod
    def execute_prompt(cls, prompt: str) -> "CommandResult":
        return cls(action=CommandAction.EXECUTE_PROMPT, prompt_to_execute=prompt)

    @classmethod
    def error(cls, msg: str | None = None) -> "CommandResult":
        return cls(action=CommandAction.ERROR, message=msg)

    @classmethod
    def exit(cls) -> "CommandResult":
        return cls(action=CommandAction.EXIT)


# A handler takes (context, parts, raw_command) where parts is
# command.split(maxsplit=2). It returns a CommandResult.
HandlerFn = Callable[["CommandContext", list[str], str], Awaitable[CommandResult]]


@dataclass
class CommandSpec:
    name: str
    handler: HandlerFn
    help: str = ""
    args: str = ""
    category: str = "general"
    aliases: list[str] = field(default_factory=list)


class CommandRegistry:
    """Maps canonical command names (and non-i18n aliases) to handlers."""

    def __init__(self):
        self._commands: dict[str, CommandSpec] = {}
        self._aliases: dict[str, str] = {}

    def register(
        self,
        name: str,
        handler: HandlerFn,
        help: str = "",
        args: str = "",
        category: str = "general",
        aliases: list[str] | None = None,
    ) -> None:
        aliases = aliases or []
        spec = CommandSpec(
            name=name,
            handler=handler,
            help=help,
            args=args,
            category=category,
            aliases=aliases,
        )
        self._commands[name] = spec
        for alias in aliases:
            self._aliases[alias] = name

    def get(self, name: str) -> CommandSpec | None:
        """Look up a spec by canonical name or non-i18n alias.

        Returns None when no handler is registered, so the caller can fall
        through to the legacy elif chain during the phased migration.
        """
        primary = self._aliases.get(name, name)
        return self._commands.get(primary)

    def has(self, name: str) -> bool:
        return self.get(name) is not None

    def get_all_specs(self) -> list[CommandSpec]:
        return list(self._commands.values())

    def names(self) -> list[str]:
        return list(self._commands.keys())


# Module-level default registry. Domain modules register into this via the
# @command decorator at import time. ChatybotApp references this instance.
registry = CommandRegistry()


def command(
    name: str,
    *,
    help: str = "",
    args: str = "",
    category: str = "general",
    aliases: list[str] | None = None,
):
    """Decorator registering an async handler under ``name``.

    The decorated function must accept (ctx, parts, command) and return a
    CommandResult.
    """
    def decorator(fn: HandlerFn) -> HandlerFn:
        registry.register(
            name=name,
            handler=fn,
            help=help,
            args=args,
            category=category,
            aliases=aliases,
        )
        return fn
    return decorator
