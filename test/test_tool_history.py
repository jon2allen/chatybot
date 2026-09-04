import os
import tempfile
import pytest
from unittest.mock import patch

from chatybot.chatybot_app import ChatybotApp


@pytest.fixture
def app():
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = os.path.join(tmpdir, "config.toml")
        with open(config_path, "w") as f:
            f.write("[general]\nmodel = 'test_model'\n")

        with patch("chatybot.chatybot_app.readline"), patch("chatybot.chatybot_app.ConfigManager") as mock_cfg:
            cfg_instance = mock_cfg.return_value
            cfg_instance.config = {
                "models": {
                    "test_model": {
                        "name": "test-model",
                        "base_url": "https://api.openai.com/v1",
                        "api_key": "TEST_KEY",
                    }
                }
            }
            cfg_instance.active_model_alias = "test_model"
            cfg_instance.get_model_config.return_value = cfg_instance.config["models"]["test_model"]
            cfg_instance.system_message = "System"

            app_instance = ChatybotApp()
            app_instance.config_manager = cfg_instance
            app_instance.session_dir = os.path.join(tmpdir, "sessions")
            yield app_instance


def _make_loop(records):
    """Build a minimal agentic_loop list of tool-call records."""
    return [
        {
            "turn": r.get("turn", 1),
            "tool": r.get("tool", "unknown"),
            "arguments": r.get("arguments", {}),
            "result": r.get("result", ""),
            "exit_code": r.get("exit_code", 0),
            "status": r.get("status", "success"),
            "timestamp": r.get("timestamp", "2026-09-03T12:00:00.000000"),
            "duration_ms": r.get("duration_ms", 50.0),
        }
        for r in records
    ]


