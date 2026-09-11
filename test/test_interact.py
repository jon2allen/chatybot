"""Tests for tools/interact_utils.py and commands/interact.py."""

import sys
import unittest
from unittest.mock import MagicMock, patch

from chatybot.tools.interact_utils import ask_user, _is_interactive, _in_script
from chatybot.commands.interact import _parse_ask_args


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_app(script_context: bool = False) -> MagicMock:
    app = MagicMock()
    app.script_context = script_context
    app.buffer_manager.set_script_var = MagicMock(return_value=True)
    return app


# ---------------------------------------------------------------------------
# _is_interactive / _in_script
# ---------------------------------------------------------------------------

class TestIsInteractive(unittest.TestCase):
    def test_script_context_blocks(self):
        app = _make_app(script_context=True)
        self.assertFalse(_is_interactive(app))

    def test_no_tty_blocks(self):
        app = _make_app(script_context=False)
        with patch("sys.stdin") as mock_stdin:
            mock_stdin.isatty.return_value = False
            self.assertFalse(_is_interactive(app))

    def test_interactive_when_tty_and_no_script(self):
        app = _make_app(script_context=False)
        with patch("sys.stdin") as mock_stdin:
            mock_stdin.isatty.return_value = True
            self.assertTrue(_is_interactive(app))

    def test_none_app_uses_stdin_only(self):
        with patch("sys.stdin") as mock_stdin:
            mock_stdin.isatty.return_value = True
            self.assertTrue(_is_interactive(None))


# ---------------------------------------------------------------------------
# ask_user — batch/script skipping
# ---------------------------------------------------------------------------

class TestAskUserSkip(unittest.TestCase):
    def test_skipped_in_script_context(self):
        app = _make_app(script_context=True)
        result = ask_user(prompt="Continue?", question_type="yesno", app=app)
        self.assertEqual(result["status"], "skipped")
        self.assertIn("script", result["reason"])

    def test_skipped_when_not_a_tty(self):
        app = _make_app(script_context=False)
        with patch("sys.stdin") as mock_stdin:
            mock_stdin.isatty.return_value = False
            result = ask_user(prompt="Continue?", question_type="yesno", app=app)
        self.assertEqual(result["status"], "skipped")
        self.assertIn("non-interactive", result["reason"])

    def test_no_set_script_var_when_skipped(self):
        app = _make_app(script_context=True)
        ask_user(prompt="Q?", target_variable="ANSWER", app=app)
        app.buffer_manager.set_script_var.assert_not_called()


# ---------------------------------------------------------------------------
# ask_user — success paths
# ---------------------------------------------------------------------------

