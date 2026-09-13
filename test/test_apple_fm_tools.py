#!/usr/bin/env python3
"""
Unit tests for the apple_fm native tool calling bridge.

Tests that do NOT require the apple-fm-sdk package test the schema
mapping and TOML-to-tool logic. Tests that DO require the SDK are
skipped when it's not installed.
"""

import pytest
import json
from chatybot.apple_fm_backend import _TOML_TYPE_MAP, _ASK_USER_SCHEMA


# ---------------------------------------------------------------------------
# SDK-free tests: type mapping and schema definitions
# ---------------------------------------------------------------------------

class TestTypeMapping:
    """Tests for TOML type to Python type mapping."""

    def test_string_maps_to_str(self):
        assert _TOML_TYPE_MAP["string"] is str

    def test_integer_maps_to_int(self):
        assert _TOML_TYPE_MAP["integer"] is int

    def test_boolean_maps_to_bool(self):
        assert _TOML_TYPE_MAP["boolean"] is bool

    def test_number_maps_to_float(self):
        assert _TOML_TYPE_MAP["number"] is float

    def test_float_maps_to_float(self):
        assert _TOML_TYPE_MAP["float"] is float

    def test_unknown_type_defaults_to_str(self):
        # When looking up an unknown type, the code uses .get(toml_type, str)
        assert _TOML_TYPE_MAP.get("unknown", str) is str


class TestAskUserSchema:
    """Tests for the built-in ask_user tool schema."""

    def test_prompt_is_required(self):
        assert _ASK_USER_SCHEMA["prompt"]["optional"] is False

    def test_prompt_is_string(self):
        assert _ASK_USER_SCHEMA["prompt"]["type"] == "string"

    def test_choices_is_optional(self):
        assert _ASK_USER_SCHEMA["choices"]["optional"] is True

    def test_question_type_is_optional(self):
        assert _ASK_USER_SCHEMA["question_type"]["optional"] is True

    def test_target_variable_is_optional(self):
        assert _ASK_USER_SCHEMA["target_variable"]["optional"] is True

    def test_has_four_params(self):
        assert len(_ASK_USER_SCHEMA) == 4


# ---------------------------------------------------------------------------
# SDK-required tests: generable class and tool wrapper creation
# ---------------------------------------------------------------------------

# Check if the SDK is available
try:
    import apple_fm_sdk as fm
    _SDK_AVAILABLE = True
except ImportError:
    _SDK_AVAILABLE = False

pytestmark = pytest.mark.skipif(not _SDK_AVAILABLE, reason="apple-fm-sdk not installed")


class TestGenerableClassCreation:
    """Tests for dynamic @fm.generable class creation from TOML params."""

    def test_creates_class_with_correct_name(self):
        from chatybot.apple_fm_backend import _create_generable_class
        params = {"path": {"type": "string", "description": "File path", "optional": False}}
        cls = _create_generable_class("read_file", params)
        assert cls.__name__ == "read_file_Args"

    def test_class_is_generable(self):
        from chatybot.apple_fm_backend import _create_generable_class
        params = {"path": {"type": "string", "description": "File path", "optional": False}}
        cls = _create_generable_class("read_file", params)
        assert hasattr(cls, "generation_schema")

    def test_generation_schema_returns_fm_schema(self):
        from chatybot.apple_fm_backend import _create_generable_class
        params = {"path": {"type": "string", "description": "File path", "optional": False}}
        cls = _create_generable_class("read_file", params)
        schema = cls.generation_schema()
        assert schema is not None

    def test_empty_parameters(self):
        from chatybot.apple_fm_backend import _create_generable_class
        cls = _create_generable_class("no_args", {})
        assert hasattr(cls, "generation_schema")

    def test_multiple_parameters(self):
        from chatybot.apple_fm_backend import _create_generable_class
        params = {
            "path": {"type": "string", "description": "File path", "optional": False},
            "content": {"type": "string", "description": "Content to write", "optional": False},
            "append": {"type": "boolean", "description": "Append mode", "optional": True},
        }
        cls = _create_generable_class("write_file", params)
        schema = cls.generation_schema()
        assert schema is not None


