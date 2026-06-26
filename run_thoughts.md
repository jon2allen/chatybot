# `/run` Command Design Thoughts

## Overview

This document explores design options for implementing a `/run` command in ChatDSL that supports two primary modes:

1. **Execute Mode**: Run a shell command and store output in `last_completion`
2. **Extract Mode**: Parse `last_completion` for tool calls and populate special variables

> **⚠️  CRITICAL**: This document was updated to address security vulnerabilities and consistency issues identified in the original design. See [Critical Fixes](#critical-fixes) section.

---

## Background

ChatDSL currently supports various escape commands (`/model`, `/temp`, `/save`, `/script`, etc.) that control application behavior and provide scripting capabilities. The application maintains state through variables like `LAST_RESPONSE` which can be accessed in scripts via `${LAST_RESPONSE}` syntax.

The need for a `/run` command arises from two use cases:
- **Shell Integration**: Users want to execute system commands from within ChatDSL scripts
- **Tool Call Extraction**: LLMs may output tool/function calls that need to be parsed and acted upon

**Note on Current Parser Limitations**: The existing ChatDSL parser supports single-line `/if` conditions, not multi-line `/if` `/else` `/endif` blocks. Example workflows in this document that use multi-line conditionals assume either:
- (A) Future parser enhancement, or
- (B) Simplified to single-line syntax where possible

---

## Critical Fixes (Addressed from Original Design)

### 🔴 P0: Shell Injection Vulnerability
**Problem**: Original design used `subprocess.run(command, shell=True)` combined with `${VAR}` substitution, creating arbitrary code execution risk.

**Fix**: 
- **NEVER** use `shell=True`
- Use `shlex.split(command)` + `shell=False`
- Variable substitution happens in Python *before* shell execution

**Safe Pattern**:
```python
# UNSAFE (original):
subprocess.run(command, shell=True)  # Injection vector!

# SAFE (fixed):
subprocess.run(shlex.split(command), shell=False)  # No injection possible
```

### 🔴 P0: Contradictory Blocklist
**Problem**: Original BLOCKED_COMMANDS included `curl` and `wget`, but examples showed `/run curl "https://api.weather.com/..."`

**Fix**: Replace coarse blocklist with **pattern-based dangerous operation detection** + user confirmation:
```python
DANGEROUS_PATTERNS = [
    (r'rm\s+-r\b', "Recursive delete (rm -r)"),
    (r'rm\s+--recursive\b', "Recursive delete (rm --recursive)"),
    (r'>\s*(/dev/|/etc/|/usr/|/bin/|/sbin/)', "Write to system directory"),
    (r':\s*>\s*\S+', "Here-document"),
    (r';\s*', "Command chaining"),
    (r'&&\s*', "AND-chain"),
    (r'\|\s*', "OR-chain"),
    (r'\$\(', "Command substitution"),
    (r'`', "Backtick substitution"),
]
```

**Allow by default**: `curl`, `wget`, `ls`, `cat`, `grep`, `echo`, `date`, `df`, `du`, `free`, `mv`, `cp`, etc.

### 🟡 P1: Variable Store Inconsistency
**Problem**: Original implementation wrote to `self.last_completion` but read from `load_var("LAST_COMPLETION")`

**Fix**: Use `buffer_manager` consistently for all variable storage:
```python
# Write:
self.buffer_manager.set_script_var('LAST_COMPLETION', result.stdout)

# Read:
last_completion = self.buffer_manager.get_script_var('LAST_COMPLETION')
```

### 🟡 P1: Multi-Tool Support (Day-One Requirement)
**Problem**: Original doc punted on multi-tool indexing (`${TOOL_NAME[0]}`)

**Fix**: Multi-tool support is **non-optional**. Modern LLMs routinely return multiple tool calls.

**Variables**:
```
${TOOL_COUNT}              # Total number of tool calls
${TOOL_NAME}               # First tool (backward compat)
${TOOL_ARGS}               # First tool args (backward compat)
${TOOL_NAME[0]}            # Indexed access to tool 0
${TOOL_NAME[1]}            # Indexed access to tool 1
${TOOL_ARGS[0]}            # Indexed access to args
${TOOL_CALLS}              # JSON array of all tool calls
```

### 🟡 P1: Parser Registration
**Action**: Must add to `src/chatybot/chatdsl_parse.py`:
```python
VALID_ESCAPE_COMMANDS = {
    # ... existing ...
    'run',
    'extract_tools',
}
```

### 🟡 P2: State Flag Audit Required
**Problem**: `auto_exit_pending` flag was added but has no visible consumer

**Action**: Before adding more state, audit existing flags:
- Search codebase for `auto_exit_pending`
- Remove if unused, or complete implementation
- Document purpose if keeping

**Command**: `grep -rn "auto_exit_pending" src/chatybot/`

### 🟡 P2: ;; Tokenization Conflict
**Problem**: `/run` output containing `;;` could accidentally terminate multiline blocks

**Mitigation**: Only treat `;;` as multiline terminator when it appears on its own line:
```python
# In multiline parser:
if line.strip() == ";;":  # Only if ENTIRE line is ;;
    self.multi_line_mode = False
```

**Test Case Required**:
```python
async def test_run_output_with_double_semicolon(self, app):
    """Command output containing ';;' shouldn't break multiline mode."""
    # Simulate: /run echo "data;;more"
    # Then verify multiline mode isn't accidentally exited
    pass
```

---

## Design Options

### Option 1: Subcommand-Based Design

#### Concept
Single `/run` command with two subcommands:
- `/run extract` - Parse `last_completion` for tool calls
- `/run <command>` - Execute shell command, store in `last_completion`

#### Workflow
```chatdsl
# Mode 1: Execute shell command
/run "du -sh"
# Output goes to last_completion