class TestAskUserSuccess(unittest.TestCase):
    def _run_interactive(self, user_inputs, **kwargs):
        """Run ask_user with a fake TTY and simulated keyboard input."""
        app = _make_app(script_context=False)
        with patch("sys.stdin") as mock_stdin:
            mock_stdin.isatty.return_value = True
            with patch("builtins.input", side_effect=user_inputs):
                result = ask_user(app=app, **kwargs)
        return result, app

    def test_yesno_accepts_number(self):
        result, _ = self._run_interactive(
            ["1"], prompt="Continue?", question_type="yesno"
        )
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["answer"], "yes")

    def test_yesno_accepts_text(self):
        result, _ = self._run_interactive(
            ["no"], prompt="Continue?", question_type="yesno"
        )
        self.assertEqual(result["answer"], "no")

    def test_yesno_retries_bad_input(self):
        result, _ = self._run_interactive(
            ["maybe", "nope", "2"],  # third attempt is valid
            prompt="Continue?", question_type="yesno"
        )
        self.assertEqual(result["answer"], "no")

    def test_choice_by_number(self):
        result, _ = self._run_interactive(
            ["2"],
            prompt="Pick model:",
            choices=["gpt-4", "claude", "gemini"],
            question_type="choice",
        )
        self.assertEqual(result["answer"], "claude")

    def test_choice_by_text(self):
        result, _ = self._run_interactive(
            ["gemini"],
            prompt="Pick model:",
            choices=["gpt-4", "claude", "gemini"],
            question_type="choice",
        )
        self.assertEqual(result["answer"], "gemini")

    def test_free_text(self):
        result, _ = self._run_interactive(
            ["hello world"],
            prompt="Enter name:", question_type="text"
        )
        self.assertEqual(result["answer"], "hello world")

    def test_sets_target_variable(self):
        result, app = self._run_interactive(
            ["yes"],
            prompt="OK?", question_type="yesno", target_variable="MY_VAR"
        )
        self.assertEqual(result["answer"], "yes")
        self.assertEqual(result["target_variable"], "MY_VAR")
        self.assertEqual(result["reserved_variable"], "ASK_RESULT")
        # Should set both ASK_RESULT (reserved) and MY_VAR (target)
        app.buffer_manager.set_script_var.assert_any_call("ASK_RESULT", "yes", allow_protected=True)
        app.buffer_manager.set_script_var.assert_any_call("MY_VAR", "yes")

    def test_always_sets_reserved_ask_result_without_target_var(self):
        result, app = self._run_interactive(
            ["optionA"],
            prompt="Pick:", choices=["optionA", "optionB"], question_type="choice"
        )
        self.assertEqual(result["answer"], "optionA")
        self.assertIsNone(result["target_variable"])
        self.assertEqual(result["reserved_variable"], "ASK_RESULT")
        app.buffer_manager.set_script_var.assert_called_once_with("ASK_RESULT", "optionA", allow_protected=True)

    def test_eof_returns_error(self):
        app = _make_app(script_context=False)
        with patch("sys.stdin") as mock_stdin:
            mock_stdin.isatty.return_value = True
            with patch("builtins.input", side_effect=EOFError):
                result = ask_user(prompt="Q?", question_type="yesno", app=app)
        self.assertEqual(result["status"], "error")
        self.assertIn("interrupted", result["reason"])


# ---------------------------------------------------------------------------
# _parse_ask_args (argument parser for /ask command)
# ---------------------------------------------------------------------------

class TestParseAskArgs(unittest.TestCase):
    def test_simple_prompt_no_var(self):
        prompt, choices, var, qtype = _parse_ask_args('"Continue?"')
        self.assertEqual(prompt, "Continue?")
        self.assertIsNone(choices)
        self.assertIsNone(var)
        self.assertEqual(qtype, "text")

    def test_yesno_with_var(self):
        prompt, choices, var, qtype = _parse_ask_args('yesno "Overwrite?" -> OVERWRITE')
        self.assertEqual(prompt, "Overwrite?")
        self.assertIsNone(choices)
        self.assertEqual(var, "OVERWRITE")
        self.assertEqual(qtype, "yesno")

    def test_choice_with_options_and_var(self):
        prompt, choices, var, qtype = _parse_ask_args(
            'choice "Pick model:" gpt-4 claude gemini -> MODEL'
        )
        self.assertEqual(prompt, "Pick model:")
        self.assertEqual(choices, ["gpt-4", "claude", "gemini"])
        self.assertEqual(var, "MODEL")
        self.assertEqual(qtype, "choice")

    def test_implicit_choice_from_extra_tokens(self):
        prompt, choices, var, qtype = _parse_ask_args('"Pick one:" alpha beta -> RESULT')
        self.assertEqual(choices, ["alpha", "beta"])
        self.assertEqual(var, "RESULT")
        self.assertEqual(qtype, "choice")

    def test_prompt_only_no_arrow(self):
        prompt, choices, var, qtype = _parse_ask_args('"What is your name?"')
        self.assertEqual(prompt, "What is your name?")
        self.assertIsNone(var)

    def test_choice_keyword_with_no_options_falls_back_to_text(self):
        prompt, choices, var, qtype = _parse_ask_args('choice "Enter value:" -> X')
        self.assertIsNone(choices)
        self.assertEqual(qtype, "text")

    def test_empty_args(self):
        prompt, choices, var, qtype = _parse_ask_args("")
        self.assertEqual(prompt, "")
        self.assertIsNone(choices)
        self.assertIsNone(var)


