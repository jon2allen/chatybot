#! /usr/bin/env python3
import asyncio
import os
import readline
import time
import tomllib
from datetime import datetime
from typing import Dict, Any, List, Tuple, Optional, Callable, Union
import logging
import atexit
from .chatydb import set_db, search_db, dblog, load_var, save_var, list_dbs, SEARCHBUFFER

# Add these imports at the top of the file
import re
import shlex
import random
from .extract_code import process_file  # Import the function from extract_code.py

try:
    import openai
    from openai import AsyncOpenAI
except ImportError:
    raise ImportError("OpenAI SDK is not installed. Please install it with 'pip install openai'.")

# Global variables
CONFIG: Dict[str, Any] = {}
DEFAULT_MODEL_ALIAS = None
ACTIVE_MODEL_ALIAS = None
CHAT_HISTORY: List[Tuple[str, str]] = []
FILE_BUFFER = ""
PROMPT_BUFFER = ""
FILE_BANKS: Dict[str, str] = {f"filebank{i}": "" for i in range(1, 6)}
CODE_ONLY_FLAG = False
LOGGING_ACTIVE = False
LOG_FILE = None
MULTI_LINE_MODE = False
INPUT_HISTORY: List[str] = []
INPUT_HISTORY_INDEX = -1
INPUT_HISTORY_MATCHES: List[str] = []
SYSTEM_MESSAGE = "You are a helpful assistant."
MAX_TOKENS = None
STREAMING_ENABLED = False
NOTE_MODE = False  # New global variable for note mode
REASONING_MODE = True  # New global variable for NVIDIA reasoning toggle
SHOW_THINKING = True  # Toggle whether to show <think> tags / reasoning text

# Add these global variables
SCRIPT_VARS: Dict[str, str] = {}
SCRIPT_CONTEXT = False
TOP_P = None
TOP_K = None
FREQ_PENALTY = None
PRES_PENALTY = None
SEED_CONFIG = None

def load_config() -> None:
    """
    Load the configuration from chat_config.toml.
    """
    global CONFIG, DEFAULT_MODEL_ALIAS, ACTIVE_MODEL_ALIAS, SYSTEM_MESSAGE, MAX_TOKENS
    global TOP_P, TOP_K, FREQ_PENALTY, PRES_PENALTY

    config_path = os.path.expanduser("~/.config/chatybot/chat_config.toml")
    
    # Create the config directory if it doesn't exist
    os.makedirs(os.path.dirname(config_path), exist_ok=True)
    
    # Check if config exists in ~/.config, otherwise try local and copy
    if not os.path.exists(config_path):
        local_config = os.path.join(os.path.dirname(__file__), "chat_config.toml")
        if os.path.exists(local_config):
            import shutil
            shutil.copy2(local_config, config_path)
            print(f"Copied local '{local_config}' to '{config_path}'")
        else:
            raise FileNotFoundError(f"Configuration file not found. Please create '{config_path}'.")

    try:
        with open(config_path, "rb") as f:
            CONFIG = tomllib.load(f)
    except tomllib.TOMLDecodeError:
        raise ValueError(f"Invalid TOML format in '{config_path}'.")

    # Set the default model alias to the first model in the config
    DEFAULT_MODEL_ALIAS = next(iter(CONFIG["models"]))
    ACTIVE_MODEL_ALIAS = DEFAULT_MODEL_ALIAS

    # Load system message if specified in config
    if "system_message" in CONFIG:
        SYSTEM_MESSAGE = CONFIG["system_message"]

    # Load max tokens if specified in config
    if "max_tokens" in CONFIG:
        MAX_TOKENS = CONFIG["max_tokens"]

    # Load other parameters if specified in config
    if "top_p" in CONFIG:
        TOP_P = CONFIG["top_p"]
    if "top_k" in CONFIG:
        TOP_K = CONFIG["top_k"]
    if "frequency_penalty" in CONFIG:
        FREQ_PENALTY = CONFIG["frequency_penalty"]
    if "presence_penalty" in CONFIG:
        PRES_PENALTY = CONFIG["presence_penalty"]

def get_openai_client(model_alias: str) -> AsyncOpenAI:
    """
    Creates an openai.AsyncOpenAI client instance based on the model's config,
    using the _API_KEY environment variable for authentication.
    """
    model_config = CONFIG["models"].get(model_alias)

    if not model_config:
        raise ValueError(f"Model alias '{model_alias}' not found in configuration.")

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

def start_logging() -> None:
    """
    Start logging to a file with a timestamp.
    """
    global LOGGING_ACTIVE, LOG_FILE

    if not LOGGING_ACTIVE:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_filename = f"chatybot.log.{timestamp}"
        LOG_FILE = open(log_filename, "w")
        LOGGING_ACTIVE = True
        print(f"Logging started. Writing to '{log_filename}'.")

