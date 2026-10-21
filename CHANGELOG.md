# Changelog

All notable changes, release milestones, and version history for **Chatybot** are documented in this file.

Unreleased
----------
- **Security refusals in tool loops**:
  - Refusals are final, not errors: a security DENY, a declined ASK, a non-interactive block and a refused output now return `Security refusal (final): <reason>. Do not retry this action or an equivalent one. Tell the user what you were trying to do and ask how to proceed.` instead of `Error: ...`, which weaker models treated as transient and retried. Script variables (`TOOL_DISPATCH_EXIT_CODE=1`, `TOOL_DISPATCH_ERROR`) are unchanged. Guidance string localized in all six languages.
  - Refusal memory per tool loop: a refused call repeated with the same (normalized) arguments gets the stored refusal back without a new policy evaluation, Jev call or prompt, and without running the tool again when its output was refused. Only refusals are remembered, never approvals. Scripts and direct `/tool` dispatches are unaffected.
  - Refusal limit: `max_refusals_per_loop` in `security.toml` (default 3, `0` disables). When reached, the loop ends and the user gets a summary of the refused calls and reasons; non-interactive runs set `TOOL_DISPATCH_EXIT_CODE=1`.
  - Refusals are detected by a flag set in `dispatch_tool`, not by searching tool output, so a file or page that contains the refusal text is not counted.
  - New `refusal_repeat` and `refusal_limit` events in `security_chain.jsonl` (chain engine) or `jev_security.jsonl` (jev engine), joined to the original decision by `request_id`; reasons and arguments are redacted and cut to 4,000 characters, and a value is omitted if redaction fails. `jev_eval.py --from-log` reports them per session. `TOOL_DISPATCH_REQUEST_ID` is a new protected script variable.
- **Tool-loop guard**:
  - Stops models that keep repeating the same tool call (reported with Cohere and dots free models). A repeat counts only when the arguments and the result are both identical, within the last `loop_guard_window` (8) executed calls, so A, B, A, B alternation is caught and state-changing sequences are not.
  - When a call has returned the same result `loop_guard_repeats - 1` (2) times, the next request is not executed and the model is told to use the earlier result or change approach; if it asks again with nothing else run in between, the loop stops with an explanation. Withheld calls are marked `"loop_guard"` in `AGENTIC_LOOP` / `/tool history`.
  - The guard only withholds calls: it never executes anything or skips a security check; security-refused calls are left to the refusal limit; `ask_user` is exempt.
  - Settings: `loop_guard`, `loop_guard_repeats`, `loop_guard_window` in `tools_config.toml` `[config]`; `/tool loop_guard [on|off|repeats <n>|window <n>]`. Added `test/test_loop_guard.py`.
- **Jev rubric v1.2**:
  - New rule `shell_startup` (ask): reading, searching or sourcing `~/.zshrc`, `~/.zshenv`, `~/.zprofile`, `~/.bashrc`, `~/.bash_profile`, `~/.profile` or the fish config.
  - New rule `persistence` (deny): writing to those files, crontab entries, launchd agents or daemons, systemd units, login items, and `git config --global` hooks or aliases.
  - `secrets` now names `~/.netrc`, `~/.npmrc`, `~/.pypirc`, `~/.git-credentials`, `~/.docker/config.json` and `~/.kube/config`.
  - Test set grown from 102 to 129 cases; 129/129 over 3 runs, harmless commands scored at most 0.45 and flagged ones at least 0.75 (`tools/jev-eval/baseline/run7-rubric-v1.2.jsonl`, history in `jev_proof_of_concept.md`).
  - Startup notice when `~/.config/chatybot/jev_security.toml` is older than the bundled rubric, naming the new rules. The user's file is never modified; merge the changes or copy `src/chatybot/security/default_jev_security.toml`.
- **Documentation**:
  - `doc/jev_security_engine.md` updated to match the code: chain short-circuit rules, run-7 results, redaction, output security, log formats, what leaves the machine, and known limitations (including that the model sees Jev rule scores in refusals). Corrected an earlier claim that builtin asks for every shell command; it allows read-only git commands.
  - `doc/chatdsl_guide_v1.md`: documented that `--script` and `--run` always exit 0 and how scripts detect failures through `RUN_EXIT_CODE`, `TOOL_DISPATCH_EXIT_CODE`, `TOOL_DISPATCH_ERROR` and `TOOL_DISPATCH_RESULT`.

- **Jev payload redaction now uses SecretScanner (security fix)**:
  - Requests to the Jev API, Jev/chain logs and payload traces were redacted with an older pattern list that missed Groq (`gsk_`), Hugging Face (`hf_`), Google (`AIza`), JWTs, keys passed as command-line flags, and the user's own unprefixed keys. `jev.redact_text` now runs `SecretScanner.redact()` first: exact known secrets (`<redacted:KEY_NAME>`), whole private-key blocks, and every provider/assignment rule, replacing only the value so Jev still sees the command.
  - New `SecretScanner.redact()`; new rules for command-line flag credentials (`--api-key X`, `--token X`, `--password X`) and HTTP Basic credentials; database-URL passwords are now value-checked (placeholders like `user:password@` are ignored).
  - Shell expansions (`$VAR`, `${VAR}`, `$(cmd)`) and `Bearer`/`Basic` scheme words are no longer redacted, so Jev can see intent such as keychain reads.

- **Output secret scanner precision**:
  - The generic credential rules now treat their regex match as a candidate and check the value: code that only references a credential (`os.environ[...]`, `getpass()`, `settings.SECRET_KEY`, `$(...)`, `${{ }}`), placeholders (`your_`, `<...>`, `example`, `fake`), paths, URLs and short or low-randomness values no longer prompt. Repo files that would prompt on read dropped from 32 to 5 (all test fixtures with fake keys).
  - Passwords: 8+ characters; a bare word without digits is a value in env-style (`DB_PASSWORD=x`), YAML/prose (`password: x`) and `.netrc` lines, and a variable name in code-style assignments (`password = x`, `password=password`).
  - New `.netrc` rule (`login <user> password <value>`); JSON (`"api_key": "..."`) and `:=` assignments are now covered.
  - Output rules accept an optional `validator` (`token_value`, `password_value`, `credential_value`); see `[output_security]` in the default `security.toml`.
  - Added `test/test_secret_scanner.py`, including a guard that no `src/` file or doc prompts on read.

- **Post-Execution Output Security (Egress Filtering & Secret Protection)**:
  - Added post-execution output screening in `SecurityManager` and policy engines (`builtin`, `jev`, `chain`, `allow_all`, `stdio_binary`) to evaluate tool output (`read_file`, `run_command`, `str_search`, `read_url`) before it enters LLM context.
  - Implemented clean tri-state access control (ALLOW / ASK / DENY) avoiding fragile token redaction:
    - **ALLOW**: Untouched raw tool output enters LLM context.
    - **ASK**: Prompts user interactively to authorize LLM viewing sensitive data. If approved (`y`), raw output is passed completely intact; if declined (`n`), output is withheld. Respects `-y`/auto-approve and `non_interactive_ask` ("deny" blocks, "allow" permits).
    - **DENY**: Hard blocks disclosure, erases raw output from context, sets `TOOL_DISPATCH_EXIT_CODE = '1'`, and returns a clear policy violation error.
  - Added built-in regex rules detecting private cryptographic keys (DENY), GitHub tokens (ASK), AWS keys (ASK), API keys (ASK), and bearer tokens/passwords (ASK).
  - Added `[output_security]` configuration section in `default_security.toml` with `enabled`, `tools`, and customizable `rules`.
  - Added output security evaluation latency measurement (`last_security_duration_ms`) and debug trace logging.
  - Added comprehensive test coverage across `test/test_pluggable_security.py` and `test/test_security_chain_jev.py`.
- **Jev Security Engine, Chaining & Allow Mode** (branch `jev_security`):

  - **`engine = "allow"`**: runs tools without policy checks, like chatybot before v0.9.0. Persistent in `security.toml` (unlike `--no-security`), prints a startup warning, and by default still protects `security.toml`, `jev_security.toml`, `*.racf` and `~/.config/chatybot/.env` (`[allow] protect_security_config`).
  - **`engine = "chain"`**: runs several engines per tool call. `enforce` stages decide (strictest verdict wins; later enforcers are skipped after a DENY); `shadow` stages are pass-through, evaluated and logged only. Optional JSONL comparison log with per-stage verdicts, latency and a disagreement flag; secrets are redacted in the log.
  - **`engine = "jev"`**: TypeSafe Jev decision-model engine driven by a rubric (`~/.config/chatybot/jev_security.toml`, seeded from `security/default_jev_security.toml`). Self-protection floor before any API call, secret redaction, head+tail truncation that forces at least ASK, per-session cache, `on_error` fail-safe (ASK interactive / DENY non-interactive), optional JSONL log, `noul` or `combined` mode.
  - Rubric scoring shared between the engine and the `tools/jev-eval` harness (`security/jev_rubric.py`).
  - Added `test/test_security_chain_jev.py` (Jev HTTP stubbed).
- **Pluggable Security Evaluation Instrumentation**:
  - Measured execution duration (`duration_ms`) inside `SecurityManager.evaluate()` using `time.perf_counter()`, stamped onto `PolicyDecision`.
  - Exposed evaluation duration in `--security` debug trace lines (`[Security Debug] [TIME] Security evaluation for '{tool}' completed in {ms} ms ({verdict})`).
  - Recorded security evaluation time in the agentic loop output alongside tool duration: `Tool time: X.X ms (security: Y.Y ms)` (or `<0.1 ms` for sub-0.1ms checks).
  - Saved `SECURITY_EVAL_TIME_MS` script buffer variable in `dispatch_tool` for scripts and inspection.
