# Time-Travel Context Replay (`/session replay`) — Implementation Plan

## 1. Overview & Architecture

Context replay reconstructs the exact message array `[{"role": "...", "content": "..."}]` as it was sent to the model at any turn in a session, runs `ContextLimiter.truncate_messages_verbose()`, and provides rich diagnostics on evicted messages, anchor overflows, and token deltas.

Integrating this under `/session replay` naturally extends the session inspection suite (`/session view`, `/session info`, `/session history`).

```
┌─────────────────────────────────────────────────────────────┐
│  /session replay [<id>] [at <N> | diff <A> <B> | step]      │
│  (Optional top-level alias: /replay)                        │
│  (src/chatybot/commands/session.py or commands/replay.py)   │
│  └──────────────────────────┬───────────────────────────────┘
│                             ▼
│  SessionReplayer (src/chatybot/session_replayer.py)         │
│  ├─ Loads session meta + turns via BaseSessionStore         │
│  ├─ Fallback to active session if <id> is omitted           │
│  ├─ Reconstructs system prompt from config/meta             │
│  ├─ for each turn: build messages → run verbose truncation  │
│  └─ Returns TurnSnapshot[] or TurnDiff                      │
│                             ▼
│  ┌───────────────────────────────────────────────────────┐  │
│  │ reconstruct_messages_from_turns()                     │  │
│  │ (Clean thinking token handling, command filtering)    │  │
│  └───────────────────────────────────────────────────────┘  │
│  ┌───────────────────────────────────────────────────────┐  │
│  │ ContextLimiter.truncate_messages_verbose()            │  │
│  │ (Index-tagged diagnostic wrapper diffing in/out)      │  │
│  └───────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. File Layout

| File | Responsibilities |
|---|---|
| `src/chatybot/context_limit.py` | Add `TruncationDiagnostic` dataclass and `truncate_messages_verbose()` method. |
| `src/chatybot/session_replayer.py` | **(NEW)** Replay engine: `reconstruct_messages_from_turns()`, `TurnSnapshot`, `TurnDiff`, and `SessionReplayer`. |
| `src/chatybot/commands/session.py` | Add `elif subcmd == "replay":` handler to `/session`. |
| `src/chatybot/commands/replay.py` | **(NEW)** Optional convenience wrapper registering `/replay` as a root alias forwarding to the replay handler. |
| `src/chatybot/chaty_help.py` | Update `/session` (and `/replay`) help descriptions and examples. |
| `test/test_session_replayer.py` | **(NEW)** Unit and integration tests for message reconstruction, verbose truncation, and replay CLI modes. |

---

## 3. Command Syntax & User Experience

All subcommands default to the **active session** if an explicit session `<id>` is omitted.

| Command Syntax | Description |
|---|---|
| `/session replay` | Summary timeline of all turns in the active session. |
| `/session replay <id>` | Summary timeline for session `<id>`. |
| `/session replay [id] at <N>` | Full reconstructed message dump at Turn `N` (shows anchors, evicted messages, token counts). |
| `/session replay [id] diff <A> <B>` | Compares Turn `A` vs Turn `B` (shows new messages added, newly evicted turns, token delta). |
| `/session replay [id] step` | Interactive stepping mode: step turn-by-turn with Enter (`q` to quit). |
| `/session replay ... limit=<N>` | Override the context limit for any of the above modes (e.g., test how a 16k budget would behave). |
| `/replay ...` | Direct top-level shorthand alias for `/session replay ...`. |

---

## 4. Implementation Steps

### Step 1: Add `truncate_messages_verbose` to `ContextLimiter`
**File:** `src/chatybot/context_limit.py`

Non-breaking diagnostic method wrapping `truncate_messages` with monotonic index tracking (`_orig_idx`):

```python
@dataclass
class TruncationDiagnostic:
    original_messages: list[dict]
    truncated_messages: list[dict]
    did_truncate: bool
    original_tokens: int
    truncated_tokens: int
    effective_limit: int           # raw limit (before pct adjustment)
    target_limit: int              # pct-adjusted limit actually enforced
    anchor_count: int
    evicted_count: int              # How many messages were dropped
    evicted_indices: list[int]      # Original 0-based indices that were removed
    content_truncated: bool         # True if string truncation fired on a message
    anchors_alone_exceed_limit: bool # Infinite-loop warning condition

