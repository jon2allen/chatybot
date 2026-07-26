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

def test_calculate_tool_direct_result():
    from chatybot.tools.math_utils import calculate
    res = calculate("100 * 4")
    assert res["status"] == "success"
    assert res["result"] == 400
    assert "target_variable" not in res
    assert res["message"] == "Result: 400"

def test_calculate_tool_word_expression():
    from chatybot.tools.math_utils import calculate
    res = calculate("fifty times two")
    assert res["status"] == "success"
    assert res["result"] == 100

def test_calculate_tool_with_target_variable(app):
    from chatybot.tools.math_utils import calculate
    res = calculate("25 + 75", target_variable="total_sum", app=app)
    assert res["status"] == "success"
    assert res["result"] == 100
    assert res["target_variable"] == "total_sum"
    assert str(app.buffer_manager.get_script_var("total_sum")) == "100"

def test_calculate_tool_invalid_expression():
    from chatybot.tools.math_utils import calculate
    res = calculate("100 * cat")
    assert res["status"] == "error"
    assert "Unsupported mathematical term" in res["message"]
    assert res["result"] is None

def test_calculate_tool_mixed_decimal_float():
    from chatybot.tools.math_utils import calculate
    res = calculate("(1/3) * 3.14159 * 15 * 15 * 20")
    assert res["status"] == "success"
    assert "4712.385" in str(res["result"])


def test_calculate_tool_pi_and_exponentiation():
    from chatybot.tools.math_utils import calculate
    res = calculate("1/3 * pi * (15)^2 * 20")
    assert res["status"] == "success"
    assert "4712.38" in str(res["result"])


@pytest.mark.anyio
async def test_calc_multilingual(app, capsys):
    # Test Spanish (es -> ESP)
    app.i18n.set_locale("es")
    await app.handle_escape_command('/calc "cinco + treinta" esp_test')
    assert str(app.buffer_manager.get_script_var("esp_test")) == "35"

    # Test French (fr -> FRE)
    app.i18n.set_locale("fr")
    await app.handle_escape_command('/calc "cinq plus trois" fre_test')
    assert str(app.buffer_manager.get_script_var("fre_test")) == "8"



