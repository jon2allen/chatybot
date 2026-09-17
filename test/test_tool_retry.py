"""
test_tool_retry.py - Unit tests for /tool retry [edit|fix|run] post-turn tool rescue feature.
"""

import json
from unittest.mock import AsyncMock, patch

import pytest

from chatybot.chatybot_app import ChatybotApp
from chatybot.commands.context import CommandContext
from chatybot.commands.tools import (
    _build_tool_retry_buffer,
    _extract_retry_candidate,
    cmd_tool,
)


def test_extract_retry_candidate_from_valid_json():
    app = ChatybotApp()
    raw = 'Here is the tool call: {"tool": "list_directory", "arguments": {"path": "/tmp"}}'
    candidate = _extract_retry_candidate(raw, app)
    assert candidate["tool"] == "list_directory"
    assert candidate["arguments"] == {"path": "/tmp"}
    assert candidate["is_valid"] is True


def test_extract_retry_candidate_from_xml_invoke():
    app = ChatybotApp()
    raw = """<dots_function_call>
<invoke="write_file">
">
<parameter name="path">/scratch/script.chatdsl</parameter>
<parameter name="content">
# ChatDSL content
/setdb 3Kingdoms
</parameter>
</invoke>
</dots_function_call>"""
    candidate = _extract_retry_candidate(raw, app)
    assert candidate["tool"] == "write_file"
    assert candidate["arguments"]["path"] == "/scratch/script.chatdsl"
    assert "/setdb 3Kingdoms" in candidate["arguments"]["content"]
    assert candidate["is_valid"] is True


def test_extract_retry_candidate_from_bash_fence():
    app = ChatybotApp()
    raw = """I will run the command for you:
```bash
find / -name "chatdsl_skill.md" 2>/dev/null
```"""
    candidate = _extract_retry_candidate(raw, app)
    assert candidate["tool"] == "run_command"
    assert candidate["arguments"]["command"] == 'find / -name "chatdsl_skill.md" 2>/dev/null'
    assert candidate["is_valid"] is True


def test_extract_retry_candidate_from_escaped_bash_fence():
    app = ChatybotApp()
    raw = r'I will list the contents for you: ```bash\nls -la scratch/retry_test\n```'
    candidate = _extract_retry_candidate(raw, app)
    assert candidate["tool"] == "run_command"
    assert candidate["arguments"]["command"] == 'ls -la scratch/retry_test'
    assert candidate["is_valid"] is True



def test_extract_retry_candidate_unknown_tool():
    app = ChatybotApp()
    raw = """<action="custom_magic_tool">
<parameter name="foo">bar</parameter>
</action>"""
    candidate = _extract_retry_candidate(raw, app)
    assert candidate["tool"] == "custom_magic_tool"
    assert candidate["arguments"]["foo"] == "bar"
    assert candidate["is_valid"] is False


def test_build_tool_retry_buffer_valid_tool():
    app = ChatybotApp()
    candidate = {
        "tool": "write_file",
        "arguments": {"path": "/tmp/test.txt", "content": "Hello World"},
        "is_valid": True,
    }
    raw_completion = "Some explanation before call:\n<invoke=write_file>\n<parameter name=\"path\">/tmp/test.txt</parameter>\n</invoke>"
    buf = _build_tool_retry_buffer(candidate, app, raw_text=raw_completion)
    assert "# Target Tool: write_file" in buf
    assert "# PARAMETER SCHEMA:" in buf
    assert "# ORIGINAL COMPLETION / RAW TOOL CALL (LAST_COMPLETION):" in buf
    assert "# <invoke=write_file>" in buf
    assert '"tool": "write_file"' in buf
    assert '"path": "/tmp/test.txt"' in buf


def test_build_tool_retry_buffer_invalid_tool_has_warning():
    app = ChatybotApp()
    candidate = {
        "tool": "save_script_unknown",
        "arguments": {"path": "/tmp/test.txt"},
        "is_valid": False,
    }
    buf = _build_tool_retry_buffer(candidate, app)
    assert "WARNING: 'save_script_unknown' is NOT a recognized/enabled tool name!" in buf
    assert "# AVAILABLE ENABLED TOOLS:" in buf
    assert "write_file" in buf


