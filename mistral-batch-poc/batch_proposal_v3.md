# Batch API Subsystem Proposal — v3

**Status:** Proposal v3 — **Phase 1 implemented** (branch `batch_api`, 2026-10-29; see §4.9 for the as-built delta)  
**Scope:** OpenRouter Batch API and Mistral Batch API only  
**Proof of concept & Live Spike:** Validated live on 2026-10-28 (see §2)  
**Supersedes:** `batch_proposal_v2.md` and `batch_proposal_v1.md`  

---

## 0. Changes from v2

| # | Change | Where |
|---|---|---|
| 1 | **Idiomatic model selection:** `/model <alias>` is specified on its own line matching all ChatyBot recipes, verified against `chat_config.toml` (`batch = true`) | §4.1, §4.3 |
| 2 | **`/batch prompt` replaces `/batch task`:** aligns with prompt engineering; supports inline prompt strings, named templates, or external prompt files (`file=path`) | §4.2, §4.3 |
| 3 | **Idiomatic `key=value` parameters for `/batch add`:** replaces Unix-style `--flags` with ChatyBot-standard parameters (`filebank=1 split=lines`, `var=name`, `id=custom_id`, `file=path`) | §4.3 |
| 4 | **`/batch dump <name> [var=<name>]`:** formats the JSON request payload for inspection and automatically binds it into a script variable (default `${BATCH_PAYLOAD}`) for ChatDSL scripts | §4.3, §4.4 |
| 5 | **Auto-generated sequenced IDs:** automatic zero-padded item IDs (`batch_0001`, `fb1_line_0001`) with collision prevention and client-token prefixing for orphan recovery | §4.3, §4.4 |
| 6 | **Live spike facts integrated:** OpenRouter `Idempotency-Key` omission and `metadata` stripping confirmed; native `usage.cost` (exact USD) and `provider` host telemetry recorded directly | §2, §3, §4.7 |
| 7 | **Complete ChatDSL Walkthrough:** Recipe 14.11 added to showcase the idiomatic end-to-end automation sequence | §5 |
| 8 | **Storage & Historical Tracking (Option 1):** Dedicated directory per batch instance + global `index.jsonl` catalog; completely decoupled from session data with conversational history disabled | §4.4 |
| 9 | **`/batchlist` Global Catalog Command:** First-class `/batchlist` (and `/batch list`) command with rich filtering modeled after `/session list` (`limit=`, `all`, `ids`, `range=`, `model=`, `status=`, `since=`, `here=`, `var=`) and automatic population of `${BATCH_LIST}` and `${BATCH_IDS}` | §4.3, §4.4 |
| 10 | **Manifest Locking & Post-End Ingestion Rules:** `/batch add` after `/batch end` refuses with clear reopen instructions (`/batch start <name>`) to preserve security inspection and manifest synchronization; submitted batches are strictly immutable | §4.3, §4.4 |
| 11 | **Draft Inspection & Stream Manipulation:** REPL and script sub-commands to list, inspect, edit, remove, and reset items in the open staging draft (`/batch items`, `/batch ids`, `/batch show <id>`, `/batch edit <id>`, `/batch remove <id>`, `/batch clear [name]`, `/batch status`) | §4.3 |

---

## 1. Motivation

ChatyBot treats batch inference as a first-class subsystem alongside interactive chat, image generation (`/imagine`), and reranking (`/rerank`). Batch jobs outlive the prompt cycle that creates them, requiring persistent state and a clean lifecycle (stage → inspect → submit → poll → retrieve).

Core use cases: bulk translation, document summarization, dataset classification, evaluation scoring, and multi-model benchmark runs — all at 50% discount off standard token pricing.

---

## 2. What We Validated (Proof of Concept & Live Spike)

All experiments run in `mistral-batch-poc/` within the workspace:

