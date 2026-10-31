# Chatybot Config Data Model — Design

**Document Version:** 1.1
**Date:** July 23, 2026 (date of the last commit touching this file: `d40bd04`, 2026-07-23 11:35 -0400)
**Status:** Implemented with deviations — the design landed as `src/chatybot/config_model.py` and then grew substantially beyond this document; validated against source on October 31, 2026. See Implementation Deviations, the Batch Addendum, and Open Items below
**Applies To:** `src/chatybot/config_model.py` (Pydantic models), `src/chatybot/config_manager.py` (consumers), `chat_config.toml` / `test_config.toml`

---

## Implementation Deviations (as-built vs. this proposal)

Validated claim-by-claim on 2026-10-31. What matches: Pydantic v2 `BaseModel`, the discriminated union on `type`, `ModelConfig` union type, alias injection from the TOML key, `api_key` as env-var-name convention (with the NOTE's suggested `resolve_api_key()` now implemented via `env_utils`), `ChatConfig.from_toml`, and the `chat_models()` / `reranker_models()` / `image_capable_models()` accessors.

The deviations — the implementation grew past this document:

1. **The model type taxonomy is stale.** This document specifies `"chat"` and `"reranker"` only. `config_model.py` ships **four** types: `chat`, `reranker`, `decision` (`DecisionModelConfig`, the `/decide` TypeSafe Jev endpoint, with `endpoint_path`), and `apple_fm` (`AppleFMModelConfig`, Apple on-device Foundation Model, which overrides `base_url` to a `"on-device"` sentinel and `vendor` to `"apple"`).
2. **Batch capability is missing entirely** — see the Addendum below. Rerank, by contrast, was already covered here and remains accurate.
3. **`BaseModelConfig` grew fields** absent from the field analysis: `prompt_caching`, `prompt_cache_key`, `input_cost_per_mtok` (from the prompt-caching proposal), and `context_limit`. `api_key` also changed from required `str` to `Optional[str]` — necessary for `apple_fm` and local models.
4. **The top-level container grew sections** beyond `image_generation` + `models`: `[batch]` (`BatchSettings`), `[mcp]` (`MCPConfig`/`MCPServerConfig`), `[default]` (`DefaultSettings`: `model`, `prompt_caching`), and global settings (`system_message`, `max_tokens`, `top_p`, `top_k`, `frequency_penalty`, `presence_penalty`, `enable_chat_history`, `auto_truncate`, `auto_truncate_pct` with a 10-100 validator).
5. **Round-trip serialization exists**: `to_toml_string()`/`to_toml()` with category-aware formatting — not covered by this design at all.
6. **`detect_provider()` vendor heuristics** (base_url/api_key/name-based, 14 providers) and the `detected_vendor` property are not specified here.
7. **The `nvidia_1` WARNING is still valid** — `test_config.toml` still has `image_endpoint` on `nvidia_1` without `image_generation = true`, and no cross-field validator was ever added.
8. **Field analysis counts are stale**: this document analyzed 27 models; `test_config.toml` now has 29.

## Addendum — Batch Capability (as-built, 2026-10-31)

Batch is a **capability flag on chat models plus a global settings section**, not a separate model type. From batch proposal v3 (Phase 1, branch `batch_api`):

- `ChatModelConfig.batch: bool = False` — marks a model usable for asynchronous provider batch jobs (`/batch start` → `/batch run`). The model `name` must be a provider batch variant (e.g. `openai/gpt-oss-120b:batch` on OpenRouter).
- `ChatConfig.batch: BatchSettings` — global defaults:
  - `default_model: str | None` — batch model alias used when the active model is not batch-capable
  - `max_cost_usd: float = 5.00` — pre-submit cost-estimate ceiling; `/batch run` refuses above it unless `force=true`
  - `max_open_per_provider: int = 3` — cap on simultaneously open batches per provider
  - `keep_remote_files: bool = False` — Phase 2 (Mistral Files API) input/output file retention
- Accessors: `ChatConfig.batch_capable_models()`; `ConfigManager.list_batch_capable_models()` and `ConfigManager.get_batch_config()`.

## Open Items

1. **Update or retire this document**: the class diagram, field tables, and Pydantic sketch now describe roughly half of `config_model.py`. Either regenerate them from the current implementation or mark this file historical and point to `config_model.py`'s docstrings as the living reference.
2. **Resolve the `nvidia_1` question** — `image_endpoint` without `image_generation = true` is still ambiguous; decide config-bug vs. intentional, then add (or explicitly reject) the cross-field validator.
3. **Document the `decision` and `apple_fm` types** in the taxonomy and diagram if this document is kept current (their fields are only in `config_model.py` docstrings today).
4. **Tighten `vendor` to a `Literal` enum** — design decision 5 said "we can later tighten this"; `detect_provider()` already maintains a de facto 14-value enum that a `Literal` could formalize.

---

## Field Analysis

After reviewing all 27 models in `test_config.toml`, the following fields appear across model entries:

### Universal Fields (present on every model)
| Field | Type | Notes |
|-------|------|-------|
| `name` | `str` | The actual API model identifier (e.g. `"gemini-2.5-flash"`) |
| `base_url` | `str` | API endpoint base URL |
| `api_key` | `str` | Environment variable name holding the actual key |

### Common Optional Fields (most models)
| Field | Type | Default | Notes |
|-------|------|---------|-------|
| `temperature` | `float` | `None` | Sampling temperature |
| `top_k` | `int` | `None` | Top-K sampling param |

### Capability / Type Fields
| Field | Type | Default | Notes |
|-------|------|---------|-------|
| `type` | `str` | `"chat"` | `"chat"` or `"reranker"` |
| `vendor` | `str` | `None` | `"mistral"`, `"google"`, `"openai"`, `"openrouter"` |
| `image_generation` | `bool` | `False` | Whether model supports image gen |
| `image_endpoint` | `str` | `None` | Sub-path for image requests (e.g. `"/images/generations"`) |
| `image_modalities` | `list[str]` | `None` | For OpenRouter-style: `["image"]`, `["image","text"]` |

### Top-Level Section
| Field | Type | Notes |
|-------|------|-------|
| `default_dir` | `str` | Default save dir for generated images |
| `default_size` | `str` | e.g. `"1024x1024"` |
| `default_quality` | `str` | e.g. `"standard"` |

---

## Model Type Taxonomy

```
ModelType:
  "chat"      — standard LLM chat completion (the vast majority)
  "reranker"  — re-ranking API (cohere_reranker, remote_jina_rerank)
```

When `type == "reranker"`:
- `temperature`, `top_k`, `image_*` fields are not applicable

When `type == "chat"` and `image_generation == True`:
- `image_endpoint` is required
- `vendor` is required (determines how the image call is structured)
- `image_modalities` may be set for OpenRouter-style requests

---

## Design Decisions

1. **Use Pydantic v2 `BaseModel`** — already in the venv (`pydantic 2.12.5`), gives free validation + schema export.
2. **Discriminated Union** — use `type` literal to split `ChatModelConfig` from `RerankerModelConfig`, enabling strict validation of which fields are required.
3. **`ModelConfig` = Union type** — the `models` dict in `ChatConfig` maps alias → `ModelConfig`.
4. **`api_key` stores env var name, not actual key** — keep this convention, do not change semantics.
5. **`vendor` as `Optional[str]`** — not all models set it; we can later tighten this to a `Literal` enum.
6. **`image_modalities` as `Optional[list[str]]`** — OpenRouter-specific, absent on other vendors.
7. **Alias key** — the TOML key (e.g. `mistral_1`) is the alias/handle used in chatybot; it should be preserved as a field `alias` when loading from dict.

---

## Proposed Class Diagram

```mermaid
classDiagram
    class ImageGenerationSettings {
        +str default_dir
        +str default_size
        +str default_quality
    }

    class BaseModelConfig {
        <<abstract>>
        +str alias
        +str name
        +str base_url
        +str api_key
        +Optional[float] temperature
        +Optional[int] top_k
    }

    class ChatModelConfig {
        +Literal["chat"] type = "chat"
        +Optional[str] vendor
        +bool image_generation = False
        +Optional[str] image_endpoint
        +Optional[list[str]] image_modalities
    }

    class RerankerModelConfig {
        +Literal["reranker"] type = "reranker"
    }

    class ChatConfig {
        +ImageGenerationSettings image_generation
        +dict[str, ModelConfig] models
        +classmethod from_toml(path) ChatConfig
        +list[ChatModelConfig] chat_models()
        +list[RerankerModelConfig] reranker_models()
        +list[ChatModelConfig] image_capable_models()
    }

    BaseModelConfig <|-- ChatModelConfig
    BaseModelConfig <|-- RerankerModelConfig
    ChatConfig "1" --> "1" ImageGenerationSettings
    ChatConfig "1" --> "0..*" BaseModelConfig : models
```

---

## Pydantic Implementation Sketch

```python
from __future__ import annotations
from typing import Annotated, Literal, Optional, Union
from pydantic import BaseModel, Field


class ImageGenerationSettings(BaseModel):
    default_dir: str = "~/chatybot_images"
    default_size: str = "1024x1024"
    default_quality: str = "standard"


class BaseModelConfig(BaseModel):
    alias: str = ""          # populated from the TOML key, not the TOML body
    name: str
    base_url: str
    api_key: str
    temperature: Optional[float] = None
    top_k: Optional[int] = None


class ChatModelConfig(BaseModelConfig):
    type: Literal["chat"] = "chat"
    vendor: Optional[str] = None
    image_generation: bool = False
    image_endpoint: Optional[str] = None
    image_modalities: Optional[list[str]] = None


class RerankerModelConfig(BaseModelConfig):
    type: Literal["reranker"] = "reranker"


# Discriminated union on `type` field
ModelConfig = Annotated[
    Union[ChatModelConfig, RerankerModelConfig],
    Field(discriminator="type"),
]


class ChatConfig(BaseModel):
    image_generation: ImageGenerationSettings = Field(
        default_factory=ImageGenerationSettings
    )
    models: dict[str, ModelConfig] = {}

    @classmethod
    def from_toml(cls, path: str) -> "ChatConfig":
        import tomllib
        with open(path, "rb") as f:
            raw = tomllib.load(f)
        # Inject alias from dict key into each model entry
        for alias, model_data in raw.get("models", {}).items():
            model_data["alias"] = alias
        return cls.model_validate(raw)

    def chat_models(self) -> list[ChatModelConfig]:
        return [m for m in self.models.values() if isinstance(m, ChatModelConfig)]

    def reranker_models(self) -> list[RerankerModelConfig]:
        return [m for m in self.models.values() if isinstance(m, RerankerModelConfig)]

    def image_capable_models(self) -> list[ChatModelConfig]:
        return [m for m in self.chat_models() if m.image_generation]
```

---

## Key Notes / Open Questions

> [!NOTE]
> `api_key` is the **name of an environment variable** (e.g. `"MISTRAL_API_KEY"`), not the key itself.
> If we want runtime key resolution, a `resolve_api_key()` method on `BaseModelConfig` could call `os.getenv(self.api_key)`.

> [!WARNING]
> `nvidia_1` has `image_endpoint` set but **not** `image_generation = true`. This may be a config bug — or intentional. Worth clarifying before enforcing a validator that requires both together.

> [!TIP]
> Once validated, `ChatConfig` could be the single source of truth passed to all model-selection UI, alias lookups, and API dispatch logic in `chatybot_app.py`.
