# ChatDSL Technical Guide & Tutorial

**ChatDSL** (Chat Domain-Specific Language) is the powerful scripting language behind **Chatybot**. It allows you to automate complex interactions with Large Language Models (LLMs), manage context through sophisticated buffer systems, and integrate persistent data from TinyDB into your AI workflows.

---

## Table of Contents
1. [Core Concepts](#core-concepts)
2. [Language Specification](#language-specification)
3. [Tutorial Checklist](#tutorial-checklist)
4. [LLM Comparison Workflows](#llm-comparison-workflows)
5. [Database Integration Patterns](#database-integration-patterns)
6. [Best Practices](#best-practices)
7. [Full Command Reference](#full-command-reference)

---

## Core Concepts

### Line-Based Execution
ChatDSL scripts are executed via a robust lexical state machine. Each command is either a **Script Command** (set, if, wait), an **Escape Command** (starting with `/`), or **Chat Input** (to be sent to the LLM).

### The Buffer System
Chatybot utilizes a dual-layer context system:
- **Main Buffer (`/file`)**: A temporary storage for text that is prepended to the *next* chat completion. Use this for the primary document you are currently discussing.
- **File Banks (`/filebank1-5`)**: Five persistent slots (1-5) that hold text in memory. These are referenced in prompts using `{filebankN}`. They persist across multiple LLM calls until cleared or overwritten.

### Script Variables
Variables are defined using `set name = value`. They are injected into commands, file paths, and prompts using the `${name}` syntax.

---

## Language Specification

### Comments
Comments can be full-line or inline. Use `#` to document your logic.
```dsl
# This is a full-line comment
set x = 1  # This is an inline comment
```

### Variables
- **Definition**: `set var_name = "value"`
- **Substitution**: `${var_name}`
- **Multiline Support**: Variable values can span multiple lines if wrapped in quotes (`"` or `'`).
- **Safety**: Escape characters (`\`) are disallowed inside variable values to ensure prompt stability.

### Control Flow
- **Conditional**: `if ${condition} then /command`
- **Comparison**: `if ${var1} == "expected" then /echo Match Found`
- **Negation**: `if not ${condition} then /command` or `if ${var1} != "value" then ...`
- **Delay**: `wait <seconds>` (useful for API rate limit management)

### Chat Input
Any line that does not start with a command reserved word (`set`, `if`, `wait`, `#`) or an escape character (`/`) is treated as a prompt and sent to the active LLM.

#### Multi-line Blocks
For complex prompts, use the `/multiline` toggle:
```dsl
/multiline
Please summarize the following points:
1. Economic impact
2. Social changes
;;
/multiline
```

---

## Tutorial Checklist

### Level 1: Your First Automation
This script switches to a model, sets a system role, and asks a simple question.
```dsl
/model gpt4
/system "You are a concise technical writer."
What are the three tiers of a modern web application?
/save web_tiers.txt
```

### Level 2: Contextual Analysis
Load a file into the context buffer and ask the AI to process it.
```dsl
set file_path = "./data/api_specs.json"
/file ${file_path}
Identify all endpoint security vulnerabilities in this file.
/save vulnerabilities_report.txt
```

### Level 3: Advanced File Banks
Using multiple file banks and parameterized scripts:
```dsl
# Usage: /script analyze.chatdsl x="original_v1.py" y="refactored_v2.py"
/filebank1 ${x}
/filebank2 ${y}

Analyze the differences between {filebank1} and {filebank2}.
List all performance optimizations made in the second version.
/save refactor_analysis.txt
```

---

## LLM Comparison Workflows

One of Chatybot's most powerful use cases is comparing how different models handle the same task.

### The Comparison Pattern
1.  **Define Question**: Generate or load a set of questions into a file.
2.  **Iterate Models**: Switch models and run the same prompt from the file.
3.  **Store Results**: Save each model's response to a unique file.
4.  **Aggregate**: Load all results into File Banks.
5.  **Analyze**: Prompt a "Judge" model (e.g., a high-reasoning model) to compare the contents of the file banks.

### Sample Script Fragment
```dsl
# Setup
set question_file = "questions.txt"
set results1 = "response_model_a.txt"
set results2 = "response_model_b.txt"

# Model A test
/model mistral_1
/prompt ${question_file}
/save ${results1}

# Model B test
/model gemma_3
/prompt ${question_file}
/save ${results2}

# The Comparison
/filebank1 ${results1}
/filebank2 ${results2}

/model o1_pro
/multiline
Compare the following two responses for technical accuracy:
Model A: {filebank1}
Model B: {filebank2}
Who provided a better explanation and why?
;;
/save final_comparison.txt
```

---

## Database Integration Patterns

Persistent knowledge management via TinyDB.

### The Research-Log Pattern
Use this to find existing data and record new insights.
```dsl
/setdb project_archive
/searchdb "encryption standards 2024"
/loadvar history ALL

/system "You are a security auditor."
Based on our previous research: ${history}
What is the recommended transition plan for RSA-2048?

/dblog  # Saves the AI's response back to project_archive.json
```

---

## Best Practices

1.  **Variable Hygiene**: Use underscores in variable names (`source_file`) rather than camelCase.
2.  **State Management**: Always `/clearfile` before loading new context to prevent context "pollution" if your script is long.
3.  **Wait for APIs**: Use `wait 1` or `wait 2` between intense bursts of activity to avoid hitting provider rate limits.
4.  **Quote Paths**: If your file paths might contain variables that could expand to have spaces, use quotes: `/save "${output_dir}/${filename}.txt"`.
5.  **Debug Visibility**: Use `/dump all` and `/mem` at the start or end of complex scripts to verify that your variables and buffers are loaded correctly.

---

## Full Command Reference

### Scripting Commands
| Command | Usage |
|---------|-------|
| `set` | Define a script variable (supports multiline). |
| `if` | Conditional execution (supports `==`, `!=`, `not`). |
| `wait` | Pause execution for N seconds. |
| `/echo` | Print text to stdout with variable expansion. |
| `/script`| Run a script file (supports `x="val"` parameters). |
| `#` | Line comment (supports inline comments). |

### System & Model Control
| Command | Usage |
|---------|-------|
| `/model` | Switch active model alias. |
| `/listmodels` | Show all available models. |
| `/env` | Display defined API keys and environment variables (`set \| grep -i api`). |
| `/system` | Update the system prompt. |
| `/temp` | Set temperature (0.0 - 2.0). |
| `/maxtokens`| Set completion token limit. |
| `/streaming`| Toggle real-time text output. |
| `/reasoning`| Toggle internal "thinking" phases for support models. |
| `/thinking` | Toggle visibility of `<think>` and `<thought>` blocks. |

### File & Buffer Management
| Command | Usage |
|---------|-------|
| `/file` | Load a file into the Chat context buffer. |
| `/filebankN`| Load a file into Bank 1-5. |
| `/clearfile`| Clear the main context buffer. |
| `/showfile` | Print the current buffer (first 100 chars or 'all'). |
| `/prompt` | Load a prompt from a file and execute it. |
| `/save` | Write the last LLM response to a file (supports spaces). |
| `/codeonly` | Tell the LLM to skip conversational filler. |
| `/notemode` | Automatically extract code blocks to separate files on save. |

### Database Commands
| Command | Usage |
|---------|-------|
| `/setdb` | Select active TinyDB storage. |
| `/dblist` | List all databases. |
| `/searchdb` | Search content in current DB. |
| `/dblog` | Log last response to DB. |
| `/loadvar` | Map search results/IDs to a variable. |
| `/savevar` | Export a variable's content to a file. |
| `/setvar` | Hard-code a variable value (CLI version). |
| `/mem` | Show memory size of buffers and variables. |
| `/dump` | Print the content of a specific variable or 'all'. |
