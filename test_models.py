#!/usr/bin/env python3
"""
test_models.py

A short script to test config_model.py. It loads test_config.toml,
lists all models, and searches for all models that have an NVIDIA endpoint
(base_url containing 'nvidia').
"""

import sys
from pathlib import Path

# Add src/ to python path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from chatybot.config_model import ChatConfig

def main():
    config_path = Path(__file__).parent / "test_config.toml"
    if not config_path.exists():
        print(f"Error: {config_path} not found.")
        sys.exit(1)

    print(f"Loading configuration from: {config_path}")
    cfg = ChatConfig.from_toml(config_path)

    # 1. List all models
    print("\n=== All Loaded Models ===")
    for alias, model in cfg.models.items():
        m_type = getattr(model, "type", "unknown")
        print(f"Alias: {alias:<25} | Name: {model.name:<45} | Type: {m_type}")

    # 2. Search for models with an NVIDIA endpoint
    print("\n=== Models with NVIDIA Endpoints (base_url containing 'nvidia') ===")
    nvidia_models = []
    for alias, model in cfg.models.items():
        if "nvidia" in model.base_url.lower():
            nvidia_models.append(model)
            print(f"Alias: {alias:<25} | Name: {model.name:<45} | Base URL: {model.base_url}")

    print(f"\nFound {len(nvidia_models)} model(s) with an NVIDIA endpoint.")

if __name__ == "__main__":
    main()
