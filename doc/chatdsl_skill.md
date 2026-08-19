# ChatDSL Skill Guide

## Overview

ChatDSL (Chat Domain-Specific Language) is a scripting language for **chatybot** that enables automation of LLM interactions, file management, and workflow orchestration. This guide captures the complete syntax, patterns, and best practices for writing effective ChatDSL scripts.

---

## Quick Reference Table

| Feature | Syntax | Example |
|---------|--------|---------|
| **Variable Set** | `set name = "value"` | `set lang = "french"` |
| **Variable Reference** | `${name}` | `/file ${filename}` |
| **Comment** | `# comment` | `# This is a comment` |
| ** Conditional** | `if condition then /command` | `if ${x} == "1" then /echo Match` |
| **Negation** | `if not condition then` | `if not ${debug} then /echo Skip` |
| **Comparison** | `==`, `!=` | `if ${a} != ${b} then ...` |
| **Wait** | `wait N` | `wait 2` (seconds) |
| **Escape Command** | `/command args` | `/model gpt4` |
| **Script Include** | `/script file.dsl` | `/script compare.chatdsl` |
| **Script Params** | `/script f.dsl x=v y=v z=v` | `/script a.dsl x=1 y="gpt4"` |
| **Multiline Block** | `/multiline` ... `;;` `/multiline` | See below |
| **File Buffer** | `/file path` | `/file context.txt` |
| **File Bank (1-5)** | `/filebankN path` | `/filebank1 ref.txt` |
| **Show Buffer** | `/showfile [all]` | `/showfile all` |
| **Clear Buffer** | `/clearfile` | - |
| **Save Response** | `/save path` | `/save output.txt` |
| **Model Switch** | `/model alias` | `/model gpt4` |
| **System Prompt** | `/system "prompt"` | `/system "You are a translator."` |
| **Echo** | `/echo text` | `/echo "Starting..."` |

---

## Core Concepts

### 1.Line-Based Execution

Each line is either:
- **Script Command**: `set`, `if`, `wait`, `#` (comment)
- **Escape Command**: Starts with `/` (e.g., `/model`, `/file`, `/save`)
- **Chat Input**: Any other text → sent to LLM

### 2. Buffer System

```
┌─────────────────────────────────────────────────────────────┐
│                        BUFFER SYSTEM                           │
├─────────────────────────────────────────────────────────────┤
│  Main Buffer (/file)           ┆  File Bank 1-5 (/filebankN)    │
│  ┌──────────────────────────┐  ┆  ┌──────────┐ ┌──────────┐   │
│  │  Temporary context         │  ┆  │ bank1    │ │ bank2    │   │
│  │  Cleared on /clearfile     │  ┆  │ persistent│ │ persistent│   │
│  │  Prepended to next prompt  │  ┆  └──────────┘ └──────────┘   │
│  └──────────────────────────┘  ┆  Referenced as {filebank1-5} │
└─────────────────────────────────┴────────────────────────────────┘
```

### 3. Variable System

Variables are **script-scoped** and persist for the duration of script execution.

```dsl
# Definition
set filename = "article.txt"
set system_prompt = "You are a helpful assistant."

# Usage with ${variable} syntax
/file ${filename}
/system "${system_prompt}"

# Multiline values (must be quoted)
set instructions = """
1. Be concise
2. Be accurate
3. Use markdown
"""
```

**Variable Precedence:**
1. Script parameters (x, y, z) - passed via `/script file.dsl x=v y=v z=v`
2. Set variables - defined with `set name = value`
3. Empty default

---

## Script Parameters (x, y, z)

The `/script` command supports **three special parameters**: `x`, `y`, `z`.

### Usage

```bash
/script myscript.chatdsl x="value1" y="value2" z="value3"
```

### Syntax Rules

| Format | Example | Notes |
|--------|---------|-------|
| `x=value` | `x=hello` | Unquoted, single word |
| `x="value"` | `x="hello world"` | Quoted, supports spaces |
| `x='value'` | `x='hello world'` | Single-quoted, supports spaces |
| `x=123` | `x=42` | Numeric values (stored as strings) |

### Parameter Mapping Pattern

Since only `x`, `y`, `z` are supported, map them to meaningful names at script start:

```dsl
# lang_compare.chatdsl
# Usage: /script lang_compare.chatdsl x=N y=TRANSLATOR z=JUDGE

if ${x} != "" then set article_num = ${x}
if ${article_num} == "" then set article_num = 1

if ${y} != "" then set model_translator = ${y}
if ${model_translator} == "" then set model_translator = "llama1"

if ${z} != "" then set model_judge = ${z}
if ${model_judge} == "" then set model_judge = "mistral_1"
```

### Examples

```bash
# All three parameters
/script compare.chatdsl x="file1.txt" y="file2.txt" z="output.txt"

# Partial parameters
script analyze.chatdsl x=5 z="results.txt"

# No parameters (use defaults)
/script default.chatdsl

# With spaces in values
/script process.chatdsl x="my document.txt" y="model name"
```

---

## Conditional Logic

### Syntax

```dsl
if <condition> then <command>
```

### Supported Operators

| Operator | Description | Example |
|----------|-------------|---------|
| `==` | Equals | `if ${x} == "yes" then` |
| `!=` | Not equals | `if ${x} != "" then` |
| `not` | Negation | `if not ${debug} then` |

### Examples

```dsl
# String equality
if ${lang} == "french" then /echo "Bonjour!"

# Not empty
if ${filename} != "" then /file ${filename}

# Negation
if not ${verbose} then /echo "Running in quiet mode"

# Combined logic
if ${x} == "1" then set flag = "enabled"
if not ${flag} then /echo "Flag not set"
```

### Important Notes

- Condition must be enclosed in `${}`
- String comparison is **literal** (case-sensitive)
- No boolean type - empty string = false, any value = true
- `then` keyword is **required**

---

## Control Flow

### Wait Command

Pause execution (useful for rate limiting):

```dsl
# Wait 2 seconds between API calls
/model gpt4
prompt 1
/save response1.txt
wait 2

/model gemma
prompt 2
/save response2.txt
```

### If-Then Structure

```dsl
# Single command
if ${debug} then /echo "Debug mode active"

# Multiple commands - each needs its own if
if ${verbose} then /echo "Starting..."
if ${verbose} then /echo "Loading files..."
```

---

## File Operations

### Main Buffer (/file)

```dsl
# Load file into main buffer (context for next prompt)
/file article.txt

# Reference in prompt (automatically prepended)
Summarize the following text:

# Clear buffer
/clearfile
```

### File Banks (/filebank1-5)

```dsl
# Load into persistent banks
/filebank1 reference.txt
/filebank2 comparison.txt

# Reference in prompts using {filebankN}
Compare these:
Source: {filebank1}
Target: {filebank2}

# Clear a bank
/filebank1 clear
```

### File Bank Strategy

| Use Case | Recommended Bank |
|----------|-----------------|
| Source text | filebank1 |
| Reference/Canonical | filebank2 |
| Translation/Generated | filebank3 |
| Comparison 1 | filebank4 |
| Comparison 2 | filebank5 |

### Save Commands

```dsl
# Save last LLM response
/save output.txt
/save "output with spaces.txt"

# Note mode - extract code blocks
/notemode on
/save generated_code.py
/notemode off
```

---

## Multiline Input

For complex prompts that span multiple lines:

```dsl
/multiline
Write a Python function that:
1. Takes a list of integers
2. Returns the sum of even numbers only
3. Handles empty lists gracefully
;;
/multiline
```

### Rules

- Start with `/multiline` on its own line
- End with `;;` on its own line, followed by `/multiline` on the next line
- Everything between is treated as a single prompt
- Variables are **expanded** within multiline blocks

### Example with Variables

```dsl
set topic = "quantum computing"
set style = "explain like I'm 5"

/multiline
${style}

Please explain ${topic} in simple terms.
;;
/multiline
```

---

## Model Management

### Switching Models

```dsl
/model gpt4
/model mistral_1
/model llama1
```

### Model Settings

```dsl
# Temperature (0.0-2.0)
/temp 0.7

# Max tokens
/maxtokens 2000

# Top-p sampling
/top_p 0.9

# Top-k sampling
/top_k 50

# Frequency penalty (-2.0 to 2.0)
/freq_penalty 0.1

# Presence penalty (-2.0 to 2.0)
/pres_penalty 0.1

# Seed
/seed 42
/seed time
/seed random 1,100
```

---

## Database Integration

### TinyDB Commands

