# Implementation Plan: Skills Tools (`call_skill` & `search_skills`)

## Goal

Provide a lightweight, two-stage mechanism for the LLM to discover and load skills on demand during the agentic tool loop:

1. **`search_skills`**: Discovers available skills by keyword (across name, description, and tags), returning **compact metadata summaries only** (`name`, `description`, `tags`). Crucially, it does **not** return the instruction `content`, keeping token consumption minimal.
2. **`call_skill`**: Retrieves a specific skill's full instruction `content` by name on demand, enabling skill-to-skill delegation (e.g. `grill-with-docs` delegating to `grilling` and `domain-modeling`).

### Core Philosophy: Zero Context Pollution

- **No bloated static catalog:** In systems with 50 to 100+ skills, dumping every skill description into the system prompt wastes thousands of tokens, bloats on-device Apple FM models, and causes attention dilution ("skill confusion").
- **User-directed default:** In most workflows, the user explicitly instructs the model to use a skill (e.g. "use grilling", "help me grill my plan", or `/skill apply grilling`), or a pre-configured meta-skill instructs the model to call specific skills.
- **On-demand discovery:** When the model or user needs to discover an existing capability, the model calls `search_skills(query="...")` which returns only ~20–35 tokens per match.
- **On-demand loading:** Only the selected skill's instructions are loaded via `call_skill(name="...")`.

No nested chatybot instance, no new model call, no subprocess. The tools are fast in-process lookups against `skillsdb`.

---

## Architecture Overview

### Current Tool Dispatch Flow

```
User prompt
  -> _inject_skills()          keyword trigger match -> system prompt injection (pre-turn)
  -> chat_completion()         sends prompt + tool context to LLM
  -> run_tool_loop()           multi-turn loop
       -> model outputs JSON tool call
       -> dispatch_tool()      routes to in-process handler or subprocess
       -> result fed back as "Tool execution results:\n..." in temp_history
       -> repeat until model outputs natural language (no tool call)
```

### In-Process Dispatching

