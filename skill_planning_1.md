# Skills Database Planning — Session 1

## Date: 2026-09-23

---

## Part 1: Survey of How Other Platforms Handle Skills

### Research Methodology

Web searches were conducted across multiple queries covering Claude Code, Cursor, Devin, Vibe, and the broader Agent Skills ecosystem, including centralization patterns and database storage approaches.

---

### The Agent Skills Open Standard

Anthropic published the **SKILL.md format** as an open standard (now at agentskills.io). A skill is a folder containing a `SKILL.md` file with YAML frontmatter (name, description required) plus a markdown body, with optional `scripts/`, `references/`, and `assets/` subdirectories. It uses **progressive disclosure**: at startup the agent loads only name + description (~100 tokens), then pulls in the full body (~2,000 tokens) only when a task matches. This format is now adopted by 25+ tools.

Key sources:
- Agent Skills Overview — agentskills.io
- Claude Code Docs — code.claude.com/docs/en/skills
- Anthropic Skills repo — github.com/anthropics/skills
- SKILL.md Format Specification — agensi.io/learn/agent-skills-open-standard

---

### How Each Platform Handles Skills

| Platform | Storage | Discovery | Centralized? |
|---|---|---|---|
| **Claude Code** | Filesystem: `~/.claude/skills/` (user) + `.claude/skills/` (repo) | Auto-scan at startup; model loads on demand | No — purely local files |
| **Cursor** | Filesystem: `.cursor/rules/*.mdc` files (legacy `.cursorrules`) | Rule types: Always, Auto-Attached (glob), Agent-Requested, Manual | No — version-controlled files |
| **Devin** | Cloud-hosted Knowledge Base + SKILL.md files committed to repos | Knowledge items have trigger descriptions; auto-retrieved when triggers match during sessions | Yes — closest precedent |
| **Vibe** | Filesystem: `~/.vibe/skills/` + project `.vibe/skills/`; plugin packages | Auto-scan + plugin marketplace | No — local files + plugins |

#### Claude Code

Claude Code discovers Skills automatically from two locations: a user-level folder at `~/.claude/skills/` and a repo-level folder at `.claude/skills/`. No API registration, no per-request enabling. When the model sees a task that matches a Skill's stated purpose, it loads the SKILL.md, follows the steps, and uses whatever scripts the folder contains.

Custom commands have been merged into skills. A file at `.claude/commands/deploy.md` and a skill at `.claude/skills/deploy/SKILL.md` both create `/deploy` and work the same way. Skills add optional features: a directory for supporting files, frontmatter to control whether you or Claude invokes them, and the ability for Claude to load them automatically when relevant.

Claude Code skills follow the Agent Skills open standard, which works across multiple AI tools. The same skill works across the Claude API, Claude Code, and other agents.

Sources:
- code.claude.com/docs/en/skills
- platform.claude.com/docs/en/agents-and-tools/agent-skills/overview
- github.com/anthropics/claude-code (skill-development SKILL.md)
- hidekazu-konishi.com — Claude Code Skills Complete Guide
- totalum.app — Claude Code Skills in 2026

#### Cursor

Cursor Project Rules are Markdown-based `.mdc` files that live in `.cursor/rules/` and tell Cursor how to behave for specific projects, file types, frameworks, and workflows. The legacy `.cursorrules` file in the project root still works but is no longer recommended.

Rule types:
- **Always** — loaded into context for every interaction
- **Auto-Attached** — triggered by glob pattern matching files in the editor
- **Agent-Requested** — the agent decides to load based on task relevance
- **Manual** — only loaded when explicitly referenced via `@rulename`

Rules are version-controlled files scoped to the codebase. No central database. Teams share rules via the repository.

Sources:
- cursor.com/docs
- dev.to — Mastering Cursor Rules
- kirill-markin.com — Cursor IDE Rules for AI
- github.com/PatrickJS/awesome-cursorrules

#### Devin

Devin maintains a cloud-hosted, database-backed knowledge store with:

- **Trigger-based retrieval** — each item has a trigger description; Devin pulls it in only when relevant during a session
- **Scoping hierarchy** — no repo / one repo / all repos, then Organization scope (default) and Enterprise scope
- **Promotion** — org-level items can be promoted to enterprise scope
- **AI-generated suggestions** — Devin suggests new knowledge from session feedback
- **Macros** — `!macro-name` shortcuts to load context bundles
- **Knowledge is deprecated** — being migrated into Skills-in-Plugins (SKILL.md files committed to repos), but the centralized cloud-store model remains

Devin Knowledge is a shared library of triggers, procedures, and constraints the agent retrieves during sessions. Knowledge can be scoped to a single organization or to an entire enterprise. If an organization-level knowledge item proves useful enough to share across the entire enterprise, you can promote it directly from the knowledge editor.

Devin also supports Skills as SKILL.md files committed directly into repositories — step-by-step instructions for repeatable workflows, discovered automatically by Devin, and followed exactly whenever the relevant task comes up.

Enterprise admins centrally manage roles, IdP groups, IP access lists, and organization-wide Knowledge and Playbook standards at the Enterprise level.

Sources:
- docs.devin.ai/product-guides/knowledge
- fast.io/resources/devin-knowledge-guide/
- medium.com/@nitinmatani22 — Devin's Knowledge Base
- medium.com/@nitinmatani22 — Devin AI Skills: The SKILL.md Files
- cognition.com/blog/how-cognition-uses-devin-to-build-devin
- innfactory.ai — Devin: Cognition's AI Coding Agent Harness
- fast.io/resources/devin-enterprise-guide/

#### Vibe (Mistral)

Vibe is powered by Mistral's models (including Devstral 2) and supports the Agent Skills specification natively. Skills are stored as SKILL.md files in `~/.vibe/skills/` (global) and project-local `.vibe/skills/`. Plugin packages provide additional skill bundles via a marketplace.

Vibe's skill system uses the same progressive disclosure pattern: the agent sees a one-line description at startup and pulls in full instructions only when the task matches.

Sources:
- agentskill.sh/vibe
- docs.factory.ai/guides/skills/vibe-coding

---

### Precedent for Database Centralization

There is clear precedent at three levels:

#### 1. Devin's Knowledge Base (product-level, closest to the goal)

Devin proves the product model: cloud-hosted, trigger-based retrieval, org/enterprise scoping, AI suggestions. The key Devin patterns worth adopting: trigger-based retrieval (not always-on), scoping hierarchy, and learning from session feedback.

#### 2. Google Cloud Skill Registry (infrastructure-level)

Google's Gemini Enterprise Agent Platform ships a "secure, private, low-latency repository" for agent skills. Agents dynamically discover and load capabilities via API. This is a true database-backed centralized skill store with CRUD operations, search, and governance. Skill Registry includes a built-in `gcp-skill-registry` skill that allows agents to interact with Skill Registry to create, search for, and manage available skills.

Source: docs.cloud.google.com/gemini-enterprise-agent-platform/build/skill-registry

#### 3. skills.sh (community/open registry)

An open-source package registry (like npm for skills) hosting tens of thousands of skills. Install via `npx skills add`. It is a centralized distribution layer, not a runtime database — skills still get installed to local filesystem. Works across 11 AI coding agents including Claude Code, Cursor, Windsurf, Copilot, Codex, and more.

Sources:
- skills.sh
- productcool.com/product/skills-sh
- open-vsx.org — Skills.sh Agent Skills Manager extension

#### 4. "Canonicalize-then-fan-out" pattern (emerging community practice)

AgentPatterns.ai documents this architecture: maintain canonical SKILL.md files in a central repo, then use CI to generate tool-specific outputs (`.claude/CLAUDE.md`, `.github/copilot-instructions.md`, etc.) and sync them to downstream repos. JFrog markets a similar "Agent Skills Repository" for enterprise governance, addressing the "shadow skills" problem of unmanaged scripts proliferating across teams.

A Reddit thread on r/dataengineering (2026) captured the team-level pain: "We have incredibly valuable context trapped in siloed repos, meaning an agent working on Project A has zero context about a critical system decision made in Project B." The recommended approach was a centralized `ai-docs` repo with a root AGENTS.md, a skills/ folder, a rules/ folder, and a docs/ folder.

Sources:
- agentpatterns.ai/workflows/central-repo-shared-agent-standards/
- jfrog.com/learn/ai-security/agent-skills-repository/
- reddit.com/r/dataengineering — How are you centralizing knowledge/context from AI agents?

#### 5. Academic Research

An arXiv paper ("From Registry to Repository: How AI Agent Skills Are Written, Adapted, and Maintained") found that skills reach an agent through two distinct channels: some are published to centralised registries such as skills.sh (which already hosts tens of thousands of skills), whilst others are authored by developers for individual repositories and maintained alongside the source code as project-specific infrastructure.

Source: arxiv.org/html/2607.00911v1

---

### Bottom Line from the Survey

The industry is moving from scattered local files toward centralized stores. If you want to build a database-backed skill store, Devin's Knowledge Base architecture (trigger-based retrieval + scope hierarchy + promotion) is the most directly applicable reference design.

---

## Part 2: Chatybot Codebase Review

### TinyDB Layer

- `src/chatybot/tinydb1/corpus_manager.py` — `CorpusManager` class wraps TinyDB
  - Single table `items`, fields: type, name, content, metadata
  - Methods: `add_item`, `get_item`, `get_items_by_type`, `get_items_by_metadata`, `update_item`, `delete_item`, `search_items`, `get_all_items`
- `src/chatybot/chatydb.py` — Global DB facade (697 lines)
  - DB files at `~/.local/share/chatybot/db/<name>.json`
  - Global `_manager` (CorpusManager), `_db_path`, `_active_db_name`
  - `set_db(name)` opens/activates, `list_dbs()`, `search_db()`, `dblog()`, `dbprint()`, `load_var()`, `save_var()`
  - Rolling backups to `.backups/` subdir
  - `SEARCHBUFFER` global for search results

### Command System

- `src/chatybot/commands/registry.py` — `@command` decorator, `CommandRegistry`, `CommandResult`, `CommandContext`
- Commands registered at import time into module-level `registry`
- `CommandContext` has: `buffer_manager`, `config_manager`, `i18n`, `session_store`, `app`
- `handle_escape_command` in `chatybot_app.py:5570` — resolves i18n alias, checks registry, falls through to legacy elif chain

### Session System

- `src/chatybot/session_interface.py` — `BaseSessionStore` ABC
- `src/chatybot/session_store_jsonl.py` — JSONL implementation
- Sessions at `~/.local/share/chatybot/sessions/`
- Session turns store: `prompt`, `response`, `thinking`, `model_alias`, `timestamp`, `agentic_loop`, `type`
- `/session` command has subcommands: start, auto, stop, status, history, note, save, list, use, show, export, info, delete, merge, compress, prune, replay, query, get

### System Prompt Assembly

At `chatybot_app.py:1394`:
- `current_system_message = self.config_manager.system_message`
- Tool context prepended, agentic instructions appended
- Reasoning/thinking adjustments applied
- Final system message inserted as `messages[0]` with role "system"

### DB Tools (LLM-callable)

- `src/chatybot/tools/db_tools.py` — `db_search`, `db_get`, `db_list`, `db_summary`
- These are LLM tool-call functions, registered via `tools_config.toml`

### Storage Layout

```
~/.local/share/chatybot/
├── db/              — TinyDB JSON files (content/chat databases)
├── sessions/        — session files (JSONL)
├── scratch/         — scratchpad
~/.config/chatybot/
├── chat_config.toml
├── tools_config.toml
└── profiles/
```

### Existing Commands (by category)

