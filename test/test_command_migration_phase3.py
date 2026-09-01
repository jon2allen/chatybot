"""Tests for Phase 3 migrated commands: session, tools, proc, db, rerank, debug_misc.

Validates that commands migrated to the registry produce identical behavior
to the legacy elif chain, including:
- Session: /session (status, auto, stop, history subcommands)
- Tools: /run, /run_safe, /run_unsafe, /tool (list, on, off, auto, max_turns)
- Proc: /proc (not found, usage), /source (not found), /script (usage)
- DB: /setdb (usage), /dblist, /searchdb (usage), /dblog, /dbprint
- Rerank: /documents (usage, invalid source), /rerank (no query, no source)
- Debug: /trace (tps on/off), /debug (payload, response), /notemode, /codeonly,
  /codeoff, /multiline, /env, /logging (status), /save (usage), /mem, /dump,
  /calc, /setvar, /reloadmacros, /listmacros
- i18n alias dispatch for migrated commands
"""

import pytest
from chatybot.commands.registry import registry as default_registry
from chatybot.chatybot_app import ChatybotApp


def _make_app(capsys=None):
    app = ChatybotApp()
    app.initialize()
    if capsys is not None:
        capsys.readouterr()
    return app


# ---------------------------------------------------------------------------
# Registry coverage
# ---------------------------------------------------------------------------

def test_all_phase3_commands_registered():
    expected = [
        "/session", "/run", "/run_safe", "/run_unsafe", "/tool",
        "/proc", "/source", "/script",
        "/setdb", "/dblist", "/searchdb", "/dblog", "/dbprint",
        "/loadvar", "/savevar",
        "/documents", "/rerank",
        "/trace", "/debug", "/prompt", "/logging", "/save",
        "/notemode", "/codeonly", "/codeoff", "/multiline",
        "/env", "/profile", "/mem", "/dump",
        "/calc", "/str_search", "/setvar",
        "/reloadmacros", "/listmacros",
    ]
    for name in expected:
        assert default_registry.has(name), f"{name} not registered"


# ---------------------------------------------------------------------------
# Session commands
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_session_no_arg(capsys):
    app = _make_app(capsys)
    result = await app.handle_escape_command("/session")
    assert result is True
    out = capsys.readouterr().out
    assert "Active Session ID:" in out
    assert "Session Mode:" in out


@pytest.mark.anyio
async def test_session_status(capsys):
    app = _make_app(capsys)
    result = await app.handle_escape_command("/session status")
    assert result is True
    out = capsys.readouterr().out
    assert "Active Session ID:" in out


@pytest.mark.anyio
async def test_session_auto_status(capsys):
    app = _make_app(capsys)
    result = await app.handle_escape_command("/session auto")
    assert result is True
    out = capsys.readouterr().out
    assert "Auto Session Mode" in out


@pytest.mark.anyio
async def test_session_stop(capsys):
    app = _make_app(capsys)
    result = await app.handle_escape_command("/session stop")
    assert result is True
    out = capsys.readouterr().out
    assert "paused" in out


@pytest.mark.anyio
async def test_session_history_status(capsys):
    app = _make_app(capsys)
    result = await app.handle_escape_command("/session history")
    assert result is True
    out = capsys.readouterr().out
    assert "Chat History Collection" in out


@pytest.mark.anyio
async def test_session_delete_usage(capsys):
    app = _make_app(capsys)
    result = await app.handle_escape_command("/session delete")
    assert result is True
    out = capsys.readouterr().out
    assert "Usage: /session delete" in out


@pytest.mark.anyio
async def test_session_delete_not_found(capsys):
    app = _make_app(capsys)
    result = await app.handle_escape_command('/session delete "non_existent_session"')
    assert result is True
    out = capsys.readouterr().out
    assert "Error: Session 'non_existent_session' not found." in out


@pytest.mark.anyio
async def test_session_unknown_subcmd(capsys):
    app = _make_app(capsys)
    result = await app.handle_escape_command("/session bogus")
    assert result is True
    out = capsys.readouterr().out
    assert "Unknown session subcommand" in out


# ---------------------------------------------------------------------------
# Tools commands
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_run_no_arg(capsys):
    app = _make_app(capsys)
    result = await app.handle_escape_command("/run")
    assert result is True
    out = capsys.readouterr().out
    assert "Usage: /run" in out


@pytest.mark.anyio
async def test_run_safe(capsys):
    app = _make_app(capsys)
    result = await app.handle_escape_command("/run safe")
    assert result is True
    out = capsys.readouterr().out
    assert "Safe mode enabled" in out
    assert app.safe_mode is True


@pytest.mark.anyio
async def test_run_unsafe(capsys):
    app = _make_app(capsys)
    app.safe_mode = True
    result = await app.handle_escape_command("/run unsafe")
    assert result is True
    out = capsys.readouterr().out
    assert "Safe mode disabled" in out
    assert app.safe_mode is False


