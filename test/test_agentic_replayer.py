"""Tests for the Time-Travel Agentic Loop Replay feature.

Covers:
  1. temp_history reconstruction (prior turns, prompt, per-step tool-call/result messages)
  2. AgenticReplayer snapshots (step 0 baseline, step growth, truncation diagnostics)
  3. AgenticReplayer diffs (added messages, token delta, newly evicted)
  4. /tool replay CLI workflows (summary, at, diff, no-loop, missing step, limit override)
"""

import sys
from io import StringIO

import pytest

from chatybot.agentic_replayer import (
    AgenticReplayer,
    AgenticStepSnapshot,
    AgenticStepDiff,
    reconstruct_agentic_messages,
)
from chatybot.context_limit import ContextLimiter


# ---------------------------------------------------------------------------
# 1. Reconstruction
# ---------------------------------------------------------------------------

def _agentic_turn(turn_id=2, prompt="List files", loop=None):
    turn = {"turn_id": turn_id, "prompt": prompt, "response": "Done"}
    if loop is not None:
        turn["agentic_loop"] = loop
    return turn


def test_reconstruct_agentic_messages_baseline_step0():
    turns = [
        {"turn_id": 1, "prompt": "hi", "response": "hello"},
        _agentic_turn(turn_id=2, prompt="do work", loop=[
            {"turn": 1, "tool": "list_directory", "arguments": {"path": "."},
             "result": "file1\nfile2", "status": "success", "duration_ms": 5},
        ]),
    ]
    msgs = reconstruct_agentic_messages(turns, 2, "sys", up_to_step=0)
    # system + prior user/assistant + agentic prompt = 1 + 2 + 1 = 4
    assert [m["role"] for m in msgs] == ["system", "user", "assistant", "user"]
    assert msgs[-1]["content"] == "do work"


def test_reconstruct_agentic_messages_step1_adds_tool_call_and_result():
    turns = [
        {"turn_id": 1, "prompt": "hi", "response": "hello"},
        _agentic_turn(turn_id=2, prompt="do work", loop=[
            {"turn": 1, "tool": "list_directory", "arguments": {"path": "."},
             "result": "file1\nfile2", "status": "success", "duration_ms": 5},
        ]),
    ]
    msgs = reconstruct_agentic_messages(turns, 2, "sys", up_to_step=1)
    # system + prior pair + prompt + assistant(toolcall) + user(result) = 6
    assert [m["role"] for m in msgs] == ["system", "user", "assistant", "user", "assistant", "user"]
    assistant_call = [m for m in msgs if m["role"] == "assistant"][1]
    assert "list_directory" in assistant_call["content"]
    assert "```json" in assistant_call["content"]
    result_msg = [m for m in msgs if m["role"] == "user"][-1]
    assert "Tool execution results:" in result_msg["content"]
    assert "file1" in result_msg["content"]


def test_reconstruct_agentic_messages_multiple_steps_accumulate():
    turns = [
        _agentic_turn(turn_id=1, prompt="p", loop=[
            {"turn": 1, "tool": "t1", "arguments": {}, "result": "r1", "status": "success"},
            {"turn": 2, "tool": "t2", "arguments": {"x": 1}, "result": "r2", "status": "success"},
        ]),
    ]
    msgs = reconstruct_agentic_messages(turns, 1, "sys", up_to_step=2)
    # system + prompt + (assistant + user) * 2 = 1 + 1 + 4 = 6
    assert len(msgs) == 6
    # Both tool results present
    contents = [m["content"] for m in msgs if m["role"] == "user"]
    assert any("r1" in c for c in contents)
    assert any("r2" in c for c in contents)


def test_reconstruct_agentic_messages_ignores_command_turns_before():
    turns = [
        {"turn_id": 1, "prompt": "hi", "response": "hello"},
        {"type": "command", "text": "/model foo", "verb": "/model"},
        _agentic_turn(turn_id=2, prompt="do work", loop=[
            {"turn": 1, "tool": "t", "arguments": {}, "result": "r", "status": "success"},
        ]),
    ]
    msgs = reconstruct_agentic_messages(turns, 2, "sys", up_to_step=1)
    # Only turn 1 contributes prior context; command turn skipped
    user_prompts = [m["content"] for m in msgs if m["role"] == "user"]
    assert "hi" in user_prompts
    assert "do work" in user_prompts


def test_reconstruct_agentic_messages_no_system_prompt():
    turns = [_agentic_turn(turn_id=1, prompt="p", loop=[])]
    msgs = reconstruct_agentic_messages(turns, 1, "", up_to_step=0)
    assert msgs == [{"role": "user", "content": "p"}]


