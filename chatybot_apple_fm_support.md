# Chatybot Apple Foundation Model Support (BETA)

**Date:** 2026-09-13
**Status:** Beta. Implemented and verified end-to-end on macOS 26.6.2 with
apple-fm-sdk 0.2.1. The 4096-token context window imposes significant
constraints on usability. Read the caveats section before using.

---

## 1. Overview

Chatybot supports Apple's on-device Foundation Model as a first-class model
type under the alias `apple_fm`. The model runs locally on macOS 26+ via
Apple Intelligence. There is no API key, no network request, no base URL,
and no per-token cost. Inference is entirely on-device.

The integration adds a new model type (`apple_fm`) to chatybot's
configuration system, a parallel inference path that bypasses the OpenAI
client entirely, and a native tool calling bridge that connects Apple's
`fm.Tool` API to chatybot's existing tool dispatch infrastructure.

This is a beta feature. The on-device model has a fixed 4096-token context
window that cannot be increased. This limit constrains every aspect of
usage: conversation length, number of registered tools, tool result size,
and system prompt complexity. The model is best suited for short
interactions, quick questions, and simple tool use with small outputs. It
is not suitable for long agentic sessions, large file operations, or
multi-turn conversations with extensive history.

---

## 2. Requirements

| Requirement | Minimum | Verified System |
|---|---|---|
| macOS | 26.0+ | 26.6.2 |
| Hardware | Apple Silicon (M1 or later) | arm64 |
| Xcode | 26.0+ with SDK agreement accepted | Required for SDK build |
| Python | 3.10+ | 3.14.7 |
| Apple Intelligence | Enabled in System Settings | Required |
| apple-fm-sdk | 0.2.1+ | 0.2.1 |

### Installation

The SDK is an optional dependency, not installed by default:

```bash
pip install apple-fm-sdk
```

Or via the chatybot optional extra (quotes required in zsh to avoid bracket
glob expansion):

```bash
pip install 'chatybot[apple_fm]'
```

Xcode 26+ must be installed and the SDK agreement must be accepted in the
Xcode application before the package will build and function correctly.
The package bundles Swift bridging code that compiles during installation.

### Enabling Apple Intelligence

Apple Intelligence must be turned on in System Settings. If it is off, the
model will report `APPLE_INTELLIGENCE_NOT_ENABLED` and chatybot will display
a human-readable error message directing the user to enable it.

---

## 3. Architecture

### 3.1 Inference Path

The apple_fm model type uses a parallel inference path that does not touch
the OpenAI client. The branch happens at the top of `chat_completion()`,
before any client creation or vendor-specific parameter logic:

```
chat_config.toml
    [models.apple_fm]
    type = "apple_fm"
         |
         v
config_model.py
    AppleFMModelConfig (Pydantic, BaseModelConfig subclass)
    ModelConfig discriminated union
         |
         v
chatybot_app.py :: chat_completion()
    if model_config["type"] == "apple_fm":
        return await self._apple_fm_completion(prompt, stream)
                    |
                    v
         apple_fm_backend.py
         (lazy import, platform guard, session management)
                    |
                    v
         apple_fm_sdk.LanguageModelSession.respond()
         or .stream_response()
```

The OpenAI path (`get_openai_client` to `chat.completions.create`) is never
reached for apple_fm models. This means none of the vendor-specific
parameter handling (nvidia `nvext`, mistral `random_seed`, google seed
warnings, reasoning effort, etc.) applies.

### 3.2 Module Isolation

All `apple_fm_sdk` imports are isolated in `src/chatybot/apple_fm_backend.py`.
The rest of chatybot never imports the SDK directly. The module-level import
is wrapped in a try/except so chatybot starts and runs normally on any
platform, including Linux, Windows, and macOS versions below 26.

### 3.3 Session Management

A fresh `LanguageModelSession` is created for each completion call.
Conversation history is managed by chatybot (concatenated into the prompt
text), not by the SDK session. This matches chatybot's existing pattern
where `chat_completion()` rebuilds the full message list each call.

The `SystemLanguageModel` instance is cached as a singleton in
`apple_fm_backend.py` because it is expensive to create. The session is not
cached.

### 3.4 Configuration

The `apple_fm` model type is defined in `config_model.py` as
`AppleFMModelConfig`, extending `BaseModelConfig`:

```toml
[models.apple_fm]
type = "apple_fm"
name = "Apple Foundation Model"
context_limit = 4096
temperature = 0.7
```

