
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
- **Model Switching** - Easily switch between different LLMs
- **File Buffer System** - Load files as context for prompts
- **Multi-Line Input** - Compose complex prompts with ease
- **Streaming Responses** - Real-time output from the model
- **Session Logging** - Save and review chat sessions
- **Input History** - Navigate previous inputs with Tab key

### **Advanced Features**
- **Scripting Engine** - Automate workflows with scripts
- **Variable Substitution** - Dynamic prompts with `${variables}`
- **Conditional Logic** - `if-then` statements in scripts
- **File Banks** - Organize multiple context files
- **Prompt Templates** - Reusable prompt structures
- **Code-Only Mode** - Generate pure code without explanations
- **TinyDB Integration** - Persistent storage for search results and chat logs
- **Advanced Variable Linking** - Use database results in prompts via `${variables}`

---

## **Installation**

### **Prerequisites**
- Python 3.11+
- `pip` package manager
- `parsley` library
- API keys for your preferred LLMs (OpenAI, Anthropic, etc.)

### **Installation Steps**

#### **From PyPI**
```bash
pip install chatybot
```

#### **From Source**
```bash
# Clone the repository
git clone https://github.com/jon2allen/chatybot.git
cd chatybot

# Install in editable mode
pip install -e .

nano src/chatybot/chat_config.toml  # Add your API keys and model configurations
```

### **Troubleshooting**
**macOS Permission Denied Error (`~/.config`)**
On macOS, if you encounter a `Permission denied` error when `chatybot` attempts to access or create the `~/.config` directory, it usually means the folder is owned by `root` or another user. 

