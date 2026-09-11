"""
Tests for documentation packaging and access via doc_utils and /docs command.
"""

import os
from pathlib import Path
import pytest

import chatybot
import chatybot.commands  # ensure all command handlers are registered
from chatybot.doc_utils import get_doc_dir, get_doc_path, list_docs
from chatybot.commands.context import CommandContext
from chatybot.commands.registry import registry


def test_doc_utils_get_doc_dir():
    """Verify that get_doc_dir resolves to an existing directory with documentation files."""
    doc_dir = get_doc_dir()
    assert isinstance(doc_dir, Path)
    assert doc_dir.exists()
    assert doc_dir.is_dir()
    assert (doc_dir / "chatdsl_cookbook.md").exists()
    assert (doc_dir / "cookbook").is_dir()


def test_doc_utils_get_doc_path():
    """Verify resolving relative file paths inside doc/."""
    cookbook = get_doc_path("chatdsl_cookbook.md")
    assert cookbook.exists()
    assert cookbook.is_file()
    assert cookbook.stat().st_size > 0

    recipe = get_doc_path("cookbook/01_1_first_automation.chatdsl")
    assert recipe.exists()
    assert recipe.is_file()

    # Empty string should return doc_dir
    assert get_doc_path("") == get_doc_dir()


from chatybot.chatybot_app import ChatybotApp


def _make_app(capsys=None):
    app = ChatybotApp()
    app.initialize()
    if capsys is not None:
        capsys.readouterr()
    return app


def test_doc_utils_list_docs():
    """Verify list_docs returns valid document relative paths."""
    all_docs = list_docs()
    assert len(all_docs) > 40
    assert "chatdsl_cookbook.md" in all_docs
    assert any(d.startswith("cookbook") for d in all_docs)

    recipes = list_docs("cookbook")
    assert len(recipes) >= 50
    assert "cookbook/01_1_first_automation.chatdsl" in recipes


def test_chatybot_package_exports():
    """Verify package top-level re-exports."""
    assert callable(chatybot.get_doc_dir)
    assert callable(chatybot.get_doc_path)
    assert callable(chatybot.list_docs)
    assert callable(chatybot.display_doc)
    assert callable(chatybot.highlight_content)


def test_highlight_content():
    """Verify highlight_content applies syntax highlighting to markdown and chatdsl."""
    from chatybot.doc_utils import highlight_content

    md_text = "# Header\n\n- item 1\n- item 2"
    hl_md = highlight_content(md_text, "test.md")
    assert isinstance(hl_md, str)

    dsl_text = "/model mistral_1\n# Comment\n/echo hello"
    hl_dsl = highlight_content(dsl_text, "test.chatdsl")
    assert isinstance(hl_dsl, str)


def test_display_doc_script_mode(capsys):
    """Verify display_doc in script mode renders incremental chunked pages."""
    from chatybot.doc_utils import display_doc

    sample_content = "\n".join(f"Line {i}" for i in range(1, 101))
    
    # Page 1 (lines 1-40)
    display_doc(sample_content, "sample.md", in_script=True, page_size=40, page_num=1)
    out1 = capsys.readouterr().out
    assert "Page 1/3" in out1
    assert "Line 1" in out1
    assert "Line 40" in out1
    assert "Line 41" not in out1
    assert "Next: /docs sample.md page=2" in out1

    # Page 2 (lines 41-80)
    display_doc(sample_content, "sample.md", in_script=True, page_size=40, page_num=2)
    out2 = capsys.readouterr().out
    assert "Page 2/3" in out2
    assert "Line 41" in out2
    assert "Line 80" in out2

    # Page 3 (lines 81-100, final)
    display_doc(sample_content, "sample.md", in_script=True, page_size=40, page_num=3)
    out3 = capsys.readouterr().out
    assert "Page 3/3" in out3
    assert "Line 100" in out3
    assert "End of sample.md" in out3


