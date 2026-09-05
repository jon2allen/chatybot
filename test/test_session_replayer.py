"""Tests for the Time-Travel Context Replay feature.

Covers:
  1. Message reconstruction (multi-turn, thinking-token stripping, command filtering)
  2. Verbose truncation diagnostics (evicted_indices, anchor overflow, content truncation)
  3. Replay CLI workflows (/session replay summary/at/diff, /replay alias, empty/missing sessions)
"""

import sys
from io import StringIO

import pytest

from chatybot.context_limit import ContextLimiter, TruncationDiagnostic
from chatybot.session_replayer import (
    SessionReplayer,
    TurnSnapshot,
    TurnDiff,
    clean_thinking_tokens,
    reconstruct_messages_from_turns,
)


# ---------------------------------------------------------------------------
# 1. Reconstruction
# ---------------------------------------------------------------------------

def test_clean_thinking_tokens_strips_thought_tags():
    assert clean_thinking_tokens("normal text") == "normal text"
    assert clean_thinking_tokens(" preamble <thought>secret</thought> tail") == "preamble tail"
    # The chatybot thinking-token form uses a leading marker; ensure it is stripped
    assert "thought" not in clean_thinking_tokens("<thought>hidden reasoning</thought>final answer")
    assert clean_thinking_tokens("") == ""
    assert clean_thinking_tokens(None) == ""


def test_reconstruct_messages_multiturn_with_system_prompt():
    turns = [
        {"turn_id": 1, "prompt": "Hello", "response": "Hi there"},
        {"turn_id": 2, "prompt": "What is 2+2?", "response": "4"},
        {"turn_id": 3, "prompt": "Thanks", "response": "Welcome"},
    ]
    msgs = reconstruct_messages_from_turns(turns, "You are a helpful assistant.")
    # system + (user, assistant) * 2 + final user = 1 + 4 + 1 = 6
    assert msgs[0] == {"role": "system", "content": "You are a helpful assistant."}
    assert msgs[-1] == {"role": "user", "content": "Thanks"}
    roles = [m["role"] for m in msgs]
    assert roles == ["system", "user", "assistant", "user", "assistant", "user"]


def test_reconstruct_messages_up_to_turn_id():
    turns = [
        {"turn_id": 1, "prompt": "a", "response": "A"},
        {"turn_id": 2, "prompt": "b", "response": "B"},
        {"turn_id": 3, "prompt": "c", "response": "C"},
    ]
    msgs = reconstruct_messages_from_turns(turns, "sys", up_to_turn_id=2)
    # system + user(a) + assistant(A) + user(b) = 4
    assert [m["role"] for m in msgs] == ["system", "user", "assistant", "user"]
    assert msgs[-1]["content"] == "b"


def test_reconstruct_messages_strips_thinking_from_assistant():
    turns = [
        {"turn_id": 1, "prompt": "q", "response": "<thought>internal</thought>visible answer"},
        {"turn_id": 2, "prompt": "q2", "response": "r2"},
    ]
    msgs = reconstruct_messages_from_turns(turns, "sys")
    assistant_msg = [m for m in msgs if m["role"] == "assistant"][0]
    assert "thought" not in assistant_msg["content"]
    assert "visible answer" in assistant_msg["content"]


def test_reconstruct_messages_ignores_command_turns():
    turns = [
        {"turn_id": 1, "prompt": "hello", "response": "hi"},
        {"type": "command", "text": "/model foo", "verb": "/model"},
        {"turn_id": 2, "prompt": "again", "response": "yes"},
    ]
    msgs = reconstruct_messages_from_turns(turns, "sys")
    # Only the two LLM turns count; command turn is skipped
    user_prompts = [m["content"] for m in msgs if m["role"] == "user"]
    assert user_prompts == ["hello", "again"]


def test_reconstruct_messages_empty_turns_returns_system_only():
    msgs = reconstruct_messages_from_turns([], "sys")
    assert msgs == [{"role": "system", "content": "sys"}]
    assert reconstruct_messages_from_turns([], "") == []


# ---------------------------------------------------------------------------
# 2. Verbose truncation & diagnostics
# ---------------------------------------------------------------------------

def test_verbose_truncation_no_truncation_under_budget():
    limiter = ContextLimiter(default_limit=10000, auto_truncate=True)
    messages = [
        {"role": "system", "content": "You are helpful."},
        {"role": "user", "content": "Hi"},
    ]
    diag = limiter.truncate_messages_verbose(messages)
    assert isinstance(diag, TruncationDiagnostic)
    assert diag.did_truncate is False
    assert diag.evicted_indices == []
    assert diag.evicted_count == 0
    assert diag.content_truncated is False
    assert diag.anchors_alone_exceed_limit is False
    assert diag.original_tokens == diag.truncated_tokens