No `base_url` or `api_key` is needed. The `base_url` field defaults to the
sentinel value `"on-device"` and is never used for any HTTP request. The
`api_key` field is `None`. The `vendor` field defaults to `"apple"`.

### 3.5 Files Modified or Created

| File | Purpose |
|---|---|
| `src/chatybot/config_model.py` | `AppleFMModelConfig` class, discriminated union, `apple_fm_models()` accessor, TOML serialization |
| `src/chatybot/vendors.py` | `apple_fm` vendor preset for config TUI |
| `src/chatybot/chat_config.toml` | Default `apple_fm` model entry |
| `src/chatybot/apple_fm_backend.py` | Platform check, import guard, session management, streaming, generation options, native tool bridge |
| `src/chatybot/chatybot_app.py` | Early branch in `chat_completion()`, `_apple_fm_completion()` method |
| `src/chatybot/commands/models.py` | `/model info` display tweak for on-device base URL |
| `src/chatybot/config_tui.py` | `apple_fm` type in model editor, hidden fields for base_url/api_key |
| `pyproject.toml` | Optional `apple_fm` extra dependency |
| `test/test_apple_fm_config.py` | Config layer tests (15 tests, SDK-free) |
| `test/test_apple_fm_tools.py` | Tool bridge tests (26 tests, SDK-required) |

---

## 4. Multiplatform Strategy

### 4.1 Install

`apple-fm-sdk` is an optional extra, not a core dependency. It is not
platform-gated with `sys_platform == 'darwin'` because that would
auto-install on all Macs, including macOS versions below 26 and Intel Macs
where it cannot function. Explicit opt-in is the correct behavior.

### 4.2 Three-Layer Enable Check

| Layer | Check | When |
|---|---|---|
| 1. Config file | TOML entry exists | Always (just data, any platform) |
| 2. Import guard | `apple_fm_sdk` importable | First prompt to apple_fm model |
| 3. Model availability | `SystemLanguageModel().is_available()` | First prompt, after import succeeds |

### 4.3 Behavior on `/model apple_fm`

The switch always succeeds because it only sets config state. Errors
surface on the first prompt, matching how chatybot handles other model
errors (missing API keys, unreachable endpoints, etc.):

| Platform State | `/model apple_fm` | First Prompt |
|---|---|---|
| macOS 26+ arm64, SDK installed, AI on | Switches | Works |
| macOS 26+ arm64, SDK not installed | Switches | Error with install instructions |
| macOS 26+ arm64, SDK installed, AI off | Switches | Error: enable Apple Intelligence |
| macOS < 26 or Intel Mac | Switches | Error: requires macOS 26+ Apple Silicon |
| Linux / Windows | Switches | Error: requires macOS 26+ |

### 4.4 Error Messages

`SystemLanguageModelUnavailableReason` enum values are mapped to
human-readable messages:

| Enum Value | Message |
|---|---|
| `APPLE_INTELLIGENCE_NOT_ENABLED` | Apple Intelligence is not enabled. Turn it on in System Settings > Apple Intelligence. |
| `DEVICE_NOT_ELIGIBLE` | This device does not support Apple Foundation Models (requires Apple Silicon M1+). |
| `MODEL_NOT_READY` | The model is still downloading. Wait for it to finish in System Settings > Apple Intelligence. |
| `UNKNOWN` | Apple Foundation Model is unavailable for an unknown reason. |

---

## 5. Supported Parameters

The SDK exposes a limited set of generation parameters via
`GenerationOptions` and `SamplingMode`. Chatybot maps its existing commands
to these parameters.

### 5.1 Generation Options

| Chatybot Command | SDK Parameter | Range | Notes |
|---|---|---|---|
| `/temp <value>` | `GenerationOptions.temperature` | 0.0 to 1.0 | Higher is more random. SDK max is 1.0, narrower than chatybot's 0.0-2.0 validation. |
| `/maxtokens <value>` | `GenerationOptions.maximum_response_tokens` | Positive integer | Apple warns: strict limits may cause malformed or incomplete output. |
| `/top_k <value>` | `SamplingMode.random(top=N)` | Positive integer | Top-k sampling. Mapped via `build_sampling_mode()`. |
| `/top_p <value>` | `SamplingMode.random(probability_threshold=N)` | 0.0 to 1.0 | Top-p (nucleus) sampling. Mapped via `build_sampling_mode()`. |
| `/seed <value>` | `SamplingMode.random(seed=N)` | Integer | Reproducible output. Also supports `time` and `random <min>,<max>`. |

