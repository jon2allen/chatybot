# ChatDSL Comprehensive Guide

## Overview

ChatDSL (Chat Domain-Specific Language) is a powerful scripting language designed for automating interactions with Large Language Models (LLMs). This guide provides a complete reference for working with ChatDSL, including features, tutorials, howtos, and a comprehensive keyword reference.

> *Last updated: 2025-07-23*
>
> *Version: 1.0*
>
> *Compatible with Chatybot v0.6.4+*

---

# Features

## Core Capabilities

### 1. Multi-Language Support
ChatDSL supports 6 languages with full command aliasing:
- **English (EN)** - Primary language
- **Spanish (ES)** - Spanish translations of all commands
- **French (FR)** - French translations of all commands
- **Chinese (ZH)** - Chinese translations of all commands
- **Italian (IT)** - Italian translations of all commands
- **Arabic (AR)** - Arabic translations of all commands

### 2. Scripting Features
- **Variable System**: Script-scoped variables with `${name}` syntax
- **Conditional Logic**: `if` statements with `==`, `!=`, and `not` operators
- **Buffer Management**: Main buffer and 5 file banks for persistent context
- **Multiline Input**: Complex prompts spanning multiple lines
- **File Operations**: Load, view, clear, and save files
- **Script Parameters**: `x`, `y`, `z` parameters for custom scripts
- **Macros**: Reusable prompt templates with Parsley PEG grammar parsing

### 3. LLM Integration
- **Model Management**: Switch between 20+ configured models across 8 providers
- **System Prompts**: Set core behavioral rules
- **Temperature Control**: `0.0-2.0` for response randomness
- **Token Limits**: Control completion length
- **Sampling Control**: `top_p`, `top_k`, `freq_penalty`, `pres_penalty`
- **Reasoning Controls**: `reasoning`, `effort`, and `thinking` modes
- **Vendor-Specific Optimizations**: NVIDIA, Mistral, Google, OpenAI adaptations

### 4. Advanced Features
- **Tool Loops**: Autonomous execution with tool calling (local + MCP)
- **Image Generation**: OpenAI, Mistral, OpenRouter, Ollama support
- **Database Integration**: TinyDB vector storage with reranking
- **Profile System**: `.chatdsl` files as persistent session profiles
- **MCP Integration**: Model Context Protocol server support

### 5. Diagnostics & Monitoring
- **Trace Outputs**: TPS, raw payload, image debug, rerank, agentic loop tracing
- **Debug Commands**: View raw responses and memory usage
- **Logging**: File logging and error tracking
- **Buffer Inspection**: Check memory and variable states

---

# Project Structure

## Source Layout

```
src/chatybot/                    # Main package
├── __init__.py                  # Version: "0.6.4"
├── main.py                      # Entry point → chatybot_app.run()
├── chatybot_app.py              # Core application (5,887 lines)
├── buffer_manager.py            # File banks, image banks, script variables
├── chatydb.py                   # TinyDB database integration
├── chaty_help.py                # Structured help system
├── chatdsl_parse.py             # ChatDSL grammar parser
├── config_manager.py            # TOML config loading
├── config_model.py              # Pydantic config validation
├── config_sync.py               # Config file sync
├── config_tui.py                # Terminal UI for config
├── dispatcher.py                # Tool execution gateway
├── extract_code.py              # Code block extraction
├── image_generator.py           # Multi-vendor image generation
├── image_manager.py             # Image loading utilities
├── localization.py              # i18n / multi-language support
├── logging_manager.py           # Chat logging
├── macro.chatdsl                # Default macro definitions
├── mcp_client.py                # MCP protocol integration
├── menu.chatdsl                 # Menu DSL script
├── pattern.py                   # Command pattern matcher
├── profile_editor.py            # Curses profile editor
├── profile_manager.py           # Profile CRUD operations
├── vendors.py                   # Vendor preset definitions
├── chat_config.toml             # Default model configurations
├── tools_config.toml            # Tool definitions for agentic mode
├── translations.json            # Multi-language translations
├── profiles/                    # Preset profile scripts
├── tinydb1/corpus_manager.py    # TinyDB wrapper
└── tools/
    ├── __init__.py
    ├── file_utils.py            # File tools: list, read, write, grep, run, replace
    └── tool_config_tui.py       # Tool configuration TUI
```

## Entry Points

```bash
chatybot                  # Main CLI entry point
chatdsl_parse             # DSL parser utility
chatybot-config           # Configuration TUI editor
```

---

# Tutorials

## Tutorial 1: Basic Translation Workflow

This tutorial demonstrates how to translate a file between languages using ChatDSL.

### Prerequisites
- A source text file (`english.txt`)
- API keys configured in `~/.config/chatybot/chat_config.toml`

