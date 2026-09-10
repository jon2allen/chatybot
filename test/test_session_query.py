"""
Unit and integration tests for session query engine and /session query command.
"""

import os
import pytest
from datetime import datetime

from chatybot.query.base import (
    BaseQueryEngine,
    QueryRequest,
    QueryResponse,
    register_query_engine,
    get_query_engine,
    list_query_engines,
)
from chatybot.tools.context_query import session_search
from chatybot.buffer_manager import BufferManager


class MockApp:
    def __init__(self, tmp_path):
        self.active_session_id = "test_sess_01"
        self.active_session_name = "Auth Refactoring"
        self.session_notes = "Important: fix auth JWT bearer token bug before release"
        self.session_dir = str(tmp_path / "sessions")
        self.scratch_dir = str(tmp_path / "scratch")
        os.makedirs(self.scratch_dir, exist_ok=True)
        
        self.session_turns = [
            {
                "prompt": "How do we implement database migration with rollback?",
                "response": "Use alembic with downgrade scripts for rollback.",
                "timestamp": "2026-04-10T10:00:00",
            },
            {
                "prompt": "We encountered an auth error with expired token",
                "response": "Refresh the token when receiving HTTP 401 unauthorized.",
                "timestamp": "2026-04-12T14:30:00",
            }
        ]
        self.buffer_manager = BufferManager()

    def get_scratch_dir(self, create=False):
        return self.scratch_dir


def test_query_engine_pluggability():
    # Verify default engine is registered
    engines = list_query_engines()
    assert "grep" in engines
    
    default_engine = get_query_engine()
    assert default_engine.name == "grep"

    # Register a mock custom engine
    @register_query_engine("custom_mock")
    class MockCustomEngine(BaseQueryEngine):
        name = "custom_mock"
        def search(self, app, request):
            return QueryResponse(total_matches=999, matches=[], engine="custom_mock")

    assert "custom_mock" in list_query_engines()
    custom_inst = get_query_engine("custom_mock")
    assert custom_inst.name == "custom_mock"


def test_grep_engine_and_or_matching(tmp_path):
    app = MockApp(tmp_path)
    engine = get_query_engine("grep")

    # 1. Test AND operator: both 'auth' and 'token' in Turn 2
    req_and = QueryRequest(terms=["auth", "token"], operator="AND")
    res_and = engine.search(app, req_and)
    assert res_and.total_matches == 2  # Turn 2 + Note
    assert res_and.matches[0].size_bytes > 0
    assert res_and.to_dict()["matches"][0]["size_bytes"] > 0
    
    # 2. Test AND operator failure: 'migration' and 'auth' are in different turns
    req_and_fail = QueryRequest(terms=["migration", "auth"], operator="AND")
    res_and_fail = engine.search(app, req_and_fail)
    assert res_and_fail.total_matches == 0

    # 3. Test OR operator: matches Turn 1 ('migration') and Turn 2 ('auth') and Note ('auth')
    req_or = QueryRequest(terms=["migration", "auth"], operator="OR")
    res_or = engine.search(app, req_or)
    assert res_or.total_matches == 3


def test_grep_engine_date_filtering(tmp_path):
    app = MockApp(tmp_path)
    engine = get_query_engine("grep")

    # Turn 1 is 2026-04-10, Turn 2 is 2026-04-12
    req_date = QueryRequest(
        terms=["auth"],
        since_dt=datetime(2026, 4, 11, 0, 0, 0),
        until_dt=datetime(2026, 4, 13, 0, 0, 0)
    )
    res = engine.search(app, req_date)
    # Turn 2 matches and falls within the date filter
    turn_matches = [m for m in res.matches if m.role == "exchange"]
    assert len(turn_matches) == 1
    assert turn_matches[0].turn_id == 2