@pytest.mark.anyio
async def test_cmd_docs_listing(capsys):
    """Test executing the /docs command to list documents."""
    app = _make_app(capsys)
    result = await app.handle_escape_command("/docs")
    assert result is True
    captured = capsys.readouterr().out
    assert "Bundled Documentation" in captured
    assert "chatdsl_cookbook.md" in captured
    assert "Cookbook Examples" in captured


@pytest.mark.anyio
async def test_cmd_docs_path_and_cookbook(capsys):
    """Test /docs path and /docs cookbook subcommands."""
    app = _make_app(capsys)

    # /docs path
    await app.handle_escape_command("/docs path")
    out = capsys.readouterr().out
    assert "Documentation directory:" in out

    # /docs cookbook
    await app.handle_escape_command("/docs cookbook")
    out_cb = capsys.readouterr().out
    assert "ChatDSL Cookbook Recipes" in out_cb
    assert "01_1_first_automation.chatdsl" in out_cb


@pytest.mark.anyio
async def test_cmd_docs_view_file(capsys):
    """Test /docs <filename> in standard and script context."""
    app = _make_app(capsys)

    # Non-script (TTY mock fallback or piped)
    await app.handle_escape_command("/docs cookbook/01_1_first_automation.chatdsl")
    out = capsys.readouterr().out
    assert "01_1_first_automation.chatdsl" in out or "mistral_1" in out

    # In script mode
    app.script_context = True
    await app.handle_escape_command("/docs chatdsl_cookbook.md page=1")
    out_script = capsys.readouterr().out
    assert "Page 1/" in out_script
    assert "Lines 1-40" in out_script
    assert "Next: /docs chatdsl_cookbook.md page=2" in out_script


@pytest.mark.anyio
async def test_cmd_docs_load_to_script_var(capsys):
    """Test /docs <filename> var=<name> loads content into a script variable."""
    app = _make_app(capsys)

    # Load cookbook example into a script var
    await app.handle_escape_command("/docs cookbook/01_1_first_automation.chatdsl var=my_template")
    out = capsys.readouterr().out
    assert "Loaded '01_1_first_automation.chatdsl'" in out
    assert "into script_var '$my_template'" in out

    # Verify content in buffer_manager script_vars
    val = app.buffer_manager.get_script_var("my_template")
    assert val is not None
    assert "/model mistral_1" in val or "chatdsl" in val.lower()

    # Also verify target= alias
    await app.handle_escape_command("/docs chatdsl_guide.md target=guide_var")
    out2 = capsys.readouterr().out
    assert "into script_var '$guide_var'" in out2
    val2 = app.buffer_manager.get_script_var("guide_var")
    assert val2 is not None
    assert "ChatDSL" in val2


def test_search_docs_utility():
    """Test search_docs matching and snippet generation."""
    from chatybot.doc_utils import search_docs

    # Single term search
    matches = search_docs(["cookbook"], limit=10)
    assert len(matches) > 0
    assert any("cookbook" in m.snippet.lower() for m in matches)

    # Multi-term AND search
    matches_and = search_docs(["model", "prompt"], op="AND", limit=5)
    for m in matches_and:
        assert "model" in m.line_text.lower() and "prompt" in m.line_text.lower()

    # Multi-term OR search
    matches_or = search_docs(["foreach", "nonexistenttermxyz"], op="OR", limit=5)
    assert len(matches_or) > 0
    assert any("foreach" in m.line_text.lower() for m in matches_or)


@pytest.mark.anyio
async def test_cmd_docs_search(capsys):
    """Test /docs search command with snippets and script_var saving."""
    app = _make_app(capsys)

    # Search with output
    await app.handle_escape_command("/docs search model prompt limit=5")
    out = capsys.readouterr().out
    assert "match(es) across" in out
    assert ":" in out

    # Search with var= saving
    await app.handle_escape_command("/docs search cookbook var=search_res limit=3")
    out2 = capsys.readouterr().out
    assert "Saved 3 search result(s) to script_var '$search_res'" in out2
    res_var = app.buffer_manager.get_script_var("search_res")
    assert isinstance(res_var, list)
    assert len(res_var) == 3
    assert "filename" in res_var[0]
    assert "snippet" in res_var[0]


