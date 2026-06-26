#!/usr/bin/env python3
"""
Unit tests for Chatybot /run and /tool command functionality.
"""

import pytest
import tempfile
import os
import json
from unittest.mock import MagicMock, patch, AsyncMock
from src.chatybot.chatybot_app import ChatybotApp


class TestRunCommandBehavior:
    """Test suite for the /run and /tool commands"""

    @pytest.fixture
    def app(self):
        """Create a ChatybotApp instance with clean state and mock dependencies"""
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

    def test_execute_simple_command(self, app):
        """Verifies execution of simple shell actions and consistent variable store updates"""
        app.safe_mode = True
        app.execute_shell_command("echo hello")
        
        assert app.buffer_manager.get_script_var('RUN_EXIT_CODE') == '0'
        assert app.buffer_manager.get_script_var('RUN_COMPLETION').strip() == 'hello'
        assert app.buffer_manager.get_script_var('RUN_ERROR') == ''
        assert app.buffer_manager.get_script_var('LAST_COMPLETION').strip() == 'hello'

    @pytest.mark.anyio
    async def test_run_variable_substitution(self, app):
        """Confirms ${VAR} substitutions are successfully resolved before executing"""
        app.buffer_manager.set_script_var('MY_VAR', 'hello_world')
        
        # We handle /run echo ${MY_VAR}
        await app.handle_escape_command("/run echo ${MY_VAR}")
        
        assert app.buffer_manager.get_script_var('RUN_EXIT_CODE') == '0'
        assert app.buffer_manager.get_script_var('RUN_COMPLETION').strip() == 'hello_world'

    def test_safe_mode_blocks_dangerous_patterns(self, app):
        """Asserts that unsafe shell actions are blocked under /run_safe"""
        app.safe_mode = True
        
        # Test command with recursive delete rm -rf
        app.execute_shell_command("rm -rf /some/path")
        
        assert app.buffer_manager.get_script_var('RUN_EXIT_CODE') == '-1'
        assert "Blocked (safe mode)" in app.buffer_manager.get_script_var('RUN_COMPLETION')

    def test_unsafe_mode_prompt_confirmation(self, app):
        """Verifies prompt and execution flow for dangerous commands under /run_unsafe"""
        app.safe_mode = False
        
        # Mock input to abort (return 'n')
        with patch('builtins.input', return_value='n'):
            app.execute_shell_command("rm -rf /some/path")
            assert app.buffer_manager.get_script_var('RUN_EXIT_CODE') == '-1'
            assert "Command aborted by user" in app.buffer_manager.get_script_var('RUN_COMPLETION')
            
        # Mock input to confirm (return 'y') and mock subprocess.run to avoid actual execution
        with patch('builtins.input', return_value='y'):
            with patch('subprocess.run') as mock_run:
                mock_run.return_value.returncode = 0
                mock_run.return_value.stdout = "aborted_but_override_success"
                mock_run.return_value.stderr = ""
                app.execute_shell_command("rm -rf /some/path")
                assert app.buffer_manager.get_script_var('RUN_EXIT_CODE') == '0'

    @pytest.mark.anyio
    async def test_quotes_stripping_and_balance(self, app):
        """Verifies correct outer-quote stripping and shlex token matching"""
        # Outer quotes stripped
        await app.handle_escape_command('/run "echo hello"')
        assert app.buffer_manager.get_script_var('RUN_COMPLETION').strip() == 'hello'
        
        # Unbalanced quotes should show warning/error
        with patch('builtins.print') as mock_print:
            await app.handle_escape_command('/run "echo hello')
            # Should print error message
            mock_print.assert_any_call("Error: No closing quotation")

    @pytest.mark.anyio
    async def test_tool_mode_toggle(self, app):
        """Verifies context building and variable updates when toggling /tool on/off"""
        # Check /tool on
        with patch('os.path.exists', return_value=True):
            with patch('builtins.open', tempfile.NamedTemporaryFile):
                # Mock generate_tool_context to return a specific description
                app.generate_tool_context = MagicMock(return_value="=== AVAILABLE TOOLS ===\ntool: list_directory")
                
                await app.handle_escape_command("/tool on")
                assert app.tool_mode is True
                assert app.buffer_manager.get_script_var('TOOL_CONTEXT') == "=== AVAILABLE TOOLS ===\ntool: list_directory"
                
        # Check /tool off
        await app.handle_escape_command("/tool off")
        assert app.tool_mode is False
        assert app.buffer_manager.get_script_var('TOOL_CONTEXT') == ""

    @pytest.mark.anyio
    async def test_tool_dispatch_from_last_completion(self, app):
        """Verifies executing tool payloads parsed from LAST_COMPLETION"""
        # Set LAST_COMPLETION to a valid json invocation
        invocation = {"tool": "list_directory", "arguments": {"path": "."}}
        app.buffer_manager.set_script_var('LAST_COMPLETION', json.dumps(invocation))
        
        # Mock subprocess.run for dispatcher.py execution
        with patch('subprocess.run') as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = '{"status": "success", "result": ["file1.txt"]}'
            mock_run.return_value.stderr = ''
            
            await app.handle_escape_command("/tool")
            
            assert app.buffer_manager.get_script_var('TOOL_DISPATCH_EXIT_CODE') == '0'
            assert "success" in app.buffer_manager.get_script_var('TOOL_DISPATCH_RESULT')

    @pytest.mark.anyio
    async def test_tool_dispatch_with_direct_json_or_file(self, app):
        """Asserts correct routing of arguments via inline JSON or file paths"""
        invocation = {"tool": "list_directory", "arguments": {"path": "."}}
        
        with patch('subprocess.run') as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = '{"status": "success"}'
            mock_run.return_value.stderr = ''
            
            # Inline JSON
            await app.handle_escape_command(f'/tool {json.dumps(invocation)}')
            assert app.buffer_manager.get_script_var('TOOL_DISPATCH_EXIT_CODE') == '0'
            
            # From file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as tmp:
                tmp.write(json.dumps(invocation))
                tmp_path = tmp.name
                
            try:
                await app.handle_escape_command(f'/tool {tmp_path}')
                assert app.buffer_manager.get_script_var('TOOL_DISPATCH_EXIT_CODE') == '0'
            finally:
                os.unlink(tmp_path)

    @pytest.mark.anyio
    async def test_double_semicolon_output_no_conflict(self, app):
        """Confirms that double-semicolons (;;) in command outputs are processed safely"""
        # Execute a command that outputs double-semicolons
        app.safe_mode = False # Allow command chaining or other symbols if any
        
        # We can mock subprocess.run to return double semicolons
        with patch('subprocess.run') as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = 'line1\n;;\nline2'
            mock_run.return_value.stderr = ''
            
            with patch('builtins.input', return_value='y'):
                app.execute_shell_command("echo ';'")
            
            assert app.buffer_manager.get_script_var('RUN_COMPLETION') == 'line1\n;;\nline2'
            # Check that it doesn't trigger multiline mode or auto_exit_pending in app state
            assert app.multi_line_mode is False
            assert app.auto_exit_pending is False

    @pytest.mark.anyio
    async def test_tool_loop_terminal_state(self, app):
        """Setup chat history with NL response, tool loop exits immediately"""
        app.chat_history = [("User query", "Some response that is NOT a tool call")]
        app.chat_completion = AsyncMock(return_value="Still not a tool call")
        await app.handle_escape_command("/tool loop 3")
        assert app.chat_history == [("User query", "Still not a tool call")]
        assert app.chat_completion.call_count == 1

    @pytest.mark.anyio
    async def test_tool_loop_execution_success(self, app):
        """Setup tool call, dispatch tool, get final response, verify history has only final response"""
        app.chat_history = [("Find files", '{"tool": "list_directory", "arguments": {"path": "."}}')]
        app.chat_completion = AsyncMock(return_value="Here is the content: some final response text")
        
        with patch('subprocess.run') as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = '{"status": "success", "result": ["file1.txt"]}'
            mock_run.return_value.stderr = ''
            
            await app.handle_escape_command("/tool loop 5")
            
            # Length of chat_history must still be 1 (original turn)
            assert len(app.chat_history) == 1
            # Final output must be committed to history
            assert app.chat_history[-1][0] == "Find files"
            assert app.chat_history[-1][1] == "Here is the content: some final response text"
            
            # chat_completion should have been called once with temp history
            app.chat_completion.assert_called_once()
            
            # Check that TOOL_DISPATCH_RESULT was written
            assert "success" in app.buffer_manager.get_script_var('TOOL_DISPATCH_RESULT')

    @pytest.mark.anyio
    async def test_tool_loop_max_turns_limit(self, app):
        """Setup tool loop that keeps requesting tools, should exit at max turns"""
        app.chat_history = [("Find files", '{"tool": "list_directory", "arguments": {"path": "."}}')]
        app.chat_completion = AsyncMock(return_value='{"tool": "list_directory", "arguments": {"path": "."}}')
        
        with patch('subprocess.run') as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = '{"status": "success"}'
            mock_run.return_value.stderr = ''
            
            await app.handle_escape_command("/tool loop max=2")
            
            # 2 turns maximum:
            # Turn 1: process initial, calls dispatch, requests next completion (1 completion call)
            # Turn 2: processes next completion, calls dispatch, reaches max turns limit, and requests final summary completion.
            # So chat_completion should be called exactly twice.
            assert app.chat_completion.call_count == 2
            assert len(app.chat_history) == 1
            assert "list_directory" in app.chat_history[-1][1]

    def test_run_command_tool(self):
        """Verifies that the run_command tool executes safe commands and blocks unsafe ones"""
        from src.chatybot.tools.file_utils import run_command
        
        # Test safe command execution
        res = run_command("echo hello_world")
        assert "hello_world" in res
        
        # Test dangerous command blocking
        res_blocked = run_command("rm -rf /some/dir")
        assert "Blocked" in res_blocked

    def test_extract_tool_call_comments(self, app):
        """Verifies that extract_tool_call strips comments and trailing commas correctly"""
        text = """
        To do this:
        ```json
        {
          "tool": "find_files", // Find matching files
          "arguments": {
            "path": ".",  # Start from root
            "pattern": "*.chatdsl",
          }
        }
        ```
        """
        tool_call = app.extract_tool_call(text)
        assert tool_call is not None
        assert tool_call["tool"] == "find_files"
        assert tool_call["arguments"]["path"] == "."
        assert tool_call["arguments"]["pattern"] == "*.chatdsl"

    @pytest.mark.anyio
    async def test_tool_loop_argument_parsing(self, app):
        """Verifies different argument combinations for the /tool loop command"""
        app.chat_history = [("Query", "Result")]
        
        # Mock execute_tool_loop to assert max_turns passed to it
        app.execute_tool_loop = AsyncMock()
        
        # Default with no args -> 5
        await app.handle_escape_command("/tool loop")
        app.execute_tool_loop.assert_called_with(5)
        
        # 'max' -> 100
        await app.handle_escape_command("/tool loop max")
        app.execute_tool_loop.assert_called_with(100)
        
        # 'max=150' without force -> capped at 100
        await app.handle_escape_command("/tool loop max=150")
        app.execute_tool_loop.assert_called_with(100)
        
        # 'max=150 force' -> 150
        await app.handle_escape_command("/tool loop max=150 force")
        app.execute_tool_loop.assert_called_with(150)
        
        # 'force 150' -> 150
        await app.handle_escape_command("/tool loop force 150")
        app.execute_tool_loop.assert_called_with(150)

    @pytest.mark.anyio
    async def test_tool_loop_initializes_with_natural_language(self, app):
        """Verifies that if the last completion was natural language, the loop fetches an initial tool call from LLM"""
        app.chat_history = [("Find files", "Sure! I can help you search for that.")]
        
        # First call: LLM returns a tool call
        # Second call: LLM returns final response
        app.chat_completion = AsyncMock(side_effect=[
            '{"tool": "list_directory", "arguments": {"path": "."}}',
            "Here is the final response."
        ])
        
        with patch('subprocess.run') as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = '{"status": "success"}'
            mock_run.return_value.stderr = ''
            
            await app.handle_escape_command("/tool loop max=2")
            
            # The tool loop should have successfully fetched the tool call first, run it,
            # and then finished on the second turn.
            assert app.chat_completion.call_count == 2
            assert app.chat_history[-1][1] == "Here is the final response."

    def test_extract_tool_call_normalization(self, app):
        """Verifies that extract_tool_call normalizes fully qualified function paths to short tool names"""
        # Test fully qualified name in JSON block
        text1 = '```json\n{"tool": "chatybot.tools.file_utils.find_files", "arguments": {"path": "/github2", "search_term": "Conrad"}}\n```'
        call1 = app.extract_tool_call(text1)
        assert call1 is not None
        assert call1["tool"] == "find_files"
        assert call1["arguments"]["search_term"] == "Conrad"

        # Test fully qualified name in raw text JSON
        text2 = '{"tool": "chatybot.tools.file_utils.list_directory", "arguments": {"path": "."}}'
        call2 = app.extract_tool_call(text2)
        assert call2 is not None
        assert call2["tool"] == "list_directory"

    @pytest.mark.anyio
    async def test_native_tool_calls_mapping(self, app):
        """Verifies that native tool_calls in API response are successfully mapped to JSON blocks in chat_completion"""
        app.initialize()
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_message = MagicMock()
        
        # Configure tool call object
        mock_tool_call = MagicMock()
        mock_tool_call.function.name = "list_directory"
        mock_tool_call.function.arguments = '{"path": "/github2"}'
        
        mock_message.content = None
        mock_message.tool_calls = [mock_tool_call]
        mock_message.reasoning_content = None
        mock_message.reasoning = None
        
        mock_response.choices = [MagicMock(message=mock_message)]
        mock_response.usage.prompt_tokens = 100
        mock_response.usage.completion_tokens = 15
        
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
        
        with patch.object(app, 'get_openai_client', return_value=mock_client):
            res = await app.chat_completion("hello world", stream=False)
            
            # The result should be formatted as a JSON tool call block
            assert "list_directory" in res
            assert "/github2" in res
            assert "```json" in res

    @pytest.mark.anyio
    async def test_tool_prompt_subcommand(self, app):
        """Verifies that the /tool prompt escape command generates/shows the correct context and instructions"""
        app.generate_tool_context = MagicMock(return_value="=== AVAILABLE TOOLS ===\ntool: list_directory")
        with patch('builtins.print') as mock_print:
            res = await app.handle_escape_command("/tool prompt")
            assert res is True
            mock_print.assert_any_call("\n=== TOOL CONTEXT INJECTED INTO PROMPT ===")
            mock_print.assert_any_call("=== AVAILABLE TOOLS ===\ntool: list_directory")
            mock_print.assert_any_call("\n=== AGENTIC LOOP SYSTEM INSTRUCTIONS ===")

    @pytest.mark.anyio
    async def test_custom_agentic_instructions(self, app):
        """Verifies custom agentic instructions override the default and are printed/injected correctly"""
        app.agentic_instructions = "CUSTOM INSTRUCTIONS"
        app.generate_tool_context = MagicMock(return_value="=== AVAILABLE TOOLS ===\ntool: list_directory")
        with patch('builtins.print') as mock_print:
            res = await app.handle_escape_command("/tool prompt")
            assert res is True
            mock_print.assert_any_call("CUSTOM INSTRUCTIONS")

    @pytest.mark.anyio
    async def test_custom_tool_timeout(self, app):
        """Verifies custom tool timeout is read and applied to the dispatcher subprocess execution"""
        app.tool_timeout = 75
        with patch('subprocess.run') as mock_run, \
             patch('os.path.exists', return_value=True):
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = "success"
            
            res = app.dispatch_tool('{"tool": "list_directory"}')
            assert res == "success"
            mock_run.assert_called_once()
            _, kwargs = mock_run.call_args
            assert kwargs.get('timeout') == 75

    @pytest.mark.anyio
    async def test_run_command_output_behavior(self, app):
        """Verifies that running a command prints stdout on success, and prints error and exit code on failure"""
        # Test success output
        with patch('builtins.print') as mock_print:
            await app.handle_escape_command('/run "echo hello"')
            mock_print.assert_called_with("hello\n", end="")

        # Test failure output
        with patch('subprocess.run') as mock_run:
            mock_run.return_value.returncode = 5
            mock_run.return_value.stdout = "some stdout output"
            mock_run.return_value.stderr = "some error stderr"
            
            with patch('builtins.print') as mock_print:
                await app.handle_escape_command('/run "some_failing_command"')
                mock_print.assert_any_call("some error stderr", end="")
                mock_print.assert_any_call("Command exited with code 5")


