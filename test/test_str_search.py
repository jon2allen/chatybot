import pytest
import anyio
from chatybot.chatybot_app import ChatybotApp
from chatybot.tools.str_utils import str_search


@pytest.fixture
def app():
    return ChatybotApp()


# --- Tool function tests (direct calls) ---

def test_str_search_count_basic():
    res = str_search("error", "this is an error and another error")
    assert res["status"] == "success"
    assert res["result"] == 2
    assert res["count"] == 2
    assert res["mode"] == "c"


def test_str_search_count_case_sensitive():
    res = str_search("Error", "this is an error and Error")
    assert res["status"] == "success"
    assert res["result"] == 1
    assert res["count"] == 1
    assert res["case_insensitive"] is False


def test_str_search_count_case_insensitive():
    res = str_search("Error", "this is an error and Error", case_sensitive=False)
    assert res["status"] == "success"
    assert res["result"] == 2
    assert res["count"] == 2
    assert res["case_insensitive"] is True


def test_str_search_no_match():
    res = str_search("warning", "this is an error")
    assert res["status"] == "success"
    assert res["result"] == 0
    assert res["count"] == 0


def test_str_search_empty_pattern():
    res = str_search("", "some text")
    assert res["status"] == "error"
    assert "empty" in res["message"].lower()


def test_str_search_empty_text():
    res = str_search("error", "")
    assert res["status"] == "success"
    assert res["result"] == 0


def test_str_search_positions_mode():
    res = str_search("ab", "abXabXab", mode="m")
    assert res["status"] == "success"
    assert res["result"] == [(0, 2), (3, 5), (6, 8)]
    assert res["count"] == 3


def test_str_search_positions_mode_case_insensitive():
    res = str_search("ab", "ABab", mode="m", case_sensitive=False)
    assert res["status"] == "success"
    assert res["result"] == [(0, 2), (2, 4)]
    assert res["count"] == 2


def test_str_search_with_target_variable(app):
    res = str_search("cat", "cat dog cat", target_variable="my_matches", app=app)
    assert res["status"] == "success"
    assert res["result"] == 2
    assert res["target_variable"] == "my_matches"
    assert str(app.buffer_manager.get_script_var("my_matches")) == "2"


def test_str_search_positions_with_target_variable(app):
    res = str_search("x", "xYxZx", mode="m", target_variable="pos_list", app=app)
    assert res["status"] == "success"
    assert res["result"] == [(0, 1), (2, 3), (4, 5)]
    stored = app.buffer_manager.get_script_var("pos_list")
    assert stored == [(0, 1), (2, 3), (4, 5)]


def test_str_search_special_regex_chars_escaped():
    res = str_search("a+b", "a+b and ab")
    assert res["status"] == "success"
    assert res["result"] == 1
    assert res["count"] == 1


# --- Slash command tests ---
# In production, handle_escape_command receives raw commands with ${VAR} intact
# (the exclusion list prevents pre-resolution). These tests pass raw commands
# to match that production flow.

@pytest.mark.anyio
async def test_slash_str_search_default_count(app, capsys):
    app.buffer_manager.set_script_var("LOG", "error info error warn error")
    await app.handle_escape_command('/str_search "error" ${LOG}')
    captured = capsys.readouterr()
    assert "Found 3 match(es)" in captured.out
    assert str(app.buffer_manager.get_script_var("STR_SEARCH")) == "3"


@pytest.mark.anyio
async def test_slash_str_search_case_insensitive(app, capsys):
    app.buffer_manager.set_script_var("LOG", "Error error ERROR")
    await app.handle_escape_command('/str_search "error" ${LOG} i')
    captured = capsys.readouterr()
    assert "Found 3 match(es)" in captured.out
    assert str(app.buffer_manager.get_script_var("STR_SEARCH")) == "3"


@pytest.mark.anyio
async def test_slash_str_search_custom_var(app, capsys):
    app.buffer_manager.set_script_var("DATA", "hello world hello")
    await app.handle_escape_command('/str_search "hello" ${DATA} c my_count')
    captured = capsys.readouterr()
    assert "Found 2 match(es)" in captured.out
    assert str(app.buffer_manager.get_script_var("my_count")) == "2"


@pytest.mark.anyio
async def test_slash_str_search_positions_mode(app, capsys):
    app.buffer_manager.set_script_var("TXT", "abXab")
    await app.handle_escape_command('/str_search "ab" ${TXT} m')
    captured = capsys.readouterr()
    assert "Found 2 match(es)" in captured.out
    result = app.buffer_manager.get_script_var("STR_SEARCH")
    assert result == [(0, 2), (3, 5)]


@pytest.mark.anyio
async def test_slash_str_search_combined_flags(app, capsys):
    app.buffer_manager.set_script_var("TXT", "FooFOOfoo")
    await app.handle_escape_command('/str_search "foo" ${TXT} im positions')
    captured = capsys.readouterr()
    assert "Found 3 match(es)" in captured.out
    result = app.buffer_manager.get_script_var("positions")
    assert result == [(0, 3), (3, 6), (6, 9)]


@pytest.mark.anyio
async def test_slash_str_search_no_match(app, capsys):
    app.buffer_manager.set_script_var("TXT", "hello world")
    await app.handle_escape_command('/str_search "xyz" ${TXT}')
    captured = capsys.readouterr()
    assert "Found 0 match(es)" in captured.out
    assert str(app.buffer_manager.get_script_var("STR_SEARCH")) == "0"


@pytest.mark.anyio
async def test_slash_str_search_missing_args(app, capsys):
    await app.handle_escape_command('/str_search')
    captured = capsys.readouterr()
    assert "Usage:" in captured.out


@pytest.mark.anyio
async def test_slash_str_search_undefined_var(app, capsys):
    await app.handle_escape_command('/str_search "test" ${UNDEFINED_VAR}')
    captured = capsys.readouterr()
    assert "not set" in captured.out


@pytest.mark.anyio
async def test_str_search_protected_var(app):
    old_user_write = getattr(app.buffer_manager.script_vars, '_is_user_write', False)
    app.buffer_manager.script_vars._is_user_write = True
    try:
        res = app.buffer_manager.set_script_var("STR_SEARCH", 99)
        assert res is False
    finally:
        app.buffer_manager.script_vars._is_user_write = old_user_write


@pytest.mark.anyio
async def test_slash_str_search_with_variable_substitution(app, capsys):
    app.buffer_manager.set_script_var("pat", "dog")
    app.buffer_manager.set_script_var("TEXT", "cat dog cat dog cat")
    # Pass raw command - handler resolves ${pat} and ${TEXT} internally
    await app.handle_escape_command('/str_search "${pat}" ${TEXT}')
    captured = capsys.readouterr()
    assert "Found 2 match(es)" in captured.out
    assert str(app.buffer_manager.get_script_var("STR_SEARCH")) == "2"