def truncate_messages_verbose(
    self,
    messages: list[dict],
    limit: int | None = None,
    target_pct: float | None = None,
) -> TruncationDiagnostic:
    """Run truncate_messages and return a comprehensive diagnostic struct."""
    if not messages:
        return TruncationDiagnostic(
            original_messages=[], truncated_messages=[], did_truncate=False,
            original_tokens=0, truncated_tokens=0, effective_limit=0,
            target_limit=0, anchor_count=0, evicted_count=0,
            evicted_indices=[], content_truncated=False,
            anchors_alone_exceed_limit=False
        )

    # Attach monotonic tracking tags to avoid content collision
    tagged_messages = [{"_orig_idx": i, **m} for i, m in enumerate(messages)]
    orig_tokens = self.count_tokens_messages(messages)

    # Variable names aligned with truncate_messages (context_limit.py:113-118):
    #   effective_limit = the raw limit (before pct adjustment)
    #   target_limit    = the pct-adjusted limit actually enforced
    effective_limit = limit or self.context_limit or 0
    pct = (target_pct if target_pct is not None else self.truncate_pct) / 100.0
    target_limit = int(effective_limit * pct) if effective_limit else 0

    # Anchor partition overflow detection
    anchors = []
    if tagged_messages:
        anchors.append(tagged_messages[0])
        if len(tagged_messages) > 1 and tagged_messages[1].get("role") == "user":
            anchors.append(tagged_messages[1])
    anchor_tokens = self.count_tokens_messages(anchors)
    anchors_alone_overflow = bool(target_limit and anchor_tokens > target_limit)

    # Run core truncation on copy.
    # NOTE: _orig_idx tags survive because truncate_messages does a shallow
    # dict copy (result = [dict(m) for m in messages]) which preserves extra
    # keys. If truncate_messages is ever refactored to reconstruct dicts with
    # only role/content, this tracking silently breaks — add a regression test.
    clean_copy = [dict(m) for m in tagged_messages]
    truncated_tagged, did_truncate_ret = self.truncate_messages(
        clean_copy, limit=limit, target_pct=target_pct
    )

    surviving_indices = {m["_orig_idx"] for m in truncated_tagged if "_orig_idx" in m}
    evicted_indices = [i for i in range(len(messages)) if i not in surviving_indices]
    content_truncated = any("[... content truncated" in str(m.get("content", "")) for m in truncated_tagged)

    # Clean tags
    final_truncated = [{k: v for k, v in m.items() if k != "_orig_idx"} for m in truncated_tagged]
    trunc_tokens = self.count_tokens_messages(final_truncated)

    return TruncationDiagnostic(
        original_messages=messages,
        truncated_messages=final_truncated,
        did_truncate=did_truncate_ret or content_truncated,
        original_tokens=orig_tokens,
        truncated_tokens=trunc_tokens,
        effective_limit=effective_limit,
        target_limit=target_limit,
        anchor_count=len(anchors),
        evicted_count=len(evicted_indices),
        evicted_indices=evicted_indices,
        content_truncated=content_truncated,
        anchors_alone_exceed_limit=anchors_alone_overflow,
    )
```

---

### Step 2: Build `SessionReplayer` Engine
**File:** `src/chatybot/session_replayer.py`

Handles payload synthesis, thinking tag sanitization, and diff calculations.

```python
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple
from chatybot.context_limit import ContextLimiter, TruncationDiagnostic
from chatybot.session_interface import BaseSessionStore