def test_grep_engine_scratchpad_files(tmp_path):
    app = MockApp(tmp_path)
    # Write a disposable script in scratch directory
    scratch_file = os.path.join(app.scratch_dir, "test_task.py")
    with open(scratch_file, "w") as f:
        f.write("# Script to run database migration\nprint('starting migration')\n")

    engine = get_query_engine("grep")
    req = QueryRequest(terms=["migration"], include_scratch=True)
    res = engine.search(app, req)
    
    scratch_matches = [m for m in res.matches if m.source == "scratch"]
    assert len(scratch_matches) >= 1
    assert "test_task.py" in scratch_matches[0].metadata["file"]


def test_scratch_dir_deduplication(tmp_path):
    app = MockApp(tmp_path)
    scratch_file = os.path.join(app.scratch_dir, "task.txt")
    with open(scratch_file, "w") as f:
        f.write("unique token to match\n")

    # Point session_dir so that its parent / scratch is the same directory
    app.session_dir = str(tmp_path / "sessions")
    os.makedirs(app.session_dir, exist_ok=True)
    # Even if get_scratch_dir returns a path ending with /., realpath canonicalizes it
    app.get_scratch_dir = lambda create=False: str(tmp_path / "scratch" / ".")

    engine = get_query_engine("grep")
    req = QueryRequest(terms=["unique", "token"], include_scratch=True)
    res = engine.search(app, req)

    scratch_matches = [m for m in res.matches if m.source == "scratch"]
    assert len(scratch_matches) == 1


def test_scratch_file_unreadable_mtime(tmp_path, monkeypatch):
    app = MockApp(tmp_path)
    scratch_file = os.path.join(app.scratch_dir, "task_err.txt")
    with open(scratch_file, "w") as f:
        f.write("scratch test data\n")

    # Simulate OSError when fetching mtime
    def mock_getmtime(path):
        if "task_err.txt" in path:
            raise OSError("Permission denied")
        return os.path.getmtime(path)

    monkeypatch.setattr(os.path, "getmtime", mock_getmtime)
    engine = get_query_engine("grep")

    # 1. Under active date filter, unreadable mtime (mtime=None) is excluded
    req_date = QueryRequest(
        terms=["scratch"],
        include_scratch=True,
        since_dt=datetime(2026, 1, 1),
    )
    res_date = engine.search(app, req_date)
    assert len([m for m in res_date.matches if m.source == "scratch"]) == 0

    # 2. Without date filter, file is still searched and matched
    req_no_date = QueryRequest(terms=["scratch"], include_scratch=True)
    res_no_date = engine.search(app, req_no_date)
    scratch_matches = [m for m in res_no_date.matches if m.source == "scratch"]
    assert len(scratch_matches) == 1
    assert scratch_matches[0].timestamp is None




def test_session_search_llm_tool(tmp_path):
    app = MockApp(tmp_path)
    
    # Test tool invocation
    res = session_search(
        query="auth token",
        operator="AND",
        since="2026-04-01",
        target_variable="MY_TOOL_VAR",
        app=app,
    )
    
    assert res["status"] == "success"
    assert res["total_matches"] >= 1
    
    # Verify protected variable and custom variable were set
    assert "SESSION_QUERY" in app.buffer_manager.script_vars
    assert "MY_TOOL_VAR" in app.buffer_manager.script_vars
    assert app.buffer_manager.script_vars["MY_TOOL_VAR"]["total_matches"] == res["total_matches"]


def test_session_search_ids_only(tmp_path):
    app = MockApp(tmp_path)
    
    res = session_search(
        query="auth",
        ids_only=True,
        target_variable="SIDS_VAR",
        app=app,
    )
    assert res["status"] == "success"
    assert "session_ids" in res
    assert "test_sess_01" in res["session_ids"]
    assert app.buffer_manager.script_vars["SIDS_VAR"] == ["test_sess_01"]


