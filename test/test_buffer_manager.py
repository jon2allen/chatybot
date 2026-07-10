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
        """Test replacing placeholders in prompt - returns (text, image_list)"""
        manager.load_file_to_bank(1, temp_file)
        manager.set_script_var("test_var", "variable_value")
        
        prompt = "Content: {filebank1}, Variable: ${test_var}"
        text, images = manager.replace_placeholders(prompt)
        
        assert "Test content for buffer manager" in text
        assert "variable_value" in text
        assert "{filebank1}" not in text
        assert "${test_var}" not in text
        assert images == []  # No images in this test
    
    def test_replace_placeholders_no_placeholders(self, manager):
        """Test replacing placeholders when none exist - returns (text, [])"""
        prompt = "Regular prompt without placeholders"
        text, images = manager.replace_placeholders(prompt)
        assert text == prompt
        assert images == []
    
    def test_replace_placeholders_legacy(self, manager, temp_file):
        """Test legacy method returns string only"""
        manager.load_file_to_bank(1, temp_file)
        
        prompt = "Content: {filebank1}"
        result = manager.replace_placeholders_legacy(prompt)
        
        assert isinstance(result, str)
        assert "Test content for buffer manager" in result
        assert "{filebank1}" not in result

    def test_replace_placeholders_clear_unresolved(self, manager):
        """Test that replace_placeholders_legacy clears unresolved placeholders when clear_unresolved is True (default)"""
        prompt = "save to ${z} and {y[1]} and $x"
        result = manager.replace_placeholders_legacy(prompt)
        assert result == "save to and and"

        result_keep = manager.replace_placeholders_legacy(prompt, clear_unresolved=False)
        assert result_keep == prompt
    
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

    def test_show_memory_usage_with_search_buffer(self, manager, capsys):
        """Test showing memory usage with search buffer"""
        search_buffer = [{"id": 1, "content": "test content"}]
        manager.show_memory_usage(search_buffer=search_buffer)
        captured = capsys.readouterr()
        assert "SEARCH_BUFFER" in captured.out

    def test_dump_variables_search_buffer(self, manager, capsys):
        """Test dumping search buffer"""
        search_buffer = [{"id": 1, "content": "test content"}]
        manager.dump_variables("search_buffer", search_buffer=search_buffer)
        captured = capsys.readouterr()
        assert "SEARCH_BUFFER:" in captured.out
        assert "test content" in captured.out

    def test_protected_variables(self, manager):
        """Test that protected variables cannot be modified by set_script_var unless explicitly allowed"""
        # Test modifying a normal variable works
        assert manager.set_script_var("normal_var", "value") is True
        assert manager.get_script_var("normal_var") == "value"

        # Under user write context, modifying protected variables fails without allow_protected=True
        manager.script_vars._is_user_write = True
        try:
            assert manager.set_script_var("AGENTIC_LOOP", ["record1"]) is False
            assert manager.get_script_var("AGENTIC_LOOP") is None

            # Test modifying protected variables succeeds with allow_protected=True
            assert manager.set_script_var("AGENTIC_LOOP", ["record1"], allow_protected=True) is True
            assert manager.get_script_var("AGENTIC_LOOP") == ["record1"]

            # Test direct assignment raises ValueError
            with pytest.raises(ValueError) as exc_info:
                manager.script_vars["AGENTIC_LOOP"] = ["record2"]
            assert "is a protected variable and cannot be modified" in str(exc_info.value)

            # Test that newly protected variables (like RUN_COMPLETION) are also protected
            assert manager.set_script_var("RUN_COMPLETION", "output") is False
            assert manager.set_script_var("RUN_COMPLETION", "output", allow_protected=True) is True
            assert manager.get_script_var("RUN_COMPLETION") == "output"

            with pytest.raises(ValueError):
                manager.script_vars["RUN_COMPLETION"] = "hack"
        finally:
            manager.script_vars._is_user_write = False