def stop_logging() -> None:
    """
    Stop logging and close the log file.
    """
    global LOGGING_ACTIVE, LOG_FILE

    if LOGGING_ACTIVE and LOG_FILE:
        LOG_FILE.close()
        LOGGING_ACTIVE = False
        print("Logging stopped.")

def format_datetime(dt: datetime) -> str:
    """
    Format datetime in local time with timezone.
    """
    return dt.strftime("%b %d, %Y, %I:%M:%S %p %Z")

def log_message(message: str) -> None:
    """
    Log a message to the log file if logging is active.
    """
    global LOG_FILE, LOGGING_ACTIVE

    if LOGGING_ACTIVE and LOG_FILE:
        timestamp = format_datetime(datetime.now())
        LOG_FILE.write(f"{timestamp} - {message}\n")
        LOG_FILE.flush()

def list_models() -> None:
    """
    List all available models with their details in a formatted table.
    """
    print("\nAvailable Models:")

    # Calculate column widths
    alias_width = max(len("Alias"), max(len(alias) for alias in CONFIG["models"]))
    name_width = max(len("Model Name"), max(len(config["name"]) for config in CONFIG["models"].values()))
    url_width = max(len("Base URL"), max(len(config.get("base_url", "Default OpenAI URL")) for config in CONFIG["models"].values()))

    # Print header
    header = f"{'Alias':<{alias_width}} {'Model Name':<{name_width}} {'Base URL':<{url_width}} {'Temp':<6} {'MaxT':<6} {'TopP':<6} {'TopK':<6} {'FreqP':<6} {'PresP':<6}"
    print(header)
    print("-" * len(header))

    # Print models
    for alias, config in CONFIG["models"].items():
        base_url = config.get("base_url", "Default OpenAI URL")
        temp = config.get("temperature", 0.7)
        max_tokens = config.get("max_tokens", "Default")
        top_p = config.get("top_p", "Def")
        top_k = config.get("top_k", "Def")
        freq_p = config.get("frequency_penalty", "Def")
        pres_p = config.get("presence_penalty", "Def")
        print(f"{alias:<{alias_width}} {config['name']:<{name_width}} {base_url:<{url_width}} {temp:<6.2f} {str(max_tokens):<6} {str(top_p):<6} {str(top_k):<6} {str(freq_p):<6} {str(pres_p):<6}")

    print()

def get_history_path() -> str:
    path = os.path.expanduser("~/.local/share/chatybot")
    os.makedirs(path, exist_ok=True)
    return os.path.join(path, ".chat_history")

def save_input_history() -> None:
    """
    Save input history to a file before exiting.
    """
    if INPUT_HISTORY:
        with open(get_history_path(), "w") as f:
            f.write("\n".join(INPUT_HISTORY))

def load_input_history() -> None:
    """
    Load input history from file.
    """
    global INPUT_HISTORY
    try:
        with open(get_history_path(), "r") as f:
            INPUT_HISTORY = [line.strip() for line in f.readlines() if line.strip()]
        # Set up readline history
        for line in INPUT_HISTORY:
            readline.add_history(line)
    except FileNotFoundError:
        pass

def input_history_completer(text: str, state: int) -> Optional[str]:
    """
    Completer function for readline to navigate input history.
    """
    global INPUT_HISTORY, INPUT_HISTORY_INDEX, INPUT_HISTORY_MATCHES

    if state == 0:
        # Filter history based on text
        INPUT_HISTORY_MATCHES = [h for h in INPUT_HISTORY if h.startswith(text)]
        INPUT_HISTORY_INDEX = 0
    else:
        INPUT_HISTORY_INDEX += 1

    if INPUT_HISTORY_INDEX < len(INPUT_HISTORY_MATCHES):
        return INPUT_HISTORY_MATCHES[INPUT_HISTORY_INDEX]
    return None

def replace_placeholders(prompt: str) -> str:
    """
    Replace filebank and script variable placeholders in the prompt.
    """
    # Replace filebank placeholders: {filebank1}
    for bank_name, content in FILE_BANKS.items():
        placeholder = f"{{{bank_name}}}"
        if placeholder in prompt:
            prompt = prompt.replace(placeholder, content)
    
    # Replace script variable placeholders: ${varname}
    for var_name, var_value in SCRIPT_VARS.items():
        placeholder = f"${{{var_name}}}"
        if placeholder in prompt:
            prompt = prompt.replace(placeholder, str(var_value))
            
    return prompt

def show_memory_usage() -> None:
    """
    Show size of the file buffer, filebanks, and script variables in KB.
    """
    print(f"\n{'Source':<20} {'Size (KB)':>10}")
    print("-" * 32)
    
    # File Buffer
    file_buffer_size = len(FILE_BUFFER.encode('utf-8')) / 1024
    print(f"{'FILE_BUFFER':<20} {file_buffer_size:>10.2f}")
    
    # File Banks
    for i in range(1, 6):
        bank_name = f"filebank{i}"
        bank_size = len(FILE_BANKS[bank_name].encode('utf-8')) / 1024
        print(f"{bank_name:<20} {bank_size:>10.2f}")
    
    # Script Variables
    for var_name, var_value in SCRIPT_VARS.items():
        var_size = len(str(var_value).encode('utf-8')) / 1024
        print(f"{var_name:<20} {var_size:>10.2f}")
    print()