- **Tool argument envelopes (security fix)**:
  - Models sometimes wrap tool arguments as `{"parameters": {...}}`, `{"args": {...}}` or `{"arguments": {...}}`. Previously the security check judged the wrapped form while execution unwrapped it, so builtin path/command checks and self-protection could be bypassed (e.g. a wrapped `read_file /etc/passwd` was allowed).
  - One rule now lives in `chatybot/tool_args.py` (`unwrap_tool_args`): unwrap only a lone envelope key, repeatedly. `dispatch_tool` normalizes once before the security check, and `SecurityManager.evaluate`, the tool-call normalizer, `dispatcher.py` and the in-app tools (`ask_user`, `decide_*`, `call_skill`, `search_skills`) all use the same arguments, so a decoy envelope beside real arguments can no longer be judged in their place.
- **Jev / chain observability and hardening**:
  - Jev and chain logs are on by default (`~/.config/chatybot/logs/jev_security.jsonl`, `security_chain.jsonl`); `log_path = ""` turns them off.
  - The Jev log records every call with a `source` (api, cache, self_protect, skip_tools, error); cached decisions keep their scores and are returned as copies.
  - ASK outcomes (approved, declined, auto-approved via `-y` or `non_interactive_ask`, blocked non-interactive) are logged with the decision's `request_id` via `SecurityManager.record_outcome`, called from tool dispatch. Decisions now carry `request_id` (not part of the engine wire protocol).
  - Malformed Jev probabilities (NaN, ±inf, outside 0–1, choice distributions that do not sum to 1) are treated as missing and give ASK instead of ALLOW.
  - Test that fails if `default_jev_security.toml` and `tools/jev-eval/rubric.toml` drift apart.
  - `tools/jev-eval/jev_eval.py --from-log`: summarise live logs, re-grade saved Jev scores with new thresholds, and `--export` cases worth labelling as draft corpus entries.

- **TinyDB Persistence & Dispatcher Performance**:
  - **Snapshot-on-Write Optimization**: Moved TinyDB rolling snapshot backups from database activation (`/setdb`) to the first write (`/dblog`) per session, completely eliminating backup churn and rotation on read-only operations and model tools (`db_search`, `db_get`).
  - **Dispatcher Startup Optimization**: Removed unused `chatydb` import and `log_to_database` hook from `dispatcher.py` (saves ~2–3 ms per tool call).
  - **Model DB Tool Hardening**: Isolated scoped model queries from active session databases, eliminated double-serialized JSON strings, suppressed stdout output during tool calls, prevented phantom directory and file creation on missing DB queries, and handled corrupted database files gracefully.

October 15th, 2026 (v0.9.0)
---------------------------
- **Pluggable Security Release v0.9.0**:
  - Official release of Chatybot Pluggable Security Architecture and integration into master.
  - Bumped version to 0.9.0 across `pyproject.toml`, `chatybot_app.py`, and package initialization.

October 14th, 2026
------------------
- **RACF-Guard Engine Diagnostics & Traceability**:
  - Added candidate profile specificity scoring logs in debug trace (`tools/racf-guard/src/engine.rs`), displaying evaluated candidate profiles alongside matching specificity scores for deep audit inspection.

