import asyncio
import logging
from typing import Dict, Any, List
from mcp import ClientSession, StdioServerParameters, stdio_client

class MCPClientManager:
    def __init__(self, config_data: Dict[str, Any]):
        self.server_configs = config_data.get("mcp", {}).get("servers", {})
        self.active_sessions: Dict[str, ClientSession] = {}
        self.active_transports: Dict[str, Any] = {}
        self.cached_schemas: Dict[str, List[Any]] = {}

    async def startup(self):
        """Runs at Chatybot boot to launch persistent servers and discover tools."""
        for server_name, cfg in self.server_configs.items():
            is_persistent = cfg.get("persistent", False)
            params = StdioServerParameters(
                command=cfg.get("command"),
                args=cfg.get("args", []),
                env=cfg.get("env")
            )
            
            try:
                if is_persistent:
                    # Launch background daemon connection
                    transport = stdio_client(params)
                    read, write = await transport.__aenter__()
                    session = ClientSession(read, write)
                    await session.__aenter__()
                    await session.initialize()
                    
                    self.active_transports[server_name] = transport
                    self.active_sessions[server_name] = session
                    
                    # Retrieve and register tools
                    tools_result = await session.list_tools()
                    self.cached_schemas[server_name] = tools_result.tools
                else:
                    # Run a brief handshake once to discover tools
                    self.cached_schemas[server_name] = await self._discover_tools_once(params)
            except Exception as e:
                print(f"[MCP] Warning: Failed to initialize server '{server_name}': {e}")
                self.cached_schemas[server_name] = []

    async def _discover_tools_once(self, params: StdioServerParameters) -> List[Any]:
        """Performs a single connection handshake to list tools on a stateless server."""
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                tools_result = await session.list_tools()
                return tools_result.tools

    async def execute_tool(self, server_name: str, tool_name: str, arguments: Dict[str, Any]) -> str:
        """Invokes the tool depending on the server's configured persistence strategy."""
        cfg = self.server_configs.get(server_name)
        if not cfg:
            raise ValueError(f"MCP server '{server_name}' is not configured.")

        is_persistent = cfg.get("persistent", False)

        if is_persistent:
            session = self.active_sessions.get(server_name)
            if not session:
                raise RuntimeError(f"Persistent server '{server_name}' is not running.")
            result = await session.call_tool(tool_name, arguments)
            return self._format_result(result)
        else:
            # On-demand execution
            params = StdioServerParameters(
                command=cfg.get("command"),
                args=cfg.get("args", []),
                env=cfg.get("env")
            )
            async with stdio_client(params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    result = await session.call_tool(tool_name, arguments)
                    return self._format_result(result)

    def _format_result(self, result: Any) -> str:
        """Helper to format the CallToolResult content to a string."""
        text_parts = []
        # CallToolResult contains content
        content_items = getattr(result, "content", [])
        for item in content_items:
            if hasattr(item, "text") and item.text:
                text_parts.append(item.text)
            elif isinstance(item, dict) and "text" in item:
                text_parts.append(item["text"])
            else:
                try:
                    if hasattr(item, "model_dump_json"):
                        text_parts.append(item.model_dump_json())
                    elif hasattr(item, "model_dump"):
                        text_parts.append(str(item.model_dump()))
                    else:
                        text_parts.append(str(item))
                except Exception:
                    text_parts.append(str(item))
        return "\n".join(text_parts)

    async def shutdown(self):
        """Cleans up background processes on CLI exit."""
        for server_name, session in list(self.active_sessions.items()):
            try:
                await session.__aexit__(None, None, None)
            except Exception:
                pass
            transport = self.active_transports.get(server_name)
            if transport:
                try:
                    await transport.__aexit__(None, None, None)
                except Exception:
                    pass
        self.active_sessions.clear()
        self.active_transports.clear()
