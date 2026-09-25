#!/usr/bin/env python3
"""
Unit tests for Dynamic Context Injection (!`cmd`) in BufferManager
"""

import pytest
from src.chatybot.buffer_manager import BufferManager


class MockApp:
    """Minimal mock app for testing dynamic injection with safe mode."""

    def __init__(self, safe_mode=True, safe_mode_askfirst=False, trace_raw_payload=False):
        self.safe_mode = safe_mode
        self.safe_mode_askfirst = safe_mode_askfirst
        self.trace_raw_payload = trace_raw_payload

    def check_dangerous(self, command: str) -> str | None:
        """Mirror of ChatybotApp.check_dangerous for testing."""
        import re

        DANGEROUS_PATTERNS = [
            (r'rm\s+-r\b', "Recursive delete (rm -r)"),
            (r'rm\s+--recursive\b', "Recursive delete (rm --recursive)"),
            (r'rm\s+-rf\b', "Recursive force delete (rm -rf)"),
            (r'rm\s+--recursive\s+--force\b', "Recursive force delete"),
            (r'>\s*(/dev/|/etc/|/usr/|/bin/|/sbin/|/lib/|/boot/|/var/|/opt/)', "Write to critical system directory"),
            (r':\s*\>\s*\S+', "Here-document"),
            (r';\s*', "Command chaining with ;"),
            (r'&&\s*', "AND-chain"),
            (r'\|\s*', "OR-chain"),
            (r'\$\(', "Command substitution"),
            (r'`[^`]+`', "Backtick command substitution"),
            (r'chmod\s+-R\b', "Recursive chmod"),
            (r'chown\s+-R\b', "Recursive chown"),
            (r'mkfs\b', "Filesystem creation"),
            (r'dd\s+if=\s*', "dd command (disk operations)"),
            (r'fdisk\b', "Partition table manipulation"),
            (r'format\b', "Disk formatting"),
            (r'partition\b', "Partition manipulation"),
            (r'mount\b', "Mount filesystems"),
            (r'umount\b', "Unmount filesystems"),
            (r'sudo\b', "Privilege escalation (sudo)"),
            (r'su\s+', "Switch user"),
        ]

        for pattern, description in DANGEROUS_PATTERNS:
            if re.search(pattern, command):
                return description
        return None


