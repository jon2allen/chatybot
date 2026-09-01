"""Command package: importing this module triggers registration of all
domain command modules into the module-level registry.

Add new domain modules here as they are created during the phased migration.
"""

from chatybot.commands import debug       # noqa: F401  (registers /echo)
from chatybot.commands import image        # noqa: F401  (registers /imagine, /saveimage, etc.)
from chatybot.commands import buffer       # noqa: F401  (registers /file, /filebank1-5, /imagebank1-5, etc.)
from chatybot.commands import models        # noqa: F401  (registers /model, /temp, /top_p, etc.)
from chatybot.commands import db            # noqa: F401  (registers /setdb, /dblist, /searchdb, etc.)
from chatybot.commands import debug_misc   # noqa: F401  (registers /trace, /debug, /prompt, /logging, etc.)
from chatybot.commands import session       # noqa: F401  (registers /session)
from chatybot.commands import tools         # noqa: F401  (registers /run, /run_safe, /run_unsafe, /tool)
from chatybot.commands import proc_macros   # noqa: F401  (registers /proc, /source, /script)
from chatybot.commands import rerank        # noqa: F401  (registers /documents, /rerank)
