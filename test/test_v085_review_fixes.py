"""
test_v085_review_fixes.py - Regression tests for issues identified in v0.8.5 review:
1. replace_file_content bounded mode replacing all occurrences within bounds.
2. normalize_tool_call avoiding false positives on arbitrary single-key dicts in prose.
3. extract_kv_tool_calls ignoring unfenced conversational prose.
4. XML tool-call text stripped from JSON scanner input.
5. _extract_thinking_tokens handling <thinking> tags.
6. /save clean_thinking handling mismatched closing tags without truncating to end of string.
"""

import pytest

from chatybot.chatybot_app import ChatybotApp
from chatybot.tools.file_utils import replace_file_content


def test_replace_file_content_bounded_mode_replaces_all_occurrences(tmp_path):
    target_file = str(tmp_path / "sample.txt")
    initial_content = "header\ntarget\ntarget\ntarget\nfooter\n"
    with open(target_file, "w", encoding="utf-8") as f:
        f.write(initial_content)

    # Replace within lines 2 to 4 (the 3 target lines)
    res = replace_file_content(
        path=target_file,
        target="target",
        replacement="replaced",
        start_line=2,
        end_line=4,
    )
    assert "Success: Replaced 3 occurrence(s)" in res

    with open(target_file, "r", encoding="utf-8") as f:
        new_content = f.read()

    assert new_content == "header\nreplaced\nreplaced\nreplaced\nfooter\n"


def test_normalize_tool_call_avoids_arbitrary_single_key_dict():
    app = ChatybotApp()
    # Arbitrary prose JSON should NOT be treated as a tool call
    prose_json = 'Here is the configuration example:\n{"config": {"nested": true}}\nPlease review it.'
    calls = app.extract_tool_calls(prose_json)
    assert len(calls) == 0

    # Known tool single-key format SHOULD be treated as a tool call
    valid_single_key = '{"list_directory": {"path": "."}}'
    valid_calls = app.extract_tool_calls(valid_single_key)
    assert len(valid_calls) == 1
    assert valid_calls[0]["tool"] == "list_directory"
    assert valid_calls[0]["arguments"] == {"path": "."}


def test_extract_kv_tool_calls_ignores_unfenced_prose():
    app = ChatybotApp()
    # Unfenced conversational prose mentioning tool: and path:
    prose = """I recommend using this tool:
tool: read_file
path: config.json
Note: this reads the configuration file.
"""
    calls = app.extract_tool_calls(prose)
    assert len(calls) == 0

    # Fenced code block with tool: and path: should be extracted
    fenced = """I will read the file:
```yaml
tool: read_file
path: config.json
```
"""
    fenced_calls = app.extract_tool_calls(fenced)
    assert len(fenced_calls) == 1
    assert fenced_calls[0]["tool"] == "read_file"
    assert fenced_calls[0]["arguments"] == {"path": "config.json"}


def test_xml_tool_call_not_re_scanned_by_json_scanner():
    app = ChatybotApp()
    xml_with_json_prose = """
<tool_call>
<function=run_command>
<parameter=command>echo hello</parameter>
</function>
</tool_call>

Also note: {"config": {"nested": true}}
"""
    calls = app.extract_tool_calls(xml_with_json_prose)
    assert len(calls) == 1
    assert calls[0]["tool"] == "run_command"
    assert calls[0]["arguments"] == {"command": "echo hello"}


def test_extract_thinking_tokens_supports_thinking_tags():
    app = ChatybotApp()
    response = "<thinking>\nStep 1: Compute result\n</thinking>\nThe final answer is 42."
    thinking, clean = app._extract_thinking_tokens(response)
    assert thinking == "Step 1: Compute result"
    assert clean == "The final answer is 42."


@pytest.mark.anyio
async def test_save_mismatched_closing_tags_does_not_truncate(tmp_path):
    app = ChatybotApp()
    app.initialize()
    # Mismatched tags: opened with <think>, closed with </thinking>
    app.chat_history = [
        ("Compute answer", "<think>Some inner reasoning</thinking>Final answer is 100."),
    ]
    target_file = str(tmp_path / "mismatched_save.txt")
    result = await app.handle_escape_command(f"/save {target_file}")
    assert result is True

    with open(target_file, "r", encoding="utf-8") as f:
        content = f.read()

    assert content == "Final answer is 100."


def test_extract_tool_calls_dots_function_call():
    app = ChatybotApp()
    sample = """<dots_function_call>
<invoke="find_files">
">
<parameter name="pattern">
*chatdsl*
</parameter>
</invoke>
</dots_function_call>
<dots_function_call>
<invoke="read_file">
<parameter name="path">./src/chatybot/doc/chatdsl_skill.md</parameter>
</invoke>
</dots_function_call>"""
    calls = app.extract_tool_calls(sample)
    assert len(calls) == 2
    assert calls[0] == {"tool": "find_files", "arguments": {"pattern": "*chatdsl*"}}
    assert calls[1] == {"tool": "read_file", "arguments": {"path": "./src/chatybot/doc/chatdsl_skill.md"}}


def test_extract_tool_calls_invoke_equal_multiline_content():
    app = ChatybotApp()
    sample = """<dots_function_call>
<invoke="write_file">
<parameter name="path">/home/user/scratch/test.chatdsl</parameter>
<parameter name="content">
# ChatDSL Script
/setdb 3Kingdoms
/dblog
</parameter>
</invoke>
</dots_function_call>"""
    calls = app.extract_tool_calls(sample)
    assert len(calls) == 1
    assert calls[0]["tool"] == "write_file"
    assert calls[0]["arguments"]["path"] == "/home/user/scratch/test.chatdsl"
    assert "/setdb 3Kingdoms" in calls[0]["arguments"]["content"]


def test_extract_tool_calls_dots_invoke_loose_equals_syntax():
    """Verify loose invoke syntax like <invoke="=" read_file"> from dots_free is recognized."""
    app = ChatybotApp()
    sample = """<think>Let me read the file to understand its structure.
</think>

<dots_function_call>
<invoke="=" read_file">
<parameter name="path">3kingdoms_culture.chatdsl
</parameter>
</invoke>
</dots_function_call>"""
    calls = app.extract_tool_calls(sample)
    assert len(calls) == 1
    assert calls[0]["tool"] == "read_file"
    assert calls[0]["arguments"]["path"] == "3kingdoms_culture.chatdsl"


