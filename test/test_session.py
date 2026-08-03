import os
import json
import pytest
import tempfile
import asyncio
from chatybot.chatybot_app import ChatybotApp

@pytest.fixture
def app():
    app_instance = ChatybotApp()
    app_instance.session_dir = tempfile.mkdtemp()
    app_instance.initialize()
    return app_instance

@pytest.mark.anyio
async def test_session_start_and_append(app):
    await app.handle_escape_command("/session start unit_test_session")
    assert app.active_session_name == "unit_test_session"
    assert app.active_session_id is not None
    assert app.buffer_manager.script_vars.get("SESSION_NAME") == "unit_test_session"

    app.append_session_turn("What is Python?", "Python is a programming language.")
    assert len(app.session_turns) == 1
    assert app.session_turns[0]["prompt"] == "What is Python?"
    assert app.session_turns[0]["response"] == "Python is a programming language."

    # Verify JSON file written to disk
    session_file = os.path.join(app.get_sessions_dir(), f"{app.active_session_id}.json")
    assert os.path.exists(session_file)

    with open(session_file, "r", encoding="utf-8") as f:
        data = json.load(f)
        assert data["custom_name"] == "unit_test_session"
        assert len(data["turns"]) == 1

@pytest.mark.anyio
async def test_session_use_and_load(app):
    await app.handle_escape_command("/session start load_test")
    app.append_session_turn("First prompt", "First response")
    app.append_session_turn("Second prompt", "Second response")

    session_id = app.active_session_id

    # Reset in-memory chat state
    app.chat_history.clear()
    app.session_turns.clear()
    app.active_session_id = None

    # Load session back
    await app.handle_escape_command(f"/session use {session_id}")
    assert app.active_session_id == session_id
    assert len(app.session_turns) == 2
    assert len(app.chat_history) == 2
    assert app.chat_history[0] == ("First prompt", "First response")

@pytest.mark.anyio
async def test_session_export_markdown(app, capsys):
    await app.handle_escape_command("/session start export_test")
    app.append_session_turn("Explain async", "<think>Thinking about async...</think>Async is non-blocking.")

    export_path = os.path.join(app.session_dir, "test_export.md")
    await app.handle_escape_command(f"/session export {export_path} -t")

    assert os.path.exists(export_path)
    with open(export_path, "r", encoding="utf-8") as f:
        content = f.read()
        assert "# Session Transcript: export_test" in content
        assert "Explain async" in content
        assert "> Thinking about async..." in content
        assert "Async is non-blocking." in content

@pytest.mark.anyio
async def test_session_list_and_status(app, capsys):
    await app.handle_escape_command("/session start list_test")
    app.append_session_turn("Test prompt for slug generation", "Test response")

    await app.handle_escape_command("/session list")
    captured = capsys.readouterr()
    assert "list_test" in captured.out
    assert "Prompt:" in captured.out

    await app.handle_escape_command("/session status")
    captured_status = capsys.readouterr()
    assert "Active Session ID:" in captured_status.out
    assert "Turn Count: 1" in captured_status.out
