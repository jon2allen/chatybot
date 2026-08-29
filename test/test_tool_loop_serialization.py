import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from src.chatybot.chatybot_app import ChatybotApp

@pytest.fixture
def app():
    return ChatybotApp(no_tools=True)

def test_extract_tool_calls_normalizes_sets_and_non_json_types(app):
    """Verify that extract_tool_calls normalizes python set/frozenset and custom structures to JSON lists."""
    # When model outputs python-style dictionary with sets (often parsed via ast.literal_eval fallback)
    text = '{"tool": "analyze_files", "arguments": {"files": {"a.py", "b.py"}, "flags": {"x", "y"}}}'
    calls = app.extract_tool_calls(text)
    assert len(calls) == 1
    assert calls[0]["tool"] == "analyze_files"
    # Arguments should have been normalized to list
    assert isinstance(calls[0]["arguments"]["files"], list)
    assert sorted(calls[0]["arguments"]["files"]) == ["a.py", "b.py"]
    assert isinstance(calls[0]["arguments"]["flags"], list)
    assert sorted(calls[0]["arguments"]["flags"]) == ["x", "y"]

@pytest.mark.anyio
async def test_execute_tool_loop_handles_non_serializable_args(app):
    """Verify that execute_tool_loop executes smoothly without TypeError when tool args contain set or complex objects."""
    app.enable_chat_history = True
    app.chat_history = [("Initial prompt", '{"tool": "sample_tool", "arguments": {"items": {"1", "2"}}}')]
    
    # Mock dispatch_tool to avoid executing actual shell/tools
    app.dispatch_tool = AsyncMock(return_value='{"status": "ok"}')
    
    # Mock subsequent chat_completion to return natural language and exit the loop cleanly
    app.chat_completion = AsyncMock(return_value="All finished processing.")
    
    # Should not raise TypeError: Object of type set is not JSON serializable
    await app.execute_tool_loop(max_turns=2)
    
    assert app.dispatch_tool.called

