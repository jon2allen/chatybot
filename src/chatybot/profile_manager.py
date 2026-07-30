"""
profile_manager.py — Profile Manager Module

Manages discovery, loading, creation, and deletion of chatybot profiles.
Each profile is stored as a separate .chatdsl file in the profile directory.

This follows the same pattern as config_manager.py but handles multiple files
instead of a single configuration file.

Usage:
    from chatybot.profile_manager import ProfileManager
    from chatybot.profile_model import Profile

    pm = ProfileManager()
    
    # List all profiles
    profiles = pm.list_profiles()
    
    # Load a profile
    profile = pm.load_profile("coding")
    
    # Save a profile
    pm.save_profile(profile, "my_profile")
    
    # Delete a profile
    pm.delete_profile("old_profile")
"""

import os
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .profile_model import Profile, ProfileMeta, ProfileConfig, PROFILE_VERSION


# ============================================================================
# PROFILE PRESETS
# ============================================================================

PROFILE_PRESETS: Dict[str, Dict[str, Any]] = {
    "coding": {
        "name": "Development Profile",
        "description": "Optimized for coding, debugging, and technical assistance",
        "model_alias": "devstral_1",
        "tool_mode": "auto",
        "tool_auto_execute": True,
        "reasoning": True,
        "show_thinking": False,
        "reasoning_effort": "medium",
        "temperature": 0.7,
        "max_turns": 75,
        "trace_tps": True,
        "trace_agentic_loop": False,
        "trace_raw_payload": False,
        "trace_rerank": False,
        "trace_tps_perf": False,
        "disabled_tools": [],
    },
    "general": {
        "name": "General Assistance Profile",
        "description": "Balanced assistance with restricted tool access",
        "model_alias": "mistral_1",
        "tool_mode": "off",
        "tool_auto_execute": False,
        "reasoning": False,
        "show_thinking": False,
        "reasoning_effort": "none",
        "temperature": 0.7,
        "max_turns": 25,
        "trace_tps": False,
        "trace_agentic_loop": False,
        "trace_raw_payload": False,
        "trace_rerank": False,
        "trace_tps_perf": False,
        "disabled_tools": [],
    },
    "explorer": {
        "name": "Explorer Mode",
        "description": "Safe read-only exploration for browsing and querying",
        "model_alias": "mistral_1",
        "tool_mode": "auto",
        "tool_auto_execute": True,
        "reasoning": False,
        "show_thinking": False,
        "reasoning_effort": "none",
        "temperature": 0.7,
        "max_turns": 25,
        "trace_tps": False,
        "trace_agentic_loop": False,
        "trace_raw_payload": False,
        "trace_rerank": False,
        "trace_tps_perf": False,
        "disabled_tools": ["run_command", "run_safe", "run_unsafe", "setdb"],
    },
}


