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


def test_read_file_single_filename_non_windows():
    """Test that a single filename in non-Windows assumes current dir (./<filename>)."""
    filename = "temp_single_file_test.txt"
    with open(filename, "w", encoding="utf-8") as f:
        f.write("single file content")
    try:
        content = read_file(filename)
        assert "1: single file content" in content
    finally:
        if os.path.exists(filename):
            os.unlink(filename)



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


def test_read_file_slice_absolute_line_numbering():
    """Verify reading a slice with start_line retains absolute file line numbers."""
    with tempfile.NamedTemporaryFile(mode='w', delete=False, encoding='utf-8') as f:
        for i in range(1, 21):
            f.write(f"Line number {i}\n")
        f.flush()
        temp_name = f.name
    try:
        content = read_file(temp_name, start_line=10, end_line=13)
        assert "10: Line number 10\n" in content
        assert "11: Line number 11\n" in content
        assert "12: Line number 12\n" in content
        assert "13: Line number 13\n" in content
        # Ensure it does NOT start from 1:
        assert not content.startswith("1: ")
    finally:
        os.unlink(temp_name)


def test_replace_file_content_with_line_bounds():
    """Verify replace_file_content with start_line and end_line bounds."""
    with tempfile.NamedTemporaryFile(mode='w', delete=False, encoding='utf-8') as f:
        f.write("target\nmiddle\ntarget\n")
        f.flush()
        temp_name = f.name
    try:
        # Replacing within lines 1-2 only changes the first occurrence
        res = replace_file_content(temp_name, "target", "REPLACED", start_line=1, end_line=2)
        assert "Success: Replaced 1 occurrence(s)" in res
        assert "(within lines 1-2)" in res

        with open(temp_name, "r", encoding="utf-8") as f:
            updated = f.read()
        assert updated == "REPLACED\nmiddle\ntarget\n"

        # Searching for 'middle' in lines 1-1 fails with range diagnosis
        fail_res = replace_file_content(temp_name, "middle", "NEW", start_line=1, end_line=1)
        assert "within lines 1-1" in fail_res
    finally:
        os.unlink(temp_name)


def test_replace_file_content_indentation_diagnosis():
    """Verify replace_file_content provides diagnostic message on indentation mismatch."""
    with tempfile.NamedTemporaryFile(mode='w', delete=False, encoding='utf-8') as f:
        f.write("    def my_function():\n        return True\n")
        f.flush()
        temp_name = f.name
    try:
        # Off by one leading space (5 spaces instead of 4)
        mismatched_target = "     def my_function():\n        return True"
        res = replace_file_content(temp_name, mismatched_target, "    def updated():\n        return True")
        assert "Error: Target content not found" in res
        assert "Diagnosis:" in res
        assert "indentation/whitespace discrepancy" in res
        assert "Target (line 1): 5 leading spaces" in res
        assert "File   (line 1): 4 leading spaces" in res
    finally:
        os.unlink(temp_name)



def test_write_file_and_replace_backup_preservation():
    """Verify write_file and replace_file_content preserve backups in session directory."""
    from src.chatybot.tools.file_utils import write_file, replace_file_content

    with tempfile.TemporaryDirectory() as tmpdir:
        session_root = os.path.join(tmpdir, "sessions")
        active_sess_id = "test_session_123"
        
        # Mock app object with session context
        class MockApp:
            def __init__(self):
                self.session_dir = session_root
                self.active_session_id = active_sess_id
                self.backup_file_on_write = True

        mock_app = MockApp()

        target_file = os.path.join(tmpdir, "workdir", "target.txt")

        # 1. First write on nonexistent file should not create backup
        res1 = write_file(target_file, "version 1 content", app=mock_app)
        assert "Success: Wrote to file" in res1
        assert "backup saved" not in res1
        assert os.path.exists(target_file)

        # 2. Overwriting existing file should create a backup in session backups dir
        res2 = write_file(target_file, "version 2 content", app=mock_app)
        assert "Success: Wrote to file" in res2
        assert "pre-edit backup saved" in res2

        # Check backup content
        expected_backup_dir = os.path.join(session_root, active_sess_id, "backups")
        assert os.path.exists(expected_backup_dir)
        
        # Find the backup file in backup dir tree
        backup_files = []
        for root, dirs, files in os.walk(expected_backup_dir):
            for f in files:
                backup_files.append(os.path.join(root, f))
        
        assert len(backup_files) == 1
        with open(backup_files[0], "r", encoding="utf-8") as bf:
            assert bf.read() == "version 1 content"

        # 3. replace_file_content should save an applicable diff patch
        res3 = replace_file_content(target_file, "version 2", "version 3", app=mock_app)
        assert "Success: Replaced 1 occurrence(s)" in res3
        assert "diff patch saved" in res3

        expected_diff_dir = os.path.join(session_root, active_sess_id, "diffs")
        assert os.path.exists(expected_diff_dir)
        diff_files = []
        for root, dirs, files in os.walk(expected_diff_dir):
            for f in files:
                if f.endswith(".patch"):
                    diff_files.append(os.path.join(root, f))
        assert len(diff_files) == 1
        with open(diff_files[0], "r", encoding="utf-8") as df:
            diff_content = df.read()
            assert "--- a/" in diff_content
            assert "+++ b/" in diff_content
            assert "-version 2 content" in diff_content
            assert "+version 3 content" in diff_content

        # 4. A second write_file preserves the single initial full-copy backup (does not overwrite initial backup)
        res4 = write_file(target_file, "version 4 content", app=mock_app)
        assert "Success: Wrote to file" in res4
        with open(backup_files[0], "r", encoding="utf-8") as bf:
            assert bf.read() == "version 1 content"

        # 5. When backup_file_on_write is False, no backup or diff is made
        mock_app.backup_file_on_write = False
        res5 = replace_file_content(target_file, "version 4", "version 5", app=mock_app)
        assert "Success: Replaced 1 occurrence(s)" in res5
        assert "diff patch saved" not in res5