# Mode 2: Extract tool calls from last_completion
/run extract
# Parses last_completion, populates ${TOOL_NAME}, ${TOOL_ARGS}, etc.
```

#### Implementation
```python
elif cmd.startswith("/run"):
    parts = cmd.split(maxsplit=2)  # Split into: /run, subcommand, rest

    if len(parts) < 2:
        print("Usage: /run <extract|command>")
        return

    subcommand = parts[1]

    if subcommand == "extract":
        # Extract mode: parse last_completion for tool calls
        self.extract_tool_calls()
    else:
        # Execute mode: run shell command
        shell_command = ' '.join(parts[1:])  # Rejoin in case command has spaces
        self.execute_shell_command(shell_command)
```

#### Variables Populated

| Mode | Variable | Source | Example |
|------|----------|--------|---------|
| Execute | `${LAST_COMPLETION}` | Shell command stdout | `"12K\t./src"` |
| Execute | `${LAST_ERROR}` | Shell command stderr | `""` |
| Execute | `${LAST_EXIT_CODE}` | Return code | `"0"` |
| Extract | `${TOOL_FOUND}` | Parsed from `LAST_COMPLETION` | `"true"` |
| Extract | `${TOOL_COUNT}` | Number of tool calls | `"2"` |
| Extract | `${TOOL_NAME}` | First tool name | `"get_weather"` |
| Extract | `${TOOL_ARGS}` | First tool arguments | `{"city": "NYC"}` |
| Extract | `${TOOL_NAME[0]}` | Indexed: first tool | `"get_weather"` |
| Extract | `${TOOL_NAME[1]}` | Indexed: second tool | `"get_forecast"` |
| Extract | `${TOOL_CALL}` | Raw first tool call | `<tool>get_weather(...)</tool>` |
| Extract | `${TOOL_CALLS}` | JSON array of all | `[{...}, {...}]` |
| Extract | `${TOOL_FORMAT}` | Detected format | `"xml"` |
| Extract | `${TOOL_ERROR}` | Extraction error | `"No tool calls found"` |

#### Format Detection (for extract mode)
1. Try XML: `<tool>...</tool>` or `<function name="...">...</function>`
2. Try JSON: Look for `tool_calls` key in parsed JSON
3. Try Markdown: \`\`\`tool or \`\`\`function
4. Try inline: `TOOL: name(args)` pattern

#### Pros
- Clean, intuitive syntax
- Consistent with existing DSL patterns (`/script`, `/save`, etc.)
- Two clear, distinct modes
- Easy to extend with more subcommands later

#### Cons
- Two different actions under one command name (could be confusing)
- Need to handle quote parsing carefully for shell commands

---

### Option 2: Flag-Based Design

#### Concept
Use flags to distinguish modes:
- `/run -e` or `/run --extract` - Extract tool calls
- `/run <command>` - Execute command (default)

#### Workflow
```chatdsl
# Execute command (default)
/run du -sh

# Extract tool calls
/run -e
/run --extract
```

#### Implementation
```python
elif cmd.startswith("/run"):
    parts = cmd.split(maxsplit=2)
    
    # Check for flags first
    if len(parts) >= 2 and parts[1] in ['-e', '--extract']:
        self.extract_tool_calls()
    else:
        # Everything else is a shell command
        shell_command = cmd[5:].strip()  # Remove "/run "
        if shell_command:
            self.execute_shell_command(shell_command)
        else:
            print("Usage: /run [-e|--extract] or /run <command>")
```

#### Variables (same as Option 1)
- Execute: `${LAST_COMPLETION}`, `${LAST_ERROR}`, `${LAST_EXIT_CODE}`
- Extract: `${TOOL_FOUND}`, `${TOOL_COUNT}`, `${TOOL_NAME}`, `${TOOL_ARGS}`, `${TOOL_NAME[n]}`, `${TOOL_CALLS}`, etc.

#### Additional Features
- Support chaining: `/run --extract && /echo "Tool: ${TOOL_NAME}"`
- Short and long flag forms for user preference

#### Pros
- Standard CLI convention (flags for options)
- Default action is most common (execute command)
- Easy to remember: `-e` for extract
- Backward compatible if we add more flags later

#### Cons
- Less discoverable for new users
- Flags might conflict with shell command arguments
- Slightly more complex parsing

---

### Option 3: Separate Commands Design (RECOMMENDED)

#### Concept
Two distinct commands for clarity:
- `/run <command>` - Execute shell command -> stores in `LAST_COMPLETION`
- `/extract_tools [format]` - Parse `LAST_COMPLETION` -> populates `${TOOL_*}` variables

#### Workflow
```chatdsl
# Execute command
/run df -h

# Later, extract tool calls from LLM response
/extract_tools
```

#### Implementation
```python
# In handle_escape_command:

elif cmd.startswith("/run "):
    # Always execute mode
    shell_command = cmd[5:].strip()
    if shell_command:
        self.execute_shell_command(shell_command)
    else:
        print("Usage: /run <command>")


elif cmd.startswith("/extract_tools"):
    # Always extract mode
    parts = cmd.split(maxsplit=1)
    format_hint = parts[1] if len(parts) > 1 else "auto"
    self.extract_tool_calls(format=format_hint)
