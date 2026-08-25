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


def test_tui_save_menu_dialog_overwrite():
    tui = ConfigTUI(config_path="test_config.toml")
    tui.save_config_to_file = MagicMock()
    
    mock_stdscr = MagicMock()
    mock_stdscr.getmaxyx.return_value = (40, 80)
    
    mock_win = MagicMock()
    mock_win.getmaxyx.return_value = (8, 48)
    # Default is Overwrite (index 0). Pressing Enter (10) should execute save.
    mock_win.getch.side_effect = [10]
    
    with patch("curses.newwin", return_value=mock_win), \
         patch("curses.color_pair", return_value=0):
        tui.save_menu_dialog(mock_stdscr)
        
    tui.save_config_to_file.assert_called_once_with(mock_stdscr)


def test_tui_save_menu_dialog_save_as():
    tui = ConfigTUI(config_path="test_config.toml")
    tui.save_config_as_dialog = MagicMock(return_value=True)
    tui.save_config_to_file = MagicMock()
    
    mock_stdscr = MagicMock()
    mock_stdscr.getmaxyx.return_value = (40, 80)
    
    mock_win = MagicMock()
    mock_win.getmaxyx.return_value = (8, 48)
    # Press right (curses.KEY_RIGHT) to move to Save As... (index 1), then Enter (10).
    import curses
    mock_win.getch.side_effect = [curses.KEY_RIGHT, 10]
    
    with patch("curses.newwin", return_value=mock_win), \
         patch("curses.color_pair", return_value=0):
        tui.save_menu_dialog(mock_stdscr)
        
    tui.save_config_as_dialog.assert_called_once_with(mock_stdscr)
    tui.save_config_to_file.assert_not_called()


def test_tui_save_menu_dialog_cancel():
    tui = ConfigTUI(config_path="test_config.toml")
    tui.save_config_to_file = MagicMock()
    tui.save_config_as_dialog = MagicMock()
    
    mock_stdscr = MagicMock()
    mock_stdscr.getmaxyx.return_value = (40, 80)
    
    mock_win = MagicMock()
    mock_win.getmaxyx.return_value = (8, 48)
    # Escape (27) should exit.
    mock_win.getch.side_effect = [27]
    
    with patch("curses.newwin", return_value=mock_win), \
         patch("curses.color_pair", return_value=0):
        tui.save_menu_dialog(mock_stdscr)
        
    tui.save_config_to_file.assert_not_called()
    tui.save_config_as_dialog.assert_not_called()


def test_tui_draw_main_screen_version():
    from chatybot.config_model import ChatConfig
    tui = ConfigTUI(config_path="test_config.toml")
    tui.config = ChatConfig(models={})
    tui.sync_models_list()
    
    mock_stdscr = MagicMock()
    mock_stdscr.getmaxyx.return_value = (40, 80)
    
    with patch("curses.color_pair", return_value=0):
        tui.draw_main_screen(mock_stdscr)
        
    # Verify that stdscr.addstr was called with a version string
    called_args = []
    for call in mock_stdscr.addstr.call_args_list:
        args, kwargs = call
        for arg in args:
            if isinstance(arg, str):
                called_args.append(arg)
            
    # Check that some form of version string (e.g. starting with "v") is drawn
    # e.g., "v0.5.0"
    version_drawn = any(val.startswith("v") and len(val) >= 4 for val in called_args)
    assert version_drawn


def test_huggingface_vendor_preset():
    from chatybot.vendors import VENDOR_PRESETS, vendor_names
    assert "huggingface" in VENDOR_PRESETS
    assert "huggingface" in vendor_names()
    preset = VENDOR_PRESETS["huggingface"]
    assert preset.name == "huggingface"
    assert preset.base_url == "https://router.huggingface.co/v1"
    assert preset.api_key_env == "HF_API_KEY"


def test_huggingface_model_initialization():
    tui = ConfigTUI(config_path="test_config.toml")
    tui.config = ChatConfig(models={})
    tui.edit_model_form = MagicMock()
    
    mock_stdscr = MagicMock()
    tui.initialize_new_model_form(mock_stdscr, "huggingface")
    
    tui.edit_model_form.assert_called_once()
    args, kwargs = tui.edit_model_form.call_args
    alias, model = args[1], args[2]
    assert model.vendor == "huggingface"
    assert model.base_url == "https://router.huggingface.co/v1"
    assert model.api_key == "HF_API_KEY"


