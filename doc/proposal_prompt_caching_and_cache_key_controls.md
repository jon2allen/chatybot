# Technical Proposal: Multi-Vendor Prompt Caching & `prompt_cache_key` Optimization Controls

**Document Version:** 1.6  
**Date:** October 26, 2026 (rev. 1.6: §8 consolidated as-built implementation differences; feature implemented and tested. rev. 1.5: structured system prompt blocks, compaction cache-miss dynamics, [default] TOML config, dblog schema, /trace cache flag, /cachekey reset synonym)  
**Status:** Implemented (tests: `test/test_prompt_caching.py`; full suite green)  
**Applies To:** `ChatybotApp`, `chat_completion()`, `ConfigManager`, ChatDSL commands (`/cachekey`), Telemetry (`/dblog`, `/trace`), and Model Providers (Mistral, OpenRouter, OpenAI, Anthropic, DeepSeek, Google Gemini, and local vLLM/Ollama engines)

---

## 1. Problem Statement & Motivation

During multi-turn conversations, autonomous tool execution loops, and document-heavy retrieval (RAG), Chatybot resends extensive context to the model provider on every turn:
1. **Accumulated Conversation History:** In sessions spanning 10–30+ turns, prior dialogue history is repeatedly transmitted.
2. **Tool Definition Payloads:** Detailed JSON schemas for native tools (`read_file`, `run_command`, `write_file`) and external MCP servers are serialized into the request body on every turn.
3. **Reference Context & Documents:** Content injected from `/file`, `/filebank`, or codebase searches is resent across multiple follow-up prompts.

Without prompt caching, the remote LLM must re-read, tokenize, and recalculate Key-Value (KV) attention tensors for the entire prefix from scratch on every single turn. This produces two major penalties:
- **Financial Cost:** Input tokens dominate LLM expenses; recalculating static history wastes 50%–90% of token spend.
- **Latency & Time-to-First-Token (TTFT):** Processing tens of thousands of prefix tokens causes noticeable multi-second response lags before token generation begins.

