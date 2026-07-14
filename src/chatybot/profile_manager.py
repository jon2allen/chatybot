import os
import re
import shutil
from dataclasses import dataclass
from typing import Optional, List

@dataclass
class ProfileMeta:
    """Lightweight metadata parsed from annotation comments."""
    name: str
    description: str
    source_path: str

class ProfileManager:
    """Manages discovery, CRUD, and preset seeding for chatybot profiles."""

    def __init__(self, profile_dir: str = "~/.config/chatybot/profiles"):
        self.profile_dir = os.path.expanduser(profile_dir)

    def ensure_dir(self) -> None:
        os.makedirs(self.profile_dir, exist_ok=True)

    def seed_presets(self) -> None:
        """Write bundled preset files if they don't already exist."""
        self.ensure_dir()
        preset_src = os.path.join(os.path.dirname(__file__), "profiles")
        if os.path.isdir(preset_src):
            for fname in os.listdir(preset_src):
                if fname.endswith(".chatdsl"):
                    dst = os.path.join(self.profile_dir, fname)
                    if not os.path.exists(dst):
                        shutil.copy2(os.path.join(preset_src, fname), dst)

    def list_profiles(self) -> List[str]:
        """Return sorted list of .chatdsl filenames in profile_dir."""
        if not os.path.isdir(self.profile_dir):
            return []
        return sorted(f for f in os.listdir(self.profile_dir)
                      if f.endswith(".chatdsl"))

    def read_meta(self, name_or_path: str) -> ProfileMeta:
        """Read display metadata from annotation comments."""
        path = self._resolve_path(name_or_path)
        stem = os.path.splitext(os.path.basename(path))[0]
        meta_name = stem
        meta_desc = ""
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                if not line.startswith("#"):
                    break   # Stop at first non-comment line
                m = re.match(r"#\s*@name:\s*(.+)", line)
                if m:
                    meta_name = m.group(1).strip()
                    continue
                m = re.match(r"#\s*@description:\s*(.+)", line)
                if m:
                    meta_desc = m.group(1).strip()
        return ProfileMeta(name=meta_name, description=meta_desc, source_path=path)

    def clone_profile(self, src_name: str, dst_name: str) -> str:
        """Clone a profile under a new name."""
        src = self._resolve_path(src_name)
        fname = dst_name if dst_name.endswith(".chatdsl") else dst_name + ".chatdsl"
        dst = os.path.join(self.profile_dir, fname)
        shutil.copy2(src, dst)
        return dst

    def delete_profile(self, name: str) -> None:
        os.remove(self._resolve_path(name))

    def export_profile(self, name: str, dest_path: str) -> None:
        shutil.copy2(self._resolve_path(name), os.path.expanduser(dest_path))

    def import_profile(self, src_path: str) -> str:
        self.ensure_dir()
        fname = os.path.basename(src_path)
        if not fname.endswith(".chatdsl"):
            raise ValueError("Import source must be a .chatdsl file")
        dst = os.path.join(self.profile_dir, fname)
        shutil.copy2(os.path.expanduser(src_path), dst)
        return dst

    def _resolve_path(self, name_or_path: str) -> str:
        if os.path.isabs(name_or_path) or name_or_path.startswith("~"):
            p = os.path.expanduser(name_or_path)
        else:
            fname = name_or_path if name_or_path.endswith(".chatdsl") \
                    else name_or_path + ".chatdsl"
            p = os.path.join(self.profile_dir, fname)
        if not os.path.exists(p):
            raise FileNotFoundError(f"Profile not found: {p}")
        return p