```dsl
# Select database
/setdb knowledge_base

# Search database
/searchdb "machine learning"

# Load results into variable
/loadvar results ALL

# Log last response to database
/dblog

# List databases
/dblist

# Print database contents
/dbprint
/dbprint formatted_report.md

# Set variable directly
/setvar question "What is AI?"

# Save variable to file
/savevar results output.json
```

### Workflow Pattern

```dsl
/setdb research
/searchdb "climate change 2024"
/loadvar prior_research ALL

/system "You are a climate scientist with access to prior research."
Based on: ${prior_research}

What are the latest findings on climate change?

/dblog
```

---

## Scripting Patterns

### Pattern 1: File Comparison

```dsl
# Usage: /script compare.chatdsl x=file1 y=file2
/filebank1 ${x}
/filebank2 ${y}

Compare the contents of these two files:
File 1: {filebank1}
File 2: {filebank2}

What are the key differences?
/save comparison_results.txt
```

### Pattern 2: Multi-Model Evaluation

```dsl
# Usage: /script evaluate.chatdsl x=prompt_file y=output_dir
set prompt_file = ${x}
set output_dir = ${y}

# Model 1
/model gpt4
/prompt ${prompt_file}
/save ${output_dir}/gpt4_response.txt

# Model 2
/model clauce
/prompt ${prompt_file}
/save ${output_dir}/claude_response.txt

# Compare
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
```

### Pattern 3: Batch Processing

```dsl
# Usage: /script batch.chatdsl x=input_dir y=output_dir
set input_dir = ${x}
set output_dir = ${y}

set files = "file1.txt,file2.txt,file3.txt"

set file = "file1.txt"
/file ${input_dir}/${file}
Process this: {file}
/save ${output_dir}/${file}_processed.txt

set file = "file2.txt"
/file ${input_dir}/${file}
Process this: {file}
/save ${output_dir}/${file}_processed.txt

set file = "file3.txt"
/file ${input_dir}/${file}
Process this: {file}
/save ${output_dir}/${file}_processed.txt
```

### Pattern 4: Translation Pipeline

```dsl
# Usage: /script translate.chatdsl x=english_file y=target_lang z=output_file
set source = ${x}
set lang = ${y}
set output = ${z}

/file ${source}
set text = "{file}"

/model mistral_1
Translate to ${lang}:
${text}
/save ${output}
```

---

## Variable Substitution Deep Dive

### When Variables Are Expanded

Variables (`${name}`) are expanded in:
- ✅ Command arguments
- ✅ File paths
- ✅ Prompt text
- ✅ Multiline blocks
- ✅ Set command values
- ❌ Inside single/double quotes in set values (quotes are stripped, then value is stored literally)

### Nested Variables

```dsl
set base = "data"
set filename = "${base}/article.txt"
/file ${filename}  # Expands to: /file data/article.txt
```

### Escaping

- **Not supported**: Escape characters (\\, \$, etc.) are **disallowed** in `set` values
- **Workaround**: Use variable concatenation

```dsl
# ❌ Not allowed:
# set path = "C:\users\file.txt"

# ✅ Use instead:
set drive = "C:"
set folder = "users"
set file = "file.txt"
set path = "${drive}/${folder}/${file}"
```

---

## Debugging & Inspection

### Inspection Commands

```dsl
# Show all variables
/dump all

# Show specific variable
/dump filename

# Show memory usage
/mem

# Show current buffer
/showfile
/showfile all

# Show file bank
/filebank1 show
/filebank1 show all
```

### Trace Commands

```dsl
# Raw payload tracing
/trace rawpayload on
/trace rawpayload off

# TPS (tokens per second) tracing
/trace tps on
/trace tps off

# TPS performance tracing
/trace tpsperf on
/trace tpsperf off
```

### Echo for Debugging

```dsl
/echo "Current article: ${article_num}"
/echo "Model: ${model_translator}"
```

---

## Error Handling

### Common Issues & Solutions

| Issue | Solution |
|-------|----------|
| Variable not expanding | Check `${name}` syntax (no spaces) |
| File not found | Use `/echo` to verify path expansion |
| Multiline not ending | Ensure `;;` on its own line, then `/multiline` |
| Set value with spaces | Use double quotes: `set var = "value with spaces"` |
| Backslash in value | Not allowed - restructure path or use forward slashes |
| Command not recognized | Check for typos, `;` at end of line, or missing `/` |

### Validation Pattern

