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


class TestToolExecutionTracing:
    """Tests for tool execution output and trace_agentic_loop recording."""

    @pytest.mark.anyio
    async def test_call_prints_tool_and_records_agentic_loop(self, capsys):
        from chatybot.apple_fm_backend import _create_tool_wrapper

        class MockBufferManager:
            def __init__(self):
                self.vars = {}

            def get_script_var(self, name):
                return self.vars.get(name)

            def set_script_var(self, name, val, allow_protected=False):
                self.vars[name] = val

        class MockApp:
            def __init__(self):
                self.buffer_manager = MockBufferManager()
                self.trace_agentic_loop = True
                self.dispatched = []

            async def dispatch_tool(self, invocation):
                self.dispatched.append(invocation)
                self.buffer_manager.set_script_var('TOOL_DISPATCH_EXIT_CODE', '0')
                return "File content mock"

        app = MockApp()
        tool_meta = {
            "description": "Read file",
            "parameters": {"path": {"type": "string", "description": "path", "optional": False}},
        }
        tool_cls = _create_tool_wrapper("read_file", tool_meta, app=app)
        tool_instance = tool_cls()

        class MockArgs:
            def value(self, py_type, for_property):
                if for_property == "path":
                    return "README.md"
                return None

        result = await tool_instance.call(MockArgs())
        assert result == "File content mock"
        assert len(app.dispatched) == 1

        captured = capsys.readouterr().out
        # Option #3 verification
        assert "[Apple FM] LLM requested tool: read_file" in captured
        assert "Arguments: {\"path\": \"README.md\"}" in captured
        assert "Tool Result: File content mock" in captured

        # Trace mode verification
        assert "--- [Trace: Apple FM Tool Execution] ---" in captured
        assert "Tool: read_file" in captured
        assert "Exit Code: 0" in captured

        # AGENTIC_LOOP record verification
        records = app.buffer_manager.get_script_var("AGENTIC_LOOP")
        assert isinstance(records, list)
        assert len(records) == 1
        assert records[0]["tool"] == "read_file"
        assert records[0]["arguments"] == {"path": "README.md"}
        assert records[0]["status"] == "success"
        assert records[0]["exit_code"] == 0