### 5.2 Parameter Resolution

Parameters are resolved in the same order as the OpenAI path: runtime
override (from `/temp`, `/top_k`, etc.) takes precedence over model config
values from `chat_config.toml`.

### 5.3 Sampling Mode Constraints

The SDK's `SamplingMode.random()` allows only one of `top` (top-k) or
`probability_threshold` (top-p) at a time. When both `/top_k` and `/top_p`
are set, `top_k` takes precedence because it is the more specific
constraint. The `seed` parameter can be combined with either.

### 5.4 Unsupported Parameters

The following chatybot commands have no equivalent in the SDK and are
silently ignored for apple_fm models:

| Chatybot Command | Reason |
|---|---|
| `/freq_penalty` | SDK has no frequency penalty parameter |
| `/pres_penalty` | SDK has no presence penalty parameter |
| `/reasoning` | On-device model does not support reasoning mode |
| `/effort` | On-device model does not support reasoning effort |
| `/thinking` | On-device model does not produce thinking tokens |
| `/thoughtstyle` | Not applicable to Apple Foundation Model |

---

## 6. Tool Calling

### 6.1 Native Tool Calling (Default for apple_fm)

When `/tool on` is enabled, chatybot builds `fm.Tool` instances from
`tools_config.toml` and registers them natively with the
`LanguageModelSession`. The SDK handles the entire tool loop internally:
the model decides when to call a tool, the SDK invokes the tool's `call()`
method, feeds the result back to the model, and the model continues until
it produces a final natural language response.

This is different from how other models work in chatybot. Other models use
prompt injection: tool schemas are injected into the system prompt, the
model outputs JSON tool calls in code fences, and `execute_tool_loop()`
parses and dispatches them. The native path bypasses all of that
machinery.

### 6.2 Tool Bridge Architecture

```
tools_config.toml
    [tools.list_directory]
    enabled = true
    description = "List contents of a directory"
    module = "chatybot.tools.file_utils"
    function = "list_directory"
    [tools.list_directory.parameters.path]
    type = "string"
    description = "Directory path to list"
    optional = true
         |
         v
apple_fm_backend.py :: build_tools(app)
    Reads tools_config.toml via app._load_tools_config()
    For each enabled tool:
      1. _create_generable_class() — builds @fm.generable class from TOML params
      2. _create_tool_wrapper() — creates fm.Tool subclass
         - name and description from TOML
         - arguments_schema returns the generable class schema
         - call() extracts args, builds JSON, delegates to app.dispatch_tool()
    Returns list of fm.Tool instances
         |
         v
apple_fm_backend.py :: create_session(tools=[...])
    LanguageModelSession(tools=tool_instances)
         |
         v
SDK handles tool loop internally
    Model calls tool -> SDK invokes call() -> dispatch_tool() executes
    -> result returned to model -> model continues -> final response
```

### 6.3 Tool Disable/Enable

`/tool disable` and `/tool enable` work with the native path. These
commands set `app.tool_overrides[tool_name] = False/True`. The
`build_tools()` function reads `tool_overrides` on every call and skips
disabled tools. The disable takes effect on the next prompt (not
mid-session), which matches the prompt-injection path's behavior.

### 6.4 Fallback to Prompt Injection

If `build_tools()` returns an empty list (SDK not installed, no tools
configured, or all tools disabled), `_apple_fm_completion()` falls back to
the prompt-injection approach: tool context is injected into the system
message and `execute_tool_loop()` handles dispatch. This fallback is
automatic and transparent.

### 6.5 Built-in ask_user Tool

The `ask_user` tool is registered natively if it is not already defined in
`tools_config.toml`. If the user's `tools_config.toml` already includes an
`ask_user` entry, the built-in version is not added to avoid duplicates.

### 6.6 MCP Tools

MCP tools are not currently bridged to native `fm.Tool` instances. Only
tools defined in `tools_config.toml` and the built-in `ask_user` tool are
registered natively. MCP tool support is a future enhancement.

---

## 7. Context Window Constraints

### 7.1 The 4096-Token Limit

The on-device model has a fixed 4096-token context window. This is a hard
limit set by Apple and cannot be configured or increased. There is no
parameter on `SystemLanguageModel` or `GenerationOptions` to change it.

