"""
Unit tests for Profile unmanaged custom content region parsing and preservation.
"""

import tempfile
import os
from chatybot.profile_model import Profile, UNMANAGED_CONTENT_DELIMITER
from chatybot.profile_manager import ProfileManager


def test_unmanaged_content_parsing_and_preservation():
    """Verify content below the unmanaged delimiter is preserved without parsing."""
    raw_content = """# @name: Custom Preserved Profile
# @description: Test profile with custom unmanaged body
/model devstral_1
/temp 0.5

# ============================================================================
# USER CUSTOM CONTENT / MESSAGES / VARIABLES BELOW THIS LINE
# Note: Profile editor will not modify content below this line.
# To edit this profile file directly: /path/to/profile.chatdsl
# ============================================================================

/set MY_CUSTOM_VAR="hello world"
# User notes here
What is the speed of light?
"""
    profile = Profile.from_chatdsl_string(raw_content)
    assert profile.config.model_alias == "devstral_1"
    assert profile.config.temperature == 0.5
    assert "/set MY_CUSTOM_VAR=" in profile.unmanaged_content
    assert "What is the speed of light?" in profile.unmanaged_content

    # Re-serialize and check
    output = profile.to_chatdsl()
    assert UNMANAGED_CONTENT_DELIMITER.split("\n")[1] in output
    assert "/set MY_CUSTOM_VAR=\"hello world\"" in output
    assert "What is the speed of light?" in output


def test_unmanaged_content_file_roundtrip():
    """Verify ProfileManager preserves unmanaged content when saving profiles to disk."""
    with tempfile.TemporaryDirectory() as tmpdir:
        pm = ProfileManager(tmpdir)
        path = os.path.join(tmpdir, "custom.chatdsl")
        
        with open(path, "w", encoding="utf-8") as f:
            f.write("""# @name: Disk Test
/model mistral_1

# ============================================================================
# USER CUSTOM CONTENT / MESSAGES / VARIABLES BELOW THIS LINE
# Note: Profile editor will not modify content below this line.
# To edit this profile file directly: /tmp/custom.chatdsl
# ============================================================================

Custom prompt text here
""")
        
        loaded = pm.load_profile("custom")
        assert "Custom prompt text here" in loaded.unmanaged_content
        
        # Save modifications to structured fields
        loaded = loaded.with_updates(name="Updated Disk Test")
        pm.save_profile(loaded, "custom")
        
        with open(path, "r", encoding="utf-8") as f:
            reloaded_str = f.read()
            
        assert "# @name: Updated Disk Test" in reloaded_str
        assert "Custom prompt text here" in reloaded_str