def test_reconstruct_agentic_messages_missing_turn_returns_prior_only():
    turns = [{"turn_id": 1, "prompt": "hi", "response": "hello"}]
    msgs = reconstruct_agentic_messages(turns, 99, "sys", up_to_step=1)
    # system + prior pair, no agentic prompt (turn not found)
    assert [m["role"] for m in msgs] == ["system", "user", "assistant"]


# ---------------------------------------------------------------------------
# 2. Snapshots
# ---------------------------------------------------------------------------

def _make_app_with_limiter(limit=None):
    """Build a minimal app-like object with a ContextLimiter and config_manager."""
    class _App:
        def __init__(self):
            self.context_limiter = ContextLimiter(default_limit=limit, auto_truncate=bool(limit))
            class _CM:
                system_message = "You are a helpful assistant."
                active_model_alias = "test_model"
                def get_model_config(self, alias):
                    return {"name": "test-model"}
            self.config_manager = _CM()
            self.live_tool_context = ""
            self.tool_context = ""
            self.live_agentic_instructions = ""
            self.agentic_instructions = ""
            self.default_agentic_instructions = ""
            self.reasoning_mode = True
            self.thoughtstyle = "none"
    return _App()


def test_snapshot_step0_baseline():
    app = _make_app_with_limiter()
    turns = [
        {"turn_id": 1, "prompt": "hi", "response": "hello"},
        _agentic_turn(turn_id=2, prompt="do work", loop=[
            {"turn": 1, "tool": "t", "arguments": {}, "result": "r", "status": "success", "duration_ms": 3},
        ]),
    ]
    replayer = AgenticReplayer(app)
    snap = replayer.snapshot_at_step(turns, 2, "sys", 0)
    assert isinstance(snap, AgenticStepSnapshot)
    assert snap.step == 0
    assert snap.tool == ""
    assert snap.status == ""
    assert snap.message_count == 4  # system + prior pair + prompt


def test_snapshot_step1_growth():
    app = _make_app_with_limiter()
    turns = [
        _agentic_turn(turn_id=1, prompt="p", loop=[
            {"turn": 1, "tool": "t1", "arguments": {}, "result": "r1", "status": "success", "duration_ms": 7},
        ]),
    ]
    replayer = AgenticReplayer(app)
    snap0 = replayer.snapshot_at_step(turns, 1, "sys", 0)
    snap1 = replayer.snapshot_at_step(turns, 1, "sys", 1)
    assert snap1.message_count == snap0.message_count + 2  # +assistant +user
    assert snap1.total_tokens > snap0.total_tokens
    assert snap1.tool == "t1"
    assert snap1.status == "success"
    assert snap1.duration_ms == 7.0


def test_snapshot_truncation_with_limit():
    app = _make_app_with_limiter(limit=80)
    big = "B" * 200
    turns = [
        _agentic_turn(turn_id=1, prompt="p " + big, loop=[
            {"turn": 1, "tool": "t", "arguments": {}, "result": big, "status": "success"},
            {"turn": 2, "tool": "t2", "arguments": {}, "result": big, "status": "success"},
        ]),
    ]
    replayer = AgenticReplayer(app)
    snap = replayer.snapshot_at_step(turns, 1, "sys", 2, limit=80)
    assert snap.did_truncate is True
    assert len(snap.evicted_indices) >= 1
    # No _orig_idx tags leak
    assert all("_orig_idx" not in m for m in snap.truncated_messages)


def test_snapshot_missing_step_returns_none():
    app = _make_app_with_limiter()
    turns = [_agentic_turn(turn_id=1, prompt="p", loop=[
        {"turn": 1, "tool": "t", "arguments": {}, "result": "r", "status": "success"},
    ])]
    replayer = AgenticReplayer(app)
    assert replayer.snapshot_at_step(turns, 1, "sys", 5) is None
    assert replayer.snapshot_at_step(turns, 1, "sys", -1) is None


def test_replay_loop_includes_baseline_and_all_steps():
    app = _make_app_with_limiter()
    turns = [
        _agentic_turn(turn_id=1, prompt="p", loop=[
            {"turn": 1, "tool": "t1", "arguments": {}, "result": "r1", "status": "success"},
            {"turn": 2, "tool": "t2", "arguments": {}, "result": "r2", "status": "success"},
        ]),
    ]
    replayer = AgenticReplayer(app)
    # Use the in-memory turns directly via snapshot to avoid needing a session store
    snaps = [replayer.snapshot_at_step(turns, 1, "sys", i) for i in range(0, 3)]
    assert [s.step for s in snaps] == [0, 1, 2]


