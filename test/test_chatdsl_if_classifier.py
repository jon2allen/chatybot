"""Unit tests for the shared ChatDSL line classifier (chatybot.chatdsl_if).

Covers the keyword gate, the per-keyword shape heuristics, the
quote-aware first-`then` rule, and a full walk-through of a script that
uses defproc blocks, block if/elseif/else/endif, and foreach.
"""
import pytest

from chatybot.chatdsl_if import (
    SCRIPT_KEYWORDS,
    classify_script_line,
    find_outside_quotes,
)


def cl(line):
    return classify_script_line(line)


# ---------------------------------------------------------------------------
# Baselines: empty / comment / command / prompt
# ---------------------------------------------------------------------------

def test_empty_comment_command_prompt():
    assert cl("").kind == "empty"
    assert cl("   \n").kind == "empty"
    assert cl("# a comment").kind == "comment"
    assert cl("/echo hi").kind == "command"
    assert cl("just some prose").kind == "prompt"
    assert cl("tell me a story").kind == "prompt"


# ---------------------------------------------------------------------------
# if: block vs single-line, first-then rule, $ heuristic
# ---------------------------------------------------------------------------

def test_if_block_open():
    c = cl("if $SCORE >= 90 then")
    assert c.kind == "if_block" and c.is_block
    assert c.condition == "$SCORE >= 90"


def test_if_block_open_with_colon():
    c = cl("if $SCORE >= 90 then:")
    assert c.kind == "if_block" and c.is_block
    assert c.condition == "$SCORE >= 90"


def test_if_single_line():
    c = cl("if $MODE == fast then /setvar plan quick")
    assert c.kind == "if_single" and not c.is_block
    assert c.condition == "$MODE == fast"
    assert c.then_body == "/setvar plan quick"
    assert c.else_body is None


def test_if_single_line_with_else():
    c = cl("if $MODE == slow then /setvar a 1 else /setvar a 2")
    assert c.kind == "if_single"
    assert c.then_body == "/setvar a 1"
    assert c.else_body == "/setvar a 2"


def test_if_first_then_wins_not_last():
    # Line ends with 'then' but the FIRST then terminates the condition.
    c = cl("if $X then /echo then")
    assert c.kind == "if_single"
    assert c.condition == "$X"
    assert c.then_body == "/echo then"


def test_if_prose_with_then_is_prompt():
    c = cl("if you find bug after review then fix")
    assert c.kind == "prompt" and c.keyword == "if"


def test_if_prose_with_operator_is_prompt():
    # Even with a comparison operator, no $var -> prose.
    c = cl("if x > 3 then answer")
    assert c.kind == "prompt" and c.keyword == "if"


def test_if_quoted_then_inside_condition_is_skipped():
    c = cl('if "$A" == "x then y" then /echo hi')
    assert c.kind == "if_single"
    assert c.condition == '"$A" == "x then y"'
    assert c.then_body == "/echo hi"


def test_if_not_prefix_condition_preserved():
    c = cl("if not $ENABLED then /setvar r 1")
    assert c.kind == "if_single"
    assert c.condition == "not $ENABLED"


def test_if_modifier_condition():
    c = cl("if $flag:lower == yes then /setvar r 1")
    assert c.kind == "if_single"
    assert c.condition == "$flag:lower == yes"


def test_if_missing_then_is_invalid_not_prompt():
    c = cl("if $X")
    assert c.kind == "invalid_construct"
    assert c.reason == "missing 'then'"


def test_if_empty_condition_is_invalid():
    c = cl("if then /setvar a b")
    assert c.kind == "invalid_construct"
    assert c.reason == "empty condition"


def test_if_case_insensitive_keyword():
    c = cl("IF $X then /setvar a b")
    assert c.kind == "if_single"
    assert c.condition == "$X"


# ---------------------------------------------------------------------------
# elseif / else / endif
# ---------------------------------------------------------------------------

def test_elseif_block_branch():
    c = cl("elseif $SCORE >= 60 then:")
    assert c.kind == "elseif" and c.is_block
    assert c.condition == "$SCORE >= 60"


def test_elif_alias():
    c = cl("elif $SCORE >= 60 then")
    assert c.kind == "elseif" and c.is_block


def test_elseif_with_inline_body_is_invalid():
    c = cl("elseif $x then /setvar a b")
    assert c.kind == "invalid_construct"


def test_else_exact_and_colon():
    assert cl("else").kind == "else"
    assert cl("else:").kind == "else"


