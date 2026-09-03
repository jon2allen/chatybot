import os
import tempfile
from pathlib import Path
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

    def test_get_scratch_dir_trailing_slash_and_relative(self, app):
        app.active_session_id = None
        # Trailing slash
        app.session_dir = "/tmp/test_chatybot/sessions/"
        scratch_dir = app.get_scratch_dir(create=False)
        expected = str(Path("/tmp/test_chatybot/scratch").resolve())
        assert scratch_dir == expected
        assert not scratch_dir.endswith("sessions/scratch")

        # Relative path
        app.session_dir = "my_sessions/"
        rel_scratch = app.get_scratch_dir(create=False)
        assert rel_scratch.endswith("scratch")
        assert not rel_scratch.endswith("my_sessions/scratch")

    def test_get_scratch_dir_mkdir_failure(self, app):
        with patch("os.makedirs", side_effect=OSError("Permission denied")):
            scratch = app.get_scratch_dir(create=True)
            assert scratch is None

            app.tool_scratch = True
            app._tool_scratch_user_set = True
            context = app.generate_tool_context()
            # If scratch_dir creation fails, scratchpad area should be omitted
            assert "=== SCRATCHPAD AREA ===" not in context

    def test_scratch_path_quoted_in_prompt_context(self, app):
        app.tool_scratch = True
        app._tool_scratch_user_set = True
        app.active_session_id = "test_alias 20260903"
        context = app.generate_tool_context()
        assert 'python3 "' in context
        assert 'bash "' in context

    def test_profile_manager_sets_tool_scratch_user_set(self, app):
        from chatybot.profile_manager import ProfileManager
        from chatybot.profile_model import Profile, ProfileConfig, ToolSettings

        pm = ProfileManager(os.path.join(tempfile.gettempdir(), "profiles"))
        cfg = ProfileConfig(model_alias="test_model", tool_settings=ToolSettings(scratch=True))
        profile = Profile(name="test_prof", config=cfg)

        app._tool_scratch_user_set = False
        pm.apply_profile_commands(profile, app)
        assert app.tool_scratch is True
        assert app._tool_scratch_user_set is True

    @pytest.mark.anyio
    async def test_tool_scratch_on_notice_when_tool_mode_off(self, app, capsys):
        app.tool_mode = False
        await app.handle_escape_command("/tool scratch on")
        captured = capsys.readouterr().out
        assert "Tool mode is currently OFF" in captured