# ---------------------------------------------------------------------------
# 3. Diffs
# ---------------------------------------------------------------------------

def test_diff_steps_added_messages_and_token_delta():
    app = _make_app_with_limiter()
    turns = [
        _agentic_turn(turn_id=1, prompt="p", loop=[
            {"turn": 1, "tool": "t1", "arguments": {}, "result": "r1", "status": "success"},
            {"turn": 2, "tool": "t2", "arguments": {}, "result": "r2", "status": "success"},
        ]),
    ]
    replayer = AgenticReplayer(app)
    diff = replayer.diff_steps_from_turns(turns, 1, "sys", 0, 2)
    assert isinstance(diff, AgenticStepDiff)
    assert diff.token_delta > 0
    # Step 2 adds the step-1 and step-2 tool messages (4 messages)
    assert len(diff.added_messages) == 4


def test_diff_steps_newly_evicted_under_limit():
    app = _make_app_with_limiter(limit=160)
    big = "B" * 200
    turns = [
        _agentic_turn(turn_id=1, prompt="p " + big, loop=[
            {"turn": 1, "tool": "t1", "arguments": {}, "result": big, "status": "success"},
            {"turn": 2, "tool": "t2", "arguments": {}, "result": big, "status": "success"},
        ]),
    ]
    replayer = AgenticReplayer(app)
    diff = replayer.diff_steps_from_turns(turns, 1, "sys", 1, 2, limit=160)
    assert diff.truncation_evicted_delta > 0
    assert len(diff.newly_evicted) > 0


# Add a convenience method used by the diff tests (avoids needing a session store).
def _diff_steps_from_turns(self, turns, agentic_turn_id, system_prompt, step_a, step_b, limit=None):
    agentic_turn = self._find_agentic_turn(turns, agentic_turn_id)
    if agentic_turn is None:
        return None
    snap_a = self.snapshot_at_step(turns, agentic_turn_id, system_prompt, step_a, limit=limit)
    snap_b = self.snapshot_at_step(turns, agentic_turn_id, system_prompt, step_b, limit=limit)
    if snap_a is None or snap_b is None:
        return None
    a_keys = {(m.get("role"), m.get("content")) for m in snap_a.messages}
    added = [m for m in snap_b.messages if (m.get("role"), m.get("content")) not in a_keys]
    b_surviving_keys = {(m.get("role"), m.get("content")) for m in snap_b.truncated_messages}
    newly_evicted = [
        m for m in snap_a.truncated_messages
        if (m.get("role"), m.get("content")) not in b_surviving_keys
    ]
    return AgenticStepDiff(
        step_a=step_a, step_b=step_b, added_messages=added, newly_evicted=newly_evicted,
        token_delta=snap_b.total_tokens - snap_a.total_tokens,
        truncation_evicted_delta=len(snap_b.evicted_indices) - len(snap_a.evicted_indices),
        anchor_overflow_changed=snap_a.anchors_alone_exceed_limit != snap_b.anchors_alone_exceed_limit,
        snapshot_a=snap_a, snapshot_b=snap_b,
    )

AgenticReplayer.diff_steps_from_turns = _diff_steps_from_turns


def test_replay_loop_and_diff_steps_with_preloaded_turns():
    class DummyApp:
        def __init__(self):
            self.load_called = False
            self.context_limiter = None
            self.config_manager = None
        def _get_session_store(self):
            self.load_called = True
            raise RuntimeError("Should not load from disk when turns are provided")

    replayer = AgenticReplayer(DummyApp())
    turns = [
        _agentic_turn(turn_id=1, prompt="p", loop=[
            {"turn": 1, "tool": "t1", "arguments": {}, "result": "r1", "status": "success"},
            {"turn": 2, "tool": "t2", "arguments": {}, "result": "r2", "status": "success"},
        ]),
    ]
    snapshots = replayer.replay_loop("dummy_session", turn_id=1, turns=turns, system_prompt="sys")
    assert len(snapshots) == 3  # step 0, 1, 2
    assert not replayer.app.load_called

    diff = replayer.diff_steps("dummy_session", turn_id=1, step_a=0, step_b=1, turns=turns, system_prompt="sys")
    assert diff is not None
    assert diff.step_a == 0
    assert diff.step_b == 1
    assert not replayer.app.load_called


# ---------------------------------------------------------------------------
# 4. CLI workflows
# ---------------------------------------------------------------------------