@pytest.mark.anyio
async def test_run_safe_standalone(capsys):
    app = _make_app(capsys)
    result = await app.handle_escape_command("/run_safe")
    assert result is True
    assert app.safe_mode is True


@pytest.mark.anyio
async def test_run_unsafe_standalone(capsys):
    app = _make_app(capsys)
    result = await app.handle_escape_command("/run_unsafe")
    assert result is True
    assert app.safe_mode is False


@pytest.mark.anyio
async def test_tool_no_arg(capsys):
    app = _make_app(capsys)
    # /tool with no args dispatches from LAST_COMPLETION - should not crash
    result = await app.handle_escape_command("/tool")
    assert result is True


@pytest.mark.anyio
async def test_tool_max_turns_status(capsys):
    app = _make_app(capsys)
    result = await app.handle_escape_command("/tool max_turns")
    assert result is True
    out = capsys.readouterr().out
    assert "max tool turns" in out.lower()


@pytest.mark.anyio
async def test_tool_rate_limit_status(capsys):
    app = _make_app(capsys)
    result = await app.handle_escape_command("/tool rate_limit")
    assert result is True
    out = capsys.readouterr().out
    assert "rate_limit" in out.lower()


# ---------------------------------------------------------------------------
# Proc / script / source commands
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_proc_no_arg(capsys):
    app = _make_app(capsys)
    result = await app.handle_escape_command("/proc")
    assert result is True
    out = capsys.readouterr().out
    assert "Usage: /proc" in out


@pytest.mark.anyio
async def test_proc_not_found(capsys):
    app = _make_app(capsys)
    result = await app.handle_escape_command("/proc nonexistent_proc")
    assert result is True
    out = capsys.readouterr().out
    assert "not found" in out


@pytest.mark.anyio
async def test_source_no_arg(capsys):
    app = _make_app(capsys)
    result = await app.handle_escape_command("/source")
    assert result is True
    out = capsys.readouterr().out
    assert "Usage: /source" in out


@pytest.mark.anyio
async def test_source_not_found(capsys):
    app = _make_app(capsys)
    result = await app.handle_escape_command("/source nonexistent.chatdsl")
    assert result is True
    out = capsys.readouterr().out
    assert "not found" in out


@pytest.mark.anyio
async def test_script_no_arg(capsys):
    app = _make_app(capsys)
    result = await app.handle_escape_command("/script")
    assert result is True
    out = capsys.readouterr().out
    assert "Usage: /script" in out


# ---------------------------------------------------------------------------
# DB commands
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_setdb_no_arg(capsys):
    app = _make_app(capsys)
    result = await app.handle_escape_command("/setdb")
    assert result is True
    out = capsys.readouterr().out
    assert "Usage: /setdb" in out


@pytest.mark.anyio
async def test_dblist(capsys):
    app = _make_app(capsys)
    result = await app.handle_escape_command("/dblist")
    assert result is True


@pytest.mark.anyio
async def test_searchdb_no_arg(capsys):
    app = _make_app(capsys)
    result = await app.handle_escape_command("/searchdb")
    assert result is True
    out = capsys.readouterr().out
    assert "Usage: /searchdb" in out


@pytest.mark.anyio
async def test_dblog(capsys):
    app = _make_app(capsys)
    result = await app.handle_escape_command("/dblog")
    assert result is True


@pytest.mark.anyio
async def test_dbprint(capsys):
    app = _make_app(capsys)
    result = await app.handle_escape_command("/dbprint")
    assert result is True


@pytest.mark.anyio
async def test_loadvar_no_arg(capsys):
    app = _make_app(capsys)
    result = await app.handle_escape_command("/loadvar")
    assert result is True
    out = capsys.readouterr().out
    assert "Usage: /loadvar" in out


@pytest.mark.anyio
async def test_savevar_no_arg(capsys):
    app = _make_app(capsys)
    result = await app.handle_escape_command("/savevar")
    assert result is True
    out = capsys.readouterr().out
    assert "Usage: /savevar" in out


# ---------------------------------------------------------------------------
# Rerank commands
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_documents_no_arg(capsys):
    app = _make_app(capsys)
    result = await app.handle_escape_command("/documents")
    assert result is True
    out = capsys.readouterr().out
    assert "Usage: /documents" in out


@pytest.mark.anyio
async def test_documents_invalid_source(capsys):
    app = _make_app(capsys)
    result = await app.handle_escape_command("/documents bogus=test")
    assert result is True
    out = capsys.readouterr().out
    assert "Invalid source type" in out


@pytest.mark.anyio
async def test_rerank_no_query(capsys):
    app = _make_app(capsys)
    result = await app.handle_escape_command("/rerank")
    assert result is True
    out = capsys.readouterr().out
    assert "Usage: /rerank" in out


