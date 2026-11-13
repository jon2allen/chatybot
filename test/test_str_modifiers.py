"""Tests for string modifiers engine (${var:modifier}) and str_utils."""

import pytest
from chatybot.tools.str_utils import StringModifierError, apply_string_modifier
from chatybot.buffer_manager import BufferManager
from chatybot.chatybot_app import ChatybotApp


# ============================================================================
# 1. str_utils.apply_string_modifier unit tests
# ============================================================================

def test_apply_string_modifier_basic_transforms():
    assert apply_string_modifier("Hello World", "lower") == "hello world"
    assert apply_string_modifier("hello world", "upper") == "HELLO WORLD"
    assert apply_string_modifier("hello world", "title") == "Hello World"
    assert apply_string_modifier("john's book", "title") == "John's Book"
    assert apply_string_modifier("élan vital über", "title") == "Élan Vital Über"
    assert apply_string_modifier("ÉCOLE", "title") == "École"
    assert apply_string_modifier("hello world", "capitalize") == "Hello world"
    assert apply_string_modifier("  spaced  ", "trim") == "spaced"
    assert apply_string_modifier("  spaced  ", "strip") == "spaced"
    assert apply_string_modifier("  left", "ltrim") == "left"
    assert apply_string_modifier("right  ", "rtrim") == "right"
    assert apply_string_modifier("12345", "len") == "5"
    assert apply_string_modifier("12345", "length") == "5"


def test_apply_string_modifier_slice():
    assert apply_string_modifier("abcdef", "slice:0:3") == "abc"
    assert apply_string_modifier("abcdef", "SLICE:0:3") == "abc"
    assert apply_string_modifier("abcdef", "slice:2:") == "cdef"
    assert apply_string_modifier("abcdef", "slice::3") == "abc"
    assert apply_string_modifier("abcdef", "slice:-3:") == "def"
    assert apply_string_modifier("abcdef", "sub:1:4") == "bcd"
    assert apply_string_modifier("abcdef", "SUB:1:4") == "bcd"


def test_apply_string_modifier_slice_invalid(capsys):
    # Bare slice and invalid slice arguments raise StringModifierError
    with pytest.raises(StringModifierError):
        apply_string_modifier("abcdef", "slice")
    captured = capsys.readouterr()
    assert "Error: Invalid slice parameters in modifier 'slice'" in captured.out

    with pytest.raises(StringModifierError):
        apply_string_modifier("abcdef", "slice:x:2")
    captured2 = capsys.readouterr()
    assert "Error: Invalid slice parameters in modifier 'slice:x:2'" in captured2.out


def test_apply_string_modifier_chained():
    assert apply_string_modifier("   HeLLo WoRLd   ", "trim:lower") == "hello world"
    assert apply_string_modifier("abcdef", "slice:0:3:upper") == "ABC"
    assert apply_string_modifier("  hi  ", "trim:upper:len") == "2"


def test_apply_string_modifier_chaining_order():
    """Verify that modifier pipelines are strictly executed left-to-right."""
    # lower:capitalize vs capitalize:lower
    assert apply_string_modifier("HELLO WORLD", "lower:capitalize") == "Hello world"
    assert apply_string_modifier("HELLO WORLD", "capitalize:lower") == "hello world"

    # trim:slice vs slice:trim
    assert apply_string_modifier("  abc  ", "trim:slice:0:2") == "ab"
    assert apply_string_modifier("  abc  ", "slice:0:2:trim") == ""


def test_apply_string_modifier_edge_cases(capsys):
    assert apply_string_modifier("test", "") == "test"
    # Unknown modifier outputs Error and raises StringModifierError
    with pytest.raises(StringModifierError):
        apply_string_modifier("test", "unknown_mod")
    captured = capsys.readouterr()
    assert "Error: Unknown string modifier 'unknown_mod'" in captured.out
    assert apply_string_modifier(12345, "upper") == "12345"
    assert apply_string_modifier(12345, "len") == "5"
    assert apply_string_modifier(12345, "slice:0:2") == "12"


# ============================================================================
# 2. BufferManager placeholder expansion with modifiers & preservation of JSON/format
# ============================================================================

