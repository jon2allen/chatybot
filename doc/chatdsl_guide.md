# ChatDSL Comprehensive Guide

## Overview

ChatDSL (Chat Domain-Specific Language) is a powerful scripting language designed for automating interactions with Large Language Models (LLMs). This guide provides a complete reference for working with ChatDSL, including features, tutorials, howtos, and a comprehensive keyword reference.

> *Last updated: 2026-08-19*
>
> *Version: 1.0*
>
> *Compatible with Chatybot v0.7.6+*

---

# Features

## Core Capabilities

### 1. Multi-Language Support
ChatDSL supports 6 languages out of the box:
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
- **File Operations**: Upload, view, clear, and save files
- **Script Parameters**: `x`, `y`, `z` parameters for custom scripts

### 3. LLM Integration
- **Model Management**: Switch between configured models
- **System Prompts**: Set core behavioral rules
- **Temperature Control**: `0.0-2.0` for response randomness
- **Token Limits**: Control completion length
- **Sampling Control**: `top_p`, `top_k`, `freq_penalty`, `pres_penalty`
- **Reasoning Controls**: `reasoning` and `thinking` modes

### 4. Advanced Features
- **Macros**: Reusable prompt templates (requires `macro.chatdsl`)
- **Database Integration**: TinyDB vector storage with RAG
- **Tool Loops**: Autonomous execution with tool calling
- **Image Generation**: `imagine` commands with size/quality control
- **Shell Commands**: `run` commands with safety options

### 5. Diagnostics & Monitoring
- **Trace Outputs**: TPS, rerank, and raw payload tracing
- **Debug Commands**: View raw responses and memory usage
- **Logging**: File logging and error tracking
- **Buffer Inspection**: Check memory and variable states

---

# Tutorials

## Tutorial 1: Basic Translation Workflow

This tutorial demonstrates how to translate a file between languages using ChatDSL.

### Prerequisites
- A source text file (`english.txt`)
- API keys for translation models

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
   set source_text = "{file}"
   ```

3. **Perform Translation**
   ```dsl
   /echo "Translating to ${target_lang}..."
   
   /model gemma
   Translate ${target_lang}:
   ${source_text}
   
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
set source_text = "{file}"

# Translate
echo "Translating to ${target_lang}..."

/model gemma
Translate ${target_lang}:
${source_text}

save ${output_file}

echo "Translation saved to ${output_file}"
```

---

## Tutorial 2: File Comparison Using ChatDSL

Learn how to compare two files and identify key differences.

### Script Overview
This script compares two files and analyzes their differences in structure, content, and style.

### Usage
```bash
/script compare_articles.chatdsl x=article1.txt y=article2.txt z=comparison.txt
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

### Script Structure
This pattern compares responses from multiple models to the same prompt.

### Usage
```bash
/script evaluate.chatdsl x=prompt.txt y=output_dir
```

### Complete Script

```dsl
# evaluate.chatdsl
# Usage: /script evaluate.chatdsl x=prompt_file y=output_dir

set prompt_file = ${x}
set output_dir = ${y}

# Model 1 - GPT-4
/echo "Processing with GPT-4..."
/model gpt4
/prompt ${prompt_file}
/save ${output_dir}/gpt4_response.txt

# Model 2 - Claude
/echo "Processing with Claude..."
/model clauce
/prompt ${prompt_file}
/save ${output_dir}/claude_response.txt

# Compare responses
echo "Comparing models..."

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

## HowTo: Configure ChatDSL for Translation

### Step 1: Prepare Directory Structure
```bash
my_project/
├── chatybot.py
├── translate.chatdsl
├── english.txt
└── config.json
```

### Step 2: Create Configuration File
```json
{
  "models": {
    "gpt4": "openai/gpt-4",
    "gemma": "google/gemma-2b-it",
    "mistral": "mistralai/mistral-7b"
  },
  "directories": {
    "output": "output",
    "templates": "templates"
  },
  "settings": {
    "temperature": 0.3,
    "max_tokens": 2000,
    "timeout": 30
  }
}
```

### Step 3: Create Translation Script
```dsl
# translate.chatdsl
# Usage: /script translate.chatdsl x=source.txt y=target_lang z=output.txt

