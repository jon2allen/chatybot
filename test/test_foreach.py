#!/usr/bin/env python3
"""
Unit tests for ChatDSL Multiline Foreach Loop (foreach item in array ... endfor).
"""

import os
import tempfile
import pytest
from chatybot.chatybot_app import ChatybotApp


@pytest.fixture
def app():
    """Fixture providing an initialized ChatybotApp instance."""
    app_inst = ChatybotApp()
    return app_inst


@pytest.mark.anyio
async def test_basic_foreach_loop(app):
    """Test executing a foreach loop over a Python list in ScriptVars."""
    app.buffer_manager.script_vars["fruits"] = ["apple", "banana", "cherry"]
    app.buffer_manager.script_vars["log"] = ""

    script = """
foreach fruit in fruits
set log = "${log}${fruit}_"
endfor
"""
    with tempfile.NamedTemporaryFile("w+", suffix=".chatdsl", delete=False) as f:
        f.write(script)
        f.flush()
        temp_path = f.name

    try:
        await app.execute_script(temp_path)
        assert app.buffer_manager.script_vars.get("log") == "apple_banana_cherry_"
    finally:
        os.unlink(temp_path)


@pytest.mark.anyio
async def test_json_string_array_foreach(app):
    """Test executing foreach over a JSON list string stored in ScriptVars."""
    app.buffer_manager.script_vars["json_items"] = '["one", "two", "three"]'
    app.buffer_manager.script_vars["result"] = ""

    script = """
foreach item in json_items
set result = "${result}${item}-"
endfor
"""
    with tempfile.NamedTemporaryFile("w+", suffix=".chatdsl", delete=False) as f:
        f.write(script)
        f.flush()
        temp_path = f.name

    try:
        await app.execute_script(temp_path)
        assert app.buffer_manager.script_vars.get("result") == "one-two-three-"
    finally:
        os.unlink(temp_path)


@pytest.mark.anyio
async def test_foreach_save_restore_item_var(app):
    """Verify loop variable is snapshotted and restored post-loop."""
    app.buffer_manager.script_vars["letters"] = ["x", "y"]
    app.buffer_manager.script_vars["item"] = "original_item"

    script = """
foreach item in letters
set last_seen = "${item}"
endfor
"""
    with tempfile.NamedTemporaryFile("w+", suffix=".chatdsl", delete=False) as f:
        f.write(script)
        f.flush()
        temp_path = f.name

    try:
        await app.execute_script(temp_path)
        assert app.buffer_manager.script_vars.get("last_seen") == "y"
        # Check original pre-loop value is restored
        assert app.buffer_manager.script_vars.get("item") == "original_item"
    finally:
        os.unlink(temp_path)


@pytest.mark.anyio
async def test_nested_foreach_loops(app):
    """Test nested foreach loops executing outer and inner elements."""
    app.buffer_manager.script_vars["outer_list"] = ["A", "B"]
    app.buffer_manager.script_vars["inner_list"] = ["1", "2"]
    app.buffer_manager.script_vars["combos"] = ""

    script = """
foreach out_item in outer_list
  foreach in_item in inner_list
    set combos = "${combos}${out_item}${in_item}_"
  endfor
endfor
"""
    with tempfile.NamedTemporaryFile("w+", suffix=".chatdsl", delete=False) as f:
        f.write(script)
        f.flush()
        temp_path = f.name

    try:
        await app.execute_script(temp_path)
        assert app.buffer_manager.script_vars.get("combos") == "A1_A2_B1_B2_"
    finally:
        os.unlink(temp_path)


@pytest.mark.anyio
async def test_invalid_or_missing_array_variable(app, capsys):
    """Verify missing or non-array variable prints warning and skips without crashing."""
    app.buffer_manager.script_vars["not_an_array"] = "just_a_string"

    script = """
foreach item in non_existent
set ran = "yes"
endfor

foreach item in not_an_array
set ran = "yes"
endfor
"""
    with tempfile.NamedTemporaryFile("w+", suffix=".chatdsl", delete=False) as f:
        f.write(script)
        f.flush()
        temp_path = f.name

    try:
        await app.execute_script(temp_path)
        captured = capsys.readouterr()
        assert "Warning: '$non_existent' is not a valid array for foreach loop. Skipping." in captured.out
        assert "Warning: '$not_an_array' is not a valid array for foreach loop. Skipping." in captured.out
        assert "ran" not in app.buffer_manager.script_vars
    finally:
        os.unlink(temp_path)


@pytest.mark.anyio
async def test_proc_call_inside_foreach(app):
    """Test calling /proc inside a foreach loop body."""
    app.buffer_manager.script_vars["langs"] = ["Python", "Go"]
    app.buffer_manager.script_vars["reviews"] = ""

    script = """
defproc review(lang)
set reviews = "${reviews}[${lang}_ok]"
endproc

foreach target_lang in langs
/proc review lang="${target_lang}"
endfor
"""
    with tempfile.NamedTemporaryFile("w+", suffix=".chatdsl", delete=False) as f:
        f.write(script)
        f.flush()
        temp_path = f.name

    try:
        await app.execute_script(temp_path)
        assert app.buffer_manager.script_vars.get("reviews") == "[Python_ok][Go_ok]"
    finally:
        os.unlink(temp_path)


@pytest.mark.anyio
async def test_unclosed_foreach_error(app, capsys):
    """Verify unclosed foreach at end of script outputs error message."""
    script = """
foreach item in colors
set x = 1
"""
    with tempfile.NamedTemporaryFile("w+", suffix=".chatdsl", delete=False) as f:
        f.write(script)
        f.flush()
        temp_path = f.name

    try:
        await app.execute_script(temp_path)
        captured = capsys.readouterr()
        assert "Error: Unclosed foreach loop at end of script." in captured.out
    finally:
        os.unlink(temp_path)


@pytest.mark.anyio
async def test_setvar_array_from_last_response_with_markdown_json(app):
    """Verify /setvar var[] ${LAST_RESPONSE} handles markdown code block wrapped JSON."""
    markdown_json = '```json\n[\n "Nanjing Duck",\n "Xiaolongbao"\n]\n```'
    app.chat_history = [("prompt", markdown_json)]

    script = """
/setvar dishes[] ${LAST_RESPONSE}
set result = ""
foreach d in dishes
set result = "${result}${d};"
endfor
"""
    with tempfile.NamedTemporaryFile("w+", suffix=".chatdsl", delete=False) as f:
        f.write(script)
        f.flush()
        temp_path = f.name

    try:
        await app.execute_script(temp_path)
        assert app.buffer_manager.script_vars.get("dishes") == ["Nanjing Duck", "Xiaolongbao"]
        assert app.buffer_manager.script_vars.get("result") == "Nanjing Duck;Xiaolongbao;"
    finally:
        os.unlink(temp_path)