| File | Role |
|---|---|
| `poems.py` | 10 Du Fu poems (Chinese source text + titles) |
| `run_batch_openrouter.py` | Working runner: submit → poll → retrieve via OpenRouter Batch API |
| `check_results.py` | Structural validation + side-by-side pinyin/English eyeball review |
| `spike_openrouter_batch.py` | Live architectural probes: list schemas, metadata persistence, idempotency deduplication |

### The Translation Run
- **Model:** `openai/gpt-oss-120b:batch` via `POST https://openrouter.ai/api/v1/batches`
- **Ingestion:** single-call inline array (`endpoint`, `model`, then `requests` in strict stream order).
- **Results:** 10/10 completed (0 failed). Prompt ~198–246 tokens, completion ~928–1955 tokens.
- **Actual Billed Cost:** `$0.002051105` (reported directly in `usage.cost`).
- **Quality:** Tone marks accurate, line counts consistent, English faithful.

### Live Spike Results (`spike_openrouter_batch.py`, 2026-10-28)
1. **Idempotency-Key Header [spike-validated]:** Duplicate submissions with identical `Idempotency-Key` headers created two distinct batches (`...8787` vs `...8791`). OpenRouter does **not** deduplicate batch POSTs. The pre-POST local sidecar write (`status = "submitting"`) is **strictly mandatory**.
2. **Metadata Omission [spike-validated]:** OpenRouter returned HTTP 202 for top-level `"metadata": {...}`, but `GET /batches/{id}` silently omitted the field. Server-side metadata cannot be used for OpenRouter reconciliation.
3. **List & In-Progress Visibility [spike-validated]:** List items and in-progress batch records return `"results": null`. Request `custom_id`s are not queryable until completion. In-flight orphan reconciliation must follow heuristic-plus-confirm (§4.4 rule 3).
4. **Exact Cost & Provider Telemetry [spike-validated]:** Completed batch objects return `"provider": "DeepInfra"` and `"usage": {"cost": 0.002051105}`. Exact billed USD cost is known at completion without post-hoc estimation math.

---

## 3. Provider Notes: OpenRouter vs Mistral

| Dimension | OpenRouter | Mistral |
|---|---|---|
| Ingestion | Single-call inline `requests` array in one JSON body | Dual-path: file upload (`POST /v1/files`) or inline (<10,000 items) |
| Capacity | ~200 MB request ceiling | Up to 1,000,000 requests (file) / 10,000 (inline) |
| Model field | Job-level, must be `:batch` variant slug | Job-level; per-request optional |
| Statuses | `validating` → `in_progress` → `finalizing` → `completed` / `failed` / `expired` / `cancelled` | `QUEUED` → `RUNNING` → `SUCCESS` / `FAILED` / `TIMEOUT_EXCEEDED` / `CANCELLED` |
| Counters | `request_counts.total / completed / failed` | `total_requests / completed_requests / succeeded_requests / failed_requests` |
| Results | Inlined in `GET /batches/{id}` (`results` array) | Via Files API (`output_file` / `error_file` jsonl) |
| **List endpoint** | `GET /api/v1/batches` (list items omit results: `results: null`) **[spike-validated]** | `GET /v1/batch/jobs` with metadata filtering **[web-validated]** |
| **Job metadata** | Accepted with 202, but silently dropped; omitted from batch record **[spike-validated]** | Custom key-value `metadata` assignable at creation **[web-validated]** |
| **Idempotency** | Unsupported for batch creation; duplicate headers make duplicate jobs **[spike-validated]** | Not documented **[unverified]** |
| **Cancellation** | **No cancel endpoint — submitted batches always run to completion or expire within 24h [web-verified 2026-10-29]**; `/batch cancel force=true` marks cancelled locally only | To be verified in Phase 2 |
| **Cost Telemetry** | Exact billed `usage.cost` (USD) and host `provider` populated in batch object **[spike-validated]** | Token counts returned in response; cost calculated from rates |
| Retention | 30 days, then 410 Gone | Until client deletes via Files API |
| Pricing | 50% discount off standard token rates | 50% discount across batch endpoints |

---

## 4. Proposed Architecture & Idiomatic ChatDSL Design

