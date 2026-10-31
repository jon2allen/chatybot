# ChatDSL Procedure System Proposal (`defproc` / `endproc` / `/proc` / `local`)

**Document Version:** 1.1
**Date:** July 30, 2026 (date of the last commit touching this file: `12bc73a`, 2026-07-30 17:20 -0400)
**Status:** Implemented — validated against source and `test/test_procs.py` (14 tests green) on October 31, 2026; see Implementation Deviations and Open Items below
**Applies To:** ChatDSL procedure system — `defproc`/`endproc`/`local` capture in `chatybot_app.py`, `/proc` execution in `commands/proc_macros.py`, `ScriptVars` protected variables in `buffer_manager.py`

---

## Implementation Deviations (as-built vs. this proposal)

Validated claim-by-claim on 2026-10-31. Phase 1 (file-based `/proc`, Save/Restore, `/script` parameter fix) and Phase 2 (inline `defproc`/`endproc`, `local` scope, `PROC_MAX_DEPTH` guard) are implemented as specified, including the `(proc)>` REPL prompt verbatim. The deviations all fall in the reserved-variables section (§9 of the embedded spec):

1. **`PROC_RESULT` has no system behavior.** It is never referenced in source; it works only because any script variable is settable. The "standard return value convention" is unenforced — usable, but nothing reserves it.
2. **`PROC_MAX_DEPTH` is honored but not in `protected_vars`.** Read from `ScriptVars` with default 20 (invalid values warn and fall back to 20), but the proposal's "must be added to `ScriptVars.protected_vars`" was not done — it is a plain user-writable variable.
3. **`LAST_ERROR` does not exist.** No reference anywhere in `src/`; the "captures text of last failed command/tool, system-only" variable was not implemented.
4. **`SYS_*` / `CHATY_*` prefix reservations are not implemented.** `protected_vars` in `buffer_manager.py` is a fixed name list (`AGENTIC_LOOP`, `CHAT_HISTORY`, `LAST_RESPONSE`, `RUN_*`, `DECIDE_*`, etc.); there is no prefix-matching reservation logic.
5. **`LAST_RESPONSE` is protected as specified** — the one §9 entry fully delivered.
6. **`local` at top level silently becomes a global.** Outside a procedure there is no stack frame, so `local x = 1` at script top level leaks permanently. The proposal never specified this case.
7. **Nested `defproc` is a hard error, but script mode does not abort the run.** The implementation prints the error, discards the outer procedure body, and continues processing the rest of the script; REPL mode aborts the capture without defining. The proposal said "print an error and abort" — the script-mode behavior is softer than specified.
8. **File-based `/proc` search paths are a superset.** As built: memory → `name` → `name.chatdsl` → `procs/name.chatdsl` → `~/.config/chatybot/procs/name.chatdsl`, with wrapper `defproc`/`endproc` lines stripped. The proposal specified only `./procs/name.chatdsl`.

## Open Items

1. **Reserved-variable enforcement:** implement `LAST_ERROR` and `SYS_*`/`CHATY_*` prefix reservations in `buffer_manager.py`, or formally drop them from the spec.
2. **Decide the reservation status of `PROC_RESULT` and `PROC_MAX_DEPTH`:** add to `protected_vars` (strictly managed) or document them as unreserved conventions.
3. **Define top-level `local` semantics:** currently a silent global set; either reject it outside procedures or document the behavior.
4. **Nested `defproc` in scripts:** decide whether the current discard-and-continue behavior is intended, or whether it should abort the script run.
5. **Doc consistency:** this file now carries the same status/version header convention as `doc/proposal_*.md`; the embedded spec below still reads "Status: Design Review" and is retained verbatim as the historical design record.

---

This is a great technical direction. To make ChatDSL procedures truly powerful and resilient—especially for recursion and complex logic—moving beyond purely global state is essential.

Here is a review and discussion of the best options for handling script variables, local scoping, recursion, and reserved system globals, followed by the fully regenerated specification.

### 1. Supporting Local-Only Script Variables

Currently, `ScriptVars` is a single dictionary with no namespacing. If a procedure uses a variable `idx`, it overwrites any existing `idx` in the global scope.

**Best Options for Local Scope:**

* **The "Save/Restore" Pattern (Context Manager Approach):** When a procedure is called, the executor snapshots the current values of any parameters or explicitly declared local variables. When the procedure exits, it restores the original values. This simulates a local scope without requiring a full rewrite of `ScriptVars` into a call stack.
* **The `local` Keyword:** Introduce a `local var_name = value` declarative command. During a procedure call, the executor tracks variables declared as `local`. Upon `endproc`, it purges them from `ScriptVars` (or restores their pre-call global state).

**Recommendation:** Implement the **Save/Restore** pattern for all procedure parameters by default. Add a `local` keyword for internal variables that shouldn't bleed out of the procedure.

### 2. Recursion Considerations

Recursion is currently permitted, with a depth guard configurable via `PROC_MAX_DEPTH` (default 20). However, recursion inherently breaks if variables are strictly global.

