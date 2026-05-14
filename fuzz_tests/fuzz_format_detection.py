#!/usr/bin/env python3
"""
Atheris Fuzzer for BufferManager format detection functions.

Tests:
- File extension parsing
- MIME type detection logic
- Edge cases in extension handling

Usage:
    python fuzz_format_detection.py [-atheris_runs=N] [-max_len=N]
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.chatybot.buffer_manager import BufferManager

import atheris
atheris.instrument_all()


def TestOneInput(data: bytes):
    """Test format detection with fuzzed file paths."""
    bm = BufferManager()
    
    # Decode input - let ValueError propagate to Atheris
    try:
        path_str = data.decode('utf-8')
    except UnicodeDecodeError:
        try:
            path_str = data.decode('latin-1')
        except UnicodeDecodeError:
            path_str = data.decode('utf-8', errors='replace')
    
    # Test image format detection
    try:
        mime = bm.detect_image_format(path_str)
        if mime:
            _ = mime.encode('utf-8')
    except ValueError:
        pass  # Expected for unsupported formats
    
    # Test audio format detection
    try:
        mime = bm.detect_audio_format(path_str)
        if mime:
            _ = mime.encode('utf-8')
    except ValueError:
        pass  # Expected for unsupported formats


def main():
    os.makedirs("corpus", exist_ok=True)
    atheris.Setup(sys.argv, TestOneInput)
    atheris.Fuzz()


if __name__ == "__main__":
    main()
