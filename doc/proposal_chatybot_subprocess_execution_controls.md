# Technical Proposal: Configurable Chatybot Sub-Process Execution & Developer Override Controls

**Document Version:** 1.0  
**Date:** October 25, 2026  
**Status:** Proposed / Under Review  
**Applies To:** Builtin Policy Engine (`BuiltinPolicyEngine`, `SecurityManager`), CLI flags, Environment Controls, and RACF Guard (`racf-guard`)  

---

## 1. Problem Statement & Motivation

Chatybot tools (especially `run_command`) include strict protections against running instances of `chatybot` from within `chatybot`:

1. **The Recursive Loop Risk:**  
   If an autonomous LLM agent executes `chatybot` inside a tool loop, it can spawn unbounded child sessions, consume memory/file descriptors, exhaust API rate limits, and lead to denial of service.
2. **The Privilege Escalation Risk:**  
   A sub-process running `chatybot` might attempt to bypass active session constraints or run in different privilege contexts.
3. **The Developer Dilemma (Dogfooding / Testing Obstacle):**  
   Developers working on Chatybot itself frequently need to:
   - Run integration tests (e.g. `pytest`, which spawns `chatybot` CLI commands).
   - Test CLI invocations (`chatybot --version`, `chatybot --help`, `chatybot --profile`).
   - Run benchmark scripts or multi-agent test environments.

Currently, `CHATYBOT_EXEC_PATTERN` in `BuiltinPolicyEngine` (Tier 0) is **hardcoded to unconditionally `DENY`** any command matching `chatybot`, `python -m chatybot`, or wrapper variations (`sudo chatybot`, `bash -c chatybot`). There is currently no official configuration flag or environment toggle to permit this when legitimately working on the codebase.

---

## 2. Multi-Layer Defense-in-Depth Model

To prevent recursive loops while supporting legitimate developer workflows, the system will provide four complementary layers:

```
                            Command Request (run_command)
                                         │
                                         ▼
                   ┌───────────────────────────────────────────┐
                   │  Is Chatybot sub-process pattern matched? │
                   │         (CHATYBOT_EXEC_PATTERN)           │
                   └─────────────────────┬─────────────────────┘
                                         │ Yes
                                         ▼
                   ┌───────────────────────────────────────────┐
                   │     Is Developer Override Active?         │
                   │  (config: allow_chatybot_subprocess=true  │
                   │   or env: CHATYBOT_ALLOW_SUBPROCESS=1     │
                   │   or CLI: --dev / --allow-sub-chatybot)   │
                   └─────────────────────┬─────────────────────┘
                                         │
                        ┌────────────────┴────────────────┐
                     No │                                 │ Yes
                        ▼                                 ▼
         ┌─────────────────────────────┐   ┌─────────────────────────────┐
         │       Hard DENY             │   │    Evaluated by Policy      │
         │ (Tier 0 blocked immediately)│   │ (allow or ask confirmation) │
         └─────────────────────────────┘   └──────────────┬──────────────┘
                                                          │ Child spawned
                                                          ▼
                                           ┌─────────────────────────────┐
                                           │ Recursion Guard in Child    │
                                           │ (Max depth / recursion lock)│
                                           └─────────────────────────────┘
```

---

## 3. Specification of Developer Controls

### 3.1 Configuration Toggle (`security.toml`)

Under the `[builtin]` section (and optionally top-level), introduce `allow_chatybot_subprocess` and `chatybot_exec_policy`:

```toml
[builtin]
# Policy for executing chatybot sub-processes via run_command.
# Options:
#   "deny"  (default) - Strictly block any chatybot execution in Tier 0.
#   "ask"   - Require explicit interactive user confirmation before running sub-chatybot.
#   "allow" - Unconditionally allow running chatybot sub-processes (recommended for test runners).
chatybot_exec_policy = "ask"

# Convenience boolean shorthand (true maps to "allow" or "ask"):
allow_chatybot_subprocess = true
```

### 3.2 Environment Variable Fast-Path

For developers running CI pipelines, test scripts, or local test runs without altering their persistent configuration file:

```bash
# Allow sub-process execution for this command run
export CHATYBOT_ALLOW_SUBPROCESS=1
# or
CHATYBOT_ALLOW_SUBPROCESS=1 pytest
```

When `CHATYBOT_ALLOW_SUBPROCESS=1` (or `"true"` / `"yes"`), the Tier 0 hard denial is bypassed, allowing the command to be governed by normal DSL or tool rules.

### 3.3 Command-Line Startup Flags

Add developer CLI switches:

```bash
# Explicit flag:
chatybot --allow-chatybot-subprocess

# Developer shortcut mode (also enables debug diagnostics and relaxes self-blocking):
chatybot --dev
```

---

## 4. Unwrapping & Pattern Matching Robustness

The `CHATYBOT_EXEC_PATTERN` already catches:
- Direct commands: `chatybot`, `./chatybot.py`, `/usr/local/bin/chatybot`
- Wrapper commands: `env VAR=val chatybot`, `nohup chatybot &`, `sudo chatybot`
- Script runners: `bash -c "chatybot"`, `sh chatybot.py`
- Python module launches: `python -m chatybot`, `python3 /path/to/chatybot.py`, `python -c "import chatybot..."`
- Subshell chaining: `echo test && chatybot`

When the override is set to `"ask"`, the user confirmation prompt will display:
```text
[Security Policy: Chatybot Sub-Process]
The assistant requested to execute a Chatybot sub-process:
  Command: 'python -m pytest test/test_session.py'
Running sub-processes of Chatybot can cause recursive loops. Proceed? (y/N):
```

---

## 5. Recursion Lock & Max Depth Guard (Child Process Safety)

Even when developer override is enabled, an unconstrained sub-process could still accidentally spawn another sub-process indefinitely if an automated loop triggers it.

To guarantee that an allowed sub-process cannot run infinitely, implement an **inherited recursion depth counter**:

1. **Environment Depth Counter:**
   Whenever `run_command` executes, it sets or increments:
   ```python
   current_depth = int(os.environ.get("CHATYBOT_RECURSION_DEPTH", "0"))
   env["CHATYBOT_RECURSION_DEPTH"] = str(current_depth + 1)
   env["CHATYBOT_PARENT_PID"] = str(os.getpid())
   ```
2. **Child Startup Enforcement:**
   In `chatybot/cli.py`:
   ```python
   MAX_CHATYBOT_DEPTH = 2  # Allows 1 parent + 1 child test instance
   depth = int(os.environ.get("CHATYBOT_RECURSION_DEPTH", "0"))
   if depth > MAX_CHATYBOT_DEPTH:
       print(f"[Security Fatal] Maximum Chatybot sub-process recursion depth ({MAX_CHATYBOT_DEPTH}) exceeded.")
       sys.exit(1)
   ```

---

## 6. RACF-Guard (`racf-guard`) Policy Mapping

In the RACF architecture, role-based access control naturally accommodates developer permissions without code modifications:

```racf
# Universal default: Deny chatybot execution to all standard roles
RDEFINE COMMAND *chatybot*       UACC(DENY)
RDEFINE COMMAND python*chatybot* UACC(DENY)
RDEFINE COMMAND */chatybot*      UACC(DENY)

# Grant explicit execution authority to DEVELOPER or SYSADM group:
PERMIT *chatybot*       CLASS(COMMAND) ID(DEVELOPER) ACCESS(ALLOW)
PERMIT python*chatybot* CLASS(COMMAND) ID(DEVELOPER) ACCESS(ALLOW)
PERMIT */chatybot*      CLASS(COMMAND) ID(DEVELOPER) ACCESS(ALLOW)
```

When a developer connects their user ID to the `DEVELOPER` group (`CONNECT alice GROUP(DEVELOPER)`), `racf-guard` cleanly grants access to run `chatybot` commands.

---

## 7. Implementation Plan

1. **Update `BuiltinPolicyEngine` (`src/chatybot/security/builtin.py`)**:
   - Add `chatybot_exec_policy: str = "deny"` (or `allow_chatybot_subprocess: bool = False`) to `__init__`.
   - Check `os.environ.get("CHATYBOT_ALLOW_SUBPROCESS")`.
   - If policy is `"ask"`, return `Verdict.ASK` with warning prompt; if `"allow"`, permit execution; if `"deny"`, enforce Tier 0 `Verdict.DENY`.
2. **Update `SecurityManager` (`src/chatybot/security/manager.py`)**:
   - Parse `chatybot_exec_policy` and `allow_chatybot_subprocess` from `security.toml` `[builtin]` block and pass to `BuiltinPolicyEngine`.
3. **Update CLI Arguments (`src/chatybot/cli.py`)**:
   - Add `--allow-chatybot-subprocess` / `--dev` flag.
4. **Child Recursion Depth Guard**:
   - Add `CHATYBOT_RECURSION_DEPTH` check at application entry to prevent unbounded nesting.
5. **Documentation**:
   - Document the developer toggle in `doc/pluggable_security.md` and `src/chatybot/security/default_security.toml`.
