#!/usr/bin/env python3
"""
Unit tests for extract_code module
"""

import pytest
import tempfile
import os
from src.chatybot.extract_code import is_code_file, extract_code_blocks, process_file


class TestExtractCode:
    """Test suite for extract_code functions"""
    
    @pytest.fixture
    def temp_python_file(self):
        """Create a temporary Python file for testing"""
        python_content = '''"""
This is a Python file
"""

def hello_world():
    """Print hello world"""
    print("Hello, World!")
    
if __name__ == "__main__":
    hello_world()
'''
        
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.py') as f:
            f.write(python_content)
            f.flush()
            yield f.name
        os.unlink(f.name)
    
    @pytest.fixture
    def temp_markdown_file(self):
        """Create a temporary Markdown file for testing"""
        markdown_content = '''# Markdown File

This is a markdown file with code blocks:

```python
def hello():
    print("Hello")
```

Some more text here.

```javascript
console.log("JavaScript code");
```
'''
        
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.md') as f:
            f.write(markdown_content)
            f.flush()
            yield f.name
        os.unlink(f.name)
    
    @pytest.fixture
    def temp_text_file(self):
        """Create a temporary text file for testing"""
        text_content = "This is a plain text file with no code content."
        
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
            f.write(text_content)
            f.flush()
            yield f.name
        os.unlink(f.name)
    
    def test_is_code_file_python(self, temp_python_file):
        """Test that Python file is detected as code"""
        assert is_code_file(temp_python_file) is True
    
    def test_is_code_file_markdown(self, temp_markdown_file):
        """Test that Markdown file is not detected as code"""
        assert is_code_file(temp_markdown_file) is False
    
    def test_is_code_file_text(self, temp_text_file):
        """Test that text file is not detected as code"""
        assert is_code_file(temp_text_file) is False
    
    def test_is_code_file_nonexistent(self):
        """Test that nonexistent file returns False"""
        assert is_code_file("/nonexistent/file.py") is False
    
    def test_is_code_file_empty(self):
        """Test that empty file returns False"""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.py') as f:
            f.write("")
            f.flush()
            empty_file = f.name
        
        assert is_code_file(empty_file) is False
        os.unlink(empty_file)
    
    def test_extract_code_blocks_markdown(self, temp_markdown_file):
        """Test extracting code blocks from markdown"""
        code_blocks, non_code_content = extract_code_blocks(temp_markdown_file)
        
        assert len(code_blocks) == 2
        assert "def hello():" in code_blocks[0]
        assert "console.log" in code_blocks[1]
        assert "# Markdown File" in non_code_content
        assert "Some more text here" in non_code_content
        assert "```python" not in non_code_content
        assert "```javascript" not in non_code_content
    
    def test_extract_code_blocks_no_blocks(self, temp_text_file):
        """Test extracting code blocks from file with no blocks"""
        code_blocks, non_code_content = extract_code_blocks(temp_text_file)
        
        assert len(code_blocks) == 0
        assert non_code_content == "This is a plain text file with no code content."
    
    def test_extract_code_blocks_python(self, temp_python_file):
        """Test extracting code blocks from Python file"""
        code_blocks, non_code_content = extract_code_blocks(temp_python_file)
        
        # Python files don't have markdown-style code blocks, so should return empty
        assert len(code_blocks) == 0
        assert non_code_content == '''"""
This is a Python file
"""

def hello_world():
    """Print hello world"""
    print("Hello, World!")
    
if __name__ == "__main__":
    hello_world()
'''
    
    def test_process_file_code_file(self, temp_python_file):
        """Test processing a code file"""
        # Create a backup of the original file
        with open(temp_python_file, 'r') as f:
            original_content = f.read()
        
        process_file(temp_python_file)
        
        # File should be unchanged since it's a code file without markdown blocks
        with open(temp_python_file, 'r') as f:
            processed_content = f.read()
        
        assert processed_content == original_content
        
        # Check if notes file was created (it shouldn't be for code files without blocks)
        notes_file = temp_python_file.replace('.py', '')
        notes_file = f"notes_{os.path.basename(notes_file)}.py"
        notes_file = os.path.join(os.path.dirname(temp_python_file), notes_file)
        
        assert not os.path.exists(notes_file)
    
    def test_process_file_markdown_file(self, temp_markdown_file, capsys):
        """Test processing a markdown file with code blocks"""
        process_file(temp_markdown_file)
        
        # Markdown files are not detected as code files, so they should be skipped
        captured = capsys.readouterr()
        assert "Skipping non-code file" in captured.out
        
        # Original file should remain unchanged
        with open(temp_markdown_file, 'r') as f:
            processed_content = f.read()
        
        assert "# Markdown File" in processed_content
        assert "```python" in processed_content
        assert "```javascript" in processed_content
    
    def test_process_file_non_code_file(self, temp_text_file, capsys):
        """Test processing a non-code file"""
        process_file(temp_text_file)
        
        captured = capsys.readouterr()
        assert "Skipping non-code file" in captured.out


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
