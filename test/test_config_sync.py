#!/usr/bin/env python3
"""
Unit tests for config_sync module
"""

import os
import tempfile
import pytest
from src.chatybot.config_sync import deep_merge, serialize_toml, sync_toml_file, load_toml

class TestConfigSync:
    """Test suite for config_sync utility functions"""

    def test_deep_merge_simple(self):
        source = {"a": 1, "b": {"c": 2}}
        destination = {"b": {"d": 3}}
        
        changes = deep_merge(source, destination)
        
        assert "a" in changes
        assert "b.c" in changes
        assert destination == {"a": 1, "b": {"c": 2, "d": 3}}

    def test_deep_merge_preserves_customizations(self):
        source = {"a": 1, "b": {"c": 2}}
        destination = {"a": 10, "b": {"c": 20}}
        
        changes = deep_merge(source, destination)
        
        assert len(changes) == 0
        assert destination == {"a": 10, "b": {"c": 20}}

    def test_serialize_toml_simple(self):
        data = {
            "config": {
                "max_turns": 25,
                "shell": True,
                "agentic_instructions": "Do things.\nBe good."
            },
            "tools": {
                "list_dir": {
                    "enabled": True,
                    "description": "List directory"
                }
            }
        }
        serialized = serialize_toml(data)
        
        import tomllib
        parsed = tomllib.loads(serialized)
        assert parsed == data

    def test_sync_toml_file_missing_user_file(self):
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.toml') as pkg_file:
            pkg_file.write("[config]\ntimeout = 30\n")
            pkg_file.flush()
            pkg_path = pkg_file.name

        user_path = pkg_path + ".user"
        
        try:
            # Sync when user file doesn't exist
            sync_toml_file(pkg_path, user_path, "test_config")
            
            assert os.path.exists(user_path)
            user_data = load_toml(user_path)
            assert user_data == {"config": {"timeout": 30}}
        finally:
            if os.path.exists(pkg_path):
                os.unlink(pkg_path)
            if os.path.exists(user_path):
                os.unlink(user_path)

    def test_sync_toml_file_merging(self):
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.toml') as pkg_file:
            pkg_file.write("[config]\ntimeout = 30\nnew_key = true\n")
            pkg_file.flush()
            pkg_path = pkg_file.name

        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.toml') as user_file:
            user_file.write("[config]\ntimeout = 45\n")
            user_file.flush()
            user_path = user_file.name

        try:
            sync_toml_file(pkg_path, user_path, "test_config")
            
            user_data = load_toml(user_path)
            # Custom timeout preserved, new_key merged
            assert user_data == {"config": {"timeout": 45, "new_key": True}}
        finally:
            if os.path.exists(pkg_path):
                os.unlink(pkg_path)
            if os.path.exists(user_path):
                os.unlink(user_path)
