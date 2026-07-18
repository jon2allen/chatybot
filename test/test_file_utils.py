#!/usr/bin/env python3
"""
Unit tests for file_utils module (specifically read_file binary checks).
"""

import os
import pytest
import tempfile
from src.chatybot.tools.file_utils import read_file, list_directory, find_files, grep_search, replace_file_content


def test_read_file_text():
    """Test reading a standard text file returns its contents with line numbers."""
    with tempfile.NamedTemporaryFile(mode='w', delete=False, encoding='utf-8') as f:
        f.write("Hello, ChatyBot! This is standard text.")
        f.flush()
        temp_name = f.name
    try:
        content = read_file(temp_name)
        assert "1: Hello, ChatyBot! This is standard text." in content
        assert not content.startswith("Error reading file:")
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

def test_find_files_finds_directories():
    """Test that find_files also finds matching directories."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a directory matching a pattern
        matching_dir = os.path.join(tmpdir, "matching_dir")
        os.makedirs(matching_dir, exist_ok=True)
        
        matches = find_files(tmpdir, pattern="*dir", details=True)
        # Should match matching_dir
        matching_entries = [m for m in matches if m["name"] == "matching_dir"]
        assert len(matching_entries) == 1
        entry = matching_entries[0]
        assert entry["path"] == matching_dir
        assert entry["type"] == "directory"
        assert "modified" in entry


def test_grep_search_literal():
    """Test searching for a literal term using grep_search."""
    with tempfile.TemporaryDirectory() as tmpdir:
        file_path = os.path.join(tmpdir, "test_file.txt")
        with open(file_path, "w") as f:
            f.write("Line 1: apple\nLine 2: Banana\nLine 3: Cherry\n")
        
        # Test case-sensitive match
        results = grep_search("Banana", path=tmpdir)
        assert len(results) == 1
        assert results[0]["line_number"] == 2
        assert results[0]["content"] == "Line 2: Banana"
        assert results[0]["file"] == file_path

        # Test case-insensitive match
        results_ci = grep_search("banana", path=tmpdir, case_insensitive=True)
        assert len(results_ci) == 1

        # Test no match
        results_none = grep_search("durian", path=tmpdir)
        assert len(results_none) == 0


def test_grep_search_regex():
    """Test searching for a regular expression pattern using grep_search."""
    with tempfile.TemporaryDirectory() as tmpdir:
        file_path = os.path.join(tmpdir, "test_file.txt")
        with open(file_path, "w") as f:
            f.write("apple\nBanana\nCherry\n")
            
        # Test regex pattern
        results = grep_search("^[BC]", path=tmpdir, is_regex=True)
        assert len(results) == 2
        lines = [r["content"] for r in results]
        assert "Banana" in lines
        assert "Cherry" in lines

        # Test invalid regex
        results_invalid = grep_search("[invalid", path=tmpdir, is_regex=True)
        assert len(results_invalid) == 1
        assert "error" in results_invalid[0]


def test_grep_search_edge_cases():
    """Test grep_search edge cases (line truncation, single file search, folder pruning)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a single file with a very long line
        file_path = os.path.join(tmpdir, "long_line.txt")
        long_line = "a" * 1500 + "MATCH"
        with open(file_path, "w") as f:
            f.write(long_line + "\n")

        # Test single file search directly via path
        results_file = grep_search("MATCH", path=file_path)
        assert len(results_file) == 1
        assert results_file[0]["file"] == file_path
        # Test line truncation
        assert len(results_file[0]["content"]) < 1500
        assert results_file[0]["content"].endswith(" [TRUNCATED]")

        # Test directory pruning (e.g., matching a pattern inside a pruned folder should not return matches)
        pruned_dir = os.path.join(tmpdir, ".git")
        os.makedirs(pruned_dir)
        pruned_file = os.path.join(pruned_dir, "config")
        with open(pruned_file, "w") as f:
            f.write("MATCH\n")

        results_dir = grep_search("MATCH", path=tmpdir)
        # Should match the file in root (long_line.txt), but not the one in .git/
        assert len(results_dir) == 1
        assert results_dir[0]["file"] == file_path


def test_replace_file_content():
    """Test replace_file_content replaces target content successfully."""
    with tempfile.TemporaryDirectory() as tmpdir:
        file_path = os.path.join(tmpdir, "test_replace.txt")
        with open(file_path, "w") as f:
            f.write("hello world\nhello world\n")
        
        # Test basic replacement
        result = replace_file_content(file_path, "world", "there")
        assert "Success: Replaced 2 occurrence(s)" in result
        
        with open(file_path, "r") as f:
            content = f.read()
        assert content == "hello there\nhello there\n"

        # Test non-existent target
        result_fail = replace_file_content(file_path, "nonexistent", "new")
        assert "Error: Target content not found" in result_fail

        # Test non-existent file
        result_no_file = replace_file_content(os.path.join(tmpdir, "no_such_file.txt"), "hello", "hi")
        assert "Error: File" in result_no_file


