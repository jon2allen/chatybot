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
