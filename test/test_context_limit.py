import pytest
import sys
from io import StringIO
from unittest.mock import MagicMock, patch
from chatybot.context_limit import ContextLimiter
from chatybot.chatybot_app import ChatybotApp


@pytest.fixture
def app():
    """Create a ChatybotApp instance with clean state and mock dependencies"""
    with patch('src.chatybot.chatybot_app.readline'):
        with patch('src.chatybot.chatybot_app.ConfigManager') as mock_cfg:
            cfg_instance = mock_cfg.return_value
            cfg_instance.config = {
                "models": {
                    "test_model": {
                        "name": "test-model",
                        "base_url": "https://api.openai.com/v1",
                        "api_key": "TEST_KEY"
                    }
                }
            }
            cfg_instance.active_model_alias = "test_model"
            cfg_instance.get_model_config.return_value = cfg_instance.config["models"]["test_model"]
            cfg_instance.system_message = "System"
            
            application = ChatybotApp()
            application.config_manager = cfg_instance
            yield application


def test_context_limiter_token_counting():
    """Test heuristic token counting for strings and message dictionaries."""
    limiter = ContextLimiter()

    # Empty text
    assert limiter.count_tokens_text("") == 0

    # Short text (e.g. 16 chars -> ~4 tokens)
    text = "1234567890123456"
    assert limiter.count_tokens_text(text) == 4

    # Message counting
    msg = {"role": "user", "content": "Hello world!"}
    # 3 (base) + 1 (role "user") + 3 (content 12 chars -> 3 tokens) = 7
    tokens = limiter.count_tokens_message(msg)
    assert tokens > 0

    # List of messages
    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Tell me a joke."}
    ]
    total_tokens = limiter.count_tokens_messages(messages)
    assert total_tokens > tokens


def test_context_limiter_warnings():
    """Test warning messages generated at 70% and 90% thresholds."""
    limiter = ContextLimiter(default_limit=1000)

    # Below 70% -> No warning
    assert limiter.check_warnings(500) is None
    assert limiter.check_warnings(699) is None

    # 70% to 89.9% -> 70% warning
    warn_70 = limiter.check_warnings(750)
    assert warn_70 is not None
    assert "75.0%" in warn_70
    assert "750/1,000" in warn_70

    # 90%+ -> 90% warning with approaching note
    warn_90 = limiter.check_warnings(950)
    assert warn_90 is not None
    assert "95.0%" in warn_90
    assert "Approaching context window limit" in warn_90


def test_context_limiter_truncation():
    """Test truncation of intermediate messages while preserving system message and initial goal."""
    limiter = ContextLimiter(default_limit=45, auto_truncate=True)

    long_chunk = "A" * 60  # ~15 tokens per message
    messages = [
        {"role": "system", "content": "System prompt"},
        {"role": "user", "content": "Initial Goal: Translate poem"},
        {"role": "assistant", "content": f"Intermediate Tool 1: {long_chunk}"},
        {"role": "user", "content": f"Intermediate Tool Result 1: {long_chunk}"},
        {"role": "assistant", "content": f"Intermediate Tool 2: {long_chunk}"},
    ]

    truncated, did_trunc = limiter.truncate_messages(messages, limit=55)
    assert did_trunc is True
    # System message preserved at index 0
    assert truncated[0]["role"] == "system"
    # Initial goal preserved at index 1
    assert truncated[1]["role"] == "user"
    assert "Initial Goal: Translate poem" in truncated[1]["content"]
    # Intermediate tool messages were dropped
    assert len(truncated) < len(messages)

    # Test with target_pct (e.g. 50% of 100 limit -> target 50)
    limiter_pct = ContextLimiter(default_limit=100, auto_truncate=True, truncate_pct=50.0)
    truncated_pct, did_trunc_pct = limiter_pct.truncate_messages(messages, limit=100)
    assert did_trunc_pct is True
    assert len(truncated_pct) < len(messages)
    assert truncated_pct[0]["role"] == "system"
    assert "Initial Goal" in truncated_pct[1]["content"]