- **db**: `/setdb` `/dblist` `/searchdb` `/dblog` `/dbprint` `/loadvar` `/savevar`
- **session**: `/session` (with many subcommands)
- **models**: `/system` `/temp` `/context` `/context_limit` `/auto_truncate` `/top_p` `/top_k` `/freq_penalty` `/pres_penalty` `/reasoning` `/effort` `/thinking` `/thoughtstyle` `/seed` `/stream` `/listmodels`
- **tools**: `/run` `/run_safe` `/run_unsafe` `/continue` `/tool`
- **debug**: `/echo` `/trace` `/debug` `/prompt` `/logging` `/save` `/notemode` `/codeonly` `/codeoff` `/multiline` `/env` `/profile` `/mem` `/dump` `/calc` `/str_search` `/setvar` `/reloadmacros` `/listmacros` `/docs`
- **buffer**: `/file` `/clearfile` `/showfile`
- **proc_macros**: `/proc` `/source` `/script` `/chatdsl`
- **rerank**: `/documents` `/rerank`
- **replay**: `/replay`

---

## Part 3: How Devin Does It (Detailed Comparison)

Devin's Knowledge Base is the closest precedent to what is desired:

| Devin Feature | How It Works |
|---|---|
| **Storage** | Cloud-hosted database, not files |
| **Trigger-based retrieval** | Each item has a trigger description; Devin retrieves it only when a session matches |
| **Scoping** | No repo / one repo / all repos, then Organization (default) / Enterprise (promotable) |
| **AI suggestions** | Devin suggests new knowledge from session feedback |
| **Macros** | `!macro-name` shortcuts load context bundles instantly |
| **Migration** | Knowledge is being migrated into Skills-in-Plugins (SKILL.md files committed to repos) |

The key Devin patterns worth adopting: trigger-based retrieval (not always-on), scoping hierarchy, and learning from session feedback.

---

## Part 4: Four Implementation Options

### Option 1: Dedicated Skills TinyDB (Separate File, Separate Manager)

```
~/.local/share/chatybot/
├── db/              ← existing chat/content databases
│   ├── mydb.json
│   └── ...
├── skills.json      ← NEW: dedicated skills database
└── sessions/
```

**Architecture**: New `skillsdb.py` module with its own `CorpusManager` instance, completely independent from `chatydb.py`. The skills DB is always available regardless of which content DB is active.

**Skill record schema** (stored as TinyDB items with `type="skill"`):
```python
{
    "type": "skill",
    "name": "code-review",
    "content": "# Code Review Skill\nWhen the user asks to review code...",
    "metadata": {
        "description": "Reviews code for bugs, style, and security",
        "triggers": ["review code", "code review", "check my code"],
        "tags": ["coding", "review"],
        "scope": "global",
        "enabled": True,
        "created_at": "2026-09-23T...",
        "source": "manual"  # or "session:abc123"
    }
}
```

**`/skill` command** (new command verb with subcommands):
```
/skill list                    — list all skills (name + description + enabled)
/skill show <name>             — show full skill content
/skill create                  — launch wizard
/skill edit <name>             — edit skill content in $EDITOR
/skill delete <name>           — delete a skill
/skill enable <name>           — enable a skill
/skill disable <name>          — disable a skill
/skill search <query>          — search skills by name/content/tags
/skill learn [name]            — learn a skill from current session
/skill apply <name>            — manually inject a skill into the next prompt
/skill export <name> <file>    — export to SKILL.md format
/skill import <file>           — import from SKILL.md file
```

**Wizard** (`/skill create`): Interactive prompt sequence:
1. Skill name (validated against `_DB_NAME_RE` pattern)
2. Description (one-line, used for trigger matching)
3. Trigger phrases (comma-separated)
4. Tags (comma-separated)
5. Content body (multi-line input until `EOF` or `---`)

**Progressive disclosure**: At startup, load all enabled skill descriptions (~1 line each, ~20 tokens). Before each completion, check if the user prompt matches any skill's triggers/description. If match, inject the skill body into the system prompt for that turn only.

**Session learning** (`/skill learn`): Extracts the successful prompt+response pattern from the current session turns. The user reviews and names it. The skill content is derived from the session's effective prompt and the assistant's successful approach.

**Comparison to Devin**: This mirrors Devin's model most closely — a centralized store independent of any specific working database, with trigger-based retrieval and session learning.

| Pros | Cons |
|---|---|
| Clean separation from content DBs | New module + new manager to maintain |
| Skills always available regardless of active DB | Cannot scope skills to a specific database |
| Reuses CorpusManager unchanged | Slight duplication with chatydb.py patterns |
| Most similar to Devin's centralized model | |

**Effort**: Medium. New `skillsdb.py` (~200 lines), new `commands/skills.py` (~300 lines), system prompt injection hook (~50 lines).

---

### Option 2: Skills as Typed Items in the Active DB (Same Table, New Type)

```
~/.local/share/chatybot/db/
├── mydb.json        ← contains chat logs AND skills (type="skill")
├── project2.json
└── ...
```

**Architecture**: No new module. Skills are stored as `type="skill"` items in whatever database is currently active via the existing `chatydb.py` + `CorpusManager`. The `/skill` command operates on the active DB.

**Skill record**: Same schema as Option 1, but stored in the active DB's `items` table alongside `type="chat"` items.

**`/skill` command**: Same subcommands, but all operations go through `chatydb._manager` (the existing global). `/skill list` calls `_manager.get_items_by_type("skill")`.

**Wizard**: Same interactive flow, but calls `chatydb._manager.add_item("skill", name, content, metadata)`.

**Progressive disclosure**: Before each completion, query the active DB for enabled skills, match triggers, inject. Requires an active DB to be set.

**Session learning**: Same as Option 1, but stores into the active DB.

**Comparison to Devin**: This is less like Devin's centralized model and more like having skills scoped to individual projects/databases. It is closer to Devin's per-repo scoping.

| Pros | Cons |
|---|---|
| Zero infrastructure changes — uses existing CorpusManager | Skills locked to active DB; no global skills |
| Skills co-located with related content | Must `/setdb` before skills work |
| `/dbprint`, `/searchdb` already work with type filter | Skills mixed with chat logs in same file |
| Easiest to implement | No cross-DB skill sharing |

**Effort**: Low. New `commands/skills.py` (~250 lines), minor system prompt hook (~40 lines). No new module.

---

### Option 3: Hybrid — Global Skills DB + Per-DB Skill Overrides

```
~/.local/share/chatybot/
├── db/
│   ├── mydb.json           ← may contain type="skill_override" items
│   └── ...
├── skills.json             ← global skills database
└── sessions/
```

**Architecture**: Combines Options 1 and 2. A global `skills.json` (managed by a new `skillsdb.py`) holds the master skill definitions. When a content DB is activated via `/setdb`, any `type="skill_override"` items in that DB are merged on top, overriding or extending global skills.

**Merge precedence**: Per-DB override > Global. If a skill exists in both, the per-DB version wins. If a skill exists only in the per-DB, it is added. If only in global, the global version is used.

**`/skill` command**: Extended with scope awareness:
```
/skill list [global|local|all]    — list skills by scope
/skill create [global|local]      — create in global or current DB
/skill promote <name>             — promote a local skill to global
/skill learn [name] [global|local] — learn from session
```

**Wizard**: Same as Option 1, but asks "global or local?" at the start.

**Progressive disclosure**: Load global skills at startup. On `/setdb`, merge per-DB overrides. Match triggers and inject as before.

**Session learning**: Can learn to either global or local scope.

**Comparison to Devin**: This maps directly to Devin's scoping hierarchy — global skills = Enterprise/Organization scope, per-DB skills = repo-scoped knowledge, promote = Devin's "Promote to Enterprise."

| Pros | Cons |
|---|---|
| Most flexible — global + per-project skills | Most complex to implement |
| Direct analog to Devin's scoping model | Merge logic adds complexity |
| Skills travel with their project DB | Two storage locations to manage |
| Promotion path from local to global | More testing surface |

**Effort**: High. New `skillsdb.py` (~250 lines), `commands/skills.py` (~350 lines), merge logic (~100 lines), system prompt hook (~60 lines).

---

### Option 4: Skills as Session-Derived Artifacts (Session-First Model)

```
~/.local/share/chatybot/
├── db/
│   └── skills.json         ← skills DB, but populated FROM sessions
├── sessions/
│   ├── abc123/             ← session that produced a skill
│   └── ...
└── ...
```

**Architecture**: Skills are always learned from sessions first, then curated into the skills DB. The flow is: user has a good session -> `/skill learn` extracts the pattern -> user reviews and saves it. The skills DB uses the same CorpusManager but is populated exclusively through the learning workflow (though manual creation is still possible via the wizard).

**Session learning is the primary entry point**, not an add-on:

```
/skill learn                    — analyze current session, propose skill
/skill learn <turn_range>       — learn from specific turns (e.g. "3-7")
/skill learn --auto              — auto-extract without confirmation
/skill review                   — review pending learned skills (accept/reject)
/skill list [pending|active]    — list skills by status
/skill apply <name>             — inject skill into next prompt
/skill wizard                   — manual creation (fallback)
```

**Learning process**: The system takes the session turns, identifies the user's intent (from prompts) and the successful approach (from responses), and generates a SKILL.md-style document. The skill is saved with `metadata.source = "session:<id>"` and `metadata.status = "pending"` until reviewed.

**Progressive disclosure**: Same trigger-based injection as other options, but only `status="active"` skills are injected.

**Comparison to Devin**: This goes beyond Devin's model by making session-derived learning the primary workflow rather than an auxiliary feature. Devin suggests knowledge from sessions but still expects manual authoring as the main path.

| Pros | Cons |
|---|---|
| Skills grounded in real sessions | Learning quality depends on session quality |
| Most natural UX — learn from what worked | Requires LLM call to extract skill from session |
| Skills have provenance (which session) | Manual creation is secondary, less polished |
| Novel approach, differentiator from Devin | More complex learning logic |

**Effort**: Medium-High. `skillsdb.py` (~200 lines), `commands/skills.py` (~350 lines), learning extraction logic (~150 lines, may need an LLM call), system prompt hook (~50 lines).

---

## Part 5: Ease-of-Use Comparison

| Criterion | Option 1: Dedicated DB | Option 2: Typed Items | Option 3: Hybrid | Option 4: Session-First |
|---|---|---|---|---|
| **Implementation effort** | Medium | Low | High | Medium-High |
| **Always available** | Yes | No (needs `/setdb`) | Yes | Yes |
| **Global skills** | Yes | No | Yes | Yes |
| **Per-project scoping** | No | Yes (per DB) | Yes | No |
| **Devin scoping analog** | Partial (global only) | Partial (per-repo only) | Full | Partial |
| **Session learning** | Add-on | Add-on | Add-on | Primary workflow |
| **Wizard** | Yes | Yes | Yes (scope-aware) | Yes (review-based) |
| **Reuses existing code** | CorpusManager reused | Everything reused | CorpusManager reused | CorpusManager + session store |
| **`/skill` command** | Yes | Yes | Yes (scope-aware) | Yes (review-aware) |
| **Conceptual complexity** | Low | Lowest | Highest | Medium |

---

## Part 6: Recommendation

**Option 1 (Dedicated Skills TinyDB)** is the best starting point. It is the cleanest fit for the codebase:

- Reuses `CorpusManager` unchanged (same TinyDB code)
- Skills are always available regardless of which content DB is active
- The `/skill` command with subcommands fits naturally into the existing `@command` pattern
- The wizard is straightforward interactive input (same pattern as `/session note`)
- Session learning can be added as `/skill learn` without architectural changes
- If per-project scoping is later desired, can evolve toward Option 3 without rewriting

Option 3 is the most Devin-like but is over-engineered for a first implementation. Option 4 is the most novel but depends on reliable skill extraction from sessions, which adds an LLM dependency and quality risk. Option 2 is the quickest but the "must `/setdb` first" constraint will be friction.

The `/skill` command verb is a clear yes — it follows the existing command pattern exactly, and the subcommand structure mirrors `/session` and `/tool`. The wizard and session learning both fit as subcommands (`/skill create`, `/skill learn`) without needing separate command verbs.

---

## Part 7: Gap Resolution — Concerns Addressed

### Concern 1 (RED): Two System Prompt Code Paths

**Finding**: Confirmed. `chatybot_app.py` has two independent system message assembly paths:

- **Path A** (`chat_completion`, line 1306): Standard OpenAI-compatible completions. System message assembled at ~line 1394, inserted as `messages.insert(0, {"role": "system", ...})`.
- **Path B** (`_apple_fm_completion`, line 2252): Apple Foundation Model path. System message assembled at ~line 2337, passed as `instructions=system_message` to `create_session()`.

The branch happens at line 1339:
```python
if model_config.get("type") == "apple_fm":
    return await self._apple_fm_completion(prompt, stream=stream)
```

Both paths start from the same source (`self.config_manager.system_message`) and apply similar but not identical augmentation logic (tool context, agentic instructions, reasoning adjustments).

**Resolution**: The skill injection hook must be placed in **both** paths. The cleanest approach is a shared helper method on `ChatybotApp`:

```python
def _inject_skills(self, system_message: str, user_prompt: str) -> str:
    """Inject matching skill content into the system message.

    Called from both chat_completion and _apple_fm_completion after
    their own system message assembly, before the message is sent
    to the model.
    """
    from .skillsdb import get_matching_skills
    matched = get_matching_skills(user_prompt)
    if matched:
        skill_block = "\n\n".join(
            f"## Skill: {s['name']}\n{s['content']}" for s in matched
        )
        if system_message:
            return f"{system_message}\n\n--- Active Skills ---\n{skill_block}"
        return f"--- Active Skills ---\n{skill_block}"
    return system_message
```

Injection points:
- Path A: After line ~1430 (after all system message augmentation, before `messages.insert`)
- Path B: After line ~2360 (after system message assembly, before `create_session(instructions=system_message, ...)`)

If Path B (Apple FM) is not a priority for v1, the plan should explicitly state that limitation. However, since the hook is a single method called from two sites, covering both is low-cost.

**Scope decision for v1**: Cover both paths. The shared helper makes this trivial.

---

### Concern 2 (YELLOW): Trigger Matching Algorithm

**Finding**: The original plan said "check if the user prompt matches any skill's triggers" without specifying the algorithm. `CorpusManager.search_items()` uses regex case-insensitive search on `name` and `content` fields via TinyDB's `Query().search()` — but that searches item content, not trigger phrases stored in metadata.

**Resolution**: For v1, use **case-insensitive substring matching** of each trigger phrase against the user prompt. This is simple, predictable, and aligns with the existing `search_db()` pattern in `chatydb.py` (which does `q in name.lower()` substring matching).

Algorithm (in `skillsdb.py`):

```python
def get_matching_skills(user_prompt: str) -> list[dict]:
    """Return enabled skills whose triggers match the user prompt.

    Matching: case-insensitive substring. For each enabled skill,
    each trigger phrase is checked against the user prompt. If any
    trigger phrase appears as a substring of the lowercased prompt,
    the skill is included.

    Trigger phrases should be short, distinctive phrases the user
    would type (e.g. "review code", "write a test", "refactor this").
    Single-word triggers like "test" will match broadly — users should
    use more specific phrases to avoid false positives.
    """
    prompt_lower = user_prompt.lower()
    all_skills = _get_enabled_skills()
    matched = []
    for skill in all_skills:
        triggers = skill.get("metadata", {}).get("triggers", [])
        for trigger in triggers:
            if trigger.lower() in prompt_lower:
                matched.append(skill)
                break  # one match is enough
    return matched
```

**Design implications for trigger phrases**:
- Triggers are substrings, not regex or wildcards
- "review code" matches "can you review code in auth.py" — good
- "test" matches "latest test results" — likely a false positive
- Users should write 2+ word triggers for precision
- The wizard should show a warning for single-word triggers

**Future enhancement** (not v1): fuzzy matching, TF-IDF similarity, or LLM-based semantic matching could improve precision. But substring matching is the right v1 choice — it is debuggable, has zero latency, and users can reason about it.

---

### Concern 3 (YELLOW): update_item Does Full Metadata Replacement

**Finding**: Confirmed at `corpus_manager.py:110`:
```python
if metadata is not None:
    updates['metadata'] = metadata  # full replacement, not a merge
```

This means `/skill enable <name>` and `/skill disable <name>` cannot just call `update_item(item_id, metadata={"enabled": True})` — that would wipe all other metadata fields (triggers, tags, description, etc.).

**Resolution**: Add a `patch_metadata` helper to `CorpusManager`:

```python
def patch_metadata(self, item_id: int, key: str, value: Any) -> bool:
    """Patch a single metadata key without replacing the entire dict.

    Reads the current item, merges the key into its metadata, and
    writes back the full metadata dict. This is necessary because
    TinyDB's update() replaces the entire field value.
    """
    item = self.items.get(doc_id=item_id)
    if not item:
        return False
    current_metadata = item.get("metadata", {})
    current_metadata[key] = value
    self.items.update({"metadata": current_metadata}, doc_ids=[item_id])
    return True
```

Alternatively, `skillsdb.py` can implement this at its own level without modifying `CorpusManager`, since it has access to the manager instance:

```python
def _patch_skill_metadata(manager, item_id, key, value):
    item = manager.get_item(item_id)
    if not item:
        return False
    metadata = item.get("metadata", {})
    metadata[key] = value
    manager.update_item(item_id, metadata=metadata)
    return True
```

**Decision**: Add `patch_metadata` to `CorpusManager` since it is a generally useful operation and other future code paths (not just skills) will benefit. The read-modify-write pattern is safe for single-user TinyDB (no concurrent writers).

---

### Concern 4 (YELLOW): Startup Initialization

**Finding**: `chatydb.py` uses lazy initialization — the `_manager` global is `None` until `set_db()` is called. There is no DB initialization in `ChatybotApp.__init__`. The DB is opened on-demand when the user runs `/setdb` or when a tool call references a database.

**Resolution**: The skills DB should follow the same lazy pattern but with one difference: it should auto-initialize on first use, not require an explicit `/skill init` command.

Two initialization points:

1. **Lazy open on first `/skill` command**: The first time any `/skill` subcommand runs, `skillsdb.py` opens `~/.local/share/chatybot/skills.json` if it is not already open. This is the simplest and matches `chatydb.py`'s pattern.

2. **Pre-load for trigger matching**: The trigger-matching hook (`_inject_skills`) needs skills loaded before every completion. Rather than opening the DB on every completion call, load the skill index (name + description + triggers + enabled flag only, not full content) once at startup and cache it.

Implementation in `skillsdb.py`:

```python
_skills_manager: CorpusManager | None = None
_skills_cache: list[dict] | None = None  # cached index of enabled skills

SKILLS_DB_PATH = os.path.join(
    os.path.expanduser("~/.local/share/chatybot"), "skills.json"
)

def _ensure_manager() -> CorpusManager:
    """Lazy-open the skills DB. Called on first /skill command or
    first trigger match check."""
    global _skills_manager, _skills_cache
    if _skills_manager is not None:
        return _skills_manager
    os.makedirs(os.path.dirname(SKILLS_DB_PATH), exist_ok=True)
    _skills_manager = CorpusManager(SKILLS_DB_PATH)
    _skills_cache = None  # invalidate cache
    return _skills_manager

def _get_enabled_skills() -> list[dict]:
    """Return cached index of enabled skills for trigger matching.
    Cache is invalidated on any /skill create/edit/delete/enable/disable."""
    global _skills_cache
    if _skills_cache is not None:
        return _skills_cache
    manager = _ensure_manager()
    _skills_cache = [
        item for item in manager.get_items_by_type("skill")
        if item.get("metadata", {}).get("enabled", True)
    ]
    return _skills_cache

def _invalidate_cache():
    """Call after any mutation (create/update/delete/enable/disable)."""
    global _skills_cache
    _skills_cache = None
```

**Startup sequence**:
- `ChatybotApp.__init__`: No change needed. Skills DB is not opened at startup.
- First `chat_completion` or `_apple_fm_completion` call: `_inject_skills` calls `_get_enabled_skills()` which lazy-opens the DB and caches the index. If `skills.json` does not exist, it is created empty. The cost is one TinyDB open on the first completion — negligible.
- First `/skill` command: Same lazy open via `_ensure_manager()`.

**Cache invalidation**: Every mutating `/skill` subcommand (`create`, `edit`, `delete`, `enable`, `disable`, `learn`) calls `_invalidate_cache()` after writing. The next completion call rebuilds the cache.

---

### Concern 5 (YELLOW): /skill edit Needs Async-Safe $EDITOR Launch

**Finding**: The codebase already has a precedent for launching `$EDITOR` from async command handlers. In `commands/tools.py:573`, the `/tool edit_live` handler uses:

```python
import subprocess
# ...
editor = config_editor or os.environ.get("VISUAL") or os.environ.get("EDITOR") or default_editor
cmd = shlex.split(editor) + [temp_path]
subprocess.run(cmd)  # blocking call inside an async handler
```

This is a **blocking `subprocess.run()` inside an async function**. It works because:
1. The chatybot event loop is single-threaded and not serving other requests concurrently
2. The user is blocked waiting for the editor to close anyway
3. There is no `asyncio.create_subprocess_exec()` usage anywhere in the codebase

The same pattern appears in `commands/tools.py:1664` for the tool retry editor.

**Resolution**: `/skill edit` should follow the exact same pattern as `/tool edit_live`:

```python
@command("/skill", ...)
async def cmd_skill(ctx: CommandContext, parts: list, command: str) -> CommandResult:
    # ... subcommand dispatch ...
    if subcmd == "edit":
        import subprocess
        import tempfile
        import shlex

        skill_name = parts[2].strip('"')
        manager = _ensure_manager()
        # Find skill by name
        skills = [s for s in manager.get_items_by_type("skill")
                  if s.get("name") == skill_name]
        if not skills:
            print(f"Skill '{skill_name}' not found.")
            return CommandResult.ok()

        skill = skills[0]
        skill_id = skill.doc_id

        with tempfile.NamedTemporaryFile(
            suffix=".md", delete=False, mode="w", encoding="utf-8"
        ) as tf:
            tf.write(f"# Skill: {skill['name']}\n")
            tf.write(f"# Description: {skill.get('metadata', {}).get('description', '')}\n")
            tf.write(f"# Triggers: {', '.join(skill.get('metadata', {}).get('triggers', []))}\n")
            tf.write(f"# Tags: {', '.join(skill.get('metadata', {}).get('tags', []))}\n")
            tf.write(f"# Enabled: {skill.get('metadata', {}).get('enabled', True)}\n")
            tf.write("# --- Edit content below this line ---\n")
            tf.write(skill.get("content", ""))
            temp_path = tf.name

        # Resolve editor (same precedence as /tool edit_live)
        config = ctx.app._load_tools_config()
        config_editor = config.get("config", {}).get("editor") if config else None
        default_editor = "notepad.exe" if os.name == "nt" else "vi"
        editor = (config_editor
                  or os.environ.get("VISUAL")
                  or os.environ.get("EDITOR")
                  or default_editor)

        print(f"Opening skill editor using '{editor}'...")
        if os.name == "nt":
            cmd = shlex.split(editor, posix=False) + [temp_path]
        else:
            cmd = shlex.split(editor) + [temp_path]
        subprocess.run(cmd)  # blocking, same as /tool edit_live

        # Read back and parse
        with open(temp_path, "r", encoding="utf-8") as f:
            saved = f.read()
        os.unlink(temp_path)

        # Parse header fields and content
        # ... (extract description, triggers, tags, enabled from comments,
        #      content is everything after the "---" marker)
        _invalidate_cache()
        return CommandResult.ok()
```

**Note**: This is safe because chatybot is a single-user CLI, not a concurrent server. The blocking `subprocess.run()` is the established pattern in this codebase. Using `asyncio.create_subprocess_exec()` would be more "correct" but would diverge from the existing convention and add complexity for no practical benefit.

---

### Concern 6 (GREEN): Tags vs Triggers Distinction

**Finding**: The schema has both `tags` and `triggers` in metadata, but their behavioral difference was not stated.

**Resolution**: Explicit definitions:

- **Triggers** (`metadata.triggers`): A list of phrases used for **automated matching**. Before each completion, the user's prompt is checked against each trigger phrase via case-insensitive substring match. If any trigger matches, the skill's full content is injected into the system prompt for that turn. Triggers are the "activation mechanism" — they determine *when* a skill is loaded. Example: `["review code", "code review", "check my code"]`.