@pytest.mark.anyio
async def test_tool_retry_run_mode_dispatches_valid_call():
    app = ChatybotApp()
    app.initialize()
    app.buffer_manager.set_script_var(
        "LAST_COMPLETION",
        '{"tool": "list_directory", "arguments": {"path": "."}}',
        allow_protected=True,
    )
    app.dispatch_tool = AsyncMock(return_value="Dispatched")

    ctx = CommandContext(
        buffer_manager=app.buffer_manager,
        config_manager=app.config_manager,
        i18n=app.i18n,
        session_store=app._get_session_store(),
        app=app,
    )

    result = await cmd_tool(ctx, ["/tool", "retry", "run"], "/tool retry run")
    assert result is not None
    app.dispatch_tool.assert_called_once()
    called_arg = json.loads(app.dispatch_tool.call_args[0][0])
    assert called_arg["tool"] == "list_directory"
    assert called_arg["arguments"] == {"path": "."}


@pytest.mark.anyio
async def test_tool_retry_edit_mode_executes_on_editor_save():
    app = ChatybotApp()
    app.initialize()
    app.buffer_manager.set_script_var(
        "LAST_COMPLETION",
        '<invoke="write_file"><parameter name="path">/tmp/out.txt</parameter><parameter name="content">hello</parameter></invoke>',
        allow_protected=True,
    )
    app.dispatch_tool = AsyncMock(return_value="Dispatched")

    # Mock subprocess.run to simulate user saving a corrected JSON in editor
    def mock_subprocess_run(cmd, *args, **kwargs):
        temp_file = cmd[-1]
        edited_content = """# Comments
{
  "tool": "write_file",
  "arguments": {
    "path": "/tmp/custom.txt",
    "content": "custom content"
  }
}"""
        with open(temp_file, "w", encoding="utf-8") as f:
            f.write(edited_content)

    with patch("subprocess.run", side_effect=mock_subprocess_run):
        ctx = CommandContext(
            buffer_manager=app.buffer_manager,
            config_manager=app.config_manager,
            i18n=app.i18n,
            session_store=app._get_session_store(),
            app=app,
        )
        await cmd_tool(ctx, ["/tool", "retry", "edit"], "/tool retry edit")

    app.dispatch_tool.assert_called_once()
    dispatched = json.loads(app.dispatch_tool.call_args[0][0])
    assert dispatched["tool"] == "write_file"
    assert dispatched["arguments"]["path"] == "/tmp/custom.txt"
    assert dispatched["arguments"]["content"] == "custom content"


@pytest.mark.anyio
async def test_tool_inject_literal_text():
    app = ChatybotApp()
    app.initialize()
    ctx = CommandContext(
        buffer_manager=app.buffer_manager,
        config_manager=app.config_manager,
        i18n=app.i18n,
        session_store=app._get_session_store(),
        app=app,
    )

    cmd = '/tool inject <invoke name="write_file"><parameter name="path">test.py</parameter></invoke>'
    result = await cmd_tool(ctx, ["/tool", "inject", '<invoke name="write_file"><parameter name="path">test.py</parameter></invoke>'], cmd)
    assert result is not None

    last_comp = app.buffer_manager.get_script_var("LAST_COMPLETION")
    assert '<invoke name="write_file">' in last_comp
    assert '<parameter name="path">test.py</parameter>' in last_comp
    assert app.chat_history[-1] == ("assistant", '<invoke name="write_file"><parameter name="path">test.py</parameter></invoke>')


@pytest.mark.anyio
async def test_tool_inject_file(tmp_path):
    app = ChatybotApp()
    app.initialize()
    ctx = CommandContext(
        buffer_manager=app.buffer_manager,
        config_manager=app.config_manager,
        i18n=app.i18n,
        session_store=app._get_session_store(),
        app=app,
    )

    test_file = tmp_path / "mock_turn.txt"
    test_file.write_text('{"tool": "list_directory", "arguments": {"path": "/var/log"}}', encoding="utf-8")

    cmd = f'/tool inject file={test_file}'
    result = await cmd_tool(ctx, ["/tool", "inject", f"file={test_file}"], cmd)
    assert result is not None

    last_comp = app.buffer_manager.get_script_var("LAST_COMPLETION")
    assert '"tool": "list_directory"' in last_comp
    assert '"path": "/var/log"' in last_comp


