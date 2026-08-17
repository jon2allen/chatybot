import pytest
from unittest.mock import AsyncMock, MagicMock
from src.chatybot.chatybot_app import ChatybotApp

@pytest.fixture
def mock_app():
    app = ChatybotApp()
    return app

def test_is_permanent_capability_error(mock_app):
    assert mock_app._is_permanent_capability_error("Error calling tool 'display_info': Elicitation not supported") is True
    assert mock_app._is_permanent_capability_error("Method not found") is True
    assert mock_app._is_permanent_capability_error("Capability not supported by server") is True
    assert mock_app._is_permanent_capability_error("Protocol error: unsupported feature") is True
    
    assert mock_app._is_permanent_capability_error("File not found: test.py") is False
    assert mock_app._is_permanent_capability_error("SyntaxError: invalid syntax") is False
    assert mock_app._is_permanent_capability_error("") is False

def test_format_capability_error(mock_app):
    raw_err = "Error calling tool 'display_info': Elicitation not supported"
    formatted = mock_app._format_capability_error("mcp__mcp_command_serv__display_info", raw_err)
    
    assert "Elicitation not supported" in formatted
    assert "[PERMANENT CAPABILITY ERROR]: Feature not supported by client environment. DO NOT retry this tool. Select an alternative tool or complete response directly." in formatted

    # Test no duplicate addition
    double_formatted = mock_app._format_capability_error("mcp__mcp_command_serv__display_info", formatted)
    assert double_formatted == formatted

@pytest.mark.anyio
async def test_dispatch_tool_capability_error_interception(mock_app):
    mock_mcp_manager = AsyncMock()
    mock_mcp_manager.execute_tool.return_value = "Error calling tool 'display_info': Elicitation not supported"
    mock_app.mcp_manager = mock_mcp_manager

    tool_call = {
        "tool": "mcp__mcp_command_serv__display_info",
        "arguments": {"info": "test"}
    }
    
    result = await mock_app.dispatch_tool(invocation_json=str(tool_call).replace("'", '"'))
    
    assert "[PERMANENT CAPABILITY ERROR]" in result
    assert "DO NOT retry this tool" in result
    assert mock_app.buffer_manager.get_script_var('TOOL_DISPATCH_EXIT_CODE') == '1'
    assert mock_app.tool_overrides.get("mcp__mcp_command_serv__display_info") is False

    # Second invocation should be blocked immediately without calling execute_tool again
    second_result = await mock_app.dispatch_tool(invocation_json=str(tool_call).replace("'", '"'))
    assert "currently disabled" in second_result
