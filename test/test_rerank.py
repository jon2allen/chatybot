#!/usr/bin/env python3
"""
Unit tests for Chatybot Semantic Reranking functionality
"""

import pytest
import os
import tempfile
import json
import re
from unittest.mock import MagicMock, AsyncMock, patch
from src.chatybot.chatybot_app import ChatybotApp
from src.chatybot.buffer_manager import BufferManager
from src.chatybot.config_manager import ConfigManager
from EasyRerank import TextParser


class TestSemanticReranking:
    """Test suite for semantic reranking feature integration"""

    @pytest.fixture
    def app(self):
        """Create a ChatybotApp instance with clean state"""
        with patch('src.chatybot.chatybot_app.readline'):
            application = ChatybotApp()
            application.config_manager = MagicMock()
            application.config_manager.config = {
                "models": {
                    "remote_jina_rerank": {
                        "name": "jina-reranker-v3",
                        "type": "reranker",
                        "base_url": "https://api.jina.ai/v1/rerank",
                        "api_key": "JINA_API_KEY"
                    }
                }
            }
            application.config_manager.active_model_alias = "remote_jina_rerank"
            application.config_manager.get_model_config.return_value = application.config_manager.config["models"]["remote_jina_rerank"]
            
            application.buffer_manager = BufferManager()
            application.chat_history = []
            return application

    def test_text_parser_basic(self):
        """Test TextParser lines and paragraphs methods from EasyRerank package"""
        content = "Paragraph 1\nLine 2\n\nParagraph 2\nLine 4"
        parser = TextParser(content)
        
        paragraphs = list(parser.paragraphs())
        assert len(paragraphs) == 2
        assert paragraphs[0] == "Paragraph 1\nLine 2"
        assert paragraphs[1] == "Paragraph 2\nLine 4"
        
        lines = list(parser.lines())
        assert len(lines) == 4
        assert lines[0] == "Paragraph 1"
        assert lines[1] == "Line 2"
        assert lines[2] == "Paragraph 2"
        assert lines[3] == "Line 4"

    def test_rerank_argument_parsing(self, app):
        """Test the regex parsing of parameters inside the /rerank command"""
        command = '/rerank "separation of powers", top_n=3, item=2, split=line, return=text, full_doc=true'
        
        query_match = re.search(r'^/rerank\s+["\']([^"\']+)["\']', command, re.IGNORECASE)
        assert query_match is not None
        assert query_match.group(1) == "separation of powers"
        
        remainder = command[query_match.end():]
        top_n_match = re.search(r'\btop_n\s*=\s*(\d+)', remainder, re.IGNORECASE)
        item_match = re.search(r'\bitem\s*=\s*(\d+)', remainder, re.IGNORECASE)
        split_match = re.search(r'\bsplit\s*=\s*([a-zA-Z]+)', remainder, re.IGNORECASE)
        return_match = re.search(r'\breturn\s*=\s*([a-zA-Z]+)', remainder, re.IGNORECASE)
        full_doc_match = re.search(r'\bfull_doc\s*=\s*([a-zA-Z]+)', remainder, re.IGNORECASE)
        
        assert top_n_match.group(1) == "3"
        assert item_match.group(1) == "2"
        assert split_match.group(1) == "line"
        assert return_match.group(1) == "text"
        assert full_doc_match.group(1) == "true"

    def test_rerank_custom_base_url(self, app):
        """Test that custom base_url config (like OpenRouter) is forwarded to EasyRanker backend_instance"""
        app.rerank_documents_source = {"type": "var", "identifier": "CHAT_HISTORY"}
        app.chat_history = [("User query", "System response")]
        
        openrouter_config = {
            "name": "cohere/rerank-v3.5",
            "type": "reranker",
            "base_url": "https://openrouter.ai/api/v1/rerank",
            "api_key": "OPENROUTER_API_KEY"
        }
        app.config_manager.get_model_config.return_value = openrouter_config
        
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "test_openrouter_key"}):
            with patch('src.chatybot.chatybot_app.EasyRanker') as mock_easyranker:
                mock_instance = MagicMock()
                mock_instance.backend_instance = MagicMock()
                mock_easyranker.return_value = mock_instance
                
                import asyncio
                asyncio.run(app.handle_escape_command('/rerank "test query"'))
                
                assert mock_instance.backend_instance.base_url == "https://openrouter.ai/api/v1/rerank"
