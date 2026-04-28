#! /usr/bin/env python3
"""
Buffer Manager Module
Manages file buffers, file banks, script variables, and image banks
"""

import base64
from pathlib import Path
from typing import Dict, List, Optional, Tuple


class BufferManager:
    """Manages file buffers, file banks, script variables, image banks, and audio banks."""
    
    def __init__(self):
        self.file_buffer: str = ""
        self.prompt_buffer: str = ""
        self.file_banks: Dict[str, str] = {f"filebank{i}": "" for i in range(1, 6)}
        self.image_banks: Dict[str, str] = {f"imagebank{i}": "" for i in range(1, 6)}
        self.audio_banks: Dict[str, str] = {f"audiobank{i}": "" for i in range(1, 6)}
        self.script_vars: Dict[str, str] = {}
        
        # Audio file manager for audio operations
        self.audio_file_manager = None
    
    def load_file_to_buffer(self, file_path: str) -> None:
        """
        Load a file into the file buffer.
        
        Args:
            file_path: Path to the file to load
            
        Raises:
            Exception: If there's an error reading the file
        """
        try:
            with open(file_path, "r") as f:
                self.file_buffer = f.read()
            print(f"File '{file_path}' loaded into buffer.")
        except Exception as e:
            print(f"Error reading file: {str(e)}")
            raise
    
    def clear_file_buffer(self) -> None:
        """Clear the file buffer."""
        self.file_buffer = ""
        print("File buffer cleared.")
    
    def show_file_buffer(self, show_all: bool = False) -> None:
        """
        Show the file buffer content.
        
        Args:
            show_all: If True, show entire content. If False, show first 100 characters.
        """
        if self.file_buffer:
            if show_all:
                print(self.file_buffer)
            else:
                print(self.file_buffer[:100] + ("..." if len(self.file_buffer) > 100 else ""))
        else:
            print("File buffer is empty.")
    
    def load_file_to_bank(self, bank_num: int, file_path: str) -> None:
        """
        Load a file into a specific file bank.
        
        Args:
            bank_num: File bank number (1-5)
            file_path: Path to the file to load
            
        Raises:
            ValueError: If bank_num is invalid
            Exception: If there's an error reading the file
        """
        if bank_num < 1 or bank_num > 5:
            raise ValueError("Invalid filebank number. Please use 1 through 5.")
        
        bank_name = f"filebank{bank_num}"
        try:
            with open(file_path, "r") as f:
                self.file_banks[bank_name] = f.read()
            print(f"File '{file_path}' loaded into {bank_name}.")
        except Exception as e:
            print(f"Error reading file: {str(e)}")
            raise
    
    def clear_file_bank(self, bank_num: int) -> None:
        """
        Clear a specific file bank.
        
        Args:
            bank_num: File bank number (1-5)
            
        Raises:
            ValueError: If bank_num is invalid
        """
        if bank_num < 1 or bank_num > 5:
            raise ValueError("Invalid filebank number. Please use 1 through 5.")
        
        bank_name = f"filebank{bank_num}"
        self.file_banks[bank_name] = ""
        print(f"{bank_name} cleared.")
    
    def show_file_bank(self, bank_num: int, show_all: bool = False) -> None:
        """
        Show the content of a specific file bank.
        
        Args:
            bank_num: File bank number (1-5)
            show_all: If True, show entire content. If False, show first 100 characters.
            
        Raises:
            ValueError: If bank_num is invalid
        """
        if bank_num < 1 or bank_num > 5:
            raise ValueError("Invalid filebank number. Please use 1 through 5.")
        
        bank_name = f"filebank{bank_num}"
        content = self.file_banks[bank_name]
        if not content:
            print(f"{bank_name} is empty.")
            return
        
        if show_all:
            print(content)
        else:
            print(content[:100] + ("..." if len(content) > 100 else ""))
    
    def set_script_var(self, var_name: str, var_value: str) -> None:
        """
        Set a script variable.
        
        Args:
            var_name: Name of the variable
            var_value: Value of the variable
        """
        self.script_vars[var_name] = var_value
        print(f"Variable '{var_name}' set.")

    def detect_image_format(self, file_path: str) -> str:
        """
        Detect image MIME type from file extension.
        
        Args:
            file_path: Path to the image file
            
        Returns:
            MIME type string (e.g., 'image/jpeg', 'image/png')
            
        Raises:
            ValueError: If file format is not supported
        """
        ext = Path(file_path).suffix.lower()
        if ext in ['.jpg', '.jpeg']:
            return 'image/jpeg'
        elif ext == '.png':
            return 'image/png'
        else:
            raise ValueError(f"Unsupported image format: {ext}. Use .jpg, .jpeg, or .png")

    def load_image_to_bank(self, bank_num: int, file_path: str) -> None:
        """
        Load an image file into a specific image bank as base64 data URL.
        
        Args:
            bank_num: Image bank number (1-5)
            file_path: Path to the image file to load
            
        Raises:
            ValueError: If bank_num is invalid or image format is unsupported
            Exception: If there's an error reading the file
        """
        if bank_num < 1 or bank_num > 5:
            raise ValueError("Invalid imagebank number. Please use 1 through 5.")
        
        bank_name = f"imagebank{bank_num}"
        
        # Detect format
        mime_type = self.detect_image_format(file_path)
        
        # Load and encode
        try:
            with open(file_path, "rb") as f:
                image_data = f.read()
            
            base64_data = base64.b64encode(image_data).decode('utf-8')
            data_url = f"data:{mime_type};base64,{base64_data}"
            self.image_banks[bank_name] = data_url
            print(f"Image '{file_path}' loaded into {bank_name}.")
        except Exception as e:
            print(f"Error reading image file: {str(e)}")
            raise

    def clear_image_bank(self, bank_num: int) -> None:
        """
        Clear a specific image bank.
        
        Args:
            bank_num: Image bank number (1-5)
            
        Raises:
            ValueError: If bank_num is invalid
        """
        if bank_num < 1 or bank_num > 5:
            raise ValueError("Invalid imagebank number. Please use 1 through 5.")
        
        bank_name = f"imagebank{bank_num}"
        self.image_banks[bank_name] = ""
        print(f"{bank_name} cleared.")

    def show_image_bank(self, bank_num: int, show_all: bool = False) -> None:
        """
        Show info about an image bank (not the actual image data).
        
        Args:
            bank_num: Image bank number (1-5)
            show_all: Currently unused, for future expansion
            
        Raises:
            ValueError: If bank_num is invalid
        """
        if bank_num < 1 or bank_num > 5:
            raise ValueError("Invalid imagebank number. Please use 1 through 5.")
        
        bank_name = f"imagebank{bank_num}"
        content = self.image_banks[bank_name]
        if not content:
            print(f"{bank_name} is empty.")
            return
        
        # Extract MIME type and approximate size from data URL
        if content.startswith("data:"):
            mime_end = content.find(";")
            mime_type = content[5:mime_end] if mime_end > 0 else "unknown"
            # Approximate size from base64 length (4 chars = 3 bytes)
            data_start = content.find(",") + 1
            if data_start > 0:
                base64_len = len(content) - data_start
                approx_size_kb = (base64_len * 3) / 4 / 1024
                print(f"{bank_name}: {mime_type}, ~{approx_size_kb:.2f}KB")
            else:
                print(f"{bank_name}: {mime_type}")
        else:
            print(f"{bank_name}: Invalid data format")
    
    # ============================================================================
    # Audio Bank Methods
    # ============================================================================
    
    def detect_audio_format(self, file_path: str) -> str:
        """
        Detect audio MIME type from file extension.
        
        Args:
            file_path: Path to the audio file
            
        Returns:
            MIME type string (e.g., 'audio/mpeg', 'audio/wav')
        """
        ext = Path(file_path).suffix.lower().lstrip('.')
        format_map = {
            'mp3': 'audio/mpeg',
            'wav': 'audio/wav',
            'flac': 'audio/flac',
            'ogg': 'audio/ogg',
            'm4a': 'audio/m4a',
            'webm': 'audio/webm',
            'opus': 'audio/opus',
            'aac': 'audio/aac',
            'pcm': 'audio/pcm',
        }
        return format_map.get(ext, f"audio/{ext}")
    
    def load_audio_to_bank(self, bank_num: int, file_path: str) -> None:
        """
        Load an audio file into a specific audio bank as base64 data URL.
        
        Args:
            bank_num: Audio bank number (1-5)
            file_path: Path to the audio file to load
            
        Raises:
            ValueError: If bank_num is invalid or audio format is unsupported
            Exception: If there's an error reading the file
        """
        if bank_num < 1 or bank_num > 5:
            raise ValueError("Invalid audiobank number. Please use 1 through 5.")
        
        bank_name = f"audiobank{bank_num}"
        
        # Detect format
        mime_type = self.detect_audio_format(file_path)
        
        # Load and encode
        try:
            with open(file_path, "rb") as f:
                audio_data = f.read()
            
            base64_data = base64.b64encode(audio_data).decode('utf-8')
            data_url = f"data:{mime_type};base64,{base64_data}"
            self.audio_banks[bank_name] = data_url
            print(f"Audio '{file_path}' loaded into {bank_name}.")
        except Exception as e:
            print(f"Error reading audio file: {str(e)}")
            raise
    
    def clear_audio_bank(self, bank_num: int) -> None:
        """
        Clear a specific audio bank.
        
        Args:
            bank_num: Audio bank number (1-5)
            
        Raises:
            ValueError: If bank_num is invalid
        """
        if bank_num < 1 or bank_num > 5:
            raise ValueError("Invalid audiobank number. Please use 1 through 5.")
        
        bank_name = f"audiobank{bank_num}"
        self.audio_banks[bank_name] = ""
        print(f"{bank_name} cleared.")
    
    def show_audio_bank(self, bank_num: int, show_all: bool = False) -> None:
        """
        Show info about an audio bank (not the actual audio data).
        
        Args:
            bank_num: Audio bank number (1-5)
            show_all: Currently unused, for future expansion
            
        Raises:
            ValueError: If bank_num is invalid
        """
        if bank_num < 1 or bank_num > 5:
            raise ValueError("Invalid audiobank number. Please use 1 through 5.")
        
        bank_name = f"audiobank{bank_num}"
        content = self.audio_banks[bank_name]
        if not content:
            print(f"{bank_name} is empty.")
            return
        
        # Extract MIME type and approximate size from data URL
        if content.startswith("data:audio/"):
            mime_end = content.find(";")
            mime_type = content[11:mime_end] if mime_end > 0 else "unknown"  # "data:audio/" = 11 chars
            # Approximate size from base64 length (4 chars = 3 bytes)
            data_start = content.find(",") + 1
            if data_start > 0:
                base64_len = len(content) - data_start
                approx_size_kb = (base64_len * 3) / 4 / 1024
                print(f"{bank_name}: {mime_type}, ~{approx_size_kb:.2f}KB")
            else:
                print(f"{bank_name}: {mime_type}")
        else:
            print(f"{bank_name}: Invalid data format")
    
    def is_audio_variable(self, var_value: str) -> bool:
        """
        Check if a variable value is an audio data URL.
        
        Args:
            var_value: Variable value to check
            
        Returns:
            True if value starts with 'data:audio/'
        """
        return var_value.startswith("data:audio/")
    
    def get_audio_format_from_variable(self, var_value: str) -> Optional[str]:
        """
        Extract audio format from a data URL variable.
        
        Args:
            var_value: Audio data URL
            
        Returns:
            Format string (e.g., 'mp3', 'wav') or None
        """
        if not self.is_audio_variable(var_value):
            return None
        
        # Format is between "data:audio/" and ";base64,"
        parts = var_value.split(";")
        if len(parts) >= 1:
            format_part = parts[0].replace("data:audio/", "")
            return format_part
        return None
    
    def replace_placeholders(self, prompt: str, include_images: bool = True, include_audio: bool = True) -> Tuple[str, List[Dict]]:
        """
        Replace filebank, script variable, imagebank, and audiobank placeholders in the prompt.
        
        For image banks, returns separated text and images for proper OpenAI multimodal format.
        For audio banks, placeholders are replaced with descriptive text.
        
        Args:
            prompt: The prompt string containing placeholders
            include_images: If True, include image banks in search (for chat completion)
                          If False, images are ignored (for echo command)
            include_audio: If True, include audio banks in search
            
        Returns:
            Tuple of (text_prompt, image_list) where:
            - text_prompt: Prompt with filebank, script var, and audio bank placeholders replaced
            - image_list: List of image content dicts for OpenAI format
        """
        # First, handle text placeholders (filebanks and script vars)
        text_prompt = prompt
        for bank_name, content in self.file_banks.items():
            placeholder = f"{{{bank_name}}}"
            if placeholder in text_prompt:
                text_prompt = text_prompt.replace(placeholder, content)
        
        for var_name, var_value in self.script_vars.items():
            placeholder = f"${{{var_name}}}"
            if placeholder in text_prompt:
                text_prompt = text_prompt.replace(placeholder, str(var_value))
        
        # Handle audio banks (always replace with descriptive text)
        if include_audio:
            for bank_name, content in self.audio_banks.items():
                placeholder = f"{{{bank_name}}}"
                if placeholder in text_prompt:
                    if content and content.startswith("data:audio/"):
                        # Extract format and size info
                        mime_end = content.find(";")
                        mime_type = content[11:mime_end] if mime_end > 0 else "unknown"
                        data_start = content.find(",") + 1
                        if data_start > 0:
                            base64_len = len(content) - data_start
                            approx_size_kb = (base64_len * 3) / 4 / 1024
                            text_prompt = text_prompt.replace(
                                placeholder,
                                f"[Audio: {mime_type}, ~{approx_size_kb:.1f}KB]"
                            )
                        else:
                            text_prompt = text_prompt.replace(placeholder, "[Audio]")
                    else:
                        text_prompt = text_prompt.replace(placeholder, "[Audio Bank Empty]")
        
        # Collect images only if requested
        image_list = []
        if include_images:
            for bank_name, content in self.image_banks.items():
                placeholder = f"{{{bank_name}}}"
                if placeholder in text_prompt:
                    if content:  # Has valid image data
                        if content.startswith("data:"):
                            image_list.append({
                                "type": "image_url",
                                "image_url": {"url": content}
                            })
                        # Remove the placeholder from text since it's now an image
                        text_prompt = text_prompt.replace(placeholder, "")
        
        # Clean up any remaining whitespace from removed placeholders
        text_prompt = text_prompt.strip()
        # Replace double spaces with single spaces
        while "  " in text_prompt:
            text_prompt = text_prompt.replace("  ", " ")
        
        return text_prompt, image_list
    
    def replace_placeholders_legacy(self, prompt: str) -> str:
        """
        Legacy method for backward compatibility.
        Replaces placeholders and returns only text (ignoring images).
        Used by /echo command and other places that don't need image handling.
        
        Args:
            prompt: The prompt string containing placeholders
            
        Returns:
            Prompt with placeholders replaced (text only)
        """
        text_prompt, _ = self.replace_placeholders(prompt, include_images=False)
        return text_prompt
    
    def show_memory_usage(self, search_buffer: list = None) -> None:
        """
        Show size of the file buffer, filebanks, image banks, and script variables in KB.
        """
        print(f"\n{'Source':<20} {'Size (KB)':>10}")
        print("-" * 32)
        
        # File Buffer
        file_buffer_size = len(self.file_buffer.encode('utf-8')) / 1024
        print(f"{'FILE_BUFFER':<20} {file_buffer_size:>10.2f}")
        
        # File Banks
        for i in range(1, 6):
            bank_name = f"filebank{i}"
            bank_size = len(self.file_banks[bank_name].encode('utf-8')) / 1024
            print(f"{bank_name:<20} {bank_size:>10.2f}")
        
        # Image Banks
        for i in range(1, 6):
            bank_name = f"imagebank{i}"
            content = self.image_banks[bank_name]
            if content and content.startswith("data:"):
                # For base64 data URLs, calculate size differently
                data_start = content.find(",") + 1
                if data_start > 0:
                    base64_len = len(content) - data_start
                    bank_size = (base64_len * 3) / 4 / 1024  # Approximate
                    print(f"{bank_name:<20} {bank_size:>10.2f}")
                else:
                    print(f"{bank_name:<20} {0:>10.2f}")
            else:
                print(f"{bank_name:<20} {0:>10.2f}")
        
        # Search Buffer
        if search_buffer is not None:
            import json
            sb_size = len(json.dumps(search_buffer).encode('utf-8')) / 1024
            print(f"{'SEARCH_BUFFER':<20} {sb_size:>10.2f}")
            
        # Script Variables
        for var_name, var_value in self.script_vars.items():
            var_size = len(str(var_value).encode('utf-8')) / 1024
            print(f"{var_name:<20} {var_size:>10.2f}")
        print()
    
    def dump_variables(self, name: str = "all", search_buffer: list = None, chat_history: list = None) -> None:
        """
        Print the contents of a variable or 'all' variables.
        
        Args:
            name: Name of variable to dump, or 'all' for all variables
            search_buffer: Optional search buffer to dump
            chat_history: Optional chat history list to dump
        """
        if name == "all":
            print("\n--- DUMP ALL VARIABLES ---")
            print(f"FILE_BUFFER: {self.file_buffer}")
            for i in range(1, 6):
                bank_name = f"filebank{i}"
                print(f"{bank_name.upper()}: {self.file_banks[bank_name]}")
            for i in range(1, 6):
                bank_name = f"imagebank{i}"
                content = self.image_banks[bank_name]
                print(f"{bank_name.upper()}: {'<image data>' if content else ''}")
            
            if search_buffer is not None:
                print(f"SEARCH_BUFFER: {search_buffer}")
            
            if chat_history is not None and chat_history:
                print("CHAT_HISTORY:")
                for i, (prompt, response) in enumerate(chat_history, 1):
                    print(f"  [{i}] PROMPT: {prompt[:100]}{'...' if len(prompt) > 100 else ''}")
                    print(f"      RESPONSE: {response[:100]}{'...' if len(response) > 100 else ''}")
                
            for var_name, var_value in self.script_vars.items():
                print(f"SCRIPT_VAR '{var_name}': {var_value}")
            print("--- END DUMP ---\n")
        elif name == "file_buffer":
            print(f"FILE_BUFFER: {self.file_buffer}")
        elif name == "search_buffer":
            if search_buffer is not None:
                print(f"SEARCH_BUFFER: {search_buffer}")
            else:
                print("SEARCH_BUFFER is empty or not available.")
        elif name == "chat_history" or name == "CHAT_HISTORY":
            if chat_history is not None and chat_history:
                print("\n--- CHAT_HISTORY ---")
                for i, (prompt, response) in enumerate(chat_history, 1):
                    print(f"[{i}]")
                    print(f"  PROMPT: {prompt}")
                    print(f"  RESPONSE: {response}")
                    print()
                print("--- END CHAT_HISTORY ---\n")
            else:
                print("CHAT_HISTORY is empty.")
        elif name.startswith("filebank") and name[8:].isdigit():
            if name in self.file_banks:
                print(f"{name.upper()}: {self.file_banks[name]}")
            else:
                print(f"Error: {name} not found.")
        elif name.startswith("imagebank") and name[9:].isdigit():
            if name in self.image_banks:
                content = self.image_banks[name]
                print(f"{name.upper()}: {'<image data>' if content else ''}")
            else:
                print(f"Error: {name} not found.")
        elif name in self.script_vars:
            print(f"SCRIPT_VAR '{name}': {self.script_vars[name]}")
        else:
            print(f"Error: Variable '{name}' not found.")
