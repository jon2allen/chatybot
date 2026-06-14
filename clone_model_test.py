#!/usr/bin/env python3
"""
clone_model_test.py

A script to load test_config.toml, clone the mistral_1 model to mistral_1_lowtemp,
set its temperature to 0.1, and save the updated configuration to test2_config.toml.
"""

import sys
from pathlib import Path

# Add src/ to python path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from chatybot.config_model import ChatConfig

def main():
    root_dir = Path(__file__).parent
    config_path = root_dir / "test_config.toml"
    output_path = root_dir / "test2_config.toml"

    if not config_path.exists():
        print(f"Error: {config_path} not found.")
        sys.exit(1)

    print(f"Loading configuration from: {config_path}")
    cfg = ChatConfig.from_toml(config_path)

    # 1. Check if mistral_1 exists
    if "mistral_1" not in cfg.models:
        print("Error: 'mistral_1' model not found in configuration.")
        sys.exit(1)

    print("Cloning 'mistral_1' to 'mistral_1_lowtemp'...")
    mistral_1 = cfg.models["mistral_1"]

    # 2. Clone the model using model_copy and update the fields
    # Using Pydantic's model_copy to clone with fields update
    cloned_model = mistral_1.model_copy(update={
        "alias": "mistral_1_lowtemp",
        "temperature": 0.1
    })

    # 3. Insert the cloned model into the ChatConfig models dict
    cfg.models["mistral_1_lowtemp"] = cloned_model
    print(f"Cloned model: {cloned_model}")

    # 4. Save the configuration to test2_config.toml
    print(f"Saving updated configuration to: {output_path}")
    cfg.to_toml(output_path)

    # 5. Reload to verify the changes
    print("\nVerifying 'test2_config.toml' load...")
    cfg2 = ChatConfig.from_toml(output_path)
    if "mistral_1_lowtemp" in cfg2.models:
        loaded_clone = cfg2.models["mistral_1_lowtemp"]
        print("Success! Loaded cloned model successfully:")
        print(f"  Alias: {loaded_clone.alias}")
        print(f"  Name: {loaded_clone.name}")
        print(f"  Temperature: {loaded_clone.temperature}")
        print(f"  Base URL: {loaded_clone.base_url}")
        print(f"  API Key: {loaded_clone.api_key}")
    else:
        print("Error: Cloned model 'mistral_1_lowtemp' was not found in the saved config.")
        sys.exit(1)

if __name__ == "__main__":
    main()