```dsl
# Check if file exists before loading
set test_file = "data.txt"

# Try to load, but no error handling in ChatDSL
# So we check if variable is set
if ${test_file} != "" then /file ${test_file}
```

---

## Performance Tips

### Rate Limiting

```dsl
# Between model calls
/model gpt4
prompt 1
/save response1.txt
wait 2  # 2 second delay

/model gpt4
prompt 2
/save response2.txt
```

### Buffer Management

```dsl
# Clear buffer between unrelated prompts
/clearfile

# To prevent context pollution
/file new_context.txt
```

### Reduce Token Usage

```dsl
# Use /codeonly to reduce verbosity
/codeonly
Write Python code to solve this problem.
/codeoff
```

---

## Complete Example: Article Comparison Script

```dsl
# compare_articles.chatdsl
# Usage: /script compare_articles.chatdsl x=article1.txt y=article2.txt z=output.txt

# Parameter mapping
if ${x} != "" then set file1 = ${x}
if ${file1} == "" then set file1 = "default1.txt"

if ${y} != "" then set file2 = ${y}
if ${file2} == "" then set file2 = "default2.txt"

if ${z} != "" then set output = ${z}
if ${output} == "" then set output = "comparison.txt"

# Load files
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

---

## Style Guide

### Variable Naming

| Convention | Example | Notes |
|------------|---------|-------|
| snake_case | `article_num`, `model_name` | ✅ Preferred |
| camelCase | `articleNum`, `modelName` | ⚠️ Works but less common |
| UPPER_CASE | `ARTICLE_NUM` | For constants |
| Single letter | `x`, `y`, `z` | For script parameters only |

### Comments

```dsl
# Full line comment
set x = 1  # Inline comment

# Section headers
# ============================================
# TRANSLATION SECTION
# ============================================
```

### Script Structure

```dsl
# 1. Header with usage
# Script: description
# Usage: /script script.chatdsl [params]

# 2. Parameter handling
if ${x} != "" then set param1 = ${x}
if ${param1} == "" then set param1 = "default"

# 3. Configuration
set base_dir = "output"
/model gpt4

# 4. Main logic
/file input.txt
process this...
/save output.txt

# 5. Cleanup (optional)
/clearfile
/echo "Done"
```

---

## Command Reference

### System Commands

| Command | Arguments | Description |
|---------|-----------|-------------|
| `/model` | alias | Switch active model |
| `/listmodels` | - | List available models |
| `/env` | [filter] | Display API keys and env vars |
| `/system` | "prompt" | Set system message |
| `/temp` | 0.0-2.0 | Temperature |
| `/maxtokens` | N | Max tokens |
| `/top_p` | 0.0-1.0 | Top-p sampling |
| `/top_k` | N | Top-k sampling |
| `/freq_penalty` | -2.0-2.0 | Frequency penalty |
| `/pres_penalty` | -2.0-2.0 | Presence penalty |
| `/seed` | N/time/random | Random seed |
| `/stream` | - | Toggle streaming |
| `/reasoning` | on/off | Toggle reasoning (NVIDIA/Qwen) |
| `/thinking` | on/off | Toggle `<think>` blocks |
| `/thoughtstyle` | none/gemma4/nanbeige | Thought formatting |

### File Commands

| Command | Arguments | Description |
|---------|-----------|-------------|
| `/file` | path | Load to main buffer |
| `/showfile` | [all] | Show buffer content |
| `/clearfile` | - | Clear buffer |
| `/filebank1-5` | path/clear/show | Manage file banks |
| `/prompt` | file | Load and execute prompt file |
| `/save` | path | Save last response |
| `/codeonly` | - | Code-only mode on |
| `/codeoff` | - | Code-only mode off |
| `/notemode` | on/off | Auto-extract code blocks |

### Scripting Commands

| Command | Arguments | Description |
|---------|-----------|-------------|
| `set` | name = value | Define variable |
| `if` | condition then cmd | Conditional execution |
| `wait` | N | Pause N seconds |
| `/script` | file [x=v y=v z=v] | Run script with params |
| `/echo` | text | Print to stdout |
| `#` | text | Comment |

### Database Commands

