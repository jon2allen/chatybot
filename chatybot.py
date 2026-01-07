import asyncio
import os
import readline
import time
import tomllib
from datetime import datetime
from typing import Dict, Any, List, Tuple, Optional, Callable, Union # Added Callable, Union
import logging
import atexit

# Add these imports at the top of the file
import re
import shlex

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

# Add these global variables
SCRIPT_VARS: Dict[str, str] = {}
SCRIPT_CONTEXT = False

def load_config() -> None:
    """
    Load the configuration from chat_config.toml.
    """
    global CONFIG, DEFAULT_MODEL_ALIAS, ACTIVE_MODEL_ALIAS, SYSTEM_MESSAGE, MAX_TOKENS

    try:
        with open("chat_config.toml", "rb") as f:
            CONFIG = tomllib.load(f)
    except FileNotFoundError:
        raise FileNotFoundError("Configuration file 'chat_config.toml' not found.")
    except tomllib.TOMLDecodeError:
        raise ValueError("Invalid TOML format in 'chat_config.toml'.")

    # Set the default model alias to the first model in the config
    DEFAULT_MODEL_ALIAS = next(iter(CONFIG["models"]))
    ACTIVE_MODEL_ALIAS = DEFAULT_MODEL_ALIAS

    # Load system message if specified in config
    if "system_message" in CONFIG:
        SYSTEM_MESSAGE = CONFIG["system_message"]

    # Load max tokens if specified in config
    if "max_tokens" in CONFIG:
        MAX_TOKENS = CONFIG["max_tokens"]

