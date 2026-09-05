"""
profile_model.py — Chatybot profile data model.

Provides Pydantic v2 models for loading, validating, and serializing
chatybot profile (.chatdsl) files.

Profile Structure:
    - Metadata: name, description, version, created_at, updated_at
    - Model settings: model alias, temperature, etc.
    - Tool settings: tool mode, disabled tools, max turns
    - Debug/Trace settings: various trace flags
    - Reasoning settings: reasoning mode, effort, show_thinking

Usage:
    from chatybot.profile_model import Profile, ProfileConfig

    # Load from file
    profile = Profile.from_file("~/.config/chatybot/profiles/coding.chatdsl")
    
    # Create new
    profile = Profile(
        name="My Profile",
        description="A custom profile",
        model_alias="mistral_1",
        tool_mode="auto",
        reasoning_effort="medium"
    )
    
    # Serialize to chatdsl format
    chatdsl_content = profile.to_chatdsl()
"""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field, field_validator


# ============================================================================
# PROFILE VERSION
# ============================================================================

PROFILE_VERSION = "1.0"
"""Current profile format version."""


# ============================================================================
# TOOL SETTINGS
# ============================================================================

class ToolSettings(BaseModel):
    """Tool-related configuration for a profile."""

    mode: str = "off"
    """Tool mode: 'off', 'auto', or 'on'."""

    disabled_tools: List[str] = Field(default_factory=list)
    """List of disabled tool names."""

    max_turns: Optional[int] = None
    """Maximum number of tool turns. None means unlimited."""

    auto_execute: bool = True
    """Whether to auto-execute tools when detected."""

    scratch: bool = False
    """Whether scratch mode is enabled for the profile."""

    @field_validator("mode")
    @classmethod
    def validate_mode(cls, v: str) -> str:
        if v not in ("off", "auto", "on"):
            raise ValueError(f"tool.mode must be one of 'off', 'auto', 'on', got '{v}'")
        return v


# ============================================================================
# TRACE SETTINGS
# ============================================================================

class TraceSettings(BaseModel):
    """Debug/trace configuration for a profile."""

    tps: bool = False
    """Trace tokens per second."""

    agentic_loop: bool = False
    """Trace agentic loop execution."""

    raw_payload: bool = False
    """Trace raw API payloads."""

    rerank: bool = False
    """Trace reranking operations."""

    tps_perf: bool = False
    """Trace TPS performance metrics."""

    imagedbg: bool = False
    """Trace image generation debug output."""


# ============================================================================
# REASONING SETTINGS
# ============================================================================

class ReasoningSettings(BaseModel):
    """Reasoning and thinking configuration for a profile."""

    enabled: bool = False
    """Whether reasoning mode is enabled."""

    effort: str = "none"
    """Reasoning effort: 'none', 'low', 'medium', 'high'."""

    show_thinking: bool = False
    """Whether to show thinking/thought process."""

    @field_validator("effort")
    @classmethod
    def validate_effort(cls, v: str) -> str:
        valid_efforts = ("none", "low", "medium", "high")
        if v not in valid_efforts:
            raise ValueError(f"reasoning.effort must be one of {valid_efforts}, got '{v}'")
        return v


# ============================================================================
# PROFILE CONFIG (Core Data)
# ============================================================================