# ---------------------------------------------------------------------------
# cmd_ask command handler
# ---------------------------------------------------------------------------

class TestCmdAsk(unittest.IsolatedAsyncioTestCase):
    async def test_cmd_ask_with_target_var(self):
        from chatybot.commands.interact import cmd_ask
        from chatybot.commands.context import CommandContext
        import io
        from contextlib import redirect_stdout

        app = _make_app(script_context=False)
        ctx = CommandContext(
            buffer_manager=app.buffer_manager,
            config_manager=MagicMock(),
            i18n=MagicMock(),
            session_store=None,
            app=app,
        )
        f = io.StringIO()
        with patch("sys.stdin") as mock_stdin:
            mock_stdin.isatty.return_value = True
            with patch("builtins.input", return_value="yes"):
                with redirect_stdout(f):
                    result = await cmd_ask(ctx, ["/ask", 'yesno "OK?" -> MY_FLAG'], '/ask yesno "OK?" -> MY_FLAG')

        from chatybot.commands.registry import CommandAction
        output = f.getvalue()
        self.assertEqual(result.action, CommandAction.HANDLED)
        self.assertIn("[ask] 'yes' -> $MY_FLAG (also in $ASK_RESULT)", output)

    async def test_cmd_ask_without_target_var(self):
        from chatybot.commands.interact import cmd_ask
        from chatybot.commands.context import CommandContext
        from chatybot.commands.registry import CommandAction
        import io
        from contextlib import redirect_stdout

        app = _make_app(script_context=False)
        ctx = CommandContext(
            buffer_manager=app.buffer_manager,
            config_manager=MagicMock(),
            i18n=MagicMock(),
            session_store=None,
            app=app,
        )
        f = io.StringIO()
        with patch("sys.stdin") as mock_stdin:
            mock_stdin.isatty.return_value = True
            with patch("builtins.input", return_value="hello"):
                with redirect_stdout(f):
                    result = await cmd_ask(ctx, ["/ask", '"Enter name:"'], '/ask "Enter name:"')

        output = f.getvalue()
        self.assertEqual(result.action, CommandAction.HANDLED)
        self.assertIn("[ask] 'hello' -> $ASK_RESULT", output)


# ---------------------------------------------------------------------------
# Help system registration
# ---------------------------------------------------------------------------

class TestAskHelp(unittest.TestCase):
    def test_help_system_has_ask(self):
        from chatybot.chaty_help import get_help_system, reset_help_system
        reset_help_system()
        hs = get_help_system()
        cmd = hs.get_command("/ask")
        self.assertIsNotNone(cmd)
        self.assertEqual(cmd.name, "/ask")
        self.assertIn("ASK_RESULT", cmd.long_desc)
        self.assertEqual(cmd.category, "interact")

    def test_help_system_text_for_ask(self):
        from chatybot.chaty_help import get_help_system, reset_help_system
        reset_help_system()
        hs = get_help_system()
        help_text = hs.get_help_text("/ask")
        self.assertIn("/ask", help_text)
        self.assertIn("ASK_RESULT", help_text)


# ---------------------------------------------------------------------------
# Dispatch ask_user in ChatybotApp
# ---------------------------------------------------------------------------

class TestDispatchAskUser(unittest.IsolatedAsyncioTestCase):
    async def test_dispatch_unwraps_nested_parameters(self):
        from chatybot.chatybot_app import ChatybotApp
        import json
        app = ChatybotApp()
        payload = json.dumps({
            "tool": "ask_user",
            "arguments": {
                "parameters": {
                    "prompt": "Which option?",
                    "question_type": "choice",
                    "choices": ["Alpha", "Beta"]
                }
            }
        })
        with patch("sys.stdin") as mock_stdin:
            mock_stdin.isatty.return_value = True
            with patch("builtins.input", return_value="1"):
                result_json = await app.dispatch_tool(payload)

        data = json.loads(result_json)
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["result"]["answer"], "Alpha")


if __name__ == "__main__":
    unittest.main()


