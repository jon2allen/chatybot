import pytest
import anyio
from chatybot.chatybot_app import ChatybotApp
from chatybot.buffer_manager import BufferManager

@pytest.fixture
def app():
    return ChatybotApp()

@pytest.mark.anyio
async def test_calc_default_protected_calc_var(app, capsys):
    app.buffer_manager.set_script_var("test1", "5")
    # Escape commands run replace_placeholders_legacy in interactive/script execution before handle_escape_command
    cmd = app.buffer_manager.replace_placeholders_legacy('/calc "one plus ${test1}"')
    await app.handle_escape_command(cmd)
    captured = capsys.readouterr()
    assert "CALC = 6" in captured.out
    assert str(app.buffer_manager.get_script_var("CALC")) == "6"

@pytest.mark.anyio
async def test_calc_custom_var(app, capsys):
    await app.handle_escape_command('/calc "2 + 10" test1')
    captured = capsys.readouterr()
    assert "test1 = 12" in captured.out
    assert str(app.buffer_manager.get_script_var("test1")) == "12"

@pytest.mark.anyio
async def test_calc_word_numbers(app, capsys):
    await app.handle_escape_command('/calc "fifty times two" result_var')
    captured = capsys.readouterr()
    assert "result_var = 100" in captured.out
    assert str(app.buffer_manager.get_script_var("result_var")) == "100"

def test_calc_protected_var_prevention(app):
    # Check that CALC is protected from user /setvar command
    old_user_write = getattr(app.buffer_manager.script_vars, '_is_user_write', False)
    app.buffer_manager.script_vars._is_user_write = True
    try:
        res = app.buffer_manager.set_script_var("CALC", 99)
        assert res is False
    finally:
        app.buffer_manager.script_vars._is_user_write = old_user_write

@pytest.mark.anyio
async def test_execute_test22_chatdsl_script(app, capsys):
    await app.execute_script("dsl_test/test22_calc_evaluation.chatdsl")
    captured = capsys.readouterr()
    assert "CALC = 20" in captured.out
    assert "my_var = 40" in captured.out
    assert "calc_sum = 100" in captured.out
    assert "word_calc = 100" in captured.out
    assert "double_calc = 40" in captured.out
    assert "var1 = 7" in captured.out
    assert "Error: 'CALC' is a protected variable" in captured.out

