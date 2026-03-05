#!/usr/bin/env python3
"""
Unit tests for BufferManager module
"""

import pytest
import tempfile
import os
from src.chatybot.buffer_manager import BufferManager


class TestBufferManager:
    """Test suite for BufferManager class"""
    
    @pytest.fixture
    def manager(self):
        """Create a fresh BufferManager instance for each test"""
        return BufferManager()
    
    @pytest.fixture
    def temp_file(self):
        """Create a temporary file for testing"""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
            f.write("Test content for buffer manager")
            f.flush()
            yield f.name
        os.unlink(f.name)
    
    def test_initialization(self, manager):
        """Test that BufferManager initializes correctly"""
        assert manager.file_buffer == ""
        assert manager.prompt_buffer == ""
        assert len(manager.file_banks) == 5
        assert all(name == f"filebank{i}" for i, name in enumerate(manager.file_banks, 1))
        assert manager.script_vars == {}
    
    def test_load_file_to_buffer(self, manager, temp_file):
        """Test loading file to buffer"""
        manager.load_file_to_buffer(temp_file)
        assert manager.file_buffer == "Test content for buffer manager"
    
    def test_load_file_to_buffer_nonexistent(self, manager):
        """Test loading nonexistent file raises exception"""
        with pytest.raises(Exception):
            manager.load_file_to_buffer("/nonexistent/file.txt")
    
    def test_clear_file_buffer(self, manager, temp_file):
        """Test clearing file buffer"""
        manager.load_file_to_buffer(temp_file)
        manager.clear_file_buffer()
        assert manager.file_buffer == ""
    
    def test_show_file_buffer(self, manager, temp_file, capsys):
        """Test showing file buffer content"""
        manager.load_file_to_buffer(temp_file)
        manager.show_file_buffer()
        captured = capsys.readouterr()
        assert "Test content for buffer manager" in captured.out
    
    def test_show_file_buffer_empty(self, manager, capsys):
        """Test showing empty file buffer"""
        manager.show_file_buffer()
        captured = capsys.readouterr()
        assert "File buffer is empty" in captured.out
    
    def test_load_file_to_bank(self, manager, temp_file):
        """Test loading file to bank"""
        manager.load_file_to_bank(1, temp_file)
        assert manager.file_banks["filebank1"] == "Test content for buffer manager"
    
    def test_load_file_to_bank_invalid(self, manager, temp_file):
        """Test loading file to invalid bank number"""
        with pytest.raises(ValueError):
            manager.load_file_to_bank(0, temp_file)
        with pytest.raises(ValueError):
            manager.load_file_to_bank(6, temp_file)
    
    def test_clear_file_bank(self, manager, temp_file):
        """Test clearing file bank"""
        manager.load_file_to_bank(2, temp_file)
        manager.clear_file_bank(2)
        assert manager.file_banks["filebank2"] == ""
    
    def test_clear_file_bank_invalid(self, manager):
        """Test clearing invalid file bank"""
        with pytest.raises(ValueError):
            manager.clear_file_bank(0)
    
    def test_show_file_bank(self, manager, temp_file, capsys):
        """Test showing file bank content"""
        manager.load_file_to_bank(3, temp_file)
        manager.show_file_bank(3)
        captured = capsys.readouterr()
        assert "Test content for buffer manager" in captured.out
    
    def test_show_file_bank_empty(self, manager, capsys):
        """Test showing empty file bank"""
        manager.show_file_bank(1)
        captured = capsys.readouterr()
        assert "filebank1 is empty" in captured.out
    
    def test_show_file_bank_invalid(self, manager):
        """Test showing invalid file bank"""
        with pytest.raises(ValueError):
            manager.show_file_bank(0)
    
    def test_set_script_var(self, manager):
        """Test setting script variable"""
        manager.set_script_var("test_var", "test_value")
        assert manager.script_vars["test_var"] == "test_value"
    
    def test_replace_placeholders(self, manager, temp_file):
        """Test replacing placeholders in prompt"""
        manager.load_file_to_bank(1, temp_file)
        manager.set_script_var("test_var", "variable_value")
        
        prompt = "Content: {filebank1}, Variable: ${test_var}"
        result = manager.replace_placeholders(prompt)
        
        assert "Test content for buffer manager" in result
        assert "variable_value" in result
        assert "{filebank1}" not in result
        assert "${test_var}" not in result
    
    def test_replace_placeholders_no_placeholders(self, manager):
        """Test replacing placeholders when none exist"""
        prompt = "Regular prompt without placeholders"
        result = manager.replace_placeholders(prompt)
        assert result == prompt
    
    def test_show_memory_usage(self, manager, temp_file, capsys):
        """Test showing memory usage"""
        manager.load_file_to_buffer(temp_file)
        manager.load_file_to_bank(1, temp_file)
        manager.set_script_var("test_var", "test_value")
        
        manager.show_memory_usage()
        captured = capsys.readouterr()
        
        assert "FILE_BUFFER" in captured.out
        assert "filebank1" in captured.out
        assert "test_var" in captured.out
        assert "Size (KB)" in captured.out
    
    def test_dump_variables_all(self, manager, temp_file, capsys):
        """Test dumping all variables"""
        manager.load_file_to_buffer(temp_file)
        manager.load_file_to_bank(1, temp_file)
        manager.set_script_var("test_var", "test_value")
        
        manager.dump_variables("all")
        captured = capsys.readouterr()
        
        assert "FILE_BUFFER:" in captured.out
        assert "FILEBANK1:" in captured.out
        assert "SCRIPT_VAR 'test_var'" in captured.out
    
    def test_dump_variables_single(self, manager, temp_file, capsys):
        """Test dumping single variable"""
        manager.load_file_to_buffer(temp_file)
        manager.set_script_var("test_var", "test_value")
        
        manager.dump_variables("file_buffer")
        captured = capsys.readouterr()
        assert "FILE_BUFFER:" in captured.out
        
        manager.dump_variables("test_var")
        captured = capsys.readouterr()
        assert "SCRIPT_VAR 'test_var'" in captured.out
    
    def test_dump_variables_invalid(self, manager, capsys):
        """Test dumping invalid variable"""
        manager.dump_variables("nonexistent")
        captured = capsys.readouterr()
        assert "Error: Variable 'nonexistent' not found" in captured.out


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
