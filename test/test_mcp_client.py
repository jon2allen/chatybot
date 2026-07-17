import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from src.chatybot.mcp_client import MCPClientManager

@pytest.fixture
def mcp_config():
    return {
        "mcp": {
            "servers": {
                "test_persistent": {
                    "command": "python",
                    "args": ["-m", "test_server"],
                    "persistent": True,
                    "env": {"VAR": "value"}
                },
                "test_ondemand": {
                    "command": "python",
                    "args": ["-m", "test_server2"],
                    "persistent": False
                }
            }
        }
    }

@pytest.mark.anyio
async def test_mcp_manager_initialization_and_startup(mcp_config):
    # Mock stdio_client and ClientSession
    mock_session = AsyncMock()
    mock_session.__aenter__.return_value = mock_session
    
    # Configure tool mock
    tool_mock = MagicMock()
    tool_mock.name = "tool1"
    tool_mock.description = "desc1"
    tool_mock.inputSchema = {"type": "object"}
    
    mock_session.list_tools.return_value = MagicMock(tools=[tool_mock])
    
    mock_transport = AsyncMock()
    mock_transport.__aenter__.return_value = ("read_stream", "write_stream")
    
    with patch("chatybot.mcp_client.stdio_client", return_value=mock_transport), \
         patch("chatybot.mcp_client.ClientSession", return_value=mock_session):
         
        manager = MCPClientManager(mcp_config)
        await manager.startup()
        
        # Verify that both servers were processed
        assert "test_persistent" in manager.cached_schemas
        assert "test_ondemand" in manager.cached_schemas
        
        # Verify cached schemas have the mock tool
        assert len(manager.cached_schemas["test_persistent"]) == 1
        assert manager.cached_schemas["test_persistent"][0].name == "tool1"
        
        # Verify persistent session is stored
        assert "test_persistent" in manager.active_sessions
        assert manager.active_sessions["test_persistent"] == mock_session

@pytest.mark.anyio
async def test_mcp_manager_execute_persistent_tool(mcp_config):
    mock_session = AsyncMock()
    # Mock CallToolResult
    mock_result = MagicMock()
    content_mock = MagicMock()
    content_mock.text = "Tool result text"
    mock_result.content = [content_mock]
    mock_session.call_tool.return_value = mock_result
    
    manager = MCPClientManager(mcp_config)
    manager.active_sessions["test_persistent"] = mock_session
    
    res = await manager.execute_tool("test_persistent", "tool1", {"arg": "val"})
    assert res == "Tool result text"
    mock_session.call_tool.assert_called_once_with("tool1", {"arg": "val"})

@pytest.mark.anyio
async def test_mcp_manager_execute_ondemand_tool(mcp_config):
    mock_session = AsyncMock()
    mock_session.__aenter__.return_value = mock_session
    
    mock_result = MagicMock()
    content_mock = MagicMock()
    content_mock.text = "Ondemand result text"
    mock_result.content = [content_mock]
    mock_session.call_tool.return_value = mock_result
    
    mock_transport = AsyncMock()
    mock_transport.__aenter__.return_value = ("read_stream", "write_stream")
    
    with patch("chatybot.mcp_client.stdio_client", return_value=mock_transport), \
         patch("chatybot.mcp_client.ClientSession", return_value=mock_session):
         
        manager = MCPClientManager(mcp_config)
        res = await manager.execute_tool("test_ondemand", "tool2", {"arg": "val"})
        
        assert res == "Ondemand result text"
        mock_session.initialize.assert_called_once()
        mock_session.call_tool.assert_called_once_with("tool2", {"arg": "val"})

@pytest.mark.anyio
async def test_mcp_manager_shutdown(mcp_config):
    mock_session = AsyncMock()
    mock_transport = AsyncMock()
    
    manager = MCPClientManager(mcp_config)
    manager.active_sessions["test_persistent"] = mock_session
    manager.active_transports["test_persistent"] = mock_transport
    
    await manager.shutdown()
    
    # Sessions should be cleared
    assert len(manager.active_sessions) == 0
    assert len(manager.active_transports) == 0
    mock_session.__aexit__.assert_called_once()
    mock_transport.__aexit__.assert_called_once()