def test_backup_unnamed_session_and_history_off():
    """Verify backups are in session dir even when unnamed, and only in global backup dir if history is off."""
    from src.chatybot.tools.file_utils import write_file

    with tempfile.TemporaryDirectory() as tmpdir:
        session_root = os.path.join(tmpdir, "sessions")
        target_file = os.path.join(tmpdir, "target.txt")

        # 1. Unnamed session (active_session_id is None, but enable_chat_history is True)
        class MockAppUnnamed:
            def __init__(self):
                self.session_dir = session_root
                self.active_session_id = None
                self.enable_chat_history = True
                self.backup_file_on_write = True

        app_unnamed = MockAppUnnamed()
        write_file(target_file, "initial text", app=app_unnamed)
        res = write_file(target_file, "updated text", app=app_unnamed)
        assert "pre-edit backup saved" in res
        # Check that backup is located under sessions/, NOT directly under backups/
        backup_path = res.split("pre-edit backup saved: '")[1].split("'")[0]
        assert backup_path.startswith(session_root)
        assert "/backups/" in backup_path
        with open(backup_path, "r", encoding="utf-8") as bf:
            assert bf.read() == "initial text"

        # 2. History collection OFF (/session history off) -> should go to global backups directory
        class MockAppHistoryOff:
            def __init__(self):
                self.session_dir = session_root
                self.active_session_id = "test_sess"
                self.enable_chat_history = False
                self.backup_file_on_write = True

        app_hist_off = MockAppHistoryOff()
        res_off = write_file(target_file, "history off update", app=app_hist_off)
        assert "pre-edit backup saved" in res_off
        backup_path_off = res_off.split("pre-edit backup saved: '")[1].split("'")[0]
        global_backup_dir = os.path.join(os.path.dirname(session_root), "backups")
        assert backup_path_off.startswith(global_backup_dir)
        with open(backup_path_off, "r", encoding="utf-8") as bf:
            assert bf.read() == "updated text"

        # 3. Environment variable fallback (when app is None, e.g. from dispatcher subprocess)
        os.environ["CHATYBOT_SESSION_DIR"] = session_root
        os.environ["CHATYBOT_ACTIVE_SESSION_ID"] = "env_sess_456"
        os.environ["CHATYBOT_ENABLE_CHAT_HISTORY"] = "1"
        os.environ["CHATYBOT_BACKUP_ON_WRITE"] = "1"
        try:
            res_env = write_file(target_file, "subprocess update", app=None)
            assert "pre-edit backup saved" in res_env
            backup_path_env = res_env.split("pre-edit backup saved: '")[1].split("'")[0]
            assert backup_path_env.startswith(os.path.join(session_root, "env_sess_456", "backups"))
        finally:
            os.environ.pop("CHATYBOT_SESSION_DIR", None)
            os.environ.pop("CHATYBOT_ACTIVE_SESSION_ID", None)
            os.environ.pop("CHATYBOT_ENABLE_CHAT_HISTORY", None)

def test_get_relative_backup_target():
    """Verify _get_relative_backup_target handles drive letters and normal POSIX paths without losing colons."""
    from src.chatybot.tools.file_utils import _get_relative_backup_target

    # Standard POSIX absolute path
    posix_path = "/Users/jon/project/file.txt"
    assert _get_relative_backup_target(posix_path) == "Users/jon/project/file.txt"

    # Windows-style path with drive letter
    win_path = "C:\\Users\\jon\\project\\file.txt"
    rel_win = _get_relative_backup_target(win_path)
    assert "C:" not in rel_win
    assert rel_win.startswith("C")

    # POSIX path with colon in filename should NOT strip the colon
    posix_colon = "/tmp/my:file.txt"
    assert _get_relative_backup_target(posix_colon) == "tmp/my:file.txt"
