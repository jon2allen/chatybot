#!/usr/bin/env python3
"""
Unit tests for file_utils module (specifically read_file binary checks).
"""

import os
import pytest
import tempfile
from src.chatybot.tools.file_utils import read_file


def test_read_file_text():
    """Test reading a standard text file returns its contents."""
    with tempfile.NamedTemporaryFile(mode='w', delete=False, encoding='utf-8') as f:
        f.write("Hello, ChatyBot! This is standard text.")
        f.flush()
        temp_name = f.name
    try:
        content = read_file(temp_name)
        assert content == "Hello, ChatyBot! This is standard text."
    finally:
        os.unlink(temp_name)


def test_read_file_binary():
    """Test reading a binary file containing null bytes returns a binary error message."""
    with tempfile.NamedTemporaryFile(mode='wb', delete=False) as f:
        # Write some text followed by null bytes and binary payload
        f.write(b"Hello binary world!\x00\x01\x02\x03\x04")
        f.flush()
        temp_name = f.name
    try:
        content = read_file(temp_name)
        assert "Binary file format is not supported" in content
    finally:
        os.unlink(temp_name)


def test_read_file_nonexistent():
    """Test reading a nonexistent file returns a standard file error message."""
    content = read_file("/nonexistent/file/path/here.txt")
    assert "Error reading file" in content
