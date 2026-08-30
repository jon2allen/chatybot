"""Tests for the modular command registry, context, and the /echo migration.

These validate the "sweet spot" Phase 1 foundation:
- registry registration / lookup / alias / fall-through semantics
- CommandResult typed returns and the legacy-contract adapter
- /echo migrated to the registry produces identical output to the legacy
  behavior, including variable substitution, quote stripping, empty input,
  and localized alias dispatch (/repetir, /回显, /eco, /ترديد).
"""

import pytest

from chatybot.commands.registry import (
    CommandRegistry,
    CommandResult,
    CommandAction,
    command,
    registry as default_registry,
)
from chatybot.commands.context import CommandContext
from chatybot.chatybot_app import ChatybotApp


# ---------------------------------------------------------------------------
# Registry mechanics
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_registry_register_and_get():
    reg = CommandRegistry()

    async def handler(ctx, parts, command):
        return CommandResult.ok()

    reg.register("/foo", handler, help="foo", aliases=["/f"])
    assert reg.has("/foo")
    assert reg.has("/f")  # alias
    assert reg.get("/foo").name == "/foo"
    assert reg.get("/f").name == "/foo"  # alias resolves to primary
    assert reg.get("/missing") is None


def test_registry_fall_through_returns_none():
    """Unregistered commands return None so the caller can fall through."""
    reg = CommandRegistry()
    assert reg.get("/not-registered") is None


def test_default_registry_has_echo():
    """Importing chatybot.commands registers /echo into the default registry."""
    assert default_registry.has("/echo")


# ---------------------------------------------------------------------------
# CommandResult / adapter
# ---------------------------------------------------------------------------

def test_command_result_constructors():
    assert CommandResult.ok().action == CommandAction.HANDLED
    assert CommandResult.ok("hi").message == "hi"
    assert CommandResult.execute_prompt("p").action == CommandAction.EXECUTE_PROMPT
    assert CommandResult.execute_prompt("p").prompt_to_execute == "p"
    assert CommandResult.error("boom").action == CommandAction.ERROR
    assert CommandResult.exit().action == CommandAction.EXIT


@pytest.mark.anyio
async def test_adapt_command_result_handled():
    app = ChatybotApp()
    app.initialize()
    assert app._adapt_command_result(CommandResult.ok()) is True


@pytest.mark.anyio
async def test_adapt_command_result_execute_prompt():
    app = ChatybotApp()
    app.initialize()
    assert app._adapt_command_result(CommandResult.execute_prompt("x")) == "EXECUTE_PROMPT"


# ---------------------------------------------------------------------------
# /echo migration: behavior parity with the legacy implementation
# ---------------------------------------------------------------------------

def _make_app(capsys=None):
    app = ChatybotApp()
    app.initialize()
    # initialize() may emit a LoggingManager warning to stdout; clear it so
    # later capsys reads only capture command output.
    if capsys is not None:
        capsys.readouterr()
    return app


@pytest.mark.anyio
async def test_echo_basic(capsys):
    app = _make_app(capsys)
    result = await app.handle_escape_command("/echo hello world")
    out = capsys.readouterr().out
    assert result is True
    assert out.strip() == "hello world"


@pytest.mark.anyio
async def test_echo_quoted_strips_quotes(capsys):
    app = _make_app(capsys)
    await app.handle_escape_command('/echo "hello"')
    assert capsys.readouterr().out.strip() == "hello"

    await app.handle_escape_command("/echo 'hello'")
    assert capsys.readouterr().out.strip() == "hello"


@pytest.mark.anyio
async def test_echo_empty_prints_blank(capsys):
    app = _make_app(capsys)
    result = await app.handle_escape_command("/echo")
    assert result is True
    assert capsys.readouterr().out == "\n"


@pytest.mark.anyio
async def test_echo_variable_substitution(capsys):
    app = _make_app(capsys)
    app.buffer_manager.set_script_var("MY_VAR", "chatybot")
    await app.handle_escape_command("/echo value=${MY_VAR}")
    assert capsys.readouterr().out.strip() == "value=chatybot"


@pytest.mark.anyio
async def test_echo_preserves_internal_whitespace(capsys):
    """Regression guard: /echo uses command.split(maxsplit=1)[1], which
    preserves internal spacing that maxsplit=2 would collapse."""
    app = _make_app(capsys)
    await app.handle_escape_command("/echo a   b   c")
    assert capsys.readouterr().out.strip() == "a   b   c"


# ---------------------------------------------------------------------------
# /echo via localized aliases (i18n resolution before registry lookup)
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_echo_spanish_alias(capsys):
    app = ChatybotApp(lang="spanish")
    app.initialize()
    capsys.readouterr()
    result = await app.handle_escape_command('/repetir "hola"')
    assert result is True
    assert capsys.readouterr().out.strip() == "hola"


@pytest.mark.anyio
async def test_echo_chinese_alias(capsys):
    app = ChatybotApp(lang="chinese")
    app.initialize()
    capsys.readouterr()
    result = await app.handle_escape_command('/回显 "你好"')
    assert result is True
    assert capsys.readouterr().out.strip() == "你好"


@pytest.mark.anyio
async def test_echo_italian_alias(capsys):
    app = ChatybotApp(lang="italian")
    app.initialize()
    capsys.readouterr()
    result = await app.handle_escape_command('/eco "ciao"')
    assert result is True
    assert capsys.readouterr().out.strip() == "ciao"


@pytest.mark.anyio
async def test_echo_arabic_alias(capsys):
    app = ChatybotApp(lang="arabic")
    app.initialize()
    capsys.readouterr()
    result = await app.handle_escape_command('/ترديد "marhaba"')
    assert result is True
    assert capsys.readouterr().out.strip() == "marhaba"


@pytest.mark.anyio
async def test_echo_english_alias_resolves_cross_locale(capsys):
    """English manager can resolve a Chinese alias (cross-locale fallback)."""
    app = ChatybotApp(lang="english")
    app.initialize()
    capsys.readouterr()
    result = await app.handle_escape_command('/回显 "hello"')
    assert result is True
    assert capsys.readouterr().out.strip() == "hello"


# ---------------------------------------------------------------------------
# Fall-through: unmigrated commands still hit the legacy elif chain
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_unmigrated_command_still_works(capsys):
    """/help is NOT in the registry; it must fall through to the legacy chain."""
    app = _make_app(capsys)
    result = await app.handle_escape_command("/help")
    assert result is True
    out = capsys.readouterr().out
    assert len(out) > 0  # help text printed