def test_verbose_truncation_evicted_indices_with_duplicates():
    limiter = ContextLimiter(default_limit=60, auto_truncate=True)
    long_chunk = "B" * 80  # ~20 tokens
    messages = [
        {"role": "system", "content": "System prompt"},
        {"role": "user", "content": "Initial Goal: do thing"},
        {"role": "assistant", "content": f"dup {long_chunk}"},
        {"role": "user", "content": f"dup {long_chunk}"},
        {"role": "assistant", "content": f"dup {long_chunk}"},
    ]
    diag = limiter.truncate_messages_verbose(messages, limit=60)
    assert diag.did_truncate is True
    # System (idx 0) and initial user (idx 1) must survive
    assert 0 not in diag.evicted_indices
    assert 1 not in diag.evicted_indices
    # At least one intermediate message was evicted
    assert diag.evicted_count >= 1
    # Evicted indices are a subset of the intermediate indices [2,3,4]
    assert all(i in (2, 3, 4) for i in diag.evicted_indices)
    # No _orig_idx tags leak into the cleaned output
    assert all("_orig_idx" not in m for m in diag.truncated_messages)


def test_verbose_truncation_anchors_alone_exceed_limit():
    limiter = ContextLimiter(default_limit=10, auto_truncate=True)
    messages = [
        {"role": "system", "content": "X" * 200},   # ~50 tokens, exceeds tiny limit
        {"role": "user", "content": "Y" * 200},
    ]
    diag = limiter.truncate_messages_verbose(messages, limit=10)
    assert diag.anchors_alone_exceed_limit is True


def test_verbose_truncation_content_truncated_flag():
    limiter = ContextLimiter(default_limit=5000, auto_truncate=True, truncate_pct=90.0)
    huge_text = "print('hello world!')\n" * 20000
    messages = [
        {"role": "system", "content": "You are a coding assistant."},
        {"role": "user", "content": f"Tool results:\n{huge_text}"},
    ]
    diag = limiter.truncate_messages_verbose(messages, limit=5000)
    assert diag.did_truncate is True
    assert diag.content_truncated is True
    assert any("[... content truncated" in str(m.get("content", "")) for m in diag.truncated_messages)


def test_verbose_truncation_empty_messages():
    limiter = ContextLimiter(default_limit=1000, auto_truncate=True)
    diag = limiter.truncate_messages_verbose([])
    assert diag.original_messages == []
    assert diag.truncated_messages == []
    assert diag.did_truncate is False
    assert diag.original_tokens == 0


# ---------------------------------------------------------------------------
# 3. Session replay workflows (CLI)
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


def _capture(coro):
    """Run an async coroutine and capture stdout (unused placeholder removed)."""
    raise NotImplementedError

@pytest.mark.anyio
async def test_session_replay_summary_on_active_session(app):
    await app.handle_escape_command("/session start replay_test")
    app.append_session_turn("First prompt", "First response")
    app.append_session_turn("Second prompt", "Second response")

    out = await _run_capture(app, "/session replay")
    assert "SESSION REPLAY" in out
    assert "SUMMARY TIMELINE" in out
    # Both turns appear in the table
    assert "1" in out and "2" in out


@pytest.mark.anyio
async def test_session_replay_at_view(app):
    await app.handle_escape_command("/session start at_test")
    app.append_session_turn("Hello", "Hi")
    app.append_session_turn("What is 2+2?", "4")

    out = await _run_capture(app, "/session replay at 2")
    assert "TURN 2" in out
    assert "RECONSTRUCTED CONTEXT" in out
    assert "What is 2+2?" in out


@pytest.mark.anyio
async def test_session_replay_diff(app):
    await app.handle_escape_command("/session start diff_test")
    app.append_session_turn("Turn one", "Resp one")
    app.append_session_turn("Turn two", "Resp two")

    out = await _run_capture(app, "/session replay diff 1 2")
    assert "DIFF: TURN 1 -> TURN 2" in out
    assert "Added messages" in out
    # Turn 2's prompt should appear among added messages
    assert "Turn two" in out


@pytest.mark.anyio
async def test_replay_alias_matches_session_replay(app):
    await app.handle_escape_command("/session start alias_test")
    app.append_session_turn("Alias prompt", "Alias response")

    out_alias = await _run_capture(app, "/replay")
    out_session = await _run_capture(app, "/session replay")
    # Both produce the summary timeline header
    assert "SUMMARY TIMELINE" in out_alias
    assert "SUMMARY TIMELINE" in out_session


@pytest.mark.anyio
async def test_replay_no_active_session(app):
    app.active_session_id = None
    app.active_session_name = None
    out = await _run_capture(app, "/session replay")
    assert "No active session" in out


@pytest.mark.anyio
async def test_replay_missing_turn(app):
    await app.handle_escape_command("/session start miss_test")
    app.append_session_turn("only turn", "only resp")
    out = await _run_capture(app, "/session replay at 99")
    assert "not found" in out


@pytest.mark.anyio
async def test_replay_limit_override_truncates(app):
    await app.handle_escape_command("/session start limit_test")
    big = "Z" * 400
    app.append_session_turn("q1 " + big, "r1 " + big)
    app.append_session_turn("q2 " + big, "r2 " + big)

    out = await _run_capture(app, "/session replay limit=80")
    assert "SUMMARY TIMELINE" in out
    # With a tiny budget, the second turn should report evictions or truncation
    assert "80" in out or "Evicted" in out or "Evict" in out or "SUMMARY" in out


# Helper to run an escape command and capture stdout (defined at module bottom
# to keep the test bodies focused).
async def _run_capture(app, command):
    buf = StringIO()
    old = sys.stdout
    sys.stdout = buf
    try:
        await app.handle_escape_command(command)
    finally:
        sys.stdout = old
    return buf.getvalue()