### 4.1 Model Selection (`/model`)

Model selection is strictly decoupled and written on its own line, matching standard ChatyBot convention:

```chatdsl
/model gptoss_batch
```

In `chat_config.toml`:
```toml
[models.gptoss_batch]
provider = "openrouter"
model = "openai/gpt-oss-120b:batch"
batch = true

[batch]
default_model = "gptoss_batch"
max_cost_usd = 5.00
max_open_per_provider = 3
keep_remote_files = false
```

- When `/batch start` is invoked, it validates that the current `/model` (or default) has `batch = true`.
- If an interactive chat model lacks batch capabilities, ChatyBot refuses with an informative message pointing to available batch aliases.
- **Mode semantics (identical to image/audio):** `/model` is a mode switch. While a batch-capability model is selected, non-batch operations (interactive chat, `/imagine`, ...) error until the user selects an appropriate model. Conversely, scripts that select a batch model leave the session in batch mode when they end — switch back with `/model <chat-alias>` if the session continues interactively (see final step of the §5 walkthrough).

---

### 4.2 Batch Prompt (`/batch prompt`)

Instead of abstract "tasks", batches are driven by **prompts**:

```
/batch prompt <"inline prompt" | template_name | file="path">
```

1. **Inline Text:**
   `/batch prompt "Translate each poem into faithful English and pinyin with tone marks."`
2. **Named Template (Built-in or User Task):**
   `/batch prompt translate`
3. **External Prompt File:**
   `/batch prompt file="prompts/legal_summary.txt"`

The prompt sets the system role instruction and JSON contract applied across all items in the batch.

---

### 4.3 Command Surface & `key=value` Syntax

```
/batch [status]                                 view active batch draft status and item count
/batch start <name> [model=<alias>] [temp=] [max_tokens=] [top_p=] [clear=true]  open (or reopen a draft) staging session
/batch add <text | filebank=N | var=NAME | ...> append an item to the staging file
/batch items [name] [ids] [limit=N] [range=...] list staged items with previews / filter
/batch ids [name] [var=<target>]                list bare item IDs in draft & export to variable
/batch show <id>                                inspect full payload of a single staged item
/batch edit <id> <text | var=NAME | file=PATH>  in-place update of an item in the open draft
/batch remove <id>                              remove an item from the open draft (alias: /batch del)
/batch clear [name]                             reset staged items back to 0 (alias: /batch reset)
/batch clone <src> <new> [prompt=...] [model=]  duplicate a batch into a new editable draft
/batch prompt <"text" | template | file=path>   set the batch instruction template
/batch dump <name> [var=<name>]                 inspect JSON payload & bind to script variable
/batch end                                      inspect items, validate schema, lock manifest
/batch abort                                    discard open staging session
/batch run [name]                               estimate cost, confirm budget, submit job
/batch check [name] [wait=true]                 poll status / retrieve results (wait=true blocks until terminal)
/batch results [name] [limit=N] [var=<name>]    print retrieved completions (paginated) & export ${BATCH_RESULTS}
/batch retry <name>                             new batch containing only failed/invalid items
/batch list [filters...]                        alias for /batchlist (see filtering below)
/batchlist [filters...]                         global catalog query with rich session-like filters
/batch cancel <name> [force=true]               cancel in-flight batch (force=true: local-only when the provider cannot cancel)
```

#### Item Ingestion Details (`/batch add`)
* **Auto-generated IDs (Default):** If `id=` is omitted, ChatyBot automatically assigns sequenced IDs:
  - Direct adds: `<batch_name>_0001`, `<batch_name>_0002`...
  - From filebank: `fb1_line_0001`, `fb1_line_0002`...
  - From script variable: `<var_name>_0001`, `<var_name>_0002`...
* **Explicit ID:** `/batch add id=chunwang "国破山河在..."` (warns on collision).
* **Multi-Item Ingestion:**
  - `filebank=1 split=lines` (or `split=paragraphs`, or `split=none` to keep a whole multi-line variable/string as ONE item)
  - `var=my_array` (ingests every element of a ChatDSL array variable)
  - `file="data/corpus.txt" split=lines`

