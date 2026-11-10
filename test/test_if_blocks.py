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


# ============================================================================
# 1. Single-line if with else
# ============================================================================

@pytest.mark.anyio
async def test_single_line_if_else_branch_true(app):
    await run_script(app, """
set X = "10"
if "${X}" > 5 then /setvar res pass else /setvar res fail
""")
    assert app.buffer_manager.get_script_var("res") == "pass"


@pytest.mark.anyio
async def test_single_line_if_else_branch_false(app):
    await run_script(app, """
set X = "2"
if "${X}" > 5 then /setvar res pass else /setvar res fail
""")
    assert app.buffer_manager.get_script_var("res") == "fail"


@pytest.mark.anyio
async def test_single_line_if_quoted_else_in_then_cmd(app):
    await run_script(app, """
set FLAG = "1"
if "${FLAG}" == "1" then set msg = "something else here" else set msg = "other"
""")
    assert app.buffer_manager.get_script_var("msg") == "something else here"


@pytest.mark.anyio
async def test_single_line_if_quoted_else_in_false_branch(app):
    await run_script(app, """
set FLAG = "0"
if "${FLAG}" == "1" then set msg = "something else here" else set msg = "fallback else value"
""")
    assert app.buffer_manager.get_script_var("msg") == "fallback else value"


# ============================================================================
# 2. Block if ... endif (basic & multiline body)
# ============================================================================

@pytest.mark.anyio
async def test_block_if_true_multi_command(app):
    await run_script(app, """
set SCORE = "85"
if "${SCORE}" >= 80 then
    set status = "passed"
    set grade = "A"
endif
""")
    assert app.buffer_manager.get_script_var("status") == "passed"
    assert app.buffer_manager.get_script_var("grade") == "A"


@pytest.mark.anyio
async def test_block_if_false_skipped(app):
    await run_script(app, """
set SCORE = "50"
if "${SCORE}" >= 80 then
    set status = "passed"
    set grade = "A"
endif
""")
    assert app.buffer_manager.get_script_var("status") is None
    assert app.buffer_manager.get_script_var("grade") is None


# ============================================================================
# 3. Block if ... else ... endif
# ============================================================================

@pytest.mark.anyio
async def test_block_if_else_true_path(app):
    await run_script(app, """
set VAL = "100"
if "${VAL}" > 50 then
    set branch = "high"
    set code = "1"
else
    set branch = "low"
    set code = "2"
endif
""")
    assert app.buffer_manager.get_script_var("branch") == "high"
    assert app.buffer_manager.get_script_var("code") == "1"


@pytest.mark.anyio
async def test_block_if_else_false_path(app):
    await run_script(app, """
set VAL = "20"
if "${VAL}" > 50 then
    set branch = "high"
    set code = "1"
else
    set branch = "low"
    set code = "2"
endif
""")
    assert app.buffer_manager.get_script_var("branch") == "low"
    assert app.buffer_manager.get_script_var("code") == "2"


# ============================================================================
# 4. Block if ... elseif ... else ... endif
# ============================================================================

@pytest.mark.anyio
async def test_block_if_elseif_first_branch(app):
    await run_script(app, """
set N = "95"
if "${N}" >= 90 then
    set level = "gold"
elseif "${N}" >= 75 then
    set level = "silver"
else
    set level = "bronze"
endif
""")
    assert app.buffer_manager.get_script_var("level") == "gold"


@pytest.mark.anyio
async def test_block_if_elseif_second_branch(app):
    await run_script(app, """
set N = "80"
if "${N}" >= 90 then
    set level = "gold"
elseif "${N}" >= 75 then
    set level = "silver"
else
    set level = "bronze"
endif
""")
    assert app.buffer_manager.get_script_var("level") == "silver"


@pytest.mark.anyio
async def test_block_if_elif_alias_third_branch(app):
    await run_script(app, """
set N = "60"
if "${N}" >= 90 then
    set level = "gold"
elif "${N}" >= 75 then
    set level = "silver"
elif "${N}" >= 50 then
    set level = "bronze"
else
    set level = "none"
endif
""")
    assert app.buffer_manager.get_script_var("level") == "bronze"