This is the single most important constraint for apple_fm usage. The 4096
tokens must accommodate everything: system instructions, user prompt, chat
history, tool schemas, tool results, and the model's response. When the
total exceeds 4096 tokens, the SDK raises `ExceededContextWindowSizeError`
and the request fails.

### 7.2 What Consumes Tokens

| Component | Approximate Token Cost | Notes |
|---|---|---|
| System instructions | 50-200 | Config system message |
| Agentic instructions | 100-150 | Appended when tool_mode is on |
| Tool schemas (per tool) | 100-200 | Name, description, parameter definitions |
| Tool schemas (14 tools) | 1400-2800 | All tools_config.toml tools combined |
| Chat history (per turn) | 50-200 | One user + one assistant message |
| User prompt | Variable | Depends on prompt length |
| Tool results | Variable | File contents, directory listings, command output |
| Model response | Variable | Counted against the same budget |

### 7.3 Practical Implications

With 14 tools registered, tool schemas alone consume roughly 1400-2800
tokens, leaving only 1300-2700 tokens for everything else. This is
extremely tight. The following scenarios will likely overflow the context
window:

- **Listing a large directory** — `ls .` in a project root with hundreds of
  files produces output that exceeds the remaining budget.
- **Reading a file** — any file larger than a few hundred lines will
  overflow.
- **Multi-turn conversations** — after 3-4 turns, accumulated history
  consumes most of the budget.
- **Running shell commands** — command output is often large and
  unpredictable.
- **Multiple tool calls in one turn** — each tool result adds to the
  context.

### 7.4 Recommended Practices

**Disable most tools.** With 14 tools registered, there is almost no room
for prompt, history, or tool results. Disable all tools and enable only
the 1 or 2 needed for the current task:

```
/tool disable all
/tool enable calculate
/tool enable list_directory
```

This frees 1000-2000 tokens of context for actual content.

**Keep file reads small.** The `read_file` tool will overflow the context
window on any substantial file. Only read small files or specific line
ranges. Consider using `grep_search` to find specific content instead of
reading entire files.

**Limit conversation history.** Chat history is concatenated into the
prompt text. After 3-4 turns, history alone may consume most of the
budget. Start a fresh session with `/clear` when changing topics.

**Use short system messages.** Long system instructions eat into the
available context. Keep the system message concise for apple_fm sessions.

**Avoid large tool results.** Shell command output, directory listings, and
file contents are the most common cause of context overflow. Prefer tools
that return small, focused results.

### 7.5 Context Window Comparison

| Model Type | Context Window | Relative Size |
|---|---|---|
| Apple Foundation Model (on-device) | 4,096 tokens | 1x |
| Apple Private Cloud Compute (not yet available in SDK) | ~32,000 tokens | 8x |
| Mistral Large | 128,000 tokens | 31x |
| Gemini 2.5 Pro | 2,097,152 tokens | 512x |

The apple_fm model has the smallest context window of any model chatybot
supports. It is 31x smaller than Mistral Large and 512x smaller than
Gemini 2.5 Pro.

---

## 8. Streaming

Streaming is supported via `session.stream_response()`, which returns an
async iterator yielding text snapshots. Toggle with `/stream` as with any
other model.

The SDK's streaming yields complete text snapshots (not deltas). Each
yielded value contains the full text generated so far, not just the new
tokens since the last yield. Chatybot accumulates these into the full
response for history and logging.

Streaming does not support guided generation (structured output). For
basic text responses, streaming works the same as the OpenAI path.

---

## 9. Config TUI Support

The `apple_fm` type is available in the config TUI (`chatybot-config`).
When creating or editing a model with type `apple_fm`:

- The `base_url` and `api_key` fields are hidden (they do not apply)
- The `vendor` field auto-populates to `apple`
- The `base_url` is set to `on-device`
- Image generation fields are hidden
- Temperature and top_k fields remain editable

The type selector cycles through `chat`, `reranker`, and `apple_fm`.

---

## 10. What Is Supported