def test_else_with_trailing_text_is_prompt():
    assert cl("else /setvar a b").kind == "prompt"


def test_endif_endfor_exact_and_colon():
    assert cl("endif").kind == "endif"
    assert cl("endif:").kind == "endif"
    assert cl("endfor").kind == "endfor"
    assert cl("endfor:").kind == "endfor"


def test_endif_with_trailing_text_is_prompt():
    assert cl("endif now").kind == "prompt"


# ---------------------------------------------------------------------------
# foreach / defproc / set / wait / local / def / macro / break / endproc
# ---------------------------------------------------------------------------

def test_foreach_constructs():
    c = cl("foreach num in range(1:6:1)")
    assert c.kind == "foreach" and c.item_var == "num" and c.iterable == "range(1:6:1)"
    c = cl("foreach line in lines({filebank1})")
    assert c.kind == "foreach" and c.iterable == "lines({filebank1})"
    c = cl("foreach x in myarray")
    assert c.kind == "foreach" and c.iterable == "myarray"


def test_foreach_prose_is_prompt():
    assert cl("foreach item on the list, discuss").kind == "prompt"
    assert cl("foreach x in my head").kind == "prompt"  # iterable not a var/range/lines


def test_defproc_construct_vs_prose():
    c = cl("defproc handle_high()")
    assert c.kind == "defproc" and c.name == "handle_high"
    assert cl("defproc is short for procedure").kind == "prompt"
    assert cl("endproc").kind == "endproc"


def test_set_construct_vs_prose():
    assert cl('set SCORE = "95"').kind == "set"
    assert cl("set cases[] = [\"a\", \"b\"]").kind == "set"
    assert cl("set the table for dinner").kind == "prompt"


def test_wait_construct_vs_prose():
    assert cl("wait 5").kind == "wait"
    assert cl("wait 1.5").kind == "wait"
    assert cl("wait for it").kind == "prompt"


def test_local_def_macro_break():
    assert cl("local x = 1").kind == "local"
    assert cl("locally speaking").kind == "prompt"
    assert cl('def greet(name) = "hi ${name}"').kind == "macro_def"
    assert cl("%greet(bob)").kind == "macro"
    assert cl("% not a macro").kind == "prompt"
    assert cl("break").kind == "break"


def test_keywords_cover_expected_set():
    assert {"if", "elseif", "elif", "else", "endif", "set", "wait", "local",
            "def", "defproc", "endproc", "foreach", "endfor", "break"} <= SCRIPT_KEYWORDS


# ---------------------------------------------------------------------------
# find_outside_quotes
# ---------------------------------------------------------------------------

def test_find_outside_quotes():
    assert find_outside_quotes('a "x then y" b then c', r"\s+then\b").group(0) == " then"
    assert find_outside_quotes('"then" only', r"\s+then\b") is None
    # An apostrophe opens a quote region (same rule as evaluate_condition),
    # so text after it is treated as quoted.
    assert find_outside_quotes("it's then", r"\s+then\b") is None


# ---------------------------------------------------------------------------
# Full script walk-through (defproc blocks + block if + foreach with if)
# ---------------------------------------------------------------------------

SCRIPT = '''\
defproc handle_high()
  set verdict = "excellent"
  /echo Branch ran: high
endproc

set SCORE = "95"
set verdict = "none"

if $SCORE >= 90 then
    /proc handle_high
elseif $SCORE >= 50 then
    /proc handle_mid
else
    /proc handle_low
endif

foreach num in range(1:6:1)
    if $num >= 4 then
        set label = "big"
    else
        set label = "small"
    endif
    /echo num=${num} -> ${label}
endfor
'''

EXPECTED_KINDS = [
    "defproc", "set", "command", "endproc",
    "set", "set",
    "if_block", "command", "elseif", "command", "else", "command", "endif",
    "foreach", "if_block", "set", "else", "set", "endif", "command", "endfor",
]


def test_full_script_walkthrough():
    kinds = [cl(line).kind for line in SCRIPT.splitlines() if line.strip()]
    assert kinds == EXPECTED_KINDS


def test_walkthrough_if_conditions():
    lines = [l for l in SCRIPT.splitlines() if l.strip()]
    assert cl(lines[6]).condition == "$SCORE >= 90"
    assert cl(lines[8]).condition == "$SCORE >= 50"
    assert cl(lines[14]).condition == "$num >= 4"
    assert cl(lines[13]).kind == "foreach"