class TestToolWrapperCreation:
    """Tests for fm.Tool wrapper creation."""

    def test_tool_wrapper_has_name(self):
        from chatybot.apple_fm_backend import _create_tool_wrapper
        tool_meta = {
            "description": "Read a file",
            "parameters": {"path": {"type": "string", "description": "File path", "optional": False}},
        }
        tool_cls = _create_tool_wrapper("read_file", tool_meta, app=None)
        assert tool_cls.name == "read_file"

    def test_tool_wrapper_has_description(self):
        from chatybot.apple_fm_backend import _create_tool_wrapper
        tool_meta = {
            "description": "Read a file",
            "parameters": {"path": {"type": "string", "description": "File path", "optional": False}},
        }
        tool_cls = _create_tool_wrapper("read_file", tool_meta, app=None)
        assert tool_cls.description == "Read a file"

    def test_tool_wrapper_has_arguments_schema(self):
        from chatybot.apple_fm_backend import _create_tool_wrapper
        tool_meta = {
            "description": "Read a file",
            "parameters": {"path": {"type": "string", "description": "File path", "optional": False}},
        }
        tool_cls = _create_tool_wrapper("read_file", tool_meta, app=None)
        instance = tool_cls()
        schema = instance.arguments_schema
        assert schema is not None

    def test_tool_wrapper_is_fm_tool_subclass(self):
        from chatybot.apple_fm_backend import _create_tool_wrapper
        tool_meta = {
            "description": "Read a file",
            "parameters": {"path": {"type": "string", "description": "File path", "optional": False}},
        }
        tool_cls = _create_tool_wrapper("read_file", tool_meta, app=None)
        assert issubclass(tool_cls, fm.Tool)


class TestBuildTools:
    """Tests for build_tools() with a mock app."""

    def test_build_tools_returns_list(self):
        from chatybot.apple_fm_backend import build_tools

        class MockApp:
            tool_overrides = {}
            def _load_tools_config(self):
                return {
                    "tools": {
                        "read_file": {
                            "enabled": True,
                            "description": "Read a file",
                            "parameters": {
                                "path": {"type": "string", "description": "File path", "optional": False}
                            },
                        }
                    }
                }

        tools = build_tools(MockApp())
        assert isinstance(tools, list)
        assert len(tools) >= 1  # read_file + ask_user

    def test_build_tools_includes_ask_user(self):
        from chatybot.apple_fm_backend import build_tools

        class MockApp:
            tool_overrides = {}
            def _load_tools_config(self):
                return {"tools": {}}

        tools = build_tools(MockApp())
        assert any(t.name == "ask_user" for t in tools)

    def test_build_tools_respects_disabled(self):
        from chatybot.apple_fm_backend import build_tools

        class MockApp:
            tool_overrides = {"read_file": False}
            def _load_tools_config(self):
                return {
                    "tools": {
                        "read_file": {
                            "enabled": True,
                            "description": "Read a file",
                            "parameters": {
                                "path": {"type": "string", "description": "File path", "optional": False}
                            },
                        }
                    }
                }

        tools = build_tools(MockApp())
        assert not any(t.name == "read_file" for t in tools)

    def test_build_tools_respects_not_enabled(self):
        from chatybot.apple_fm_backend import build_tools

        class MockApp:
            tool_overrides = {}
            def _load_tools_config(self):
                return {
                    "tools": {
                        "disabled_tool": {
                            "enabled": False,
                            "description": "A disabled tool",
                            "parameters": {},
                        }
                    }
                }

        tools = build_tools(MockApp())
        assert not any(t.name == "disabled_tool" for t in tools)

    def test_build_tools_empty_config(self):
        from chatybot.apple_fm_backend import build_tools

        class MockApp:
            tool_overrides = {}
            def _load_tools_config(self):
                return {}

        tools = build_tools(MockApp())
        # Should still include ask_user
        assert any(t.name == "ask_user" for t in tools)
