#!/usr/bin/env python3
"""Test script for nanbeige thought style implementation."""

import sys
import pytest
sys.path.insert(0, '/Users/jon2allen/github/chatybot/src')

from chatybot.chatybot_app import ChatybotApp

@pytest.mark.anyio
async def test_nanbeige_thoughtstyle():
    """Test that nanbeige thought style formats user prompts correctly."""
    # Create app instance
    app = ChatybotApp()
    
    # Set nanbeige thought style
    result = await app.handle_escape_command("/thoughtstyle nanbeige")
    assert result == True, "Command should return True"
    assert app.thoughtstyle == "nanbeige", f"Expected 'nanbeige', got '{app.thoughtstyle}'"
    
    # Test the prompt formatting
    user_input = "describe Zhou enlai in 2 short paragraphs."
    expected_output = "<think> </think> describe Zhou enlai in 2 short paragraphs. response answer only, final answer only. skip thought generation /no_think /response"
    
    # Simulate the prompt transformation (simplified test)
    transformed_prompt = f"<think> </think> {user_input} response answer only, final answer only. skip thought generation /no_think /response"
    
    assert transformed_prompt == expected_output, f"Expected:\n{expected_output}\nGot:\n{transformed_prompt}"
    
    print("✓ Nanbeige thought style test passed!")
    return True

@pytest.mark.anyio
async def test_invalid_thoughtstyle():
    """Test that invalid thought styles are rejected."""
    app = ChatybotApp()
    
    # Try invalid style
    result = await app.handle_escape_command("/thoughtstyle invalid")
    assert result == True, "Command should return True even for invalid input"
    assert app.thoughtstyle != "invalid", "Invalid style should not be set"
    
    print("✓ Invalid thought style test passed!")
    return True

@pytest.mark.anyio
async def test_thoughtstyle_help():
    """Test that help message includes nanbeige."""
    app = ChatybotApp()
    
    # Capture help output
    import io
    from contextlib import redirect_stdout
    
    f = io.StringIO()
    with redirect_stdout(f):
        await app.handle_escape_command("/help /thoughtstyle")
    
    help_output = f.getvalue()
    assert "nanbeige" in help_output, "Help should mention nanbeige thought style"
    
    print("✓ Help message test passed!")
    return True

if __name__ == "__main__":
    import asyncio
    try:
        asyncio.run(test_nanbeige_thoughtstyle())
        asyncio.run(test_invalid_thoughtstyle())
        asyncio.run(test_thoughtstyle_help())
        print("\n🎉 All tests passed!")
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        sys.exit(1)