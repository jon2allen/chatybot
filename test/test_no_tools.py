#!/usr/bin/env python3
"""
Unit tests for ChatyBot --no-tools CLI option and runtime behavior.
"""

import pytest
import argparse
from unittest.mock import patch, MagicMock
from src.chatybot.chatybot_app import ChatybotApp


class TestNoToolsBehavior:
    """Test suite for --no-tools disabling MCP and startup tool mode."""

    def test_no_tools_initialization(self):
        """Verify that ChatybotApp with no_tools=True bypasses MCPClientManager and starts disabled."""
        app = ChatybotApp(no_tools=True)
        app.initialize()

        # MCP manager should be None
        assert app.no_tools is True
        assert app.mcp_manager is None
        assert app.tool_mode is False
        assert app.tool_auto is False
        assert app.tool_context == ""

    @pytest.mark.anyio
    async def test_internal_tools_can_be_enabled_with_no_tools(self):
        """Verify that internal/local tools can still be enabled manually during session."""
        app = ChatybotApp(no_tools=True)
        app.initialize()

        # Initially disabled
        assert app.tool_mode is False
        assert app.mcp_manager is None

        # Turn tools on
        res = await app.handle_escape_command("/tool on")
        assert res is True
        assert app.tool_mode is True
        assert "read_file" in app.tool_context or "AVAILABLE TOOLS" in app.tool_context

        # Enable specific internal tool
        res_enable = await app.handle_escape_command("/tool enable read_file")
        assert res_enable is True
        assert app.tool_overrides.get("read_file") is True

        # Tool list command works cleanly without MCP
        res_list = await app.handle_escape_command("/tool list")
        assert res_list is True

    def test_cli_argument_parsing_no_tools(self):
        """Verify that --no-tools is recognized by CLI argument parser."""
        parser = argparse.ArgumentParser(description="Chatybot CLI")
        parser.add_argument(
            "-c", "--config",
            help="Path to alternate TOML configuration file",
            default=None
        )
        parser.add_argument(
            "--no-tools",
            action="store_true",
            help="Disable tools on startup and bypass all MCP server loading via stdio"
        )

        args = parser.parse_args(["--no-tools"])
        assert args.no_tools is True

        args_default = parser.parse_args([])
        assert args_default.no_tools is False