@pytest.mark.anyio
async def test_rerank_no_source(capsys):
    app = _make_app(capsys)
    app.rerank_documents_source = None
    result = await app.handle_escape_command('/rerank "test query"')
    assert result is True
    out = capsys.readouterr().out
    assert "No document source" in out


# ---------------------------------------------------------------------------
# Debug / misc commands
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_trace_no_arg(capsys):
    app = _make_app(capsys)
    result = await app.handle_escape_command("/trace")
    assert result is True
    out = capsys.readouterr().out
    assert "Usage: /trace" in out


@pytest.mark.anyio
async def test_trace_tps_on(capsys):
    app = _make_app(capsys)
    result = await app.handle_escape_command("/trace tps on")
    assert result is True
    out = capsys.readouterr().out
    assert "Trace tps set to True" in out
    assert app.trace_tps is True


@pytest.mark.anyio
async def test_trace_tps_off(capsys):
    app = _make_app(capsys)
    app.trace_tps = True
    result = await app.handle_escape_command("/trace tps off")
    assert result is True
    out = capsys.readouterr().out
    assert "Trace tps set to False" in out
    assert app.trace_tps is False


@pytest.mark.anyio
async def test_trace_invalid_state(capsys):
    app = _make_app(capsys)
    result = await app.handle_escape_command("/trace tps maybe")
    assert result is True
    out = capsys.readouterr().out
    assert "invalid state" in out


@pytest.mark.anyio
async def test_debug_no_arg(capsys):
    app = _make_app(capsys)
    result = await app.handle_escape_command("/debug")
    assert result is True
    out = capsys.readouterr().out
    assert "Usage: /debug" in out


@pytest.mark.anyio
async def test_debug_payload(capsys):
    app = _make_app(capsys)
    result = await app.handle_escape_command("/debug payload")
    assert result is True
    out = capsys.readouterr().out
    assert "Debug payload mode" in out
    assert app.debug_payload_mode is True


@pytest.mark.anyio
async def test_debug_response(capsys):
    app = _make_app(capsys)
    result = await app.handle_escape_command("/debug response")
    assert result is True
    out = capsys.readouterr().out
    assert "Debug response mode" in out
    assert app.debug_response_mode is True


@pytest.mark.anyio
async def test_prompt_no_arg(capsys):
    app = _make_app(capsys)
    result = await app.handle_escape_command("/prompt")
    assert result is True
    out = capsys.readouterr().out
    assert "Usage: /prompt" in out


@pytest.mark.anyio
async def test_prompt_not_found(capsys):
    app = _make_app(capsys)
    result = await app.handle_escape_command("/prompt nonexistent_file.txt")
    assert result is True
    out = capsys.readouterr().out
    assert "not found" in out


@pytest.mark.anyio
async def test_logging_no_arg(capsys):
    app = _make_app(capsys)
    result = await app.handle_escape_command("/logging")
    assert result is True
    out = capsys.readouterr().out
    assert "Logging is" in out


@pytest.mark.anyio
async def test_save_no_arg(capsys):
    app = _make_app(capsys)
    result = await app.handle_escape_command("/save")
    assert result is True
    out = capsys.readouterr().out
    assert "Usage: /save" in out


@pytest.mark.anyio
async def test_notemode_no_arg(capsys):
    app = _make_app(capsys)
    result = await app.handle_escape_command("/notemode")
    assert result is True
    out = capsys.readouterr().out
    assert "Note mode" in out


@pytest.mark.anyio
async def test_notemode_on(capsys):
    app = _make_app(capsys)
    result = await app.handle_escape_command("/notemode on")
    assert result is True
    assert app.note_mode is True


@pytest.mark.anyio
async def test_notemode_off(capsys):
    app = _make_app(capsys)
    app.note_mode = True
    result = await app.handle_escape_command("/notemode off")
    assert result is True
    assert app.note_mode is False


@pytest.mark.anyio
async def test_codeonly(capsys):
    app = _make_app(capsys)
    result = await app.handle_escape_command("/codeonly")
    assert result is True
    assert app.code_only_flag is True


@pytest.mark.anyio
async def test_codeoff(capsys):
    app = _make_app(capsys)
    app.code_only_flag = True
    result = await app.handle_escape_command("/codeoff")
    assert result is True
    assert app.code_only_flag is False


@pytest.mark.anyio
async def test_multiline_toggle(capsys):
    app = _make_app(capsys)
    initial = app.multi_line_mode
    result = await app.handle_escape_command("/multiline")
    assert result is True
    assert app.multi_line_mode == (not initial)


@pytest.mark.anyio
async def test_env(capsys):
    app = _make_app(capsys)
    result = await app.handle_escape_command("/env")
    assert result is True
    out = capsys.readouterr().out
    assert "ENVIRONMENT VARIABLES" in out