To fix this, take ownership of your `.config` directory by running this command in your terminal:
```bash
sudo chown -R $(whoami) ~/.config
```
If the directory does not exist at all and errors persist, you can create it and then set the ownership:
```bash
mkdir -p ~/.config
sudo chown -R $(whoami) ~/.config
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
  /notemode <on|off> - Toggle note mode for /save command.
  /codeonly - Set flag to generate code only without explanations.
  /codeoff - Reverse the code-only flag.
  /multiline - Toggle multi-line input mode (use ';;' to end input).
  /system <message> - Set a custom system message.
  /temp <value> - Set temperature for the current model (0.0-2.0).
  /maxtokens <value> - Set max tokens for the current model.
  /top_p <value> - Set top_p for the current model (0.0-1.0).
  /top_k <value> - Set top_k for the current model.
  /freq_penalty <value> - Set frequency penalty (-2.0-2.0).
  /pres_penalty <value> - Set presence penalty (-2.0-2.0).
  /reasoning <on|off> - Toggle reasoning (thinking) for NVIDIA and Qwen models.
  /thinking <on|off> - Toggle display of <think> and <thought> blocks and reasoning text.
  /thoughtstyle <none|gemma4|nanbeige|nanbeige_code> - Set prompting format for negative prompt to disable reasoning - auto.
  /seed <value> - Set seed (int, 'time', or 'random <min>,<max>').
  /stream - Toggle streaming responses.
  /trace <rawpayload|tps|tpsperf> <on|off> - Debugging options
  /script <file> - Execute a script file containing multiple commands.
  /quit - Exit the program.
  /setdb <dbname> - Create or select a TinyDB database. Use 'Null' to deactivate.
  /dblist - List all TinyDB databases in the db directory.
  /searchdb <query> - Search all docs in the current database.
  /dblog - Log the last chat completion to the database.
  /dbprint - Print the entire database contents in a formatted report.
  /loadvar <varname> [ALL|id|range] - Load search buffer, all docs, a doc ID, or a range (e.g. 1-5) into a variable.
  /savevar <varname> <filename> - Save a variable's contents to a file.
  /setvar <varname> <value> - Set a script variable to a string.
  /mem - Show size of buffers and script variables.
  /dump [varname|all] - Print content of buffers or script variables.

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
| `! <search>` | Search command history and select from last 5 matches | `! model` |
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
| `/top_p <value>` | Set top_p (0.0-1.0) | `/top_p 0.9` |
| `/top_k <value>` | Set top_k | `/top_k 40` |
| `/freq_penalty <value>` | Set freq penalty | `/freq_penalty 0.5` |
| `/pres_penalty <value>` | Set presence penalty | `/pres_penalty 0.5` |
| `/reasoning <on\|off>` | Toggle NVIDIA/Qwen reasoning | `/reasoning off` |
| `/thinking <on\|off>` | Toggle `<think>` and `<thought>` visibility | `/thinking off` |
| `/thoughtstyle <none\|gemma4\|nanbeige\|nanbeige_code>` | Set prompting format for negative prompt to disable reasoning - auto | `/thoughtstyle nanbeige_code` |
| `/seed <value>` | Set PRNG Seed | `/seed time` |

**Note:** `nanbeige_code` may only generate thinking tokens - this is an artifact/quirk of the model.
| `/stream` | Toggle streaming | `/stream` |
| `/trace <cmd> <state>`| Trace tokens/payload | `/trace rawpayload on` |
| `/debug payload` | Edit payload in editor and send to API | `/debug payload` |
| `/codeonly` | Enable code-only mode | `/codeonly` |
| `/codeoff` | Disable code-only mode | `/codeoff` |
| `/notemode <on\|off>` | Toggle note block separation | `/notemode on` |
| `/multiline` | Toggle multi-line input | `/multiline` |
| `/logging <start\|end>` | Start/stop logging | `/logging start` |
| `/save <file>` | Save last response | `/save output.txt` |
| `/script <path>` | Execute a script | `/script setup.dsl` |
| `/setdb <name>` | Select TinyDB database. Use `Null` to deactivate. | `/setdb knowledge` |
| `/dblist` | List all TinyDB databases | `/dblist` |
| `/searchdb <q>` | Search current database | `/searchdb "python"` |
| `/dblog` | Log last response (with prompt/model) to DB | `/dblog` |
| `/dbprint [file]` | Print formatted DB report | `/dbprint report.txt` |
| `/loadvar <v> [p]` | Store search, ALL, ID, or range in variable | `/loadvar results 1-5` |
| `/savevar <v> <f>`| Save variable to file | `/savevar results log.txt` |
| `/setvar <v> <val>`| Set a string variable (text only) | `/setvar user "Jon"` |
| `/imagebank{1-5} <file>` | Load image into bank for vision analysis | `/imagebank1 cat.jpg` |
| `/imagebank{1-5} clear` | Clear an image bank | `/imagebank1 clear` |
| `/imagebank{1-5} show` | Show image bank info | `/imagebank1 show` |
| `/mem` | Show memory size of buffers/variables | `/mem` |
| `/dump [v\|all]` | Dump variables | `/dump all` |
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

### **ChatDSL Validation**
For automated validation of `.chatdsl` files, use the `chatdsl_parse` utility:
```bash
chatdsl_parse --file my_script.chatdsl
```
- Returns exit code **0** on successful parse.
- Returns exit code **1** on parse error or file error.
- Use the `-v` flag for verbose error output.

### **Database & Variable Integration (New!)**
```bash
/setdb my_knowledge       # Open or create 'db/my_knowledge.json'
/searchdb "linked list"   # Search content, results stored in SEARCHBUFFER
/loadvar search_results   # Copy SEARCHBUFFER to ${search_results}
chat --> Explain these: ${search_results}
/dblog                    # Save the AI's explanation back to the database
```

### **Variable Substitution**
Variables can be set manually, via search results, or in scripts:
```bash
/setvar username "Jon"
chat --> Hello ${username}, show me ${search_results}
```

**Note:** Script variables (`/setvar`) are for **text substitution only**. For image analysis with vision models, use image banks instead. Load images with `/imagebank1 <file>` and reference them with `{imagebank1}` syntax in your prompts. The `{imagebank1}` placeholder sends the image as a proper multimodal attachment, while `${var}` substitution inserts text only.

### **Image Generation**
chatybot supports **text-to-image generation** and **image-to-text (vision) analysis** for supported models.

#### **Image Output Directory**
Generated images are saved to a date-organized directory structure:
```
~/chatybot_images/
└── YYYY-MM-DD/
    ├── prompt_001.png
    ├── prompt_002.png
    └── ...
