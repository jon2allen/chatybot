#!/usr/bin/env python3
"""
Test script to verify the refactored code works
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

def test_imports():
    """Test that all modules can be imported"""
    print("Testing imports...")
    
    try:
        from chatybot.config_manager import ConfigManager
        print("✓ ConfigManager imported successfully")
    except Exception as e:
        print(f"✗ ConfigManager import failed: {e}")
        return False
    
    try:
        from chatybot.logging_manager import LoggingManager
        print("✓ LoggingManager imported successfully")
    except Exception as e:
        print(f"✗ LoggingManager import failed: {e}")
        return False
    
    try:
        from chatybot.buffer_manager import BufferManager
        print("✓ BufferManager imported successfully")
    except Exception as e:
        print(f"✗ BufferManager import failed: {e}")
        return False
    
    try:
        from chatybot.chatybot_app import ChatybotApp
        print("✓ ChatybotApp imported successfully")
    except Exception as e:
        print(f"✗ ChatybotApp import failed: {e}")
        return False
    
    return True

def test_config_manager():
    """Test ConfigManager functionality"""
    print("\nTesting ConfigManager...")
    
    try:
        from chatybot.config_manager import ConfigManager
        
        # Test initialization
        cm = ConfigManager()
        print("✓ ConfigManager initialized")
        
        # Test config loading (this might fail if no config file exists, but that's ok)
        try:
            cm.load_config()
            print("✓ Config loaded successfully")
        except FileNotFoundError:
            print("✓ Config loading failed as expected (no config file)")
        except Exception as e:
            print(f"✗ Config loading failed unexpectedly: {e}")
            return False
        
        return True
    except Exception as e:
        print(f"✗ ConfigManager test failed: {e}")
        return False

def test_logging_manager():
    """Test LoggingManager functionality"""
    print("\nTesting LoggingManager...")
    
    try:
        from chatybot.logging_manager import LoggingManager
        
        # Test initialization
        lm = LoggingManager()
        print("✓ LoggingManager initialized")
        
        # Test logging (without actually starting to avoid file creation)
        if lm.logging_active:
            print("✗ Logging should not be active by default")
            return False
        
        print("✓ LoggingManager test passed")
        return True
    except Exception as e:
        print(f"✗ LoggingManager test failed: {e}")
        return False

def test_buffer_manager():
    """Test BufferManager functionality"""
    print("\nTesting BufferManager...")
    
    try:
        from chatybot.buffer_manager import BufferManager
        
        # Test initialization
        bm = BufferManager()
        print("✓ BufferManager initialized")
        
        # Test file buffer operations
        if bm.file_buffer != "":
            print("✗ File buffer should be empty by default")
            return False
        
        bm.file_buffer = "test content"
        if bm.file_buffer != "test content":
            print("✗ File buffer set failed")
            return False
        
        bm.clear_file_buffer()
        if bm.file_buffer != "":
            print("✗ File buffer clear failed")
            return False
        
        print("✓ BufferManager test passed")
        return True
    except Exception as e:
        print(f"✗ BufferManager test failed: {e}")
        return False

def test_chatybot_app():
    """Test ChatybotApp initialization"""
    print("\nTesting ChatybotApp...")
    
    try:
        from chatybot.chatybot_app import ChatybotApp
        
        # Test initialization
        app = ChatybotApp()
        print("✓ ChatybotApp initialized")
        
        # Test that managers are initialized
        if not hasattr(app, 'config_manager'):
            print("✗ config_manager not found")
            return False
        
        if not hasattr(app, 'logging_manager'):
            print("✗ logging_manager not found")
            return False
        
        if not hasattr(app, 'buffer_manager'):
            print("✗ buffer_manager not found")
            return False
        
        print("✓ ChatybotApp test passed")
        return True
    except Exception as e:
        print(f"✗ ChatybotApp test failed: {e}")
        return False

def main():
    """Run all tests"""
    print("Running refactored code tests...\n")
    
    all_passed = True
    
    all_passed &= test_imports()
    all_passed &= test_config_manager()
    all_passed &= test_logging_manager()
    all_passed &= test_buffer_manager()
    all_passed &= test_chatybot_app()
    
    print(f"\n{'='*50}")
    if all_passed:
        print("✓ All tests passed! The refactoring is working correctly.")
    else:
        print("✗ Some tests failed. Please check the output above.")
    print(f"{'='*50}")
    
    return 0 if all_passed else 1

if __name__ == "__main__":
    sys.exit(main())