def dump_variables(name: str = "all") -> None:
    """
    Print the contents of a variable or 'all' variables.
    """
    if name == "all":
        print("\n--- DUMP ALL VARIABLES ---")
        print(f"FILE_BUFFER: {FILE_BUFFER}")
        for i in range(1, 6):
            bank_name = f"filebank{i}"
            print(f"{bank_name.upper()}: {FILE_BANKS[bank_name]}")
        for var_name, var_value in SCRIPT_VARS.items():
            print(f"SCRIPT_VAR '{var_name}': {var_value}")
        print("--- END DUMP ---\n")
    elif name == "file_buffer":
        print(f"FILE_BUFFER: {FILE_BUFFER}")
    elif name.startswith("filebank") and name[8:].isdigit():
        if name in FILE_BANKS:
            print(f"{name.upper()}: {FILE_BANKS[name]}")
        else:
            print(f"Error: {name} not found.")
    elif name in SCRIPT_VARS:
        print(f"SCRIPT_VAR '{name}': {SCRIPT_VARS[name]}")
    else:
        print(f"Error: Variable '{name}' not found.")

async def chat_completion(prompt: str, stream: bool = False) -> str:
    """
    Send a prompt to the OpenAI API and return the response.
    """
    global ACTIVE_MODEL_ALIAS, CHAT_HISTORY, FILE_BUFFER, PROMPT_BUFFER, CODE_ONLY_FLAG, MAX_TOKENS
    global TOP_P, TOP_K, FREQ_PENALTY, PRES_PENALTY, SEED_CONFIG

    client = get_openai_client(ACTIVE_MODEL_ALIAS)
    model_config = CONFIG["models"][ACTIVE_MODEL_ALIAS]
    model_name = model_config["name"]

    # Replace placeholders in the prompt
    full_prompt = replace_placeholders(prompt)

    # Prepare the prompt with file buffer and prompt buffer if available
    if PROMPT_BUFFER:
        full_prompt = PROMPT_BUFFER + "\n\n" + full_prompt
    if FILE_BUFFER:
        full_prompt = f"File:\n{FILE_BUFFER}\n\n{full_prompt}"

    # Add code-only instruction if flag is set
    if CODE_ONLY_FLAG:
        full_prompt = "Do not explain or describe the code - generate the code requested only. " + full_prompt

    # Prepare messages for chat completion
    messages = [{"role": "user", "content": full_prompt}]

    is_reasoning_model = "nvidia" in model_config.get("base_url", "").lower() or "nvidia" in model_name.lower() or "qwen" in model_name.lower()
    
    current_system_message = SYSTEM_MESSAGE
    if is_reasoning_model and not REASONING_MODE:
        if current_system_message:
            current_system_message += "\ndetailed thinking off"
        else:
            current_system_message = "detailed thinking off"

    # Use system prompt unless the model name contains "gemma"
    if "gemma" not in model_name.lower():
        messages.insert(0, {"role": "system", "content": current_system_message})

    # Prepare completion parameters
    kwargs = {
        "model": model_name,
        "messages": messages,
        "temperature": model_config.get("temperature", 0.7),
    }

    # Add optional parameters if defined globally or in model config
    mt = MAX_TOKENS if MAX_TOKENS is not None else model_config.get("max_tokens")
    if mt is not None: kwargs["max_tokens"] = mt

    is_mistral = "mistral.ai" in model_config.get("base_url", "").lower()
    is_openai_official = "api.openai.com" in model_config.get("base_url", "").lower()
    is_google = "googleapis.com" in model_config.get("base_url", "").lower()
    is_bytez = "bytez.com" in model_config.get("base_url", "").lower()

    tp = TOP_P if TOP_P is not None else model_config.get("top_p")
    if tp is not None:
        if is_nvidia:
            kwargs.setdefault("extra_body", {}).setdefault("nvext", {})["top_p"] = tp
        else:
            kwargs["top_p"] = tp
    
    fp = FREQ_PENALTY if FREQ_PENALTY is not None else model_config.get("frequency_penalty")
    if fp is not None: kwargs["frequency_penalty"] = fp
    
    pp = PRES_PENALTY if PRES_PENALTY is not None else model_config.get("presence_penalty")
    if pp is not None: kwargs["presence_penalty"] = pp

    tk = TOP_K if TOP_K is not None else model_config.get("top_k")
    if tk is not None:
        if is_nvidia:
            kwargs.setdefault("extra_body", {}).setdefault("nvext", {})["top_k"] = tk
        elif not is_mistral and not is_openai_official and not is_google and not is_bytez:
            # Mistral, OpenAI official, Google Gemini, and Bytez APIs reject top_k as an extra input.
            # Only add for other providers (OpenRouter, etc.)
            kwargs.setdefault("extra_body", {})["top_k"] = tk

    # Seed handling
    current_seed = None
    if SEED_CONFIG is not None:
        if SEED_CONFIG == "time":
            current_seed = int(time.time())
        elif isinstance(SEED_CONFIG, tuple) and SEED_CONFIG[0] == "random":
            current_seed = random.randint(SEED_CONFIG[1], SEED_CONFIG[2])
        else:
            try:
                current_seed = int(SEED_CONFIG)
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
        if stream:
            kwargs["stream"] = True
            response = await client.chat.completions.create(**kwargs)

            full_response = ""
            print("Assistant: ", end="", flush=True)
            
            buffer = ""
            in_think_block = False
            
            async for chunk in response:
                if not chunk.choices: continue
                delta = chunk.choices[0].delta
                
                reasoning = getattr(delta, "reasoning_content", None)
                if reasoning:
                    full_response += reasoning
                    if SHOW_THINKING:
                        print(f"\033[90m{reasoning}\033[0m", end="", flush=True)

                if delta.content:
                    content = delta.content
                    full_response += content
                    
                    if not SHOW_THINKING:
                        buffer += content
                        while buffer:
                            if not in_think_block:
                                think_idx = buffer.find("<think>")
                                if think_idx != -1:
                                    print(buffer[:think_idx], end="", flush=True)
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
                                    buffer = buffer[end_idx + len("</think>"):]
                                    in_think_block = False
                                else:
                                    if len(buffer) >= len("</think>"):
                                        buffer = buffer[-(len("</think>") - 1):]
                                    break
                    else:
                        print(content, end="", flush=True)
                        
            if buffer and not SHOW_THINKING and not in_think_block:
                print(buffer, end="", flush=True)
            print()  # New line after streaming
        else:
            response = await client.chat.completions.create(**kwargs)
            message = response.choices[0].message
            content = message.content or ""
            reasoning = getattr(message, "reasoning_content", None) or ""
            
            full_response = ""
            if reasoning:
                if SHOW_THINKING:
                    print(f"\033[90m{reasoning}\033[0m")
                full_response += f"{reasoning}\n\n"
            
            full_response += content

            if not SHOW_THINKING:
                import re
                print_content = re.sub(r'<think>.*?</think>\s*', '', content, flags=re.DOTALL)
            else:
                print_content = content
                
            if not print_content.strip() and not (reasoning and SHOW_THINKING):
                print("Warning: Received an empty response from the model.")
            elif print_content.strip():
                print(print_content)

        # Calculate and display metrics
        elapsed_time = time.time() - start_time
        print(f"\nExecution time: {elapsed_time:.2f} seconds")

        if hasattr(response, 'usage'):
            print(f"Input tokens: {response.usage.prompt_tokens}, Output tokens: {response.usage.completion_tokens}")

        # Log user entry with datetime and model info
        if LOGGING_ACTIVE:
            current_time = format_datetime(datetime.now())
            log_message(f"Datetime: {current_time}")
            log_message(f"Model: {ACTIVE_MODEL_ALIAS} ({model_name})")
            log_message(f"User: {prompt}")

        CHAT_HISTORY.append((prompt, full_response))

        # Log assistant entry with completion datetime and token count
        if LOGGING_ACTIVE:
            input_tokens = response.usage.prompt_tokens if hasattr(response, 'usage') else "N/A"
            output_tokens = response.usage.completion_tokens if hasattr(response, 'usage') else "N/A"
            log_message(f"\nExecution time: {elapsed_time:.2f} seconds")
            log_message(f"Number of tokens: Input {input_tokens}, Output {output_tokens}")
            log_message(f"Assistant: {full_response}\n")

        return full_response
    except Exception as e:
        error_msg = f"Error during chat completion: {str(e)}"
        print(error_msg)
        if LOGGING_ACTIVE:
            log_message(error_msg)
        return f"Error: {str(e)}"