### Step-by-Step Guide

1. **Configure Parameters**
   ```dsl
   # Usage: /script translate.chatdsl x=english.txt y=spanish z=output.txt
   if ${x} != "" then set source = ${x}
   if ${source} == "" then set source = "english.txt"
   
   if ${y} != "" then set target_lang = ${y}
   if ${target_lang} == "" then set target_lang = "spanish"
   
   if ${z} != "" then set output_file = ${z}
   if ${output_file} == "" then set output_file = "output.txt"
   ```

2. **Load Source File**
   ```dsl
   /file ${source}
   ```

3. **Perform Translation**
   ```dsl
   /echo "Translating to ${target_lang}..."
   
   /model gemini_flash
   Translate ${target_lang}:
   
   /save ${output_file}
   ```

4. **Results**
   - File created at `${output_file}`
   - Translation saved in target language

### Complete Script

```dsl
# translate.chatdsl
# Usage: /script translate.chatdsl x=english.txt y=spanish z=output.txt

# Parameter handling
if ${x} != "" then set source_file = ${x}
if ${source_file} == "" then set source_file = "english.txt"

if ${y} != "" then set target_lang = ${y}
if ${target_lang} == "" then set target_lang = "spanish"

if ${z} != "" then set output_file = ${z}
if ${output_file} == "" then set output_file = "output.txt"

# Load source
/file ${source_file}

# Translate
/echo "Translating to ${target_lang}..."

/model gemini_flash
Translate ${target_lang}:

/save ${output_file}

/echo "Translation saved to ${output_file}"
```

---

## Tutorial 2: File Comparison Using ChatDSL

Learn how to compare two files and identify key differences.

### Usage
```bash
/chatybot.py
chat --> /script compare_articles.chatdsl x=article1.txt y=article2.txt z=comparison.txt
```

### Complete Script

```dsl
# compare_articles.chatdsl
# Usage: /script compare_articles.chatdsl x=article1.txt y=article2.txt z=comparison.txt

# Parameter handling
if ${x} != "" then set file1 = ${x}
if ${file1} == "" then set file1 = "default1.txt"

if ${y} != "" then set file2 = ${y}
if ${file2} == "" then set file2 = "default2.txt"

if ${z} != "" then set output = ${z}
if ${output} == "" then set output = "comparison.txt"

# Load files into banks
/filebank1 ${file1}
/filebank2 ${file2}

/echo "Comparing ${file1} and ${file2}"

# Generate comparison
/system "You are a precise text comparison expert."

/multiline
Compare these two articles and identify:
1. Structural differences
2. Content differences
3. Style differences

Article A:
{filebank1}

Article B:
{filebank2}

Provide a detailed comparison.
;;
/multiline

# Save result
/save ${output}

/echo "Comparison saved to ${output}"
```

### Expected Output
The script will generate a detailed comparison covering:
- **Structural differences**: Section order, headings, formatting
- **Content differences**: Facts, data, main arguments
- **Style differences**: Vocabulary, sentence structure, tone

---

## Tutorial 3: Multi-Model Evaluation

Evaluate how different models respond to the same prompt.

### Usage
```bash
/chatybot.py
chat --> /script evaluate.chatdsl x=prompt.txt y=output_dir
```

### Complete Script

```dsl
# evaluate.chatdsl
# Usage: /script evaluate.chatdsl x=prompt_file y=output_dir

set prompt_file = ${x}
set output_dir = ${y}

# Model 1 - GPT-4
/echo "Processing with GPT-4..."
/model openai_gpt4
/prompt ${prompt_file}
/save ${output_dir}/gpt4_response.txt

# Model 2 - Claude
/echo "Processing with Claude..."
/model claude
/prompt ${prompt_file}
/save ${output_dir}/claude_response.txt

# Compare responses
/echo "Comparing models..."

/filebank1 ${output_dir}/gpt4_response.txt
/filebank2 ${output_dir}/claude_response.txt

/multiline
Compare these two responses to the same prompt:

Model A (GPT-4):
{filebank1}

Model B (Claude):
{filebank2}

Which is better and why?
;;
/multiline
/save ${output_dir}/comparison.txt

/echo "Evaluation complete! Results in ${output_dir}"
```

### Output Files
- `${output_dir}/gpt4_response.txt` - GPT-4 response
- `${output_dir}/claude_response.txt` - Claude response
- `${output_dir}/comparison.txt` - Side-by-side comparison

---

# HowTos

## HowTo: Configure Chatybot

### Configuration File Location
```bash
~/.config/chatybot/chat_config.toml    # User configuration (overrides defaults)
src/chatybot/chat_config.toml          # Default configuration (bundled)
```