#### Behavior When `/batch add` is Called After `/batch end`
When `/batch end` is executed, it runs the security/secret scan, compiles `staging.jsonl` into the final provider payload `requests.json`, and locks the staging manifest (`status: staged`).

1. **If the batch is staged (before `/batch run`):**
   - ChatyBot **strictly rejects** direct `/batch add` calls. Allowing silent appending would cause `staging.jsonl` and `requests.json` to desync and allow uninspected items to bypass the security scanner.
   - User receives an informative error with recovery steps:
     ```text
     Error: Staging session is closed. Batch 'dufu_run' is locked (status: staged).
     • To append more items: run '/batch start dufu_run' to reopen the draft, add items, then '/batch end'.
     • To submit current batch: run '/batch run dufu_run'.
     ```
   - **Reopen Workflow:** Running `/batch start <name>` safely transitions the state back from `staged` to `draft`, appends the new items to `staging.jsonl`, and requires another `/batch end` to re-scan and re-lock the manifest.

2. **If the batch was already submitted (`submitting`, `submitted`, `in_progress`, `completed`):**
   - The batch instance is **strictly immutable**.
   - `/batch add` immediately refuses:
     ```text
     Error: Batch 'dufu_run' has already been submitted (status: in_progress). Submitted batches cannot be modified. Start a new batch with '/batch start <new_name>'.
     ```

#### Draft Inspection & Stream Manipulation in REPL
In active draft sessions, developers can inspect, edit, or prune staged items prior to sealing and submission:

1. **Listing Items with Content Previews (`/batch items`):**
   ```bash
   /batch items [name] [limit=10] [range=0:20]
   ```
   Outputs sequenced lines with index, custom ID, and a truncated first-line preview:
   ```text
   [Staged Items: dufu_run (5 items, status: draft)]
     #1  fb1_line_0001   "國破山河在，城春草木深..."
     #2  fb1_line_0002   "感時花濺淚，恨別鳥驚心..."
     #3  fb1_line_0003   "烽火連三月，家書抵萬金..."
     #4  fb1_line_0004   "白頭搔更短，渾欲不勝簪..."
     #5  chunwang_vip    "春望: 國破山河在..."
   ```

2. **Listing Bare IDs (`/batch ids`):**
   ```bash
   /batch ids [name] [var=<target>]
   ```
   Outputs bare IDs suitable for copy-paste or piping, and automatically exports the ID array to `${BATCH_ITEM_IDS}` (or custom `var=<target>`).

3. **Inspecting a Single Item (`/batch show <id>`):**
   ```bash
   /batch show chunwang_vip
   ```
   Displays the full text payload, character count, and origin metadata of that specific item.

4. **In-Place Item Editing (`/batch edit <id>`):**
   ```bash
   /batch edit chunwang_vip "春望: 國破山河在，城春草木深... (corrected text)"
   /batch edit fb1_line_0002 var=corrected_prompt
   ```
   Replaces the item's payload in `staging.jsonl` matching `<id>`. If `<id>` does not exist, an error is reported.

5. **Removing an Item (`/batch remove <id>` or `/batch del <id>`):**
   ```bash
   /batch remove fb1_line_0004
   ```
   Deletes the item from `staging.jsonl` and decrements the draft item count.

6. **Resetting Items to Empty (`/batch clear` or `/batch reset`):**
   ```bash
   /batch clear [name]
   ```
   Empties `staging.jsonl` to 0 bytes and resets item counts to 0, keeping the model and prompt configuration active in `draft` mode. Can also be invoked during start via `/batch start <name> clear=true`.

* **Immutability Guarantee:** `/batch clear`, `/batch edit`, and `/batch remove` are strictly confined to `draft` mode (or reopened drafts). Once `/batch run` dispatches the batch, modifications are permanently locked.

