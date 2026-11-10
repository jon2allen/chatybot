# String Modifiers Implementation Document

**Feature:** Variable Modifier Expansion (`${var:modifier}`) & String Utilities Engine  
**Branch:** `if_update`  
**Date:** November 2026  
**Status:** Implemented & Verified  

---

## 1. Overview & Motivation

In ChatDSL scripts and interactive prompts, user input frequently varies in casing, leading/trailing whitespace, or length (for instance, `/ask` returning `"Yes"`, `"YES"`, or `" yes "`). Previously, comparing or formatting string variables required exact textual matching or external processing.

This feature introduces **Variable Modifiers** (`${var:modifier}`) and an underlying **String Utilities Engine** ([`str_utils.py`](file:///Users/jon2allen/github/chatybot/src/chatybot/tools/str_utils.py)). It allows inline transformations directly during variable placeholder resolution anywhere in Chatybot (conditionals, prompt buffers, `/echo`, `/set`, and templates), without introducing external dependencies.

---

## 2. Architecture & Component Integration

```
                         ┌──────────────────────────────────────────────┐
                         │       src/chatybot/tools/str_utils.py        │
                         │    (Dedicated String Utilities Module)       │
                         │    - apply_string_modifier(val, spec)        │
                         │    - STRING_MODIFIERS registry               │
                         └──────────────┬───────────────────────────────┘
                                        │ imports
                ┌───────────────────────┴──────────────────────────────┐
                ▼                                                      ▼
┌─────────────────────────────────┐                  ┌──────────────────────────────────┐
│  src/chatybot/buffer_manager.py │                  │   src/chatybot/chatybot_app.py   │
│  - replace_placeholders()       │                  │  - evaluate_condition()          │
│    expands: ${var:modifier}     │                  │    supports: toggle:lower == yes │
│             ${arr[0]:modifier}  │                  │              $toggle:upper == YES│
└────────────────┬────────────────┘                  └──────────────────────────────────┘
                 │
                 ▼
Used everywhere: Prompts, Scripts, /set, /echo, LLM messages, /calc
```

### Component Roles:

1. **`src/chatybot/tools/str_utils.py`**:
   - Pure-Python module with zero application state or circular dependencies.
   - Houses `STRING_MODIFIERS` mapping and `apply_string_modifier(val, modifier_spec)`.
   - Supports single modifiers, chained modifiers (colon-separated), and parametric modifiers (`slice:start:end`).

2. **`src/chatybot/buffer_manager.py`**:
   - In `BufferManager.replace_placeholders`, recognizes modifier suffixes in braced variable references with a leading `$`: `${KEY:MODIFIER}` and `${ARRAY[INDEX]:MODIFIER}`.
   - Plain unbraced `$KEY` references expand normally across prompt text, even when followed by punctuation or colons (e.g. `Summarize $topic: be brief`).
   - Preserves plain `{key}` format specifications (e.g. `{x:02d}`, `{model:gpt-4}`) and JSON/dictionary syntax (e.g. `d = {a:1}`) by requiring the leading `$` for modifiers.
   - Updates `clear_unresolved` regex so only unresolved modified variables (`${UNKNOWN:lower}`) are purged, leaving JSON or python format specs intact.

3. **`src/chatybot/chatybot_app.py`**:
   - In `ChatybotApp.evaluate_condition`, pre-resolves unbraced `$var:modifier` operands, respecting quotes (avoids double quoting when already enclosed in quotes, e.g. `"$ans:trim:lower" == "yes"`).
   - Properly matches open-ended slice modifiers with trailing colons (e.g. `$id:slice:-3:`, `$id:slice:5:`).
   - `_resolve_operand` handles bare variable syntax with modifiers (e.g. `toggle:lower == "yes"`).
   - Operands enclosed in quotes (`"12:30"`, `"https://..."`) are strictly treated as string literals, protecting embedded colons from being misinterpreted as modifiers.
   - Colon splitting for modifiers is only activated when the left part is a known variable name.
   - Bare modifier truthiness checks (`if flag:lower then`) evaluate the variable transformation directly before boolean resolution.

---

## 3. Supported Modifiers Reference

| Modifier | Example | Input | Output | Description |
| :--- | :--- | :--- | :--- | :--- |
| `lower` | `${name:lower}` | `"Alice Smith"` | `"alice smith"` | Converts string to lowercase |
| `upper` | `${env:upper}` | `"prod"` | `"PROD"` | Converts string to uppercase |
| `title` | `${msg:title}` | `"hello world"` | `"Hello World"` | Converts string to title case |
| `capitalize` | `${word:capitalize}` | `"admin"` | `"Admin"` | Capitalizes first character |
| `trim` / `strip` | `${text:trim}` | `"  hello  "` | `"hello"` | Strips leading and trailing whitespace |
| `ltrim` / `lstrip` | `${text:ltrim}` | `"  hello  "` | `"hello  "` | Strips leading whitespace |
| `rtrim` / `rstrip` | `${text:rtrim}` | `"  hello  "` | `"  hello"` | Strips trailing whitespace |
| `len` / `length` | `${code:len}` | `"ABC123"` | `"6"` | Returns character count as numeric string |
| `slice:s:e` | `${id:slice:0:4}` | `"user_101"` | `"user"` | Substring slice by index (`start:end`) |
| `slice:s:` | `${id:slice:5:}` | `"user_101"` | `"101"` | Substring slice from start to end |
| `slice:-n:` | `${id:slice:-3:}` | `"user_101"` | `"101"` | Negative index slicing from end |

### Chaining Modifiers:
Multiple modifiers can be chained sequentially using colons:
```chatdsl
set raw_input = "   yEs   "
set clean = "${raw_input:trim:lower}"
# Result: "yes"

set text = "abcdef"
set result = "${text:slice:0:3:upper}"
# Result: "ABC"
```

---

## 4. ChatDSL Usage Examples

### 1. Robust Case-Insensitive Conditionals

```chatdsl
/ask "Proceed with deployment (Yes/No)?" -> CONFIRM

# Matches "yes", "YES", "Yes", "  yes  ", etc.
if CONFIRM:trim:lower == "yes" then
    /echo "Starting deployment..."
else
    /echo "Deployment cancelled."
endif
```

### 2. Formatted Output and Prompts

```chatdsl
set username = "john doe"
set user_role = "admin"

/echo Welcome, ${username:title}! Your role is: [${user_role:upper}]
# Output: Welcome, John Doe! Your role is: [ADMIN]
```

### 3. String Length Checks

```chatdsl
/ask "Enter a password:" -> PWD

if PWD:len < 8 then
    /echo "Error: Password must be at least 8 characters long."
else
    /echo "Password length accepted."
endif
```

### 4. Array Element Formatting

```chatdsl
set items[] = ["apple", "BANANA", "cherry"]

foreach item in items
    /echo Item: ${item:capitalize}
endfor
# Output:
# Item: Apple
# Item: Banana
# Item: Cherry
```

---

## 5. Operand Quoting & Safety Guidelines

1. **Quoted Operands are Strictly String Literals**:
   In `if` condition expressions, quoted operands (e.g. `"yes"`, `"12:30"`, `"abc:len"`) are strictly evaluated as string literals. They are never inspected or resolved as variable names or modifier pipelines, preventing injection or confusion with colons in URLs/timestamps.

2. **Quoting Expanded Operands**:
   When comparing variables whose contents are user-provided or dynamically generated (e.g., from `/ask` or `$LAST_RESPONSE`), it is recommended to quote the operand:
   ```chatdsl
   if "$user_input" == "yes" then
   # or with modifiers:
   if "${user_input:trim:lower}" == "yes" then
   ```
   This guarantees the expanded string is evaluated as a strict literal.

3. **Unicode Word Handling in `title`**:
   The `title` modifier capitalizes initial letters using Unicode character class matching (`[^\W\d_]`), correctly handling accented and international characters (e.g. `élan vital über` -> `Élan Vital Über`).

4. **Modifier Error Handling**:
   - Unknown modifiers emit a descriptive console warning (listing supported modifiers) and preserve the input string untouched.
   - Malformed slice specifications (e.g. non-numeric bounds or bare `slice`) emit `Warning: Invalid slice parameters in modifier '...'. Usage: slice:start:end` and preserve the input string.

---

## 6. Testing & Verification

Comprehensive test coverage is implemented in [`test/test_str_modifiers.py`](file:///Users/jon2allen/github/chatybot/test/test_str_modifiers.py):

1. **Unit Tests (`str_utils.py`)**:
   - `test_apply_string_modifier_basic_transforms`: verifies `lower`, `upper`, `title`, `capitalize`, `trim`, `ltrim`, `rtrim`, `len`, including Unicode support for `title`.
   - `test_apply_string_modifier_slice`: verifies forward, backward, omitted index, and negative index slices.
   - `test_apply_string_modifier_slice_invalid`: verifies warnings and graceful recovery for malformed slice parameters.
   - `test_apply_string_modifier_chained`: verifies multi-stage pipeline transformations (`trim:upper:len`, `slice:0:3:upper`).
   - `test_apply_string_modifier_edge_cases`: verifies empty strings, non-string values, and unknown modifiers.

2. **Placeholder Expansion Tests (`buffer_manager.py`)**:
   - `test_buffer_manager_modifiers`: validates `${VAR:modifier}` and `${ARRAY[idx]:modifier}` expansion.
   - `test_buffer_manager_unbraced_colon_expansion`: validates that unbraced `$var:` in normal prompt text (e.g. `Summarize $topic: be brief`) expands cleanly.
   - `test_buffer_manager_clear_unresolved_with_modifiers`: verifies unresolved modified variables are cleanly removed when `clear_unresolved=True`, while preserving JSON dicts and Python format strings (`{x:02d}`).

3. **Condition Evaluator & Script Tests (`chatybot_app.py`)**:
   - `test_evaluate_condition_colon_operands`: verifies that colons in literals, timestamps (`"12:30"`), URLs, and variable values are not treated as modifier splitters.
   - `test_evaluate_condition_modifiers`: verifies braced and bare syntax inside `if` comparisons.
   - `test_evaluate_condition_bare_modifier_truthiness`: verifies truthiness evaluation without binary operators (`flag:lower`).
   - `test_chatdsl_script_with_modifiers`: end-to-end execution of multi-line `if/else/endif` blocks using string modifiers.

All 92 related tests across the test suite (`test_if_blocks.py`, `test_if_numeric.py`, `test_procs.py`, `test_foreach.py`, `test_str_modifiers.py`) pass cleanly.