@pytest.mark.anyio
async def test_block_if_elseif_else_fallback(app):
    await run_script(app, """
set N = "30"
if "${N}" >= 90 then
    set level = "gold"
elseif "${N}" >= 75 then
    set level = "silver"
else
    set level = "bronze"
endif
""")
    assert app.buffer_manager.get_script_var("level") == "bronze"


# ============================================================================
# 5. Nested block if
# ============================================================================

@pytest.mark.anyio
async def test_nested_block_if_both_true(app):
    await run_script(app, """
set A = "1"
set B = "1"
if "${A}" == "1" then
    if "${B}" == "1" then
        set outcome = "both_yes"
    else
        set outcome = "A_only"
    endif
else
    set outcome = "neither"
endif
""")
    assert app.buffer_manager.get_script_var("outcome") == "both_yes"


@pytest.mark.anyio
async def test_nested_block_if_inner_false(app):
    await run_script(app, """
set A = "1"
set B = "0"
if "${A}" == "1" then
    if "${B}" == "1" then
        set outcome = "both_yes"
    else
        set outcome = "A_only"
    endif
else
    set outcome = "neither"
endif
""")
    assert app.buffer_manager.get_script_var("outcome") == "A_only"


@pytest.mark.anyio
async def test_nested_block_if_outer_false(app):
    await run_script(app, """
set A = "0"
set B = "1"
if "${A}" == "1" then
    if "${B}" == "1" then
        set outcome = "both_yes"
    else
        set outcome = "A_only"
    endif
else
    set outcome = "neither"
endif
""")
    assert app.buffer_manager.get_script_var("outcome") == "neither"


# ============================================================================
# 6. Integration with foreach & break
# ============================================================================

@pytest.mark.anyio
async def test_block_if_inside_foreach_with_break(app):
    await run_script(app, """
set items[] = ["apple", "STOP", "cherry"]
set collected = ""
foreach item in items
    if "${item}" == "STOP" then
        break
    else
        set collected = "${collected}${item},"
    endif
endfor
""")
    assert app.buffer_manager.get_script_var("collected") == "apple,"


# ============================================================================
# 7. Integration with defproc
# ============================================================================

@pytest.mark.anyio
async def test_block_if_inside_defproc(app):
    await run_script(app, """
defproc classify(score)
    if "${score}" >= 70 then
        set result = "pass"
    else
        set result = "fail"
    endif
endproc

/proc classify score="85"
""")
    assert app.buffer_manager.get_script_var("result") == "pass"

    await run_script(app, """
defproc classify(score)
    if "${score}" >= 70 then
        set result = "pass"
    else
        set result = "fail"
    endif
endproc

/proc classify score="45"
""")
    assert app.buffer_manager.get_script_var("result") == "fail"


# ============================================================================
# 8. Error handling: stray and unclosed blocks
# ============================================================================

@pytest.mark.anyio
async def test_orphan_else_error(app, capsys):
    await run_script(app, """
else
set x = "bad"
""")
    captured = capsys.readouterr()
    assert "Error: 'else' used without matching 'if' block" in captured.out


@pytest.mark.anyio
async def test_orphan_endif_error(app, capsys):
    await run_script(app, """
endif
""")
    captured = capsys.readouterr()
    assert "Error: 'endif' used without matching 'if' block" in captured.out


@pytest.mark.anyio
async def test_unclosed_if_block_error(app, capsys):
    await run_script(app, """
if 5 > 3 then
set x = "incomplete"
""")
    captured = capsys.readouterr()
    assert "Error: Unclosed if block at end of script" in captured.out


@pytest.mark.anyio
async def test_bare_variable_resolution_in_if(app):
    await run_script(app, """
set num_poems = "5"
if num_poems >= 5 then
    set res = "five_or_more"
else
    set res = "less"
endif
""")
    assert app.buffer_manager.get_script_var("res") == "five_or_more"


@pytest.mark.anyio
async def test_calc_with_dollar_target_var(app):
    await run_script(app, """
set num_poems = "5"
/calc "$num_poems + 2" $num_poems
if num_poems == 7 then
    set res = "seven"
endif
""")
    assert app.buffer_manager.get_script_var("res") == "seven"
    assert str(app.buffer_manager.get_script_var("num_poems")) == "7"
