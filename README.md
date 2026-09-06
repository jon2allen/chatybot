
# chatybot - Interactive AI Chatbot Interface

[![PyPI Version](https://img.shields.io/pypi/v/chatybot.svg)](https://pypi.org/project/chatybot/)
[![Documentation](https://img.shields.io/badge/docs-GitHub%20Doc%20Tree-blue.svg)](https://github.com/jon2allen/chatybot/tree/master/doc)
[![ChatDSL Cookbook](https://img.shields.io/badge/ChatDSL-Cookbook-orange.svg)](https://github.com/jon2allen/chatybot/blob/master/doc/chatdsl_cookbook.md)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](https://opensource.org/licenses/MIT)

**chatybot** is a powerful command-line interface for interacting with language models, featuring a custom domain-specific language (DSL) for advanced prompt engineering, scripting, and automation.

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
- **Config Utility Views** - Interactive TUI for managing model configurations with vendor presets
- **Native Array & Subscript Support** - Declare list variables with `[]` and access elements using index subscripts
- **Extended Metadata Database Search** - `/searchdb` recursively searches through structured record metadata (JSON, lists, and dicts) for a target query
- **Model Context Protocol (MCP)** - Dynamic host connecting to stdio-based MCP servers with robust session/lifecycle management
- **Multilingual Support (i18n)** - Out-of-the-box support for Spanish, French, Chinese, Italian, and Levantine Arabic, featuring localized CLI strings and cross-locale command alias resolution
- **Math Evaluation Engine** - Inline `/calc` calculation command and a patch-supported mathematical expression evaluation tool
- **Session Persistence & Workspace Management** - Multi-turn session history persistence, notes annotation, workspace metrics, gzip compression, pruning, and Markdown transcript exports (`/session`)
- **Procedure Definition Engine** - Reusable script procedures with stack-frame isolation and local variable scoping (`defproc`, `/proc`, `local`)
- **Multiline Iteration & Generators** - `foreach` loops supporting collections, `range()`, `lines()` file iteration, and early `break` statements
- **Pattern Search** - Substring and regex pattern matching across text variables into `${STR_SEARCH}` (`/str_search`)
- **Macro Management & Tutorial** - Macro inspection table (`/listmacros`) with signatures, templates, search filter, and interactive tutorial
- **Profile TUI Manager** - Full curses-based profile editor (`--profile-edit` / `/profile edit`)
- **Optimized Startup Performance** - Deferred macro PEG grammar compilation and on-demand SDK imports for ultra-fast boot times
- **Context Budgeting & Metrics** - Dynamic token budget tracking, soft warnings (30KB), hard truncation safeguards (50KB), and `get_context_metrics` inspection tool
- **Time-Travel Context Replay** - Reconstruct, inspect, and diff the exact token context arrays and message eviction histories across session turns (`/replay`) and agentic tool loops (`/tool replay`)
- **Permanent Capability Error Guard** - Automatic protocol/capability error detection and immediate tool auto-disabling to eliminate infinite agentic retry loops
- **Hugging Face Preset & `/env` Inspection** - Vendor preset for Hugging Face inference endpoints and dedicated `/env` environment inspection command
- **Enhanced Session Filtering & Sorting** - `/session list` sorting by latest activity, model filtering (`model=...`), and range pagination (`limit=...`, `range=start:end`)


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

**Windows Python App Execution Aliases Conflict**
On Windows, Microsoft includes "App Execution Aliases" by default that redirect `python.exe` and `python3.exe` calls to the Microsoft Store redirector (`C:\Users\<user>\AppData\Local\Microsoft\WindowsApps`) if Python path priority collides. This can intercept `python` calls and interfere with Chatybot's tool execution environment.

**Recommended Solution**:
1. Open Windows Settings (`Win + I`).
2. Navigate to: **Apps** → **Advanced app settings** → **App execution aliases**.
3. Turn **OFF** the toggles for:
   - **App Installer (`python.exe`)**
   - **App Installer (`python3.exe`)**
4. Restart your terminal and verify your installation with `python --version`.

---

## **Quick Start**

Get started with Chatybot in 3 simple steps:

### **1. Install Chatybot**

```bash
pip install chatybot
```
*(Or install from source with `git clone https://github.com/jon2allen/chatybot.git && cd chatybot && pip install -e .`)*

---

### **2. Set Your API Key(s)**

> [!IMPORTANT]
> **How Chatybot handles API keys**: In `chat_config.toml`, model definitions reference the **name of the environment variable** (for example, `api_key = "MISTRAL_API_KEY"`), NOT the raw secret string. This keeps your secrets safely out of configuration files and Git commits.

Choose any of the following methods to set your keys:

#### **Method A: Interactive Setup Wizard (Fastest & Easiest)**
Chatybot provides an interactive wizard that securely prompts for keys, masks credentials, and saves them to `.env` or your system environment:

* **Cross-Platform (Linux, macOS, Windows)**:
  ```bash
  # Run directly from the chatybot command:
  chatybot --setup-keys

  # Or via the standalone tool:
  chatybot-setup-keys
  ```
* **Linux / macOS / WSL (From git clone)**:
  ```bash
  ./bin/setup_keys.sh
  ```
* **Windows (From git clone - CMD, PowerShell, or Double-Click)**:
  ```cmd
  bin\setup_keys.bat
  ```

#### **Method B: Shell / System Environment Variables**

* **Linux & macOS (`bash` / `zsh`)**:
  ```bash
  # Mistral AI (Default preset in chat_config.toml)
  export MISTRAL_API_KEY="your-mistral-api-key"

  # Optional additional providers:
  export OPENAI_API_KEY="your-openai-api-key"
  export OPENROUTER_API_KEY="your-openrouter-api-key"
  export GEMINI_API_KEY="your-gemini-api-key"
  export ANTHROPIC_API_KEY="your-anthropic-api-key"
  export NVIDIA_API="your-nvidia-api-key"
  ```
  > **Tip**: Persist across sessions by appending to `~/.zshrc` (macOS) or `~/.bashrc` (Linux):
  > ```bash
  > echo 'export MISTRAL_API_KEY="your-key"' >> ~/.zshrc && source ~/.zshrc
  > ```

* **Windows Command Prompt (`cmd.exe`)**:
  ```cmd
  rem Permanent user environment variable (active in all new terminal windows):
  setx MISTRAL_API_KEY "your-mistral-api-key"

  rem Current session only:
  set MISTRAL_API_KEY=your-mistral-api-key
  ```

* **Windows PowerShell**:
  ```powershell
  # Permanent user environment variable:
  [System.Environment]::SetEnvironmentVariable('MISTRAL_API_KEY', 'your-mistral-api-key', 'User')

  # Current session only:
  $env:MISTRAL_API_KEY = "your-mistral-api-key"
  ```

#### **Method C: Using a `.env` File (All Platforms)**
Copy the included template and fill in your keys:
```bash
# Linux / macOS:
cp .env.example .env

# Windows (Command Prompt):
copy .env.example .env
```
Open `.env` in any text editor and paste your keys. Chatybot automatically detects and loads `.env` on startup from your current working directory or `~/.config/chatybot/.env`.

#### **Supported API Key Reference**

| Provider | Environment Variable | Default Preset in Chatybot? | Where to get key |
|:---|:---|:---|:---|
| **Mistral AI** | `MISTRAL_API_KEY` | **Yes** (`mistral_1`) | [console.mistral.ai](https://console.mistral.ai/) |
| **OpenAI** | `OPENAI_API_KEY` | Optional (`gpt_4o`, `o1`, `o3`) | [platform.openai.com](https://platform.openai.com/api-keys) |
| **OpenRouter** | `OPENROUTER_API_KEY` | Optional (`mistral_pixtral`, `claude`, etc.) | [openrouter.ai](https://openrouter.ai/keys) |
| **Google Gemini** | `GEMINI_API_KEY` | Optional (`gemini_flash`, `gemini_pro`) | [aistudio.google.com](https://aistudio.google.com/app/apikey) |
| **Anthropic** | `ANTHROPIC_API_KEY` | Optional (Claude models) | [console.anthropic.com](https://console.anthropic.com/) |
| **NVIDIA NIM** | `NVIDIA_API` | Optional (`nvidia_llama3`) | [build.nvidia.com](https://build.nvidia.com/) |
| **Groq** | `GROQ_API_KEY` | Optional (Llama 3, Mixtral) | [console.groq.com](https://console.groq.com/keys) |
| **DeepSeek** | `DEEPSEEK_API_KEY` | Optional | [platform.deepseek.com](https://platform.deepseek.com/) |
| **Cohere** | `COHERE_API_KEY` | Optional | [dashboard.cohere.com](https://dashboard.cohere.com/api-keys) |
| **Hugging Face** | `HF_API_KEY` | Optional (`hf_preset`) | [huggingface.co](https://huggingface.co/settings/tokens) |
| **Jina AI** | `JINA_API_KEY` | Optional (Search & Reranking) | [jina.ai](https://jina.ai/) |
| **Ollama** | *(None required)* | Local models (`ollama_llama3`) | Localhost (`http://localhost:11434/v1`) |

---

### **3. Start Chatybot & Verify**

Launch Chatybot from anywhere:
```bash
chatybot
```

Once inside the interactive prompt, you can verify and manage your setup:

```text
chat --> /env             # Inspect detected API keys and active environment variables
chat --> /listmodels      # View all available models and their endpoints
chat --> /model mistral_1 # Switch active model (or e.g. /model gemini_flash)
chat --> /help            # View all available escape commands
chat --> Hello!           # Start chatting!
```


---

## **Command Reference**

| Command | Description | Example |
|---------|-------------|---------|
| `! <search>` | Search command history and select from last 5 matches | `! model` |
| `/help` | Show help message | `/help` |
| `/model <alias>` | Switch models | `/model gpt4` |
| `/listmodels` | List available models | `/listmodels` |
| `/env [filter]` | Display defined API keys & env vars (`set \| grep -i api`) | `/env` |
| `/file <path>` | Load file into buffer | `/file notes.txt` |
| `/filebank1 <path>` | Load file into file bank 1 | `/filebank1 data.txt` |
| `/showfile [all]` | Show file content | `/showfile all` |
| `/clearfile` | Clear file buffer | `/clearfile` |
| `/prompt <path>` | Load prompt template | `/prompt template.txt` |
| `/system <msg>` | Set system message | `/system "You are an expert coder."` |
| `/temp <value>` | Set temperature (0.0-2.0) | `/temp 0.7` |
| `/maxtokens <value>` | Set max tokens (alias: `/max_tokens`) | `/maxtokens 1000` |
| `/top_p <value>` | Set top_p (0.0-1.0) | `/top_p 0.9` |
| `/top_k <value>` | Set top_k | `/top_k 40` |
| `/freq_penalty <value>` | Set freq penalty | `/freq_penalty 0.5` |
| `/pres_penalty <value>` | Set presence penalty | `/pres_penalty 0.5` |
| `/reasoning <on\|off>` | Toggle NVIDIA/Qwen/GLM reasoning | `/reasoning off` |
| `/effort <low\|medium\|high\|xhigh\|none>` | Set reasoning effort / strength for OpenAI (o1, o3), Mistral, GLM (GLM-5.2), and Meta Muse Glimmer | `/effort high` |
| `/thinking <on\|off>` | Toggle `<think>` and `<thought>` visibility | `/thinking off` |
| `/thoughtstyle <none\|gemma4\|nanbeige\|nanbeige_code>` | Set prompting format for negative prompt to disable reasoning - auto | `/thoughtstyle nanbeige_code` |
| `/seed <value>` | Set PRNG Seed | `/seed time` |
| `/stream` | Toggle streaming | `/stream` |
| `/trace <cmd> <state>`| Trace tokens/payload | `/trace rawpayload on` |
| `/debug <payload\|response [raw]\|vmem [start\|stop\|status]>` | Control debug modes or background virtual memory logging | `/debug vmem start` |
| `/codeonly` | Enable code-only mode | `/codeonly` |
| `/codeoff` | Disable code-only mode | `/codeoff` |
| `/notemode <on\|off>` | Toggle note block separation | `/notemode on` |
| `/multiline` | Enter multi-line input | `/multiline` |
| `/logging <start [hex]\|end\|hex [on\|off]>` | Start (with optional hex escaping) or stop logging | `/logging start hex` |
| `/save <file> [all] [nothink\|withthink]` | Save last response or all history, with optional thinking stripping | `/save output.txt all nothink` |
| `/script <path>` | Execute a script | `/script setup.dsl` |
| `/source <path>` | Execute a script dynamically in the current session | `/source ~/.chatybot_profile` |
| `/profile [subcommand]` | Manage session profiles dynamically (list, use, clone, delete, export, import, show, edit) | `/profile use coding` |
| `/run <command>` | Execute a shell command and capture stdout/stderr/exit code | `/run ls -la` |
| `/run_safe` | Enable safe mode for shell execution (blocks dangerous commands) | `/run_safe` |
| `/run_unsafe [askfirst]` | Disable safe mode (runs directly; optional `askfirst` prompts Y/N) | `/run_unsafe` |
| `/tool <subcommand>` | Manage native tool loop mode, scratchpad directory, inspect prompt context, or dispatch invocations | `/tool scratch on` |
| `/setdb <name>` | Select TinyDB database. Use `Null` to deactivate. | `/setdb knowledge` |
| `/dblist` | List all TinyDB databases | `/dblist` |
| `/searchdb <q>` | Search current database | `/searchdb "python"` |
| `/dblog` | Log last response (with prompt/model) to DB | `/dblog` |
| `/dbprint [file]` | Print formatted DB report | `/dbprint report.txt` |
| `/loadvar <v> [p]` | Store search, ALL, ID, or range in variable | `/loadvar results 1-5` |
| `/savevar <v> <f>`| Save variable to file | `/savevar results log.txt` |
| `/setvar <v> <val>`| Set a string variable (supports `{CHAT_HISTORY}` JSON export) | `/setvar var1 {CHAT_HISTORY}` |
| `/documents <src>=<id>`| Set the active rerank source: `db=<name>`, `var=<name>` (or `CHAT_HISTORY`/`file`), `filebank=<1-5>`, or `dir="<path>"` | `/documents dir="test/conrad_test"` |
| `/rerank "<query>"` | Semantically rerank source sentences/chunks with optional parameters | `/rerank "sea voyage" top_n=3 split=paragraph` |
| `/trace rerank <state>`| Enable/disable debugging output for the reranking processor | `/trace rerank on` |
| `/imagebank{1-5} <file>` | Load image into bank for vision analysis | `/imagebank1 cat.jpg` |
| `/imagebank{1-5} clear` | Clear an image bank | `/imagebank1 clear` |
| `/session [subcommand]` | Manage multi-turn session persistence, note annotations, exports, merging, compression, and pruning | `/session start my_project` |
| `/listmacros [filter]` | List loaded macros with signatures, templates, and search filter | `/listmacros debug` |
| `/reloadmacros [file]` | Reload macro definitions from `macro.chatdsl` or a custom file | `/reloadmacros` |
| `/str_search "<pat>" <var> [flags] [dest]` | Search substring patterns in a text variable into `${STR_SEARCH}` (flags: `c`=count, `m`=positions, `i`=ignore case) | `/str_search "error" ${LOG} ic count_var` |
| `/proc <name> [p1="v1"]` | Execute a named procedure block defined with `defproc` | `/proc summarize_text text="${file_buffer}"` |
| `defproc <name>(<args>)` | Define a reusable procedure block with isolated local variable scoping (`local var = val`) | `defproc greet(name)` |
| `foreach <var> in <iter>` | Multiline loop iterating over arrays, `range(start, end[, step])`, or `lines("file.txt")` | `foreach x in range(1, 5)` |
| `/break` \| `break` | Terminate the enclosing `foreach` loop immediately | `break` |
| `/mem` | Show memory size of buffers/variables | `/mem` |
| `/dump [v\|v[idx]\|all]` | Dump variables or specific array elements | `/dump all` or `/dump arr[0]` |
| `/quit` \| `/exit` | Exit the program | `/quit` |

| **CLI Flag** | Description | Example |
|-------------|-------------|---------|
| `--config-edit` | Launch the TUI configuration manager to edit models | `chatybot --config-edit` |
| `--profile-edit` | Launch the interactive TUI profile manager | `chatybot --profile-edit` |
| `-c <path>` \| `--config <path>` | Path to alternate TOML configuration file | `chatybot -c ~/my_config.toml` |
| `--script <path>` | Execute a script file and exit | `chatybot --script test.chatdsl` |
| `--run <query>` | Execute a single query (prompts or chained escape commands) and exit | `chatybot --run "/model gpt4; list 5 cities"` |
| `--profile <name\|path>` | Load a startup profile or script prior to entering interactive REPL | `chatybot --profile coding` |
| `--no-tools` | Disable tools on startup and bypass all MCP server loading via stdio | `chatybot --no-tools` |

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
When used interactively, `/prompt` displays the file content (truncated to 500 chars) and asks for confirmation before executing. In script context (inside a `.chatdsl` script), `/prompt` auto-executes without confirmation — the prompt is sent to the model immediately.

### **Scripting & Dynamic Sourcing**
Create a script file (`setup.chatdsl`):
```dsl
set project = "chatbot"
if ${project} then /file ${project}_requirements.txt
wait 1
chat --> Generate documentation for this project
```

#### **Executing Scripts (`/script` vs `/source`)**
* **`/script <file> [key="value"]...`** — Executes a script with optional runtime parameter bindings:
  ```bash
  /script setup.chatdsl project="my_app"
  ```
* **`/source <file>`** — Dynamically executes a script directly in the **current interactive session** (like Unix shell `source` / `.`):
  ```bash
  /source ~/.chatybot_profile
  /source setup_env.chatdsl
  ```
  - **State Retention**: Defined variables (`${var}`), switched models (`/model`), toggled tools (`/tool`), and defined procedures (`defproc`) persist in your active REPL session.
  - **Companion Macro Auto-Loading**: If a `macro.chatdsl` file exists in the same directory as the sourced script, its macros are compiled and loaded automatically.
  - **Multilingual Support**: Automatically preprocessed through the localization engine (also callable as `/origen`, `/加载脚本`, `/sorgente`, `/مصدر`).

#### **Multilingual ChatDSL Guides**
To assist users in multiple languages, localized versions of the ChatDSL technical guide are available in the [doc](doc/) folder:
- 📖 [Arabic ChatDSL Guide (العربية)](doc/chatdsl_guide_v1_arabic.md)
- 📖 [Chinese ChatDSL Guide (简体中文)](doc/chatdsl_guide_v1_chinese.md)
- 📖 [French ChatDSL Guide (Français)](doc/chatdsl_guide_v1_french.md)
- 📖 [Italian ChatDSL Guide (Italiano)](doc/chatdsl_guide_v1_italian.md)
- 📖 [Spanish ChatDSL Guide (Español)](doc/chatdsl_guide_v1_spanish.md)


### **ChatDSL Validation**
For automated validation of `.chatdsl` files, use the `chatdsl_parse` utility:
```bash
chatdsl_parse --file my_script.chatdsl
```
- Returns exit code **0** on successful parse.
- Returns exit code **1** on parse error or file error.
- Use the `-v` flag for verbose error output.

### **Database & Variable Integration (New!)**
The `/searchdb` command performs a case-insensitive search across the document `name`, `content`, and any keys or values stored in its `metadata` (such as `model_alias`, `model_name`, or custom tags).

```bash
/setdb my_knowledge       # Open or create 'db/my_knowledge.json'
/searchdb "linked list"   # Search name, content, and metadata fields
/loadvar search_results   # Copy SEARCHBUFFER to ${search_results}
chat --> Explain these: ${search_results}
/dblog                    # Save the AI's explanation back to the database
```

### **Semantic Reranking**
chatybot supports real-time semantic document reranking via the `EasyRerank` library. This allows you to automatically split massive document sources (directories, database records, variables, or conversation history) into semantic chunks, score them against a target query using local or remote cross-encoder models, and inject only the most relevant context back into LLM prompts.

#### **1. Setting the Active Dataset (`/documents`)**
Specify the target corpus using the `/documents` command:
```bash
/documents <source_type>=<identifier>
```
*   `db=<name>`: Fetches records from a TinyDB database matching `<name>`.
*   `var=<name>`: Loads from a script variable (e.g. `${search_results}`).
*   `var=CHAT_HISTORY`: Special variable that segments the current conversation history.
*   `var=file`: Uses the main file buffer directly.
*   `filebank=<1-5>`: Uses the contents of `filebank1` through `filebank5`.
*   `dir="<path>"`: Specifies a local folder containing `.txt` files (wrap in double quotes if the path contains spaces).

#### **2. Executing Reranking (`/rerank`)**
Rerank the active documents against a search query:
```bash
/rerank "<query>" [, top_n=<n>] [, items=<n>] [, split=<sentence|line|paragraph>] [, return=<summ|text>] [, full_doc=<true|false>] [, limit_batch_size=<n>] [, limit_top_n=<n>] [, max_limit=<n>]
```
**Parameters:**
*   `top_n` *(Default: 2)*: Maximum number of top results to return.
*   `items` / `item` *(Default: 1)*: Number of segmentation units grouped per text chunk.
*   `split` *(Default: sentence)*: Segmentation mode:
    *   `sentence`: Sub-document sentence-based segmentation.
    *   `line`: Segments strictly by non-empty lines (keeps tables and lists together).
    *   `paragraph`: Segments by double newlines (`\n\n`).
*   `return` *(Default: summ)*:
    *   `summ`: Prints a beautifully formatted ASCII results table (Rank, Score, Reference, Snippet) and appends it to the chat history as a virtual assistant turn.
    *   `text`: Returns the plain text of matched chunks concatenated together (perfect for saving into script variables).
*   `full_doc` *(Default: false)*: If `true`, returns the parent document content (from database, file, variable) rather than just the segment chunk text.
*   `limit_batch_size` *(Default: 64)*: Batch size for batched Top-N pre-filtering.
*   `limit_top_n` *(Default: 3)*: Top N chunks kept per pre-filtering batch.
*   `max_limit` *(Default: 64)*: Maximum number of chunks collected during pre-filtering (can be scaled up to e.g. 700 to process massive directories).

#### **3. Debugging Reranking (`/debug response` & `/trace rerank`)**
*   **`/debug response [raw]`**: Active debug mode for the next prompt. In `/rerank`, it prints a raw JSON dump or list representation of the final resolved result set, bypassing intermediate batch request spam.
*   **`/trace rerank <on|off>`**: Toggle tracing. When `return=text` is used, tracing `on` will still print the formatted ASCII summary table to stdout for debugging, while keeping variables clean.

### **Variable Substitution**
Variables can be set manually, via search results, or in scripts:
```bash
/setvar username "Jon"
chat --> Hello ${username}, show me ${search_results}
```

#### **Special & Protected Variable Case Insensitivity**
All predefined system and protected variables (such as `CHAT_HISTORY`, `LAST_RESPONSE`, `AGENTIC_LOOP`, `TOOL_CONTEXT`, and `LAST_COMPLETION`) are case-insensitive. They can be referenced, subscripted, or dumped using any case variation (e.g. `${chat_history[0]}` or `/dump agentic_loop`). Custom user-defined script variables remain case-sensitive.

#### **Quote and Escape Rules**
* **Surrounding Quotes**: When setting a scalar variable (e.g., `/setvar name "Jon"` or `/setvar name = 'Jon'`), any surrounding single (`'`) or double (`"`) quotes are automatically stripped.
* **Escaping is Forbidden**: The backslash escape character (`\`) is **strictly forbidden** inside variable values. Attempting to use `\` will result in an error. This prevents syntax errors inside the ChatDSL parser (which does not support backslash escapes).
* **Quotes Inside Quotes**: To include quotes within a variable's value, **alternate single and double quotes** instead of escaping:
  ```bash
  # Stores: This is an "inner" quote
  /setvar my_var 'This is an "inner" quote'

  # Stores: This is an 'inner' quote
  /setvar my_var "This is an 'inner' quote"
  ```
* **Leading/Trailing Whitespace**: Unquoted values have leading and trailing whitespace trimmed. To preserve leading spaces in a value, wrap the value in quotes (e.g., `/setvar indented "  text"` stores `  text`).

**Note:** Script variables (`/setvar`) are for **text substitution only**. For image analysis with vision models, use image banks instead. Load images with `/imagebank1 <file>` and reference them with `{imagebank1}` syntax in your prompts. The `{imagebank1}` placeholder sends the image as a proper multimodal attachment, while `${var}` substitution inserts text only.

### **Image Support (Beta)**
chatybot supports **text-to-image generation** and **image-to-text (vision) analysis** for supported models. This feature is currently in **Beta**.

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

### **Shell Execution & Autonomous Tool Calling (New!)**

Chatybot supports local shell execution and fully autonomous agentic tool-calling loops.

#### **1. Shell Execution (`/run`)**
The `/run` command executes shell commands on the host machine and integrates outputs directly with the ChatDSL variable environment.
*   **Command**: `/run <command>`
*   **Variable Integration**: Execution automatically sets the following variables:
    *   `${RUN_COMPLETION}`: Captures the command's stdout.
    *   `${RUN_ERROR}`: Captures the command's stderr.
    *   `${RUN_EXIT_CODE}`: Captures the exit code (e.g. `0` on success).
    *   `${LAST_COMPLETION}`: Captures stdout for backwards compatibility.
*   **Security Modes**:
    *   `/run_safe` (Default): Restricts dangerous or destructive command patterns (like `rm -rf`, `sudo`, etc.) to prevent accidental damage.
    *   `/run_unsafe`: Disables safe mode. Commands execute directly without confirmation prompts (ideal for automated background scripts).
    *   `/run_unsafe askfirst`: Disables safe mode with confirmation. Prompts with `(y/N)` when dangerous command patterns are encountered.

*Examples*:
```dsl
# 1. Basic command execution & output inspection
/run ls -la
/echo Command exit status: ${RUN_EXIT_CODE}
/echo Command output: ${RUN_COMPLETION}

# 2. Capturing current date / timestamp into a custom variable
/run date +%Y%m%d_%H%M%S
set run_id = "${RUN_COMPLETION}"
/echo "Generated run ID: ${run_id}"
```

#### **2. Autonomous Tool Loop (`/tool`)**
You can enable native-like tool usage for LLMs, allowing them to autonomously select and execute local python functions in a multi-turn loop.
*   **`/tool on`**: Enables tool mode and injects all active tool definitions from `tools_config.toml` into the LLM system prompt context.
*   **`/tool off`**: Disables tool mode.
*   **`/tool list`**: Lists all available tools, showing their enabled/disabled status and description.
*   **`/tool enable <tool>|all`**: Dynamically enables a specific tool or all tools for the current session.
*   **`/tool disable <tool>|all`**: Dynamically disables a specific tool or all tools, forcing an immediate prompt context refresh and runtime block in the dispatcher.
*   **`/tool prompt`**: Displays the active tool injection context and system instructions.
*   **`/tool scratch [on|off|clean|status|show]`**: Toggle or manage the dedicated agentic scratchpad directory:
    *   `on`: Enables scratchpad mode and injects dedicated instructions directing the LLM to write, test, and execute disposable Python/Bash scripts within a dedicated temporary folder (`~/.local/share/chatybot/sessions/<session_id>/scratch/` for active sessions, or `~/.local/share/chatybot/scratch/` as a global fallback) without altering project files.
    *   `off`: Disables scratchpad mode and removes scratchpad instructions from the system prompt.
    *   `clean`: Purges all temporary scripts, outputs, and subdirectories from the active scratchpad folder.
    *   `status` (or `show`/`info`): Displays current scratchpad state, directory path, and lists all files currently in the scratchpad.
*   **`/tool loop [turns|max|max=val] [force]`**: Starts the autonomous execution loop. Chatybot will feed the model's requests to local tools, execute them, and feed results back to the model until:
    *   The model returns a conversational natural-language answer (terminal state).
    *   The maximum number of turns is reached (default 25; configurable via `max_turns` in `tools_config.toml`; use `max` or `max=100` to increase). Loop counts greater than 100 require the `force` flag.
*   **`/tool auto [on|off]`**: Enables/disables auto-execution of the tool loop. When enabled, any tool call block detected in the LLM completion response automatically triggers the autonomous execution loop.
*   **`/tool <file.json>` or `/tool <json_string>`**: Manually dispatch a specific tool invocation.

*Example*:
```dsl
/tool on
chat --> find all markdown files
/tool loop 10
# LLM will autonomously execute tools in a loop for up to 10 turns (or until finished).
```

#### **Built-in System Tools**
The following tools are packaged by default and can be enabled/disabled dynamically:

| Tool Name | Description | Key Parameters |
|-----------|-------------|----------------|
| `list_directory` | Lists the contents of a directory, optionally with detailed file metadata (size, mod time, etc.). | `path` (optional), `details` (optional) |
| `read_file` | Reads the full text contents of a file on disk (rejects binary file patterns for safety). | `path` (required) |
| `find_files` | Finds files matching a glob pattern, optionally filtering by containing a literal search term. | `path` (optional), `pattern` (optional), `search_term` (optional), `details` (optional) |
| `write_file` | Writes content to a file, or appends to it if the `append` parameter is `true`. | `path` (required), `content` (required), `append` (optional) |
| `change_dir` | Changes the current working directory for subsequent tool executions. | `path` (required) |
| `grep_search` | Searches for exact pattern matches or regular expressions within files or directories. | `query` (required), `path` (optional), `pattern` (optional), `case_insensitive` (optional), `is_regex` (optional), `max_matches` (optional) |
| `replace_file_content` | Replaces a specific block of text in a file with new content. | `path` (required), `target` (required), `replacement` (required) |
| `run_command` | Executes shell commands on the host machine using safe subprocess tokenization. | `command` (required) |

#### **Supported Tool Calling Formats**
Chatybot's extraction engine automatically recognizes, parses, and normalizes all major LLM tool-calling output syntaxes without requiring provider-specific adapter layers:

| Format Style | Example Syntax | Supported Models |
| :--- | :--- | :--- |
| **1. Single-Key Tool Dictionary** | `{"list_directory": {"path": "src/project", "details": true}}` | Devstral, Mistral, Command-R |
| **2. Standard Tool Object** | `{"tool": "list_directory", "arguments": {"path": "src/project"}}` | Cohere, OpenAI, Anthropic, Custom |
| **3. Named Function Object** | `{"name": "list_directory", "arguments": {"path": "src/project"}}` | OpenAI Function Calling, Qwen |
| **4. Function Call Object** | `{"function": "list_directory", "arguments": {"path": "src/project"}}` | Llama-3-Groq-ToolUse, Hermes |
| **5. Header-Prefixed Tool Call** | `<\|tool_call\|>call:list_directory{"path": "src/project"}<\|tool_call\|>` | Gemma 4, FunctionGemma, Granite |
| **6. XML / Function Tag Syntax** | `<tool_call><function name="list_directory"><parameter name="path">src/project</parameter></function></tool_call>` | Anthropic XML, DeepSeek, Command-R+ |
| **7. Python-style / Single-Quoted Dicts** | `{'tool': 'list_directory', 'arguments': {'path': 'src/project'}}` | Python literal output (auto-repaired via AST / JSON repair) |
| **8. Unquoted Key JSON** | `{tool: list_directory, arguments: {path: "src/project"}}` | Auto-repaired and normalized |

#### **3. Tool Configuration (`tools_config.toml`)**
All agentic tools and execution configurations are managed in `src/chatybot/tools_config.toml` (which is copied to `~/.config/chatybot/tools_config.toml` upon initialization).

*Example Configuration File*:
```toml
[config]
tool_timeout = 60              # Execution timeout in seconds per tool
rate_limit_delay = 2.0         # Rate limit sleep duration (seconds) between LLM calls
max_turns = 25                 # Maximum turn count for auto-loop or default loop
strip_thinking_from_filebanks = true

# Define individual tools
[tools.list_directory]
enabled = true
description = "List contents of a directory"
module = "chatybot.tools.file_utils"
function = "list_directory"

[tools.list_directory.parameters.path]
type = "string"
description = "Directory path to list"
optional = true
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

### **Session Management & Persistence (New!)**
Chatybot supports high-performance conversation session persistence across restarts, workspace inspection, notes annotations, gzip compression, multi-model session merging, and Markdown transcript exports.

#### **Pluggable Session Storage Architecture**
Sessions are persisted by default using a high-performance **JSON Lines (`jsonl`)** directory structure with $O(1)$ turn appends, atomic metadata writes, and in-memory directory caching:
* `~/.local/share/chatybot/sessions/<session_id>/meta.json` — Lightweight session metadata (timestamps, turn count, notes, custom names, model alias).
* `~/.local/share/chatybot/sessions/<session_id>/turns.jsonl` — Append-only interaction exchanges (or `turns.jsonl.gz` when compressed).

A legacy single-file flat JSON store (`monolithic`) is also supported via `session_storage_engine = "monolithic"` in `tools_config.toml` / `chat_config.toml`. A standalone CLI migration tool (`bin/migrate_sessions` or `chatybot-migrate-sessions`) seamlessly upgrades legacy workspaces.

#### **Session Commands**
```bash
/session start project_alpha               # Start and persist new named session
/session list [limit=N] [range=A:B] [all]  # List recent sessions with pagination
/session list [compressed|uncompressed]    # Filter sessions by compression state
/session use project_alpha                 # Load prior session history into memory
/session note "Initial design discussion"  # Add persistent metadata note (up to 1024 chars)
/session show [--thinking|-t]              # Inspect full exchange history and tool logs
/session export transcript.md [-t]         # Export conversation as GitHub-flavored Markdown
/session compress [pattern|days|all]       # Compress inactive sessions (supports wildcards, e.g. 'mistral*')
/session uncompress [pattern|all]          # Decompress sessions (supports wildcards)
/session prune [keep=N] [days=D] [size=M]  # Prune workspace by retention count, age, or size quota
/session info                              # Display aggregate workspace disk metrics and stats
/session delete <name|id|--all>            # Delete a session or purge workspace
/session merge <target> <s1> <s2> [s3...]  # Merge multiple sessions into a combined session
```

#### **Merging Sessions from Different Models**
When merging sessions that were generated with different AI models (for example, merging a `cohere_north` session with a `mistral_large` session via `/session merge comparison_report sess_1 sess_2`):
* **Custom Name (`custom_name`)**: Set to the `<target_name>` provided as the first argument (`"comparison_report"`).
* **Session ID (`session_id`)**: Automatically generated as `merged_<YYYYMMDD_HHMMSS>` with timestamp-collision resolution (e.g., `merged_20260826_220615`).
* **Composite Model Alias (`model_alias`)**: Set in `meta.json` to the unique model aliases concatenated with underscores in order of appearance (e.g., `"cohere_north_mistral_large"`).
* **Turn-Level Attribution**: Each individual turn in `turns.jsonl` preserves its original model provenance (`"model_alias": "cohere_north"`, `"model_alias": "mistral_large"`), ensuring accurate multi-model transcripts when viewing via `/session show` or exporting to Markdown.
* **Consolidated Notes (`notes`)**: Any notes attached to the source sessions are automatically aggregated with source session labels and joined by pipe delimiters (e.g., `"[sess_1] Initial exploration | [sess_2] Followup benchmarks"`).

> [!WARNING]
> **Concurrent Session Access:** If two chatybot instances run under the same user and load the same session via `/session use`, their writes will interleave. Each instance keeps its own in-memory turn list and overwrites the other's turns on save (last-write-wins), producing a divergent or incoherent transcript. A timestamped `.lock` file sentinel warns when a session is already in use by an active process, and automatically expires stale locks older than 24 hours. For separate conversations, use `/session start` to create independent sessions. See `session_concurrency.md` for details.

---

### **Context Window Management & Time-Travel Replay (New!)**

Chatybot includes an advanced context monitoring, auto-truncation, and time-travel replay suite that lets you inspect, limit, and debug the exact message payloads and token budgets sent to language models across multi-turn sessions and agentic tool loops.

#### **1. Live Context Monitoring (`/context`, `/ctx`)**
View real-time token counts, buffer sizes, and context budget utilization:
```bash
/context                      # View active prompt context breakdown and budget bar
/context session              # Inspect token usage by session conversation history
/context loop                 # Inspect token usage by agentic tool loop executions
/context buffers              # Inspect token usage by prompt buffers, file banks, and system message
/context 10000                # Set context limit to 10,000 tokens (supports $variables: /context $my_limit)
/context off                  # Disable context limit
/context ctx_data             # Save full metrics dictionary to a ChatDSL script variable
```

*Example Output*:
```text
Context Usage Breakdown:
  • Session History:  ~8,259 tokens (13 turns, 32.26 KB)
  • Last Tool Loop:   ~3,042 tokens (3 tool calls, 11.88 KB) [archived trace]
  • Buffers / System: ~7 tokens (0.03 KB)
  ──────────────────────────────────────────────
  Total:              ~8,266 / 10,000 tokens [████████████████░░░░] 82.7%
  Remaining:          ~1,734 tokens
  Auto-Truncate:      ON (100%)
```

#### **2. Context Limits & Auto-Truncation Engine (`/auto_truncate`)**
Prevent context window overflows during lengthy discussions or data-heavy tool executions:
* **Setting Limits**: Configure a hard token limit via `/context <tokens>`, `/context_limit <tokens>`, or model configuration (`context_limit = 16000` in `chat_config.toml`).
* **Auto-Truncation**: Enable automated pruning with `/auto_truncate on` or `/auto_truncate <percentage>` (e.g. `/auto_truncate 90` to trim down to 90% of the limit when exceeded).
* **Anchor Protection**: The **System Prompt** (index 0) and the **Initial User Goal / Prompt** (index 1) are permanently anchored and never dropped.
* **Message Eviction**: When context exceeds the target budget, Chatybot evicts older intermediate conversation turns and prior tool call/result pairs from oldest to newest while preserving recent turns.
* **Content Truncation**: If individual messages remain oversized (e.g. reading massive files), content is trimmed with a clear `[... content truncated to fit context limit ...]` indicator.
* **Warning Tiers**:
  * **$70.0\% - 89.9\%$**: `[Warning: Context usage at 75.0% of limit (7,500/10,000 tokens).]`
  * **$90.0\% - 99.9\%$**: `[Warning: Context usage at 95.0% of limit (9,500/10,000 tokens). Approaching context window limit.]`
  * **$\ge 100\%$**: `[Warning: Context usage at 120.0% of limit (12,000/10,000 tokens). Exceeds context limit (auto-truncate is OFF).]`

#### **3. Time-Travel Context Replay (`/replay`, `/tool replay`)**
Reconstruct and inspect the exact prompt array and truncation state sent to the LLM at any point in history.

```bash
/replay                                # Summary timeline of all turns in the active session
/replay <session_id>                   # Summary timeline for a specific persisted session
/replay at 5                           # Reconstructed message array dump at Turn 5 (anchors, kept, evicted)
/replay diff 3 4                       # Compare Turn 3 vs Turn 4 (added messages, newly evicted, token delta)
/replay step                           # Interactive turn-by-turn stepping debugger (Enter=next, show=dump, q=quit)
/replay limit=8000                     # Override context limit on the fly to simulate different token budgets
/tool replay [at N|diff A B|step]      # Replay agentic tool loop step timeline for the last tool execution
```

*Replay Timeline Overview*:
```text
==============================================================================
AGENTIC LOOP REPLAY — SUMMARY (turn 17)
==============================================================================
Step  Tool                Msgs  Uncut Tok   Trunc Tok   Evicted  AnchorWarn 
------------------------------------------------------------------------------
0     (baseline)          34    12429       9721        15       -          
1     list_directory      36    13761       9915        19       -          
2     read_file           38    14775       9910        23       -          
5     read_file           44    23499       2705        42       -          
20    read_file           74    38089       2705        72       -          
==============================================================================
```

*Timeline Column Reference*:
* **`Step / Turn`**: 0-based or 1-based index in the tool loop or session (`0 = (baseline)` pre-loop state).
* **`Tool`**: Name of the tool executed at that step.
* **`Msgs`**: Total message count in the prompt array before truncation.
* **`Uncut Tok`**: Raw token count of all messages if submitted without truncation.
* **`Trunc Tok`**: Final token count submitted to the model after eviction and content truncation.
* **`Evicted`**: Total count of older intermediate messages dropped from the prompt array to satisfy the token budget.
* **`AnchorWarn`**: Flag (`OVERFLOW` / `-`) indicating if protected anchors (system message + initial user goal) alone exceed the token limit.

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
│   ├── macro.chatdsl    # Default macro definitions
│   ├── config_model.py  # Configuration data model with Pydantic v2
│   ├── config_manager.py # Configuration loading and management
│   ├── config_tui.py    # Curses-based TUI for configuration
│   └── vendors.py       # Vendor preset definitions
├── config_model_design.md # Configuration data model design document
├── config_tui_design.md  # TUI design documentation
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
7. **Config Utility**: TUI-based configuration management with vendor presets

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

## **Configuration Utility**

chatybot provides a comprehensive configuration management system with both file-based and interactive TUI options.

### **Config Data Model**
The configuration system uses Pydantic v2 models to validate and manage:
- **Chat Models**: Standard LLM configurations with temperature, top_k, base_url, api_key
- **Reranker Models**: Specialized configurations for re-ranking APIs
- **Image Generation Settings**: Default directory, size, and quality for generated images
- **Vendor Presets**: Pre-defined configurations for popular providers (Mistral, Google, OpenAI, OpenRouter, NVIDIA, PublicAI, Bytez, Ollama, Llama.cpp, Jina)

### **Using the Config TUI**
Launch the interactive configuration manager:
```bash
chatybot --config-edit
```

The TUI provides:
- **Model Browser**: Navigate and filter through configured models
- **Vendor Presets**: Quick setup with predefined vendor configurations
- **Model Editor**: Add, clone, edit, and delete models
- **Save Options**: Save configuration to current or new file locations

### **File-Based Configuration**
Edit `~/.config/chatybot/chat_config.toml` directly or use the `-c` flag to specify an alternate config file:
```bash
chatybot -c ~/my_custom_config.toml
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

September 6th, 2026 (v0.8.3)
---------------------------
- **Time-Travel Context Replay (`/replay`, `/tool replay`)**:
  - Added interactive context replay engines to reconstruct and inspect the exact prompt/history arrays sent to LLMs at any turn (`/replay`) or agentic tool step (`/tool replay`).
  - Supported timeline overview (`summary`), specific turn inspection (`at <N>`), step-by-step interactive navigation (`step`), and turn-to-turn differential diagnostics (`diff <A> <B>`).
  - Added strict newly-evicted message tracking (`newly_evicted`), token delta calculation, and anchor overflow detection.
  - Optimized CLI execution with zero redundant disk reads by passing preloaded session turns into `SessionReplayer` and `AgenticReplayer`.
- **Context Limiting & Token Counting Enhancements**:
  - Optimized message eviction in `ContextLimiter.truncate_messages` from $O(N^2)$ to $O(N)$ via precomputed token caching and running sums during turn dropping.
  - Unified anchor partitioning logic (`ContextLimiter.partition_anchors`) across core truncation and verbose diagnostics.
  - Enforced strict token budget compliance after prepending truncation notices to prevent budget overruns.
  - Extended heuristic token counting to fully account for assistant `tool_calls` (function names + JSON arguments) and tool metadata (`name`, `tool_call_id`).
- **Context Command & Script Variable Resolution**:
  - Enhanced `/context` to support single-argument limit setting (`/context 10000`, `/context off`) and script variable resolution (`/context $my_limit`).
  - Included system prompt and non-empty file bank token breakdown in `/context` metrics output.
- **Cookbook Validation & Parser Hardening**:
  - Validated all 55 ChatDSL cookbook recipe scripts in `doc/cookbook/` with full parser compliance.
  - Integrated localized command alias resolution into `chatdsl_parse`.

September 3rd, 2026 (v0.8.2)
---------------------------
- **Agentic Scratchpad Area (`/tool scratch`)**:
  - Added dedicated temporary scratchpad area for models to create, test, and execute disposable Python/Bash scripts and scratch files without modifying project files.
  - Implemented `/tool scratch [on|off|clean|status|show]` commands with real-time prompt injection, clean purging, and file inventory.
  - Integrated session-scoped scratchpads (`~/.local/share/chatybot/sessions/<session_id>/scratch/`) with global fallback (`~/.local/share/chatybot/scratch/`).
  - Added ChatDSL profile integration (`/tool scratch on|off`) with persistence across session reloads.
  - Hardened path resolution against trailing slashes, relative paths, and wrapped prompt execution paths in quotes for safety with space-containing paths.
  - Added multi-language keywords for `scratch` and `clean` across all supported languages (ES, FR, ZH, IT, AR).
- **Environment & Multi-Platform Key Setup**:
  - Added interactive cross-platform API key setup wizard `chatybot-setup-keys` and CLI flag `chatybot --setup-keys`.
  - Added native setup scripts `bin/setup_keys.sh` (POSIX/macOS/Linux) and `bin/setup_keys.bat` (Windows with `setx` user registry persistence and double-click Explorer support).
  - Added `.env.example` template and updated `.gitignore` for security.
  - Centralized `.env` file loading and API key resolution in `src/chatybot/env_utils.py`, supporting `export ` prefixes, comments, quotes, nearest-project boundaries, and non-destructive global defaults (`~/.config/chatybot/.env`).
  - Hardened API key resolution against false positives for custom lowercase environment variable names.
- **Quick Start Documentation Revamp**:
  - Rewrote the Quick Start guide with a clear 3-step setup walkthrough, supported provider key reference table, and `/env` inspection verification.

September 1st, 2026 (v0.8.0)
---------------------------
- **PyPI Project URLs & Documentation Links**:
  - Pointed PyPI project metadata and README badges directly to the active `master` branch URLs, resolving 404 links.
- **Modular Command Registry Architecture**:
  - Decoupled monolithic command dispatcher in `chatybot_app.py` into dedicated domain modules under `src/chatybot/commands/` (`registry.py`, `context.py`, `tools.py`, `session.py`, `models.py`, `buffer.py`, `db.py`, `image.py`, `proc_macros.py`, `rerank.py`, `debug_misc.py`, `debug.py`).
  - Added structured command execution lifecycle (`CommandResult`, `CommandContext`) with domain routing, aliases, and isolated error handling.
  - Added comprehensive migration test suites (`test_command_registry.py`, `test_command_migration_phase2.py`, `test_command_migration_phase3.py`).
- **Session & Workflow Enhancements**:
  - Added `/chatdsl history` command to export, format, and codify active interactive session history directly into runnable ChatDSL automation scripts.
  - Persisted lightweight command execution verbs directly in `turns.jsonl` for full session replay fidelity and clean multi-turn provenance.
  - Added `/session name <alias>` subcommand and automatic startup command preservation during session creation.
- **Tool Handling & Unicode Output Normalization**:
  - Configured `ensure_ascii=False` for all tool execution payloads, file utilities, and model communication to cleanly render native Unicode characters and file paths.

August 31st, 2026 (v0.7.9)
-------------------------
- **Live Tool Prompt Editing & Restoration**:
  - Added `/tool prompt live_edit` (or `/tool prompt edit_live`) to open an interactive editor (`notepad`, `vi`, `$VISUAL`, `$EDITOR`) and live-customize tool context and agentic system instructions for the active session.
  - Added `/tool prompt restore` to instantly restore live system prompt overrides back to `tools_config.toml` defaults.
  - Added `restore` and `live_edit` keyword translations across all supported languages (EN, ES, FR, ZH, IT, AR) in `translations.json`.
  - Added `/tool max_turns <int>` command and documentation for configuring default maximum turns in automated tool loops (`/tool auto on`).
- **Tool Loop Robustness & Type Sanitization**:
  - Implemented recursive `sanitize_json_types` in `extract_tool_calls` normalizing Python `set`, `frozenset`, and `tuple` instances into JSON-compliant lists.
  - Replaced raw JSON serializers across `execute_tool_loop` with `safe_json_dumps` to prevent serialization crashes during logging, dispatching, and turn tracking.
  - Added unit test suite in `test/test_tool_loop_serialization.py`.
- **Rerank Evaluation Datasets**:
  - Added 30-dish culinary dataset in `10_foods.txt` and updated sparse context / reranking demonstration workflows.
- **Documentation & Localization Updates**:
  - Updated Command Reference, `/help` command metadata, and multi-language documentation guides in `doc/` to **v0.7.9+**.
  - Synchronized package version to **0.7.9** across `pyproject.toml`, `src/chatybot/__init__.py`, and startup banner.

August 28th, 2026 (v0.7.8)
-------------------------
- **`/prompt` Loading & Execution Security**:
  - Strictly unwrapped matched outer quotation pairs (`"..."` or `'...'`) for prompt file paths while rejecting mismatched quotes and preventing inner character mangling.
  - Added interactive confirmation and capped interactive prompt terminal previews to 500 characters with remaining character indicators to avoid terminal scrollback flooding on large files.
  - Added tilde expansion (`~`), explicit file existence checks, UTF-8 decoding, and empty / whitespace-only file rejections.
  - Hardened buffer lifecycle by preventing `prompt_buffer` leaks on read failures or user cancellations and cleaning up duplicate buffer clearing.
  - Documented interactive confirmation vs non-interactive script context auto-execution across ChatDSL guides and logged sentinel review in `open_issues.md`.
- **Pluggable Session Storage Architecture**:
  - Abstracted session persistence into pluggable storage engines (`BaseSessionStore`, `session_factory.py`) with configurable engines (`jsonl` vs `monolithic`).
  - Added high-performance JSONL engine (`meta.json` + `turns.jsonl`) eliminating quadratic write amplification on turn appends.
  - Implemented standalone CLI migration utility `bin/migrate_sessions` (`chatybot-migrate-sessions`) with `--dry-run`, backups, and selective migration.
  - Hardened session persistence with atomic `.tmp` merge operations, same-second collision loops (`_2`, `_3`), re-entrant thread locks (`RLock`), stale `.lock` auto-expiration (24h), and directory `mtime` metadata caching.
  - Added wildcard globbing to `/session compress` and `/session uncompress`, compression status filters (`/session list compressed|uncompressed`), and multi-model composite provenance attribution.
- **ChatDSL Cookbook & Recipe Suite**:
  - Published comprehensive task-oriented `doc/chatdsl_cookbook.md` with 52 standalone runnable recipes in `doc/cookbook/`.
  - Documented `/source` command (Recipe 10.3) for dynamic in-session script execution, companion `macro.chatdsl` auto-loading, and environment state retention.
- **Variable Scoping & Buffer Manager Hardening**:
  - Introduced `user_write()` context manager in `BufferManager` to permanently eliminate mutable `_is_user_write` flag leaks across `foreach`, `/script`, `/proc`, and `/setvar`.
  - Hardened `/setvar` name validation, overwrite protections, and alternate quoting syntax.
  - Unified `${arr}` prompt text rendering across native lists and JSON array strings.
  - Guarded array subscript parsing (`var[idx]`) against invalid JSON fallback substring indexing.
  - Preserved internal whitespace formatting in prompt placeholder substitution.
  - Silenced internal `set_script_var` writes while keeping interactive `/setvar` user feedback.
- **Localization (i18n) & Cross-Platform Fixes**:
  - Expanded key-value argument translation (`k=v`), session keywords (`uncompress`, `compressed`, `days`, `limit`, etc.), and help descriptions across all 6 locales (EN, ES, FR, ZH, IT, AR) in `localization.py` and `translations.json`.
  - Fixed Windows tool dispatcher subprocessing using `sys.executable` fallback.
  - Added Windows path normalization (`normalize_path`) handling double-escaped backslashes across file tools.
  - Synchronized package version to **0.7.8** across `pyproject.toml`, `src/chatybot/__init__.py`, and startup banner.

August 25th, 2026 (v0.7.7)
-------------------------
- **Windows Platform Compatibility**:
  - Added Windows conditional dependencies (`pyreadline3`, `windows-curses`) in `pyproject.toml`.
  - Added platform-conditional readline imports and safe calls in `chatybot_app.py`.
  - Added defensive curses imports and fallback instructions in TUI modules (`config_tui.py`, `profile_tui.py`, `profile_editor.py`).
  - Added Windows Python App Execution Aliases troubleshooting section to `README.md`.
- **Chat History Control & Agentic Guard**:
  - Added `enable_chat_history` toggle to configuration model, manager, and `chat_config.toml`.
  - Added `/session history [on|off]` command to inspect and dynamically toggle in-memory history collection.
  - Enforced policy guard preventing agentic tool loops when chat history collection is disabled.
  - Added test suite in `test/test_chat_history_flag.py`.
- **Tool Config TUI Manager**:
  - Added full curses-based interactive tool manager (`tool_config_tui.py`) for configuring tool timeouts, rate limits, turn limits, and enabling/disabling individual tools.
- **Localization & Version Synchronization**:
  - Added `history` keyword translations across all supported locales (EN, ES, FR, ZH, IT, AR) in `translations.json`.
  - Synchronized package version strings across `pyproject.toml`, `src/chatybot/__init__.py`, and runtime REPL startup banners to **0.7.7**.
  - Synchronized compatibility notices across multi-language documentation guides in `doc/`.

August 24th, 2026 (v0.7.6)
-------------------------
- **Documentation & Table Formatting**:
  - Restored clean Command Reference Markdown table rendering and moved the Concurrent Session Access warning into a dedicated **Session Management & Persistence** section under Advanced Features.
- **Meta Muse Glimmer & Reasoning Strength**:
  - Added reasoning strength support for Meta Muse Glimmer models via `/effort` (`low`, `medium`, `high`, `xhigh`) mapped to `extra_body.chat_template_kwargs.reasoning_strength`.
  - Added `/max_tokens` alias for `/maxtokens` across CLI, scripts, and localization catalogs.
  - Added native reasoning mode (`is_reasoning_model`) and `/effort` forwarding support for GLM 5.2 / GLM models across Mistral AI and custom OpenAI-compatible endpoints.
  - Synchronized package version strings across `pyproject.toml`, `src/chatybot/__init__.py`, and runtime REPL startup banners to **0.7.6**.
  - Synchronized compatibility notices across multi-language documentation guides in `doc/`.

August 23rd, 2026
-------------------------
- **Empty Assistant Payload Guard**:
  - Retained original past response content when stripping thinking tags from thought-only responses, falling back to `[No response content]` to eliminate Cohere API 400 validation errors.
- **Trace ImageDbg Profile Integration**:
  - Added `imagedbg` trace field to `Profile` model, presets, and ChatDSL parser/serializer.
  - Integrated `ImageDbg` trace option into `ProfileEditor` and `ProfileTUI` curses interfaces with layout alignment.
- **Trace & Loop Validation**:
  - Enhanced `/trace` command validation and TPS performance file handling to prevent second-based file collision.
  - Guarded interactive editor subprocesses during non-interactive `/debug payload` script execution.
  - Enhanced procedure redefinition warnings, loop break validation, and 3-part step syntax in `range()`.

August 22nd, 2026
-------------------------
- **Session Engineering & Path Optimization**:
  - Added atomic writes, session locking, initial model alias, turn model tracking, and metadata caching (`/session list`).
  - Streamlined session path resolution and added TOML validation for `session_mode` configuration.
  - Preserved source notes during `/session merge`.

August 21st, 2026
-------------------------
- **Database & Log Enhancements**:
  - Added thinking token awareness and reasoning metadata tracking to `/dblog`.
  - Improved search query rejoining, database name validation, sub-argument parsing, and hex mode formatting (`/logging`).
- **Config TUI Bulk Operations**:
  - Added bulk find-and-replace feature across endpoints and providers in Config TUI (`config_tui.py`).

August 20th, 2026
-------------------------
- **Parameter Controls & Logging**:
  - Added hex mode formatting to `/logging` to escape unprintable characters.
  - Added support for disabling `/top_k`, `/top_p`, `/temp`, and penalties.
  - Harmonized agentic tool loop turn reminders with natural language completion rules.

August 19th, 2026 (v0.7.3)
-------------------------
- **CLI Startup Flag (`--no-tools`)**:
  - Added `--no-tools` command-line option to disable tools on startup and bypass all MCP server initialization via stdio, while keeping internal tools available to enable dynamically during the session.
- **Release Version Synchronization**:
  - Synchronized package version strings across `pyproject.toml`, `src/chatybot/__init__.py`, and runtime REPL startup banners to **0.7.3**.
  - Synchronized compatibility notices and timestamps across all multi-language documentation guides in `doc/`.

August 18th, 2026
-------------------------
- **Shell Execution Mode Enhancements (`/run_unsafe`)**:
  - Configured default `/run_unsafe` to execute dangerous command patterns directly without interactive confirmation prompts for non-interactive scripting.
  - Added `/run_unsafe askfirst` (and `/run unsafe askfirst`) mode to prompt for user confirmation (`[y/N]`) before executing dangerous commands.
- **Environment & Key Inspector (`/env`)**:
  - Added dedicated `/env [filter]` command for inspecting active API keys and environment variables with optional case-insensitive substring filtering.
- **Hugging Face Model Preset**:
  - Integrated native Hugging Face vendor presets and endpoint configuration in `vendors.py`, `chat_config.toml`, and the Config TUI editor for models like DeepSeek-R1, Qwen 2.5, Llama 3.3, and SmolLM2.

August 16th, 2026
-------------------------
- **Configurable Context Limits & Auto-Truncation (`context_limit.py`)**:
  - Introduced `ContextLimiter` engine with token estimation heuristic (~4 bytes/token), warning triggers at 70% and 90% capacity, and turn/content auto-truncation.
  - Added `/context_limit [tokens|off]` command to set, inspect, or disable session token limits, plus model-level `context_limit` in `chat_config.toml`.
  - Added `/auto_truncate [on|off|10-100]` command to toggle or configure truncation thresholds.
  - Dynamically refreshed tool system prompt preambles and instructions whenever context limits change.
  - Reported context limits and remaining token budgets in `get_context_metrics` and tool context.
- **Permanent Capability Error Guard & Auto-Disabling**:
  - Implemented `_is_permanent_capability_error()` in `chatybot_app.py` to detect unrecoverable protocol/capability errors (such as unsupported MCP client elicitation or missing RPC methods).
  - Implemented automatic dispatcher-level tool disabling (`self.tool_overrides[tool] = False`) to prevent infinite LLM retry loops upon permanent errors.
  - Added diagnostic `[TOOL USAGE HINT]` to `calculate` in `math_utils.py` distinguishing scalar math operators from list/array statistical operations.
  - Added `sys_default` profile (`sys_default.chatdsl`) prompting the agent to prefer writing temporary Python/bash scripts in `/tmp` via `run_command` over multiple separate tool turns.
- **Rate Limit Delay Configuration**:
  - Added `/tool rate_limit <seconds>` with runtime caching and per-turn delay calculations in the agentic loop.
- **Session List Filtering & Sorting (`/session list`)**:
  - Sorted session files by most recent modification timestamp (newest first).
  - Added model filtering: `/session list model=<alias>`.
  - Added pagination options: `/session list limit=10`, `/session list range=start:end`, and `/session list all`.
- **Multilingual Support (i18n) & Documentation**:
  - Expanded `translations.json` across all 6 supported locales (EN, ES, FR, IT, ZH, AR) for new v0.7.0+ commands and context budgeting.
  - Updated all language-specific ChatDSL documentation guides in `doc/`.

August 15th, 2026
-------------------------
- **Partial File Reading**:
  - Extended `read_file` in `src/chatybot/tools/file_utils.py` with `start_line` and `end_line` parameters for ranged line filtering.
- **Memory Diagnostic Help Updates**:
  - Updated `/mem` help and inspection with detail and debug options.

August 14th, 2026
-------------------------
- **Context Metrics Tool (`get_context_metrics`)**:
  - Introduced `get_context_metrics` native tool to inspect live session context usage, prompt token counts, and agentic loop payload size.
- **Tool Payload Safety Limits**:
  - Added soft warnings (at 30KB) and hard truncation safeguards (at 50KB) for tool execution outputs to protect against runaway context bloat.
- **Agentic Loop Turn Tracking**:
  - Counted agentic loop turns in total turn count and clarified context summary reporting.

August 13th, 2026
-------------------------
- **Documentation & Milestone Updates**:
  - Updated `README.md` key features, command reference, and change log with recent commit milestones.

August 11th, 2026
-------------------------
- **Startup & Boot Performance Optimizations**:
  - Deferred Parsley macro PEG grammar compilation into lazy accessors, deferring parser overhead until macros are expanded.
  - Lazy-loaded `EasyRerank` and `mcp` SDK imports inside respective command and execution handlers, cutting cold boot time by **~45% to 60%** (~900ms saved).
- **Macro Discovery & Management (`/listmacros`)**:
  - Added `/listmacros [filter]` command rendering a clean formatted table of available macros, parameter signatures, and template summaries with keyword search filtering.
  - Added an interactive macro coding and execution tutorial to `/help macro` and `/help /listmacros`.
- **Package Version Synchronization**:
  - Aligned internal version strings across `__init__.py` and startup banners with PyPI version 0.7.0.

August 7th, 2026
------------------------
- **Multilingual Session Localization**:
  - Localized `/session` subcommands, arguments, notes, and keywords across all supported target languages (Spanish, French, Chinese, Italian, Arabic).

August 3rd - 4th, 2026
------------------------
- **Session Workspace Management Suite**:
  - Added comprehensive workspace commands: `/session info` (workspace size, turn counts, file stats), `/session delete <name|id|all>`, `/session merge <target> <s1> <s2>` (with automatic source notes consolidation), `/session compress [days|all]` (gzip compression), and `/session prune [keep=N] [days=D] [size=M]`.
  - Added session annotation notes (`/session note <text>`) capped at 1024 characters, displayed in session metadata without consuming LLM context tokens.
  - Auto-generated prompt slugs derived from Turn 1 for session auto-naming.
  - Fixed variable permissions by passing `allow_protected=True` when updating `RUN_*` and `LAST_COMPLETION` system variables.

August 2nd, 2026
------------------------
- **Session Persistence Engine (`/session`)**:
  - Introduced conversation session persistence (`/session start`, `/session auto [on|off]`, `/session stop`, `/session save`, `/session list`, `/session use`, `/session show`).
  - Added Markdown transcript exporting (`/session export <file.md> [-t]`) with optional `<thought>` block inclusion.
  - Multi-turn conversation context continuity: automatically injects prior session turns into chat completion payloads.
- **Pattern Search Command (`/str_search`)**:
  - Added `/str_search "<pattern>" <text_var> [flags] [dest_var]` for fast substring pattern matching in text variables with count (`c`), match position indices (`m`), and case-insensitivity (`i`) flags, exporting to protected `${STR_SEARCH}`.
- **Enhanced Conditional Expressions**:
  - Added greater-than (`>`), less-than (`<`), `>=` and `<=` relational operator support for `if ... then` blocks.

July 30th - 31st, 2026
------------------------
- **Procedure Definition Engine (`defproc` / `/proc` / `local`)**:
  - Added reusable procedure blocks with argument passing and execution via `/proc <name> param1="val"`.
  - Implemented stack-frame snapshotting for isolated `local var = value` scoping and recursion depth guards.
- **Multiline Iteration & Generators (`foreach`)**:
  - Added multiline `foreach <var> in <iter>` loop construct supporting arrays, `range(start, end[, step])`, and `lines("file.txt")` generators.
  - Added `break` statement support to exit loops early while maintaining variable scope restoration.
- **Profile TUI Editor**:
  - Built interactive curses-based Profile Manager (`chatybot --profile-edit` / `/profile edit`) with validation, preset creation, and field length protection.

July 26th, 2026 (v0.7.0)
------------------------
- **Model Context Protocol (MCP)**: Native integration for hosts supporting stdio-based MCP servers with robust session/lifecycle management.
- **Multilingual localization (i18n)**: Out-of-the-box support for Spanish, French, Chinese, Italian, and Levantine Arabic. Localizes help systems, REPL banners, goodbye exit lines, and supports cross-locale command alias resolution and script pre-translation.
- **Math Evaluation Engine**: Features the `/calc` escape command and an interactive LLM calculation tool powered by custom precedence and Decimal coercion patches.
- **Command Verb Validation**: Revamped prompt validation to safely identify unquoted/unescaped leading command verbs regardless of the active language, preventing accidental LLM traffic.
- **Documentation**: Localized ChatDSL technical guides in Arabic, Chinese, French, Italian, and Spanish.

July 16th, 2026 (v0.6.4)
------------------------
- **Virtual Memory Monitoring**: Implemented a background daemon thread that logs process memory metrics (`VmSize` and `VmRSS`) at 1-second intervals.
- **Cross-Platform Compatibility**: Added Linux-native `/proc/self/status` support, fallback to `psutil` on other systems, and macOS/Darwin physical footprint tracking (`proc_pid_rusage` via `ctypes` system calls).
- **Interactive Debug Commands**: Introduced the `/debug vmem <start|stop|status>` escape command to control the monitor state, log locations, and query live memory usage.
- **Dedicated Log Files**: Outputs metric captures with millisecond-resolution timestamps to dedicated log files (`chatybot.vmem.<timestamp>.log`).
- **New replace_file_content Tool**: Packaged a new built-in system tool to replace specific target string blocks within files.
- **Help System & Test Integration**: Integrated commands into `/help /debug`, CLI auto-complete, and verified correctness with the `test/test_vmem.py` test suite.

July 12th, 2026 (v0.6.3)
------------------------
- **Automatic Configuration Synchronization**: Implemented `config_sync` utility which automatically merges packaged TOML default configurations into user configuration directories on startup.
- **Deep Merging & Settings Preservation**: Supports recursively merging new model definitions and tools while fully preserving existing user customizations (like customized timeouts or disabled tools).
- **Graceful Error Handling & Idempotency**: Detects and reports syntax/decode errors in configurations without silently overwriting user customizations, and runs at most once per file path per process.
- **Verification Testing**: Created unit tests under `test_config_sync.py` and a functional mockup demo in `scratch/test_config_sync_mock.py` to verify config merge behavior.

July 9th, 2026 (v0.6.2)
-----------------------
- **Dynamic Tool Management**: Implemented `/tool list`, `/tool enable <tool>`, and `/tool disable <tool>` to dynamically control available agentic tools during a session.
- **Strict Context Syncing**: Ensured that LLM prompt context is strictly synchronized and regenerated on any runtime tool state change and loop execution.
- **Environment Enforced Tool Override**: Integrated environment variable verification (`CHATYBOT_TOOL_OVERRIDES`) in subprocess execution to prevent disallowed tools from executing.
- **Tool Execution Safeguards**: Added parallel tool call limits (`max_tool_calls_per_turn` config support) and handled excess tool calls gracefully. Added execution enhancements and payload debugging logging.
- **Agentic Loop Metrics & Logging**: Saved detailed execution logs and metrics to the `AGENTIC_LOOP` script variable, and added step-by-step logging to `execute_tool_loop`.
- **System Tooling Expansion**: Added a built-in `change_dir` tool, default shell command support for `run_command`, and safety checks to reject binary files in `read_file`.
- **ChatDSL Variable Enhancements**: Automatically cleared undefined script variables to empty string instead of retaining syntax placeholders.
- **Comprehensive Integration Testing**: Created `test21_tool_management.chatdsl` to validate all runtime overrides, enable/disable actions, context syncing, and dispatcher enforcement.

July 1st, 2026 (v0.6.1)
-----------------------
- **User-Level Configuration Path**: Copied and loaded `tools_config.toml` from `~/.config/chatybot/` for pip installations to prevent read-only directory issues.
- **Auto-Trigger Agentic Tool Loop**: Implemented the new `/tool auto [on|off]` subcommand to automatically run the agentic tool loop upon detecting tool calls, featuring custom streaming chunk reconstruction support.
- **Semicolon Command Chaining**: Enabled chaining multiple escape commands and prompts on a single line separated by semicolons (`;`) via a new centralized `execute_line` execution helper. Supports CLI `--run` option command lists.
- **Startup Profile Scripting**: Added a `--profile <script>` CLI option and `/source <script>` escape command to execute scripts in the current interactive session without exiting, with a new `default_profile` config setting.
- **JSON Parsing Auto-Repair**: Upgraded the JSON extractor to handle raw newlines inside quote literals, ignore `#` or `//` comment characters within quotes, and automatically repair unbalanced JSON output payloads cut off mid-turn.
- **New Built-in write_file System Tool**: Registered a new system tool `write_file` supporting both write and append operations.
- **Refined Agentic Prompts**: Updated system prompt instructions and `tools_config.toml` defaults to prevent eager tool usage on general knowledge queries.
- **Configurable Turn Limit**: Added a configurable `max_turns` limit parameter (default 25) to `tools_config.toml` under `[config]` for the auto-loop and `/tool loop`.

June 28th, 2026 (v0.6.0)
------------------------
- **Command Help System Expansion**: Updated the global `/help /tool` command definitions to fully document `/tool loop` subcommands including turn limits (`max`, `max=val`) and the `force` override parameters.
- **ChatDSL Integration & Verification**: Validated and verified `/run` and `/tool` commands within `.chatdsl` scripts, adding robust unit tests for script parser compatibility, variable scoping, and conditional evaluations.
- **Advanced Documentation Overhaul**: Detailed local shell execution (`/run`), autonomous tool loops (`/tool`), and `tools_config.toml` structure in the main README.

June 27th, 2026
---------------
- **Empty API Content Response Resolve**: Handled API response validation and mapped native `tool_calls` structures to prevent "empty content" parse issues for models like `devstral-2512`.
- **Parallel Tool execution & Timeout Prevention**: Supported multiple parallel tool call extraction/execution and added configurable trace thinking exclusion parameters to prevent transient timeouts.
- **Rate Limit Delay Configuration**: Introduced rate limit delays configurable via `tools_config.toml` and applied them to the autonomous tool loop.

June 24th, 2026 (v0.5.5)
------------------------
- **Interactive Escape Command Variable Resolution**: Enabled resolving variables and subscripts inside interactive escape commands (e.g. `/filebank1 ${arr1[0]}`).
- **Quotes and Equals Sign Stripping**: Standardized interactive `/setvar` to automatically strip surrounding single/double quotes and leading `=` signs from scalar values, matching DSL script behavior.
- **Improved Quote Documentation**: Documented variable quote alternating rules and why the escape character `\` is forbidden in the README.

June 20th, 2026 (v0.5.4)
------------------------
- **Version Bump**: Updated to v0.5.4 to support native array integration and metadata-aware database search.
- **Native Array & Subscript Syntax**: Implemented dynamic array declaration (e.g. `set arr[] = [...]`) and bracket-based subscripts (e.g. `arr[0]`) in `ScriptVars`.
- **Extended Metadata DB Search**: Refactored `search_db` in `chatydb.py` to recursively match queries in metadata keys/values (dicts, lists) in addition to name/content.
- **Memory Diagnostic CLI**: Enhanced `/mem debug` with clean object representation, dynamic sizing, and variable type auditing.
- **Testing Expansion**: Added dedicated unit test files `test_arrays.py` and `test_chatydb.py`.

June 18th, 2026 (v0.5.3)
------------------------
- **Version Bump**: Updated to v0.5.3 to support stateless multiline boundary behavior.
- **State-Based Multiline Mode**: Replaced legacy `/multiline` toggle-off requirement with a deterministic, auto-exiting `;;` boundary parser.
- **Legacy Bypass Lookahead**: Added parser lookahead inside scripts and deferred check state in the interactive REPL to silently bypass legacy trailing `/multiline` toggles.
- **Deprecated Token Reporting**: Logged warning messages when legacy `/multiline` toggles are bypassed.
- **Double Semicolon Tokenization**: Enhanced character-level parser to treat `;;` as a standalone command token.

June 15th, 2026 (v0.5.2)
------------------------
- **Version Bump**: Updated to v0.5.2 to reflect new configuration management features.
- **Config Utility Views**: Added comprehensive TUI-based configuration management with pycurses.
- **Enhanced /help**: Integrated structured help system with keyword filtering and command deep-dives.

June 14th, 2026 (v0.5.1)
------------------------
- **Config Data Model**: Introduced `config_model.py` with Pydantic v2 models for structured configuration management. Supports chat models, reranker models, and image generation settings with full TOML validation.
- **Config TUI**: Added curses-based terminal UI (`config_tui.py`) for interactive configuration management. Features include:
  - Browse, filter, and select models
  - Add new models with vendor presets (Mistral, Google, OpenAI, OpenRouter, NVIDIA, PublicAI, Bytez, Ollama, Llama.cpp, Jina)
  - Clone existing models as templates
  - Edit model parameters (temperature, top_k, etc.)
  - Delete models
  - Save configuration to file
- **Vendor Presets**: Added `vendors.py` with predefined vendor configurations for quick model setup.
- **Config Save Feature**: Enhanced save functionality in Config TUI to support saving as new files.
- **Pycurses Design**: Initial TUI design implementation with comprehensive documentation in `config_tui_design.md`.

June 5th, 2026
--------------
- **License Format**: Updated LICENSE to SPDX format for better compatibility and standardization.

June 4-5th, 2026 (v0.5.0)
-------------------------
- **Debug Response for Rerank**: Added `/debug response` and `/debug response raw` integration for `/rerank` which outputs raw JSON lists of the final resolved result set, avoiding intermediate batch spam.
- **Cohere Rerank Support**: Configured Cohere's Reranker v3.5 via OpenRouter in `chat_config.toml`.
- **Conrad book testing**: Created and validated `test_conrad_full_c.chatdsl` to test Cohere reranking.

June 3rd, 2026
--------------
- **Batched Top-N pre-filtering**: Integrated EasyRerank's batched Top-N processing for massive directory files to prevent context exhaustion.
- **Limit Scaling**: Enabled execution limits scaling (`max_limit` up to 700) to support processing the entire Gutenberg book *Chance* (~14,000 lines).

June 2nd, 2026
--------------
- **Sparse Context Injection**: Created `test_sparse_injection.chatdsl` showcasing sparse context injection workflow.
- **Filebank Document Source**: Supported `filebank` as a document source type (`filebank<1-5>`) in `/documents`.
- **Parameter Enhancements**: Handled both `item=` and `items=` parameters and standardized split types.

June 1st, 2026
--------------
- **EasyRerank 0.2.0 Integration**: Upgraded routing and document loading. Added support for chunking by lines and paragraphs (`split=line` and `split=paragraph`).

May 17th, 2026 (v0.4.4)
----------------------
- **Smart Thought Saving**: Upgraded the `/save` command to automatically respect the `/thinking` toggle state by default, stripping `<think>` and `<thought>` blocks when `/thinking` is `OFF`.
- **Custom Stripping Modifiers**: Added `nothink` and `withthink` parameters to `/save` to allow force-stripping or force-including thinking blocks on demand.
- **Thought Standardisation**: Wrapped all raw streaming and non-streaming thinking and reasoning chunks in standardized `<think>...</think>` tags in conversation history.
- **Improved UX**: Documented the new `/save` command options in `/help` and added descriptions to the README command list and command tables.

May 16th, 2026 (v0.4.3)
----------------------
- **Enhanced Chat History Export**: Added `{CHAT_HISTORY}` placeholder to `/setvar` for JSON chat history export and added the `all` parameter to the `/save` command.
- **Improved UX**: Added `/exit` as a natural alias for `/quit`.
- **Documentation Overhaul**: Fixed markdown formatting issues in the command table and established a dedicated **Known Issues** section.

May 1st, 2026 (v0.4.2)
----------------------
- **Mistral Thinking Support**: Added support for Mistral's structured reasoning format (list of thinking/text blocks) in both streaming and non-streaming modes.
- **Reasoning Effort**: Introduced the `/effort <low|medium|high|none>` command to control reasoning effort for supported models (Mistral, OpenAI o1/o3).
- **Prompt Execution Fix**: Improved `/prompt` execution logic to avoid duplicate prompts and clear the buffer after execution.

Apr 28th, 2026 (v0.4.1)
--------------
- **Hotfix**: Added missing `image_manager.py` module and declared explicit `aiohttp` requirement in dependencies.

Apr 28th, 2026 (v0.4.0)
--------------
- **Image Support (Beta)**: Officially designated text-to-image generation and vision analysis as Beta features.
- **Test Stability**: Resolved brittle test assertions and isolated test execution environments.
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

  - added /notemode - this will split code from explanation.  but only first block.

   Warning:  should not be used for markdown, readme or other such docs.

```
===========================
Active model: mistral-large-2512 (alias: mistral_1)
chat --> /model nvidia_1
Switched to model: nvidia/nemotron-nano-12b-v2-vl:free (alias: nvidia_1)
chat --> create a C program that demonstrates a linked list
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

## **Known Issues**

- **`nanbeige_code` Generation**: When using `/thoughtstyle nanbeige_code`, the model may only generate thinking tokens without producing the final output. This is a known artifact/quirk of the `nanbeige` model itself.

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
