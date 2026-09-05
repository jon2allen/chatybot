import pytest
from chatybot.chatybot_app import ChatybotApp


@pytest.fixture
def test_app():
    app = ChatybotApp()
    app.initialize()

    # Populate session history
    app.chat_history = [
        ("Hello, who are you?", "I am Chatybot, your AI assistant."),
        ("What can you do?", "I can help with coding, analysis, and tools.")
    ]

    # Populate agentic loop
    app.buffer_manager.set_script_var("AGENTIC_LOOP", [
        {"turn": 1, "tool": "test_tool", "arguments": {}, "result": "sample", "status": "success"}
    ], allow_protected=True)

    return app


@pytest.mark.anyio
async def test_cmd_context_default_all_no_limit(test_app, capsys):
    test_app.context_limiter.set_limit(None, from_user=True)
    capsys.readouterr()

    await test_app.handle_escape_command("/context")
    out = capsys.readouterr().out

    assert "Context Usage Breakdown:" in out
    assert "Session History:" in out
    assert "2 turns" in out
    assert "Agentic Loop:" in out
    assert "1 tool call" in out
    assert "Context Limit:      Disabled (no limit configured)" in out


@pytest.mark.anyio
async def test_cmd_context_with_limit_and_progress_bar(test_app, capsys):
    test_app.context_limiter.set_limit(1000, from_user=True)
    test_app.context_limiter.set_auto_truncate(True, pct=85.0)
    capsys.readouterr()

    await test_app.handle_escape_command("/ctx")
    out = capsys.readouterr().out

    assert "Context Usage Breakdown:" in out
    assert "/ 1,000 tokens" in out
    assert "Auto-Truncate:      ON (85%)" in out
    assert "█" in out or "░" in out


@pytest.mark.anyio
async def test_cmd_context_specific_scopes(test_app, capsys):
    # Test session scope
    await test_app.handle_escape_command("/context session")
    out = capsys.readouterr().out
    assert "Session History:" in out
    assert "Agentic Loop:" not in out

    # Test loop scope
    capsys.readouterr()
    await test_app.handle_escape_command("/context loop")
    out = capsys.readouterr().out
    assert "Agentic Loop:" in out
    assert "Session History:" not in out
