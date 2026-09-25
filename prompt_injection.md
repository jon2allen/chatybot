# Implementation Plan: Inline Dynamic Context Injection (`!`cmd``) for Chatybot

**Document:** `prompt_injection.md`  
**Date:** September 25, 2026  
**Status:** Revised Architecture & Implementation Plan (post codebase review)  
**Target Scope:** Universal prompt pre-execution of short, synchronous host commands. Skill content coverage is a separate integration point (see Section 3.1).

---

## 1. Overview & Objectives

Dynamic Context Injection allows users and skill authors to embed lightweight shell commands directly into prompts or skill bodies using the syntax ``!`<command>` ``. 

Before the prompt payload is sent to the LLM, Chatybot detects these blocks, executes the command locally in a tightly constrained subshell, and replaces the tag with the command's `stdout`.

### Key Design Constraint: "Short Commands Only"
This feature is strictly for **quick, deterministic context gathering** (e.g. `git status -s`, `date`, `cat version.txt`, `which python3`). Any long-running, interactive, heavy build, or multi-step execution belongs in the existing `/run` and `/run_safe` facility.

---

## 2. Technical Requirements & Guardrails

| Requirement | Specification | Enforcement Mechanism |
| :--- | :--- | :--- |
| **Syntax** | ``!`command` `` | Case-sensitive regex: `r"!`([^`\r\n]+)`"` (backtick has no special meaning in regex; `\`` is a redundant escape) |
| **Execution Window** | **Strict timeout: 3.0 seconds max** | `subprocess.run(..., timeout=3.0)` |
| **Output Size Cap** | **Max 4 KB (or ~100 lines)** | Truncate `stdout` beyond 4096 bytes with notice: `[... truncated at 4KB ...]` |
| **Safety Integration** | Must respect `app.safe_mode` and `app.safe_mode_askfirst` | Check command against `app.check_dangerous()` (returns warning string or `None`); three-tier response: block / askfirst-confirm / allow |
| **Shell Execution** | `shell=False` with `shlex.split()` | Consistent with existing `execute_shell_command()` security model (`chatybot_app.py:3554`); prevents shell injection |
| **Failure Handling** | Non-zero exit code or timeout | Output inline notice: `[Command '...' failed (exit code N): ...]` or `[Timed out (>3s). Use /run for long commands]` |
| **Stdin Policy** | Non-interactive only | `stdin=subprocess.DEVNULL` (immediately fails commands expecting interactive input) |
| **No Re-entrancy** | Single-pass evaluation | Output text containing ``!`...` `` is treated as literal text; never recursively executed |
| **History Operator Disambiguation** | ``!`cmd` `` must not collide with existing `!` history search | The `!` history handler (`chatybot_app.py:6123`) intercepts prompts starting with `!`; it must check for an immediately-following backtick and skip interception when `` !` `` is detected |

### Safe Mode Default Behavior

`safe_mode` is `True` by default (`chatybot_app.py:150`). The existing `check_dangerous()` patterns block `;`, `|`, `&&`, `$(`, and backtick substitution. This means common commands like `git log | head`, `echo $(date)`, or `ls; pwd` will be **blocked by default**. Users must either run `/run unsafe` to disable safe mode, or the feature should consider its own narrower allowlist for read-only commands (e.g. `git`, `date`, `cat`, `which`, `ls`, `pwd`, `echo`) that bypasses the broad `check_dangerous()` patterns.

---

## 3. Architecture & Integration Points

The ideal location for this functionality is within **`BufferManager`** alongside placeholder and variable substitution, ensuring it applies universally across:
1. Interactive console prompts
2. ChatDSL scripts (`/script`, `/source`)
3. Multi-line blocks (`/multiline ... ;; /multiline`)

```
User Prompt
          │
          ▼
BufferManager.replace_placeholders(prompt)
          │
          ├─► 1. Replace variables: ${VAR}, {filebank1-5}, {imagebank1-5}
          │
          ├─► 2. Replace dynamic injection: !`command` (via expand_dynamic_injections)
          │        │
          │        ├─► Safe Mode check (check_dangerous: block / askfirst / allow)
          │        ├─► Run subprocess (shlex.split, shell=False, timeout=3s, DEVNULL stdin, cap=4KB)
          │        └─► Substitute stdout in place of !`...`
          │
          ▼
Final Expanded Prompt String ──► Sent to LLM
```

### 3.1 Skill Content Coverage (Separate Integration Point)

The original plan claimed coverage of "Injected skill content (`_inject_skills` in `chatybot_app.py`)". However, `_inject_skills` appends skill content to the **system message** (`chatybot_app.py:1461`), which happens *after* `replace_placeholders` runs on the **user prompt** (`chatybot_app.py:1351`). The system message never passes through `replace_placeholders`, so `` !`cmd` `` in skill bodies would never be expanded.

To cover skill content, `expand_dynamic_injections` must also be called inside `_inject_skills` on the `skill_block` string before it is appended to the system message. This is a separate code change from the `replace_placeholders` integration.

### 3.2 `/run` Command Exclusion

`replace_placeholders` is also called from the `/run` command handler (`tools.py:768`). A command like `` /run !`echo hi` `` would execute the `` !`echo hi` `` block during placeholder resolution, then pass the result to `execute_shell_command` for a second execution. To avoid this double-execution, `expand_dynamic_injections` should accept an `enabled` flag (defaulting to `True`) and the `/run` path should call `replace_placeholders` with dynamic injection disabled, or the `/run` handler should call `replace_placeholders` with a new `expand_injections=False` parameter.

---

## 4. Detailed Component Implementation Plan

### Step 4.1: Add `expand_dynamic_injections` in `BufferManager`
File: [`src/chatybot/buffer_manager.py`](file:///Users/jon2allen/github/chatybot/src/chatybot/buffer_manager.py)

Add helper method:
```python
import subprocess
import shlex
import re

DYNAMIC_INJECTION_PATTERN = re.compile(r"!`([^`\r\n]+)`")
MAX_DYNAMIC_INJECTION_BYTES = 4096
DYNAMIC_INJECTION_TIMEOUT = 3.0

def expand_dynamic_injections(self, text: str) -> str:
    """Executes inline !`cmd` blocks and substitutes stdout.
    
    Constrained to short, read-oriented commands. Long-running or interactive
    commands are aborted and directed to the /run facility.
    Uses shlex.split() + shell=False for security, consistent with
    execute_shell_command() in chatybot_app.py.
    """
    if "!`" not in text:
        return text

    def _eval_match(match: re.Match) -> str:
        cmd = match.group(1).strip()
        if not cmd:
            return ""

        # 1. Safe Mode Check (three-tier: block / askfirst / allow)
        app = getattr(self, "app", None)
        if app:
            danger = app.check_dangerous(cmd)
            if danger:
                if getattr(app, "safe_mode", False):
                    return f"[Blocked by safe_mode: '{cmd}' ({danger})]"
                elif getattr(app, "safe_mode_askfirst", False):
                    # In non-interactive prompt expansion, we cannot prompt
                    # the user, so default to blocking with a notice.
                    return f"[Blocked (safe_mode_askfirst, non-interactive): '{cmd}' ({danger})]"

        # 2. Execute with strict constraints (shell=False for security)
        try:
            res = subprocess.run(
                shlex.split(cmd),
                shell=False,
                capture_output=True,
                text=True,
                timeout=DYNAMIC_INJECTION_TIMEOUT,
                stdin=subprocess.DEVNULL,
            )
            output = res.stdout
            if len(output.encode("utf-8")) > MAX_DYNAMIC_INJECTION_BYTES:
                output = output[:MAX_DYNAMIC_INJECTION_BYTES] + "\n[... truncated at 4KB. Use /run for full output ...]"
            
            if res.returncode != 0 and not output.strip():
                err = res.stderr.strip() or f"exit code {res.returncode}"
                return f"[{cmd}: {err}]"
            return output.strip()

        except subprocess.TimeoutExpired:
            return f"[Command '{cmd}' timed out (>3s). Use /run for long-running commands.]"
        except ValueError as e:
            # shlex.split can raise on malformed commands
            return f"[Command parse error '{cmd}': {e}]"
        except Exception as e:
            return f"[Command error '{cmd}': {e}]"

    return DYNAMIC_INJECTION_PATTERN.sub(_eval_match, text)
```

### Step 4.2: Integrate into `replace_placeholders()`
File: [`src/chatybot/buffer_manager.py`](file:///Users/jon2allen/github/chatybot/src/chatybot/buffer_manager.py)

Inside `replace_placeholders(prompt, ...)`:
After resolving `${vars}` and `{filebank}` placeholders, pass `text_prompt` through `self.expand_dynamic_injections(text_prompt)`.

Add an `expand_injections: bool = True` parameter to `replace_placeholders()` so the `/run` handler can call it with `expand_injections=False` to avoid double-execution (see Section 3.2).

### Step 4.3: Integrate into `_inject_skills()` for Skill Content
File: [`src/chatybot/chatybot_app.py`](file:///Users/jon2allen/github/chatybot/src/chatybot/chatybot_app.py)

Inside `_inject_skills()` (line 5565), after assembling `skill_block` and before returning, call:
```python
skill_block = self.buffer_manager.expand_dynamic_injections(skill_block)
```
This ensures `` !`cmd` `` blocks in skill bodies are expanded before being injected into the system message.

### Step 4.4: Disambiguate from `!` History Operator
File: [`src/chatybot/chatybot_app.py`](file:///Users/jon2allen/github/chatybot/src/chatybot/chatybot_app.py)

The `!` history handler at line 6123 intercepts any prompt starting with `!`. Add a guard so that prompts starting with `` !` `` (bang-backtick) are NOT intercepted as history commands:
```python
if prompt.startswith("!") and not prompt.startswith("!`"):
    selected_command = await self.handle_history_command(prompt)
    ...
```

### Step 4.5: Trace & Audit Visibility
File: [`src/chatybot/chatybot_app.py`](file:///Users/jon2allen/github/chatybot/src/chatybot/chatybot_app.py)

When `/trace on` or `/debug on` is active, log any executed dynamic injection command and elapsed execution time to the console/log file so the user has full audit visibility into what ran locally before the prompt was dispatched.

### Step 4.6: Update Help and Documentation
- Update `chaty_help.py` under prompts/syntax to document the ``!`cmd` `` syntax.
- Update `doc/chatdsl_guide.md` and `chatdsl_bnf.txt` to include the ``!`cmd` `` syntax in `<text-content>`.
- Document the interaction with safe mode (ON by default; many common commands with `|`, `;`, `$()` will be blocked).

---

## 5. Test Cases & Verification Suite

Create [`test/test_dynamic_injection.py`](file:///Users/jon2allen/github/chatybot/test/test_dynamic_injection.py):

1. **Basic Substitution**:
   - Prompt: `"The year is !`echo 2026`."`
   - Expected: `"The year is 2026."`
2. **Timeout Enforcement**:
   - Prompt: `"Sleep: !`sleep 5`."`
   - Expected: Injects `[Command 'sleep 5' timed out (>3s). Use /run for long-running commands.]` within ~3 seconds without blocking the turn.
3. **Output Cap Enforcement**:
   - Prompt generating >4KB (e.g. `python -c "print('x'*5000)"`)
   - Expected: Output truncated at 4096 bytes with truncation notice.
4. **Safe Mode Enforcement (block)**:
   - With `safe_mode=True`, prompt: ``!`rm -rf /test```
   - Expected: Injects `[Blocked by safe_mode: 'rm -rf /test' (Recursive force delete (rm -rf))]`.
5. **Safe Mode Enforcement (askfirst, non-interactive)**:
   - With `safe_mode=False`, `safe_mode_askfirst=True`, prompt: ``!`rm -rf /test```
   - Expected: Injects `[Blocked (safe_mode_askfirst, non-interactive): ...]` (cannot prompt user during prompt expansion).
6. **Safe Mode Blocks Shell Operators by Default**:
   - With `safe_mode=True` (default), prompt: ``!`git log | head` ``
   - Expected: Blocked by `check_dangerous` (OR-chain pattern). Document that users must `/run unsafe` for piped commands.
7. **Non-Zero Exit & Stderr**:
   - Prompt: ``!`ls /nonexistent_directory_chatybot_xyz` ``
   - Expected: Captures error message or exit code without crashing application.
8. **shlex.split Parse Error**:
   - Prompt: ``!`echo "unterminated` ``
   - Expected: Injects `[Command parse error ...]` without crashing.
9. **History Operator Disambiguation**:
   - Prompt starting with `` !`echo hi` `` is NOT intercepted by the `!` history handler.
   - Prompt starting with `! git` (no backtick) IS intercepted by the history handler as before.
10. **No Double-Execution via /run**:
    - `/run !`echo hi`` does not execute `echo hi` twice (once in placeholder expansion, once in `execute_shell_command`).
11. **Interaction in Skills**:
    - Create a test skill with ``!`git --version` `` and verify the system message contains the git version string (requires Step 4.3 integration).

---

## 6. Implementation Rollout Checklist

- [ ] Add `expand_dynamic_injections` helper in `src/chatybot/buffer_manager.py` using `shlex.split()` + `shell=False`.
- [ ] Use `app.check_dangerous()` (not `is_safe_command`) for safe mode checks; handle three-tier response.
- [ ] Add `expand_injections` parameter to `replace_placeholders()`; call with `False` from `/run` handler.
- [ ] Call `expand_dynamic_injections` inside `_inject_skills()` for skill body coverage.
- [ ] Add `` !` `` guard to the `!` history handler in `chatybot_app.py` (line 6123).
- [ ] Ensure `stdin=subprocess.DEVNULL` and `timeout=3.0` are strictly applied.
- [ ] Add audit logging when `/trace` is enabled.
- [ ] Add test suite `test/test_dynamic_injection.py` and verify with `pytest`.
- [ ] Update `chatdsl_bnf.txt` and documentation.
- [ ] Document safe mode interaction (default ON blocks `|`, `;`, `$()`, backticks).
- [ ] Update `chatybot_todo.md` upon completion.