```

**Configuration:**
- Default: `~/chatybot_images/` (set in `chat_config.toml` under `[image_generation].default_dir`)
- Override at runtime: `/imagedir /custom/path/to/images`
- Override in config: Edit `default_dir` in `src/chatybot/chat_config.toml`

**Path Resolution:**
1. Config file `default_dir` (if set)
2. Hardcoded fallback: `~/chatybot_images`

#### **Text-to-Image Generation**
Generate images from text prompts using supported models (OpenAI, Mistral, Google, OpenRouter):
```bash
/model openrouter_image
/imagine "a red toyota corolla 1980s on a mountain road"
```

**Supported Models:**
- `openrouter_image`: Google gemini-2.5-flash-image (OpenRouter)
- `flux_1`: Flux.2 models (OpenRouter)
- `mistral_1`: Mistral image models
- `gemini_flash`, `gemini_pro`: Google image models

**Image Size Options:**
```bash
/imagesize 1024x1024      # Default
/imagesize 1920x1080      # Wide
/imagesize 1K            # Google format for gemini models
```

#### **Image-to-Text (Vision) Analysis**
Load images into image banks and query vision models:
```bash
/imagebank1 my_photo.jpg     # Load image into bank 1
/model openrouter_image     # Switch to vision model
Describe this image: {imagebank1}
```

**Image Bank Commands:**
| Command | Description | Example |
|---------|-------------|---------|
| `/imagebank{1-5} <file>` | Load image into bank | `/imagebank1 cat.jpg` |
| `/imagebank{1-5} clear` | Clear an image bank | `/imagebank1 clear` |
| `/imagebank{1-5} show` | Show image bank info | `/imagebank1 show` |

### **Conditional Logic**
```dsl
set debug = true
if ${debug} then /temp 0.1
if not ${debug} then /temp 0.7
```

### **Macro System (New!)**
Chatybot now features a powerful macro system based on Parsley. Macros allow you to define reusable prompt templates with parameters.

**Defining Macros** (in `src/chatybot/macro.chatdsl`):
```dsl
def expert(topic) = "You are an expert in {topic}. Provide detailed information about {topic}."
def compare(a, b) = "Compare {a} and {b} and discuss their differences."
```

**Using Macros**:
```bash
%expert(Python)
%compare("GPT-4", "Claude 3")
```
Macros can be called from the interactive prompt or within scripts. Inline variable substitution is supported in macro arguments: `%expert(${current_topic})`.

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

```text
chatybot/
├── pyproject.toml       # Python package build configuration
├── cleanhouse.sh        # Setup/Reinstall cleanup script
├── src/chatybot/        # Main application package
│   ├── main.py          # Primary application entry point
│   ├── chatydb.py       # TinyDB database manager module
│   ├── extract_code.py  # Utilities for isolating code blocks
│   ├── chat_config.toml # Default/Fallback LLM configuration
│   └── macro.chatdsl    # Default macro definitions
├── dsl_test/            # Script examples and testing
├── ~/.config/chatybot/  # Active user configuration directory (Auto-generated)
└── ~/.local/share/chatybot/ # Active database and history storage (Auto-generated)
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

### Change log

Apr 20th, 2026
--------------
- **Image Generation Configuration**: Synchronized `chat_config.toml` with local additions (mistral_pixtral, elephant models) and updated flux_1 to flux.2-klein-4b
- **OpenRouter Size Fix**: Resolved Google model image generation error by mapping pixel sizes to K-based format (1024x1024→"1K") when manually set via `/imagesize`
- **Hybrid Size Handling**: Implemented smart size handling that skips `image_config` for Google models when using default size
- **Echo Command Bug Fix**: Fixed `'tuple' object has no attribute 'startswith'` error by unpacking tuple from `replace_placeholders()`
- **Memory & History**: Added CHAT_HISTORY to `/mem` display, enabled `/dump CHAT_HISTORY`, added `/save <file> all` for full chat history export
- **Documentation**: Updated `/help` text to clarify `/setvar` is for text-only variables, added Image Generation section to README, documented image bank requirements for vision models
- **Test Assets**: Added 15 test images with corresponding .txt files containing `subject:` and `color:` for accuracy testing, created comprehensive `accuracytest.chatdsl` script

