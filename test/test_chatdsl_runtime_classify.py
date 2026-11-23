"""Runtime tests for classifier-driven dispatch in execute_command_list /
execute_script_command (src/chatybot/chatdsl_if.py).

Pins the prose-hazard fixes: prompt lines starting with keywords go to the LLM
whole, trailing-`then` lines are single-line ifs (not phantom blocks), stray
block keywords error instead of being sent as chat, and unclosed blocks abort.
"""
import os
import tempfile

import pytest

from chatybot.chatybot_app import ChatybotApp


@pytest.fixture
def app():
    return ChatybotApp()


@pytest.fixture
def sent_prompts(app):
    """Stub out the LLM and capture every prompt that would be sent."""
    sent = []

    async def fake_chat(prompt, stream=False):
        sent.append(prompt)
        return "LLM-REPLY"

    app.chat_completion = fake_chat
    return sent


async def run_script(app, script):
    with tempfile.NamedTemporaryFile(mode="w", suffix=".chatdsl", delete=False) as f:
        f.write(script)
        f.flush()
        try:
            await app.execute_script(f.name)
        finally:
            os.unlink(f.name)


@pytest.mark.anyio
async def test_prose_if_sent_to_llm_whole(app, sent_prompts):
    await run_script(app, 'set X = "1"\nif you find bug after review then fix\n/setvar after ran\n')
    assert sent_prompts == ["if you find bug after review then fix"]
    assert app.buffer_manager.get_script_var("after") == "ran"


@pytest.mark.anyio
async def test_undefined_bare_var_condition_is_prompt(app, sent_prompts):
    await run_script(app, "if x > 3 then answer\n")
    assert sent_prompts == ["if x > 3 then answer"]


@pytest.mark.anyio
async def test_defined_bare_var_condition_is_construct(app, sent_prompts):
    await run_script(app, 'set num_poems = "5"\nif num_poems >= 5 then\n    set res = "five_or_more"\nendif\n')
    assert sent_prompts == []
    assert app.buffer_manager.get_script_var("res") == "five_or_more"


@pytest.mark.anyio
async def test_trailing_then_is_single_line_not_phantom_block(app, sent_prompts):
    await run_script(app, 'set X = "1"\nif $X then /echo then\n/setvar after done\n')
    assert app.buffer_manager.get_script_var("after") == "done"


@pytest.mark.anyio
async def test_single_line_if_else_still_works(app, sent_prompts):
    await run_script(app, 'set X = "1"\nif $X then /setvar a single else /setvar a other\n')
    assert app.buffer_manager.get_script_var("a") == "single"


@pytest.mark.anyio
async def test_stray_endif_errors_not_sent_to_llm(app, sent_prompts, capsys):
    await run_script(app, "endif\n/setvar after done\n")
    assert sent_prompts == []
    assert "Error: 'endif' used without matching 'if' block" in capsys.readouterr().out
    assert app.buffer_manager.get_script_var("after") == "done"


@pytest.mark.anyio
async def test_stray_endfor_errors_not_sent_to_llm(app, sent_prompts, capsys):
    await run_script(app, "endfor\n/setvar after done\n")
    assert sent_prompts == []
    assert "Error: 'endfor' used without matching 'foreach' block" in capsys.readouterr().out
    assert app.buffer_manager.get_script_var("after") == "done"


@pytest.mark.anyio
async def test_unclosed_if_aborts_script(app, sent_prompts, capsys):
    await run_script(app, 'if $X then\n/setvar swallowed yes\n/setvar after done\n')
    assert app.buffer_manager.get_script_var("swallowed") is None
    assert app.buffer_manager.get_script_var("after") is None
    assert "Error: Unclosed if block at end of script" in capsys.readouterr().out


@pytest.mark.anyio
async def test_literal_comparison_block(app, sent_prompts):
    await run_script(app, 'if 5 > 3 then\n    set lit = "yes"\nendif\n')
    assert app.buffer_manager.get_script_var("lit") == "yes"


@pytest.mark.anyio
async def test_quoted_prompt_starting_with_keyword_passes_through(app, sent_prompts):
    # Escape hatch: a quoted line is a prompt even though it starts with a keyword
    await run_script(app, '"if you want quality then revise"\n')
    assert sent_prompts == ['"if you want quality then revise"']