async def execute_script_command(command: str, original_handler: Callable[[str], Union[bool, str]]) -> bool:
    """
    Execute a command within a script context.
    Returns True if the command was handled, False otherwise.
    """
    global SCRIPT_VARS, SCRIPT_CONTEXT, PROMPT_BUFFER

    # Handle script-specific commands
    if command.startswith("set "):
        try:
            _, var_part = command.split(maxsplit=1)
            var_name, var_value = var_part.split("=", maxsplit=1)
            SCRIPT_VARS[var_name.strip()] = var_value.strip().strip('"\'')
            return True
        except ValueError:
            print("Invalid set command. Usage: set <name> = <value>")
            return True

    # Replace variables in the command
    def replace_var(match):
        var_name = match.group(1)
        return SCRIPT_VARS.get(var_name, "")

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
                if condition in SCRIPT_VARS:
                    # More robust truthy check for string variables
                    if SCRIPT_VARS[condition].lower() in ["true", "1", "yes"]:
                        return await execute_script_command(then_command, original_handler)
                    elif SCRIPT_VARS[condition].lower() in ["false", "0", "no", ""]:
                        return True # Condition is false, do nothing
                elif condition.lower() == "true":
                    return await execute_script_command(then_command, original_handler)
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
            temp_prompt = "Using the following prompt, please provide a response:\n" + PROMPT_BUFFER
            response = await chat_completion(temp_prompt, stream=STREAMING_ENABLED)
            log_message(f"User: {temp_prompt}\nAssistant: {response}\n")
            PROMPT_BUFFER = ""  # Clear the buffer after execution
            return True # Handled
        return result if isinstance(result, bool) else False # Return boolean indicating if handled

    # If not a command, treat as chat input
    if SCRIPT_CONTEXT:
        response = await chat_completion(processed_command, stream=STREAMING_ENABLED)
        log_message(f"User: {processed_command}\nAssistant: {response}\n")
        return True

    return False

