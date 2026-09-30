# Cookbook Skills Proposal — Dynamic Skill Loading & Delegation Documentation

## Date: 2026-09-30

---

## 1. Background

The skills system has evolved across several recent commits:

| Commit | Summary |
|--------|---------|
| `9af8ceb` | Skills database system with TinyDB, `/skill` command (13 subcommands), trigger matching, default skill seeding, 26 tests |
| `049c984` | `/skill on` and `/skill off` session-level auto-trigger toggle |
| `aa63e15` | Trigger specificity ranking via `top_k` parameter |
| `049c984` | Word-boundary regex trigger matching (prevents false positives) |
| `ebadbfa` | Skill tracing (`/skill debug`), sticky skill lock (`/skill exit`), trigger validation (min 3 chars, 2 words) |
| `d80e360` | Dynamic context injection (`!`cmd``) and skills analysis docs |
| `c506db3` | **`search_skills` and `call_skill` tools** for agentic skill delegation — the focus of this proposal |
| `f06d820` | Clear `_turn_skills_loaded` at tool loop end and on KeyboardInterrupt |

Commit `c506db3` added two in-process tools that let the LLM discover and load skills on-demand during the autonomous tool loop. These tools are fully implemented, tested (14 tests in `test/test_skill_tools.py`), registered in `tools_config.toml`, and documented in the `/help` system and `src/chatybot/doc/README.md` changelog. However, they are **not documented** in the cookbook, the skill guide, or the main ChatDSL guide — the three documents users consult most.

This proposal specifies the documentation updates needed to close that gap.

---

## 2. How the Tools Actually Work

Understanding the implementation is essential before writing docs. The following is verified against the source code.

### 2.1 `search_skills` — Discovery Without Context Pollution

**Source:** `src/chatybot/tools/skill_utils.py:13`

```python
def search_skills(query: str = "", limit: int = 10, app: Any = None) -> dict[str, Any]:
```

- Searches across skill **name**, **description**, and **tags** (not content).
- Returns compact metadata only: `{"name", "description", "tags"}` per match.
- Instruction `content` is excluded from both the search corpus and the result set.
- Empty query or `"*"` returns all enabled skills up to `limit`.
- This is a **deliberate reimplementation** of `skillsdb.search_skills()` — the database version searches `content` too, which would load instruction text into the model's context during discovery. The tool version avoids this. (Documented in `skill_tool.md:291`.)

**Return shape:**
```json
{
  "status": "success",
  "count": 3,
  "total_matched": 3,
  "skills": [
    {"name": "code-review", "description": "...", "tags": ["code", "review"]},
    ...
  ]
}
```

### 2.2 `call_skill` — On-Demand Loading With Delegation Safety

**Source:** `src/chatybot/tools/skill_utils.py:72`

```python
def call_skill(name: str, app: Any = None) -> dict[str, Any]:
```

- Looks up a skill by name. Case-insensitive with hyphen/underscore normalization (`domain_modeling` -> `domain-modeling`).
- Returns the skill's full instruction `content` for the model to follow.
- If the skill has a `tool_config`, it is applied **silently** (no user prompt) — prompting mid-loop is disruptive. A snapshot is saved for `/skill restore`.
- Returns a `tool_state` summary (`changed`, `changes`, `message`) so the model knows what tools changed.
- Returns `depth` (current delegation count) so the model can self-monitor.

**Recursion protection** (`skill_utils.py:96-127`):
- `_turn_skills_loaded` list tracks every skill loaded across the entire tool loop (not per-call), so cycle detection works across turns: Turn 1 loads "A", Turn 2 loads "B", Turn 3 tries "A" again -> cycle detected.
- `MAX_SKILLS_PER_TURN = 5` — hard limit on delegations per tool loop.
- Circular delegation returns an error with the full chain: `"Circular skill delegation detected: A -> B -> A"`.
- Depth limit returns an error with the chain and limit: `"Maximum skill delegations per tool loop (5) reached. Chain: A -> B -> C -> D -> E"`.
- `_turn_skills_loaded` is cleared at tool loop end and on `KeyboardInterrupt` (commit `f06d820`).