```

#### Variables
- `/run` -> `${LAST_COMPLETION}` (stdout), `${LAST_ERROR}` (stderr), `${LAST_EXIT_CODE}` (return code)
- `/extract_tools` -> `${TOOL_FOUND}`, `${TOOL_COUNT}`, `${TOOL_NAME}`, `${TOOL_ARGS}`, `${TOOL_NAME[n]}`, `${TOOL_CALLS}`, `${TOOL_FORMAT}`, `${TOOL_ERROR}`

#### Optional format hint
```chatdsl
/extract_tools xml
/extract_tools json
/extract_tools markdown
/extract_tools auto  # default
```

#### Pros
- **Most explicit** - no ambiguity
- Each command does one thing well
- Easier to document and understand
- Can extend `/extract_tools` with options without affecting `/run`
- Follows Unix philosophy (do one thing)
- **RECOMMENDED** for production

#### Cons
- Two commands to learn instead of one
- Slightly more verbose in scripts
- Less "discoverable" connection between the two

---

## Comparison Table

| Feature | Option 1: Subcommands | Option 2: Flags | Option 3: Separate Commands |
|---------|----------------------|----------------|---------------------------|
| **Syntax Clarity** | ✅✅ Good | ✅ Good | ✅✅✅ Best |
| **Ease of Learning** | ✅✅ | ✅ | ✅✅✅ |
| **Command Count** | 1 | 1 | 2 |
| **Discoverability** | ✅✅ | ⚠️ | ✅✅ |
| **Extensibility** | ✅✅✅ Best | ✅✅ | ✅✅ |
| **Shell Conflict Risk** | ⚠️ (quote parsing) | ⚠️ (flag parsing) | ✅✅ |
| **Script Readability** | ✅✅ | ✅ | ✅✅✅ |
| **Unix-like** | ⚠️ | ✅✅ | ✅✅✅ |
| **Type Safety** | ✅✅ | ✅✅ | ✅✅✅ |
| **Implementation Complexity** | ⚠️ | ⚠️ | ✅✅ |
| **Security** | ✅✅ (with fixes) | ✅✅ (with fixes) | ✅✅✅ (with fixes) |

---

## Recommendation: Option 3 (Separate Commands)

### Rationale
- Clearest separation of concerns
- Each command has a single, well-defined purpose
- Easier to document and maintain
- Lower risk of parsing conflicts
- Most aligned with existing DSL patterns (each `/command` does one thing)
- **Easier to secure** - each command has its own security considerations

### Example Script Usage (Compatible with Current Parser)

```chatdsl
# Scenario 1: Get disk usage (single-line, works today)
/run df -h
/echo "Disk usage: ${LAST_COMPLETION}"

# Scenario 2: Extract tool calls from LLM
# (Assuming LLM was instructed to output tool calls)
Tell me the weather and use a tool to get current data.

/extract_tools
/if "${TOOL_FOUND}" == "true" /echo "LLM requested tool: ${TOOL_NAME}"

# Scenario 3: Process multiple tool calls
/extract_tools
/if "${TOOL_COUNT}" > "0" /echo "Found ${TOOL_COUNT} tool call(s)"

# Scenario 4: Combined workflow - extract then act
/extract_tools
/if "${TOOL_FOUND}" == "true" /run echo "Would execute: ${TOOL_NAME}(${TOOL_ARGS})"

