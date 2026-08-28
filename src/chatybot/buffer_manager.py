#!/usr/bin/env python3
"""
Buffer Manager Module
Manages file buffers, file banks, script variables, and image banks
"""

import base64
import re
import json
import contextlib
from pathlib import Path
from collections import UserDict
from typing import Dict, List, Tuple, Any, Optional


class ScriptVars(UserDict):
    """
    A dictionary-like wrapper that automatically tracks variable types 
    on assignment, maintaining 100% backward compatibility.
    """
    def __init__(self, manager, *args, **kwargs):
        self.manager = manager
        self.types: Dict[str, str] = {}
        self._is_user_write: bool = False
        self.protected_vars = {
            'AGENTIC_LOOP',
            'CHAT_HISTORY',
            'LAST_RESPONSE',
            'TOOL_CONTEXT',
            'TOOL_DISPATCH_RESULT',
            'TOOL_DISPATCH_ERROR',
            'TOOL_DISPATCH_EXIT_CODE',
            'RUN_COMPLETION',
            'RUN_ERROR',
            'RUN_EXIT_CODE',
            'LAST_COMPLETION',
            'latest_rerank',
            'CALC',
            'STR_SEARCH',
            'SESSION_NAME',
            'SESSION_ENABLE',
        }
        super().__init__(*args, **kwargs)

    @contextlib.contextmanager
    def user_write(self):
        """Context manager that sets _is_user_write True for the duration,
        restoring the prior value on exit (including on exceptions). Replaces
        the error-prone manual save/restore idiom scattered across callers."""
        old = self._is_user_write
        self._is_user_write = True
        try:
            yield
        finally:
            self._is_user_write = old

    def _resolve_key(self, key: str) -> str:
        if not isinstance(key, str):
            return key
        if key in self.data:
            return key
        key_upper = key.upper()
        if key_upper in self.protected_vars and key_upper in self.data:
            return key_upper
        return key

    def __getitem__(self, key: str):
        return super().__getitem__(self._resolve_key(key))

    def __contains__(self, key: str):
        return super().__contains__(self._resolve_key(key))

    def get_type(self, key: str) -> str:
        """Returns the type identifier ('text', 'image', 'audio', 'array', 'json', 'base64')."""
        return self.types.get(self._resolve_key(key), "text")

    def __setitem__(self, key: str, value: Any):
        # Canonicalize protected var names to uppercase so reads and writes converge.
        if isinstance(key, str) and key.upper() in self.protected_vars:
            key = key.upper()
        if self._is_user_write and key in self.protected_vars:
            raise ValueError(f"'{key}' is a protected variable and cannot be modified.")
        # 1. Native Python Array / Dict / JSON Detection
        if isinstance(value, list):
            self.types[key] = "array"
            super().__setitem__(key, value)
            return
        if isinstance(value, dict):
            self.types[key] = "json"
            super().__setitem__(key, value)
            return

        if key == "CHAT_HISTORY" and isinstance(value, str):
            try:
                parsed = json.loads(value)
                if isinstance(parsed, list):
                    self.types[key] = "array"
                    super().__setitem__(key, parsed)  # Store as native list
                    return
            except Exception:
                pass

        str_val = str(value) if value is not None else ""
        super().__setitem__(key, str_val)
        
        # 2. Multimodal: Audio & Image Detection (sub-microsecond prefix match)
        str_val_stripped = str_val.strip()
        
        if str_val_stripped.startswith("data:image/") or any(str_val_stripped.startswith(p) for p in ["iVBOR", "/9j/", "UklGR"]):
            self.types[key] = "image"
            return
            
        if str_val_stripped.startswith("data:audio/") or any(str_val_stripped.startswith(p) for p in ["SUQz", "UklGR_audio"]): 
            self.types[key] = "audio"
            return

        # 3. JSON & Serialized Array detection
        if (str_val_stripped.startswith("[") and str_val_stripped.endswith("]")) or \
           (str_val_stripped.startswith("{") and str_val_stripped.endswith("}")):
            try:
                parsed = json.loads(str_val_stripped)
                self.types[key] = "array" if isinstance(parsed, list) else "json"
                return
            except Exception:
                pass
                
        # 4. Fallback for general binary base64
        if self.manager.is_base64_payload(str_val_stripped):
            self.types[key] = "base64"
            return
            
        # 5. Default
        self.types[key] = "text"

    def __delitem__(self, key: str):
        resolved = self._resolve_key(key)
        super().__delitem__(resolved)
        self.types.pop(resolved, None)


