"""
Unit tests for ChatyBot help system updates (procedures and foreach loops).
"""

import pytest
from chatybot.chaty_help import get_help_system


def test_help_proc_and_defproc():
    """Verify help system registers and retrieves help for /proc, defproc, and local."""
    help_sys = get_help_system()
    
    proc_help = help_sys.get_help_text("/proc")
    assert "/proc <name>" in proc_help
    assert "procedure" in proc_help.lower()

    defproc_help = help_sys.get_help_text("defproc")
    assert "defproc <name>" in defproc_help
    assert "reusable procedure block" in defproc_help.lower()

    local_help = help_sys.get_help_text("local")
    assert "local <name>" in local_help
    assert "local" in local_help.lower()


def test_help_foreach_and_generators():
    """Verify help system registers and retrieves help for foreach, range, and lines."""
    help_sys = get_help_system()

    foreach_help = help_sys.get_help_text("foreach")
    assert "foreach <item_var>" in foreach_help
    assert "range" in foreach_help
    assert "lines" in foreach_help

    range_matches = help_sys.filter_commands("range")
    assert any(cmd.name == "foreach" for cmd in range_matches)

    lines_matches = help_sys.filter_commands("lines")
    assert any(cmd.name == "foreach" for cmd in lines_matches)
