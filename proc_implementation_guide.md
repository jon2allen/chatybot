# ChatDSL Procedure System — Implementation & User Guide

**Document:** `proc_implementation_guide.md`  
**Date:** 2026-07-30  
**Status:** Implemented & Fully Verified  

---

## 1. Overview & Syntax Architecture

The ChatDSL Procedure System adds reusable subroutines with parameter passing, local scoping, recursion support, and interactive REPL capture.

### Keyword Conventions: Imperative vs. Structural

ChatDSL distinguishes between **imperative action verbs** (which execute immediately and start with `/`) and **structural/declarative keywords** (which delimit blocks or assign state without a slash):

| Keyword | Type | Syntax | Description |
|---|---|---|---|
| `defproc` | Non-slash (declarative) | `defproc name(p1, p2)` or `defproc name` | Starts a procedure definition block. |
| `endproc` | Non-slash (structural) | `endproc` | Ends and commits a procedure definition block. |
| `local` | Non-slash (declarative) | `local var = value` or `local var` | Declares a variable scoped exclusively to the active procedure frame. |
| `/proc` | Slash command (imperative) | `/proc name key="val" ...` | Executes a defined procedure (in-memory or file fallback). |

---

## 2. Special Features & Mechanics

### Unblocked Parameter Identifiers
Parameter keys are no longer restricted to single-letter `x,y,z`. Any valid DSL/Python identifier (`[a-zA-Z_]\w*`) is supported for both `/script` and `/proc`:

```chatdsl
/proc generate_report topic="Quantum Computing" target_file="report.md" out="final_doc"
```

### Local Scoping & Virtual Stack Frame (Save/Restore)
Although ChatDSL's `ScriptVars` dictionary remains flat for global compatibility, procedures simulate true stack frames using a **Save/Restore Virtual Stack**:

1. **Call Entry:** When `/proc foo param_a="val"` is called, the executor pushes a stack frame (`active_proc_stack`).
2. **Snapshotting:** Before parameters or `local` variables are written, their previous global state is snapshotted in the frame.
3. **Execution:** The procedure body runs using standard variable replacement (`${param_a}`, `${local_var}`).
4. **Call Exit:** Upon `endproc` or completion, the frame is popped and all snapshotted variables are restored to their pre-call values (or deleted if they didn't exist prior to the call).

### Interactive REPL Capture Mode
In interactive mode (`chat -->`), entering `defproc name` switches the prompt to `(proc)>` and captures lines interactively until `endproc` appears on a line by itself:

```
chat --> defproc quick_summary(subject)
(proc)> Summarize ${subject} in 3 bullet points.
(proc)> set PROC_RESULT = ${LAST_RESPONSE}
(proc)> endproc
Procedure 'quick_summary' defined with params: [subject]
```

### Interactive Prompt Execution inside Procedures
When `/proc` runs—whether invoked from a script or interactively from the REPL prompt—plain text lines (such as `what are five cities in Italy`) are automatically dispatched to `chat_completion`. Answers appear on screen and update `CHAT_HISTORY`, making downstream commands like `/save file.txt` work seamlessly.

### File-Based Fallback Resolution
When `/proc name` is called, the executor checks:
1. In-memory `self.procedures` table first.
2. If not found in memory, resolves disk paths in order:
   - `./name.chatdsl`
   - `./procs/name.chatdsl`
   - `~/.chatybot/procs/name.chatdsl`

---

## 3. Rules & Guardrails

### 1. No Nested `defproc`
Defining a `defproc` inside another procedure body is a **hard error**. The executor cancels procedure capture immediately:

```chatdsl
# INVALID - Will trigger a hard error:
defproc outer()
  defproc inner()   # HARD ERROR: Nested defproc is not allowed.
  endproc
endproc
```

### 2. Recursion Support & `PROC_MAX_DEPTH`
Recursive calls (`/proc name` calling itself inside its body) are fully supported because parameter states are isolated per frame by the virtual stack.

To prevent infinite loops, recursion depth is guarded by `PROC_MAX_DEPTH` (default: **20**):

```chatdsl
# Adjust recursion depth limit if needed:
/setvar PROC_MAX_DEPTH 50
```

If recursion exceeds `PROC_MAX_DEPTH`, execution unwinds safely and prints an error message.

---

## 4. Reserved System Variables & Return Patterns

### System Variables Reference

| Variable Name | Case-Insensitive? | Description | Writable by Script? |
|---|---|---|---|
| `${LAST_RESPONSE}` | Yes (`${last_response}`) | Holds the text response from the last LLM prompt. | System / Protected |
| `${CHAT_HISTORY}` | Yes (`${chat_history}`) | Array/string of full conversation history. | System / Protected |
| `${PROC_RESULT}` | Yes (`${proc_result}`) | Standard global slot for single procedure return values. | **Yes** |
| `${PROC_MAX_DEPTH}` | Yes | Recursion depth limit (default: 20). | **Yes** |
| `${LAST_ERROR}` | Yes | Captures error text from the last failed command/tool. | System / Protected |

### Recommended Return Value Patterns

#### Pattern A — Caller-Named Output (`out=varname`) *(Primary & Recursion-Safe)*
The caller passes an `out="my_var"` parameter. Inside the proc, use `set ${out} = ...`:

```chatdsl
defproc calc_double(val, out)
  /calc "${val} * 2" temp_res
  set ${out} = ${temp_res}
endproc

/proc calc_double val="21" out="doubled_number"
# ${doubled_number} is now "42"
```

#### Pattern B — `PROC_RESULT` Convenience *(Simple, Single-Level)*
```chatdsl
defproc get_topic_info(topic)
  Tell me a fun fact about ${topic}.
  set PROC_RESULT = ${LAST_RESPONSE}
endproc

/proc get_topic_info topic="Astronomy"
/setvar fun_fact ${PROC_RESULT}
```

---

## 5. Sample Uses & Code Examples

### Sample 1: Interactive Multi-Query & Save Procedure

```chatdsl
defproc research_cities()
  what are five cities in Italy
  /save cities/italy.txt
  
  what are five cities in Bulgaria
  /save cities/bulgaria.txt
endproc

/proc research_cities
```

### Sample 2: Parameterized Code Security Review

```chatdsl
defproc review_code(language, filepath, out_var)
  local mode = "security and performance"
  /file ${filepath}
  
  /multiline
  Review this ${language} code focusing on ${mode}.
  Highlight critical vulnerabilities and suggest code diffs.
  ;;
  /multiline

  set ${out_var} = ${LAST_RESPONSE}
endproc

/proc review_code language="Python" filepath="src/auth.py" out_var="py_review"
/proc review_code language="Go"     filepath="src/server.go" out_var="go_review"
```

### Sample 3: Recursive Countdown Procedure

```chatdsl
defproc countdown(n, out)
  local is_zero = "no"
  if "${n} == 0" then set is_zero = "yes"
  
  if "${is_zero} == yes" then set ${out} = "done"
  
  if "${is_zero} == no" then /setvar next_n ${n}
  if "${is_zero} == no" then /calc "${next_n} - 1" next_n
  if "${is_zero} == no" then /proc countdown n="${next_n}" out="${out}"
endproc

/proc countdown n="5" out="countdown_status"
# ${countdown_status} will be "done"
```

### Sample 4: Utility Procedure Using `PROC_RESULT`

```chatdsl
defproc extract_json_block()
  Extract and validate any JSON objects present in ${LAST_RESPONSE}.
  set PROC_RESULT = ${LAST_RESPONSE}
endproc

Explain API endpoints for user authentication.
/proc extract_json_block
/setvar api_json ${PROC_RESULT}
```

---

## 6. Test Suite & Verification

The procedure system is verified by 9 unit tests in `test/test_procs.py`:

```bash
.venv/bin/pytest test/test_procs.py
```

Tests cover:
- Parameter identifier unblocking (`my_lang`, `target_file`).
- Inline `defproc` / `endproc` parsing and execution.
- Local scoping and snapshot restoration (`local` keyword).
- Parameterized return output (`out=var`).
- Recursive procedure frame isolation.
- Recursion depth limit (`PROC_MAX_DEPTH`).
- Hard error on nested `defproc`.
- Disk fallback procedure loading (`procs/external.chatdsl`).
- Interactive REPL prompt execution dispatch to LLM.