| Command | Arguments | Description |
|---------|-----------|-------------|
| `/setdb` | name | Select database |
| `/dblist` | - | List databases |
| `/searchdb` | "query" | Search database |
| `/dblog` | - | Log response to DB |
| `/dbprint` | [file] | Print DB contents |
| `/loadvar` | name ALL/IDs | Load search results |
| `/savevar` | name file | Save variable to file |
| `/setvar` | name value | Set variable (CLI) |

### Debug Commands

| Command | Arguments | Description |
|---------|-----------|-------------|
| `/mem` | - | Show memory usage |
| `/dump` | all/name | Dump variables |
| `/trace` | type on/off | Enable tracing |
| `/help` | - | Show help |
| `/quit` | - | Exit |

---

## BNF Grammar (Reference)

From `chatdsl_bnf.txt`:

```
<script> ::= { <script-line> }
<script-line> ::= ( <command> | <comment> | <empty-line> ) <newline>

<command> ::= <escape-command> | <script-command> | <chat-input>
<escape-command> ::= "/" <escape-command-name> [ <whitespace> <escape-command-args> ]

<script-command> ::= <set-command> | <wait-command> | <if-command>

<set-command> ::= "set" <whitespace> <variable-name> <whitespace> "=" <whitespace> <variable-value>
<wait-command> ::= "wait" <whitespace> <number>
<if-command> ::= "if" <whitespace> <condition> <whitespace> "then" <whitespace> <command>

<condition> ::= [ "not" <whitespace> ] <logical-expression>
<logical-expression> ::= <operand> [ <whitespace> <operator> <whitespace> <operand> ]
<operator> ::= "==" | "!="
<operand> ::= <string> | <variable-reference> | <number> | <identifier>

<variable-reference> ::= "${" <variable-name> "}"
<variable-name> ::= <identifier>

<chat-input> ::= <single-line-text> | <multiline-block>
<multiline-block> ::= "/multiline" <newline> { <text-content> <newline> } ";;" <newline> "/multiline"
```

---

## Limitations & Known Issues

1. **Only 3 script parameters** (x, y, z) - map to meaningful names at script start
2. **No escape characters** in `set` values - use forward slashes or restructure
3. **No native loops** - use repetition or external bash loops
4. **No arrays/lists** - use numbered variables (file1, file2, etc.)
5. **No functions** - but macros are supported with `%` syntax
6. **Case-sensitive** string comparison
7. **No floating point** in wait - use integers only

---

## Macros (Advanced)

Macros allow reusable command templates:

```dsl
# Define macro
%def compare_lang(lang, file)
/filebank1 ${file}
Translate to {lang}:
{filebank1}
/save ${lang}_translation.txt
%end

# Use macro
%compare_lang(french, input.txt)
%compare_lang(spanish, input.txt)
```

Note: Macro support requires `macro.chatdsl` in same directory.

---

## Best Practices Checklist

- [ ] Use descriptive variable names (snake_case)
- [ ] Add header comment with usage instructions
- [ ] Map x, y, z to meaningful names at script start
- [ ] Provide sensible defaults for optional parameters
- [ ] Clear buffers between unrelated operations (`/clearfile`)
- [ ] Use file banks for persistent context
- [ ] Add `wait` between rapid API calls
- [ ] Use `/codeonly` for code generation
- [ ] Include `/echo` statements for progress tracking
- [ ] Test with and without parameters
- [ ] Document required directory structure
- [ ] Quote paths that may contain spaces
- [ ] Use multiline for complex prompts

---

## Common Patterns Reference

### Parameter Defaults
```dsl
if ${x} != "" then set var = ${x}
if ${var} == "" then set var = "default"
```

### File Loading with Fallback
```dsl
if ${file} != "" then /file ${file}
```

### Conditional Model Selection
```dsl
if ${fast} then /model gemma
if not ${fast} then /model gpt4
```

### Batch Processing Template
```dsl
set files = "a.txt,b.txt,c.txt"
# Manually process each
set file = "a.txt"
# ... process ...
set file = "b.txt"
# ... process ...
```

### Comparison Workflow
```dsl
/filebank1 original.txt
/filebank2 translated.txt
Compare {filebank1} and {filebank2}
```

---

## Resources

- ** chatybot GitHub**: Full implementation and examples
- **CHATDSL_TECHNICAL_GUIDE.md**: Technical deep dive
- **chatdsl_bnf.txt**: Formal grammar specification
- **script_param_implementation.md**: Parameter passing details
- **dsl_test/**: Test scripts demonstrating all features