**Return shape (success):**
```json
{
  "status": "success",
  "skill": {
    "name": "code-review",
    "description": "Review code for quality and bugs",
    "content": "You are a code reviewer. Analyze the following code..."
  },
  "tool_state": {
    "changed": true,
    "changes": ["enabled: read_file, grep_search"],
    "message": "Tool configuration updated for skill 'code-review'. Use /skill restore to revert."
  },
  "depth": 1
}
```

### 2.3 Critical Distinction: Tool Calls vs. ChatDSL Commands

`search_skills` and `call_skill` are **LLM tool calls** invoked by the model during the autonomous tool loop. They are **not** ChatDSL script commands. A user does not type `search_skills query="grilling"` in a `.chatdsl` file. Instead:

1. The user enables the tools: `/tool enable search_skills,call_skill`
2. The user starts the tool loop: `/tool auto on` or `/tool loop 20 force`
3. The **model** decides to call `search_skills` and `call_skill` as tool calls (JSON), not as script lines.

This distinction must be clear in all documentation. Showing these as DSL script syntax would mislead users.

### 2.4 Existing Documentation Baseline

Before proposing new docs, note what already exists:

| Location | Coverage |
|----------|----------|
| `src/chatybot/doc/README.md:716-717` | Tool reference table entries for both tools |
| `src/chatybot/doc/README.md:1203-1206` | Changelog entry with implementation details |
| `src/chatybot/chaty_help.py:899-947` | `/skill` and `/tool` help text mentioning both tools |
| `skill_tool.md` | Full implementation specification (735 lines) — developer-facing, not user-facing |
| `skill_concerns.md` | Architecture and scalability analysis — developer-facing |
| `prompt_injection.md` | Dynamic context injection spec — developer-facing |

**Not documented anywhere user-facing:**
- The cookbook (`chatdsl_cookbook.md`) — no skill chapter
- The skill guide (`chatdsl_skill.md`) — no mention of `/skill` command, skills database, or dynamic loading
- The main guide (`chatdsl_guide_v1.md`) — only a passing reference to `chatdsl_skill.md`
- All 5 translated guides — no skill content

---

## 3. Pre-Work: Resolve Duplicated Doc Trees

The repository has two parallel doc directories:

```
doc/                          # Root-level docs
src/chatybot/doc/              # Package-level docs (shipped with install)
```

The cookbook is currently identical between both trees. However, `chatdsl_skill.md` has already diverged (7-line diff). Any new documentation must be written in both trees or the duplication resolved first.

**Recommendation:** Designate `src/chatybot/doc/` as canonical (it ships with the package). Replace `doc/` with a symlink to `src/chatybot/doc/`, or remove `doc/` entirely and update any references. This prevents future drift and halves the maintenance burden for all documentation, not just this proposal.

**If the duplication cannot be resolved now:** All file paths in this proposal should be applied to both `doc/` and `src/chatybot/doc/`. The cookbook recipe files in `doc/cookbook/` and `src/chatybot/doc/cookbook/` must also be kept in sync.

---

## 4. Proposed Documentation Updates

### 4.1 New Cookbook Chapter: Chapter 15 — Dynamic Skill Loading & Delegation

Add to `chatdsl_cookbook.md` after Chapter 14, before Appendix A. Follow the existing recipe format: Goal, Commands, Script file, Run command, DSL code block, Walkthrough, Variations.

Each recipe includes a corresponding `.chatdsl` file in `cookbook/`, matching the established pattern (e.g. `08_1_tool_enable.chatdsl`).

---

#### 15.1 Discovering skills with `search_skills`

- **Goal:** Let the model discover available skills by keyword during an autonomous tool loop, without loading full instruction content into context.
- **Commands:** `/tool on`, `/tool enable search_skills,call_skill`, `/tool auto on`, `/tool loop`.
- **Script:** `cookbook/15_1_skill_discovery.chatdsl`
- **Run:** `/script doc/cookbook/15_1_skill_discovery.chatdsl`

```dsl
/model devstral_1
/tool on
/tool enable search_skills,call_skill
/tool auto on
/tool max_turns 20

chat --> I want to review some code. Find a relevant skill and use it to review the files in src/.

/tool loop 20 force
```

