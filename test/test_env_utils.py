"""
test_env_utils.py — Unit tests for env_utils module.
"""

import os
import tempfile
from pathlib import Path
import pytest

from chatybot.env_utils import (
    parse_env_line,
    load_env_file,
    load_project_env_files,
    resolve_api_key,
)


class TestParseEnvLine:
    def test_basic_assignment(self):
        assert parse_env_line("MISTRAL_API_KEY=test_key_123") == ("MISTRAL_API_KEY", "test_key_123")

    def test_export_prefix(self):
        assert parse_env_line("export OPENAI_API_KEY=sk-test-456") == ("OPENAI_API_KEY", "sk-test-456")
        assert parse_env_line("export\tGEMINI_API_KEY=AIza123") == ("GEMINI_API_KEY", "AIza123")

    def test_quoted_values(self):
        assert parse_env_line('MISTRAL_API_KEY="quoted-key"') == ("MISTRAL_API_KEY", "quoted-key")
        assert parse_env_line("MISTRAL_API_KEY='single-quoted'") == ("MISTRAL_API_KEY", "single-quoted")

    def test_multiple_equals(self):
        assert parse_env_line("BASE_URL=https://example.com/api?v=1&x=2") == ("BASE_URL", "https://example.com/api?v=1&x=2")

    def test_comments_and_blanks(self):
        assert parse_env_line("# This is a comment") is None
        assert parse_env_line("   ") is None
        assert parse_env_line("") is None
        assert parse_env_line("NO_EQUALS_HERE") is None


class TestLoadEnvFile:
    def test_load_with_and_without_override(self, monkeypatch):
        monkeypatch.setenv("EXISTING_KEY", "original_value")

        with tempfile.TemporaryDirectory() as tmpdir:
            env_file = Path(tmpdir) / ".env"
            env_file.write_text(
                "EXISTING_KEY=new_value\n"
                "NEW_KEY=hello_world\n"
                "export EXPORTED_KEY=exported_val\n"
            )

            # Test override=False (setdefault)
            result = load_env_file(env_file, override=False)
            assert result["NEW_KEY"] == "hello_world"
            assert os.environ["EXISTING_KEY"] == "original_value"  # Not overridden
            assert os.environ["NEW_KEY"] == "hello_world"
            assert os.environ["EXPORTED_KEY"] == "exported_val"

            # Test override=True
            load_env_file(env_file, override=True)
            assert os.environ["EXISTING_KEY"] == "new_value"  # Overridden


class TestLoadProjectEnvFiles:
    def test_local_takes_priority_and_stops_parent_search(self, monkeypatch):
        monkeypatch.delenv("LOCAL_KEY", raising=False)
        monkeypatch.delenv("PARENT_KEY", raising=False)
        monkeypatch.delenv("GLOBAL_KEY", raising=False)

        with tempfile.TemporaryDirectory() as tmpdir:
            parent_dir = Path(tmpdir) / "parent"
            project_dir = parent_dir / "project"
            project_dir.mkdir(parents=True)

            # Parent .env
            (parent_dir / ".env").write_text("PARENT_KEY=parent_val\nSHARED_KEY=parent_shared\n")

            # Project .env
            (project_dir / ".env").write_text("LOCAL_KEY=local_val\nSHARED_KEY=local_shared\n")

            # Global .env
            global_dir = Path(tmpdir) / "global_config"
            global_dir.mkdir()
            (global_dir / ".env").write_text("GLOBAL_KEY=global_val\nSHARED_KEY=global_shared\n")

            loaded = load_project_env_files(cwd=project_dir, config_home=global_dir)

            # Local was loaded, parent was skipped because local was found
            assert str(project_dir / ".env") in loaded
            assert str(parent_dir / ".env") not in loaded
            assert str(global_dir / ".env") in loaded

            assert os.environ.get("LOCAL_KEY") == "local_val"
            assert os.environ.get("PARENT_KEY") is None  # Parent not leaked
            assert os.environ.get("SHARED_KEY") == "local_shared"  # Global didn't override local
            assert os.environ.get("GLOBAL_KEY") == "global_val"  # Global fallback provided


class TestResolveApiKey:
    def test_resolves_existing_environment_variable(self, monkeypatch):
        monkeypatch.setenv("MISTRAL_API_KEY", "real-secret-12345")
        assert resolve_api_key("MISTRAL_API_KEY") == "real-secret-12345"

    def test_resolves_known_raw_key_prefixes(self, monkeypatch):
        monkeypatch.delenv("sk-openrouter-key", raising=False)
        assert resolve_api_key("sk-openrouter-key") == "sk-openrouter-key"
        assert resolve_api_key("nvapi-12345678") == "nvapi-12345678"
        assert resolve_api_key("AIzaSyDummyKey") == "AIzaSyDummyKey"
        assert resolve_api_key("gsk_groqkey123") == "gsk_groqkey123"
        assert resolve_api_key("hf_token123") == "hf_token123"
        assert resolve_api_key("co-test-key") == "co-test-key"

    def test_resolves_raw_key_with_whitespace(self, monkeypatch):
        raw_with_spaces = "my raw key string"
        assert resolve_api_key(raw_with_spaces) == raw_with_spaces

    def test_custom_unset_lowercase_env_var_returns_none(self, monkeypatch):
        """CRITICAL: Ensure long custom env var names do NOT trigger false-positive raw-key leaks."""
        custom_var = "my_custom_mistral_api_key_v2"
        monkeypatch.delenv(custom_var, raising=False)
        assert resolve_api_key(custom_var) is None

    def test_empty_or_none_spec(self):
        assert resolve_api_key(None) is None
        assert resolve_api_key("") is None
