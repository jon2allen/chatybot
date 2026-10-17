"""
Security Self-Protection Floor
A small literal check shared by the newer engines ("allow", "jev", "chain"
stages) so that no policy engine, however permissive or probabilistic, lets a
tool read or change chatybot's own security configuration or secrets.

Protected:
  * any file named *security.toml* (this covers security.toml and
    jev_security.toml, the Jev rubric) and RACF policy files (*.racf)
  * the chatybot secrets file: ~/.config/chatybot/.env
For run_command, the command text is searched for the same names. This is a
literal floor, not a complete defense against shell indirection; the main
engines (builtin DSL, racf-guard, Jev) are responsible for that.
"""

from __future__ import annotations

import os
import re
from typing import Any

from chatybot.security.models import PolicyDecision, PolicyRequest, Verdict

CONFIG_DIR = os.path.abspath(os.path.expanduser("~/.config/chatybot"))

_PATH_TOOLS = {
    "read_file", "write_file", "delete_file", "list_directory", "file_info",
    "make_directory", "remove_directory", "replace_file_content", "patch_file",
    "find_files", "grep_search", "change_dir",
}

_COMMAND_PATTERN = re.compile(
    r"security\.toml|\.racf\b|\.config/chatybot/\.env\b",
    re.IGNORECASE,
)


def _is_protected_path(raw: str) -> bool:
    if not raw or not str(raw).strip():
        return False
    candidates = {os.path.abspath(os.path.expanduser(raw))}
    try:
        candidates.add(os.path.realpath(next(iter(candidates))))
    except OSError:
        pass
    secrets_file = os.path.join(CONFIG_DIR, ".env")
    for p in candidates:
        base = os.path.basename(p).lower()
        if "security.toml" in base or base.endswith(".racf"):
            return True
        if os.path.normcase(p) in {os.path.normcase(secrets_file), os.path.normcase(CONFIG_DIR)}:
            return True
    return False


def _path_values(params: dict[str, Any]) -> list[str]:
    out: list[str] = []
    for k, v in params.items():
        k_clean = k.lower().replace("_", "").replace("-", "")
        if isinstance(v, str) and (
            k_clean in {"path", "file", "target", "dir", "directory", "filename", "source", "destination", "dest"}
            or k_clean.endswith(("path", "file", "dir"))
        ):
            out.append(v)
    return out


def check(request: PolicyRequest) -> PolicyDecision | None:
    """Return a DENY decision if the request touches protected security files, else None."""
    tool = (request.tool or "").strip().lower()
    params = request.parameters or {}
    if tool in _PATH_TOOLS:
        for p in _path_values(params):
            if _is_protected_path(p):
                return PolicyDecision(
                    verdict=Verdict.DENY,
                    reason=f"Access to security configuration '{p}' is denied (security self-protection).",
                )
    if tool == "run_command":
        cmd = str(params.get("command") or params.get("cmd") or "")
        if _COMMAND_PATTERN.search(cmd):
            return PolicyDecision(
                verdict=Verdict.DENY,
                reason="Command references chatybot security configuration or secrets (security self-protection).",
            )
    return None
