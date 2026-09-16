#!/usr/bin/env python3
"""
Unit tests for TinyDB database tools (db_search, db_list).
"""

import json
import os
import tempfile
from unittest.mock import patch

import pytest

from src.chatybot import chatydb
from src.chatybot.tinydb1.corpus_manager import CorpusManager
from src.chatybot.tools.db_tools import db_get, db_list, db_search


class TestDbSearch:
    """Test suite for db_search tool"""

    @pytest.fixture(autouse=True)
    def setup_cleanup(self):
        """Reset chatydb global state before and after tests"""
        chatydb.SEARCHBUFFER.clear()
        chatydb._manager = None
        chatydb._db_path = None
        yield
        chatydb.SEARCHBUFFER.clear()
        chatydb._manager = None
        chatydb._db_path = None

    def _create_test_db(self, tmp_path):
        """Create a test database with known items"""
        manager = CorpusManager(tmp_path)
        manager.add_item("doc", "Pasta Recipe", "Carbonara with guanciale", {"cuisine": "italian"})
        manager.add_item("doc", "Beef Recipe", "Wellington with mushrooms", {"cuisine": "british"})
        manager.add_item("chat", "last_chat", "What is the weather today?", {"model": "gpt-4"})
        manager.close()
        return tmp_path

    def test_search_by_content(self):
        """Search matches content field"""
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
            tmp_path = tmp.name
        try:
            self._create_test_db(tmp_path)
            chatydb._manager = CorpusManager(tmp_path)

            result = json.loads(db_search("carbonara"))
            assert result["total_matches"] == 1
            assert result["results"][0]["name"] == "Pasta Recipe"
        finally:
            os.unlink(tmp_path)

    def test_search_by_name(self):
        """Search matches name field"""
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
            tmp_path = tmp.name
        try:
            self._create_test_db(tmp_path)
            chatydb._manager = CorpusManager(tmp_path)

            result = json.loads(db_search("beef"))
            assert result["total_matches"] == 1
            assert result["results"][0]["name"] == "Beef Recipe"
        finally:
            os.unlink(tmp_path)

    def test_search_by_metadata(self):
        """Search matches metadata values"""
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
            tmp_path = tmp.name
        try:
            self._create_test_db(tmp_path)
            chatydb._manager = CorpusManager(tmp_path)

            result = json.loads(db_search("italian"))
            assert result["total_matches"] == 1
            assert result["results"][0]["name"] == "Pasta Recipe"
        finally:
            os.unlink(tmp_path)

    def test_search_wildcard_lists_all(self):
        """Wildcard query returns all items"""
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
            tmp_path = tmp.name
        try:
            self._create_test_db(tmp_path)
            chatydb._manager = CorpusManager(tmp_path)

            result = json.loads(db_search("*"))
            assert result["total_matches"] == 3
        finally:
            os.unlink(tmp_path)

    def test_search_no_matches(self):
        """Search with no matches returns empty results"""
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
            tmp_path = tmp.name
        try:
            self._create_test_db(tmp_path)
            chatydb._manager = CorpusManager(tmp_path)

            result = json.loads(db_search("sushi"))
            assert result["total_matches"] == 0
            assert result["results"] == []
        finally:
            os.unlink(tmp_path)

    def test_search_no_database(self):
        """Search without an active database returns error"""
        result = json.loads(db_search("anything"))
        assert "error" in result

    def test_search_limit(self):
        """Limit parameter caps results"""
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
            tmp_path = tmp.name
        try:
            self._create_test_db(tmp_path)
            chatydb._manager = CorpusManager(tmp_path)

            result = json.loads(db_search("*", limit=2))
            assert result["total_matches"] == 3
            assert result["returned"] == 2
            assert len(result["results"]) == 2
        finally:
            os.unlink(tmp_path)

    def test_search_content_preview_truncated(self):
        """Content preview is truncated to 500 chars"""
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
            tmp_path = tmp.name
        try:
            manager = CorpusManager(tmp_path)
            long_content = "A" * 1000
            manager.add_item("doc", "Long Doc", long_content, {})
            manager.close()
            chatydb._manager = CorpusManager(tmp_path)

            result = json.loads(db_search("long"))
            assert result["results"][0]["content_length"] == 1000
            assert len(result["results"][0]["content_preview"]) == 500
        finally:
            os.unlink(tmp_path)

    def test_search_case_insensitive(self):
        """Search is case-insensitive"""
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
            tmp_path = tmp.name
        try:
            self._create_test_db(tmp_path)
            chatydb._manager = CorpusManager(tmp_path)

            result = json.loads(db_search("PASTA"))
            assert result["total_matches"] == 1
        finally:
            os.unlink(tmp_path)

    def test_search_full_content(self):
        """full_content=True returns full content instead of preview"""
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
            tmp_path = tmp.name
        try:
            manager = CorpusManager(tmp_path)
            long_content = "B" * 1000
            manager.add_item("doc", "Full Doc", long_content, {})
            manager.close()
            chatydb._manager = CorpusManager(tmp_path)

            result = json.loads(db_search("Full", full_content=True))
            assert "content" in result["results"][0]
            assert "content_preview" not in result["results"][0]
            assert result["results"][0]["content"] == long_content
            assert result["results"][0]["content_length"] == 1000
        finally:
            os.unlink(tmp_path)


