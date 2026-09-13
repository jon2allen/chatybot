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


@pytest.mark.anyio
async def test_history_off_save_last_completion(app, tmp_path, monkeypatch):
    app.enable_chat_history = False

    async def mock_create(**kwargs):
        class MockChoice:
            message = type("Message", (), {"content": "Beijing is famous for Peking duck.", "tool_calls": None})()
        class MockResponse:
            choices = [MockChoice()]
            usage = type("Usage", (), {"prompt_tokens": 10, "completion_tokens": 8})()
        return MockResponse()

    class MockClient:
        class chat:
            class completions:
                create = staticmethod(mock_create)

    monkeypatch.setattr(app, "get_openai_client", lambda *args, **kwargs: MockClient())
    monkeypatch.setattr(app.config_manager, "get_model_config", lambda *args: {"name": "test-model"})

    await app.chat_completion("What is a famous dish in Beijing?", stream=False)

    assert app.last_response == "Beijing is famous for Peking duck."
    assert app.last_prompt == "What is a famous dish in Beijing?"
    assert len(app.chat_history) == 1
    assert app.chat_history[-1][1] == "Beijing is famous for Peking duck."

    # Test variable resolution
    assert app.buffer_manager.resolve_text_variable("LAST_RESPONSE") == "Beijing is famous for Peking duck."
    assert app.buffer_manager.resolve_text_variable("LAST_COMPLETION") == "Beijing is famous for Peking duck."

    # Test /save
    target_file = str(tmp_path / "beijing_food.txt")
    await app.handle_escape_command(f"/save {target_file}")
    with open(target_file, "r") as f:
        saved_content = f.read()
    assert saved_content == "Beijing is famous for Peking duck."


@pytest.mark.anyio
async def test_history_off_model_switch_no_prior_messages(app, tmp_path, monkeypatch):
    app.enable_chat_history = False
    captured_calls = []

    async def mock_create(**kwargs):
        captured_calls.append(kwargs.get("messages", []))
        idx = len(captured_calls)
        class MockChoice:
            message = type("Message", (), {"content": f"Answer {idx}", "tool_calls": None})()
        class MockResponse:
            choices = [MockChoice()]
            usage = type("Usage", (), {"prompt_tokens": 5, "completion_tokens": 3})()
        return MockResponse()

    class MockClient:
        class chat:
            class completions:
                create = staticmethod(mock_create)

    monkeypatch.setattr(app, "get_openai_client", lambda *args, **kwargs: MockClient())
    monkeypatch.setattr(app.config_manager, "get_model_config", lambda *args: {"name": "test-model"})

    # Turn 1
    await app.chat_completion("Query 1", stream=False)
    assert captured_calls[0][-1]["content"] == "Query 1"

    # Switch model
    app.selected_model = "another-model"

    # Turn 2
    await app.chat_completion("Query 2", stream=False)
    # Ensure Turn 1 prompt and answer were NOT passed to the second model
    messages_turn_2 = captured_calls[1]
    turn_2_contents = [m["content"] for m in messages_turn_2]
    assert "Query 1" not in turn_2_contents
    assert "Answer 1" not in turn_2_contents
    assert turn_2_contents[-1] == "Query 2"

    # Verify chat_history only holds the latest turn
    assert len(app.chat_history) == 1
    assert app.chat_history[0] == ("Query 2", "Answer 2")

    # Verify /save saves Answer 2 cleanly without error
    target_file = str(tmp_path / "turn2.txt")
    await app.handle_escape_command(f"/save {target_file}")
    with open(target_file, "r") as f:
        assert f.read() == "Answer 2"