@pytest.mark.anyio
async def test_mem(capsys):
    app = _make_app(capsys)
    result = await app.handle_escape_command("/mem")
    assert result is True


@pytest.mark.anyio
async def test_dump(capsys):
    app = _make_app(capsys)
    result = await app.handle_escape_command("/dump")
    assert result is True


@pytest.mark.anyio
async def test_calc_no_arg(capsys):
    app = _make_app(capsys)
    result = await app.handle_escape_command("/calc")
    assert result is True
    out = capsys.readouterr().out
    assert "Usage: /calc" in out


@pytest.mark.anyio
async def test_calc_simple(capsys):
    app = _make_app(capsys)
    result = await app.handle_escape_command('/calc "2 + 3"')
    assert result is True
    out = capsys.readouterr().out
    assert "CALC = 5" in out


@pytest.mark.anyio
async def test_str_search_no_arg(capsys):
    app = _make_app(capsys)
    result = await app.handle_escape_command("/str_search")
    assert result is True
    out = capsys.readouterr().out
    assert "Usage: /str_search" in out


@pytest.mark.anyio
async def test_setvar_no_arg(capsys):
    app = _make_app(capsys)
    result = await app.handle_escape_command("/setvar")
    assert result is True
    out = capsys.readouterr().out
    assert "Usage: /setvar" in out


@pytest.mark.anyio
async def test_setvar_basic(capsys):
    app = _make_app(capsys)
    result = await app.handle_escape_command("/setvar MY_TEST hello")
    assert result is True
    out = capsys.readouterr().out
    assert "Variable 'MY_TEST' set." in out
    assert app.buffer_manager.get_script_var("MY_TEST") == "hello"


@pytest.mark.anyio
async def test_setvar_invalid_name(capsys):
    app = _make_app(capsys)
    result = await app.handle_escape_command("/setvar 123bad value")
    assert result is True
    out = capsys.readouterr().out
    assert "Invalid variable name" in out


@pytest.mark.anyio
async def test_reloadmacros(capsys):
    app = _make_app(capsys)
    result = await app.handle_escape_command("/reloadmacros")
    assert result is True
    out = capsys.readouterr().out
    assert "Reloaded macros from default file" in out


@pytest.mark.anyio
async def test_reloadmacros_custom_file(capsys, tmp_path):
    macro_file = tmp_path / "custom.chatdsl"
    macro_file.write_text("def test_m = /echo from_macro\n", encoding="utf-8")
    app = _make_app(capsys)
    result = await app.handle_escape_command(f'/reloadmacros "{macro_file}"')
    assert result is True
    out = capsys.readouterr().out
    assert f"Reloaded macros from '{macro_file}'" in out


@pytest.mark.anyio
async def test_listmacros(capsys):
    app = _make_app(capsys)
    result = await app.handle_escape_command("/listmacros")
    assert result is True


# ---------------------------------------------------------------------------
# i18n alias dispatch for Phase 3 commands
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_session_spanish_alias(capsys):
    app = ChatybotApp(lang="spanish")
    app.initialize()
    capsys.readouterr()
    result = await app.handle_escape_command("/sesion")
    assert result is True
    out = capsys.readouterr().out
    assert "Active Session ID:" in out


@pytest.mark.anyio
async def test_tool_spanish_alias(capsys):
    app = ChatybotApp(lang="spanish")
    app.initialize()
    capsys.readouterr()
    result = await app.handle_escape_command("/herramienta max_turns")
    assert result is True
    out = capsys.readouterr().out
    assert "max tool turns" in out.lower()


@pytest.mark.anyio
async def test_trace_spanish_alias(capsys):
    app = ChatybotApp(lang="spanish")
    app.initialize()
    capsys.readouterr()
    result = await app.handle_escape_command("/rastreo tps on")
    assert result is True
    out = capsys.readouterr().out
    assert "Trace tps set to True" in out


@pytest.mark.anyio
async def test_logging_spanish_alias(capsys):
    app = ChatybotApp(lang="spanish")
    app.initialize()
    capsys.readouterr()
    result = await app.handle_escape_command("/registro")
    assert result is True
    out = capsys.readouterr().out
    assert "Logging is" in out


# ---------------------------------------------------------------------------
# Fall-through: /help and /quit still work via legacy chain
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_help_still_works(capsys):
    app = _make_app(capsys)
    result = await app.handle_escape_command("/help")
    assert result is True
    out = capsys.readouterr().out
    assert len(out) > 0


@pytest.mark.anyio
async def test_unknown_command_returns_false(capsys):
    app = _make_app(capsys)
    result = await app.handle_escape_command("/nonexistent_command_xyz")
    assert result is False
    out = capsys.readouterr().out
    assert "Unknown command" in out
