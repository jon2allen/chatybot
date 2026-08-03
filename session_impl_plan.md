# Chatybot Session Persistence Implementation Plan (`session_impl_plan.md`)

This document outlines the architectural plan for implementing **Session-Based Conversation Persistence** in `Chatybot`, including automatic and explicit session naming, slash command integration, multi-language support, and agentic tool loop trajectory management.

---

## 1. Executive Summary & Goals

The goal of Session Persistence is to allow Chatybot users to save, resume, auto-name, and manage multi-turn conversation histories across interactive REPL turns and script executions.

### Key Objectives:
1. **Flexible Naming**: Support user-defined session names (`/session start <name>`) and automatic session naming (`/session auto [on|off]`).
2. **Agentic Tool Loop Awareness**: Isolate intermediate tool execution steps (`AGENTIC_LOOP`) from the primary conversation history while committing clean synthesized outcomes (or optionally recording full telemetry).
3. **Multi-Language Support**: Fully translate `/session` slash commands and keywords across all 6 supported languages (EN, ES, FR, ZH, IT, AR).
4. **Resilience & Storage Options**: Provide lightweight JSON turn persistence by default, with optional TinyDB integration (`ChatyDB`) and audit logging (`LoggingManager`).

---

## 2. Architecture & Storage Structure

Sessions are persisted under `~/.local/share/chatybot/sessions/` (or test directory during pytest runs).

```
~/.local/share/chatybot/
├── sessions/
│   ├── auto/
│   │   ├── session_20260802_223045.json
│   │   └── session_fix_recursion_bug.json
│   ├── coding_project_v2.json
│   └── refactor_parser.json
```

### Session Document Schema (`.json`):
Filenames on disk follow the strict naming convention: `<model_alias>_<timestamp>.json` (e.g. `gemini_flash_20260802_223045.json`).

```json
{
  "session_id": "gemini_flash_20260802_223045",
  "model_alias": "gemini_flash",
  "created_at": "2026-08-02T22:30:45Z",
  "updated_at": "2026-08-02T22:32:00Z",
  "first_prompt_slug": "find_all_usages_of_execute_command_list",
  "custom_name": "coding_project_v2",
  "system_message": "You are a Python engineer.",
  "turns": [
    {
      "turn_id": 1,
      "prompt": "Find all usages of execute_command_list",
      "thinking": "The user wants to locate execute_command_list. I will use grep_search...",
      "response": "Found 12 usages across chatybot_app.py and tests.",
      "agentic_loop": [
        {"tool": "grep_search", "query": "execute_command_list", "matches": 12}
      ]
    }
  ]
}
```

---

## 3. Thinking & Reasoning Token Handling (`<think>`)

Reasoning/thinking models (e.g. DeepSeek-R1, Mistral Thinking) produce `<think>...</think>` or `<thought>...</thought>` blocks. Handling these in sessions requires explicit rules:

1. **Field Separation**: Extracted `<think>` content is stored in a dedicated `"thinking"` field, keeping the main `"response"` field clean.
2. **Context Window Re-hydration**: When resuming past turns, **only `"response"`** is re-sent in LLM prompt payloads to save tokens and prevent reasoning repetition.
3. **Configuration Parameter**: `tools_config.toml` includes:
   ```toml
   [config]
   session_strip_thinking = "separate"  # Options: "separate" (default), true (strip), false (embed)
   ```
4. **Inspection**: REPL output hides thinking tokens by default; `/session show --thinking` displays full reasoning traces.

---

## 4. Command Suite & Workflow

### Slash Commands (`/session`)

| Command | Arguments | Description | Example |
| :--- | :--- | :--- | :--- |
| `/session start` | `<name>` | Clear active history & start a new user-named session (metadata `custom_name` set to `<name>`). | `/session start refactor_parser` |
| `/session auto` | `[on\|off]` | Enable/disable auto-named session logging (`<model>_<timestamp>.json`). | `/session auto on` |
| `/session use` | `<name\|id>` | Switch to or load an existing session by ID or custom name. | `/session use gemini_flash_20260802_223045` |
| `/session save` | `[name]` | Set custom display name for current session or save explicitly. | `/session save final_debug` |
| `/session show` | `[--thinking\|-t]` | Show formatted view of active session exchanges. | `/session show -t` |
| `/session export` | `<filepath.md> [--thinking\|-t]` | Export full session transcript to a Markdown file. | `/session export my_notes.md -t` |
| `/session list` | — | List saved sessions showing filename (`model_timestamp`), first prompt slug, and turn count. | `/session list` |
| `/session status` | — | Show active session ID, custom name, turn count, and file path. | `/session status` |
| `/session off` | — | Pause session recording for current session. | `/session off` |

### Session Markdown Export (`/session export <file.md>`)

The `/session export` command renders the session history into a GitHub-Flavored Markdown file (`.md`) at a user-specified file path:

* **Syntax**: `/session export <filepath.md> [--thinking|-t]`
* **Export File Structure**:

```markdown
# Session Transcript: coding_project_v2

- **Session ID**: `gemini_flash_20260802_223045`
- **Model**: `gemini_flash`
- **Created**: 2026-08-02 22:30:45 UTC
- **Total Exchanges**: 2

---

## Turn 1

### User
Find all usages of execute_command_list

### Reasoning Trace
> The user wants to locate execute_command_list. I will use grep_search...

### Assistant
Found 12 usages across chatybot_app.py and tests.

#### Tools Executed
- `grep_search(query="execute_command_list")` -> 12 matches

---

## Turn 2

### User
Change execute_command_list to handle async execution

### Assistant
Updated execute_command_list in chatybot_app.py to use await.

#### Tools Executed
- `view_file(path="chatybot_app.py")`
- `replace_file_content(TargetFile="chatybot_app.py")`
```

### Formatted Session Output (`/session show`)

Running `/session show` prints a clean, beautifully formatted transcript of the active session exchanges:

```text
================================================================================
SESSION: gemini_flash_20260802_223045 (Name: coding_project_v2)
Model: gemini_flash | Created: 2026-08-02 22:30:45 | Total Turns: 2
================================================================================

[Turn 1]
User: Find all usages of execute_command_list
Assistant: Found 12 usages across chatybot_app.py and tests.
(Tools executed: 1 -> grep_search)

--------------------------------------------------------------------------------

[Turn 2]
User: Change execute_command_list to handle async execution
Assistant: Updated execute_command_list in chatybot_app.py to use await.
(Tools executed: 2 -> view_file, replace_file_content)

================================================================================
```

When run with `--thinking` or `-t` (`/session show -t`), it expands the `<think>` block per turn:

```text
[Turn 1]
User: Find all usages of execute_command_list
Thinking:
  The user wants to locate execute_command_list. I will use grep_search...
Assistant: Found 12 usages across chatybot_app.py and tests.
(Tools executed: 1 -> grep_search)
```

### On-Disk Filename vs. `/session list` Output Format

* **Disk Filename Convention**: `<model_alias>_<YYYYMMDD_HHMMSS>.json` (e.g. `mistral_1_20260802_223045.json`).
* **Metadata Content**: Stores `first_prompt_slug` (slugified first 6–8 words of Turn 1) inside the JSON header.
* **`/session list` Display Format**:
  ```
  Available Sessions:
    1. mistral_1_20260802_223045.json
       ├─ Prompt: "find all usages of execute_command_list..."
       ├─ Custom Name: "refactor_parser"
       └─ Turns: 4 exchanges (Updated: 2026-08-02 22:32)
    
    2. gemini_flash_20260802_221510.json
       ├─ Prompt: "explain difference between async and sync..."
       └─ Turns: 1 exchange (Updated: 2026-08-02 22:15)
  ```

---

## 4. Agentic Loop Integration

During an autonomous tool calling loop (`in_tool_loop = True`):

1. **Intermediate Turns**: Executed inside `AGENTIC_LOOP` array variable and temporary prompt context.
2. **Turn Completion**: When `run_tool_loop` finishes:
   * **Clean Mode (Default)**: Replaces `self.chat_history[-1]` with `(initial_prompt, final_natural_language_response)` and appends a single clean turn to the session JSON file.
   * **Telemetry Mode (`--session-type telemetry`)**: Preserves intermediate `agentic_loop` tool call steps inside the turn record for full trajectory replay.

---

## 5. Configuration & i18n Mappings

### `tools_config.toml` Settings
```toml
[config]
session_mode = "auto"              # Options: "off", "on", "auto"
session_type = "clean"             # Options: "clean", "telemetry", "hybrid"
session_dir = "~/.local/share/chatybot/sessions"
session_auto_save = true
```

### Multi-Language Command Verb Translations (`translations.json`)
* **English**: `/session`
* **Spanish**: `/sesion`, `/session`
* **French**: `/session`
* **Chinese**: `/会话`
* **Italian**: `/sessione`
* **Arabic**: `/جلسة`

---

## 6. Implementation Checklist & File Touches

- [ ] **`src/chatybot/chatybot_app.py`**:
  - Add session attributes (`active_session_name`, `session_mode`, `session_type`, `session_dir`).
  - Implement `handle_session_command()`, `save_session_turn()`, and `load_session()`.
  - Integrate turn auto-save at end of `run_prompt()` and `run_tool_loop()`.
- [ ] **`src/chatybot/buffer_manager.py`**:
  - Register `SESSION_NAME` and `SESSION_ENABLE` in `protected_vars`.
- [ ] **`src/chatybot/tools_config.toml`**:
  - Add default `[config]` parameters for session persistence.
- [ ] **`src/chatybot/translations.json`**:
  - Register `/session` aliases and subcommand keywords across EN, ES, FR, ZH, IT, AR.
- [ ] **`src/chatybot/chaty_help.py`**:
  - Add structured `/session` command documentation in the help catalog.
- [ ] **Unit Tests (`test/test_session.py`)**:
  - Test `/session start`, `/session auto`, `/session use`, `/session save`, auto-naming, and agentic loop turn commits.
