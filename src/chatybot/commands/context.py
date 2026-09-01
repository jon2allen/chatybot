"""CommandContext: the focused interface handed to every command handler.

During the phased migration, ``app`` is exposed so handlers can reach
attributes that have not yet been factored behind a clean protocol. As
domains migrate, handlers should prefer the typed members
(``buffer_manager``, ``config_manager``, ``i18n``) over ``app``.
"""

from dataclasses import dataclass
from typing import Any, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from chatybot.buffer_manager import BufferManager
    from chatybot.config_manager import ConfigManager
    from chatybot.localization import LocalizationManager
    from chatybot.session_interface import BaseSessionStore


@dataclass
class CommandContext:
    """Clean interface provided to all command handlers."""
    buffer_manager: "BufferManager"
    config_manager: "ConfigManager"
    i18n: "LocalizationManager"
    session_store: Optional["BaseSessionStore"]
    app: Any  # Reference to ChatybotApp during phased migration

    @property
    def config(self):
        return self.config_manager.config
