# Devstral Empty Response and Scoping Fix

## 1. The Issue
When switching to `devstral-2512` (alias: `devstral_1`) with `/tool on` enabled, queries requesting tool usage would return:
```
Warning: Received an empty response from the model.
```
despite reporting output token counts (typically 17 or 26 tokens) and completing extremely quickly.

## 2. Root Cause
* **Native Tool Calls**: `devstral-2512` is natively trained to utilize tools. When it sees tool definitions in the system/user prompt (under `/tool on`), it generates native tool-calling sequences (e.g. `[TOOL_CALLS] ...`).
* **Interception**: The API gateway intercepts these tokens and populates `choices[0].message.tool_calls`, leaving `choices[0].message.content` empty.
* **Missing Handler**: Chatybot did not previously look at the `tool_calls` attribute in `chat_completion`, thus treating the response as empty.

## 3. The Fixes

### A. Mapping Native Tool Calls to Chatybot JSON Blocks
We added a handler in `chat_completion` (inside `src/chatybot/chatybot_app.py`) to detect if `message.tool_calls` is populated. If present, it maps the native function calls back into Chatybot's expected triple-backtick markdown JSON blocks:
```python
if hasattr(message, "tool_calls") and message.tool_calls:
    tool_calls_list = []
    for tc in message.tool_calls:
        tc_name = tc.function.name
        tc_args = tc.function.arguments
        if isinstance(tc_args, str):
            try:
                tc_args = json.loads(tc_args)
            except Exception:
                pass
        tool_calls_list.append({
            "tool": tc_name,
            "arguments": tc_args
        })
    if tool_calls_list:
        if len(tool_calls_list) == 1:
            content = f"```json\n{json.dumps(tool_calls_list[0])}\n```"
        else:
            content = f"```json\n{json.dumps(tool_calls_list)}\n```"
```
This enables native tool calling compatibility for `devstral-2512` and any other native tool-calling models.

### B. Resolving UnboundLocalError / Name Shadowing
A temporary `import json` was placed inside this conditional branch. However, because `json` was already used earlier in the `chat_completion` function to dump raw debug messages, defining `import json` inside the function scope caused Python to treat `json` as a local variable for the *entire* function. This resulted in an `UnboundLocalError` when accessing `json.dumps()` in the debug blocks.
* **Fix**: Removed the redundant local `import json` block, relying entirely on the global `import json` defined at the top of `chatybot_app.py`.

### C. Added `devstral` to Reasoning Models list
Added `"devstral"` to the models that support `reasoning_effort` selection (via `/reasoning`).

### D. Unit Testing
Added a new test case `test_native_tool_calls_mapping` to `test/test_run_command.py` that verifies native tool call structures are correctly mapped to JSON block strings.
