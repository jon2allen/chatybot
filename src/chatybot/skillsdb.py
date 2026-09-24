"""Skills database management for chatybot.

Provides a dedicated TinyDB-backed skills store, separate from the content
databases managed by chatydb.py. Skills are stored as type="skill" items
with metadata for trigger matching, tool configuration, and scoping.

The skills DB is lazily opened on first use (first /skill command or first
trigger match check). A cached index of enabled skills is maintained and
invalidated on any mutation.
"""

import copy
import os
from datetime import datetime
from typing import Any

from .tinydb1.corpus_manager import CorpusManager

SKILLS_DB_PATH = os.path.join(
    os.path.expanduser("~/.local/share/chatybot"), "skills.json"
)

_skills_manager: CorpusManager | None = None
_skills_cache: list[dict] | None = None


def _ensure_manager() -> CorpusManager:
    """Lazy-open the skills DB. Called on first /skill command or first
    trigger match check. Seeds default skills on first creation."""
    global _skills_manager, _skills_cache
    if _skills_manager is not None:
        return _skills_manager
    os.makedirs(os.path.dirname(SKILLS_DB_PATH), exist_ok=True)
    is_new = not os.path.exists(SKILLS_DB_PATH)
    _skills_manager = CorpusManager(SKILLS_DB_PATH)
    _skills_cache = None
    if is_new:
        _seed_default_skills(_skills_manager)
    return _skills_manager


def _get_enabled_skills() -> list[dict]:
    """Return cached index of enabled skills for trigger matching.

    Cache is invalidated on any /skill create/edit/delete/enable/disable.
    """
    global _skills_cache
    if _skills_cache is not None:
        return _skills_cache
    manager = _ensure_manager()
    _skills_cache = [
        item for item in manager.get_items_by_type("skill")
        if item.get("metadata", {}).get("enabled", True)
    ]
    return _skills_cache


def _invalidate_cache() -> None:
    """Call after any mutation (create/update/delete/enable/disable)."""
    global _skills_cache
    _skills_cache = None


def get_matching_skills(user_prompt: str) -> list[dict]:
    """Return enabled skills whose triggers match the user prompt.

    Matching: case-insensitive substring. For each enabled skill, each
    trigger phrase is checked against the user prompt. If any trigger
    phrase appears as a substring of the lowercased prompt, the skill
    is included.
    """
    prompt_lower = user_prompt.lower()
    all_skills = _get_enabled_skills()
    matched = []
    for skill in all_skills:
        triggers = skill.get("metadata", {}).get("triggers", [])
        for trigger in triggers:
            if trigger.lower() in prompt_lower:
                matched.append(skill)
                break
    return matched


def list_skills(enabled_only: bool = False) -> list[dict]:
    """Return all skills, optionally filtered to enabled only."""
    manager = _ensure_manager()
    skills = manager.get_items_by_type("skill")
    if enabled_only:
        skills = [s for s in skills if s.get("metadata", {}).get("enabled", True)]
    return skills


def get_skill_by_name(name: str) -> dict | None:
    """Return the first skill with the given name, or None."""
    manager = _ensure_manager()
    for skill in manager.get_items_by_type("skill"):
        if skill.get("name") == name:
            return skill
    return None


def create_skill(
    name: str,
    content: str,
    description: str = "",
    triggers: list[str] | None = None,
    tags: list[str] | None = None,
    tool_config: dict | None = None,
    source: str = "manual",
) -> int:
    """Create a new skill and return its doc_id."""
    manager = _ensure_manager()
    if triggers is None:
        triggers = []
    if tags is None:
        tags = []
    metadata: dict[str, Any] = {
        "description": description,
        "triggers": triggers,
        "tags": tags,
        "enabled": True,
        "source": source,
        "created_at": datetime.now().isoformat(),
    }
    if tool_config is not None:
        metadata["tool_config"] = tool_config
    doc_id = manager.add_item("skill", name, content, metadata)
    _invalidate_cache()
    return doc_id


def update_skill(
    item_id: int,
    name: str | None = None,
    content: str | None = None,
    metadata: dict | None = None,
) -> bool:
    """Update an existing skill. Metadata is a full replacement if provided."""
    manager = _ensure_manager()
    result = manager.update_item(item_id, name=name, content=content, metadata=metadata)
    _invalidate_cache()
    return result


def patch_skill_metadata(item_id: int, key: str, value: Any) -> bool:
    """Patch a single metadata key on a skill without replacing the full dict."""
    manager = _ensure_manager()
    result = manager.patch_metadata(item_id, key, value)
    _invalidate_cache()
    return result


def delete_skill(item_id: int) -> bool:
    """Delete a skill by doc_id."""
    manager = _ensure_manager()
    result = manager.delete_item(item_id)
    _invalidate_cache()
    return result