**Walkthrough**
1. `/tool enable search_skills,call_skill` activates both skill tools. They are in-process tools (no subprocess overhead), dispatched directly in `dispatch_tool()`.
2. The model calls `search_skills` as a tool call (JSON), e.g. `{"tool": "search_skills", "arguments": {"query": "code review"}}`.
3. `search_skills` returns compact metadata only — name, description, tags — for each match. No instruction content. Five results cost roughly 150 tokens instead of 3,000.
4. The model reads the results and decides which skill to load next.

**What the model sees (example tool result):**
```json
{
  "status": "success",
  "count": 1,
  "total_matched": 1,
  "skills": [
    {"name": "code-review", "description": "Review code for quality, bugs, and style", "tags": ["code", "review", "quality"]}
  ]
}
```

**Variations:**
- `search_skills` with empty query returns all enabled skills: `{"query": ""}` or `{"query": "*"}`.
- Adjust `limit` to control result count: `{"query": "test", "limit": 3}`.

---

#### 15.2 Loading skill instructions with `call_skill`

- **Goal:** Load a skill's full instructions by name so the model can follow them during the tool loop.
- **Commands:** `/tool on`, `/tool enable search_skills,call_skill`, `/tool auto on`, `/tool loop`.
- **Script:** `cookbook/15_2_skill_loading.chatdsl`
- **Run:** `/script doc/cookbook/15_2_skill_loading.chatdsl`

```dsl
/model devstral_1
/tool on
/tool enable search_skills,call_skill
/tool auto on
/tool max_turns 20

chat --> Load the "code-review" skill and use it to review src/auth.py.

/tool loop 20 force
```

**Walkthrough**
1. The model calls `call_skill` as a tool call: `{"tool": "call_skill", "arguments": {"name": "code-review"}}`.
2. `call_skill` looks up the skill by name. Name matching is case-insensitive and normalizes hyphens/underscores: `code_review`, `Code-Review`, and `code-review` all resolve to the same skill.
3. The skill's full instruction `content` is returned to the model. The model follows those instructions for the remainder of the loop.
4. If the skill has a `tool_config`, it is applied silently (no user prompt). The result includes a `tool_state` summary so the model knows what tools changed.

**What the model sees (example tool result):**
```json
{
  "status": "success",
  "skill": {
    "name": "code-review",
    "description": "Review code for quality, bugs, and style",
    "content": "You are a code reviewer. Analyze the following code for..."
  },
  "tool_state": {
    "changed": true,
    "changes": ["enabled: read_file, grep_search"],
    "message": "Tool configuration updated for skill 'code-review'. Use /skill restore to revert."
  },
  "depth": 1
}
```

**Variations:**
- If the skill has no `tool_config`, the `tool_state` field is omitted from the result.
- The `depth` field shows how many skills have been loaded in this tool loop so far.

---

#### 15.3 Skill delegation chains

- **Goal:** Chain multiple skills in a single tool loop, where one skill's instructions tell the model to load another skill.
- **Commands:** `/tool on`, `/tool enable search_skills,call_skill`, `/tool auto on`, `/tool loop`.
- **Script:** `cookbook/15_3_skill_delegation.chatdsl`
- **Run:** `/script doc/cookbook/15_3_skill_delegation.chatdsl`

```dsl
/model devstral_1
/tool on
/tool enable search_skills,call_skill
/tool auto on
/tool max_turns 30

chat --> Research the codebase architecture. Use skills to guide your analysis.

/tool loop 30 force
```

**Walkthrough**
1. The model calls `call_skill("domain-modeling")`. The domain-modeling skill's instructions might say: "Call the Skill tool for 'code-review' to review the architecture you identified."
2. The model then calls `call_skill("code-review")` in a subsequent turn. The `_turn_skills_loaded` list now contains `["domain-modeling", "code-review"]`.
3. The model follows both skills' instructions, combining their guidance.
4. `depth` in each result increments: 1, then 2.

**What the model sees (second call result):**
```json
{
  "status": "success",
  "skill": {
    "name": "code-review",
    "description": "Review code for quality, bugs, and style",
    "content": "..."
  },
  "depth": 2
}
```

