# src/chatybot/vendors.py
"""Vendor preset definitions for the Config TUI and model creation."""

from dataclasses import dataclass
from typing import Optional

@dataclass(frozen=True)
class VendorPreset:
    name: str
    base_url: str
    api_key_env: Optional[str] = None
    image_support: bool = False
    default_type: str = "chat"       # "chat" or "reranker"

VENDOR_PRESETS: dict[str, VendorPreset] = {
    "mistral":    VendorPreset("mistral",    "https://api.mistral.ai/v1",
                               "MISTRAL_API_KEY", image_support=True),
    "google":     VendorPreset("google",     "https://generativelanguage.googleapis.com/v1beta/openai/",
                               "GEMINI_API_KEY", image_support=True),
    "openai":     VendorPreset("openai",     "https://api.openai.com/v1",
                               "OPENAI_API_KEY", image_support=True),
    "openrouter": VendorPreset("openrouter", "https://openrouter.ai/api/v1",
                               "OPENROUTER_API_KEY"),
    "nvidia":     VendorPreset("nvidia",     "https://integrate.api.nvidia.com/v1",
                               "NVIDIA_API"),
    "publicai":   VendorPreset("publicai",   "https://api.publicai.co/v1",
                               "SWISS_API_KEY"),
    "bytez":      VendorPreset("bytez",      "https://api.bytez.com/models/v2/openai/v1",
                               "BYTEZ_API_KEY"),
    "ollama":     VendorPreset("ollama",     "http://localhost:11434/v1"),
    "llama_cpp":  VendorPreset("llama_cpp",  "http://localhost:8080/v1"),
    "jina":       VendorPreset("jina",       "https://api.jina.ai/v1/rerank",
                               "JINA_API_KEY", default_type="reranker"),
}

def vendor_names() -> list[str]:
    """Ordered list of vendor names for the TUI picker."""
    return list(VENDOR_PRESETS.keys())
