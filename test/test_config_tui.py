# test/test_config_tui.py
"""Unit tests for the curses-based Config TUI logic."""

import pytest
from unittest.mock import MagicMock, patch

from chatybot.config_model import ChatConfig, ChatModelConfig
from chatybot.config_tui import ConfigTUI, main


def test_tui_initialization():
    tui = ConfigTUI(config_path="dummy_config.toml")
    assert tui.config_path == "dummy_config.toml"
    assert tui.selected_idx == 0
    assert tui.filter_text == ""
    assert tui.has_changes is False


def test_tui_apply_filter():
    tui = ConfigTUI()
    # Mock loaded config
    config = ChatConfig(models={
        "mistral_1": ChatModelConfig(name="mistral-large", base_url="https://api.mistral.ai/v1", vendor="mistral"),
        "openai_1": ChatModelConfig(name="gpt-4o", base_url="https://api.openai.com/v1", vendor="openai"),
        "llama_local": ChatModelConfig(name="llama3", base_url="http://localhost:11434/v1", vendor="ollama"),
    })
    tui.config = config
    tui.sync_models_list()
    
    assert len(tui.filtered_list) == 3
    
    # Filter by name/alias/vendor
    tui.filter_text = "mistral"
    tui.apply_filter()
    assert len(tui.filtered_list) == 1
    assert tui.filtered_list[0][0] == "mistral_1"
    
    tui.filter_text = "local"
    tui.apply_filter()
    assert len(tui.filtered_list) == 1
    assert tui.filtered_list[0][0] == "llama_local"


def test_tui_execute_clone_success():
    tui = ConfigTUI()
    tui.config = ChatConfig(models={
        "source_alias": ChatModelConfig(
            name="source-name",
            base_url="https://api.openai.com/v1",
            temperature=0.7,
            top_k=50
        )
    })
    tui.sync_models_list()
    
    # Clone with overrides
    res = tui.execute_clone(
        stdscr=None,
        source_model=tui.config.models["source_alias"],
        new_alias="cloned_alias",
        temp_str="0.2",
        top_k_str="10"
    )
    
    assert res is True
    assert "cloned_alias" in tui.config.models
    cloned = tui.config.models["cloned_alias"]
    assert cloned.temperature == 0.2
    assert cloned.top_k == 10
    assert cloned.base_url == "https://api.openai.com/v1"
    assert tui.has_changes is True


def test_tui_execute_clone_duplicate_alias_blocks():
    tui = ConfigTUI()
    tui.config = ChatConfig(models={
        "existing_alias": ChatModelConfig(
            name="existing",
            base_url="https://api.openai.com/v1"
        )
    })
    tui.sync_models_list()
    
    # Attempting duplicate alias should fail
    res = tui.execute_clone(
        stdscr=None,
        source_model=tui.config.models["existing_alias"],
        new_alias="existing_alias",
        temp_str="0.5",
        top_k_str=""
    )
    
    assert res is False
    assert tui.status_is_error is True
    assert "already exists" in tui.status_message


def test_tui_apply_form_edits():
    tui = ConfigTUI()
    tui.config = ChatConfig(models={
        "my_model": ChatModelConfig(
            name="gpt-4o",
            base_url="https://api.openai.com/v1",
            api_key="OPENAI_API_KEY",
            vendor="openai",
            image_generation=True
        )
    })
    tui.sync_models_list()
    
    form_data = {
        "alias": "my_new_alias",
        "name": "gpt-4o-mini",
        "type": "chat",
        "base_url": "https://api.openai.com/v1",
        "api_key": "NEW_KEY",
        "vendor": "openai",
        "temperature": "1.2",
        "top_k": "",
        "image_generation": "false",
        "image_endpoint": "",
        "image_modalities": "",
    }
    
    res = tui.apply_form_edits(
        old_alias="my_model",
        form_data=form_data,
        is_new=False
    )
    
    assert res is True
    assert "my_model" not in tui.config.models
    assert "my_new_alias" in tui.config.models
    
    updated = tui.config.models["my_new_alias"]
    assert updated.name == "gpt-4o-mini"
    assert updated.api_key == "NEW_KEY"
    assert updated.temperature == 1.2
    assert updated.image_generation is False


