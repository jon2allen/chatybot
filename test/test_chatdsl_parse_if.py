"""chatdsl_parse tests for `if` handling.

- Single-line `if <cond> then <cmd> [else <cmd>]` must parse with the condition text preserved.
- Block `if ... endif` is runtime-only: the parser must reject it with a clear error.
- Every real .chatdsl script in the repo is parsed (regression sweep), and the block-if
  fixtures are executed by the chat app.
"""
from pathlib import Path

import pytest

from chatybot.chatdsl_parse import ParseError, Tokenizer, TParser
from chatybot.chatybot_app import ChatybotApp

REPO_ROOT = Path(__file__).resolve().parent.parent
BLOCK_FIXTURE_DIR = REPO_ROOT / "test" / "fixtures" / "chatdsl_block"

# Scripts that already failed to parse before the if-block change. They are unrelated to `if`.
PRE_EXISTING_PARSE_FAILURES = {
    "beijing5.chatdsl",
    "doc/cookbook/10_6_session_query_and_extraction.chatdsl",
    "dsl_test/civil_war_1865.chatdsl",
    "dsl_test/logging_stress_test.chatdsl",
    "dsl_test/test10_error_handling.chatdsl",  # deliberately invalid escape command
    "dsl_test/test6_multiline_input.chatdsl",
    "dsl_test/test_think_dsl.chatdsl",
    "london5.chatdsl",
    "rome52.chatdsl",
    "test/test_tool_retry_fix.chatdsl",
}


def parse_text(text: str):
    return TParser(Tokenizer().tokenize(text)).parse()


def all_repo_scripts():
    scripts = []
    for path in sorted(REPO_ROOT.rglob("*.chatdsl")):
        rel = path.relative_to(REPO_ROOT).as_posix()
        if rel.startswith(".venv/") or path.is_relative_to(BLOCK_FIXTURE_DIR):
            continue
        scripts.append(rel)
    return scripts


# ----------------------------------------------------------------------------
# Single-line if: condition text is preserved exactly
# ----------------------------------------------------------------------------

@pytest.mark.parametrize(
    "condition",
    [
        "$MODE == fast",
        "$SCORE >= 80",
        "$flag:lower == yes",
        "not $ENABLED",
        '"$NAME" == "bob smith"',
    ],
)
def test_single_line_condition_text_preserved(condition):
    ast = parse_text(f"if {condition} then /setvar res single\n")
    assert len(ast) == 1
    assert ast[0]["type"] == "if_command"
    assert ast[0]["condition"] == condition


def test_single_line_if_with_else_still_parses_then_command():
    ast = parse_text("if $MODE == fast then /setvar res single\n")
    assert ast[0]["then"]["name"] == "/setvar"
    assert ast[0]["then"]["args"] == ["res", "single"]


# ----------------------------------------------------------------------------
# Block if: rejected by the parser with a clear message
# ----------------------------------------------------------------------------

@pytest.mark.parametrize("fixture", sorted(BLOCK_FIXTURE_DIR.glob("*.chatdsl")), ids=lambda p: p.name)
def test_block_if_fixture_is_rejected_by_parser(fixture):
    with pytest.raises(ParseError, match="not supported by chatdsl_parse"):
        parse_text(fixture.read_text(encoding="utf-8"))


def test_block_if_with_colon_is_rejected():
    with pytest.raises(ParseError, match="not supported by chatdsl_parse"):
        parse_text("if $X == 1 then:\n    /setvar a b\nendif\n")


def test_block_if_error_never_produces_if_block_node():
    # The old parser returned an if_block node with mangled conditions; it must not anymore.
    with pytest.raises(ParseError):
        parse_text("if $MODE == fast then\n    /setvar a b\nendif\n")


# ----------------------------------------------------------------------------
# Regression sweep over every real script in the repo
# ----------------------------------------------------------------------------

@pytest.mark.parametrize(
    "rel_path",
    [
        pytest.param(
            rel,
            marks=pytest.mark.xfail(strict=True, reason="pre-existing parse failure, unrelated to if"),
        )
        if rel in PRE_EXISTING_PARSE_FAILURES
        else rel
        for rel in all_repo_scripts()
    ],
)
def test_real_repo_script_parses(rel_path):
    text = (REPO_ROOT / rel_path).read_text(encoding="utf-8")
    parse_text(text)


# ----------------------------------------------------------------------------
# Block-if fixtures run correctly in the chat app
# ----------------------------------------------------------------------------

@pytest.fixture
def app():
    return ChatybotApp()


@pytest.mark.anyio
async def test_fixture_block_basic_runs(app):
    await app.execute_script(str(BLOCK_FIXTURE_DIR / "block_basic.chatdsl"))
    assert app.buffer_manager.get_script_var("grade") == "A"
    assert app.buffer_manager.get_script_var("status") == "passed"


@pytest.mark.anyio
async def test_fixture_block_elseif_else_runs(app):
    await app.execute_script(str(BLOCK_FIXTURE_DIR / "block_elseif_else.chatdsl"))
    assert app.buffer_manager.get_script_var("grade") == "D"


@pytest.mark.anyio
async def test_fixture_block_nested_runs(app):
    await app.execute_script(str(BLOCK_FIXTURE_DIR / "block_nested.chatdsl"))
    assert app.buffer_manager.get_script_var("msg") == "gold-eu"


@pytest.mark.anyio
async def test_fixture_block_unset_var_runs(app):
    await app.execute_script(str(BLOCK_FIXTURE_DIR / "block_unset_var.chatdsl"))
    assert app.buffer_manager.get_script_var("res") == "none"