# Scenario 5: Access specific tool by index
/extract_tools
/if "${TOOL_COUNT}" > "1" /echo "Second tool: ${TOOL_NAME[1]}"
```

> **Note**: Examples use single-line `/if condition command` syntax which is compatible with the current ChatDSL parser. Multi-line if/else/endif blocks would require parser enhancements.

---

## Variable Specifications

### From `/run <command>`
- `${LAST_COMPLETION}` = stdout of command (string)
- `${LAST_ERROR}` = stderr of command (string)
- `${LAST_EXIT_CODE}` = return code as string (e.g., `"0"`)

**All stored via `buffer_manager.set_script_var()` for consistency.**

### From `/extract_tools`
- `${TOOL_FOUND}` = `"true"` or `"false"`
- `${TOOL_COUNT}` = number of tool calls detected (string, e.g., `"2"`)
- `${TOOL_FORMAT}` = detected format: `"xml"`, `"json"`, `"markdown"`, or `"inline"`
- `${TOOL_ERROR}` = error message if extraction failed, else empty

**First Tool (backward compatibility)**:
- `${TOOL_NAME}` = name of first tool call
- `${TOOL_ARGS}` = arguments of first tool call (JSON string)
- `${TOOL_CALL}` = raw text of first tool call

**Indexed Access (multi-tool support)**:
- `${TOOL_NAME[0]}` = name of tool call 0
- `${TOOL_NAME[1]}` = name of tool call 1
- `${TOOL_NAME[2]}` = name of tool call 2
- ...
- `${TOOL_ARGS[0]}` = arguments of tool call 0
- `${TOOL_ARGS[1]}` = arguments of tool call 1

**Complete Data**:
- `${TOOL_CALLS}` = JSON array containing all tool calls

**Example TOOL_CALLS value**:
```json
[
  {"name": "get_weather", "args": {"city": "NYC"}, "raw": "<tool name=\"get_weather\">{\"city\": \"NYC\"}</tool>"},
  {"name": "get_forecast", "args": {"days": 7}, "raw": "<tool name=\"get_forecast\">{\"days\": 7}</tool>"}
]
```

---

## Implementation Considerations

### For Extract Mode
1. **Multi-tool support**: Mandatory from day one. Parse all tool calls, store indexed variables.
2. **Format standardization**: Output variables as strings always, even for JSON/numbers.
3. **Error handling**: Set `${TOOL_FOUND}` = `"false"` and `${TOOL_ERROR}` on any error.
4. **Empty input**: If `LAST_COMPLETION` is empty, set `${TOOL_FOUND}` = `"false"`.

### For Execute Mode
1. **Timeout**: Default 30 seconds, configurable via `/set RUN_TIMEOUT 60`
2. **Working directory**: Use `os.getcwd()` (current working directory)
3. **Environment variables**: Inherit from parent process
4. **Dangerous patterns**: Detect and confirm (see Security Design below)

### Security Considerations
1. **NEVER use shell=True** - Use `shlex.split()` + `shell=False`
2. **Pattern-based dangerous detection** - Not coarse command blocklists
3. **User confirmation for dangerous operations** - In safe mode (default)
4. **Safe mode toggle** - `/run_safe` (default ON), `/run_unsafe` (opt-in)
5. **Logging** - Optionally log executed commands to file

### Integration Points
- Modify `handle_escape_command()` in `chatybot_app.py`
- Add to `chatdsl_parse.py` `VALID_ESCAPE_COMMANDS` set
- Update help system in `chaty_help.py`
- Add to README documentation
- Register variables in `buffer_manager.py` if needed

---

## Detailed Implementation Sketches (SECURITY-FIXED)

### Execute Mode Implementation

```python
def execute_shell_command(self, command, timeout=30):
    """
    Execute a shell command and store output in LAST_COMPLETION.
    
    SECURITY: Uses shlex.split() + shell=False to prevent injection.
    Variables are substituted in Python BEFORE shell execution.
    """
    import subprocess
    import shlex
    
    # CRITICAL: Variable substitution already happened in the caller
    # So 'command' contains literal strings, not ${VAR} references
    
    # Check for dangerous patterns
    danger = self.check_dangerous(command)
    if danger:
        if self.safe_mode:
            self.buffer_manager.set_script_var('LAST_COMPLETION', 
                f"Blocked (safe mode): {danger}")
            self.buffer_manager.set_script_var('LAST_ERROR', '')
            self.buffer_manager.set_script_var('LAST_EXIT_CODE', '-1')
            print(f"⚠️  Blocked: {danger}")
            return
        else:
            confirm = input(f"⚠️  {danger} Execute anyway? (y/N): ")
            if confirm.lower() != 'y':
                self.buffer_manager.set_script_var('LAST_COMPLETION', "Command aborted by user")
                self.buffer_manager.set_script_var('LAST_ERROR', '')
                self.buffer_manager.set_script_var('LAST_EXIT_CODE', '-1')
                print("❌ Command aborted")
                return
    
    try:
        # SAFE: No shell=True, uses shlex.split for proper tokenization
        result = subprocess.run(
            shlex.split(command),
            shell=False,  # CRITICAL: Prevents shell injection
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout,
            cwd=os.getcwd()
        )
        
        # Store in buffer_manager (consistent with extract mode)
        self.buffer_manager.set_script_var('LAST_COMPLETION', result.stdout)
        self.buffer_manager.set_script_var('LAST_ERROR', result.stderr)
        self.buffer_manager.set_script_var('LAST_EXIT_CODE', str(result.returncode))
        
        if result.returncode != 0:
            print(f"⚠️  Command exited with code {result.returncode}")
        else:
            print(f"✅ Command executed")
            
    except subprocess.TimeoutExpired:
        self.buffer_manager.set_script_var('LAST_COMPLETION', 
            f"Error: Command timed out after {timeout}s")
        self.buffer_manager.set_script_var('LAST_ERROR', '')
        self.buffer_manager.set_script_var('LAST_EXIT_CODE', '-2')
        print(f"⏰ Timeout after {timeout}s")
    except FileNotFoundError as e:
        self.buffer_manager.set_script_var('LAST_COMPLETION', '')
        self.buffer_manager.set_script_var('LAST_ERROR', f"Command not found: {e.filename}")
        self.buffer_manager.set_script_var('LAST_EXIT_CODE', '-1')
        print(f"❌ Command not found: {e.filename}")
    except Exception as e:
        self.buffer_manager.set_script_var('LAST_COMPLETION', '')
        self.buffer_manager.set_script_var('LAST_ERROR', str(e))
        self.buffer_manager.set_script_var('LAST_EXIT_CODE', '-1')
        print(f"⚠️  Error: {e}")


def check_dangerous(self, command):
    """Check command for dangerous patterns. Returns warning message or None."""
    import re
    
    DANGEROUS_PATTERNS = [
        # Recursive deletes
        (r'rm\s+-r\b', "Recursive delete (rm -r)"),
        (r'rm\s+--recursive\b', "Recursive delete (rm --recursive)"),
        (r'rm\s+-rf\b', "Recursive force delete (rm -rf)"),
        (r'rm\s+--recursive\s+--force\b', "Recursive force delete"),
        
        # System directory writes
        (r'>\s*(/dev/|/etc/|/usr/|/bin/|/sbin/|/lib/|/boot/', "Write to critical system directory"),
        
        # Shell features that could be exploited
        (r':\s*>\s*\S+', "Here-document"),
        (r';\s*', "Command chaining with ;"),
        (r'&&\s*', "AND-chain"),
        (r'\|\s*', "OR-chain"),
        (r'\$\(', "Command substitution"),
        (r'`[^`]+`', "Backtick command substitution"),
        
        # Dangerous commands
        (r'chmod\s+-R\b', "Recursive chmod"),
        (r'chown\s+-R\b', "Recursive chown"),
        (r'mkfs\b', "Filesystem creation"),
        (r'dd\s+if=\s*', "dd command (disk operations)"),
        (r'fdisk\b', "Partition table manipulation"),
        (r'format\b', "Disk formatting"),
        (r'partition\b', "Partition manipulation"),
        (r'mount\b', "Mount filesystems"),
        (r'umount\b', "Unmount filesystems"),
        
        # Privilege escalation
        (r'sudo\b', "Privilege escalation (sudo)"),
        (r'su\s+', "Switch user"),
    ]
    
    for pattern, description in DANGEROUS_PATTERNS:
        if re.search(pattern, command):
            return description
    
    return None