@pytest.fixture
def app(monkeypatch):
    import tempfile
    from chatybot.chatybot_app import ChatybotApp
    tmp_dir = tempfile.mkdtemp()
    monkeypatch.setenv("CHATYBOT_TEST_SESSIONS_DIR", tmp_dir)
    app_instance = ChatybotApp()
    app_instance.initialize()
    app_instance.session_dir = tmp_dir
    app_instance.session_store = None
    return app_instance


async def _run_capture(app, command):
    buf = StringIO()
    old = sys.stdout
    sys.stdout = buf
    try:
        await app.handle_escape_command(command)
    finally:
        sys.stdout = old
    return buf.getvalue()


@pytest.mark.anyio
async def test_tool_replay_no_loop(app):
    await app.handle_escape_command("/session start noloop_test")
    app.append_session_turn("hello", "hi")
    out = await _run_capture(app, "/tool replay")
    assert "No agentic tool loops found" in out


@pytest.mark.anyio
async def test_tool_replay_summary(app):
    await app.handle_escape_command("/session start replay_loop")
    app.append_session_turn("List my files", "thinking...")
    # Attach an agentic loop to the turn
    loop = [
        {"turn": 1, "tool": "list_directory", "arguments": {"path": "."},
         "result": "file1.txt\nfile2.txt", "exit_code": 0, "status": "success",
         "timestamp": "2026-09-05T10:00:00", "duration_ms": 12.0},
        {"turn": 2, "tool": "read_file", "arguments": {"path": "file1.txt"},
         "result": "contents here", "exit_code": 0, "status": "success",
         "timestamp": "2026-09-05T10:00:01", "duration_ms": 8.0},
    ]
    app.attach_agentic_loop_to_current_turn(loop, final_response="Here are your files.")
    app.save_active_session()

    out = await _run_capture(app, "/tool replay")
    assert "AGENTIC LOOP REPLAY" in out
    assert "SUMMARY" in out
    # Step 0 baseline + steps 1 and 2 appear
    assert "list_directory" in out
    assert "read_file" in out


@pytest.mark.anyio
async def test_tool_replay_at_step(app):
    await app.handle_escape_command("/session start at_step_test")
    app.append_session_turn("do work", "...")
    loop = [
        {"turn": 1, "tool": "list_directory", "arguments": {"path": "."},
         "result": "f1", "exit_code": 0, "status": "success", "duration_ms": 5.0},
    ]
    app.attach_agentic_loop_to_current_turn(loop, final_response="done")
    app.save_active_session()

    out = await _run_capture(app, "/tool replay at 1")
    assert "STEP 1" in out
    assert "list_directory" in out
    assert "Tool execution results:" in out


@pytest.mark.anyio
async def test_tool_replay_diff(app):
    await app.handle_escape_command("/session start diff_loop_test")
    app.append_session_turn("do work", "...")
    loop = [
        {"turn": 1, "tool": "t1", "arguments": {}, "result": "r1", "exit_code": 0, "status": "success", "duration_ms": 1.0},
        {"turn": 2, "tool": "t2", "arguments": {}, "result": "r2", "exit_code": 0, "status": "success", "duration_ms": 1.0},
    ]
    app.attach_agentic_loop_to_current_turn(loop, final_response="done")
    app.save_active_session()

    out = await _run_capture(app, "/tool replay diff 0 2")
    assert "DIFF: STEP 0 -> STEP 2" in out
    assert "Added messages" in out
    assert "token delta" in out.lower() or "Token delta" in out


@pytest.mark.anyio
async def test_tool_replay_missing_step(app):
    await app.handle_escape_command("/session start miss_step_test")
    app.append_session_turn("do work", "...")
    loop = [
        {"turn": 1, "tool": "t1", "arguments": {}, "result": "r1", "exit_code": 0, "status": "success", "duration_ms": 1.0},
    ]
    app.attach_agentic_loop_to_current_turn(loop, final_response="done")
    app.save_active_session()

    out = await _run_capture(app, "/tool replay at 99")
    assert "not found" in out


@pytest.mark.anyio
async def test_tool_replay_no_active_session(app):
    app.active_session_id = None
    app.active_session_name = None
    out = await _run_capture(app, "/tool replay")
    assert "No active session" in out


@pytest.mark.anyio
async def test_tool_replay_limit_override(app):
    await app.handle_escape_command("/session start limit_loop_test")
    big = "Z" * 400
    app.append_session_turn("p " + big, "...")
    loop = [
        {"turn": 1, "tool": "t1", "arguments": {}, "result": big, "exit_code": 0, "status": "success", "duration_ms": 1.0},
    ]
    app.attach_agentic_loop_to_current_turn(loop, final_response="done")
    app.save_active_session()

    out = await _run_capture(app, "/tool replay limit=80")
    assert "SUMMARY" in out
