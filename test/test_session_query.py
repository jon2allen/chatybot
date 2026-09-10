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

