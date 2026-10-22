"""Tests for the tool-loop guard (stage 5): repeated identical calls with identical results."""

import json

import pytest

from chatybot.loop_guard import DUPLICATE, NUDGE, RUN, STOP, LoopGuard

LS = ("list_directory", {"path": "."})
CAT = ("read_file", {"path": "a.txt"})


def run(guard, call, result="same"):
    """Check a call; if allowed, record it with the given result. Returns the decision action."""
    guard.start_turn()
    d = guard.check(*call)
    if d.action == RUN:
        guard.record(*call, result)
    return d.action


# --------------------------------------------------------------------------- unit


def test_third_identical_call_is_withheld_then_loop_stops():
    g = LoopGuard()
    assert [run(g, LS), run(g, LS)] == [RUN, RUN]
    assert run(g, LS) == NUDGE
    assert run(g, LS) == STOP


def test_same_call_with_changing_result_is_never_flagged():
    g = LoopGuard()
    assert all(run(g, LS, f"listing {i}") == RUN for i in range(10))


def test_alternating_loop_is_caught():
    g = LoopGuard()
    assert [run(g, LS), run(g, CAT), run(g, LS), run(g, CAT)] == [RUN] * 4
    assert run(g, LS) == NUDGE


def test_window_forgets_old_calls():
    g = LoopGuard(window=4)
    run(g, LS)
    for i in range(4):
        run(g, ("read_file", {"path": f"{i}.txt"}))
    assert run(g, LS) == RUN and run(g, LS) == RUN


def test_duplicate_in_one_turn_runs_once():
    g = LoopGuard()
    g.start_turn()
    assert g.check(*LS).action == RUN
    g.record(*LS, "x")
    d = g.check(*LS)
    assert d.action == DUPLICATE and "call #1" in d.message


def test_wrapped_and_bare_arguments_are_the_same_call():
    g = LoopGuard()
    run(g, LS)
    run(g, ("list_directory", {"parameters": {"path": "."}}))
    assert run(g, LS) == NUDGE


def test_after_nudge_other_work_allows_one_retry():
    g = LoopGuard()
    run(g, LS), run(g, LS)
    assert run(g, LS) == NUDGE
    run(g, ("write_file", {"path": "b.txt", "content": "x"}), "written")
    assert run(g, LS) == RUN  # something ran in between: one more try
    assert run(g, LS) == STOP  # still the same result


def test_after_nudge_changed_result_clears_the_nudge():
    g = LoopGuard()
    run(g, LS), run(g, LS)
    assert run(g, LS) == NUDGE
    run(g, ("write_file", {"path": "b.txt", "content": "x"}), "written")
    assert run(g, LS, "new listing") == RUN
    assert run(g, LS, "new listing") == RUN
    assert run(g, LS, "new listing") == NUDGE  # a fresh nudge, not an immediate stop


def test_disabled_and_exempt_tools_always_run():
    g = LoopGuard(enabled=False)
    assert all(run(g, LS) == RUN for _ in range(6))
    g = LoopGuard()
    assert all(run(g, ("ask_user", {"question": "ok?"})) == RUN for _ in range(6))


def test_repeats_setting():
    g = LoopGuard(repeats=4)
    assert [run(g, LS) for _ in range(4)] == [RUN, RUN, RUN, NUDGE]
    assert LoopGuard(repeats=0).repeats == 2


# --------------------------------------------------------------------------- tool loop


def _app(tmp_path, monkeypatch, default_verdict="allow"):
    from chatybot.chatybot_app import ChatybotApp

    sec_cfg = tmp_path / "security.toml"
    sec_cfg.write_text(
        'version = "1.0"\nengine = "builtin"\nfail_safe = "deny"\nmax_refusals_per_loop = 3\n'
        f'[builtin]\ndefault_verdict = "{default_verdict}"\n'
    )
    app = ChatybotApp(security_config_path=str(sec_cfg))
    app.initialize()
    app.enable_chat_history = True
    app.rate_limit_delay = 0.0
    app._cached_rate_limit_delay = 0.0
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    return app


def _loop_with(app, monkeypatch, responses):
    """Feed the loop a fixed list of model responses; returns the list of histories seen."""
    seen = []

    async def mock_completion(history, stream=False):
        seen.append(history[-1]["content"])
        return responses[min(len(seen) - 1, len(responses) - 1)]

    monkeypatch.setattr(app, "chat_completion", mock_completion)
    return seen


