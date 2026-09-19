"""Command package: importing this module triggers registration of all
domain command modules into the module-level registry.

Add new domain modules here as they are created during the phased migration.
"""

from chatybot.commands import (
    buffer,  # noqa: F401  (registers /file, /filebank1-5, /imagebank1-5, etc.)
    db,  # noqa: F401  (registers /setdb, /dblist, /searchdb, etc.)
    debug,  # noqa: F401  (registers /echo)
    decide,  # noqa: F401  (registers /decide)
    debug_misc,  # noqa: F401  (registers /trace, /debug, /prompt, /logging, etc.)
    image,  # noqa: F401  (registers /imagine, /saveimage, etc.)
    interact,  # noqa: F401  (registers /ask)
    models,  # noqa: F401  (registers /model, /temp, /top_p, etc.)
    proc_macros,  # noqa: F401  (registers /proc, /source, /script)
    replay,  # noqa: F401  (registers /replay)
    rerank,  # noqa: F401  (registers /documents, /rerank)
    session,  # noqa: F401  (registers /session)
    tools,  # noqa: F401  (registers /run, /run_safe, /run_unsafe, /tool)
)
