"""
Documentation and resource locator utility for Chatybot.
Provides access to bundled package documentation and guides.
"""

import sys
from pathlib import Path
from typing import List, Optional

if sys.version_info >= (3, 11):
    from importlib.resources import files
else:
    from importlib_resources import files


def get_doc_dir() -> Path:
    """
    Return the Path to the documentation directory.
    
    Checks in the following order:
    1. Bundled package data via importlib.resources (installed wheel/package)
    2. Repository root fallback (for local development checkouts)
    """
    try:
        bundled = files("chatybot").joinpath("doc")
        # importlib.resources.files may return a Traversable; cast to Path if filesystem-backed
        p = Path(str(bundled))
        if p.exists() and p.is_dir():
            return p
    except Exception:
        pass

    # Development repository fallback: repo_root / "doc"
    repo_fallback = Path(__file__).resolve().parent.parent.parent / "doc"
    if repo_fallback.exists() and repo_fallback.is_dir():
        return repo_fallback

    # Package internal fallback: src/chatybot/doc
    pkg_fallback = Path(__file__).resolve().parent / "doc"
    if pkg_fallback.exists() and pkg_fallback.is_dir():
        return pkg_fallback

    return Path(__file__).resolve().parent / "doc"


def get_doc_path(rel_path: str = "") -> Path:
    """
    Resolve a specific document or subdirectory within the documentation.

    Args:
        rel_path: Relative path within the doc directory (e.g. "chatdsl_cookbook.md" or "cookbook/01_1_first_automation.chatdsl").

    Returns:
        Path to the requested documentation file or directory.
    """
    doc_root = get_doc_dir()
    if not rel_path:
        return doc_root
    return doc_root / rel_path.lstrip("/\\")


def list_docs(subpath: str = "") -> List[str]:
    """
    List relative paths of all documents available in the doc directory or a subpath.
    """
    target = get_doc_path(subpath)
    if not target.exists() or not target.is_dir():
        return []

    results = []
    for item in target.rglob("*"):
        if item.is_file() and not item.name.startswith("."):
            results.append(str(item.relative_to(get_doc_dir())))
    return sorted(results)