#### Payload Inspection & Variable Binding (`/batch dump`)
* Prints the formatted JSON request body that will be submitted to the provider.
* Binds the JSON string directly into a script variable:
  - Default: `${BATCH_PAYLOAD}`
  - Custom: `/batch dump dufu_run var=my_payload`
* In ChatDSL, this allows downstream scripts or `/run` shims to inspect, validate, or count items before calling `/batch run`.

---

### 4.4 Storage Architecture, Historical Tracking & Session Decoupling (Option 1)

#### 1. Complete Decoupling from Session Data (Session History Disabled)
- **Why:** A batch job is an asynchronous, bulk background task (often 100 to 10,000+ items). Treating batch items as conversational turns would pollute the chat session, blow up the active context window, and break conversational continuity.
- **Engine Rule:** When executing `/batch` commands, conversational session history recording is **completely bypassed** (`skip_history = True`). `app.chat_history` is untouched. Batch operations dispatch via direct HTTP clients (`POST /batches`) rather than the conversational LLM turn loop (`generate_response`).

#### 2. Directory Layout: Dedicated Instance Folder + Global Index
All batch data is stored under `~/.local/share/chatybot/batches/` (colocated with session data), structured as an isolated instance directory per job with a lightweight global catalog:

```
~/.local/share/chatybot/batches/
├── index.jsonl                               # Global catalog for instant /batchlist
└── btch-1793231-dufu_run/                    # Dedicated directory per batch instance
    ├── meta.json                             # Job metadata, model, timestamps, status, exact cost
    ├── staging.jsonl                         # Append-only inputs flushed per line during /batch add
    ├── requests.json                         # Built OpenRouter request payload (written at /batch end)
    └── results.jsonl                         # Canonical local results (one record per custom_id,
                                              # stored in staging order — providers return results
                                              # in arbitrary completion order; custom_id is the join key)
```

#### 3. Instance Metadata (`meta.json`)
```json
{
  "batch_id": "btch-1793231-dufu_run",
  "provider_id": "batch-1793231171-ucvR8ZAAoDIE4WUCmRII",
  "name": "dufu_run",
  "provider": "openrouter",
  "host_backend": "DeepInfra",
  "model": "openai/gpt-oss-120b:batch",
  "prompt": "Translate each Chinese poem into pinyin and English.",
  "status": "completed",
  "item_count": 10,
  "created_at": 1793231171,
  "finalized_at": 1793231953,
  "cost_usd": 0.002051105,
  "workspace": "/home/jon2allen/github2/chatybot"
}
```

#### 4. Global Catalog Querying: `/batchlist` (Mirrors `/session list`)
A dedicated command `/batchlist` (and `/batch list`) queries `index.jsonl` using the identical filter syntax established in `/session list`:

```
/batchlist [all] [ids] [limit=N] [range=start:end] [model=<filter>] [status=<filter>] [since=<Nd|Nh|Nm>] [here=true] [var=<target_var>]
```

| Parameter | Type / Example | Description |
|---|---|---|
| `limit=N` | `limit=10` | Number of batch records to display (default: 10) |
| `all` | keyword | Remove limit and display all batches in history |
| `ids` | keyword | Display or export only batch ID strings |
| `range=start:end` | `range=0:5`, `range=10:` | Slice pagination across the catalog |
| `model=<alias>` | `model=gptoss_batch` | Filter by model alias or substring |
| `status=<status>` | `status=completed`, `status=in_progress` | Filter by batch lifecycle status (`draft`, `staged`, `submitting`, `submitted`, `in_progress`, `completed`, `failed`, `submit_failed`, `cancelled`, `expired`) |
| `since=<time>` | `since=7d`, `since=24h`, `since=30m` | Time window filter using standard `d` (days), `h` (hours), or `m` (minutes) |
| `here=true` | keyword | Filter batches launched from the current active workspace directory |
| `var=<varname>` | `var=my_batches` | Export the resulting batch records or IDs into script variable `<varname>` |