async def execute_script(script_path: str) -> None:
    """
    Execute a script file containing multiple commands.
    """
    global SCRIPT_VARS, SCRIPT_CONTEXT, MULTI_LINE_MODE

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
        SCRIPT_CONTEXT = True
        multi_line_buffer = []
        in_multi_line = False

        for cmd in commands_list:
            # Check if we're in multi-line mode and not processing an escaped command
            if MULTI_LINE_MODE and not cmd.startswith("/") and not in_multi_line:
                in_multi_line = True
                multi_line_buffer = [cmd]
                continue

            if in_multi_line:
                if cmd.strip() == ";;":
                    # End of multi-line input, process it
                    full_prompt = "\n".join(multi_line_buffer)
                    print(f"Executing multi-line prompt: {full_prompt[:50]}...")
                    handled = await execute_script_command(full_prompt, handle_escape_command)
                    if not handled:
                        print(f"Error processing multi-line command")
                    in_multi_line = False
                    multi_line_buffer = []
                elif cmd.startswith("/"):
                    # Escaped command in the middle of multi-line - process the buffer first
                    full_prompt = "\n".join(multi_line_buffer)
                    print(f"Executing multi-line prompt: {full_prompt[:50]}...")
                    handled = await execute_script_command(full_prompt, handle_escape_command)
                    if not handled:
                        print(f"Error processing multi-line command")

                    # Then process the escaped command
                    print(f"Executing: {cmd}")
                    handled = await execute_script_command(cmd, handle_escape_command)
                    if not handled:
                        print(f"Unknown command in script: {cmd}")
                    in_multi_line = False
                    multi_line_buffer = []
                else:
                    # Continue building multi-line input
                    multi_line_buffer.append(cmd)
            else:
                print(f"Executing: {cmd}")
                handled = await execute_script_command(cmd, handle_escape_command)
                if not handled:
                    print(f"Unknown command in script: {cmd}")

        print("Script execution finished")

        # If we ended while in multi-line mode, process what we have
        if in_multi_line and multi_line_buffer:
            full_prompt = "\n".join(multi_line_buffer)
            print(f"Executing multi-line prompt: {full_prompt[:50]}...")
            handled = await execute_script_command(full_prompt, handle_escape_command)
            if not handled:
                print(f"Error processing multi-line command")

    except Exception as e:
        print(f"Error executing script: {str(e)}")
    finally:
        SCRIPT_CONTEXT = False

async def execute_script_old(script_path: str) -> None:
    """
    Execute a script file containing multiple commands.
    """
    global SCRIPT_CONTEXT

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
            # Attempt to split by semicolon, but be aware of quotes.
            # A simple split by ';' will break quoted strings containing ';'.
            # For robust parsing, a state machine or a more complex regex is needed.
            # For "little change", we'll use a simple split and note the limitation.
            if ';' in line:
                # This will break quoted strings like "set msg = "hello; world""
                # Users should avoid using ';' inside quoted strings if it's meant as a command separator.
                commands_list.extend([cmd.strip() for cmd in line.split(';') if cmd.strip()])
            else:
                commands_list.append(line)

        # Execute each command
        SCRIPT_CONTEXT = True
        for cmd in commands_list:
            print(f"Executing: {cmd}")
            handled = await execute_script_command(cmd, handle_escape_command)
            if not handled:
                print(f"Unknown command in script: {cmd}")

    except Exception as e:
        print(f"Error executing script: {str(e)}")
    finally:
        SCRIPT_CONTEXT = False

