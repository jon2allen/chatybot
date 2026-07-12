#! /usr/bin/env python3
"""
Logging Manager Module
Handles logging functionality for the application
"""

import os
import sys
from datetime import datetime
from typing import Optional


class StdoutLoggingInterceptor:
    """Intercepts and buffers stdout writes to log complete lines to the active log file."""
    def __init__(self, original_stdout, logging_manager):
        self.stdout = original_stdout
        self.logging_manager = logging_manager
        self.buffer = []

    def write(self, message: str):
        # 1. Output to physical console (preserve layout, colors, margins)
        self.stdout.write(message)
        
        # 2. Buffer for logging
        self.buffer.append(message)
        
        # 3. Write to file if a newline is encountered and logging is active
        if "\n" in message:
            full_line = "".join(self.buffer).rstrip("\n")
            if full_line.strip() and self.logging_manager.logging_active:
                self.logging_manager.log_message(full_line)
            self.buffer.clear()

    def flush(self):
        self.stdout.flush()


class LoggingManager:
    """Manages logging to files with timestamps."""
    
    def __init__(self):
        self.logging_active: bool = False
        self.log_file: Optional[object] = None
        # Hook sys.stdout to our interceptor to capture all console print outputs
        self.original_stdout = sys.stdout
        self.interceptor = StdoutLoggingInterceptor(sys.stdout, self)
        sys.stdout = self.interceptor

    def __del__(self):
        """Restore original stdout when manager is destroyed."""
        if hasattr(self, 'original_stdout') and sys.stdout is self.interceptor:
            sys.stdout = self.original_stdout
    
    def start_logging(self) -> None:
        """
        Start logging to a file with a timestamp.
        """
        if not self.logging_active:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            log_filename = f"chatybot.log.{timestamp}"
            self.log_file = open(log_filename, "w")
            self.logging_active = True
            print(f"Logging started. Writing to '{log_filename}'.")
    
    def stop_logging(self) -> None:
        """
        Stop logging and close the log file.
        """
        if self.logging_active and self.log_file:
            self.log_file.close()
            self.logging_active = False
            print("Logging stopped.")
    
    def format_datetime(self, dt: datetime) -> str:
        """
        Format datetime in local time with timezone.
        
        Args:
            dt: Datetime object to format
            
        Returns:
            Formatted datetime string
        """
        return dt.strftime("%b %d, %Y, %I:%M:%S %p %Z")
    
    def log_message(self, message: str) -> None:
        """
        Log a message to the log file if logging is active.
        
        Args:
            message: Message to log
        """
        if self.logging_active and self.log_file:
            timestamp = self.format_datetime(datetime.now())
            self.log_file.write(f"{timestamp} - {message}\n")
            self.log_file.flush()