def test_buffer_manager_modifiers():
    bm = BufferManager()
    bm.set_script_var("NAME", "  Alice Smith  ")
    bm.set_script_var("CODE", "secret_12345")
    bm.set_script_var("LIST[]", ["apple", "BANANA", "Cherry"])

    # Base modifiers
    assert bm.replace_placeholders("${NAME:lower}")[0] == "alice smith"
    assert bm.replace_placeholders("${NAME:upper}")[0] == "ALICE SMITH"
    assert bm.replace_placeholders("${NAME:trim}")[0] == "Alice Smith"
    assert bm.replace_placeholders("${NAME:trim:lower}")[0] == "alice smith"
    assert bm.replace_placeholders("${NAME: upper}")[0] == "ALICE SMITH"  # whitespace tolerant
    assert bm.replace_placeholders("${CODE:len}")[0] == "12"
    assert bm.replace_placeholders("${CODE:slice:0:6}")[0] == "secret"

    # Array subscripts with modifiers
    assert bm.replace_placeholders("${LIST[1]:lower}")[0] == "banana"
    assert bm.replace_placeholders("${LIST[0]:upper}")[0] == "APPLE"


def test_buffer_manager_preserves_json_and_format_specs():
    bm = BufferManager()
    bm.set_script_var("x", "5")
    bm.set_script_var("name", "Bob")
    bm.set_script_var("model", "m1")

    # Format specs or dictionary syntax without $ must NOT be mangled or treated as modifiers
    assert bm.replace_placeholders("{x:02d}")[0] == "{x:02d}"
    assert bm.replace_placeholders("{name:10}")[0] == "{name:10}"
    assert bm.replace_placeholders("{model:gpt-4}")[0] == "{model:gpt-4}"
    assert bm.replace_placeholders('data = {"a": 1, "b": 2}')[0] == 'data = {"a": 1, "b": 2}'


def test_buffer_manager_unbraced_colon_expansion():
    bm = BufferManager()
    bm.set_script_var("topic", "cats")
    bm.set_script_var("name", "Bob")
    bm.set_script_var("x", "5")

    assert bm.replace_placeholders("Summarize $topic: be brief")[0] == "Summarize cats: be brief"
    assert bm.replace_placeholders("Hello $name: welcome")[0] == "Hello Bob: welcome"
    assert bm.replace_placeholders("ratio $x:1")[0] == "ratio 5:1"

    # Undefined unbraced with colon is cleared when clear_unresolved=True
    text, _ = bm.replace_placeholders("Look at $undefined: here", clear_unresolved=True)
    assert text == "Look at : here"


def test_buffer_manager_clear_unresolved_with_modifiers():
    bm = BufferManager()
    # Unresolved with modifiers should be cleared cleanly when clear_unresolved=True
    text, _ = bm.replace_placeholders("Hello ${UNKNOWN:lower} World", clear_unresolved=True)
    assert text == "Hello World"

    # Ordinary dict/format strings without $ must NOT be cleared by clear_unresolved
    text2, _ = bm.replace_placeholders('d = {a:1} f"{val:10}"', clear_unresolved=True)
    assert text2 == 'd = {a:1} f"{val:10}"'


# ============================================================================
# 3. ChatybotApp condition evaluation: colon operands and negative tests
# ============================================================================

def test_evaluate_condition_colon_operands():
    """Ensure colons in timestamps, URLs, ratios, and string literals are NOT mangled."""
    app = ChatybotApp()
    app.buffer_manager.set_script_var("t1", "12:30")
    app.buffer_manager.set_script_var("t2", "12:45")
    app.buffer_manager.set_script_var("url", "https://a.com")
    app.buffer_manager.set_script_var("inj", "abc:len")

    # High regression probes
    assert app.evaluate_condition('"12:30" == "12:45"') is False
    assert app.evaluate_condition('$t1 == $t2') is False
    assert app.evaluate_condition('${url} == "https://evil.com"') is False
    assert app.evaluate_condition('"${url}" != "https://other"') is True
    assert app.evaluate_condition('"ratio 3:2" == "ratio 3"') is False
    assert app.evaluate_condition('inj == "abc:len"') is True
    assert app.evaluate_condition('"${inj}" == "abc:len"') is True
    assert app.evaluate_condition('nosuch:len == 6') is False