Apr 14th, 2026 (v0.3.0)
--------------
- **Parsley Macro System**: Integrated a robust macro expansion system using Parsley grammars.
- **Macro Definitions**: Supports `def name(params) = "template"` syntax with multi-parameter support.
- **Macro Invocations**: Use `%name(args)` to expand templates in prompts and scripts.
- **Variable Integration**: Macro arguments support `${variable}` substitution.
- **Packaging**: Relocated `macro.chatdsl` to the package source and updated `pyproject.toml` to include it in distribution.
- **Dependencies**: Added `parsley` as a core dependency.

Apr 5th, 2026 (v0.2.9)
--------------
- **New Thought Styles**: Added `nanbeige` and `nanbeige_code` thought styles for specialized prompt formatting.
- **Nanbeige Style**: Implements `<think> </think>` wrapping with response-only instructions for concise answers.
- **Nanbeige Code Style**: Implements `<think></think>` wrapping with code-only instructions for minimal commentary code generation.
- **Documentation**: Updated help text and documentation to clarify thought style usage and model quirks.
- **Command Enhancement**: Updated `/thoughtstyle` help to describe it as "prompting format for negative prompt to disable reasoning - auto".

Apr 1st, 2026 (v0.2.8)
--------------
- **Command Validation**: Added a safety check to detect command verbs sent without an escape character (e.g., `help`, `model`) at the start of a prompt, preventing unintentional LLM calls.
- **Improved Responsiveness**: Reduced wait times by quickly identifying invalid command usage.
- **PyPI Release**: Bumped version for publication to PyPI and synchronized startup display.

Mar 31st, 2026 (v0.2.7)
--------------
- **ChatDSL Parser CLI**: Added `chatdsl_parse` as a standalone executable script.
- **Exit Codes**: Updated `chatdsl_parse` to return 0 on success and 1 on parse Failure/Exception.
- **Packaging**: Integrated `chatdsl_parse` into `pyproject.toml` console scripts.

Mar 20th, 2026 (v0.2.6)
--------------
- **Apostrophe Recognition**: Resolved a critical bug where apostrophes in natural language (e.g., "Assyria's") were misinterpreted as opening quotes, incorrectly merging commands.
- **Robust Path Capture**: Enhanced `/save`, `/prompt`, and `/file` handlers to support filenames with spaces by capturing the entire command remainder.
- **Substitution Integrity**: Fixed a regression that caused variable substitution regexes to be double-escaped, ensuring `${varname}` tokens are correctly replaced.

Mar 19th, 2026 (v0.2.5)
--------------
- **New Command `/echo`**: Implemented direct stdout printing with full variable substitution and automatic quote stripping.
- **Multiline Variable Support**: Enabled the `set` command to capture values spanning multiple lines when wrapped in quotes.

Mar 16th, 2026
--------------
- **Advanced Logic**: Significantly expanded `if-then` logic to support full string comparisons (`==`, `!=`) and logical negation (`not`).
- **Parameterized Scripts**: Updated `/script` to allow passing inline variables (e.g., `/script file.chatdsl x="value"`).
- **Security Sanitization**: Added a safety check to disallow escape characters (`\\`) within `set` variable assignments.
- **Test Infrastructure**: Added test data, `CHATDSL_TECHNICAL_GUIDE.md`, and `civil_war_1865.chatdsl`.

Mar 15th, 2026 (v0.2.4)
--------------
- **Database Enhancements**: Added `/dbprint` command to generate high-quality formatted reports of database contents.
- **Improved Logging**: Enhanced `/dblog` to capture the original prompt and detailed model metadata (name and alias) for better analysis.
- **Qwen Support**: Added explicit reasoning control for Qwen (SiliconFlow) models via the `/reasoning` command.
- **Documentation**: Updated ChatDSL BNF and technical specifications.