October 13th, 2026
------------------
- **Policy Engine Hardening & P0/P1 Edge Cases**:
  - Enforced policy self-protection: strictly denied read/write access to `security.toml` and `*.racf` files across both Builtin and RACF policy engines.
  - Hardened shell command parsing against command chaining (`&&`, `||`, `;`, `&`, `|`, `` ` ``, `$()`), subshell execution, and path traversal tricks.
  - Resolved P1 multi-parameter inspection edge cases and added `ResourceClass::Ps` enforcement for `manage_task` and process inspection commands.
  - Optimized `StdioBinaryPolicyEngine` startup with cached banner results.
- **RACF-Guard Deployment Tools & Profiles**:
  - Added automated `setup.sh` one-shot installer script for `racf-guard`.
  - Added restrictive directory control (`restrictive_dir.racf`) and process control (`process_control.racf`) reference policy profiles.
- **Multilingual Localization & Documentation Synchronization**:
  - Localized all security approval prompts, action headers, and confirmation responses across English, Spanish, French, Italian, Arabic, and Chinese.
  - Extracted changelog from README into standalone `CHANGELOG.md` and synchronized `doc/` tree for `/docs` discovery.
  - Added Chapter 16 ("Pluggable Security & Policy Guardrails") to ChatDSL Cookbook (`doc/chatdsl_cookbook.md`) with 4 end-to-end recipes.
  - Added Pluggable Security API Specification (`doc/pluggable_security_api.md`) and technical notes on subprocess one-shot evaluation architecture.

October 12th, 2026
------------------
- **RACF-Guard Reference Policy Engine (Rust)**:
  - Implemented `racf-guard` in Rust (`tools/racf-guard/`) providing enterprise-grade IBM RACF-style access control with users, groups, universal access (`UACC`), and explicit access lists.
  - Added resource classes: `FACILITY` (tools), `COMMAND` (bash commands), `DIR` (path globbing), `CONTENT` (payload/file inspection), and `PS` (process IDs/names).
  - Added CLI flag forwarding (`--banner`, `--audit`, `--policy`, `--debug`) and audit logging.
- **CLI Security Controls & Non-Interactive Execution**:
  - Added `-y`/`--yes` CLI flag and `non_interactive_ask` configuration for headless automation and non-interactive scripting.
  - Added `--no-security` CLI flag for unconstrained environments with prominent startup warnings.
  - Added sub-agent recursion defense preventing nested execution of `chatybot` to block privilege escalation attacks.
  - Added read-only git whitelist guards and destructive git command denials (`push --force`, `reset --hard`, `clean -fdx`).

October 11th, 2026
------------------
- **Pluggable Tri-State Security Core & Builtin DSL**:
  - Introduced pluggable security architecture with `SecurityManager` enforcing tri-state evaluation (`allow`, `ask`, `deny`) before dispatching tool calls.
  - Implemented human-readable Security DSL grammar, parser, and matcher in `src/chatybot/security/dsl.py`.
  - Added automatic seeding of default policy to `~/.config/chatybot/security.toml` on first run with console notification.
  - Integrated startup banner reporting of active security engine and loaded DSL rule count.
  - Added `--security` CLI debug flag displaying parsed rules and execution trace.
  - Added Tier 0 filesystem path protection against directory traversal and root privilege tampering.
  - Converted interactive user prompt confirmations to non-blocking async operations (`asyncio.to_thread`).
  - Added unit test suite in `test/test_pluggable_security.py`.

September 30th, 2026 (v0.8.8)
----------------------------
- **`/docs` Line-Based Navigation & Search-to-View Workflow**:
  - Added `line=N` parameter to `/docs <filename>` — centers the target line in a 40-line chunk with context above and below, so search results (which return `filename:line_number`) can be jumped to directly.
  - Fixed `page=N` being silently ignored in REPL mode — `page=N` (when N > 1) now uses chunked display in both REPL and script contexts instead of falling through to the full-screen pager.
  - Added Prev/Next navigation footers to both `line=` and `page=` modes, enabling back-and-forth paging through the file from any entry point.
  - Updated `/docs search` output to suggest the exact `line=` command for the first match (e.g. `Jump to first match: /docs chatdsl_cookbook.md line=928`).
  - Updated `/docs` help text, usage string, and examples in `chaty_help.py`.
  - Added 7 new tests in `test/test_doc_utils.py` (22 total, all passing).

September 29th, 2026
--------------------
- **Agentic Skill Discovery & Delegation Tools (`search_skills`, `call_skill`)**:
  - Added `search_skills` tool in `src/chatybot/tools/skill_utils.py` returning compact metadata summaries (`name`, `description`, `tags`) with instruction `content` stripped to guarantee zero context pollution.
  - Added `call_skill` tool with case-insensitivity and hyphen/underscore normalization, silent mid-loop `tool_config` application (with tool state diff report and snapshot preservation), and recursion/cycle protection (max 5 delegations per tool loop).
  - Registered `[tools.search_skills]` and `[tools.call_skill]` in `tools_config.toml`.
  - Implemented in-process dispatching in `chatybot_app.py`'s `dispatch_tool()` handler, with `_turn_skills_loaded` tracking across `run_tool_loop()` turns.
  - Added tool_config serialization support to `/skill edit` in `commands/skills.py`.
  - Added comprehensive unit test suite in `test/test_skill_tools.py` (14 passing tests) and updated `/help` documentation.
- **Skill Tracing & Sticky Lock (`/skill debug`, `/skill exit`)**:
  - Added `/skill debug [on|off]` subcommand for real-time trace logging of trigger scanning and ranking.
  - Added sticky session lock: auto-triggered skills stay locked as `app.active_skill` for subsequent turns until `/skill exit` or manual override.
  - Enforced trigger validation: minimum 3 characters and minimum 2 words to eliminate short false-positive triggers.
  - Added duplicate skill name checks in `create_skill` raising `ValueError`.
- **Comprehensive Code Modernization & Linter Compliance (Ruff)**:
  - Narrowed 36 blind/silent exception handlers to specific exception types (`JSONDecodeError`, `OSError`, `UnicodeDecodeError`, `ValueError`).
  - Replaced silent `except: pass` blocks with warning prints on key I/O failures across logging, session management, and file tools.
  - Configured suppression rules in `pyproject.toml` for `ASYNC230`/`ASYNC221` (single-coroutine event loop) and `SIM115` (session-lifetime file handles).
  - Cleaned up import aliasing (`PLR0402` in `query/__init__.py`) and simplified nested conditional checks across TUI and command modules.

September 28th, 2026
--------------------
- **Trigger Matching Engine Hardening & Specificity Ranking**:
  - Replaced naive substring trigger matching with word-boundary regex (`\b`) in `get_matching_skills` to eliminate substring false positives (e.g. trigger "log" matching "biology", "catalog", or "logging").
  - Implemented trigger specificity ranking (`top_k=1` default) scoring matches by word count of the matched trigger phrase; longer triggers rank higher, injecting only the single most specific skill per turn.
- **Session-Level Auto-Trigger Control (`/skill on`, `/skill off`)**:
  - Added `/skill on` and `/skill off` subcommands to dynamically toggle auto-triggering within the active session.
  - Added session-scoped `skills_enabled` flag on `ChatybotApp` (session-scoped, defaults on).
  - Updated `/skill` help text, usage string, and command reference tables.

September 25th, 2026
--------------------
- **Dynamic Context Injection (!`cmd`) in Prompts & Skills**:
  - Implemented inline shell execution (`!`cmd``) in `BufferManager` with strict guardrails: 3.0s execution timeout, 4KB output cap, non-interactive stdin (`DEVNULL`), and `safe_mode` / `safe_mode_askfirst` checks via `app.check_dangerous()`.
  - Added automatic glob wildcard expansion (`*`, `?`, `[]`) for arguments under `shell=False`.
  - Added `expand_injections` flag to `replace_placeholders` to prevent double-execution in `/run`.
  - Expanded dynamic command injections inside skill bodies in `_inject_skills`.
  - Disambiguated `!` history recall from `!\`` dynamic command injection at start of line.
  - Added comprehensive test suite in `test/test_dynamic_injection.py` (23 passing tests).
  - Documented architectural roadmap in `skill_concerns.md` and revised specification in `prompt_injection.md`.

September 24th, 2026
--------------------
- **Pattern Matching for Skill Management (`/skill enable`, `/skill disable`)**:
  - `/skill enable` and `/skill disable` now support glob patterns matching `/tool enable|disable` behavior (`all`, fnmatch patterns like `code-*`).
  - Added exact case-insensitive name fallback when no glob characters are present and no pattern matched.
  - Standardized shared `_enable_disable_skill` helper and updated usage strings.

September 23rd, 2026
--------------------
- **Skills Database System (`/skill`, `skillsdb.py`)**:
  - Added TinyDB-backed skills store (`~/.local/share/chatybot/skills.json`) with cached trigger index and lazy initialization.
  - Introduced `/skill` command suite with 13 subcommands (`list`, `show`, `create`, `edit`, `delete`, `enable`, `disable`, `search`, `learn`, `apply`, `export`, `import`, `restore`).
  - Added pre-turn prompt injection (`_inject_skills`) and interactive tool reconfiguration (`_apply_skill_tool_config`) with user diff confirmation and rollback snapshotting (`/skill restore`).
  - Supported open `SKILL.md` format (YAML frontmatter + markdown body) for export/import.
  - Seeded 7 default built-in skills (`code-review`, `debug-error`, `write-test`, `research-agent`, `compare-models`, `batch-translate`, `db-research-log`).
  - Wired skill injection into both standard completion (OpenAI API) and on-device Apple Foundation Models (`_apple_fm_completion`).
  - Added 26 unit tests covering CRUD, trigger matching, enable/disable, search, and export/import.
- **ChatDSL Grammar & Specification**:
  - Synchronized ChatDSL BNF specification (`chatdsl_bnf.txt`) to v0.8.7.

September 22nd, 2026
--------------------
- **Raw Payload Tracing for Structured Decisions**:
  - Added `/trace rawpayload on` support for `/decide` command and `decide_*` decision tools.
  - Dumps formatted request JSON (endpoint, headers, token/byte metrics) and response JSON (status, probabilities, calibrated confidence).
  - Forwarded logging manager to log decision payloads and propagated tracing environment variables to subprocess dispatcher.

September 21st, 2026 (v0.8.7)
----------------------------
- **Structured Decision Engine (`/decide`)**:
  - Integrated TypeSafe Jev & OpenRouter decision model support with three question types: `choice`, `score`, and `noul` (boolean).
  - Added calibrated confidence gating with `threshold=<float>`, falling back deterministically to `"FALLBACK"` when confidence falls below the floor.
  - Implemented automatic calibration unpacking into protected registers (`${DECIDE}`, `${DECIDE_CONF}`, `${DECIDE_PROB}`, `${DECIDE_FULL}`) and custom variable registers (`<var>`, `<var>_choice`, `<var>_conf`, `<var>_prob`, `<var>_prob_<option>`).
  - Added support for ordinal scales with `scale="min:max"` (including negative integer ranges) or `levels=`, with Jev 10-level validation.
  - Full variable and placeholder resolution for `<state>` and `<instructions>` with backslash escape protection.
  - Decision turns are fully persisted and serialized across sessions (`/session show`, `/session export`, `save_active_session`).
  - Added multilingual alias dispatch (`/decidir`, `/decider`, `/决策`, `/decidi`, `/قرار`).
- **Thinking Tag Normalization & `/setvar` Flags**:
  - `/setvar` and array assignments (`/setvar var[]`) now automatically strip reasoning tags (`<think>`, `<thought>`, `<thinking>`) by default.
  - Added `withthink` / `raw` and `nothink` / `clean` flags to `/setvar` to explicitly retain or strip thinking blocks.
  - Improved robustness of unclosed or truncated thinking tag stripping during stream interruptions.
- **Database Summary Tool (`db_summary`)**:
  - Added `db_summary` agent tool to `tools_config.toml` for retrieving concise database manifests in compact table or JSON format with range filtering.
- **Model Configuration & TUI**:
  - Added `type = "decision"` model configuration support with TypeSafe vendor presets in `chat_config.toml` and interactive editing in `config_tui.py`.

September 18th, 2026 (v0.8.6)
----------------------------
- **Tool History Append Mode (`/tool append_mode [summary|full|off]`)**:
  - Added configurable history commit modes for autonomous tool loops (`summary` [default], `full`, and `off`).
  - `summary` appends a compact, redacted execution summary of tool calls and exit statuses to the final response, keeping token overhead minimal while reinforcing correct tool invocation signatures for future turns.
  - `full` records every intermediate step and tool output for models requiring explicit step-by-step reasoning context.
  - `off` preserves only the final natural-language response.
- **Autonomous Tool Loop Resilience & Rescue (`/tool retry`, `/tool continue`, `/tool inject`)**:
  - Enhanced tool call extraction to recognize loose invoke syntax, XML tags (`<invoke="=" read_file">`), and functional formats without vendor adapters.
  - Added intelligent fallback in `/tool retry` to prevent false default assignments when parsing natural language completions.
  - Added `/tool continue` command to resume the agentic loop immediately after interactive tool rescues.
- **Database Management & Integrity Utilities (`/setdb`, `/dbprint`)**:
  - Added automatic rolling snapshot backups, taken lazily on first write (`/dblog`) per session to prevent churn on reads.
  - Added summary tables, range filtering, and CSV/JSON export capabilities to `/dbprint`.
  - Added `db_mgmt_util` integrity checker with test harnesses and fixtures.
- **Session Alias & Localization Enhancements**:
  - Added `/session new` alias for `/session start`.
  - Expanded multilingual keyword mapping (`append_mode`, `summary`, `retry`, `continue`, `inject`, `off`) across all 6 supported locales (EN, ES, FR, ZH, IT, AR).

September 13th, 2026 (v0.8.5)
----------------------------
- **Non-Destructive Session Query & Extraction Engine (`/session query`, `/session get`)**:
  - Added `/session query` command and `session_search` tool to search session turns, conversation history, notes, and scratchpad files with boolean AND/OR matching.
  - Implemented rich date range and timestamp constraints (`since=`, `until=`, `range=`) supporting relative expressions (`today`, `yesterday`, `7d`, `24h`) and date ranges (`2026-03-01..2026-05-01`).
  - Added fast discovery mode (`ids` / `--ids`) to return matched session IDs, and full-content mode (`full` / `--full`) to inspect unabbreviated exchanges.
  - Added `/session get` command and `session_get` tool for non-destructive, read-only extraction of prompts, responses, thinking blocks, or both (`turn=N` or `turn=all`) from past or active sessions without session switching or context pollution.
  - Added automated script variable assignment via `var=<name>` and protected variables `${SESSION_QUERY}` and `${SESSION_GET}`.
  - Implemented 3-tier session size caching (`_summary_cache`, lazy size evaluation during search, and per-query memoization) to report exact session storage sizes in bytes and formatted human units (`KB`/`MB`) with zero redundant disk reads.
  - Added dedicated `sessions` list to search responses with whole-session byte counts, eliminating turn-level size confusion.
- **Interactive Prompts & Agentic User Feedback (`/ask`, `ask_user`)**:
  - Added `/ask` command to prompt the user interactively (`yesno`, `choice`, `text`) and store answers into `${ASK_RESULT}` or custom variables with `-> VARNAME`.
  - Added `ask_user` tool enabling autonomous LLMs to pause and request clarifications or decisions during agentic tool loops.
  - Added non-interactive and background process detection to prevent freezing or `SIGTTIN` suspension in headless runs, batch pipelines, and cron tasks, returning structured skip status payloads to LLMs.
- **Multi-Format LLM Tool Call Normalization**:
  - Expanded tool call extraction to recognize 12 standard formats without vendor adapters: Anthropic/MCP XML tags (`<tool_use>`, `<invoke>`, `<call>`, `<tool>`), YAML key-value blocks, DeepSeek DSML, Kimi K2 instruction syntax, unquoted key JSON, and unescaped inner quote repair.
- **Clean Output Saving by Default (`/save`)**:
  - Refactored `/save` to strip `<think>`, `<thought>`, and `<thinking>` blocks by default, saving clean LLM outputs directly without leaking chain-of-thought traces.
  - Decoupled `/save` behavior from `app.show_thinking` so saved files are clean regardless of whether interactive thinking is displayed in the terminal.
  - Added explicit modifiers: `withthink` (or `raw`) to include thinking tags in saved files, and `nothink` (or `clean`) to explicitly exclude them.
  - Added full multilingual alias support (`conpensar`/`sinpensar`, `avecpenser`/`sanspenser`, `含思考`/`无思考`, `conpensare`/`senzapensare`, `مع_تفكير`/`بدون_تفكير`, `raw`/`crudo`/`brut`/`原始内容`/`grezzo`/`خام`).
  - Added single latest-turn fallback so `/save` succeeds even when `/session history off` is active in stateless benchmark scripts.
- **File Write Backup & Re-applicable Diff Preservation**:
  - `write_file` preserves a single initial full-copy backup of existing files before modification under `<session_dir>/<session_id>/backups/<relative_path>`.
  - `replace_file_content` computes and saves standard, re-applicable unified diff patches (`<session_dir>/<session_id>/diffs/<relative_path>.<timestamp>.patch`).
  - Configurable via `backup_file_on_write = true` in `tools_config.toml`.
- **Cookbook, Documentation & CLI Polish**:
  - Added Recipe 2.6 (*Interactive User Prompts with `/ask`*), Recipe 8.4 (*User Interaction During Tool Loops with `ask_user`*), and Recipe 10.6 (*Non-Destructive Session Query and Turn Extraction*) to `doc/chatdsl_cookbook.md`.
  - Configured `LESS="-R"` in `display_doc` so syntax-highlighted ANSI sequences render in full color on Linux terminals without escaping as `ESC[...]`.
  - Enforced 80-column terminal output standards across banners, tables, and session metrics.

September 8th, 2026 (v0.8.4)
---------------------------
- **Session Management & Filtering Automation**:
  - Added `${SESSION_IDS}` protected variable and `ids` compact flag to `/session list` for automated batch workflows and clean terminal display.
  - Added `since=` datetime filter (`<N>d`, `<N>h`, `<N>m`) with compounding `AND` logic to filter sessions by recency.
  - Added target variable support (`var=<name>`) for `/session list`, assigning flat string IDs when `ids` is present or full session objects otherwise.
  - Added protected variables `${TOOL_LIST}`, `${TOOL_HISTORY}`, `${TOOL_REPLAY}`, and `${REPLAY}` with `var=` support across tool and replay commands.
- **Cookbook & Documentation**:
  - Added Recipe 10.5 (*Session Filtering and Bulk Management with `foreach`*) to `doc/chatdsl_cookbook.md` and runnable script `doc/cookbook/10_5_session_management.chatdsl`.
  - Updated all multilingual documentation and guides to reflect v0.8.4 compatibility.

September 6th, 2026 (v0.8.3)
---------------------------
- **Time-Travel Context Replay (`/replay`, `/tool replay`)**:
  - Added interactive context replay engines to reconstruct and inspect the exact prompt/history arrays sent to LLMs at any turn (`/replay`) or agentic tool step (`/tool replay`).
  - Supported timeline overview (`summary`), specific turn inspection (`at <N>`), step-by-step interactive navigation (`step`), and turn-to-turn differential diagnostics (`diff <A> <B>`).
  - Added strict newly-evicted message tracking (`newly_evicted`), token delta calculation, and anchor overflow detection.
  - Optimized CLI execution with zero redundant disk reads by passing preloaded session turns into `SessionReplayer` and `AgenticReplayer`.
- **Context Limiting & Token Counting Enhancements**:
  - Optimized message eviction in `ContextLimiter.truncate_messages` from $O(N^2)$ to $O(N)$ via precomputed token caching and running sums during turn dropping.
  - Unified anchor partitioning logic (`ContextLimiter.partition_anchors`) across core truncation and verbose diagnostics.
  - Enforced strict token budget compliance after prepending truncation notices to prevent budget overruns.
  - Extended heuristic token counting to fully account for assistant `tool_calls` (function names + JSON arguments) and tool metadata (`name`, `tool_call_id`).
- **Context Command & Script Variable Resolution**:
  - Enhanced `/context` to support single-argument limit setting (`/context 10000`, `/context off`) and script variable resolution (`/context $my_limit`).
  - Included system prompt and non-empty file bank token breakdown in `/context` metrics output.
- **Cookbook Validation & Parser Hardening**:
  - Validated all 55 ChatDSL cookbook recipe scripts in `doc/cookbook/` with full parser compliance.
  - Integrated localized command alias resolution into `chatdsl_parse`.

September 3rd, 2026 (v0.8.2)
---------------------------
- **Agentic Scratchpad Area (`/tool scratch`)**:
  - Added dedicated temporary scratchpad area for models to create, test, and execute disposable Python/Bash scripts and scratch files without modifying project files.
  - Implemented `/tool scratch [on|off|clean|status|show]` commands with real-time prompt injection, clean purging, and file inventory.
  - Integrated session-scoped scratchpads (`~/.local/share/chatybot/sessions/<session_id>/scratch/`) with global fallback (`~/.local/share/chatybot/scratch/`).
  - Added ChatDSL profile integration (`/tool scratch on|off`) with persistence across session reloads.
  - Hardened path resolution against trailing slashes, relative paths, and wrapped prompt execution paths in quotes for safety with space-containing paths.
  - Added multi-language keywords for `scratch` and `clean` across all supported languages (ES, FR, ZH, IT, AR).
- **Environment & Multi-Platform Key Setup**:
  - Added interactive cross-platform API key setup wizard `chatybot-setup-keys` and CLI flag `chatybot --setup-keys`.
  - Added native setup scripts `bin/setup_keys.sh` (POSIX/macOS/Linux) and `bin/setup_keys.bat` (Windows with `setx` user registry persistence and double-click Explorer support).
  - Added `.env.example` template and updated `.gitignore` for security.
  - Centralized `.env` file loading and API key resolution in `src/chatybot/env_utils.py`, supporting `export ` prefixes, comments, quotes, nearest-project boundaries, and non-destructive global defaults (`~/.config/chatybot/.env`).
  - Hardened API key resolution against false positives for custom lowercase environment variable names.
- **Quick Start Documentation Revamp**:
  - Rewrote the Quick Start guide with a clear 3-step setup walkthrough, supported provider key reference table, and `/env` inspection verification.

September 1st, 2026 (v0.8.0)
---------------------------
- **PyPI Project URLs & Documentation Links**:
  - Pointed PyPI project metadata and README badges directly to the active `master` branch URLs, resolving 404 links.
- **Modular Command Registry Architecture**:
  - Decoupled monolithic command dispatcher in `chatybot_app.py` into dedicated domain modules under `src/chatybot/commands/` (`registry.py`, `context.py`, `tools.py`, `session.py`, `models.py`, `buffer.py`, `db.py`, `image.py`, `proc_macros.py`, `rerank.py`, `debug_misc.py`, `debug.py`).
  - Added structured command execution lifecycle (`CommandResult`, `CommandContext`) with domain routing, aliases, and isolated error handling.
  - Added comprehensive migration test suites (`test_command_registry.py`, `test_command_migration_phase2.py`, `test_command_migration_phase3.py`).
- **Session & Workflow Enhancements**:
  - Added `/chatdsl history` command to export, format, and codify active interactive session history directly into runnable ChatDSL automation scripts.
  - Persisted lightweight command execution verbs directly in `turns.jsonl` for full session replay fidelity and clean multi-turn provenance.
  - Added `/session name <alias>` subcommand and automatic startup command preservation during session creation.
- **Tool Handling & Unicode Output Normalization**:
  - Configured `ensure_ascii=False` for all tool execution payloads, file utilities, and model communication to cleanly render native Unicode characters and file paths.

August 31st, 2026 (v0.7.9)
-------------------------
- **Live Tool Prompt Editing & Restoration**:
  - Added `/tool prompt live_edit` (or `/tool prompt edit_live`) to open an interactive editor (`notepad`, `vi`, `$VISUAL`, `$EDITOR`) and live-customize tool context and agentic system instructions for the active session.
  - Added `/tool prompt restore` to instantly restore live system prompt overrides back to `tools_config.toml` defaults.
  - Added `restore` and `live_edit` keyword translations across all supported languages (EN, ES, FR, ZH, IT, AR) in `translations.json`.
  - Added `/tool max_turns <int>` command and documentation for configuring default maximum turns in automated tool loops (`/tool auto on`).
- **Tool Loop Robustness & Type Sanitization**:
  - Implemented recursive `sanitize_json_types` in `extract_tool_calls` normalizing Python `set`, `frozenset`, and `tuple` instances into JSON-compliant lists.
  - Replaced raw JSON serializers across `execute_tool_loop` with `safe_json_dumps` to prevent serialization crashes during logging, dispatching, and turn tracking.
  - Added unit test suite in `test/test_tool_loop_serialization.py`.
- **Rerank Evaluation Datasets**:
  - Added 30-dish culinary dataset in `10_foods.txt` and updated sparse context / reranking demonstration workflows.
- **Documentation & Localization Updates**:
  - Updated Command Reference, `/help` command metadata, and multi-language documentation guides in `doc/` to **v0.7.9+**.
  - Synchronized package version to **0.7.9** across `pyproject.toml`, `src/chatybot/__init__.py`, and startup banner.

August 28th, 2026 (v0.7.8)
-------------------------
- **`/prompt` Loading & Execution Security**:
  - Strictly unwrapped matched outer quotation pairs (`"..."` or `'...'`) for prompt file paths while rejecting mismatched quotes and preventing inner character mangling.
  - Added interactive confirmation and capped interactive prompt terminal previews to 500 characters with remaining character indicators to avoid terminal scrollback flooding on large files.
  - Added tilde expansion (`~`), explicit file existence checks, UTF-8 decoding, and empty / whitespace-only file rejections.
  - Hardened buffer lifecycle by preventing `prompt_buffer` leaks on read failures or user cancellations and cleaning up duplicate buffer clearing.
  - Documented interactive confirmation vs non-interactive script context auto-execution across ChatDSL guides and logged sentinel review in `open_issues.md`.
- **Pluggable Session Storage Architecture**:
  - Abstracted session persistence into pluggable storage engines (`BaseSessionStore`, `session_factory.py`) with configurable engines (`jsonl` vs `monolithic`).
  - Added high-performance JSONL engine (`meta.json` + `turns.jsonl`) eliminating quadratic write amplification on turn appends.
  - Implemented standalone CLI migration utility `bin/migrate_sessions` (`chatybot-migrate-sessions`) with `--dry-run`, backups, and selective migration.
  - Hardened session persistence with atomic `.tmp` merge operations, same-second collision loops (`_2`, `_3`), re-entrant thread locks (`RLock`), stale `.lock` auto-expiration (24h), and directory `mtime` metadata caching.
  - Added wildcard globbing to `/session compress` and `/session uncompress`, compression status filters (`/session list compressed|uncompressed`), and multi-model composite provenance attribution.
- **ChatDSL Cookbook & Recipe Suite**:
  - Published comprehensive task-oriented `doc/chatdsl_cookbook.md` with 52 standalone runnable recipes in `doc/cookbook/`.
  - Documented `/source` command (Recipe 10.3) for dynamic in-session script execution, companion `macro.chatdsl` auto-loading, and environment state retention.
- **Variable Scoping & Buffer Manager Hardening**:
  - Introduced `user_write()` context manager in `BufferManager` to permanently eliminate mutable `_is_user_write` flag leaks across `foreach`, `/script`, `/proc`, and `/setvar`.
  - Hardened `/setvar` name validation, overwrite protections, and alternate quoting syntax.
  - Unified `${arr}` prompt text rendering across native lists and JSON array strings.
  - Guarded array subscript parsing (`var[idx]`) against invalid JSON fallback substring indexing.
  - Preserved internal whitespace formatting in prompt placeholder substitution.
  - Silenced internal `set_script_var` writes while keeping interactive `/setvar` user feedback.
- **Localization (i18n) & Cross-Platform Fixes**:
  - Expanded key-value argument translation (`k=v`), session keywords (`uncompress`, `compressed`, `days`, `limit`, etc.), and help descriptions across all 6 locales (EN, ES, FR, ZH, IT, AR) in `localization.py` and `translations.json`.
  - Fixed Windows tool dispatcher subprocessing using `sys.executable` fallback.
  - Added Windows path normalization (`normalize_path`) handling double-escaped backslashes across file tools.
  - Synchronized package version to **0.7.8** across `pyproject.toml`, `src/chatybot/__init__.py`, and startup banner.

August 25th, 2026 (v0.7.7)
-------------------------
- **Windows Platform Compatibility**:
  - Added Windows conditional dependencies (`pyreadline3`, `windows-curses`) in `pyproject.toml`.
  - Added platform-conditional readline imports and safe calls in `chatybot_app.py`.
  - Added defensive curses imports and fallback instructions in TUI modules (`config_tui.py`, `profile_tui.py`, `profile_editor.py`).
  - Added Windows Python App Execution Aliases troubleshooting section to `README.md`.
- **Chat History Control & Agentic Guard**:
  - Added `enable_chat_history` toggle to configuration model, manager, and `chat_config.toml`.
  - Added `/session history [on|off]` command to inspect and dynamically toggle in-memory history collection.
  - Enforced policy guard preventing agentic tool loops when chat history collection is disabled.
  - Added test suite in `test/test_chat_history_flag.py`.
- **Tool Config TUI Manager**:
  - Added full curses-based interactive tool manager (`tool_config_tui.py`) for configuring tool timeouts, rate limits, turn limits, and enabling/disabling individual tools.
- **Localization & Version Synchronization**:
  - Added `history` keyword translations across all supported locales (EN, ES, FR, ZH, IT, AR) in `translations.json`.
  - Synchronized package version strings across `pyproject.toml`, `src/chatybot/__init__.py`, and runtime REPL startup banners to **0.7.7**.
  - Synchronized compatibility notices across multi-language documentation guides in `doc/`.

August 24th, 2026 (v0.7.6)
-------------------------
- **Documentation & Table Formatting**:
  - Restored clean Command Reference Markdown table rendering and moved the Concurrent Session Access warning into a dedicated **Session Management & Persistence** section under Advanced Features.
- **Meta Muse Glimmer & Reasoning Strength**:
  - Added reasoning strength support for Meta Muse Glimmer models via `/effort` (`low`, `medium`, `high`, `xhigh`) mapped to `extra_body.chat_template_kwargs.reasoning_strength`.
  - Added `/max_tokens` alias for `/maxtokens` across CLI, scripts, and localization catalogs.
  - Added native reasoning mode (`is_reasoning_model`) and `/effort` forwarding support for GLM 5.2 / GLM models across Mistral AI and custom OpenAI-compatible endpoints.
  - Synchronized package version strings across `pyproject.toml`, `src/chatybot/__init__.py`, and runtime REPL startup banners to **0.7.6**.
  - Synchronized compatibility notices across multi-language documentation guides in `doc/`.

August 23rd, 2026
-------------------------
- **Empty Assistant Payload Guard**:
  - Retained original past response content when stripping thinking tags from thought-only responses, falling back to `[No response content]` to eliminate Cohere API 400 validation errors.
- **Trace ImageDbg Profile Integration**:
  - Added `imagedbg` trace field to `Profile` model, presets, and ChatDSL parser/serializer.
  - Integrated `ImageDbg` trace option into `ProfileEditor` and `ProfileTUI` curses interfaces with layout alignment.
- **Trace & Loop Validation**:
  - Enhanced `/trace` command validation and TPS performance file handling to prevent second-based file collision.
  - Guarded interactive editor subprocesses during non-interactive `/debug payload` script execution.
  - Enhanced procedure redefinition warnings, loop break validation, and 3-part step syntax in `range()`.

August 22nd, 2026
-------------------------
- **Session Engineering & Path Optimization**:
  - Added atomic writes, session locking, initial model alias, turn model tracking, and metadata caching (`/session list`).
  - Streamlined session path resolution and added TOML validation for `session_mode` configuration.
  - Preserved source notes during `/session merge`.

August 21st, 2026
-------------------------
- **Database & Log Enhancements**:
  - Added thinking token awareness and reasoning metadata tracking to `/dblog`.
  - Improved search query rejoining, database name validation, sub-argument parsing, and hex mode formatting (`/logging`).
- **Config TUI Bulk Operations**:
  - Added bulk find-and-replace feature across endpoints and providers in Config TUI (`config_tui.py`).

August 20th, 2026
-------------------------
- **Parameter Controls & Logging**:
  - Added hex mode formatting to `/logging` to escape unprintable characters.
  - Added support for disabling `/top_k`, `/top_p`, `/temp`, and penalties.
  - Harmonized agentic tool loop turn reminders with natural language completion rules.

August 19th, 2026 (v0.7.3)
-------------------------
- **CLI Startup Flag (`--no-tools`)**:
  - Added `--no-tools` command-line option to disable tools on startup and bypass all MCP server initialization via stdio, while keeping internal tools available to enable dynamically during the session.
- **Release Version Synchronization**:
  - Synchronized package version strings across `pyproject.toml`, `src/chatybot/__init__.py`, and runtime REPL startup banners to **0.7.3**.
  - Synchronized compatibility notices and timestamps across all multi-language documentation guides in `doc/`.

August 18th, 2026
-------------------------
- **Shell Execution Mode Enhancements (`/run_unsafe`)**:
  - Configured default `/run_unsafe` to execute dangerous command patterns directly without interactive confirmation prompts for non-interactive scripting.
  - Added `/run_unsafe askfirst` (and `/run unsafe askfirst`) mode to prompt for user confirmation (`[y/N]`) before executing dangerous commands.
- **Environment & Key Inspector (`/env`)**:
  - Added dedicated `/env [filter]` command for inspecting active API keys and environment variables with optional case-insensitive substring filtering.
- **Hugging Face Model Preset**:
  - Integrated native Hugging Face vendor presets and endpoint configuration in `vendors.py`, `chat_config.toml`, and the Config TUI editor for models like DeepSeek-R1, Qwen 2.5, Llama 3.3, and SmolLM2.

August 16th, 2026
-------------------------
- **Configurable Context Limits & Auto-Truncation (`context_limit.py`)**:
  - Introduced `ContextLimiter` engine with token estimation heuristic (~4 bytes/token), warning triggers at 70% and 90% capacity, and turn/content auto-truncation.
  - Added `/context_limit [tokens|off]` command to set, inspect, or disable session token limits, plus model-level `context_limit` in `chat_config.toml`.
  - Added `/auto_truncate [on|off|10-100]` command to toggle or configure truncation thresholds.
  - Dynamically refreshed tool system prompt preambles and instructions whenever context limits change.
  - Reported context limits and remaining token budgets in `get_context_metrics` and tool context.
- **Permanent Capability Error Guard & Auto-Disabling**:
  - Implemented `_is_permanent_capability_error()` in `chatybot_app.py` to detect unrecoverable protocol/capability errors (such as unsupported MCP client elicitation or missing RPC methods).
  - Implemented automatic dispatcher-level tool disabling (`self.tool_overrides[tool] = False`) to prevent infinite LLM retry loops upon permanent errors.
  - Added diagnostic `[TOOL USAGE HINT]` to `calculate` in `math_utils.py` distinguishing scalar math operators from list/array statistical operations.
  - Added `sys_default` profile (`sys_default.chatdsl`) prompting the agent to prefer writing temporary Python/bash scripts in `/tmp` via `run_command` over multiple separate tool turns.
- **Rate Limit Delay Configuration**:
  - Added `/tool rate_limit <seconds>` with runtime caching and per-turn delay calculations in the agentic loop.
- **Session List Filtering & Sorting (`/session list`)**:
  - Added sorting by `updated_at` descending (most recently active first).
  - Added model filtering: `/session list model=<alias>`.
  - Added pagination options: `/session list limit=10`, `/session list range=start:end`, and `/session list all`.
  - Added `since=` age filter: `/session list since=7d`, `since=24h`, `since=30m`. Filters to sessions updated within the given window. Compounds as AND with all other filters.
- **Multilingual Support (i18n) & Documentation**:
  - Expanded `translations.json` across all 6 supported locales (EN, ES, FR, IT, ZH, AR) for new v0.7.0+ commands and context budgeting.
  - Updated all language-specific ChatDSL documentation guides in `doc/`.

August 15th, 2026
-------------------------
- **Partial File Reading**:
  - Extended `read_file` in `src/chatybot/tools/file_utils.py` with `start_line` and `end_line` parameters for ranged line filtering.
- **Memory Diagnostic Help Updates**:
  - Updated `/mem` help and inspection with detail and debug options.

August 14th, 2026
-------------------------
- **Context Metrics Tool (`get_context_metrics`)**:
  - Introduced `get_context_metrics` native tool to inspect live session context usage, prompt token counts, and agentic loop payload size.
- **Tool Payload Safety Limits**:
  - Added soft warnings (at 30KB) and hard truncation safeguards (at 50KB) for tool execution outputs to protect against runaway context bloat.
- **Agentic Loop Turn Tracking**:
  - Counted agentic loop turns in total turn count and clarified context summary reporting.

August 13th, 2026
-------------------------
- **Documentation & Milestone Updates**:
  - Updated `README.md` key features, command reference, and change log with recent commit milestones.

August 11th, 2026
-------------------------
- **Startup & Boot Performance Optimizations**:
  - Deferred Parsley macro PEG grammar compilation into lazy accessors, deferring parser overhead until macros are expanded.
  - Lazy-loaded `EasyRerank` and `mcp` SDK imports inside respective command and execution handlers, cutting cold boot time by **~45% to 60%** (~900ms saved).
- **Macro Discovery & Management (`/listmacros`)**:
  - Added `/listmacros [filter]` command rendering a clean formatted table of available macros, parameter signatures, and template summaries with keyword search filtering.
  - Added an interactive macro coding and execution tutorial to `/help macro` and `/help /listmacros`.
- **Package Version Synchronization**:
  - Aligned internal version strings across `__init__.py` and startup banners with PyPI version 0.7.0.

August 7th, 2026
------------------------
- **Multilingual Session Localization**:
  - Localized `/session` subcommands, arguments, notes, and keywords across all supported target languages (Spanish, French, Chinese, Italian, Arabic).

August 3rd - 4th, 2026
------------------------
- **Session Workspace Management Suite**:
  - Added comprehensive workspace commands: `/session info` (workspace size, turn counts, file stats), `/session delete <name|id|all>`, `/session merge <target> <s1> <s2>` (with automatic source notes consolidation), `/session compress [days|all]` (gzip compression), and `/session prune [keep=N] [days=D] [size=M]`.
  - Added session annotation notes (`/session note <text>`) capped at 1024 characters, displayed in session metadata without consuming LLM context tokens.
  - Auto-generated prompt slugs derived from Turn 1 for session auto-naming.
  - Fixed variable permissions by passing `allow_protected=True` when updating `RUN_*` and `LAST_COMPLETION` system variables.

August 2nd, 2026
------------------------
- **Session Persistence Engine (`/session`)**:
  - Introduced conversation session persistence (`/session start`, `/session auto [on|off]`, `/session stop`, `/session save`, `/session list`, `/session use`, `/session show`).
  - Added Markdown transcript exporting (`/session export <file.md> [-t]`) with optional `<thought>` block inclusion.
  - Multi-turn conversation context continuity: automatically injects prior session turns into chat completion payloads.
- **Pattern Search Command (`/str_search`)**:
  - Added `/str_search "<pattern>" <text_var> [flags] [dest_var]` for fast substring pattern matching in text variables with count (`c`), match position indices (`m`), and case-insensitivity (`i`) flags, exporting to protected `${STR_SEARCH}`.
- **Enhanced Conditional Expressions**:
  - Added greater-than (`>`), less-than (`<`), `>=` and `<=` relational operator support for `if ... then` blocks.

July 30th - 31st, 2026
------------------------
- **Procedure Definition Engine (`defproc` / `/proc` / `local`)**:
  - Added reusable procedure blocks with argument passing and execution via `/proc <name> param1="val"`.
  - Implemented stack-frame snapshotting for isolated `local var = value` scoping and recursion depth guards.
- **Multiline Iteration & Generators (`foreach`)**:
  - Added multiline `foreach <var> in <iter>` loop construct supporting arrays, `range(start, end[, step])`, and `lines("file.txt")` generators.
  - Added `break` statement support to exit loops early while maintaining variable scope restoration.
- **Profile TUI Editor**:
  - Built interactive curses-based Profile Manager (`chatybot --profile-edit` / `/profile edit`) with validation, preset creation, and field length protection.

July 26th, 2026 (v0.7.0)
------------------------
- **Model Context Protocol (MCP)**: Native integration for hosts supporting stdio-based MCP servers with robust session/lifecycle management.
- **Multilingual localization (i18n)**: Out-of-the-box support for Spanish, French, Chinese, Italian, and Levantine Arabic. Localizes help systems, REPL banners, goodbye exit lines, and supports cross-locale command alias resolution and script pre-translation.
- **Math Evaluation Engine**: Features the `/calc` escape command and an interactive LLM calculation tool powered by custom precedence and Decimal coercion patches.
- **Command Verb Validation**: Revamped prompt validation to safely identify unquoted/unescaped leading command verbs regardless of the active language, preventing accidental LLM traffic.
- **Documentation**: Localized ChatDSL technical guides in Arabic, Chinese, French, Italian, and Spanish.

July 16th, 2026 (v0.6.4)
------------------------
- **Virtual Memory Monitoring**: Implemented a background daemon thread that logs process memory metrics (`VmSize` and `VmRSS`) at 1-second intervals.
- **Cross-Platform Compatibility**: Added Linux-native `/proc/self/status` support, fallback to `psutil` on other systems, and macOS/Darwin physical footprint tracking (`proc_pid_rusage` via `ctypes` system calls).
- **Interactive Debug Commands**: Introduced the `/debug vmem <start|stop|status>` escape command to control the monitor state, log locations, and query live memory usage.
- **Dedicated Log Files**: Outputs metric captures with millisecond-resolution timestamps to dedicated log files (`chatybot.vmem.<timestamp>.log`).
- **New replace_file_content Tool**: Packaged a new built-in system tool to replace specific target string blocks within files.
- **Help System & Test Integration**: Integrated commands into `/help /debug`, CLI auto-complete, and verified correctness with the `test/test_vmem.py` test suite.

July 12th, 2026 (v0.6.3)
------------------------
- **Automatic Configuration Synchronization**: Implemented `config_sync` utility which automatically merges packaged TOML default configurations into user configuration directories on startup.
- **Deep Merging & Settings Preservation**: Supports recursively merging new model definitions and tools while fully preserving existing user customizations (like customized timeouts or disabled tools).
- **Graceful Error Handling & Idempotency**: Detects and reports syntax/decode errors in configurations without silently overwriting user customizations, and runs at most once per file path per process.
- **Verification Testing**: Created unit tests under `test_config_sync.py` and a functional mockup demo in `scratch/test_config_sync_mock.py` to verify config merge behavior.

July 9th, 2026 (v0.6.2)
-----------------------
- **Dynamic Tool Management**: Implemented `/tool list`, `/tool enable <tool>`, and `/tool disable <tool>` to dynamically control available agentic tools during a session.
- **Strict Context Syncing**: Ensured that LLM prompt context is strictly synchronized and regenerated on any runtime tool state change and loop execution.
- **Environment Enforced Tool Override**: Integrated environment variable verification (`CHATYBOT_TOOL_OVERRIDES`) in subprocess execution to prevent disallowed tools from executing.
- **Tool Execution Safeguards**: Added parallel tool call limits (`max_tool_calls_per_turn` config support) and handled excess tool calls gracefully. Added execution enhancements and payload debugging logging.
- **Agentic Loop Metrics & Logging**: Saved detailed execution logs and metrics to the `AGENTIC_LOOP` script variable, and added step-by-step logging to `execute_tool_loop`.
- **System Tooling Expansion**: Added a built-in `change_dir` tool, default shell command support for `run_command`, and safety checks to reject binary files in `read_file`.
- **ChatDSL Variable Enhancements**: Automatically cleared undefined script variables to empty string instead of retaining syntax placeholders.
- **Comprehensive Integration Testing**: Created `test21_tool_management.chatdsl` to validate all runtime overrides, enable/disable actions, context syncing, and dispatcher enforcement.

July 1st, 2026 (v0.6.1)
-----------------------
- **User-Level Configuration Path**: Copied and loaded `tools_config.toml` from `~/.config/chatybot/` for pip installations to prevent read-only directory issues.
- **Auto-Trigger Agentic Tool Loop**: Implemented the new `/tool auto [on|off]` subcommand to automatically run the agentic tool loop upon detecting tool calls, featuring custom streaming chunk reconstruction support.
- **Semicolon Command Chaining**: Enabled chaining multiple escape commands and prompts on a single line separated by semicolons (`;`) via a new centralized `execute_line` execution helper. Supports CLI `--run` option command lists.
- **Startup Profile Scripting**: Added a `--profile <script>` CLI option and `/source <script>` escape command to execute scripts in the current interactive session without exiting, with a new `default_profile` config setting.
- **JSON Parsing Auto-Repair**: Upgraded the JSON extractor to handle raw newlines inside quote literals, ignore `#` or `//` comment characters within quotes, and automatically repair unbalanced JSON output payloads cut off mid-turn.
- **New Built-in write_file System Tool**: Registered a new system tool `write_file` supporting both write and append operations.
- **Refined Agentic Prompts**: Updated system prompt instructions and `tools_config.toml` defaults to prevent eager tool usage on general knowledge queries.
- **Configurable Turn Limit**: Added a configurable `max_turns` limit parameter (default 25) to `tools_config.toml` under `[config]` for the auto-loop and `/tool loop`.

June 28th, 2026 (v0.6.0)
------------------------
- **Command Help System Expansion**: Updated the global `/help /tool` command definitions to fully document `/tool loop` subcommands including turn limits (`max`, `max=val`) and the `force` override parameters.
- **ChatDSL Integration & Verification**: Validated and verified `/run` and `/tool` commands within `.chatdsl` scripts, adding robust unit tests for script parser compatibility, variable scoping, and conditional evaluations.
- **Advanced Documentation Overhaul**: Detailed local shell execution (`/run`), autonomous tool loops (`/tool`), and `tools_config.toml` structure in the main README.

June 27th, 2026
---------------
- **Empty API Content Response Resolve**: Handled API response validation and mapped native `tool_calls` structures to prevent "empty content" parse issues for models like `devstral-2512`.
- **Parallel Tool execution & Timeout Prevention**: Supported multiple parallel tool call extraction/execution and added configurable trace thinking exclusion parameters to prevent transient timeouts.
- **Rate Limit Delay Configuration**: Introduced rate limit delays configurable via `tools_config.toml` and applied them to the autonomous tool loop.

June 24th, 2026 (v0.5.5)
------------------------
- **Interactive Escape Command Variable Resolution**: Enabled resolving variables and subscripts inside interactive escape commands (e.g. `/filebank1 ${arr1[0]}`).
- **Quotes and Equals Sign Stripping**: Standardized interactive `/setvar` to automatically strip surrounding single/double quotes and leading `=` signs from scalar values, matching DSL script behavior.
- **Improved Quote Documentation**: Documented variable quote alternating rules and why the escape character `\` is forbidden in the README.

June 20th, 2026 (v0.5.4)
------------------------
- **Version Bump**: Updated to v0.5.4 to support native array integration and metadata-aware database search.
- **Native Array & Subscript Syntax**: Implemented dynamic array declaration (e.g. `set arr[] = [...]`) and bracket-based subscripts (e.g. `arr[0]`) in `ScriptVars`.
- **Extended Metadata DB Search**: Refactored `search_db` in `chatydb.py` to recursively match queries in metadata keys/values (dicts, lists) in addition to name/content.
- **Memory Diagnostic CLI**: Enhanced `/mem debug` with clean object representation, dynamic sizing, and variable type auditing.
- **Testing Expansion**: Added dedicated unit test files `test_arrays.py` and `test_chatydb.py`.

June 18th, 2026 (v0.5.3)
------------------------
- **Version Bump**: Updated to v0.5.3 to support stateless multiline boundary behavior.
- **State-Based Multiline Mode**: Replaced legacy `/multiline` toggle-off requirement with a deterministic, auto-exiting `;;` boundary parser.
- **Legacy Bypass Lookahead**: Added parser lookahead inside scripts and deferred check state in the interactive REPL to silently bypass legacy trailing `/multiline` toggles.
- **Deprecated Token Reporting**: Logged warning messages when legacy `/multiline` toggles are bypassed.
- **Double Semicolon Tokenization**: Enhanced character-level parser to treat `;;` as a standalone command token.

June 15th, 2026 (v0.5.2)
------------------------
- **Version Bump**: Updated to v0.5.2 to reflect new configuration management features.
- **Config Utility Views**: Added comprehensive TUI-based configuration management with pycurses.
- **Enhanced /help**: Integrated structured help system with keyword filtering and command deep-dives.

June 14th, 2026 (v0.5.1)
------------------------
- **Config Data Model**: Introduced `config_model.py` with Pydantic v2 models for structured configuration management. Supports chat models, reranker models, and image generation settings with full TOML validation.
- **Config TUI**: Added curses-based terminal UI (`config_tui.py`) for interactive configuration management. Features include:
  - Browse, filter, and select models
  - Add new models with vendor presets (Mistral, Google, OpenAI, OpenRouter, NVIDIA, PublicAI, Bytez, Ollama, Llama.cpp, Jina)
  - Clone existing models as templates
  - Edit model parameters (temperature, top_k, etc.)
  - Delete models
  - Save configuration to file
- **Vendor Presets**: Added `vendors.py` with predefined vendor configurations for quick model setup.
- **Config Save Feature**: Enhanced save functionality in Config TUI to support saving as new files.
- **Pycurses Design**: Initial TUI design implementation with comprehensive documentation in `config_tui_design.md`.

June 5th, 2026
--------------
- **License Format**: Updated LICENSE to SPDX format for better compatibility and standardization.

June 4-5th, 2026 (v0.5.0)
-------------------------
- **Debug Response for Rerank**: Added `/debug response` and `/debug response raw` integration for `/rerank` which outputs raw JSON lists of the final resolved result set, avoiding intermediate batch spam.
- **Cohere Rerank Support**: Configured Cohere's Reranker v3.5 via OpenRouter in `chat_config.toml`.
- **Conrad book testing**: Created and validated `test_conrad_full_c.chatdsl` to test Cohere reranking.

June 3rd, 2026
--------------
- **Batched Top-N pre-filtering**: Integrated EasyRerank's batched Top-N processing for massive directory files to prevent context exhaustion.
- **Limit Scaling**: Enabled execution limits scaling (`max_limit` up to 700) to support processing the entire Gutenberg book *Chance* (~14,000 lines).

June 2nd, 2026
--------------
- **Sparse Context Injection**: Created `test_sparse_injection.chatdsl` showcasing sparse context injection workflow.
- **Filebank Document Source**: Supported `filebank` as a document source type (`filebank<1-5>`) in `/documents`.
- **Parameter Enhancements**: Handled both `item=` and `items=` parameters and standardized split types.

June 1st, 2026
--------------
- **EasyRerank 0.2.0 Integration**: Upgraded routing and document loading. Added support for chunking by lines and paragraphs (`split=line` and `split=paragraph`).

May 17th, 2026 (v0.4.4)
----------------------
- **Smart Thought Saving**: Upgraded the `/save` command to automatically respect the `/thinking` toggle state by default, stripping `<think>` and `<thought>` blocks when `/thinking` is `OFF`.
- **Custom Stripping Modifiers**: Added `nothink` and `withthink` parameters to `/save` to allow force-stripping or force-including thinking blocks on demand.
- **Thought Standardisation**: Wrapped all raw streaming and non-streaming thinking and reasoning chunks in standardized `<think>...</think>` tags in conversation history.
- **Improved UX**: Documented the new `/save` command options in `/help` and added descriptions to the README command list and command tables.

May 16th, 2026 (v0.4.3)
----------------------
- **Enhanced Chat History Export**: Added `{CHAT_HISTORY}` placeholder to `/setvar` for JSON chat history export and added the `all` parameter to the `/save` command.
- **Improved UX**: Added `/exit` as a natural alias for `/quit`.
- **Documentation Overhaul**: Fixed markdown formatting issues in the command table and established a dedicated **Known Issues** section.

May 1st, 2026 (v0.4.2)
----------------------
- **Mistral Thinking Support**: Added support for Mistral's structured reasoning format (list of thinking/text blocks) in both streaming and non-streaming modes.
- **Reasoning Effort**: Introduced the `/effort <low|medium|high|none>` command to control reasoning effort for supported models (Mistral, OpenAI o1/o3).
- **Prompt Execution Fix**: Improved `/prompt` execution logic to avoid duplicate prompts and clear the buffer after execution.

Apr 28th, 2026 (v0.4.1)
--------------
- **Hotfix**: Added missing `image_manager.py` module and declared explicit `aiohttp` requirement in dependencies.

Apr 28th, 2026 (v0.4.0)
--------------
- **Image Support (Beta)**: Officially designated text-to-image generation and vision analysis as Beta features.
- **Test Stability**: Resolved brittle test assertions and isolated test execution environments.
- **Image Generation Configuration**: Synchronized `chat_config.toml` with local additions (mistral_pixtral, elephant models) and updated flux_1 to flux.2-klein-4b
- **OpenRouter Size Fix**: Resolved Google model image generation error by mapping pixel sizes to K-based format (1024x1024→"1K") when manually set via `/imagesize`
- **Hybrid Size Handling**: Implemented smart size handling that skips `image_config` for Google models when using default size
- **Echo Command Bug Fix**: Fixed `'tuple' object has no attribute 'startswith'` error by unpacking tuple from `replace_placeholders()`
- **Memory & History**: Added CHAT_HISTORY to `/mem` display, enabled `/dump CHAT_HISTORY`, added `/save <file> all` for full chat history export
- **Documentation**: Updated `/help` text to clarify `/setvar` is for text-only variables, added Image Generation section to README, documented image bank requirements for vision models
- **Test Assets**: Added 15 test images with corresponding .txt files containing `subject:` and `color:` for accuracy testing, created comprehensive `accuracytest.chatdsl` script

Apr 14th, 2026 (v0.3.0)
--------------
- **Parsley Macro System**: Integrated a robust macro expansion system using Parsley grammars.
- **Macro Definitions**: Supports `def name(params) = "template"` syntax with multi-parameter support.
- **Macro Invocations**: Use `%name(args)` to expand templates in prompts and scripts.
- **Variable Integration**: Macro arguments support `${variable}` substitution.
- **Packaging**: Relocated `macro.chatdsl` to the package source and updated `pyproject.toml` to include it in distribution.
- **Dependencies**: Added `parsley` as a core dependency.

Apr 5th, 2026 (v0.2.9)
--------------
- **New Thought Styles**: Added `nanbeige` and `nanbeige_code` thought styles for specialized prompt formatting.
- **Nanbeige Style**: Implements `<think> </think>` wrapping with response-only instructions for concise answers.
- **Nanbeige Code Style**: Implements `<think></think>` wrapping with code-only instructions for minimal commentary code generation.
- **Documentation**: Updated help text and documentation to clarify thought style usage and model quirks.
- **Command Enhancement**: Updated `/thoughtstyle` help to describe it as "prompting format for negative prompt to disable reasoning - auto".

Apr 1st, 2026 (v0.2.8)
--------------
- **Command Validation**: Added a safety check to detect command verbs sent without an escape character (e.g., `help`, `model`) at the start of a prompt, preventing unintentional LLM calls.
- **Improved Responsiveness**: Reduced wait times by quickly identifying invalid command usage.
- **PyPI Release**: Bumped version for publication to PyPI and synchronized startup display.

Mar 31st, 2026 (v0.2.7)
--------------
- **ChatDSL Parser CLI**: Added `chatdsl_parse` as a standalone executable script.
- **Exit Codes**: Updated `chatdsl_parse` to return 0 on success and 1 on parse Failure/Exception.
- **Packaging**: Integrated `chatdsl_parse` into `pyproject.toml` console scripts.

Mar 20th, 2026 (v0.2.6)
--------------
- **Apostrophe Recognition**: Resolved a critical bug where apostrophes in natural language (e.g., "Assyria's") were misinterpreted as opening quotes, incorrectly merging commands.
- **Robust Path Capture**: Enhanced `/save`, `/prompt`, and `/file` handlers to support filenames with spaces by capturing the entire command remainder.
- **Substitution Integrity**: Fixed a regression that caused variable substitution regexes to be double-escaped, ensuring `${varname}` tokens are correctly replaced.

Mar 19th, 2026 (v0.2.5)
--------------
- **New Command `/echo`**: Implemented direct stdout printing with full variable substitution and automatic quote stripping.
- **Multiline Variable Support**: Enabled the `set` command to capture values spanning multiple lines when wrapped in quotes.

Mar 16th, 2026
--------------
- **Advanced Logic**: Significantly expanded `if-then` logic to support full string comparisons (`==`, `!=`) and logical negation (`not`).
- **Parameterized Scripts**: Updated `/script` to allow passing inline variables (e.g., `/script file.chatdsl x="value"`).
- **Security Sanitization**: Added a safety check to disallow escape characters (`\\`) within `set` variable assignments.
- **Test Infrastructure**: Added test data, `CHATDSL_TECHNICAL_GUIDE.md`, and `civil_war_1865.chatdsl`.

Mar 15th, 2026 (v0.2.4)
--------------
- **Database Enhancements**: Added `/dbprint` command to generate high-quality formatted reports of database contents.
- **Improved Logging**: Enhanced `/dblog` to capture the original prompt and detailed model metadata (name and alias) for better analysis.
- **Qwen Support**: Added explicit reasoning control for Qwen (SiliconFlow) models via the `/reasoning` command.
- **Documentation**: Updated ChatDSL BNF and technical specifications.

Mar 5th, 2026 (v0.2.3)
----------------------
- **Bug Fixes**: Fixed `SEARCHBUFFER` reference issue by mutating the list in-place, ensuring visibility across modules for `/mem` and `/dump`.
- **Maintenance**: Version bump for PyPI release.

Mar 5th, 2026 (v0.2.2)
----------------------
- **Bug Fixes**: Fixed `/savevar` and `/loadvar` to correctly use the buffer manager's variable storage.
- **Enhanced Debugging**: Added `SEARCHBUFFER` visibility to `/mem` and `/dump` commands.
- **Maintenance**: Removed redundant script variable attributes from the main application class.

Mar 5th, 2026 (v0.2.1)
----------------------
- **Testing**: Added test suite and increased coverage of dsl_test.
- **Variable Substitution**: Update to substitution for variables.

Mar 3rd, 2026
-------------
- **Variables**: Updated variable substitution in set statement.

Mar 2nd, 2026
-------------
- **Cleanup**: Removed sonnet test data and test fruit directory.
- **Fixes**: Corrected nanjing chatdsl.

Feb 27th, 2026
-------------
- **Bug Fixes**: Fixed temperature command to use instance variable, fixed `/listmodels` command formatting, and fixed SEARCHBUFFER issue in `search_db`.
- **Database Features**: Added database commands to refactored version.
- **Documentation**: Removed emojis from documentation and consolidated dates.
- **Complete OOP Refactoring**: Comprehensive architectural overhaul from procedural to object-oriented design:
  - Created ConfigManager class for centralized configuration management
  - Created LoggingManager class for logging functionality
  - Created BufferManager class for buffer and variable management
  - Created ChatybotApp class as main application orchestrator
  - Simplified main.py to be just an entry point
  - Applied OOP best practices: encapsulation, single responsibility, composition
  - Maintained all existing functionality while improving code structure
  - Added comprehensive test suite and detailed refactoring documentation
  - New architecture provides better maintainability, testability, and extensibility

Feb 26th, 2026
--------------
- **Tracing & Debugging**: Added new `/trace` command options:
  - `/trace rawpayload on`: Dumps the raw JSON string passed to the LLM completion API.
  - `/debug payload`: Captures the payload that would be sent to the LLM API, opens it in your system editor for modification, then sends the modified payload to the API and displays the response.
  - `/trace tps on`: Calculates and outputs think tokens and regular tokens per second.
  - `/trace tpsperf on`: Logs an in-memory bucketed tokens per second calculation, saved out to a quoted CSV on completion.

Feb 24th, 2026
--------------
- **Version 0.1.2 Release**: Preparation and package bumping for PyPI publication.
- **Enhanced Reasoning Display**: Added support to natively color and display `<think>` tags embedded within standard content streams (e.g., `nanbeige` or local Ollama usage).
- **Backend Model Extractor Fixes**: Updated the openai dependency requirement to `>=1.61.0` and added fallbacks to capture both `reasoning_content` and `reasoning` delta fields for wider compatibility.
- **System Commands Optimization**: Fixed a bug where `/system` would truncate inputs after the first word, properly capturing full multi-word system prompts.

Feb 22nd, 2026
--------------
- **Packaging and Distribution**: 
  - Restructured into `src/chatybot` module for PEP 517 compliance. 
  - Added `pyproject.toml` enabling rapid `pip install` globally across the path via console script `chatybot`.
  - Migrated configuration files and databases from the active working directory into persistent `~/.config/chatybot/` and `~/.local/share/chatybot/` locations.
  - Built graceful config fallbacks and a cleanup script for straightforward deployments.
- **Model Compatibility**:
  - Added dummy API key bypass logic for testing with local `localhost`/`Ollama` server endpoints natively.
  - Expanded `/reasoning off` toggle support to also apply to Qwen (2.5/3) reasoning models.

Feb 17th, 2026
--------------
- **Enhanced Database Control**: Added `/setdb Null` to deactivate database support dynamically.
- **Advanced `/loadvar`**: Now supports `ALL`, specific `id`, and `range` (e.g., `1-5`) for the database items.
- **Improved Usability**: Added shebang to `chatybot.py` for direct execution.

Jan 25th, 2026
--------------
- **LLM Parameter Tuning**: Added commands for `/seed`, `/top_k`, `/top_p`, `/freq_penalty`, and `/pres_penalty`.
- **NVIDIA Reasoning**: Added `/reasoning <on|off>` to toggle detailed thinking for NVIDIA models.
- **Debugging Suite**: New commands `/mem` and `/dump` for inspecting buffer sizes and variable contents.
- **Database Management**: Added `/dblist` to view available TinyDB files.
- **Provider Stability**: Improved compatibility for Mistral, Google Gemini, and Bytez APIs.

Jan 24th, 2026
--------------
- **TinyDB Integration**: New database module (`chatydb.py`) for persistent storage.
- **Persistent Search Buffer**: `/searchdb` results are cached in `SEARCHBUFFER`.
- **Variable Linking**: `/loadvar` now bridges database results to `${variable}` placeholders.
- **Prompt Injection**: All prompts now support `${variable}` substitution for dynamic context.
- **Manual Variables**: Added `/setvar` for setting session variables via the CLI.
- **Database Logging**: `/dblog` allows one-click archiving of AI responses to the active database.

Jan 10th
-------------

  - added /notemode - this will split code from explanation.  but only first block.

   Warning:  should not be used for markdown, readme or other such docs.

```
===========================
Active model: mistral-large-2512 (alias: mistral_1)
chat --> /model nvidia_1
Switched to model: nvidia/nemotron-nano-12b-v2-vl:free (alias: nvidia_1)
chat --> create a C program that demonstrates a linked list
Here's a well-structured C program that demonstrates the implementation and usage of a **singly linked list**. This program includes basic operations such as:

- **Appending** elements to the end of the list.
- **Printing** the contents of the list.
- **Freeing** the memory allocated to the list to prevent memory leaks.

---

### C Program: Demonstrating a Singly Linked List

```c
#include <stdio.h>
#include <stdlib.h>

.............

This program provides a solid foundation for understanding and working with linked lists in C. You can expand upon it to implement more complex data structures or algorithms.


Execution time: 28.95 seconds
Input tokens: 29, Output tokens: 2509
chat --> /notemode on
Note mode enabled. Code blocks will be extracted when using /save.
chat --> /save demo_link_list.c
Last chat completion saved to 'demo_link_list.c'.
Note mode is ON. Processing file 'demo_link_list.c'...
Processed demo_link_list.c -> notes_demo_link_list.c

```

The demo_link_list.c should be a raw C file.  the notes_ prefix has all the notes

```
-rw-r--r--  1 jon2allen jon2allen  1.6K Jan 10 16:24 demo_link_list.c
-rw-r--r--  1 jon2allen jon2allen  1.6K Jan 10 16:24 notes_demo_link_list.c
```
       

  - enhanced logging - when logging is enabled 

```
Datetime: Jan 10, 2026, 04:11:42 PM 
Model: nvidia_1 (nvidia/nemotron-nano-12b-v2-vl:free)
User: create a bash program that uses cat for all programs with *.py extension in a subdir

Execution time: 50.25 seconds
Number of tokens: Input 37, Output 3971
Assistant: Here's a well-structured Bash script that uses the `cat` command to display the contents of all `.py` files located in a specified subdirectory. The script is designed to be flexible, robust, and user-friendly.
```