# Model selection based on language
if ${y} == "spanish" then set model = "mistral"
if ${y} == "french" then set model = "gpt4"
if ${y} == "chinese" then set model = "gemma"
if ${y} == "italian" then set model = "gemma"

# Default model
set model = "gemma"

# Load and translate
/model ${model}
Translate to ${y}:
${x_content}
/save ${z}
```

## HowTo: Batch Process Files

### Overview
Process multiple files using a loop pattern.

### Script Template
```dsl
# batch.chatdsl
# Usage: /script batch.chatdsl x=input_dir y=output_dir

set input_dir = ${x}
set output_dir = ${y}
set files = "a.txt,b.txt,c.txt"

# Process each file
set file_list = split(${files}, ",")

# Loop through files
foreach file in ${file_list}:
    set input_file = "${input_dir}/${file}"
    set output_file = "${output_dir}/${file}_processed.txt"
    
    /echo "Processing ${file}..."
    /file ${input_file}
    
    # Process logic here
    process = "Analyze ${file}"
    
    /save ${output_file}
    /echo "Saved ${output_file}"
```

### Manual Loop Implementation
Since ChatDSL doesn't have loops, use this pattern:
```dsl
# batch.chatdsl
# Usage: /script batch.chatdsl x=input_dir y=output_dir

set input_dir = ${x}
set output_dir = ${y}
set files = "${x}/a.txt,${x}/b.txt,${x}/c.txt"

# File a
set file = "a.txt"
/file "${input_dir}/${file}"
Analyze ${file}
/save "${output_dir}/${file}_processed.txt"

# File b
set file = "b.txt"
/file "${input_dir}/${file}"
Analyze ${file}
/save "${output_dir}/${file}_processed.txt"

# File c
set file = "c.txt"
/file "${input_dir}/${file}"
Analyze ${file}
/save "${output_dir}/${file}_processed.txt"
```

## HowTo: Set Up Tool Calling Loop

### Enable Tool Mode
```dsl
# Enable tool schemas in system prompt
/tool on

# Make tools available
tool enable all

# Configure for autonomous execution
tool auto

# Set turn limit
tool max_turns 10
```

### Execute Tool Loop
```dsl
/tool loop max=50 force
```

### Check Tool Status
```dsl
/tool list
/tool prompt
```

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

### Advanced Workflow
```dsl
# Create image directory if not exists
set image_dir = "images"
/makedir ${image_dir}
/imagedir ${image_dir}

# Generate multiple related images
/imagine a cat playing with yarn, photorealistic
/save ${image_dir}/cat_toy.jpg

/imagine a dog chasing butterflies, watercolor style
/save ${image_dir}/dog_hunting.jpg

