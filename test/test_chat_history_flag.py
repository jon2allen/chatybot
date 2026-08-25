"""
test_chat_history_flag.py - Unit tests for enable_chat_history flag and /session history command
"""

import pytest
from unittest.mock import patch, MagicMock
from src.chatybot.chatybot_app import ChatybotApp


@pytest.fixture
def app():
    with patch('src.chatybot.chatybot_app.readline'):
        app_inst = ChatybotApp()
        app_inst.enable_chat_history = True
        return app_inst


@pytest.mark.anyio
async def test_session_history_command_status(app):
    # Check default status display
    with patch('builtins.print') as mock_print:
        await app.execute_line("/session history")
        mock_print.assert_any_call("Chat History Collection is currently: ON")


@pytest.mark.anyio
async def test_session_history_command_off_and_on(app):
    # Toggle off
    with patch('builtins.print') as mock_print:
        await app.execute_line("/session history off")
        assert app.enable_chat_history is False
        mock_print.assert_any_call("Chat history collection disabled. Note: Agentic tool loops are also disabled in this mode.")

    # Toggle back on
    with patch('builtins.print') as mock_print:
        await app.execute_line("/session history on")
        assert app.enable_chat_history is True
        mock_print.assert_any_call("Chat history collection enabled.")


@pytest.mark.anyio
async def test_execute_tool_loop_blocked_when_history_disabled(app):
    app.enable_chat_history = False
    with patch('builtins.print') as mock_print:
        await app.execute_tool_loop(max_turns=25)
        mock_print.assert_called_with("Error: Agentic tool loops are disabled when chat history collection is turned off.")
