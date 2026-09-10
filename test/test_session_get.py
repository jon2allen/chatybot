"""
Tests for /session get command and session_get LLM tool.
"""

import os
import pytest

from chatybot.tools.context_query import session_get
from chatybot.buffer_manager import BufferManager


class MockAppWithSession:
    def __init__(self):
        self.active_session_id = "sess_active_123"
        self.active_session_name = "Auth_Workflow"
        self.session_notes = "Refactored token refresh logic"
        self.session_model_alias = "gpt-4o"
        self.session_turns = [
            {
                "turn_id": 1,
                "prompt": "How do we handle 401 error?",
                "response": "Inspect www-authenticate header and refresh the token.",
                "thinking": "Step 1: Check header. Step 2: Request new JWT.",
            },
            {
                "turn_id": 2,
                "prompt": "What if refresh fails?",
                "response": "Redirect the user to login.",
            }
        ]
        self.buffer_manager = BufferManager()


def test_session_get_active_turn_both():
    app = MockAppWithSession()
    res = session_get("active", turn_id=1, part="both", app=app)
    
    assert res["status"] == "success"
    assert res["session_id"] == "sess_active_123"
    assert res["turn_id"] == 1
    assert res["size_bytes"] > 0
    assert res["size_bytes"] == len(res["text"].encode("utf-8"))
    assert "How do we handle 401 error?" in res["text"]
    assert "Inspect www-authenticate header" in res["text"]
    assert "Thinking: Step 1" in res["text"]


def test_session_get_prompt_only():
    app = MockAppWithSession()
    res = session_get("active", turn_id=1, part="prompt", app=app)
    
    assert res["status"] == "success"
    assert res["text"] == "How do we handle 401 error?"


def test_session_get_response_only():
    app = MockAppWithSession()
    res = session_get("active", turn_id=2, part="response", app=app)
    
    assert res["status"] == "success"
    assert res["text"] == "Redirect the user to login."


def test_session_get_all_turns_with_target_var():
    app = MockAppWithSession()
    res = session_get("active", part="both", target_variable="EXTRACTED_CONV", app=app)
    
    assert res["status"] == "success"
    assert res["total_turns"] == 2
    assert "How do we handle 401 error?" in res["text"]
    assert "Redirect the user to login." in res["text"]
    
    # Check variable assignment
    assert "EXTRACTED_CONV" in app.buffer_manager.script_vars
    assert app.buffer_manager.script_vars["EXTRACTED_CONV"] == res["text"]


def test_session_get_invalid_turn():
    app = MockAppWithSession()
    res = session_get("active", turn_id=99, app=app)
    assert res["status"] == "error"
    assert "not found" in res["message"]
