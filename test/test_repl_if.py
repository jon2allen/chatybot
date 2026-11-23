"""REPL (interactive prompt) handling of single-line `if`.

- A real single-line `if <cond> then <cmd>` typed at the prompt runs as a command.
- Prose that starts with `if` is still sent to the model.
- Block `if` is script-only and is refused at the prompt.
- `if`/`set`/`wait` are not reserved chat words, so ordinary prompts reach the model.
"""
from unittest.mock import AsyncMock

import pytest

from chatybot.chatybot_app import ChatybotApp
from chatybot.pattern import PatternMatcher


@pytest.fixture
def app():
    return ChatybotApp()


@pytest.fixture
def chat(app, monkeypatch):
    mock = AsyncMock()
    monkeypatch.setattr(app, "chat_completion", mock)
    return mock


@pytest.mark.anyio
async def test_repl_single_line_if_runs_command(app, chat):
    await app.execute_line('/setvar score 85')
    await app.execute_line('if $score >= 80 then /setvar grade A')
    assert app.buffer_manager.get_script_var("grade") == "A"
    chat.assert_not_called()


@pytest.mark.anyio
async def test_repl_single_line_if_else_branch(app, chat):
    await app.execute_line('/setvar score 10')
    await app.execute_line('if $score >= 80 then /setvar grade A else /setvar grade F')
    assert app.buffer_manager.get_script_var("grade") == "F"
    chat.assert_not_called()


@pytest.mark.anyio
async def test_repl_prose_if_goes_to_model(app, chat):
    await app.execute_line("If you can, summarize this")
    chat.assert_awaited_once()


@pytest.mark.anyio
async def test_repl_if_with_unset_bare_name_is_prose(app, chat):
    await app.execute_line("if x > 3 then answer the question")
    chat.assert_awaited_once()


@pytest.mark.anyio
async def test_repl_block_if_is_refused(app, chat, capsys):
    await app.execute_line("if $score >= 80 then")
    chat.assert_not_called()
    assert "script-only" in capsys.readouterr().out


@pytest.mark.parametrize("word", ["if", "elseif", "elif", "else", "endif", "set", "wait"])
def test_script_words_are_not_reserved_chat_words(app, word):
    assert not app.matcher.pattern.fullmatch(word)


@pytest.mark.anyio
async def test_repl_if_keyword_is_case_insensitive(app, chat):
    await app.execute_line('/setvar score 85')
    await app.execute_line('IF $score >= 80 then /setvar grade A')
    assert app.buffer_manager.get_script_var("grade") == "A"
    chat.assert_not_called()
