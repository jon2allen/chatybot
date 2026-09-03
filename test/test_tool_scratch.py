import os
import tempfile
import pytest
from unittest.mock import patch

from chatybot.chatybot_app import ChatybotApp
from chatybot.profile_model import ProfileConfig


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


class TestToolScratch:
    def test_get_scratch_dir_no_session(self, app):
        app.active_session_id = None
        scratch_dir = app.get_scratch_dir(create=True)
        assert os.path.exists(scratch_dir)
        assert scratch_dir.endswith("scratch")
        assert "sessions" not in os.path.basename(scratch_dir)

    def test_get_scratch_dir_active_session(self, app):
        app.active_session_id = "test_session_123"
        scratch_dir = app.get_scratch_dir(create=True)
        assert os.path.exists(scratch_dir)
        expected_suffix = os.path.join("sessions", "test_session_123", "scratch")
        assert scratch_dir.endswith(expected_suffix)

    @pytest.mark.anyio
    async def test_tool_scratch_toggle_on_off(self, app):
        # Enable tool mode so TOOL_CONTEXT gets updated in buffer_manager
        app.tool_mode = True
        
        # Turn scratch on
        await app.handle_escape_command("/tool scratch on")
        assert app.tool_scratch is True
        context = app.buffer_manager.get_script_var("TOOL_CONTEXT")
        assert "=== SCRATCHPAD AREA ===" in context
        scratch_dir = app.get_scratch_dir(create=False)
        assert scratch_dir in context

        # Turn scratch off
        await app.handle_escape_command("/tool scratch off")
        assert app.tool_scratch is False
        context_off = app.buffer_manager.get_script_var("TOOL_CONTEXT")
        assert "=== SCRATCHPAD AREA ===" not in context_off

    @pytest.mark.anyio
    async def test_tool_scratch_status_and_clean(self, app, capsys):
        await app.handle_escape_command("/tool scratch on")
        scratch_dir = app.get_scratch_dir(create=True)

        # Create temporary dummy files
        test_file1 = os.path.join(scratch_dir, "test1.py")
        test_file2 = os.path.join(scratch_dir, "test2.sh")
        with open(test_file1, "w") as f:
            f.write("print('hello')\n")
        with open(test_file2, "w") as f:
            f.write("echo 'hello'\n")

        # Test status shows files
        capsys.readouterr()  # clear buffer
        await app.handle_escape_command("/tool scratch status")
        captured = capsys.readouterr().out
        assert "Tool scratch mode is currently enabled" in captured
        assert "test1.py" in captured
        assert "test2.sh" in captured

        # Clean scratch directory
        await app.handle_escape_command("/tool scratch clean")
        captured_clean = capsys.readouterr().out
        assert "Cleaned scratch directory: removed 2 item(s)" in captured_clean
        assert not os.path.exists(test_file1)
        assert not os.path.exists(test_file2)

    def test_profile_model_scratch_parsing_and_serialization(self):
        from chatybot.profile_model import Profile

        content_on = """/model test_model
/tool auto on
/tool on
/tool scratch on
/tool max_turns 25
"""
        profile = Profile.from_chatdsl_string(content_on)
        assert profile.config.tool_settings.scratch is True

        # Check serialization contains /tool scratch on
        serialized = profile.to_chatdsl()
        assert "/tool scratch on" in serialized

        content_off = """/model test_model
/tool auto on
/tool on
/tool scratch off
/tool max_turns 25
"""
        profile_off = Profile.from_chatdsl_string(content_off)
        assert profile_off.config.tool_settings.scratch is False
        assert "/tool scratch on" not in profile_off.to_chatdsl()
