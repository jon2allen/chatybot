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
    "huggingface": VendorPreset("huggingface", "https://router.huggingface.co/v1",
                                "HF_API_KEY"),
    "ollama":     VendorPreset("ollama",     "http://localhost:11434/v1"),
    "llama_cpp":  VendorPreset("llama_cpp",  "http://localhost:8080/v1"),
    "jina":       VendorPreset("jina",       "https://api.jina.ai/v1/rerank",
                               "JINA_API_KEY", default_type="reranker"),
}

def vendor_names() -> list[str]:
    """Ordered list of vendor names for the TUI picker."""
    return list(VENDOR_PRESETS.keys())


def get_env_status(config_models: Optional[dict] = None) -> list[dict]:
    """
    Collect all template API keys, config model API keys, and any defined environment
    variables matching API / KEY / TOKEN / SECRET patterns (like `set | grep -i api`).

    Returns a sorted list of dictionaries with metadata for each variable:
    [
        {
            "name": "HF_API_KEY",
            "is_set": True,
            "length": 37,
            "masked": "hf_...89ab",
            "source": "Template (huggingface)",
            "vendor": "huggingface",
            "in_template": True
        },
        ...
    ]
    """
    import os
    import re

    results: dict[str, dict] = {}

    # 1. Add all vendor template presets
    for v_name, preset in VENDOR_PRESETS.items():
        if preset.api_key_env:
            k = preset.api_key_env
            results[k] = {
                "name": k,
                "vendor": v_name,
                "source": f"Template ({v_name})",
                "in_template": True,
            }

    # 2. Add all model keys from loaded config (if provided)
    if config_models:
        items = config_models.items() if hasattr(config_models, "items") else []
        for alias, model in items:
            k = getattr(model, "api_key", None) if not isinstance(model, dict) else model.get("api_key")
            if k and isinstance(k, str) and not k.startswith("http") and len(k) < 80:
                if k not in results:
                    v_str = (getattr(model, "vendor", None) if not isinstance(model, dict) else model.get("vendor")) or alias
                    results[k] = {
                        "name": k,
                        "vendor": v_str,
                        "source": f"Model ({alias})",
                        "in_template": False,
                    }

    # 3. Add any environment variable from os.environ matching API, KEY, TOKEN, SECRET, HF, etc.
    api_pattern = re.compile(r'(api|key|token|secret|huggingface|hf_)', re.IGNORECASE)
    for env_k in os.environ.keys():
        if api_pattern.search(env_k):
            if env_k not in results:
                results[env_k] = {
                    "name": env_k,
                    "vendor": "",
                    "source": "Environment",
                    "in_template": False,
                }

    # 4. Populate status & masked values
    final_list = []
    for k, info in results.items():
        val = os.environ.get(k)
        is_set = val is not None and len(val.strip()) > 0
        if is_set:
            v_str = val.strip()
            length = len(v_str)
            if length <= 6:
                masked = "*" * length
            elif length <= 12:
                masked = f"{v_str[:2]}...{v_str[-2:]}"
            else:
                masked = f"{v_str[:4]}...{v_str[-4:]}"
        else:
            length = 0
            masked = "(not set)"

        final_list.append({
            "name": k,
            "is_set": is_set,
            "length": length,
            "masked": masked,
            "source": info["source"],
            "vendor": info.get("vendor", ""),
            "in_template": info.get("in_template", False),
        })

    # Sort: Template keys first (or defined first), then alphabetically
    final_list.sort(key=lambda x: (not x["in_template"], not x["is_set"], x["name"].lower()))
    return final_list
