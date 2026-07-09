# Tool Management Update

This update adds runtime, session-based tool enable/disable capabilities and tool status listing to Chatybot.

## New Subcommands under `/tool`

| Command | Action |
|---|---|
| `/tool list` | Lists all registered tools with their current state (`[ON]` / `[OFF]`) and description. |
| `/tool enable <name>` | Enables a specific tool for the current session (case-insensitive matching). |
| `/tool enable all` | Enables all registered tools. |
| `/tool disable <name>` | Disables a specific tool for the current session (case-insensitive matching). |
| `/tool disable all` | Disables all registered tools. |

---

## Technical Design & Behavior

1. **In-Memory State**: Added a `self.tool_overrides` dictionary to the `ChatybotApp` instance. This overrides the default TOML configuration (`enabled = true/false`) only for the duration of the current session.
2. **Context Regeneration**: When `/tool enable` or `/tool disable` is invoked:
   - It updates the in-memory overrides.
   - If tool mode is active (`self.tool_mode`), it immediately regenerates the tool context and updates the `TOOL_CONTEXT` script variable, updating the LLM's system prompt context on the fly.
3. **Subprocess Isolation Enforced**:
   - `dispatcher.py` runs as a separate subprocess and loads `tools_config.toml` from disk.
   - To respect in-memory overrides, the overrides are serialized to JSON and passed to the dispatcher subprocess via the `CHATYBOT_TOOL_OVERRIDES` environment variable.
   - The dispatcher checks this variable. If a tool is disabled at runtime, execution is blocked and returns a validation error code (`VALIDATION_FAILURE`).

---

## Modified Files

### [src/chatybot/chatybot_app.py](file:///home/jon2allen/github2/chatybot/src/chatybot/chatybot_app.py)
- **`__init__`**: Initialized `self.tool_overrides` dict.
- **`_load_tools_config`**: Added helper method to parse the TOML config file (using `tomllib` or `toml` package fallback).
- **`generate_tool_context`**: Refactored to use `_load_tools_config` and check both config defaults and `self.tool_overrides` status.
- **`dispatch_tool`**: Added passing of `self.tool_overrides` via `CHATYBOT_TOOL_OVERRIDES` environment variable to the dispatcher subprocess.
- **`/tool` command handler**: Added subcommands `list`, `enable`, and `disable`.

### [src/chatybot/dispatcher.py](file:///home/jon2allen/github2/chatybot/src/chatybot/dispatcher.py)
- **`validate_and_route`**: Intercepts `CHATYBOT_TOOL_OVERRIDES` environment variable to ensure runtime overrides are respected, raising `PermissionError` for disabled tools.

### [test/test_run_command.py](file:///home/jon2allen/github2/chatybot/test/test_run_command.py)
- **`test_tool_enable_disable_list`**: Added comprehensive integration test for `/tool list`, `/tool enable`, `/tool disable` (including case insensitivity, error handling, bulk toggling, and LLM context regeneration).
