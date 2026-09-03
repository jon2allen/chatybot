"""
env_utils.py — Environment and API Key Resolution Utilities for Chatybot.

Centralizes .env parsing, directory-precedence loading, and robust API key
resolution across Chatybot.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

# Known prefixes for vendor API keys (unambiguous secret keys)
KNOWN_KEY_PREFIXES = (
    "sk-",      # OpenAI, OpenRouter, Anthropic, Mistral (some formats)
    "nvapi-",   # NVIDIA NIM
    "AIza",     # Google Gemini / AI Studio
    "gsk_",     # Groq
    "hf_",      # Hugging Face
    "co-",      # Cohere
    "bytez-",   # Bytez
)


def parse_env_line(line: str) -> Optional[Tuple[str, str]]:
    """
    Parse a single line from an env file.
    
    Supports:
      - Plain assignment: KEY=val
      - Shell export syntax: export KEY=val
      - Quoted values: KEY="val" or KEY='val'
      - Comments and blank lines (ignored)
    """
    line = line.strip()
    if not line or line.startswith("#"):
        return None
    
    if line.startswith("export ") or line.startswith("export\t"):
        line = line.split(maxsplit=1)[1].strip()

    if "=" not in line:
        return None

    k, v = line.split("=", 1)
    k = k.strip()
    v = v.strip().strip("\"'")
    
    if not k:
        return None
        
    return k, v


def load_env_file(filepath: Union[str, Path], override: bool = True) -> Dict[str, str]:
    """
    Read key-value pairs from an env file into os.environ.
    
    Args:
        filepath: Path to the .env file.
        override: If True, overwrite existing os.environ values.
                  If False, only set keys not already present in os.environ (setdefault).
                  
    Returns:
        Dict of parsed key-value pairs from the file.
    """
    path = Path(filepath).expanduser()
    if not path.is_file():
        return {}

    parsed: Dict[str, str] = {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                pair = parse_env_line(line)
                if pair:
                    k, v = pair
                    parsed[k] = v
                    if override:
                        os.environ[k] = v
                    else:
                        os.environ.setdefault(k, v)
    except Exception:
        pass

    return parsed


def load_project_env_files(
    cwd: Optional[Union[str, Path]] = None,
    config_home: Optional[Union[str, Path]] = None,
) -> List[str]:
    """
    Load environment variables respecting project boundaries and global fallbacks:
    
    1. Check for a project-level .env starting at cwd and moving up parent directories:
       [./.env, ../.env, ../../.env].
       Stop immediately at the first found project .env and load it (override=True).
    2. Check global fallback at ~/.config/chatybot/.env.
       Load with override=False (setdefault), so global keys never override project
       or active shell environment variables.
       
    Returns:
        List of paths that were loaded.
    """
    loaded: List[str] = []
    base = Path(cwd) if cwd else Path.cwd()

    # 1. Search for closest project .env (stop at first match)
    candidates = [
        base / ".env",
        base.parent / ".env",
        base.parent.parent / ".env",
    ]
    for cand in candidates:
        if cand.is_file():
            load_env_file(cand, override=True)
            loaded.append(str(cand))
            break  # Do not traverse further up once local project root is identified

    # 2. Global fallback (only populates missing keys; never overrides)
    if config_home:
        global_env = Path(config_home).expanduser() / ".env"
    else:
        global_env = Path("~/.config/chatybot/.env").expanduser()

    if global_env.is_file() and str(global_env) not in loaded:
        load_env_file(global_env, override=False)
        loaded.append(str(global_env))

    return loaded


def resolve_api_key(key_spec: Optional[str]) -> Optional[str]:
    """
    Resolve an API key spec to its secret string value.
    
    In Chatybot, model definitions in chat_config.toml usually specify the NAME
    of an environment variable (e.g. 'MISTRAL_API_KEY').
    
    Resolution logic:
    1. If key_spec is an existing environment variable in os.environ, return its value.
    2. If key_spec starts with a known secret key prefix (e.g. 'sk-', 'nvapi-', 'AIza'),
       return key_spec directly as a failsafe for users who pasted raw keys.
    3. If key_spec contains characters illegal in environment variable names (whitespace),
       treat it as a raw string value.
    4. Otherwise, return None (avoids false-positive raw-key leaks for custom unset env vars).
    """
    if not key_spec:
        return None

    # 1. Check environment variable
    env_val = os.environ.get(key_spec)
    if env_val:
        return env_val

    # 2. Unambiguous raw key vendor prefixes
    if key_spec.startswith(KNOWN_KEY_PREFIXES):
        return key_spec

    # 3. Contains whitespace or invalid env var characters -> cannot be an env var name
    if any(c.isspace() for c in key_spec) or re.search(r"[\t\n\r;]", key_spec):
        return key_spec

    # 4. Syntactically valid env-var identifier that is simply unset in the environment
    return None
