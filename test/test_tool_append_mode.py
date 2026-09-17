"""
test_tool_append_mode.py - Unit tests for /tool append_mode (off|full|summary),
format_tool_loop_summary, and robust XML tool tag extraction.
"""

import pytest

from chatybot.chatybot_app import ChatybotApp
from chatybot.commands.context import CommandContext
from chatybot.commands.tools import cmd_tool


def test_xml_extractor_tolerates_missing_space_in_invokename():
    app = ChatybotApp()
    raw = """
    <dots_function_call>
    <invokename="run_command">
    <parameter name="command">cat > 3kingdoms_geo.chatdsl << 'DSLEOF'
    hello
    DSLEOF
    </parameter>
    </invoke>
    </dots_function_call>
    """
    calls = app.extract_tool_calls(raw)
    assert len(calls) == 1
    assert calls[0]["tool"] == "run_command"
    assert "cat > 3kingdoms_geo.chatdsl" in calls[0]["arguments"]["command"]


def test_xml_extractor_parses_json_inside_tool_use_container():
    app = ChatybotApp()
    raw = """
    <tool_use>
    {"name": "write_file", "arguments": {"path": "3kingdoms_sun_quan.chatdsl", "content": "test content"}}
    </tool_use>
    """
    calls = app.extract_tool_calls(raw)
    assert len(calls) == 1
    assert calls[0]["tool"] == "write_file"
    assert calls[0]["arguments"]["path"] == "3kingdoms_sun_quan.chatdsl"
    assert calls[0]["arguments"]["content"] == "test content"


def test_format_tool_loop_summary_redacts_large_content():
    app = ChatybotApp()
    agentic_loop = [
        {
            "tool": "read_file",
            "arguments": {"path": "sample.chatdsl"},
            "status": "success",
            "exit_code": 0,
        },
        {
            "tool": "write_file",
            "arguments": {
                "path": "sample_out.chatdsl",
                "content": "A" * 200,  # > 60 chars
            },
            "status": "success",
            "exit_code": 0,
        },
        {
            "tool": "run_command",
            "arguments": {"command": "false"},
            "status": "error",
            "exit_code": 1,
        }
    ]
    summary = app.format_tool_loop_summary(agentic_loop)
    assert "[Tool Executions]:" in summary
    assert "read_file(path='sample.chatdsl') -> Success" in summary
    assert "write_file(path='sample_out.chatdsl', content=<200 chars>) -> Success" in summary
    assert "run_command(command='false') -> Error (code 1)" in summary


@pytest.mark.anyio
async def test_cmd_tool_append_mode(capsys):
    app = ChatybotApp()
    app.initialize()
    ctx = CommandContext(
        buffer_manager=app.buffer_manager,
        config_manager=app.config_manager,
        i18n=app.i18n,
        session_store=app._get_session_store(),
        app=app,
    )

    # 1. Query current mode (default: summary)
    await cmd_tool(ctx, ["/tool", "append_mode"], "/tool append_mode")
    captured = capsys.readouterr()
    assert "Current tool append mode: summary" in captured.out

    # 2. Set to off
    await cmd_tool(ctx, ["/tool", "append_mode", "off"], "/tool append_mode off")
    captured = capsys.readouterr()
    assert "Tool append mode set to: off" in captured.out
    assert app.tool_append_mode == "off"

    # 3. Set to full
    await cmd_tool(ctx, ["/tool", "append_mode", "full"], "/tool append_mode full")
    captured = capsys.readouterr()
    assert "Tool append mode set to: full" in captured.out
    assert app.tool_append_mode == "full"

    # 4. Set to summary
    await cmd_tool(ctx, ["/tool", "append_mode", "summary"], "/tool append_mode summary")
    captured = capsys.readouterr()
    assert "Tool append mode set to: summary" in captured.out
    assert app.tool_append_mode == "summary"

    # 5. Invalid mode
    await cmd_tool(ctx, ["/tool", "append_mode", "invalid"], "/tool append_mode invalid")
    captured = capsys.readouterr()
    assert "Invalid append mode: 'invalid'" in captured.out


@pytest.mark.anyio
async def test_run_tool_loop_summary_mode():
    app = ChatybotApp()
    app.enable_chat_history = True
    app.tool_append_mode = "summary"
    app.chat_history = [("Generate script", '{"tool": "write_file", "arguments": {"path": "test.txt", "content": "data"}}')]

    # Mock dispatch_tool to record execution and exit code
    async def mock_dispatch(payload):
        app.buffer_manager.set_script_var("TOOL_DISPATCH_EXIT_CODE", 0)
        return "10 bytes written."

    app.dispatch_tool = mock_dispatch

    # Mock chat_completion to return natural language on turn 2
    mock_responses = [
        "Script generated successfully and ready to use.",
    ]
    call_idx = 0

    async def mock_chat(messages, stream=False):
        nonlocal call_idx
        resp = mock_responses[call_idx]
        call_idx += 1
        return resp

    app.chat_completion = mock_chat

    await app.run_tool_loop(max_turns=3)

    assert len(app.chat_history) == 1
    prompt, resp = app.chat_history[0]
    assert prompt == "Generate script"
    assert "[Tool Executions]:" in resp
    assert "write_file(path='test.txt', content='data') -> Success" in resp
    assert "Script generated successfully and ready to use." in resp


@pytest.mark.anyio
async def test_run_tool_loop_full_mode():
    app = ChatybotApp()
    app.enable_chat_history = True
    app.tool_append_mode = "full"
    app.chat_history = [("Generate script", '{"tool": "write_file", "arguments": {"path": "test.txt", "content": "data"}}')]

    async def mock_dispatch(payload):
        app.buffer_manager.set_script_var("TOOL_DISPATCH_EXIT_CODE", 0)
        return "10 bytes written."

    app.dispatch_tool = mock_dispatch

    mock_responses = [
        "Script generated successfully and ready to use.",
    ]
    call_idx = 0

    async def mock_chat(messages, stream=False):
        nonlocal call_idx
        resp = mock_responses[call_idx]
        call_idx += 1
        return resp

    app.chat_completion = mock_chat

    await app.run_tool_loop(max_turns=3)

    # In full mode, all intermediate turns are preserved in chat_history
    assert len(app.chat_history) >= 2
    assert app.chat_history[0][0] == "Generate script"
    assert "write_file" in app.chat_history[0][1]
    assert app.chat_history[-1][1] == "Script generated successfully and ready to use."


@pytest.mark.anyio
async def test_run_tool_loop_off_mode():
    app = ChatybotApp()
    app.enable_chat_history = True
    app.tool_append_mode = "off"
    app.chat_history = [("Generate script", '{"tool": "write_file", "arguments": {"path": "test.txt", "content": "data"}}')]

    async def mock_dispatch(payload):
        app.buffer_manager.set_script_var("TOOL_DISPATCH_EXIT_CODE", 0)
        return "10 bytes written."

    app.dispatch_tool = mock_dispatch

    mock_responses = [
        "Script generated successfully and ready to use.",
    ]
    call_idx = 0

    async def mock_chat(messages, stream=False):
        nonlocal call_idx
        resp = mock_responses[call_idx]
        call_idx += 1
        return resp

    app.chat_completion = mock_chat

    await app.run_tool_loop(max_turns=3)

    assert len(app.chat_history) == 1
    prompt, resp = app.chat_history[0]
    assert prompt == "Generate script"
    assert "[Tool Executions]:" not in resp
    assert resp == "Script generated successfully and ready to use."