def test_evaluate_condition_modifiers():
    app = ChatybotApp()
    app.buffer_manager.set_script_var("toggle", "YES")
    app.buffer_manager.set_script_var("role", "  Admin  ")
    app.buffer_manager.set_script_var("code", "prod_deploy")

    # Braced
    assert app.evaluate_condition('"${toggle:lower}" == "yes"') is True
    assert app.evaluate_condition('"${toggle:upper}" == "YES"') is True
    assert app.evaluate_condition('"${role:trim:lower}" == "admin"') is True
    assert app.evaluate_condition('"${toggle:len}" == "3"') is True

    # Quoted unbraced $var:modifier
    assert app.evaluate_condition('"$toggle:lower" == "yes"') is True
    assert app.evaluate_condition('"$toggle:upper" == "YES"') is True
    assert app.evaluate_condition('"$role:trim:lower" == "admin"') is True

    # Bare
    assert app.evaluate_condition('toggle:lower == "yes"') is True
    assert app.evaluate_condition('toggle:upper == "YES"') is True
    assert app.evaluate_condition('$toggle:lower == "yes"') is True
    assert app.evaluate_condition('code:slice:0:4 == "prod"') is True
    assert app.evaluate_condition('code:len > 5') is True

    # Open-ended slices (unbraced, quoted unbraced, bare, braced)
    app.buffer_manager.set_script_var("id", "user_101")
    assert app.evaluate_condition('$id:slice:-3: == "101"') is True
    assert app.evaluate_condition('$id:slice:5: == "101"') is True
    assert app.evaluate_condition('"$id:slice:-3:" == "101"') is True
    assert app.evaluate_condition('"$id:slice:5:" == "101"') is True
    assert app.evaluate_condition('id:slice:-3: == "101"') is True
    assert app.evaluate_condition('"${id:slice:-3:}" == "101"') is True


def test_evaluate_condition_bare_modifier_truthiness():
    """Ensure bare modifiers in truthiness checks evaluate correctly without operators."""
    app = ChatybotApp()
    app.buffer_manager.set_script_var("flag_no", "NO")
    app.buffer_manager.set_script_var("flag_yes", "YES")
    app.buffer_manager.set_script_var("flag_zero", "0")

    assert app.evaluate_condition("flag_no:lower") is False
    assert app.evaluate_condition("$flag_no:lower") is False
    assert app.evaluate_condition("flag_yes:lower") is True
    assert app.evaluate_condition("$flag_yes:lower") is True
    assert app.evaluate_condition("flag_zero:trim") is False


# ============================================================================
# 4. End-to-end ChatDSL script execution
# ============================================================================

@pytest.mark.anyio
async def test_chatdsl_script_with_modifiers():
    app = ChatybotApp()
    script = """
set answer = "  YeS  "
if answer:trim:lower == "yes" then
    set result = "${answer:trim:upper}"
else
    set result = "no"
endif
"""
    await app.execute_command_list([line for line in script.strip().splitlines()])
    assert app.buffer_manager.get_script_var("result") == "YES"


@pytest.mark.anyio
async def test_unknown_modifier_in_set_aborts(capsys):
    app = ChatybotApp()
    script = """
set var = "Bob"
set x = "${var:unknown_mod}"
set reached = "yes"
"""
    with pytest.raises(StringModifierError):
        await app.execute_command_list([line for line in script.strip().splitlines()])

    assert app.buffer_manager.get_script_var("x") is None
    assert app.buffer_manager.get_script_var("reached") is None
    captured = capsys.readouterr()
    assert "Error: Unknown string modifier 'unknown_mod'" in captured.out


@pytest.mark.anyio
async def test_unknown_modifier_in_condition_aborts(capsys):
    app = ChatybotApp()
    script = """
set ans = "yes"
if ans:lowr == "yes" then
    set reached = "yes"
endif
"""
    with pytest.raises(StringModifierError):
        await app.execute_command_list([line for line in script.strip().splitlines()])

    assert app.buffer_manager.get_script_var("reached") is None
    captured = capsys.readouterr()
    assert "Error: Unknown string modifier 'lowr'" in captured.out


@pytest.mark.anyio
async def test_unknown_modifier_aborts_execute_script(tmp_path, capsys):
    app = ChatybotApp()
    script_content = """
set user = "Alice"
set bad = "${user:uper}"
set finished = "true"
"""
    f = tmp_path / "test_abort.chatdsl"
    f.write_text(script_content)

    await app.execute_script(str(f))

    assert app.buffer_manager.get_script_var("bad") is None
    assert app.buffer_manager.get_script_var("finished") is None
    captured = capsys.readouterr()
    assert "Error: Unknown string modifier 'uper'" in captured.out
    assert "Error executing script:" in captured.out
    assert "Script execution finished" not in captured.out
