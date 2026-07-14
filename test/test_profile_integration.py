import pytest
import tempfile
import os
from unittest.mock import MagicMock, patch, AsyncMock
from src.chatybot.chatybot_app import ChatybotApp

class TestProfileIntegration:
    @pytest.fixture
    def app(self):
        with patch('src.chatybot.chatybot_app.readline'):
            with patch('src.chatybot.chatybot_app.ConfigManager') as mock_cfg:
                cfg_instance = mock_cfg.return_value
                cfg_instance.config = {
                    "models": {
                        "test_model": {
                            "name": "test-model",
                            "base_url": "https://api.openai.com/v1",
                            "api_key": "TEST_KEY"
                        }
                    }
                }
                cfg_instance.active_model_alias = "test_model"
                cfg_instance.get_model_config.return_value = cfg_instance.config["models"]["test_model"]
                cfg_instance.system_message = "System"
                
                application = ChatybotApp()
                application.config_manager = cfg_instance
                yield application

    @pytest.mark.anyio
    async def test_handle_profile_command_list(self, app, capsys):
        with tempfile.TemporaryDirectory() as tmpdir:
            app.profile_dir = tmpdir
            
            # Create a mock profile
            profile_path = os.path.join(tmpdir, "test.chatdsl")
            with open(profile_path, "w", encoding="utf-8") as f:
                f.write("# @name: Integration Test Profile\n# @description: Test desc\n/model test_model")
                
            await app.handle_profile_command(["list"])
            captured = capsys.readouterr()
            
            assert "test.chatdsl" in captured.out
            assert "Test desc" in captured.out

    @pytest.mark.anyio
    async def test_handle_profile_command_use(self, app):
        with tempfile.TemporaryDirectory() as tmpdir:
            app.profile_dir = tmpdir
            
            # Create a mock profile
            profile_path = os.path.join(tmpdir, "use_test.chatdsl")
            with open(profile_path, "w", encoding="utf-8") as f:
                f.write("/model test_model\n/temp 1.5")
                
            app.execute_script = AsyncMock()
            await app.handle_profile_command(["use", "use_test"])
            
            app.execute_script.assert_called_once_with(profile_path)

    @pytest.mark.anyio
    async def test_tool_max_turns_command(self, app):
        # Test default
        assert app.max_turns == 25
        
        # Set max_turns using command
        await app.handle_escape_command("/tool max_turns 42")
        assert app.max_turns == 42
        
        # Test showing current
        with patch('builtins.print') as mock_print:
            await app.handle_escape_command("/tool max_turns")
            mock_print.assert_called_with("Current max tool turns: 42")

    def test_profile_help_documentation(self, app):
        app.initialize()
        # Verify HelpSystem registration
        from src.chatybot.chaty_help import get_help_system
        help_sys = get_help_system()
        help_text = help_sys.get_help_text("/profile")
        assert "/profile" in help_text
        assert "Manage chat session profiles dynamically" in help_text
        assert "list" in help_text
        assert "edit" in help_text

        # Verify show_help output contains /profile
        with patch('builtins.print') as mock_print:
            app.show_help()
            called_args = [call[0][0] for call in mock_print.call_args_list if call[0]]
            profile_line = [line for line in called_args if "/profile" in line]
            assert len(profile_line) > 0
            assert "Manage session profiles dynamically" in profile_line[0]

        # Verify matcher autocomplete contains profile
        assert "profile" in app.matcher.words