class TestDynamicInjection:
    """Test suite for !`cmd` dynamic context injection."""

    @pytest.fixture
    def manager(self):
        """BufferManager with no app (no safe mode checks)."""
        return BufferManager()

    @pytest.fixture
    def manager_safe(self):
        """BufferManager with safe_mode=True (default)."""
        bm = BufferManager()
        bm.app = MockApp(safe_mode=True)
        return bm

    @pytest.fixture
    def manager_unsafe(self):
        """BufferManager with safe_mode=False."""
        bm = BufferManager()
        bm.app = MockApp(safe_mode=False)
        return bm

    @pytest.fixture
    def manager_askfirst(self):
        """BufferManager with safe_mode=False, askfirst=True."""
        bm = BufferManager()
        bm.app = MockApp(safe_mode=False, safe_mode_askfirst=True)
        return bm

    def test_no_injection_marker(self, manager):
        """Text without !` should pass through unchanged."""
        result = manager.expand_dynamic_injections("Hello world")
        assert result == "Hello world"

    def test_basic_substitution(self, manager):
        """Basic !`echo` substitution."""
        result = manager.expand_dynamic_injections("The year is !`echo 2026`.")
        assert result == "The year is 2026."

    def test_multiple_injections(self, manager):
        """Multiple !`cmd` blocks in one string."""
        result = manager.expand_dynamic_injections("!`echo a` and !`echo b`")
        assert result == "a and b"

    def test_empty_command(self, manager):
        """Empty !`` (no content) should not match the regex and pass through."""
        result = manager.expand_dynamic_injections("start !`` end")
        assert result == "start !`` end"

    def test_timeout_enforcement(self, manager):
        """Commands exceeding 3s timeout should be caught."""
        result = manager.expand_dynamic_injections("!`sleep 5`")
        assert "timed out" in result
        assert "sleep 5" in result
        assert "/run" in result

    def test_output_cap_enforcement(self, manager):
        """Output beyond 4KB should be truncated."""
        result = manager.expand_dynamic_injections("!`python3 -c \"print('x'*5000)\"`")
        assert len(result.encode("utf-8")) <= 4096 + 200  # allow for truncation notice
        assert "truncated at 4KB" in result

    def test_nonzero_exit_with_stderr(self, manager):
        """Non-zero exit with stderr should produce error notice."""
        result = manager.expand_dynamic_injections("!`ls /nonexistent_directory_chatybot_xyz_123`")
        # Either an error notice or empty output (ls writes to stderr)
        assert result.startswith("[") or result == ""

    def test_safe_mode_blocks_dangerous(self, manager_safe):
        """safe_mode=True should block rm -rf."""
        result = manager_safe.expand_dynamic_injections("!`rm -rf /test`")
        assert "Blocked by safe_mode" in result
        assert "rm -rf /test" in result

    def test_safe_mode_blocks_pipe(self, manager_safe):
        """safe_mode=True should block pipe operator by default."""
        result = manager_safe.expand_dynamic_injections("!`git log | head`")
        assert "Blocked by safe_mode" in result

    def test_safe_mode_blocks_semicolon(self, manager_safe):
        """safe_mode=True should block semicolon chaining."""
        result = manager_safe.expand_dynamic_injections("!`ls; pwd`")
        assert "Blocked by safe_mode" in result

    def test_safe_mode_blocks_command_substitution(self, manager_safe):
        """safe_mode=True should block $() substitution."""
        result = manager_safe.expand_dynamic_injections("!`echo $(date)`")
        assert "Blocked by safe_mode" in result

    def test_askfirst_blocks_noninteractive(self, manager_askfirst):
        """safe_mode_askfirst=True should block in non-interactive context."""
        result = manager_askfirst.expand_dynamic_injections("!`rm -rf /test`")
        assert "Blocked" in result
        assert "askfirst" in result.lower() or "non-interactive" in result.lower()

    def test_unsafe_mode_allows_safe_command(self, manager_unsafe):
        """safe_mode=False should allow benign commands."""
        result = manager_unsafe.expand_dynamic_injections("!`echo hello`")
        assert result == "hello"

    def test_shlex_parse_error(self, manager):
        """Malformed commands (unbalanced quotes) should produce parse error."""
        result = manager.expand_dynamic_injections("!`echo \"unterminated`")
        assert "parse error" in result or "Command error" in result

    def test_no_reentrancy(self, manager):
        """Output containing !`cmd` should not be recursively executed."""
        # echo a string that looks like an injection — should NOT be executed
        result = manager.expand_dynamic_injections("!`echo '!`whoami`'`")
        # The inner !`whoami` is part of the command string passed to echo,
        # but shlex.split will see it as part of the argument.
        # The key assertion: the result should not contain the actual whoami output
        # as a recursively executed injection.
        # Since shell=False, the backticks are literal to echo.
        assert "whoami" in result  # echo outputs the literal text

    def test_injection_in_replace_placeholders(self, manager):
        """replace_placeholders should expand !`cmd` by default."""
        result, _ = manager.replace_placeholders("Year: !`echo 2026`")
        assert result == "Year: 2026"

    def test_replace_placeholders_expand_injections_false(self, manager):
        """replace_placeholders with expand_injections=False should NOT expand !`cmd`."""
        result, _ = manager.replace_placeholders("Year: !`echo 2026`", expand_injections=False)
        assert result == "Year: !`echo 2026`"

    def test_replace_placeholders_legacy_no_injection(self, manager):
        """replace_placeholders_legacy should NOT expand !`cmd` (used by /run)."""
        result = manager.replace_placeholders_legacy("Year: !`echo 2026`")
        assert result == "Year: !`echo 2026`"

    def test_variable_then_injection(self, manager):
        """Variables should be resolved before dynamic injection."""
        manager.set_script_var("MYVAR", "2026")
        result, _ = manager.replace_placeholders("Year: ${MYVAR}, echo: !`echo hi`")
        assert "Year: 2026" in result
        assert "echo: hi" in result

    def test_trace_logging(self, capsys):
        """When trace_raw_payload is True, execution should be logged."""
        bm = BufferManager()
        bm.app = MockApp(safe_mode=False, trace_raw_payload=True)
        bm.expand_dynamic_injections("!`echo traced`")
        captured = capsys.readouterr()
        assert "[trace]" in captured.out
        assert "echo traced" in captured.out

    def test_trace_logging_blocked(self, capsys):
        """When trace is on and command is blocked, should log the block."""
        bm = BufferManager()
        bm.app = MockApp(safe_mode=True, trace_raw_payload=True)
        bm.expand_dynamic_injections("!`rm -rf /test`")
        captured = capsys.readouterr()
        assert "[trace]" in captured.out
        assert "blocked" in captured.out

    def test_no_trace_when_disabled(self, capsys):
        """When trace_raw_payload is False, no trace output."""
        bm = BufferManager()
        bm.app = MockApp(safe_mode=False, trace_raw_payload=False)
        bm.expand_dynamic_injections("!`echo quiet`")
        captured = capsys.readouterr()
        assert "[trace]" not in captured.out

    def test_no_app_no_safe_mode_check(self, manager):
        """Without an app reference, commands should execute without safe mode checks."""
        # No app set, so check_dangerous is never called
        result = manager.expand_dynamic_injections("!`echo noapp`")
        assert result == "noapp"