Mar 5th, 2026 (v0.2.3)
----------------------
- **Bug Fixes**: Fixed `SEARCHBUFFER` reference issue by mutating the list in-place, ensuring visibility across modules for `/mem` and `/dump`.
- **Maintenance**: Version bump for PyPI release.

Mar 5th, 2026 (v0.2.2)
----------------------
- **Bug Fixes**: Fixed `/savevar` and `/loadvar` to correctly use the buffer manager's variable storage.
- **Enhanced Debugging**: Added `SEARCHBUFFER` visibility to `/mem` and `/dump` commands.
- **Maintenance**: Removed redundant script variable attributes from the main application class.

Mar 5th, 2026 (v0.2.1)
----------------------
- **Testing**: Added test suite and increased coverage of dsl_test.
- **Variable Substitution**: Update to substitution for variables.

Mar 3rd, 2026
-------------
- **Variables**: Updated variable substitution in set statement.

Mar 2nd, 2026
-------------
- **Cleanup**: Removed sonnet test data and test fruit directory.
- **Fixes**: Corrected nanjing chatdsl.

Feb 27th, 2026
-------------
- **Bug Fixes**: Fixed temperature command to use instance variable, fixed `/listmodels` command formatting, and fixed SEARCHBUFFER issue in `search_db`.
- **Database Features**: Added database commands to refactored version.
- **Documentation**: Removed emojis from documentation and consolidated dates.
- **Complete OOP Refactoring**: Comprehensive architectural overhaul from procedural to object-oriented design:
  - Created ConfigManager class for centralized configuration management
  - Created LoggingManager class for logging functionality
  - Created BufferManager class for buffer and variable management
  - Created ChatybotApp class as main application orchestrator
  - Simplified main.py to be just an entry point
  - Applied OOP best practices: encapsulation, single responsibility, composition
  - Maintained all existing functionality while improving code structure
  - Added comprehensive test suite and detailed refactoring documentation
  - New architecture provides better maintainability, testability, and extensibility

Feb 26th, 2026
--------------
- **Tracing & Debugging**: Added new `/trace` command options:
  - `/trace rawpayload on`: Dumps the raw JSON string passed to the LLM completion API.
  - `/debug payload`: Captures the payload that would be sent to the LLM API, opens it in your system editor for modification, then sends the modified payload to the API and displays the response.
  - `/trace tps on`: Calculates and outputs think tokens and regular tokens per second.
  - `/trace tpsperf on`: Logs an in-memory bucketed tokens per second calculation, saved out to a quoted CSV on completion.

Feb 24th, 2026
--------------
- **Version 0.1.2 Release**: Preparation and package bumping for PyPI publication.
- **Enhanced Reasoning Display**: Added support to natively color and display `<think>` tags embedded within standard content streams (e.g., `nanbeige` or local Ollama usage).
- **Backend Model Extractor Fixes**: Updated the openai dependency requirement to `>=1.61.0` and added fallbacks to capture both `reasoning_content` and `reasoning` delta fields for wider compatibility.
- **System Commands Optimization**: Fixed a bug where `/system` would truncate inputs after the first word, properly capturing full multi-word system prompts.

Feb 22nd, 2026
--------------
- **Packaging and Distribution**: 
  - Restructured into `src/chatybot` module for PEP 517 compliance. 
  - Added `pyproject.toml` enabling rapid `pip install` globally across the path via console script `chatybot`.
  - Migrated configuration files and databases from the active working directory into persistent `~/.config/chatybot/` and `~/.local/share/chatybot/` locations.
  - Built graceful config fallbacks and a cleanup script for straightforward deployments.
- **Model Compatibility**:
  - Added dummy API key bypass logic for testing with local `localhost`/`Ollama` server endpoints natively.
  - Expanded `/reasoning off` toggle support to also apply to Qwen (2.5/3) reasoning models.

Feb 17th, 2026
--------------
- **Enhanced Database Control**: Added `/setdb Null` to deactivate database support dynamically.
- **Advanced `/loadvar`**: Now supports `ALL`, specific `id`, and `range` (e.g., `1-5`) for the database items.
- **Improved Usability**: Added shebang to `chatybot.py` for direct execution.

