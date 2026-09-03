#!/usr/bin/env python3
"""
Chatybot API Key Setup Utility
Cross-platform interactive wizard to configure API keys on Windows, macOS, and Linux.
"""

import os
import sys
import subprocess
from pathlib import Path
from typing import List, Tuple, Dict

# Supported providers: (env_var_name, display_name, status, url)
KEYS: List[Tuple[str, str, str, str]] = [
    ("MISTRAL_API_KEY", "Mistral AI", "Default Preset", "https://console.mistral.ai/"),
    ("OPENAI_API_KEY", "OpenAI (GPT-4o, o1, o3)", "Optional", "https://platform.openai.com/api-keys"),
    ("OPENROUTER_API_KEY", "OpenRouter (Claude, Llama, DeepSeek)", "Optional", "https://openrouter.ai/keys"),
    ("GEMINI_API_KEY", "Google Gemini (2.5 Flash, 1.5 Pro)", "Optional", "https://aistudio.google.com/app/apikey"),
    ("ANTHROPIC_API_KEY", "Anthropic (Claude 3.5)", "Optional", "https://console.anthropic.com/"),
    ("NVIDIA_API", "NVIDIA NIM / Build", "Optional", "https://build.nvidia.com/"),
    ("GROQ_API_KEY", "Groq (Llama, Mixtral)", "Optional", "https://console.groq.com/keys"),
    ("DEEPSEEK_API_KEY", "DeepSeek", "Optional", "https://platform.deepseek.com/"),
    ("COHERE_API_KEY", "Cohere", "Optional", "https://dashboard.cohere.com/api-keys"),
    ("HF_API_KEY", "Hugging Face Token", "Optional", "https://huggingface.co/settings/tokens"),
    ("JINA_API_KEY", "Jina AI (Search / Rerank)", "Optional", "https://jina.ai/"),
]


def mask_key(val: str) -> str:
    """Mask sensitive key string for display."""
    if len(val) <= 8:
        return "********"
    return f"{val[:4]}...{val[-4:]}"


def load_existing_env_file(filepath: Path) -> Dict[str, str]:
    """Parse key-value pairs from an existing .env file."""
    keys: Dict[str, str] = {}
    if not filepath.exists():
        return keys
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    keys[k.strip()] = v.strip().strip("\"'")
    except Exception:
        pass
    return keys


def main():
    print("======================================================")
    print("          Chatybot API Key Setup Assistant           ")
    print("======================================================")
    print("Chatybot reads API keys from environment variables or .env files.")
    print("In chat_config.toml, model definitions reference the name of these")
    print("variables (e.g. api_key = \"MISTRAL_API_KEY\"), keeping secrets secure.\n")

    # Load existing .env in current working directory if present
    env_file_keys = load_existing_env_file(Path(".env"))

    collected: Dict[str, str] = {}

    print("Press [Enter] to keep current/blank value, or type a new key.\n")

    for var_name, display_name, status, url in KEYS:
        current_val = os.environ.get(var_name) or env_file_keys.get(var_name, "")
        
        if current_val:
            masked = mask_key(current_val)
            print(f"● {display_name} ({var_name}) [{status}]")
            print(f"  Key URL: {url}")
            try:
                user_input = input(f"  Value [current: {masked}]: ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\nSetup cancelled.")
                return
            collected[var_name] = user_input if user_input else current_val
        else:
            print(f"○ {display_name} ({var_name}) [{status}]")
            print(f"  Key URL: {url}")
            try:
                user_input = input("  Value [leave blank to skip]: ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\nSetup cancelled.")
                return
            if user_input:
                collected[var_name] = user_input
        print()

    # Check if at least one key is provided
    active_keys = {k: v for k, v in collected.items() if v}
    if not active_keys:
        print("No API keys were provided or retained.")
        return

    is_windows = sys.platform == "win32"
    user_home = Path.home()

    print("------------------------------------------------------")
    print("Where would you like to save your API keys?")
    print("  1) Local .env file (./.env) - Recommended for current project")
    print(f"  2) Global Chatybot .env ({user_home / '.config' / 'chatybot' / '.env'}) - Loaded everywhere")
    if is_windows:
        print("  3) Windows User Environment (setx) - Permanent system registry")
        print("  4) Print PowerShell and CMD export commands only")
    else:
        shell = os.environ.get("SHELL", "")
        profile_name = ".zshrc" if "zsh" in shell else ".bashrc"
        print(f"  3) Shell startup profile (~/{profile_name}) - Persistent exports")
        print("  4) Print shell export commands only")

    try:
        choice = input("Select an option [1-4, default: 1]: ").strip()
    except (EOFError, KeyboardInterrupt):
        choice = "1"

    if choice == "2":
        dest_dir = user_home / ".config" / "chatybot"
        dest_dir.mkdir(parents=True, exist_ok=True)
        target = dest_dir / ".env"
        _write_env_file(target, active_keys)
        print(f"\n✓ Successfully saved keys to {target}!")

    elif choice == "3":
        if is_windows:
            print("\nSaving keys to Windows User Environment via setx...")
            for k, v in active_keys.items():
                try:
                    subprocess.run(["setx", k, v], check=True, capture_output=True)
                    print(f"  ✓ Registered {k}")
                except Exception as e:
                    print(f"  ✗ Failed to set {k}: {e}")
            print("\n✓ Keys successfully saved to Windows Environment!")
            print("Note: Restart open Command Prompt or PowerShell windows for new variables to take effect.")
        else:
            shell = os.environ.get("SHELL", "")
            profile = user_home / (".zshrc" if "zsh" in shell else ".bashrc")
            print(f"\nAppending export statements to {profile}...")
            with open(profile, "a", encoding="utf-8") as f:
                f.write("\n# --- Chatybot API Keys ---\n")
                for k, v in active_keys.items():
                    f.write(f'export {k}="{v}"\n')
            print(f"✓ Successfully saved keys to {profile}!")
            print(f"Run 'source {profile}' to activate in this terminal.")

    elif choice == "4":
        print("\nRun these commands in your shell to activate for this session:")
        if is_windows:
            print("# For PowerShell:")
            for k, v in active_keys.items():
                print(f'$env:{k} = "{v}"')
            print("\n# For Command Prompt (CMD):")
            for k, v in active_keys.items():
                print(f'set {k}={v}')
        else:
            for k, v in active_keys.items():
                print(f'export {k}="{v}"')

    else:
        # Default: local .env
        target = Path(".env")
        _write_env_file(target, active_keys)
        print(f"\n✓ Successfully created {target} in current directory!")

    print("\nSetup complete!")
    print("To verify your active keys inside Chatybot, start the app and run /env:")
    print("  chatybot")
    print("  chat --> /env")
    print("  chat --> /listmodels\n")


def _write_env_file(path: Path, keys: Dict[str, str]):
    """Write key-value dictionary to a .env file with secure permissions."""
    lines = [
        "# Chatybot Environment Configuration",
        "# Auto-generated by Chatybot setup assistant",
    ]
    for k, v in keys.items():
        lines.append(f'{k}="{v}"')
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")
    try:
        os.chmod(path, 0o600)
    except Exception:
        pass


if __name__ == "__main__":
    main()