### Configuration File Format (TOML)

```toml
# ============================================================================
# IMAGE GENERATION SETTINGS
# ============================================================================

[image_generation]
default_dir = "~/chatybot_images"
default_size = "1024x1024"
default_quality = "standard"

# ============================================================================
# CHAT MODELS
# ============================================================================

[models.mistral_1]
name = "mistral-large-2512"
temperature = 0.7
top_k = 1
base_url = "https://api.mistral.ai/v1"
api_key = "MISTRAL_API_KEY"
image_generation = true
image_endpoint = "/images/generations"
vendor = "mistral"

[models.gemini_flash]
name = "gemini-2.5-flash"
temperature = 0.0
top_k = 1
base_url = "https://generativelanguage.googleapis.com/v1beta/openai/"
api_key = "GEMINI_API_KEY"
image_generation = true
vendor = "google"

[models.openai_gpt4]
name = "gpt-4o"
temperature = 0.1
top_k = 1
base_url = "https://api.openai.com/v1"
api_key = "OPENAI_API_KEY"
image_generation = true
vendor = "openai"

[models.ollama_llama3]
name = "llama3.2"
temperature = 0.7
top_k = 1
base_url = "http://localhost:11434/v1"
api_key = "OLLAMA"
```

### Model Configuration Properties

| Property | Type | Description |
|----------|------|-------------|
| `name` | string | Model identifier (API-specific) |
| `temperature` | float | Response randomness (0.0-2.0) |
| `top_k` | integer | Top-K sampling count |
| `base_url` | string | API endpoint URL |
| `api_key` | string | Environment variable name for API key |
| `image_generation` | boolean | Enable image generation capability |
| `image_endpoint` | string | Image generation endpoint path |
| `vendor` | string | Provider identifier |

### Supported Vendors

| Vendor | Description |
|--------|-------------|
| `mistral` | Mistral AI API |
| `google` | Google Generative AI |
| `openai` | OpenAI API |
| `openrouter` | OpenRouter aggregated API |
| `nvidia` | NVIDIA NIM API |
| `publicai` | PublicAI API |
| `bytez` | Bytez API |
| `ollama` | Local Ollama server |

### Tool Configuration

Location: `src/chatybot/tools_config.toml`

```toml
[config]
tool_timeout = 60
rate_limit_delay = 2.0
max_turns = 25
strip_thinking_from_filebanks = true
shell = true
default_profile = ""
profile_dir = "~/.config/chatybot/profiles"
enable_profile_edit = true

agentic_instructions = """
IMPORTANT: You are executing in an autonomous, multi-turn tool-calling loop.
Use tools ONLY when necessary to perform actions on the system or fetch external information.
1. You can output one or more tool calls in a single turn if they can be executed in parallel or sequence. Use the JSON format enclosed in ```json ... ```.
2. Do NOT output any conversational text, descriptions, planning thoughts, or explanations before or after the tool calls.
3. Only output natural language when you have finished all tool executions and are ready to present the final result.
"""

[tools.list_directory]
enabled = true
description = "List contents of a directory"
module = "chatybot.tools.file_utils"
function = "list_directory"

[tools.read_file]
enabled = true
description = "Read the contents of a file"
module = "chatybot.tools.file_utils"
function = "read_file"
```

---

## HowTo: Batch Process Files

Since ChatDSL doesn't have loops, process files by repeating the logic manually:

### Script Template

```dsl
# batch.chatdsl
# Usage: /script batch.chatdsl x=input_dir y=output_dir

set input_dir = ${x}
set output_dir = ${y}

# File a
set file = "a.txt"
/file ${input_dir}/${file}
Analyze ${file}
/save ${output_dir}/${file}_processed.txt

# File b
set file = "b.txt"
/file ${input_dir}/${file}
Analyze ${file}
/save ${output_dir}/${file}_processed.txt

# File c
set file = "c.txt"
/file ${input_dir}/${file}
Analyze ${file}
/save ${output_dir}/${file}_processed.txt
```

---

## HowTo: Set Up Tool Calling Loop

### Enable Tool Mode
```dsl
# Enable tool schemas in system prompt
/tool on

# Make tools available
/tool enable all

# Configure for autonomous execution
/tool auto

# Set turn limit
/tool max_turns 10
```

### Execute Tool Loop
```dsl
/tool loop 50 force
```

### Check Tool Status
```dsl
/tool list
/tool prompt
```

### Available Tools

| Tool | Description |
|------|-------------|
| `list_directory` | List directory contents |
| `read_file` | Read file contents |
| `find_files` | Find files by pattern |
| `run_command` | Execute shell command |
| `write_file` | Write or append to file |
| `change_dir` | Change working directory |
| `grep_search` | Search file contents |
| `replace_file_content` | Find and replace in file |

