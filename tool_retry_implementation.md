# Post-Turn Tool Rescue: `/tool retry`

## 1. Overview & Problem Statement

During conversational sessions with LLMs, models occasionally output malformed, unrecognized, or raw text tool invocations instead of executing them cleanly (e.g. XML `<dots_function_call>`, `<invoke>`, malformed JSON, or markdown code fences like `write_file`). In other cases, a model attempts to call a tool with a slight typo in the tool name or missing required parameters.

Previously, recovering from this required re-prompting the LLM or manually copying the payload.

The **`/tool retry`** feature provides deterministic, post-turn rescue capabilities directly from the last assistant completion (`${LAST_COMPLETION}`). It parses candidate tool invocations from the completion and allows you to edit, interactively fix, or directly execute the tool without consuming additional AI tokens.

---

## 2. Command Syntax

```bash
/tool retry [edit|fix|run]
```

- **/tool retry edit** *(Default)*:
  Opens your configured `$EDITOR` (or `$VISUAL`, or `vi` / `notepad`) with the extracted tool payload formatted as clean JSON. The top of the buffer contains comment headers (`#`) documenting the tool's expected schema and parameter types. If the tool name is invalid or unrecognized, a prominent warning header is inserted listing all currently enabled tools.
- **/tool retry fix**:
  Runs an interactive CLI wizard directly in the terminal to inspect parameter fields, fill in missing values, or correct the tool name.
- **/tool retry run**:
  Attempts to parse and execute the candidate tool immediately if the syntax and tool name are already valid.

---

## 3. How It Works

### Step 1: Candidate Extraction
When `/tool retry` is executed, Chatybot inspects the last assistant completion in the current session (`app.session.last_assistant_completion()`). It uses deterministic regex extractors to harvest tool calls from:
1. Standard JSON tool call objects (`{"tool": "...", "parameters": {...}}`).
2. XML tags (`<invoke name="...">`, `<dots_function_call>`, `<tool_call>`, `<function_call>`).
3. Markdown fenced code blocks (e.g., ```` ```bash ````, ```` ```chatdsl ````, ```` ```python ````).
4. Raw shell commands or function-style syntax (e.g., `write_file(path="...", content="...")`).

### Step 2: Buffer Construction with Schema Comments
When opening `$EDITOR` (`/tool retry edit`), Chatybot dynamically inspects the available tools in `app.get_available_tools()` and builds a template.

#### Case A: Recognized Tool Name
If the candidate tool name exists (e.g., `write_file`), the buffer displays the tool description and expected parameter schema:

```json
# Tool: write_file
# Description: Write content to a file.
# Expected Parameters:
#   - path (string): [Required] Destination file path
#   - content (string): [Required] Text content to write
#
# Edit the JSON payload below. Lines starting with '#' are ignored.

{
  "tool": "write_file",
  "parameters": {
    "path": "sample.py",
    "content": "print('hello world')"
  }
}
```

#### Case B: Unrecognized / Invalid Tool Name
If the tool name is unknown or invalid (e.g. `create_file` or `unknown_tool`), Chatybot places a prominent warning banner and lists all enabled tools with short descriptions for quick selection. The `"tool": "CHANGE_ME"` field is placed on the first non-comment line for immediate editing:

```json
# ==============================================================================
# WARNING: 'create_file' is NOT a valid tool name!
# ==============================================================================
# Please change the "tool" field below to one of the valid enabled tools:
#
#   - bash: Run a bash command or script in a subshell
#   - read_file: Read the contents of a file
#   - write_file: Write content to a file
#   - list_files: List files in a directory
#   - search_code: Search codebase for matching strings or patterns
#
# Lines starting with '#' are ignored upon save.
# ==============================================================================

{
  "tool": "CHANGE_ME",
  "parameters": {
    "path": "test.txt",
    "content": "example"
  }
}
```

### Step 3: Execution and Session History
Upon saving and exiting the editor (or confirming in interactive mode):
1. Chatybot strips all comment lines starting with `#` and parses the JSON.
2. It validates the tool name against `app.get_available_tools()`.
3. It dispatches the tool call through `app.dispatch_tool(name, params)`.
4. The tool execution result is printed to the terminal and recorded in session history.

---

## 4. Interaction with Session History & `/save`

Since the raw completion is preserved as the turn's last completion:
- If you need to inspect or archive the raw turn before editing, you can use `/save <filename>` or `/tool history` to review the unmodified exchange.
- Running `/tool retry` does not overwrite the assistant's previous message text; it adds the executed tool call and its output into the conversation stream.

---

## 5. Live Mock Injector: `/tool inject`

To facilitate local offline testing, edge-case debugging, and test automation without incurring LLM inference costs or tokens, the **`/tool inject`** command injects a synthetic or malformed completion directly into `${LAST_COMPLETION}` and `chat_history`.

### Syntax

```bash
/tool inject <payload text>
/tool inject file=<path_to_file>
```

### Examples

```bash
# Inject literal XML completion:
/tool inject <invoke name="write_file"><parameter name="path">test.py</parameter><parameter name="content">print('hello')</parameter></invoke>

# Inject from an existing crash or test fixture file:
/tool inject file=crashes/malformed_turn.txt
/tool inject file="test/fixtures/dots_broken_turn.txt"

# Immediately test rescue in $EDITOR:
/tool retry edit
```

---

## 6. Summary of Files Modified & Added

- **`src/chatybot/commands/tools.py`**:
  - `_extract_retry_candidate()`: Deterministic regex parser for tool call patterns (JSON, XML, markdown code blocks).
  - `_build_tool_retry_buffer()`: Generates editor buffer with schema documentation and invalid tool warnings.
  - `_handle_tool_retry()`: Controller for `edit`, `fix`, and `run` sub-actions.
  - `_handle_tool_inject()`: Seeds mock assistant completion into `${LAST_COMPLETION}` and session history from text or `file=<path>`.
- **`src/chatybot/chaty_help.py`**:
  - Added documentation and examples for `/tool retry [edit|fix|run]` and `/tool inject [file=<path>|<payload>]`.
- **`test/test_tool_retry.py`**:
  - Test suite covering candidate extraction, buffer generation, warning headers, inject commands, and editor/CLI execution flows.