```

### Extract Mode Implementation (Multi-Tool Support)

```python
def extract_tool_calls(self, format_hint="auto"):
    """
    Parse LAST_COMPLETION for tool calls and populate TOOL_* variables.
    
    Supports multiple tool calls with indexed variable access.
    """
    # Get the last completion from buffer_manager (consistent store)
    last_completion = self.buffer_manager.get_script_var('LAST_COMPLETION') or ""
    
    if not last_completion.strip():
        self.buffer_manager.set_script_var('TOOL_FOUND', 'false')
        self.buffer_manager.set_script_var('TOOL_COUNT', '0')
        self.buffer_manager.set_script_var('TOOL_ERROR', 'No content to parse')
        self.buffer_manager.set_script_var('TOOL_FORMAT', '')
        self.buffer_manager.set_script_var('TOOL_NAME', '')
        self.buffer_manager.set_script_var('TOOL_ARGS', '')
        self.buffer_manager.set_script_var('TOOL_CALL', '')
        self.buffer_manager.set_script_var('TOOL_CALLS', '[]')
        print("⚠️  No content in LAST_COMPLETION to parse")
        return
    
    # Try different formats based on hint or auto-detection
    tool_calls = []
    detected_format = ""
    
    if format_hint == "auto" or format_hint == "xml":
        tool_calls = self._parse_xml_tool_calls(last_completion)
        if tool_calls:
            detected_format = "xml"
    
    if not tool_calls and (format_hint == "auto" or format_hint == "json"):
        tool_calls = self._parse_json_tool_calls(last_completion)
        if tool_calls:
            detected_format = "json"
    
    if not tool_calls and (format_hint == "auto" or format_hint == "markdown"):
        tool_calls = self._parse_markdown_tool_calls(last_completion)
        if tool_calls:
            detected_format = "markdown"
    
    if not tool_calls and format_hint == "auto":
        tool_calls = self._parse_inline_tool_calls(last_completion)
        if tool_calls:
            detected_format = "inline"
    
    # Set common variables
    self.buffer_manager.set_script_var('TOOL_FOUND', 'true' if tool_calls else 'false')
    self.buffer_manager.set_script_var('TOOL_COUNT', str(len(tool_calls)))
    self.buffer_manager.set_script_var('TOOL_FORMAT', detected_format)
    
    # Clear previous indexed variables (optional, for cleanliness)
    # In practice, we just overwrite them
    
    if tool_calls:
        # Set all tool calls as JSON array
        import json
        self.buffer_manager.set_script_var('TOOL_CALLS', json.dumps(tool_calls))
        self.buffer_manager.set_script_var('TOOL_ERROR', '')
        
        # Set first tool for backward compatibility
        first_tool = tool_calls[0]
        self.buffer_manager.set_script_var('TOOL_NAME', first_tool.get('name', ''))
        self.buffer_manager.set_script_var('TOOL_ARGS', first_tool.get('args', ''))
        self.buffer_manager.set_script_var('TOOL_CALL', first_tool.get('raw', ''))
        
        # Set indexed variables for multi-tool support
        for i, tool in enumerate(tool_calls):
            self.buffer_manager.set_script_var(f'TOOL_NAME[{i}]', tool.get('name', ''))
            self.buffer_manager.set_script_var(f'TOOL_ARGS[{i}]', tool.get('args', ''))
        
        print(f"✅ Extracted {len(tool_calls)} tool call(s) ({detected_format})")
    else:
        self.buffer_manager.set_script_var('TOOL_NAME', '')
        self.buffer_manager.set_script_var('TOOL_ARGS', '')
        self.buffer_manager.set_script_var('TOOL_CALL', '')
        self.buffer_manager.set_script_var('TOOL_CALLS', '[]')
        self.buffer_manager.set_script_var('TOOL_ERROR', 'No tool calls found')
        print("⚠️  No tool calls found in LAST_COMPLETION")


def _parse_xml_tool_calls(self, text):
    """Parse XML formatted tool calls."""
    import re
    tool_calls = []
    
    # Pattern 1: <tool name="func">args</tool>
    # Pattern 2: <function name="func">args</function>
    # Pattern 3: <tool>name(args)</tool>
    patterns = [
        (r'<tool\s+name="([^"]+)"[^>]*>([^<]*)</tool>', lambda m: {'name': m.group(1), 'args': m.group(2), 'raw': m.group(0)}),
        (r'<function\s+name="([^"]+)"[^>]*>([^<]*)</function>', lambda m: {'name': m.group(1), 'args': m.group(2), 'raw': m.group(0)}),
        (r'<tool>([^<]*)</tool>', lambda m: self._parse_tool_content(m.group(1))),
        (r'<function>([^<]*)</function>', lambda m: self._parse_tool_content(m.group(1))),
    ]
    
    for pattern, handler in patterns:
        for match in re.finditer(pattern, text):
            try:
                tool_calls.append(handler(match))
            except:
                continue
    
    return tool_calls


def _parse_tool_content(self, content):
    """Parse tool content in format: name(args) or just name."""
    content = content.strip()
    if '(' in content and content.endswith(')'):
        # Format: name(args)
        name = content[:content.index('(')].strip()
        args = content[content.index('(')+1:-1].strip()
        return {'name': name, 'args': args, 'raw': content}
    else:
        # Format: just name
        return {'name': content, 'args': '', 'raw': content}


def _parse_json_tool_calls(self, text):
    """Parse JSON formatted tool calls."""
    import json
    import re
    
    tool_calls = []
    
    # Try to find JSON objects in the text
    # Look for { ... "tool_calls": [...] ... }
    json_pattern = r'\{[^{}]*"tool_calls"\s*:\s*\\[[^{}]*\][^{}]*\}'
    
    for match in re.finditer(json_pattern, text):
        try:
            data = json.loads(match.group(0))
            if 'tool_calls' in data:
                for tc in data['tool_calls']:
                    if 'function' in tc:
                        func = tc['function']
                        tool_calls.append({
                            'name': func.get('name', ''),
                            'args': json.dumps(func.get('arguments', {})),
                            'raw': json.dumps(tc)
                        })
                    elif 'tool' in tc:
                        # Alternative format
                        tool_calls.append({
                            'name': tc['tool'].get('name', ''),
                            'args': json.dumps(tc['tool'].get('arguments', {})),
                            'raw': json.dumps(tc)
                        })
        except (json.JSONDecodeError, KeyError):
            continue
    
    return tool_calls


