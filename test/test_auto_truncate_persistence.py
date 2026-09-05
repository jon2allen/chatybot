import pytest
import tempfile
import os
from chatybot.chatybot_app import ChatybotApp
from chatybot.config_model import ChatConfig
from chatybot.config_manager import ConfigManager
from chatybot.profile_model import Profile, ProfileConfig, ProfileMeta
from chatybot.profile_manager import ProfileManager


def test_config_model_auto_truncate():
    # 1. Defaults
    config_default = ChatConfig()
    assert config_default.auto_truncate is False
    assert config_default.auto_truncate_pct == 100.0

    # 2. Custom values
    config_custom = ChatConfig(auto_truncate=True, auto_truncate_pct=85.0)
    assert config_custom.auto_truncate is True
    assert config_custom.auto_truncate_pct == 85.0

    # 3. Invalid bounds validation
    with pytest.raises(ValueError):
        ChatConfig(auto_truncate_pct=5.0)

    with pytest.raises(ValueError):
        ChatConfig(auto_truncate_pct=105.0)


def test_config_manager_loads_auto_truncate():
    toml_content = """
auto_truncate = true
auto_truncate_pct = 75.0

[models.test_model]
name = "test-model"
base_url = "https://api.test.ai/v1"
"""
    with tempfile.NamedTemporaryFile("w", suffix=".toml", delete=False) as f:
        f.write(toml_content)
        tmp_path = f.name

    try:
        cm = ConfigManager(tmp_path)
        cm.load_config()
        assert cm.auto_truncate is True
        assert cm.auto_truncate_pct == 75.0
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


def test_profile_model_auto_truncate_parse_and_serialize():
    dsl_content = """# @name: Auto Truncate Profile
/model devstral_1
/auto_truncate 80
/tool off
"""
    profile = Profile.from_chatdsl_string(dsl_content)
    assert profile.config.auto_truncate is True
    assert profile.config.truncate_pct == 80.0

    serialized = profile.to_chatdsl()
    assert "/auto_truncate 80" in serialized

    # Test turning off
    dsl_off = """# @name: Disabled Truncate Profile
/model devstral_1
/auto_truncate off
"""
    profile_off = Profile.from_chatdsl_string(dsl_off)
    assert profile_off.config.auto_truncate is False

    serialized_off = profile_off.to_chatdsl()
    assert "/auto_truncate off" in serialized_off


@pytest.mark.anyio
async def test_profile_manager_applies_auto_truncate():
    app = ChatybotApp()
    app.initialize()

    # Create a profile with auto_truncate = True, pct = 70.0
    profile = Profile(
        meta=ProfileMeta(name="Test Auto Truncate"),
        config=ProfileConfig(
            model_alias="devstral_1",
            auto_truncate=True,
            truncate_pct=70.0,
        ),
    )

    pm = ProfileManager()
    pm.apply_profile_commands(profile, app)

    assert app.context_limiter.auto_truncate is True
    assert app.context_limiter.truncate_pct == 70.0
