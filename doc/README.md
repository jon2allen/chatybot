
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
- [Pluggable Security Architecture](#pluggable-security-architecture)
- [Examples](#examples)
- [Change Log](#change-log)
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
- **Enhanced Session Filtering & Sorting** - `/session list` sorting by latest activity, model filtering (`model=...`), age filtering (`since=Nd/h/m`), and range pagination (`limit=...`, `range=start:end`)
- **Non-Destructive Session Query & Turn Extraction** - Search past session turns, conversation history, notes, and scratchpads with boolean AND/OR matching, date constraints (`since=`, `until=`, `range=`), fast discovery (`ids`), and entire session byte size tracking (`/session query`, `session_search`). Extract turn prompts, responses, or reasoning traces read-only without switching sessions or polluting context (`/session get`, `session_get`).
- **Pluggable Security Architecture & Policy Guardrails** - Pre-execution security interception for all agentic tool calls and shell operations via built-in Python Security DSL or high-performance external engines (e.g. `racf-guard`). Standardized resource classification (`EXEC`, `FS_READ`, `FS_WRITE`, `NET`, `PROCESS`, `CONTENT`), tri-state verdicts (`ALLOW`, `ASK`, `DENY`), unattended script auto-approval (`-y` / `--auto-approve`), verbose debug tracing (`--security`), and full multilingual localization.

---

## **Installation**

### **Prerequisites**
- Python 3.11+
- `pip` package manager
- `parsley` library
- API keys for your preferred LLMs (OpenAI, Anthropic, etc.)
- Terminal emulator with at least **80 columns** (minimum `80x24`; **100–120 columns** recommended for optimal REPL and TUI operation)

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
| **Apple Foundation Model** | *(None required)* | On-device (`apple_fm`) | [Apple Foundation Models](https://developer.apple.com/documentation/foundationmodels) |

> [!NOTE]
> **Apple Foundation Model (Beta):** Chatybot supports Apple's on-device
> Foundation Model on macOS 26+ with Apple Intelligence enabled. The model
> runs locally with no API key and no network. The context window is
> limited to 4096 tokens, which constrains conversation length, tool
> usage, and file operations. Install with `pip install apple-fm-sdk`
> (or `pip install 'chatybot[apple_fm]'` in zsh). See the full
> [Apple FM Support Guide](chatybot_apple_fm_support.md) for details,
> caveats, and recommended practices.

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

#### **CLI Launch Options & Security Flags**
```bash
# Standard interactive startup with active security policy
chatybot

# Enable verbose security evaluation debug output (rule matching, timings, verdicts)
chatybot --security

# Run non-interactive batch script with automatic approval for ASK verdicts
chatybot -y --script doc/cookbook/16_2_script_with_auto_approve.chatdsl

# Temporarily disable all security checks (unconstrained execution for testing/benchmarks)
chatybot --no-security

# Launch without loading MCP tools or external stdio servers
chatybot --no-tools
```

> [!TIP]
> **Optimal Terminal Size for REPL Operation**:
> * **Standard Baseline:** A terminal window of at least **80 columns by 24 rows (`80x24`)** is required for standard operation. Command separators, status banners, session workspace metrics (`/session info`), conversation turn histories (`/session show`), picklists (`/chatdsl history`), tool loop summaries (`/tool history`), and context differential replay (`/replay`) are all standardized to 80-column output.
> * **Recommended Power-User Size:** A window width of **100 to 120 columns** (e.g. `100x30` or `120x35`) provides the best interactive experience. It leaves ample breathing room for complex multi-turn dialogs, side-by-side terminal splits, long filepaths, and curses-based configuration TUIs (`--profile-edit` / `/profile edit` and `config_tui`) without horizontal line wrapping.


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
| `/save <file> [all] [withthink|raw|nothink]` | Save last response or all history (omits thinking by default; withthink/raw includes) | `/save output.txt` |
| `/script <path>` | Execute a script | `/script setup.dsl` |
| `/source <path>` | Execute a script dynamically in the current session | `/source ~/.chatybot_profile` |
| `/profile [subcommand]` | Manage session profiles dynamically (list, use, clone, delete, export, import, show, edit) | `/profile use coding` |
| `/run <command>` | Execute a shell command and capture stdout/stderr/exit code | `/run ls -la` |
| `/run_safe` | Enable safe mode for shell execution (blocks dangerous commands) | `/run_safe` |
| `/run_unsafe [askfirst]` | Disable safe mode (runs directly; optional `askfirst` prompts Y/N) | `/run_unsafe` |
| `/tool <subcommand>` | Manage native tool loop mode, scratchpad directory, inspect prompt context, or dispatch invocations | `/tool scratch on` |
| `/skill <subcommand>` | Manage the skills database and session-level auto-triggering | `/skill off` |
| `/setdb <name>` | Select TinyDB database. Use `Null` to deactivate. | `/setdb knowledge` |
| `/dblist` | List all TinyDB databases | `/dblist` |
| `/searchdb <q>` | Search current database | `/searchdb "python"` |
| `/dblog` | Log last response (with prompt/model) to DB | `/dblog` |
| `/dbprint [file]` | Print formatted DB report | `/dbprint report.txt` |
| `/loadvar <v> [p]` | Store search, ALL, ID, or range in variable | `/loadvar results 1-5` |
| `/savevar <v> <f>`| Save variable to file | `/savevar results log.txt` |
| `/setvar <v> <val> [flags]`| Set a string variable (strips thinking tags by default; `withthink` preserves) | `/setvar var1 ${LAST_COMPLETION} withthink` |
| `/decide "<st>" <type> "<ins>"`| Evaluate content with TypeSafe Jev structured decision models (`choice`, `score`, `noul`) | `/decide "$text" choice "Classify" options="A:First,B:Second" var=cat` |
| `/documents <src>=<id>`| Set the active rerank source: `db=<name>`, `var=<name>` (or `CHAT_HISTORY`/`file`), `filebank=<1-5>`, or `dir="<path>"` | `/documents dir="test/conrad_test"` |
| `/rerank "<query>"` | Semantically rerank source sentences/chunks with optional parameters | `/rerank "sea voyage" top_n=3 split=paragraph` |
| `/trace rerank <state>`| Enable/disable debugging output for the reranking processor | `/trace rerank on` |
| `/imagebank{1-5} <file>` | Load image into bank for vision analysis | `/imagebank1 cat.jpg` |
| `/imagebank{1-5} clear` | Clear an image bank | `/imagebank1 clear` |
| `/session [subcommand]` | Manage multi-turn session persistence, note annotations, exports, merging, compression, and pruning | `/session start my_project` (or `/session new`) |
| `/session query [terms] [options]` | Search turns, notes, and scratchpads with boolean logic, date filters, and whole session byte sizes | `/session query "error" since=7d ids` |
| `/session get <sid|active> [turn=N] [part]` | Extract turn prompts, responses, or thoughts read-only without switching sessions | `/session get sess_1 turn=1 both var=turn_data` |
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

### **Skills System**
Skills are reusable, trigger-activated instructions stored in a dedicated TinyDB database (`~/.local/share/chatybot/skills.json`). When a user prompt matches a skill's trigger phrases, the skill content is injected into the system prompt for that turn. Skills can optionally configure the agentic tool loop (enable/disable specific tools, set auto-loop and max_turns).

```bash
/skill list                 # List all skills
/skill show code-review     # Show full skill details
/skill create               # Interactive creation wizard
/skill enable code-review   # Re-enable a disabled skill
/skill disable code-review  # Disable a skill (stays in DB, not triggered)
/skill apply code-review    # Manually inject a skill into the next prompt
/skill search "debug"       # Search by name, content, description, tags
/skill learn my-workflow     # Learn a skill from current session turns
/skill export code-review skill.md  # Export to SKILL.md format
/skill import skill.md      # Import from SKILL.md file
/skill restore              # Restore previous tool configuration
```

**Session-level auto-trigger toggle:**

```bash
/skill off                  # Disable auto-triggering for this session
/skill on                   # Re-enable auto-triggering for this session
```

`/skill off` is a session-scoped toggle — it does not modify individual skill records in the database. When auto-triggering is off, no skills are injected based on trigger phrase matching. Manual injection via `/skill apply` still works regardless of the toggle state. The toggle resets to `on` on the next session.

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

#### **Reasoning & Thinking Tag Stripping in Variables**
* **Default Behavior**: Setting variables via `/setvar <name> <value>` or array append `/setvar arr[] <value>` automatically strips reasoning tags (`<think>`, `<thought>`, and `<thinking>`), matching `/save` and `/dblog`.
* **Explicit Flags**:
  * `withthink` (or `raw`): Preserves thinking tags and reasoning blocks verbatim inside the stored variable.
  * `nothink` (or `clean`): Explicitly strips reasoning tags.
```bash
# Clean content without thinking traces
/setvar clean_ans ${LAST_COMPLETION}

# Preserve thinking tags explicitly
/setvar raw_ans ${LAST_COMPLETION} withthink
```

### **Structured Decisions (`/decide`) (New!)**
Chatybot integrates with **TypeSafe Jev** and OpenRouter structured decision models (`type = "decision"` in `chat_config.toml`), allowing scripts to run deterministic evaluations, classifications, and calibrations without unpredictable free-form text formatting.

#### **Question Types**
1. **`choice`**: Selects a discrete option from candidate descriptions.
   ```bash
   /decide "$ticket" choice "Which team should handle this ticket?" options="billing:Invoicing,technical:Bugs,sales:Pricing" threshold=0.70 var=team
   ```
2. **`score`**: Evaluates content along an ordinal spectrum via `scale="min:max"` or custom `levels=`.
   ```bash
   /decide "$bug_report" score "How severe is this bug?" scale="1:5" var=severity
   ```
3. **`noul`**: Fast calibrated binary evaluation returning boolean `true`/`false`.
   ```bash
   /decide "$message" noul "Is this customer query urgent?" var=is_urgent
   ```

#### **Calibration Unpacking & Confidence Gating**
* **`threshold=<float>`**: If calibrated confidence falls below the specified floor, the primary variable resolves to `"FALLBACK"`, enabling safe, deterministic error-handling in ChatDSL scripts (`if "${team}" == "FALLBACK" then ...`).
* **Registers**:
  * `${DECIDE}`: Decision result (or `"FALLBACK"`).
  * `${DECIDE_CONF}`: Calibrated confidence score ($0.00 - 1.00$).
  * `${DECIDE_PROB}`: Winning option probability.
  * `${DECIDE_FULL}`: Complete raw API response payload.
  * When `var=<name>` is used, also populates `<name>_choice`, `<name>_conf`, `<name>_prob`, and `<name>_prob_<option>`.
* **Session Persistence**: Decision prompts, state inputs, confidence levels, and outputs are automatically recorded as structured turns in active sessions (`/session show`, `/session export`).

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
*   **`/tool list [detail] [pattern] [var=<name>]`**: Lists all available tools, showing their enabled/disabled status and description. Automatically populates protected variable `${TOOL_LIST}` and optional target variable with structured tool metadata.
*   **`/tool enable <tool>|all`**: Dynamically enables a specific tool or all tools for the current session.
*   **`/tool disable <tool>|all`**: Dynamically disables a specific tool or all tools, forcing an immediate prompt context refresh and runtime block in the dispatcher.
*   **`/tool prompt [live_edit|edit_live|restore]`**: Displays the active tool injection context and system instructions, opens an external editor for live adjustments, or restores defaults.
*   **`/tool scratch [on|off|clean|status|show]`**: Toggle or manage the dedicated agentic scratchpad directory:
    *   `on`: Enables scratchpad mode and injects dedicated instructions directing the LLM to write, test, and execute disposable Python/Bash scripts within a dedicated temporary folder (`~/.local/share/chatybot/sessions/<session_id>/scratch/` for active sessions, or `~/.local/share/chatybot/scratch/` as a global fallback) without altering project files.
    *   `off`: Disables scratchpad mode and removes scratchpad instructions from the system prompt.
    *   `clean`: Purges all temporary scripts, outputs, and subdirectories from the active scratchpad folder.
    *   `status` (or `show`/`info`): Displays current scratchpad state, directory path, and lists all files currently in the scratchpad.
*   **`/tool append_mode [off|full|summary]`**: Configure how autonomous tool loop execution results are recorded into conversation history:
    *   `summary` (default): Appends a compact, redacted execution summary of tool calls and statuses (e.g. `write_file(path="out.dsl", content="<1347 chars>") -> Success`) to the final response. Keeps token overhead minimal while reinforcing successful tool signatures and outcomes for future turns.
    *   `full`: Appends every intermediate turn and tool result from the loop into chat history for models requiring explicit step-by-step history.
    *   `off`: Preserves only the final natural-language response.
*   **`/tool loop [turns|max|max=val] [force]`**: Starts the autonomous execution loop. Chatybot will feed the model's requests to local tools, execute them, and feed results back to the model until:
    *   The model returns a conversational natural-language answer (terminal state).
    *   The maximum number of turns is reached (default 25; configurable via `max_turns` in `tools_config.toml`; use `max` or `max=100` to increase). Loop counts greater than 100 require the `force` flag.
*   **`/tool auto [on|off]`**: Enables/disables auto-execution of the tool loop. When enabled, any tool call block detected in the LLM completion response automatically triggers the autonomous execution loop.
*   **`/tool history [<turn_id>|current] [csv [file.csv]] [var=<name>]`**: List all agentic tool loops recorded in the active session, or show detailed tool calls for a specific turn. Automatically populates protected variable `${TOOL_HISTORY}` and optional target variable.
*   **`/tool replay [<turn_id>] [at <N>|diff <A> <B>|step] [limit=<N>] [var=<name>]`**: Time-travel agentic loop replay. Automatically populates protected variable `${TOOL_REPLAY}` and optional target variable.
*   **`/tool <file.json>` or `/tool <json_string>`**: Manually dispatch a specific tool invocation.

*Example*:
```dsl
/tool on
/tool list var=my_tools
chat --> find all markdown files
/tool loop 10
/tool history current var=last_loop
# LLM will autonomously execute tools in a loop for up to 10 turns (or until finished).
```

#### **Built-in System Tools**
The following tools are packaged by default and can be enabled/disabled dynamically:

| Tool Name | Description | Key Parameters |
|-----------|-------------|----------------|
| `list_directory` | Lists the contents of a directory, optionally with detailed file metadata (size, mod time, etc.). | `path` (optional), `details` (optional) |
| `read_file` | Reads contents of a file on disk with optional line range filtering (retains absolute line numbers). | `path` (required), `start_line` (optional), `end_line` (optional) |
| `find_files` | Finds files matching a glob pattern, optionally filtering by containing a literal search term. | `path` (optional), `pattern` (optional), `search_term` (optional), `details` (optional) |
| `write_file` | Writes content to a file, or appends to it if the `append` parameter is `true`. | `path` (required), `content` (required), `append` (optional) |
| `change_dir` | Changes the current working directory for subsequent tool executions. | `path` (required) |
| `grep_search` | Searches for exact pattern matches or regular expressions within files or directories. | `query` (required), `path` (optional), `pattern` (optional), `case_insensitive` (optional), `is_regex` (optional), `max_matches` (optional) |
| `replace_file_content` | Replaces a specific block of text in a file with new content, with indentation diagnosis and optional line bounds. | `path` (required), `target` (required), `replacement` (required), `start_line` (optional), `end_line` (optional) |
| `run_command` | Executes shell commands on the host machine using safe subprocess tokenization. | `command` (required) |
| `calculate` | Safely evaluates a mathematical or natural language math expression using mathparse. Optionally saves the result into a script variable. | `expression` (required), `target_variable` (optional) |
| `str_search` | Searches for a substring pattern in text with optional case-insensitive matching. Returns match count or positions. | `pattern` (required), `text` (required), `mode` (optional), `case_sensitive` (optional), `target_variable` (optional) |
| `get_context_metrics` | Returns the current size of context in characters, KB, and estimated tokens for session history, agentic loop, or buffers. | `scope` (optional), `target_variable` (optional) |
| `session_search` | Searches across active and saved session turns, notes, and scratchpads with boolean logic and date filtering. | `query` (required), `operator` (optional), `since` (optional), `until` (optional), `range` (optional), `include_scratch` (optional), `limit` (optional), `ids_only` (optional), `full` (optional), `target_variable` (optional) |
| `session_get` | Extracts read-only prompt, response, thinking, or full exchange text from a past or active session without switching sessions. | `session_id` (required), `turn_id` (optional), `part` (optional), `target_variable` (optional) |
| `ask_user` | Prompts the user interactively for input (choice, yesno, or text). | `prompt` (required), `choices` (optional), `question_type` (optional), `target_variable` (optional) |
| `search_skills` | Searches available skills by keyword (name, description, tags) and returns compact metadata summaries without instruction content. | `query` (optional), `limit` (optional) |
| `call_skill` | Loads a skill's full instructions by name on demand with name normalization, silent tool configuration, and recursion cycle protection. | `name` (required) |

**Optional Tools** (disabled by default, enable with `/tool enable <name>`):

| Tool Name | Description | Key Parameters |
|-----------|-------------|----------------|
| `db_search` | Searches a TinyDB database for items matching a query across name, content, and metadata (lists all if query omitted). Pass `full_content=true` to retrieve full texts in one step. | `query` (optional), `db_name` (optional), `limit` (optional), `full_content` (optional) |
| `db_get` | Retrieves a single complete item from a TinyDB database by its integer ID. Uses active DB if `db_name` omitted. | `item_id` (required), `db_name` (optional) |
| `db_list` | Lists all available TinyDB databases with entry counts and file sizes. | none |
| `db_summary` | Concise summary table or JSON list of database items (ID, timestamp, prompt snippet, thinking tokens) without heavy content payloads. | `db_name` (optional), `item_range` (optional), `format` (optional), `limit` (optional) |
| `decide_score` | Evaluates target content against a numeric scale (e.g. '1:10') or qualitative rubric levels using the default TypeSafe Jev decision model. Returns winning score, calibrated confidence (0.00-1.00), and probability distributions. | `state` (required), `instructions` (required), `scale` (optional), `levels` (optional), `threshold` (optional), `target_variable` (optional) |
| `decide_choice` | Evaluates target content against discrete choices/options with calibrated confidence using the default decision model. | `state` (required), `instructions` (required), `options` (required), `threshold` (optional), `target_variable` (optional) |
| `decide_noul` | Evaluates a binary proposition or verification condition (true/false) with calibrated confidence and probability using the default decision model. | `state` (required), `instructions` (required), `threshold` (optional), `target_variable` (optional) |

#### **Supported Tool Calling Formats**
Chatybot's extraction engine automatically recognizes, parses, and normalizes all major LLM tool-calling output syntaxes without requiring provider-specific adapter layers:

| Format Style | Example Syntax | Supported Models |
| :--- | :--- | :--- |
| **1. Single-Key Tool Dictionary** | `{"list_directory": {"path": "src/project", "details": true}}` | Devstral, Mistral, Command-R |
| **2. Standard Tool Object** | `{"tool": "list_directory", "arguments": {"path": "src/project"}}` | Cohere, OpenAI, Anthropic, Custom |
| **3. Named Function Object** | `{"name": "list_directory", "arguments": {"path": "src/project"}}` | OpenAI Function Calling, Qwen |
| **4. Function Call Object** | `{"function": "list_directory", "arguments": {"path": "src/project"}}` | Llama-3-Groq-ToolUse, Hermes |
| **5. Header-Prefixed Tool Call** | `<\|tool_call\|>call:list_directory{"path": "src/project"}<\|tool_call\|>` | Gemma 4, FunctionGemma, Granite |
| **6. XML / Function, Invoke & Tool-Use Syntax** | `<tool_use><tool_name>find_files</tool_name><arguments>{"path": "dir"}</arguments></tool_use>` or `<invoke name="run_command"><parameter name="command">git status</parameter></invoke>` | Anthropic XML, MCP, Google AI Studio / Gemini, DeepSeek, Command-R+ |
| **7. Python-style / Single-Quoted Dicts** | `{'tool': 'list_directory', 'arguments': {'path': 'src/project'}}` | Python literal output (auto-repaired via AST / JSON repair) |
| **8. Unquoted Key JSON** | `{tool: list_directory, arguments: {path: "src/project"}}` | Auto-repaired and normalized |
| **9. YAML / Key-Value Blocks** | `tool: read_file\npath: src/project/file.py` | LangChain ReAct, HuggingFace, Google AI Studio / Gemini |
| **10. Unescaped Inner Quotes JSON** | `{"tool": "run_command", "arguments": {"command": "echo "hello""}}` | Auto-repaired by inner quote delimiter detection |
| **11. Special-Token Native Instruction Syntax** | `<\|tool_calls_section_begin\|><\|tool_call_begin\|>functions.run_command:0<\|tool_call_argument_begin\|>{"command": "which fpc"}<\|tool_call_end\|><\|tool_calls_section_end\|>` | Moonshot AI / Kimi K2 (`Kimi_k2_0711`), Kimi-Chat |
| **12. DeepSeek Markup Language (DSML)** | `<｜｜DSML｜｜ calls><｜｜DSML｜｜ invoke name="run_command"><｜｜DSML｜｜ parameter name="arguments" string="false">{"command": "pwd"}</｜｜DSML｜｜ parameter></｜｜DSML｜｜ invoke></｜｜DSML｜｜ calls>` | DeepSeek-V3, DeepSeek-R1, DeepSeek-Coder-V2 (Hugging Face / vLLM / raw) |

#### **3. Tool Configuration (`tools_config.toml`)**
All agentic tools and execution configurations are managed in `src/chatybot/tools_config.toml` (which is copied to `~/.config/chatybot/tools_config.toml` upon initialization).

*Example Configuration File*:
```toml
[config]
tool_timeout = 60              # Execution timeout in seconds per tool
rate_limit_delay = 2.0         # Rate limit sleep duration (seconds) between LLM calls
max_turns = 25                 # Maximum turn count for auto-loop or default loop
strip_thinking_from_filebanks = true
backup_file_on_write = true    # Automatically preserve pre-edit backups in session backups/ before modifying files

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

##### **File Mutation Safety & Automatic Backups**
Whenever agent tools (`write_file` or `replace_file_content`) overwrite or modify an existing file on disk, Chatybot automatically creates a pre-edit copy inside the active session backup directory:
```text
~/.local/share/chatybot/sessions/<session_id>/backups/<relative_path>
```
* **Default Enabled**: Enabled by default (`backup_file_on_write = true`).
* **Zero Repository Pollution**: No `.bak` files are placed inside your git working directory or source tree.
* **Manual Override**: To disable automatic file backups, hand-edit `~/.config/chatybot/tools_config.toml` (or `src/chatybot/tools_config.toml`) and set:
  ```toml
  [config]
  backup_file_on_write = false
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
/session start project_alpha               # Start and persist new named session (alias: /session new; sets ${SESSION_NAME})
/session list [limit=N] [range=A:B] [all]  # List sessions; always sets ${SESSION_LIST} (dicts) and ${SESSION_IDS} (sid strings)
/session list ids                          # Compact sid-only output; ${SESSION_IDS} still set; var= gets sid list
/session list model=test_model var=my_var  # Filter by model alias and save session objects to custom variable
/session list ids var=old_ids             # Save filtered sid list to custom variable
/session list [compressed|uncompressed]    # Filter sessions by compression state
/session list since=7d                     # Filter to sessions updated in the last 7 days
/session list since=24h model=devstral     # Compound AND filter: last 24 hours AND model match
/session list since=30m limit=5            # Last 30 minutes, at most 5 results
/session use project_alpha                 # Load prior session history into memory (sets ${SESSION_NAME})
/session note "Initial design discussion"  # Add persistent metadata note (up to 1024 chars)
/session show [--thinking|-t]              # Inspect full exchange history and tool logs
/session export transcript.md [-t]         # Export conversation as GitHub-flavored Markdown
/session compress [pattern|days|all]       # Compress inactive sessions (supports wildcards, e.g. 'mistral*')
/session uncompress [pattern|all]          # Decompress sessions (supports wildcards)
/session prune [keep=N] [days=D] [size=M]  # Prune workspace by retention count, age, or size quota
/session info                              # Display aggregate workspace disk metrics and stats
/session delete <name|id|--all>            # Delete a session or purge workspace
/session merge <target> <s1> <s2> [s3...]  # Merge multiple sessions into a combined session
/session query "keyword" [since=7d] [ids]  # Search turns, notes, and scratchpad with date & size metrics
/session query since=24h ids               # Filter-only discovery of all recent sessions with sizes
/session get <sid|active> [turn=N] [part]  # Read-only extraction without switching active sessions
```

> [!NOTE]
> **`since=` filter syntax**: Use `d` (days), `h` (hours), or `m` (minutes) as the unit suffix.
> All filters compound as **AND** — e.g. `since=7d model=gemini compressed` returns only sessions
> matching all three criteria. The output header shows the active filter set for confirmation.
>
> **Protected variables set by `/session list`**:
> - `${SESSION_LIST}` — always set; list of session summary dicts (`sid`, `cname`, `slug`, `turns_cnt`, `upd`, `snote`, `compressed`, `model_alias`).
> - `${SESSION_IDS}` — always set; flat `list[str]` of session IDs in the same order as `SESSION_LIST`. Ready for `foreach` without any further extraction.
>
> When `var=<name>` is used with `ids`, the named variable receives the **sid list** (same as `${SESSION_IDS}`).
> Without `ids`, `var=` receives the **full dict list** (same as `${SESSION_LIST}`).

**Scripting example — delete all old devstral sessions:**
```dsl
/session list since=30d model=devstral ids all
foreach sid in ${SESSION_IDS}
    /session delete ${sid}
endfor
```

#### **Non-Destructive Session Query & Extraction (`/session query`, `/session get`)**

Chatybot provides high-speed, non-destructive search and extraction across conversation histories, turn exchanges, metadata notes, and scratchpads without switching sessions or polluting the model's active context window.

##### **1. Querying Sessions (`/session query`)**
Search across active and persisted sessions using the pluggable `GrepQueryEngine`:
```bash
# Basic keyword search (displays matching turns with 80-char snippets and whole session size)
/session query "database migration"

# Boolean OR search
/session query database migration or

# Restrict search to messages updated in the last 7 days
/session query "auth error" since=7d

# Search within an explicit date range
/session query "token expired" range="2026-03-01 to 2026-05-01"

# Fast discovery mode: return matching session IDs and full session storage sizes
/session query "binary search" ids var=MATCH_IDS

# Filter-only discovery: list all sessions updated in the last 24 hours with their sizes
/session query since=24h ids

# Full-content mode: view complete turn prompt and response without snippet truncation
/session query "architecture decision" full
```

* **Storage Footprint Display**: Every match and discovered session reports its **entire session storage size** on disk (e.g. `8.2 KB` or `45.1 KB`), cached via a 3-tier lazy evaluation architecture to eliminate redundant disk I/O.
* **Automatic Script Variables**:
  * `${SESSION_QUERY}`: Always populated with the query result dictionary (`total_matches`, `matches`, `session_ids`, `sessions`).
  * `var=<name>`: When `ids` is specified, saves the flat list of session IDs to `<name>`; otherwise, saves the full query dictionary.
  * In `ids` mode, `${SESSION_IDS}` is also automatically updated, allowing immediate pipelining into `foreach`.

##### **2. Non-Destructive Turn Extraction (`/session get`)**
Extract turns from any past session on disk or the active session without loading it into active memory (`/session use`), keeping your current conversation pristine:
```bash
# Extract both prompt and response for turn 1 of a past session
/session get sess_20260908_083123 turn=1 both var=FIRST_TURN

# Extract only the assistant response
/session get sess_20260908_083123 turn=2 response var=BOT_REPLY

# Extract model thinking/reasoning trace
/session get sess_20260908_083123 turn=1 thinking

# Extract all turns from the active session into a structured array
/session get active turn=all both var=ALL_TURNS
```

* **Protected Variable**: Populates `${SESSION_GET}` with the extracted dictionary (`session_id`, `turn_id`, `prompt`, `response`, `thinking`, `model_alias`, `size_bytes`).
* **Field Access**: When saved into a variable via `var=MY_VAR`, access fields directly in ChatDSL: `${MY_VAR}.prompt`, `${MY_VAR}.response`, or array indices `${MY_VAR}[0].prompt` when `turn=all`.

##### **3. Agentic Tool Calling (`session_search`, `session_get`)**
Both capabilities are exposed as native tools for LLM tool calling in agentic loops:
* `session_search(query="", since="7d", ids_only=True)`: Enables the AI model to discover relevant past interactions, notes, or scratchpads, returning matching sessions with their whole-session byte sizes.
* `session_get(session_id="...", turn=1, part="both")`: Enables the model to selectively pull prior context into its working memory on demand without bloating its context window.


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
Reconstruct and inspect the exact prompt array and truncation state sent to the LLM at any point in history. Both commands automatically populate protected script variables (`${REPLAY}` and `${TOOL_REPLAY}`) and support custom target variables via `var=<name>` or `target=<name>`.

```bash
/replay                                # Summary timeline of all turns in the active session (sets ${REPLAY})
/replay <session_id>                   # Summary timeline for a specific persisted session
/replay at 5 var=turn_5                # Reconstructed message array dump at Turn 5 (anchors, kept, evicted)
/replay diff 3 4                       # Compare Turn 3 vs Turn 4 (added messages, newly evicted, token delta)
/replay step                           # Interactive turn-by-turn stepping debugger (Enter=next, show=dump, q=quit)
/replay limit=8000                     # Override context limit on the fly to simulate different token budgets
/tool replay [at N|diff A B|step]      # Replay agentic tool loop step timeline for the last tool execution (sets ${TOOL_REPLAY})
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
==============================================================================
Notes / Column Legend:
  • Step:       Agentic loop step index (0 = pre-loop baseline state)
  • Tool:       Tool invoked at this step
  • Msgs:       Total messages in prompt array before truncation
  • Uncut Tok:  Raw token count of prompt array before truncation
  • Trunc Tok:  Token count after auto-truncation/eviction to fit limit
  • Evicted:    Number of older intermediate messages dropped from prompt
  • AnchorWarn: YES if system + initial user anchors exceed context limit
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

## **Pluggable Security Architecture**

Chatybot features a policy-driven security gateway that evaluates all agentic tool calls and shell operations before execution. Tool invocations are mapped to standard resource classes (`EXEC`, `FS_READ`, `FS_WRITE`, `NET`, `PROCESS`, `CONTENT`) and evaluated for an **`ALLOW`**, **`ASK`**, or **`DENY`** verdict.

Detailed architecture, configuration schemas, IPC specifications, and policy examples are documented in [`doc/pluggable_security.md`](doc/pluggable_security.md).

### **Policy Engines**

| Engine | Description | Configuration |
|---|---|---|
| **Builtin** (Default) | In-process Python engine evaluating English-like Security DSL rules, path traversal boundaries, and dangerous command patterns. | `engine = "builtin"` in `~/.config/chatybot/security.toml` |
| **Binary (`racf-guard`)** | External high-performance Rust engine evaluating enterprise IBM RACF-style security definitions (`.racf`). Runs via standard stdio JSON protocol. | `engine = "binary"` in `~/.config/chatybot/security.toml` |

---

### **Enabling RACF-Guard (`engine = "binary"`)**

`racf-guard` is located in the repository under [`tools/racf-guard/`](tools/racf-guard/). It brings mainframe-grade Access Control Lists (ACLs), user/group role assignments, and discrete/generic resource matching to agent operations.

#### **1. Location and Build**
From the repository root:
```bash
cd tools/racf-guard
cargo build --release
```
The compiled binary will be located at:
```bash
tools/racf-guard/target/release/racf-guard
```

#### **2. Automated Setup**
Run the bundled setup script:
```bash
cd tools/racf-guard
./setup.sh
```
This builds the release binary, copies the reference seed policy to `~/.config/chatybot/security.racf`, connects your active OS user to the `DEVELOPER` group, and configures `~/.config/chatybot/security.toml`.

#### **3. Manual Configuration in `~/.config/chatybot/security.toml`**
To switch Chatybot to `racf-guard`:
```toml
engine = "binary"
fail_safe = "deny"

[binary]
# Absolute path or ~/ path to the compiled racf-guard binary
path = "~/.config/chatybot/racf-guard"   # or path to tools/racf-guard/target/release/racf-guard
args = ["--policy", "~/.config/chatybot/security.racf"]
timeout_seconds = 2.0
```
Copy `tools/racf-guard/examples/security.racf` to `~/.config/chatybot/security.racf` and ensure your username is connected:
```racf
CONNECT <your-username> GROUP(DEVELOPER)
```

---

### **Backing Out of RACF (Reverting to Builtin)**

To switch back to the built-in Python security engine:
1. Open `~/.config/chatybot/security.toml`.
2. Change the top-level `engine` field back to `"builtin"`:
   ```toml
   engine = "builtin"
   ```
3. Chatybot immediately returns to evaluating the `[builtin]` DSL rules, path restrictions, and command filters.

*(Note: If `engine = "binary"` is configured but the binary cannot be found at the specified path, Chatybot automatically logs a warning and gracefully falls back to the builtin engine.)*

---

### **Disabling Security Policy Evaluation**

Security enforcement can be disabled temporarily or per-invocation:

#### **Method 1: CLI Flag (`--no-security`) — Recommended**
Bypass policy evaluation for a single session, script, or benchmark run:
```bash
chatybot --no-security
```
When active, Chatybot prints:
```text
[Security Warning] Security policy evaluation is DISABLED (--no-security) — all tools execute without policy checks.
```

#### **Method 2: Unattended Automation (`-y` / `--auto-approve`)**
If you do not want to disable security entirely, but need non-interactive scripts to execute without stopping at interactive confirmation prompts (`ASK` verdicts):
```bash
chatybot -y --script doc/cookbook/16_2_script_with_auto_approve.chatdsl
# or
chatybot --auto-approve
```

---

### **Configuration (`~/.config/chatybot/security.toml`)**
```toml
version = "1.0"
engine = "builtin"          # "builtin" or "binary"
fail_safe = "deny"          # "deny" or "ask" (fallback if external binary crashes)
non_interactive_ask = "deny" # Resolution for ASK in scripts without -y

[builtin]
default_verdict = "ask"

# English-like Security DSL (Deny-overrides by tier: DENY > ASK > ALLOW)
dsl_rules = [
    # Default Posture: Policy Self-Protection (strictly prevent agent from tampering with or reading security configs)
    "deny read file ending with security.toml",
    "deny write file ending with security.toml",
    "deny read file with racf in it",
    "deny write file with racf in it",

    # Safe file allow-lists
    "allow read file ending with .md because 'docs are safe'",
    "allow read file ending with .txt",

    # Sensitive path & secret protection
    "block write file ending with .env",
    "never read file with api_key in it",

    # Dangerous command guards
    "ask before run command with sudo",
    "deny run command with 'rm -rf' in it",
    "deny run command with 'git push --force' in it",
    "allow run command starting with 'git status'",
    "allow run command starting with 'git diff'",
]

[builtin.path_restrictions]
denied_paths = ["/etc", "/var/root", "/boot", "/System", "~/.ssh", "~/.aws", "~/.gnupg"]

[builtin.command_rules]
denied_patterns = ["rm -rf /", "rm -rf /*", ":(){ :|:& };:", "mkfs", "dd if=/dev/zero"]

[binary]
path = "~/.config/chatybot/racf-guard"
args = ["--policy", "~/.config/chatybot/security.racf"]
timeout_seconds = 2.0
```

### **Security CLI Options & Script Integration**
- **Debug & Rule Inspection**: `chatybot --security` outputs loaded rule definitions, active engine banners, and verbose per-turn evaluation decisions.
- **Auditing RACF Policies**: `racf-guard -p examples/security.racf -l` outputs formatted ACL audit tables across all resource classes.
- **Unattended Execution**: Pass `-y` / `--yes` / `--auto-approve` to automatically approve `ASK` verdicts in automated scripts or CI pipelines.
- **Disable Security**: Pass `--no-security` to disable policy checks entirely.
- **Handling Policy Denials**: In ChatDSL scripts, denials populate `${TOOL_DISPATCH_EXIT_CODE}` (`1` or `-1`) and `${TOOL_DISPATCH_ERROR}` (explanation message) without crashing the session (see [Cookbook Chapter 16](doc/chatdsl_cookbook.md#chapter-16--pluggable-security--policy-guardrails)).

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

## **Change Log**

All notable releases, feature additions, bug fixes, and version milestones are documented in [CHANGELOG.md](CHANGELOG.md).

---

## **License**

This project is licensed under the **MIT License**. See the [LICENSE](LICENSE) file for details.

---

## **Known Issues**

- **`nanbeige_code` Generation**: When using `/thoughtstyle nanbeige_code`, the model may only generate thinking tokens without producing the final output. This is a known artifact/quirk of the `nanbeige` model itself.
- **Session Auto-Creation on Pre-Prompt File Modification**: When session mode is active (`auto` or `on`) and a file is modified via `write_file` or `replace_file_content` before the user enters their first prompt, an active session is initialized on disk to anchor the pre-edit backup and diff patch under `~/.local/share/chatybot/sessions/<session_id>/`. When chat history or sessions are disabled (`/session history off` or `/session off`), file backups fall back to the global backup path (`~/.local/share/chatybot/backups/`) and no session is created.
- **Interactive `/ask` in Batch Mode & Background Jobs**: The `/ask` command and `ask_user` tool require an active, foreground controlling terminal (`stdin.isatty()` and foreground process group). When running in true non-interactive batch mode (such as background jobs `cmd &`, cron, CI runners, or piped stdin), `/ask` will automatically bypass/skip without blocking (recording `[ask] Skipped`). Scripts designed to run headlessly in batch should establish default fallback variables (`set proceed = "yes"`) or receive inputs via command-line script parameters (`x=`, `y=`, `z=`).
- **Session History Accumulation in Multi-Model & Batch ChatDSL Scripts**:
  - **Why this occurs**: In interactive sessions, chatybot retains conversation history across turns (`/session history on` by default) so the model remembers prior dialogue. When running ChatDSL automation scripts that compare multiple models (`/model <name>`), run evaluation benchmarks, loop through test cases (`foreach`), or invoke LLM judges, past turns accumulate in the payload sent to subsequent models. This causes cross-model context contamination (e.g. Model B sees Model A's answers as prior assistant turns), context bloat, and skewed evaluations.
  - **Resolution**: Place `/session history off` at the beginning of stateless, multi-model, benchmark, or fuzzing scripts. Chatybot keeps the single latest turn available in memory so that `/save <file>`, `${LAST_RESPONSE}`, `${LAST_COMPLETION}`, and `/dblog` succeed normally without leaking prior turns into future prompts.
  - **Which scripts benefit from `/session` (History ON)**:
    - *Agentic Tool Loops*: Scripts using `/tool loop` or autonomous tool execution where tool calls, command outputs, and file edits must feed back into the model across consecutive turns to complete complex multi-step objectives.
    - *Iterative Multi-Turn Reasoning*: Dialogues where a single model refines, debugs, or incrementally elaborates on its previous answers.
  - **Which scripts cannot benefit and require `/session history off`**:
    - *Multi-Model Comparisons*: Scripts querying Model A, switching `/model`, and querying Model B with the same prompt (e.g. `nanjing5.chatdsl`, `cpp_algorithms.chatdsl`).
    - *Independent Test / Benchmark Suites*: Scripts testing zero-shot capabilities or novel DSLs across models (e.g. `dsl_test/test_vortex_dsl.chatdsl`).
    - *Batch / Fuzz Loops*: Scripts iterating over input arrays or running automated database logging (`/dblog`) where each prompt must be evaluated independently.

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