def test_get_env_status_functionality():
    from chatybot.vendors import get_env_status
    import os
    
    with patch.dict(os.environ, {"HF_API_KEY": "hf_1234567890abcdef", "CUSTOM_SERVICE_API_KEY": "secret_abc"}, clear=False):
        env_status = get_env_status()
        
        # Must include HF_API_KEY and other templates
        names = [e["name"] for e in env_status]
        assert "HF_API_KEY" in names
        assert "MISTRAL_API_KEY" in names
        assert "OPENAI_API_KEY" in names
        assert "CUSTOM_SERVICE_API_KEY" in names
        
        hf_item = next(e for e in env_status if e["name"] == "HF_API_KEY")
        assert hf_item["is_set"] is True
        assert hf_item["length"] == len("hf_1234567890abcdef")
        assert hf_item["masked"].startswith("hf_")
        assert "huggingface" in hf_item["source"]


def test_show_env_vars_dialog():
    tui = ConfigTUI(config_path="test_config.toml")
    tui.config = ChatConfig(models={})
    
    mock_stdscr = MagicMock()
    mock_stdscr.getmaxyx.return_value = (40, 80)
    
    mock_win = MagicMock()
    mock_win.getmaxyx.return_value = (24, 70)
    # Press 'q' to close
    mock_win.getch.side_effect = [ord('q')]
    
    with patch("curses.newwin", return_value=mock_win), \
         patch("curses.color_pair", return_value=0):
        tui.show_env_vars_dialog(mock_stdscr)
        
    mock_win.refresh.assert_called()


def test_bulk_replace_scopes():
    tui = ConfigTUI()
    tui.config = ChatConfig(models={
        "mistral_1": ChatModelConfig(name="mistral-large", base_url="https://api.mistral.ai/v1", vendor="mistral"),
        "gemini_1": ChatModelConfig(name="gemini-flash", base_url="https://generativelanguage.googleapis.com/v1beta/openai/", vendor="google"),
        "gemini_2": ChatModelConfig(name="gemini-pro", base_url="https://generativelanguage.googleapis.com/v1beta/openai/", vendor="google"),
    })
    tui.sync_models_list()

    scopes = tui.get_available_replace_scopes()
    scope_labels = [s[0] for s in scopes]
    assert "All Models" in scope_labels
    assert "Vendor: google" in scope_labels
    assert "Vendor: mistral" in scope_labels


def test_compute_bulk_replacements_api_key_replace():
    tui = ConfigTUI()
    tui.config = ChatConfig(models={
        "gemini_1": ChatModelConfig(name="gemini-flash", base_url="https://generativelanguage.googleapis.com/v1beta/openai/", api_key="GEMINI_API_KEY", vendor="google"),
        "gemini_2": ChatModelConfig(name="gemini-pro", base_url="https://generativelanguage.googleapis.com/v1beta/openai/", api_key="GEMINI_API_KEY", vendor="google"),
        "mistral_1": ChatModelConfig(name="mistral-large", base_url="https://api.mistral.ai/v1", api_key="MISTRAL_API_KEY", vendor="mistral"),
    })
    tui.sync_models_list()

    # Replace GEMINI_API_KEY -> GOOGLE_API_KEY for all models
    err, candidates = tui.compute_bulk_replacements(
        field_key="api_key",
        scope_type="all",
        scope_value="",
        mode="replace",
        find_str="GEMINI_API_KEY",
        replace_str="GOOGLE_API_KEY",
    )
    assert err is None
    assert len(candidates) == 2
    for c in candidates:
        assert c["old_val"] == "GEMINI_API_KEY"
        assert c["new_val"] == "GOOGLE_API_KEY"
        assert c["enabled"] is True


def test_compute_bulk_replacements_vendor_scope():
    tui = ConfigTUI()
    tui.config = ChatConfig(models={
        "gemini_1": ChatModelConfig(name="gemini-flash", base_url="https://generativelanguage.googleapis.com/v1beta/openai/", temperature=0.7, vendor="google"),
        "gemini_2": ChatModelConfig(name="gemini-pro", base_url="https://generativelanguage.googleapis.com/v1beta/openai/", temperature=0.7, vendor="google"),
        "mistral_1": ChatModelConfig(name="mistral-large", base_url="https://api.mistral.ai/v1", temperature=0.7, vendor="mistral"),
    })
    tui.sync_models_list()

    # Set temperature = 0.0 only for google vendor
    err, candidates = tui.compute_bulk_replacements(
        field_key="temperature",
        scope_type="vendor",
        scope_value="google",
        mode="set",
        find_str="",
        replace_str="0.0",
    )
    assert err is None
    assert len(candidates) == 2
    aliases = [c["alias"] for c in candidates]
    assert "gemini_1" in aliases
    assert "gemini_2" in aliases
    assert "mistral_1" not in aliases
    assert candidates[0]["new_val"] == 0.0


