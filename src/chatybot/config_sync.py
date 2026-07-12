import os
import shutil

def deep_merge(source: dict, destination: dict, path: str = "") -> list[str]:
    """
    Recursively merges keys from source into destination.
    Only adds keys that are missing in destination.
    Returns a list of keys added (with their path).
    """
    changes = []
    for key, value in source.items():
        current_path = f"{path}.{key}" if path else key
        if key not in destination:
            destination[key] = value
            changes.append(current_path)
        elif isinstance(value, dict) and isinstance(destination[key], dict):
            sub_changes = deep_merge(value, destination[key], current_path)
            changes.extend(sub_changes)
    return changes

def serialize_toml(data: dict, prefix: str = "") -> str:
    """
    Serializes a dictionary to TOML format.
    Recursively handles dictionaries as sub-tables.
    """
    lines = []
    # Write non-dictionary keys first
    for key, value in data.items():
        if not isinstance(value, dict):
            if isinstance(value, str):
                # Escape backslashes and double quotes
                escaped = value.replace('\\', '\\\\').replace('"', '\\"')
                if '\n' in value:
                    lines.append(f'{key} = """{value}"""')
                else:
                    lines.append(f'{key} = "{escaped}"')
            elif isinstance(value, bool):
                lines.append(f'{key} = {str(value).lower()}')
            elif isinstance(value, list):
                formatted_list = ", ".join(f'"{item}"' if isinstance(item, str) else str(item) for item in value)
                lines.append(f'{key} = [{formatted_list}]')
            elif value is None:
                continue
            else:
                lines.append(f'{key} = {value}')

    # Write sub-dictionaries next
    for key, value in data.items():
        if isinstance(value, dict):
            # Do not output empty tables
            if not value:
                continue
            table_name = f"{prefix}.{key}" if prefix else key
            lines.append(f"\n[{table_name}]")
            sub_toml = serialize_toml(value, prefix=table_name)
            if sub_toml.strip():
                lines.append(sub_toml)

    return "\n".join(lines)

def load_toml(path: str) -> dict:
    """Loads a TOML file using tomllib or toml fallback."""
    if not os.path.exists(path):
        return {}
    try:
        import tomllib
        with open(path, 'rb') as f:
            return tomllib.load(f)
    except ImportError:
        import toml
        with open(path, 'r', encoding='utf-8') as f:
            return toml.load(f)

_synced_files = set()

def sync_toml_file(package_toml_path: str, user_toml_path: str, file_label: str) -> None:
    """
    Compares the packaged default TOML with user's local TOML configuration.
    If the user's TOML file is missing, it copies the package TOML.
    If it exists, it deep-merges missing keys from package TOML into user TOML,
    alerts the user of the new keys added, and writes the merged config back.
    """
    user_toml_path = os.path.expanduser(user_toml_path)
    if user_toml_path in _synced_files:
        return
    _synced_files.add(user_toml_path)

    os.makedirs(os.path.dirname(user_toml_path), exist_ok=True)

    # If user config does not exist or is empty, copy package config directly
    if not os.path.exists(user_toml_path) or os.path.getsize(user_toml_path) == 0:
        if os.path.exists(package_toml_path):
            shutil.copy2(package_toml_path, user_toml_path)
            print(f"[Config Sync] Initialized local '{file_label}' at '{user_toml_path}'")
        return

    # Load both TOML files
    package_dict = load_toml(package_toml_path)
    user_dict = load_toml(user_toml_path)

    if not package_dict:
        return  # Package config could not be loaded

    # Deep merge package config keys into user config
    added_keys = deep_merge(package_dict, user_dict)

    if added_keys:
        # Write merged config back to user's config path
        try:
            serialized = serialize_toml(user_dict)
            with open(user_toml_path, "w", encoding="utf-8") as f:
                f.write(serialized)
                if not serialized.endswith("\n"):
                    f.write("\n")
            print(f"\n[Config Sync] Alert: Merged new keys from package updates into local '{file_label}' ({user_toml_path}):")
            for k in added_keys:
                print(f"  + Added: {k}")
            print()
        except Exception as e:
            print(f"[Config Sync] Warning: Failed to write merged '{file_label}': {e}")
