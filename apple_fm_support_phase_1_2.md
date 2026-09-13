# Apple Foundation Model Support — Phase 1 & 2 Implementation Report

**Date:** 2026-09-13
**Status:** Implemented and verified end-to-end. Config-layer tests passing. Apple FM chat confirmed working on macOS 26.6.2 with apple-fm-sdk 0.2.1.

---

## Overview

This report documents the integration of Apple's on-device Foundation Model
(`apple-fm-sdk`) into chatybot as a new model type: `/model apple_fm`. The
model runs locally on macOS 26+ via Apple Intelligence — no API key, no
network, no `base_url`.

Phases 1 (config layer) and 2 (inference path) are complete. The existing
OpenAI-compatible inference path is untouched; the apple_fm model type
branches into a parallel completion method.

---

## Architecture

```
chat_config.toml
    [models.apple_fm]
    type = "apple_fm"          ← new discriminator value
         │
         ▼
config_model.py
    AppleFMModelConfig         ← new Pydantic model (BaseModelConfig subclass)
    ModelConfig union          ← ChatModelConfig | RerankerModelConfig | AppleFMModelConfig
         │
         ▼
chatybot_app.py :: chat_completion()
    if model_config["type"] == "apple_fm":
        return await self._apple_fm_completion(prompt, stream)
                                    │
                                    ▼
                         apple_fm_backend.py
                         (lazy import, platform guard)
                                    │
                                    ▼
                         apple_fm_sdk.LanguageModelSession.respond()
```

The OpenAI path (`get_openai_client` → `chat.completions.create`) is never
reached for apple_fm models. The branch happens at the top of
`chat_completion()`, before any client creation or vendor-specific logic.

---

## Files Changed

### Phase 1 — Config Layer

| File | Change |
|---|---|
| `src/chatybot/config_model.py` | New `AppleFMModelConfig` class. Added to discriminated union. New `apple_fm_models()` accessor. `to_toml_string()` categorizes under "APPLE FM MODELS" header. |
| `src/chatybot/vendors.py` | Added `apple_fm` vendor preset (`VendorPreset("apple_fm", "on-device", None, image_support=False)`). |
| `src/chatybot/chat_config.toml` | Added `[models.apple_fm]` entry with `type`, `name`, `context_limit = 4096`, `temperature = 0.7`. |
| `pyproject.toml` | Added `[project.optional-dependencies] apple_fm = ["apple-fm-sdk"]`. |

### Phase 2 — Inference Path

| File | Change |
|---|---|
| `src/chatybot/apple_fm_backend.py` (new) | Platform check, import guard, session management. All `apple_fm_sdk` imports are isolated here. |
| `src/chatybot/chatybot_app.py` | 3-line early branch in `chat_completion()`. New `_apple_fm_completion()` method (~130 lines) handling prompt building, SDK call, and post-processing. |

### Tests

| File | Change |
|---|---|
| `test/test_apple_fm_config.py` (new) | 15 tests covering config model, TOML round-trip, and minimal-config edge cases. All SDK-free. |

---

## Detailed Design Decisions

### 1. Config Model: `AppleFMModelConfig`

```python
class AppleFMModelConfig(BaseModelConfig):
    type: Literal["apple_fm"] = "apple_fm"
    base_url: str = "on-device"      # sentinel, not used for HTTP
    vendor: Optional[str] = "apple"
```

- Extends `BaseModelConfig` (not `ChatModelConfig`) — apple_fm has no image
  generation, no `image_endpoint`, no `image_modalities`.
- `base_url` is overridden from required to `"on-device"` sentinel. The
  `detected_vendor` heuristic in `BaseModelConfig` would otherwise fail to
  classify it.
- `api_key` inherits as `Optional[str] = None` from the base — no key needed.
- `context_limit` and `temperature` are inherited from the base class.

### 2. Multiplatform Strategy

**Install:** Optional extra, not a core dependency.

```toml
[project.optional-dependencies]
apple_fm = ["apple-fm-sdk"]
```

```bash
pip install chatybot[apple_fm]
```

Not platform-gated with `; sys_platform == 'darwin'` because that would
auto-install on all Macs including macOS < 26 and Intel Macs where it won't
work. Explicit opt-in is better.

**Enable:** Three layers, checked in order at runtime:

| Layer | Check | When |
|---|---|---|
| 1. Config file | TOML entry exists | Always (just data, any platform) |
| 2. Import guard | `apple_fm_sdk` importable | First prompt to apple_fm model |
| 3. Model availability | `SystemLanguageModel().is_available()` | First prompt, after import succeeds |

**What happens on `/model apple_fm`:**

| Platform | Switch | First prompt |
|---|---|---|
| macOS 26+ arm64, SDK installed, AI on | Works | Works |
| macOS 26+ arm64, SDK not installed | Works | Error: install instructions |
| macOS 26+ arm64, SDK installed, AI off | Works | Error: enable Apple Intelligence |
| macOS < 26 or Intel Mac | Works | Error: requires macOS 26+ Apple Silicon |
| Linux / Windows | Works | Error: requires macOS 26+ |

The switch always succeeds (it's just config state). Errors surface on
first prompt — matching how chatybot handles other model errors (API key
missing, etc.).

### 3. Backend Module: `apple_fm_backend.py`

All `apple_fm_sdk` imports are isolated in this single module. The rest of
chatybot never imports the SDK directly. The module provides:

- `is_platform_supported()` — macOS 26+ check
- `check_available()` → `(bool, reason)` — combined platform + import check
- `get_model()` → `(model, error)` — cached `SystemLanguageModel` singleton
- `create_session(instructions)` → `(session, error)` — fresh
  `LanguageModelSession` per completion
- `respond(session, prompt)` → `str` — wraps `session.respond()`

A fresh session is created per completion call so that conversation
history is managed by chatybot (not accumulated by the SDK session). This
matches chatybot's existing pattern where `chat_completion()` rebuilds the
full message list each call.

### 4. Completion Method: `_apple_fm_completion()`

Mirrors the OpenAI path's post-processing:

- **Prompt building:** buffer placeholders, file buffer, prompt buffer,
  tool context injection, code-only flag, chat history concatenation
- **System message:** config system message + tool context + agentic
  instructions (when tool mode is on)
- **SDK call:** `create_session(instructions=...)` then `respond(session, prompt)`
- **Post-processing:** logging, session activity, chat history append,
  session turn recording, tool auto-launch detection

Message-list prompts (from the tool loop) are handled by concatenating
roles into text (`User: ...`, `Assistant: ...`), since the SDK's
`respond()` takes a single string.

### 5. Dependency Management

`apple-fm-sdk` is an optional extra. The import in `apple_fm_backend.py`
is wrapped in try/except:

```python
try:
    import apple_fm_sdk as fm
    _SDK_AVAILABLE = True
except ImportError as e:
    fm = None
    _SDK_AVAILABLE = False
    _IMPORT_ERROR = str(e)
```

Chatybot starts and runs normally without the SDK. Only `/model apple_fm`
followed by a prompt triggers the check.

---

## Python Requirements

| Requirement | Chatybot | apple-fm-sdk | Your System |
|---|---|---|---|
| Python | >=3.11 | >=3.10 | 3.14.7 |
| macOS | Any | 26.0+ | 26.6.2 |
| Xcode | Not required | 26.0+ (SDK agreement) | Needs verification |
| Hardware | Any | Apple Silicon M1+ | arm64 |
| Apple Intelligence | N/A | Must be enabled | User must enable |

Install: `pip install chatybot[apple_fm]` or `pip install apple-fm-sdk`

---

## Feature Status

| Feature | Status |
|---|---|
| `/model apple_fm` switch | Works |
| `/listmodels` shows apple_fm | Works |
| `/model info apple_fm` | Works (shows config context_limit) |
| Basic chat (non-streaming) | Implemented, needs SDK to test |
| Chat history | Implemented (history concatenated into prompt) |
| System message | Implemented (passed as session instructions) |
| Tool mode / agentic loop | Implemented (prompt-injection approach) |
| Streaming | Implemented via `session.stream_response()` async iterator |
| Native `fm.Tool` calling | Implemented — `build_tools()` bridges `tools_config.toml` tools to `fm.Tool` subclasses, delegates `call()` to `dispatch_tool()` |
| TPS metrics / token counts | Not yet (SDK doesn't expose usage the same way) |
| Config TUI support | Vendor preset registered; full TUI flow untested |

---

## Test Results

```
test/test_apple_fm_config.py — 15 passed in 0.07s
test/test_config_manager.py  — 15 passed in 0.06s
Full suite (excluding pre-existing failures) — 814 passed in 74.59s
```

Pre-existing failures (not caused by these changes):
- `test/test_capability_error.py` — coroutine mock issue, fails on unmodified codebase
- `test/test_tool_scratch.py` — scratch directory has leftover files from prior runs

### End-to-End Verification (2026-09-13)

Verified on macOS 26.6.2, arm64, Python 3.14.7, apple-fm-sdk 0.2.1:

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

Response string format (`str(response)`) confirmed working — returns plain
text, no `.content` attribute access needed.

---

## How to Test End-to-End

### Step 1 — Install the SDK

```bash
cd /Users/jon2allen/github/chatybot
.venv/bin/pip install apple-fm-sdk
```

Or via the optional extra (quotes required in zsh to avoid bracket globbing):

```bash
.venv/bin/pip install 'chatybot[apple_fm]'
```

Requires Xcode 26+ with the SDK agreement accepted. If Xcode prompts to
accept the agreement, open the Xcode app and accept it.

### Step 2 — Verify the backend module

```bash
.venv/bin/python -c "
from chatybot.apple_fm_backend import check_available
ready, reason = check_available()
print(f'Ready: {ready}')
print(f'Reason: {reason}')
"
```

Expected output with SDK installed and Apple Intelligence on:
```
Ready: True
Reason:
```

### Step 3 — Run chatybot

```bash
.venv/bin/chatybot
```

### Step 4 — Switch and chat

```
/model apple_fm
hello, how are you?
```

### Step 5 — Verify model info

```
/model info apple_fm
```

Should show:
```
Model Information: Apple Foundation Model (alias: apple_fm)
Provider:        apple
Base URL:        on-device
Context Limit:   4,096 tokens [Config (Override)]
Temperature:     0.7
```

---

## Known Limitations and Assumptions

1. **Response string format:** Confirmed working. `str(response)` returns
   the plain text of the model's response. Verified with apple-fm-sdk 0.2.1.

2. **Streaming:** Implemented. The SDK provides `session.stream_response()`
   as an async iterator yielding text chunks. When `stream=True` (toggled
   via `/stream`), `_apple_fm_completion()` iterates chunks and prints them
   with `flush=True` for real-time output.

3. **No token counts:** The SDK does not expose `usage.prompt_tokens` /
   `usage.completion_tokens` like the OpenAI API. TPS metrics and token
   counting are not available for apple_fm completions.

4. **Session per call:** A new `LanguageModelSession` is created for each
   completion. This is simpler and matches chatybot's stateless pattern, but
   may have higher overhead than reusing a session. If the SDK maintains
   conversation context across `respond()` calls, a future optimization could
   cache sessions per conversation.

5. **Tool calling via native fm.Tool:** Implemented. When `tool_mode` is
   enabled, `build_tools()` reads `tools_config.toml` and creates `fm.Tool`
   subclasses for each enabled tool. Each tool's `call()` method delegates to
   chatybot's existing `dispatch_tool()`, so all tool execution (subprocess
   dispatch, MCP, built-in tools) works unchanged. The built-in `ask_user`
   tool is also registered natively. The SDK handles the tool loop internally
   — the model calls tools, the SDK executes `call()`, feeds results back,
   and the model continues until it produces a final response. No
   prompt-injection or `execute_tool_loop()` needed.

6. **Config TUI:** The `apple_fm` vendor preset is registered in
   `vendors.py`, but the full TUI flow for creating an apple_fm model
   through the interactive config editor has not been tested.

---

## Next Phases

### Phase 4 — Polish
- Config TUI: full apple_fm model creation flow
- `/model info apple_fm`: show "On-device" instead of base_url
- Error messages: detect specific `is_available()` reasons and map to
  actionable guidance
- Session caching: reuse `LanguageModelSession` across calls if the SDK
  supports multi-turn context
- MCP tools: bridge MCP tool schemas to `fm.Tool` subclasses (currently
  only `tools_config.toml` tools and `ask_user` are registered natively)
- Agentic loop tracing: capture tool calls made by the SDK for `/trace`