def clean_thinking_tokens(text: str) -> str:
    """Safely strip thinking tags."""
    if not text or not isinstance(text, str):
        return ""
    cleaned = re.sub(r"<think>.*?</think>\s*", "", text, flags=re.DOTALL)
    cleaned = re.sub(r"<thought>.*?</thought>\s*", "", cleaned, flags=re.DOTALL)
    return cleaned.strip()

def reconstruct_messages_from_turns(
    turns: List[Dict[str, Any]],
    system_prompt: str,
    up_to_turn_id: Optional[int] = None,
    include_current: bool = True,
) -> List[Dict[str, Any]]:
    """Reconstruct message list for LLM context at a specific turn."""
    messages: List[Dict[str, Any]] = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})

    llm_turns = [t for t in turns if t.get("type") != "command" and "prompt" in t]
    if up_to_turn_id is not None:
        target_idx = None
        for idx, t in enumerate(llm_turns):
            if t.get("turn_id") == up_to_turn_id:
                target_idx = idx
                break
        if target_idx is not None:
            llm_turns = llm_turns[: target_idx + 1]

    if not llm_turns:
        return messages

    for turn in llm_turns[:-1]:
        messages.append({"role": "user", "content": turn.get("prompt", "")})
        resp = turn.get("response", "")
        messages.append({"role": "assistant", "content": clean_thinking_tokens(resp)})

    last_turn = llm_turns[-1]
    messages.append({"role": "user", "content": last_turn.get("prompt", "")})
    if not include_current:
        resp = last_turn.get("response", "")
        messages.append({"role": "assistant", "content": clean_thinking_tokens(resp)})

    return messages
```

#### Dataclasses and Engine Class:

```python
@dataclass
class TurnSnapshot:
    turn_id: int
    message_count: int          # messages in the reconstructed list
    total_tokens: int           # before truncation
    truncated_tokens: int       # after truncation (if applied)
    did_truncate: bool
    evicted_indices: list[int]  # original 0-based indices removed by truncation
    anchors_alone_exceed_limit: bool
    messages: list[dict]        # full reconstructed message list
    truncated_messages: list[dict]  # after truncation
    is_tool_turn: bool
    model_alias: str | None

@dataclass
class TurnDiff:
    turn_a: int
    turn_b: int
    added_messages: list[dict]          # messages present at turn_b but not turn_a
    newly_evicted: list[dict]           # messages that survived at turn_a but were evicted by turn_b
    token_delta: int                    # total_tokens_b - total_tokens_a (before truncation)
    truncation_evicted_delta: int       # evicted_count_b - evicted_count_a
    anchor_overflow_changed: bool       # True if overflow state differs between turns
    snapshot_a: TurnSnapshot
    snapshot_b: TurnSnapshot
```

- `SessionReplayer`:
  - `load(target: str) -> Tuple[meta, turns]`
  - `reconstruct_system_prompt(meta, turns) -> str`
  - `snapshot_at_turn(turns, system_prompt, turn_id, limit=None) -> TurnSnapshot`
  - `replay_all(target, limit=None) -> List[TurnSnapshot]`
  - `diff_turns(target, turn_a, turn_b, limit=None) -> TurnDiff`

#### `reconstruct_system_prompt` approach:

The system prompt is not stored per-turn in the turn record. It is reconstructed from current config as an approximation:

```python
def reconstruct_system_prompt(self, meta: dict, turns: list[dict]) -> str:
    """
    Reconstruct the system prompt that would have been active.
    Approximate — the exact prompt at session time is not stored.

    Built from (mirrors chat_completion lines 1249-1319):
      1. config_manager.system_message (base)
      2. Tool context + agentic instructions (if any turn has agentic_loop)
      3. Model-specific suffixes (gemma4, nanbeige — detected from model_alias)
      4. Reasoning mode settings

    The result is flagged as approximate in the CLI output.
    """
    base = self.config_manager.system_message or ""
    has_tool_turns = any(t.get("agentic_loop") for t in turns)
    parts = [base]
    if has_tool_turns:
        # Append tool context + agentic instructions from config_manager
        # (exact strings available at runtime via config_manager)
        parts.append(self._get_tool_context())
        parts.append(self._get_agentic_instructions())
    model_alias = meta.get("model_alias", "")
    suffix = self._get_model_suffix(model_alias)
    if suffix:
        parts.append(suffix)
    return "\n".join(p for p in parts if p)
