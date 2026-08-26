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

    # Verify JSONL session storage written to disk
    session_dir = os.path.join(app.get_sessions_dir(), app.active_session_id)
    meta_file = os.path.join(session_dir, "meta.json")
    turns_file = os.path.join(session_dir, "turns.jsonl")
    assert os.path.exists(meta_file)
    assert os.path.exists(turns_file)

    with open(meta_file, "r", encoding="utf-8") as f:
        data = json.load(f)
        assert data["custom_name"] == "unit_test_session"
        assert data["turn_count"] == 1

    with open(turns_file, "r", encoding="utf-8") as f:
        turns = [json.loads(line) for line in f if line.strip()]
        assert len(turns) == 1
        assert turns[0]["prompt"] == "What is Python?"

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
async def test_chat_history_payload_injection(app, monkeypatch):
    """Verify past chat_history exchanges are injected into payload messages."""
    app.chat_history.append(("Who won the world cup in 2022?", "Argentina won the world cup."))
    
    captured_messages = []

    async def mock_create(**kwargs):
        nonlocal captured_messages
        captured_messages = kwargs.get("messages", [])
        class MockChoice:
            message = type("Message", (), {"content": "Understood.", "tool_calls": None})()
        class MockResponse:
            choices = [MockChoice()]
            usage = type("Usage", (), {"prompt_tokens": 10, "completion_tokens": 5})()
        return MockResponse()

    # Mock client completion
    class MockClient:
        class chat:
            class completions:
                create = staticmethod(mock_create)

    monkeypatch.setattr(app, "get_openai_client", lambda *args, **kwargs: MockClient())
    monkeypatch.setattr(app.config_manager, "get_model_config", lambda *args: {"name": "test-model"})

    await app.chat_completion("What language do they speak there?")
    
    # Assert prior exchanges were prepended
    assert len(captured_messages) >= 3
    assert captured_messages[-3]["role"] == "user"
    assert captured_messages[-3]["content"] == "Who won the world cup in 2022?"
    assert captured_messages[-2]["role"] == "assistant"
    assert captured_messages[-2]["content"] == "Argentina won the world cup."
    assert captured_messages[-1]["role"] == "user"
    assert captured_messages[-1]["content"] == "What language do they speak there?"

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
    assert "Prompt: \"test_prompt_for_slug_generation\"" in captured.out

    await app.handle_escape_command("/session status")
    captured_status = capsys.readouterr()
    assert "Active Session ID:" in captured_status.out
    assert "Turn Count: 1" in captured_status.out

@pytest.mark.anyio
async def test_session_info_and_delete(app, capsys):
    await app.handle_escape_command("/session start del_test1")
    app.append_session_turn("P1", "R1")
    
    await app.handle_escape_command("/session start del_test2")
    app.append_session_turn("P2", "R2")

    await app.handle_escape_command("/session info")
    captured = capsys.readouterr()
    assert "Total Sessions:" in captured.out
    assert "Space Consumed:" in captured.out

    # Delete single session explicitly
    await app.handle_escape_command("!echo y | /session delete del_test1")
    await app.handle_escape_command("/session delete del_test1")
    await app.handle_escape_command("/session list")
    captured_list = capsys.readouterr()
    assert "del_test1" not in captured_list.out.split("Available Sessions:")[-1]

@pytest.mark.anyio
async def test_session_merge_compress_prune(app, capsys):
    # Setup session 1
    await app.handle_escape_command("/session start s1")
    app.append_session_turn("Prompt 1", "Resp 1")
    s1_id = app.active_session_id

    # Setup session 2
    await app.handle_escape_command("/session start s2")
    app.append_session_turn("Prompt 2", "Resp 2")
    s2_id = app.active_session_id

    # Test merge
    capsys.readouterr()
    await app.handle_escape_command(f"/session merge merged_target {s1_id} {s2_id}")
    captured = capsys.readouterr()
    assert "Merged 2 sessions" in captured.out

    # Test compress with wildcard pattern
    await app.handle_escape_command("/session compress merged*")
    captured_comp = capsys.readouterr()
    assert "Compressed" in captured_comp.out

    # Test list compressed filter
    await app.handle_escape_command("/session list compressed all")
    captured_compressed_list = capsys.readouterr()
    assert "merged_target" in captured_compressed_list.out
    assert "[compressed]" in captured_compressed_list.out

    # Test uncompress with wildcard glob pattern
    await app.handle_escape_command("/session uncompress merged*")
    captured_uncomp_glob = capsys.readouterr()
    assert "Uncompressed" in captured_uncomp_glob.out

    # Test uncompress all remaining
    await app.handle_escape_command("/session uncompress all")
    captured_uncomp = capsys.readouterr()

    # Test list compressed is now empty
    await app.handle_escape_command("/session list compressed all")
    captured_empty = capsys.readouterr()
    assert "No saved sessions found" in captured_empty.out

    # Test prune
    await app.handle_escape_command("/session prune keep=1")
    captured_prune = capsys.readouterr()
    assert "Pruned" in captured_prune.out

@pytest.mark.anyio
async def test_session_note(app, capsys):
    await app.handle_escape_command("/session start note_test")
    app.append_session_turn("P1", "R1")

    await app.handle_escape_command("/session note Benchmark test run for version 2.0")
    assert app.session_notes == "Benchmark test run for version 2.0"

    await app.handle_escape_command("/session status")
    captured_status = capsys.readouterr()
    assert "Notes: Benchmark test run for version 2.0" in captured_status.out

    await app.handle_escape_command("/session list")
    captured_list = capsys.readouterr()
    assert "Notes: \"Benchmark test run for version 2.0\"" in captured_list.out
