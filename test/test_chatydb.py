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
        yield
        chatydb.SEARCHBUFFER.clear()
        chatydb._manager = None
        chatydb._db_path = None

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
            assert item["metadata"]["thinking_content"] == "2 + 2 = 4"
            assert item["metadata"]["thinking_tokens"] == 42
            assert item["metadata"]["reasoning_effort"] == "high"
            assert item["metadata"]["prompt"] == "What is 2+2?"

        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