- **Tags** (`metadata.tags`): A list of keywords used for **human browsing and organization**. Tags have no behavioral effect on matching or injection. They are used by `/skill search` and `/skill list` for filtering and grouping. Tags help the user find and manage skills but do not affect what the LLM sees. Example: `["coding", "review", "quality"]`.

The wizard should explain this distinction when asking for each field:
- Step 3 (Triggers): "Enter trigger phrases that should activate this skill (comma-separated). These are matched against your prompt text. Use 2+ word phrases for precision. Example: review code, code review"
- Step 4 (Tags): "Enter tags for organization and search (comma-separated). Tags do not affect activation — use triggers for that. Example: coding, review, quality"

---

## Part 8: Localization Analysis — New Words for /skill Command

### Localization System Architecture

Chatybot's localization system (`src/chatybot/localization.py`) uses a `translations.json` catalog with 6 locales: `en`, `es`, `fr`, `zh`, `it`, `ar`. Each locale has three sections:

- **aliases**: Localized slash-command names mapped to canonical English commands (e.g. `/sesion` -> `/session` in Spanish)
- **keywords**: Localized subcommand words mapped to canonical English keywords (e.g. `iniciar` -> `start` in Spanish)
- **ui**: UI string templates (e.g. `goodbye_message`, `chat_prompt`)

The `resolve_command()` method resolves localized `/skill` aliases back to `/skill`. The `translate_script()` method translates localized keywords in ChatDSL scripts. The `get_reverse_aliases()` method builds a reverse map for all locales.

### Web Search Validation: "Skill" Terminology in Other Languages

Web searches confirmed that the AI/LLM community uses established translations of "skill" in each of chatybot's supported languages:

| Language | Word for "Skill" | Evidence from Web Search |
|---|---|---|
| **Spanish** | habilidad (pl. habilidades) | Google Cloud docs (es): "Las habilidades de los agentes son paquetes reutilizables de instrucciones"; alphaXiv (es): "una habilidad es más que una simple llamada a una función"; Salesforce (es): "habilidades prediseñadas" |
| **French** | compétence (pl. compétences) | alphaXiv (fr): "compétences externes — des collections de documentation"; ActuIA (fr): "Skills agentiques: quatre cadres de compétences pour LLM"; "bibliothèque de compétences (skill library)" |
| **Chinese** | 技能 (ji néng) | alphaXiv (zh): "大语言模型（LLM）智能体越来越依赖于'技能'"; Zhihu (zh): "通过'技能'武装智能体"; "技能" is the standard term in Chinese AI documentation |
| **Italian** | competenza (pl. competenze) | Botpress (it): "agenti LLM" with "competenze"; standard Italian AI terminology uses "competenza" for agent capabilities |
| **Arabic** | مهارة (pl. مهارات) | Skillstore (ar): "مهارة AI — سوق مهارات الذكاء الاصطناعي"; "مهارات وكيل قابلة لإعادة الاستخدام" (reusable agent skills); TrueFoundry (ar): "مركزة مهارات الوكلاء" |

**Key finding**: The term "skill" in the AI agent context is well-established in all 5 non-English locales. The translations are not ad-hoc — they appear in Google Cloud documentation, academic papers (alphaXiv translations), and commercial AI platforms. The word "skill" itself is also sometimes left untranslated in technical contexts (especially in Chinese and Arabic communities), but the native terms are widely used and understood.

### Existing Translations for /skill Subcommands

Analysis of `translations.json` shows which subcommand keywords already exist and which are missing:

| Canonical Keyword | en | es | fr | zh | it | ar |
|---|---|---|---|---|---|---|
| `list` | list | listar | lister | 列表 | elenco | عرض |
| `show` | show | mostrar | afficher/voir | 显示 | mostra | إظهار |
| `search` | search | buscar | rechercher/chercher | 搜索 | cerca/cerca | ابحث |
| `delete` | delete | eliminar/borrar | supprimer/effacer | 删除 | elimina/cancella | حذف |
| `enable` | *(missing)* | habilitar | activer_outil | 启用 | abilita | شغل |
| `disable` | *(missing)* | deshab | desactiver_outil | 禁用 | disabilita | طفي |
| `edit` | *(missing)* | editar | editer | 编辑 | modifica | عدل |
| `export` | export | exportar | exporter | 导出 | esporta | تصدير |
| `create` | **MISSING** | **MISSING** | **MISSING** | **MISSING** | **MISSING** | **MISSING** |
| `learn` | **MISSING** | **MISSING** | **MISSING** | **MISSING** | **MISSING** | **MISSING** |
| `apply` | **MISSING** | **MISSING** | **MISSING** | **MISSING** | **MISSING** | **MISSING** |
| `import` | **MISSING** | **MISSING** | **MISSING** | **MISSING** | **MISSING** | **MISSING** |
| `wizard` | **MISSING** | **MISSING** | **MISSING** | **MISSING** | **MISSING** | **MISSING** |

**Note on `enable`/`disable`**: These exist in es/fr/zh/it/ar but are missing from the English `en` locale (they were added for `/tool enable`/`/tool disable` but never added to `en` keywords since English uses the same word). The English keywords section should include `enable -> enable` and `disable -> disable` for consistency, though they are functionally no-ops.

**Note on `edit`**: Missing from `en` keywords. Exists in es/fr/zh/it/ar but not in en. Should add `edit -> edit` to en.

### New Words to Add

#### 1. New `/skill` command alias (all locales)

| Locale | Alias | Canonical |
|---|---|---|
| en | `/skill` | `/skill` |
| es | `/habilidad` | `/skill` |
| fr | `/competence` | `/skill` |
| zh | `/技能` | `/skill` |
| it | `/competenza` | `/skill` |
| ar | `/مهارة` | `/skill` |

#### 2. New keywords (all locales)

| Canonical | en | es | fr | zh | it | ar |
|---|---|---|---|---|---|---|
| `create` | create | crear | créer | 创建 | crea | إنشاء |
| `learn` | learn | aprender | apprendre | 学习 | impara | تعلم |
| `apply` | apply | aplicar | appliquer | 应用 | applica | تطبيق |
| `import` | import | importar | importer | 导入 | importa | استيراد |
| `wizard` | wizard | asistente | assistant | 向导 | procedura | معالج |
| `enable` | enable | *(exists: habilitar)* | *(exists: activer_outil)* | *(exists: 启用)* | *(exists: abilita)* | *(exists: شغل)* |
| `disable` | disable | *(exists: deshab)* | *(exists: desactiver_outil)* | *(exists: 禁用)* | *(exists: disabilita)* | *(exists: طفي)* |
| `edit` | edit | *(exists: editar)* | *(exists: editer)* | *(exists: 编辑)* | *(exists: modifica)* | *(exists: عدل)* |