def test_session_search_full_content(tmp_path):
    app = MockApp(tmp_path)
    
    res = session_search(
        query="auth",
        full=True,
        app=app,
    )
    assert res["status"] == "success"
    assert res["total_matches"] >= 1
    first_match = res["matches"][0]
    assert "We encountered an auth error with expired token" in first_match["snippet"]
    assert first_match["full_text"] is not None


def test_total_matches_unbounded_by_limit(tmp_path):
    app = MockApp(tmp_path)
    # Add several matching turns to active session
    app.session_turns = [
        {"prompt": f"test query term item {i}", "response": "answer", "timestamp": "2026-04-10T10:00:00"}
        for i in range(10)
    ]
    engine = get_query_engine("grep")
    # Request limit of 3
    req = QueryRequest(terms=["test"], limit=3)
    res = engine.search(app, req)

    # matches list is capped at limit 3, but total_matches reflects all 10 hits
    assert len(res.matches) == 3
    assert res.total_matches == 10


def test_missing_timestamp_excluded_under_date_filter(tmp_path):
    app = MockApp(tmp_path)
    # 1 turn has a timestamp inside range, 1 turn has timestamp outside range, 1 turn has NO timestamp
    app.session_turns = [
        {"prompt": "auth token in range", "response": "ok", "timestamp": "2026-04-12T12:00:00"},
        {"prompt": "auth token out of range", "response": "ok", "timestamp": "2026-01-01T12:00:00"},
        {"prompt": "auth token without timestamp", "response": "ok", "timestamp": None},
    ]
    engine = get_query_engine("grep")
    req = QueryRequest(
        terms=["auth"],
        since_dt=datetime(2026, 4, 1, 0, 0, 0),
        until_dt=datetime(2026, 4, 30, 0, 0, 0),
    )
    res = engine.search(app, req)
    # Only the turn with in-range timestamp should match; missing timestamp must not bypass filter
    turn_matches = [m for m in res.matches if m.role == "exchange"]
    assert len(turn_matches) == 1
    assert "in range" in turn_matches[0].full_text


def test_ids_only_not_bounded_by_limit(tmp_path):
    app = MockApp(tmp_path)
    # Mock saved sessions store
    class MockStore:
        def list_sessions(self, limit=None, since_dt=None):
            return [
                {"sid": "sess_1"},
                {"sid": "sess_2"},
                {"sid": "sess_3"},
            ]
        def load_session(self, sid):
            return ({"notes": None}, [{"prompt": f"match term in {sid}", "response": "res"}])

    class MockAppWithStore(MockApp):
        def get_session_store(self):
            return MockStore()

    store_app = MockAppWithStore(tmp_path)
    store_app.active_session_id = None
    store_app.session_turns = []
    store_app.session_notes = None

    engine = get_query_engine("grep")
    # Request with limit=1 and ids_only=True
    req = QueryRequest(terms=["match"], limit=1, ids_only=True)
    res = engine.search(store_app, req)

    # All 3 sessions should be found despite limit=1
    assert len(res.session_ids) == 3
    assert res.total_matches == 3
    assert sorted(res.session_ids) == ["sess_1", "sess_2", "sess_3"]


def test_store_error_isolation(tmp_path):
    # If one session file raises an exception when loaded, other sessions are still searched
    class CorruptStore:
        def list_sessions(self, limit=None, since_dt=None):
            return [
                {"sid": "sess_corrupt"},
                {"sid": "sess_healthy"},
            ]
        def load_session(self, sid):
            if sid == "sess_corrupt":
                raise IOError("Corrupted json file")
            return ({"notes": None}, [{"prompt": "healthy match", "response": "res"}])

    class MockAppCorrupt(MockApp):
        def get_session_store(self):
            return CorruptStore()

    corrupt_app = MockAppCorrupt(tmp_path)
    corrupt_app.active_session_id = None
    corrupt_app.session_turns = []
    corrupt_app.session_notes = None

    engine = get_query_engine("grep")
    req = QueryRequest(terms=["healthy"])
    res = engine.search(corrupt_app, req)

    assert res.total_matches == 1
    assert res.matches[0].session_id == "sess_healthy"


