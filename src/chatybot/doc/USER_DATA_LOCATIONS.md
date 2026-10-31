# Where your data lives

ChatyBot stores user data in two XDG-standard locations, split by role:
configuration and secrets under `~/.config/chatybot/`, state and data under
`~/.local/share/chatybot/`. Everything outside those two roots is either
an override you configured or a known outlier (listed below).

Use this document to find any file the app creates, to know what to back
up, and to know what is safe to delete.

## Configuration and secrets: `~/.config/chatybot/`

| Path | Used by | Contents |
|---|---|---|
| `chat_config.toml` | `config_manager`, `dispatcher`, `env_utils` | Models, providers, sampling defaults, `[batch]` guard settings |
| `tools_config.toml` | tools subsystem, `tool_config_tui` | Agentic tool enable/disable, MCP servers, loop settings |
| `security.toml` | `security/manager` | Security policy, verdicts, tool gates |
| `jev_security.toml` | `security/jev`, `setup_jev` | JEV rubric configuration |
| `.env` | `env_utils` | **API keys.** Loaded into the environment at startup; protected by the secret scanner |
| `profiles/*.chatdsl` | `profile_manager` | Named profiles (`coding`, `general`, `explorer`, ...) applied with `/profile use` |
| `procs/` | `commands/proc_macros` | Optional user-level proc library (`<proc_name>.chatdsl`), searched after `./procs/` |
| `logs/security_chain.jsonl` | `security/chain` | Append-only security decision log (every allow/deny verdict) |
| `logs/jev_security.jsonl` | `security/jev` | JEV decision log |

Back this directory up if you care about your configuration. The `.env`
file holds secrets — exclude it from shared backups.

## State and data: `~/.local/share/chatybot/`

| Path | Used by | Contents |
|---|---|---|
| `sessions/<session_id>/` | `chatybot_app`, `session_factory` | Per-session store: `meta.json` (metadata), `turns.jsonl` (append-only turns, or `.gz`), `backups/`, `diffs/`, `scratch/` |
| `batches/` | `batch_manager` | Batch API jobs: `index.jsonl` global catalog plus one directory per batch (`btch-<ts>-<slug>/`) holding `meta.json`, `staging.jsonl`, `requests.json`, `results.jsonl`. Fully decoupled from session history |
| `db/*.json` | `chatydb`, `tools/db_tools` | TinyDB-style stores for search results and corpora (`/db save`, rerank sources) |
| `scratch/` | `tools/file_utils` | Global scratchpad fallback when no session is active |
| `backups/`, `diffs/` | `tools/file_utils` | Global file-edit backups and diffs when chat history is off |
| `skills.json` | `skillsdb` | Skill triggers and content (TinyDB) |
| `test/` | test environment | Test-isolated data |

The sessions directory location can be overridden with the `session_dir`
key in `tools_config.toml` / `chat_config.toml`. Batch storage resolution
order: `CHATYBOT_TEST_BATCHES_DIR` env var (test override) →
`BatchManager(batches_dir=...)` argument → the default above.

## Outliers (known, deliberate)

| Path | Written by | Notes |
|---|---|---|
| `~/chatybot_images` | `image_generator`, `image_manager` | Default image output dir; overrides via the image config `default_dir` key |
| `./chatybot.log.<timestamp>` | `logging_manager` | Created in the **current working directory** when `/log` is on |
| `./chatybot.vmem.<timestamp>.log` | `chatybot_app` vmem monitor | Created in the **current working directory** |

There is no user data anywhere else: the legacy `~/.chatybot/` root held
only batch data and was retired when batches moved to the XDG data dir
(the proc search path and help examples that referenced it were updated).

## Current state (verified 2026-10-30)

Crosschecked against a live installation:

- `~/.config/chatybot/` — `chat_config.toml`, `tools_config.toml`,
  `security.toml` (+ `.bak`), `jev_security.toml`, `profiles/` (5
  profiles), `logs/` (both security logs active).
- `~/.local/share/chatybot/` — `sessions/`, `batches/` (6 instances:
  4 completed, 2 in progress; catalog `index.jsonl` intact), `db/` (11
  stores), `scratch/`, `skills.json`, `test/`.
- `~/.chatybot/` — empty; safe to delete.
- `~/chatybot_images` — not created (image `default_dir` configured
  elsewhere or images unused).