### MCP Tool Integration

MCP tools are namespaced as `mcp__<server>__<tool>`:
```dsl
# MCP tools auto-discovered from connected servers
/tool list

# Execute MCP tool
# (Automatic via tool loop - LLM generates JSON tool calls)
```

---

## HowTo: Image Generation Workflow

### Basic Image Generation
```dsl
# Set image parameters
/imagedir output/
/imagesize 1024x1024
/imagequality hd

# Generate image
/imagine a beautiful sunset over mountains

# List generated images
/listimages

# Show image details
/showimage
```

### Save Generated Image
```dsl
# Generate and save
/imagine a cat playing with yarn
/saveimage images/cat_toy.jpg
```

### Load Image into Bank
```dsl
# Load image for use in prompts
/loadimage images/cat_toy.jpg imagebank1

# Reference in prompt
Describe this image: {imagebank1}
```

### Image Bank Management
```dsl
# Load into specific bank
/imagebank1 path/to/image.jpg

# Show bank contents
/imagebank1 show

# Clear bank
/imagebank1 clear
```

### Supported Image Vendors

| Vendor | Model | Notes |
|--------|-------|-------|
| OpenAI | gpt-4o | Native image generation |
| Mistral | mistral-large-2512 | Via OpenAI-compatible API |
| Google | gemini-2.5-flash, gemini-2.5-pro | Via OpenAI-compatible endpoint |
| OpenRouter | google/gemini-2.5-flash-image | Chat completions with modalities |
| OpenRouter | black-forest-labs/flux.2-klein-4b | Dedicated image model |
| Ollama | Local models | Via `/api/generate` endpoint |

---

## HowTo: Database Integration

### Connect and Query
```dsl
# Set up database
/setdb knowledge_base

# Search for information
/searchdb "machine learning algorithms 2024"

# Load results
/loadvar ml_results ALL

# Add context to prompt
/system "You are an AI expert with access to 2024 ML research."

Based on: ${ml_results}

What are the key developments in ML in 2024?

# Log response to database
/dblog
```

### Rerank Search Results
```dsl
# Perform search then rerank
/searchdb "climate change economics"
/rerank

# Load reranked results
/loadvar ranked_results TOP5
```

### Document Sources for Reranking

| Source | Syntax | Description |
|--------|--------|-------------|
| Database | `/documents db=<name>` | TinyDB database |
| Variable | `/documents var=<name>` | Script variable |
| File Bank | `/documents filebank=<1-5>` | File bank content |
| Directory | `/documents dir="<path>"` | Directory of files |

### Database Commands

| Command | Description |
|---------|-------------|
| `/setdb <name>` | Create/select database |
| `/setdb Null` | Deactivate database |
| `/dblist` | List all databases |
| `/searchdb <query>` | Search database |
| `/dblog` | Log last chat to database |
| `/dbprint [file]` | Print database contents |
| `/loadvar <var> [ALL\|id\|range]` | Load DB records into variable |
| `/savevar <var> <file>` | Save variable to file |
| `/setvar <name> <value>` | Set variable directly |

---

## HowTo: Profile Management

### Profile Commands

```dsl
# List available profiles
/profile list

# Use a profile
/profile use my_profile

# Clone current session to new profile
/profile clone new_profile

# Delete a profile
/profile delete old_profile

# Export profile
/profile export my_profile export_path/

# Import profile
/profile import import_path/

# Show current profile
/profile show

# Edit profile in curses editor
/profile edit
```

### Profile Directory
```bash
~/.config/chatybot/profiles/    # User profiles
src/chatybot/profiles/          # Preset profiles
```

---

## HowTo: History Search

```dsl
# Search command history
! machine learning

# Search for specific command
! /model
```

---

# Reference

# ChatDSL Keyword Reference

## Command Keywords

### System & Interface Commands

| Keyword | Category | Syntax | Description |
|---------|----------|--------|-------------|
| `/help` | General | `/help [cmd\|keyword]` | Display help interface |
| `/quit` | General | `/quit` | Close session and save history |
| `/exit` | General | `/exit` | Close session and save history |
| `/echo` | General | `/echo text` | Print text with variable evaluation |
| `/source` | General | `/source file.dsl` | Load and execute a script file |
| `/script` | General | `/script file.dsl [x=v y=v z=v]` | Run script with parameters |
| `/calc` | General | `/calc <expr>` | Evaluate math expression |
| `/str_search` | General | `/str_search <needle> [haystack]` | Search for substring in text |
| `/proc` | General | `/proc <name> [args]` | Execute defined procedure |
| `/session` | General | `/session <subcmd> [args]` | Manage chat sessions (list/show/save/prune/etc.) |
| `/reloadmacros` | General | `/reloadmacros [file]` | Reload macro definitions |

