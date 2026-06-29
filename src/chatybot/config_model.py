"""
config_model.py — Chatybot configuration data model.

Provides Pydantic v2 models for loading and validating chat_config.toml.

Model hierarchy:
    BaseModelConfig
    ├── ChatModelConfig    (type = "chat")    — standard LLM chat + optional image generation
    └── RerankerModelConfig (type = "reranker") — re-ranking API endpoints

Top-level container: ChatConfig
    - image_generation: ImageGenerationSettings
    - models: dict[alias → ModelConfig]

Usage:
    from chatybot.config_model import ChatConfig

    config = ChatConfig.from_toml("~/.config/chatybot/chat_config.toml")
    for model in config.image_capable_models():
        print(model.alias, model.vendor)
"""

from __future__ import annotations

import os
import tomllib
from pathlib import Path
from typing import Annotated, Literal, Optional, Union

from pydantic import BaseModel, Field


# ============================================================================
# IMAGE GENERATION SETTINGS
# ============================================================================

class ImageGenerationSettings(BaseModel):
    """Global defaults for image generation output."""

    default_dir: str = "~/chatybot_images"
    """Directory where generated images are saved."""

    default_size: str = "1024x1024"
    """Default image resolution; 1024x1024 is supported by all major image models."""

    default_quality: str = "standard"
    """Default quality tier (e.g. 'standard', 'hd')."""


# ============================================================================
# BASE MODEL CONFIG
# ============================================================================

class BaseModelConfig(BaseModel):
    """
    Fields shared by all model entries regardless of type.

    Note: ``api_key`` stores the *name* of an environment variable,
    not the actual key value (e.g. ``"MISTRAL_API_KEY"``).
    Call :meth:`resolve_api_key` to retrieve the live value.
    """

    alias: str = ""
    """The TOML table key used to reference this model (e.g. 'mistral_1').
    Injected at load time from the dict key — not present in the TOML body itself."""

    name: str
    """The API model identifier sent in requests (e.g. 'mistral-large-2512')."""

    base_url: str
    """Base URL of the API endpoint."""

    api_key: Optional[str] = None
    """Name of the environment variable holding the actual API key."""

    temperature: Optional[float] = None
    """Sampling temperature. None means 'use provider default'."""

    top_k: Optional[int] = None
    """Top-K sampling parameter. None means 'use provider default'."""

    def resolve_api_key(self) -> Optional[str]:
        """Return the actual API key by reading the named environment variable."""
        if not self.api_key:
            return None
        return os.getenv(self.api_key)

    @property
    def detected_vendor(self) -> str:
        """Heuristically detect the vendor name based on base_url, api_key, or name if not explicitly set."""
        explicit = getattr(self, "vendor", None)
        if explicit:
            return explicit
        
        base_url_lower = self.base_url.lower()
        api_key_lower = (self.api_key or "").lower()
        name_lower = self.name.lower()
        
        if "openrouter" in base_url_lower or "openrouter" in api_key_lower:
            return "openrouter"
        if "googleapis.com" in base_url_lower or "gemini" in api_key_lower or "google" in name_lower or "google" in base_url_lower:
            return "google"
        if "mistral" in base_url_lower or "mistral" in api_key_lower:
            return "mistral"
        if "openai.com" in base_url_lower or "openai" in api_key_lower:
            return "openai"
        if "nvidia" in base_url_lower or "nvidia" in api_key_lower:
            return "nvidia"
        if "jina" in base_url_lower or "jina" in api_key_lower:
            return "jina"
        if "localhost:11434" in base_url_lower or "ollama" in base_url_lower or "ollama" in api_key_lower:
            return "ollama"
        if "localhost:8080" in base_url_lower or "llama.cpp" in base_url_lower or "llama-cpp" in base_url_lower:
            return "llama_cpp"
        if "publicai" in base_url_lower or "swiss" in api_key_lower:
            return "publicai"
        if "bytez" in base_url_lower or "bytez" in api_key_lower:
            return "bytez"
        return ""


# ============================================================================
# CHAT MODEL CONFIG
# ============================================================================

class ChatModelConfig(BaseModelConfig):
    """
    Configuration for a standard chat-completion (or image-generation) model.

    Image generation fields are optional and only relevant when
    ``image_generation`` is ``True``.
    """

    type: Literal["chat"] = "chat"
    """Discriminator field — always 'chat' for this class."""

    vendor: Optional[str] = None
    """Vendor identifier used to select the correct API adapter.
    Known values: 'mistral', 'google', 'openai', 'openrouter'.
    Required when image_generation is True."""

    image_generation: bool = False
    """Whether this model supports image generation requests."""

    image_endpoint: Optional[str] = None
    """Sub-path appended to base_url for image requests.
    e.g. '/images/generations' or '/chat/completions'."""

    image_modalities: Optional[list[str]] = None
    """OpenRouter-style modality list for image requests.
    e.g. ['image'] or ['image', 'text']."""


