#! /usr/bin/env python3
"""
Main Chatybot Application Class
Orchestrates all components and provides the main interface
"""

import asyncio
import os
import readline
import time
import re
import shlex
import random
from datetime import datetime
from typing import Dict, Any, List, Tuple, Optional, Callable, Union
import logging
import atexit

try:
    import openai
    from openai import AsyncOpenAI
except ImportError:
    raise ImportError("OpenAI SDK is not installed. Please install it with 'pip install openai'.")

from .config_manager import ConfigManager
from .logging_manager import LoggingManager
from .buffer_manager import BufferManager
from .extract_code import process_file
from .chatydb import set_db, search_db, dblog, load_var, save_var, list_dbs, SEARCHBUFFER

# Global variables needed for database functionality
app = None  # Global app instance for database functions to access


class ChatybotApp:
    """Main application class for Chatybot."""
    
    def __init__(self):
        """Initialize the Chatybot application."""
        # Initialize managers
        self.config_manager = ConfigManager()
        self.logging_manager = LoggingManager()
        self.buffer_manager = BufferManager()
        
        # Chat state
        self.chat_history: List[Tuple[str, str]] = []
        self.input_history: List[str] = []
        self.input_history_index = -1
        self.input_history_matches: List[str] = []
        
        # Flags and settings
        self.code_only_flag: bool = False
        self.streaming_enabled: bool = False
        self.note_mode: bool = False
        self.reasoning_mode: bool = True
        self.show_thinking: bool = True
        self.multi_line_mode: bool = False
        self.script_context: bool = False
        
        # Trace settings
        self.trace_raw_payload: bool = False
        self.trace_tps: bool = False
        self.trace_tps_perf: bool = False
        
        # Seed configuration
        self.seed_config: Optional[Union[int, str, Tuple[str, int, int]]] = None
        
        # Top-level parameters
        self.temperature: Optional[float] = None
        self.top_p: Optional[float] = None
        self.top_k: Optional[int] = None
        self.freq_penalty: Optional[float] = None
        self.pres_penalty: Optional[float] = None
        
        # Script variables for database operations
        self.script_vars: Dict[str, str] = {}
    
    def initialize(self) -> None:
        """Initialize the application by loading configuration and setting up history."""
        # Load configuration
        self.config_manager.load_config()
        
        # Set up input history
        self.load_input_history()
        
        # Set up readline for command history
        readline.set_completer(self.input_history_completer)
        readline.parse_and_bind("tab: complete")
        readline.set_completer_delims(" \t\n;")
        
        # Register save function to be called on exit
        atexit.register(self.save_input_history)
    
    def get_history_path(self) -> str:
        """
        Get the path to the chat history file.
        
        Returns:
            Path to the chat history file
        """
        path = os.path.expanduser("~/.local/share/chatybot")
        os.makedirs(path, exist_ok=True)
        return os.path.join(path, ".chat_history")
    
    def save_input_history(self) -> None:
        """Save input history to a file before exiting."""
        if self.input_history:
            with open(self.get_history_path(), "w") as f:
                f.write("\n".join(self.input_history))
    
    def load_input_history(self) -> None:
        """Load input history from file."""
        try:
            with open(self.get_history_path(), "r") as f:
                self.input_history = [line.strip() for line in f.readlines() if line.strip()]
            # Set up readline history
            for line in self.input_history:
                readline.add_history(line)
        except FileNotFoundError:
            pass
    
    def input_history_completer(self, text: str, state: int) -> Optional[str]:
        """
        Completer function for readline to navigate input history.
        
        Args:
            text: Current input text
            state: Current state in the completion
            
        Returns:
            Next matching history item or None
        """
        if state == 0:
            # Filter history based on text
            self.input_history_matches = [h for h in self.input_history if h.startswith(text)]
            self.input_history_index = 0
        else:
            self.input_history_index += 1
        
        if self.input_history_index < len(self.input_history_matches):
            return self.input_history_matches[self.input_history_index]
        return None
    
    def get_openai_client(self, model_alias: str) -> AsyncOpenAI:
        """
        Creates an openai.AsyncOpenAI client instance based on the model's config.
        
        Args:
            model_alias: The model alias to get client for
            
        Returns:
            AsyncOpenAI client instance
            
        Raises:
            ValueError: If model alias is not found or API key is missing
        """
        model_config = self.config_manager.get_model_config(model_alias)
        
        api_key_env = model_config.get("api_key", "")
        api_key = os.environ.get(api_key_env)
        
        # Bypass strict API key requirement for local models/Ollama
        if not api_key:
            base_url = model_config.get("base_url", "")
            if api_key_env.upper() in ["OLLAMA", "NONE", "DUMMY", "LOCAL"] or "localhost" in base_url or "127.0.0.1" in base_url:
                api_key = "dummy-key-for-local"
            else:
                raise ValueError(
                    f"API key not found for model alias '{model_alias}'. "
                    f"Please set the '{api_key_env}' environment variable."
                )
        
        base_url = model_config.get("base_url")
        
        return AsyncOpenAI(
            api_key=api_key,
            base_url=base_url if base_url else None
        )
    
    async def chat_completion(self, prompt: str, stream: bool = False) -> str:
        """
        Send a prompt to the OpenAI API and return the response.
        
        Args:
            prompt: The prompt to send
            stream: Whether to stream the response
            
        Returns:
            The model's response
        """
        model_alias = self.config_manager.active_model_alias
        client = self.get_openai_client(model_alias)
        model_config = self.config_manager.get_model_config(model_alias)
        model_name = model_config["name"]
        
        # Replace placeholders in the prompt
        full_prompt = self.buffer_manager.replace_placeholders(prompt)
        
        # Prepare the prompt with file buffer and prompt buffer if available
        if self.buffer_manager.prompt_buffer:
            full_prompt = self.buffer_manager.prompt_buffer + "\n\n" + full_prompt
        if self.buffer_manager.file_buffer:
            full_prompt = f"File:\n{self.buffer_manager.file_buffer}\n\n{full_prompt}"
        
        # Add code-only instruction if flag is set
        if self.code_only_flag:
            full_prompt = "Do not explain or describe the code - generate the code requested only. " + full_prompt
        
        # Prepare messages for chat completion
        messages = [{"role": "user", "content": full_prompt}]
        
        is_nvidia = "nvidia" in model_config.get("base_url", "").lower() or "nvidia" in model_name.lower()
        is_reasoning_model = is_nvidia or "qwen" in model_name.lower()
        
        current_system_message = self.config_manager.system_message
        if is_reasoning_model and not self.reasoning_mode:
            if current_system_message:
                current_system_message += "\ndetailed thinking off"
            else:
                current_system_message = "detailed thinking off"
        
        # Use system prompt unless the model name contains "gemma"
        if "gemma" not in model_name.lower():
            messages.insert(0, {"role": "system", "content": current_system_message})
        
        # Prepare completion parameters
        temp = self.temperature if self.temperature is not None else model_config.get("temperature", 0.7)
        kwargs = {
            "model": model_name,
            "messages": messages,
            "temperature": temp,
        }
        
        # Add optional parameters if defined globally or in model config
        mt = self.config_manager.max_tokens if self.config_manager.max_tokens is not None else model_config.get("max_tokens")
        if mt is not None: kwargs["max_tokens"] = mt
        
        is_mistral = "mistral.ai" in model_config.get("base_url", "").lower()
        is_openai_official = "api.openai.com" in model_config.get("base_url", "").lower()
        is_google = "googleapis.com" in model_config.get("base_url", "").lower()
        is_bytez = "bytez.com" in model_config.get("base_url", "").lower()
        
        tp = self.top_p if self.top_p is not None else model_config.get("top_p")
        if tp is not None:
            if is_nvidia:
                kwargs.setdefault("extra_body", {}).setdefault("nvext", {})["top_p"] = tp
            else:
                kwargs["top_p"] = tp
        
        fp = self.freq_penalty if self.freq_penalty is not None else model_config.get("frequency_penalty")
        if fp is not None: kwargs["frequency_penalty"] = fp
        
        pp = self.pres_penalty if self.pres_penalty is not None else model_config.get("presence_penalty")
        if pp is not None: kwargs["presence_penalty"] = pp
        
        tk = self.top_k if self.top_k is not None else model_config.get("top_k")
        if tk is not None:
            if is_nvidia:
                kwargs.setdefault("extra_body", {}).setdefault("nvext", {})["top_k"] = tk
            elif not is_mistral and not is_openai_official and not is_google and not is_bytez:
                # Mistral, OpenAI official, Google Gemini, and Bytez APIs reject top_k as an extra input.
                # Only add for other providers (OpenRouter, etc.)
                kwargs.setdefault("extra_body", {})["top_k"] = tk
        
        # Seed handling
        current_seed = None
        if self.seed_config is not None:
            if self.seed_config == "time":
                current_seed = int(time.time())
            elif isinstance(self.seed_config, tuple) and self.seed_config[0] == "random":
                current_seed = random.randint(self.seed_config[1], self.seed_config[2])
            else:
                try:
                    current_seed = int(self.seed_config)
                except (ValueError, TypeError):
                    current_seed = None
        
        if current_seed is not None:
            if is_google or is_bytez:
                # Google Gemini and Bytez endpoints do not support 'seed' and reject it
                print(f"Warning: Seed parameter is not supported by {'Google' if is_google else 'Bytez'} API. Skipping.")
            else:
                print(f"Using seed: {current_seed}")
                if is_mistral:
                    # Mistral official API expects 'random_seed' instead of 'seed'
                    kwargs.setdefault("extra_body", {})["random_seed"] = current_seed
                else:
                    kwargs["seed"] = current_seed
        
        try:
            start_time = time.time()
            
            if self.trace_raw_payload:
                import json
                print("Payload:")
                print("-----------------------------")
                # Don't fail if kwargs can't be JSON serialized completely, fallback handled
                try:
                    print(json.dumps(kwargs, indent=2))
                except TypeError:
                    print(str(kwargs))
                print("---- end of payload ---")
            
            tps_records = []
            think_tokens_estimate = 0
            regular_tokens_estimate = 0
            
            if stream:
                kwargs["stream"] = True
                response = await client.chat.completions.create(**kwargs)
                
                full_response = ""
                print("Assistant: ", end="", flush=True)
                
                buffer = ""
                in_think_block = False
                
                async for chunk in response:
                    chunk_time = time.time()
                    if not chunk.choices: continue
                    delta = chunk.choices[0].delta
                    
                    reasoning = getattr(delta, "reasoning_content", getattr(delta, "reasoning", None))
                    if reasoning:
                        full_response += reasoning
                        think_tokens_estimate += 1
                        if self.trace_tps_perf:
                            tps_records.append((chunk_time, "think", 1))
                        if self.show_thinking:
                            print(f"\033[90m{reasoning}\033[0m", end="", flush=True)
                    
                    if delta.content:
                        content = delta.content
                        full_response += content
                        
                        if in_think_block or "<think>" in content:
                            think_tokens_estimate += 1
                            if self.trace_tps_perf:
                                tps_records.append((chunk_time, "think", 1))
                        else:
                            regular_tokens_estimate += 1
                            if self.trace_tps_perf:
                                tps_records.append((chunk_time, "regular", 1))
                        
                        buffer += content
                        while buffer:
                            if not in_think_block:
                                think_idx = buffer.find("<think>")
                                if think_idx != -1:
                                    print(buffer[:think_idx], end="", flush=True)
                                    if self.show_thinking:
                                        print("\033[90m<think>", end="", flush=True)
                                    buffer = buffer[think_idx + len("<think>"):]
                                    in_think_block = True
                                else:
                                    match_len = 0
                                    for i in range(len("<think>") - 1, 0, -1):
                                        if buffer.endswith("<think>"[:i]):
                                            match_len = i
                                            break
                                    if match_len > 0:
                                        print(buffer[:-match_len], end="", flush=True)
                                        buffer = buffer[-match_len:]
                                        break
                                    else:
                                        print(buffer, end="", flush=True)
                                        buffer = ""
                            else:
                                end_idx = buffer.find("</think>")
                                if end_idx != -1:
                                    if self.show_thinking:
                                        print(buffer[:end_idx] + "</think>\033[0m", end="", flush=True)
                                    buffer = buffer[end_idx + len("</think>"):]
                                    in_think_block = False
                                else:
                                    match_len = 0
                                    for i in range(len("</think>") - 1, 0, -1):
                                        if buffer.endswith("</think>"[:i]):
                                            match_len = i
                                            break
                                    if match_len > 0:
                                        if self.show_thinking:
                                            print(buffer[:-match_len], end="", flush=True)
                                        buffer = buffer[-match_len:]
                                        break
                                    else:
                                        if self.show_thinking:
                                            print(buffer, end="", flush=True)
                                        buffer = ""
            
                if buffer:
                    if in_think_block and self.show_thinking:
                        print(buffer + "\033[0m", end="", flush=True)
                    elif not in_think_block:
                        print(buffer, end="", flush=True)
                elif in_think_block and self.show_thinking:
                    print("\033[0m", end="", flush=True)
                print()  # New line after streaming
            else:
                response = await client.chat.completions.create(**kwargs)
                message = response.choices[0].message
                content = message.content or ""
                reasoning = getattr(message, "reasoning_content", getattr(message, "reasoning", None)) or ""
                
                full_response = ""
                if reasoning:
                    if self.show_thinking:
                        print(f"\033[90m{reasoning}\033[0m")
                    full_response += f"{reasoning}\n\n"
                
                full_response += content
                
                import re
                if not self.show_thinking:
                    print_content = re.sub(r'<think>.*?</think>\s*', '', content, flags=re.DOTALL)
                else:
                    print_content = re.sub(r'(<think>.*?</think>)', r'\033[90m\1\033[0m', content, flags=re.DOTALL)
                
                if not print_content.strip() and not (reasoning and self.show_thinking):
                    print("Warning: Received an empty response from the model.")
                elif print_content.strip():
                    print(print_content)
            
            # Calculate and display metrics
            elapsed_time = time.time() - start_time
            print(f"\nExecution time: {elapsed_time:.2f} seconds")
            
            out_tokens = 0
            if hasattr(response, 'usage') and response.usage:
                out_tokens = response.usage.completion_tokens
                print(f"Input tokens: {response.usage.prompt_tokens}, Output tokens: {out_tokens}")
            
            if think_tokens_estimate + regular_tokens_estimate > 0 and out_tokens > 0:
                ratio_think = think_tokens_estimate / (think_tokens_estimate + regular_tokens_estimate)
                think_t = int(out_tokens * ratio_think)
                reg_t = out_tokens - think_t
            else:
                think_t = think_tokens_estimate
                reg_t = regular_tokens_estimate
            
            if self.trace_tps:
                tps_think = think_t / elapsed_time if elapsed_time > 0 else 0
                tps_reg = reg_t / elapsed_time if elapsed_time > 0 else 0
                tps_total = (think_t + reg_t) / elapsed_time if elapsed_time > 0 else 0
                print(f"TPS (Total): {tps_total:.2f} (Think: {tps_think:.2f}, Regular: {tps_reg:.2f})")
            
            if self.trace_tps_perf and tps_records:
                buckets = {}
                for t, typ, count in tps_records:
                    sec_offset = int(t - start_time)
                    if sec_offset not in buckets:
                        buckets[sec_offset] = {"think": 0, "regular": 0}
                    buckets[sec_offset][typ] += count
                
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                csv_filename = f"tps+{timestamp}.csv"
                try:
                    import csv
                    with open(csv_filename, "w", newline="") as csvfile:
                        writer = csv.writer(csvfile, quoting=csv.QUOTE_ALL)
                        writer.writerow(["Second", "Think_Tokens", "Regular_Tokens", "Total_Tokens"])
                        for sec in sorted(buckets.keys()):
                            th = buckets[sec]["think"]
                            rg = buckets[sec]["regular"]
                            writer.writerow([sec, th, rg, th + rg])
                    print(f"TPS performance saved to '{csv_filename}'")
                except Exception as e:
                    print(f"Error saving TPS performance: {e}")
            
            # Log user entry with datetime and model info
            if self.logging_manager.logging_active:
                current_time = self.logging_manager.format_datetime(datetime.now())
                self.logging_manager.log_message(f"Datetime: {current_time}")
                self.logging_manager.log_message(f"Model: {model_alias} ({model_name})")
                self.logging_manager.log_message(f"User: {prompt}")
            
            self.chat_history.append((prompt, full_response))
            
            # Log assistant entry with completion datetime and token count
            if self.logging_manager.logging_active:
                input_tokens = response.usage.prompt_tokens if hasattr(response, 'usage') else "N/A"
                output_tokens = response.usage.completion_tokens if hasattr(response, 'usage') else "N/A"
                self.logging_manager.log_message(f"\nExecution time: {elapsed_time:.2f} seconds")
                self.logging_manager.log_message(f"Number of tokens: Input {input_tokens}, Output {output_tokens}")
                self.logging_manager.log_message(f"Assistant: {full_response}\n")
            
            return full_response
        except Exception as e:
            error_msg = f"Error during chat completion: {str(e)}"
            print(error_msg)
            if self.logging_manager.logging_active:
                self.logging_manager.log_message(error_msg)
            return f"Error: {str(e)}"
    
    async def execute_script_command(self, command: str, original_handler: Callable[[str], Union[bool, str]]) -> bool:
        """
        Execute a command within a script context.
        
        Args:
            command: The command to execute
            original_handler: The original command handler function
            
        Returns:
            True if the command was handled, False otherwise
        """
        # Handle script-specific commands
        if command.startswith("set "):
            try:
                _, var_part = command.split(maxsplit=1)
                var_name, var_value = var_part.split("=", maxsplit=1)
                # Replace variables in the value before storing
                def replace_var(match):
                    var_name_match = match.group(1)
                    return self.buffer_manager.script_vars.get(var_name_match, "")
                processed_value = re.sub(r'\$\{(\w+)\}', replace_var, var_value.strip().strip('"\''))
                self.buffer_manager.script_vars[var_name.strip()] = processed_value
                return True
            except ValueError:
                print("Invalid set command. Usage: set <name> = <value>")
                return True
        
        # Replace variables in the command
        def replace_var(match):
            var_name = match.group(1)
            return self.buffer_manager.script_vars.get(var_name, "")
        
        processed_command = re.sub(r'\$\{(\w+)\}', replace_var, command)
        
        # Handle wait command
        if processed_command.startswith("wait "):
            try:
                _, seconds = processed_command.split(maxsplit=1)
                await asyncio.sleep(float(seconds))
                return True
            except ValueError:
                print("Invalid wait command. Usage: wait <seconds>")
                return True
        
        # Handle if-then commands
        if processed_command.startswith("if "):
            try:
                # Simple condition checking for now (can be expanded)
                if "then" in processed_command:
                    condition, then_part = processed_command[3:].split("then", maxsplit=1)
                    condition = condition.strip()
                    then_command = then_part.strip()
                    
                    # Simple condition evaluation (can be expanded)
                    # Check if condition is a variable name and its value is truthy
                    if condition in self.buffer_manager.script_vars:
                        # More robust truthy check for string variables
                        if self.buffer_manager.script_vars[condition].lower() in ["true", "1", "yes"]:
                            return await self.execute_script_command(then_command, original_handler)
                        elif self.buffer_manager.script_vars[condition].lower() in ["false", "0", "no", ""]:
                            return True # Condition is false, do nothing
                    elif condition.lower() == "true":
                        return await self.execute_script_command(then_command, original_handler)
                    elif condition.lower() == "false":
                        return True
            except ValueError:
                print("Invalid if command. Usage: if <condition> then <command>")
                return True
        
        # For other commands, use the original handler
        if processed_command.startswith("/"):
            # The original_handler (handle_escape_command) is now async, so we must await it.
            result = await original_handler(processed_command)
            if result == "EXECUTE_PROMPT":
                # This means a /prompt command was executed and confirmed.
                # The prompt buffer is already set by handle_escape_command.
                # We need to trigger the chat completion here.
                temp_prompt = "Using the following prompt, please provide a response:\n" + self.buffer_manager.prompt_buffer
                response = await self.chat_completion(temp_prompt, stream=self.streaming_enabled)
                self.logging_manager.log_message(f"User: {temp_prompt}\nAssistant: {response}\n")
                self.buffer_manager.prompt_buffer = ""  # Clear the buffer after execution
                return True # Handled
            return result if isinstance(result, bool) else False # Return boolean indicating if handled
        
        # If not a command, treat as chat input
        if self.script_context:
            response = await self.chat_completion(processed_command, stream=self.streaming_enabled)
            self.logging_manager.log_message(f"User: {processed_command}\nAssistant: {response}\n")
            return True
        
        return False
    
    async def execute_script(self, script_path: str) -> None:
        """
        Execute a script file containing multiple commands.
        
        Args:
            script_path: Path to the script file
        """
        try:
            print("Loading script: ", script_path)
            with open(script_path, "r") as f:
                script_content = f.read()
            
            # Remove comments (lines starting with #)
            script_content = "\n".join(
                line for line in script_content.split("\n")
                if not line.strip().startswith("#")
            )
            
            # Split commands by newlines or semicolons
            commands_list = []
            for line in script_content.split("\n"):
                line = line.strip()
                if not line:
                    continue
                # Attempt to split by semicolon, but be aware of quotes
                if ';' in line:
                    # Split by semicolon but preserve quoted strings
                    commands = []
                    current = []
                    in_quotes = False
                    quote_char = None
                    
                    for char in line:
                        if char in ('"', "'") and not in_quotes:
                            in_quotes = True
                            quote_char = char
                            current.append(char)
                        elif char == quote_char and in_quotes:
                            in_quotes = False
                            quote_char = None
                            current.append(char)
                        elif char == ';' and not in_quotes:
                            commands.append(''.join(current).strip())
                            current = []
                        else:
                            current.append(char)
                    
                    if current:
                        commands.append(''.join(current).strip())
                    
                    commands_list.extend([cmd for cmd in commands if cmd])
                else:
                    commands_list.append(line)
            
            # Execute each command
            self.script_context = True
            multi_line_buffer = []
            in_multi_line = False
            
            for cmd in commands_list:
                # Check if we're in multi-line mode and not processing an escaped command
                if self.multi_line_mode and not cmd.startswith("/") and not in_multi_line:
                    in_multi_line = True
                    multi_line_buffer = [cmd]
                    continue
                
                if in_multi_line:
                    if cmd.strip() == ";;":
                        # End of multi-line input, process it
                        full_prompt = "\n".join(multi_line_buffer)
                        print(f"Executing multi-line prompt: {full_prompt[:50]}...")
                        handled = await self.execute_script_command(full_prompt, self.handle_escape_command)
                        if not handled:
                            print(f"Error processing multi-line command")
                        in_multi_line = False
                        multi_line_buffer = []
                    elif cmd.startswith("/"):
                        # Escaped command in the middle of multi-line - process the buffer first
                        full_prompt = "\n".join(multi_line_buffer)
                        print(f"Executing multi-line prompt: {full_prompt[:50]}...")
                        handled = await self.execute_script_command(full_prompt, self.handle_escape_command)
                        if not handled:
                            print(f"Error processing multi-line command")
                        
                        # Then process the escaped command
                        print(f"Executing: {cmd}")
                        handled = await self.execute_script_command(cmd, self.handle_escape_command)
                        if not handled:
                            print(f"Unknown command in script: {cmd}")
                        in_multi_line = False
                        multi_line_buffer = []
                    else:
                        # Continue building multi-line input
                        multi_line_buffer.append(cmd)
                else:
                    print(f"Executing: {cmd}")
                    handled = await self.execute_script_command(cmd, self.handle_escape_command)
                    if not handled:
                        print(f"Unknown command in script: {cmd}")
            
            print("Script execution finished")
            
            # If we ended while in multi-line mode, process what we have
            if in_multi_line and multi_line_buffer:
                full_prompt = "\n".join(multi_line_buffer)
                print(f"Executing multi-line prompt: {full_prompt[:50]}...")
                handled = await self.execute_script_command(full_prompt, self.handle_escape_command)
                if not handled:
                    print(f"Error processing multi-line command")
        
        except Exception as e:
            print(f"Error executing script: {str(e)}")
        finally:
            self.script_context = False
    
    async def handle_escape_command(self, command: str) -> Union[bool, str]:
        """
        Handle escape commands.
        
        Args:
            command: The command to handle
            
        Returns:
            True if the command was handled, False otherwise, or "EXECUTE_PROMPT" for prompt execution
        """
        parts = command.split(maxsplit=2)
        if self.logging_manager.logging_active:
            self.logging_manager.log_message(f"Escape command: {command}")
        cmd = parts[0].lower()
        
        if cmd == "/help":
            self.show_help()
            return True
        
        elif cmd == "/trace":
            if len(parts) >= 3:
                subcmd = parts[1].lower()
                state = parts[2].lower()
                is_on = state == "on"
                if subcmd == "rawpayload":
                    self.trace_raw_payload = is_on
                    print(f"Trace rawpayload set to {is_on}")
                elif subcmd == "tps":
                    self.trace_tps = is_on
                    print(f"Trace tps set to {is_on}")
                elif subcmd == "tpsperf":
                    self.trace_tps_perf = is_on
                    print(f"Trace tpsperf set to {is_on}")
                else:
                    print("Unknown /trace subcommand. Use rawpayload, tps, or tpsperf.")
            else:
                print("Usage: /trace <rawpayload|tps|tpsperf> <on|off>")
            return True
        
        elif cmd == "/prompt":
            if len(parts) < 2:
                print("Usage: /prompt <file>")
                return True
            
            file_path = parts[1]
            try:
                with open(file_path, "r") as f:
                    self.buffer_manager.prompt_buffer = f.read()
                print(f"\nPrompt loaded from '{file_path}':")
                print("-" * 40)
                print(self.buffer_manager.prompt_buffer)
                print("-" * 40)
                
                # Ask for confirmation only if not in script context
                if not self.script_context:
                    while True:
                        confirm = input("\nExecute this prompt? (Y/N): ").strip().lower()
                        if confirm in ['y', 'yes']:
                            print("\nExecuting prompt...")
                            # Set a flag to execute the prompt in the main loop
                            return "EXECUTE_PROMPT"
                        elif confirm in ['n', 'no']:
                            self.buffer_manager.prompt_buffer = ""
                            print("Prompt discarded.")
                            return True
                        else:
                            print("Please enter Y or N.")
                else:
                    # In script context, assume confirmation and return flag
                    return "EXECUTE_PROMPT"
            except Exception as e:
                print(f"Error reading prompt file: {str(e)}")
            return True
        
        elif cmd.startswith("/filebank"):
            # Handle filebank commands
            bank_num = cmd[9:]  # Extract the number after /filebank
            if not bank_num.isdigit() or int(bank_num) < 1 or int(bank_num) > 5:
                print("Invalid filebank number. Please use /filebank1 through /filebank5.")
                return True
            
            bank_num_int = int(bank_num)
            
            if len(parts) < 2:
                print(f"Usage: {cmd} <file> or {cmd} clear or {cmd} show [all]")
                return True
            
            subcommand = parts[1].lower()
            
            if subcommand == "clear":
                self.buffer_manager.clear_file_bank(bank_num_int)
                return True
            elif subcommand == "show":
                show_all = len(parts) > 2 and parts[2].lower() == "all"
                self.buffer_manager.show_file_bank(bank_num_int, show_all)
                return True
            else:
                # Assume it's a file path
                file_path = parts[1]
                try:
                    self.buffer_manager.load_file_to_bank(bank_num_int, file_path)
                except Exception as e:
                    print(f"Error reading file: {str(e)}")
                return True
        
        elif cmd == "/file":
            if len(parts) < 2:
                print("Usage: /file <path>")
                return True
            
            file_path = parts[1]
            try:
                self.buffer_manager.load_file_to_buffer(file_path)
            except Exception as e:
                print(f"Error reading file: {str(e)}")
            return True
        
        elif cmd == "/clearfile":
            self.buffer_manager.clear_file_buffer()
            return True
        
        elif cmd == "/showfile":
            show_all = len(parts) > 1 and parts[1].lower() == "all"
            self.buffer_manager.show_file_buffer(show_all)
            return True
        
        elif cmd == "/model":
            if len(parts) < 2:
                # Show current model
                model_config = self.config_manager.get_model_config(self.config_manager.active_model_alias)
                print(f"Current model: {model_config['name']} (alias: {self.config_manager.active_model_alias})")
                return True
            
            model_alias = parts[1]
            self.config_manager.set_active_model(model_alias)
            model_config = self.config_manager.get_model_config(model_alias)
            print(f"Switched to model: {model_config['name']} (alias: {model_alias})")
            return True
        
        elif cmd == "/logging":
            if len(parts) < 2:
                print("Usage: /logging <start|end>")
                return True
            
            action = parts[1].lower()
            if action == "start":
                self.logging_manager.start_logging()
            elif action == "end":
                self.logging_manager.stop_logging()
            else:
                print("Invalid logging action. Use 'start' or 'end'.")
            return True
        
        elif cmd == "/save":
            if len(parts) < 2:
                print("Usage: /save <file>")
                return True
            
            file_path = parts[1]
            if self.chat_history:
                last_response = self.chat_history[-1][1]
                try:
                    directory = os.path.dirname(file_path)
                    if directory and not os.path.exists(directory):
                        os.makedirs(directory, exist_ok=True)
                        print(f"Created directory path: '{directory}'")
                    
                    with open(file_path, "w") as f:
                        f.write(last_response)
                    print(f"Last chat completion saved to '{file_path}'.")
                    
                    # If note mode is on, process the file to extract code blocks
                    if self.note_mode:
                        print(f"Note mode is ON. Processing file '{file_path}'...")
                        process_file(file_path)
                except Exception as e:
                    print(f"Error saving file: {str(e)}")
            else:
                print("No chat history to save.")
            return True
        
        elif cmd == "/notemode":
            if len(parts) < 2:
                print(f"Note mode is currently {'ON' if self.note_mode else 'OFF'}")
                return True
            
            action = parts[1].lower()
            if action == "on":
                self.note_mode = True
                print("Note mode enabled. Code blocks will be extracted when using /save.")
            elif action == "off":
                self.note_mode = False
                print("Note mode disabled.")
            else:
                print("Invalid note mode action. Use 'on' or 'off'.")
            return True
        
        elif cmd == "/codeonly":
            self.code_only_flag = True
            print("Code-only mode enabled.")
            return True
        
        elif cmd == "/codeoff":
            self.code_only_flag = False
            print("Code-only mode disabled.")
            return True
        
        elif cmd == "/multiline":
            self.multi_line_mode = not self.multi_line_mode
            print(f"Multi-line mode {'enabled' if self.multi_line_mode else 'disabled'}. "
                  f"{'Use ;; to end input' if self.multi_line_mode else ''}")
            return True
        
        elif cmd == "/system":
            if len(parts) < 2:
                print(f"Current system message: {self.config_manager.system_message}")
                return True
            
            self.config_manager.system_message = command.split(maxsplit=1)[1].strip(' "\'')
            print(f"System message updated: {self.config_manager.system_message}")
            return True
        
        elif cmd == "/temp":
            if len(parts) < 2:
                current_temp = self.temperature if self.temperature is not None else self.config_manager.get_model_config(self.config_manager.active_model_alias).get("temperature", 0.7)
                print(f"Current temperature: {current_temp}")
                return True
            
            try:
                temp = float(parts[1])
                if not 0.0 <= temp <= 2.0:
                    raise ValueError
                self.temperature = temp
                print(f"Temperature set to {temp}")
            except ValueError:
                print("Invalid temperature value. Please provide a number between 0.0 and 2.0.")
            return True
        
        elif cmd == "/maxtokens":
            if len(parts) < 2:
                current_max = self.config_manager.max_tokens if self.config_manager.max_tokens is not None else self.config_manager.get_model_config(self.config_manager.active_model_alias).get("max_tokens", "Default")
                print(f"Current max tokens: {current_max}")
                return True
            
            try:
                max_tokens = int(parts[1])
                if max_tokens <= 0:
                    raise ValueError
                self.config_manager.max_tokens = max_tokens
                print(f"Max tokens set to {max_tokens}")
            except ValueError:
                print("Invalid max tokens value. Please provide a positive integer.")
            return True
        
        elif cmd == "/top_p":
            if len(parts) < 2:
                current_tp = self.top_p if self.top_p is not None else self.config_manager.get_model_config(self.config_manager.active_model_alias).get("top_p", "Default")
                print(f"Current top_p: {current_tp}")
                return True
            try:
                val = float(parts[1])
                self.top_p = val
                print(f"top_p set to {val}")
            except ValueError:
                print("Invalid top_p value. Please enter a float.")
            return True
        
        elif cmd == "/top_k":
            if len(parts) < 2:
                current_tk = self.top_k if self.top_k is not None else self.config_manager.get_model_config(self.config_manager.active_model_alias).get("top_k", "Default")
                print(f"Current top_k: {current_tk}")
                return True
            try:
                val = int(parts[1])
                self.top_k = val
                print(f"top_k set to {val}")
            except ValueError:
                print("Invalid top_k value. Please enter an integer.")
            return True
        
        elif cmd == "/freq_penalty":
            if len(parts) < 2:
                current_fp = self.freq_penalty if self.freq_penalty is not None else self.config_manager.get_model_config(self.config_manager.active_model_alias).get("frequency_penalty", "Default")
                print(f"Current frequency penalty: {current_fp}")
                return True
            try:
                val = float(parts[1])
                self.freq_penalty = val
                print(f"Frequency penalty set to {val}")
            except ValueError:
                print("Invalid frequency penalty value. Please enter a float.")
            return True
        
        elif cmd == "/pres_penalty":
            if len(parts) < 2:
                current_pp = self.pres_penalty if self.pres_penalty is not None else self.config_manager.get_model_config(self.config_manager.active_model_alias).get("presence_penalty", "Default")
                print(f"Current presence penalty: {current_pp}")
                return True
            try:
                val = float(parts[1])
                self.pres_penalty = val
                print(f"Presence penalty set to {val}")
            except ValueError:
                print("Invalid presence penalty value. Please enter a float.")
            return True
        
        elif cmd == "/reasoning":
            if len(parts) > 1 and parts[1].lower() in ["on", "off"]:
                if parts[1].lower() == "on":
                    self.reasoning_mode = True
                else:
                    self.reasoning_mode = False
                print(f"Reasoning mode is now {'ON' if self.reasoning_mode else 'OFF'}")
            else:
                print(f"Reasoning mode is currently {'ON' if self.reasoning_mode else 'OFF'}")
            return True
        
        elif cmd == "/thinking":
            if len(parts) > 1 and parts[1].lower() in ["on", "off"]:
                if parts[1].lower() == "on":
                    self.show_thinking = True
                else:
                    self.show_thinking = False
                print(f"Thinking display is now {'ON' if self.show_thinking else 'OFF'}")
            else:
                print(f"Thinking display is currently {'ON' if self.show_thinking else 'OFF'}")
            return True
        
        elif cmd == "/seed":
            if len(parts) < 2:
                print(f"Current seed setting: {self.seed_config}")
                return True
            
            arg = parts[1].lower()
            if arg in ["clear", "none", "off"]:
                self.seed_config = None
                print("Seed cleared.")
            elif arg == "time":
                self.seed_config = "time"
                print("Seed set to 'time' (uses Unix timestamp per completion).")
            elif arg == "random":
                if len(parts) < 3:
                    print("Usage: /seed random <min>, <max>")
                    return True
                try:
                    # Handle both "random 1,999" and "random 1, 999"
                    range_str = parts[2]
                    if ',' not in range_str:
                        print("Usage: /seed random <min>, <max>")
                        return True
                    v1_str, v2_str = range_str.split(',', 1)
                    v1 = int(v1_str.strip())
                    v2 = int(v2_str.strip())
                    self.seed_config = ("random", v1, v2)
                    print(f"Seed set to random range: {v1} to {v2}")
                except ValueError:
                    print("Invalid range. Use: /seed random <min>, <max>")
            else:
                try:
                    seed_val = int(parts[1])
                    self.seed_config = seed_val
                    print(f"Seed set to fixed value: {seed_val}")
                except ValueError:
                    print("Invalid seed. Use an integer, 'time', or 'random <min>, <max>'.")
            return True
        
        elif cmd == "/stream":
            self.streaming_enabled = not self.streaming_enabled
            print(f"Streaming responses {'enabled' if self.streaming_enabled else 'disabled'}")
            return True
        
        elif cmd == "/listmodels":
            self.config_manager.list_models()
            return True
        
        elif cmd == "/script":
            if len(parts) < 2:
                print("Usage: /script <file>")
                return True
            
            script_path = parts[1]
            print("command /script with ", script_path)
            # Execute script asynchronously so it doesn't block the main loop
            await self.execute_script(script_path)
            return True
        
        elif cmd == "/quit":
            print("Goodbye! Thanks for chatting.")
            self.logging_manager.stop_logging()
            self.save_input_history()
            exit(0)
        
        # Database commands
        elif cmd == "/setdb":
            if len(parts) < 2:
                print("Usage: /setdb <dbname>")
                return True
            dbname = parts[1].strip('"')
            set_db(dbname)
            return True
        elif cmd == "/dblist":
            list_dbs()
            return True
        elif cmd == "/searchdb":
            if len(parts) < 2:
                print("Usage: /searchdb <query>")
                return True
            query = parts[1].strip('"')
            search_db(query)
            return True
        elif cmd == "/dblog":
            dblog()
            return True
        elif cmd == "/loadvar":
            if len(parts) < 2:
                print("Usage: /loadvar <varname> [ALL | id | range]")
                return True
            varname = parts[1].strip('"')
            extra = parts[2] if len(parts) > 2 else None
            load_var(varname, extra)
            return True
        elif cmd == "/savevar":
            if len(parts) < 3:
                print("Usage: /savevar <varname> <filename>")
                return True
            varname = parts[1].strip('"')
            filename = parts[2].strip('"')
            save_var(varname, filename)
            return True
        
        elif cmd == "/mem":
            self.buffer_manager.show_memory_usage()
            return True
        
        elif cmd == "/dump":
            var_name = parts[1] if len(parts) > 1 else "all"
            self.buffer_manager.dump_variables(var_name)
            return True
        
        elif cmd == "/setvar":
            if len(parts) < 3:
                print("Usage: /setvar <varname> <value>")
                return True
            var_name = parts[1].strip('"')
            var_value = parts[2]
            self.buffer_manager.set_script_var(var_name, var_value)
            return True
        
        return False
    
    def show_help(self) -> None:
        """Show help message with available commands."""
        print("Active escape commands:")
        print("  /help - Show this help message.")
        print("  /prompt <file> - Load a prompt from a file.")
        print("  /file <path> - Read a text file into the buffer.")
        print("  /showfile [all] - Show the first 100 characters of the file buffer or the entire file if 'all' is specified.")
        print("  /clearfile - Clear the file buffer.")
        print("  /filebank{1..5} <file> - Load a text file into filebank1 through filebank5.")
        print("  /filebank{1..5} clear - Clear the specified filebank.")
        print("  /filebank{1..5} show [all] - Show the first 100 characters of the filebank or all if 'all' is specified.")
        print("  /model [alias] - Switch to a different model or show current model.")
        print("  /listmodels - List available models from toml.")
        print("  /logging <start|end> - Start or stop logging.")
        print("  /save <file> - Save the last chat completion to a file.")
        print("  /notemode <on|off> - Toggle note mode for /save command.")
        print("  /codeonly - Set flag to generate code only without explanations.")
        print("  /codeoff - Reverse the code-only flag.")
        print("  /multiline - Toggle multi-line input mode (use ';;' to end input).")
        print("  /system <message> - Set a custom system message.")
        print("  /temp <value> - Set temperature for the current model (0.0-2.0).")
        print("  /maxtokens <value> - Set max tokens for the current model.")
        print("  /top_p <value> - Set top_p for the current model (0.0-1.0).")
        print("  /top_k <value> - Set top_k for the current model.")
        print("  /freq_penalty <value> - Set frequency penalty (-2.0-2.0).")
        print("  /pres_penalty <value> - Set presence penalty (-2.0-2.0).")
        print("  /reasoning <on|off> - Toggle reasoning (thinking) for NVIDIA and Qwen models.")
        print("  /thinking <on|off> - Toggle display of <think> blocks and reasoning text.")
        print("  /seed <value> - Set seed (int, 'time', or 'random <min>,<max>').")
        print("  /stream - Toggle streaming responses.")
        print("  /trace <rawpayload|tps|tpsperf> <on|off> - Debugging options")
        print("  /script <file> - Execute a script file containing multiple commands.")
        print("  /quit - Exit the program.")
        print("  /setdb <dbname> - Create or select a TinyDB database. Use 'Null' to deactivate.")
        print("  /dblist - List all TinyDB databases in the db directory.")
        print("  /searchdb <query> - Search all docs in the current database.")
        print("  /dblog - Log the last chat completion to the database.")
        print("  /loadvar <varname> [ALL|id|range] - Load search buffer, all docs, a doc ID, or a range (e.g. 1-5) into a variable.")
        print("  /savevar <varname> <filename> - Save a variable's contents to a file.")
        print("  /setvar <varname> <value> - Set a script variable to a string.")
        print("  /mem - Show size of buffers and script variables.")
        print("  /dump [varname|all] - Print content of buffers or script variables.")
        print("\nScript-specific features:")
        print("  set <name> = <value> - Define a variable")
        print("  ${name} - Reference a variable")
        print("  if <condition> then <command> - Conditional execution")
        print("  wait <seconds> - Pause execution")
        print("  # comment - Comments in script files")
    
    async def get_multi_line_input(self) -> str:
        """
        Get multi-line input from the user.
        
        Returns:
            Multi-line input as a single string
        """
        print("Multi-line mode. Enter your prompt (use ';;' on a new line to finish):")
        lines = []
        while True:
            line = input()
            if line.strip() == ";;":
                break
            lines.append(line)
        return "\n".join(lines)
    
    async def main_loop(self) -> None:
        """Main chat loop."""
        print("===========================")
        print("Chatybot.py                ")
        print("Created by Jon Allen - 2025")
        print("===========================")
        print(f"Active model: {self.config_manager.get_model_config(self.config_manager.active_model_alias)['name']} (alias: {self.config_manager.active_model_alias})")
        
        while True:
            try:
                if self.multi_line_mode:
                    prompt = await self.get_multi_line_input()
                else:
                    prompt = input("chat --> ")
                
                # Add to input history
                if prompt.strip() and (not self.input_history or prompt != self.input_history[-1]):
                    self.input_history.append(prompt)
                    readline.add_history(prompt)
                
                if not prompt.strip():
                    continue
                
                if prompt.startswith("/"):
                    result = await self.handle_escape_command(prompt)
                    if result == "EXECUTE_PROMPT":
                        # Execute the buffered prompt
                        temp_prompt = "Using the following prompt, please provide a response:\n" + self.buffer_manager.prompt_buffer
                        response = await self.chat_completion(temp_prompt, stream=self.streaming_enabled)
                        self.buffer_manager.prompt_buffer = ""  # Clear the buffer after execution
                    continue
                
                response = await self.chat_completion(prompt, stream=self.streaming_enabled)
            
            except KeyboardInterrupt:
                print("\nGoodbye! Thanks for chatting.")
                self.logging_manager.stop_logging()
                self.save_input_history()
                break
            except Exception as e:
                print(f"Error: {str(e)}")
    
    def run(self) -> None:
        """Run the application."""
        self.initialize()
        asyncio.run(self.main_loop())


def run():
    """Entry point for the application."""
    global app
    app = ChatybotApp()
    # Also set the module-level app variable
    import sys
    current_module = sys.modules[__name__]
    current_module.app = app
    app.run()


if __name__ == "__main__":
    run()
