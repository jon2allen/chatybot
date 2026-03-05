#!/usr/bin/env python3
"""
Simple script to run all tests in the test directory
"""

import subprocess
import sys
import os


def run_tests():
    """Run all pytest tests in the test directory"""
    print("Running all tests...")
    
    # Change to the project root directory
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    os.chdir(project_root)
    
    # Run pytest
    result = subprocess.run([
        sys.executable, "-m", "pytest", 
        "test/", 
        "-v", 
        "--tb=short"
    ], capture_output=False)
    
    return result.returncode


if __name__ == "__main__":
    exit_code = run_tests()
    sys.exit(exit_code)