async def handle_escape_command(command: str) -> Union[bool, str]:
    """
    Handle escape commands. Returns True if the command was handled, False otherwise.
    """
    global ACTIVE_MODEL_ALIAS, FILE_BUFFER, PROMPT_BUFFER, CODE_ONLY_FLAG, LOGGING_ACTIVE, MULTI_LINE_MODE
    global SYSTEM_MESSAGE, MAX_TOKENS, STREAMING_ENABLED, FILE_BANKS, NOTE_MODE
    global TOP_P, TOP_K, FREQ_PENALTY, PRES_PENALTY

    parts = command.split(maxsplit=2)
    if LOGGING_ACTIVE:
        log_message(f"Escape command: {command}")
    cmd = parts[0].lower()

    if cmd == "/help":
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
        return True

    elif cmd == "/prompt":
        if len(parts) < 2:
            print("Usage: /prompt <file>")
            return True

        file_path = parts[1]
        try:
            with open(file_path, "r") as f:
                PROMPT_BUFFER = f.read()
            print(f"\nPrompt loaded from '{file_path}':")
            print("-" * 40)
            print(PROMPT_BUFFER)
            print("-" * 40)

            # Ask for confirmation only if not in script context
            if not SCRIPT_CONTEXT:
                while True:
                    confirm = input("\nExecute this prompt? (Y/N): ").strip().lower()
                    if confirm in ['y', 'yes']:
                        print("\nExecuting prompt...")
                        # Set a flag to execute the prompt in the main loop
                        return "EXECUTE_PROMPT"
                    elif confirm in ['n', 'no']:
                        PROMPT_BUFFER = ""
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

        bank_name = f"filebank{bank_num}"

        if len(parts) < 2:
            print(f"Usage: {cmd} <file> or {cmd} clear or {cmd} show [all]")
            return True

        subcommand = parts[1].lower()

        if subcommand == "clear":
            FILE_BANKS[bank_name] = ""
            print(f"{bank_name} cleared.")
            return True
        elif subcommand == "show":
            content = FILE_BANKS[bank_name]
            if not content:
                print(f"{bank_name} is empty.")
                return True

            if len(parts) > 2 and parts[2].lower() == "all":
                print(content)
            else:
                print(content[:100] + ("..." if len(content) > 100 else ""))
            return True
        else:
            # Assume it's a file path
            file_path = parts[1]
            try:
                with open(file_path, "r") as f:
                    FILE_BANKS[bank_name] = f.read()
                print(f"File '{file_path}' loaded into {bank_name}.")
            except Exception as e:
                print(f"Error reading file: {str(e)}")
            return True

    elif cmd == "/file":
        if len(parts) < 2:
            print("Usage: /file <path>")
            return True

        file_path = parts[1]
        try:
            with open(file_path, "r") as f:
                FILE_BUFFER = f.read()
            print(f"File '{file_path}' loaded into buffer.")
        except Exception as e:
            print(f"Error reading file: {str(e)}")
        return True

    elif cmd == "/clearfile":
        FILE_BUFFER = ""
        print("File buffer cleared.")
        return True

    elif cmd == "/showfile":
        if FILE_BUFFER:
            if len(parts) > 1 and parts[1].lower() == "all":
                print(FILE_BUFFER)
            else:
                print(FILE_BUFFER[:100] + ("..." if len(FILE_BUFFER) > 100 else ""))
        else:
            print("File buffer is empty.")
        return True

    elif cmd == "/model":
        if len(parts) < 2:
            # Show current model
            model_config = CONFIG["models"][ACTIVE_MODEL_ALIAS]
            print(f"Current model: {model_config['name']} (alias: {ACTIVE_MODEL_ALIAS})")
            return True

        model_alias = parts[1]
        if model_alias not in CONFIG["models"]:
            print(f"Model alias '{model_alias}' not found in configuration.")
            return True

        ACTIVE_MODEL_ALIAS = model_alias
        model_config = CONFIG["models"][model_alias]
        print(f"Switched to model: {model_config['name']} (alias: {model_alias})")
        return True

    elif cmd == "/logging":
        if len(parts) < 2:
            print("Usage: /logging <start|end>")
            return True

        action = parts[1].lower()
        if action == "start":
            start_logging()
        elif action == "end":
            stop_logging()
        else:
            print("Invalid logging action. Use 'start' or 'end'.")
        return True

    elif cmd == "/save":
        if len(parts) < 2:
            print("Usage: /save <file>")
            return True

        file_path = parts[1]
        if CHAT_HISTORY:
            last_response = CHAT_HISTORY[-1][1]
            try:
                directory = os.path.dirname(file_path)
                if directory and not os.path.exists(directory):
                    os.makedirs(directory, exist_ok=True)
                    print(f"Created directory path: '{directory}'")

                with open(file_path, "w") as f:
                    f.write(last_response)
                print(f"Last chat completion saved to '{file_path}'.")

                # If note mode is on, process the file to extract code blocks
                if NOTE_MODE:
                    print(f"Note mode is ON. Processing file '{file_path}'...")
                    process_file(file_path)
            except Exception as e:
                print(f"Error saving file: {str(e)}")
        else:
            print("No chat history to save.")
        return True
    # New database commands
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

    elif cmd == "/setvar":
        if len(parts) < 3:
            print("Usage: /setvar <varname> <value>")
            return True
        var_name = parts[1].strip('"')
        var_value = parts[2]
        SCRIPT_VARS[var_name] = var_value
        print(f"Variable '{var_name}' set.")
        return True

    elif cmd == "/mem":
        show_memory_usage()
        return True

    elif cmd == "/dump":
        var_name = parts[1] if len(parts) > 1 else "all"
        dump_variables(var_name)
        return True

    elif cmd == "/notemode":
        if len(parts) < 2:
            print(f"Note mode is currently {'ON' if NOTE_MODE else 'OFF'}")
            return True

        action = parts[1].lower()
        if action == "on":
            NOTE_MODE = True
            print("Note mode enabled. Code blocks will be extracted when using /save.")
        elif action == "off":
            NOTE_MODE = False
            print("Note mode disabled.")
        else:
            print("Invalid note mode action. Use 'on' or 'off'.")
        return True

    elif cmd == "/codeonly":
        CODE_ONLY_FLAG = True
        print("Code-only mode enabled.")
        return True

    elif cmd == "/codeoff":
        CODE_ONLY_FLAG = False
        print("Code-only mode disabled.")
        return True

    elif cmd == "/multiline":
        MULTI_LINE_MODE = not MULTI_LINE_MODE
        print(f"Multi-line mode {'enabled' if MULTI_LINE_MODE else 'disabled'}. "
              f"{'Use ;; to end input' if MULTI_LINE_MODE else ''}")
        return True

    elif cmd == "/system":
        if len(parts) < 2:
            print(f"Current system message: {SYSTEM_MESSAGE}")
            return True

        SYSTEM_MESSAGE = parts[1]
        print(f"System message updated: {SYSTEM_MESSAGE}")
        return True

    elif cmd == "/temp":
        if len(parts) < 2:
            current_temp = CONFIG["models"][ACTIVE_MODEL_ALIAS].get("temperature", 0.7)
            print(f"Current temperature: {current_temp}")
            return True

        try:
            temp = float(parts[1])
            if not 0.0 <= temp <= 2.0:
                raise ValueError
            CONFIG["models"][ACTIVE_MODEL_ALIAS]["temperature"] = temp
            print(f"Temperature set to {temp} for model {ACTIVE_MODEL_ALIAS}")
        except ValueError:
            print("Invalid temperature value. Please provide a number between 0.0 and 2.0.")
        return True

    elif cmd == "/maxtokens":
        if len(parts) < 2:
            current_max = MAX_TOKENS if MAX_TOKENS is not None else CONFIG["models"][ACTIVE_MODEL_ALIAS].get("max_tokens", "Default")
            print(f"Current max tokens: {current_max}")
            return True

        try:
            max_tokens = int(parts[1])
            if max_tokens <= 0:
                raise ValueError
            MAX_TOKENS = max_tokens
            print(f"Max tokens set to {max_tokens}")
        except ValueError:
            print("Invalid max tokens value. Please provide a positive integer.")
        return True

    elif cmd == "/top_p":
        if len(parts) < 2:
            current_tp = TOP_P if TOP_P is not None else CONFIG["models"][ACTIVE_MODEL_ALIAS].get("top_p", "Default")
            print(f"Current top_p: {current_tp}")
            return True
        try:
            val = float(parts[1])
            TOP_P = val
            print(f"top_p set to {val}")
        except ValueError:
            print("Invalid top_p value. Please enter a float.")
        return True

    elif cmd == "/top_k":
        if len(parts) < 2:
            current_tk = TOP_K if TOP_K is not None else CONFIG["models"][ACTIVE_MODEL_ALIAS].get("top_k", "Default")
            print(f"Current top_k: {current_tk}")
            return True
        try:
            val = int(parts[1])
            TOP_K = val
            print(f"top_k set to {val}")
        except ValueError:
            print("Invalid top_k value. Please enter an integer.")
        return True

    elif cmd == "/freq_penalty":
        if len(parts) < 2:
            current_fp = FREQ_PENALTY if FREQ_PENALTY is not None else CONFIG["models"][ACTIVE_MODEL_ALIAS].get("frequency_penalty", "Default")
            print(f"Current frequency penalty: {current_fp}")
            return True
        try:
            val = float(parts[1])
            FREQ_PENALTY = val
            print(f"Frequency penalty set to {val}")
        except ValueError:
            print("Invalid frequency penalty value. Please enter a float.")
        return True

    elif cmd == "/pres_penalty":
        if len(parts) < 2:
            current_pp = PRES_PENALTY if PRES_PENALTY is not None else CONFIG["models"][ACTIVE_MODEL_ALIAS].get("presence_penalty", "Default")
            print(f"Current presence penalty: {current_pp}")
            return True
        try:
            val = float(parts[1])
            PRES_PENALTY = val
            print(f"Presence penalty set to {val}")
        except ValueError:
            print("Invalid presence penalty value. Please enter a float.")
        return True

    elif cmd == "/reasoning":
        if len(parts) > 1 and parts[1].lower() in ["on", "off"]:
            global REASONING_MODE
            if parts[1].lower() == "on":
                REASONING_MODE = True
            else:
                REASONING_MODE = False
            print(f"Reasoning mode is now {'ON' if REASONING_MODE else 'OFF'}")
        else:
            print(f"Reasoning mode is currently {'ON' if getattr(sys.modules[__name__], 'REASONING_MODE', True) else 'OFF'}")
        return True

    elif cmd == "/thinking":
        if len(parts) > 1 and parts[1].lower() in ["on", "off"]:
            global SHOW_THINKING
            if parts[1].lower() == "on":
                SHOW_THINKING = True
            else:
                SHOW_THINKING = False
            print(f"Thinking display is now {'ON' if SHOW_THINKING else 'OFF'}")
        else:
            print(f"Thinking display is currently {'ON' if getattr(sys.modules[__name__], 'SHOW_THINKING', True) else 'OFF'}")
        return True

    elif cmd == "/seed":
        global SEED_CONFIG
        if len(parts) < 2:
            print(f"Current seed setting: {SEED_CONFIG}")
            return True
        
        arg = parts[1].lower()
        if arg in ["clear", "none", "off"]:
            SEED_CONFIG = None
            print("Seed cleared.")
        elif arg == "time":
            SEED_CONFIG = "time"
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
                SEED_CONFIG = ("random", v1, v2)
                print(f"Seed set to random range: {v1} to {v2}")
            except ValueError:
                print("Invalid range. Use: /seed random <min>, <max>")
        else:
            try:
                seed_val = int(parts[1])
                SEED_CONFIG = seed_val
                print(f"Seed set to fixed value: {seed_val}")
            except ValueError:
                print("Invalid seed. Use an integer, 'time', or 'random <min>, <max>'.")
        return True

    elif cmd == "/stream":
        STREAMING_ENABLED = not STREAMING_ENABLED
        print(f"Streaming responses {'enabled' if STREAMING_ENABLED else 'disabled'}")
        return True

    elif cmd == "/listmodels":
        list_models()
        return True

    elif cmd == "/script":
        if len(parts) < 2:
            print("Usage: /script <file>")
            return True

        script_path = parts[1]
        print("command /script with ", script_path)
        # Execute script asynchronously so it doesn't block the main loop
        await execute_script(script_path)
        return True

    elif cmd == "/quit":
        print("Goodbye! Thanks for chatting.")
        stop_logging()
        save_input_history()
        exit(0)

    return False