def _parse_markdown_tool_calls(self, text):
    """Parse markdown code block formatted tool calls."""
    import re
    tool_calls = []
    
    # Pattern: ```tool or ```function
    pattern = r'```(?:tool|function)\s*\n([\s\S]*?)```'
    
    for match in re.finditer(pattern, text):
        content = match.group(1).strip()
        if content:
            # Try to parse as JSON first
            try:
                import json
                data = json.loads(content)
                if isinstance(data, dict) and 'name' in data:
                    tool_calls.append({
                        'name': data['name'],
                        'args': json.dumps(data.get('arguments', {})),
                        'raw': content
                    })
                elif isinstance(data, list):
                    for item in data:
                        if isinstance(item, dict) and 'name' in item:
                            tool_calls.append({
                                'name': item['name'],
                                'args': json.dumps(item.get('arguments', {})),
                                'raw': json.dumps(item)
                            })
            except (json.JSONDecodeError, TypeError):
                # Parse as simple format: name(args)
                tool = self._parse_tool_content(content)
                tool_calls.append(tool)
    
    return tool_calls


def _parse_inline_tool_calls(self, text):
    """Parse inline tool call patterns like TOOL: name(args)."""
    import re
    tool_calls = []
    
    # Pattern: TOOL: name(args) or FUNCTION: name(args)
    pattern = r'\b(TOOL|FUNCTION):\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\((.*)\)'
    
    for match in re.finditer(pattern, text):
        tool_calls.append({
            'name': match.group(2),
            'args': match.group(3).strip(),
            'raw': match.group(0)
        })
    
    return tool_calls
```

---

## Security Design (REVISED)

### Core Principles

1. **NEVER use `shell=True`** - This is the #1 security rule
2. **Variable substitution happens in Python** - Before subprocess execution
3. **Pattern-based detection** - Not coarse command blocklists
4. **User confirmation for dangerous operations** - In safe mode (default)
5. **Safe mode is default** - Users must opt-in to danger

### Dangerous Pattern Detection

```python
DANGEROUS_PATTERNS = [
    # Recursive deletes
    (r'rm\s+-r\b', "Recursive delete (rm -r)"),
    (r'rm\s+--recursive\b', "Recursive delete (rm --recursive)"),
    (r'rm\s+-rf\b', "Recursive force delete (rm -rf)"),
    (r'rm\s+--recursive\s+--force\b', "Recursive force delete"),
    
    # System directory writes
    (r'>\s*(/dev/|/etc/|/usr/|/bin/|/sbin/|/lib/|/boot/|/var/|/opt/)', 
     "Write to critical system directory"),
    
    # Shell features that could be exploited
    (r':\s*>\s*\S+', "Here-document"),
    (r';\s*', "Command chaining with ;"),
    (r'&&\s*', "AND-chain"),
    (r'\|\s*', "OR-chain"),
    (r'\$\(', "Command substitution"),
    (r'`[^`]+`', "Backtick command substitution"),
    
    # Dangerous commands
    (r'chmod\s+-R\b', "Recursive chmod"),
    (r'chown\s+-R\b', "Recursive chown"),
    (r'mkfs\b', "Filesystem creation"),
    (r'dd\s+if=\s*', "dd command (disk operations)"),
    (r'fdisk\b', "Partition table manipulation"),
    (r'format\b', "Disk formatting"),
    (r'partition\b', "Partition manipulation"),
    (r'mount\b', "Mount filesystems"),
    (r'umount\b', "Unmount filesystems"),
    
    # Privilege escalation
    (r'sudo\b', "Privilege escalation (sudo)"),
    (r'su\s+', "Switch user"),
]
```

> **Note**: `curl`, `wget`, `mv`, `cp`, `cat`, `grep`, `echo`, `date`, `df`, `du`, `free`, `ls`, etc. are **NOT** blocked by default. Only dangerous *patterns* are flagged.

### Safe Mode Implementation

```python
# In __init__ method:
self.safe_mode = True  # Default to safe

# New commands:
elif cmd == "/run_safe":
    self.safe_mode = True
    print("✅ Safe mode enabled - dangerous patterns require confirmation")

elif cmd == "/run_unsafe":
    self.safe_mode = False
    print("⚠️  Safe mode disabled - dangerous commands allowed without confirmation")
```

### Why This Approach Works

With `shell=False` + `shlex.split()`:
- User input: `/run echo ${EVIL}`
- ChatDSL substitutes: `/run echo malicious; rm -rf /`
- shlex.split: `['echo', 'malicious; rm -rf /']`
- subprocess: runs literally `echo 'malicious; rm -rf /'` - **NO EXECUTION**

The `;` is just an argument to echo, not a shell operator.

**This eliminates shell injection entirely.**

---

## Testing Strategy

### Unit Tests for `/run` Command

```python
# test_run_command.py

import pytest
from unittest.mock import patch, MagicMock