@pytest.mark.anyio
async def test_tool_inject_and_retry_chain():
    app = ChatybotApp()
    app.initialize()
    app.dispatch_tool = AsyncMock(return_value="Dispatched")
    ctx = CommandContext(
        buffer_manager=app.buffer_manager,
        config_manager=app.config_manager,
        i18n=app.i18n,
        session_store=app._get_session_store(),
        app=app,
    )

    # 1. Inject
    inject_cmd = '/tool inject {"tool": "list_directory", "arguments": {"path": "/src"}}'
    await cmd_tool(ctx, ["/tool", "inject", '{"tool": "list_directory", "arguments": {"path": "/src"}}'], inject_cmd)

    # 2. Retry run
    retry_cmd = '/tool retry run'
    await cmd_tool(ctx, ["/tool", "retry", "run"], retry_cmd)

    app.dispatch_tool.assert_called_once()
    called_arg = json.loads(app.dispatch_tool.call_args[0][0])
    assert called_arg["tool"] == "list_directory"
    assert called_arg["arguments"] == {"path": "/src"}


@pytest.mark.anyio
async def test_tool_retry_records_in_agentic_loop_and_session():
    app = ChatybotApp()
    app.initialize()
    app.session_turns = [{"turn_id": 1, "prompt": "test prompt", "response": "test resp", "agentic_loop": []}]
    app.buffer_manager.set_script_var(
        "LAST_COMPLETION",
        '{"tool": "list_directory", "arguments": {"path": "/tmp"}}',
        allow_protected=True,
    )
    app.dispatch_tool = AsyncMock(return_value='{"status": "success", "files": ["a.txt", "b.txt"]}')

    ctx = CommandContext(
        buffer_manager=app.buffer_manager,
        config_manager=app.config_manager,
        i18n=app.i18n,
        session_store=app._get_session_store(),
        app=app,
    )

    await cmd_tool(ctx, ["/tool", "retry", "run"], "/tool retry run")

    # Check AGENTIC_LOOP
    agentic_loop = app.buffer_manager.get_script_var("AGENTIC_LOOP")
    assert isinstance(agentic_loop, list)
    assert len(agentic_loop) == 1
    assert agentic_loop[0]["tool"] == "list_directory"
    assert agentic_loop[0]["status"] == "success"

    # Check session turn attachment
    assert len(app.session_turns[0]["agentic_loop"]) == 1
    assert app.session_turns[0]["agentic_loop"][0]["tool"] == "list_directory"

    # Check LAST_TOOL_RESCUED variable
    last_rescued = app.buffer_manager.get_script_var("LAST_TOOL_RESCUED")
    assert last_rescued["tool"] == "list_directory"


@pytest.mark.anyio
async def test_tool_continue_resumes_loop():
    from chatybot.commands.tools import cmd_continue

    app = ChatybotApp()
    app.initialize()
    app.run_tool_loop = AsyncMock()

    tool_rec = {
        "turn": 1,
        "tool": "read_file",
        "arguments": {"path": "test.txt"},
        "result": "file contents here",
        "status": "success",
    }
    app.buffer_manager.set_script_var("LAST_TOOL_RESCUED", tool_rec, allow_protected=True)

    ctx = CommandContext(
        buffer_manager=app.buffer_manager,
        config_manager=app.config_manager,
        i18n=app.i18n,
        session_store=app._get_session_store(),
        app=app,
    )

    # Test /tool continue
    await cmd_tool(ctx, ["/tool", "continue"], "/tool continue")
    app.run_tool_loop.assert_called_once()
    assert "Tool: read_file" in app.run_tool_loop.call_args[1]["initial_tool_results"]
    assert "file contents here" in app.run_tool_loop.call_args[1]["initial_tool_results"]

    # Test /continue shorthand
    app.run_tool_loop.reset_mock()
    await cmd_continue(ctx, ["/continue", "15"], "/continue 15")
    app.run_tool_loop.assert_called_once()
    assert app.run_tool_loop.call_args[1]["max_turns"] == 15