| Feature | Status |
|---|---|
| `/model apple_fm` switch | Supported |
| `/listmodels` shows apple_fm | Supported |
| `/model info apple_fm` | Supported (displays "on-device, no network") |
| Basic chat (non-streaming) | Supported |
| Streaming (`/stream`) | Supported |
| Chat history | Supported (concatenated into prompt) |
| System message (`/system`) | Supported (passed as session instructions) |
| Temperature (`/temp`) | Supported (0.0-1.0) |
| Max tokens (`/maxtokens`) | Supported |
| Top-k (`/top_k`) | Supported (via SamplingMode.random) |
| Top-p (`/top_p`) | Supported (via SamplingMode.random) |
| Seed (`/seed`) | Supported (via SamplingMode.random) |
| Native tool calling (`/tool on`) | Supported (fm.Tool bridge) |
| Tool disable/enable | Supported |
| Config TUI model creation | Supported |
| Platform guard (non-Mac) | Supported (clear error message) |
| Apple Intelligence off detection | Supported (human-readable error) |

---

## 11. What Is Not Supported

| Feature | Reason |
|---|---|
| Frequency penalty (`/freq_penalty`) | SDK has no equivalent parameter |
| Presence penalty (`/pres_penalty`) | SDK has no equivalent parameter |
| Reasoning mode (`/reasoning`) | On-device model does not support reasoning |
| Reasoning effort (`/effort`) | On-device model does not support reasoning effort |
| Thinking display (`/thinking`) | Model does not produce thinking tokens |
| Thought style (`/thoughtstyle`) | Not applicable |
| Context window > 4096 tokens | Hard limit set by Apple, not configurable |
| Private Cloud Compute | SDK does not yet expose PCC |
| MCP tools (native bridge) | Not yet implemented; MCP tools not bridged to fm.Tool |
| Agentic loop tracing (`/trace`) | SDK controls the tool loop; chatybot cannot trace individual tool calls |
| TPS metrics / token counts | SDK does not expose usage.prompt_tokens / completion_tokens |
| Concurrent requests | SDK sessions are not safe for concurrent use |
| Image generation | Not supported by the on-device model |
| Multimodal input (images) | Not wired for apple_fm path |

---

## 12. Gotchas and Edge Cases

### 12.1 Temperature Range

The SDK accepts temperature in the range 0.0 to 1.0. Chatybot's `/temp`
command validates 0.0 to 2.0. Setting `/temp 1.5` will pass 1.5 to the SDK,
which may reject it or clamp it. Keep temperature at 1.0 or below for
apple_fm models.

### 12.2 Top-k and Top-p Mutual Exclusion

The SDK's `SamplingMode.random()` allows only one of `top` (top-k) or
`probability_threshold` (top-p). If both `/top_k` and `/top_p` are set,
chatybot passes `top_k` and silently drops `top_p`. There is no warning
printed for this. This is by design since the SDK would raise an error if
both were passed.

### 12.3 Streaming Yields Snapshots, Not Deltas

The SDK's `stream_response()` yields complete text snapshots, not token
deltas. Each yielded value is the full text generated so far. This means
the accumulated response may contain redundant text if not handled
correctly. Chatybot's implementation handles this by using the final
snapshot as the complete response.

### 12.4 Session Per Call

A new `LanguageModelSession` is created for each completion. This means the
SDK does not maintain conversation context across calls. Chatybot
compensates by concatenating chat history into the prompt text. This is
less efficient than reusing a session but ensures chatybot's history
management remains the single source of truth.

### 12.5 Tool Schemas Consume Context

Each registered tool's schema (name, description, parameter definitions)
consumes tokens from the 4096 budget. With 14 tools from `tools_config.toml`,
schemas alone may consume 1400-2800 tokens. This leaves very little room for
the prompt, history, and tool results. Disable unused tools to free
context.

### 12.6 Large Tool Results Cause Overflow

Tool results (file contents, directory listings, command output) are fed
back into the model's context by the SDK. If a tool result is large, the
SDK will raise `ExceededContextWindowSizeError`. There is no way to
truncate tool results before the SDK processes them in the native tool
calling path. The prompt-injection path (fallback when no tools are built)
has the same constraint but `execute_tool_loop()` at least truncates
between turns.

### 12.7 zsh Bracket Globbing

Installing the optional extra with `pip install chatybot[apple_fm]` fails
in zsh because `[...]` is interpreted as a glob pattern. Use quotes:
`pip install 'chatybot[apple_fm]'`. Or install the SDK directly:
`pip install apple-fm-sdk`.

### 12.8 Xcode Agreement

The `apple-fm-sdk` package bundles Swift bridging code that compiles during
installation. If Xcode 26+ is installed but the SDK agreement has not been
accepted, the build will fail with a cryptic error. Open the Xcode
application and accept the agreement prompt before installing the package.