**Automatic Protected Variable Exports:**
Just as `/session list` exports `${SESSION_LIST}` and `${SESSION_IDS}`, every invocation of `/batchlist` automatically exports:
- `${BATCH_LIST}`: list of matched batch metadata dictionaries.
- `${BATCH_IDS}`: list of matched batch ID strings.

#### 5. Deep Inspection & Management
- Deep inspection (`/batch check <id>` or `/batch show <id>`) loads the specific `meta.json` and `results.jsonl` from that batch's isolated folder.
- Deleting or archiving historical runs is clean and non-destructive: removing `btch-xxx/` and pruning its entry from `index.jsonl` leaves all other batches untouched.

#### 6. Crash-Safe State Machine
```
[draft] ──(/batch end)──> [staged] ──(/batch run pre-fsync)──> [submitting]
                                                                     |
   +-----------------------------------------------------------------+
   v
[submitted] --(poll)--> [in_progress] --(poll)--> [completed]
   |                        |                     |   (writes results.jsonl &
   +----------+-------------+                     |    records usage.cost)
              v                                   v
      [submit_failed]               [failed | expired | cancelled]
              |                                 |
              +--------(/batch retry)-----------+
                (new batch from failed/invalid items)
```

1. **Pre-POST Fsync:** `meta.json` is written with `status = "submitting"` and fsynced **before** the network socket opens.
2. **Provider terminal states** (`failed`, `expired`, `cancelled`) are terminal locally as well; `completed` is the only success exit. All three feed `/batch retry`, which builds a new linked batch from the failed/invalid items.
3. **Reconciliation Rules (§4.4 Rule 3):**
   - **Mistral:** Match `client_token` in provider metadata.
   - **OpenRouter:** Heuristic match (creation window + model + count) presented to user for confirmation.

---

### 4.5 Content Security & Secret Inspection

- At `/batch end`, every staged item runs through ChatyBot's Secret Scanner and Security Engine.
- If an API key, private credential, or blocked pattern is detected, staging locks and identifies the offending `custom_id`.
- Unresolved security hits cannot be submitted.

---

### 4.6 Cost & Concurrency Guards

1. **Pre-submit Estimate:** `(input_tokens + max_tokens) × batch_rate`. If above `max_cost_usd` ($5.00 default), `/batch run` refuses unless `force=true`.
2. **Concurrency Cap:** Maximum 3 open batches per provider. Refuses if cap is reached.
3. **Exact Telemetry on Retrieval [spike-validated]:** OpenRouter populates `usage.cost` ($0.00205...) and `provider` directly on completion. ChatyBot records these exact figures in the batch's `meta.json` and the global `index.jsonl` catalog — never the session store (see §4.4 session decoupling).

---

### 4.7 Phasing

| Phase | Scope | Effort | Status |
|---|---|---|---|
| 0 (POC) | Standalone Python scripts validating OpenRouter inline batch | hours | **Done** |
| 0b (Spike) | Live API probes for idempotency, metadata, and schemas | ~2 hours | **Completed (2026-10-28)** |
| 1 | Native `commands/batch.py` + `batch_manager.py`: `/model`, `/batch prompt`, `/batch start/add/end/dump/run/check`, `filebank` & `script_var` resolution, OpenRouter backend | 2–3 days | **Implemented & live-validated (branch `batch_api`, 2026-10-29; 136 tests in test/test_batch_api.py + config-tui + help suites)** |
| 1b (post-impl) | Hardening & usability from live OpenRouter runs and external review: `/batch results` + completions in `/batch show`; item-ID batch resolution; `/batch clone` (with overwrite guard); sampling parameters (temp/max_tokens/top_p/penalties) with per-item cost guard; provider-aware cancel (OpenRouter has none — force=true local-only); staging-order result normalization; empty-completion surfacing in check/status/results/batchlist; `/trace rawpayload` coverage; config-TUI batch flag; per-subcommand option parsing; crash-safety regression tests | — | **Completed (2026-10-29, see §4.9 delta table)** |
| 1c (validation) | End-to-end ChatDSL validation: `dsl_test/10_recipes_test.chatdsl` (unique run tags, split=none staging, wait=true polling, var persistence) and cookbook recipe `doc/cookbook/14_11_batch_api_blank_retry.chatdsl` (blank-completion detection + selective item retry) — both validated against the live API (10/10 completed, 2 empty completions observed and handled) | — | **Completed (2026-10-29)** |
| 2 | Mistral backend (Files API, dual ingestion, metadata reconciliation; `supports_cancel` flag to be verified per §3) | 1–2 days | Next |
| 3 | `/batch retry` (error records AND status-200 empty completions — see §4.9 row 15), background asyncio poller, model comparison. Note: the manual retry pattern is already documented and scriptable via `/batch clone` + recipe 14.11 | 1–2 days | Future |

