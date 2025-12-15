#!/usr/bin/env python3

import os
import asyncio
import readline
import tomllib
from datetime import datetime
from typing import Dict, Any
import logging

try:
    import openai
    from openai import AsyncOpenAI
except ImportError:
    raise ImportError("OpenAI SDK is not installed. Please install it with 'pip install openai'.")


# Global variables
CONFIG: Dict[str, Any] = {}
DEFAULT_MODEL_ALIAS = None
ACTIVE_MODEL_ALIAS = None
CHAT_HISTORY = []
FILE_BUFFER = ""
CODE_ONLY_FLAG = False
LOGGING_ACTIVE = False
LOG_FILE = None


def load_config() -> None:
    """
    Load the configuration from chat_config.toml.
    """
    global CONFIG, DEFAULT_MODEL_ALIAS, ACTIVE_MODEL_ALIAS
    
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
    print("{:<15} {:<30} {:<40}".format("Alias", "Model Name", "Base URL"))
    print("-" * 85)

    for alias, config in CONFIG["models"].items():
        base_url = config.get("base_url", "Default OpenAI URL")
        print("{:<15} {:<30} {:<40}".format(alias, config["name"], base_url))

    print()



async def chat_completion(prompt: str) -> str:
    """
    Send a prompt to the OpenAI API and return the response.
    """
    global ACTIVE_MODEL_ALIAS, CHAT_HISTORY, FILE_BUFFER, CODE_ONLY_FLAG
    
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
        messages.insert(0, {"role": "system", "content": "You are a helpful assistant."})
    
    try:
        response = await client.chat.completions.create(
            model=model_name,
            messages=messages,
            temperature=model_config.get("temperature", 0.7),
        )
        
        chat_response = response.choices[0].message.content
        CHAT_HISTORY.append((prompt, chat_response))
        
        return chat_response
    except Exception as e:
        return f"Error: {str(e)}"


def handle_escape_command(command: str) -> bool:
    """
    Handle escape commands. Returns True if the command was handled, False otherwise.
    """
    global ACTIVE_MODEL_ALIAS, FILE_BUFFER, CODE_ONLY_FLAG, LOGGING_ACTIVE
    
    parts = command.split(maxsplit=1)
    cmd = parts[0].lower()
    
    if cmd == "/help":
        print("Active escape commands:")
        print("  /help - Show this help message.")
        print("  /file <path> - Read a text file into the buffer.")
        print("  /showfile [all] - Show the first 100 characters of the file buffer or the entire file if 'all' is specified.")
        print("  /model <alias> - Switch to a different model.")
        print("  /listmodels - list available models from toml. ")
        print("  /logging <start|end> - Start or stop logging.")
        print("  /save <file> - Save the last chat completion to a file.")
        print("  /codeonly - Set flag to generate code only without explanations.")
        print("  /codeoff - Reverse the code-only flag.")
        print("  /quit - Exit the program.")
        return True
    
    elif cmd == "/file":
        if len(parts) < 2:
            print("Usage: /file <path>")
            return True
        
        file_path = parts[1]
        try:
            with open(file_path, "r") as f:
                FILE_BUFFER = f.read(4096)  # Read up to 4KB
            print(f"File '{file_path}' loaded into buffer.")
        except Exception as e:
            print(f"Error reading file: {str(e)}")
        return True
    
    elif cmd == "/showfile":
        if FILE_BUFFER:
            if len(parts) > 1 and parts[1].lower() == "all":
                print(FILE_BUFFER)
            else:
                print(FILE_BUFFER[:100])
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
 
    elif cmd == "/listmodels":
        list_models()
        return True
   
    elif cmd == "/quit":
        print("Goodbye! Thanks for chatting.")
        stop_logging()
        exit(0)
    
    return False


async def main() -> None:
    """
    Main function to run the chat loop.
    """
    global ACTIVE_MODEL_ALIAS
    
    load_config()
    print(f"Active model: {CONFIG['models'][ACTIVE_MODEL_ALIAS]['name']} (alias: {ACTIVE_MODEL_ALIAS})")
    
    while True:
        try:
            prompt = input("chat --> ")
            
            if not prompt.strip():
                continue
            
            if prompt.startswith("/"):
                if not handle_escape_command(prompt):
                    print("Unknown command. Type '/help' for available commands.")
                continue
            
            response = await chat_completion(prompt)
            print(response)
            log_message(f"User: {prompt}\nAssistant: {response}\n")
            
        except KeyboardInterrupt:
            print("\nGoodbye! Thanks for chatting.")
            stop_logging()
            break
        except Exception as e:
            print(f"Error: {str(e)}")


if __name__ == "__main__":
    asyncio.run(main())