### 12.9 Apple Intelligence Download

Even after enabling Apple Intelligence, the model may not be immediately
available. The system needs to download the model, which can take
significant time depending on network speed. During this period,
`is_available()` returns `(False, MODEL_NOT_READY)` and chatybot displays
"The model is still downloading."

### 12.10 No Token Usage Reporting

The SDK does not expose `usage.prompt_tokens` or `usage.completion_tokens`
like the OpenAI API. Chatybot's TPS metrics, token counting, and
`/context` command will not show accurate token usage for apple_fm
completions. The execution time is still reported.

### 12.11 Duplicate ask_user Tool

If `ask_user` is already defined in the user's `tools_config.toml`,
`build_tools()` will not add the built-in version. This prevents duplicate
tool registration. If the user's `ask_user` definition has different
parameters than the built-in schema, the user's definition takes
precedence.

---

## 12. Testing

### 12.1 Unit Tests

| Test File | Tests | Requires SDK | Description |
|---|---|---|---|
| `test/test_apple_fm_config.py` | 15 | No | Config model, TOML loading, TOML round-trip, minimal config |
| `test/test_apple_fm_tools.py` | 26 | Yes (skipped if not installed) | Type mapping, generable class creation, tool wrapper, build_tools with mock app |

All 41 tests pass. The config tests run on any platform. The tool tests
are automatically skipped when the SDK is not installed.

### 12.2 End-to-End Verification

Verified on macOS 26.6.2, arm64, Python 3.14.7, apple-fm-sdk 0.2.1:

**Basic chat:**
```
chat --> /model apple_fm
Switched to model: Apple Foundation Model (alias: apple_fm)

chat --> list 5 cities in spain
Assistant: Sure! Here are five cities in Spain:

1. Madrid
2. Barcelona
3. Seville
4. Valencia
5. Bilbao

Execution time: 1.49 seconds
```

**Native tool calling (list_directory):**
```
Prompt: Use the list_directory tool to list files in the 'bin' directory.
  [dispatch_tool] tool=list_directory args={'path': 'bin', 'details': True}

Response: Here are the files in the 'bin' directory:
1. migrate_sessions
2. setup_keys.bat
3. setup_keys.sh
4. tool_config
```

**Native tool calling (calculate):**
```
Prompt: What is 15 times 37? Use the calculate tool.
  [dispatch_tool] tool=calculate args={'expression': '15 times 37', 'target_variable': 'result'}
  [dispatch_tool] tool=calculate args={'expression': '15 * 37', 'target_variable': 'result'}

Response: The result of 15 times 37 is 555.
```

The calculate test demonstrates the SDK's internal tool loop: the model
called the tool twice (first with natural language, then with symbolic
notation) before producing the final response.

### 12.3 Test Suite Results

```
test/test_apple_fm_config.py  — 15 passed
test/test_apple_fm_tools.py   — 26 passed (26 skipped without SDK)
Full suite (excluding pre-existing failures) — 831 passed
```

Pre-existing failures unrelated to apple_fm:
- `test/test_capability_error.py` — coroutine mock issue in the unmodified codebase
- `test/test_tool_scratch.py` — scratch directory has leftover files from prior runs

---

## 13. Future Enhancements

| Enhancement | Priority | Notes |
|---|---|---|
| History limiting (last 1-2 turns) | Medium | Would extend usable session from 3-4 turns to 6-8 |
| MCP tool bridge | Low | Bridge MCP tool schemas to fm.Tool subclasses |
| Context limiter integration | Medium | Wire chatybot's context_limiter into the apple_fm path |
| Session caching | Low | Reuse LanguageModelSession across calls if SDK supports multi-turn |
| Agentic loop tracing | Low | SDK controls the loop; may not be possible to trace |
| Private Cloud Compute | Future | When Apple exposes PCC in the SDK, add as a separate model type |
| Custom MLX backends | Future | WWDC 2026 opened the framework to custom LLM backends |

---

## 14. Quick Start

```bash
# 1. Install the SDK
pip install apple-fm-sdk

# 2. Run chatybot
chatybot

# 3. Switch to apple_fm
/model apple_fm

# 4. Chat
list 5 cities in Spain

# 5. For tool use, disable most tools first
/tool disable all
/tool enable calculate
/tool on
what is 15 times 37?

# 6. Check model info
/model info apple_fm

# 7. Adjust temperature
/temp 0.3
```