Both `search_skills` and `call_skill` are registered as **in-process handlers** in `dispatch_tool()` ([chatybot_app.py](file:///Users/jon2allen/github/chatybot/src/chatybot/chatybot_app.py#L3682)), alongside `ask_user`, `session_search`, and `decide_*`.

**Rationale:**
- Both tools access `skillsdb`, an internal Chatybot module.
- Running them in-process avoids subprocess startup latency and temporary file serialization overhead.
- Direct access to `app` allows trace logging and potential future tool state checks.

---

## Files to Change

### 1. New file: `src/chatybot/tools/skill_utils.py`

Contains the tool functions. Minimal, self-contained, and safe.

```python
"""Skill tools for LLM-initiated skill discovery and delegation.

Provides:
- search_skills(): Look up available skills by keyword (name, description, tags)
  returning compact summaries to avoid context pollution.
- call_skill(): Look up a skill by name and return its full instruction content
  on demand during the tool loop.
"""

from typing import Any


def search_skills(
    query: str = "",
    limit: int = 10,
    app: Any = None,
) -> dict[str, Any]:
    """Search available skills and return compact metadata summaries.

    To avoid context pollution, this returns ONLY name, description, and tags.
    It does NOT return the full instruction content.

    Parameters
    ----------
    query:
        Keyword to search across skill name, description, and tags.
        If empty or "*", returns all enabled skills up to limit.
    limit:
        Maximum number of matching skills to return (default 10).
    app:
        The running ChatybotApp instance (optional).

    Returns
    -------
    dict
        {"status": "success", "count": ..., "skills": [{"name": ..., "description": ..., "tags": [...]}, ...]}
    """
    from chatybot import skillsdb

    q = (query or "").strip().lower()
    all_skills = skillsdb.list_skills(enabled_only=True)

    if not q or q == "*":
        matches = all_skills
    else:
        matches = []
        for s in all_skills:
            name = str(s.get("name") or "").lower()
            meta = s.get("metadata", {})
            desc = str(meta.get("description") or "").lower()
            tags = " ".join(str(t) for t in meta.get("tags", [])).lower()
            if q in name or q in desc or q in tags:
                matches.append(s)

    results = []
    for s in matches[:limit]:
        meta = s.get("metadata", {})
        results.append({
            "name": s.get("name", ""),
            "description": meta.get("description", ""),
            "tags": meta.get("tags", []),
        })

    return {
        "status": "success",
        "count": len(results),
        "total_matched": len(matches),
        "skills": results,
    }
```

**Note on `total_matched`:** This field shows how many skills matched before slicing to `limit`. There is no `offset` parameter for pagination. If the model needs more results, it can call again with a higher `limit`. Pagination via offset is a future enhancement if skill counts grow large enough to warrant it.

```python
def call_skill(name: str, app: Any = None) -> dict[str, Any]:
    """Look up a skill by name and return its full instruction content.

    If the skill has a tool_config and app is available, the tool changes
    are applied silently (no user prompt) and a tool_state summary is
    returned so the model knows what tools are now available.

    Parameters
    ----------
    name:
        The skill name to look up. Case-insensitive with hyphen/underscore fallback.
    app:
        The running ChatybotApp instance. Pass None only in tests.
        Required for tool_config application and recursion tracking.

    Returns
    -------
    dict
        {"status": "success", "skill": {...}, "tool_state": {...}, "depth": N}
        or
        {"status": "error", "reason": "..."}
    """
    from chatybot import skillsdb

    # --- Recursion tracking (per tool-loop, not per-call) ---
    # Track across the entire multi-turn tool loop so that cycle detection
    # works across turns (Turn 1: call_skill("A"), Turn 2: call_skill("B"),
    # Turn 3: call_skill("A") -> cycle detected).
    # The list is initialized at the start of run_tool_loop() and cleared
    # when the loop terminates.
    MAX_SKILLS_PER_TURN = 5
    if app is not None:
        if not hasattr(app, "_turn_skills_loaded"):
            app._turn_skills_loaded = []
        loaded = app._turn_skills_loaded

        # Cycle detection: if this skill was already loaded in this tool loop, refuse
        if name in loaded:
            chain_str = " -> ".join(loaded)
            return {
                "status": "error",
                "reason": (
                    f"Circular skill delegation detected: {chain_str} -> {name}. "
                    f"Skill '{name}' was already loaded in this tool loop. "
                    f"Remove the circular reference in the skill instructions."
                ),
            }

        # Depth limit: prevent unbounded chaining even without cycles
        if len(loaded) >= MAX_SKILLS_PER_TURN:
            chain_str = " -> ".join(loaded)
            return {
                "status": "error",
                "reason": (
                    f"Maximum skill delegations per tool loop ({MAX_SKILLS_PER_TURN}) reached. "
                    f"Chain: {chain_str}. "
                    f"Cannot load more skills in this turn."
                ),
            }

        loaded.append(name)

    skill = skillsdb.get_skill_by_name(name)

    # Fallback lookup: case-insensitive and hyphen/underscore normalization.
    # Uses enabled_only=True to avoid scanning disabled skills that would
    # be rejected by the enabled check below anyway.
    if not skill:
        return {
            "status": "error",
            "reason": f"Skill '{name}' not found. Use search_skills to discover available skills.",
        }

    meta = skill.get("metadata", {})
    enabled = meta.get("enabled", True)

    if not enabled:
        return {"status": "error", "reason": f"Skill '{skill.get('name', name)}' is disabled"}

    # --- Tool config application ---
    tool_state = None
    tool_config = meta.get("tool_config")
    if tool_config and app is not None:
        tool_state = _apply_tool_config_silent(app, tool_config, skill.get("name", name))

    # --- Build result ---
    result: dict[str, Any] = {
        "status": "success",
        "skill": {
            "name": skill.get("name", name),
            "description": meta.get("description", ""),
            "content": skill.get("content", ""),
        },
    }
    if tool_state:
        result["tool_state"] = tool_state

    return result


def _apply_tool_config_silent(app: Any, config: dict, skill_name: str) -> dict[str, Any]:
    """Apply a skill's tool_config silently (no user prompt).

    Returns a summary of what changed so the model knows its current
    tool capabilities. This is the mid-loop equivalent of
    _apply_skill_tool_config() but without the interactive confirmation.

    The previous tool state is snapshotted for /skill restore.
    """
    changes: list[str] = []
    if config.get("mode") == "on" and not app.tool_mode:
        changes.append("tool_mode: on")
    if config.get("mode") == "off" and app.tool_mode:
        changes.append("tool_mode: off")
    if config.get("enable_tools"):
        changes.append(f"enabled: {', '.join(config['enable_tools'])}")
    if config.get("disable_tools"):
        changes.append(f"disabled: {', '.join(config['disable_tools'])}")
    if config.get("max_turns") and config["max_turns"] != app.max_turns:
        changes.append(f"max_turns: {config['max_turns']}")

    if not changes:
        return {"changed": False, "message": "No tool changes needed"}

    # Save snapshot for /skill restore -- but only if no snapshot exists yet.
    # If skill A applies a config (saving snapshot S0), then skill B applies
    # another config, we must not overwrite S0 with the intermediate state.
    # /skill restore should always roll back to the user's original state.
    if getattr(app, "_tool_state_snapshot", None) is None:
        app._save_tool_state_snapshot()

    # Apply changes
    if config.get("mode") == "on" and not app.tool_mode:
        app.tool_mode = True
    elif config.get("mode") == "off" and app.tool_mode:
        app.tool_mode = False

    for tool_name in config.get("enable_tools", []):
        app.tool_overrides[tool_name] = True
    for tool_name in config.get("disable_tools", []):
        app.tool_overrides[tool_name] = False

    if app.tool_mode:
        app.generate_tool_context()
        app.buffer_manager.set_script_var('TOOL_CONTEXT', app.tool_context)

    if config.get("auto_loop"):
        app.tool_auto = True
    if config.get("max_turns"):
        app.max_turns = config["max_turns"]

    return {
        "changed": True,
        "changes": changes,
        "message": f"Tool configuration updated for skill '{skill_name}'. "
                   f"Changes: {'; '.join(changes)}. "
                   f"Use /skill restore to revert.",
    }
```

**Design decisions:**

- **`search_skills` returns compact metadata only:** Excludes `content` to prevent context bloat. Returning 5 search results consumes ~150 tokens instead of ~3,000 tokens.
- **`search_skills` reimplements search rather than calling `skillsdb.search_skills()`:** The existing `skillsdb.search_skills()` (skillsdb.py:170) searches across name, content, description, and tags. This tool intentionally excludes `content` from both the search corpus and the result set to avoid loading instruction text into the model's context during discovery. The duplication is deliberate.
- **`call_skill` includes name normalization:** Handles case-insensitivity and hyphen/underscore variations (e.g. `domain_modeling` -> `domain-modeling`), preventing brittle tool failures. The fallback scan uses `enabled_only=True` to avoid matching disabled skills that would be rejected immediately after.
- **`call_skill` applies `tool_config` silently:** When the delegated skill has a `tool_config`, it is applied without user confirmation (unlike the pre-turn `_apply_skill_tool_config()` which prompts). Rationale: prompting mid-tool-loop is disruptive -- the model is in a multi-turn sequence and the user would need to approve tool changes at an arbitrary point. A snapshot is saved for `/skill restore`. The `tool_state` field in the result tells the model what changed.
- **`call_skill` returns `tool_state` in the result:** After applying tool_config, the result includes a `tool_state` object with `changed` (bool), `changes` (list of human-readable strings), and `message`. This tells the model what tools are now available/disabled without it having to infer from context. If the skill has no tool_config, `tool_state` is omitted from the result.
- **Tool context is regenerated on the next loop turn:** The tool loop calls `chat_completion()` per turn, which re-injects `effective_tool_context` (line 1365) from `self.tool_context`. Since `_apply_tool_config_silent()` calls `generate_tool_context()` which updates `self.tool_context`, the next turn's context will reflect the new tool state automatically. No special plumbing needed.
- **Does NOT alter `active_skill` lock:** The lock follows the user's initial trigger, not the model's intermediate tool delegations.
- **Recursion is tracked via `app._turn_skills_loaded`:** A list of skill names loaded during the current tool loop, initialized at the start of `run_tool_loop()` and cleared when the loop terminates. Cycle detection and a per-loop limit of 5 delegations prevent unbounded chaining. See the Recursion Handling section below.

---

### 2. Modify: `src/chatybot/tools_config.toml`

Register both `search_skills` and `call_skill`:

```toml
[tools.search_skills]
enabled = true
description = "Search available skills by keyword (name, description, tags). Returns a compact list of matching skill names and descriptions without loading full content. Use when the user asks to find a skill or when looking for a relevant skill to load."
module = "chatybot.tools.skill_utils"
function = "search_skills"

[tools.search_skills.parameters.query]
type = "string"
description = "Keyword to search across skill names, descriptions, and tags. Leave empty or '*' to list all skills."
optional = true

[tools.search_skills.parameters.limit]
type = "integer"
description = "Maximum number of skill summaries to return (default 10)"
optional = true

[tools.call_skill]
enabled = true
description = "Load a skill's full instructions by name. Use when a skill or user tells you to load another skill (e.g. 'Call the Skill tool for grilling'). Returns the skill's instruction content for you to follow."
module = "chatybot.tools.skill_utils"
function = "call_skill"

[tools.call_skill.parameters.name]
type = "string"
description = "The exact or normalized name of the skill to load"
optional = false
```

---

### 3. Modify: `src/chatybot/chatybot_app.py` -- `dispatch_tool()`

Add an in-process handler for both `call_skill` and `search_skills` in `dispatch_tool()`, placed right after `ask_user` (around line 3862):

```python
elif tool_name in ("call_skill", "search_skills"):
    is_enabled = self.tool_overrides.get(tool_name, True)
    if not is_enabled:
        err_msg = f"Error: Tool '{tool_name}' is currently disabled."
        self.buffer_manager.set_script_var('TOOL_DISPATCH_RESULT', '')
        self.buffer_manager.set_script_var('TOOL_DISPATCH_ERROR', err_msg)
        self.buffer_manager.set_script_var('TOOL_DISPATCH_EXIT_CODE', '-1')
        print(err_msg)
        return err_msg
    try:
        from .tools import skill_utils
        args = tool_call.get("arguments", {}) or {}
        if isinstance(args, dict):
            if "parameters" in args and isinstance(args["parameters"], dict):
                args = args["parameters"]
            elif "arguments" in args and isinstance(args["arguments"], dict):
                args = args["arguments"]

        if tool_name == "call_skill":
            res = skill_utils.call_skill(
                name=args.get("name", ""),
                app=self,
            )
        else:
            # Coerce limit safely: model may pass a string or invalid value
            raw_limit = args.get("limit", 10)
            try:
                limit_val = int(raw_limit)
            except (TypeError, ValueError):
                limit_val = 10
            res = skill_utils.search_skills(
                query=args.get("query", ""),
                limit=limit_val,
                app=self,
            )

        result_str = json.dumps(
            {"status": res["status"], "tool": tool_name, "result": res},
            indent=2,
            ensure_ascii=False,
        )
        self.buffer_manager.set_script_var('TOOL_DISPATCH_RESULT', result_str)
        self.buffer_manager.set_script_var('TOOL_DISPATCH_ERROR', '')
        self.buffer_manager.set_script_var('TOOL_DISPATCH_EXIT_CODE', '0')
        if res["status"] == "success":
            print(f"Tool dispatched successfully (in-process {tool_name})")
        else:
            print(f"{tool_name} failed: {res.get('reason', 'unknown')}")
        return result_str
    except Exception as e:
        err_msg = f"Error: {tool_name} tool execution failed: {e}"
        self.buffer_manager.set_script_var('TOOL_DISPATCH_RESULT', '')
        self.buffer_manager.set_script_var('TOOL_DISPATCH_ERROR', str(e))
        self.buffer_manager.set_script_var('TOOL_DISPATCH_EXIT_CODE', '1')
        return err_msg
```

---

## End-to-End Flow Examples

### Flow 1: Explicit Skill Delegation (Matt Pocock Pattern)

1. User types: `"help me grill my plan for a new auth system"`
2. `_inject_skills()` triggers `grill-with-docs` (injected into system prompt).
3. The prompt instructs the model: *"Call the Skill tool for 'grilling' and 'domain-modeling'"*.
4. Model executes:
   ```json
   {"tool": "call_skill", "arguments": {"name": "grilling"}}
   ```
5. `call_skill` returns the full grilling instructions.
6. Model executes:
   ```json
   {"tool": "call_skill", "arguments": {"name": "domain-modeling"}}
   ```
7. Model follows both instruction sets and begins interviewing the user.

---

### Flow 2: On-Demand Skill Discovery (Zero Context Pollution)

1. User types: `"Can you help me interview and stress-test my database schema? Is there a skill for that?"`
2. No specific trigger matched pre-turn (system prompt remains small and clean).
3. Model sees `search_skills` tool in context and runs:
   ```json
   {"tool": "search_skills", "arguments": {"query": "interview"}}
   ```
4. Tool returns a compact list (no full instruction content):
   ```json
   {
     "status": "success",
     "count": 1,
     "skills": [
       {
         "name": "grilling",
         "description": "A relentless interview technique to stress-test designs and uncover blindspots",
         "tags": ["interview", "design", "architecture"]
       }
     ]
   }
   ```
5. Model sees that `grilling` is the exact match and calls:
   ```json
   {"tool": "call_skill", "arguments": {"name": "grilling"}}
   ```
6. Model receives the full grilling instructions and adopts the persona.

---

## Recursion Handling

### The Problem

Skill A's instructions tell the model to call skill B. Skill B's
instructions tell the model to call skill A. Without guards, the model
loops indefinitely, consuming turns and tokens without producing useful
output. Even without a direct cycle, deep chains (A -> B -> C -> D -> E
-> F ...) degrade context quality as each loaded skill's instructions
accumulate in conversation history.

### Why per-call tracking does not work

`call_skill` is a synchronous function that returns text. It does not
nest -- each call is a discrete tool call in a separate loop turn. If
we increment a depth counter on entry and decrement on exit (like a
call stack), the counter is always 0 at the start of each call. Cycle
detection that resets after each call will never catch a cycle that
spans turns:

```
Turn 1: call_skill("A") -> chain: [] -> ["A"] -> returns -> resets to []
Turn 2: call_skill("B") -> chain: [] -> ["B"] -> returns -> resets to []
Turn 3: call_skill("A") -> chain: [] -> ["A"] -> returns -> resets to []
  ^-- cycle never detected!
```

### Solution: Per-tool-loop tracking

Track all skills loaded across the entire multi-turn tool loop in a
single list that persists for the loop's lifetime:

**`app._turn_skills_loaded`** (list[str], initialized at loop start):

- Initialized to `[]` at the start of `run_tool_loop()` (see
  `chatybot_app.py` modification below).
- On each `call_skill` invocation, checks if the requested name is
  already in the list (cycle detection).
- If not, appends the name and proceeds.
- Hard limit of `MAX_SKILLS_PER_TURN = 5`. If exceeded, returns an
  error without loading the skill.
- The list is NOT reset after each `call_skill` returns. It accumulates
  across all turns in the loop.
- Cleared when the tool loop terminates (natural language response
  reached or `max_turns` hit).

### Lifecycle

```
run_tool_loop() starts
  -> app._turn_skills_loaded = []

Turn 1: Model calls call_skill("grilling")
  -> check: "grilling" not in [] -> ok
  -> app._turn_skills_loaded = ["grilling"]
  -> skill loaded, result returned to model

Turn 2: Model calls call_skill("domain-modeling")
  -> check: "domain-modeling" not in ["grilling"] -> ok
  -> app._turn_skills_loaded = ["grilling", "domain-modeling"]
  -> skill loaded, result returned to model

Turn 3: Model calls call_skill("grilling")  (circular)
  -> check: "grilling" in ["grilling", "domain-modeling"] -> REFUSE
  -> error: "Circular skill delegation detected: grilling -> domain-modeling -> grilling"

Tool loop terminates
  -> app._turn_skills_loaded = []  (cleared for next loop)
```

### What about true nesting?

True nesting (skill A's tool_config spawns a sub-loop that calls skill
B within that sub-loop) is not possible in the current architecture.
`call_skill` is a synchronous function that returns text. It does not
spawn a new tool loop. If sub-agent isolation is needed (separate
context window, separate tool loop), that is the Phase 4 sub-agent
engine described in [skill_concerns.md](file:///Users/jon2allen/github/chatybot/skill_concerns.md).

### Initialization

`app._turn_skills_loaded` is initialized to `[]` at the start of
`run_tool_loop()` in `chatybot_app.py`. Add one line after
`self.in_tool_loop = True` (around line 4998):

```python
self.in_tool_loop = True
self._turn_skills_loaded = []  # Track skills loaded in this tool loop
```

The list is cleared naturally when the next `run_tool_loop()` call
reinitializes it. No cleanup needed on loop termination.

---

## Known Limitations & Future Roadmap

1. **Tool config is applied silently, not confirmed:** Unlike the pre-turn `_apply_skill_tool_config()` which prompts the user with a diff summary, `call_skill` applies tool_config without confirmation. This is intentional -- prompting mid-loop is disruptive. The user can revert with `/skill restore`. Future enhancement: add a `confirm_tool_config` flag to skill metadata for skills that should prompt even mid-loop.
2. **Session Lock Remains with Parent:** The parent skill stays locked as `self.active_skill` across subsequent turns. `call_skill` does not change the lock.
3. **Context Accumulation in Tool Results:** Loaded skill instructions remain in conversation history turns. Each `call_skill` result (including full instruction content) stays in `temp_history` for the duration of the tool loop. Future phase: sub-agents running in isolated contexts as outlined in [skill_concerns.md](file:///Users/jon2allen/github/chatybot/skill_concerns.md).
4. **Snapshot is saved once per tool loop:** `_apply_tool_config_silent` only saves a snapshot if `_tool_state_snapshot` is None, so the first delegation's snapshot is preserved across multiple delegations. `/skill restore` always rolls back to the state before the first `call_skill` applied tool changes.
5. **No pagination in `search_skills`:** The `total_matched` field shows how many skills matched before slicing to `limit`. There is no `offset` parameter. The model can call again with a higher `limit` if needed.

---

## Testing Plan

### Unit Test (`tests/test_skill_tools.py`)

```python
from chatybot.tools.skill_utils import call_skill, search_skills
from chatybot import skillsdb


def test_skill_tools():
    # Setup test skill
    skillsdb.create_skill(
        name="test-interview",
        content="Detailed secret instructions for interview...",
        description="Interview assistant",
        triggers=["test interview"],
        tags=["interview", "test"],
    )

    # 1. Test search_skills returns metadata without content
    search_res = search_skills("interview")
    assert search_res["status"] == "success"
    assert search_res["count"] >= 1
    matched = [s for s in search_res["skills"] if s["name"] == "test-interview"][0]
    assert matched["description"] == "Interview assistant"
    assert "content" not in matched  # Zero context pollution!

    # 2. Test call_skill returns full content
    call_res = call_skill("test-interview")
    assert call_res["status"] == "success"
    assert call_res["skill"]["content"] == "Detailed secret instructions for interview..."
    assert call_res["depth"] == 1

    # 3. Test call_skill case-insensitivity and normalization
    call_norm = call_skill("TEST_INTERVIEW")
    assert call_norm["status"] == "success"
    assert call_norm["skill"]["name"] == "test-interview"

    # 4. Test not found
    err_res = call_skill("nonexistent")
    assert err_res["status"] == "error"
    assert "search_skills" in err_res["reason"]


def test_call_skill_tool_config(app):
    """Test that call_skill applies tool_config silently and returns tool_state."""
    # Setup skill with tool_config
    skillsdb.create_skill(
        name="test-agentic",
        content="Use read_file to inspect code.",
        description="Agentic test skill",
        triggers=["test agentic"],
        tool_config={
            "mode": "on",
            "enable_tools": ["read_file", "grep_search"],
            "disable_tools": ["write_file"],
            "auto_loop": True,
            "max_turns": 15,
        },
    )

    res = call_skill("test-agentic", app=app)
    assert res["status"] == "success"
    assert "tool_state" in res
    assert res["tool_state"]["changed"] is True
    assert "enabled: read_file, grep_search" in res["tool_state"]["changes"]
    assert "disabled: write_file" in res["tool_state"]["changes"]
    assert app.tool_overrides.get("read_file") is True
    assert app.tool_overrides.get("write_file") is False
    assert app.max_turns == 15


def test_call_skill_recursion_cycle(app):
    """Test that circular delegation is detected across tool loop turns."""
    # Simulate: skill-a already loaded earlier in this tool loop
    app._turn_skills_loaded = ["skill-a"]

    # Create skill-a that would be called again (circular)
    skillsdb.create_skill(
        name="skill-a",
        content="Call skill-a again (circular)",
        description="Circular skill",
        triggers=["circular test"],
    )

    res = call_skill("skill-a", app=app)
    assert res["status"] == "error"
    assert "Circular skill delegation detected" in res["reason"]
    assert "skill-a -> skill-a" in res["reason"]


def test_call_skill_recursion_depth_limit(app):
    """Test that max delegations per tool loop is enforced."""
    app._turn_skills_loaded = ["a", "b", "c", "d", "e"]  # At the limit

    skillsdb.create_skill(
        name="skill-f",
        content="Too deep",
        description="Depth test",
        triggers=["depth test"],
    )

    res = call_skill("skill-f", app=app)
    assert res["status"] == "error"
    assert "Maximum skill delegations per tool loop" in res["reason"]
    assert "5" in res["reason"]


def test_call_skill_accumulates_across_turns(app):
    """Test that _turn_skills_loaded accumulates across calls (not reset per call)."""
    app._turn_skills_loaded = []

    skillsdb.create_skill(
        name="skill-x",
        content="Test X",
        description="Test",
        triggers=["test x"],
    )
    skillsdb.create_skill(
        name="skill-y",
        content="Test Y",
        description="Test",
        triggers=["test y"],
    )

    # First call
    res1 = call_skill("skill-x", app=app)
    assert res1["status"] == "success"
    assert app._turn_skills_loaded == ["skill-x"]

    # Second call (different skill, should succeed)
    res2 = call_skill("skill-y", app=app)
    assert res2["status"] == "success"
    assert app._turn_skills_loaded == ["skill-x", "skill-y"]

    # Third call (circular -- skill-x already loaded)
    res3 = call_skill("skill-x", app=app)
    assert res3["status"] == "error"
    assert "Circular" in res3["reason"]


def test_call_skill_snapshot_not_overwritten(app):
    """Test that _tool_state_snapshot is saved only once across multiple delegations."""
    skillsdb.create_skill(
        name="skill-config-a",
        content="Skill A",
        description="Config A",
        triggers=["config a"],
        tool_config={"mode": "on", "enable_tools": ["read_file"], "disable_tools": ["write_file"]},
    )
    skillsdb.create_skill(
        name="skill-config-b",
        content="Skill B",
        description="Config B",
        triggers=["config b"],
        tool_config={"mode": "on", "enable_tools": ["grep_search"], "disable_tools": ["run_command"]},
    )

    app._turn_skills_loaded = []
    app._tool_state_snapshot = None

    # First delegation saves snapshot
    call_skill("skill-config-a", app=app)
    snapshot_after_a = app._tool_state_snapshot
    assert snapshot_after_a is not None

    # Second delegation should NOT overwrite the snapshot
    call_skill("skill-config-b", app=app)
    assert app._tool_state_snapshot is snapshot_after_a  # Same object, not replaced

---

## Summary of Changes

| File | Change | Lines |
|---|---|---|
| `src/chatybot/tools/skill_utils.py` | New file: `search_skills()`, `call_skill()`, `_apply_tool_config_silent()` | ~170 lines |
| `src/chatybot/tools_config.toml` | Add `[tools.search_skills]` and `[tools.call_skill]` | ~25 lines |
| `src/chatybot/chatybot_app.py` | Add in-process dispatcher block + `_turn_skills_loaded` init in `run_tool_loop()` | ~42 lines |

Total: ~237 lines of clean, modular code touching 3 files without breaking existing workflows.
