#!/usr/bin/env python3
"""
Unit tests for ChatyDB functionality
"""

import pytest
import os
import tempfile
from unittest.mock import MagicMock, patch
import src.chatybot.chatydb as chatydb
from src.chatybot.tinydb1.corpus_manager import CorpusManager


class TestChatyDB:
    """Test suite for ChatyDB and metadata search"""

    @pytest.fixture(autouse=True)
    def setup_cleanup(self):
        """Reset chatydb global variables before and after tests"""
        chatydb.SEARCHBUFFER.clear()
        chatydb._manager = None
        chatydb._db_path = None
        chatydb._active_db_name = None
        chatydb._session_backed_up_dbs.clear()
        yield
        chatydb.SEARCHBUFFER.clear()
        chatydb._manager = None
        chatydb._db_path = None
        chatydb._active_db_name = None
        chatydb._session_backed_up_dbs.clear()

    def test_search_db_name_content_and_metadata(self):
        """Test that search_db matches query in name, content, and metadata fields"""
        # Create a temporary database file
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            # Initialize CorpusManager
            manager = CorpusManager(tmp_path)
            
            # Add test items
            manager.add_item("doc", "Span Cities", "Madrid, Barcelona", {"country": "Spain", "region": "Europe"})
            manager.add_item("doc", "German Cities", "Berlin, Munich", {"country": "Germany", "creator": "Admin"})
            manager.add_item("doc", "Bulgarian Cities", "Sofia, Plovdiv", {"country": "Bulgaria", "tags": ["eastern", "europe"]})

            # Mock chatydb internal manager and database path
            chatydb._manager = manager
            chatydb._db_path = tmp_path

            # 1. Search by name
            chatydb.search_db("Span")
            assert len(chatydb.SEARCHBUFFER) == 1
            assert chatydb.SEARCHBUFFER[0]["name"] == "Span Cities"

            # 2. Search by content
            chatydb.search_db("Munich")
            assert len(chatydb.SEARCHBUFFER) == 1
            assert chatydb.SEARCHBUFFER[0]["name"] == "German Cities"

            # 3. Search by metadata value (dict value)
            chatydb.search_db("Germany")
            assert len(chatydb.SEARCHBUFFER) == 1
            assert chatydb.SEARCHBUFFER[0]["name"] == "German Cities"

            # 4. Search by metadata key (dict key)
            chatydb.search_db("creator")
            assert len(chatydb.SEARCHBUFFER) == 1
            assert chatydb.SEARCHBUFFER[0]["name"] == "German Cities"

            # 5. Search by metadata list element
            chatydb.search_db("eastern")
            assert len(chatydb.SEARCHBUFFER) == 1
            assert chatydb.SEARCHBUFFER[0]["name"] == "Bulgarian Cities"

            # 6. Search for non-matching query
            chatydb.search_db("nonexistent")
            assert len(chatydb.SEARCHBUFFER) == 0

        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

    def test_dblog_with_thinking(self):
        """Test dblog with include_thinking=True logs thinking_content and thinking_tokens."""
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            manager = CorpusManager(tmp_path)
            chatydb._manager = manager
            chatydb._db_path = tmp_path

            # Mock chatybot module with mock app instance
            mock_app = MagicMock()
            mock_app.chat_history = [("What is 2+2?", "<think>\n2 + 2 = 4\n</think>\nThe answer is 4.")]
            mock_app._extract_thinking_tokens.return_value = ("2 + 2 = 4", "The answer is 4.")
            mock_app.last_reasoning_tokens = 42
            mock_app.reasoning_effort = "high"
            mock_app.config_manager.active_model_alias = "gemini_flash"
            mock_app.config_manager.get_model_config.return_value = {"name": "gemini-2.5-flash"}

            mock_mod = MagicMock()
            mock_mod.app = mock_app

            import sys
            with patch.dict(sys.modules, {"chatybot.chatybot_app": mock_mod}):
                chatydb.dblog(include_thinking=True)

            items = manager.get_all_items()
            assert len(items) == 1
            item = items[0]
            assert item["type"] == "chat"
            assert "<think>" in item["content"]
            assert item["metadata"]["thinking_content"] == "2 + 2 = 4"
            assert item["metadata"]["thinking_tokens"] == 42
            assert item["metadata"]["reasoning_effort"] == "high"
            assert item["metadata"]["prompt"] == "What is 2+2?"

        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

    def test_dblog_default_strips_thinking(self):
        """Test dblog without thinking argument strips thinking tags from content."""
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            manager = CorpusManager(tmp_path)
            chatydb._manager = manager
            chatydb._db_path = tmp_path

            mock_app = MagicMock()
            mock_app.chat_history = [("What is 2+2?", "<think>\n2 + 2 = 4\n</think>\nThe answer is 4.")]
            mock_app._extract_thinking_tokens.return_value = ("2 + 2 = 4", "The answer is 4.")
            mock_app.last_reasoning_tokens = 42
            mock_app.reasoning_effort = "high"
            mock_app.config_manager.active_model_alias = "gemini_flash"
            mock_app.config_manager.get_model_config.return_value = {"name": "gemini-2.5-flash"}

            mock_mod = MagicMock()
            mock_mod.app = mock_app

            import sys
            with patch.dict(sys.modules, {"chatybot.chatybot_app": mock_mod}):
                chatydb.dblog(include_thinking=False)

            items = manager.get_all_items()
            assert len(items) == 1
            item = items[0]
            assert item["type"] == "chat"
            assert item["content"] == "The answer is 4."
            assert "<think>" not in item["content"]
            assert item["metadata"]["thinking_content"] is None
            assert item["metadata"]["thinking_tokens"] == 0
            assert item["metadata"]["prompt"] == "What is 2+2?"

        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

    def test_backup_db_creation_and_rotation(self, tmp_path):
        """Test that _backup_db creates snapshots and prunes older ones when exceeding max_backups."""
        db_file = tmp_path / "testdb.json"
        db_file.write_text('{"items": {"1": {"content": "hello"}}}')

        # Run 7 backups with max_backups=3
        backups_created = []
        for i in range(7):
            res = chatydb._backup_db(str(db_file), "testdb", max_backups=3)
            assert res is not None
            backup_path, count, max_count = res
            assert count <= 3
            assert max_count == 3
            assert os.path.exists(backup_path)

        backup_dir = tmp_path / ".backups" / "testdb"
        assert backup_dir.exists()
        retained = list(backup_dir.glob("testdb.*.bak.json"))
        assert len(retained) == 3

    def test_backup_db_skips_empty_or_nonexistent(self, tmp_path):
        """Test that _backup_db returns None for nonexistent or empty files."""
        # Nonexistent
        res = chatydb._backup_db(str(tmp_path / "nonexistent.json"), "nonexistent")
        assert res is None

        # Empty file (0 bytes)
        empty_file = tmp_path / "empty.json"
        empty_file.touch()
        res = chatydb._backup_db(str(empty_file), "empty")
        assert res is None

    def test_set_db_triggers_backup_on_existing(self, tmp_path, monkeypatch, capsys):
        """Test that set_db automatically backs up an existing DB file."""
        # Point _ensure_db_path to our temp directory
        def mock_ensure_db_path(name):
            return str(tmp_path / f"{name}.json")

        monkeypatch.setattr(chatydb, "_ensure_db_path", mock_ensure_db_path)

        db_file = tmp_path / "mycorpus.json"
        db_file.write_text('{"items": {"1": {"name": "Doc1", "type": "doc", "content": "text", "metadata": {}}}}')

        chatydb.set_db("mycorpus")

        out = capsys.readouterr().out
        assert "[backup] Snapshot saved:" in out
        assert ".backups/mycorpus/mycorpus." in out

        backup_dir = tmp_path / ".backups" / "mycorpus"
        assert backup_dir.exists()
        backups = list(backup_dir.glob("mycorpus.*.bak.json"))
        assert len(backups) == 1

    def test_set_db_skips_backup_if_already_active_or_backed_up(self, tmp_path, monkeypatch, capsys):
        """Test that repeated set_db calls (e.g. from db_search / db_get) do not create multiple backups."""
        def mock_ensure_db_path(name):
            return str(tmp_path / f"{name}.json")

        monkeypatch.setattr(chatydb, "_ensure_db_path", mock_ensure_db_path)

        db_file = tmp_path / "repeated.json"
        db_file.write_text('{"items": {"1": {"name": "Doc1", "type": "doc", "content": "text", "metadata": {}}}}')

        # First call: opens DB and creates snapshot
        chatydb.set_db("repeated")
        out1 = capsys.readouterr().out
        assert "[backup] Snapshot saved:" in out1

        # Second call: same DB name while already active -> early exit, no second backup
        chatydb.set_db("repeated")
        out2 = capsys.readouterr().out
        assert "[backup] Snapshot saved:" not in out2

        # Verify only 1 backup file exists
        backup_dir = tmp_path / ".backups" / "repeated"
        backups = list(backup_dir.glob("repeated.*.bak.json"))
        assert len(backups) == 1

    def test_dbprint_table_mode_and_range_filtering(self, tmp_path, capsys):
        """Test dbprint with table_mode=True and item_range filtering."""
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
            tmp_path_file = tmp.name

        try:
            manager = CorpusManager(tmp_path_file)
            chatydb._manager = manager
            chatydb._db_path = tmp_path_file
            chatydb._active_db_name = "test_table"

            # Add 3 items with distinct metadata
            manager.add_item("chat", "chat1", "<think>reasoning</think>Answer 1", {"prompt": "What is A?", "model_alias": "m1"})
            manager.add_item("chat", "chat2", "Answer 2", {"prompt": "What is B?", "model_alias": "m2", "thinking_content": "meta reason", "thinking_tokens": 500})
            manager.add_item("chat", "chat3", "Answer 3", {"prompt": "What is C?", "model_alias": "m3"})

            # 1. Print all items in table mode
            chatydb.dbprint(table_mode=True)
            out_all = capsys.readouterr().out
            assert "DATABASE SUMMARY TABLE: test_table (3 items" in out_all
            assert "ID" in out_all and "Timestamp" in out_all and "Thinking" in out_all
            assert "in content" in out_all
            assert "metadata" in out_all
            assert "stripped" in out_all
            assert "500" in out_all

            # 2. Filter range 1-2
            chatydb.dbprint(table_mode=True, item_range="1-2")
            out_range = capsys.readouterr().out
            assert "(2 items, range: 1-2)" in out_range
            assert "What is A?" in out_range
            assert "What is B?" in out_range
            assert "What is C?" not in out_range

            # 3. Filter single ID 3
            chatydb.dbprint(table_mode=False, item_range=3)
            out_single = capsys.readouterr().out
            assert "Items displayed: 1 (filter: ID 3)" in out_single
            assert "Answer 3" in out_single
            assert "Answer 1" not in out_single

            # 4. Export to file
            export_file = tmp_path / "export_table.txt"
            chatydb.dbprint(target_file=str(export_file), table_mode=True, item_range="2-3")
            out_export = capsys.readouterr().out
            assert f"Database report saved to '{export_file}'." in out_export
            assert export_file.exists()
            content = export_file.read_text()
            assert "DATABASE SUMMARY TABLE: test_table (2 items, range: 2-3)" in content
            assert "What is B?" in content
            assert "What is C?" in content
            assert "What is A?" not in content

        finally:
            if os.path.exists(tmp_path_file):
                os.unlink(tmp_path_file)