def _count_dispatches(app, monkeypatch):
    calls = []
    orig = app.dispatch_tool

    async def counting(*a, **kw):
        calls.append(a)
        return await orig(*a, **kw)

    monkeypatch.setattr(app, "dispatch_tool", counting)
    return calls


@pytest.mark.anyio
async def test_tool_loop_stops_repeating_model(tmp_path, monkeypatch):
    app = _app(tmp_path, monkeypatch)
    target = tmp_path / "f.txt"
    target.write_text("hello")
    call = json.dumps({"tool": "read_file", "arguments": {"path": str(target)}})
    app.chat_history = [("read it", call)]
    seen = _loop_with(app, monkeypatch, [call])  # the model repeats forever
    dispatched = _count_dispatches(app, monkeypatch)

    await app.run_tool_loop(max_turns=25)

    assert len(dispatched) == 2  # third request nudged, fourth stops the loop
    assert len(seen) == 3
    assert "Loop guard: 'read_file' was already called" in seen[-1]
    final = app.buffer_manager.get_script_var("LAST_COMPLETION")
    assert final.startswith("Loop guard stopped the tool loop")
    records = app.buffer_manager.get_script_var("AGENTIC_LOOP")
    assert records[-1]["loop_guard"] == "nudge" and records[-1]["status"] == "error"
    assert app.in_tool_loop is False and app._loop_guard is None


@pytest.mark.anyio
async def test_tool_loop_parallel_duplicate_runs_once(tmp_path, monkeypatch):
    app = _app(tmp_path, monkeypatch)
    target = tmp_path / "f.txt"
    target.write_text("hello")
    # extract_tool_calls already merges these; the guard's DUPLICATE check is a backstop
    # for any path that does not (covered by test_duplicate_in_one_turn_runs_once).
    bare = {"tool": "read_file", "arguments": {"path": str(target)}}
    wrapped = {"tool": "read_file", "arguments": {"parameters": {"path": str(target)}}}
    app.chat_history = [("read it", json.dumps([bare, wrapped]))]
    seen = _loop_with(app, monkeypatch, ["All done."])
    dispatched = _count_dispatches(app, monkeypatch)

    await app.run_tool_loop(max_turns=5)

    assert len(dispatched) == 1
    assert seen[0].count("Tool: read_file") == 1
    assert app.buffer_manager.get_script_var("LAST_COMPLETION") == "All done."


@pytest.mark.anyio
async def test_tool_loop_guard_off_restores_old_behaviour(tmp_path, monkeypatch):
    app = _app(tmp_path, monkeypatch)
    app.loop_guard_enabled = False
    target = tmp_path / "f.txt"
    target.write_text("hello")
    call = json.dumps({"tool": "read_file", "arguments": {"path": str(target)}})
    app.chat_history = [("read it", call)]
    _loop_with(app, monkeypatch, [call])
    dispatched = _count_dispatches(app, monkeypatch)

    await app.run_tool_loop(max_turns=6)

    assert len(dispatched) == 6


@pytest.mark.anyio
async def test_refused_calls_are_left_to_the_security_limit(tmp_path, monkeypatch):
    """A repeated denied call is handled by refusal memory and max_refusals_per_loop, not the guard."""
    app = _app(tmp_path, monkeypatch, default_verdict="deny")
    call = json.dumps({"tool": "run_command", "arguments": {"command": "rm -rf /tmp/x"}})
    app.chat_history = [("go", call)]
    _loop_with(app, monkeypatch, [call])

    await app.run_tool_loop(max_turns=25)

    final = app.buffer_manager.get_script_var("LAST_COMPLETION")
    assert "Reached security refusal limit (3)" in final
    assert "Loop guard" not in final


def test_loop_guard_config_and_command(tmp_path):
    from chatybot.chatybot_app import ChatybotApp

    app = ChatybotApp()
    app._apply_loop_guard_config({"loop_guard": "off", "loop_guard_repeats": 5, "loop_guard_window": "12"})
    assert (app.loop_guard_enabled, app.loop_guard_repeats, app.loop_guard_window) == (False, 5, 12)
    app._apply_loop_guard_config({"loop_guard_repeats": 1, "loop_guard_window": True})
    assert app.loop_guard_repeats == 2 and app.loop_guard_window == 12
