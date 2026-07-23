# Help System Implementation Summary

## Overview

Implemented enhanced help system for ChatyBot with two key features:
- **Alternative A (Keyword Filter)**: Filter commands by keyword
- **Alternative C (Command Deep-dive)**: Detailed help for specific commands

## Branch

`help`

## Files Modified

### New File: `src/chatybot/chaty_help.py`
- **Purpose**: Central help system with structured command information
- **Key Classes**:
  - `CommandHelp`: Dataclass for structured help information per command
  - `HelpSystem`: Central help system with filtering and categorization
- **Features**:
  - Keyword filtering across all command attributes
  - Command categorization (file, model, image, debug, etc.)
  - Detailed command information with usage, examples, parameters
  - Expandable architecture for future enhancements

### Modified File: `src/chatybot/chatybot_app.py`
- **Import Added**: `from .chaty_help import get_help_system`
- **Initialization**: Added `self.help_system = get_help_system()` in `__init__`
- **Command Handler**: Modified `/help` handler to accept optional query argument
- **Help Output**: Added help tips at bottom of default `/help` output

## Usage

### Original Behavior (Preserved)
```
/help
```
Shows all available commands in the original format, with new help tips appended.

### New Features

#### Alternative A: Keyword Filter
```
/help file
/help model
/help image
```
Filters commands by keyword and displays them grouped by category.

#### Alternative C: Command Deep-dive
```
/help /file
/help /model
/help /imagine
```
Shows detailed help for a specific command including:
- Category
- Usage syntax
- Short and long descriptions
- Examples
- Parameters
- See also references

### Error Handling
```
/help /nonexistent
/help xyz123
```
Shows helpful error message: "No commands found matching '<query>'. Try /help for all commands."

## Help Tips Added

The following instructions are now appended to the default `/help` output:

```
--- Help Tips ---
Use '/help <command>' for detailed help on a specific command (e.g., '/help /file').
Use '/help <keyword>' to filter commands by keyword (e.g., '/help file' shows all file-related commands).
For more information, see chaty_help.py.
```

## Command Help Structure

Each command in `chaty_help.py` includes:

```python
CommandHelp(
    name="/file",
    category="file",
    short_desc="Load a text file into the buffer",
    usage="/file <path>",
    long_desc="Loads text from a file into the persistent file buffer...",
    examples=["/file prompt.txt", "/file data.json"],
    see_also=["/showfile", "/clearfile"],
    parameters={"path": "Path to the file to load"}
)
```

## Categories Defined

- **system**: Core system commands (`/help`, `/quit`)
- **file**: File management (`/file`, `/filebank1-5`, `/showfile`, etc.)
- **image**: Image handling (`/imagine`, `/imagebank1-5`, `/imagesize`, etc.)
- **model**: Model configuration (`/model`, `/listmodels`, `/temp`, etc.)
- **output**: Output control (`/save`, `/codeonly`, `/notemode`, etc.)
- **input**: Input handling (`/prompt`, `/multiline`)
- **debug**: Debugging tools (`/trace`, `/debug`, `/logging`, etc.)
- **script**: Scripting (`/script`, `/reloadmacros`)
- **database**: Database operations (`/setdb`, `/dblist`, `/searchdb`, etc.)
- **variable**: Variable management (`/loadvar`, `/savevar`, `/setvar`, etc.)
- **utility**: Utility commands (`/echo`, `/mem`, `/dump`)
- **history**: History commands (`!`)

## Implementation Details

### Keyword Matching
The `matches_keyword()` method checks if a keyword matches:
- Command name
- Short description
- Long description
- Category
- Aliases
- Examples

### Query Resolution Logic
The `get_help_text()` method resolves queries in this order:

1. If query is `None` → Return all commands grouped by category
2. If query starts with `/`:
   - Check if it's an exact command match
   - Try stripping leading slash and rechecking
   - Fall back to keyword filtering if no command match
3. If query doesn't start with `/` → Treat as keyword filter

### Formatting
- **Command List**: Grouped by category, alphabetically sorted
- **Command Detail**: Structured with headers, parameters, examples

## Testing

All features have been tested:
- `/help` → Original behavior preserved
- `/help file` → Keyword filtering works
- `/help /file` → Specific command detail works
- `/help model` → Keyword filtering for model commands works
- `/help /nonexistent` → Error handling works

## Future Expansion

The `HelpSystem` class is designed for easy expansion:
- Add new commands by calling `register_command()`
- Add new categories as needed
- Extend `CommandHelp` dataclass with additional fields
- Implement additional filtering methods
- Add TUI support (Alternative D) using the same data

## Notes

- The original `/help` output in `show_help()` is preserved for backward compatibility
- The new help system provides structured data that can be used for various output formats
- All command help information is centralized in `chaty_help.py` for easy maintenance