class TestImageBanks:
    """Test suite for Image Bank functionality"""
    
    @pytest.fixture
    def manager(self):
        """Create a fresh BufferManager instance for each test"""
        return BufferManager()
    
    @pytest.fixture
    def jpeg_image(self):
        """Path to a sample JPEG image"""
        return "test_images/test1.jpg"
    
    @pytest.fixture
    def png_image(self):
        """Path to a sample PNG image"""
        return "test_images/test5.png"
    
    def test_image_banks_initialization(self, manager):
        """Test that image banks are initialized"""
        assert len(manager.image_banks) == 5
        assert all(name == f"imagebank{i}" for i, name in enumerate(manager.image_banks, 1))
        assert all(content == "" for content in manager.image_banks.values())
    
    def test_detect_image_format_jpg(self, manager):
        """Test JPEG format detection"""
        assert manager.detect_image_format("test.jpg") == "image/jpeg"
        assert manager.detect_image_format("test.JPG") == "image/jpeg"
    
    def test_detect_image_format_jpeg(self, manager):
        """Test JPEG format detection with .jpeg extension"""
        assert manager.detect_image_format("test.jpeg") == "image/jpeg"
    
    def test_detect_image_format_png(self, manager):
        """Test PNG format detection"""
        assert manager.detect_image_format("test.png") == "image/png"
        assert manager.detect_image_format("test.PNG") == "image/png"
    
    def test_detect_image_format_invalid(self, manager):
        """Test invalid format raises error"""
        with pytest.raises(ValueError) as exc_info:
            manager.detect_image_format("test.gif")
        assert "Unsupported image format" in str(exc_info.value)
    
    def test_load_image_to_bank(self, manager, jpeg_image):
        """Test loading image to bank"""
        manager.load_image_to_bank(1, jpeg_image)
        assert manager.image_banks["imagebank1"].startswith("data:image/jpeg;base64,")
    
    def test_load_image_to_bank_invalid_bank(self, manager, jpeg_image):
        """Test loading image with invalid bank number"""
        with pytest.raises(ValueError) as exc_info:
            manager.load_image_to_bank(0, jpeg_image)
        assert "Invalid imagebank number" in str(exc_info.value)
        
        with pytest.raises(ValueError) as exc_info:
            manager.load_image_to_bank(6, jpeg_image)
        assert "Invalid imagebank number" in str(exc_info.value)
    
    def test_load_png_image(self, manager, png_image):
        """Test loading PNG image"""
        manager.load_image_to_bank(1, png_image)
        assert manager.image_banks["imagebank1"].startswith("data:image/png;base64,")
    
    def test_clear_image_bank(self, manager, jpeg_image):
        """Test clearing image bank"""
        manager.load_image_to_bank(1, jpeg_image)
        assert manager.image_banks["imagebank1"] != ""
        manager.clear_image_bank(1)
        assert manager.image_banks["imagebank1"] == ""
    
    def test_clear_image_bank_invalid(self, manager):
        """Test clearing invalid image bank"""
        with pytest.raises(ValueError) as exc_info:
            manager.clear_image_bank(0)
        assert "Invalid imagebank number" in str(exc_info.value)
    
    def test_show_image_bank_empty(self, manager, capsys):
        """Test showing empty image bank"""
        manager.show_image_bank(1)
        captured = capsys.readouterr()
        assert "imagebank1 is empty" in captured.out
    
    def test_show_image_bank_with_image(self, manager, jpeg_image, capsys):
        """Test showing image bank with loaded image"""
        manager.load_image_to_bank(1, jpeg_image)
        manager.show_image_bank(1)
        captured = capsys.readouterr()
        assert "imagebank1:" in captured.out
        assert "image/jpeg" in captured.out
        assert "KB" in captured.out
    
    def test_replace_placeholders_with_images(self, manager, jpeg_image, png_image):
        """Test placeholder replacement with image banks"""
        manager.load_image_to_bank(1, jpeg_image)
        manager.load_image_to_bank(2, png_image)
        
        prompt = "Describe {imagebank1} and {imagebank2}"
        text, images = manager.replace_placeholders(prompt)
        
        assert "Describe" in text
        assert "{imagebank1}" not in text
        assert "{imagebank2}" not in text
        assert len(images) == 2
        assert images[0]["type"] == "image_url"
        assert images[1]["type"] == "image_url"
        assert "image/jpeg" in images[0]["image_url"]["url"]
        assert "image/png" in images[1]["image_url"]["url"]
    
    def test_replace_placeholders_include_images_false(self, manager, jpeg_image):
        """Test placeholder replacement with include_images=False"""
        manager.load_image_to_bank(1, jpeg_image)
        
        prompt = "Describe {imagebank1}"
        text, images = manager.replace_placeholders(prompt, include_images=False)
        
        assert "Describe {imagebank1}" == text
        assert images == []
    
    def test_memory_usage_with_image_banks(self, manager, jpeg_image, capsys):
        """Test memory usage shows image banks"""
        manager.load_image_to_bank(1, jpeg_image)
        manager.show_memory_usage()
        captured = capsys.readouterr()
        assert "imagebank1" in captured.out
        assert "imagebank2" in captured.out
    
    def test_dump_variables_with_image_banks(self, manager, jpeg_image, capsys):
        """Test dump variables shows image banks"""
        manager.load_image_to_bank(1, jpeg_image)
        manager.dump_variables("all")
        captured = capsys.readouterr()
        assert "IMAGEBANK1:" in captured.out
        assert "<image data>" in captured.out
    
    def test_dump_single_image_bank(self, manager, jpeg_image, capsys):
        """Test dumping single image bank"""
        manager.load_image_to_bank(1, jpeg_image)
        manager.dump_variables("imagebank1")
        captured = capsys.readouterr()
        assert "IMAGEBANK1:" in captured.out
        assert "<image data>" in captured.out


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
