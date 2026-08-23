#!/usr/bin/env python3
"""
Unit tests for command verb validation in ChatybotApp.chat_completion
"""

import pytest
import asyncio
from unittest.mock import MagicMock, patch
from src.chatybot.chatybot_app import ChatybotApp


class TestCommandVerbValidation:
    """Test suite for command verb validation logic"""

    @pytest.fixture
    def app(self):
        """Create a ChatybotApp instance with clean state and mock dependencies"""
        with patch('src.chatybot.chatybot_app.readline'), \
             patch.object(ChatybotApp, 'load_input_history'), \
             patch('src.chatybot.chatybot_app.ConfigManager') as mock_cfg:
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
            cfg_instance.system_message = ""
            
            application = ChatybotApp()
            application.config_manager = cfg_instance
            application.buffer_manager = MagicMock()
            application.buffer_manager.replace_placeholders.side_effect = lambda p: (p, [])
            application.buffer_manager.prompt_buffer = ""
            application.buffer_manager.file_buffer = ""
            
            mock_client = MagicMock()
            mock_completion = MagicMock()
            mock_choice = MagicMock()
            mock_choice.message.content = "OK response"
            mock_choice.message.reasoning_content = None
            mock_completion.choices = [mock_choice]
            
            async def mock_create(*args, **kwargs):
                return mock_completion
                
            mock_client.chat.completions.create = mock_create
            
            async def mock_retrieve(*args, **kwargs):
                return MagicMock()
            mock_client.models.retrieve = mock_retrieve
            
            application.get_openai_client = MagicMock(return_value=mock_client)
            yield application

    def test_command_verb_unquoted_at_start(self, app, capsys):
        """Test that unquoted command verbs at the start of prompt return error."""
        unquoted_prompts = [
            "help",
            "help me write python code",
            "model gpt4",
            "file test.txt",
            "run ls -la",
            "save output.txt",
            "debug payload",
            "thoughtstyle gemma4",
            "exit",
            "loadimage1 cat.jpg",
            "   help me",
            "HELP ME",
            "help: explain this"
        ]
        for prompt in unquoted_prompts:
            result = asyncio.run(app.chat_completion(prompt))
            assert result == "", f"Expected empty result for unquoted prompt: {prompt}"
            captured = capsys.readouterr()
            assert "Error command verb at beginning:" in captured.out

    def test_command_verb_quoted_at_start(self, app, capsys):
        """Test that quoted command verbs or prompts starting with quotes pass validation."""
        quoted_prompts = [
            '"help"',
            "'help'",
            '"help" me write code',
            "'help' me write code",
            '"help me write python code"',
            "'help me write python code'",
            '"model" is a concept',
            '  "help me"',
            '“help”',
            '‘help’'
        ]
        for prompt in quoted_prompts:
            result = asyncio.run(app.chat_completion(prompt))
            assert result == "OK response", f"Expected success for quoted prompt: {prompt}"
            captured = capsys.readouterr()
            assert "Error command verb at beginning:" not in captured.out

    def test_command_verb_as_non_first_word(self, app, capsys):
        """Test that command verbs appearing later in the prompt (not as first word) are allowed."""
        normal_prompts = [
            "I need help with python",
            "Please run this command",
            "What model is this?",
            "Show the file contents",
            "Can you check the model performance?"
        ]
        for prompt in normal_prompts:
            result = asyncio.run(app.chat_completion(prompt))
            assert result == "OK response", f"Expected success for normal prompt: {prompt}"
            captured = capsys.readouterr()
            assert "Error command verb at beginning:" not in captured.out

    def test_command_verb_substring_words(self, app, capsys):
        """Test that words starting with command verb substrings (like helper, modeling) are allowed."""
        substring_prompts = [
            "helper function for math",
            "modeling a new architecture",
            "files in current folder"
        ]
        for prompt in substring_prompts:
            result = asyncio.run(app.chat_completion(prompt))
            assert result == "OK response", f"Expected success for substring prompt: {prompt}"
            captured = capsys.readouterr()
            assert "Error command verb at beginning:" not in captured.out

    def test_localized_command_verb_unquoted(self, app, capsys):
        """Test that unquoted localized/translated command verbs (e.g. calcular, ayuda) return error."""
        # Spanish locale testing
        app.i18n.set_locale("es")
        spanish_prompts = [
            "calcular 2 + 2",
            "ayuda",
            "modelo gpt4"
        ]
        for prompt in spanish_prompts:
            result = asyncio.run(app.chat_completion(prompt))
            assert result == "", f"Expected empty result for Spanish unquoted prompt: {prompt}"
            captured = capsys.readouterr()
            assert "Error command verb at beginning:" in captured.out

        # French locale testing
        app.i18n.set_locale("fr")
        french_prompts = [
            "calculer 5 + 5",
            "aide",
            "modele claude"
        ]
        for prompt in french_prompts:
            result = asyncio.run(app.chat_completion(prompt))
            assert result == "", f"Expected empty result for French unquoted prompt: {prompt}"
            captured = capsys.readouterr()
            assert "Error command verb at beginning:" in captured.out


    @pytest.mark.anyio
    async def test_model_info_command(self, app, capsys):
        # Test /model info for the active model
        await app.handle_escape_command("/model info")
        captured = capsys.readouterr()
        assert "Model Information: test-model (alias: test_model)" in captured.out
        assert "Provider:        Unknown" in captured.out

        # Test /model <alias> info for an existing model
        await app.handle_escape_command("/model test_model info")
        captured = capsys.readouterr()
        assert "Model Information: test-model (alias: test_model)" in captured.out

        # Test /model <alias> info for a nonexistent model
        with patch.object(app.config_manager, "get_model_config", return_value=None):
            await app.handle_escape_command("/model nonexistent info")
            captured = capsys.readouterr()
            assert "Error: Model alias 'nonexistent' not found in configuration." in captured.out

        # Test localized /model info translation
        app.i18n.set_locale("es")
        translated_es = app.i18n.translate_command_string("/modelo informacion")
        assert translated_es == "/model info"

        app.i18n.set_locale("fr")
        translated_fr = app.i18n.translate_command_string("/modele informations")
        assert translated_fr == "/model info"

    @pytest.mark.anyio
    async def test_proc_and_foreach_command_translation(self, app):
        """Test localization resolving for /proc and foreach commands/keywords."""
        app.i18n.set_locale("es")
        assert app.i18n.resolve_command("/procedimiento") == "/proc"
        assert app.i18n.translate_script("definirproc myproc()") == "defproc myproc()"
        assert app.i18n.translate_script("paracada i en rango(1:5)") == "foreach i en rango(1:5)"

        app.i18n.set_locale("fr")
        assert app.i18n.resolve_command("/procedure") == "/proc"
        assert app.i18n.translate_script("pourchaque line en lignes(doc)") == "foreach line en lignes(doc)"

    @pytest.mark.anyio
    async def test_debug_payload_in_script_context(self, app, capsys):
        """Verify /debug payload mode is skipped when executing in script context."""
        app.debug_payload_mode = True
        app.script_context = True

        await app.chat_completion("Test prompt", stream=False)
        captured = capsys.readouterr()

        assert "Warning: /debug payload is not allowed in script context. Skipping." in captured.out
        assert app.debug_payload_mode is False



