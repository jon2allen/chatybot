import asyncio
import logging
from typing import Dict, Any, List, Optional
from urllib.parse import urlparse
import httpx
from mcp import ClientSession, StdioServerParameters, stdio_client
from mcp.server.fastmcp import FastMCP

class MCPClientManager:
    def __init__(self, config_data: Dict[str, Any]):
        self.server_configs = config_data.get("mcp", {}).get("servers", {})
        self.active_sessions: Dict[str, ClientSession] = {}
        self.active_transports: Dict[str, Any] = {}
        self.cached_schemas: Dict[str, List[Any]] = {}
        self.http_clients: Dict[str, httpx.AsyncClient] = {}

    async def startup(self):
        """Runs at Chatybot boot to launch persistent servers and discover tools."""
        for server_name, cfg in self.server_configs.items():
            is_persistent = cfg.get("persistent", False)
            
            # Detect server type based on configuration
            server_url = cfg.get("url")
            if server_url:
                # FastMCP HTTP server
                await self._setup_fastmcp_http_server(server_name, cfg)
            else:
                # Traditional stdio server
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

    async def _setup_fastmcp_http_server(self, server_name: str, cfg: Dict[str, Any]) -> None:
        """Setup FastMCP HTTP server connection."""
        server_url = cfg.get("url")
        if not server_url:
            print(f"[MCP] Warning: No URL provided for HTTP server '{server_name}'")
            self.cached_schemas[server_name] = []
            return
            
        try:
            is_persistent = cfg.get("persistent", False)
            parsed_url = urlparse(server_url)
            host = parsed_url.hostname or "localhost"
            port = parsed_url.port or (443 if parsed_url.scheme == "https" else 80)
            
            # Create HTTP client for communicating with FastMCP server
            http_client = httpx.AsyncClient(base_url=server_url, timeout=30.0)
            self.http_clients[server_name] = http_client
            
            if is_persistent:
                # Test connection and initialize session
                # For HTTP-based FastMCP, we establish persistent connection
                self.cached_schemas[server_name] = await self._discover_fastmcp_tools(server_name, http_client)
                print(f"[MCP] FastMCP HTTP server '{server_name}' initialized and tools discovered")
            else:
                # Stateless: discover tools once
                self.cached_schemas[server_name] = await self._discover_fastmcp_tools(server_name, http_client)
                print(f"[MCP] FastMCP HTTP server '{server_name}' tools discovered")
                
        except Exception as e:
            print(f"[MCP] Warning: Failed to initialize FastMCP HTTP server '{server_name}': {e}")
            self.cached_schemas[server_name] = []
            if server_name in self.http_clients:
                await self.http_clients[server_name].aclose()

    async def _discover_fastmcp_tools(self, server_name: str, http_client: httpx.AsyncClient) -> List[Any]:
        """Discover tools from a FastMCP HTTP server."""
        try:
            # Use the MCP protocol to list tools
            response = await http_client.post(
                "/mcp",
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "tools/list",
                    "params": {}
                }
            )
            
            if response.status_code == 200:
                result = response.json()
                if "result" in result and "tools" in result["result"]:
                    return result["result"]["tools"]
            
            # Fallback: try to parse as FastMCP tools endpoint
            response = await http_client.get("/tools")
            if response.status_code == 200:
                return response.json()
                
        except Exception as e:
            logger.error(f"Error discovering FastMCP tools for {server_name}: {e}")
        
        return []

    async def execute_tool(self, server_name: str, tool_name: str, arguments: Dict[str, Any]) -> str:
        """Invokes the tool depending on the server's configured persistence strategy."""
        cfg = self.server_configs.get(server_name)
        if not cfg:
            raise ValueError(f"MCP server '{server_name}' is not configured.")

        server_url = cfg.get("url")
        if server_url:
            # FastMCP HTTP server
            return await self._execute_fastmcp_tool(server_name, cfg, tool_name, arguments)
        else:
            # Traditional stdio server (existing logic)
            return await self._execute_stdio_tool(server_name, cfg, tool_name, arguments)

    async def _execute_fastmcp_tool(self, server_name: str, cfg: Dict[str, Any], tool_name: str, arguments: Dict[str, Any]) -> str:
        """Execute tool on FastMCP HTTP server."""
        http_client = self.http_clients.get(server_name)
        if not http_client:
            raise RuntimeError(f"FastMCP HTTP server '{server_name}' is not connected.")
        
        try:
            # Use the MCP protocol to call tool
            response = await http_client.post(
                "/mcp",
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "tools/call",
                    "params": {
                        "name": tool_name,
                        "arguments": arguments
                    }
                }
            )
            
            if response.status_code == 200:
                result = response.json()
                if "result" in result:
                    return self._format_fastmcp_result(result["result"])
                else:
                    return f"Error: {result.get('error', 'Unknown error')}"
            else:
                return f"Error: HTTP {response.status_code}"
                
        except Exception as e:
            logger.error(f"Error calling FastMCP tool {tool_name} on {server_name}: {e}")
            return f"Error: {str(e)}"

    async def _execute_stdio_tool(self, server_name: str, cfg: Dict[str, Any], tool_name: str, arguments: Dict[str, Any]) -> str:
        """Execute tool on traditional stdio MCP server (existing logic)."""
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

    def _format_fastmcp_result(self, result: Any) -> str:
        """Helper to format FastMCP tool result to string."""
        text_parts = []
        
        if isinstance(result, dict):
            # Handle various result formats from FastMCP
            if "content" in result:
                for item in result["content"]:
                    if hasattr(item, "text") and item.text:
                        text_parts.append(item.text)
                    elif isinstance(item, dict) and "text" in item:
                        text_parts.append(item["text"])
                    else:
                        text_parts.append(str(item))
            elif "text" in result:
                text_parts.append(result["text"])
            else:
                text_parts.append(str(result))
        else:
            # Generic fallback
            text_parts.append(str(result))
        
        return "\n".join(text_parts)

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
        
        # Close HTTP clients for FastMCP servers
        for server_name, http_client in list(self.http_clients.items()):
            try:
                await http_client.aclose()
            except Exception:
                pass
        self.http_clients.clear()