def test_compute_bulk_replacements_validation_and_errors():
    tui = ConfigTUI()
    tui.config = ChatConfig(models={
        "mistral_1": ChatModelConfig(name="mistral-large", base_url="https://api.mistral.ai/v1", vendor="mistral"),
    })
    tui.sync_models_list()

    # Invalid float
    err, candidates = tui.compute_bulk_replacements(
        field_key="temperature",
        scope_type="all",
        scope_value="",
        mode="set",
        find_str="",
        replace_str="invalid_float",
    )
    assert "Invalid float value" in err

    # Negative temperature
    err, candidates = tui.compute_bulk_replacements(
        field_key="temperature",
        scope_type="all",
        scope_value="",
        mode="set",
        find_str="",
        replace_str="-0.5",
    )
    assert "Temperature must be >= 0.0" in err

    # Empty find string in replace mode for string
    err, candidates = tui.compute_bulk_replacements(
        field_key="base_url",
        scope_type="all",
        scope_value="",
        mode="replace",
        find_str="",
        replace_str="https://new-url.com",
    )
    assert "Find value cannot be empty" in err


def test_apply_bulk_replacements():
    tui = ConfigTUI()
    tui.config = ChatConfig(models={
        "m1": ChatModelConfig(name="m1", base_url="https://api.test/v1", api_key="OLD_KEY"),
        "m2": ChatModelConfig(name="m2", base_url="https://api.test/v1", api_key="OLD_KEY"),
    })
    tui.sync_models_list()

    changes = [
        {"alias": "m1", "field": "api_key", "new_val": "NEW_KEY", "enabled": True},
        {"alias": "m2", "field": "api_key", "new_val": "NEW_KEY", "enabled": False},  # unchecked
    ]

    applied_count = tui.apply_bulk_replacements(changes)
    assert applied_count == 1
    assert tui.config.models["m1"].api_key == "NEW_KEY"
    assert tui.config.models["m2"].api_key == "OLD_KEY"
    assert tui.has_changes is True


def test_bulk_replace_dialog_cancel():
    tui = ConfigTUI(config_path="test_config.toml")
    tui.config = ChatConfig(models={
        "mistral_1": ChatModelConfig(name="mistral-large", base_url="https://api.mistral.ai/v1", vendor="mistral")
    })
    tui.sync_models_list()

    mock_stdscr = MagicMock()
    mock_stdscr.getmaxyx.return_value = (40, 80)

    mock_win = MagicMock()
    mock_win.getmaxyx.return_value = (17, 64)
    # Press ESC to exit dialog
    mock_win.getch.side_effect = [27]

    with patch("curses.newwin", return_value=mock_win), \
         patch("curses.color_pair", return_value=0):
        tui.bulk_replace_dialog(mock_stdscr)

    mock_win.refresh.assert_called()


def test_bulk_replace_preview_dialog_flow():
    tui = ConfigTUI(config_path="test_config.toml")
    tui.config = ChatConfig(models={
        "m1": ChatModelConfig(name="m1", base_url="https://api.test/v1", api_key="OLD_KEY")
    })
    tui.sync_models_list()

    mock_stdscr = MagicMock()
    mock_stdscr.getmaxyx.return_value = (40, 80)

    mock_win = MagicMock()
    mock_win.getmaxyx.return_value = (20, 70)
    # Press Tab to focus Apply, then Enter
    mock_win.getch.side_effect = [9, 10]

    candidates = [
        {
            "alias": "m1",
            "model_name": "m1",
            "vendor": "custom",
            "field": "api_key",
            "old_val": "OLD_KEY",
            "new_val": "NEW_KEY",
            "enabled": True,
        }
    ]

    with patch("curses.newwin", return_value=mock_win), \
         patch("curses.color_pair", return_value=0):
        result = tui.bulk_replace_preview_dialog(mock_stdscr, candidates, "Test Summary")

    assert result is True
    assert tui.config.models["m1"].api_key == "NEW_KEY"


def test_cycle_index_fallback():
    opts = ["mistral", "google", "openai"]
    # Existing in list
    assert ConfigTUI._cycle_index(opts, "google") == 1
    # Not in list (custom vendor) -> fallback to 0 safely without crash
    assert ConfigTUI._cycle_index(opts, "custom_unlisted_vendor") == 0


def test_apply_form_edits_preserves_context_limit():
    tui = ConfigTUI()
    tui.config = ChatConfig(models={
        "m1": ChatModelConfig(
            name="old-name",
            base_url="https://api.test/v1",
            context_limit=128000,
            vendor="mistral",
        )
    })
    tui.sync_models_list()

    form_data = {
        "alias": "m1",
        "name": "new-name",
        "type": "chat",
        "base_url": "https://api.test/v1",
        "api_key": "",
        "vendor": "mistral",
        "temperature": "0.7",
        "top_k": "1",
        "image_generation": "false",
        "image_endpoint": "",
        "image_modalities": "",
    }

    success = tui.apply_form_edits("m1", form_data, is_new=False)
    assert success is True
    updated_model = tui.config.models["m1"]
    assert updated_model.name == "new-name"
    # Verify context_limit was preserved from the existing model
    assert updated_model.context_limit == 128000







