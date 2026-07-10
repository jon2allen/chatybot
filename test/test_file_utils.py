#!/usr/bin/env python3
"""
Unit tests for file_utils module (specifically read_file binary checks).
"""

import os
import pytest
import tempfile
from src.chatybot.tools.file_utils import read_file, list_directory, find_files


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


def test_list_directory_basic():
    """Test list_directory returns a list of names when details=False."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a file and a subdirectory
        file_path = os.path.join(tmpdir, "test_file.txt")
        with open(file_path, "w") as f:
            f.write("hello")
        dir_path = os.path.join(tmpdir, "test_dir")
        os.makedirs(dir_path, exist_ok=True)
        
        contents = list_directory(tmpdir, details=False)
        assert len(contents) == 2
        assert "test_file.txt" in contents
        assert "test_dir" in contents
        assert all(isinstance(x, str) for x in contents)


def test_list_directory_detailed():
    """Test list_directory returns metadata dictionaries when details=True."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a file
        file_path = os.path.join(tmpdir, "test_file.txt")
        with open(file_path, "w") as f:
            f.write("hello world")
        
        # Create a subdirectory
        dir_path = os.path.join(tmpdir, "test_sub_dir")
        os.makedirs(dir_path, exist_ok=True)
        
        contents = list_directory(tmpdir, details=True)
        assert len(contents) == 2
        
        # Find file entry
        file_entry = next(item for item in contents if item["name"] == "test_file.txt")
        assert file_entry["type"] == "file"
        assert file_entry["size"] == 11
        assert "modified" in file_entry
        assert file_entry["modified"] != "unknown"
        
        # Find dir entry
        dir_entry = next(item for item in contents if item["name"] == "test_sub_dir")
        assert dir_entry["type"] == "directory"
        assert dir_entry["size"] == 0
        assert "modified" in dir_entry
        assert dir_entry["modified"] != "unknown"


def test_find_files_basic():
    """Test find_files returns list of path strings when details=False."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a file inside a subdirectory
        sub_dir = os.path.join(tmpdir, "subdir")
        os.makedirs(sub_dir, exist_ok=True)
        file_path = os.path.join(sub_dir, "test_file.chatdsl")
        with open(file_path, "w") as f:
            f.write("test content")
        
        matches = find_files(tmpdir, pattern="*.chatdsl", details=False)
        assert len(matches) == 1
        assert matches[0] == file_path
        assert isinstance(matches[0], str)


def test_find_files_detailed():
    """Test find_files returns dictionaries with metadata when details=True."""
    with tempfile.TemporaryDirectory() as tmpdir:
        sub_dir = os.path.join(tmpdir, "subdir")
        os.makedirs(sub_dir, exist_ok=True)
        file_path = os.path.join(sub_dir, "test_file.chatdsl")
        with open(file_path, "w") as f:
            f.write("test content")
        
        matches = find_files(tmpdir, pattern="*.chatdsl", details=True)
        assert len(matches) == 1
        entry = matches[0]
        assert entry["name"] == "test_file.chatdsl"
        assert entry["path"] == file_path
        assert entry["type"] == "file"
        assert entry["size"] == 12
        assert "modified" in entry
        assert entry["modified"] != "unknown"


