#!/usr/bin/env python3
"""
Unit tests for ChatDSL Procedure System (defproc / endproc / /proc / local).
"""

import os
import tempfile
import pytest
from chatybot.chatybot_app import ChatybotApp


@pytest.fixture
def app():
    """Fixture providing a initialized ChatybotApp instance."""
    app_inst = ChatybotApp()
    return app_inst


@pytest.mark.anyio
async def test_unblocked_script_param_names(app):
    """Verify script/proc parameter pattern accepts any valid identifier."""
    with tempfile.NamedTemporaryFile("w+", suffix=".chatdsl", delete=False) as f:
        f.write('/setvar output "${my_lang}_${target_file}"\n')
        f.flush()
        temp_path = f.name

    try:
        cmd = f'/script {temp_path} my_lang="Python" target_file="main.py"'
        result = await app.handle_escape_command(cmd)
        assert result is True
        assert app.buffer_manager.script_vars.get("my_lang") == "Python"
        assert app.buffer_manager.script_vars.get("target_file") == "main.py"
        assert app.buffer_manager.script_vars.get("output") == "Python_main.py"
    finally:
        os.unlink(temp_path)


@pytest.mark.anyio
async def test_inline_defproc_and_call(app):
    """Test defining a procedure inline and calling it via /proc."""
    script = """
defproc greet(first_name, last_name)
set full_name = "${first_name} ${last_name}"
set greeting = "Hello ${full_name}!"
endproc

/proc greet first_name="John" last_name="Doe"
"""
    with tempfile.NamedTemporaryFile("w+", suffix=".chatdsl", delete=False) as f:
        f.write(script)
        f.flush()
        temp_path = f.name

    try:
        await app.execute_script(temp_path)
        assert "greet" in app.procedures
        assert app.procedures["greet"]["params"] == ["first_name", "last_name"]
        assert app.buffer_manager.script_vars.get("full_name") == "John Doe"
        assert app.buffer_manager.script_vars.get("greeting") == "Hello John Doe!"
    finally:
        os.unlink(temp_path)


@pytest.mark.anyio
async def test_local_variable_scoping(app):
    """Verify local variables do not bleed out and restore pre-call state."""
    app.buffer_manager.script_vars["mode"] = "global_mode"
    app.buffer_manager.script_vars["temp_var"] = "pre_existing"

    script = """
defproc test_scope(param_a)
local temp_var = "inside_proc"
local mode = "proc_mode"
local new_local = "should_be_deleted"
set PROC_RESULT = "${param_a}_${mode}_${temp_var}"
endproc

/proc test_scope param_a="value1"
"""
    with tempfile.NamedTemporaryFile("w+", suffix=".chatdsl", delete=False) as f:
        f.write(script)
        f.flush()
        temp_path = f.name

    try:
        await app.execute_script(temp_path)
        # Check PROC_RESULT captured the local variables during execution
        assert app.buffer_manager.script_vars.get("PROC_RESULT") == "value1_proc_mode_inside_proc"
        # Check global variables are restored post-execution
        assert app.buffer_manager.script_vars.get("mode") == "global_mode"
        assert app.buffer_manager.script_vars.get("temp_var") == "pre_existing"
        # Check variables that didn't exist before call are deleted
        assert "new_local" not in app.buffer_manager.script_vars
        assert "param_a" not in app.buffer_manager.script_vars
    finally:
        os.unlink(temp_path)


@pytest.mark.anyio
async def test_out_parameter_return_pattern(app):
    """Test returning values using out=varname pattern."""
    script = """
defproc compute_sum(a, b, out)
local result = "sum_is_calculated"
set ${out} = "${a}_plus_${b}"
endproc

/proc compute_sum a="5" b="10" out="my_sum"
"""
    with tempfile.NamedTemporaryFile("w+", suffix=".chatdsl", delete=False) as f:
        f.write(script)
        f.flush()
        temp_path = f.name

    try:
        await app.execute_script(temp_path)
        assert app.buffer_manager.script_vars.get("my_sum") == "5_plus_10"
        assert "result" not in app.buffer_manager.script_vars
    finally:
        os.unlink(temp_path)


