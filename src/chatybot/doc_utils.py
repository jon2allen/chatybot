"""
Documentation and resource locator utility for Chatybot.
Provides access to bundled package documentation and guides.
"""

import sys
from pathlib import Path

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


def get_readme_content() -> str | None:
    """
    Retrieve the canonical README.md content.
    Checks:
    1. src/chatybot/doc/README.md or local doc_dir/README.md
    2. Repository root README.md
    3. Package distribution metadata ('Description' field in importlib.metadata)
    """
    # 1. Bundled or local doc directory
    doc_file = get_doc_path("README.md")
    if doc_file.exists() and doc_file.is_file():
        try:
            return doc_file.read_text(encoding="utf-8")
        except Exception:
            pass

    # 2. Repo root README.md
    repo_readme = Path(__file__).resolve().parent.parent.parent / "README.md"
    if repo_readme.exists() and repo_readme.is_file():
        try:
            return repo_readme.read_text(encoding="utf-8")
        except Exception:
            pass

    # 3. Installed package metadata fallback
    try:
        if sys.version_info >= (3, 10):
            from importlib.metadata import metadata
        else:
            from importlib_metadata import metadata

        meta = metadata("chatybot")
        desc = meta.get("Description")
        if desc:
            return desc
    except Exception:
        pass

    return None


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
    clean = rel_path.lstrip("/\\")
    target = doc_root / clean

    # If asking for README.md and not found in doc_root, fallback to repo root if available
    if clean.lower() in ("readme.md", "readme") and not target.exists():
        repo_readme = Path(__file__).resolve().parent.parent.parent / "README.md"
        if repo_readme.exists():
            return repo_readme

    return target


def list_docs(subpath: str = "") -> list[str]:
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
        from pygments.lexers import MarkdownLexer, PythonLexer

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
        import os
        import pydoc

        # Ensure less passes through raw ANSI color sequences (-R)
        old_less = os.environ.get("LESS")
        if old_less is None:
            os.environ["LESS"] = "-R"
        elif "-R" not in old_less and "-r" not in old_less:
            os.environ["LESS"] = f"{old_less} -R"

        try:
            pydoc.pager(highlighted)
        finally:
            if old_less is None:
                os.environ.pop("LESS", None)
            else:
                os.environ["LESS"] = old_less
    except Exception:
        print(highlighted)


def check_text_match(text: str, terms: list[str], op: str = "AND") -> tuple[bool, list[str]]:
    """
    Check if text matches terms using AND/OR logic.
    Reuses the exact matching logic from GrepQueryEngine.
    """
    if not terms:
        return True, []
    text_lower = text.lower()
    matched = [t for t in terms if t.lower() in text_lower]
    if op.upper() == "AND":
        return len(matched) == len(terms), matched
    else:  # OR
        return len(matched) > 0, matched


def make_snippet(text: str, matched_terms: list[str], max_len: int = 120) -> str:
    """
    Create a contextual snippet around matched terms.
    Reuses the exact snippet generator from GrepQueryEngine.
    """
    clean_text = " ".join(text.split())
    if not matched_terms or not clean_text:
        return clean_text[:max_len] + ("..." if len(clean_text) > max_len else "")

    first_idx = -1
    clean_lower = clean_text.lower()
    for t in matched_terms:
        idx = clean_lower.find(t.lower())
        if idx != -1 and (first_idx == -1 or idx < first_idx):
            first_idx = idx

    if first_idx == -1:
        first_idx = 0

    start = max(0, first_idx - 40)
    end = min(len(clean_text), first_idx + max_len - 40)
    prefix = "..." if start > 0 else ""
    suffix = "..." if end < len(clean_text) else ""
    return f"{prefix}{clean_text[start:end]}{suffix}"


class DocSearchMatch:
    """Represents a matched documentation line/entry."""

    def __init__(self, filename: str, line_number: int, line_text: str, matched_terms: list[str], snippet: str):
        self.filename = filename
        self.line_number = line_number
        self.line_text = line_text
        self.matched_terms = matched_terms
        self.snippet = snippet

    def to_dict(self) -> dict:
        return {
            "filename": self.filename,
            "line_number": self.line_number,
            "line_text": self.line_text,
            "matched_terms": self.matched_terms,
            "snippet": self.snippet,
        }


def search_docs(
    terms: list[str],
    op: str = "AND",
    limit: int = 20,
    subpath: str = "",
) -> list[DocSearchMatch]:
    """
    Search across bundled documentation files for terms matching AND/OR boolean logic.
    Reuses GrepQueryEngine matching and snippet semantics.
    """
    clean_terms = [t.strip().lower() for t in terms if t.strip()]
    if not clean_terms:
        return []

    doc_files = list_docs(subpath)
    matches: list[DocSearchMatch] = []

    for rel_path in doc_files:
        full_path = get_doc_path(rel_path)
        if not full_path.is_file():
            continue

        try:
            content = full_path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue

        for line_num, line in enumerate(content.splitlines(), start=1):
            is_match, matched = check_text_match(line, clean_terms, op=op)
            if is_match:
                snippet = make_snippet(line, matched, max_len=120)
                matches.append(DocSearchMatch(
                    filename=rel_path,
                    line_number=line_num,
                    line_text=line.strip(),
                    matched_terms=matched,
                    snippet=snippet,
                ))
                if len(matches) >= limit:
                    return matches

    return matches