* **The Problem:** If `defproc factorial(n)` relies on a global `n`, calling `factorial(n-1)` overwrites the `n` needed when the call stack unwinds.
* **The Solution:** Recursion *requires* the Save/Restore mechanism mentioned above. By snapshotting parameter states before a nested `/proc` call and restoring them after, you create a virtual call stack within the flat `ScriptVars` dictionary.

### 3. Reserved System Global Variables

To prevent user scripts from breaking system mechanics, certain global variables must be reserved and protected.

**Recommended Reserved Variables:**

* **`PROC_RESULT`**: The standard convention for procedure return values.


* **`PROC_MAX_DEPTH`**: The configurable recursion depth limit.


* **`LAST_RESPONSE`**: Populated automatically by the LLM chat completion.


* **`LAST_ERROR`**: To capture error states from failed commands or tools.
* **`SYS_*` and `CHATY_***`: Reserving specific prefixes is best practice so the system can safely inject context (e.g., `SYS_CURRENT_FILE`, `SYS_OS`) without fear of collision.

---

### 📄 Regenerated Complete Specification

```markdown
# ChatDSL Procedure Design — Complete Specification

**Date:** 2026-07-30 (updated)
**Status:** Design Review
**Files Reviewed:** `chatdsl_parse.py`, `chatybot_app.py` (`execute_script`, `handle_escape_command`, `/script` handler)

---

## 📌 Executive Summary

This document specifies the design for **`defproc` / `endproc` / `/proc`**, a reusable procedure system for ChatDSL scripts. The goal is to enable named, callable blocks of ChatDSL commands with parameter passing, local variable scoping, recursion, and return value conventions.

---

## 1️⃣ Background & Motivation

### Current Reuse Mechanisms
ChatDSL scripts currently support two reuse mechanisms:

| Mechanism       | Defined By                          | Called By               | Body Type          | Parameters       |
|-----------------|-------------------------------------|-------------------------|--------------------|------------------|
| `def` macro     | `def name(p1, p2) = "template {p1}"` | `%name(arg1, arg2)`    | Single-line template | Positional       |
| `/multiline`    | `/multiline` ... `;;` `/multiline`   | Inline only            | Multi-line text    | None             |

### Problems
- **Macros** are limited to single-line string templates. They cannot include commands or LLM calls.
- **`/multiline`** is anonymous and non-reusable.
- **No way** to factor out repeated sequences of commands into a named, callable unit with isolated state.

### Goal
Add `defproc` to define a named, reusable block of ChatDSL commands, and `/proc` to call it — with named parameter passing, local scoping to prevent state bleeding, and a return value convention.

---

## 2️⃣ Current Architecture

### Key Facts
- `execute_script()` in `chatybot_app.py` builds a flat `commands_list` by splitting the script on `\n` and `;;`.
- Commands are dispatched one-by-one through `execute_script_command()` → `handle_escape_command()`.
- `/multiline` is handled by an `in_multi_line` state flag + `multi_line_buffer` in the main loop.
- **All variables are global** — `ScriptVars` is a single dict with no namespacing[cite: 1].
- `/script myfile.chatdsl x="v" y="v" z="v"` already injects named variables before running a file, but the regex is **hardcoded to only `x`, `y`, `z`**[cite: 1] (see Section 5).

---

## 3️⃣ Design Decisions: Keyword Conventions

### Why No Slashes on `defproc` and `endproc`
All `/verb` commands in ChatDSL are **imperative actions** — they perform an action immediately (e.g., `/setvar`, `/model`). Structural/declarative keywords already exist **without** a slash (e.g., `set`, `def`, `if`, `wait`).

`defproc` and `endproc` are **structural** — they delimit a definition block, not an action. Using slashes would create the first slash-commands that don't perform an immediate action.

### The Keyword Table
| Keyword               | Slash? | Role                                      |
|-----------------------|--------|-------------------------------------------|
| `defproc name(params)`| **No** | Starts a procedure definition (declarative) |
| `endproc`             | **No** | Ends/commits a procedure definition (structural) |
| `local var = val`     | **No** | Declares a variable scoped only to the proc |
| `/proc name key=val`  | **Yes**| Calls/executes a procedure (imperative)   |

---

## 4️⃣ Syntax Specification

### Script Mode
```chatdsl
# --- Definition ---
defproc analyze_code(lang, target)
  /file ${target}
  local mode = "security"
  /multiline
  Analyze this ${lang} code for ${mode} issues.
  Focus on memory safety and injection vectors.
  ;;
  /multiline
  set PROC_RESULT = ${LAST_RESPONSE}
endproc

# --- Call ---
/proc analyze_code lang="Python" target="mycode.py"

```

#### Key Points:

* `defproc name(p1, p2)` opens the block — params are optional.
* `local name = value` defines an internal variable that will be purged upon `endproc`.
* `endproc` on its own line closes and commits the procedure.
* `/proc name key=val ...` executes a defined procedure.

### REPL (Interactive) Mode

In the interactive REPL, typing `defproc` on a line by itself (or with its header) automatically enters a multiline capture mode.

```chatdsl
chat --> defproc greet(name)
(proc)> local greeting = "Hello ${name}!"
(proc)> echo ${greeting}
(proc)> endproc
Procedure 'greet' defined with params: [name]

