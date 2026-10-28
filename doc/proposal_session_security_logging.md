# Proposal: Session-Level Security Decision Logging

**Version:** 1.1
**Date:** October 28, 2026
**Status:** Implemented

## 1. Problem

Security decisions are not recorded in session data. When a tool call is
blocked or prompted, the session turn (`turns.jsonl`) records only the
refusal text as a generic error (`exit_code: 1`, `status: "error"`). The
verdict, engine, reason, and outcome are invisible to anyone reading the
session transcript without cross-referencing the separate engine log files
(`jev_security.jsonl`, `security_chain.jsonl`).

This makes it hard to:

- Audit what was blocked and why from session data alone.
- Reconstruct a timeline of security decisions across a session.
- Compare security behavior across models, sessions, or time ranges.
- Diagnose false positives without opening the engine-specific log.

Additionally, `BuiltinPolicyEngine` and `racf-guard` (when run standalone)
have no decision log at all -- their verdicts are lost unless the caller
records them.

## 2. Design

### 2.1 Security field on agentic loop tool records

Add a `security` object to each tool record in the `agentic_loop` array
inside session turns, populated whenever a security evaluation occurred.
Input and output phases are stored separately so the output check does not
overwrite the input decision:

```json
{
  "turn": 3,
  "tool": "grep_search",
  "arguments": {"query": "security", "path": "doc/"},
  "result": "Security refusal (final): Jev: system_dirs=0.64->deny ...",
  "exit_code": 1,
  "status": "error",
  "timestamp": "2026-10-27T15:11:40.702946",
  "duration_ms": 250.3,
  "security": {
    "input": {
      "verdict": "deny",
      "engine": "jev",
      "reason": "Jev: system_dirs=0.64->deny",
      "request_id": "b3219c5e-0ad4-4688-90bd-0f59831b7a01",
      "duration_ms": 249.7
    }
  }
}
```

For allowed tools, the field is present but lightweight:

```json
"security": {
  "input": {
    "verdict": "allow",
    "engine": "jev",
    "reason": "Jev: no rule triggered",
    "duration_ms": 155.4
  }
}
```

When both input and output phases run, both are recorded:

```json
"security": {
  "input": {
    "verdict": "ask",
    "engine": "jev",
    "reason": "needs human",
    "request_id": "r-in",
    "outcome": "approved",
    "duration_ms": 200.0
  },
  "output": {
    "verdict": "allow",
    "engine": "jev",
    "reason": "output fine",
    "duration_ms": 10.0
  }
}
```

A refusal served from the loop cache is marked so it can be distinguished
from a fresh evaluation:

```json
"security": {
  "input": {
    "verdict": "deny",
    "engine": "jev",
    "reason": "blocked",
    "request_id": "r-cached",
    "source": "cache"
  }
}
```

### 2.2 Fields

| Field | Type | When present | Source |
|-------|------|-------------|--------|
| `verdict` | string | always | `PolicyDecision.verdict.value` |
| `engine` | string | always | `SecurityManager.engine_type` (`"disabled"` when security is off) |
| `reason` | string | always | `PolicyDecision.reason` |
| `duration_ms` | float | always | `PolicyDecision.duration_ms` |
| `request_id` | string | deny/ask | `PolicyDecision.request_id` |
| `outcome` | string | ask only | "approved", "declined", "auto_approved_yes_flag", "auto_approved_non_interactive", "blocked_non_interactive" |
| `source` | string | cache only | `"cache"` for refusals served from the loop refusal cache |

`request_id` is omitted for allow. `outcome` is omitted for allow and deny
(the outcome is the verdict itself). `source` is omitted for fresh
evaluations (absent means "eval").

### 2.3 Output security

Output-phase decisions are stored under `security.output`, separate from
`security.input`. This preserves the input verdict, request_id, and
outcome even when the output check returns allow.

### 2.4 Engine name exposure

`SecurityManager` stores `self.engine_type` (set to `"disabled"` when
security is off, or the configured engine name otherwise) so the caller
can read it without re-parsing config.

### 2.5 Clearing and cache

`SECURITY_DECISION` is cleared at two points to prevent stale data from
leaking into the next tool record:

1. In the agentic loop, before each tool dispatch (alongside
   `TOOL_DISPATCH_RESULT`).
2. In `dispatch_tool`, at the start of the security section (covers
   non-loop callers like DSL scripts).

Cached loop refusals (`_serve_loop_refusal`) produce a security record
with `source: "cache"` so they can be distinguished from fresh
evaluations in the audit trail.

### 2.6 What is NOT logged in the session

- Per-rule scores (jev-specific, stays in `jev_security.jsonl`).
- Per-stage verdicts and disagreement flags (chain-specific, stays in
  `security_chain.jsonl`).
- Model name, rubric version, usage/cost (engine-specific, stays in
  engine logs).
- API request/response payloads.

The session log answers "what happened." The engine log answers "why."

## 3. Implementation

### 3.1 Script variable approach

`SECURITY_DECISION` is a protected script var (added to
`buffer_manager.protected_vars`) set by `_store_security_decision` after
each security evaluation. The agentic loop reads it when building
`tool_record` and attaches it as `tool_record["security"]`.

### 3.2 Per-phase storage

`_store_security_decision` takes a `phase` parameter (`"input"` or
`"output"`) and stores decisions under `{"input": {...}, "output": {...}}`
so the output check does not overwrite the input decision.

### 3.3 Outcome recording

The `_record_sec_outcome` and `_record_post_outcome` closures call
`_store_security_decision` with the outcome string, which updates the
stored input or output phase with the outcome field.

### 3.4 Cached refusals

`_serve_loop_refusal` calls `_store_security_decision` with
`source="cache"` so cached refusals are distinguishable from fresh
evaluations in the audit trail.

### 3.5 Engine type attribute

`SecurityManager.engine_type` is set to `"disabled"` when security is
off, or the configured engine name (`"builtin"`, `"jev"`, `"chain"`,
`"binary"`, `"allow"`) otherwise.

### 3.6 Backward compatibility

Old sessions without the `security` field continue to work. Analysis
tools treat missing `security` as "not recorded" rather than "no
security decision." The field is additive.

## 4. Relationship to engine logs

| Concern | Session log | Engine log |
|---------|-------------|------------|
| Always written (even when sessions off) | No | Yes |
| Verdict + reason | Yes | Yes |
| Engine name | Yes | Implicit (file name) |
| Working directory | Via session context | Yes (just added) |
| Per-rule scores | No | Yes (jev) |
| Per-stage verdicts | No | Yes (chain) |
| Usage/cost | No | Yes (jev) |
| Outcome (approved/declined) | Yes (in tool record) | Yes (outcome line) |
| Covers builtin/racf standalone | Yes | No (gap) |

## 5. Analysis tooling

A companion script (`scripts/session_security_report.py`) reads session
data from `~/.local/share/chatybot/sessions/` and produces formatted
reports.

Features:
- Date range filtering (e.g., past 4 days).
- Model filtering (e.g., only `mistral_1` sessions).
- Phrase search in session prompts (e.g., "security").
- Summary tables: verdicts (fresh only), by source, by engine, by tool,
  by model, by day, by outcome.
- Detail listing of deny/ask decisions with phase and source markers.
- Cross-reference with engine logs (`--cross-ref`, `--engine-log PATH`)
  joining by request_id, filtered to `event == "decision"` entries.
