# Chatybot Pluggable Security API Specification

This document provides the formal specification for developing custom security policy engines for Chatybot. It defines the IPC wire protocol, JSON schemas, approval interfaces, banner contract, debug forwarding, and Python in-process plugin interfaces.

If you are an operator configuring rules or using the built-in policy engine, see the [Chatybot Pluggable Security Guide](file:///Users/jon2allen/github/chatybot/doc/pluggable_security.md) instead.

---

## 1. Overview & Architecture

Chatybot evaluates **every tool invocation** (both built-in tools like `run_command` and external MCP server tools) against an active security policy before execution. The security subsystem supports two integration modes:

```
                      ┌──────────────────────────────────────────────┐
                      │              Chatybot Core                   │
                      │    (ChatybotApp.dispatch_tool)               │
                      └──────────────────────┬───────────────────────┘
                                             │
                                             ▼
                      ┌──────────────────────────────────────────────┐
                      │               SecurityManager                │
                      │     (Config loader & fail-safe supervisor)   │
                      └──────────────┬───────────────────────────────┘
                                     │
                 ┌───────────────────┴───────────────────┐
                 ▼                                       ▼
    ┌───────────────────────────┐           ┌───────────────────────────┐
    │     In-Process Engine     │           │   External Binary Engine  │
    │  (BuiltinPolicyEngine or  │           │ (StdioBinaryPolicyEngine) │
    │   custom Python class)    │           └─────────────┬─────────────┘
    └───────────────────────────┘                         │
                                                 stdin    │   stdout / stderr
                                              (JSON req)  │   (JSON resp / trace)
                                                          ▼
                                            ┌───────────────────────────┐
                                            │ Custom Binary / Script    │
                                            │ (Rust, Go, Python, Bash)  │
                                            │ e.g. racf-guard           │
                                            └───────────────────────────┘
```

1. **External Process (Standard)**: An executable binary or script communicating via JSON over standard streams (`stdin`, `stdout`, `stderr`).
2. **In-Process Python Class**: A Python class extending [`BasePolicyEngine`](file:///Users/jon2allen/github/chatybot/src/chatybot/security/base.py) directly imported into the runtime.

---

## 2. Stdio Binary Engine Specification

When `engine = "binary"` is configured in `~/.config/chatybot/security.toml`, Chatybot uses [`StdioBinaryPolicyEngine`](file:///Users/jon2allen/github/chatybot/src/chatybot/security/adapters/stdio_binary.py) to delegate decisions to an external process.

### Configuration (`security.toml`)

```toml
version             = "1.0"
engine              = "binary"
fail_safe           = "deny"       # Verdict used if the binary fails ("deny" | "ask" | "allow")
non_interactive_ask = "deny"       # How to resolve ASK when running non-interactively ("deny" | "allow")

[binary]
path            = "/path/to/your/custom-guard"
args            = ["--config", "/path/to/policy.rules"]
timeout_seconds = 2.0
```

### Process Lifecycle

- **One-Shot Evaluation:** For each tool invocation, Chatybot spawns the process specified by `[binary].path` with `[binary].args`.
- **Input Delivery:** Chatybot pipes a single JSON object (UTF-8 encoded) to the process's standard input (`stdin`), then closes `stdin` (EOF).
- **Output Collection:** Chatybot captures standard output (`stdout`) and standard error (`stderr`) until the process exits or `timeout_seconds` is reached.
- **Process Termination:** The process must complete and exit with code `0`. Non-zero exit codes immediately trigger the `fail_safe` verdict.

*(For detailed architectural rationale, performance benchmarks, and design trade-offs of this one-shot model, see [Section 10: Technical Architecture Notes](#10-technical-architecture-notes).)*

---

## 3. JSON Wire Schemas

### Request Schema (`PolicyRequest`)

Piped to the binary's `stdin` as a single-line or pretty-printed JSON object:

```json
{
  "version": "1.0",
  "request_id": "c1f7a40b-71a2-4a0b-9ef1-4b15c7a09123",
  "timestamp": "2026-10-13T20:00:00+00:00",
  "tool": "run_command",
  "parameters": {
    "command": "git push --force origin main"
  },
  "context": {
    "session_id": "session-8924b1",
    "interactive": true,
    "user": "jon2allen",
    "debug": false
  }
}
```

#### Field Definitions

| Field | Type | Required | Description |
|---|---|---|---|
| `version` | `string` | Yes | Protocol version string (currently `"1.0"`). |
| `request_id` | `string` | Yes | Unique UUIDv4 string identifying this evaluation request. |
| `timestamp` | `string` | Yes | ISO 8601 UTC timestamp of the tool dispatch request. |
| `tool` | `string` | Yes | Name of the tool being executed (e.g. `run_command`, `write_file`, `mcp__postgres__query`). |
| `parameters` | `object` | Yes | Dictionary of tool arguments submitted by the model. |
| `context` | `object` | Yes | Ambient execution metadata: `session_id` (`str`), `interactive` (`bool`), `user` (`str`), `debug` (`bool`). |

---

### Response Schema (`PolicyDecision`)

The binary must emit a single JSON object to `stdout`:

```json
{
  "status": "ask",
  "reason": "Force push can overwrite remote git history",
  "prompt_details": {
    "title": "Git History Overwrite",
    "message": "Authorize force-pushing to origin main?",
    "risk_level": "high"
  },
  "modified_parameters": null
}
```

#### Field Definitions

| Field | Type | Required | Description |
|---|---|---|---|
| `status` | `string` | Yes | Decision verdict. Must be one of: `"allow"`, `"deny"`, or `"ask"` (case-insensitive). |
| `reason` | `string` | Yes | Human-readable explanation. Displayed in audit logs, block error messages, and confirmation prompts. |
| `prompt_details` | `object` | Conditional | **Required when `status` is `"ask"`** (optional for `"allow"` or `"deny"`). Defines UI confirmation details. |
| `prompt_details.title` | `string` | No | Short title for the prompt dialog (defaults to `"Permission Request"`). |
| `prompt_details.message` | `string` | No | User-facing question explaining what is being authorized (defaults to `"Authorize action?"`). |
| `prompt_details.risk_level` | `string` | No | Perceived risk level. Must be one of: `"low"`, `"medium"`, `"high"`, or `"critical"` (defaults to `"medium"`). |
| `modified_parameters` | `object` or `null` | No | Optional dictionary of sanitized or modified tool arguments. Must be a JSON object if provided; otherwise `null`. |

---

## 4. Verdict Semantics & Approval Protocol

Chatybot enforces three distinct verdict states:

### 1. `status = "allow"`
The tool call is permitted immediately. Chatybot dispatches the tool to its implementation without interrupting the user or prompting for confirmation.

### 2. `status = "deny"`
The tool call is blocked immediately.
- The model receives an error response: `Error: Security Policy Blocked: <reason>`.
- The event is recorded in the session audit log: `[Security Audit] BLOCKED tool '<tool>'. Reason: <reason>`.
- The tool implementation is never invoked.

### 3. `status = "ask"` (Human-in-the-Loop Approval)
The action requires explicit confirmation before it may execute.

#### Interactive CLI Sessions
When running in an interactive terminal (`sys.stdin.isatty()` is `true`):
1. Chatybot renders an approval box displaying `prompt_details.title`, `reason`, and the `risk_level`:
   ```text
   ┌── [SECURITY CONFIRMATION REQUIRED] ──────────────────────────┐
   │ Tool:        run_command                                    │
   │ Risk Level:  HIGH                                           │
   │ Reason:      Force push can overwrite remote git history    │
   │ Action:      Authorize force-pushing to origin main?        │
   └─────────────────────────────────────────────────────────────┘
   Proceed with execution? [y/N]:
   ```
2. The prompt confirmation is localized (e.g. `[y/N]` for English, `[s/N]` for Spanish, `[o/N]` for French).
3. The prompt is awaited in a background thread via `asyncio.to_thread` so asynchronous network connections and MCP streams remain active while waiting.
4. If approved: tool executes and logs `[Security Audit] USER APPROVED tool '<tool>'`.
5. If denied or aborted: tool is blocked and logs `[Security Audit] USER DECLINED tool '<tool>'`.

#### Non-Interactive & Headless Sessions
When running in unattended environments (ChatDSL scripts `--script`, one-shot `--run`, CI/CD pipelines, or piped stdin):
- **CLI Flag `-y` / `--yes` / `--auto-approve`:** If passed by the operator, `ASK` verdicts are automatically approved and logged as `[Security Audit] AUTO APPROVED (-y) tool '<tool>'`.
- **Config `non_interactive_ask`:** When `-y` is omitted:
  - `"deny"` (default): Fails fast. Blocks execution immediately with: `Error: Security Policy Blocked: Action requires confirmation but session is non-interactive (non_interactive_ask='deny')`.
  - `"allow"`: Automatically approves execution and logs `[Security Audit] AUTO APPROVED (non_interactive_ask=allow) tool '<tool>'`.

> [!IMPORTANT]
> **Hard Denial Invariant:** Neither `-y` nor `non_interactive_ask="allow"` can bypass a `"deny"` verdict. Hard denials are always enforced regardless of execution flags.

---

## 5. Banner Protocol (`--banner`)

To identify the active security engine on startup, Chatybot queries the binary with the `--banner` flag.

### CLI Contract
- **Command:** `<binary_path> [configured_args...] --banner`
- **Execution:** Invoked once during startup and whenever `--security` diagnostics run.
- **Timeout:** `1.5` seconds.
- **Exit Code:** Must exit with code `0`.
- **Output:** A single concise line emitted to `stdout` describing the engine name, version, and policy state.

### Example Banner Outputs
```text
RACF-Guard v0.1.0 (4 groups, 41 profiles loaded from security.racf)
```
```text
CorporateFirewall v2.4 (Connected to https://policy.internal.corp)
```

### Caching & Fallback Behavior
- [`StdioBinaryPolicyEngine`](file:///Users/jon2allen/github/chatybot/src/chatybot/security/adapters/stdio_binary.py#L126-L153) caches the banner output in memory after the first successful query to prevent launching subprocesses repeatedly.
- If the binary does not support `--banner`, times out, or returns a non-zero exit code, Chatybot falls back gracefully to: `Binary: <basename_of_binary>`.

---

## 6. Debug & Tracing Protocol (`--debug` and `stderr`)

Chatybot supports end-to-end tracing for security policy evaluations.

### How Debug Mode is Triggered
When a user launches Chatybot with the `--security` diagnostic flag:
1. **CLI Flag Injection:** Chatybot inspects the binary arguments. If neither `--debug` nor `-d` is present in `args`, Chatybot automatically appends `--debug` to the command line.
2. **Context Injection:** Chatybot sets `"debug": true` in the `context` dictionary of the JSON request payload.

### Standard Error Forwarding Contract
- Any text emitted by the binary to `stderr` during an evaluation is captured by Chatybot.
- Each line in `stderr` is prefixed and printed directly to the user's terminal:
  ```text
  [Security Debug] [External Binary] <line_from_stderr>
  ```
- This allows the engine to output step-by-step rule evaluation traces without corrupting the JSON payload on `stdout`.

### Trace Example
Binary writes to `stderr`:
```text
[Policy Trace] Matching tool 'git.status' against rule table
[Policy Trace] Rule #12 MATCHED (ACCESS: ALLOW)
```
Chatybot surfaces to terminal:
```text
[Security Debug] [External Binary] [Policy Trace] Matching tool 'git.status' against rule table
[Security Debug] [External Binary] [Policy Trace] Rule #12 MATCHED (ACCESS: ALLOW)
```

---

## 7. Fail-Safe & Error Handling Semantics

Safety requires that security failures fail-closed. If an external binary encounters an anomaly, Chatybot intercepts the error and returns a fallback verdict equal to `fail_safe` (default: `"deny"`).

### Conditions that Trigger Fail-Safe

| Failure Condition | Fail-Safe Log Reason |
|---|---|
| Execution exceeds `timeout_seconds` | `External policy evaluation timed out after <N>s. Failing safe to <fail_safe>.` |
| Non-zero process exit code | `External policy binary exited with code <N>: <stderr_snippet>` |
| Empty stdout | `External policy binary produced empty output.` |
| Malformed JSON syntax | `External policy binary produced invalid JSON (<details>).` |
| JSON output is not a dictionary | `External policy binary response was not a JSON object.` |
| `status` field is missing or non-string | `External policy binary returned non-string status (<raw>).` |
| `status` is not `"allow"`, `"deny"`, or `"ask"` | `External policy binary returned unknown status '<raw>'.` |
| `modified_parameters` is not an object or null | `External policy binary returned non-object modified_parameters.` |

Developers should ensure their binaries:
1. Catch internal exceptions and output a valid JSON `{"status": "deny", "reason": "Internal error: ..."}` with exit code `0`.
2. Keep evaluation latency well under `timeout_seconds` (recommended `< 50ms`).

---

## 8. In-Process Python Engine Interface

For Python developers who want to embed a custom policy engine without subprocess IPC overhead, Chatybot exposes the abstract base class [`BasePolicyEngine`](file:///Users/jon2allen/github/chatybot/src/chatybot/security/base.py).

### Class Definition

```python
from abc import ABC, abstractmethod
from chatybot.security.models import PolicyRequest, PolicyDecision

class BasePolicyEngine(ABC):
    """Abstract base class for all security policy evaluation engines."""

    @abstractmethod
    def evaluate(self, request: PolicyRequest) -> PolicyDecision:
        """Evaluate a tool request and return a tri-state PolicyDecision."""
        raise NotImplementedError

    def get_banner(self) -> str:
        """Return a concise identification banner describing this engine."""
        return type(self).__name__
```

### Implementing a Custom Python Engine

```python
from chatybot.security.base import BasePolicyEngine
from chatybot.security.models import (
    PolicyRequest,
    PolicyDecision,
    PolicyPromptDetails,
    Verdict,
)

class EnterprisePolicyEngine(BasePolicyEngine):
    def __init__(self, allowed_domains: list[str]):
        self.allowed_domains = allowed_domains

    def get_banner(self) -> str:
        return f"EnterprisePolicyEngine v1.0 (Domains: {len(self.allowed_domains)})"

    def evaluate(self, request: PolicyRequest) -> PolicyDecision:
        # 1. Deny dangerous shell commands
        if request.tool == "run_command":
            cmd = request.parameters.get("command", "")
            if "rm -rf" in cmd:
                return PolicyDecision(
                    verdict=Verdict.DENY,
                    reason="Recursive deletion is forbidden by enterprise policy."
                )

        # 2. Require human approval for file writes
        if request.tool in ("write_file", "replace_file_content"):
            return PolicyDecision(
                verdict=Verdict.ASK,
                reason="Modifying repository files requires approval.",
                prompt_details=PolicyPromptDetails(
                    title="Codebase Modification",
                    message=f"Authorize modification of {request.parameters.get('target_file')}?",
                    risk_level="medium"
                )
            )

        # 3. Default to allow
        return PolicyDecision(verdict=Verdict.ALLOW, reason="Action permitted.")
```

---

## 9. Reference Implementations

### Minimal Custom Python Binary (`custom_guard.py`)

A complete, standalone executable script demonstrating the full IPC protocol:

```python
#!/usr/bin/env python3
import sys
import json

def main():
    # Handle --banner query
    if "--banner" in sys.argv:
        print("CustomPythonGuard v1.0 (Demo Engine)")
        sys.exit(0)

    is_debug = "--debug" in sys.argv or "-d" in sys.argv

    # Read PolicyRequest from stdin
    try:
        raw_input = sys.stdin.read()
        if not raw_input.strip():
            sys.exit(1)
        req = json.loads(raw_input)
    except Exception as exc:
        if is_debug:
            sys.stderr.write(f"Failed to parse stdin JSON: {exc}\n")
        sys.exit(1)

    tool = req.get("tool", "")
    params = req.get("parameters", {})

    if is_debug:
        sys.stderr.write(f"[Debug] Evaluating tool '{tool}' with params {params}\n")

    # Evaluate decision
    if tool == "run_command":
        cmd = str(params.get("command", ""))
        if "rm " in cmd:
            decision = {
                "status": "deny",
                "reason": "File removal commands are prohibited."
            }
        elif "git push" in cmd:
            decision = {
                "status": "ask",
                "reason": "Remote push requires operator confirmation.",
                "prompt_details": {
                    "title": "Git Remote Action",
                    "message": "Authorize pushing commits to remote?",
                    "risk_level": "high"
                }
            }
        else:
            decision = {
                "status": "allow",
                "reason": "Command permitted."
            }
    else:
        decision = {
            "status": "allow",
            "reason": "Tool permitted."
        }

    # Emit JSON response to stdout
    print(json.dumps(decision))
    sys.exit(0)

if __name__ == "__main__":
    main()
```

### Reference Production Engine (`racf-guard`)

For a production-grade compiled implementation written in Rust modeling IBM z/OS RACF resource classes, role groups, and least-privilege default-deny access control, see:
- Source code: [`tools/racf-guard/`](file:///Users/jon2allen/github/chatybot/tools/racf-guard)
- Architecture and User Guide: [`tools/racf-guard/README.md`](file:///Users/jon2allen/github/chatybot/tools/racf-guard/README.md)

---

## 10. Technical Architecture Notes

### 10.1 The One-Shot Subprocess Model & Design Rationale

In the `binary` adapter architecture ([`StdioBinaryPolicyEngine`](file:///Users/jon2allen/github/chatybot/src/chatybot/security/adapters/stdio_binary.py)), Chatybot explicitly spawns a **fresh, independent subprocess instance** of the policy engine (e.g. `racf-guard`) for each tool request:

```
Tool Dispatch ──► Spawn Child Process ──► Pipe JSON (stdin) ──► Read JSON (stdout) ──► Process Exits (0)
```

This stateless, one-shot architecture was chosen deliberately for three foundational reasons:

1. **Process & Memory Fault Isolation (Fail-Closed Boundary):**
   Security subsystems must never compromise the host application's stability. If a custom security engine experiences a segmentation fault, memory panic, unhandled exception, or memory leak, the fault is completely contained within the ephemeral child process. Chatybot detects the abnormal termination, prevents any unverified tool from executing, and cleanly applies the configured `fail_safe` verdict (defaulting to `"deny"`).

2. **Instant, Zero-Downtime Policy Hot-Reloading:**
   Because each invocation reads the policy definitions fresh from disk (e.g. `security.racf`), policy modifications take effect immediately. Administrators can edit rule files or issue command-line access grants (`racf-guard permit ...`) without sending POSIX signals (`SIGHUP`), resetting IPC connections, or restarting running Chatybot agent sessions.

3. **Zero Daemon Lifecycle Management:**
   Long-lived background daemons introduce complex failure modes: stale Unix domain sockets (`/tmp/racf.sock`), orphaned PID files, leaked file descriptors, and zombie processes when the host terminal is killed abruptly (`Ctrl+C` or `kill -9`). The one-shot process model has zero background footprint and guarantees complete cleanup upon tool completion.

---

### 10.2 Latency & Performance Profile

| Engine Implementation | Typical Execution Latency | Practical Impact on Agent Loop |
|---|---|---|
| **Compiled Native (Rust `racf-guard`, Go, C/C++)** | **1.5 ms – 3.0 ms** | **Negligible (< 0.5% of tool dispatch cycle)**. Cold startup, policy script parsing, AST generation, and JSON serialization complete almost instantaneously. Compared to model inference and network roundtrips (500 ms – 3,000 ms), the overhead is imperceptible. |
| **Lightweight Script (Bash, Awk, Coreutils)** | **3.0 ms – 10.0 ms** | **Negligible**. Fast invocation suited for rapid prototyping or simple shell wrappers. |
| **Interpreted Runtimes (Python, Node.js)** | **50.0 ms – 250.0 ms** | **Noticeable if loading large packages**. Python interpreter startup and module import overhead (e.g. Pydantic, Pandas, cryptography libraries) can introduce perceptible latency if spawned per tool. For Python-based engines, developers should either use minimal standard-library scripts or implement an in-process class via [`BasePolicyEngine`](#8-in-process-python-engine-interface). |

---

### 10.3 Statefulness & Multi-Request Tracking

Because the binary process terminates immediately after returning its verdict, it is inherently **stateless** between separate tool evaluations. 

If your security architecture requires stateful policies (such as rolling rate limits, token-bucket frequency caps, or cross-tool sequence analysis):

1. **Leverage Request Context:** Inspect `request.context["session_id"]`, `request.context["user"]`, and `request.timestamp` to track evaluation correlation.
2. **External State Store:** Have your binary persist counters to a fast local database (e.g. SQLite, RocksDB, or a shared memory-mapped cache file).
3. **Use the In-Process Python API:** Implement [`BasePolicyEngine`](#8-in-process-python-engine-interface) directly within Chatybot. Because in-process engines remain resident in memory for the entire lifetime of the `ChatybotApp` process, they can hold arbitrary in-memory state, sliding windows, and session caches without IPC or process startup overhead.

---

### 10.4 Future Architectural Roadmap: Daemon & Socket Modes

While the one-shot stdio subprocess is the default and standard adapter, the pluggable architecture is designed to accommodate additional adapter types as requirements evolve:
- **`engine = "socket"` (Unix Domain Socket / Named Pipe):** For ultra-high throughput environments or centralized enterprise security daemons running across multiple agent processes.
- **`engine = "stream"` (Persistent Long-Lived Process):** Keeping a single binary process alive and streaming line-delimited JSON (`JSON-Lines` / NDJSON) over persistent `stdin`/`stdout` pipes.
