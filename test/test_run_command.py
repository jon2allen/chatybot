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
        app.buffer_manager.set_script_var('LAST_COMPLETION', json.dumps(invocation), allow_protected=True)
        
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
        
        # Test safe command execution (default shell=True)
        res = run_command("echo hello_world")
        assert "hello_world" in res
        
        # Test with shell=False explicitly
        res_no_shell = run_command("echo hello_world_no_shell", shell=False)
        assert "hello_world_no_shell" in res_no_shell

        # Test chaining with shell=True (should succeed)
        res_chained = run_command("echo hello && echo world")
        assert "hello" in res_chained and "world" in res_chained

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
        
        # Default with no args -> app.max_turns
        await app.handle_escape_command("/tool loop")
        app.execute_tool_loop.assert_called_with(app.max_turns)
        
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
            
            res = await app.dispatch_tool('{"tool": "list_directory"}')
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

    @pytest.mark.anyio
    async def test_execute_script_tool_run(self, app):
        """Verifies that running a ChatDSL script containing /run and /tool works correctly"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.chatdsl', delete=False) as f:
            f.write(
                "set TEST_VAR = \"Hello World\"\n"
                "/echo ${TEST_VAR}\n"
                "/run echo \"Executed from ChatDSL\"\n"
                "if ${RUN_EXIT_CODE} == 0 then /echo Run command succeeded!\n"
                "/tool on\n"
                "/tool off\n"
            )
            script_path = f.name

        try:
            with patch('subprocess.run') as mock_run, \
                 patch('builtins.print') as mock_print:
                mock_run.return_value.returncode = 0
                mock_run.return_value.stdout = "Executed from ChatDSL\n"
                mock_run.return_value.stderr = ""
                
                # Mock generate_tool_context to return tool headers
                app.generate_tool_context = MagicMock(return_value="tool_context")
                
                await app.execute_script(script_path)
                
                # Verify that tool mode was toggled on and off
                assert app.tool_mode is False  # Because "/tool off" ran last
        finally:
            if os.path.exists(script_path):
                os.remove(script_path)

    @pytest.mark.anyio
    async def test_tool_auto_mode(self, app):
        """Verifies /tool auto on/off command toggling, state verification, and auto-triggering behavior"""
        from src.chatybot.chatybot_app import PatternMatcher
        app.matcher = PatternMatcher(["/tool", "/run"])
        
        # Test default state
        assert app.tool_auto is False

        # Mock generate_tool_context to return tool headers
        app.generate_tool_context = MagicMock(return_value="tool_context")

        # Test command enabling
        await app.handle_escape_command("/tool auto on")
        assert app.tool_auto is True
        assert app.tool_mode is True
        assert app.buffer_manager.get_script_var('TOOL_CONTEXT') == "tool_context"

        # Test command disabling
        await app.handle_escape_command("/tool auto off")
        assert app.tool_auto is False

        # Test interactive /tool auto state query printout
        with patch('builtins.print') as mock_print:
            await app.handle_escape_command("/tool auto")
            mock_print.assert_any_call("Tool auto mode is currently disabled")

        # Re-enable tool auto
        await app.handle_escape_command("/tool auto on")
        assert app.tool_auto is True

        # Mock execute_tool_loop to track execution
        app.execute_tool_loop = AsyncMock()

        # Call chat_completion but mock it returning a tool call
        tool_call_json = '```json\n{"tool": "list_directory", "arguments": {"path": "."}}\n```'
        
        # When calling chat completion with tool auto on and a tool call in response:
        with patch.object(app, 'extract_tool_calls', return_value=[{"tool": "list_directory", "arguments": {"path": "."}}]):
            mock_client = MagicMock()
            mock_message = MagicMock()
            mock_message.content = tool_call_json
            mock_message.tool_calls = None
            mock_choice = MagicMock()
            mock_choice.message = mock_message
            mock_response = MagicMock()
            mock_response.choices = [mock_choice]
            mock_response.usage = None
            
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
            app.get_openai_client = MagicMock(return_value=mock_client)
            
            await app.chat_completion("some query", stream=False)
            
            # Since auto-loop is triggered, execute_tool_loop should have been called!
            app.execute_tool_loop.assert_called_once_with(max_turns=app.max_turns)

    @pytest.mark.anyio
    async def test_tool_auto_mode_streaming(self, app):
        """Verifies tool auto-triggering works correctly when response is streamed with native tool_calls chunks"""
        from src.chatybot.chatybot_app import PatternMatcher
        app.matcher = PatternMatcher(["/tool", "/run"])
        
        # Enable tool auto mode
        await app.handle_escape_command("/tool auto on")
        assert app.tool_auto is True

        # Mock execute_tool_loop to track execution
        app.execute_tool_loop = AsyncMock()

        # Simulate streaming chunk responses containing tool_calls deltas
        class MockChoiceDeltaFunction:
            def __init__(self, name=None, arguments=None):
                self.name = name
                self.arguments = arguments

        class MockChoiceDeltaToolCall:
            def __init__(self, index, id=None, function=None):
                self.index = index
                self.id = id
                self.function = function

        class MockChoiceDelta:
            def __init__(self, content=None, tool_calls=None):
                self.content = content
                self.tool_calls = tool_calls

        class MockChoice:
            def __init__(self, delta):
                self.delta = delta

        class MockChunk:
            def __init__(self, choices):
                self.choices = choices

        chunk1 = MockChunk([MockChoice(MockChoiceDelta(
            tool_calls=[MockChoiceDeltaToolCall(index=0, id="call_1", function=MockChoiceDeltaFunction(name="list_directory"))]
        ))])
        chunk2 = MockChunk([MockChoice(MockChoiceDelta(
            tool_calls=[MockChoiceDeltaToolCall(index=0, function=MockChoiceDeltaFunction(arguments='{"path"'))]
        ))])
        chunk3 = MockChunk([MockChoice(MockChoiceDelta(
            tool_calls=[MockChoiceDeltaToolCall(index=0, function=MockChoiceDeltaFunction(arguments=': "."}'))]
        ))])

        async def mock_stream_generator():
            yield chunk1
            yield chunk2
            yield chunk3

        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_stream_generator())
        app.get_openai_client = MagicMock(return_value=mock_client)

        with patch.object(app, 'extract_tool_calls', return_value=[{"tool": "list_directory", "arguments": {"path": "."}}]):
            await app.chat_completion("some query", stream=True)
            
            # Since auto-loop is triggered by the reconstructed tool call JSON, execute_tool_loop should be called!
            app.execute_tool_loop.assert_called_once_with(max_turns=app.max_turns)

    def test_cli_option_script(self):
        """Verifies that the --script option initializes the app, executes the script, and exits"""
        from src.chatybot.chatybot_app import run
        
        with patch('sys.argv', ['chatybot', '--script', 'my_script.chatdsl']), \
             patch('src.chatybot.chatybot_app.ChatybotApp.initialize') as mock_init, \
             patch('src.chatybot.chatybot_app.ChatybotApp.execute_script', new_callable=AsyncMock) as mock_execute, \
             patch('src.chatybot.chatybot_app.ChatybotApp.run') as mock_run_loop, \
             patch('sys.exit', side_effect=SystemExit) as mock_exit:
             
            with pytest.raises(SystemExit):
                run()
            
            mock_init.assert_called_once()
            mock_execute.assert_called_once_with('my_script.chatdsl')
            mock_run_loop.assert_not_called()
            mock_exit.assert_called_once_with(0)

    def test_cli_option_run_query(self):
        """Verifies that the --run option with a normal query runs chat_completion and exits"""
        from src.chatybot.chatybot_app import run
        
        with patch('sys.argv', ['chatybot', '--run', 'what is python']), \
             patch('src.chatybot.chatybot_app.ChatybotApp.initialize') as mock_init, \
             patch('src.chatybot.chatybot_app.ChatybotApp.chat_completion', new_callable=AsyncMock) as mock_chat, \
             patch('src.chatybot.chatybot_app.ChatybotApp.handle_escape_command', new_callable=AsyncMock) as mock_escape, \
             patch('src.chatybot.chatybot_app.ChatybotApp.run') as mock_run_loop, \
             patch('sys.exit', side_effect=SystemExit) as mock_exit:
             
            with pytest.raises(SystemExit):
                run()
            
            mock_init.assert_called_once()
            mock_chat.assert_called_once_with('what is python', stream=False)
            mock_escape.assert_not_called()
            mock_run_loop.assert_not_called()
            mock_exit.assert_called_once_with(0)

    def test_cli_option_run_escape(self):
        """Verifies that the --run option with an escape command executes handle_escape_command and exits"""
        from src.chatybot.chatybot_app import run
        
        with patch('sys.argv', ['chatybot', '--run', '/tool auto on']), \
             patch('src.chatybot.chatybot_app.ChatybotApp.initialize') as mock_init, \
             patch('src.chatybot.chatybot_app.ChatybotApp.chat_completion', new_callable=AsyncMock) as mock_chat, \
             patch('src.chatybot.chatybot_app.ChatybotApp.handle_escape_command', new_callable=AsyncMock) as mock_escape, \
             patch('src.chatybot.chatybot_app.ChatybotApp.run') as mock_run_loop, \
             patch('sys.exit', side_effect=SystemExit) as mock_exit:
             
            with pytest.raises(SystemExit):
                run()
            
            mock_init.assert_called_once()
            mock_escape.assert_called_once_with('/tool auto on')
            mock_chat.assert_not_called()
            mock_run_loop.assert_not_called()
            mock_exit.assert_called_once_with(0)

    def test_cli_option_run_chain(self):
        """Verifies that the --run option handles chained escape and query commands correctly"""
        from src.chatybot.chatybot_app import run
        
        with patch('sys.argv', ['chatybot', '--run', '/model devstral_1; list 5 cities']), \
             patch('src.chatybot.chatybot_app.ChatybotApp.initialize') as mock_init, \
             patch('src.chatybot.chatybot_app.ChatybotApp.chat_completion', new_callable=AsyncMock) as mock_chat, \
             patch('src.chatybot.chatybot_app.ChatybotApp.handle_escape_command', new_callable=AsyncMock) as mock_escape, \
             patch('src.chatybot.chatybot_app.ChatybotApp.run') as mock_run_loop, \
             patch('sys.exit', side_effect=SystemExit) as mock_exit:
             
            with pytest.raises(SystemExit):
                run()
            
            mock_init.assert_called_once()
            mock_escape.assert_called_once_with('/model devstral_1')
            mock_chat.assert_called_once_with('list 5 cities', stream=False)
            mock_run_loop.assert_not_called()
            mock_exit.assert_called_once_with(0)

    def test_extract_tool_calls_multiline_with_comments(self, app):
        """Verifies that extract_tool_calls handles multi-line JSON values containing comment characters within quotes correctly"""
        raw_completion = (
            '```json\n'
            '{\n'
            '  "tool": "run_command",\n'
            '  "arguments": {\n'
            '    "command": "cat > init_mitigation.md << \'EOF\'\\n# Database Initialization Mitigation Strategy\\n\\n## Current State Analysis\\nEOF"\n'
            '  }\n'
            '}\n'
            '```'
        )
        tool_calls = app.extract_tool_calls(raw_completion)
        assert len(tool_calls) == 1
        assert tool_calls[0]["tool"] == "run_command"
        assert "# Database" in tool_calls[0]["arguments"]["command"]

    def test_extract_tool_calls_unbalanced_braces_repair(self, app):
        """Verifies that extract_tool_calls correctly repairs and extracts unbalanced JSON blocks with missing closing quotes/braces at the end of completions"""
        # Case 1: missing one closing brace at the end of the JSON object
        raw_completion_1 = (
            '```json\n'
            '{\n'
            '  "tool": "run_command",\n'
            '  "arguments": {\n'
            '    "command": "cat > test.txt\\nhello"\n'
            '  }\n'
            '}'
        )
        tool_calls_1 = app.extract_tool_calls(raw_completion_1)
        assert len(tool_calls_1) == 1
        assert tool_calls_1[0]["tool"] == "run_command"
        assert tool_calls_1[0]["arguments"]["command"] == "cat > test.txt\nhello"

        # Case 2: missing closing quote AND two closing braces at the end
        raw_completion_2 = (
            '```json\n'
            '{\n'
            '  "tool": "run_command",\n'
            '  "arguments": {\n'
            '    "command": "cat > test.txt\\nhello'
        )
        tool_calls_2 = app.extract_tool_calls(raw_completion_2)
        assert len(tool_calls_2) == 1
        assert tool_calls_2[0]["tool"] == "run_command"
        assert tool_calls_2[0]["arguments"]["command"] == "cat > test.txt\nhello"

        # Case 3: missing closing brace before markdown code fence backticks
        raw_completion_3 = (
            '```json\n'
            '{\n'
            '  "tool": "run_command",\n'
            '  "arguments": {\n'
            '    "command": "git log --oneline --since=\\"24 hours ago\\" --name-only --pretty=format:\\"%h %s\\" | head -50"\n'
            '  }\n'
            '```'
        )
        tool_calls_3 = app.extract_tool_calls(raw_completion_3)
        assert len(tool_calls_3) == 1
        assert tool_calls_3[0]["tool"] == "run_command"
        assert "git log" in tool_calls_3[0]["arguments"]["command"]

    def test_extract_tool_calls_raw_newlines_in_quotes(self, app):
        """Verifies that extract_tool_calls correctly parses JSON with raw/unescaped newlines inside quote literals"""
        raw_completion = (
            '{\n'
            '  "tool": "run_command",\n'
            '  "arguments": {\n'
            '    "command": "cat << \'EOF\' > test.txt\n'
            'line 1\n'
            'line 2\n'
            'EOF"\n'
            '  }\n'
            '}'
        )
        tool_calls = app.extract_tool_calls(raw_completion)
        assert len(tool_calls) == 1
        assert tool_calls[0]["tool"] == "run_command"
        assert "line 1\nline 2" in tool_calls[0]["arguments"]["command"]

    @pytest.mark.anyio
    async def test_write_file_tool(self, app):
        """Verifies that the write_file tool writes and appends contents correctly"""
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = os.path.join(tmpdir, "test_write.txt")
            
            # Test write
            invocation_write = {
                "tool": "write_file",
                "arguments": {
                    "path": filepath,
                    "content": "hello world\n"
                }
            }
            res_write = await app.dispatch_tool(json.dumps(invocation_write))
            assert "success" in res_write
            
            with open(filepath, "r") as f:
                content = f.read()
            assert content == "hello world\n"
            
            # Test append
            invocation_append = {
                "tool": "write_file",
                "arguments": {
                    "path": filepath,
                    "content": "additional text",
                    "append": True
                }
            }
            res_append = await app.dispatch_tool(json.dumps(invocation_append))
            assert "success" in res_append
            
            with open(filepath, "r") as f:
                content = f.read()
            assert content == "hello world\nadditional text"

    @pytest.mark.anyio
    async def test_replace_file_content_tool(self, app):
        """Verifies that the replace_file_content tool replaces content correctly"""
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = os.path.join(tmpdir, "test_replace.txt")
            with open(filepath, "w") as f:
                f.write("hello world\nhello world\n")
            
            # Test replace
            invocation_replace = {
                "tool": "replace_file_content",
                "arguments": {
                    "path": filepath,
                    "target": "world",
                    "replacement": "there"
                }
            }
            res_replace = await app.dispatch_tool(json.dumps(invocation_replace))
            assert "Success" in res_replace
            assert "2 occurrence" in res_replace
            
            with open(filepath, "r") as f:
                content = f.read()
            assert content == "hello there\nhello there\n"

    @pytest.mark.anyio
    async def test_tool_loop_agentic_loop_variable(self, app):
        """Verifies that the AGENTIC_LOOP script variable accumulates tool records during tool loop runs"""
        app.chat_history = [("Find files", '{"tool": "list_directory", "arguments": {"path": "."}}')]
        app.chat_completion = AsyncMock(return_value="Here is the final response.")
        
        with patch('subprocess.run') as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = '{"status": "success", "result": ["file1.txt"]}'
            mock_run.return_value.stderr = ''
            
            await app.execute_tool_loop(max_turns=3)
            
            agentic_loop = app.buffer_manager.get_script_var('AGENTIC_LOOP')
            assert isinstance(agentic_loop, list)
            assert len(agentic_loop) == 1
            record = agentic_loop[0]
            assert record["turn"] == 1
            assert record["tool"] == "list_directory"
            assert record["arguments"] == {"path": "."}
            assert "success" in record["result"]
            assert record["exit_code"] == 0
            assert record["status"] == "success"

    @pytest.mark.anyio
    async def test_tool_loop_logging(self, app):
        """Verifies that the tool execution steps and final response are logged if logging is active"""
        app.chat_history = [("Find files", '{"tool": "list_directory", "arguments": {"path": "."}}')]
        app.chat_completion = AsyncMock(return_value="Here is the final response.")
        
        # Activate logging
        app.logging_manager.logging_active = True
        app.logging_manager.log_message = MagicMock()
        
        with patch('subprocess.run') as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = '{"status": "success", "result": ["file1.txt"]}'
            mock_run.return_value.stderr = ''
            
            await app.execute_tool_loop(max_turns=3)
            
            # Verify log_message was called for the intermediate step and the final response
            assert app.logging_manager.log_message.call_count >= 2
            
            # Find the calls for intermediate tool executions and final responses
            log_calls = [call[0][0] for call in app.logging_manager.log_message.call_args_list]
            
            # Check intermediate step
            assert any("Tool Loop Execution:" in call and "list_directory" in call for call in log_calls)
            # Check final response log
            assert any("Assistant (Agentic Loop Final):" in call and "Here is the final response." in call for call in log_calls)

    @pytest.mark.anyio
    async def test_tool_enable_disable_list(self, app):
        """Verifies that the /tool list, enable, and disable commands modify the tool_overrides dict and context appropriately."""
        # Setup mock configs
        mock_config = {
            "tools": {
                "list_directory": {
                    "enabled": True,
                    "description": "List contents of a directory"
                },
                "write_file": {
                    "enabled": False,
                    "description": "Write a file"
                }
            }
        }
        app._load_tools_config = MagicMock(return_value=mock_config)
        
        # 1. Test /tool list (checks that it prints and doesn't fail)
        import sys
        from io import StringIO
        
        captured_output = StringIO()
        sys.stdout = captured_output
        try:
            res = await app.handle_escape_command("/tool list")
            assert res is True
        finally:
            sys.stdout = sys.__stdout__
            
        output = captured_output.getvalue()
        assert "list_directory" in output
        assert "write_file" in output
        assert "[ON] " in output
        assert "[OFF]" in output
        
        # 2. Test /tool disable list_directory
        res = await app.handle_escape_command("/tool disable list_directory")
        assert res is True
        assert app.tool_overrides["list_directory"] is False
        
        # 3. Test /tool enable write_file
        res = await app.handle_escape_command("/tool enable write_file")
        assert res is True
        assert app.tool_overrides["write_file"] is True
        
        # 4. Test case-insensitivity on enable
        res = await app.handle_escape_command("/tool enable WRITE_FILE")
        assert res is True
        assert app.tool_overrides["write_file"] is True
        
        # 5. Test error on non-existent tool
        captured_output = StringIO()
        sys.stdout = captured_output
        try:
            res = await app.handle_escape_command("/tool enable fake_tool")
            assert res is True
        finally:
            sys.stdout = sys.__stdout__
        assert "Error: No tools matched pattern 'fake_tool'" in captured_output.getvalue()
        
        # 6. Test enable/disable all
        res = await app.handle_escape_command("/tool disable all")
        assert res is True
        assert all(v is False for v in app.tool_overrides.values())
        
        res = await app.handle_escape_command("/tool enable all")
        assert res is True
        assert all(v is True for v in app.tool_overrides.values())
        
        # 7. Test context generation respects overrides
        app.tool_mode = True
        context = app.generate_tool_context()
        # Since all tools are enabled, both should be in context
        assert "list_directory" in context
        assert "write_file" in context
        
        app.tool_overrides["write_file"] = False
        context_after_disable = app.generate_tool_context()
        assert "list_directory" in context_after_disable
        assert "write_file" not in context_after_disable

    @pytest.mark.anyio
    async def test_tool_glob_matching(self, app):
        """Verifies that glob-style patterns can list, enable, and disable tools."""
        # Setup mock configs with local and MCP tools
        mock_config = {
            "tools": {
                "list_directory": {
                    "enabled": True,
                    "description": "List contents of a directory"
                },
                "write_file": {
                    "enabled": True,
                    "description": "Write a file"
                },
                "read_file": {
                    "enabled": True,
                    "description": "Read a file"
                }
            }
        }
        app._load_tools_config = MagicMock(return_value=mock_config)
        
        # Setup mock MCP client manager with cached schemas
        mock_mcp = MagicMock()
        class DummyTool:
            def __init__(self, name, description=""):
                self.name = name
                self.description = description
                self.inputSchema = {"properties": {}, "required": []}
                
        mock_mcp.cached_schemas = {
            "gitserver": [
                DummyTool("clone"),
                DummyTool("commit")
            ]
        }
        app.mcp_manager = mock_mcp

        # Initialize overrides
        app.tool_overrides = {}

        # 1. Test /tool list with glob filter
        import sys
        from io import StringIO
        
        captured_output = StringIO()
        sys.stdout = captured_output
        try:
            res = await app.handle_escape_command("/tool list *file*")
            assert res is True
        finally:
            sys.stdout = sys.__stdout__
            
        output = captured_output.getvalue()
        assert "write_file" in output
        assert "read_file" in output
        assert "list_directory" not in output
        assert "gitserver" not in output

        # 2. Test /tool list with MCP matching glob
        captured_output = StringIO()
        sys.stdout = captured_output
        try:
            res = await app.handle_escape_command("/tool list mcp__git*")
            assert res is True
        finally:
            sys.stdout = sys.__stdout__
            
        output = captured_output.getvalue()
        assert "mcp__gitserver__clone" in output
        assert "mcp__gitserver__commit" in output
        assert "write_file" not in output

        # 3. Test /tool disable using glob pattern (e.g. *file*)
        res = await app.handle_escape_command("/tool disable *file*")
        assert res is True
        assert app.tool_overrides["write_file"] is False
        assert app.tool_overrides["read_file"] is False
        # list_directory and MCP tools should remain untouched or defaulted (not disabled via override)
        assert "list_directory" not in app.tool_overrides

        # 4. Test /tool disable all mcp tools using mcp* glob
        res = await app.handle_escape_command("/tool disable mcp*")
        assert res is True
        assert app.tool_overrides["mcp__gitserver__clone"] is False
        assert app.tool_overrides["mcp__gitserver__commit"] is False
        
        # 5. Test /tool enable using glob pattern
        res = await app.handle_escape_command("/tool enable *")
        assert res is True
        assert app.tool_overrides["list_directory"] is True
        assert app.tool_overrides["write_file"] is True
        assert app.tool_overrides["read_file"] is True
        assert app.tool_overrides["mcp__gitserver__clone"] is True
        assert app.tool_overrides["mcp__gitserver__commit"] is True

        # 6. Test when no tools match a glob
        captured_output = StringIO()
        sys.stdout = captured_output
        try:
            res = await app.handle_escape_command("/tool disable non_existent*")
            assert res is True
        finally:
            sys.stdout = sys.__stdout__
        assert "Error: No tools matched pattern 'non_existent*'" in captured_output.getvalue()

        # 7. Test /tool list detail
        captured_output = StringIO()
        sys.stdout = captured_output
        try:
            res = await app.handle_escape_command("/tool list detail *directory*")
            assert res is True
        finally:
            sys.stdout = sys.__stdout__
            
        output = captured_output.getvalue()
        assert "**list_directory**" in output
        assert "Description: List contents of a directory" in output
        assert "write_file" not in output

    def test_gemma4_and_native_tool_call_extraction(self, app):
        """Verifies parsing of Gemma 4 native tool call tags, FunctionGemma tags, unquoted keys, and Python dict structures"""
        # Gemma 4 format with unquoted keys and <|tool_call> tags
        text1 = '<|tool_call>call:run_command{command: "git status --porcelain"}<tool_call|>'
        calls1 = app.extract_tool_calls(text1)
        assert len(calls1) == 1
        assert calls1[0]["tool"] == "run_command"
        assert calls1[0]["arguments"] == {"command": "git status --porcelain"}

        # Gemma 4 format with <|tool_call|> closing tag
        text2 = '<|tool_call|>call:list_directory{path: "."}<|tool_call|>'
        calls2 = app.extract_tool_calls(text2)
        assert len(calls2) == 1
        assert calls2[0]["tool"] == "list_directory"
        assert calls2[0]["arguments"] == {"path": "."}

        # FunctionGemma format with multiple args and Python booleans/None
        text3 = '<start_function_call>call:find_files{path: ".", details: True, search_term: None}<end_function_call>'
        calls3 = app.extract_tool_calls(text3)
        assert len(calls3) == 1
        assert calls3[0]["tool"] == "find_files"
        assert calls3[0]["arguments"] == {"path": ".", "details": True, "search_term": None}

        # Function call with parentheses
        text4 = 'call:change_dir({path: "/home/user"})'
        calls4 = app.extract_tool_calls(text4)
        assert len(calls4) == 1
        assert calls4[0]["tool"] == "change_dir"
        assert calls4[0]["arguments"] == {"path": "/home/user"}

    def test_xml_tool_call_extraction(self, app):
        """Verifies parsing of XML-style <tool_call><function=...><parameter=...> syntax into canonical tool call dicts"""
        raw_xml = '''
Assistant: The user wants to find the average size of chatdsl files.
<tool_call>
<function=find_files>
<parameter=pattern>
*.chatdsl
</parameter>
<parameter=details>
true
</parameter>
</function>
</tool_call>
'''
        calls = app.extract_tool_calls(raw_xml)
        assert len(calls) == 1
        assert calls[0]["tool"] == "find_files"
        assert calls[0]["arguments"] == {"pattern": "*.chatdsl", "details": True}

    @pytest.mark.anyio
    async def test_tool_translate_command(self, app):
        """Verifies /tool translate command converts XML tool calls into canonical JSON string"""
        raw_xml = '''
<tool_call>
<function=find_files>
<parameter=pattern>*.chatdsl</parameter>
<parameter=details>true</parameter>
</function>
</tool_call>
'''
        app.buffer_manager.set_script_var('LAST_COMPLETION', raw_xml)
        import io, sys
        captured = io.StringIO()
        sys.stdout = captured
        try:
            res = await app.handle_escape_command("/tool translate")
            assert res is True
        finally:
            sys.stdout = sys.__stdout__
        
        output = captured.getvalue()
        assert '"tool": "find_files"' in output
        assert '"pattern": "*.chatdsl"' in output
        assert '"details": true' in output

    def test_payload_limits_string_enforcement(self):
        """Verifies soft warning and hard truncation on run_command string outputs."""
        from src.chatybot.tools.file_utils import enforce_string_payload_limits, SOFT_WARNING_BYTES, HARD_TRUNCATE_BYTES
        
        # 1. Normal size (< 30 KB)
        normal_str = "line\n" * 100
        res_normal = enforce_string_payload_limits(normal_str, "run_command")
        assert res_normal == normal_str

        # 2. Soft warning (30 KB - 50 KB)
        soft_str = "a" * (35 * 1024)
        res_soft = enforce_string_payload_limits(soft_str, "run_command")
        assert "[NOTE: Tool 'run_command' output is large" in res_soft

        # 3. Hard truncation (> 50 KB)
        hard_str = "".join([f"Line {i}: output details here\n" for i in range(1000)])  # ~30 KB - let's make it 60 KB
        hard_str_large = "".join([f"Line {i:04d}: large payload data text block content here\n" for i in range(1500)]) # ~75 KB
        res_hard = enforce_string_payload_limits(hard_str_large, "run_command")
        assert "[WARNING: Tool 'run_command' output exceeded hard limit" in res_hard
        assert "Line 0000:" in res_hard  # Head preserved
        assert "Line 1499:" in res_hard  # Tail preserved

    def test_payload_limits_list_enforcement(self):
        """Verifies list truncation and warnings on find_files and grep_search."""
        from src.chatybot.tools.file_utils import enforce_list_payload_limits
        
        # 1. Normal list
        small_list = [{"file": f"test_{i}.py"} for i in range(10)]
        res_small = enforce_list_payload_limits(small_list, "find_files", max_items=100)
        assert len(res_small) == 10

        # 2. Hard truncation (> 100 items)
        large_list = [{"file": f"test_{i}.py", "size": 1024} for i in range(150)]
        res_large = enforce_list_payload_limits(large_list, "find_files", max_items=100)
        assert len(res_large) == 101  # 100 items + 1 truncation warning note
        assert "warning" in res_large[-1]
        assert "50 additional results omitted" in res_large[-1]["warning"]