Prompt caching allows model providers to store computed KV states in GPU memory or fast storage. However, **different LLM providers implement prompt caching using radically different paradigms**:
- Some require an explicit identifier string (e.g. Mistral's `prompt_cache_key`).
- Some require in-payload breakpoint markers (e.g. Anthropic's `cache_control`).
- Some perform automatic prefix caching without any parameters, provided the prompt prefix is byte-stable (e.g. OpenAI, DeepSeek, Google Gemini, and local vLLM/Ollama).

This proposal specifies a unified, provider-aware prompt caching architecture for Chatybot that provides automatic session-bound caching out of the box, programmatic ChatDSL control, and universal cache telemetry across all supported vendors.

---

## 2. Multi-Vendor Landscape Analysis

Prompt caching in modern LLMs falls into three architectural categories:

```
                            Prompt Caching Paradigms
                                       │
     ┌─────────────────────────────────┼─────────────────────────────────┐
     ▼                                 ▼                                 ▼
[Explicit Cache Key]        [Explicit Breakpoints]          [Automatic Prefix Caching]
   Mistral AI                 Anthropic (Claude)               OpenAI (GPT-4o, o1, o3)
   (via prompt_cache_key)     (via cache_control blocks)       DeepSeek (V3, R1)
                                                               Google Gemini (Auto)
                                                               Local (vLLM, Ollama)
```

### 2.1 Mistral AI (Explicit `prompt_cache_key`)
- **Mechanism:** The client passes an explicit top-level string `prompt_cache_key` (e.g., `"chatybot-sess-1234"`).
- **Behavior:** The API server groups requests sharing the same key. If a new request shares the prefix of an earlier request with that key, the KV cache is reused. Per Mistral's documentation, the key **increases the chance of a cache hit but does not guarantee one** — a hit occurs only when the API finds a compatible cached prefix for the request.
- **Economics:** Cached tokens are billed at **~10% of the standard input price** (~90% discount).
- **Latency:** Instantaneous prefill for cached turns.

### 2.2 OpenRouter (Multi-Vendor Proxy & Native Sticky Routing)
- **Mechanism:** OpenRouter proxies requests across underlying hosts (Mistral, Anthropic, OpenAI, DeepSeek, etc.).
- **Sticky Routing via `session_id`:** Passing a `session_id` string (via the request body parameter `session_id` or `x-session-id` header) activates OpenRouter's native sticky routing starting on request #1. OpenRouter pins the conversation to the same backend provider and host instance. This eliminates cross-provider hop jitter during multi-turn chats or agentic tool loops, which would otherwise invalidate KV caches.
- **Cache Key Fallback:** If `prompt_cache_key` is passed, OpenRouter also honors it and falls back to using it as the sticky routing key.
- **Normalized Breakpoints:** OpenRouter accepts normalized cache breakpoints across providers (e.g., `cache_control: {"type": "ephemeral"}` or `prompt_cache_breakpoint`) and converts them to upstream provider specifications.
- **Reporting:** OpenRouter standardizes cache reporting across all upstream models in `response.usage.prompt_tokens_details` (`cached_tokens` and `cache_write_tokens`).

### 2.3 OpenAI (GPT-4o, GPT-4o-mini, o1, o3, o3-mini)
- **Mechanism:** **Fully Automatic Prefix Caching (Implicit).**
- **Requirements:** Prompts must be $\ge 1,024$ tokens. OpenAI automatically matches prefixes in 128-token increments. No custom header or key is required.
- **Economics & Cache-Write Surcharges:**
  - **Cache Reads:** 50% discount on cached tokens (e.g. $1.25/M vs $2.50/M on GPT-4o).
  - **Cache Writes:** Cache writes are billed at a surcharge based on retention tier: **1.25×** base input price for standard 30-minute retention, or **2.5×** for extended 12-hour retention.
  - **Telemetry:** OpenAI reports both `cached_tokens` and `cache_write_tokens` under `usage.prompt_tokens_details`. Net savings calculations must account for the write surcharge during cache-warming requests.
- **TTL:** 5–10 minutes of default inactivity (sliding window), up to 30 minutes / 12 hours depending on tier.
- **Explicit Breakpoints (optional, not used by Chatybot):** Newer OpenAI models also support explicit `prompt_cache_breakpoint` markers and `prompt_cache_options` (including `prewarm`). Chatybot relies on implicit caching only and does not emit these markers.

### 2.4 Anthropic (Claude 3.5 Sonnet, Claude 3.7 Sonnet, Claude 3 Haiku)
- **Access path:** Chatybot reaches Anthropic models **exclusively via OpenRouter**; no direct `api.anthropic.com` vendor is supported. Anthropic's OpenAI-compat endpoint does not reliably honor `cache_control` injection, and the native Messages API is out of scope for the OpenAI-client code path.
- **Known Gap (acknowledged):** The design below places breakpoints only on the **last tool definition and the system prompt**. Because automatic prefix providers cache the entire message prefix but Anthropic only caches up to the last `cache_control` marker, **conversation turns themselves are never cached for Claude models**. On a 30-turn conversation this is where most tokens live, so Anthropic savings will be materially lower than Mistral/OpenAI savings for history-heavy sessions. Adding a further breakpoint on the last (or second-to-last) message is a possible future improvement but is **out of scope for v1**: it must respect Anthropic's 4-breakpoint budget, interacts awkwardly with compaction/truncation (a moving breakpoint must be recomputed every turn), and mutating per-turn message tails risks breaking prefix stability for the system+tool segment that *is* cached. The breakpoint layout is centralized in `_apply_anthropic_breakpoints()` precisely so this decision can be revisited in one place.
- **Mechanism:** **Explicit Breakpoint Caching (`cache_control`).**
- **How it works:** A `cache_control: {"type": "ephemeral"}` marker is added to the system prompt or up to 4 message blocks.
- **Economics & Surcharges:**
  - **Cache Reads:** **90% discount** ($0.30/M vs $3.00/M on Sonnet).
  - **Cache Writes:** First-time cache creation incurs a **1.25× surcharge** ($3.75/M vs $3.00/M).
  - **Telemetry:** Anthropic reports `cache_creation_input_tokens` (writes) and `cache_read_input_tokens` (reads).
- **TTL:** 5-minute rolling TTL, refreshed on every cache hit.

### 2.5 DeepSeek (DeepSeek-V3, DeepSeek-R1)
- **Mechanism:** **Fully Automatic Context Caching.**
- **How it works:** Automatic on 64-token chunk boundaries. No key or configuration required.
- **Economics:** **75% discount** ($0.07/M cached vs $0.27/M uncached tokens). No cache-write surcharge.

### 2.6 Google Gemini (Gemini 2.5 and newer)
- **Implicit:** Enabled by default on all Gemini 2.5+ models with ~75% discount, passed through automatically on cache hits. Minimum cacheable prefix is **1,024 tokens (Flash)** / **2,048 tokens (Pro)**. (The 32,768-token minimum often cited belongs to the Gemini 1.5 era and no longer applies.)
- **Explicit (Context Caching):** Pre-allocates a persistent cache object with a resource ID (`cachedContents/...`) and explicit TTL (e.g. 1 hour or 24 hours), ideal for massive corpora. Storage cost applies per hour. **Reachability note:** explicit caching requires the native `generateContent` API and is **not reachable through the OpenAI-compatible endpoint** Chatybot uses — Chatybot therefore relies on implicit caching only for Gemini.

### 2.7 Local Inference (vLLM, Ollama, llama.cpp)
- **vLLM:** Supports Automatic Prefix Caching (APC) with PagedAttention (`--enable-prefix-caching`). Reuses KV blocks across identical prefixes with 0 client configuration.
- **Ollama:** Reuses GPU KV cache across successive turns for the duration of `keep_alive` (default 5 minutes).

---

### 2.8 Provider Comparison Matrix

| Provider | Mechanism | Required Parameter | Min Tokens | Read Discount | Write Surcharge | Cache TTL |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Mistral AI** | Explicit Key | `prompt_cache_key` | None | **~90%** | None (1.0×) | Variable |
| **OpenRouter** | Sticky Session / Passthrough | `session_id` or `prompt_cache_key` | Varies | Up to **90%** | Upstream rate | Upstream |
| **OpenAI** | Automatic Prefix | *None* | 1,024 | **50%** | **1.25×–2.5×** (`cache_write_tokens`) | 5–30 min / 12h |
| **Anthropic** | Breakpoints | `cache_control: {"type": "ephemeral"}` | 1,024 (2,048 Haiku; 4,096 Haiku 4.5) | **90%** | **1.25×** (`cache_creation`) | 5 min (rolling) |
| **DeepSeek** | Automatic Prefix | *None* | 64 | **75%** | None (1.0×) | Variable |
| **Google Gemini** | Automatic (implicit) | *None* | 1,024 (Flash) / 2,048 (Pro) | **~75%** | None | Not documented (automatic) |
| **Local (vLLM/Ollama)**| Automatic (PagedAttention)| *None* | Block size | **100% compute** | None | `keep_alive` |

---

## 3. Evaluation of Architectural Options

### Option 1: Automatic Session-Bound Caching (Zero-Config / Implicit)
- **Description:** Whenever an active session exists (`self.active_session_id`), automatically pass `prompt_cache_key = f"chatybot-{self.active_session_id}"`.
- **Pros:** Zero user configuration required; multi-turn conversations and tool loops instantly get 80–90% cost savings.
- **Cons:** Does not share cache across separate sessions that load the same profile or documents.

### Option 2: Hierarchical Hybrid Strategy (Session + Profile + Document Hash)
- **Description:** A multi-tier resolution engine that computes a SHA-256 fingerprint for static document prefixes, falls back to session ID, and then profile name.
- **Pros:** Maximizes cache hit rates for both multi-turn chat and repeated single-turn document/RAG queries.
- **Cons:** Adds complexity in computing and tracking hash invalidations when filebank contents change.

### Option 3: First-Class ChatDSL & Command-Level Control (`/cachekey`)
- **Description:** Explicit user commands (`/cachekey set <name>`, `/cachekey off`, `/cachekey status`) and script variable `${PROMPT_CACHE_KEY}`.
- **Pros:** Provides complete control for developers writing batch scripts, benchmarks, or RAG pipelines.
- **Cons:** Requires active user awareness if not paired with automatic defaults.

---

## 4. Recommended Architecture: Unified Hybrid Caching

The recommended architecture adopts **Option 1 as the default behavior**, layered with **Option 3's explicit controls**, and backed by **Prefix Stabilization** to optimize automatic caching providers.

```
                      Prompt Caching Pipeline
                                 │
     ┌───────────────────────────┴───────────────────────────┐
     ▼                                                       ▼
[Key Resolution Layer]                              [Prefix Stabilization]
  1. Script Var: ${PROMPT_CACHE_KEY}                  1. Deterministic Tool Ordering
  2. Manual: /cachekey set <name>                     2. Static System Prompt Policy
  3. Session: chatybot-{active_session_id}            3. Strict Sequential Appending
  4. Profile: chatybot-prof-{active_profile}                 │
     │                                                       │
     └───────────────────────────┬───────────────────────────┘
                                 │
                                 ▼
                   [Provider Payload Adaptor]
                     ├─ Mistral: prompt_cache_key
                     ├─ OpenRouter: session_id sticky routing (+ prompt_cache_key)
                     ├─ Anthropic (via OpenRouter): cache_control breakpoint
                     └─ OpenAI/DeepSeek/vLLM: Standard payload
                                 │
                                 ▼
                     [Universal Telemetry]
                     Read cached_tokens & cache_write_tokens
                     Compute Net Financial Savings in CLI & /dblog
```

---

## 5. Technical Specifications

### 5.1 Prefix Stabilization Framework (Universal Pre-requisite)
For automatic prefix caching (OpenAI, DeepSeek, vLLM, Gemini) and breakpoint caching (Anthropic) to succeed, the byte sequence of the prompt prefix must remain **100% identical** across requests.

1. **Deterministic Tool Serialization:**
   Sort native and MCP tool definitions alphabetically by name before generating the `tools` payload. The sort key must handle both OpenAI-style (`function.name`) and Anthropic-style (top-level `name`) tool shapes, as well as non-dict tool objects:
   ```python
   def _tool_sort_key(t: Any) -> str:
       if isinstance(t, dict):
           return str((t.get("function") or {}).get("name") or t.get("name") or "")
       fn = getattr(t, "function", None)
       return str(getattr(fn, "name", None) or getattr(t, "name", None) or "")

   sorted_tools = sorted(tools, key=_tool_sort_key)
   ```
2. **Volatile Content Isolation:**
   Do **not** place dynamic per-turn timestamps (e.g. `Current time: 18:44:27`) in the system prompt. If time information is needed, inject it into the most recent user turn message rather than the system prompt.
3. **Sequential Appending:**
   Preserve conversation turns in chronological order so that Turn $N$ is always a strict prefix of Turn $N+1$.
4. **Context Compaction & History Pruning Dynamics:**
   Chatybot automatic history truncation (`auto_truncate` at context limit) and explicit trimming commands (`/session history trim`, `/compact`) drop older dialogue turns from the head of the message history to remain within model context windows.
   - **Operational Reality:** Because dropping leading turns alters the byte sequence of the prompt prefix, all automatic prefix providers (OpenAI, DeepSeek, Gemini) and explicit key providers (Mistral) will experience an unavoidable **cold-start cache miss** on turn $N+1$ immediately following compaction.
   - **Warm-Up Surcharge:** Turn $N+1$ incurs a cache-write warm-up cost to establish the new prefix in the provider KV cache. Subsequent turns ($N+2, N+3, \dots$) will then achieve full cache hit rates against the new compacted history.

---

### 5.2 Cache Key Resolution Logic (`ChatybotApp`)

In `src/chatybot/chatybot_app.py`:

```python
def _resolve_prompt_cache_key(self, model_config: dict[str, Any]) -> str | None:
    """Resolve prompt cache key according to priority hierarchy."""
    # 1. Disabled explicitly
    if getattr(self, "prompt_caching_disabled", False):
        return None

    # 2. ChatDSL protected variable override (${PROMPT_CACHE_KEY})
    script_var = self.buffer_manager.get_script_var("PROMPT_CACHE_KEY")
    if script_var and script_var.strip():
        return script_var.strip()

    # 3. Manual user command override (/cachekey set <name>)
    if getattr(self, "custom_cache_key", None):
        return self.custom_cache_key

    # 4. Model configuration override in chat_config.toml
    config_key = model_config.get("prompt_cache_key")
    if config_key and str(config_key).strip():
        return str(config_key).strip()

    # 5. Active session binding (default)
    if self.active_session_id:
        return f"chatybot-{self.active_session_id}"

    # 6. Profile fallback for non-session queries
    active_profile = getattr(self, "active_profile_name", None) or "general"
    return f"chatybot-profile-{active_profile}"
```

**Configuration wiring:** as built, `_resolve_prompt_cache_key()` checks three disable signals in order at resolution time: the runtime toggle `self.prompt_caching_disabled` (`/cachekey off` / `/cachekey on`), the per-model `prompt_caching = false` override in the model's TOML table, and the global `[default].prompt_caching = false` surfaced as `ConfigManager.prompt_caching_default`. No TOML rewriting happens at runtime.

**`${PROMPT_CACHE_KEY}` is a normal script variable, not a protected one:** `/setvar` writes protected variables through `user_write()`, which raises on protected names — registering `PROMPT_CACHE_KEY` in `ScriptVars.protected_vars` would block the primary use case (scripts assigning `/setvar PROMPT_CACHE_KEY kb-rag-v1`). It is therefore a user-settable script variable that `_resolve_prompt_cache_key()` reads via `BufferManager.get_script_var()`.

**Cache-key hygiene:** Cache keys are used by providers for grouping and may appear in provider-side logs. Never embed secrets, API keys, or user content in a cache key; use opaque identifiers (session IDs, profile names, explicit names set via `/cachekey set`) only. This matches the guidance in Mistral's prompt-caching documentation.

---

### 5.3 Provider-Aware Payload Construction

In `chatybot_app.py:chat_completion()`:

```python
cache_key = self._resolve_prompt_cache_key(model_config)

is_mistral = "mistral.ai" in model_config.get("base_url", "").lower() or model_config.get("vendor") == "mistral"
is_openrouter = "openrouter.ai" in model_config.get("base_url", "").lower() or model_config.get("vendor") == "openrouter"
model_name_lower = model_config.get("name", "").lower()

def _apply_anthropic_breakpoints(call_kwargs: dict[str, Any]) -> None:
    """Inject cache_control breakpoints onto the last tool definition and system prompt."""
    # a. On the LAST tool definition (caches system prompt + entire tool/MCP schema suite)
    tools = call_kwargs.get("tools")
    if tools and isinstance(tools, list):
        tools_copy = list(tools)
        last_tool = tools_copy[-1]
        if isinstance(last_tool, dict):
            last_tool = dict(last_tool)
            last_tool["cache_control"] = {"type": "ephemeral"}
            tools_copy[-1] = last_tool
            call_kwargs["tools"] = tools_copy

    # b. On the system message (handles both plain string and pre-formed content-block lists)
    messages = call_kwargs.get("messages")
    if messages and messages[0].get("role") == "system":
        content = messages[0].get("content")
        if isinstance(content, str):
            messages[0]["content"] = [
                {"type": "text", "text": content, "cache_control": {"type": "ephemeral"}}
            ]
        elif isinstance(content, list) and content:
            # Tag the final block in the existing structured block list
            last_block = content[-1]
            if isinstance(last_block, dict):
                last_block = dict(last_block)
                last_block["cache_control"] = {"type": "ephemeral"}
                content[-1] = last_block

if cache_key:
    # A. Native Mistral API
    if is_mistral:
        kwargs.setdefault("extra_body", {})["prompt_cache_key"] = cache_key

    # B. OpenRouter (Unified Sticky Routing & Normalized Breakpoints)
    elif is_openrouter:
        extra = kwargs.setdefault("extra_body", {})
        # 1. OpenRouter native session_id activates sticky routing on request #1,
        #    pinning the upstream provider instance without manual provider.order
        if self.active_session_id:
            extra["session_id"] = f"chatybot-{self.active_session_id}"

        # 2. Forward prompt_cache_key (honored by Mistral and serves as sticky fallback)
        extra["prompt_cache_key"] = cache_key

        # 3. For Claude models, inject normalized cache_control breakpoints
        if "claude" in model_name_lower:
            _apply_anthropic_breakpoints(kwargs)

    # C. OpenAI / DeepSeek / vLLM / Gemini:
    # No extra body needed; Prefix Stabilization ensures automatic caching.
    # Note: Anthropic models are reached exclusively via branch B (OpenRouter);
    # no direct Anthropic API path exists (see Section 2.4).
    #
    # ACKNOWLEDGED GAP: the Anthropic breakpoints below cover only the tool
    # definitions and the system prompt. Conversation-history turns are NOT
    # breakpoint-cached for Claude models (see Section 2.4 "Known Gap").
```

**Implementation notes (as built, v1):**
- `_apply_anthropic_breakpoints()` deep-copies the message dict before converting
  string content to a block list and before re-tagging the final block, so the
  conversation history owned by ChatybotApp is never mutated in place (in-place
  mutation would accumulate `cache_control` markers across turns and eventually
  exceed Anthropic's 4-breakpoint limit).
- The profile fallback (resolution step 6) reads `self.active_profile_name`,
  which ChatybotApp now sets when `/profile use` successfully applies a profile
  (profiles are one-shot scripts in this codebase; "active profile" means the
  most recently applied one, defaulting to `"general"`).
- Net-savings dollar figures in `/cachekey status` and `[TRACE:CACHE]` require a
  known base input price; they are computed only when the model config supplies
  `input_cost_per_mtok` (USD per million tokens). Without it the UI reports
  token counts and hit rate, never a fabricated dollar amount.

---

### 5.4 Interactive & ChatDSL Commands (`/cachekey`)

Add `/cachekey` to the Chatybot command registry:

- `/cachekey` or `/cachekey status`
  Displays active caching status, current key, and session cache hit statistics:
  ```text
  [Prompt Cache Status]
    Status:           Enabled (Auto Session)
    Active Key:       chatybot-session-ses_0505
    Provider:         OpenAI / OpenRouter
    Cached Tokens:    14,250 tokens read (~84% overall hit rate)
    Write Tokens:     1,420 tokens written to cache (warm-up surcharge factored)
    Est. Net Savings: $0.034 (net benefit after warm-up write cost)
  ```
- `/cachekey session` or `/cachekey reset`
  Resets key binding to current `active_session_id` and clears any custom key.
- `/cachekey profile`
  Binds key to current active profile.
- `/cachekey set <name>`
  Sets a custom cache key (e.g. `/cachekey set kb-rag-v1`).
- `/cachekey off` / `/cachekey on`
  Toggles prompt cache key emission on or off.

---

### 5.5 Configuration Schema (`chat_config.toml`)

Under model configurations in `chat_config.toml`:

```toml
# ============================================================================
# DEFAULT SETTINGS (optional global defaults)
# ============================================================================
[default]
# Enable or disable prompt caching globally across all models (default: true)
prompt_caching = true

# ============================================================================
# CHAT MODELS
# ============================================================================
[models.mistral_1]
name = "mistral-large-2512"
base_url = "https://api.mistral.ai/v1"
api_key = "MISTRAL_API_KEY"
vendor = "mistral"

# Per-model override for prompt caching (inherits [default].prompt_caching if omitted):
prompt_caching = true

# Optional static cache key override (if omitted, uses session/profile default):
# prompt_cache_key = "shared-dev-cache"
```

---

### 5.6 Universal Telemetry Reporting

In `chatybot_app.py`, immediately following completion response receipt:

```python
if hasattr(response, "usage") and response.usage:
    prompt_tokens = response.usage.prompt_tokens
    out_tokens = response.usage.completion_tokens

    # Extract cached read tokens & cache write tokens
    cached_tokens = 0
    cache_write_tokens = 0

    # Standard OpenAI / OpenRouter / DeepSeek schema:
    p_details = getattr(response.usage, "prompt_tokens_details", None)
    if p_details is not None:
        cached_tokens = int(getattr(p_details, "cached_tokens", 0) or 0)
        cache_write_tokens = int(getattr(p_details, "cache_write_tokens", 0) or 0)

    # Anthropic native schema fallback:
    if not cached_tokens and hasattr(response.usage, "cache_read_input_tokens"):
        cached_tokens = int(getattr(response.usage, "cache_read_input_tokens", 0) or 0)
    if not cache_write_tokens and hasattr(response.usage, "cache_creation_input_tokens"):
        cache_write_tokens = int(getattr(response.usage, "cache_creation_input_tokens", 0) or 0)

    # Store metrics for session stats and database logging (/dblog)
    self.last_cached_tokens = cached_tokens
    self.last_cache_write_tokens = cache_write_tokens

    if cached_tokens > 0 or cache_write_tokens > 0:
        hit_pct = (cached_tokens / prompt_tokens) * 100 if prompt_tokens else 0
        details = f"{cached_tokens} read"
        if cache_write_tokens > 0:
            details += f", {cache_write_tokens} write"
        print(f"Tokens: {prompt_tokens} in ({details} / {hit_pct:.0f}% hit rate), {out_tokens} out")
    else:
        print(f"Input tokens: {prompt_tokens}, Output tokens: {out_tokens}")
```

#### Financial Economics: Accounting for Universal Cache-Write Surcharges

Cache writes are **not free background operations** across modern providers. Because providers like OpenAI charge **1.25×** (30-minute retention) or **2.5×** (12-hour retention) and Anthropic charges **1.25×** on cache creation writes, computing savings purely as `cached_tokens * discount` yields inflated figures during cache-warm-up periods.

Chatybot computes true **Net Economic Savings** using:

$$\text{Gross Savings} = \sum (\text{cached\_tokens} \times [P_{\text{base}} - P_{\text{cached}}])$$
$$\text{Write Surcharge} = \sum (\text{cache\_write\_tokens} \times [P_{\text{write}} - P_{\text{base}}])$$
$$\text{Net Financial Benefit} = \text{Gross Savings} - \text{Write Surcharge}$$

Where:
- $P_{\text{base}}$: Base prompt input rate per token.
- $P_{\text{cached}}$: Discounted rate for cached reads (e.g. 50% on OpenAI, 10% on Mistral/Anthropic).
- $P_{\text{write}}$: Cache creation rate (e.g. $1.25 \times P_{\text{base}}$ on OpenAI standard, $2.5 \times P_{\text{base}}$ on OpenAI extended, $1.25 \times P_{\text{base}}$ on Anthropic).

If a short session only executes 1–2 turns and incurs 5,000 write tokens with zero or minimal cache hits, the net savings correctly displays negative or break-even, rather than erroneously claiming savings.

#### Database Logging Schema (`chatydb.py:dblog()`)

When `/dblog` persists completions into TinyDB / SQLite, prompt caching metrics are saved into the turn's `metadata` dictionary matching the pattern used for `thinking_tokens`:

```python
# Inside chatydb.py:dblog()
metadata["cached_tokens"] = getattr(app_instance, "last_cached_tokens", 0) if app_instance else 0
metadata["cache_write_tokens"] = getattr(app_instance, "last_cache_write_tokens", 0) if app_instance else 0
metadata["prompt_cache_key"] = getattr(app_instance, "last_prompt_cache_key", None) if app_instance else None
```

This enables historical queries (`/searchdb` or custom analytics) to evaluate cache hit ratios, warm-up write surcharges, and aggregate cost savings across sessions and profiles over time.

#### Diagnostics & `/trace` Integration

Chatybot's trace subsystem (`commands/debug_misc.py:cmd_trace`) provides deep runtime visibility:
- **`/trace rawpayload on`**: Dumps the complete serialized API request payload, allowing developers to inspect injected `prompt_cache_key`, `session_id`, and tool `cache_control` blocks before transmission.
- **`/trace cache on`**: A dedicated diagnostic flag under `/trace` that logs a per-turn cache event line upon completion:
  ```text
  [TRACE:CACHE] Key="chatybot-ses_0505" | In=4,820 | Read=4,200 (87%) | Write=0 | NetSavings=+$0.0126
  ```

---

### 5.7 Help Text Registration (`chaty_help.py`)

Register `/cachekey` in `HelpSystem._initialize_commands()` using the existing `CommandHelp` structure so `/help cachekey`, keyword search, and category listings all work:

```python
self.register_command(CommandHelp(
    name="/cachekey",
    category="model",
    short_desc="View or control prompt-cache key binding and cache telemetry",
    usage="/cachekey [status|session|reset|profile|set <name>|on|off]",
    long_desc=(
        "Controls the prompt_cache_key sent to model providers for prompt caching. "
        "By default the key is bound to the active session id. Subcommands: "
        "status (show key, provider, hit rate, net savings), session/reset (rebind to the "
        "active session), profile (bind to the active profile), set <name> (custom "
        "key), on/off (enable or disable cache-key emission)."
    ),
    examples=["/cachekey", "/cachekey status", "/cachekey set kb-rag-v1", "/cachekey off"],
    see_also=["/dblog", "/trace", "/model"],
))
```

`category` must be one of the existing help categories (`model` fits; do not invent a new category for one command). Keep the `long_desc` wording in sync with the `/cachekey status` output mockup in §5.4 — the help text and the runtime output describe the same subcommands.

---

### 5.8 Localization (`translations.json`, `localization.py`, `pattern.py`)

Following the command-keyword customization workflow:

1. **Command verb aliases.** Add `/cachekey` to the `aliases` table for `en`, and a translated alias for every supported locale (`es`, `fr`, `zh`, `it`, `ar`):
   ```json
   "en": { "aliases": { "/cachekey": "/cachekey" } },
   "es": { "aliases": { "/clavedecache": "/cachekey" } },
   "fr": { "aliases": { "/clecache": "/cachekey" } },
   "it": { "aliases": { "/chiavecache": "/cachekey" } },
   "zh": { "aliases": { "/缓存键": "/cachekey" } },
   "ar": { "aliases": { "/مفتاح-الكاش": "/cachekey" } }
   ```
2. **Sub-keyword keywords.** `set`, `on`, and `off` already exist in the `keywords` tables. Add `status`, `session`, `reset`, and `profile` where missing, plus per-locale equivalents (e.g. `"es": {"sesion": "session", "reiniciar": "reset", "reajustar": "reset", "perfil": "profile", "estado": "status"}`). Both `session` and `reset` map to resetting to active session ID. `LocalizationManager.translate_command_string()` then rewrites `/clavedecache sesion` to `/cachekey session` before dispatch — no per-locale branching in the handler.
3. **PatternMatcher registration.** Register `cachekey` in the `PatternMatcher` (see `pattern.py` / `chatybot_app.py` `__init__`) so an unescaped leading `cachekey ...` at the start of a prompt triggers the standard "use escape sequence" validation warning instead of being silently sent to the model.
4. **UI strings.** The `[Prompt Cache Status]` block in §5.4 must be emitted through `LocalizationManager.get_ui_string()` keys (e.g. `ui.cache_status`, `ui.cache_active_key`, `ui.cache_hit_rate`) rather than hardcoded English, with the English text passed as the `default` fallback so missing translations degrade gracefully.

---

### 5.9 ChatDSL Parser Integration (`chatdsl_parse.py`)

- **Escape-command whitelist:** add `"cachekey"` to `VALID_ESCAPE_COMMANDS` in `chatdsl_parse.py`. The parser already resolves localized command forms through `LocalizationManager.resolve_command()` at parse time, so the §5.8 aliases are what make `/clavedecache ...` valid inside `.chatdsl` scripts. Without this entry, any script using the command raises `ParseError: Invalid escape command` — the whitelist and the translations must land in the same change.
- **No parser change needed for `${PROMPT_CACHE_KEY}`:** `parse_var_ref()` already parses `${IDENT}` generically, and resolution happens at runtime through `BufferManager.script_vars` (§5.2, step 2). The implementation only needs to register `PROMPT_CACHE_KEY` in `BufferManager` so it resolves in both command arguments and chat text.
- **Parser test:** a script line `/cachekey set ${CACHE_NAME}` must parse to a command node whose args contain a `variable_reference` node — add this to the parser test suite.

---

### 5.10 Cookbook & Guide Documentation

- **New cookbook recipe:** `doc/cookbook/13_5_cache_key_tuning.chatdsl` under Chapter 13 (Diagnostics, Debugging & Performance), demonstrating: checking `/cachekey status`, pinning a shared key for a RAG batch via `/cachekey set` or a `${PROMPT_CACHE_KEY}` assignment, and reading the cached-token output of a multi-turn run. Follow the existing recipe conventions (runnable script in `doc/cookbook/`, prose walkthrough in `doc/chatdsl_cookbook.md`).
- **Cookbook index updates:** the walkthrough must update the Table of Contents, Appendix A (recipe index), and Appendix B (cross-reference map) in `doc/chatdsl_cookbook.md` — all three indexes reference recipes by name.
- **Guide set sync:** add `/cachekey` and `${PROMPT_CACHE_KEY}` to the ChatDSL guide set — `chatdsl_guide_v1.md` and its translations (`chatdsl_guide_v1_spanish.md`, `chatdsl_guide_v1_french.md`, `chatdsl_guide_v1_italian.md`, `chatdsl_guide_v1_chinese.md`, `chatdsl_guide_v1_arabic.md`) — so all six language guides stay in sync with the parser's accepted commands.

---

## 6. Implementation Plan & Milestones

1. **Prefix Stabilization**:
   - Ensure tool registration dictionaries in `chatybot_app.py` sort tools deterministically before building the completion payload.
   - Audit system prompt generators to verify no per-turn volatile timestamps are prepended to the static prefix.
2. **Cache Key Resolution & Payload Adaptor**:
   - Implement `_resolve_prompt_cache_key()` in `chatybot_app.py`.
   - Inject `session_id` into OpenRouter requests for automatic request-#1 sticky host routing.
   - Inject `prompt_cache_key` for Mistral and forward through OpenRouter.
   - Inject `cache_control` breakpoints (tool definitions + system message) for Anthropic models and OpenRouter normalized breakpoints.
3. **Telemetry & Metric Logging**:
   - Capture both `cached_tokens` and `cache_write_tokens` in `chatybot_app.py`.
   - Update `chatydb.py:dblog()` metadata schema (`cached_tokens`, `cache_write_tokens`, `prompt_cache_key`).
   - Implement `/trace cache` diagnostic logging in `commands/debug_misc.py`.
   - Implement net financial savings formula subtracting cache-write warm-up surcharges.
   - Display cache hit percentages and net savings in CLI completion summaries.
4. **Command & DSL Control**:
   - Add `/cachekey` command handler in `chatybot/commands/` and register in `chaty_help.py` (§5.7).
   - Register `/cachekey` aliases and `status`/`session`/`profile` sub-keywords in `translations.json` for all six locales, and register `cachekey` in the PatternMatcher (§5.8).
   - Add `"cachekey"` to `VALID_ESCAPE_COMMANDS` in `chatdsl_parse.py` (§5.9).
   - Bind protected variable `${PROMPT_CACHE_KEY}` in `BufferManager`.
5. **Configuration Support**:
   - Support `prompt_caching` in `[default]` (global) and per-model tables in `chat_config.toml` and Config TUI.
   - Support `prompt_cache_key` override per-model.
6. **Testing & Verification**:
   - Unit tests for key resolution order (script var > `/cachekey set` > config > session > profile, with an explicit disable short-circuiting all of them).
   - Mock API tests verifying `prompt_cache_key` appears in `extra_body` for Mistral models.
   - Verification of telemetry metric calculations.
   - Command-verb tests in `test/test_command_verb_validation.py`: `/cachekey` executes with mock config; unescaped localized verbs at prompt start raise the validation warning; localized sub-keywords translate to canonical English.
   - Parser test: `/cachekey set ${CACHE_NAME}` parses with a `variable_reference` argument (§5.9).
7. **Documentation & Help**:
   - Register the `/cachekey` `CommandHelp` entry (§5.7).
   - Add cookbook recipe `13_5_cache_key_tuning.chatdsl` + walkthrough, updating the cookbook TOC and both appendices (§5.10).
   - Add `/cachekey` and `${PROMPT_CACHE_KEY}` to all six language guides (§5.10).

---

## 7. Conclusion

By implementing a **hybrid prompt caching strategy**, Chatybot achieves the best of both worlds:
- **Zero-Friction Default:** Everyday users running multi-turn chats or tool loops automatically receive 50%–90% cost reductions and faster response times without entering any commands.
- **Cross-Vendor Adaptability:** Native Mistral, OpenRouter, Anthropic, OpenAI, DeepSeek, and local engines are all addressed using their native caching paradigms.
- **Power-User Flexibility:** Developers executing ChatDSL automation, batch evaluations, and RAG pipelines gain full command-line and script variable control over cache boundaries.

---

## 8. Implementation Differences (As Built)

The feature was implemented against this proposal. The differences between the
proposal text and the shipped code are consolidated here; earlier inline
"Implementation notes" callouts describe the same decisions in context.

### 8.1 Anthropic caching scope (acknowledged gap)
Breakpoints land only on the last tool definition and the system message.
Conversation-history turns are **not** breakpoint-cached for Claude models —
see §2.4 "Known Gap". Message-tail breakpoints remain future work; the layout
is centralized in `_apply_anthropic_breakpoints()` for one-place revisitation.

### 8.2 Breakpoint helper deep-copies (bug fix over §5.3 pseudocode)
The proposed pseudocode mutated `messages[0]` and the last tool dict in place.
As built, `_apply_anthropic_breakpoints()` deep-copies both before tagging, so
ChatybotApp's conversation history is never modified and repeated application
does not accumulate `cache_control` markers toward Anthropic's 4-breakpoint
limit.

### 8.3 Disable resolution (§5.2 "Configuration wiring" changed)
Instead of ConfigManager mapping TOML to `self.prompt_caching_disabled` at
model-load time, `_resolve_prompt_cache_key()` checks three signals at
resolution time, in order: the runtime toggle `self.prompt_caching_disabled`
(`/cachekey off|on`, session-only), the per-model `prompt_caching = false`
override, and the global `[default].prompt_caching` surfaced as
`ConfigManager.prompt_caching_default`. No TOML is rewritten at runtime.

### 8.4 `${PROMPT_CACHE_KEY}` is a normal script variable, not protected
Protected variables reject `/setvar` writes (via `user_write()`), which would
block the primary use case of assigning the key from ChatDSL scripts.
`PROMPT_CACHE_KEY` is therefore a user-settable script variable read through
`BufferManager.get_script_var()`; it is not added to
`ScriptVars.protected_vars` (§5.2 step 2 and §5.9 amended accordingly).

### 8.5 Profile fallback semantics (§5.2 step 6)
This codebase has no persistent "active profile" — profiles are one-shot
scripts applied via `/profile use`. ChatybotApp now tracks
`self.active_profile_name`, set when `/profile use` succeeds and defaulting to
`"general"` in the cache-key fallback. "Profile binding" means the most
recently applied profile.

### 8.6 Net savings require configured pricing (§5.6 changed)
`/cachekey status` and `[TRACE:CACHE]` never fabricate dollar amounts. Net
savings are computed only when the model config supplies
`input_cost_per_mtok` (USD per million tokens); the formula uses conservative
constants (50% read discount, 1.25× write surcharge) rather than per-provider
rate tables. Without pricing, the UI reports token counts and hit rate only.

### 8.7 Unverified vendor claims (§2.3, §2.1 flagged)
The OpenAI cache-write surcharge tiers (1.25×/2.5×), the
`prompt_tokens_details.cache_write_tokens` field, and Mistral's
`prompt_cache_key` request parameter were not verifiable against current
provider documentation at implementation time. Telemetry extraction degrades
safely (absent fields read as 0 via strict numeric type checks), but the
comparison matrix in §2.8 and the savings math should be re-validated against
live provider docs before being treated as authoritative.

### 8.8 Command lives in the modular registry (§5.4 / skill workflow)
`/cachekey` is implemented as `commands/cachekey.py` with a `@command`
decorator (the phased-migration registry path), not as a new branch in the
legacy `handle_escape_command` elif chain. Localization, PatternMatcher
registration, `VALID_ESCAPE_COMMANDS`, help registration, and the six-locale
translations all follow the command-keyword customization workflow as
specified in §5.7–§5.9.

### 8.9 Tool sorting is defensive (§5.1 item 1)
The main OpenAI-client path in `chat_completion()` never attaches a native
`tools` array in this codebase — MCP tools are injected as prompt text and
native tool schemas exist only in the Apple FM backend path. Deterministic
sorting therefore runs inside `_apply_prompt_caching()` against whatever
`tools` payload is present, rather than as a standalone pre-serialization
step; it becomes load-bearing if native tool payloads are added later.

### 8.10 `/trace cache` output omits dollar figures by default
The §5.6 mockup shows `NetSavings=+$0.0126` on the trace line. As built, the
line carries `Key | In | Read (hit %) | Write`; the savings figure appears in
`/cachekey status` (and the completion summary) only when model pricing is
configured (see 8.6).

### 8.11 Per-API-call cache metrics in agentic loop records (addition)
Beyond the proposal, each agentic-loop tool record persisted in the session
store (`turns.jsonl`, `agentic_loop` entries) now carries a `cache` object —
`prompt_tokens`, `cached_tokens`, `cache_write_tokens`, `hit_pct` — reflecting
the completion that *requested* that tool call. The turn record also carries
loop-level totals under `cache_stats` (`api_calls`, summed tokens). This
exists because only the last completion's telemetry was previously visible:
cumulative `/cachekey status` numbers could not be decomposed after the fact.
Counters degrade to 0 in streaming mode, where per-call usage is not parsed.
The same per-call cache object is printed by `/trace agentic_loop`.