def test_tui_apply_filter_with_reranker():
    from chatybot.config_model import RerankerModelConfig
    
    tui = ConfigTUI()
    config = ChatConfig(models={
        "my_reranker": RerankerModelConfig(
            name="jina-rerank-v2",
            base_url="https://api.jina.ai/v1/rerank"
        ),
        "my_chat": ChatModelConfig(
            name="gpt-4",
            base_url="https://api.openai.com/v1",
            vendor="openai"
        )
    })
    tui.config = config
    tui.sync_models_list()
    
    # Verify apply_filter works without crashing on reranker
    tui.filter_text = "jina"
    tui.apply_filter()
    assert len(tui.filtered_list) == 1
    assert tui.filtered_list[0][0] == "my_reranker"
    
    tui.filter_text = "openai"
    tui.apply_filter()
    assert len(tui.filtered_list) == 1
    assert tui.filtered_list[0][0] == "my_chat"


def test_tui_detected_vendor_fallback():
    from chatybot.config_model import RerankerModelConfig
    
    tui = ConfigTUI()
    config = ChatConfig(models={
        "cohere": RerankerModelConfig(
            name="cohere/rerank-v3.5",
            base_url="https://openrouter.ai/api/v1/rerank"
        ),
        "gemma": ChatModelConfig(
            name="gemma-3-27b-it",
            base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
        ),
        "mistral_local": ChatModelConfig(
            name="devstral-2512",
            base_url="https://api.mistral.ai/v1"
        )
    })
    tui.config = config
    tui.sync_models_list()
    
    # Check that dynamic detected_vendor property returns the correct fallback
    assert config.models["cohere"].detected_vendor == "openrouter"
    assert config.models["gemma"].detected_vendor == "google"
    assert config.models["mistral_local"].detected_vendor == "mistral"


def test_tui_clone_dialog_cancel_does_not_clone():
    from chatybot.config_model import ChatModelConfig
    
    tui = ConfigTUI()
    tui.config = ChatConfig(models={
        "orig": ChatModelConfig(
            name="orig-model",
            base_url="https://api.openai.com/v1"
        )
    })
    tui.sync_models_list()
    
    mock_stdscr = MagicMock()
    mock_stdscr.getmaxyx.return_value = (40, 80)
    
    mock_win = MagicMock()
    mock_win.getmaxyx.return_value = (16, 50)
    mock_win.getch.side_effect = [27]
    
    with patch("curses.newwin", return_value=mock_win), \
         patch("curses.curs_set"), \
         patch("curses.color_pair", return_value=0):
        tui.clone_model_dialog(mock_stdscr, "orig", tui.config.models["orig"])
        
    assert len(tui.config.models) == 1
    assert "orig_clone" not in tui.config.models


def test_tui_clone_dialog_edit_full_passes_is_new():
    from chatybot.config_model import ChatModelConfig
    
    tui = ConfigTUI()
    tui.config = ChatConfig(models={
        "orig": ChatModelConfig(
            name="orig-model",
            base_url="https://api.openai.com/v1"
        )
    })
    tui.sync_models_list()
    
    mock_stdscr = MagicMock()
    mock_stdscr.getmaxyx.return_value = (40, 80)
    
    mock_win = MagicMock()
    mock_win.getmaxyx.return_value = (16, 50)
    # Mocking navigating to button 1: "Edit Full".
    # Focus sequence: 0 -> 1 -> 2 -> 3 -> 4.
    # We send KEY_DOWN 4 times, then Enter (10).
    import curses
    mock_win.getch.side_effect = [
        curses.KEY_DOWN,
        curses.KEY_DOWN,
        curses.KEY_DOWN,
        curses.KEY_DOWN,
        10
    ]
    
    tui.edit_model_form = MagicMock()
    
    with patch("curses.newwin", return_value=mock_win), \
         patch("curses.curs_set"), \
         patch("curses.color_pair", return_value=0):
        tui.clone_model_dialog(mock_stdscr, "orig", tui.config.models["orig"])
        
    tui.edit_model_form.assert_called_once()
    args, kwargs = tui.edit_model_form.call_args
    assert args[1] == "orig_clone"
    assert args[2].name == "orig-model"
    assert kwargs.get("is_new") is True
    
    assert len(tui.config.models) == 1
    assert "orig_clone" not in tui.config.models



