import os
import asyncio
import readline
import tomllib
from datetime import datetime
from typing import Dict, Any, List, Tuple, Optional
import logging
import atexit

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
CODE_ONLY_FLAG = False
LOGGING_ACTIVE = False
LOG_FILE = None
MULTI_LINE_MODE = False
INPUT_HISTORY: List[str] = []
INPUT_HISTORY_INDEX = -1
SYSTEM_MESSAGE = "You are a helpful assistant."
MAX_TOKENS = None
STREAMING_ENABLED = False

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
    List all available models with their details.
    """
    print("\nAvailable Models:")
    print("{:<15} {:<30} {:<40} {:<10} {:<10}".format(
        "Alias", "Model Name", "Base URL", "Temp", "Max Tokens"))
    print("-" * 85)

    for alias, config in CONFIG["models"].items():
        base_url = config.get("base_url", "Default OpenAI URL")
        temp = config.get("temperature", 0.7)
        max_tokens = config.get("max_tokens", "Default")
        print("{:<15} {:<30} {:<40} {:<10.2f} {:<10}".format(
            alias, config["name"], base_url, temp, str(max_tokens)))

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
    global INPUT_HISTORY, INPUT_HISTORY_INDEX

    if state == 0:
        # Filter history based on text
        matches = [h for h in INPUT_HISTORY if h.startswith(text)]
        INPUT_HISTORY_INDEX = 0
        INPUT_HISTORY_MATCHES = matches
    else:
        INPUT_HISTORY_INDEX += 1

    if INPUT_HISTORY_INDEX < len(INPUT_HISTORY_MATCHES):
        return INPUT_HISTORY_MATCHES[INPUT_HISTORY_INDEX]
    return None

async def chat_completion(prompt: str, stream: bool = False) -> str:
    """
    Send a prompt to the OpenAI API and return the response.
    """
    global ACTIVE_MODEL_ALIAS, CHAT_HISTORY, FILE_BUFFER, CODE_ONLY_FLAG, MAX_TOKENS

    client = get_openai_client(ACTIVE_MODEL_ALIAS)
    model_config = CONFIG["models"][ACTIVE_MODEL_ALIAS]
    model_name = model_config["name"]

    # Prepare the prompt with file buffer if available
    full_prompt = prompt
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

        CHAT_HISTORY.append((prompt, full_response))
        return full_response
    except Exception as e:
        return f"Error: {str(e)}"

def handle_escape_command(command: str) -> bool:
    """
    Handle escape commands. Returns True if the command was handled, False otherwise.
    """
    global ACTIVE_MODEL_ALIAS, FILE_BUFFER, CODE_ONLY_FLAG, LOGGING_ACTIVE, MULTI_LINE_MODE
    global SYSTEM_MESSAGE, MAX_TOKENS, STREAMING_ENABLED

    parts = command.split(maxsplit=1)
    cmd = parts[0].lower()

    if cmd == "/help":
        print("Active escape commands:")
        print("  /help - Show this help message.")
        print("  /file <path> - Read a text file into the buffer.")
        print("  /showfile [all] - Show the first 100 characters of the file buffer or the entire file if 'all' is specified.")
        print("  /clearfile - Clear the file buffer.")
        print("  /model <alias> - Switch to a different model.")
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
        print("  /quit - Exit the program.")
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
            print("Usage: /model <alias>")
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
    global ACTIVE_MODEL_ALIAS, INPUT_HISTORY, STREAMING_ENABLED

    # Load configuration
    load_config()
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
                if not handle_escape_command(prompt):
                    print("Unknown command. Type '/help' for available commands.")
                continue

            response = await chat_completion(prompt, stream=STREAMING_ENABLED)
            if not STREAMING_ENABLED:
                print(response)
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
