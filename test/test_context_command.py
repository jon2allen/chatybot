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
    assert "Last Tool Loop:" in out or "Agentic Loop:" in out
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
    assert "Last Tool Loop:" not in out

    # Test loop scope
    capsys.readouterr()
    await test_app.handle_escape_command("/context loop")
    out = capsys.readouterr().out
    assert "Last Tool Loop:" in out or "Agentic Loop Usage:" in out
    assert "Session History:" not in out


@pytest.mark.anyio
async def test_cmd_context_set_limit_direct_and_off(test_app, capsys):
    capsys.readouterr()
    await test_app.handle_escape_command("/context 10000")
    out = capsys.readouterr().out
    assert "Context limit set to 10000 tokens." in out
    assert test_app.context_limiter.context_limit == 10000

    await test_app.handle_escape_command("/context off")
    out = capsys.readouterr().out
    assert "Context limit disabled." in out
    assert test_app.context_limiter.context_limit is None


@pytest.mark.anyio
async def test_cmd_context_set_limit_via_script_var(test_app, capsys):
    test_app.buffer_manager.set_script_var("my_limit", "10000")
    capsys.readouterr()

    # /context my_limit
    await test_app.handle_escape_command("/context my_limit")
    out = capsys.readouterr().out
    assert "Context limit set to 10000 tokens." in out
    assert test_app.context_limiter.context_limit == 10000

    # /context $my_limit
    test_app.buffer_manager.set_script_var("next_limit", 15000)
    await test_app.handle_escape_command("/context $next_limit")
    out = capsys.readouterr().out
    assert "Context limit set to 15000 tokens." in out
    assert test_app.context_limiter.context_limit == 15000

    # /context_limit via script variable
    test_app.buffer_manager.set_script_var("cfg_limit", "8000")
    await test_app.handle_escape_command("/context_limit cfg_limit")
    out = capsys.readouterr().out
    assert "Context limit set to 8000 tokens." in out
    assert test_app.context_limiter.context_limit == 8000


@pytest.mark.anyio
async def test_cmd_context_save_metrics_to_var(test_app, capsys):
    capsys.readouterr()
    await test_app.handle_escape_command("/context ctx_saved")
    out = capsys.readouterr().out
    assert "ctx_saved =" in out
    saved = test_app.buffer_manager.get_script_var("ctx_saved")
    assert isinstance(saved, dict)
    assert saved.get("status") == "success"
    assert "session" in saved


@pytest.mark.anyio
async def test_context_metrics_includes_system_prompt_and_file_banks(test_app):
    from chatybot.tools.context_utils import get_context_metrics

    test_app.config_manager.system_message = "You are a specialized code reviewer."
    test_app.buffer_manager.file_banks["filebank1"] = "def hello(): pass\n" * 10

    metrics = get_context_metrics(scope="all", app=test_app)
    assert metrics["status"] == "success"
    assert metrics["buffers"]["characters"] > len(test_app.config_manager.system_message)
    assert metrics["buffers"]["estimated_tokens"] > 0