```

---

## 5️⃣ The `/script` Parameter Bug Fix

The `/script` command in `chatybot_app.py` (line 4822) restricts parameter names to only `x`, `y`, `z`.

#### Fix (one line):

```python
# Fixed: accept any valid identifier
param_pattern = r'(^|\s+)([a-zA-Z_]\w*)\s*=\s*(".*?"|\'.*?\'|\S+)'

```

---

## 6️⃣ Implementation Options

| Option | Description | Pros | Cons | Effort |
| --- | --- | --- | --- | --- |
| **C** | Named parameters (preferred) | Self-documenting; safe for complex values | Slightly more implementation | 4-6 hours |
| **D** | File-based procedures | No new state machine; reuses `/script` | No inline definition; procedures always in files | 1-2 hours |

*Option C (Named Parameters) is the selected path for phase 2.*

---

## 7️⃣ Local Variables and State Isolation

Since `ScriptVars` is a single flat dictionary, we must simulate a call stack to prevent variable collision, particularly for recursion.

### The Save/Restore Mechanism (Virtual Stack)

1. **Procedure Call Entry:** When `/proc foo x="1"` is called, the executor snapshots the current global value of `x` (if it exists). It then injects `x="1"` into `ScriptVars`.
2. **Local Declarations:** When `local y = "2"` is encountered, the executor snapshots the current global value of `y` (if it exists) and injects `y="2"` into `ScriptVars`.
3. **Procedure Exit:** When `endproc` is reached, the executor restores `x` and `y` to their original snapshotted values. If they didn't exist prior to the call, they are deleted from `ScriptVars`.

**Benefits:**

* Perfect backward compatibility with `ScriptVars`.
* Prevents "internal state bleeding".


* Safely enables deep recursion.

---

## 8️⃣ Return Values

| Pattern | Description | Recommendation |
| --- | --- | --- |
| **Caller-Named Output (`out=var`)** | The caller passes an `out=varname` parameter. The procedure writes its result to `${out}`. | **Primary Idiom.** Safe under nesting and recursion. |
| **Convention: `PROC_RESULT**` | The procedure writes its output to `PROC_RESULT`. The caller reads it after the call.

 | Secondary convenience for simple scripts. |

---

## 9️⃣ Reserved System Global Variables

To ensure procedures and user scripts do not corrupt system state, the following variables must be added to `ScriptVars.protected_vars` (or strictly managed):

| Variable Name | Purpose | Writable by Script? |
| --- | --- | --- |
| `PROC_RESULT` | Standard output convention.

 | Yes |
| `PROC_MAX_DEPTH` | Limits recursion depth to prevent infinite loops.

 | Yes |
| `LAST_RESPONSE` | Holds the immediate output of the last LLM call.

 | System Only |
| `LAST_ERROR` | Captures the text of the last failed command/tool. | System Only |
| `SYS_*` | Namespace reserved for system context (e.g., `SYS_OS`, `SYS_CWD`). | System Only |
| `CHATY_*` | Namespace reserved for application-level state. | System Only |

*Note: `PROC_RESULT` and `PROC_MAX_DEPTH` are writable by the user to allow configuration and return value assignment, but their behavior is system-reserved.*

---

## 🔟 Decided Rules

1. **No Nested `defproc`:**
A `defproc` keyword encountered inside a proc body is a **hard error**. The executor must detect this during capture mode and immediately print an error and abort.
2. **Recursion Allowed:**
`/proc name` inside a proc body is legal.
**Requirement 1:** A depth guard configurable via `PROC_MAX_DEPTH` (default: 20). If exceeded, the executor throws a hard error.
**Requirement 2:** True recursion relies on the "Save/Restore" mechanism (Section 7) so that recursive calls do not clobber the parameters of the parent frame.



---

## 1️⃣1️⃣ Recommended Two-Phase Plan

### Phase 1 — File-Based `/proc` (Option D) + Param Fix

**Deliverables:**

* Fix `/script` param regex to accept any identifier name.
* Add `/proc name [key=val ...]` that resolves to `./procs/name.chatdsl`.
* Implement Save/Restore mechanism for parameters injected into `ScriptVars`.

### Phase 2 — Inline `defproc` / `endproc` + `local` Scope

**Deliverables:**

* Add `defproc` / `endproc` detection to `execute_script_command`.
* Add `local var = val` command.
* Add `in_defproc` capture state to `execute_script` loop.
* Add recursion depth guard (`PROC_MAX_DEPTH`).
* Store bodies in memory and extend `/proc` to check memory before filesystem.

---

## 📚 Appendix: Syntax Quick Reference

```chatdsl
# Definition with parameters and local variables
defproc recursive_search(dir, pattern, out)
  local current_depth = 1
  /multiline
  Search ${dir} for${pattern}.
  ;;
  /multiline
  set ${out} =${LAST_RESPONSE}
endproc

# Call with return variable mapping
/proc recursive_search dir="./src" pattern="auth" out="search_results"
echo ${search_results}

```

```

```
