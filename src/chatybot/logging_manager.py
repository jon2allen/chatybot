#! /usr/bin/env python3
"""
Logging Manager Module
Handles logging functionality for the application

Uses pyio-intercept for thread-safe stdout interception with middleware chains.
"""

import os
import sys
import threading
import unicodedata
from datetime import datetime
from typing import Optional

try:
    from pyio_intercept import StdoutIntercept
    PYIO_INTERCEPT_AVAILABLE = True
except ImportError:
    PYIO_INTERCEPT_AVAILABLE = False


class LoggingManager:
    """Manages logging to files with timestamps."""
    
    def __init__(self):
        self.logging_active: bool = False
        self.hex_mode: bool = False
        self.log_file: Optional[object] = None
        self.buffer = []
        self._lock = threading.Lock()
        
        # Store original stdout
        self.original_stdout = sys.stdout
        self._intercept_instance = None
        self.interceptor = None  # Backward compatibility: expose interceptor
        
        # Install interceptor using pyio-intercept if available
        self._install_interceptor()
    
    def _install_interceptor(self):
        """Install stdout interceptor using pyio-intercept or fallback to custom implementation."""
        if PYIO_INTERCEPT_AVAILABLE and not os.environ.get("PYTEST_CURRENT_TEST"):
            import weakref
            self_weak = weakref.ref(self)
            # Create logging action for pyio-intercept
            def logging_action(payload, next_action, context):
                # Pass through to original stdout first (preserve console output)
                result = next_action(payload)
                
                manager = self_weak()
                if manager is None:
                    return result
                
                # Buffer for logging
                with manager._lock:
                    manager.buffer.append(payload)
                    
                    # Write to file if a newline is encountered and logging is active
                    if "\n" in payload:
                        full_line = "".join(manager.buffer).rstrip("\n")
                        if full_line.strip() and manager.logging_active:
                            manager.log_message(full_line)
                        manager.buffer.clear()
                
                return result
            
            # Create and install the interceptor
            self._intercept_instance = StdoutIntercept(actions=[logging_action])
            self._intercept_instance.install()
            
            # For backward compatibility, expose the proxy as the interceptor
            # The proxy is what's installed on sys.stdout and has the write method
            self.interceptor = self._intercept_instance._proxy
            print("[LoggingManager] Using pyio-intercept for stdout interception (thread-safe)")
        else:
            # Fallback to custom implementation if pyio-intercept not available
            self.interceptor = _FallbackStdoutInterceptor(sys.stdout, self)
            sys.stdout = self.interceptor
            print("[LoggingManager] WARNING: pyio-intercept not available, using fallback implementation")
    
    def __del__(self):
        """Restore original stdout when manager is destroyed."""
        if PYIO_INTERCEPT_AVAILABLE and self._intercept_instance:
            self._intercept_instance.uninstall()
        elif not PYIO_INTERCEPT_AVAILABLE and hasattr(self, 'interceptor') and self.interceptor:
            # Fallback cleanup
            if sys.stdout is self.interceptor:
                sys.stdout = self.original_stdout
    
    def start_logging(self, hex_mode: bool = False) -> None:
        """
        Start logging to a file with a timestamp.

        Args:
            hex_mode: If True, non-printable/control characters will be converted to hex escapes.
        """
        if not self.logging_active:
            self.hex_mode = hex_mode
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            log_filename = f"chatybot.log.{timestamp}"
            self.log_file = open(log_filename, "w", encoding="utf-8")
            self.logging_active = True
            hex_note = " (hex mode enabled)" if self.hex_mode else ""
            print(f"Logging started{hex_note}. Writing to '{log_filename}'.")
        else:
            # Logging is already active: only update hex_mode when the caller
            # explicitly requests it, so re-running `/logging start` (without
            # `hex`) does not silently disable an active hex mode.
            if hex_mode and not self.hex_mode:
                self.hex_mode = True
                print("Logging is already active. Hex mode is now enabled.")
            else:
                hex_note = "enabled" if self.hex_mode else "disabled"
                print(f"Logging is already active. Hex mode remains {hex_note}.")
    
    def stop_logging(self) -> None:
        """
        Stop logging and close the log file.
        """
        if self.logging_active and self.log_file:
            self.log_file.close()
            self.logging_active = False
            self.hex_mode = False
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
    
    @staticmethod
    def format_hex_escapes(text: str) -> str:
        """
        Convert unprintable ASCII control characters, escape codes, and invisible
        Unicode code points into human-readable hex brackets like [0x1B] or [U+200B].

        Preserves standard whitespace (newlines, tabs) and printable characters.
        """
        out = []
        for ch in text:
            code = ord(ch)
            if ch in ("\n", "\t"):
                out.append(ch)
            elif 32 <= code <= 126:
                out.append(ch)
            elif code < 32 or (127 <= code <= 159):
                out.append(f"[0x{code:02X}]")
            else:
                cat = unicodedata.category(ch)
                # Check for invisible/control/format/surrogate/private-use/unassigned
                # Unicode, plus line/paragraph separators (Zl/Zp) which act as line
                # breaks in many viewers and would corrupt the one-line-per-entry
                # log format that hex mode is meant to make visible.
                if cat in ("Cc", "Cf", "Cs", "Co", "Cn", "Zl", "Zp"):
                    # Use the conventional variable-width U+ notation (no leading
                    # zeros beyond the 4-digit BMP minimum) so supplementary-plane
                    # code points render as [U+E0001], not [U+0E0001].
                    if code <= 0xFFFF:
                        out.append(f"[U+{code:04X}]")
                    else:
                        out.append(f"[U+{code:5X}]")
                else:
                    out.append(ch)
        return "".join(out)
    
    def log_message(self, message: str) -> None:
        """
        Log a message to the log file if logging is active.
        
        Args:
            message: Message to log
        """
        if self.logging_active and self.log_file:
            if self.hex_mode:
                message = self.format_hex_escapes(message)
            timestamp = self.format_datetime(datetime.now())
            self.log_file.write(f"{timestamp} - {message}\n")
            self.log_file.flush()


class _FallbackStdoutInterceptor:
    """Fallback interceptor when pyio-intercept is not available.
    
    Maintains backward compatibility with the original implementation.
    """
    def __init__(self, original_stdout, logging_manager):
        self.stdout = original_stdout
        import weakref
        self._logging_manager_ref = weakref.ref(logging_manager)
        self.buffer = []

    def write(self, message: str):
        # 1. Output to physical console (preserve layout, colors, margins)
        self.stdout.write(message)
        
        # 2. Buffer for logging
        self.buffer.append(message)
        
        # 3. Write to file if a newline is encountered and logging is active
        if "\n" in message:
            manager = self._logging_manager_ref()
            if manager is not None:
                full_line = "".join(self.buffer).rstrip("\n")
                if full_line.strip() and manager.logging_active:
                    manager.log_message(full_line)
            self.buffer.clear()

    def flush(self):
        self.stdout.flush()

    def __getattr__(self, name):
        return getattr(self.stdout, name)