```

---

### Step 3: Implement Replay Handler & Wire into `/session`
**File:** `src/chatybot/commands/session.py` (and `commands/replay.py`)

Extract the replay argument parser into a shared helper function `handle_replay_command(ctx, raw_tokens)` that is called by both `/session replay` and the `/replay` alias.

```python
# In src/chatybot/commands/session.py
elif subcmd == "replay":
    raw_tokens = parts[2].strip().split() if len(parts) > 2 else []
    return await handle_replay_command(ctx, raw_tokens)
```

```python
# In src/chatybot/commands/replay.py
@command("/replay", help="Replay and inspect session context window history",
         args="[<id>] [at <N> | diff <A> <B> | step] [limit=<N>]", category="session")
async def cmd_replay(ctx: CommandContext, parts: list, command: str) -> CommandResult:
    raw_tokens = []
    for p in parts[1:]:
        raw_tokens.extend(p.strip().split())
    return await handle_replay_command(ctx, raw_tokens)
```

#### Argument Resolution Logic:
1. If the first token is a keyword (`at`, `diff`, `step`, `limit=...`) or tokens are empty:
   - Target session defaults to `ctx.app.active_session_id` (or `ctx.app.active_session_name`).
2. If the first token is a session ID:
   - Target session is resolved from that token.
3. Parses subcommands (`at <N>`, `diff <A> <B>`, `step`) and `limit=<int>` overrides.
4. Renders:
   - **Summary Table**: Turn #, Uncut Tokens, Truncated Tokens, Evicted Count, Anchor Warning.
   - **At View**: Breakdown of all messages (System/User/Assistant), Anchor status, Evicted status, Token sizes, and preview text.
   - **Diff View**: Exact messages added and newly evicted between Turn A and Turn B.
   - **Step View**: Interactive turn stepper using plain `input()` (matching the codebase pattern in `commands/session.py:389`, `commands/debug_misc.py:166`) with `KeyboardInterrupt` handling for `q` to quit.

---

### Step 4: Documentation & Help Updates
**File:** `src/chatybot/chaty_help.py`

Update `/session` long description and examples:
```python
Subcommands:
  ...
  /session replay [<id>] [at <N>|diff <A> <B>|step] [limit=<N>] - Replay and inspect context window history and truncation state
```

---

### Step 5: Testing Strategy
**File:** `test/test_session_replayer.py`

1. **Reconstruction**:
   - Multi-turn reconstruction with system prompt and sequential user/assistant messages.
   - Verified stripping of `<think>` and `<thought>` tags from assistant turns.
   - Ignored command turns (`type="command"`).
2. **Verbose Truncation & Diagnostics**:
   - `did_truncate=False` when under token budget.
   - Accurate `evicted_indices` with repeated duplicate strings.
   - `anchors_alone_exceed_limit=True` flag when system + first turn exceeds budget.
   - `content_truncated=True` flag when long single message is partially clipped.
3. **Session Replay Workflows**:
   - `/session replay` on active session produces formatted summary table.
   - `/session replay <id> at 3` displays message inspection view.
   - `/session replay <id> diff 2 3` reports added and dropped messages.
   - `/replay` alias behaves identically to `/session replay`.
   - Handling of missing/empty sessions without crashes.

---

### Step 6: Verification
Execute all session and tool history tests:
```bash
pytest test/test_session_replayer.py test/test_session.py test/test_tool_history.py test/test_context_limit.py
```