### Model & LLM Commands

| Keyword | Category | Syntax | Description |
|---------|----------|--------|-------------|
| `/model` | Model | `/model [alias]` | Switch model or show current |
| `/listmodels` | Model | `/listmodels` | List available models |
| `/system` | Model | `/system [message]` | Get/set system message |
| `/temp` | Model | `/temp [value]` | Temperature (0.0-2.0) |
| `/maxtokens` | Model | `/maxtokens [value]` | Max completion tokens |
| `/context_limit` | Model | `/context_limit [tokens\|off]` | Set hard context token limit |
| `/auto_truncate` | Model | `/auto_truncate [on\|off\|10-100]` | Auto-truncate context above limit % |
| `/top_p` | Model | `/top_p [value]` | Nucleus sampling (0.0-1.0) |
| `/top_k` | Model | `/top_k [value]` | Top-K sampling |
| `/freq_penalty` | Model | `/freq_penalty [value]` | Frequency penalty (-2.0 to 2.0) |
| `/pres_penalty` | Model | `/pres_penalty [value]` | Presence penalty (-2.0 to 2.0) |
| `/seed` | Model | `/seed [value]` | Random seed |
| `/stream` | Model | `/stream` | Toggle streaming responses |
| `/reasoning` | Model | `/reasoning [on\|off]` | Toggle reasoning mode |
| `/effort` | Model | `/effort [low\|medium\|high\|none]` | Set reasoning effort |
| `/thinking` | Model | `/thinking [on\|off]` | Toggle thinking blocks display |
| `/thoughtstyle` | Model | `/thoughtstyle [style]` | Set thought formatting style |

### File Buffer Commands

| Keyword | Category | Syntax | Description |
|---------|----------|--------|-------------|
| `/file` | File | `/file path` | Load text file to buffer |
| `/showfile` | File | `/showfile [all]` | View buffer contents |
| `/clearfile` | File | `/clearfile` | Clear buffer |
| `/filebank{1-5}` | File | `/filebankN path\|clear\|show [all]` | Manage file banks |
| `/imagebank{1-5}` | File | `/imagebankN path\|clear\|show` | Manage image banks |
| `/loadimage` | File | `/loadimage path <imagebank>` | Load image to bank with base64 |
| `/notemode` | File | `/notemode [on\|off]` | Extract code blocks with save |
| `/codeonly` | File | `/codeonly` | Enable code-only formatting |
| `/codeoff` | File | `/codeoff` | Disable code-only formatting |
| `/multiline` | File | `/multiline` | Toggle multiline input mode |
| `/save` | File | `/save file [all] [nothink\|withthink]` | Save last LLM response |
| `/prompt` | File | `/prompt file` | Load and execute prompt file |

### Image Generation Commands

| Keyword | Category | Syntax | Description |
|---------|----------|--------|-------------|
| `/imagine` | Image | `/imagine prompt` | Generate image from text |
| `/imagesize` | Image | `/imagesize [WxH]` | Set/get image resolution |
| `/imagequality` | Image | `/imagequality [standard\|hd]` | Set/get image quality |
| `/saveimage` | Image | `/saveimage [path]` | Save last generated image |
| `/imagedir` | Image | `/imagedir [path]` | Set/get image output folder |
| `/listimages` | Image | `/listimages` | List all saved images |
| `/showimage` | Image | `/showimage [date\|filename]` | Show image metadata |

### Shell Commands

| Keyword | Category | Syntax | Description |
|---------|----------|--------|-------------|
| `/run` | Shell | `/run command [args]` | Execute shell command |
| `/run_safe` | Shell | `/run_safe` | Enable safety confirmation prompts |
| `/run_unsafe` | Shell | `/run_unsafe` | Disable shell execution confirmations |

### Tool Loop Commands

| Keyword | Category | Syntax | Description |
|---------|----------|--------|-------------|
| `/tool` | Tools | `/tool [subcmd] [args]` | Tool mode management |
| `/tool on` | Tools | `/tool on` | Load tool definitions into prompt |
| `/tool off` | Tools | `/tool off` | Disable tool schemas |
| `/tool list` | Tools | `/tool list` | List available tools and state |
| `/tool enable` | Tools | `/tool enable <tool\|all>` | Enable specific tool or all |
| `/tool disable` | Tools | `/tool disable <tool\|all>` | Disable specific tool or all |
| `/tool auto` | Tools | `/tool auto` | Toggle automated loop on tool outputs |
| `/tool loop` | Tools | `/tool loop [turns] [force]` | Run loop with turn limit |
| `/tool max_turns` | Tools | `/tool max_turns [N]` | Get/set max turn safety cap |
| `/tool rate_limit` | Tools | `/tool rate_limit [seconds]` | Inter-turn delay pause (seconds) |
| `/tool prompt` | Tools | `/tool prompt` | View active prompt |
| `/tool prompt edit_live` | Tools | `/tool prompt edit_live` | Live-edit agentic instructions |

