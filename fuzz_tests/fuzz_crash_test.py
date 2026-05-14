#!/usr/bin/env python3
"""
Atheris Fuzzer for BufferManager.fuzz_test_crash()

This fuzzer tests the artificial crash function to verify that
the fuzzing infrastructure correctly detects and saves crashes.

Expected crashes:
- Input starting with b'CRASH1' -> ZeroDivisionError
- Input starting with b'CRASH2' -> IndexError  
- Input starting with b'CRASH3' -> TypeError

Usage:
    python fuzz_crash_test.py [-atheris_runs=N] [-max_len=N]
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.chatybot.buffer_manager import BufferManager

import atheris
atheris.instrument_all()


def TestOneInput(data: bytes):
    """Test the artificial crash function with fuzzed inputs."""
    bm = BufferManager()
    
    # This will crash on inputs starting with CRASH1, CRASH2, CRASH3
    bm.fuzz_test_crash(data)


def main():
    os.makedirs("corpus", exist_ok=True)
    atheris.Setup(sys.argv, TestOneInput)
    atheris.Fuzz()


if __name__ == "__main__":
    main()