def search_skills(query: str) -> list[dict]:
    """Search skills by name, content, description, and tags (case-insensitive)."""
    manager = _ensure_manager()
    q = query.lower()
    results = []
    for skill in manager.get_items_by_type("skill"):
        name = str(skill.get("name") or "").lower()
        content = str(skill.get("content") or "").lower()
        meta = skill.get("metadata", {})
        desc = str(meta.get("description") or "").lower()
        tags_str = " ".join(str(t) for t in meta.get("tags", [])).lower()
        if q in name or q in content or q in desc or q in tags_str:
            results.append(skill)
    return results


def export_skill_to_skillmd(name: str, filepath: str) -> bool:
    """Export a skill to SKILL.md format (YAML frontmatter + markdown body)."""
    skill = get_skill_by_name(name)
    if not skill:
        return False
    meta = skill.get("metadata", {})
    triggers = meta.get("triggers", [])
    tags = meta.get("tags", [])
    tool_config = meta.get("tool_config")

    lines = ["---"]
    lines.append(f"name: {skill['name']}")
    lines.append(f"description: {meta.get('description', '')}")
    if triggers:
        lines.append(f"triggers: {triggers}")
    if tags:
        lines.append(f"tags: {tags}")
    if tool_config:
        lines.append(f"tool_config: {tool_config}")
    lines.append(f"enabled: {meta.get('enabled', True)}")
    lines.append("---")
    lines.append("")
    lines.append(skill.get("content", ""))

    try:
        os.makedirs(os.path.dirname(filepath) or ".", exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
        return True
    except Exception:
        return False


def import_skill_from_skillmd(filepath: str) -> int | None:
    """Import a skill from a SKILL.md file (YAML frontmatter + markdown body).

    Returns the new doc_id, or None on failure.
    """
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            text = f.read()
    except Exception:
        return None

    if not text.startswith("---"):
        return None

    parts = text.split("---", 2)
    if len(parts) < 3:
        return None

    frontmatter_text = parts[1].strip()
    body = parts[2].strip()

    # Simple YAML parsing for our flat key: value format
    import re

    meta_fields: dict[str, Any] = {}
    for line in frontmatter_text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        match = re.match(r"^(\w+):\s*(.*)$", line)
        if not match:
            continue
        key = match.group(1)
        val = match.group(2).strip()
        # Parse list values like ['a', 'b'] or ["a", "b"]
        if val.startswith("[") and val.endswith("]"):
            inner = val[1:-1].strip()
            if inner:
                items = [x.strip().strip("\"'") for x in inner.split(",")]
                meta_fields[key] = items
            else:
                meta_fields[key] = []
        elif val.lower() in ("true", "false"):
            meta_fields[key] = val.lower() == "true"
        else:
            meta_fields[key] = val.strip("\"'")

    name = meta_fields.get("name", "imported-skill")
    description = meta_fields.get("description", "")
    triggers = meta_fields.get("triggers", [])
    tags = meta_fields.get("tags", [])
    tool_config = meta_fields.get("tool_config")
    if isinstance(tool_config, str):
        tool_config = None

    return create_skill(
        name=name,
        content=body,
        description=description,
        triggers=triggers if isinstance(triggers, list) else [],
        tags=tags if isinstance(tags, list) else [],
        tool_config=tool_config if isinstance(tool_config, dict) else None,
        source=f"import:{filepath}",
    )


def _seed_default_skills(manager: CorpusManager) -> None:
    """Seed the skills database with default skills on first creation."""
    for skill in DEFAULT_SKILLS:
        skill_data = copy.deepcopy(skill)
        skill_data["metadata"]["created_at"] = datetime.now().isoformat()
        manager.add_item(
            item_type=skill_data["type"],
            name=skill_data["name"],
            content=skill_data["content"],
            metadata=skill_data["metadata"],
        )
    print(f"[skills] Seeded {len(DEFAULT_SKILLS)} default skills.")


DEFAULT_SKILLS: list[dict[str, Any]] = [
    {
        "type": "skill",
        "name": "code-review",
        "content": (
            "You are a code reviewer. Read the relevant files using the available tools, "
            "identify bugs, security issues, and style problems. For each issue, cite the "
            "file and line number, explain the problem, and suggest a fix. Prioritize: "
            "security vulnerabilities, logic bugs, error handling, then style. After analysis, "
            "summarize findings as Critical, Warnings, and Style categories."
        ),
        "metadata": {
            "description": "Reviews code for bugs, style, and security using the agentic tool loop",
            "triggers": ["review code", "code review", "review my code", "review this code", "check my code"],
            "tags": ["coding", "review", "quality", "agentic"],
            "enabled": True,
            "source": "default",
            "tool_config": {
                "mode": "on",
                "enable_tools": ["read_file", "grep_search", "find_files", "list_directory"],
                "disable_tools": ["write_file", "run_command", "replace_file_content"],
                "auto_loop": True,
                "max_turns": 25,
            },
        },
    },
    {
        "type": "skill",
        "name": "debug-error",
        "content": (
            "You are a debugger. The user has provided an error message or stack trace. "
            "Use file tools to read the relevant source files, trace the error to its root "
            "cause, and explain: (1) what went wrong, (2) which file and line caused it, "
            "(3) how to fix it. Do not modify any files."
        ),
        "metadata": {
            "description": "Debug an error by reading source files and tracing root cause",
            "triggers": ["debug error", "debug this", "fix error", "stack trace", "what's wrong with", "why am i getting", "debug this error"],
            "tags": ["coding", "debug", "troubleshooting", "agentic"],
            "enabled": True,
            "source": "default",
            "tool_config": {
                "mode": "on",
                "enable_tools": ["read_file", "grep_search", "find_files", "list_directory"],
                "disable_tools": ["write_file", "run_command", "replace_file_content"],
                "auto_loop": True,
                "max_turns": 20,
            },
        },
    },
    {
        "type": "skill",
        "name": "write-test",
        "content": (
            "You are a test engineer. Read the source code using file tools, understand "
            "the function signatures and behavior, then write comprehensive unit tests. "
            "Cover: normal cases, edge cases, error handling, and boundary conditions. "
            "Write the tests to a file using the write_file tool. Use the same testing "
            "framework as existing tests in the project."
        ),
        "metadata": {
            "description": "Write unit tests by reading source code and generating test cases",
            "triggers": ["write test", "write tests", "generate tests", "create test", "unit test", "test cases for"],
            "tags": ["coding", "testing", "agentic", "quality"],
            "enabled": True,
            "source": "default",
            "tool_config": {
                "mode": "on",
                "enable_tools": ["read_file", "find_files", "grep_search", "write_file", "list_directory"],
                "disable_tools": ["run_command", "replace_file_content"],
                "auto_loop": True,
                "max_turns": 20,
            },
        },
    },
    {
        "type": "skill",
        "name": "research-agent",
        "content": (
            "You are a research agent. Use file tools to read documents in the working "
            "directory, then synthesize a 5-bullet briefing on the requested topic. "
            "After synthesizing, state READY TO LOG so the user can log the result to "
            "the database."
        ),
        "metadata": {
            "description": "Autonomous research agent that reads files and synthesizes findings",
            "triggers": ["research agent", "research this", "autonomous research", "gather information", "research topic"],
            "tags": ["research", "agentic", "database", "automation"],
            "enabled": True,
            "source": "default",
            "tool_config": {
                "mode": "on",
                "enable_tools": ["read_file", "find_files", "grep_search", "list_directory", "run_command"],
                "auto_loop": True,
                "max_turns": 30,
            },
        },
    },
    {
        "type": "skill",
        "name": "compare-models",
        "content": (
            "When comparing model responses, follow this pattern: "
            "(1) Disable session history with /session history off to prevent cross-model "
            "context contamination. "
            "(2) Run the user's prompt with the first model, save the response to a file, "
            "and load it into filebank1. "
            "(3) Run the same prompt with the second model, save to a file, load into filebank2. "
            "(4) Switch to a judge model and ask it to compare {filebank1} vs {filebank2}, "
            "scoring each 0-10 on accuracy, clarity, and completeness. "
            "(5) Re-enable session history with /session history on. "
            "The user should set variables model1, model2, and judge_model before running."
        ),
        "metadata": {
            "description": "Run the same prompt against multiple models and have a judge compare results",
            "triggers": ["compare models", "model comparison", "compare responses", "a/b test", "ab test models"],
            "tags": ["models", "comparison", "evaluation", "testing"],
            "enabled": True,
            "source": "default",
        },
    },
    {
        "type": "skill",
        "name": "batch-translate",
        "content": (
            "To batch-translate files: "
            "(1) List files with /run ls -1 ${source_dir} and capture the output with "
            "/setvar filelist {LAST_COMPLETION}. "
            "(2) Set the target model with /model ${target_model}. "
            "(3) Iterate with: foreach name in lines(${filelist}) -- for each file, load it "
            "with /file ${source_dir}/${name}, send the translation prompt, save with "
            "/save ${output_dir}/${name}, then /clearfile. "
            "(4) Break on empty names. "
            "The user should set source_dir, output_dir, target_language, and target_model variables."
        ),
        "metadata": {
            "description": "Batch-translate files in a directory using foreach iteration",
            "triggers": ["batch translate", "translate files", "translate all files", "batch process files", "translate directory"],
            "tags": ["translation", "batch", "automation", "foreach"],
            "enabled": True,
            "source": "default",
        },
    },
    {
        "type": "skill",
        "name": "db-research-log",
        "content": (
            "To search prior research and log new findings: "
            "(1) Activate the research database with /setdb ${db_name}. "
            "(2) Search for relevant prior entries with /searchdb \"${search_query}\". "
            "(3) Load results into a variable with /loadvar history ALL. "
            "(4) Compose a multiline prompt that references ${history} and asks the new question. "
            "(5) Log the response with /dblog. "
            "The user should set db_name, search_query, and model_alias variables."
        ),
        "metadata": {
            "description": "Search the database for prior research, inject into prompt, log new response",
            "triggers": ["research log", "search database", "prior research", "db research", "search and log", "inject research"],
            "tags": ["database", "research", "logging", "tinydb"],
            "enabled": True,
            "source": "default",
        },
    },
]
