# /str_search Implementation — Design Decisions

## Overview

`/str_search` is a slash command that searches for substring patterns within text variables, returning match counts or positions. It follows the same architecture as `/calc` — a slash command handler in `chatybot_app.py`, a standalone tool function in `tools/str_utils.py`, TOML dispatcher config, help registration, localization aliases, and a protected default variable.

## Design Decisions

### 1. Option 2 (Count + Positions) Chosen Over Alternatives

Three options were considered:

| Option | Result | Complexity | Use Case |
|--------|--------|------------|----------|
| 1: Boolean `in`/`not in` | `True`/`False` | Lowest | Existence check |
| **2: Count + Positions** | `int` or `[(start, end)]` | Medium | Log analysis, text processing |
| 3: Full regex with groups | `list[str]` | Highest | Advanced pattern matching |

Option 2 was selected because it covers the most common use cases (counting occurrences, finding where matches are) without requiring regex knowledge. The `m` mode returns `(start, end)` tuples, which are useful for downstream processing (slicing, highlighting). Regex was intentionally avoided to keep the interface simple and safe — `re.escape()` is used internally so patterns are treated as literal strings.

### 2. Flags as a Single Combinable String

Rather than separate boolean parameters, flags are passed as a single string (e.g., `"im"`, `"ic"`, `"m"`):

```
/str_search "error" ${LOG} im positions
```

This matches the convention of tools like `grep -i`, `sed`, etc. The parser validates that the flag token contains only characters from the set `{c, m, i, C, M, I, G}`. If the third token doesn't match this pattern, it's treated as a variable name instead.

**Rationale:** Keeps the syntax compact. `/str_search "error" ${LOG} ic my_count` reads naturally. The alternative — named flags like `case=true mode=count` — would be more verbose and break the pattern established by `/calc`.

### 3. Variable Resolution: The ${LOG} Problem

This was the most subtle issue encountered.

#### The Problem

In production, the call chain is:

```
User types: /str_search "error" ${LOG}
  → handle_command() checks exclusion list → ${LOG} NOT resolved (because /str_search is excluded)
    → handle_escape_command() receives raw: /str_search "error" ${LOG}
      → Handler strips ${} wrapper, looks up var "LOG", gets value "error info error warn error"
```

But in tests (and direct calls), `handle_escape_command` is called directly:

```python
await app.handle_escape_command('/str_search "error" ${LOG}')
```

This bypasses `handle_command()` entirely, so the exclusion list never fires. The handler receives the raw `${LOG}` string.

#### The Bug (First Attempt)

The initial handler code called `replace_placeholders_legacy()` on `text_var`:

```python
text_var = self.buffer_manager.replace_placeholders_legacy(text_var, clear_unresolved=False)
# text_var is now "error info error warn error" (the VALUE, not the variable name)
var_name = text_var
if var_name.startswith("${") and var_name.endswith("}"):
    var_name = var_name[2:-1]  # Never triggers — no ${} wrapper left!
text_value = self.buffer_manager.get_script_var(var_name)  # Looks up "error info error warn error" → None
```

`replace_placeholders_legacy("${LOG}")` resolves to the variable's **value**. After resolution, `text_var` is the literal string `"error info error warn error"`. The `${}` wrapper is gone, so the `startswith("${")` check fails, and the code tries to look up `"error info error warn error"` as a variable name — which doesn't exist.

**This worked in production** (where `replace_placeholders_legacy` was called before the handler by `handle_command`), but **failed in tests** (where the handler receives raw `${LOG}` and calls `replace_placeholders_legacy` on it itself, double-resolving).

#### The Fix

`replace_placeholders_legacy` is NOT called on `text_var`. The handler only strips the `${}` wrapper and uses the extracted name directly:

```python
var_name = text_var
if var_name.startswith("${") and var_name.endswith("}"):
    var_name = var_name[2:-1]
text_value = self.buffer_manager.get_script_var(var_name)
```

**Why this works in both contexts:**

| Context | text_var arrives as | After `${}` strip | get_script_var() |
|---------|-------------------|-------------------|------------------|
| Production (via handle_command) | `${LOG}` | `LOG` | Returns value |
| Test (direct handle_escape_command) | `${LOG}` | `LOG` | Returns value |

In both cases `text_var` arrives as `${LOG}` because:
- Production: exclusion list prevents resolution before handler
- Test: raw string passed directly

The pattern is the same as `/calc` — the handler resolves variables **internally** rather than relying on pre-resolution.

#### Why the Exclusion List Still Matters

The exclusion list at lines 1815 and 2044 of `chatybot_app.py` prevents `handle_command` from resolving `${LOG}` **before** the handler runs. Without it:

```python
# handle_command resolves ${LOG} to "error info error warn error"
processed_command = self.buffer_manager.replace_placeholders_legacy(command)
# Handler receives: /str_search "error" error info error warn error
# tokens[1] = "error" (first unquoted word after pattern)
```

The exclusion ensures `${LOG}` stays as a variable reference so the handler can look it up correctly and differentiate between the variable name and its value.

### 4. Pattern Substitution vs Variable Reference

There's an asymmetry in how `pattern_str` and `text_var` are handled:

| Argument | Resolution Method | Reason |
|----------|------------------|--------|
| `pattern_str` | `replace_placeholders_legacy()` | Pattern can contain `${var}` references (e.g., `/str_search "${search_term}" ${TEXT}`) |
| `text_var` | `${}` strip only | Must remain a variable **name** to look up the value |

If `text_var` were also passed through `replace_placeholders_legacy`, the variable's value would be substituted in place of the name, and the lookup would fail (as described in the bug above).

### 5. Protected Variable `STR_SEARCH`

`STR_SEARCH` was added to `ScriptVars.protected_vars` in `buffer_manager.py`, matching the pattern of `CALC`. This prevents users from overwriting it with `/setvar`:

```python
# /setvar STR_SEARCH 999
# → Error: 'STR_SEARCH' is a protected variable and cannot be modified.
```

The handler uses `allow_protected=True` when calling `set_script_var()`, bypassing the protection for internal writes.

### 6. Default Variable Name

The default target variable is `STR_SEARCH` (matching the `CALC` convention). Users can override it with a custom name:

```
/str_search "error" ${LOG}        → saves to STR_SEARCH
/str_search "error" ${LOG} c cnt  → saves to cnt
```

### 7. Tool Function (Standalone) vs Slash Command Handler

Two entry points exist, matching the `/calc` pattern:

| Entry Point | Location | Use Case |
|------------|----------|----------|
| Slash command handler | `chatybot_app.py:6030` | User typing `/str_search` |
| Tool function | `tools/str_utils.py:17` | LLM tool calling via dispatcher |

The tool function `str_search()` accepts explicit parameters (`pattern`, `text`, `mode`, `case_sensitive`, `target_variable`, `app`) and returns a dict. The slash command handler parses the raw command string and delegates to the tool function.

### 8. Regex Escape for Safety

Patterns are escaped with `re.escape()` before searching:

```python
matches = list(re.finditer(re.escape(pattern), text, re_flags))
```

This means `a+b` searches for the literal string `a+b`, not "a followed by one or more b". The command is documented as substring search, not regex search. Keeping it literal avoids confusion and security concerns.

### 9. Localization

Aliases were added for all supported languages:

| Language | Alias |
|----------|-------|
| English | `/str_search` |
| Spanish | `/str_search` |
| French | `/str_search` |
| Chinese | `/str_search` |
| Italian | `/str_search` |
| Arabic | `/str_search` |

No translated aliases were created because "str_search" is a technical command name (like `/calc` which also uses the same alias across languages, with only the natural-language variant translated: `/calcular`, `/calculer`, etc.). If translated aliases are desired later, they can be added to `translations.json`.

### 10. Dispatcher Tool Config

`tools_config.toml` was updated with a `[tools.str_search]` section so the LLM can also invoke the search via the tool dispatcher:

```toml
[tools.str_search]
enabled = true
description = "Search for a substring pattern in text..."
module = "chatybot.tools.str_utils"
function = "str_search"
```

Parameters mirror the tool function signature: `pattern` (required), `text` (required), `mode` (optional), `case_sensitive` (optional), `target_variable` (optional).

## Files Changed

| File | Lines | Purpose |
|------|-------|---------|
| `src/chatybot/tools/str_utils.py` | New (103) | Core `str_search()` tool function |
| `src/chatybot/chatybot_app.py` | +80, ~3 | Slash command handler, exclusion list, help text |
| `src/chatybot/chaty_help.py` | +12 | `CommandHelp` registration |
| `src/chatybot/tools_config.toml` | +22 | Dispatcher tool config |
| `src/chatybot/buffer_manager.py` | +1 | Protected variable `STR_SEARCH` |
| `src/chatybot/translations.json` | +6 | Localization aliases (6 languages) |
| `test/test_str_search.py` | New (185) | 21 tests |

## Test Coverage

| Category | Tests | Covers |
|----------|-------|--------|
| Tool function (direct) | 11 | Count, case sensitivity, positions, empty inputs, regex escaping, target variable |
| Slash command | 8 | Default var, case-insensitive, custom var, positions, combined flags, no match, missing args, undefined var |
| Protected variable | 1 | Write prevention |
| Variable substitution | 1 | `${var}` in pattern argument |
