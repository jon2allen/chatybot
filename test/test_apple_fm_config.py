#!/usr/bin/env python3
"""
Unit tests for the apple_fm model type — config layer only.

These tests do NOT require the apple-fm-sdk package or an Apple Silicon Mac.
They verify that the config model, TOML loading, and TOML serialization
handle the apple_fm model type correctly.
"""

import pytest
from chatybot.config_model import (
    ChatConfig,
    ChatModelConfig,
    RerankerModelConfig,
    AppleFMModelConfig,
)


# ---------------------------------------------------------------------------
# TOML string for testing
# ---------------------------------------------------------------------------

APPLE_FM_TOML = """
[image_generation]

[models.mistral_1]
type = "chat"
name = "mistral-large-2512"
base_url = "https://api.mistral.ai/v1"
api_key = "MISTRAL_API_KEY"

[models.apple_fm]
type = "apple_fm"
name = "Apple Foundation Model"
context_limit = 4096
temperature = 0.7
"""


@pytest.fixture
def config():
    return ChatConfig.from_toml_string(APPLE_FM_TOML)


# ---------------------------------------------------------------------------
# Config model tests
# ---------------------------------------------------------------------------

class TestAppleFMConfigModel:
    """Tests for AppleFMModelConfig class and discriminated union."""

    def test_apple_fm_model_loaded(self, config):
        """Apple FM model is loaded and is the correct type."""
        model = config.get_model("apple_fm")
        assert model is not None
        assert isinstance(model, AppleFMModelConfig)

    def test_apple_fm_type_discriminator(self, config):
        """The type discriminator resolves to apple_fm."""
        model = config.get_model("apple_fm")
        assert model.type == "apple_fm"

    def test_apple_fm_base_url_default(self, config):
        """base_url defaults to 'on-device' when not specified."""
        model = config.get_model("apple_fm")
        assert model.base_url == "on-device"

    def test_apple_fm_no_api_key(self, config):
        """api_key is None for apple_fm models."""
        model = config.get_model("apple_fm")
        assert model.api_key is None

    def test_apple_fm_vendor(self, config):
        """vendor is 'apple' for apple_fm models."""
        model = config.get_model("apple_fm")
        assert model.vendor == "apple"

    def test_apple_fm_context_limit(self, config):
        """context_limit is loaded from TOML."""
        model = config.get_model("apple_fm")
        assert model.context_limit == 4096

    def test_apple_fm_temperature(self, config):
        """temperature is loaded from TOML."""
        model = config.get_model("apple_fm")
        assert model.temperature == 0.7

    def test_chat_model_still_works(self, config):
        """Regular chat models still load alongside apple_fm."""
        model = config.get_model("mistral_1")
        assert model is not None
        assert isinstance(model, ChatModelConfig)
        assert model.type == "chat"

    def test_apple_fm_models_accessor(self, config):
        """apple_fm_models() returns only apple_fm models."""
        apple_models = config.apple_fm_models()
        assert len(apple_models) == 1
        assert apple_models[0].alias == "apple_fm"

    def test_chat_models_excludes_apple_fm(self, config):
        """chat_models() does not include apple_fm models."""
        chat_models = config.chat_models()
        assert all(not isinstance(m, AppleFMModelConfig) for m in chat_models)


# ---------------------------------------------------------------------------
# TOML round-trip tests
# ---------------------------------------------------------------------------

class TestAppleFMTOMLRoundTrip:
    """Tests for TOML serialization of apple_fm models."""

    def test_to_toml_string_includes_apple_fm(self, config):
        """to_toml_string() includes the apple_fm model entry."""
        toml_str = config.to_toml_string()
        assert "[models.apple_fm]" in toml_str
        assert 'type = "apple_fm"' in toml_str
        assert "Apple Foundation Model" in toml_str

    def test_to_toml_string_has_category_header(self, config):
        """to_toml_string() categorizes apple_fm under its own header."""
        toml_str = config.to_toml_string()
        assert "APPLE FM MODELS" in toml_str

    def test_round_trip_preserves_apple_fm(self, config):
        """Serializing and re-loading preserves the apple_fm model."""
        toml_str = config.to_toml_string()
        config2 = ChatConfig.from_toml_string(toml_str)
        model = config2.get_model("apple_fm")
        assert model is not None
        assert isinstance(model, AppleFMModelConfig)
        assert model.name == "Apple Foundation Model"
        assert model.context_limit == 4096


# ---------------------------------------------------------------------------
# Minimal config (only apple_fm)
# ---------------------------------------------------------------------------

class TestAppleFMOnlyConfig:
    """Tests with a config containing only an apple_fm model."""

    def test_only_apple_fm_config(self):
        """A config with only an apple_fm model loads correctly."""
        toml = """
[models.apple_fm]
type = "apple_fm"
name = "Apple Foundation Model"
"""
        config = ChatConfig.from_toml_string(toml)
        assert len(config.models) == 1
        model = config.get_model("apple_fm")
        assert isinstance(model, AppleFMModelConfig)
        assert model.base_url == "on-device"
        assert model.vendor == "apple"

    def test_apple_fm_as_default(self):
        """apple_fm can be the default model."""
        toml = """
[default]
model = "apple_fm"

[models.apple_fm]
type = "apple_fm"
name = "Apple Foundation Model"
"""
        config = ChatConfig.from_toml_string(toml)
        assert config.default.model == "apple_fm"
        assert config.get_model("apple_fm") is not None