---

### 4.8 Integration Points (per Command-Verb Skill)

- New module `src/chatybot/commands/batch.py` registered via the decorator registry.
- Canonical verb `/batch` registered in `translations.json` `aliases` for all languages; sub-keywords (`start`, `prompt`, `add`, `end`, `dump`, `run`, `check`, `retry`, `list`, `cancel`, `abort`) in `keywords` with localized equivalents.
- Register `/batch` in PatternMatcher and `VALID_ESCAPE_COMMANDS` in `chatdsl_parse.py`.
- Documentation in `chaty_help.py` (`CommandHelp`) and a cookbook recipe `doc/cookbook/14_11_batch_translation.chatdsl`.

---

### 4.9 Phase 1 Implementation Delta (as built, 2026-10-29)

Phase 1 shipped on branch `batch_api` with the following deviations from and
extensions to the sections above, all hardened by post-implementation review
(each with regression tests in `test/test_batch_api.py`):

| # | Topic | Spec (§) | As implemented |
|---|---|---|---|
| 1 | Cancellation | §4.3 | Provider-aware: OpenRouter has no cancel endpoint, so `/batch cancel` refuses informatively and `force=true` marks the batch cancelled locally only; `/batch check` no longer polls locally-cancelled batches. Mistral (Phase 2) uses the `supports_cancel` provider flag |
| 2 | Batch model binding | §4.1 | `/batch start` stamps the batch's model (including a `model=<alias>` override validated for `batch = true`); `/batch run`, `check`, and `cancel` operate on the batch's own model, so they work after the user switches the active chat model back |
| 3 | Sampling parameters | new | `temperature`, `max_tokens`, `top_p`, `frequency_penalty`, `presence_penalty` on `/batch start` and `/batch clone` (model-config defaults inherited at creation only, never on reopen); emitted into every per-request body, `None` omitted so provider defaults apply |
| 4 | `/batch clone <src> <new>` | new | Copies items + config into a fresh editable draft; `prompt=`/`model=`/sampling overrides; refuses to overwrite an existing draft/staged batch of the same name unless `force=true` |
| 5 | `/batch results [name]` | new | Paginated completion display (`limit=`, `range=`); binds the full record list to `${BATCH_RESULTS}` or `var=`; `/batch show <item-id>` renders input + retrieved completion, resolving the batch from the item ID across any status (name-only form shows the batch overview) |
| 6 | Cost guard | §4.6 | Estimate uses the batch's own `max_tokens` (falling back to the model config's) and prices the system prompt once per item |
| 7 | Name lifecycle | §4.3/§4.4 | In-flight batch names are refused; terminal (completed/failed/cancelled) names are reused as fresh timestamped instances — names are no longer permanently burned |
| 8 | Explicit ID collisions | §4.3 | Refused (not just warned) to preserve results.jsonl integrity |
| 9 | `/batch check` | §4.3 | Single poll by default; `wait=true` blocks with 10s→60s backoff until terminal |
| 10 | Option parsing | §4.3 | Per-subcommand option keys, so free text in `/batch add`, `/batch prompt`, `/batch edit` never loses tokens that look like another subcommand's options |
| 11 | Crash safety | §4.4 | The pre-POST sidecar write verified in the raw index log (`draft → staged → submitting → submitted`); orphan reconciliation via `/batch run <name> adopt=<provider_id>` |
| 12 | Raw payload tracing | new | `/trace rawpayload on` and `CHATYBOT_TRACE_RAW_PAYLOAD` cover batch requests (Authorization masked) and responses |
| 13 | Config TUI | new | The `batch = true` model flag is editable in the config TUI (model form, bulk replace, hidden for non-chat types) |
| 14 | Result ordering | §4.4 | Batch providers execute the queued requests in parallel and return results in arbitrary COMPLETION order, not submission order. ChatyBot normalizes `results.jsonl` (and `/batch results`) back into staging order; downstream consumers should still join by `custom_id`, never by position |
| 15 | Empty completions | new | Providers count status-200 empty completions as successes and never retry them (web-verified 2026-10-29: the gpt-oss family has documented empty-output bugs on third-party hosts). The count is stored as `empty_results` in meta/index and surfaced by `/batch check`, `/batch status`, `/batch results`, and `/batchlist`; Phase 3 `/batch retry` should treat these as failed items alongside error records |

