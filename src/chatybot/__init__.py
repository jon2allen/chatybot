__version__ = "0.8.7"

from .doc_utils import (
    DocSearchMatch,
    display_doc,
    get_doc_dir,
    get_doc_path,
    get_readme_content,
    highlight_content,
    list_docs,
    search_docs,
)

__all__ = ["__version__", "get_doc_dir", "get_doc_path", "list_docs", "display_doc", "highlight_content", "search_docs", "DocSearchMatch", "get_readme_content"]