@pytest.mark.anyio
async def test_recursion_and_saved_vars(app):
    """Verify recursive procedure calls isolate parameters per frame."""
    script = """
defproc countdown(n, out)
local is_zero = "no"
if "${n} == 0" then set is_zero = "yes"
if "${is_zero} == yes" then set ${out} = "done"
if "${is_zero} == no" then /setvar next_n ${n}
if "${is_zero} == no" then /calc "${next_n} - 1" next_n
if "${is_zero} == no" then /proc countdown n="${next_n}" out="${out}"
endproc

/proc countdown n="3" out="final_status"
"""
    with tempfile.NamedTemporaryFile("w+", suffix=".chatdsl", delete=False) as f:
        f.write(script)
        f.flush()
        temp_path = f.name

    try:
        await app.execute_script(temp_path)
        assert app.buffer_manager.script_vars.get("final_status") == "done"
    finally:
        os.unlink(temp_path)


@pytest.mark.anyio
async def test_recursion_depth_guard(app, capsys):
    """Test recursion depth limit guard triggers error when PROC_MAX_DEPTH exceeded."""
    app.buffer_manager.script_vars["PROC_MAX_DEPTH"] = "3"

    script = """
defproc infinite_loop()
/proc infinite_loop
endproc

/proc infinite_loop
"""
    with tempfile.NamedTemporaryFile("w+", suffix=".chatdsl", delete=False) as f:
        f.write(script)
        f.flush()
        temp_path = f.name

    try:
        await app.execute_script(temp_path)
        captured = capsys.readouterr()
        assert "Maximum procedure recursion depth of 3 reached" in captured.out
    finally:
        os.unlink(temp_path)


@pytest.mark.anyio
async def test_nested_defproc_error(app, capsys):
    """Verify nested defproc inside a procedure body outputs a hard error."""
    script = """
defproc outer_proc()
defproc inner_proc()
set x = 1
endproc
endproc
"""
    with tempfile.NamedTemporaryFile("w+", suffix=".chatdsl", delete=False) as f:
        f.write(script)
        f.flush()
        temp_path = f.name

    try:
        await app.execute_script(temp_path)
        captured = capsys.readouterr()
        assert "Error: Nested defproc is not allowed." in captured.out
        assert "outer_proc" not in app.procedures
    finally:
        os.unlink(temp_path)


@pytest.mark.anyio
async def test_file_based_proc_fallback(app):
    """Test /proc resolving a procedure file from disk when not in memory."""
    os.makedirs("procs", exist_ok=True)
    file_proc_path = os.path.join("procs", "external_proc.chatdsl")
    with open(file_proc_path, "w", encoding="utf-8") as f:
        f.write('set file_proc_result = "loaded_from_disk_${val}"\n')

    try:
        cmd = '/proc external_proc val="test123"'
        result = await app.handle_escape_command(cmd)
        assert result is True
        assert app.buffer_manager.script_vars.get("file_proc_result") == "loaded_from_disk_test123"
        assert "val" not in app.buffer_manager.script_vars
    finally:
        if os.path.exists(file_proc_path):
            os.unlink(file_proc_path)


@pytest.mark.anyio
async def test_interactive_proc_execution_with_prompts(app):
    """Test /proc executing plain text prompts even when invoked interactively."""
    from unittest.mock import AsyncMock
    app.chat_completion = AsyncMock(return_value="Mocked LLM Response")
    app.procedures["test_prompt_proc"] = {
        "params": [],
        "body": [
            "what are five cities in Italy",
            "what are five cities in Bulgaria"
        ]
    }
    app.script_context = False
    result = await app.handle_escape_command("/proc test_prompt_proc")
    assert result is True
    assert app.chat_completion.call_count == 2
    app.chat_completion.assert_any_call("what are five cities in Italy", stream=app.streaming_enabled)
    app.chat_completion.assert_any_call("what are five cities in Bulgaria", stream=app.streaming_enabled)
    assert app.script_context is False  # Restored after proc finish