def test_query_match_reports_full_session_size(tmp_path):
    class SizedStore:
        def list_sessions(self, limit=None, since_dt=None):
            return [{"sid": "large_sess"}]
        def load_session(self, sid):
            return ({"notes": None}, [{"prompt": "hi", "response": "session search"}])
        def get_session_size(self, sid):
            return 45000

    class MockAppSized(MockApp):
        def get_session_store(self):
            return SizedStore()

    sized_app = MockAppSized(tmp_path)
    sized_app.active_session_id = None
    sized_app.session_turns = []
    sized_app.session_notes = None

    engine = get_query_engine("grep")
    req = QueryRequest(terms=["session"])
    res = engine.search(sized_app, req)

    assert res.total_matches == 1
    match = res.matches[0]
    # size_bytes must be the full session size (45,000 bytes), not the short turn text
    assert match.size_bytes == 45000
    assert "turn_bytes" not in match.metadata
    # res.sessions must also report the entire session size
    assert len(res.sessions) == 1
    assert res.sessions[0]["session_id"] == "large_sess"
    assert res.sessions[0]["size_bytes"] == 45000


def test_session_search_empty_query_with_filters(tmp_path):
    app = MockApp(tmp_path)
    res = session_search(
        query="",
        since="yesterday",
        ids_only=True,
        app=app,
    )
    assert res["status"] == "success"
    assert "sessions" in res
    assert len(res["sessions"]) >= 1
    # Check that each entry in sessions has the entire session size
    for s_info in res["sessions"]:
        assert "session_id" in s_info
        assert "size_bytes" in s_info
        assert isinstance(s_info["size_bytes"], int)


def test_session_search_empty_query_without_filters_errors():
    res = session_search(query="")
    assert res["status"] == "error"
    assert "cannot be empty" in res["message"]


def test_lazy_size_evaluation_and_caching(tmp_path):
    size_call_counts = {"match_sess": 0, "unmatched_sess": 0}

    class InstrumentedStore:
        def list_sessions(self, limit=None, since_dt=None):
            return [
                {"sid": "match_sess", "size_bytes": 12345},
                {"sid": "unmatched_sess"},
            ]
        def load_session(self, sid):
            if sid == "match_sess":
                return ({"notes": None}, [
                    {"prompt": "match query turn 1", "response": "res 1"},
                    {"prompt": "match query turn 2", "response": "res 2"},
                ])
            return ({"notes": None}, [{"prompt": "other", "response": "other"}])

        def get_session_size(self, sid):
            size_call_counts[sid] = size_call_counts.get(sid, 0) + 1
            return 99999

    class MockAppLazy(MockApp):
        def get_session_store(self):
            return InstrumentedStore()

    app = MockAppLazy(tmp_path)
    app.active_session_id = None
    app.session_turns = []
    app.session_notes = None

    engine = get_query_engine("grep")
    req = QueryRequest(terms=["match"])
    res = engine.search(app, req)

    assert res.total_matches == 2
    # Unmatched session size should NEVER be computed/called
    assert size_call_counts["unmatched_sess"] == 0
    # Matched session size was served directly from cached summary (12345), avoiding get_session_size disk call
    assert size_call_counts["match_sess"] == 0
    assert res.matches[0].size_bytes == 12345
    assert res.matches[1].size_bytes == 12345


def test_session_search_exception_response_includes_sessions_key():
    """When session_search catches an exception, the returned dict must include 'sessions': []."""
    from unittest.mock import patch
    with patch("chatybot.tools.context_query.get_query_engine", side_effect=RuntimeError("Engine exploded")):
        res = session_search(query="test terms")
        assert res["status"] == "error"
        assert "Engine exploded" in res["message"]
        assert res["total_matches"] == 0
        assert res["matches"] == []
        assert res["session_ids"] == []
        assert res["sessions"] == []  # Verifies key presence to prevent KeyError


