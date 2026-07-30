"""
Unit tests for ProfileTUI F1 Help System.
"""

from chatybot.profile_tui import ProfileTUI, FIELD_HELP_DATABASE


def test_field_help_database_coverage():
    """Verify all form field keys have dedicated help entries in FIELD_HELP_DATABASE."""
    expected_keys = [
        "alias", "name", "description", "model", "temperature",
        "top_p", "top_k", "max_tokens", "system_message", "tool_mode",
        "tool_auto_execute", "tool_max_turns", "tool_disabled",
        "trace_tps", "trace_agentic_loop", "trace_raw_payload",
        "trace_rerank", "trace_tps_perf", "reasoning", "show_thinking",
        "reasoning_effort",
    ]
    
    for key in expected_keys:
        assert key in FIELD_HELP_DATABASE, f"Missing help entry for key: {key}"
        entry = FIELD_HELP_DATABASE[key]
        assert "title" in entry and len(entry["title"]) > 0
        assert "description" in entry and len(entry["description"]) > 0
        assert "tips" in entry and len(entry["tips"]) > 0


def test_field_help_database_tool_disabled_content():
    """Verify tool_disabled help documentation explicitly explains globs, quotes, and comma separation."""
    info = FIELD_HELP_DATABASE["tool_disabled"]
    tips = info["tips"].lower()
    
    assert "wildcard" in tips or "glob" in tips
    assert "comma" in tips or "," in tips
    assert "no quotes" in tips or "quotes" in tips
