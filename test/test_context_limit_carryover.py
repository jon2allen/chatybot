import pytest
from unittest.mock import MagicMock
from chatybot.chatybot_app import ChatybotApp
from chatybot.context_limit import ContextLimiter


@pytest.fixture
def mock_app():
    app = ChatybotApp()
    app.initialize()
    # Configure mock models in config_manager
    app.config_manager.config["models"] = {
        "model_with_limit": {
            "name": "model-with-limit-v1",
            "context_limit": 4096,
            "type": "chat"
        },
        "model_without_limit": {
            "name": "model-without-limit-v1",
            "type": "chat"
        },
        "model_with_different_limit": {
            "name": "model-diff-v1",
            "context_limit": 8192,
            "type": "chat"
        }
    }
    return app


@pytest.mark.anyio
async def test_model_switch_carries_over_limit_with_warning(mock_app, capsys):
    # 1. Start with model_with_limit
    await mock_app.handle_escape_command("/model model_with_limit")
    assert mock_app.context_limiter.context_limit == 4096

    capsys.readouterr()  # clear buffer

    # 2. Switch to model_without_limit
    await mock_app.handle_escape_command("/model model_without_limit")
    out = capsys.readouterr().out

    # Assert limit is preserved
    assert mock_app.context_limiter.context_limit == 4096
    # Assert warning message was printed
    assert "[Warning: Context limit is set to 4,096 tokens, and that will be used because none is defined in configuration for model 'model_without_limit'.]" in out


@pytest.mark.anyio
async def test_model_switch_without_limit_when_no_active_limit(mock_app, capsys):
    # Ensure no context limit is active
    mock_app.context_limiter.set_limit(None, from_user=True)
    capsys.readouterr()

    # Switch to model_without_limit
    await mock_app.handle_escape_command("/model model_without_limit")
    out = capsys.readouterr().out

    # Assert context limit remains None
    assert mock_app.context_limiter.context_limit is None
    # Assert no warning is printed
    assert "Warning" not in out
    assert "Switched to model: model-without-limit-v1 (alias: model_without_limit)" in out


@pytest.mark.anyio
async def test_model_switch_to_model_with_new_limit(mock_app, capsys):
    # Start with model_with_limit
    await mock_app.handle_escape_command("/model model_with_limit")
    assert mock_app.context_limiter.context_limit == 4096

    # Switch to model with different limit
    await mock_app.handle_escape_command("/model model_with_different_limit")
    assert mock_app.context_limiter.context_limit == 8192


@pytest.mark.anyio
async def test_session_start_preserves_context_limit(mock_app):
    # Set context limit
    mock_app.context_limiter.set_limit(2048, from_user=True)
    assert mock_app.context_limiter.context_limit == 2048

    # Start new session
    await mock_app.handle_escape_command("/session start new_session_test")
    assert mock_app.context_limiter.context_limit == 2048