/imagine a rabbit reading a book, oil painting
/save ${image_dir}/rabbit_reading.jpg
```

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

---

# Reference

# ChatDSL Keyword Reference

## Command Keywords

### System & Interface Commands

| Keyword | Category | Syntax | Description |
|---------|----------|--------|-------------|
| `/help` | General | `/help` | Display help interface |
| `/quit` | General | `/quit` | Close session and save history |
| `/exit` | General | `/exit` | Close session and save history |
| `/echo` | General | `/echo text` | Print text with variable evaluation |
| `/source` | General | `/source file.dsl` | Load and execute a script file |
| `/script` | General | `/script file.dsl [x=v y=v z=v]` | Run script with parameters |
| `/language` | General | `/language lang` | Set the scripting language |

### Model & LLM Commands

| Keyword | Category | Syntax | Description |
|---------|----------|--------|-------------|
| `/model` | Model | `/model alias` | Switch active model |
| `/listmodels` | Model | `/listmodels` | List available models |
| `/env` | Model | `/env [filter]` | Display API keys and env vars |
| `/system` | Model | `/system "prompt"` | Set system message |
| `/temp` | Model | `/temp N` | Temperature (0.0-2.0) |
| `/maxtokens` | Model | `/maxtokens N` | Max completion tokens |
| `/top_p` | Model | `/top_p N` | Nucleus sampling (0.0-1.0) |
| `/top_k` | Model | `/top_k N` | Top-K sampling |
| `/freq_penalty` | Model | `/freq_penalty N` | Frequency penalty (-2.0 to 2.0) |
| `/pres_penalty` | Model | `/pres_penalty N` | Presence penalty (-2.0 to 2.0) |
| `/seed` | Model | `/seed N/time/random` | Random seed |
| `/stream` | Model | `/stream` | Toggle streaming |
| `/reasoning` | Model | `/reasoning on/off` | Toggle reasoning mode |
| `/thinking` | Model | `/thinking on/off` | Toggle thinking blocks |
| `/thoughtstyle` | Model | `/thoughtstyle style` | Thought formatting |

### File Buffer Commands

| Keyword | Category | Syntax | Description |
|---------|----------|--------|-------------|
| `/file` | File | `/file path` | Load text file to buffer |
| `/showfile` | File | `/showfile [all]` | View buffer contents |
| `/clearfile` | File | `/clearfile` | Clear buffer |
| `/filebank1-5` | File | `/filebankN path/clear/show` | Manage file banks |
| `/loadimage` | File | `/loadimage path` | Load image to bank with base64 |
| `/notemode` | File | `/notemode on/off` | Extract code blocks with save |
| `/codeonly` | File | `/codeonly` | Enable code-only formatting |
| `/codeoff` | File | `/codeoff` | Disable code-only formatting |
| `/multiline` | File | `/multiline` | Start multiline block |
| `/save` | File | `/save path` | Save last LLM response |
| `/prompt` | File | `/prompt file` | Load and execute prompt file |
| `/imagesize` | File | `/imagesize WxH` | Set image resolution |
| `/imagequality` | File | `/imagequality standard/hd` | Set image quality |
| `/imagedir` | File | `/imagedir path` | Set image output folder |
| `/listimages` | File | `/listimages` | List generated images |
| `/showimage` | File | `/showimage` | Show image details |

### Shell Commands

| Keyword | Category | Syntax | Description |
|---------|----------|--------|-------------|
| `/run` | Shell | `/run <command>` | Execute shell command and capture output into `${RUN_COMPLETION}` |
| `/run_safe` | Shell | `/run_safe` or `/run safe` | Enable safe mode (blocks dangerous commands) |
| `/run_unsafe` | Shell | `/run_unsafe [askfirst]` or `/run unsafe [askfirst]` | Disable safe mode (runs directly; `askfirst` enables confirmation) |
| `/makedir` | Shell | `/makedir path` | Create directory |
| `/rmdir` | Shell | `/rmdir path` | Remove directory |

### Tool Loop Commands

| Keyword | Category | Syntax | Description |
|---------|----------|--------|-------------|
| `/tool` | Tools | `/tool loop max=50 force` | Run autonomous loop |
| `/tool list` | Tools | `/tool list` | List available tools |
| `/tool enable` | Tools | `/tool enable tool/all` | Enable specific tools |
| `/tool disable` | Tools | `/tool disable tool/all` | Disable specific tools |
| `/tool on` | Tools | `/tool on` | Load tool definitions |
| `/tool off` | Tools | `/tool off` | Disable tool schemas |
| `/tool auto` | Tools | `/tool auto` | Enable automated loop |
| `/tool loop` | Tools | `/tool loop max=N` | Run loop with limit |
| `/tool max_turns` | Tools | `/tool max_turns N` | Set max turn cap |
| `/tool prompt` | Tools | `/tool prompt` | View active prompt |

### Diagnostics Commands

| Keyword | Category | Syntax | Description |
|---------|----------|--------|-------------|
| `/trace` | Debug | `/trace type on/off` | Enable tracing |
| `/debug` | Debug | `/debug mode` | Set debug payload |
| `/logging` | Debug | `/logging on/off` | Enable file logging |
| `/dump` | Debug | `/dump all/variable` | Dump variables |
| `/mem` | Debug | `/mem` | Show memory usage |
| `/help` | Debug | `/help` | Show help |

### Database Commands

| Keyword | Category | Syntax | Description |
|---------|----------|--------|-------------|
| `/setdb` | Database | `/setdb name` | Connect/initialize vector storage |
| `/dblist` | Database | `/dblist` | List available databases |
| `/searchdb` | Database | `/searchdb "query"` | Execute vector query |
| `/dblog` | Database | `/dblog` | Log response to DB |
| `/dbprint` | Database | `/dbprint [file]` | Dump database contents |
| `/documents` | Database | `/documents source` | Set data source |
| `/loadvar` | Database | `/loadvar name ALL/IDs` | Load search results |
| `/savevar` | Database | `/savevar name file` | Save variable to file |
| `/setvar` | Database | `/setvar name value` | Set variable (CLI) |
| `/rerank` | Database | `/rerank` | Execute RAG rerank query |

### Image Generation Commands

| Keyword | Category | Syntax | Description |
|---------|----------|--------|-------------|
| `/imagine` | Image | `/imagine prompt` | Generate image from text |
| `/imagesize` | Image | `/imagesize WxH` | Set resolution |
| `/imagequality` | Image | `/imagequality standard/hd` | Set quality |
| `/imagedir` | Image | `/imagedir path` | Set output folder |
| `/listimages` | Image | `/listimages` | List images by date |
| `/showimage` | Image | `/showimage` | Show image details |

### Language-Specific Commands

| English | Spanish | French | Chinese | Italian | Description |
|---------|---------|--------|---------|---------|-------------|
| `/help` | `/ayuda` | `/aide` | `/帮助` | `/aiuto` | Help |
| `/echo` | `/repetir` | `/echo` | `/回显` | `/eco` | Echo |
| `/source` | `/origen` | `/source` | `/加载脚本` | `/sorgente` | Source |
| `/quit` | `/salir` | `/quitter` | `/退出` | `/esci` | Quit |
| `/file` | `/archivo` | `/fichier` | `/文件` | `/file` | File load |
| `/clearfile` | `/limpiar_archivo` | `/vider_fichier` | `/清空文件` | `/svuota_file` | Clear file |

## Scripting Keywords

| English | Spanish | French | Chinese | Italian | Description |
|---------|---------|--------|---------|---------|-------------|
| `set` | `establecer` | `definir` | `设置` | `imposta` | Variable assignment |
| `if` | `si` | `si` | `如果` | `se` | Conditional |
| `then` | `entonces` | `then` | `那么` | `quindi` | Conditional body |
| `wait` | `esperar` | `attendre` | `等待` | `aspettare` | Pause |
| `#` | `#` | `#` | `#` | `#` | Comment |

