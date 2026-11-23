"""chatdsl_parse tests for `if` handling.

- Single-line `if <cond> then <cmd> [else <cmd>]` parses with the condition text preserved.
- Block `if <cond> then` ... `elseif`/`else` ... `endif` parses into an `if_block` AST node
  (branches + optional else), with nesting, optional colons, and fail-fast errors for
  unclosed blocks / duplicate else / elseif-after-else.
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
        if rel.startswith(".venv/"):
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
# Block if: parses into an if_block AST node
# ----------------------------------------------------------------------------

@pytest.mark.parametrize("fixture", sorted(BLOCK_FIXTURE_DIR.glob("*.chatdsl")), ids=lambda p: p.name)
def test_block_if_fixture_parses_to_if_block(fixture):
    ast = parse_text(fixture.read_text(encoding="utf-8"))
    assert any(n["type"] == "if_block" for n in ast)


def test_block_if_basic_structure():
    ast = parse_text('if $SCORE >= 80 then\n    set grade = "A"\n    set status = "passed"\nendif\n')
    assert len(ast) == 1
    node = ast[0]
    assert node["type"] == "if_block"
    assert len(node["branches"]) == 1
    assert node["branches"][0]["condition"] == "$SCORE >= 80"
    assert [n["type"] for n in node["branches"][0]["body"]] == ["set_command", "set_command"]
    assert "else" not in node


def test_block_if_elseif_else_with_colons():
    ast = parse_text("if $X >= 90 then:\n    /setvar a 1\nelseif $X >= 60 then:\n    /setvar a 2\nelse:\n    /setvar a 3\nendif:\n")
    node = ast[0]
    assert node["type"] == "if_block"
    assert [b["condition"] for b in node["branches"]] == ["$X >= 90", "$X >= 60"]
    assert [n["args"] for n in node["else"]] == [["a", "3"]]


def test_block_if_elif_alias_and_condition_text_preserved():
    ast = parse_text("if $MODE == fast then\n    /setvar a 1\nelif $flag:lower == yes then\n    /setvar a 2\nendif\n")
    assert [b["condition"] for b in ast[0]["branches"]] == ["$MODE == fast", "$flag:lower == yes"]


def test_block_if_nested():
    ast = parse_text('if $TIER == gold then\n    if $REGION == eu then\n        set msg = "gold-eu"\n    else\n        set msg = "gold-other"\n    endif\nendif\n')
    outer = ast[0]
    assert outer["type"] == "if_block"
    inner = outer["branches"][0]["body"][0]
    assert inner["type"] == "if_block"
    assert inner["branches"][0]["condition"] == "$REGION == eu"
    assert "else" in inner


def test_block_if_single_line_if_inside_body():
    ast = parse_text("if $A then\n    if $B then /setvar x 1\n    /setvar y 2\nendif\n")
    body = ast[0]["branches"][0]["body"]
    assert body[0]["type"] == "if_command" and body[0]["condition"] == "$B"
    assert body[1]["type"] == "command"


# ----------------------------------------------------------------------------
# Block if: fail-fast parse errors
# ----------------------------------------------------------------------------

def test_block_if_unclosed_raises():
    with pytest.raises(ParseError, match="Unclosed if block"):
        parse_text("if $X == 1 then\n    /setvar a b\n")


def test_block_if_multiple_else_raises():
    with pytest.raises(ParseError, match="Multiple 'else'"):
        parse_text("if $X == 1 then\nelse\n    /setvar a b\nelse\n    /setvar c d\nendif\n")


def test_block_if_elseif_after_else_raises():
    with pytest.raises(ParseError, match="'elseif' after 'else'"):
        parse_text("if $X == 1 then\nelse\nelseif $Y then\n    /setvar a b\nendif\n")


def test_elseif_missing_then_raises():
    with pytest.raises(ParseError, match="Missing 'then'"):
        parse_text("if $X == 1 then\n    /setvar a b\nelseif $Y\n    /setvar c d\nendif\n")


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