async def get_multi_line_input() -> str:
    """
    Get multi-line input from the user.
    """
    print("Multi-line mode. Enter your prompt (use ';;' on a new line to finish):")
    lines = []
    while True:
        line = input()
        if line.strip() == ";;":
            break
        lines.append(line)
    return "\n".join(lines)

async def main() -> None:
    """
    Main function to run the chat loop.
    """
    global ACTIVE_MODEL_ALIAS, INPUT_HISTORY, STREAMING_ENABLED, PROMPT_BUFFER

    # Load configuration
    load_config()
    print("===========================")
    print("Chatybot.py                ")
    print("Created by Jon Allen - 2025")
    print("===========================")
    print(f"Active model: {CONFIG['models'][ACTIVE_MODEL_ALIAS]['name']} (alias: {ACTIVE_MODEL_ALIAS})")

    # Set up input history
    load_input_history()

    # Set up readline for command history
    readline.set_completer(input_history_completer)
    readline.parse_and_bind("tab: complete")
    readline.set_completer_delims(" \t\n;")

    # Register save function to be called on exit
    atexit.register(save_input_history)

    while True:
        try:
            if MULTI_LINE_MODE:
                prompt = await get_multi_line_input()
            else:
                prompt = input("chat --> ")

            # Add to input history
            if prompt.strip() and (not INPUT_HISTORY or prompt != INPUT_HISTORY[-1]):
                INPUT_HISTORY.append(prompt)
                readline.add_history(prompt)

            if not prompt.strip():
                continue

            if prompt.startswith("/"):
                result = await handle_escape_command(prompt)
                if result == "EXECUTE_PROMPT":
                    # Execute the buffered prompt
                    temp_prompt = "Using the following prompt, please provide a response:\n" + PROMPT_BUFFER
                    response = await chat_completion(temp_prompt, stream=STREAMING_ENABLED)
                    PROMPT_BUFFER = ""  # Clear the buffer after execution
                continue

            response = await chat_completion(prompt, stream=STREAMING_ENABLED)

        except KeyboardInterrupt:
            print("\nGoodbye! Thanks for chatting.")
            stop_logging()
            save_input_history()
            break
        except Exception as e:
            print(f"Error: {str(e)}")

def run():
    asyncio.run(main())

if __name__ == "__main__":
    run()
