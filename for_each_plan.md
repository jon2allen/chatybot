Here is a comprehensive design and implementation plan to support a structural, multi-line `foreach` loop in ChatDSL.

This design mirrors the declarative block structure you adopted for `defproc` and `endproc`, ensuring the language remains consistent, predictable, and easy to parse.

---

# 📌 ChatDSL `foreach` Multiline Specification

**Status:** Design Proposal

**Target Files:** `chatdsl_parse.py`, `chatybot_app.py` (`execute_script`, `execute_script_command`)

## 1️⃣ Syntax Design

We will introduce two new non-slash keywords: `foreach` and `endfor`. This avoids conflating structural flow control with imperative slash commands (like `/setvar` or `/proc`).

```chatdsl
# Standard multi-line loop
foreach file in source_files
  /echo "Currently analyzing: ${file}"
  /proc analyze_code target="${file}"
  wait 1
endfor

```

#### Key Characteristics:

* **`foreach <item_var> in <array_var>`**: The declaration header.
* **`<item_var>`**: A temporary variable injected into `ScriptVars` representing the current element.


* **`<array_var>`**: The name of the existing array in `ScriptVars` to iterate over.


* **`endfor`**: The structural terminator.

---

## 2️⃣ Architecture & Execution Model

Because `execute_script()` evaluates a flat list of commands sequentially, we cannot use standard pointer jumping without building a complex Abstract Syntax Tree (AST). Instead, we will use a **Capture and Replay** model—the exact same strategy planned for inline `defproc` bodies.

### The State Machine

We will introduce a `loop_stack` or a `foreach_depth` counter to the `execute_script()` main loop to track capture state.

1. **Enter Capture Mode:** When the parser hits `foreach item in array`, it increments `foreach_depth`. If depth is 1, it initializes an empty `foreach_buffer`, stores the `item` and `array` names, and moves to the next line.
2. **Buffering:** All subsequent lines are appended to the `foreach_buffer` as raw strings. If an inner `foreach` is encountered, `foreach_depth` increments (allowing for safely nested loops).
3. **Exit & Execute:** When `endfor` is encountered, `foreach_depth` decrements. When depth reaches 0, capture mode ends, and the loop is immediately executed.

### Replay Execution

Once the block is captured, the executor does the following in Python:

```python
# Conceptual Implementation in execute_script()
array_data = self.buffer_manager.script_vars.get(array_var_name, [])

if isinstance(array_data, list):
    for item_value in array_data:
        # 1. Inject the loop variable
        self.buffer_manager.set_script_var(item_var_name, item_value)
        
        # 2. Replay the captured block
        for buffered_cmd in foreach_buffer:
            self.execute_script_command(buffered_cmd)

```

---

## 3️⃣ Variable Scoping (The Save/Restore Pattern)

Since `ScriptVars` is a global, flat dictionary, the loop variable (`item`) will overwrite any existing global variable with the same name. To prevent data corruption, we must use the **Save/Restore** pattern during execution.

1. **Snapshot:** Before the `for` loop begins in Python, check if `<item_var>` already exists in `ScriptVars` and save its value.


2. **Iterate:** Run the loop, mutating `<item_var>` for each pass.
3. **Restore:** After the loop finishes, restore the original value of `<item_var>`. If it didn't exist prior to the loop, delete it from `ScriptVars`.

---

## 4️⃣ Implementation Phases

### Phase 1: Parser and Regex Updates

* **File:** `chatybot_app.py`
* **Action:** Add a regex pattern to `PatternMatcher` to capture the `foreach` header.
```python
# Matches: foreach item in my_array
foreach_pattern = re.compile(r'^foreach\s+([a-zA-Z_]\w*)\s+in\s+([a-zA-Z_]\w*)\s*$')

```


* **Action:** Add `foreach` and `endfor` to the `VALID_ESCAPE_COMMANDS` or keyword list in `chatdsl_parse.py`.



### Phase 2: State Tracking in Executor

* **File:** `chatybot_app.py` (`execute_script`)


* **Action:** Initialize state variables at the start of `execute_script()`:
```python
foreach_depth = 0
foreach_buffer = []
foreach_item_var = ""
foreach_array_var = ""

```


* **Action:** Modify the main command loop to catch the regex, increment depth, buffer lines, and catch `endfor`.

### Phase 3: Execution and Nesting

* **File:** `chatybot_app.py` (`execute_script`)


* **Action:** Implement the Python `for` loop that iterates over the `ScriptVars` array data.


* **Action:** Inside the Python `for` loop, recursively call `self.execute_script_command()` on the buffered lines. Because we are recursively calling the command executor, **nested `foreach` loops will work automatically** (the inner loop will trigger its own capture and replay).

---

## 5️⃣ Edge Cases to Mitigate

| Scenario | System Behavior |
| --- | --- |
| **Array does not exist** | If `array_var` is not in `ScriptVars`, the executor should treat it as an empty list and gracefully skip the block.

 |
| **Variable is not an array** | If `array_var` holds a string or integer, the executor should log a `LAST_ERROR` warning and skip the block, avoiding a crash. |
| **Empty Loop Body** | If `foreach` is immediately followed by `endfor`, the capture buffer is empty. The executor does nothing. |
| **Unclosed Loop** | If EOF is reached while `foreach_depth > 0`, throw a parsing error ("Unexpected end of script: missing 'endfor'"). |

---

How should the system handle a situation where the specified array variable does not exist or is not actually an array type within `ScriptVars`? Should it silently skip the loop as proposed, or would you prefer it throw a hard script-halting error?
