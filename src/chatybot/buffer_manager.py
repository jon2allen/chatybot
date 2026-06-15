#! /usr/bin/env python3
"""
Buffer Manager Module
Manages file buffers, file banks, script variables, and image banks
"""

import base64
from pathlib import Path
from typing import Dict, List, Tuple, Any


class BufferManager:
    """Manages file buffers, file banks, script variables, and image banks."""
    
    def __init__(self):
        self.file_buffer: str = ""
        self.prompt_buffer: str = ""
        self.file_banks: Dict[str, str] = {f"filebank{i}": "" for i in range(1, 6)}
        self.image_banks: Dict[str, str] = {f"imagebank{i}": "" for i in range(1, 6)}
        self.script_vars: Dict[str, str] = {}
        self.array_store: Dict[str, Dict[str, Any]] = {}
        self.array_counter: int = 0
    
    def allocate_array(self, data: List[str]) -> str:
        """
        Allocate a string array on the heap and return a pointer string.
        
        Args:
            data: List of strings to store
            
        Returns:
            Pointer string to the array (e.g. __ARRAY_REF_001__)
        """
        self.array_counter += 1
        ref_id = f"__ARRAY_REF_{self.array_counter:03d}__"
        self.array_store[ref_id] = {
            "type": "array",
            "data": data
        }
        return ref_id

    def clean_unreferenced_arrays(self) -> None:
        """
        Garbage collect any arrays in array_store that are not referenced by any script variable.
        """
        referenced_refs = set()
        for val in self.script_vars.values():
            if isinstance(val, str) and val.startswith("__ARRAY_REF_"):
                referenced_refs.add(val)
        
        # Identify unreferenced arrays
        unreferenced = [ref for ref in self.array_store if ref not in referenced_refs]
        for ref in unreferenced:
            del self.array_store[ref]
    
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
    def get_variable_value(self, name_with_subscript: str) -> str:
        """
        Retrieves a variable value, supporting subscripting like var[0].
        Raises KeyError if the base variable is not found.
        Raises IndexError if the index is out of bounds.
        Raises ValueError if subscripting a non-array variable.
        """
        import re
        match = re.match(r"^(\w+)\[(-?\d+)\]$", name_with_subscript)
        if match:
            var_name = match.group(1)
            index = int(match.group(2))
            if var_name not in self.script_vars:
                raise KeyError(f"Variable '{var_name}' not found")
            var_value = self.script_vars[var_name]
            if isinstance(var_value, str) and var_value.startswith("__ARRAY_REF_") and var_value in self.array_store:
                data = self.array_store[var_value]["data"]
                try:
                    return data[index]
                except IndexError:
                    raise IndexError(f"Index {index} out of bounds for array '{var_name}' of length {len(data)}")
            else:
                raise ValueError(f"Variable '{var_name}' is not an array, cannot subscript")
        else:
            if name_with_subscript not in self.script_vars:
                raise KeyError(f"Variable '{name_with_subscript}' not found")
            var_value = self.script_vars[name_with_subscript]
            if isinstance(var_value, str) and var_value.startswith("__ARRAY_REF_") and var_value in self.array_store:
                return "\n".join(self.array_store[var_value]["data"])
            return str(var_value)

    def replace_placeholders(self, prompt: str, include_images: bool = True) -> Tuple[str, List[Dict]]:
        """
        Replace filebank, script variable, and imagebank placeholders in the prompt.
        
        For image banks, returns separated text and images for proper OpenAI multimodal format.
        
        Args:
            prompt: The prompt string containing placeholders
            include_images: If True, include image banks in search (for chat completion)
                          If False, images are ignored (for echo command)
            
        Returns:
            Tuple of (text_prompt, image_list) where:
            - text_prompt: Prompt with filebank and script var placeholders replaced
            - image_list: List of image content dicts for OpenAI format
        """
        # First, handle text placeholders (filebanks and script vars)
        text_prompt = prompt
        
        import re
        # If the prompt matches a clean subscript of an existing array variable directly, resolve it
        match_direct = re.match(r"^(\w+)\[(-?\d+)\]$", text_prompt.strip())
        if match_direct:
            var_name = match_direct.group(1)
            if var_name in self.script_vars:
                var_value = self.script_vars[var_name]
                if isinstance(var_value, str) and var_value.startswith("__ARRAY_REF_") and var_value in self.array_store:
                    try:
                        text_prompt = self.get_variable_value(text_prompt.strip())
                    except Exception:
                        pass

        for bank_name, content in self.file_banks.items():
            placeholder = f"{{{bank_name}}}"
            if placeholder in text_prompt:
                text_prompt = text_prompt.replace(placeholder, content)
        # Sort keys by length descending to prevent shorter variable names matching prefixes of longer ones
        sorted_vars = sorted(list(self.script_vars.keys()), key=len, reverse=True)
        for var_name in sorted_vars:
            # 1. Braced subscripts: ${var_name[index]}
            braced_sub_pat = rf"\$\{{{re.escape(var_name)}\[(-?\d+)\]\}}"
            def replace_braced_sub(m):
                idx = m.group(1)
                try:
                    return self.get_variable_value(f"{var_name}[{idx}]")
                except Exception:
                    return m.group(0)
            text_prompt = re.sub(braced_sub_pat, replace_braced_sub, text_prompt)

            # 2. Unbraced subscripts: $var_name[index]
            unbraced_sub_pat = rf"\${re.escape(var_name)}\[(-?\d+)\]"
            def replace_unbraced_sub(m):
                idx = m.group(1)
                try:
                    return self.get_variable_value(f"{var_name}[{idx}]")
                except Exception:
                    return m.group(0)
            text_prompt = re.sub(unbraced_sub_pat, replace_unbraced_sub, text_prompt)

            # 3. Braced variables: ${var_name}
            braced_pat = rf"\$\{{{re.escape(var_name)}\}}"
            def replace_braced(m):
                try:
                    return self.get_variable_value(var_name)
                except Exception:
                    return m.group(0)
            text_prompt = re.sub(braced_pat, replace_braced, text_prompt)

            # 4. Unbraced variables: $var_name
            unbraced_pat = rf"\${re.escape(var_name)}\b"
            def replace_unbraced(m):
                try:
                    return self.get_variable_value(var_name)
                except Exception:
                    return m.group(0)
            text_prompt = re.sub(unbraced_pat, replace_unbraced, text_prompt)
        
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
    
    def show_memory_usage(self, search_buffer: list = None, detail: bool = False) -> None:
        """
        Show size of the file buffer, filebanks, image banks, and script variables in KB.
        """
        self.clean_unreferenced_arrays()
        print(f"\n{'Source':<20} {'Size (KB)':>10}")
        print("-" * 32)
        
        # File Buffer
        file_buffer_size = len(self.file_buffer.encode('utf-8')) / 1024
        print(f"{'FILE_BUFFER':<20} {file_buffer_size:>10.2f}")
        if detail and self.file_buffer:
            lines = self.file_buffer.count('\n') + 1
            words = len(self.file_buffer.split())
            chars = len(self.file_buffer)
            preview = self.file_buffer.strip().replace('\n', ' ')[:50]
            print(f"  -> {lines} lines, {words} words, {chars} chars")
            print(f"  -> Preview: \"{preview}...\"")
        
        # File Banks
        for i in range(1, 6):
            bank_name = f"filebank{i}"
            content = self.file_banks[bank_name]
            bank_size = len(content.encode('utf-8')) / 1024
            print(f"{bank_name:<20} {bank_size:>10.2f}")
            if detail and content:
                lines = content.count('\n') + 1
                words = len(content.split())
                chars = len(content)
                preview = content.strip().replace('\n', ' ')[:50]
                print(f"  -> {lines} lines, {words} words, {chars} chars")
                print(f"  -> Preview: \"{preview}...\"")
        
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
                    if detail:
                        mime_end = content.find(";")
                        mime = content[5:mime_end] if mime_end > 5 else "unknown"
                        print(f"  -> MIME type: {mime}")
                        print(f"  -> Base64 length: {base64_len} chars")
                else:
                    print(f"{bank_name:<20} {0:>10.2f}")
            else:
                print(f"{bank_name:<20} {0:>10.2f}")
        
        # Search Buffer
        if search_buffer is not None:
            import json
            sb_size = len(json.dumps(search_buffer).encode('utf-8')) / 1024
            print(f"{'SEARCH_BUFFER':<20} {sb_size:>10.2f}")
            if detail and search_buffer:
                print(f"  -> Total items: {len(search_buffer)}")
                for idx, item in enumerate(search_buffer, 1):
                    item_str = str(item)
                    item_size = len(item_str.encode('utf-8')) / 1024
                    item_preview = item_str.strip().replace('\n', ' ')[:50]
                    print(f"    [{idx}] {item_size:.2f} KB | {item_preview}...")
            
        # Script Variables
        for var_name, var_value in self.script_vars.items():
            if isinstance(var_value, str) and var_value.startswith("__ARRAY_REF_") and var_value in self.array_store:
                num_items = len(self.array_store[var_value]["data"])
                total_len = sum(len(str(x).encode('utf-8')) for x in self.array_store[var_value]["data"])
                var_size = total_len / 1024
                display_name = f"{var_name}[] ({num_items} items)"
                print(f"{display_name:<20} {var_size:>10.2f}")
                if detail:
                    for idx, elem in enumerate(self.array_store[var_value]["data"]):
                        elem_size = len(str(elem).encode('utf-8')) / 1024
                        elem_preview = str(elem).strip().replace('\n', ' ')[:40]
                        print(f"    [{idx}] {elem_size:.2f} KB | {elem_preview}")
            else:
                var_size = len(str(var_value).encode('utf-8')) / 1024
                display_name = var_name
                print(f"{display_name:<20} {var_size:>10.2f}")
                if detail:
                    val_preview = str(var_value).strip().replace('\n', ' ')[:50]
                    val_type = type(var_value).__name__
                    print(f"  -> Type: {val_type} | Value: \"{val_preview}\"")
        print()
    
    def dump_variables(self, name: str = "all", search_buffer: list = None, chat_history: list = None) -> None:
        """
        Print the contents of a variable or 'all' variables.
        
        Args:
            name: Name of variable to dump, or 'all' for all variables
            search_buffer: Optional search buffer to dump
            chat_history: Optional chat history list to dump
        """
        self.clean_unreferenced_arrays()
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
                if isinstance(var_value, str) and var_value.startswith("__ARRAY_REF_") and var_value in self.array_store:
                    print(f"SCRIPT_VAR '{var_name}': {self.array_store[var_value]['data']}")
                else:
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
            var_value = self.script_vars[name]
            if isinstance(var_value, str) and var_value.startswith("__ARRAY_REF_") and var_value in self.array_store:
                print(f"SCRIPT_VAR '{name}': {self.array_store[var_value]['data']}")
            else:
                print(f"SCRIPT_VAR '{name}': {var_value}")
        else:
            try:
                val = self.get_variable_value(name)
                print(f"SCRIPT_VAR '{name}': {val}")
            except KeyError:
                print(f"Error: Variable '{name}' not found.")
            except (IndexError, ValueError) as e:
                print(f"Error: {str(e)}.")