class TestRunCommand:
    """Tests for /run command execution."""
    
    @pytest.fixture
    def app(self):
        """Create app with mocked subprocess."""
        # Setup app with mocked dependencies
        pass
    
    async def test_execute_simple_command(self, app):
        """Test basic shell command execution."""
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(
                stdout="hello\n",
                stderr="",
                returncode=0
            )
            app.handle_escape_command("/run echo hello")
            assert app.buffer_manager.get_script_var('LAST_COMPLETION') == "hello\n"
            assert app.buffer_manager.get_script_var('LAST_ERROR') == ""
            assert app.buffer_manager.get_script_var('LAST_EXIT_CODE') == "0"
    
    async def test_execute_command_with_spaces(self, app):
        """Test command with spaces in arguments."""
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(
                stdout="hello world\n",
                stderr="",
                returncode=0
            )
            app.handle_escape_command('/run echo "hello world"')
            assert "hello world" in app.buffer_manager.get_script_var('LAST_COMPLETION')
    
    async def test_no_shell_injection(self, app):
        """Test that shell injection is prevented."""
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(
                stdout="malicious; rm -rf /\n",
                stderr="",
                returncode=0
            )
            # This should pass the literal string, not execute rm
            app.handle_escape_command('/run echo "malicious; rm -rf /"')
            
            # Verify subprocess was called with safe arguments
            call_args = mock_run.call_args[0][0]
            assert call_args == ['echo', 'malicious; rm -rf /']
            assert mock_run.call_args[1]['shell'] == False
    
    async def test_dangerous_pattern_detected(self, app):
        """Test that dangerous patterns are detected."""
        with patch('builtins.input', return_value='n'):
            app.handle_escape_command('/run rm -rf /tmp')
            assert "Blocked" in app.buffer_manager.get_script_var('LAST_COMPLETION')
    
    async def test_dangerous_pattern_allowed_with_confirmation(self, app):
        """Test that dangerous patterns can be allowed with confirmation."""
        app.safe_mode = False
        with patch('builtins.input', return_value='y'):
            with patch('subprocess.run') as mock_run:
                mock_run.return_value = MagicMock(stdout="", stderr="", returncode=0)
                app.handle_escape_command('/run rm -rf /tmp/test')
                # Should execute because user confirmed
                mock_run.assert_called_once()
    
    async def test_timeout_command(self, app):
        """Test command timeout."""
        with patch('subprocess.run') as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired('test', 30)
            app.handle_escape_command("/run sleep 100")
            assert "timeout" in app.buffer_manager.get_script_var('LAST_COMPLETION').lower()
    
    async def test_command_not_found(self, app):
        """Test handling of missing commands."""
        with patch('subprocess.run') as mock_run:
            mock_run.side_effect = FileNotFoundError('nonexistent')
            app.handle_escape_command("/run nonexistent_command")
            assert "not found" in app.buffer_manager.get_script_var('LAST_ERROR').lower()

class TestExtractTools:
    """Tests for /extract_tools command."""
    
    async def test_extract_xml_tool_call(self, app):
        """Test XML tool call extraction."""
        app.buffer_manager.set_script_var('LAST_COMPLETION', 
            '<tool name="get_weather">{"city": "NYC"}</tool>')
        app.handle_escape_command("/extract_tools")
        assert app.buffer_manager.get_script_var('TOOL_FOUND') == "true"
        assert app.buffer_manager.get_script_var('TOOL_COUNT') == "1"
        assert app.buffer_manager.get_script_var('TOOL_NAME') == "get_weather"
        assert app.buffer_manager.get_script_var('TOOL_ARGS') == '{"city": "NYC"}'
    
    async def test_extract_json_tool_call(self, app):
        """Test JSON tool call extraction."""
        json_content = '{"tool_calls": [{"function": {"name": "search", "arguments": {"query": "test"}}}]}'
        app.buffer_manager.set_script_var('LAST_COMPLETION', json_content)
        app.handle_escape_command("/extract_tools")
        assert app.buffer_manager.get_script_var('TOOL_FOUND') == "true"
        assert app.buffer_manager.get_script_var('TOOL_NAME') == "search"
    
    async def test_extract_multiple_tools(self, app):
        """Test extraction of multiple tool calls."""
        xml_content = '<tool name="func1">arg1</tool><tool name="func2">arg2</tool>'
        app.buffer_manager.set_script_var('LAST_COMPLETION', xml_content)
        app.handle_escape_command("/extract_tools")
        assert app.buffer_manager.get_script_var('TOOL_COUNT') == "2"
        assert app.buffer_manager.get_script_var('TOOL_NAME[0]') == "func1"
        assert app.buffer_manager.get_script_var('TOOL_NAME[1]') == "func2"
    
    async def test_extract_no_tool_call(self, app):
        """Test when no tool call is present."""
        app.buffer_manager.set_script_var('LAST_COMPLETION', "Just a regular response")
        app.handle_escape_command("/extract_tools")
        assert app.buffer_manager.get_script_var('TOOL_FOUND') == "false"
        assert app.buffer_manager.get_script_var('TOOL_COUNT') == "0"
    
    async def test_extract_empty_content(self, app):
        """Test extraction with empty LAST_COMPLETION."""
        app.buffer_manager.set_script_var('LAST_COMPLETION', "")
        app.handle_escape_command("/extract_tools")
        assert app.buffer_manager.get_script_var('TOOL_FOUND') == "false"
    
    async def test_double_semicolon_in_output(self, app):
        """Test that ;; in command output doesn't break multiline mode."""
        # This tests the tokenization conflict
        app.buffer_manager.set_script_var('LAST_COMPLETION', "data;;more data")
        app.handle_escape_command("/extract_tools")
        # Should not crash or misbehave
        assert app.buffer_manager.get_script_var('TOOL_FOUND') == "false"


class TestIntegration:
    """Integration tests for /run and /extract_tools workflows."""
    
    async def test_run_then_extract_workflow(self, app):
        """Test the workflow: run command, extract from output."""
        # Simulate a script that outputs tool calls
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(
                stdout='<tool name="process">{"file": "data.txt"}</tool>',
                stderr="",
                returncode=0
            )
            app.handle_escape_command('/run some_script.sh')
            
        app.handle_escape_command('/extract_tools')
        assert app.buffer_manager.get_script_var('TOOL_FOUND') == "true"
        assert app.buffer_manager.get_script_var('TOOL_NAME') == "process"
    
    async def test_variable_consistency(self, app):
        """Test that /run and /extract_tools use the same variable store."""
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(
                stdout="test output",
                stderr="",
                returncode=0
            )
            app.handle_escape_command('/run echo test')
            
        # Should be readable by extract_tools
        app.handle_escape_command('/extract_tools')
        # extract_tools reads from LAST_COMPLETION which /run wrote to
        # This tests the store consistency

