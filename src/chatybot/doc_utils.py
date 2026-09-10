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


def highlight_content(content: str, filename: str = "") -> str:
    """
    Apply syntax highlighting to content using Pygments with ANSI terminal escapes.
    Falls back to raw content if Pygments is unavailable or formatting fails.
    """
    try:
        import pygments
        from pygments.formatters import TerminalFormatter
        from pygments.lexers import MarkdownLexer, PythonLexer, TextLexer

        if filename.endswith((".chatdsl", ".dsl")):
            # ChatDSL looks like shell / python hybrid; PythonLexer or MarkdownLexer handles comments and commands cleanly
            lexer = PythonLexer()
        elif filename.endswith((".md", ".markdown")):
            lexer = MarkdownLexer()
        else:
            lexer = MarkdownLexer()

        return pygments.highlight(content, lexer, TerminalFormatter())
    except Exception:
        return content


def display_doc(
    content: str,
    filename: str = "",
    in_script: bool = False,
    page_size: int = 40,
    page_num: int = 1,
) -> None:
    """
    Display document content.
    - If interactive (REPL / not in_script): Uses syntax highlighting + terminal pager (Option 2).
    - If in script context (or requested chunk): Uses incremental chunked stepper (Option 4).
    """
    lines = content.splitlines()
    total_lines = len(lines)
    total_pages = (total_lines + page_size - 1) // page_size if total_lines > 0 else 1

    if in_script:
        # Option 4: Non-interactive / script-friendly chunked output
        page_num = max(1, min(page_num, total_pages))
        start_idx = (page_num - 1) * page_size
        end_idx = min(start_idx + page_size, total_lines)
        chunk_lines = lines[start_idx:end_idx]
        chunk_text = "\n".join(chunk_lines)

        highlighted = highlight_content(chunk_text, filename)
        print(f"\n--- {filename} [Page {page_num}/{total_pages} (Lines {start_idx + 1}-{end_idx} of {total_lines})] ---")
        print(highlighted)
        if page_num < total_pages:
            print(f"--- [Next: /docs {filename} page={page_num + 1} | lines {end_idx + 1}-{total_lines} remaining] ---")
        else:
            print(f"--- [End of {filename}] ---")
        return

    # Option 2: Interactive REPL - Syntax-highlighted fullscreen pager
    # Check if stdout is connected to a terminal or redirected
    if not sys.stdout.isatty():
        # Pipe or non-tty: print highlighted or plain text directly
        print(highlight_content(content, filename))
        return

    highlighted = highlight_content(content, filename)
    try:
        import pydoc
        pydoc.pager(highlighted)
    except Exception:
        print(highlighted)
