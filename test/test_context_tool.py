import pytest
import json
from unittest.mock import MagicMock
from chatybot.chatybot_app import ChatybotApp
from chatybot.tools.context_utils import get_context_metrics, calculate_metrics


def test_calculate_metrics():
    sample_text = "Hello world! This is a test."
    res = calculate_metrics(sample_text)
    assert res["characters"] == len(sample_text)
    assert res["bytes"] == len(sample_text.encode("utf-8"))
    assert res["kb"] == round(len(sample_text.encode("utf-8")) / 1024, 2)
    assert res["estimated_tokens"] == max(1, (len(sample_text.encode("utf-8")) + 3) // 4)


def test_get_context_metrics_direct_empty():
    res = get_context_metrics(scope="all")
    assert res["status"] == "success"
    assert res["scope"] == "all"
    assert "session" in res
    assert "agentic_loop" in res
    assert "total" in res
    assert res["session"]["turns"] == 0
    assert res["agentic_loop"]["records"] == 0
    assert res["total"]["characters"] == 0
    assert res["total"]["kb"] == 0.0


@pytest.mark.anyio
async def test_get_context_metrics_with_app_data():
    app = ChatybotApp()
    app.initialize()

    # Populate session history
    app.chat_history = [
        ("What is Python?", "Python is a high-level programming language."),
        ("Give me an example.", "Here is a code snippet: print('hello')")
    ]

    # Populate agentic loop
    app.buffer_manager.set_script_var("AGENTIC_LOOP", [
        {"turn": 1, "tool": "list_directory", "arguments": {"path": "."}, "result": "['file1.txt', 'file2.py']", "status": "success"},
        {"turn": 2, "tool": "read_file", "arguments": {"path": "file1.txt"}, "result": "Sample file content", "status": "success"}
    ], allow_protected=True)

    # Populate prompt buffer
    app.buffer_manager.prompt_buffer = "You are a helpful coding assistant."

    # 1. Test 'all' scope
    res_all = get_context_metrics(scope="all", app=app)
    assert res_all["status"] == "success"
    assert res_all["session"]["turns"] == 2
    assert res_all["session"]["characters"] > 0
    assert res_all["agentic_loop"]["turns"] == 2
    assert res_all["agentic_loop"]["records"] == 2
    assert res_all["agentic_loop"]["characters"] > 0
    assert res_all["buffers"]["characters"] > 0
    assert res_all["total"]["total_turns"] == 4
    assert res_all["total"]["characters"] > res_all["session"]["characters"]
    assert res_all["total"]["estimated_tokens"] > 0

    # 2. Test 'session' scope
    res_session = get_context_metrics(scope="session", app=app)
    assert res_session["status"] == "success"
    assert "session" in res_session
    assert "agentic_loop" not in res_session
    assert res_session["session"]["turns"] == 2

    # 3. Test 'agentic_loop' scope
    res_loop = get_context_metrics(scope="agentic_loop", app=app)
    assert res_loop["status"] == "success"
    assert "agentic_loop" in res_loop
    assert "session" not in res_loop
    assert res_loop["agentic_loop"]["turns"] == 2
    assert res_loop["agentic_loop"]["records"] == 2

    # 4. Test target_variable assignment
    res_var = get_context_metrics(scope="all", target_variable="MY_METRICS", app=app)
    assert res_var["target_variable"] == "MY_METRICS"
    saved = app.buffer_manager.get_script_var("MY_METRICS")
    assert saved is not None
    assert saved["scope"] == "all"
    assert saved["total"]["total_turns"] == 4
    assert saved["total"]["characters"] == res_all["total"]["characters"]


@pytest.mark.anyio
async def test_dispatch_tool_get_context_metrics():
    app = ChatybotApp()
    app.initialize()

    app.chat_history = [("Hello", "Hi there!")]
    app.buffer_manager.set_script_var("AGENTIC_LOOP", [{"turn": 1, "tool": "test"}], allow_protected=True)

    invocation = json.dumps({
        "tool": "get_context_metrics",
        "arguments": {
            "scope": "all",
            "target_variable": "CTX_INFO"
        }
    })

    result_str = await app.dispatch_tool(invocation)
    assert "Tool dispatched successfully" or "status" in result_str
    result_data = json.loads(result_str)
    assert result_data["status"] == "success"
    assert result_data["tool"] == "get_context_metrics"
    assert result_data["result"]["session"]["turns"] == 1
    assert result_data["result"]["agentic_loop"]["records"] == 1

    # Verify script var was set
    ctx_var = app.buffer_manager.get_script_var("CTX_INFO")
    assert ctx_var is not None
    assert ctx_var["scope"] == "all"