def test_active_session_byte_size_fallback_not_inflated(tmp_path):
    """The fallback byte size for active sessions should only sum text content, not metadata keys."""
    app = MockApp(tmp_path)
    # Turn with modest prompt/response but lots of metadata
    app.session_turns = [{
        "turn_id": 1,
        "prompt": "Hello",        # 5 bytes
        "response": "World",       # 5 bytes
        "thinking": "Ponder",      # 6 bytes
        "timestamp": "2026-09-10T17:15:36.123456789",  # 29 bytes (should NOT be counted)
        "model_alias": "very_long_model_alias_here",    # 26 bytes (should NOT be counted)
        "elapsed_ms": 123456,                           # (should NOT be counted)
        "tps": {"total": 55.5, "think": 22.2},         # (should NOT be counted)
    }]
    app.session_notes = "Note"  # 4 bytes
    app.active_session_id = "test_active"

    engine = get_query_engine("grep")
    # Force fallback calculation by ensuring store is not present
    req = QueryRequest(terms=["Hello"])
    res = engine.search(app, req)

    assert res.total_matches == 1
    # Expected size: "Note" (4) + "Hello" (5) + "World" (5) + "Ponder" (6) = 20 bytes
    assert res.matches[0].size_bytes == 20


@pytest.mark.anyio
async def test_session_query_cli_command_execution(tmp_path, monkeypatch, capsys):
    """The /session query CLI command executes without NameError (sess_filter) and returns matches."""
    from chatybot.chatybot_app import ChatybotApp
    sessions_dir = str(tmp_path / "sessions")
    monkeypatch.setenv("CHATYBOT_TEST_SESSIONS_DIR", sessions_dir)
    app = ChatybotApp()
    app.initialize()
    app.session_dir = sessions_dir
    app.session_store = None

    await app.handle_escape_command('/session start "Python Exploration"')
    app.append_session_turn("Tell me about Python decorators", "Decorators wrap functions.")
    capsys.readouterr()

    # 1. Standard query with terms
    await app.handle_escape_command("/session query decorators")
    captured = capsys.readouterr()
    assert "Query Results for 'decorators'" in captured.out
    assert "Decorators wrap functions." in captured.out
    assert "Error: No search terms specified" not in captured.out

    # 2. Query with session= filter
    sid = app.active_session_id
    await app.handle_escape_command(f"/session query decorators session={sid}")
    captured = capsys.readouterr()
    assert "Query Results for 'decorators'" in captured.out
    assert f"session={sid}" in captured.out

    # 3. Filter-only query with session= and ids flag (empty terms allowed)
    await app.handle_escape_command(f"/session query ids session={sid}")
    captured = capsys.readouterr()
    assert "Matching Sessions for all sessions" in captured.out
    assert sid in captured.out


@pytest.mark.anyio
async def test_session_get_uses_resolved_sid_without_double_resolution(tmp_path, monkeypatch):
    """session_get correctly retrieves session details and total size."""
    from chatybot.chatybot_app import ChatybotApp
    from chatybot.tools.context_query import session_get
    sessions_dir = str(tmp_path / "sessions")
    monkeypatch.setenv("CHATYBOT_TEST_SESSIONS_DIR", sessions_dir)
    app = ChatybotApp()
    app.initialize()
    app.session_dir = sessions_dir
    app.session_store = None

    await app.handle_escape_command('/session start "Double Resolve Test"')
    app.append_session_turn("First Q", "First A")
    sid = app.active_session_id

    res = session_get(session_id="Double Resolve Test", app=app)
    assert res["status"] == "success"
    assert res["session_id"] == sid
    assert res["custom_name"] == "Double Resolve Test"
    assert res["session_size_bytes"] > 0





