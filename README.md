
# chatybot - Interactive AI Chatbot Interface


**chatybot ** is a powerful command-line interface for interacting with language models, featuring a custom domain-specific language (DSL) for advanced prompt engineering, scripting, and automation.

---

## **Table of Contents**
- [Overview](#overview)
- [Key Features](#key-features)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Command Reference](#command-reference)
- [Advanced Features](#advanced-features)
  - [File Handling](#file-handling)
  - [Prompt Engineering](#prompt-engineering)
  - [Scripting](#scripting)
  - [Variable Substitution](#variable-substitution)
  - [Conditional Logic](#conditional-logic)
- [Test Cases](#test-cases)
- [Architecture](#architecture)
- [Technical Details](#technical-details)
- [Configuration](#configuration)
- [Examples](#examples)
- [Roadmap](#roadmap)
- [Contributing](#contributing)
- [License](#license)

---

## **Overview**

chatybot is an interactive command-line tool that enables seamless communication with large language models (LLMs) like GPT-4, Claude, or local models. It provides a rich set of features for:

- **Interactive chat** with AI models
- **File-based context management** for prompts
- **Advanced scripting** with variables and conditionals
- **Prompt engineering** with templates and system messages
- **Session logging** and response streaming

---

## **Key Features**

### **Core Functionality**
✅ **Model Switching** - Easily switch between different LLMs
✅ **File Buffer System** - Load files as context for prompts
✅ **Multi-Line Input** - Compose complex prompts with ease
✅ **Streaming Responses** - Real-time output from the model
✅ **Session Logging** - Save and review chat sessions
✅ **Input History** - Navigate previous inputs with Tab key

### **Advanced Features**
🚀 **Scripting Engine** - Automate workflows with scripts
🚀 **Variable Substitution** - Dynamic prompts with `${variables}`
🚀 **Conditional Logic** - `if-then` statements in scripts
🚀 **File Banks** - Organize multiple context files
🚀 **Prompt Templates** - Reusable prompt structures
🚀 **Code-Only Mode** - Generate pure code without explanations

---

## **Installation**

### **Prerequisites**
- Python 3.8+
- `pip` package manager
- API keys for your preferred LLMs (OpenAI, Anthropic, etc.)

### **Installation Steps**
```bash
# Clone the repository
git clone https://github.com/jon2allen/chatybot.git
cd chatybot

# Install dependencies
pip install -r requirements.txt

nano chat_config.toml  # Add your API keys and model configurations
```

---

## **Quick Start**

```bash
# Start the chat interface
python3 chatybot.py


Created by Jon Allen - 2025
===========================
Active model: mistral-large-2512 (alias: mistral_1)
chat --> /help
Active escape commands:
  /help - Show this help message.
  /prompt <file> - Load a prompt from a file.
  /file <path> - Read a text file into the buffer.
  /showfile [all] - Show the first 100 characters of the file buffer or the entire file if 'all' is specified.
  /clearfile - Clear the file buffer.
  /filebank{1..5} <file> - Load a text file into filebank1 through filebank5.
  /filebank{1..5} clear - Clear the specified filebank.
  /filebank{1..5} show [all] - Show the first 100 characters of the filebank or all if 'all' is specified.
  /model [alias] - Switch to a different model or show current model.
  /listmodels - List available models from toml.
  /logging <start|end> - Start or stop logging.
  /save <file> - Save the last chat completion to a file.
  /codeonly - Set flag to generate code only without explanations.
  /codeoff - Reverse the code-only flag.
  /multiline - Toggle multi-line input mode (use ';;' to end input).
  /system <message> - Set a custom system message.
  /temp <value> - Set temperature for the current model (0.0-2.0).
  /maxtokens <value> - Set max tokens for the current model.
  /stream - Toggle streaming responses.
  /script <file> - Execute a script file containing multiple commands.
  /quit - Exit the program.

Script-specific features:
  set <name> = <value> - Define a variable
  ${name} - Reference a variable
  if <condition> then <command> - Conditional execution
  wait <seconds> - Pause execution
  # comment - Comments in script files


# Basic usage
/model gpt4          # Switch to GPT-4 model
/file context.txt    # Load a context file
chat --> Hello!      # Start a conversation
```

---

## **Command Reference**

| Command | Description | Example |
|---------|-------------|---------|
| `/help` | Show help message | `/help` |
| `/model <alias>` | Switch models | `/model gpt4` |
| `/listmodels` | List available models | `/listmodels` |
| `/file <path>` | Load file into buffer | `/file notes.txt` |
| `/filebank1 <path>` | Load file into file bank 1 | `/filebank1 data.txt` |
| `/showfile [all]` | Show file content | `/showfile all` |
| `/clearfile` | Clear file buffer | `/clearfile` |
| `/prompt <path>` | Load prompt template | `/prompt template.txt` |
| `/system <msg>` | Set system message | `/system "You are an expert coder."` |
| `/temp <value>` | Set temperature (0.0-2.0) | `/temp 0.7` |
| `/maxtokens <value>` | Set max tokens | `/maxtokens 1000` |
| `/stream` | Toggle streaming | `/stream` |
| `/codeonly` | Enable code-only mode | `/codeonly` |
| `/codeoff` | Disable code-only mode | `/codeoff` |
| `/multiline` | Toggle multi-line input | `/multiline` |
| `/logging <start\|end>` | Start/stop logging | `/logging start` |
| `/save <file>` | Save last response | `/save output.txt` |
| `/script <path>` | Execute a script | `/script setup.dsl` |
| `/quit` | Exit the program | `/quit` |

---

## **Advanced Features**

### **File Handling**
```bash
/file document.txt      # Load a file into the main buffer
/filebank1 notes.txt    # Load a file into file bank 1
/showfile all           # Show all loaded files
/clearfile              # Clear the main buffer
```

### **Prompt Engineering**
```bash
/prompt template.txt    # Load a prompt template
/system "Act as a tutor" # Set system message
```

### **Scripting**
Create a script file (`setup.chatdsl`):
```dsl
set project = "chatbot"
if ${project} then /file ${project}_requirements.txt
wait 1
chat --> Generate documentation for this project
```

Execute the script:
```bash
/script setup.chatdsl
```

### **Variable Substitution**
```bash
set name = "Alice"
chat --> Hello ${name}, how are you today?
```

### **Conditional Logic**
```dsl
set debug = true
if ${debug} then /temp 0.1
if not ${debug} then /temp 0.7
```

---

## **Test Cases**

### **Test Case 1: Basic Command Execution**
**Input**:
```
/model gpt4
/listmodels
/model
```
**Expected**: Switches to `gpt4`, lists models, shows current model.

### **Test Case 2: File Handling**
**Input**:
```
/file test.txt
/showfile
/clearfile
/showfile
```
**Expected**: Loads file, shows content, clears buffer, shows empty buffer.

### **Test Case 3: Script Execution**
**Script** (`test_script.txt`):
```dsl
set project = "chatbot"
if ${project} then /file ${project}_requirements.txt
wait 1
/showfile
```
**Input**: `/script test_script.txt`
**Expected**: Loads file, waits, shows content.

### **Test Case 4: Error Handling**
**Input**:
```
/invalidcommand
/file nonexistent.txt
```
**Expected**: Shows error messages for invalid command and missing file.


---

## **Architecture**

```
chatdsl/
├── chatybot.py          # Main application
├── chat_config.toml    # Configuration file
├── dsl_test/           # Script files
├── logs               # Session logs
```

### **Core Components**
1. **Command Parser**: Processes user input and DSL commands
2. **Prompt Engine**: Handles variable substitution and template processing
3. **File Manager**: Manages file buffers and file banks
4. **Script Interpreter**: Executes DSL scripts with conditionals
5. **Model Interface**: Communicates with LLMs via API
6. **Session Logger**: Records chat sessions

---

## **Technical Details**

### **Language Features**
- **Type hints** for better code maintainability
- **Environment variables** for API keys (`OPENAI_API_KEY`, etc.)
- **TOML configuration** for models and settings
- **Readline support** for input history and navigation
- **Asynchronous operations** for streaming and file I/O

### **Error Handling**
- File operations (missing files, permissions)
- API calls (rate limits, authentication)
- Command parsing (invalid commands, syntax errors)
- Script execution (runtime errors, missing variables)

### **Performance Considerations**
- **Streaming responses** reduce perceived latency
- **File caching** for frequently used context files
- **Batch processing** for script execution

---

## **Configuration**

Edit `chat_config.toml` to customize:

```toml

[models.mistral_1]
name = "mistral-large-2512"
temperature = 0.7
top_k = 1
base_url = "https://api.mistral.ai/v1"
api_key = "MISTRAL_API_KEY"

[models.gemini_flash]
# Gemini Model running on Google's OpenAI-compatible endpoint
name = "gemini-2.5-flash"
temperature = 0.0
top_k = 1
base_url = "https://generativelanguage.googleapis.com/v1beta/openai/"
api_key = "GEMINI_API_KEY"

```

---

## **Examples**

### **Example 1: Code Generation**
```bash
/codeonly
/file requirements.txt
chat --> Generate a Python Flask app that meets these requirements
```

### **Example 2: Research Assistant**
```bash
/file research_papers.txt
/system "You are a research assistant. Summarize key points."
chat --> What are the main findings in these papers?
```

### **Example 3: Automated Workflow**
```dsl
# setup.chatdsl
set topic = "climate change"
/file ${topic}_notes.txt
chat --> Create a blog post outline about ${topic}
/save ${topic}_outline.md
```

---


## **License**

This project is licensed under the **MIT License**. See the [LICENSE](LICENSE) file for details.

---

## **Support**

For questions or issues:
- Open an issue on [GitHub](https://github.com/jon2allen/chatybot

---

**Happy Chatting with ghatybot** 