def test_context_limiter_single_large_message_truncation():
    """Test that a single massive message (e.g. huge file read tool output) is truncated to fit the limit."""
    limiter = ContextLimiter(default_limit=5000, auto_truncate=True, truncate_pct=90.0)

    # 100,000 token message
    huge_text = "print('hello world!')\n" * 20000
    messages = [
        {"role": "system", "content": "You are a coding assistant."},
        {"role": "user", "content": f"Tool execution results:\n{huge_text}"}
    ]

    truncated, did_trunc = limiter.truncate_messages(messages, limit=5000)
    assert did_trunc is True
    # System message preserved
    assert truncated[0]["role"] == "system"
    # Result fits within target limit (5000 * 0.90 = 4500)
    total_after = limiter.count_tokens_messages(truncated)
    assert total_after <= 5000
    assert "[... content truncated to fit context limit ...]" in truncated[1]["content"]


@pytest.mark.anyio
async def test_context_limit_and_auto_truncate_commands(app):
    """Test /context_limit and /auto_truncate CLI escape commands."""
    # 1. Check default context limit display
    captured = StringIO()
    sys.stdout = captured
    try:
        res = await app.handle_escape_command("/context_limit")
        assert res is True
    finally:
        sys.stdout = sys.__stdout__
    assert "Context limit is disabled" in captured.getvalue() or "Current context limit" in captured.getvalue()

    # 2. Set context limit
    captured = StringIO()
    sys.stdout = captured
    try:
        res = await app.handle_escape_command("/context_limit 4096")
        assert res is True
    finally:
        sys.stdout = sys.__stdout__
    assert "Context limit set to 4096 tokens." in captured.getvalue()
    assert app.context_limiter.context_limit == 4096
    assert app.context_limiter._user_set_limit is True

    # 3. Query set context limit
    captured = StringIO()
    sys.stdout = captured
    try:
        res = await app.handle_escape_command("/context_limit")
        assert res is True
    finally:
        sys.stdout = sys.__stdout__
    assert "Current context limit: 4096 tokens" in captured.getvalue()

    # 4. Disable context limit
    captured = StringIO()
    sys.stdout = captured
    try:
        res = await app.handle_escape_command("/context_limit off")
        assert res is True
    finally:
        sys.stdout = sys.__stdout__
    assert "Context limit disabled." in captured.getvalue()
    assert app.context_limiter.context_limit is None

    # 5. Invalid context limit input
    captured = StringIO()
    sys.stdout = captured
    try:
        res = await app.handle_escape_command("/context_limit abc")
        assert res is True
    finally:
        sys.stdout = sys.__stdout__
    assert "Invalid context limit" in captured.getvalue()

    # 6. Auto-truncate toggle
    captured = StringIO()
    sys.stdout = captured
    try:
        res = await app.handle_escape_command("/auto_truncate")
        assert res is True
    finally:
        sys.stdout = sys.__stdout__
    assert "Auto-truncation is currently disabled." in captured.getvalue()

    captured = StringIO()
    sys.stdout = captured
    try:
        res = await app.handle_escape_command("/auto_truncate on")
        assert res is True
    finally:
        sys.stdout = sys.__stdout__
    assert "Auto-truncation enabled" in captured.getvalue()
    assert app.context_limiter.auto_truncate is True

    captured = StringIO()
    sys.stdout = captured
    try:
        res = await app.handle_escape_command("/auto_truncate off")
        assert res is True
    finally:
        sys.stdout = sys.__stdout__
    assert "Auto-truncation disabled." in captured.getvalue()
    assert app.context_limiter.auto_truncate is False

    # 7. Set auto-truncate percentage (e.g. 80%)
    captured = StringIO()
    sys.stdout = captured
    try:
        res = await app.handle_escape_command("/auto_truncate 80")
        assert res is True
    finally:
        sys.stdout = sys.__stdout__
    assert "Auto-truncation enabled at 80% of context limit." in captured.getvalue()
    assert app.context_limiter.auto_truncate is True
    assert app.context_limiter.truncate_pct == 80.0

    # 8. Set auto-truncate with > 100 -> error
    captured = StringIO()
    sys.stdout = captured
    try:
        res = await app.handle_escape_command("/auto_truncate 120")
        assert res is True
    finally:
        sys.stdout = sys.__stdout__
    assert "Error: Auto-truncate percentage cannot exceed 100%" in captured.getvalue()

    # 9. Set auto-truncate with < 10 -> disabled
    captured = StringIO()
    sys.stdout = captured
    try:
        res = await app.handle_escape_command("/auto_truncate 5")
        assert res is True
    finally:
        sys.stdout = sys.__stdout__
    assert "Auto-truncation disabled (percentage below 10%)." in captured.getvalue()
    assert app.context_limiter.auto_truncate is False


