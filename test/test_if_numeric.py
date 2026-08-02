import pytest
import anyio
import tempfile
import os
from chatybot.chatybot_app import ChatybotApp


@pytest.fixture
def app():
    return ChatybotApp()


async def run_script(app, script):
    """Helper to execute a script string via temp file."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.chatdsl', delete=False) as f:
        f.write(script)
        f.flush()
        try:
            await app.execute_script(f.name)
        finally:
            os.unlink(f.name)


# --- > operator ---

@pytest.mark.anyio
async def test_if_greater_than_true(app):
    await run_script(app, """
set A = "10"
set B = "5"
if "${A}" > "${B}" then /setvar result yes
""")
    assert app.buffer_manager.get_script_var("result") == "yes"


@pytest.mark.anyio
async def test_if_greater_than_false(app):
    await run_script(app, """
set A = "3"
set B = "7"
if "${A}" > "${B}" then /setvar result yes
""")
    assert app.buffer_manager.get_script_var("result") is None


@pytest.mark.anyio
async def test_if_greater_than_equal(app):
    await run_script(app, """
set A = "5"
set B = "5"
if "${A}" > "${B}" then /setvar result yes
""")
    assert app.buffer_manager.get_script_var("result") is None


# --- < operator ---

@pytest.mark.anyio
async def test_if_less_than_true(app):
    await run_script(app, """
set A = "3"
set B = "7"
if "${A}" < "${B}" then /setvar result yes
""")
    assert app.buffer_manager.get_script_var("result") == "yes"


@pytest.mark.anyio
async def test_if_less_than_false(app):
    await run_script(app, """
set A = "10"
set B = "5"
if "${A}" < "${B}" then /setvar result yes
""")
    assert app.buffer_manager.get_script_var("result") is None


@pytest.mark.anyio
async def test_if_less_than_equal(app):
    await run_script(app, """
set A = "5"
set B = "5"
if "${A}" < "${B}" then /setvar result yes
""")
    assert app.buffer_manager.get_script_var("result") is None


# --- >= operator ---

@pytest.mark.anyio
async def test_if_greater_equal_true_greater(app):
    await run_script(app, """
set A = "10"
set B = "5"
if "${A}" >= "${B}" then /setvar result yes
""")
    assert app.buffer_manager.get_script_var("result") == "yes"


@pytest.mark.anyio
async def test_if_greater_equal_true_equal(app):
    await run_script(app, """
set A = "5"
set B = "5"
if "${A}" >= "${B}" then /setvar result yes
""")
    assert app.buffer_manager.get_script_var("result") == "yes"


@pytest.mark.anyio
async def test_if_greater_equal_false(app):
    await run_script(app, """
set A = "3"
set B = "5"
if "${A}" >= "${B}" then /setvar result yes
""")
    assert app.buffer_manager.get_script_var("result") is None


# --- <= operator ---

@pytest.mark.anyio
async def test_if_less_equal_true_less(app):
    await run_script(app, """
set A = "3"
set B = "5"
if "${A}" <= "${B}" then /setvar result yes
""")
    assert app.buffer_manager.get_script_var("result") == "yes"


@pytest.mark.anyio
async def test_if_less_equal_true_equal(app):
    await run_script(app, """
set A = "5"
set B = "5"
if "${A}" <= "${B}" then /setvar result yes
""")
    assert app.buffer_manager.get_script_var("result") == "yes"


@pytest.mark.anyio
async def test_if_less_equal_false(app):
    await run_script(app, """
set A = "10"
set B = "5"
if "${A}" <= "${B}" then /setvar result yes
""")
    assert app.buffer_manager.get_script_var("result") is None


# --- Floats ---

@pytest.mark.anyio
async def test_if_comparison_floats(app):
    await run_script(app, """
set A = "3.14"
set B = "2.71"
if "${A}" > "${B}" then /setvar result yes
""")
    assert app.buffer_manager.get_script_var("result") == "yes"


@pytest.mark.anyio
async def test_if_comparison_float_equality(app):
    await run_script(app, """
set A = "2.5"
set B = "2.50"
if "${A}" >= "${B}" then /setvar result yes
""")
    assert app.buffer_manager.get_script_var("result") == "yes"


# --- Negative numbers ---

@pytest.mark.anyio
async def test_if_comparison_negative(app):
    await run_script(app, """
set A = "-5"
set B = "3"
if "${A}" < "${B}" then /setvar result yes
""")
    assert app.buffer_manager.get_script_var("result") == "yes"


@pytest.mark.anyio
async def test_if_comparison_negative_both(app):
    await run_script(app, """
set A = "-10"
set B = "-5"
if "${A}" < "${B}" then /setvar result yes
""")
    assert app.buffer_manager.get_script_var("result") == "yes"


# --- Literal numbers (not variables) ---

@pytest.mark.anyio
async def test_if_comparison_literal_number(app):
    await run_script(app, """
set AGE = "25"
if "${AGE}" >= 18 then /setvar status adult
""")
    assert app.buffer_manager.get_script_var("status") == "adult"


@pytest.mark.anyio
async def test_if_comparison_literal_float(app):
    await run_script(app, """
set SCORE = "9.5"
if "${SCORE}" > 9.0 then /setvar passed yes
""")
    assert app.buffer_manager.get_script_var("passed") == "yes"


# --- Non-numeric error cases ---

@pytest.mark.anyio
async def test_if_comparison_non_numeric_error(app, capsys):
    await run_script(app, """
set A = "hello"
set B = "world"
if "${A}" > "${B}" then /setvar result yes
""")
    captured = capsys.readouterr()
    assert "Error: Cannot compare non-numeric values with >" in captured.out
    assert app.buffer_manager.get_script_var("result") is None


@pytest.mark.anyio
async def test_if_comparison_mixed_numeric_error(app, capsys):
    await run_script(app, """
set A = "5"
set B = "hello"
if "${A}" >= "${B}" then /setvar result yes
""")
    captured = capsys.readouterr()
    assert "Error: Cannot compare non-numeric values with >=" in captured.out
    assert app.buffer_manager.get_script_var("result") is None


@pytest.mark.anyio
async def test_if_comparison_empty_var_error(app, capsys):
    await run_script(app, """
set A = ""
set B = "5"
if "${A}" > "${B}" then /setvar result yes
""")
    captured = capsys.readouterr()
    assert "Error: Cannot compare non-numeric values with >" in captured.out


# --- Negation with numeric operators ---

@pytest.mark.anyio
async def test_if_not_greater_than(app):
    await run_script(app, """
set A = "3"
set B = "7"
if not "${A}" > "${B}" then /setvar result yes
""")
    assert app.buffer_manager.get_script_var("result") == "yes"


@pytest.mark.anyio
async def test_if_not_less_than(app):
    await run_script(app, """
set A = "10"
set B = "5"
if not "${A}" < "${B}" then /setvar result yes
""")
    assert app.buffer_manager.get_script_var("result") == "yes"


# --- Integration with /proc ---

@pytest.mark.anyio
async def test_if_numeric_then_proc(app):
    await run_script(app, """
defproc handle_high_score()
set result = "high"
endproc

set SCORE = "95"
if "${SCORE}" >= 90 then /proc handle_high_score
""")
    assert app.buffer_manager.get_script_var("result") == "high"


@pytest.mark.anyio
async def test_if_numeric_else_via_not_proc(app):
    await run_script(app, """
defproc handle_low()
set result = "low"
endproc

set SCORE = "50"
if not "${SCORE}" >= 90 then /proc handle_low
""")
    assert app.buffer_manager.get_script_var("result") == "low"
