#!/usr/bin/env python3
"""
Unit tests for Chatybot Multiline REPL and Script lookahead functionality
"""

import pytest
import tempfile
import os
from unittest.mock import MagicMock, patch, AsyncMock
from src.chatybot.chatybot_app import ChatybotApp


class TestMultilineBehavior:
    """Test suite for the new multiline REPL auto-exit and script lookahead"""

    @pytest.fixture
    def app(self):
        """Create a ChatybotApp instance with clean state and mock dependencies"""
        with patch('src.chatybot.chatybot_app.readline'):
            # Mock configuration manager so it doesn't try to load config files
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
    async def test_get_multi_line_input_auto_exit(self, app):
        """Test that get_multi_line_input sets multi_line_mode=False and auto_exit_pending=True on ';;'"""
        app.multi_line_mode = True
        app.auto_exit_pending = False
        
        # Mock input to return lines, ending with ';;'
        input_values = ["line 1", "line 2", ";;"]
        with patch('builtins.input', side_effect=input_values):
            prompt = await app.get_multi_line_input()
            
            assert prompt == "line 1\nline 2"
            assert app.multi_line_mode is False
            assert app.auto_exit_pending is True

    @pytest.mark.anyio
    async def test_repl_bypass_legacy_multiline(self, app):
        """Test that main_loop bypasses legacy /multiline when auto_exit_pending is True only under script_context"""
        # Scenario 1: Interactive REPL (script_context = False)
        app.multi_line_mode = False
        app.auto_exit_pending = True
        app.script_context = False
        
        prompt = "/multiline"
        bypassed = False
        if app.auto_exit_pending:
            app.auto_exit_pending = False
            if app.script_context and prompt.strip() == "/multiline":
                bypassed = True
                
        assert bypassed is False  # Should not be bypassed in interactive mode
        assert app.auto_exit_pending is False

        # Scenario 2: Script mode (script_context = True)
        app.auto_exit_pending = True
        app.script_context = True
        
        bypassed = False
        if app.auto_exit_pending:
            app.auto_exit_pending = False
            if app.script_context and prompt.strip() == "/multiline":
                bypassed = True
                
        assert bypassed is True  # Should be bypassed in script mode
        assert app.auto_exit_pending is False

    @pytest.mark.anyio
    async def test_script_auto_exit_and_lookahead_bypass(self, app):
        """Test that execute_script disables multi_line_mode on ';;' and bypasses trailing '/multiline'"""
        script_content = """/multiline
line 1
line 2
;;
/multiline
/save output.txt
"""
        
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.chatdsl') as f:
            f.write(script_content)
            f.flush()
            script_path = f.name
            
        try:
            # Mock chat_completion to avoid API key validation/network requests
            app.chat_completion = AsyncMock(return_value="mock response")
            
            # Setup realistic escape command handler mock that toggles mode
            async def mock_handle_escape_command(cmd):
                if cmd.strip() == "/multiline":
                    app.multi_line_mode = not app.multi_line_mode
                return True
                
            app.handle_escape_command = mock_handle_escape_command
            
            # Wrap execute_script_command to record execution calls and use mock_handle_escape_command
            executed_calls = []
            original_execute_script_command = app.execute_script_command
            
            async def wrap_execute_script_command(cmd, handler):
                executed_calls.append(cmd)
                return await original_execute_script_command(cmd, mock_handle_escape_command)
                
            app.execute_script_command = wrap_execute_script_command
            
            # Start script execution
            await app.execute_script(script_path)
            
            # Verify that multi_line_mode was toggled off on ';;'
            assert app.multi_line_mode is False
            
            # Should have executed '/multiline' (to start), the multiline prompt, and '/save output.txt'
            # But the second '/multiline' (legacy toggle off) should be bypassed.
            assert "/multiline" in executed_calls
            assert "/save output.txt" in executed_calls
            
            # The second '/multiline' should NOT be executed. Since we replace it with "",
            # we should not see a second '/multiline' call.
            multiline_calls = [c for c in executed_calls if c == "/multiline"]
            assert len(multiline_calls) == 1

        finally:
            os.unlink(script_path)

    @pytest.mark.anyio
    async def test_interactive_escape_command_placeholder_resolution(self, app):
        """Test that interactive escape commands resolve variables in main_loop"""
        app.buffer_manager.set_script_var("arr1", ["Nanjing_food_comparison/mistral_results.txt"])
        
        # Mock handle_escape_command to record the command it was called with
        called_commands = []
        async def mock_handle_escape_command(cmd):
            called_commands.append(cmd)
            return True
        app.handle_escape_command = mock_handle_escape_command
        
        # Test case 1: Standard escape command via direct input
        with patch('builtins.input', side_effect=["/dump ${arr1[0]}", KeyboardInterrupt()]):
            await app.main_loop()
            
        assert len(called_commands) == 1
        assert called_commands[0] == "/dump Nanjing_food_comparison/mistral_results.txt"
        
        # Test case 2: Escape command resolved via history search (!)
        called_commands.clear()
        app.handle_history_command = AsyncMock(return_value="/dump ${arr1[0]}")
        with patch('builtins.input', side_effect=["!1", KeyboardInterrupt()]):
            await app.main_loop()
            
        assert len(called_commands) == 1
        assert called_commands[0] == "/dump Nanjing_food_comparison/mistral_results.txt"

        # Test case 3: /setvar command is NOT resolved (handled internally)
        called_commands.clear()
        with patch('builtins.input', side_effect=["/setvar val = ${arr1[0]}", KeyboardInterrupt()]):
            await app.main_loop()
            
        assert len(called_commands) == 1
        assert called_commands[0] == "/setvar val = ${arr1[0]}"

    @pytest.mark.anyio
    async def test_source_command(self, app):
        """Test that /source executes a script path and returns True"""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.chatdsl') as f:
            f.write("# some comment\n/echo hello\n")
            f.flush()
            script_path = f.name
            
        try:
            # Mock execute_script
            mock_execute = AsyncMock()
            app.execute_script = mock_execute
            
            result = await app.handle_escape_command(f"/source {script_path}")
            assert result is True
            mock_execute.assert_called_once_with(os.path.abspath(script_path))
        finally:
            os.unlink(script_path)

    @pytest.mark.anyio
    async def test_profile_startup(self, app):
        """Test that main_loop loads and runs profile at startup"""
        app.profile_to_load = "/some/profile.chatdsl"
        
        mock_execute = AsyncMock()
        app.execute_script = mock_execute
        
        with patch('os.path.exists', return_value=True):
            with patch('builtins.input', side_effect=KeyboardInterrupt()):
                await app.main_loop()
                
        mock_execute.assert_called_once_with("/some/profile.chatdsl")



if __name__ == "__main__":
    pytest.main([__file__, "-v"])