@pytest.mark.anyio
async def test_model_specific_context_limit_override(app):
    """Test that model-specific context_limit from config is loaded when model is active."""
    app.context_limiter.set_limit(None, from_user=False)
    app.context_limiter._user_set_limit = False

    mock_model_config = {
        "name": "llama3.1:8b",
        "vendor": "ollama",
        "base_url": "http://localhost:11434/v1",
        "context_limit": 4096
    }
    app.config_manager.get_model_config = MagicMock(return_value=mock_model_config)
    app.config_manager.config["models"]["ollama_llama"] = mock_model_config

    await app.handle_escape_command("/model ollama_llama")
    assert app.context_limiter.context_limit == 4096


def test_get_context_metrics_with_context_limit(app):
    """Test that get_context_metrics tool reports context limit, usage, and remaining budget."""
    from chatybot.tools.context_utils import get_context_metrics

    app.context_limiter.set_limit(10000, from_user=True)
    app.context_limiter.set_auto_truncate(True, pct=85.0)
    app.chat_history = [
        ("What is Python?", "Python is a programming language." * 50)
    ]

    metrics = get_context_metrics(scope="all", app=app)
    assert metrics["status"] == "success"
    assert "context_limit" in metrics
    assert metrics["context_limit"]["limit_tokens"] == 10000
    assert metrics["context_limit"]["auto_truncate"] is True
    assert metrics["context_limit"]["truncate_percent"] == 85.0
    assert metrics["context_limit"]["used_tokens"] > 0
    assert metrics["context_limit"]["remaining_tokens"] < 10000
    assert "Context Limit: 10,000 tokens" in metrics["summary"]
    assert "auto-truncate: ON (85%)" in metrics["summary"]


def test_partition_anchors_and_verbose_diagnostic_consistency():
    """Verify that partition_anchors correctly handles system+user, user-only, and non-anchor starts."""
    limiter = ContextLimiter(default_limit=1000)

    # Case 1: System + User -> 2 anchors
    m1 = [
        {"role": "system", "content": "System instructions"},
        {"role": "user", "content": "First user goal"},
        {"role": "assistant", "content": "Response 1"},
        {"role": "user", "content": "Followup"}
    ]
    anchors1, evictable1 = ContextLimiter.partition_anchors(m1)
    assert len(anchors1) == 2
    assert len(evictable1) == 2
    diag1 = limiter.truncate_messages_verbose(m1, limit=50)
    assert diag1.anchor_count == 2

    # Case 2: User only (no system prompt) -> 1 anchor (user)
    m2 = [
        {"role": "user", "content": "First user goal without system"},
        {"role": "assistant", "content": "Response 1"},
        {"role": "user", "content": "Followup"}
    ]
    anchors2, evictable2 = ContextLimiter.partition_anchors(m2)
    assert len(anchors2) == 1
    assert anchors2[0]["role"] == "user"
    assert len(evictable2) == 2
    diag2 = limiter.truncate_messages_verbose(m2, limit=50)
    assert diag2.anchor_count == 1

    # Case 3: Starts with assistant or tool call -> 0 anchors
    m3 = [
        {"role": "assistant", "content": "Tool call invocation"},
        {"role": "user", "content": "Tool output"}
    ]
    anchors3, evictable3 = ContextLimiter.partition_anchors(m3)
    assert len(anchors3) == 0
    assert len(evictable3) == 2
    diag3 = limiter.truncate_messages_verbose(m3, limit=50)
    assert diag3.anchor_count == 0
    assert diag3.anchors_alone_exceed_limit is False


def test_truncation_notice_strictly_within_target_limit():
    """Verify that prepending the truncation notice does not cause total tokens to exceed limit."""
    limiter = ContextLimiter()
    
    # Create messages that exceed a tight budget of 100 tokens
    messages = [
        {"role": "system", "content": "System prompt"},
        {"role": "user", "content": "First goal: " + "word " * 50},
        {"role": "assistant", "content": "Assistant answer: " + "detail " * 60},
        {"role": "user", "content": "Followup query: " + "query " * 40}
    ]
    
    target_limit = 80
    truncated, did_trunc = limiter.truncate_messages(messages, limit=target_limit, target_pct=100.0)
    assert did_trunc is True
    final_tokens = limiter.count_tokens_messages(truncated)
    assert final_tokens <= target_limit
    
    # Check that the note was prepended
    notice_present = any("[Note:" in str(m.get("content", "")) for m in truncated)
    assert notice_present is True