Also as implemented: `/batch ids` exports `${BATCH_ITEM_IDS}`; the `[batch]`
config table ships in `chat_config.toml` with `gptoss_batch` placed last so a
batch-only model never becomes the default active model; batch commands are
registered in the PatternMatcher and ChatDSL `VALID_ESCAPE_COMMANDS`; the
cookbook recipe is `doc/cookbook/14_10_batch_api_translation.chatdsl` (named
`batch_api_*` to distinguish provider Batch APIs from batch-n in `/rerank`).

---

## 5. Walkthrough: Idiomatic ChatDSL Automation (Recipe 14.11)

```chatdsl
# Recipe 14.10 - Batch API Ingestion & Execution Pipeline (batch_api)
# Run: /script doc/cookbook/14_10_batch_api_translation.chatdsl

# 1. Select the batch-capable model (separate line)
/model gptoss_batch

# 2. Set the batch system prompt
/batch prompt "Translate each Chinese poem into pinyin with tone marks and faithful English."

# 3. Open the staging manifest
/batch start dufu_run

# 4. Ingest corpus from Filebank 1 (splits by line, auto-generates IDs)
/filebank1 data/poems_short.txt
/batch add filebank=1 split=lines

# 5. Add an extra priority item from a script variable with a custom ID
/setvar special_poem "春望: 国破山河在，城春草木深。感时花溅泪，恨别鸟惊心。"
/batch add id=chunwang var=special_poem

# 6. Close staging & execute security scan
/batch end

# 7. Dump generated JSON payload & store in script variable
/batch dump dufu_run
# Payload is printed and stored in ${BATCH_PAYLOAD} for verification

# 8. Submit to OpenRouter (writes pre-POST sidecar, verifies budget ceiling)
/batch run dufu_run

# 9. Poll progress & retrieve completed results
/batch check dufu_run

# 10. Restore the interactive chat model (session was left in batch mode)
/model mistral_1
```

---

## 6. Test Plan

1. **Command Syntax & Localization:**
   - Verify `/batch prompt`, `/batch dump`, `/batch add filebank=1 split=lines`, `/batch add var=foo`.
   - Test sub-keyword translations and unescaped verb lint warnings.
2. **Item ID Sequencing:**
   - Test auto-generation (`fb1_line_0001`, `dufu_run_0001`).
   - Test explicit ID collision warnings.
3. **Payload Dump & Variable Binding:**
   - Verify `/batch dump` displays JSON and binds `${BATCH_PAYLOAD}` and `${dufu_run_payload}`.
4. **Crash-Safe Pre-POST Submission:**
   - Simulate process kill between `submitting` sidecar write and HTTP POST; verify orphan reconciliation.
5. **Cost Guard & Exact Telemetry:**
   - Test budget refusal above `$5.00`; test storage of exact `usage.cost` upon retrieval.