def get_openai_client(model_alias: str) -> AsyncOpenAI:
    """
    Creates an openai.AsyncOpenAI client instance based on the model's config,
    using the _API_KEY environment variable for authentication.
    """
    model_config = CONFIG["models"].get(model_alias)

    if not model_config:
        raise ValueError(f"Model alias '{model_alias}' not found in configuration.")

    api_key = os.environ.get(model_config["api_key"])

    if not api_key:
        raise ValueError(
            f"API key not found for model alias '{model_alias}'. "
            f"Please set the '{model_config['api_key']}' environment variable."
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

def log_message(message: str) -> None:
    """
    Log a message to the log file if logging is active.
    """
    global LOG_FILE, LOGGING_ACTIVE

    if LOGGING_ACTIVE and LOG_FILE:
        LOG_FILE.write(f"{message}\n")
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
    header = f"{'Alias':<{alias_width}} {'Model Name':<{name_width}} {'Base URL':<{url_width}} {'Temp':<6} {'Max Tokens':<10}"
    print(header)
    print("-" * len(header))

    # Print models
    for alias, config in CONFIG["models"].items():
        base_url = config.get("base_url", "Default OpenAI URL")
        temp = config.get("temperature", 0.7)
        max_tokens = config.get("max_tokens", "Default")
        print(f"{alias:<{alias_width}} {config['name']:<{name_width}} {base_url:<{url_width}} {temp:<6.2f} {str(max_tokens):<10}")

    print()

def save_input_history() -> None:
    """
    Save input history to a file before exiting.
    """
    if INPUT_HISTORY:
        with open(".chat_history", "w") as f:
            f.write("\n".join(INPUT_HISTORY))

def load_input_history() -> None:
    """
    Load input history from file.
    """
    global INPUT_HISTORY
    try:
        with open(".chat_history", "r") as f:
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

def replace_filebank_placeholders(prompt: str) -> str:
    """
    Replace filebank placeholders in the prompt with their content.
    """
    for bank_name, content in FILE_BANKS.items():
        placeholder = f"{{{bank_name}}}"
        if placeholder in prompt:
            prompt = prompt.replace(placeholder, content)
    return prompt

async def chat_completion(prompt: str, stream: bool = False) -> str:
    """
    Send a prompt to the OpenAI API and return the response.
    """
    global ACTIVE_MODEL_ALIAS, CHAT_HISTORY, FILE_BUFFER, PROMPT_BUFFER, CODE_ONLY_FLAG, MAX_TOKENS

    client = get_openai_client(ACTIVE_MODEL_ALIAS)
    model_config = CONFIG["models"][ACTIVE_MODEL_ALIAS]
    model_name = model_config["name"]

    # Replace filebank placeholders in the prompt
    full_prompt = replace_filebank_placeholders(prompt)

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

    # Use system prompt unless the model name contains "gemma"
    if "gemma" not in model_name.lower():
        messages.insert(0, {"role": "system", "content": SYSTEM_MESSAGE})

    try:
        start_time = time.time()
        if stream:
            response = await client.chat.completions.create(
                model=model_name,
                messages=messages,
                temperature=model_config.get("temperature", 0.7),
                max_tokens=MAX_TOKENS if MAX_TOKENS else model_config.get("max_tokens"),
                stream=True
            )

            full_response = ""
            print("Assistant: ", end="", flush=True)
            async for chunk in response:
                if chunk.choices[0].delta.content:
                    content = chunk.choices[0].delta.content
                    print(content, end="", flush=True)
                    full_response += content
            print()  # New line after streaming
        else:
            response = await client.chat.completions.create(
                model=model_name,
                messages=messages,
                temperature=model_config.get("temperature", 0.7),
                max_tokens=MAX_TOKENS if MAX_TOKENS else model_config.get("max_tokens"),
            )
            full_response = response.choices[0].message.content
            print(full_response)

        # Calculate and display metrics
        elapsed_time = time.time() - start_time
        print(f"\nExecution time: {elapsed_time:.2f} seconds")

        if hasattr(response, 'usage'):
            print(f"Input tokens: {response.usage.prompt_tokens}, Output tokens: {response.usage.completion_tokens}")

        CHAT_HISTORY.append((prompt, full_response))
        return full_response
    except Exception as e:
        return f"Error: {str(e)}"

# Add this function to handle script execution
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
        # debug, print("match: ", match )
        var_name = match.group(1)
        # debug, print("var_name" , var_name )
        var1 = SCRIPT_VARS.get(var_name, "")

        # debug, print("var1: ", var1 )

        return var1

    processed_command = re.sub(r'\$\{(\w+)\}', replace_var, command)

    #  print("processed command: ",  processed_command )

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

# Modify the handle_escape_command function to add the /script command
async def handle_escape_command(command: str) -> Union[bool, str]: # Changed to async and updated return type
    """
    Handle escape commands. Returns True if the command was handled, False otherwise.
    """
    global ACTIVE_MODEL_ALIAS, FILE_BUFFER, PROMPT_BUFFER, CODE_ONLY_FLAG, LOGGING_ACTIVE, MULTI_LINE_MODE
    global SYSTEM_MESSAGE, MAX_TOKENS, STREAMING_ENABLED, FILE_BANKS

    parts = command.split(maxsplit=2)
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
        print("  /codeonly - Set flag to generate code only without explanations.")
        print("  /codeoff - Reverse the code-only flag.")
        print("  /multiline - Toggle multi-line input mode (use ';;' to end input).")
        print("  /system <message> - Set a custom system message.")
        print("  /temp <value> - Set temperature for the current model (0.0-2.0).")
        print("  /maxtokens <value> - Set max tokens for the current model.")
        print("  /stream - Toggle streaming responses.")
        print("  /script <file> - Execute a script file containing multiple commands.") # Added
        print("  /quit - Exit the program.")
        print("\nScript-specific features:") # Added
        print("  set <name> = <value> - Define a variable") # Added
        print("  ${name} - Reference a variable") # Added
        print("  if <condition> then <command> - Conditional execution") # Added
        print("  wait <seconds> - Pause execution") # Added
        print("  # comment - Comments in script files") # Added
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
                with open(file_path, "w") as f:
                    f.write(last_response)
                print(f"Last chat completion saved to '{file_path}'.")
            except Exception as e:
                print(f"Error saving file: {str(e)}")
        else:
            print("No chat history to save.")
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
            current_max = CONFIG["models"][ACTIVE_MODEL_ALIAS].get("max_tokens", "Default")
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

    elif cmd == "/stream":
        STREAMING_ENABLED = not STREAMING_ENABLED
        print(f"Streaming responses {'enabled' if STREAMING_ENABLED else 'disabled'}")
        return True

    elif cmd == "/listmodels":
        list_models()
        return True

    elif cmd == "/script": # New case for /script command
        if len(parts) < 2:
            print("Usage: /script <file>")
            return True

        script_path = parts[1]
        print("command /script with ", script_path )
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
                result = await handle_escape_command(prompt) # Added await
                if result == "EXECUTE_PROMPT":
                    # Execute the buffered prompt
                    temp_prompt = "Using the following prompt, please provide a response:\n" + PROMPT_BUFFER
                    response = await chat_completion(temp_prompt, stream=STREAMING_ENABLED)
                    log_message(f"User: {temp_prompt}\nAssistant: {response}\n")
                    PROMPT_BUFFER = ""  # Clear the buffer after execution
                continue

            response = await chat_completion(prompt, stream=STREAMING_ENABLED)
            log_message(f"User: {prompt}\nAssistant: {response}\n")

        except KeyboardInterrupt:
            print("\nGoodbye! Thanks for chatting.")
            stop_logging()
            save_input_history()
            break
        except Exception as e:
            print(f"Error: {str(e)}")

if __name__ == "__main__":
   asyncio.run(main())
