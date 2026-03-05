#! /usr/bin/env python3
"""
Logging Manager Module
Handles logging functionality for the application
"""

import os
from datetime import datetime
from typing import Optional


class LoggingManager:
    """Manages logging to files with timestamps."""
    
    def __init__(self):
        self.logging_active: bool = False
        self.log_file: Optional[object] = None
    
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