class BufferManager:
    """Manages file buffers, file banks, script variables, and image banks."""
    
    def __init__(self, app=None):
        self.app = app
        self.file_buffer: str = ""
        self.prompt_buffer: str = ""
        self.file_banks: Dict[str, str] = {f"filebank{i}": "" for i in range(1, 6)}
        self.image_banks: Dict[str, str] = {f"imagebank{i}": "" for i in range(1, 6)}
        self.script_vars = ScriptVars(self)
    
    def is_base64_payload(self, val: str) -> bool:
        """Detects if a string is a base64 payload in O(1) constant time."""
        if not val:
            return False
            
        val_stripped = val.strip()
        val_len = len(val_stripped)
        
        # 1. Quick length constraint
        if val_len <= 64:
            return False
            
        # 2. Fast prefix matches
        if val_stripped.startswith("data:") and ";base64," in val_stripped[:100]:
            return True
        if val_stripped[:5] in ("iVBOR", "/9j/", "UklGR", "R0lG", "JVBER"):
            return True

        # 3. Constant-time slice validation (checks first 80 chars)
        prefix = val_stripped[:80]
        if " " in prefix or "\n" in prefix:
            return False
            
        check_len = len(prefix) - (len(prefix) % 4)
        if check_len < 4:
            return False
            
        try:
            base64.b64decode(prefix[:check_len], validate=True)
            return True
        except Exception:
            return False

    def load_file_to_buffer(self, file_path: str) -> None:
        """Load a file into the file buffer."""
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
        """Show the file buffer content."""
        if self.file_buffer:
            if show_all:
                print(self.file_buffer)
            else:
                print(self.file_buffer[:100] + ("..." if len(self.file_buffer) > 100 else ""))
        else:
            print("File buffer is empty.")
    
    def load_file_to_bank(self, bank_num: int, file_path: str) -> None:
        """Load a file into a specific file bank."""
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
        """Clear a specific file bank."""
        if bank_num < 1 or bank_num > 5:
            raise ValueError("Invalid filebank number. Please use 1 through 5.")
        
        bank_name = f"filebank{bank_num}"
        self.file_banks[bank_name] = ""
        print(f"{bank_name} cleared.")
    
    def show_file_bank(self, bank_num: int, show_all: bool = False) -> None:
        """Show the content of a specific file bank."""
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
    
    def is_protected_var(self, var_name: str) -> bool:
        """Check if a variable is protected and cannot be modified via /setvar."""
        protected = getattr(self.script_vars, 'protected_vars', None)
        if protected is not None:
            return isinstance(var_name, str) and var_name.upper() in protected
        return False

    def set_script_var(self, var_name: str, var_value: Any, allow_protected: bool = False) -> bool:
        """Set a script variable.
        
        Args:
            var_name: Name of the variable
            var_value: Value to set
            allow_protected: If True, bypasses protection check even if this is a user write.
        
        Returns:
            True if variable was set successfully, False if protected and not allowed
        """
        old_user_write = getattr(self.script_vars, '_is_user_write', False)
        if allow_protected and hasattr(self.script_vars, '_is_user_write'):
            self.script_vars._is_user_write = False
        try:
            self.script_vars[var_name] = var_value
            return True
        except ValueError as e:
            print(f"Error: {e}")
            return False
        finally:
            if allow_protected and hasattr(self.script_vars, '_is_user_write'):
                self.script_vars._is_user_write = old_user_write

    def get_script_var(self, var_name: str) -> Optional[str]:
        """
        Get a script variable value.
        
        Args:
            var_name: Name of the variable
            
        Returns:
            Value of the variable, or None if not found
        """
        return self.script_vars.get(var_name)

    def detect_image_format(self, file_path: str) -> str:
        """Detect image MIME type from file extension."""
        ext = Path(file_path).suffix.lower()
        if ext in ['.jpg', '.jpeg']:
            return 'image/jpeg'
        elif ext == '.png':
            return 'image/png'
        else:
            raise ValueError(f"Unsupported image format: {ext}. Use .jpg, .jpeg, or .png")

    def load_image_to_bank(self, bank_num: int, file_path: str) -> None:
        """Load an image file into a specific image bank as base64 data URL."""
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
        """Clear a specific image bank."""
        if bank_num < 1 or bank_num > 5:
            raise ValueError("Invalid imagebank number. Please use 1 through 5.")
        
        bank_name = f"imagebank{bank_num}"
        self.image_banks[bank_name] = ""
        print(f"{bank_name} cleared.")

    def show_image_bank(self, bank_num: int, show_all: bool = False) -> None:
        """Show info about an image bank (not the actual image data)."""
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
        match = re.match(r"^(\w+)\[(-?\d+)\]$", name_with_subscript)
        if match:
            var_name = match.group(1)
            index = int(match.group(2))
            if var_name.upper() == "CHAT_HISTORY":
                chat_hist_val = self.resolve_text_variable("CHAT_HISTORY")
                if chat_hist_val is not None:
                    try:
                        parsed = json.loads(chat_hist_val)
                    except Exception:
                        parsed = []
                    try:
                        return str(parsed[index])
                    except IndexError:
                        raise IndexError(f"Index {index} out of bounds for array '{var_name}' of length {len(parsed)}")
                else:
                    raise KeyError(f"Variable '{var_name}' not found")
            if var_name not in self.script_vars:
                raise KeyError(f"Variable '{var_name}' not found")
            var_value = self.script_vars[var_name]
            if self.script_vars.get_type(var_name) == "array":
                parsed = var_value
                if isinstance(var_value, str):
                    try:
                        parsed = json.loads(var_value)
                    except Exception:
                        parsed = None
                if not isinstance(parsed, list):
                    raise ValueError(f"Variable '{var_name}' is marked as array but contents could not be parsed")
                try:
                    return str(parsed[index])
                except IndexError:
                    raise IndexError(f"Index {index} out of bounds for array '{var_name}' of length {len(parsed)}")
            else:
                raise ValueError(f"Variable '{var_name}' is not an array")
        else:
            if name_with_subscript not in self.script_vars:
                special_val = self.resolve_text_variable(name_with_subscript)
                if special_val is not None:
                    return special_val
                raise KeyError(f"Variable '{name_with_subscript}' not found")
            var_value = self.script_vars[name_with_subscript]
            if self.script_vars.get_type(name_with_subscript) == "array":
                parsed = var_value
                if isinstance(var_value, str):
                    try:
                        parsed = json.loads(var_value)
                    except Exception:
                        parsed = None
                if not isinstance(parsed, list):
                    return str(var_value)
                return "\n".join(map(str, parsed))
            return str(var_value)

    def resolve_text_variable(self, var_name: str) -> Optional[str]:
        """Resolves text-safe variables only (blocks base64/multimodal data)."""
        # Special variables
        if var_name.upper() == 'LAST_RESPONSE':
            if self.app and self.app.chat_history:
                return self.app.chat_history[-1][1]
            return ""
        if var_name.upper() == 'CHAT_HISTORY':
            if self.app and self.app.chat_history:
                history_json = []
                for p, r in self.app.chat_history:
                    history_json.append({"role": "user", "content": p})
                    history_json.append({"role": "assistant", "content": r})
                return json.dumps(history_json)
            return "[]"
            
        # File banks
        if var_name in self.file_banks:
            content = self.file_banks[var_name]
            if isinstance(content, str):
                strip_thinking = True
                if self.app and hasattr(self.app, 'strip_thinking_from_filebanks'):
                    strip_thinking = self.app.strip_thinking_from_filebanks
                
                if strip_thinking:
                    import re
                    content = re.sub(r"<think>.*?</think>\s*|<thought>.*?</thought>\s*", "", content, flags=re.DOTALL)
            return content
            
        # Script variables
        if var_name in self.script_vars:
            # Skip base64, image, or audio elements to prevent console/prompt bloat
            if self.script_vars.get_type(var_name) in ("image", "audio", "base64"):
                return None
            val = self.script_vars[var_name]
            if isinstance(val, list):
                return "\n".join(map(str, val))
            # Array stored as a JSON string: parse and join for consistent rendering.
            if self.script_vars.get_type(var_name) == "array" and isinstance(val, str):
                try:
                    parsed = json.loads(val)
                    if isinstance(parsed, list):
                        return "\n".join(map(str, parsed))
                except Exception:
                    pass
            return str(val)
            
        return None

    def replace_placeholders(self, prompt: str, include_images: bool = True, clear_unresolved: bool = False) -> Tuple[str, List[Dict]]:
        """
        Replace filebank, script variable, and imagebank placeholders in the prompt.
        Supports both ${VAR} and {VAR} syntaxes.
        """
        text_prompt = prompt
        multimodal_parts = []
        
        # 1. Direct subscript evaluation if the entire prompt matches a subscript exactly
        match_direct = re.match(r"^(\w+)\[(-?\d+)\]$", text_prompt.strip())
        if match_direct:
            var_name = match_direct.group(1)
            if var_name in self.script_vars:
                try:
                    text_prompt = self.get_variable_value(text_prompt.strip())
                except Exception:
                    pass

        # 2. Extract image banks if include_images is requested
        if include_images:
            for bank_name, content in self.image_banks.items():
                placeholders = [f"{{{bank_name}}}", f"${{{bank_name}}}"]
                for placeholder in placeholders:
                    if placeholder in text_prompt:
                        if content and content.startswith("data:"):
                            multimodal_parts.append({
                                "type": "image_url",
                                "image_url": {"url": content}
                            })
                        text_prompt = text_prompt.replace(placeholder, "")

        # 3. Sort keys by length descending to prevent shorter variable names matching prefixes of longer ones
        keys_to_resolve = list(self.script_vars.keys()) + ['LAST_RESPONSE', 'CHAT_HISTORY'] + list(self.file_banks.keys())
        sorted_keys = sorted(list(set(keys_to_resolve)), key=len, reverse=True)

        for key in sorted_keys:
            var_type = self.script_vars.get_type(key) if key in self.script_vars else "text"
            
            # Extract script-bound images to prompt payload
            if var_type == "image" and include_images:
                placeholders = [f"{{{key}}}", f"${{{key}}}"]
                for ph in placeholders:
                    if ph in text_prompt:
                        val = self.script_vars[key]
                        multimodal_parts.append({
                            "type": "image_url",
                            "image_url": {"url": val}
                        })
                        text_prompt = text_prompt.replace(ph, "")
                continue

            # Extract script-bound audio to prompt payload
            if var_type == "audio" and include_images:
                placeholders = [f"{{{key}}}", f"${{{key}}}"]
                for ph in placeholders:
                    if ph in text_prompt:
                        val = self.script_vars[key]
                        fmt = "wav"
                        if val.startswith("data:audio/"):
                            fmt = val.split(";")[0].split("/")[-1]
                        multimodal_parts.append({
                            "type": "input_audio",
                            "input_audio": {
                                "data": val.split(",")[-1] if "," in val else val,
                                "format": fmt
                            }
                        })
                        text_prompt = text_prompt.replace(ph, "")
                continue

            # B. Array subscript replacement (supports braced `${key[index]}` and `{key[index]}`)
            flags = re.IGNORECASE if key.upper() in self.script_vars.protected_vars or key.upper() in ('CHAT_HISTORY', 'LAST_RESPONSE') else 0
            sub_pat = rf"\$?\{{{re.escape(key)}\[(-?\d+)\]\}}"
            def replace_sub(m):
                idx = m.group(1)
                try:
                    return self.get_variable_value(f"{key}[{idx}]")
                except Exception:
                    return m.group(0)
            text_prompt = re.sub(sub_pat, replace_sub, text_prompt, flags=flags)

            # C. Standard unbraced subscript ($key[index])
            unbraced_sub_pat = rf"\${re.escape(key)}\[(-?\d+)\]"
            text_prompt = re.sub(unbraced_sub_pat, replace_sub, text_prompt, flags=flags)

            # D. Base variable replacement (braced: `${key}` / `{key}`)
            braced_pat = rf"\$?\{{{re.escape(key)}\}}"
            def replace_base(m):
                val = self.resolve_text_variable(key)
                return str(val) if val is not None else m.group(0)
            text_prompt = re.sub(braced_pat, replace_base, text_prompt, flags=flags)

            # E. Standard unbraced variable ($key)
            unbraced_pat = rf"\${re.escape(key)}\b"
            text_prompt = re.sub(unbraced_pat, replace_base, text_prompt, flags=flags)
        
        if clear_unresolved:
            # 1. Braced subscript: ${var[idx]} or {var[idx]}
            text_prompt = re.sub(r'\$?\{[a-zA-Z_]\w*\[-?\d+\]\}', "", text_prompt)
            # 2. Unbraced subscript: $var[idx]
            text_prompt = re.sub(r'\$[a-zA-Z_]\w*\[-?\d+\]', "", text_prompt)
            # 3. Braced base: ${var} or {var}
            text_prompt = re.sub(r'\$?\{[a-zA-Z_]\w*\}', "", text_prompt)
            # 4. Unbraced base: $var
            text_prompt = re.sub(r'\$[a-zA-Z_]\w*\b', "", text_prompt)
            # Collapse whitespace gaps left by removed placeholders.
            while "  " in text_prompt:
                text_prompt = text_prompt.replace("  ", " ")

        # Strip leading/trailing whitespace only; do not collapse internal
        # whitespace runs in the normal path, which would mutate legitimate
        # user content (e.g. double spaces inside substituted filebank text).
        text_prompt = text_prompt.strip()

        return text_prompt, multimodal_parts
    
    def replace_placeholders_legacy(self, prompt: str, clear_unresolved: bool = True) -> str:
        """Legacy method for backward compatibility. Replaces text and ignores images."""
        text_prompt, _ = self.replace_placeholders(prompt, include_images=False, clear_unresolved=clear_unresolved)
        return text_prompt
    
    def show_memory_usage(self, search_buffer: list = None, detail: bool = False, debug: bool = False, chat_history: list = None) -> None:
        """Show size of the file buffer, filebanks, image banks, and script variables in KB."""
        if debug:
            print("\n--- SCRIPT_VARS DEBUG METADATA ---")
            print(f"{'Variable':<25} {'Type':<12} {'Python Class':<15} {'Preview / Info':<40}")
            print("-" * 92)
            for var_name, var_value in self.script_vars.items():
                var_type = self.script_vars.get_type(var_name)
                py_class = var_value.__class__.__name__
                if isinstance(var_value, (list, dict)):
                    info = f"Length: {len(var_value)} items"
                else:
                    val_str = str(var_value)
                    if len(val_str) > 50:
                        info = f"Str length: {len(val_str)} | Preview: {val_str[:30]}..."
                    else:
                        info = val_str
                print(f"{var_name:<25} {var_type:<12} {py_class:<15} {info:<40}")
            print("--- END DEBUG METADATA ---\n")
            return

        print(f"\nSource                Size (KB)")
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
                data_start = content.find(",") + 1
                if data_start > 0:
                    base64_len = len(content) - data_start
                    bank_size = (base64_len * 3) / 4 / 1024
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
            sb_size = len(json.dumps(search_buffer).encode('utf-8')) / 1024
            print(f"{'SEARCH_BUFFER':<20} {sb_size:>10.2f}")
            if detail and search_buffer:
                print(f"  -> Total items: {len(search_buffer)}")
                for idx, item in enumerate(search_buffer, 1):
                    item_str = str(item)
                    item_size = len(item_str.encode('utf-8')) / 1024
                    item_preview = item_str.strip().replace('\n', ' ')[:50]
                    print(f"    [{idx}] {item_size:.2f} KB | {item_preview}...")
        
        # LAST_RESPONSE (from chat history)
        if chat_history is not None and chat_history:
            last_response = chat_history[-1][1]
            last_response_size = len(last_response.encode('utf-8')) / 1024
            print(f"{'LAST_RESPONSE':<20} {last_response_size:>10.2f}")
            
        # Script Variables
        for var_name, var_value in self.script_vars.items():
            var_type = self.script_vars.get_type(var_name)
            if var_type == "array":
                parsed = var_value
                if isinstance(var_value, str):
                    try:
                        parsed = json.loads(var_value)
                        if not isinstance(parsed, list):
                            parsed = [parsed]
                    except Exception:
                        parsed = [var_value]
                
                num_items = len(parsed)
                total_len = sum(len(str(x).encode('utf-8')) for x in parsed)
                var_size = total_len / 1024
                display_name = f"{var_name}[] ({num_items} items)"
                print(f"{display_name:<20} {var_size:>10.2f}")
                if detail:
                    for idx, elem in enumerate(parsed):
                        elem_size = len(str(elem).encode('utf-8')) / 1024
                        elem_preview = str(elem).strip().replace('\n', ' ')[:40]
                        print(f"    [{idx}] {elem_size:.2f} KB | {elem_preview}")
            else:
                var_size = len(str(var_value).encode('utf-8')) / 1024
                display_name = var_name
                print(f"{display_name:<20} {var_size:>10.2f}")
                if detail:
                    val_preview = str(var_value).strip().replace('\n', ' ')[:50]
                    print(f"  -> Type: {var_type} | Value: \"{val_preview}\"")
        print()
    
    def dump_variables(self, name: str = "all", search_buffer: list = None, chat_history: list = None) -> None:
        """Print the contents of a variable or 'all' variables."""
        # Clean variable name by stripping potential placeholder wrappers: ${name}, {name}, $name
        clean_name = name.strip()
        if clean_name.startswith("${") and clean_name.endswith("}"):
            clean_name = clean_name[2:-1]
        elif clean_name.startswith("{") and clean_name.endswith("}"):
            clean_name = clean_name[1:-1]
        elif clean_name.startswith("$"):
            clean_name = clean_name[1:]

        if clean_name == "all":
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
                
            # Show LAST_RESPONSE
            if chat_history is not None and chat_history:
                last_response = chat_history[-1][1]
                print(f"LAST_RESPONSE: {last_response[:200]}{'...' if len(last_response) > 200 else ''}")
            
            for var_name, var_value in self.script_vars.items():
                print(f"SCRIPT_VAR '{var_name}': {var_value}")
            print("--- END DUMP ---\n")
        elif clean_name == "file_buffer":
            print(f"FILE_BUFFER: {self.file_buffer}")
        elif clean_name == "search_buffer":
            if search_buffer is not None:
                print(f"SEARCH_BUFFER: {search_buffer}")
            else:
                print("SEARCH_BUFFER is empty or not available.")
        elif clean_name == "chat_history" or clean_name == "CHAT_HISTORY":
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
        elif clean_name.startswith("filebank") and clean_name[8:].isdigit():
            if clean_name in self.file_banks:
                print(f"{clean_name.upper()}: {self.file_banks[clean_name]}")
            else:
                print(f"Error: {clean_name} not found.")
        elif clean_name.startswith("imagebank") and clean_name[9:].isdigit():
            if clean_name in self.image_banks:
                content = self.image_banks[clean_name]
                print(f"{clean_name.upper()}: {'<image data>' if content else ''}")
            else:
                print(f"Error: {clean_name} not found.")
        elif clean_name in self.script_vars:
            print(f"SCRIPT_VAR '{clean_name}': {self.script_vars[clean_name]}")
        else:
            try:
                val = self.get_variable_value(clean_name)
                print(f"SCRIPT_VAR '{clean_name}': {val}")
            except KeyError:
                print(f"Error: Variable '{clean_name}' not found.")
            except (IndexError, ValueError) as e:
                print(f"Error: {str(e)}.")