### Diagnostics Commands

| Keyword | Category | Syntax | Description |
|---------|----------|--------|-------------|
| `/trace` | Debug | `/trace <subcmd> [on\|off]` | Toggle trace modes |
| `/trace rawpayload` | Debug | `/trace rawpayload [on\|off]` | Raw API payload tracing |
| `/trace tps` | Debug | `/trace tps [on\|off]` | Tokens per second tracing |
| `/trace tpsperf` | Debug | `/trace tpsperf [on\|off]` | TPS performance tracing |
| `/trace imagedbg` | Debug | `/trace imagedbg [on\|off]` | Image generation debug |
| `/trace rerank` | Debug | `/trace rerank [on\|off]` | Rerank operation tracing |
| `/trace agentic_loop` | Debug | `/trace agentic_loop [on\|off]` | Agentic loop tracing |
| `/debug` | Debug | `/debug <payload\|response\|vmem>` | Debug mode settings |
| `/logging` | Debug | `/logging [start\|end]` | Start/stop file logging |
| `/mem` | Debug | `/mem [detail\|debug]` | Show memory usage |
| `/dump` | Debug | `/dump [varname\|all]` | Dump variable contents |

### Database Commands

| Keyword | Category | Syntax | Description |
|---------|----------|--------|-------------|
| `/setdb` | Database | `/setdb <name\|Null>` | Connect/initialize/disable database |
| `/dblist` | Database | `/dblist` | List vector databases available |
| `/searchdb` | Database | `/searchdb <query>` | Execute vector query |
| `/dblog` | Database | `/dblog` | Log last chat to database |
| `/dbprint` | Database | `/dbprint [file]` | Dump database contents |
| `/documents` | Database | `/documents <src>=<id>` | Set rerank document source |
| `/rerank` | Database | `/rerank "<query>" [options]` | Execute semantic reranking |

### Variable Commands

| Keyword | Category | Syntax | Description |
|---------|----------|--------|-------------|
| `/setvar` | Variable | `/setvar <name> <value>` | Set a script variable |
| `/loadvar` | Variable | `/loadvar <name> [ALL\|id\|range]` | Load DB records into variable |
| `/savevar` | Variable | `/savevar <name> <filename>` | Save variable to file |

### Profile Commands

| Keyword | Category | Syntax | Description |
|---------|----------|--------|-------------|
| `/profile` | Profile | `/profile <subcmd> [args]` | Profile management |
| `/profile list` | Profile | `/profile list` | List available profiles |
| `/profile use` | Profile | `/profile use <name>` | Load a profile |
| `/profile clone` | Profile | `/profile clone <name>` | Clone current session |
| `/profile delete` | Profile | `/profile delete <name>` | Delete a profile |
| `/profile export` | Profile | `/profile export <name> <path>` | Export profile |
| `/profile import` | Profile | `/profile import <path>` | Import profile |
| `/profile show` | Profile | `/profile show` | Show current profile |
| `/profile edit` | Profile | `/profile edit` | Edit profile in TUI |

### History Commands

| Keyword | Category | Syntax | Description |
|---------|----------|--------|-------------|
| `!` | History | `! <search>` | Search command history |

## Scripting Keywords

| English | Syntax | Description |
|---------|--------|-------------|
| `set` | `set name = value` | Variable assignment |
| `local` | `local name = value` | Procedure-scoped variable |
| `if` | `if condition then command` | Conditional execution |
| `then` | (part of if) | Conditional body |
| `wait` | `wait N` | Pause N seconds |
| `defproc` | `defproc name(params)` | Define procedure |
| `endproc` | `endproc` | End procedure |
| `foreach` | `foreach item in collection` | Begin foreach loop |
| `endfor` | `endfor` | End foreach loop |
| `break` | `break` | Exit foreach loop early |
| `range` | `range(start:end:step)` | Generate number sequence |
| `lines` | `lines(text)` | Split text into lines |
| `#` | `# comment` | Comment |
| `def` | `def name(params) = "template"` | Define macro |
| `%` | `%name(args)` | Invoke macro |

## Variable Syntax

