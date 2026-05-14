#!/usr/bin/env python3
"""
Atheris Fuzzer for BufferManager file loading functions.

Tests:
- Path validation and sanitization
- File I/O operations
- Error handling for various file scenarios
- Path traversal resistance

Safety: All file operations use temp directory

Usage:
    python fuzz_file_loading.py [-atheris_runs=N] [-max_len=N]
"""

import sys
import os
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.chatybot.buffer_manager import BufferManager

import atheris
atheris.instrument_all()


def TestOneInput(data: bytes):
    """Test file loading methods with fuzzed inputs."""
    bm = BufferManager()

    print("bytes: ", data.decode('utf-8', errors='replace'))
    
    with tempfile.TemporaryDirectory() as tmpdir:
        # Test 1: Load directly from a file we write
        test_path = os.path.join(tmpdir, "fuzz_test.txt")
        with open(test_path, "wb") as f:
            f.write(data)
        
        bm.load_file_to_buffer(test_path)
        bm.clear_file_buffer()
        
        for bank_num in range(1, 6):
            bm.load_file_to_bank(bank_num, test_path)
            bm.clear_file_bank(bank_num)
        
        # Test 2: Try to construct path from fuzz data
        print( "test2 .... test2 ")
        path_str = data.decode('utf-8', errors='replace')
        
        # Strict path validation - only allow safe characters
        if (path_str and 
            all(c.isalnum() or c in '_-. ' for c in path_str) and
            not path_str.startswith('/') and
            '..' not in path_str):
            
            full_path = os.path.join(tmpdir, path_str)
            # Final safety check - must be within temp dir
            if os.path.abspath(full_path).startswith(tmpdir):
                bm.load_file_to_buffer(full_path)


def main():
    os.makedirs("corpus", exist_ok=True)
    atheris.Setup(sys.argv, TestOneInput)
    atheris.Fuzz()


if __name__ == "__main__":
    main()
