import pytest
from io import StringIO
import sys
from unittest.mock import MagicMock, patch
from chatybot.context_limit import ContextLimiter
from chatybot.tools.context_utils import get_context_metrics
from chatybot.profile_model import Profile
from chatybot.profile_editor import ProfileEditor
from chatybot.chatybot_app import ChatybotApp


def test_edge_case_1_anchors_exceed_limit_no_infinite_loop():
    """Edge Case 1: When system + user anchor prompts exceed limit, truncate_messages terminates quickly."""
    limiter = ContextLimiter(default_limit=50, auto_truncate=True)
    
    # System + user message totaling ~120 tokens (exceeding 50 limit)
    messages = [
        {"role": "system", "content": "You are a specialized coding assistant with comprehensive knowledge. " * 3},
        {"role": "user", "content": "Initial user task description and detailed step-by-step goal instructions. " * 3}
    ]
    
    # Must terminate and not hang
    truncated, did_trunc = limiter.truncate_messages(messages, limit=50)
    assert did_trunc is True
    assert len(truncated) == 2
    assert truncated[0]["role"] == "system"
    assert truncated[1]["role"] == "user"


def test_edge_case_2_single_evictable_dropped_when_anchors_plus_turn_exceed_limit():
    """Edge Case 2: When evictable list has 1 item and anchors+turn exceed limit, turn is dropped."""
    limiter = ContextLimiter(default_limit=60, auto_truncate=True)
    
    messages = [
        {"role": "system", "content": "You are an assistant."},
        {"role": "user", "content": "My initial goal."},
        {"role": "assistant", "content": "A very large intermediate turn content " * 15}
    ]
    
    truncated, did_trunc = limiter.truncate_messages(messages, limit=60)
    assert did_trunc is True
    # The intermediate turn should be evicted leaving only the 2 anchors
    assert len(truncated) == 2
    assert truncated[0]["role"] == "system"
    assert truncated[1]["role"] == "user"


def test_edge_case_3_context_buffers_scope():
    """Edge Case 3: /context buffers returns isolated buffers scope without falling back to all."""
    mock_app = MagicMock()
    mock_app.context_limiter.context_limit = 4096
    mock_app.context_limiter.auto_truncate = False
    mock_app.context_limiter.truncate_pct = 100.0
    mock_app.context_limiter.count_tokens_text.side_effect = lambda text: len(text) // 4
    mock_app.current_user_input = "Current input prompt"
    mock_app.active_tools_system_prompt = "Active tools docstring"
    mock_app.chat_history = []
    mock_app.agentic_loop_active = False

    metrics = get_context_metrics(scope="buffers", app=mock_app)
    assert metrics["status"] == "success"
    assert metrics["scope"] == "buffers"
    assert "buffers" in metrics
    assert "chat_history" not in metrics
    assert "Buffers Usage" in metrics["summary"]


@pytest.mark.anyio
async def test_edge_case_4_scoped_context_command_display(capsys):
    """Edge Case 4: Scoped /context command displays scoped token metrics accurately."""
    app = ChatybotApp()
    app.initialize()
    app.context_limiter.set_limit(5000, from_user=True)
    app.chat_history = [
        ("User prompt", "Assistant answer " * 10)
    ]
    capsys.readouterr()
    
    res = await app.handle_escape_command("/context session")
    assert res is True
    out = capsys.readouterr().out
    assert "Context Usage (Scope: session)" in out
    assert "5,000" in out


def test_edge_case_5_chatdsl_auto_truncate_clamping():
    """Edge Case 5: Profile parsing clamps /auto_truncate percentages."""
    dsl_low = """
# @name: Low Truncate
/model mistral_1
/auto_truncate 5
"""
    p_low = Profile.from_chatdsl_string(dsl_low)
    assert p_low.config.auto_truncate is False

    dsl_high = """
# @name: High Truncate
/model mistral_1
/auto_truncate 150
"""
    p_high = Profile.from_chatdsl_string(dsl_high)
    assert p_high.config.auto_truncate is True
    assert p_high.config.truncate_pct == 100.0

    dsl_valid = """
# @name: Valid Truncate
/model mistral_1
/auto_truncate 75
"""
    p_valid = Profile.from_chatdsl_string(dsl_valid)
    assert p_valid.config.auto_truncate is True
    assert p_valid.config.truncate_pct == 75.0


def test_edge_case_6_profile_editor_rejects_non_numeric_truncate_pct(tmp_path):
    """Edge Case 6: ProfileEditor ignores non-numeric strings for /auto_truncate."""
    dsl_file = tmp_path / "test_profile.chatdsl"
    dsl_file.write_text("""
# @name: Bad Truncate
/model mistral_1
/auto_truncate invalid_string
""", encoding="utf-8")

    pm_mock = MagicMock()
    editor = ProfileEditor("test_profile", pm_mock, MagicMock())
    editor.load_from_file(str(dsl_file))
    
    # Should not adopt "invalid_string" as truncate_pct
    assert editor.truncate_pct != "invalid_string"