class ProfileConfig(BaseModel):
    """
    Core configuration for a chatybot profile.

    This contains all the runtime settings that define how the chat session
    behaves when this profile is active.
    """

    # Model settings
    model_alias: str
    """The model alias to use (e.g., 'mistral_1', 'gemini_flash')."""

    temperature: Optional[float] = None
    """Sampling temperature. None means use model default."""

    top_p: Optional[float] = None
    """Top-p sampling. None means use model default."""

    top_k: Optional[int] = None
    """Top-k sampling. None means use model default."""

    max_tokens: Optional[int] = None
    """Maximum tokens. None means use model default."""

    # Tool settings
    tool_settings: ToolSettings = Field(default_factory=ToolSettings)

    # Trace/Debug settings
    trace_settings: TraceSettings = Field(default_factory=TraceSettings)

    # Reasoning settings
    reasoning_settings: ReasoningSettings = Field(default_factory=ReasoningSettings)

    # Context limit & auto-truncate settings
    auto_truncate: bool = False
    """Whether auto-truncation is enabled when context limit is reached."""

    truncate_pct: float = 100.0
    """Target percentage of context limit to truncate down to (10.0 to 100.0)."""

    # Additional settings
    system_message: Optional[str] = None
    """Custom system message. None means use global default."""

    @field_validator("temperature")
    @classmethod
    def validate_temperature(cls, v: Optional[float]) -> Optional[float]:
        if v is not None and not (0.0 <= v <= 2.0):
            raise ValueError(f"temperature must be between 0.0 and 2.0, got {v}")
        return v


# ============================================================================
# PROFILE METADATA
# ============================================================================

class ProfileMeta(BaseModel):
    """
    Metadata for a profile.

    This information is stored in annotation comments at the top of
    the .chatdsl file and is used for display purposes.
    """

    name: str = ""
    """Human-readable name of the profile."""

    description: str = ""
    """Description of what this profile does."""

    version: str = PROFILE_VERSION
    """Profile format version."""

    created_at: Optional[datetime] = None
    """When the profile was created."""

    updated_at: Optional[datetime] = None
    """When the profile was last updated."""

    author: Optional[str] = None
    """Author of the profile."""

    source_path: Optional[str] = None
    """Source file path if loaded from disk."""


# ============================================================================
# COMPLETE PROFILE MODEL
# ============================================================================

UNMANAGED_CONTENT_DELIMITER = "# ============================================================================\n# USER CUSTOM CONTENT / MESSAGES / VARIABLES BELOW THIS LINE\n# Note: Profile editor will not modify content below this line.\n# Direct file location:\n# {}\n# ============================================================================"


