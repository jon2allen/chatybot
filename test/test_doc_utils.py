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
    """Test /docs <filename> displays the file content preview."""
    app = _make_app(capsys)
    await app.handle_escape_command("/docs cookbook/01_1_first_automation.chatdsl")
    out = capsys.readouterr().out
    assert "01_1_first_automation.chatdsl" in out
    assert "model" in out or "prompt" in out or "chatdsl" in out.lower()
