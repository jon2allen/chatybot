## Overview
chatybot implements a command-line chatbot interface that interacts with various language models through the OpenAI API (or compatible APIs). It provides a flexible system for chatting with different AI models and includes file input capabilities.

## Core Functions

### 1. Configuration Management
- **`load_config()`**: Loads model configurations from a TOML file (`chat_config.toml`)
  - Returns a dictionary containing model settings
  - Sets up the default model from the first entry in the config

### 2. API Client Management
- **`get_openai_client(model_alias)`**:
  - Creates an asynchronous OpenAI client instance
  - Uses environment variables (`LLM_API_KEY`) for authentication
  - Configures the client with model-specific settings (base URL, etc.)

### 3. Chat Functionality
- **`chat_completion(client, model_alias, prompt)`**:
  - Sends a prompt to the specified language model
  - Uses model-specific parameters (temperature, top_k) from config
  - Returns the model's response

### 4. Main Application Loop
- **`main()`**:
  - Initializes the chatbot with the default model
  - Provides an interactive command-line interface
  - Handles user commands and chat interactions

## Architecture Components

### 1. Configuration System
- Uses TOML format for configuration
- Stores multiple model definitions with:
  - Model names
  - API base URLs
  - Temperature settings
  - Top-k sampling parameters

### 2. Command Processing
- Implements a primitive command parser with these commands:

  /help - Show this help message.
  /file <path> - Read a text file into the buffer.
  /showfile [all] - Show the first 100 characters of the file buffer or the entire file if 'all' is specified.
  /model <alias> - Switch to a different model.
  /listmodels - list available models from toml. 
  /logging <start|end> - Start or stop logging.
  /save <file> - Save the last chat completion to a file.
  /codeonly - Set flag to generate code only without explanations.
  /codeoff - Reverse the code-only flag.
  /quit - Exit the program.


### 3. File Buffer System
- Maintains a file buffer (up to 4KB) for context
- Automatically incorporates file content into prompts
- Clears buffer after each response

### 4. Asynchronous Design
- Uses Python's asyncio for non-blocking API calls
- Allows the chatbot to remain responsive during API calls

## Workflow
1. User starts the application - python3 chatybot.py
2. System loads configuration and initializes default model
3. User enters prompts or commands
4. For chat prompts:
   - System combines prompt with file buffer (if any)
   - Sends to LLM via API
   - Displays response
5. For commands:
   - System executes the appropriate action (load file, switch model, etc.)

## Technical Highlights
- Type hints for better code maintainability
- Environment variable support for API keys
- Configurable model parameters
- File content integration for context
- Command-line interface with readline support (for better input handling)
- Error handling for file operations and API calls
