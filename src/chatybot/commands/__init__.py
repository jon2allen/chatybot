"""Command package: importing this module triggers registration of all
domain command modules into the module-level registry.

Add new domain modules here as they are created during the phased migration.
"""

from chatybot.commands import debug  # noqa: F401  (registers /echo)
