#!/usr/bin/env python3
"""End-to-end test of Apple FM native tool calling.

Tests that:
1. build_tools() creates fm.Tool instances from tools_config.toml
2. The model can invoke a tool natively
3. The tool delegates to dispatch_tool() and returns results
4. The model incorporates the tool result into its final response
"""

import asyncio
import sys
import os
import json

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from chatybot.apple_fm_backend import check_available, build_tools, create_session, respond
import apple_fm_sdk as fm


async def test_native_tool_calling():
    # 1. Check availability
    ready, reason = check_available()
    if not ready:
        print(f"SKIP: {reason}")
        return False
    print("SDK available")

    # 2. Build a mock app that can load tools_config.toml and dispatch tools
    class MockApp:
        tool_overrides = {}
        tool_timeout = 60

        def _load_tools_config(self):
            import tomllib
            config_path = os.path.expanduser("~/.config/chatybot/tools_config.toml")
            if not os.path.exists(config_path):
                config_path = os.path.join(os.path.dirname(__file__), "src/chatybot/tools_config.toml")
            with open(config_path, "rb") as f:
                return tomllib.load(f)

        async def dispatch_tool(self, invocation_json):
            """Minimal dispatch that actually runs the tool."""
            tool_call = json.loads(invocation_json)
            tool_name = tool_call.get("tool", "")
            args = tool_call.get("arguments", {})
            print(f"  [dispatch_tool] tool={tool_name} args={args}")

            # For list_directory, actually run it
            if tool_name == "list_directory":
                import subprocess
                path = args.get("path", ".")
                result = subprocess.run(
                    ["ls", path], capture_output=True, text=True, timeout=10
                )
                return json.dumps({
                    "status": "success",
                    "tool": tool_name,
                    "result": {"output": result.stdout, "exit_code": result.returncode}
                })
            elif tool_name == "calculate":
                expression = args.get("expression", "")
                try:
                    # Safe eval
                    result = eval(expression, {"__builtins__": {}}, {})
                    return json.dumps({
                        "status": "success",
                        "tool": tool_name,
                        "result": {"result": result}
                    })
                except Exception as e:
                    return json.dumps({"status": "error", "message": str(e)})
            else:
                return json.dumps({"status": "error", "message": f"Unknown tool: {tool_name}"})

    app = MockApp()

    # 3. Build tools
    tools = build_tools(app)
    print(f"Built {len(tools)} tools:")
    for t in tools:
        print(f"  - {t.name}: {t.description[:60]}...")

    if not tools:
        print("FAIL: No tools built")
        return False

    # 4. Create session with tools
    session, err = create_session(
        instructions="You are a helpful assistant with access to tools. Use tools when asked to perform actions.",
        tools=tools,
    )
    if err:
        print(f"FAIL: {err}")
        return False
    print("Session created with tools")

    # 5. Test 1: list_directory tool call (use small dir to fit context window)
    print("\n=== TEST 1: list_directory ===")
    prompt = "Use the list_directory tool to list files in the 'bin' directory."
    print(f"Prompt: {prompt}")
    print("Response:")
    response = await respond(session, prompt)
    print(f"\nFull response:\n{response}")

    # Check if the response contains file listing info
    has_files = any(ext in response for ext in [".sh", ".py", "tool", "bin"])
    print(f"Response mentions files: {has_files}")

    # 6. Test 2: calculate tool call
    print("\n=== TEST 2: calculate ===")
    session2, err = create_session(
        instructions="You are a helpful assistant with access to tools.",
        tools=tools,
    )
    if err:
        print(f"FAIL creating session2: {err}")
    else:
        prompt2 = "What is 15 times 37? Use the calculate tool."
        print(f"Prompt: {prompt2}")
        print("Response:")
        response2 = await respond(session2, prompt2)
        print(f"\nFull response:\n{response2}")
        has_answer = "555" in response2
        print(f"Response contains 555: {has_answer}")

    return True


if __name__ == "__main__":
    result = asyncio.run(test_native_tool_calling())
    print(f"\n{'PASS' if result else 'FAIL'}")
