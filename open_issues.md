# Open Issues

## P13 — `EXECUTE_PROMPT` string sentinel through `Union[bool, str]` return type

**Severity:** Low (latent, no current trigger)

**Location:** `src/chatybot/chatybot_app.py` — `handle_escape_command` return type and both consumers (lines ~2286, ~2415)

**Description:**

`handle_escape_command` returns `Union[bool, str]`. When `/prompt` is confirmed, it returns the string sentinel `"EXECUTE_PROMPT"` instead of a boolean. Callers must explicitly check `if result == "EXECUTE_PROMPT"` to trigger prompt execution.

**Current exposure:** Low. Only two callers exist today, and both explicitly handle the sentinel. No live bug.

**Future risk:** Any new caller that checks only `if result:` or `if result is True` will:
1. Treat the string as truthy, assume the command was handled, and skip `chat_completion` — the prompt never executes.
2. Leave `prompt_buffer` populated (the handler sets it before returning). On the next normal user input, line ~1111 silently prepends it: `full_prompt = self.buffer_manager.prompt_buffer + "\n\n" + full_prompt`. The user's next message gets the loaded prompt injected with no warning.
3. No error, no log, no crash — the failure is invisible.

The `Union[bool, str]` return type gives no static-type-checker warning about the unhandled case, so the mistake would be invisible at review time.

**Suggested fix:** Replace the string sentinel with a dedicated return type or a raised exception that callers must handle explicitly. This touches every caller of `handle_escape_command` and both `EXECUTE_PROMPT` consumer sites.