class ProfileManager:
    """
    Manages chatybot profiles.

    Each profile is a separate .chatdsl file stored in the profile directory.
    Provides CRUD operations, preset seeding, and metadata management.
    """

    def __init__(self, profile_dir: str = "~/.config/chatybot/profiles"):
        """
        Initialize the ProfileManager.

        Args:
            profile_dir: Directory where profiles are stored.
                        Defaults to ~/.config/chatybot/profiles
        """
        self.profile_dir = os.path.expanduser(profile_dir)
        self._profiles_cache: Optional[Dict[str, ProfileMeta]] = None

    def ensure_dir(self) -> None:
        """Ensure the profile directory exists."""
        os.makedirs(self.profile_dir, exist_ok=True)

    def seed_presets(self) -> None:
        """Copy bundled preset files if they don't already exist."""
        self.ensure_dir()
        preset_src = os.path.join(os.path.dirname(__file__), "profiles")
        if os.path.isdir(preset_src):
            for fname in os.listdir(preset_src):
                if fname.endswith(".chatdsl"):
                    dst = os.path.join(self.profile_dir, fname)
                    if not os.path.exists(dst):
                        shutil.copy2(os.path.join(preset_src, fname), dst)

    def list_profiles(self) -> List[str]:
        """
        Return sorted list of .chatdsl filenames in profile_dir.

        Returns:
            List of profile filenames (without .chatdsl extension).
        """
        self.ensure_dir()
        if not os.path.isdir(self.profile_dir):
            return []
        return sorted(
            os.path.splitext(f)[0]
            for f in os.listdir(self.profile_dir)
            if f.endswith(".chatdsl")
        )

    def list_profile_meta(self) -> List[Tuple[str, ProfileMeta]]:
        """
        Return list of all profiles with their metadata.

        Returns:
            List of (profile_name, ProfileMeta) tuples.
        """
        profiles = self.list_profiles()
        result = []
        for name in profiles:
            try:
                meta = self.read_meta(name)
                result.append((name, meta))
            except Exception:
                # If we can't read metadata, use defaults
                result.append((name, ProfileMeta(name=name)))
        return result

    def _resolve_path(self, name_or_path: str) -> str:
        """
        Resolve a profile name or path to an absolute path.

        Args:
            name_or_path: Profile name (without extension) or path.

        Returns:
            Absolute path to the profile file.

        Raises:
            FileNotFoundError: If the profile doesn't exist.
        """
        if os.path.isabs(name_or_path) or name_or_path.startswith("~"):
            p = os.path.expanduser(name_or_path)
        else:
            p = os.path.join(self.profile_dir, name_or_path)

        if os.path.exists(p):
            return p

        if not p.endswith(".chatdsl"):
            p_ext = p + ".chatdsl"
            if os.path.exists(p_ext):
                return p_ext

        raise FileNotFoundError(f"Profile not found: {name_or_path}")

    def load_profile(self, name: str) -> Profile:
        """
        Load a profile by name.

        Args:
            name: Profile name (with or without .chatdsl extension).

        Returns:
            Profile instance.

        Raises:
            FileNotFoundError: If profile doesn't exist.
            ValueError: If profile format is invalid.
        """
        path = self._resolve_path(name)
        return Profile.from_file(path)

    def load_profile_string(self, name: str) -> str:
        """
        Load raw profile content as string.

        Args:
            name: Profile name.

        Returns:
            Profile content as string.
        """
        path = self._resolve_path(name)
        with open(path, "r", encoding="utf-8") as f:
            return f.read()

    def read_meta(self, name_or_path: str) -> ProfileMeta:
        """
        Read display metadata from annotation comments.

        Args:
            name_or_path: Profile name or path.

        Returns:
            ProfileMeta instance with parsed metadata.
        """
        path = self._resolve_path(name_or_path)
        meta = Profile.from_file(path).meta
        stem = Path(path).stem
        if not meta.name:
            meta.name = stem
        meta.source_path = path
        return meta

    def save_profile(self, profile: Profile, name: Optional[str] = None) -> str:
        """
        Save a profile to disk.

        Args:
            profile: Profile instance to save.
            name: Profile name. If None, uses profile.meta.name or generates one.

        Returns:
            Path where profile was saved.
        """
        self.ensure_dir()

        # Determine filename
        if name:
            filename = name if name.endswith(".chatdsl") else name + ".chatdsl"
        elif profile.meta.name:
            # Sanitize name for filesystem
            safe_name = re.sub(r"[^\w\-_.]", "_", profile.meta.name)
            filename = safe_name + ".chatdsl"
        else:
            # Generate a name based on model and timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{profile.config.model_alias}_{timestamp}.chatdsl"

        path = os.path.join(self.profile_dir, filename)

        # Ensure version is set
        if not profile.meta.version:
            profile = profile.with_updates(version=PROFILE_VERSION)

        # Write to file
        content = profile.to_chatdsl()
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)

        # Clear cache
        self._profiles_cache = None

        return path

    def create_profile(
        self,
        name: str,
        model_alias: str,
        description: str = "",
        preset: Optional[str] = None,
        **config_overrides: Any,
    ) -> Profile:
        """
        Create a new profile.

        Args:
            name: Profile name.
            model_alias: Model alias to use.
            description: Profile description.
            preset: Preset name to use as base ("coding", "general", "explorer").
            **config_overrides: Override preset configuration values.

        Returns:
            New Profile instance.
        """
        now = datetime.now()

        # Start with empty profile
        config = ProfileConfig(model_alias=model_alias)
        meta = ProfileMeta(
            name=name,
            description=description,
            version=PROFILE_VERSION,
            created_at=now,
            updated_at=now,
        )

        # Apply preset if specified
        if preset and preset in PROFILE_PRESETS:
            preset_data = PROFILE_PRESETS[preset]
            config.model_alias = preset_data.get("model_alias", model_alias)
            config.tool_settings.mode = preset_data.get("tool_mode", "off")
            config.tool_settings.auto_execute = preset_data.get("tool_auto_execute", True)
            config.reasoning_settings.enabled = preset_data.get("reasoning", False)
            config.reasoning_settings.show_thinking = preset_data.get("show_thinking", False)
            config.reasoning_settings.effort = preset_data.get("reasoning_effort", "none")
            config.temperature = preset_data.get("temperature")

            if preset_data.get("max_turns"):
                config.tool_settings.max_turns = preset_data["max_turns"]

            # Trace settings
            config.trace_settings.tps = preset_data.get("trace_tps", False)
            config.trace_settings.agentic_loop = preset_data.get("trace_agentic_loop", False)
            config.trace_settings.raw_payload = preset_data.get("trace_raw_payload", False)
            config.trace_settings.rerank = preset_data.get("trace_rerank", False)
            config.trace_settings.tps_perf = preset_data.get("trace_tps_perf", False)

            # Disabled tools
            config.tool_settings.disabled_tools = preset_data.get("disabled_tools", [])

        # Apply overrides
        if "tool_mode" in config_overrides:
            config.tool_settings.mode = config_overrides["tool_mode"]
        if "reasoning_effort" in config_overrides:
            config.reasoning_settings.effort = config_overrides["reasoning_effort"]
        if "temperature" in config_overrides:
            config.temperature = config_overrides["temperature"]
        if "max_turns" in config_overrides:
            config.tool_settings.max_turns = config_overrides["max_turns"]
        if "disabled_tools" in config_overrides:
            config.tool_settings.disabled_tools = config_overrides["disabled_tools"]

        return Profile(meta=meta, config=config)

    def clone_profile(self, src_name: str, dst_name: str) -> str:
        """
        Clone a profile under a new name.

        Args:
            src_name: Source profile name.
            dst_name: Destination profile name (without extension).

        Returns:
            Path where cloned profile was saved.
        """
        src = self._resolve_path(src_name)
        profile = Profile.from_file(src)

        # Update metadata for the clone
        clone_name = dst_name if dst_name else f"{profile.meta.name}_clone"
        profile = profile.with_updates(
            name=clone_name,
            description=f"Cloned from {profile.meta.name}",
        )

        return self.save_profile(profile, dst_name)

    def delete_profile(self, name: str) -> None:
        """
        Delete a profile.

        Args:
            name: Profile name to delete.

        Raises:
            FileNotFoundError: If profile doesn't exist.
        """
        path = self._resolve_path(name)
        os.remove(path)
        self._profiles_cache = None

    def export_profile(self, name: str, dest_path: str) -> None:
        """
        Export a profile to a destination path.

        Args:
            name: Profile name to export.
            dest_path: Destination path (expanded).
        """
        src = self._resolve_path(name)
        dest = os.path.expanduser(dest_path)
        shutil.copy2(src, dest)

    def import_profile(self, src_path: str, name: Optional[str] = None) -> str:
        """
        Import a profile from a file.

        Args:
            src_path: Source file path.
            name: Optional name override.

        Returns:
            Path where profile was imported to.

        Raises:
            ValueError: If source is not a .chatdsl file.
        """
        self.ensure_dir()

        src_path = os.path.expanduser(src_path)
        if not src_path.endswith(".chatdsl"):
            raise ValueError("Import source must be a .chatdsl file")

        # Determine destination filename
        if name:
            fname = name if name.endswith(".chatdsl") else name + ".chatdsl"
        else:
            fname = os.path.basename(src_path)

        dst = os.path.join(self.profile_dir, fname)
        shutil.copy2(src_path, dst)

        self._profiles_cache = None
        return dst

    def get_preset_names(self) -> List[str]:
        """Return list of available preset names."""
        return list(PROFILE_PRESETS.keys())

    def get_preset(self, name: str) -> Optional[Dict[str, Any]]:
        """Get preset configuration by name."""
        return PROFILE_PRESETS.get(name)

    def upgrade_all_profiles(self) -> List[str]:
        """
        Upgrade all profiles to current version.

        Returns:
            List of profile names that were upgraded.
        """
        upgraded = []
        for profile_name in self.list_profiles():
            try:
                profile = self.load_profile(profile_name)
                if not profile.is_current_version:
                    upgraded_profile = profile.upgrade()
                    self.save_profile(upgraded_profile, profile_name)
                    upgraded.append(profile_name)
            except Exception:
                pass
        return upgraded

    def apply_profile_commands(self, profile: Profile, app: Any) -> None:
        """
        Apply profile commands to a chatybot application instance.

        This executes the profile's DSL commands on the app.

        Args:
            profile: Profile to apply.
            app: ChatyBot application instance.
        """
        config = profile.config

        # Set model
        if config.model_alias:
            app.config_manager.set_active_model(config.model_alias)

        # Temperature
        if config.temperature is not None:
            app.temperature = config.temperature

        # Top-p
        if config.top_p is not None:
            app.top_p = config.top_p

        # Top-k
        if config.top_k is not None:
            app.top_k = config.top_k

        # Max tokens
        if config.max_tokens is not None:
            app.max_tokens = config.max_tokens

        # System message
        if config.system_message:
            app.config_manager.system_message = config.system_message

        # Tool mode
        tool_mode = config.tool_settings.mode
        if tool_mode == "auto":
            app.tool_auto = config.tool_settings.auto_execute
            app.tool_mode = True
        elif tool_mode == "on":
            app.tool_auto = False
            app.tool_mode = True
        else:
            app.tool_mode = False

        # Max turns
        if config.tool_settings.max_turns is not None:
            app.max_tool_turns = config.tool_settings.max_turns

        # Disabled tools
        app.disabled_tools = set(config.tool_settings.disabled_tools)

        # Trace settings
        app.trace_tps = config.trace_settings.tps
        app.trace_agentic_loop = config.trace_settings.agentic_loop
        app.trace_raw_payload = config.trace_settings.raw_payload
        app.trace_rerank = config.trace_settings.rerank
        app.trace_tps_perf = config.trace_settings.tps_perf

        # Reasoning settings
        app.reasoning_mode = config.reasoning_settings.enabled
        app.show_thinking = config.reasoning_settings.show_thinking
        if config.reasoning_settings.effort != "none":
            app.reasoning_effort = config.reasoning_settings.effort
        else:
            app.reasoning_effort = None