class Profile(BaseModel):
    """
    Complete chatybot profile model.

    Combines metadata and configuration into a single validated structure.
    """

    meta: ProfileMeta = Field(default_factory=ProfileMeta)
    """Profile metadata (name, description, version, timestamps)."""

    config: ProfileConfig = Field(default_factory=ProfileConfig)
    """Runtime configuration settings."""

    unmanaged_content: str = ""
    """Custom user content below the unmanaged delimiter preserved without parsing."""

    # ------------------------------------------------------------------
    # Constructors
    # ------------------------------------------------------------------

    @classmethod
    def from_file(cls, path: str | Path) -> "Profile":
        """
        Load a profile from a .chatdsl file.

        Parses annotation comments for metadata and DSL commands for config.

        Args:
            path: Path to the .chatdsl profile file.

        Returns:
            A validated Profile instance.

        Raises:
            FileNotFoundError: If the file does not exist.
            ValueError: If the file format is invalid.
        """
        resolved = Path(path).expanduser().resolve()
        if not resolved.exists():
            raise FileNotFoundError(f"Profile file not found: {path}")

        with open(resolved, "r", encoding="utf-8") as f:
            content = f.read()

        managed_part, unmanaged_part = cls._split_unmanaged_content(content)

        # Parse metadata from annotation comments
        meta = cls._parse_meta(managed_part)
        meta.source_path = str(resolved)

        # Parse configuration from DSL commands
        config = cls._parse_config(managed_part)

        # Set default model if not specified
        if not config.model_alias:
            raise ValueError("Profile must specify a model alias with /model command")

        return cls(meta=meta, config=config, unmanaged_content=unmanaged_part)

    @classmethod
    def from_chatdsl_string(cls, chatdsl_str: str) -> "Profile":
        """
        Load a profile from a raw chatdsl string.

        Args:
            chatdsl_str: The chatdsl content as a string.

        Returns:
            A validated Profile instance.
        """
        managed_part, unmanaged_part = cls._split_unmanaged_content(chatdsl_str)
        meta = cls._parse_meta(managed_part)
        config = cls._parse_config(managed_part)

        if not config.model_alias:
            raise ValueError("Profile must specify a model alias with /model command")

        return cls(meta=meta, config=config, unmanaged_content=unmanaged_part)

    @staticmethod
    def _split_unmanaged_content(content: str) -> tuple[str, str]:
        """Split content into managed header/commands and unmanaged custom body."""
        delimiter = "# USER CUSTOM CONTENT / MESSAGES / VARIABLES BELOW THIS LINE"
        if delimiter in content:
            # Find the header block
            idx = content.find(delimiter)
            # Find the start of the delimiter section (e.g. preceding line)
            start_idx = content.rfind("# ===", 0, idx)
            if start_idx == -1:
                start_idx = idx
            
            # Find the end of the delimiter header box
            end_header = content.find("# ===", idx + len(delimiter))
            if end_header != -1:
                # Skip to end of line after final delimiter bar
                newline_pos = content.find("\n", end_header)
                if newline_pos != -1:
                    managed = content[:start_idx]
                    unmanaged = content[newline_pos + 1:]
                    return managed, unmanaged
            managed = content[:start_idx]
            return managed, ""
        return content, ""

    @staticmethod
    def _parse_meta(content: str) -> ProfileMeta:
        """Parse metadata from annotation comments."""
        meta = ProfileMeta()

        for line in content.splitlines():
            line = line.strip()
            if not line or not line.startswith("#"):
                # Stop at first non-comment, non-blank line
                if line:
                    break
                continue

            # Parse @name
            m = re.match(r"#\s*@name:\s*(.+)", line)
            if m:
                meta.name = m.group(1).strip()
                continue

            # Parse @description
            m = re.match(r"#\s*@description:\s*(.+)", line)
            if m:
                meta.description = m.group(1).strip()
                continue

            # Parse @version
            m = re.match(r"#\s*@version:\s*(.+)", line)
            if m:
                meta.version = m.group(1).strip()
                continue

            # Parse @author
            m = re.match(r"#\s*@author:\s*(.+)", line)
            if m:
                meta.author = m.group(1).strip()
                continue

            # Parse @created
            m = re.match(r"#\s*@created:\s*(.+)", line)
            if m:
                try:
                    meta.created_at = datetime.fromisoformat(m.group(1).strip())
                except ValueError:
                    pass
                continue

            # Parse @updated
            m = re.match(r"#\s*@updated:\s*(.+)", line)
            if m:
                try:
                    meta.updated_at = datetime.fromisoformat(m.group(1).strip())
                except ValueError:
                    pass

        return meta

    @staticmethod
    def _parse_config(content: str) -> ProfileConfig:
        """Parse configuration from DSL commands."""
        config = ProfileConfig(model_alias="")

        for line in content.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            parts = line.split()
            if not parts:
                continue

            cmd = parts[0].lower()

            # Model selection
            if cmd == "/model" and len(parts) >= 2:
                config.model_alias = parts[1]

            # Temperature
            elif cmd == "/temp" and len(parts) >= 2:
                try:
                    config.temperature = float(parts[1])
                except ValueError:
                    pass

            # Top-p
            elif cmd == "/top_p" and len(parts) >= 2:
                try:
                    config.top_p = float(parts[1])
                except ValueError:
                    pass

            # Top-k
            elif cmd == "/top_k" and len(parts) >= 2:
                try:
                    config.top_k = int(parts[1])
                except ValueError:
                    pass

            # Max tokens
            elif cmd in ("/max_tokens", "/maxtokens") and len(parts) >= 2:
                try:
                    config.max_tokens = int(parts[1])
                except ValueError:
                    pass

            # System message
            elif cmd == "/system" and len(parts) >= 2:
                config.system_message = " ".join(parts[1:])

            # Tool commands
            elif cmd == "/tool":
                if len(parts) >= 3 and parts[1].lower() == "max_turns":
                    try:
                        config.tool_settings.max_turns = int(parts[2])
                    except ValueError:
                        pass
                elif len(parts) >= 3 and parts[1].lower() == "disable":
                    config.tool_settings.disabled_tools.append(parts[2])
                elif len(parts) >= 3 and parts[1].lower() == "scratch":
                    config.tool_settings.scratch = (parts[2].lower() == "on")
                elif len(parts) >= 2:
                    subcmd = parts[1].lower()
                    if subcmd == "off":
                        config.tool_settings.mode = "off"
                    elif subcmd == "on":
                        # Only set mode to "on" if we're not already in "auto" mode
                        # This handles the case where both "/tool auto on" and "/tool on" are present
                        if config.tool_settings.mode != "auto":
                            config.tool_settings.mode = "on"
                    elif subcmd == "auto":
                        if len(parts) >= 3 and parts[2].lower() == "off":
                            config.tool_settings.auto_execute = False
                        else:
                            config.tool_settings.auto_execute = True
                        config.tool_settings.mode = "auto"

            # Trace settings
            elif cmd == "/trace" and len(parts) >= 3:
                subcmd = parts[1].lower()
                state = parts[2].lower() == "on"
                if subcmd == "tps":
                    config.trace_settings.tps = state
                elif subcmd == "agentic_loop" or subcmd == "loop":
                    config.trace_settings.agentic_loop = state
                elif subcmd == "rawpayload" or subcmd == "raw_payload":
                    config.trace_settings.raw_payload = state
                elif subcmd == "rerank":
                    config.trace_settings.rerank = state
                elif subcmd == "tpsperf" or subcmd == "tps_perf":
                    config.trace_settings.tps_perf = state
                elif subcmd == "imagedbg":
                    config.trace_settings.imagedbg = state

            # Reasoning
            elif cmd == "/reasoning" and len(parts) >= 2:
                config.reasoning_settings.enabled = parts[1].lower() == "on"

            # Thinking
            elif cmd == "/thinking" and len(parts) >= 2:
                config.reasoning_settings.show_thinking = parts[1].lower() == "on"

            # Effort
            elif cmd == "/effort" and len(parts) >= 2:
                config.reasoning_settings.effort = parts[1].lower()

            # Auto-truncate
            elif cmd == "/auto_truncate" and len(parts) >= 2:
                sub = parts[1].lower()
                if sub in ("off", "0", "false"):
                    config.auto_truncate = False
                elif sub in ("on", "1", "true"):
                    config.auto_truncate = True
                    config.truncate_pct = 100.0
                else:
                    try:
                        pct_val = float(sub)
                        if 10.0 <= pct_val <= 100.0:
                            config.auto_truncate = True
                            config.truncate_pct = pct_val
                    except ValueError:
                        pass

        return config

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def to_chatdsl(self, include_version: bool = True) -> str:
        """
        Serialize the profile to chatdsl format.

        Args:
            include_version: Whether to include @version annotation.

        Returns:
            The profile as a chatdsl-formatted string.
        """
        lines: List[str] = []

        # Metadata annotations
        if self.meta.name:
            lines.append(f"# @name: {self.meta.name}")
        if self.meta.description:
            lines.append(f"# @description: {self.meta.description}")
        if self.meta.author:
            lines.append(f"# @author: {self.meta.author}")
        if include_version and self.meta.version:
            lines.append(f"# @version: {self.meta.version}")
        if self.meta.created_at:
            lines.append(f"# @created: {self.meta.created_at.isoformat()}")
        if self.meta.updated_at:
            lines.append(f"# @updated: {self.meta.updated_at.isoformat()}")

        # Add blank line after metadata if any exists
        if any([self.meta.name, self.meta.description, self.meta.author,
                self.meta.version, self.meta.created_at, self.meta.updated_at]):
            lines.append("")

        # Model settings
        lines.append(f"/model {self.config.model_alias}")

        if self.config.temperature is not None:
            lines.append(f"/temp {self.config.temperature}")
        if self.config.top_p is not None:
            lines.append(f"/top_p {self.config.top_p}")
        if self.config.top_k is not None:
            lines.append(f"/top_k {self.config.top_k}")
        if self.config.max_tokens is not None:
            lines.append(f"/max_tokens {self.config.max_tokens}")
        if self.config.system_message:
            lines.append(f"/system {self.config.system_message}")

        # Tool settings
        tool_mode = self.config.tool_settings.mode
        if tool_mode == "auto":
            auto_str = "on" if self.config.tool_settings.auto_execute else "off"
            lines.append(f"/tool auto {auto_str}")
            # Also add /tool on for compatibility with existing scripts
            lines.append("/tool on")
        elif tool_mode == "on":
            lines.append("/tool on")
        else:
            lines.append("/tool off")

        if self.config.tool_settings.scratch:
            lines.append("/tool scratch on")

        for disabled in self.config.tool_settings.disabled_tools:
            lines.append(f"/tool disable {disabled}")

        if self.config.tool_settings.max_turns is not None:
            lines.append(f"/tool max_turns {self.config.tool_settings.max_turns}")

        # Trace settings
        traces = self.config.trace_settings
        if traces.tps:
            lines.append("/trace tps on")
        if traces.agentic_loop:
            lines.append("/trace agentic_loop on")
        if traces.raw_payload:
            lines.append("/trace rawpayload on")
        if traces.rerank:
            lines.append("/trace rerank on")
        if traces.tps_perf:
            lines.append("/trace tpsperf on")
        if traces.imagedbg:
            lines.append("/trace imagedbg on")

        # Reasoning settings
        reasoning = self.config.reasoning_settings
        lines.append(f"/reasoning {'on' if reasoning.enabled else 'off'}")
        lines.append(f"/thinking {'on' if reasoning.show_thinking else 'off'}")
        if reasoning.effort != "none":
            lines.append(f"/effort {reasoning.effort}")

        # Auto-truncate settings
        if self.config.auto_truncate:
            if self.config.truncate_pct != 100.0:
                lines.append(f"/auto_truncate {self.config.truncate_pct:g}")
            else:
                lines.append("/auto_truncate on")
        else:
            lines.append("/auto_truncate off")

        lines.append("")
        path_str = self.meta.source_path or "<profile_file_path>"
        lines.append(UNMANAGED_CONTENT_DELIMITER.format(path_str))
        if self.unmanaged_content:
            lines.append(self.unmanaged_content.rstrip("\n"))

        return "\n".join(lines) + "\n"

    def to_dict(self) -> Dict[str, Any]:
        """Convert profile to a plain dictionary."""
        return {
            "meta": self.meta.model_dump(exclude_none=True),
            "config": self.config.model_dump(exclude_none=True),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Profile":
        """Create a profile from a dictionary."""
        return cls(
            meta=ProfileMeta(**data.get("meta", {})),
            config=ProfileConfig(**data.get("config", {}))
        )

    # ------------------------------------------------------------------
    # Versioning Support
    # ------------------------------------------------------------------

    @property
    def version(self) -> str:
        """Get the profile version."""
        return self.meta.version or PROFILE_VERSION

    @property
    def is_current_version(self) -> bool:
        """Check if profile is using the current version."""
        return self.version == PROFILE_VERSION

    def upgrade(self) -> "Profile":
        """
        Upgrade profile to current version.

        Currently a no-op since we're at version 1.0,
        but can be extended for future version migrations.

        Returns:
            Upgraded profile instance.
        """
        if self.is_current_version:
            return self

        # Future: Add version migration logic here
        # For now, just update the version
        new_meta = self.meta.model_copy()
        new_meta.version = PROFILE_VERSION
        new_meta.updated_at = datetime.now()

        return self.model_copy(update={"meta": new_meta})

    def with_updates(self, **kwargs) -> "Profile":
        """
        Create a new profile with updated metadata.

        Automatically updates the updated_at timestamp.

        Args:
            **kwargs: Metadata fields to update.

        Returns:
            New profile instance with updates.
        """
        new_meta = self.meta.model_copy(update=kwargs)
        new_meta.updated_at = datetime.now()

        # If this is a new profile (no created_at), set it
        if new_meta.created_at is None:
            new_meta.created_at = datetime.now()

        return self.model_copy(update={"meta": new_meta})
