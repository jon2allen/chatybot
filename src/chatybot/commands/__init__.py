"""Command package: importing this module triggers registration of all
domain command modules into the module-level registry.

Add new domain modules here as they are created during the phased migration.
"""

from chatybot.commands import debug   # noqa: F401  (registers /echo)
from chatybot.commands import image    # noqa: F401  (registers /imagine, /saveimage, etc.)
from chatybot.commands import buffer   # noqa: F401  (registers /file, /filebank1-5, /imagebank1-5, etc.)
from chatybot.commands import models   # noqa: F401  (registers /model, /temp, /top_p, etc.)
