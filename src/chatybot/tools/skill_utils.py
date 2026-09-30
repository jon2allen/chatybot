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
    depth = 0
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
        depth = len(loaded)

    skill = skillsdb.get_skill_by_name(name)

    # Fallback lookup: case-insensitive and hyphen/underscore normalization.
    if not skill:
        normalized = name.lower().replace("_", "-")
        for s in skillsdb.list_skills(enabled_only=True):
            if s.get("name", "").lower().replace("_", "-") == normalized:
                skill = s
                break

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
    if app is not None:
        result["depth"] = depth

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