class TestToolHistory:
    @pytest.mark.anyio
    async def test_history_no_session(self, app, capsys):
        await app.handle_escape_command("/tool history")
        out = capsys.readouterr().out
        assert "No active session" in out

    @pytest.mark.anyio
    async def test_history_empty_session(self, app, capsys):
        app.session_turns = [{"turn_id": 1, "prompt": "hi", "response": "hello"}]
        await app.handle_escape_command("/tool history")
        out = capsys.readouterr().out
        assert "No agentic tool loops found" in out

    @pytest.mark.anyio
    async def test_history_lists_loops(self, app, capsys):
        app.active_session_name = "test_session"
        app.session_turns = [
            {"turn_id": 1, "prompt": "hello", "response": "hi"},
            {
                "turn_id": 2,
                "prompt": "list files",
                "response": "done",
                "agentic_loop": _make_loop([
                    {"tool": "list_directory", "arguments": {"path": "."}},
                    {"tool": "read_file", "arguments": {"path": "a.txt"}},
                ]),
            },
            {
                "turn_id": 5,
                "prompt": "search code",
                "response": "found",
                "agentic_loop": _make_loop([
                    {"tool": "grep_search", "arguments": {"pattern": "foo"}, "status": "success"},
                    {"tool": "write_file", "arguments": {"path": "out.txt"}, "status": "error", "result": "Permission denied"},
                ]),
            },
        ]
        await app.handle_escape_command("/tool history")
        out = capsys.readouterr().out
        assert "AGENTIC LOOP HISTORY" in out
        assert "test_session" in out
        assert "Turn 2" in out
        assert "Turn 5" in out
        assert "list_directory" in out
        assert "grep_search" in out
        assert "Total: 2 loop(s)" in out
        # Timing: each loop has 2 calls x 50ms = 100ms
        assert "100ms" in out

    @pytest.mark.anyio
    async def test_history_detail_for_specific_turn(self, app, capsys):
        app.session_turns = [
            {
                "turn_id": 3,
                "prompt": "read and search",
                "response": "done",
                "agentic_loop": _make_loop([
                    {"tool": "read_file", "arguments": {"path": "test.py"}, "turn": 1},
                    {"tool": "grep_search", "arguments": {"pattern": "def"}, "turn": 2, "status": "error", "result": "No matches found"},
                ]),
            },
        ]
        await app.handle_escape_command("/tool history 3")
        out = capsys.readouterr().out
        assert "AGENTIC LOOP — Turn 3" in out
        assert "read and search" in out
        assert "read_file" in out
        assert "grep_search" in out
        assert "FAILED" in out
        assert "No matches found" in out
        assert '"path": "test.py"' in out
        # Detail view should show per-call duration and timestamp
        assert "50.0ms" in out
        assert "time:" in out

    @pytest.mark.anyio
    async def test_history_detail_turn_not_found(self, app, capsys):
        app.session_turns = [
            {"turn_id": 1, "prompt": "hi", "response": "hello"},
            {
                "turn_id": 2,
                "prompt": "do work",
                "response": "done",
                "agentic_loop": _make_loop([{"tool": "list_directory"}]),
            },
        ]
        await app.handle_escape_command("/tool history 99")
        out = capsys.readouterr().out
        assert "No turn 99 found" in out
        assert "Turns with agentic loops: 2" in out

    @pytest.mark.anyio
    async def test_history_current_uses_show_trace(self, app, capsys):
        app.buffer_manager.set_script_var(
            "AGENTIC_LOOP",
            _make_loop([{"tool": "list_directory", "turn": 1}]),
            allow_protected=True,
        )
        await app.handle_escape_command("/tool history current")
        out = capsys.readouterr().out
        assert "AGENTIC LOOP TRACE" in out
        assert "list_directory" in out

    @pytest.mark.anyio
    async def test_history_current_empty(self, app, capsys):
        await app.handle_escape_command("/tool history current")
        out = capsys.readouterr().out
        assert "No agentic loop has been run yet" in out

    @pytest.mark.anyio
    async def test_history_invalid_arg(self, app, capsys):
        await app.handle_escape_command("/tool history foobar")
        out = capsys.readouterr().out
        assert "Invalid argument 'foobar'" in out

    @pytest.mark.anyio
    async def test_history_backwards_compatible_no_timing(self, app, capsys):
        """Old session turns without timing fields should still display correctly."""
        app.session_turns = [
            {
                "turn_id": 1,
                "prompt": "old turn",
                "response": "done",
                "agentic_loop": [
                    {"turn": 1, "tool": "list_directory", "arguments": {}, "result": "", "exit_code": 0, "status": "success"},
                ],
            },
        ]
        # Summary should not crash and should not show duration
        await app.handle_escape_command("/tool history")
        out = capsys.readouterr().out
        assert "Turn 1" in out
        assert "1 calls" in out
        # No duration bracket since old records lack duration_ms
        assert "ms]" not in out

        # Detail should not crash either
        await app.handle_escape_command("/tool history 1")
        out = capsys.readouterr().out
        assert "list_directory" in out
        assert "SUCCESS" in out
        # No duration or time line for old records
        assert "ms)" not in out
        assert "time:" not in out

    @pytest.mark.anyio
    async def test_append_session_turn_stores_completion_timing(self, app):
        """append_session_turn should persist timestamp and elapsed_ms in turn_data."""
        app.session_mode = "on"
        store = app._get_session_store()
        store.create_session("test_timing_session", model_alias="test_model", custom_name="timing_test", initial_prompt="", notes=None)
        app.active_session_id = "test_timing_session"
        app.active_session_name = "timing_test"
        app.session_first_prompt_slug = "test"
        app.session_created_at = "2026-09-03T12:00:00.000000"

        timing = {
            "timestamp": "2026-09-03T12:00:01.500000",
            "elapsed_ms": 1500.0,
        }
        app.append_session_turn("test prompt", "test response", timing=timing)

        assert len(app.session_turns) == 1
        turn = app.session_turns[0]
        assert turn["timestamp"] == "2026-09-03T12:00:01.500000"
        assert turn["elapsed_ms"] == 1500.0

    @pytest.mark.anyio
    async def test_append_session_turn_stores_tps_when_provided(self, app):
        """append_session_turn should persist TPS data when included in timing dict."""
        app.session_mode = "on"
        store = app._get_session_store()
        store.create_session("test_tps_session", model_alias="test_model", custom_name="tps_test", initial_prompt="", notes=None)
        app.active_session_id = "test_tps_session"
        app.active_session_name = "tps_test"
        app.session_first_prompt_slug = "test"
        app.session_created_at = "2026-09-03T12:00:00.000000"

        timing = {
            "timestamp": "2026-09-03T12:00:01.500000",
            "elapsed_ms": 1500.0,
            "tps": {"total": 42.5, "think": 20.0, "regular": 22.5},
        }
        app.append_session_turn("test prompt", "test response", timing=timing)

        turn = app.session_turns[0]
        assert turn["tps"]["total"] == 42.5
        assert turn["tps"]["think"] == 20.0
        assert turn["tps"]["regular"] == 22.5

    @pytest.mark.anyio
    async def test_append_session_turn_without_timing(self, app):
        """append_session_turn without timing should not add timing keys (backwards compat)."""
        app.session_mode = "on"
        store = app._get_session_store()
        store.create_session("test_no_timing", model_alias="test_model", custom_name="no_timing", initial_prompt="", notes=None)
        app.active_session_id = "test_no_timing"
        app.active_session_name = "no_timing"
        app.session_first_prompt_slug = "test"
        app.session_created_at = "2026-09-03T12:00:00.000000"

        app.append_session_turn("test prompt", "test response")

        turn = app.session_turns[0]
        assert "timestamp" not in turn
        assert "elapsed_ms" not in turn
        assert "tps" not in turn
