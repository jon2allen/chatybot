"""
Unit tests for terminal dimension check (80x35) in ConfigTUI and ProfileTUI.
"""

from unittest.mock import MagicMock, patch
from chatybot.profile_tui import ProfileTUI
from chatybot.config_tui import ConfigTUI


@patch("curses.color_pair", return_value=0)
def test_profile_tui_resize_warning(mock_color_pair, tmp_path):
    tui = ProfileTUI(profile_dir=str(tmp_path))
    mock_stdscr = MagicMock()
    
    # Simulate window size smaller than 80x35
    mock_stdscr.getmaxyx.return_value = (30, 70)
    
    tui.draw_resize_warning(mock_stdscr, req_h=35, req_w=80)
    
    assert mock_stdscr.erase.called
    assert mock_stdscr.addstr.called
    assert mock_stdscr.refresh.called
    
    call_args_list = [str(call) for call in mock_stdscr.addstr.call_args_list]
    rendered_text = " ".join(call_args_list)
    assert "Terminal size too small" in rendered_text
    assert "80x35" in rendered_text


@patch("curses.color_pair", return_value=0)
def test_config_tui_resize_warning(mock_color_pair):
    tui = ConfigTUI()
    mock_stdscr = MagicMock()
    
    # Simulate window size smaller than 80x35
    mock_stdscr.getmaxyx.return_value = (30, 70)
    
    tui.draw_resize_warning(mock_stdscr, req_h=35, req_w=80)
    
    assert mock_stdscr.erase.called
    assert mock_stdscr.addstr.called
    assert mock_stdscr.refresh.called
    
    call_args_list = [str(call) for call in mock_stdscr.addstr.call_args_list]
    rendered_text = " ".join(call_args_list)
    assert "Terminal size too small" in rendered_text
    assert "80x35" in rendered_text