**Variations:**
- Skills can delegate to skills that delegate further. The chain continues until the depth limit or the model stops calling `call_skill`.

---

#### 15.4 Skills with tool configuration

- **Goal:** Load a skill that modifies the available tool set mid-loop, and understand what changed.
- **Commands:** `/tool on`, `/tool enable search_skills,call_skill`, `/tool auto on`, `/tool loop`, `/skill restore`.
- **Script:** `cookbook/15_4_skill_tool_config.chatdsl`
- **Run:** `/script doc/cookbook/15_4_skill_tool_config.chatdsl`

```dsl
/model devstral_1
/tool on
/tool enable search_skills,call_skill
/tool auto on
/tool max_turns 25

chat --> I need to debug an error in src/. Find and load a debugging skill.

/tool loop 25 force

# After the loop, restore original tool configuration
/skill restore
```

**Walkthrough**
1. The model calls `call_skill("debug-error")`. This skill has a `tool_config` that enables `read_file` and `grep_search`.
2. `call_skill` applies the `tool_config` **silently** — no user prompt. This is intentional: prompting mid-loop is disruptive since the model is in a multi-turn sequence.
3. A snapshot of the previous tool state is saved (only the first time — subsequent skills don't overwrite the original snapshot).
4. The result includes `tool_state` with `changed: true` and a list of changes, so the model knows what tools are now available.
5. After the loop, `/skill restore` rolls back to the original tool configuration saved before the first skill applied its changes.

**Why silent application?** The pre-turn `_apply_skill_tool_config()` path (triggered by `/skill apply`) prompts the user for confirmation. But mid-loop, the model is in a multi-turn autonomous sequence — interrupting to ask for approval at an arbitrary point is disruptive. The snapshot ensures the user can always revert with `/skill restore`.

**Variations:**
- A skill's `tool_config` can also set `mode: on/off`, `auto_loop`, and `max_turns`.
- If multiple skills with `tool_config` are loaded in the same loop, only the first saves a snapshot. `/skill restore` always rolls back to the user's original state, not an intermediate state.

---

#### 15.5 Recursion limits and cycle detection

- **Goal:** Understand the safety mechanisms that prevent unbounded skill chaining.
- **Commands:** (no user commands — these are automatic protections)
- **Script:** `cookbook/15_5_recursion_limits.chatdsl`
- **Run:** `/script doc/cookbook/15_5_recursion_limits.chatdsl`

```dsl
/model devstral_1
/tool on
/tool enable search_skills,call_skill
/tool auto on
/tool max_turns 30

# Create two skills that delegate to each other (for demonstration)
/skill create
# ... create skill "loop-a" with content: "Call the Skill tool for 'loop-b'"
# ... create skill "loop-b" with content: "Call the Skill tool for 'loop-a'"

chat --> Load the "loop-a" skill and follow its instructions.

/tool loop 30 force
```

**Walkthrough**
1. The model calls `call_skill("loop-a")`. Depth becomes 1.
2. loop-a's instructions say to load loop-b. The model calls `call_skill("loop-b")`. Depth becomes 2.
3. loop-b's instructions say to load loop-a. The model calls `call_skill("loop-a")` again.
4. Cycle detection triggers. `call_skill` returns an error:

```json
{
  "status": "error",
  "reason": "Circular skill delegation detected: loop-a -> loop-b -> loop-a. Skill 'loop-a' was already loaded in this tool loop. Remove the circular reference in the skill instructions."
}
```

5. The model sees the error and stops trying to load the duplicate skill.

**Two protections, independent:**

| Protection | Trigger | Limit | Error message includes |
|------------|---------|-------|-----------------------|
| Cycle detection | Same skill loaded twice in one tool loop | N/A (immediate) | Full chain: `A -> B -> A` |
| Depth limit | Total unique skills loaded in one tool loop | 5 (`MAX_SKILLS_PER_TURN`) | Chain so far + limit number |

**Tracking scope:** `_turn_skills_loaded` persists across all turns of a single `run_tool_loop()` invocation. It is cleared when the loop terminates normally or on `KeyboardInterrupt`. This means cycle detection works across turns: Turn 1 loads "A", Turn 5 tries "A" again -> detected.

**Variations:**
- The depth limit is a constant (`MAX_SKILLS_PER_TURN = 5` in `skill_utils.py:102`). It is not user-configurable.
- To reset mid-session, end the current tool loop and start a new one.

---

### 4.2 Update Chapter 8 — Add Recipe 8.5

Add a new recipe to the existing Tool Loops chapter that bridges tool loops and skills.

#### 8.5 Skill-aware tool loops

- **Goal:** Enable skill discovery and loading during autonomous tool loops so the model can find and use relevant skills on its own.
- **Commands:** `/tool on`, `/tool enable search_skills,call_skill`, `/tool auto on`, `/tool loop`.
- **Script:** `cookbook/08_5_skill_aware_loops.chatdsl`
- **Run:** `/script doc/cookbook/08_5_skill_aware_loops.chatdsl`

```dsl
/model devstral_1
/tool on
/tool enable search_skills,call_skill
/tool auto on
/tool max_turns 20

/system You can use search_skills to discover available skills and call_skill to load their instructions. When a task matches a skill's purpose, load it and follow its guidance.

chat --> Analyze the codebase and suggest improvements.

/tool loop 20 force
```

**Walkthrough**
1. `/tool enable search_skills,call_skill` activates both skill tools alongside any other enabled tools.
2. The `/system` instruction tells the model it can discover and load skills. Without this, the model may not know to use the tools.
3. During the loop, the model calls `search_skills` to find relevant skills, then `call_skill` to load them.
4. Loaded skill instructions guide the model's subsequent actions within the same loop.

**Variations:**
- `/tool enable all` enables every tool including `search_skills` and `call_skill`.
- Combine with `/tool scratch on` (Recipe 8.3) so the model can write and test scripts as part of a skill's workflow.

---

### 4.3 Update Appendix A — Recipe Index

Add entries for the new recipes to the existing table:

| # | Recipe | Commands exercised | Generalizes / source |
|---|--------|---------------------|----------------------|
| 8.5 | Skill-aware tool loops | `/tool enable search_skills,call_skill` `/tool loop` | new |
| 15.1 | Discovering skills | `search_skills` `/tool enable` `/tool loop` | new |
| 15.2 | Loading skill instructions | `call_skill` `/tool enable` `/tool loop` | new |
| 15.3 | Skill delegation chains | `call_skill` x2 `/tool loop` | new |
| 15.4 | Skills with tool config | `call_skill` `tool_state` `/skill restore` | new |
| 15.5 | Recursion limits & cycle detection | `call_skill` (error paths) | new |

---

### 4.4 Update Appendix B — Cross-Reference Map

Add a row for the new chapter:

| Cookbook chapter | Corresponding section in `chatdsl_guide_v1.md` |
|------------------|----------------------------------------------|
| 15 Dynamic Skill Loading | (new — see Section 4.6 below) |

And update the Chapter 8 row:

| Cookbook chapter | Corresponding section in `chatdsl_guide_v1.md` |
|------------------|----------------------------------------------|
| 8 Tool Loops | HowTo: Set Up Tool Calling Loop; Tool Loop Commands; **Dynamic Skill Loading** (new) |

---

### 4.5 Update `chatdsl_skill.md` — Add Skills System Section

The current `chatdsl_skill.md` is a ChatDSL scripting reference. It does not mention the `/skill` command, the skills database, trigger matching, or dynamic loading. Add a new major section after the existing content.

#### Proposed section: "The Skills System"

```markdown
## The Skills System

Skills are reusable instructions stored in a TinyDB database. When a user prompt
matches a skill's trigger phrases, the skill content is injected into the system
prompt for that turn. Skills can also configure the agentic tool loop via
`tool_config` metadata.

### Managing Skills with /skill

The `/skill` command provides 16 subcommands:

| Subcommand | Purpose |
|------------|---------|
| `list [enabled\|all]` | List skills |
| `show <name>` | Show full skill details |
| `create` | Launch interactive creation wizard |
| `edit <name>` | Edit skill in $EDITOR (content, metadata, tool_config) |
| `delete <name>` | Delete a skill |
| `enable <name\|all\|glob>` | Enable a skill (supports glob patterns) |
| `disable <name\|all\|glob>` | Disable a skill (stays in DB, not triggered) |
| `search <query>` | Search by name, content, description, tags |
| `learn [name]` | Learn a skill from current session turns |
| `apply <name>` | Manually inject skill into next prompt |
| `export <name> <file>` | Export to SKILL.md format |
| `import <file>` | Import from SKILL.md file |
| `restore` | Restore previous tool configuration |
| `on` | Enable auto-triggering for this session |
| `off` | Disable auto-triggering for this session |
| `debug [on\|off]` | Show debug info or toggle trace logging |
| `exit` | Release the active skill lock |

### Trigger Matching

Skills have trigger phrases in their metadata. When a user prompt matches a trigger,
the skill is auto-injected. Trigger matching uses:

- **Word-boundary regex** — prevents false positives (trigger "log" won't match
  "biology" or "catalog").
- **Specificity ranking** — longer triggers (more words) rank higher. Only the
  most specific matched skill is injected per turn by default.
- **Validation** — triggers must be at least 3 characters and 2 words.

### Sticky Skill Lock

When a skill is auto-triggered, it stays active as a "sticky lock" for subsequent
prompts instead of re-scanning triggers each turn. Use `/skill exit` to release
the lock and return to normal trigger scanning.

### Dynamic Loading During Tool Loops

Two in-process tools let the LLM discover and load skills on-demand during the
autonomous tool loop:

- **`search_skills`** — Search by keyword (name, description, tags). Returns
  compact metadata only, no instruction content. Prevents context pollution.
- **`call_skill`** — Load a skill's full instructions by name. Applies any
  `tool_config` silently. Returns a `tool_state` summary and current `depth`.

These are LLM tool calls, not ChatDSL commands. Enable them with:

    /tool enable search_skills,call_skill

Then start the tool loop. The model calls these tools as JSON tool calls during
the loop — the user does not type them as script lines.

### Delegation Safety

- **Cycle detection:** If the same skill is loaded twice in one tool loop,
  `call_skill` returns an error with the full chain.
- **Depth limit:** Maximum 5 skill delegations per tool loop
  (`MAX_SKILLS_PER_TURN = 5`).
- **Tracking scope:** Delegations are tracked across all turns of a single
  `run_tool_loop()` invocation, then cleared on loop termination.
- **Recovery:** Use `/skill restore` to revert tool configuration changes
  applied by skills during the loop.

### search_skills vs. skillsdb.search_skills()

The `search_skills` tool deliberately reimplements search rather than calling
`skillsdb.search_skills()`. The database version searches across `content`
too, which would load instruction text into the model's context during
discovery. The tool version excludes `content` from both the search corpus
and the result set. This duplication is intentional.
```

---

### 4.6 Update `chatdsl_guide_v1.md` — Add Dynamic Skill Loading Section

Add a new section after the existing "Tool Loops" section in the main guide. Keep it concise — the cookbook has the full recipes, the skill guide has the reference. The main guide needs an overview that points to both.

```markdown
## Dynamic Skill Loading

The skills system provides two mechanisms for using skills:

1. **Auto-triggering** — When a user prompt matches a skill's trigger phrases,
   the skill is injected into the system prompt automatically. Toggle with
   `/skill on` and `/skill off`.

2. **On-demand loading** — During the tool loop, the LLM can discover and load
   skills using two in-process tools:

   - `search_skills(query, limit)` — Find skills by keyword. Returns metadata
     only (name, description, tags) to avoid context pollution.
   - `call_skill(name)` — Load a skill's full instructions. Applies any
     `tool_config` silently and returns a `tool_state` summary.

   Enable both with `/tool enable search_skills,call_skill` before starting
   the tool loop. The model calls these as tool calls (JSON), not as ChatDSL
   script commands.

Safety features:
- Circular delegation detection (same skill loaded twice in one loop)
- Depth limit: 5 skill delegations per tool loop
- `/skill restore` reverts tool configuration changes

See the [Cookbook Chapter 15](chatdsl_cookbook.md) for recipes and the
[Skill Guide](chatdsl_skill.md) for the full `/skill` command reference.
```

---

### 4.7 Translated Guides — Phased Approach

The 5 translated guides (`_arabic`, `_chinese`, `_french`, `_italian`, `_spanish`) currently have no skill content. Translating technically precise terminology (recursion limits, cycle detection, `tool_config`, context pollution, silent application) across 5 languages is substantial work.

**Phase 1 (this proposal):** Write all new content in English first. Get the technical accuracy reviewed and stable.

**Phase 2 (follow-up):** Translate the `chatdsl_guide_v1.md` section (Section 4.6 above, ~40 lines) into all 5 languages. This is the highest-value translation since it's the main guide users find first.

**Phase 3 (follow-up):** Translate the `chatdsl_skill.md` skills section (Section 4.5 above, ~60 lines) into all 5 languages.

The cookbook recipes (Chapter 15) are lower priority for translation since they are code-heavy and the DSL syntax is language-neutral. The walkthrough prose could be translated in a later pass.

**Why phased?** Recent commit `dc0cea3` shows that even a small disambiguation note required touching all 6 language guides. Getting the English content stable first avoids re-translating after corrections.

---

## 5. Cookbook Recipe Files

Each new recipe needs a corresponding `.chatdsl` file in `cookbook/`. These match the existing pattern: a header comment with recipe number, goal, and run command, followed by the DSL script.

### `cookbook/15_1_skill_discovery.chatdsl`

```dsl
# Recipe 15.1 - Discovering skills with search_skills
# Goal: let the model discover available skills by keyword during a tool loop.
# Run: /script doc/cookbook/15_1_skill_discovery.chatdsl

/model devstral_1
/tool on
/tool enable search_skills,call_skill
/tool auto on
/tool max_turns 20

chat --> I want to review some code. Find a relevant skill and use it to review the files in src/.

/tool loop 20 force
```

### `cookbook/15_2_skill_loading.chatdsl`

```dsl
# Recipe 15.2 - Loading skill instructions with call_skill
# Goal: load a skill's full instructions by name during a tool loop.
# Run: /script doc/cookbook/15_2_skill_loading.chatdsl

/model devstral_1
/tool on
/tool enable search_skills,call_skill
/tool auto on
/tool max_turns 20

chat --> Load the "code-review" skill and use it to review src/auth.py.

/tool loop 20 force
```

### `cookbook/15_3_skill_delegation.chatdsl`

```dsl
# Recipe 15.3 - Skill delegation chains
# Goal: chain multiple skills in a single tool loop.
# Run: /script doc/cookbook/15_3_skill_delegation.chatdsl

/model devstral_1
/tool on
/tool enable search_skills,call_skill
/tool auto on
/tool max_turns 30

chat --> Research the codebase architecture. Use skills to guide your analysis.

/tool loop 30 force
```

### `cookbook/15_4_skill_tool_config.chatdsl`

```dsl
# Recipe 15.4 - Skills with tool configuration
# Goal: load a skill that modifies the tool set mid-loop, then restore.
# Run: /script doc/cookbook/15_4_skill_tool_config.chatdsl

/model devstral_1
/tool on
/tool enable search_skills,call_skill
/tool auto on
/tool max_turns 25

chat --> I need to debug an error in src/. Find and load a debugging skill.

/tool loop 25 force

# Restore original tool configuration after the loop
/skill restore
```

### `cookbook/15_5_recursion_limits.chatdsl`

```dsl
# Recipe 15.5 - Recursion limits and cycle detection
# Goal: understand the safety mechanisms that prevent unbounded skill chaining.
# Run: /script doc/cookbook/15_5_recursion_limits.chatdsl
#
# Setup: create two skills that delegate to each other:
#   /skill create  ->  name: loop-a, content: "Call the Skill tool for 'loop-b'"
#   /skill create  ->  name: loop-b, content: "Call the Skill tool for 'loop-a'"

/model devstral_1
/tool on
/tool enable search_skills,call_skill
/tool auto on
/tool max_turns 30

chat --> Load the "loop-a" skill and follow its instructions.

/tool loop 30 force
```

### `cookbook/08_5_skill_aware_loops.chatdsl`

```dsl
# Recipe 8.5 - Skill-aware tool loops
# Goal: enable skill discovery and loading during autonomous tool loops.
# Run: /script doc/cookbook/08_5_skill_aware_loops.chatdsl

/model devstral_1
/tool on
/tool enable search_skills,call_skill
/tool auto on
/tool max_turns 20

/system You can use search_skills to discover available skills and call_skill to load their instructions. When a task matches a skill's purpose, load it and follow its guidance.

chat --> Analyze the codebase and suggest improvements.

/tool loop 20 force
```

---

## 6. Summary of Changes

| Document | Change | Approx. lines | Priority |
|----------|--------|---------------|----------|
| `chatdsl_cookbook.md` | New Chapter 15 (5 recipes) | ~250 | High |
| `chatdsl_cookbook.md` | New Recipe 8.5 in Chapter 8 | ~40 | High |
| `chatdsl_cookbook.md` | Update Appendix A (6 new rows) | ~10 | Medium |
| `chatdsl_cookbook.md` | Update Appendix B (2 rows) | ~5 | Medium |
| `chatdsl_skill.md` | New "The Skills System" section | ~80 | High |
| `chatdsl_guide_v1.md` | New "Dynamic Skill Loading" section | ~40 | High |
| `cookbook/15_1` through `15_5` + `08_5` | 6 new `.chatdsl` recipe files | ~120 total | High |
| `chatdsl_guide_v1_*.md` (5 translations) | Translate Dynamic Skill Loading section | ~40 each | Medium (Phase 2) |
| `chatdsl_skill.md` translations (5) | Translate Skills System section | ~80 each | Low (Phase 3) |
| `doc/` vs `src/chatybot/doc/` | Resolve duplication (symlink or remove) | N/A | High (pre-work) |

**Total new English content:** ~545 lines across 9 files (6 new, 3 updated).
**Total translated content (Phase 2+3):** ~600 lines across 10 files.

---

## 7. Why These Changes Matter

1. **Discoverability** — Users cannot use `search_skills` and `call_skill` if they don't know they exist. The cookbook is the primary user-facing doc; a chapter there is the standard way features are introduced.
2. **Correct mental model** — The most important correction is showing these as LLM tool calls within a tool loop, not as ChatDSL script commands. Getting this wrong leads users to type `search_skills query="..."` in scripts and wonder why nothing happens.
3. **Zero-context-pollution design** — The `search_skills` reimplementation decision (excluding `content` from search and results) is a key performance feature. Users who don't understand this may try to work around it or expect full content in search results.
4. **Safety features** — Cycle detection and the depth limit are automatic protections, but users need to know they exist to design skills that don't trigger them accidentally, and to understand error messages when they do.
5. **`/skill restore`** — Tool configuration changes applied silently mid-loop are recoverable, but only if users know about `/skill restore`. Recipe 15.4 makes this explicit.
6. **Translation sustainability** — Phasing the translation work avoids the pattern seen in commit `dc0cea3` where small corrections require touching all 6 language guides. Stabilize English first, translate once.

---

## 8. Implementation Order

1. **Resolve doc duplication** (`doc/` vs `src/chatybot/doc/`) — symlink or remove one tree.
2. **Write Chapter 15** in `chatdsl_cookbook.md` (5 recipes + walkthroughs).
3. **Write Recipe 8.5** in Chapter 8 of `chatdsl_cookbook.md`.
4. **Create 6 `.chatdsl` recipe files** in `cookbook/`.
5. **Update Appendices A and B** in `chatdsl_cookbook.md`.
6. **Add "The Skills System" section** to `chatdsl_skill.md`.
7. **Add "Dynamic Skill Loading" section** to `chatdsl_guide_v1.md`.
8. **Review and test** — run each recipe script to verify it works as documented.
9. **Phase 2:** Translate the `chatdsl_guide_v1.md` section into 5 languages.
10. **Phase 3:** Translate the `chatdsl_skill.md` section into 5 languages.