**Translation rationale** (validated by web search):
- **create**: Standard cognate in es/fr/it; 创建 (chuàngjiàn) in zh; إنشاء (inshā') in ar — all standard terms in AI tool documentation
- **learn**: aprender/apprendre/impara are the standard translations for "learn" in tech contexts; 学习 (xuéxí) in zh; تعلم (ta'allum) in ar
- **apply**: aplicar/appliquer/applica are direct cognates; 应用 (yìngyòng) in zh; تطبيق (tatbīq) in ar — all used in AI/ML contexts
- **import**: importar/importer/importa are standard; 导入 (dǎorù) in zh; استيراد (istīrād) in ar
- **wizard**: "asistente"/"assistant" (es/fr) — the wizard pattern is commonly translated as "assistant" in Spanish and French software; 向导 (xiàngdǎo, "guide") in zh; procedura guidata ("guided procedure") in it; معالج (mu'ālij, "wizard/sorcerer" but standard software term for "wizard") in ar

#### 3. New UI strings (all locales)

| Key | en | es | fr | zh | it | ar |
|---|---|---|---|---|---|---|
| `skill_created` | Skill '{name}' created. | Habilidad '{name}' creada. | Compétence '{name}' créée. | 技能 '{name}' 已创建。 | Competenza '{name}' creata. | تم إنشاء المهارة '{name}'. |
| `skill_deleted` | Skill '{name}' deleted. | Habilidad '{name}' eliminada. | Compétence '{name}' supprimée. | 技能 '{name}' 已删除。 | Competenza '{name}' eliminata. | تم حذف المهارة '{name}'. |
| `skill_enabled` | Skill '{name}' enabled. | Habilidad '{name}' habilitada. | Compétence '{name}' activée. | 技能 '{name}' 已启用。 | Competenza '{name}' abilitata. | تم تفعيل المهارة '{name}'. |
| `skill_disabled` | Skill '{name}' disabled. | Habilidad '{name}' deshabilitada. | Compétence '{name}' désactivée. | 技能 '{name}' 已禁用。 | Competenza '{name}' disabilitata. | تم تعطيل المهارة '{name}'. |
| `skill_not_found` | Skill '{name}' not found. | Habilidad '{name}' no encontrada. | Compétence '{name}' introuvable. | 未找到技能 '{name}'。 | Competenza '{name}' non trovata. | المهارة '{name}' غير موجودة. |
| `skill_no_skills` | No skills found. | No se encontraron habilidades. | Aucune compétence trouvée. | 未找到技能。 | Nessuna competenza trovata. | لا توجد مهارات. |
| `skill_learned` | Skill '{name}' learned from session. | Habilidad '{name}' aprendida de la sesión. | Compétence '{name}' apprise de la session. | 从会话学习了技能 '{name}'。 | Competenza '{name}' appresa dalla sessione. | تم تعلم المهارة '{name}' من الجلسة. |
| `skill_applied` | Skill '{name}' applied to next prompt. | Habilidad '{name}' aplicada al próximo prompt. | Compétence '{name}' appliquée au prochain prompt. | 技能 '{name}' 已应用到下一个提示。 | Competenza '{name}' applicata al prossimo prompt. | تم تطبيق المهارة '{name}' على المطالبة التالية. |
| `skill_wizard_name` | Enter skill name: | Ingrese el nombre de la habilidad: | Entrez le nom de la compétence: | 输入技能名称： | Inserisci il nome della competenza: | أدخل اسم المهارة: |
| `skill_wizard_desc` | Enter description (used for trigger matching): | Ingrese descripción (usada para coincidencia de activadores): | Entrez la description (utilisée pour la correspondance des déclencheurs): | 输入描述（用于触发匹配）： | Inserisci la descrizione (usata per la corrispondenza dei trigger): | أدخل الوصف (يستخدم لمطابقة المحفزات): |
| `skill_wizard_triggers` | Enter trigger phrases (comma-separated): | Ingrese frases activadoras (separadas por comas): | Entrez les phrases déclencheurs (séparées par des virgules): | 输入触发短语（逗号分隔）： | Inserisci le frasi di attivazione (separate da virgole): | أدخل عبارات التحفيز (مفصولة بفواصل): |
| `skill_wizard_tags` | Enter tags for organization (comma-separated): | Ingrese etiquetas para organización (separadas por comas): | Entrez les étiquettes pour l'organisation (séparées par des virgules): | 输入标签用于组织（逗号分隔）： | Inserisci i tag per l'organizzazione (separati da virgole): | أدخل العلامات للتنظيم (مفصولة بفواصل): |
| `skill_wizard_content` | Enter skill content (type --- on a line to finish): | Ingrese el contenido de la habilidad (escriba --- para terminar): | Entrez le contenu de la compétence (tapez --- pour terminer): | 输入技能内容（输入 --- 结束）： | Inserisci il contenuto della competenza (digita --- per terminare): | أدخل محتوى المهارة (اكتب --- للإنهاء): |

#### 4. PatternMatcher words

The `PatternMatcher` in `ChatybotApp.__init__` (line ~95) has a hardcoded word list that blocks command verbs at the start of prompts. The word `skill` must be added to prevent the "Error command verb at beginning" message when a user types "skill" as the first word of a prompt:

```python
self.matcher = PatternMatcher(
    words=[
        # ... existing words ...
        "session", "replay", "context", "ctx", "context_limit",
        "auto_truncate", "env", "chatdsl", "docs", "doc",
        "skill",  # NEW
    ]
)
```

#### 5. Help system registration

The help system (`chaty_help.py`) should register the `/skill` command with help text. The `HelpSystem._initialize_commands()` method has a list of `CommandHelp` entries. A new entry should be added:

```python
self.register_command(CommandHelp(
    name="/skill",
    category="database",  # or a new "skills" category
    usage="/skill <list|show|create|edit|delete|enable|disable|search|learn|apply|export|import>",
    description="Manage the skills database",
    examples=[
        "/skill list",
        "/skill create",
        "/skill learn my-skill",
        "/skill enable code-review",
    ],
    aliases=["/habilidad", "/competence", "/技能", "/competenza", "/مهارة"],
))
```

### Summary of Changes Needed

| Change | File | Description |
|---|---|---|
| New `/skill` aliases | `translations.json` | Add `/skill` alias for all 6 locales |
| New keywords | `translations.json` | Add `create`, `learn`, `apply`, `import`, `wizard` keywords for all 6 locales; add `enable`, `disable`, `edit` to `en` |
| New UI strings | `translations.json` | Add 12 skill-related UI strings for all 6 locales |
| PatternMatcher word | `chatybot_app.py` | Add `"skill"` to the word list |
| Help registration | `chaty_help.py` | Register `/skill` command with help text and aliases |
| Total new translation entries | | ~5 aliases + ~30 keywords + ~72 UI strings = ~107 new entries across 6 locales |

---

## Part 9: Default Skills — What Should Ship with Chatybot

### Design Principles for Default Skills

Default skills should satisfy these criteria:

1. **Address a real pain point** — a multi-step workflow that users currently do manually or get wrong
2. **Encode institutional knowledge** — something a new user would not discover from `/help` alone
3. **Trigger naturally** — the user's prompt should contain phrases that match without contortion
4. **Not duplicate a single command** — if a workflow is one command, it does not need a skill
5. **Be grounded in existing capabilities** — use only tools, commands, and patterns that already work in chatybot

### Chatybot Capability Inventory (Relevant to Skills)

| Capability | Commands/Tools | Complexity |
|---|---|---|
| Multi-model comparison | `/model`, `/save`, `/filebank1-5`, `/multiline` | High — manual filebank juggling |
| Agentic tool loop | `/tool on`, `/tool enable`, `/tool auto`, `/tool max_turns`, `/tool loop` | High — 5-step setup |
| DB search-inject | `/setdb`, `/searchdb`, `/loadvar`, `${var}` in prompt, `/dblog` | Medium — syntax-heavy |
| Session query/extract | `/session query`, `/session get` | Medium — powerful but underused |
| Semantic reranking | `/documents`, `/rerank` | Medium — setup required |
| Structured decisions | `/decide` with choice/score/noul | Medium — complex arg syntax |
| Batch file processing | `/run ls`, `foreach`, `/file`, `/save`, `/clearfile` | Medium — foreach + lines() |
| ChatDSL scripting | `set`, `if`, `foreach`, `defproc`, `/proc`, `/script` | High — full DSL |
| Image generation | `/imagine`, `/imagesize`, `/imagequality` | Low — single command |
| Profile authoring | `/profile edit`, file format | Medium — format knowledge |
| Code extraction | `/notemode`, `/codeonly`, `/save` | Low — toggle commands |

### Recommended Default Skills (7 Skills)

---

#### Skill 1: `code-review`

**Purpose**: Review code for bugs, style issues, and security concerns using the agentic tool loop.

**Why it is a default**: The agentic tool loop is chatybot's most powerful feature but requires 5 commands to set up correctly. Users frequently forget steps or get the order wrong. This skill encodes the correct setup and adds review-specific system prompt guidance.

**Triggers**: `["review code", "code review", "review my code", "review this code", "check my code"]`

**Content**:
```markdown
# Code Review Skill

When the user asks to review code, set up the agentic tool loop for code analysis:

1. Enable tool mode and tools:
   /tool on
   /tool enable read_file grep_search find_files list_directory
   /tool auto on
   /tool max_turns 25

2. Use a focused system prompt:
   /system You are a code reviewer. Read the relevant files using tools, identify bugs, security issues, and style problems. For each issue, cite the file and line number, explain the problem, and suggest a fix. Prioritize: security vulnerabilities, logic bugs, error handling, then style.

3. Launch the tool loop:
   /tool loop 25 force

After the loop completes, summarize findings as:
- Critical: [security vulnerabilities, logic bugs]
- Warnings: [error handling gaps, edge cases]
- Style: [naming, formatting, documentation]
```

**Tags**: `["coding", "review", "quality", "agentic"]`

---

#### Skill 2: `compare-models`

**Purpose**: Run the same prompt against multiple models and have a judge model compare the results.

**Why it is a default**: The multi-model comparison pattern is the most documented chatybot workflow (cookbook recipes 04_1 through 04_3) but requires manual filebank management, session history toggling, and judge prompt authoring. Users get the filebank assignments wrong or forget to disable session history.

**Triggers**: `["compare models", "model comparison", "compare responses", "a/b test", "ab test models"]`

**Content**:
```markdown
# Model Comparison Skill

When the user asks to compare model responses:

1. Disable session history to prevent cross-model context contamination:
   /session history off

2. Run the user's prompt with the first model:
   /model ${model1}
   [user's prompt]
   /save compare_m1.txt
   /filebank1 compare_m1.txt

3. Run the same prompt with the second model:
   /model ${model2}
   [user's prompt]
   /save compare_m2.txt
   /filebank2 compare_m2.txt

4. Use a judge model to compare:
   /model ${judge_model}
   Compare {filebank1} vs {filebank2}. Score each response 0-10 on accuracy, clarity, and completeness. Pick an overall winner and explain why.

5. Re-enable session history:
   /session history on

Variables to set before running:
- model1: first model alias
- model2: second model alias
- judge_model: model alias for judging (e.g., gemini_flash)
```

**Tags**: `["models", "comparison", "evaluation", "testing"]`

---

#### Skill 3: `research-agent`

**Purpose**: Autonomous research agent that reads files, reranks for relevance, and logs findings to a database.

**Why it is a default**: This is cookbook recipe 14_1, the most complex single recipe. It combines tool loop + reranking + database logging — three subsystems that users do not naturally combine. The skill encodes the correct sequence and parameter values.

**Triggers**: `["research agent", "research this", "autonomous research", "gather information", "research topic"]`

**Content**:
```markdown
# Research Agent Skill

When the user asks for autonomous research:

1. Set up a database for logging:
   /setdb research_log

2. Configure the agentic tool loop:
   /tool on
   /tool enable all
   /tool auto on
   /tool max_turns 30
   /tool rate_limit 2

3. Set a research-focused system prompt:
   /system You are a research agent. Use file tools to read documents in the working directory, then synthesize a 5-bullet briefing on the requested topic. After synthesizing, state READY TO LOG.

4. Launch the loop:
   /tool loop 30 force

5. Log the result:
   /dblog
```

**Tags**: `["research", "agentic", "database", "automation"]`

---

#### Skill 4: `debug-error`

**Purpose**: Debug an error message or stack trace by reading relevant source files and identifying the root cause.

**Why it is a default**: Debugging is a common task where the agentic tool loop shines, but users do not know which tools to enable or how to frame the system prompt for debugging. The skill enables only the file-reading tools (not write_file or run_command) for safety.

**Triggers**: `["debug error", "debug this", "fix error", "stack trace", "what's wrong with", "why am i getting", "debug this error"]`

**Content**:
```markdown
# Debug Error Skill

When the user asks to debug an error or stack trace:

1. Enable read-only tools only (no write or execute):
   /tool on
   /tool enable read_file grep_search find_files list_directory
   /tool auto on
   /tool max_turns 20

2. Set a debugging-focused system prompt:
   /system You are a debugger. The user has provided an error message or stack trace. Use file tools to read the relevant source files, trace the error to its root cause, and explain: (1) what went wrong, (2) which file and line caused it, (3) how to fix it. Do not modify any files.

3. Launch the tool loop:
   /tool loop 20 force
```

**Tags**: `["coding", "debug", "troubleshooting", "agentic"]`

---

#### Skill 5: `batch-translate`

**Purpose**: Batch-translate files in a directory from one language to another using foreach iteration.

**Why it is a default**: Batch file processing is cookbook recipe 14_5. It combines `/run ls`, `foreach`, `lines()`, `/file`, `/save`, and `/clearfile` — a sequence that is error-prone to write from scratch. The skill provides the correct template with variable substitution.

**Triggers**: `["batch translate", "translate files", "translate all files", "batch process files", "translate directory"]`

**Content**:
```markdown
# Batch Translate Skill

When the user asks to batch-translate files:

1. List files in the source directory:
   /run ls -1 ${source_dir}
   /setvar filelist {LAST_COMPLETION}

2. Set the target model:
   /model ${target_model}

3. Iterate and translate each file:
   foreach name in lines(${filelist})
     if ${name} == "" then break
     /file ${source_dir}/${name}
     Translate to ${target_language} and keep the structure.
     /save ${output_dir}/${name}
     /clearfile
   endfor

4. Report completion:
   /echo "Batch translation complete. Files saved to ${output_dir}"

Variables to set before running:
- source_dir: directory containing files to translate
- output_dir: directory for translated files
- target_language: target language name
- target_model: model alias for translation
```

**Tags**: `["translation", "batch", "automation", "foreach"]`

---

#### Skill 6: `db-research-log`

**Purpose**: Search the database for prior research, inject it into a prompt, and log the new response back to the database.

**Why it is a default**: The search-inject-log pattern is cookbook recipe 06_2. It is the canonical TinyDB workflow but requires knowing `/searchdb`, `/loadvar`, `${var}` syntax in a multiline prompt, and `/dblog`. Users who have not read the cookbook do not discover this pattern.

**Triggers**: `["research log", "search database", "prior research", "db research", "search and log", "inject research"]`

**Content**:
```markdown
# Database Research Log Skill

When the user asks to search prior research and log new findings:

1. Activate the research database:
   /setdb ${db_name}

2. Search for relevant prior entries:
   /searchdb "${search_query}"

3. Load results into a variable:
   /loadvar history ALL

4. Compose a prompt that references prior research:
   /model ${model_alias}
   /multiline
   Given prior research: ${history}

   [user's new question]
   ;; 
   /multiline

5. Log the response:
   /dblog

Variables to set before running:
- db_name: name of the TinyDB database
- search_query: terms to search for in prior entries
- model_alias: model to use for the new response
```

**Tags**: `["database", "research", "logging", "tinydb"]`

---

#### Skill 7: `write-test`

**Purpose**: Write unit tests for a function or module by reading the source code and generating test cases.

**Why it is a default**: Test writing is a common developer task that benefits from the agentic tool loop reading the source code first. The skill enables read tools plus write_file (to create the test file) and provides a test-writing-focused system prompt.

**Triggers**: `["write test", "write tests", "generate tests", "create test", "unit test", "test cases for"]`

**Content**:
```markdown
# Write Test Skill

When the user asks to write tests:

1. Enable read and write tools:
   /tool on
   /tool enable read_file find_files grep_search write_file list_directory
   /tool auto on
   /tool max_turns 20

2. Set a test-writing system prompt:
   /system You are a test engineer. Read the source code using file tools, understand the function signatures and behavior, then write comprehensive unit tests. Cover: normal cases, edge cases, error handling, and boundary conditions. Write the tests to a file using write_file. Use the same testing framework as existing tests in the project.

3. Launch the tool loop:
   /tool loop 20 force
```

**Tags**: `["coding", "testing", "agentic", "quality"]`

---

### Summary Table

| Skill | Triggers | Tools Used | Complexity | Addresses Pain Point |
|---|---|---|---|---|
| `code-review` | "review code", "code review" | read_file, grep_search, find_files | Medium | Agentic loop setup is 5 steps |
| `compare-models` | "compare models", "a/b test" | filebanks, /save, /model | Medium | Manual filebank juggling, session history |
| `research-agent` | "research agent", "research this" | all tools, /rerank, /dblog | High | 3 subsystems combined |
| `debug-error` | "debug error", "fix error" | read_file, grep_search (read-only) | Medium | Tool selection + system prompt framing |
| `batch-translate` | "batch translate", "translate files" | /run, foreach, /file, /save | Medium | foreach + lines() syntax |
| `db-research-log` | "research log", "search database" | /searchdb, /loadvar, /dblog | Medium | TinyDB workflow syntax |
| `write-test` | "write test", "generate tests" | read_file, write_file, grep_search | Medium | Tool selection + test-focused prompt |

### What Was Deliberately Excluded

| Candidate | Why Excluded |
|---|---|
| "explain code" | Single prompt, no multi-step workflow — just send the code as context |
| "generate image" | Single command `/imagine` — no skill needed |
| "switch language" | Single command — i18n is already handled by the localization system |
| "create profile" | Profile format is documented in `/docs` and `/profile edit` provides a TUI |
| "run shell command" | Single command `/run` — no skill needed |
| "session management" | `/session` already has comprehensive subcommands |
| "rerank documents" | Two commands (`/documents`, `/rerank`) but straightforward — documented in cookbook |
| "decide" | Single command with complex args but self-contained |

### Seeding Mechanism

Default skills should be seeded into `skills.json` on first creation (when the skills DB does not exist yet). The `skillsdb.py` module should include a `_seed_default_skills()` function called from `_ensure_manager()` when the database is newly created:

```python
DEFAULT_SKILLS = [
    {
        "type": "skill",
        "name": "code-review",
        "content": "# Code Review Skill\n...",
        "metadata": {
            "description": "Review code for bugs, style, and security using the agentic tool loop",
            "triggers": ["review code", "code review", "review my code", "review this code", "check my code"],
            "tags": ["coding", "review", "quality", "agentic"],
            "enabled": True,
            "source": "default",
            "created_at": "<runtime timestamp>",
        }
    },
    # ... 6 more skills
]

def _ensure_manager() -> CorpusManager:
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

def _seed_default_skills(manager: CorpusManager) -> None:
    """Seed the skills database with default skills on first creation."""
    for skill in DEFAULT_SKILLS:
        import copy
        skill_data = copy.deepcopy(skill)
        skill_data["metadata"]["created_at"] = datetime.now().isoformat()
        manager.add_item(
            item_type=skill_data["type"],
            name=skill_data["name"],
            content=skill_data["content"],
            metadata=skill_data["metadata"],
        )
    print(f"[skills] Seeded {len(DEFAULT_SKILLS)} default skills.")
```

**Re-seeding**: If the user deletes all skills, the defaults are not re-seeded. The user can manually restore them with `/skill import <file>` if a default skills export file is provided in the `doc/` directory. Alternatively, a `/skill reset` subcommand could re-seed defaults.

**Disabling defaults**: Users can disable any default skill with `/skill disable <name>`. The skill remains in the database but is not triggered. This respects user autonomy — defaults are suggestions, not impositions.

---

## Appendix: Key Source Files Reviewed

| File | Lines | Purpose |
|---|---|---|
| `src/chatybot/tinydb1/corpus_manager.py` | 163 | CorpusManager wrapping TinyDB |
| `src/chatybot/chatydb.py` | 697 | Global DB facade (set_db, search, log, print) |
| `src/chatybot/commands/db.py` | 128 | DB commands (/setdb, /dblist, /searchdb, etc.) |
| `src/chatybot/commands/registry.py` | 155 | @command decorator, CommandRegistry, CommandResult |
| `src/chatybot/commands/context.py` | 30 | CommandContext dataclass |
| `src/chatybot/commands/session.py` | 974 | /session command with all subcommands |
| `src/chatybot/session_interface.py` | 155 | BaseSessionStore ABC |
| `src/chatybot/dispatcher.py` | 241 | Tool execution gateway |
| `src/chatybot/tools/db_tools.py` | 329 | LLM-callable DB tools (db_search, db_get, etc.) |
| `src/chatybot/config_model.py` | 618 | ChatConfig, ModelConfig, system_message |
| `src/chatybot/chatybot_app.py` | ~6000+ | Main app, command dispatch, prompt assembly (Path A: line 1306/1394, Path B: line 2252/2337) |
| `src/chatybot/chaty_help.py` | ~1150 | Help system, command documentation |
| `src/chatybot/commands/tools.py` | ~1800 | $EDITOR launch precedent (lines 546-573, 1664+) |

---

## Part 10: How Skills Enable and Disable Tools

### The Problem

The default skills proposed in Part 9 contain slash commands like `/tool on`, `/tool enable read_file grep_search`, `/tool auto on`, `/tool loop 25 force`. These are chatybot escape commands — they are processed by `handle_escape_command` in the command handler, not by the LLM.

But skills are injected into the **system prompt** as text (Part 7, `_inject_skills`). The system prompt is read by the LLM — it cannot execute slash commands. The LLM sees the text but cannot run `/tool on`.

This is a fundamental mismatch: the skill content as written in Part 9 reads like a ChatDSL script, but the injection point is the system prompt, which is LLM context, not executable code.

### How Tool Enablement Actually Works (Traced Through Code)

The tool system has three layers:

**Layer 1 — Tool mode (on/off)**:
- `app.tool_mode` (bool) — when True, tool definitions are injected into the system prompt via `generate_tool_context()`
- `/tool on` calls `generate_tool_context()`, sets `app.tool_mode = True`, stores context in `TOOL_CONTEXT` script var
- The system prompt assembly at line 1395 checks `if self.tool_mode and effective_tool_context:` and prepends the tool context

**Layer 2 — Tool enable/disable (per-tool)**:
- `app.tool_overrides` (dict[str, bool]) — per-tool override of the config default
- `/tool enable read_file` sets `app.tool_overrides["read_file"] = True`
- `generate_tool_context()` reads overrides: `is_enabled = self.tool_overrides.get(tool_name, config_enabled)` — only enabled tools appear in the context string

**Layer 3 — Auto-loop**:
- `app.tool_auto` (bool) — when True, after each completion, if tool calls are detected in the response, the agentic loop auto-launches
- `app.max_turns` (int) — max iterations for the tool loop
- At line 2203: `if self.tool_auto and self.extract_tool_calls(full_response): await self.execute_tool_loop(max_turns=self.max_turns)`

**Key insight**: All three layers are app-level state mutations. They happen via command handlers (user types `/tool on`), not via the LLM. The LLM only sees the *result* — the tool definitions in its system prompt and the ability to output tool calls.

### Three Approaches to Resolve This

#### Approach A: Skill Metadata Drives Tool Configuration (Recommended)

Skills declare their tool requirements in metadata. The `_inject_skills` hook reads these and mutates app state before the prompt is sent.

**Skill schema extension**:
```python
{
    "type": "skill",
    "name": "code-review",
    "content": "You are a code reviewer. Read the relevant files using tools, identify bugs...",
    "metadata": {
        "description": "Reviews code for bugs, style, and security",
        "triggers": ["review code", "code review", "check my code"],
        "tags": ["coding", "review"],
        "enabled": True,
        "tool_config": {
            "mode": "on",                    # "on" or "off"
            "enable_tools": ["read_file", "grep_search", "find_files", "list_directory"],
            "disable_tools": ["write_file", "run_command", "replace_file_content"],
            "auto_loop": True,
            "max_turns": 25
        }
    }
}
```

**Injection hook** (updated from Part 7):
```python
def _inject_skills(self, system_message: str, user_prompt: str) -> str:
    """Inject matching skills and configure tools."""
    from .skillsdb import get_matching_skills
    matched = get_matching_skills(user_prompt)
    if not matched:
        return system_message

    # Apply tool configuration from the first matched skill
    # (if multiple skills match, the first one's tool_config wins)
    skill = matched[0]
    tool_config = skill.get("metadata", {}).get("tool_config")
    if tool_config:
        self._apply_skill_tool_config(tool_config)

    # Inject skill content into system prompt
    skill_block = "\n\n".join(
        f"## Skill: {s['name']}\n{s['content']}" for s in matched
    )
    if system_message:
        return f"{system_message}\n\n--- Active Skills ---\n{skill_block}"
    return f"--- Active Skills ---\n{skill_block}"

def _apply_skill_tool_config(self, config: dict) -> None:
    """Apply tool configuration from a skill's metadata.

    This mutates app state (tool_mode, tool_overrides, tool_auto, max_turns).
    The changes persist for the current session — they are NOT auto-reverted
    after the skill-triggered prompt completes. Users can manually revert
    with /tool off or /tool disable.
    """
    # Enable tool mode
    if config.get("mode") == "on" and not self.tool_mode:
        context = self.generate_tool_context()
        if context:
            self.tool_mode = True
            self.buffer_manager.set_script_var('TOOL_CONTEXT', context)

    # Enable specific tools
    for tool_name in config.get("enable_tools", []):
        self.tool_overrides[tool_name] = True

    # Disable specific tools
    for tool_name in config.get("disable_tools", []):
        self.tool_overrides[tool_name] = False

    # Regenerate context with updated overrides
    if self.tool_mode:
        context = self.generate_tool_context()
        self.buffer_manager.set_script_var('TOOL_CONTEXT', context)

    # Auto-loop settings
    if config.get("auto_loop"):
        self.tool_auto = True
    if config.get("max_turns"):
        self.max_turns = config["max_turns"]
```

**What happens end-to-end**:
1. User types "review code in auth.py"
2. `chat_completion` is called
3. Before system prompt assembly, `_inject_skills` runs
4. Skill `code-review` matches trigger "review code"
5. `_apply_skill_tool_config` sets `tool_mode=True`, enables read_file/grep_search/find_files/list_directory, disables write_file/run_command, sets `tool_auto=True`, `max_turns=25`
6. `generate_tool_context()` builds the tool definitions string with only the enabled tools
7. System prompt assembly (line 1395) sees `tool_mode=True` and prepends tool context
8. Skill content ("You are a code reviewer...") is appended to system prompt
9. LLM receives: tool definitions + skill guidance + user prompt
10. LLM outputs tool calls (JSON)
11. `tool_auto` detects tool calls and launches `execute_tool_loop(max_turns=25)`

**The skill content no longer contains slash commands.** It is pure LLM guidance:
```markdown
You are a code reviewer. Read the relevant files using tools, identify
bugs, security issues, and style problems. For each issue, cite the file
and line number, explain the problem, and suggest a fix. Prioritize:
security vulnerabilities, logic bugs, error handling, then style.
```

**Persistence**: Tool config changes persist for the session. This is intentional — if the user is reviewing code, they probably want tools to stay on for follow-up questions. The user can revert with `/tool off` or `/tool disable <name>`.

**Conflict resolution**: If multiple skills match, the first matched skill's `tool_config` is applied. If a skill has no `tool_config`, tool state is unchanged — the skill is pure guidance only.

| Pros | Cons |
|---|---|
| Clean separation: metadata configures tools, content guides LLM | Tool state persists after skill prompt — user must manually revert |
| No new execution path needed — reuses existing app state mutations | Multiple matching skills with conflicting tool_config: first wins, no merge |
| Skill content is pure LLM guidance (no slash commands) | No automatic rollback (could add in future via a "session save/restore" pattern) |
| User can override any skill-applied config with manual /tool commands | |

#### Approach B: Skill Content as ChatDSL Script (Pre-Execution)

Skills contain ChatDSL that runs *before* the user's prompt is sent. The skill content is treated as a script, not as system prompt text.

**Skill schema**:
```python
{
    "type": "skill",
    "name": "code-review",
    "content": "# This is a ChatDSL setup script, not system prompt text\n/tool on\n/tool enable read_file grep_search find_files list_directory\n/tool auto on\n/tool max_turns 25\n/system You are a code reviewer. Read files, identify bugs, cite file and line.",
    "metadata": {
        "execution": "script",  # "script" or "guidance"
        "triggers": ["review code", "code review"],
    }
}
```

**Injection**: Before sending the user's prompt, `execute_command_list(skill_content)` runs the skill's ChatDSL lines. Then the user's prompt is sent normally.

**Problem**: This requires a new execution path in `chat_completion` — currently there is no "pre-prompt script execution" hook. It also mixes executable code with LLM guidance in the same field, making it hard to maintain. And if the script has errors, the user's prompt is delayed or blocked.

| Pros | Cons |
|---|---|
| Skill content is executable — can run any command | Requires new pre-prompt execution path |
| Familiar to ChatDSL users | Mixes executable code and guidance in one field |
| Can do anything ChatDSL can do | Error handling: script failures block the prompt |
| | Harder to audit — skill content is code, not just text |

#### Approach C: Hybrid — Metadata Config + Guidance Content

Skills have two fields: `setup` (metadata-driven config, applied by the hook) and `content` (LLM guidance, injected into system prompt).

This is essentially Approach A but with the tool config explicitly separated into metadata rather than embedded in the content. The content field is always pure LLM guidance.

This is what Approach A already does — the `tool_config` is in metadata, and `content` is pure guidance. The distinction is already clean.

### Recommendation

**Approach A** is the right choice. It is the simplest, reuses existing app state mutations, and keeps skill content as pure LLM guidance. The `tool_config` metadata field is optional — skills that do not need tools (like `compare-models` or `db-research-log`) simply omit it.

### Revised Default Skill Content (Part 9 Skills, Updated)

The skill content from Part 9 must be rewritten. The slash commands move to `tool_config` metadata; the content becomes pure LLM guidance.

#### code-review (revised)

```python
{
    "type": "skill",
    "name": "code-review",
    "content": "You are a code reviewer. Read the relevant files using the available tools, identify bugs, security issues, and style problems. For each issue, cite the file and line number, explain the problem, and suggest a fix. Prioritize: security vulnerabilities, logic bugs, error handling, then style. After analysis, summarize findings as Critical, Warnings, and Style categories.",
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
            "max_turns": 25
        }
    }
}
```

#### debug-error (revised)

```python
{
    "type": "skill",
    "name": "debug-error",
    "content": "You are a debugger. The user has provided an error message or stack trace. Use file tools to read the relevant source files, trace the error to its root cause, and explain: (1) what went wrong, (2) which file and line caused it, (3) how to fix it. Do not modify any files.",
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
            "max_turns": 20
        }
    }
}
```

#### write-test (revised)

```python
{
    "type": "skill",
    "name": "write-test",
    "content": "You are a test engineer. Read the source code using file tools, understand the function signatures and behavior, then write comprehensive unit tests. Cover: normal cases, edge cases, error handling, and boundary conditions. Write the tests to a file using the write_file tool. Use the same testing framework as existing tests in the project.",
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
            "max_turns": 20
        }
    }
}
```

#### research-agent (revised)

```python
{
    "type": "skill",
    "name": "research-agent",
    "content": "You are a research agent. Use file tools to read documents in the working directory, then synthesize a 5-bullet briefing on the requested topic. After synthesizing, state READY TO LOG so the user can log the result to the database.",
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
            "max_turns": 30
        }
    }
}
```

#### compare-models (revised — no tool_config needed)

```python
{
    "type": "skill",
    "name": "compare-models",
    "content": "When comparing model responses, follow this pattern: (1) Disable session history with /session history off to prevent cross-model context contamination. (2) Run the user's prompt with the first model, save the response to a file, and load it into filebank1. (3) Run the same prompt with the second model, save to a file, load into filebank2. (4) Switch to a judge model and ask it to compare {filebank1} vs {filebank2}, scoring each 0-10 on accuracy, clarity, and completeness. (5) Re-enable session history with /session history on. The user should set variables model1, model2, and judge_model before running.",
    "metadata": {
        "description": "Run the same prompt against multiple models and have a judge compare results",
        "triggers": ["compare models", "model comparison", "compare responses", "a/b test", "ab test models"],
        "tags": ["models", "comparison", "evaluation", "testing"],
        "enabled": True,
        "source": "default"
        # No tool_config — this skill is guidance only, no agentic tools needed
    }
}
```

#### batch-translate (revised — no tool_config needed)

```python
{
    "type": "skill",
    "name": "batch-translate",
    "content": "To batch-translate files: (1) List files with /run ls -1 ${source_dir} and capture the output with /setvar filelist {LAST_COMPLETION}. (2) Set the target model with /model ${target_model}. (3) Iterate with: foreach name in lines(${filelist}) — for each file, load it with /file ${source_dir}/${name}, send the translation prompt, save with /save ${output_dir}/${name}, then /clearfile. (4) Break on empty names. The user should set source_dir, output_dir, target_language, and target_model variables.",
    "metadata": {
        "description": "Batch-translate files in a directory using foreach iteration",
        "triggers": ["batch translate", "translate files", "translate all files", "batch process files", "translate directory"],
        "tags": ["translation", "batch", "automation", "foreach"],
        "enabled": True,
        "source": "default"
        # No tool_config — this skill is guidance for ChatDSL scripting, not agentic tools
    }
}
```

#### db-research-log (revised — no tool_config needed)

```python
{
    "type": "skill",
    "name": "db-research-log",
    "content": "To search prior research and log new findings: (1) Activate the research database with /setdb ${db_name}. (2) Search for relevant prior entries with /searchdb \"${search_query}\". (3) Load results into a variable with /loadvar history ALL. (4) Compose a multiline prompt that references ${history} and asks the new question. (5) Log the response with /dblog. The user should set db_name, search_query, and model_alias variables.",
    "metadata": {
        "description": "Search the database for prior research, inject into prompt, log new response",
        "triggers": ["research log", "search database", "prior research", "db research", "search and log", "inject research"],
        "tags": ["database", "research", "logging", "tinydb"],
        "enabled": True,
        "source": "default"
        # No tool_config — this skill is guidance for DB commands, not agentic tools
    }
}
```

### Summary: Which Skills Use tool_config

| Skill | tool_config? | Why |
|---|---|---|
| `code-review` | Yes | Needs agentic tool loop with read-only tools |
| `debug-error` | Yes | Needs agentic tool loop with read-only tools |
| `write-test` | Yes | Needs agentic tool loop with read + write tools |
| `research-agent` | Yes | Needs agentic tool loop with all file tools |
| `compare-models` | No | Guidance for manual ChatDSL workflow (filebanks, /save, /model) |
| `batch-translate` | No | Guidance for ChatDSL foreach workflow |
| `db-research-log` | No | Guidance for DB command workflow (/searchdb, /loadvar, /dblog) |

### What the User Sees

When a skill with `tool_config` triggers:

```
> review code in auth.py
[skill] Matched skill 'code-review'. Configuring tools...
[skill] Tool mode enabled. Tools: read_file, grep_search, find_files, list_directory
[skill] Auto-loop enabled (max_turns=25)
[skill] Injecting skill guidance into system prompt.
Tool mode enabled - tool definitions loaded
   18 lines of tool context available
[assistant begins agentic tool loop...]
```

When a skill without `tool_config` triggers:

```
> compare models mistral_1 and gemma_3
[skill] Matched skill 'compare-models'. Injecting guidance into system prompt.
[assistant provides step-by-step instructions based on skill content...]
```

### Edge Cases

1. **User already has tools configured**: If `tool_mode` is already on and the skill's `tool_config` enables different tools, the skill's enable/disable lists are applied on top of existing overrides. Tools already enabled stay enabled unless explicitly in `disable_tools`.

2. **User has tool_auto off**: The skill's `tool_config.auto_loop = True` overrides this. The user can turn it back off with `/tool auto off` after the skill triggers.

3. **No tools match**: If `enable_tools` lists a tool name that does not exist in `tools_config.toml`, it is silently ignored (stored in `tool_overrides` but has no effect since `generate_tool_context` only iterates configured tools).

4. **Multiple skills match**: First matched skill's `tool_config` wins. Subsequent skills' `tool_config` is ignored. All matched skills' content is injected into the system prompt. This prevents conflicting tool configurations.

5. **Skill disabled by user**: `/skill disable code-review` sets `metadata.enabled = False`. The skill is not loaded into the cache, so it never matches triggers and never configures tools.

### User Confirmation Before Tool Changes

**Problem**: `_apply_skill_tool_config` silently mutates app state. The user has no idea that tool mode was turned on, which tools were enabled or disabled, or that auto-loop was activated. This is surprising and potentially dangerous (e.g., a skill enabling `run_command` without the user knowing).

**Solution**: Before applying `tool_config`, prompt the user with a summary of what will change and ask for confirmation. Use `input()` directly — the same pattern used by `/session delete --all` (session.py:578) and `/tool retry` parameter editing (tools.py:1728).

**Implementation** (updated `_apply_skill_tool_config`):

```python
def _apply_skill_tool_config(self, config: dict, skill_name: str) -> bool:
    """Apply tool configuration from a skill's metadata.

    Prompts the user for confirmation before changing tool state.
    Returns True if applied, False if user declined.

    Changes persist for the session. The user can revert manually
    with /tool off, /tool disable, /tool auto off.
    A snapshot of the previous state is saved for /skill restore.
    """
    # Build a human-readable summary of what will change
    changes = []
    if config.get("mode") == "on" and not self.tool_mode:
        changes.append("Enable tool mode (ON)")
    if config.get("enable_tools"):
        changes.append(f"Enable tools: {', '.join(config['enable_tools'])}")
    if config.get("disable_tools"):
        changes.append(f"Disable tools: {', '.join(config['disable_tools'])}")
    if config.get("auto_loop") and not self.tool_auto:
        changes.append(f"Enable auto-loop (max_turns={config.get('max_turns', self.max_turns)})")
    if config.get("max_turns") and config["max_turns"] != self.max_turns:
        changes.append(f"Set max_turns to {config['max_turns']}")

    if not changes:
        # Nothing to change — tool state already matches
        return True

    # Prompt the user
    print(f"\n[skill] '{skill_name}' wants to reconfigure tools:")
    for change in changes:
        print(f"  - {change}")
    print("  These changes persist for this session.")
    print("  You can revert with /tool off, /tool disable, /tool auto off.")

    try:
        confirm = input("\nApply these tool changes? (Y/n): ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print("\n[skill] Tool changes skipped (non-interactive or interrupted).")
        return False

    if confirm in ("n", "no"):
        print("[skill] Tool changes declined. Skill guidance will be injected without tool configuration.")
        return False

    # Save snapshot for /skill restore
    self._save_tool_state_snapshot()

    # Apply the changes
    if config.get("mode") == "on" and not self.tool_mode:
        context = self.generate_tool_context()
        if context:
            self.tool_mode = True
            self.buffer_manager.set_script_var('TOOL_CONTEXT', context)

    for tool_name in config.get("enable_tools", []):
        self.tool_overrides[tool_name] = True
    for tool_name in config.get("disable_tools", []):
        self.tool_overrides[tool_name] = False

    if self.tool_mode:
        context = self.generate_tool_context()
        self.buffer_manager.set_script_var('TOOL_CONTEXT', context)

    if config.get("auto_loop"):
        self.tool_auto = True
    if config.get("max_turns"):
        self.max_turns = config["max_turns"]

    print(f"[skill] Tool configuration applied.")
    return True
```

**What the user sees**:

```
> review code in auth.py

[skill] 'code-review' wants to reconfigure tools:
  - Enable tool mode (ON)
  - Enable tools: read_file, grep_search, find_files, list_directory
  - Disable tools: write_file, run_command, replace_file_content
  - Enable auto-loop (max_turns=25)
  These changes persist for this session.
  You can revert with /tool off, /tool disable, /tool auto off.

Apply these tool changes? (Y/n): y
[skill] Tool configuration applied.
Tool mode enabled - tool definitions loaded
   18 lines of tool context available
[assistant begins agentic tool loop...]
```

If the user declines:

```
Apply these tool changes? (Y/n): n
[skill] Tool changes declined. Skill guidance will be injected without tool configuration.
[assistant responds with skill guidance but no tools available...]
```

**Non-interactive context**: When stdin is not a TTY (script execution, pipe, CI), `input()` raises `EOFError`. The handler catches this and skips tool configuration — the skill guidance is still injected, but tools are not configured. This matches the existing pattern in `/ask` (interact.py:34) which is "silently skipped when stdin is not a TTY."

### Persistence and Restore

**Default behavior**: Tool changes persist for the session. Once a skill configures tools, they stay configured until the user manually changes them. This is intentional — if the user is reviewing code, they probably want tools to stay on for follow-up questions.

**Snapshot for restore**: Before applying tool changes, `_save_tool_state_snapshot()` saves the previous state:

```python
def _save_tool_state_snapshot(self) -> None:
    """Save current tool state for /skill restore."""
    self._tool_state_snapshot = {
        "tool_mode": self.tool_mode,
        "tool_overrides": dict(self.tool_overrides),
        "tool_auto": self.tool_auto,
        "max_turns": self.max_turns,
    }

def _restore_tool_state_snapshot(self) -> bool:
    """Restore tool state from snapshot. Returns True if restored."""
    snapshot = getattr(self, "_tool_state_snapshot", None)
    if snapshot is None:
        return False
    self.tool_mode = snapshot["tool_mode"]
    self.tool_overrides = snapshot["tool_overrides"]
    self.tool_auto = snapshot["tool_auto"]
    self.max_turns = snapshot["max_turns"]
    # Regenerate context if tools are on
    if self.tool_mode:
        context = self.generate_tool_context()
        self.buffer_manager.set_script_var('TOOL_CONTEXT', context)
    else:
        self.buffer_manager.set_script_var('TOOL_CONTEXT', '')
    self._tool_state_snapshot = None  # one-shot
    return True
```

**`/skill restore` subcommand**: Reverts to the tool state that existed before the last skill-triggered tool change:

```
/skill restore    — restore previous tool configuration
```

**One-shot snapshot**: The snapshot is overwritten each time a new skill applies tool config. Only one level of undo is supported — `/skill restore` restores to the state before the most recent skill-triggered change, not to some original baseline. If the user triggers two skills in sequence, the second overwrites the first's snapshot.

**No automatic restore**: The tool state is NOT automatically restored after the skill-triggered prompt completes. The user must explicitly run `/skill restore` if they want to revert. This avoids surprising the user by silently changing their tool configuration back while they are in the middle of a follow-up question that still needs tools.

### What Is Actually Stored vs. What Is Constructed at Runtime

A skill record in TinyDB has four fields persisted by `CorpusManager.add_item()`:

```python
# corpus_manager.py:48 — what gets stored
item_data = {
    'type': 'skill',           # distinguishes from other item types
    'name': 'code-review',      # identity for /skill show, /skill delete
    'content': 'You are a code reviewer. Read the relevant files...',  # LLM guidance
    'metadata': {               # everything that makes the skill function
        'description': 'Reviews code for bugs, style, and security...',
        'triggers': ['review code', 'code review', 'check my code'],
        'tags': ['coding', 'review', 'quality', 'agentic'],
        'enabled': True,
        'source': 'default',
        'created_at': '2026-09-23T20:15:00',
        'tool_config': {
            'mode': 'on',
            'enable_tools': ['read_file', 'grep_search', 'find_files', 'list_directory'],
            'disable_tools': ['write_file', 'run_command', 'replace_file_content'],
            'auto_loop': True,
            'max_turns': 25
        }
    }
}
```

| Field | Stored in DB | Purpose | Who reads it |
|---|---|---|---|
| `type` | `"skill"` | Distinguishes from other item types (e.g. `"chat"`) | `get_items_by_type("skill")` |
| `name` | `"code-review"` | Identity for user commands | `/skill show`, `/skill delete`, `/skill enable` |
| `content` | The LLM guidance text | Injected into system prompt | The LLM (via `_inject_skills`) |
| `metadata.triggers` | `["review code", ...]` | Substring-matched against user prompt | `get_matching_skills()` |
| `metadata.tool_config` | `{mode, enable_tools, ...}` | Configures tool state | `_apply_skill_tool_config()` |
| `metadata.enabled` | `true` | On/off gate | `_get_enabled_skills()` cache |
| `metadata.tags` | `["coding", ...]` | Browsing and search | `/skill search`, `/skill list` |
| `metadata.source` | `"default"` or `"session:abc123"` | Provenance | Audit trail |
| `metadata.created_at` | ISO timestamp | Creation time | Sorting, display |

The `## Skill: code-review\n` header that appears in the system prompt is NOT stored. It is constructed at injection time:

```python
# _inject_skills — header is built here, not stored
skill_block = "\n\n".join(
    f"## Skill: {s['name']}\n{s['content']}" for s in matched
)
```

The stored content is just the guidance text. The header is added when building the system prompt.

### Two Audiences: Content vs. tool_config

The skill record serves two independent audiences:

- **The LLM** reads `content` (the guidance text). It does not see `tool_config`. It sees the resulting tool definitions in its system prompt (built by `generate_tool_context()`), but it never sees the `tool_config` metadata that caused those tools to be enabled.
- **The app** reads `metadata.tool_config` (the tool setup). It does not pass this to the LLM. It mutates `app.tool_mode`, `app.tool_overrides`, `app.tool_auto`, `app.max_turns` before the prompt is sent.

There is no inference from one to the other. The skill author explicitly declares both: the guidance text for the LLM, and the tool configuration for the app. The text "Read the relevant files using tools" does not cause tools to be enabled — the `tool_config.enable_tools` list does.

### End-to-End Flow for a Skill with tool_config

```
User types: "review code in auth.py"
        │
        ▼
get_matching_skills("review code in auth.py")
        │
        │  substring match: "review code" found in "review code in auth.py" → match
        │
        ▼
   ┌──────────────────────────────────────────┐
   │  matched skill record                    │
   │                                          │
   │  content: "You are a code reviewer..."   │  ──► injected into system prompt
   │                                          │
   │  metadata.tool_config:                   │  ──► _apply_skill_tool_config()
   │    enable: [read_file, grep_search,       │      mutates app.tool_overrides
   │              find_files, list_directory] │      mutates app.tool_mode = True
   │    disable: [write_file, run_command,     │      mutates app.tool_auto = True
   │              replace_file_content]        │      mutates app.max_turns = 25
   │    auto_loop: true                        │
   │    max_turns: 25                          │
   └──────────────────────────────────────────┘
        │                           │
        ▼                           ▼
   system prompt gets            tool definitions built
   the guidance text:            by generate_tool_context()
   "You are a code               with only enabled tools:
   reviewer..."                  read_file, grep_search,
                                 find_files, list_directory
        │                           │
        └───────────┬──────────────┘
                    ▼
        LLM receives: tool definitions + guidance + user prompt
                    │
                    ▼
        LLM outputs tool call:
        {"tool": "read_file", "arguments": {"path": "auth.py"}}
                    │
                    ▼
        tool_auto detects tool call
        launches execute_tool_loop(max_turns=25)
```

### tool_config Is Optional — Three Scenarios

A skill creator does not have to specify tools. The `tool_config` field is optional, giving the creator full control over tool behavior:

#### Scenario 1: Skill with tool_config (tools configured)

The skill configures tools and provides LLM guidance. Used for agentic workflows.

```json
{
    "name": "code-review",
    "content": "You are a code reviewer. Read files, identify bugs, cite file and line, suggest fixes. Prioritize: security vulnerabilities, logic bugs, error handling, then style.",
    "metadata": {
        "triggers": ["review code", "code review", "check my code"],
        "tool_config": {
            "mode": "on",
            "enable_tools": ["read_file", "grep_search", "find_files", "list_directory"],
            "disable_tools": ["write_file", "run_command", "replace_file_content"],
            "auto_loop": true,
            "max_turns": 25
        }
    }
}
```

User types "review code in auth.py":
1. Skill matches trigger "review code"
2. User prompted: "Apply these tool changes? (Y/n)"
3. Tools enabled/disabled, auto-loop turned on
4. Guidance injected into system prompt
5. LLM receives tool definitions + guidance + user prompt
6. LLM outputs tool calls, agentic loop runs

#### Scenario 2: Skill without tool_config (pure guidance, no tool changes)

The skill is guidance only. Tool state is untouched. Used for ChatDSL workflow patterns and advisory skills.

```json
{
    "name": "compare-models",
    "content": "When comparing models: (1) Disable session history with /session history off. (2) Run the prompt with the first model, save to file, load into filebank1. (3) Run with the second model, save to file, load into filebank2. (4) Switch to a judge model and compare {filebank1} vs {filebank2}. (5) Re-enable session history.",
    "metadata": {
        "triggers": ["compare models", "model comparison", "a/b test"],
        "tool_config": null
    }
}
```

User types "compare models mistral and gemma":
1. Skill matches trigger "compare models"
2. No tool_config → tool state unchanged (tools stay on or off as they were)
3. Guidance injected into system prompt
4. LLM provides step-by-step instructions based on skill content

#### Scenario 3: Skill with tool_config mode "off" (explicitly disable tools)

The skill turns tools off. Used for creative or conversational tasks where tools would be a distraction.

```json
{
    "name": "creative-writing",
    "content": "You are a creative writing assistant. Focus on narrative, voice, imagery, and emotional resonance. Do not use tools.",
    "metadata": {
        "triggers": ["write a story", "creative writing", "write a poem"],
        "tool_config": {
            "mode": "off"
        }
    }
}
```

User types "write a story about a lighthouse":
1. Skill matches trigger "write a story"
2. User prompted: "Disable tool mode? (Y/n)"
3. `tool_mode` set to False
4. Guidance injected into system prompt
5. LLM writes the story without tool access

#### How the code handles all three

```python
# _inject_skills — the check is simple
tool_config = skill.get("metadata", {}).get("tool_config")
if tool_config:
    # Scenarios 1 and 3: tool_config exists, apply it
    self._apply_skill_tool_config(tool_config, skill["name"])
# else: Scenario 2 — no tool_config field, skip entirely
#       tool state is untouched
```

### Wizard Step for tool_config (Optional)

The `/skill create` wizard asks about tool configuration as an optional step:

```
Step 5: Tool configuration (optional)
  Press Enter to skip (no tool changes — pure guidance skill).
  Or enter configuration:
    mode=on|off  enable=tool1,tool2  disable=tool3,tool4  auto=y|n  max=25

  Examples:
    mode=on enable=read_file,grep_search auto=y max=25
    mode=off
    (press Enter for no tool_config)

  > 
```

If the user presses Enter, `tool_config` is not set in metadata. The skill is guidance-only (Scenario 2).

If the user enters a configuration, it is parsed into the `tool_config` dict and stored in metadata. The skill will configure tools when triggered (Scenarios 1 or 3).

### Summary: tool_config Decision Matrix

| Skill has tool_config? | tool_config.mode | What happens to tools | Use case |
|---|---|---|---|
| No (null/absent) | N/A | Unchanged — tools stay as they are | Guidance-only skills (compare-models, batch-translate, db-research-log) |
| Yes | `"on"` | Tools enabled, specific tools enabled/disabled, auto-loop configured | Agentic skills (code-review, debug-error, write-test, research-agent) |
| Yes | `"off"` | Tools turned off | Creative/conversational skills where tools are a distraction |

### Which Default Skills Use tool_config

| Skill | tool_config | mode | Why |
|---|---|---|---|
| `code-review` | Yes | on | Needs agentic tool loop with read-only tools |
| `debug-error` | Yes | on | Needs agentic tool loop with read-only tools |
| `write-test` | Yes | on | Needs agentic tool loop with read + write tools |
| `research-agent` | Yes | on | Needs agentic tool loop with all file tools |
| `compare-models` | No (null) | N/A | Guidance for manual ChatDSL workflow (filebanks, /save, /model) |
| `batch-translate` | No (null) | N/A | Guidance for ChatDSL foreach workflow |
| `db-research-log` | No (null) | N/A | Guidance for DB command workflow (/searchdb, /loadvar, /dblog) |