## Variable Syntax

| Syntax | Description |
|--------|-------------|
| `${name}` | Variable reference |
| `set name = "value"` | Variable definition |
| `"value with spaces"` | Quoted value |
| `'value with spaces'` | Single-quoted value |

## Mathematical Operators

| Operator | Description |
|----------|-------------|
| `==` | Equals |
| `!=` | Not equals |
| `not` | Negation |

## Comparison Operators

| Operator | Description |
|----------|-------------|
| `==` | Equals |
| `!=` | Not equals |

## Control Flow

| Command | Syntax | Description |
|---------|--------|-------------|
| `if` | `if condition then command` | Conditional execution |
| `wait` | `wait N` | Pause N seconds |
| `set` | `set name = value` | Define variable |
| `#` | `# comment` | Comment |

## Multiline Syntax

| Keyword | Syntax | Description |
|---------|--------|-------------|
| `/multiline` | `/multiline` | Start multiline block |
| `;;` | `;;` | End multiline block |

## Error Messages

| Error | English | Spanish | French | Chinese | Italian |
|-------|---------|---------|--------|---------|---------|
| File not found | "Error: File not found" | "Error: Archivo no encontrado" | "Erreur: Fichier introuvable" | "错误: 文件没有找到" | "Errore: File non trovato" |
| Macro not defined | "ERROR: Macro 'X' not defined" | "ERROR: Macro 'X' no definido" | "ERREUR: Macro 'X' non définie" | "错误: 宏 'X' 未定义" | "ERRORE: Macro 'X' non definita" |
| Wrong arguments | "ERROR: Macro 'X' expects N arguments, got M" | "ERROR: Macro 'X' espera N argumentos, obtuvo M" | "ERREUR: Macro 'X' attend N arguments, reçu M" | "错误: 宏 'X' 需要 N 个参数，得到 M 个" | "ERRORE: Macro 'X' aspetta N argomenti, ottenuti M" |

---

# Language Mapping Summary

## Supported Languages

ChatDSL supports the following languages:

1. **English (EN)** - Primary language for documentation
2. **Spanish (ES)** - Spanish translations of all commands
3. **French (FR)** - French translations of all commands
4. **Chinese (ZH)** - Chinese translations of all commands
5. **Italian (IT)** - Italian translations of all commands

