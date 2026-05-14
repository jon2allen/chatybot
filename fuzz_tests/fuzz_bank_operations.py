#!/usr/bin/env python3
"""
Atheris Fuzzer for BufferManager bank operations.

Tests:
- Bank number validation (1-5)
- Bank loading with various file types
- Bank clearing
- Bank display
- Script variable operations

Safety: Uses temp directory for all operations

Usage:
    python fuzz_bank_operations.py [-atheris_runs=N] [-max_len=N]
"""

import sys
import os
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.chatybot.buffer_manager import BufferManager

import atheris
atheris.instrument_all()


def TestOneInput(data: bytes):
    """Test bank operations with fuzzed inputs."""
    bm = BufferManager()
    
    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = os.path.join(tmpdir, "test.txt")
        test_image = os.path.join(tmpdir, "test.png")
        
        with open(test_file, "wb") as f:
            f.write(b"file bank test content")
        with open(test_image, "wb") as f:
            f.write(b'\x89PNG\r\n\x1a\n' + data[:100])
        
        # Decode input
        path_str = data.decode('utf-8', errors='replace') if data else ""
        
        # Derive bank number from input hash for better coverage
        bank_num = (hash(path_str) % 5) + 1
        
        # Test file bank operations
        bm.load_file_to_bank(bank_num, test_file)
        bm.show_file_bank(bank_num)
        bm.clear_file_bank(bank_num)
        
        # Test image bank operations
        bm.load_image_to_bank(1, test_image)
        bm.show_image_bank(1)
        bm.clear_image_bank(1)
        
        # Test script variables
        safe_name = ''.join(c if c.isalnum() or c in '_-' else '_' for c in path_str[:50])
        if safe_name and safe_name[0].isalpha():
            bm.set_script_var(safe_name, "test_value")
            bm.dump_variables(safe_name)


def main():
    os.makedirs("corpus", exist_ok=True)
    atheris.Setup(sys.argv, TestOneInput)
    atheris.Fuzz()


if __name__ == "__main__":
    main()