Jan 25th, 2026
--------------
- **LLM Parameter Tuning**: Added commands for `/seed`, `/top_k`, `/top_p`, `/freq_penalty`, and `/pres_penalty`.
- **NVIDIA Reasoning**: Added `/reasoning <on|off>` to toggle detailed thinking for NVIDIA models.
- **Debugging Suite**: New commands `/mem` and `/dump` for inspecting buffer sizes and variable contents.
- **Database Management**: Added `/dblist` to view available TinyDB files.
- **Provider Stability**: Improved compatibility for Mistral, Google Gemini, and Bytez APIs.

Jan 24th, 2026
--------------
- **TinyDB Integration**: New database module (`chatydb.py`) for persistent storage.
- **Persistent Search Buffer**: `/searchdb` results are cached in `SEARCHBUFFER`.
- **Variable Linking**: `/loadvar` now bridges database results to `${variable}` placeholders.
- **Prompt Injection**: All prompts now support `${variable}` substitution for dynamic context.
- **Manual Variables**: Added `/setvar` for setting session variables via the CLI.
- **Database Logging**: `/dblog` allows one-click archiving of AI responses to the active database.

Jan 10th
-------------

  - added /notemode - this will split code from explaination.  but only first block.

   Warning:  should not be used for marddown, readme or other such docs.

```
===========================
Active model: mistral-large-2512 (alias: mistral_1)
chat --> /model nvidia_1
Switched to model: nvidia/nemotron-nano-12b-v2-vl:free (alias: nvidia_1)
chat --> create a C program that demostrates a linked list
Here's a well-structured C program that demonstrates the implementation and usage of a **singly linked list**. This program includes basic operations such as:

- **Appending** elements to the end of the list.
- **Printing** the contents of the list.
- **Freeing** the memory allocated to the list to prevent memory leaks.

---

### C Program: Demonstrating a Singly Linked List

```c
#include <stdio.h>
#include <stdlib.h>

.............

This program provides a solid foundation for understanding and working with linked lists in C. You can expand upon it to implement more complex data structures or algorithms.


Execution time: 28.95 seconds
Input tokens: 29, Output tokens: 2509
chat --> /notemode on
Note mode enabled. Code blocks will be extracted when using /save.
chat --> /save demo_link_list.c
Last chat completion saved to 'demo_link_list.c'.
Note mode is ON. Processing file 'demo_link_list.c'...
Processed demo_link_list.c -> notes_demo_link_list.c

```

The demo_link_list.c should be a raw C file.  the notes_ prefix has all the notes

```
-rw-r--r--  1 jon2allen jon2allen  1.6K Jan 10 16:24 demo_link_list.c
-rw-r--r--  1 jon2allen jon2allen  1.6K Jan 10 16:24 notes_demo_link_list.c
```
       

  - enhanced logging - when logging is enabled 

```
Datetime: Jan 10, 2026, 04:11:42 PM 
Model: nvidia_1 (nvidia/nemotron-nano-12b-v2-vl:free)
User: create a bash program that uses cat for all programs with *.py extension in a subdir

Execution time: 50.25 seconds
Number of tokens: Input 37, Output 3971
Assistant: Here's a well-structured Bash script that uses the `cat` command to display the contents of all `.py` files located in a specified subdirectory. The script is designed to be flexible, robust, and user-friendly.
```
---


## **License**

This project is licensed under the **MIT License**. See the [LICENSE](LICENSE) file for details.

---

## **Support**

For questions or issues:
- Open an issue on [GitHub](https://github.com/jon2allen/chatybot)

---

## **Releasing to PyPI**

To build and upload a new version to PyPI, follow these steps:

1. **Clean previous builds:**
   ```bash
   rm -rf dist/ build/ *.egg-info
   ```

2. **Build the package:**
   ```bash
   python3 -m build
   ```

3. **Upload using Twine:**
   ```bash
   python3 -m twine upload dist/*
   ```

Note: Ensure you have bumped the version in `pyproject.toml` and synchronized the display version in `src/chatybot/chatybot_app.py` before building.

---

**Happy Chatting with chatybot** 