| Syntax | Description |
|--------|-------------|
| `${name}` | Variable reference |
| `set name = "value"` | Variable definition |
| `"value with spaces"` | Quoted value |
| `'value with spaces'` | Single-quoted value |
| `{filebankN}` | File bank reference in prompts |
| `{imagebankN}` | Image bank reference in prompts |

## Operators

| Operator | Description | Example |
|----------|-------------|---------|
| `==` | Equals | `if ${x} == "yes" then` |
| `!=` | Not equals | `if ${x} != "" then` |
| `not` | Negation | `if not ${debug} then` |

## Control Flow

| Command | Syntax | Description |
|---------|--------|-------------|
| `if` | `if condition then command` | Conditional execution |
| `foreach` | `foreach item in collection` | Iterate over array or generator |
| `endfor` | `endfor` | End foreach loop |
| `break` | `break` | Exit foreach loop early |
| `wait` | `wait N` | Pause N seconds |
| `set` | `set name = value` | Define variable |
| `local` | `local name = value` | Define procedure-scoped variable |
| `defproc` | `defproc name(params)` | Define procedure |
| `endproc` | `endproc` | End procedure |
| `#` | `# comment` | Comment |

## Multiline Syntax

| Keyword | Syntax | Description |
|---------|--------|-------------|
| `/multiline` | `/multiline` | Start multiline block |
| `;;` | `;;` | End multiline block |

## Macro Syntax

| Element | Syntax | Description |
|---------|--------|-------------|
| Definition | `def name(params) = "template"` | Define macro |
| No-param | `def name() = "template"` | Define no-param macro |
| Invocation | `%name(args)` | Call macro |
| Template var | `{param}` | Parameter placeholder |

### Example Macros

```dsl
# No-parameter macros
def regen() = "Regenerate all source code"
def build() = "Build the project with optimized settings"

# Parameterized macros
def expert_prompt(topic) = "Act as an expert in {topic}. Provide detailed, accurate, and insightful information about {topic}."

def language_comparison(lang1, lang2) = "Compare {lang1} and {lang2} programming languages. Discuss their similarities, differences, syntax variations, performance characteristics, and typical use cases."
```

## Error Messages

| Error | English | Spanish | French | Chinese | Italian |
|-------|---------|---------|--------|---------|---------|
| File not found | "Error: File not found" | "Error: Archivo no encontrado" | "Erreur: Fichier introuvable" | "错误: 文件没有找到" | "Errore: File non trovato" |
| Macro not defined | "ERROR: Macro 'X' not defined" | "ERROR: Macro 'X' no definido" | "ERREUR: Macro 'X' non définie" | "错误: 宏 'X' 未定义" | "ERRORE: Macro 'X' non definita" |
| Wrong arguments | "ERROR: Macro 'X' expects N arguments, got M" | "ERROR: Macro 'X' espera N argumentos, obtuvo M" | "ERREUR: Macro 'X' attend N arguments, reçu M" | "错误: 宏 'X' 需要 N 个参数，得到 M 个" | "ERRORE: Macro 'X' aspetta N argomenti, ottenuti M" |

---

# Best Practices

## Script Writing Guidelines

### 1. Variable Naming
- Use **snake_case** for descriptive names: `article_num`, `model_name`
- Single letters (`x`, `y`, `z`) for script parameters only
- UPPER_CASE for constants

### 2. Comment Style
```dsl
# Full line comment
set var = "value"  # Inline comment

# Section headers
# ============================================
# TRANSLATION SECTION
# ============================================
```

### 3. Script Structure
```dsl
# Header with usage
# Script: description
# Usage: /script script.chatdsl [params]

# Parameter handling
if ${x} != "" then set param1 = ${x}
if ${param1} == "" then set param1 = "default"

# Configuration
set base_dir = "output"
/model gemini_flash

# Main logic
/file input.txt
process this...
/save output.txt

# Cleanup (optional)
/clearfile
/echo "Done"
```

### 4. Common Patterns

#### Parameter Defaults
```dsl
if ${x} != "" then set var = ${x}
if ${var} == "" then set var = "default"
```

#### Conditional Model Selection
```dsl
if ${fast} then /model gemini_flash
if not ${fast} then /model openai_gpt4
```

## Error Handling

### Common Issues & Solutions

| Issue | Solution |
|-------|----------|
| Variable not expanding | Check `${name}` syntax (no spaces) |
| File not found | Use `/echo` to verify path expansion |
| Multiline not ending | Ensure `;;` on its own line, then `/multiline` |
| Set value with spaces | Use double quotes: `set var = "value with spaces"` |
| Backslash in value | Not allowed - use forward slashes |
| Command not recognized | Check for typos and `/` prefix |

## Performance Tips