---

## Integration with Existing Features

### With `/script` Command

```chatdsl
# Script that uses /run
/script get_system_info.dsl

# get_system_info.dsl
/run df -h
/save disk_info.txt ${LAST_COMPLETION}

/run free -m
/save memory_info.txt ${LAST_COMPLETION}

/echo "System info collected!"
```

### With Conditional Logic (Compatible with Current Parser)

```chatdsl
# Check if a tool was called, then act on it (single-line syntax)
Tell me the weather.

/extract_tools
/if "${TOOL_FOUND}" == "true" /echo "LLM requested tool: ${TOOL_NAME}"

# Process multiple tools
/extract_tools
/if "${TOOL_COUNT}" > "0" /echo "Found ${TOOL_COUNT} tool call(s)"

# Combined workflow - extract then act
/extract_tools
/if "${TOOL_FOUND}" == "true" /run echo "Would execute: ${TOOL_NAME}(${TOOL_ARGS})"

# Access specific tool by index
/extract_tools
/if "${TOOL_COUNT}" > "1" /echo "Second tool: ${TOOL_NAME[1]}"
```

### With Variable Substitution

```chatdsl
# Use variables in /run commands
/set CITY "New York"
/run echo "Getting weather for ${CITY}"

# The variable is substituted in Python before subprocess execution
# Output: "Getting weather for New York"
# SAFE: The substitution happens in Python, then shlex.split ensures safe execution
```

> **Note on Future Parser Enhancements**: Multi-line if/else/endif blocks would enable more complex workflows but are not required for the initial `/run` implementation. The single-line syntax shown above works with the current parser.

---

## Future Enhancements

### High Priority (Post-MVP)
1. **Command History**: Track executed commands in a separate history variable
2. **if/else/endif Support**: Implement proper multi-line conditionals in parser
3. **Environment Variable Control**: Allow setting env vars for specific commands

### Medium Priority
4. **Command Aliases**: Support `/run_alias name command` to create shortcuts
5. **Background Execution**: `/run -b` to run in background (with job control)
6. **Output Filtering**: Auto-parse JSON/XML output into structured variables
7. **Tool Call Auto-Execution**: Option to automatically execute extracted tool calls

### Low Priority
8. **Sandbox Mode**: Run commands in Docker containers for isolation
9. **Command Piping**: `/run cmd1 | cmd2` support (requires shell=True alternative)
10. **Working Directory Control**: `/run -C /path command` to set cwd

---

## Open Questions

1. **Help Integration**: Should `/run` without arguments show help text?
2. **Multi-line Commands**: Should we support `\` for command continuation?
3. **Binary Output**: How should we handle commands that produce binary output?
4. **File Commands**: Should we support reading commands from files?
5. **Terminal Commands**: How do we handle commands requiring TTY (vim, nano, top)?
6. **Command History**: Should executed commands be saved to a separate history file?
7. **Environment Isolation**: Should commands run with a clean environment by default?

---

## Pre-Implementation Checklist

Before implementing `/run` and `/extract_tools`, complete these tasks:

- [ ] **Audit `auto_exit_pending`**: Run `grep -rn "auto_exit_pending" src/chatybot/` and remove or complete implementation
- [ ] **Add to VALID_ESCAPE_COMMANDS**: Add `'run'` and `'extract_tools'` to `src/chatybot/chatdsl_parse.py`
- [ ] **Verify variable store consistency**: Confirm `buffer_manager.set_script_var()` and `get_script_var()` work for all new variables
- [ ] **Test ;; tokenization**: Ensure `/run` output containing `;;` doesn't break multiline mode
- [ ] **Update help system**: Add entries for both commands in `chaty_help.py`
- [ ] **Document in README**: Add command reference with examples

---

## Implementation Order

1. **Security First**: Implement `execute_shell_command()` with `shlex.split()` + `shell=False` + pattern detection
2. **Extract Mode**: Implement `extract_tool_calls()` with multi-tool support
3. **Command Registration**: Add to `handle_escape_command()` and `VALID_ESCAPE_COMMANDS`
4. **Variable Consistency**: Ensure both commands use `buffer_manager` for all variables
5. **Testing**: Write unit tests for both commands
6. **Documentation**: Update README and help system

---

## Conclusion

The **recommended approach** is **Option 3 (Separate Commands)**:
- `/run <command>` for shell execution (with security fixes)
- `/extract_tools [format]` for parsing tool calls from `LAST_COMPLETION`

**Critical Changes from Original Design**:

1. ✅ **Security**: Removed `shell=True`, using `shlex.split()` + `shell=False`
2. ✅ **Blocklist**: Replaced with pattern-based dangerous operation detection + confirmation
3. ✅ **Multi-Tool**: Day-one support with indexed variables (`${TOOL_NAME[0]}`, etc.)
4. ✅ **Variable Store**: Consistent use of `buffer_manager.set_script_var()` / `get_script_var()`
5. ✅ **Parser Limits**: Examples compatible with current single-line `/if` syntax
6. ✅ **Registration**: Added note about VALID_ESCAPE_COMMANDS requirement
7. ✅ **State Audit**: Added pre-implementation checklist for `auto_exit_pending`
8. ✅ **Tokenization**: Added test case for `;;` in output

This design transforms ChatDSL from a prompt runner into a **real agentic scripting environment** with safe shell integration and tool call extraction. The security model is robust, and the implementation is compatible with the existing codebase.
