#!/usr/bin/env python3
"""
Atheris Fuzzer for BufferManager.replace_placeholders()

Target: String parsing and placeholder substitution logic

Tests:
- Normal placeholder replacement ({filebank1}, ${var1})
- Nested braces ({{filebank1}})
- Adjacent placeholders ({filebank1}{filebank2})
- Special characters in content ($, {, })
- Unicode characters
- Empty inputs
- Very long inputs
- Malformed placeholders

Usage:
    python fuzz_placeholders.py [-atheris_runs=N] [-max_len=N]
"""

import sys
import os

# Ensure project is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.chatybot.buffer_manager import BufferManager

# Import atheris and instrument AFTER buffer_manager is imported
import atheris
atheris.instrument_all()


def TestOneInput(data: bytes):
    """Test function called by Atheris for each fuzzed input."""
    bm = BufferManager()
    
    # Set up test data in banks and vars
    bm.file_banks["filebank1"] = "FILEBANK_1_CONTENT"
    bm.file_banks["filebank2"] = "FILEBANK_2_CONTENT"
    bm.file_banks["filebank3"] = "FILEBANK_3_CONTENT"
    bm.file_banks["filebank4"] = "FILEBANK_4_CONTENT"
    bm.file_banks["filebank5"] = "FILEBANK_5_CONTENT"
    
    bm.script_vars["var1"] = "SCRIPT_VAR_1_VALUE"
    bm.script_vars["var2"] = "SCRIPT_VAR_2_VALUE"
    bm.script_vars["var3"] = "SCRIPT_VAR_3_VALUE"
    bm.script_vars["var4"] = "SCRIPT_VAR_4_VALUE"
    bm.script_vars["var5"] = "SCRIPT_VAR_5_VALUE"
    
    # Decode input - let exceptions propagate to Atheris
    try:
        input_str = data.decode('utf-8')
    except UnicodeDecodeError:
        try:
            input_str = data.decode('latin-1')
        except UnicodeDecodeError:
            input_str = data.decode('utf-8', errors='replace')
    
    # Test replace_placeholders with images
    result_text, images = bm.replace_placeholders(input_str, include_images=True)
    if result_text:
        _ = len(result_text)
        _ = result_text.encode('utf-8')
    
    # Test replace_placeholders without images
    result_text, images = bm.replace_placeholders(input_str, include_images=False)
    
    # Test legacy method
    result_text = bm.replace_placeholders_legacy(input_str)


def main():
    os.makedirs("corpus", exist_ok=True)
    atheris.Setup(sys.argv, TestOneInput)
    atheris.Fuzz()


if __name__ == "__main__":
    main()