class TestDbGet:
    """Test suite for db_get tool"""

    @pytest.fixture(autouse=True)
    def setup_cleanup(self):
        """Reset chatydb global state before and after tests"""
        chatydb.SEARCHBUFFER.clear()
        chatydb._manager = None
        chatydb._db_path = None
        yield
        chatydb.SEARCHBUFFER.clear()
        chatydb._manager = None
        chatydb._db_path = None

    def test_db_get_success(self):
        """db_get successfully retrieves item by doc_id"""
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
            tmp_path = tmp.name
        try:
            manager = CorpusManager(tmp_path)
            doc_id = manager.add_item("doc", "Sample Item", "This is the full text.", {"author": "Alice"})
            manager.close()
            chatydb._manager = CorpusManager(tmp_path)

            result = json.loads(db_get(doc_id))
            assert result["id"] == doc_id
            assert result["name"] == "Sample Item"
            assert result["type"] == "doc"
            assert result["content"] == "This is the full text."
            assert result["content_length"] == len("This is the full text.")
            assert result["metadata"]["author"] == "Alice"
        finally:
            os.unlink(tmp_path)

    def test_db_get_not_found(self):
        """db_get returns error when item_id doesn't exist"""
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
            tmp_path = tmp.name
        try:
            manager = CorpusManager(tmp_path)
            manager.add_item("doc", "Item 1", "Content 1", {})
            manager.close()
            chatydb._manager = CorpusManager(tmp_path)

            result = json.loads(db_get(9999))
            assert "error" in result
            assert "9999 not found" in result["error"]
        finally:
            os.unlink(tmp_path)

    def test_db_get_invalid_id(self):
        """db_get returns error for non-integer id"""
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
            tmp_path = tmp.name
        try:
            manager = CorpusManager(tmp_path)
            manager.close()
            chatydb._manager = CorpusManager(tmp_path)

            result = json.loads(db_get("not_an_id"))
            assert "error" in result
            assert "Must be an integer" in result["error"]
        finally:
            os.unlink(tmp_path)

    def test_db_get_no_database(self):
        """db_get returns error when no database selected"""
        result = json.loads(db_get(1))
        assert "error" in result
        assert "No database selected" in result["error"]


class TestDbList:
    """Test suite for db_list tool"""

    @pytest.fixture(autouse=True)
    def setup_cleanup(self):
        """Save and restore the real db directory"""
        original_db_dir = os.path.expanduser("~/.local/share/chatybot/db")
        yield
        # No cleanup needed — we mock os.path.exists and os.listdir

    def test_db_list_no_directory(self):
        """Returns empty list when db directory does not exist"""
        with patch("os.path.exists", return_value=False):
            result = json.loads(db_list())
        assert result["databases"] == []
        assert "message" in result

    def test_db_list_with_databases(self):
        """Lists databases with entry counts and sizes"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # db_list does: base_dir = expanduser("~/.local/share/chatybot")
            #              db_dir = os.path.join(base_dir, "db")
            # So patch expanduser to return tmpdir, and put files in tmpdir/db/
            db_dir = os.path.join(tmpdir, "db")
            os.makedirs(db_dir)

            db1 = os.path.join(db_dir, "recipes.json")
            with open(db1, "w") as f:
                json.dump({"items": {"1": {"type": "doc"}, "2": {"type": "doc"}}}, f)

            db2 = os.path.join(db_dir, "notes.json")
            with open(db2, "w") as f:
                json.dump({"items": {"1": {"type": "chat"}}}, f)

            # Also create a non-json file that should be ignored
            with open(os.path.join(db_dir, "readme.txt"), "w") as f:
                f.write("ignore me")

            with patch("os.path.expanduser", return_value=tmpdir):
                result = json.loads(db_list())

            names = [d["name"] for d in result["databases"]]
            assert "recipes" in names
            assert "notes" in names
            assert "readme" not in names

            recipes = [d for d in result["databases"] if d["name"] == "recipes"][0]
            assert recipes["entries"] == 2
            assert recipes["size_kb"] > 0