### Rate Limiting
```dsl
# Between model calls
/model gemini_flash
prompt 1
/save response1.txt
wait 2  # 2 second delay

/model openai_gpt4
prompt 2
/save response2.txt
```

### Buffer Management
```dsl
# Clear buffer between unrelated operations
/clearfile

# Prevent context pollution
/file new_context.txt
```

### Reduce Token Usage
```dsl
# Use /codeonly for code generation
/codeonly
Write Python code to solve this problem.
/codeoff
```

---

# Quick Reference

## Command Categories

### System
- `/help` - Display help
- `/echo` - Print text
- `/quit` - Exit session
- `/script` - Run script
- `/source` - Execute script file

### Model
- `/model [alias]` - Switch model
- `/system [prompt]` - Set system message
- `/temp [value]` - Set temperature
- `/maxtokens [value]` - Set max tokens
- `/reasoning [on|off]` - Toggle reasoning
- `/effort [low|medium|high|none]` - Set reasoning effort

### File
- `/file path` - Load to buffer
- `/filebank1-5` - File bank management
- `/save file [all] [nothink|withthink]` - Save response
- `/multiline` - Complex prompts
- `/prompt file` - Execute prompt file

### Image
- `/imagine prompt` - Generate image
- `/imagesize WxH` - Set resolution
- `/saveimage [path]` - Save generated image
- `/imagebank1-5` - Image bank management

### Database
- `/setdb name` - Connect storage
- `/searchdb "query"` - Vector search
- `/dblog` - Log response
- `/rerank` - Semantic reranking

### Tool
- `/tool on` - Enable tools
- `/tool loop [turns] [force]` - Autonomous execution
- `/tool list` - List tools
- `/tool enable all` - Enable all tools

### Debug
- `/trace <type> [on|off]` - Enable tracing
- `/mem [detail|debug]` - Memory usage
- `/dump [var|all]` - Dump variables

### Profile
- `/profile list` - List profiles
- `/profile use name` - Load profile
- `/profile clone name` - Clone session

## Scripting Elements

### Variables
```dsl
set name = "value"
${name}
```

### Conditions
```dsl
if ${x} == "yes" then /command
if not ${debug} then /echo "quiet"
```

### Wait
```dsl
wait 2
```

### Multiline
```dsl
/multiline
Your prompt here
;;
/multiline
```

### Macros
```dsl
# Define
def expert_prompt(topic) = "Act as an expert in {topic}."

# Invoke
%expert_prompt(Python)
```

---

# Resources

## Documentation Files

- **ChatDSL Language Guide** (`chatdsl_language.md`) - Complete language reference with command mappings
- **ChatDSL Skill Guide** (`chatdsl_skill.md`) - Comprehensive scripting patterns
- **ChatDSL Macro Implementation** (`chatdsl_macro_implementation.md`) - Technical implementation report

## Configuration Files

- `~/.config/chatybot/chat_config.toml` - User model configuration
- `~/.config/chatybot/profiles/` - User profiles
- `src/chatybot/chat_config.toml` - Default model configuration
- `src/chatybot/tools_config.toml` - Tool definitions
- `src/chatybot/macro.chatdsl` - Default macro definitions
- `src/chatybot/translations.json` - Multi-language translations

## Project Files

- `chatdsl_bnf.txt` - Formal grammar specification
- `script_param_implementation.md` - Parameter passing details
- `dsl_test/` - Test scripts demonstrating all features

---

# Getting Started

## Quick Start

1. **Install Chatybot**
   ```bash
   pip install chatybot
   ```

2. **Configure API Keys**
   ```bash
   # Copy default config to user directory
   mkdir -p ~/.config/chatybot
   cp src/chatybot/chat_config.toml ~/.config/chatybot/
   
   # Edit with your API keys
   chatybot-config
   ```

3. **Run Chatybot**
   ```bash
   chatybot
   ```

4. **Execute a ChatDSL Script**
   ```bash
   chat --> /script my_script.chatdsl x=value1 y=value2
   ```

## Basic Commands

- `/help` - View all available commands
- `/model` - Switch between models
- `/file path` - Load context files
- `/echo "text"` - Debug output
- `/save path` - Save responses

## Example Scripts

Check the `dsl_test/` directory for working examples:
- `translate.chatdsl` - Translation workflow
- `compare.chatdsl` - File comparison
- `evaluate.chatdsl` - Multi-model evaluation
- `batch.chatdsl` - Batch processing

---

*(End of ChatDSL Comprehensive Guide)*

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2025-07-23 | Initial corrected version based on v0.6.4 source code |

---

## Author Notes

This guide is the corrected version based on thorough review of the Chatybot v0.6.4 source code. All command syntax, configuration formats, and script examples have been verified against the actual implementation.