# ============================================================================
# RERANKER MODEL CONFIG
# ============================================================================

class RerankerModelConfig(BaseModelConfig):
    """
    Configuration for a re-ranking API endpoint.

    Re-rankers do not use temperature, top_k, or image-generation fields.
    """

    type: Literal["reranker"] = "reranker"
    """Discriminator field — always 'reranker' for this class."""


# ============================================================================
# DISCRIMINATED UNION
# ============================================================================

ModelConfig = Annotated[
    Union[ChatModelConfig, RerankerModelConfig],
    Field(discriminator="type"),
]
"""Union of all supported model config types, discriminated on the ``type`` field."""


# ============================================================================
# TOP-LEVEL CONFIG CONTAINER
# ============================================================================

class ChatConfig(BaseModel):
    """
    Top-level configuration container, corresponding to chat_config.toml.

    Load with :meth:`from_toml`:

    .. code-block:: python

        config = ChatConfig.from_toml("~/.config/chatybot/chat_config.toml")
    """

    image_generation: ImageGenerationSettings = Field(
        default_factory=ImageGenerationSettings
    )
    """Global image generation defaults."""

    models: dict[str, ModelConfig] = {}
    """All model entries, keyed by their TOML alias (e.g. 'mistral_1')."""

    system_message: Optional[str] = "You are a helpful assistant."
    """Global default system message."""

    default_model: Optional[str] = None
    """Global default model alias."""

    max_tokens: Optional[int] = None
    """Global default max tokens."""

    temperature: Optional[float] = None
    """Global default temperature."""

    top_p: Optional[float] = None
    """Global default top_p."""

    top_k: Optional[int] = None
    """Global default top_k."""

    frequency_penalty: Optional[float] = None
    """Global default frequency penalty."""

    presence_penalty: Optional[float] = None
    """Global default presence penalty."""

    # ------------------------------------------------------------------
    # Constructors
    # ------------------------------------------------------------------

    @classmethod
    def _prepare_raw(cls, raw: dict) -> dict:
        """
        Inject defaults into each model entry before Pydantic validation.

        - Sets ``alias`` from the TOML table key.
        - Defaults ``type`` to ``"chat"`` for models that omit it, so the
          discriminated union can resolve correctly.
        """
        for alias, model_data in raw.get("models", {}).items():
            model_data["alias"] = alias
            model_data.setdefault("type", "chat")
        return raw

    @classmethod
    def from_toml(cls, path: str | Path) -> "ChatConfig":
        """
        Load and validate a chat_config.toml file.

        The TOML table key for each model (e.g. 'mistral_1') is injected
        as the ``alias`` field.  Models without an explicit ``type`` field
        default to ``"chat"``.

        Args:
            path: Path to the TOML config file. ``~`` is expanded.

        Returns:
            A validated :class:`ChatConfig` instance.

        Raises:
            FileNotFoundError: If the config file does not exist.
            tomllib.TOMLDecodeError: If the file is not valid TOML.
            pydantic.ValidationError: If a model entry fails validation.
        """
        resolved = Path(path).expanduser().resolve()
        with open(resolved, "rb") as f:
            raw = tomllib.load(f)
        return cls.model_validate(cls._prepare_raw(raw))

    @classmethod
    def from_toml_string(cls, toml_str: str) -> "ChatConfig":
        """
        Load and validate from a raw TOML string (useful for testing).

        Args:
            toml_str: TOML content as a string.

        Returns:
            A validated :class:`ChatConfig` instance.
        """
        raw = tomllib.loads(toml_str)
        return cls.model_validate(cls._prepare_raw(raw))

    # ------------------------------------------------------------------
    # Accessors / Filters
    # ------------------------------------------------------------------

    def chat_models(self) -> list[ChatModelConfig]:
        """Return all models of type 'chat'."""
        return [m for m in self.models.values() if isinstance(m, ChatModelConfig)]

    def reranker_models(self) -> list[RerankerModelConfig]:
        """Return all models of type 'reranker'."""
        return [m for m in self.models.values() if isinstance(m, RerankerModelConfig)]

    def image_capable_models(self) -> list[ChatModelConfig]:
        """Return chat models that have ``image_generation = True``."""
        return [m for m in self.chat_models() if m.image_generation]

    def get_model(self, alias: str) -> Optional[ModelConfig]:
        """
        Look up a model by its alias.

        Args:
            alias: The TOML table key (e.g. 'mistral_1').

        Returns:
            The matching :class:`ModelConfig`, or ``None`` if not found.
        """
        return self.models.get(alias)

    def aliases(self) -> list[str]:
        """Return all model aliases in definition order."""
        return list(self.models.keys())

    def by_vendor(self, vendor: str) -> list[ChatModelConfig]:
        """
        Return all chat models matching a given vendor string.

        Args:
            vendor: e.g. 'mistral', 'google', 'openai', 'openrouter'
        """
        return [
            m for m in self.chat_models()
            if m.vendor and m.vendor.lower() == vendor.lower()
        ]

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def to_toml_string(self) -> str:
        """
        Serialize the configuration back to a beautifully formatted TOML string.

        Models are categorized and ordered with section headers (e.g. Chat Models,
        OpenRouter Models, NVIDIA NIM Models, etc.) to match the original style.
        """
        lines = []

        # 1. Global settings (if specified)
        global_params = {
            "system_message": self.system_message,
            "default_model": self.default_model,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "top_p": self.top_p,
            "top_k": self.top_k,
            "frequency_penalty": self.frequency_penalty,
            "presence_penalty": self.presence_penalty,
        }
        has_global_params = any(v is not None for v in global_params.values())
        if has_global_params:
            lines.append("# ============================================================================")
            lines.append("# GLOBAL SETTINGS")
            lines.append("# ============================================================================")
            lines.append("")
            for k, v in global_params.items():
                if v is not None:
                    if isinstance(v, str):
                        lines.append(f'{k} = "{v}"')
                    elif isinstance(v, bool):
                        lines.append(f'{k} = {str(v).lower()}')
                    else:
                        lines.append(f'{k} = {v}')
            lines.append("")

        # 2. Global image generation settings
        lines.append("# ============================================================================")
        lines.append("# IMAGE GENERATION SETTINGS")
        lines.append("# ============================================================================")
        lines.append("")
        lines.append("[image_generation]")
        for k, v in self.image_generation.model_dump(exclude_none=True).items():
            if isinstance(v, str):
                lines.append(f'{k} = "{v}"')
            else:
                lines.append(f'{k} = {v}')
        lines.append("")

        # 2. Categorize models to match the original TOML organization
        categories: dict[str, list[tuple[str, ModelConfig]]] = {
            "CHAT MODELS": [],
            "OPENROUTER MODELS": [],
            "NVIDIA NIM MODELS": [],
            "PUBLICAI MODELS": [],
            "BYTEZ MODELS": [],
            "OLLAMA MODELS": [],
            "JINA RERANKER MODELS": [],
        }

        for alias, model in self.models.items():
            base_url = model.base_url.lower()
            if "openrouter" in base_url and model.type == "reranker":
                # Cohere reranker goes with OpenRouter
                categories["OPENROUTER MODELS"].append((alias, model))
            elif "jina" in base_url or model.type == "reranker":
                categories["JINA RERANKER MODELS"].append((alias, model))
            elif "openrouter.ai" in base_url:
                categories["OPENROUTER MODELS"].append((alias, model))
            elif "nvidia" in base_url or "integrate.api.nvidia" in base_url:
                categories["NVIDIA NIM MODELS"].append((alias, model))
            elif "publicai.co" in base_url:
                categories["PUBLICAI MODELS"].append((alias, model))
            elif "bytez.com" in base_url:
                categories["BYTEZ MODELS"].append((alias, model))
            elif "11434" in base_url or "localhost" in base_url:
                categories["OLLAMA MODELS"].append((alias, model))
            else:
                categories["CHAT MODELS"].append((alias, model))

        # Write each category out with clean formatting
        for cat_name, models_list in categories.items():
            if not models_list:
                continue

            lines.append("# ============================================================================")
            lines.append(f"# {cat_name}")
            lines.append("# ============================================================================")
            lines.append("")

            for alias, model in models_list:
                lines.append(f"[models.{alias}]")
                data = model.model_dump(exclude_none=True)
                data.pop("alias", None)

                # Prioritize keys for display: name first, then type, then alphabetical order
                ordered_keys = sorted(data.keys(), key=lambda x: (x != "name", x != "type", x))

                for k in ordered_keys:
                    v = data[k]
                    if isinstance(v, str):
                        lines.append(f'{k} = "{v}"')
                    elif isinstance(v, bool):
                        lines.append(f'{k} = {str(v).lower()}')
                    elif isinstance(v, list):
                        formatted_list = ", ".join(f'"{item}"' for item in v)
                        lines.append(f'{k} = [{formatted_list}]')
                    else:
                        lines.append(f'{k} = {v}')
                lines.append("")

        return "\n".join(lines)

    def to_toml(self, path: str | Path) -> None:
        """
        Serialize the current configuration back to a TOML file.

        Args:
            path: Target file path. ``~`` is expanded.
        """
        resolved = Path(path).expanduser().resolve()
        resolved.parent.mkdir(parents=True, exist_ok=True)
        with open(resolved, "w", encoding="utf-8") as f:
            f.write(self.to_toml_string())
