#!/usr/bin/env python3
"""
Unit tests for sampling parameter commands and disabling mechanisms (/top_k, /top_p, /temp, etc.).
"""

import pytest
from src.chatybot.chatybot_app import ChatybotApp


class TestSamplingParams:
    """Test suite for sampling parameters (/top_k, /top_p, /temp, /freq_penalty, /pres_penalty)."""

    @pytest.mark.anyio
    async def test_top_k_escape_commands(self):
        app = ChatybotApp()
        app.initialize()

        # Set integer value
        res = await app.handle_escape_command("/top_k 50")
        assert res is True
        assert app.top_k == 50

        # Disable top_k
        res = await app.handle_escape_command("/top_k off")
        assert res is True
        assert app.top_k == "off"

        # Disable top_k with none
        res = await app.handle_escape_command("/top_k none")
        assert res is True
        assert app.top_k == "off"

        # Reset to default
        res = await app.handle_escape_command("/top_k default")
        assert res is True
        assert app.top_k is None

        # Inspect current top_k
        res = await app.handle_escape_command("/top_k")
        assert res is True

    @pytest.mark.anyio
    async def test_top_p_escape_commands(self):
        app = ChatybotApp()
        app.initialize()

        # Set float value
        res = await app.handle_escape_command("/top_p 0.85")
        assert res is True
        assert app.top_p == 0.85

        # Disable top_p
        res = await app.handle_escape_command("/top_p off")
        assert res is True
        assert app.top_p == "off"

        # Reset to default
        res = await app.handle_escape_command("/top_p default")
        assert res is True
        assert app.top_p is None

    @pytest.mark.anyio
    async def test_temp_escape_commands(self):
        app = ChatybotApp()
        app.initialize()

        # Set float value
        res = await app.handle_escape_command("/temp 0.2")
        assert res is True
        assert app.temperature == 0.2

        # Reset to default
        res = await app.handle_escape_command("/temp default")
        assert res is True
        assert app.temperature is None

    @pytest.mark.anyio
    async def test_penalties_escape_commands(self):
        app = ChatybotApp()
        app.initialize()

        # Freq penalty
        res = await app.handle_escape_command("/freq_penalty 0.5")
        assert res is True
        assert app.freq_penalty == 0.5

        res = await app.handle_escape_command("/freq_penalty off")
        assert res is True
        assert app.freq_penalty == "off"

        res = await app.handle_escape_command("/freq_penalty default")
        assert res is True
        assert app.freq_penalty is None

        # Pres penalty
        res = await app.handle_escape_command("/pres_penalty 0.5")
        assert res is True
        assert app.pres_penalty == 0.5

        res = await app.handle_escape_command("/pres_penalty off")
        assert res is True
        assert app.pres_penalty == "off"

        res = await app.handle_escape_command("/pres_penalty default")
        assert res is True
        assert app.pres_penalty is None

    @pytest.mark.anyio
    async def test_logging_hex_escape_commands(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        app = ChatybotApp()
        app.initialize()

        # Start logging with hex mode
        res = await app.handle_escape_command("/logging start hex")
        assert res is True
        assert app.logging_manager.logging_active is True
        assert app.logging_manager.hex_mode is True

        # Toggle hex mode off
        res = await app.handle_escape_command("/logging hex off")
        assert res is True
        assert app.logging_manager.hex_mode is False

        # Toggle hex mode on
        res = await app.handle_escape_command("/logging hex on")
        assert res is True
        assert app.logging_manager.hex_mode is True

        # Stop logging
        res = await app.handle_escape_command("/logging end")
        assert res is True
        assert app.logging_manager.logging_active is False

    @pytest.mark.anyio
    async def test_effort_muse_glimmer_escape_commands(self, capsys):
        app = ChatybotApp()
        app.initialize()

        # Set active model to a Muse Glimmer model
        app.config_manager.active_model_alias = "glimmer"
        app.config_manager.config["models"]["glimmer"] = {
            "name": "meta/muse-glimmer-30b",
            "base_url": "https://integrate.api.nvidia.com/v1",
        }

        # Set effort to high for Muse
        res = await app.handle_escape_command("/effort high")
        assert res is True
        assert app.reasoning_effort == "high"
        captured = capsys.readouterr()
        assert "Active model is Muse Glimmer: setting reasoning_strength to 'high'" in captured.out

        # Query effort
        res = await app.handle_escape_command("/effort")
        assert res is True
        captured = capsys.readouterr()
        assert "Active model is Muse Glimmer: reasoning_strength is currently 'high'" in captured.out

        # Set effort to xhigh (Muse-specific)
        res = await app.handle_escape_command("/effort xhigh")
        assert res is True
        assert app.reasoning_effort == "xhigh"
        captured = capsys.readouterr()
        assert "Active model is Muse Glimmer: setting reasoning_strength to 'xhigh'" in captured.out

        # Disable effort
        res = await app.handle_escape_command("/effort none")
        assert res is True
        assert app.reasoning_effort is None
        captured = capsys.readouterr()
        assert "Reasoning effort disabled for Muse" in captured.out

