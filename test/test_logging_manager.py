#!/usr/bin/env python3
"""
Unit tests for LoggingManager module
"""

import pytest
import tempfile
import os
from datetime import datetime
from src.chatybot.logging_manager import LoggingManager


class TestLoggingManager:
    """Test suite for LoggingManager class"""
    
    @pytest.fixture
    def manager(self):
        """Create a fresh LoggingManager instance for each test"""
        return LoggingManager()
    
    def test_initialization(self, manager):
        """Test that LoggingManager initializes correctly"""
        assert manager.logging_active is False
        assert manager.log_file is None
    
    def test_start_logging(self, manager):
        """Test starting logging"""
        manager.start_logging()
        assert manager.logging_active is True
        assert manager.log_file is not None
        
        # Check if log file was created
        log_files = [f for f in os.listdir('.') if f.startswith('chatybot.log.')]
        assert len(log_files) > 0
        
        # Clean up
        for log_file in log_files:
            os.unlink(log_file)
    
    def test_start_logging_already_active(self, manager):
        """Test starting logging when already active"""
        manager.start_logging()
        
        # Try to start again
        manager.start_logging()
        
        # Should still be active and have the same file
        assert manager.logging_active is True
        assert manager.log_file is not None
        
        # Clean up
        log_files = [f for f in os.listdir('.') if f.startswith('chatybot.log.')]
        for log_file in log_files:
            os.unlink(log_file)
    
    def test_stop_logging(self, manager):
        """Test stopping logging"""
        manager.start_logging()
        manager.stop_logging()
        
        assert manager.logging_active is False
        # Note: log_file is not set to None after closing, just the file is closed
        assert manager.log_file.closed is True
        
        # Clean up
        log_files = [f for f in os.listdir('.') if f.startswith('chatybot.log.')]
        for log_file in log_files:
            os.unlink(log_file)
    
    def test_stop_logging_not_active(self, manager):
        """Test stopping logging when not active"""
        manager.stop_logging()
        
        assert manager.logging_active is False
        assert manager.log_file is None
    
    def test_format_datetime(self, manager):
        """Test formatting datetime"""
        test_datetime = datetime(2023, 1, 15, 14, 30, 45)
        formatted = manager.format_datetime(test_datetime)
        
        assert "Jan 15, 2023" in formatted
        assert "02:30:45 PM" in formatted
    
    def test_log_message_active(self, manager, capsys):
        """Test logging message when logging is active"""
        manager.start_logging()
        
        test_message = "This is a test message"
        manager.log_message(test_message)
        
        # Check if message was written to file
        log_files = [f for f in os.listdir('.') if f.startswith('chatybot.log.')]
        assert len(log_files) > 0
        
        with open(log_files[0], 'r') as f:
            log_content = f.read()
        
        assert test_message in log_content
        assert "Jan" in log_content or "Feb" in log_content or "Mar" in log_content  # Month
        
        manager.stop_logging()
        
        # Clean up
        for log_file in log_files:
            os.unlink(log_file)
    
    def test_log_message_not_active(self, manager):
        """Test logging message when logging is not active"""
        test_message = "This is a test message"
        manager.log_message(test_message)
        
        # Should not create any log files
        log_files = [f for f in os.listdir('.') if f.startswith('chatybot.log.')]
        assert len(log_files) == 0
    
    def test_log_message_multiple(self, manager):
        """Test logging multiple messages"""
        manager.start_logging()
        
        messages = ["First message", "Second message", "Third message"]
        for msg in messages:
            manager.log_message(msg)
        
        # Check if all messages were written to file
        log_files = [f for f in os.listdir('.') if f.startswith('chatybot.log.')]
        assert len(log_files) > 0
        
        with open(log_files[0], 'r') as f:
            log_content = f.read()
        
        for msg in messages:
            assert msg in log_content
        
        # Should have 3 lines (one per message)
        lines = log_content.strip().split('\n')
        assert len(lines) == 3
        
        manager.stop_logging()
        
        # Clean up
        for log_file in log_files:
            os.unlink(log_file)
    
    def test_log_file_naming(self, manager):
        """Test that log file has correct naming format"""
        manager.start_logging()
        
        log_files = [f for f in os.listdir('.') if f.startswith('chatybot.log.')]
        assert len(log_files) > 0
        
        # Check format: chatybot.log.YYYYMMDD_HHMMSS
        import re
        pattern = r'chatybot\.log\.\d{8}_\d{6}'
        assert re.match(pattern, log_files[0])
        
        manager.stop_logging()
        
        # Clean up
        for log_file in log_files:
            os.unlink(log_file)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