## Command Translation Examples

### System Commands

| English | Spanish | French | Chinese | Italian |
|---------|---------|--------|---------|---------|
| `/help` | `/ayuda` | `/aide` | `/帮助` | `/aiuto` |
| `/echo` | `/repetir` | `/echo` | `/回显` | `/eco` |
| `/source` | `/origen` | `/source` | `/加载脚本` | `/sorgente` |
| `/quit` | `/salir` | `/quitter` | `/退出` | `/esci` |
| `/script` | `/script` | `/script` | `/脚本` | `/script` |

### Model Commands

| English | Spanish | French | Chinese | Italian |
|---------|---------|--------|---------|---------|
| `/model` | `/modelo` | `/modele` | `/模型` | `/modello` |
| `/system` | `/sistema` | `/systeme` | `/系统提示` | `/sistema` |
| `/temp` | `/temp` | `/temp` | `/温度` | `/temp` |
| `/maxtokens` | `/max_tokens` | `/max_jetons` | `/最大Token` | `/max_token` |

### File Commands

| English | Spanish | French | Chinese | Italian |
|---------|---------|--------|---------|---------|
| `/file` | `/archivo` | `/fichier` | `/文件` | `/file` |
| `/showfile` | `/mostrar_archivo` | `/afficher_fichier` | `/显示文件` | `/mostra_file` |
| `/clearfile` | `/limpiar_archivo` | `/vider_fichier` | `/清空文件` | `/svuota_file` |

### Database Commands

| English | Spanish | French | Chinese | Italian |
|---------|---------|--------|---------|---------|
| `/setdb` | `/estab_db` | `/definir_bd` | `/设置数据库` | `/imposta_db` |
| `/searchdb` | `/buscar_db` | `/rechercher_bd` | `/搜索数据库` | `/cerca_db` |

---

# Best Practices

## Script Writing Guidelines

### 1. Variable Naming
- ✅ Use **snake_case** for descriptive names
- ✅ `article_num`, `model_name` (recommended)
- ⚠️ camelCase works but is less common
- ❌ UPPER_CASE for constants only
- ❌ Single letters (x, y, z) for script parameters only

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
/model gpt4

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

#### File Loading with Fallback
```dsl
if ${file} != "" then /file ${file}
```

#### Conditional Model Selection
```dsl
if ${fast} then /model gemma
if not ${fast} then /model gpt4
```

## Error Handling

### Common Issues & Solutions

| Issue | Solution |
|-------|----------|
| Variable not expanding | Check `${name}` syntax (no spaces) |
| File not found | Use `/echo` to verify path expansion |
| Multiline not ending | Ensure `;;` on its own line, then `/multiline` |
| Set value with spaces | Use double quotes: `set var = "value with spaces"` |
| Backslash in value | Not allowed - restructure or use forward slashes |

## Performance Tips

### Rate Limiting
```dsl
# Between model calls
/model gpt4
prompt 1
/save response1.txt
wait 2  # 2 second delay

/model gemma
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

### Model
- `/model alias` - Switch model
- `/system "prompt"` - Set system message
- `/temp N` - Set temperature

### File
- `/file path` - Load to buffer
- `/save path` - Save response
- `/multiline` - Complex prompts

### Database
- `/setdb name` - Connect storage
- `/searchdb "query"` - Vector search
- `/dblog` - Log response

### Tool
- `/tool loop max=50` - Autonomous execution
- `/tool list` - List tools
- `/tool enable all` - Enable tools

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

---

# Resources

## Documentation

- **ChatDSL Language Guide** (`chatdsl_language.md`) - Complete language reference with command mappings
- **ChatDSL Skill Guide** (`chatdsl_skill.md`) - Comprehensive scripting patterns
- **ChatDSL Macro Implementation** (`chatdsl_macro_implementation.md`) - Technical implementation report

## Other Files

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

2. **Run your first script**
   ```bash
   chatybot.py
   ```

3. **Execute a simple ChatDSL script**
   ```bash
   chat --> /model gemma
   Write a simple Python script
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

## Author Notes

This guide combines the existing documentation files into a comprehensive reference. All original documentation files have been preserved and referenced for technical details. The guide is structured to provide both learning paths (tutorials) and quick references (keyword mapping).