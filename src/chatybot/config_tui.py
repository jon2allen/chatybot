# src/chatybot/config_tui.py
"""
Curses-based terminal UI (TUI) for managing chatybot configuration.
Allows browsing, editing, cloning, deleting models with vendor presets.
"""

import os
import sys
import argparse
import curses
import curses.textpad
from typing import Optional, List, Tuple, Dict, Any

from .config_model import ChatConfig, ChatModelConfig, RerankerModelConfig
from .vendors import VENDOR_PRESETS, vendor_names, get_env_status


class ConfigTUI:
    def __init__(self, config_path: Optional[str] = None):
        self.config_path = config_path or "~/.config/chatybot/chat_config.toml"
        self.resolved_path = os.path.expanduser(self.config_path)
        self.config: Optional[ChatConfig] = None
        self.models_list: List[Tuple[str, Any]] = []  # List of (alias, model_object)
        self.filtered_list: List[Tuple[str, Any]] = []
        
        # UI State
        self.selected_idx = 0
        self.scroll_offset = 0
        self.filter_text = ""
        self.status_message = ""
        self.status_is_error = False
        self.has_changes = False

    def load_config(self) -> bool:
        """Load config from path or initialize a new one if not found."""
        try:
            if not os.path.exists(self.resolved_path):
                # Try to copy template config if it doesn't exist
                os.makedirs(os.path.dirname(self.resolved_path), exist_ok=True)
                local_config = os.path.join(os.path.dirname(__file__), "chat_config.toml")
                if os.path.exists(local_config):
                    import shutil
                    shutil.copy2(local_config, self.resolved_path)
                    self.set_status(f"Initialized new config at '{self.config_path}'")
                else:
                    # Create an empty config object
                    self.config = ChatConfig(models={})
                    self.set_status("Config file not found. Starting empty.")
                    self.sync_models_list()
                    return True

            self.config = ChatConfig.from_toml(self.resolved_path)
            self.sync_models_list()
            self.set_status(f"Loaded config from '{self.config_path}'")
            return True
        except Exception as e:
            self.status_message = f"Error loading config: {str(e)}"
            self.status_is_error = True
            return False

    def sync_models_list(self):
        """Sync the list helper with the config's dictionary."""
        if not self.config:
            self.models_list = []
        else:
            self.models_list = list(self.config.models.items())
        self.apply_filter()

    def apply_filter(self):
        """Filter models list based on filter_text."""
        if not self.filter_text:
            self.filtered_list = self.models_list
        else:
            q = self.filter_text.lower()
            self.filtered_list = [
                (alias, m) for alias, m in self.models_list
                if q in alias.lower() or q in m.name.lower() or (getattr(m, "vendor", None) and q in getattr(m, "vendor", None).lower())
            ]
        
        # Adjust selection if list shrank
        if self.selected_idx >= len(self.filtered_list):
            self.selected_idx = max(0, len(self.filtered_list) - 1)
        if self.selected_idx < 0:
            self.selected_idx = 0

    def set_status(self, msg: str, is_error: bool = False):
        self.status_message = msg
        self.status_is_error = is_error

    def run(self, stdscr):
        # Configure curses
        curses.curs_set(0)  # Hide cursor
        stdscr.keypad(True)
        
        # Color pairs
        curses.start_color()
        curses.use_default_colors()
        curses.init_pair(1, curses.COLOR_CYAN, -1)     # Header / Values
        curses.init_pair(2, curses.COLOR_BLACK, curses.COLOR_CYAN) # Selected row
        curses.init_pair(3, curses.COLOR_YELLOW, -1)   # Warning / Section header
        curses.init_pair(4, curses.COLOR_RED, -1)      # Error / Alert
        curses.init_pair(5, curses.COLOR_GREEN, -1)    # Success / OK

        if not self.config:
            if not self.load_config():
                # Show error screen and wait for keypress to exit
                stdscr.clear()
                stdscr.addstr(2, 2, "Chatybot TUI Loader Error", curses.color_pair(4) | curses.A_BOLD)
                stdscr.addstr(4, 2, self.status_message)
                stdscr.addstr(6, 2, "Press any key to exit...")
                stdscr.refresh()
                stdscr.getch()
                return

        while True:
            h, w = stdscr.getmaxyx()
            if h < 35 or w < 80:
                self.draw_resize_warning(stdscr, req_h=35, req_w=80)
                ch = stdscr.getch()
                if ch == ord('q') or ch == ord('Q'):
                    break
                elif ch == curses.KEY_RESIZE:
                    stdscr.clear()
                continue

            self.draw_main_screen(stdscr)
            ch = stdscr.getch()

            if ch == ord('q') or ch == ord('Q'):
                if self.has_changes:
                    if self.prompt_save_changes(stdscr):
                        break
                else:
                    break
            elif ch == curses.KEY_UP or ch == ord('k'):
                if self.selected_idx > 0:
                    self.selected_idx -= 1
                    if self.selected_idx < self.scroll_offset:
                        self.scroll_offset = self.selected_idx
            elif ch == curses.KEY_DOWN or ch == ord('j'):
                if self.selected_idx < len(self.filtered_list) - 1:
                    self.selected_idx += 1
                    max_rows = curses.LINES - 7  # height of list area
                    if self.selected_idx >= self.scroll_offset + max_rows:
                        self.scroll_offset = self.selected_idx - max_rows + 1
            elif ch == curses.KEY_PPAGE: # Page Up
                max_rows = curses.LINES - 7
                self.selected_idx = max(0, self.selected_idx - max_rows)
                self.scroll_offset = max(0, self.scroll_offset - max_rows)
            elif ch == curses.KEY_NPAGE: # Page Down
                max_rows = curses.LINES - 7
                self.selected_idx = min(len(self.filtered_list) - 1, self.selected_idx + max_rows)
                self.scroll_offset = min(
                    max(0, len(self.filtered_list) - max_rows),
                    self.scroll_offset + max_rows
                )
            elif ch == curses.KEY_HOME:
                self.selected_idx = 0
                self.scroll_offset = 0
            elif ch == curses.KEY_END:
                self.selected_idx = max(0, len(self.filtered_list) - 1)
                max_rows = curses.LINES - 7
                self.scroll_offset = max(0, len(self.filtered_list) - max_rows)
            elif ch == ord('/'):
                self.handle_search(stdscr)
            elif ch == 10:  # Enter (Edit)
                if self.filtered_list:
                    alias, model = self.filtered_list[self.selected_idx]
                    self.edit_model_form(stdscr, alias, model)
            elif ch == ord('n') or ch == ord('N'):
                self.create_new_model(stdscr)
            elif ch == ord('c') or ch == ord('C'):
                if self.filtered_list:
                    alias, model = self.filtered_list[self.selected_idx]
                    self.clone_model_dialog(stdscr, alias, model)
            elif ch == ord('d') or ch == ord('D'):
                if self.filtered_list:
                    alias, model = self.filtered_list[self.selected_idx]
                    self.delete_model_dialog(stdscr, alias, model)
            elif ch == ord('s') or ch == ord('S'):
                self.save_menu_dialog(stdscr)
            elif ch == ord('e') or ch == ord('E'):
                self.show_env_vars_dialog(stdscr)
            elif ch == curses.KEY_RESIZE:
                # Curses handles resizing; just clear and let next loop redraw
                stdscr.clear()

    def draw_resize_warning(self, stdscr, req_h: int = 35, req_w: int = 80):
        """Draw screen prompt asking user to resize terminal if window is too small."""
        stdscr.erase()
        h, w = stdscr.getmaxyx()
        msg1 = "Terminal size too small!"
        msg2 = f"Current size: {w}x{h}"
        msg3 = f"Please resize terminal to at least {req_w}x{req_h} (width x height)."
        msg4 = "Press 'q' to quit."

        if h >= 6:
            if w > len(msg1) + 2:
                stdscr.addstr(1, max(0, (w - len(msg1)) // 2), msg1, curses.color_pair(4) | curses.A_BOLD)
            if w > len(msg2) + 2:
                stdscr.addstr(2, max(0, (w - len(msg2)) // 2), msg2, curses.color_pair(3))
            if w > len(msg3) + 2:
                stdscr.addstr(4, max(0, (w - len(msg3)) // 2), msg3, curses.A_BOLD)
            if w > len(msg4) + 2:
                stdscr.addstr(5, max(0, (w - len(msg4)) // 2), msg4, curses.A_DIM)
        stdscr.refresh()

    def draw_main_screen(self, stdscr):
        stdscr.erase()
        h, w = stdscr.getmaxyx()
        
        # Header (2 lines)
        stdscr.addstr(0, 0, " Chatybot Config Manager", curses.color_pair(1) | curses.A_BOLD)
        
        try:
            from . import __version__
            version_str = f"v{__version__}"
        except Exception:
            try:
                import importlib.metadata
                version_str = f"v{importlib.metadata.version('chatybot')}"
            except Exception:
                version_str = "unknown"
            
        if w - len(version_str) - 2 > 30:
            stdscr.addstr(0, w - len(version_str) - 2, version_str, curses.color_pair(3))
        
        file_msg = f" File: {self.config_path}"
        loaded_msg = f"{len(self.models_list)} models loaded"
        if self.filter_text:
            loaded_msg += f" ({len(self.filtered_list)} matching)"
        if self.has_changes:
            loaded_msg += " [Unsaved changes]"
            
        stdscr.addstr(1, 0, file_msg[:w-30])
        if w - len(loaded_msg) - 2 > len(file_msg):
            stdscr.addstr(1, w - len(loaded_msg) - 2, loaded_msg, curses.A_DIM)
            
        # Divider
        stdscr.addstr(2, 0, "─" * (w - 1), curses.A_DIM)
        
        # Table Headers
        headers = f"  #   {'Alias':<22} {'Model Name':<32} {'Vendor':<12} {'Temp':<6}"
        stdscr.addstr(3, 0, headers[:w-1], curses.A_BOLD)
        stdscr.addstr(4, 0, "  " + "─" * (w - 5), curses.A_DIM)
        
        # List Area
        list_h = h - 7  # Height remaining for list
        visible_items = self.filtered_list[self.scroll_offset : self.scroll_offset + list_h]
        
        for idx, (alias, model) in enumerate(visible_items):
            actual_idx = self.scroll_offset + idx
            y = 5 + idx
            
            # Formatting values
            vendor_str = getattr(model, "vendor", None) or getattr(model, "detected_vendor", "") or "—"
            temp_str = f"{model.temperature:.2f}" if getattr(model, "temperature", None) is not None else "—"
            name_str = model.name
            
            # Truncation limits
            alias_disp = alias[:21]
            name_disp = name_str[:31]
            vendor_disp = vendor_str[:11]
            
            indicator = ">" if actual_idx == self.selected_idx else " "
            row_text = f"{indicator}{actual_idx+1:<3} {alias_disp:<22} {name_disp:<32} {vendor_disp:<12} {temp_str:<6}"
            
            # Fill the rest of the row with spaces
            row_text = f"{row_text:<{w-1}}"[:w-1]
            
            if actual_idx == self.selected_idx:
                stdscr.addstr(y, 0, row_text, curses.color_pair(2))
            else:
                stdscr.addstr(y, 0, row_text)
                
        # Fill empty space
        for y in range(5 + len(visible_items), h - 2):
            stdscr.addstr(y, 0, " " * (w - 1))
            
        # Status Bar / Message
        stdscr.addstr(h - 2, 0, "─" * (w - 1), curses.A_DIM)
        if self.status_message:
            color = curses.color_pair(4) if self.status_is_error else curses.color_pair(3)
            stdscr.addstr(h - 2, 2, f" {self.status_message} "[:w-4], color | curses.A_BOLD)
            
        # Key bindings bar
        keys_bar = " ↑↓ Navigate │ ↵ Edit │ N New │ C Clone │ D Delete │ S Save │ E Env │ Q Quit │ / Filter"
        stdscr.addstr(h - 1, 0, keys_bar[:w-1], curses.color_pair(2))
        stdscr.refresh()

    def handle_search(self, stdscr):
        h, w = stdscr.getmaxyx()
        stdscr.move(h - 1, 0)
        stdscr.clrtoeol()
        stdscr.addstr(h - 1, 0, "Filter: ", curses.color_pair(3))
        
        # Read text character by character
        curses.curs_set(1)  # Show cursor
        current_filter = self.filter_text
        
        while True:
            stdscr.move(h - 1, 8)
            stdscr.clrtoeol()
            stdscr.addstr(h - 1, 8, current_filter[:w-12])
            stdscr.refresh()
            
            ch = stdscr.getch()
            if ch in (10, 13):  # Enter
                break
            elif ch == 27:  # Escape
                current_filter = ""
                break
            elif ch in (curses.KEY_BACKSPACE, 127, 8):
                current_filter = current_filter[:-1]
            elif 32 <= ch <= 126:
                current_filter += chr(ch)
                
            self.filter_text = current_filter
            self.apply_filter()
            self.draw_main_screen(stdscr)
            stdscr.addstr(h - 1, 0, "Filter: ", curses.color_pair(3))
            
        curses.curs_set(0)  # Hide cursor
        self.filter_text = current_filter
        self.apply_filter()
        self.set_status("Filter updated")

    def edit_text_input(self, parent_win, y, x, width, initial_value: str, label: str) -> str:
        """Edit text field inline/dialog securely."""
        parent_win.move(y, x)
        curses.curs_set(1)
        val = initial_value
        
        while True:
            # Render field background and text
            parent_win.addstr(y, x, "[" + " " * (width - 2) + "]")
            disp_val = val[-(width - 4):]  # Scroll text if too long
            parent_win.addstr(y, x + 1, disp_val, curses.color_pair(1))
            
            # Position cursor at end of text
            cursor_pos = x + 1 + len(disp_val)
            parent_win.move(y, cursor_pos)
            parent_win.refresh()
            
            ch = parent_win.getch()
            if ch in (10, 13):  # Enter
                break
            elif ch == 27:  # Escape
                val = initial_value
                break
            elif ch in (curses.KEY_BACKSPACE, 127, 8):
                val = val[:-1]
            elif 32 <= ch <= 126:
                val += chr(ch)
                
        curses.curs_set(0)
        return val

    def draw_dialog_border(self, win, title: str):
        win.erase()
        win.box()
        h, w = win.getmaxyx()
        title_disp = f" {title} "
        if len(title_disp) < w - 4:
            win.addstr(0, (w - len(title_disp)) // 2, title_disp, curses.color_pair(1) | curses.A_BOLD)

    def prompt_save_changes(self, stdscr) -> bool:
        """Prompt to save changes before exiting. Return True to exit, False to abort."""
        h, w = stdscr.getmaxyx()
        win_h, win_w = 10, 48
        win_y = (h - win_h) // 2
        win_x = (w - win_w) // 2
        
        win = curses.newwin(win_h, win_w, win_y, win_x)
        win.keypad(True)
        self.draw_dialog_border(win, "Save Configuration?")
        
        win.addstr(2, 4, "You have unsaved changes.")
        win.addstr(4, 4, f"Save to: {self.config_path}")
        
        options = ["[ Save ]", "[ Save As ]", "[ Discard ]", "[ Cancel ]"]
        sel = 0
        
        while True:
            # Render options
            for idx, opt in enumerate(options):
                opt_x = 4 + (idx * 10)
                if idx == sel:
                    win.addstr(7, opt_x, opt, curses.color_pair(2))
                else:
                    win.addstr(7, opt_x, opt)
            win.refresh()
            
            ch = win.getch()
            if ch == curses.KEY_LEFT:
                sel = (sel - 1) % len(options)
            elif ch == curses.KEY_RIGHT:
                sel = (sel + 1) % len(options)
            elif ch in (10, 13):  # Enter
                if sel == 0:  # Save
                    self.save_config_to_file(stdscr)
                    return True
                elif sel == 1:  # Save As
                    if self.save_config_as_dialog(stdscr):
                        return True
                elif sel == 2:  # Discard
                    return True
                else:  # Cancel
                    return False
            elif ch == 27:  # Escape
                return False

    def save_config_as_dialog(self, stdscr) -> bool:
        h, w = stdscr.getmaxyx()
        win_h, win_w = 8, 48
        win_y = (h - win_h) // 2
        win_x = (w - win_w) // 2
        
        win = curses.newwin(win_h, win_w, win_y, win_x)
        win.keypad(True)
        self.draw_dialog_border(win, "Save Configuration As...")
        
        win.addstr(2, 4, "Path:")
        new_path = self.edit_text_input(win, 3, 4, win_w - 8, self.config_path, "Path")
        
        if new_path and new_path != self.config_path:
            self.config_path = new_path
            self.resolved_path = os.path.expanduser(new_path)
            self.save_config_to_file(stdscr)
            return True
        return False

    def save_menu_dialog(self, stdscr):
        h, w = stdscr.getmaxyx()
        win_h, win_w = 8, 48
        win_y = (h - win_h) // 2
        win_x = (w - win_w) // 2
        
        win = curses.newwin(win_h, win_w, win_y, win_x)
        win.keypad(True)
        self.draw_dialog_border(win, "Save Configuration")
        
        # Display the file to overwrite, truncated if too long
        display_path = self.config_path
        if len(display_path) > 38:
            display_path = "..." + display_path[-35:]
        win.addstr(2, 4, f"File: {display_path}")
        
        options = ["[ Overwrite ]", "[ Save As... ]", "[ Cancel ]"]
        sel = 0  # Overwrite is default
        
        while True:
            # Render options
            for idx, opt in enumerate(options):
                opt_x = 3 + (idx * 15)
                if idx == sel:
                    win.addstr(5, opt_x, opt, curses.color_pair(2))
                else:
                    win.addstr(5, opt_x, opt)
            win.refresh()
            
            ch = win.getch()
            if ch == curses.KEY_LEFT:
                sel = (sel - 1) % len(options)
            elif ch == curses.KEY_RIGHT:
                sel = (sel + 1) % len(options)
            elif ch in (10, 13):  # Enter
                if sel == 0:  # Overwrite
                    self.save_config_to_file(stdscr)
                    break
                elif sel == 1:  # Save As...
                    if self.save_config_as_dialog(stdscr):
                        break
                else:  # Cancel
                    break
            elif ch == 27:  # Escape
                break
        
        # Force a redraw of the main screen after closing
        stdscr.clear()

    def save_config_to_file(self, stdscr):
        try:
            self.config.to_toml(self.resolved_path)
            self.has_changes = False
            self.set_status(f"Saved configuration to '{self.config_path}'")
        except Exception as e:
            self.set_status(f"Error saving config: {str(e)}", is_error=True)

    def delete_model_dialog(self, stdscr, alias: str, model: Any):
        h, w = stdscr.getmaxyx()
        win_h, win_w = 12, 48
        win_y = (h - win_h) // 2
        win_x = (w - win_w) // 2
        
        win = curses.newwin(win_h, win_w, win_y, win_x)
        win.keypad(True)
        self.draw_dialog_border(win, "Delete Model?")
        
        win.addstr(2, 4, "Are you sure you want to delete:")
        win.addstr(4, 6, f"Alias: {alias}", curses.color_pair(1))
        win.addstr(5, 6, f"Model: {model.name[:28]}", curses.color_pair(1))
        win.addstr(6, 6, f"Type:  {model.type}", curses.color_pair(1))
        
        options = ["[ Delete ]", "[ Cancel ]"]
        sel = 1
        
        while True:
            for idx, opt in enumerate(options):
                opt_x = 10 + (idx * 16)
                if idx == sel:
                    win.addstr(9, opt_x, opt, curses.color_pair(4) if idx == 0 else curses.color_pair(2))
                else:
                    win.addstr(9, opt_x, opt)
            win.refresh()
            
            ch = win.getch()
            if ch == curses.KEY_LEFT:
                sel = 0
            elif ch == curses.KEY_RIGHT:
                sel = 1
            elif ch in (10, 13):  # Enter
                if sel == 0:  # Delete
                    del self.config.models[alias]
                    self.has_changes = True
                    self.sync_models_list()
                    self.set_status(f"Deleted model '{alias}'")
                    break
                else:
                    break
            elif ch == 27:
                break

    def clone_model_dialog(self, stdscr, alias: str, model: Any):
        h, w = stdscr.getmaxyx()
        win_h, win_w = 16, 50
        win_y = (h - win_h) // 2
        win_x = (w - win_w) // 2
        
        win = curses.newwin(win_h, win_w, win_y, win_x)
        win.keypad(True)
        self.draw_dialog_border(win, f"Clone Model: {alias}")
        
        win.addstr(2, 4, f"Source model: {model.name[:25]}")
        win.addstr(4, 4, "New Alias:")
        
        # Overrides inputs
        win.addstr(6, 4, "── Quick Overrides ──────────────────", curses.color_pair(3))
        win.addstr(8, 4, "Temperature:")
        win.addstr(9, 4, "Top K:")
        
        new_alias = f"{alias}_clone"
        temp_val = f"{model.temperature}" if getattr(model, "temperature", None) is not None else ""
        top_k_val = f"{model.top_k}" if getattr(model, "top_k", None) is not None else ""
        
        # Setup form navigation
        fields = [
            ("new_alias", 4, 16, 26, new_alias, "text"),
            ("temperature", 8, 18, 10, temp_val, "text"),
            ("top_k", 9, 18, 10, top_k_val, "text"),
        ]
        
        buttons = ["[ Clone ]", "[ Edit Full ]", "[ Cancel ]"]
        focus = 0  # 0-2 fields, 3-5 buttons
        
        while True:
            # Render fields
            for idx, (name, y, x, width, val, f_type) in enumerate(fields):
                win.addstr(y, x, "[" + " " * (width - 2) + "]")
                if focus == idx:
                    win.addstr(y, x + 1, " " * (width - 2), curses.color_pair(2))
                    win.addstr(y, x + 1, val[:width-2], curses.color_pair(2))
                else:
                    win.addstr(y, x + 1, val[:width-2], curses.color_pair(1))
            
            # Render buttons
            for idx, btn in enumerate(buttons):
                btn_x = 4 + (idx * 15)
                if focus == idx + 3:
                    win.addstr(12, btn_x, btn, curses.color_pair(2))
                else:
                    win.addstr(12, btn_x, btn)
                    
            win.refresh()
            
            ch = win.getch()
            if ch == curses.KEY_UP or ch == curses.KEY_PPAGE:
                focus = (focus - 1) % 6
            elif ch == curses.KEY_DOWN or ch == 9 or ch == curses.KEY_NPAGE:  # Down or Tab or Page Down
                focus = (focus + 1) % 6
            elif ch == curses.KEY_LEFT:
                if focus >= 3:  # cycle buttons
                    focus = 3 + (focus - 3 - 1) % 3
            elif ch == curses.KEY_RIGHT:
                if focus >= 3:
                    focus = 3 + (focus - 3 + 1) % 3
            elif ch in (10, 13) or (32 <= ch <= 126) or ch in (8, 127, curses.KEY_BACKSPACE):  # Enter, direct text input, backspace
                if focus < 3:
                    # Edit focused field
                    name, y, x, width, val, f_type = fields[focus]
                    initial_val = val
                    if 32 <= ch <= 126:
                        initial_val = val + chr(ch)
                    elif ch in (8, 127, curses.KEY_BACKSPACE):
                        initial_val = val[:-1]
                    new_val = self.edit_text_input(win, y, x, width, initial_val, name)
                    fields[focus] = (name, y, x, width, new_val, f_type)
                elif ch in (10, 13):
                    btn_idx = focus - 3
                    if btn_idx == 0:  # Clone
                        if self.execute_clone(stdscr, model, fields[0][4], fields[1][4], fields[2][4]):
                            break
                    elif btn_idx == 1:  # Edit Full
                        new_alias_str = fields[0][4].strip()
                        if not new_alias_str:
                            self.set_status("Error: New alias cannot be empty!", is_error=True)
                            continue
                        if new_alias_str in self.config.models:
                            self.set_status(f"Error: Alias '{new_alias_str}' already exists!", is_error=True)
                            continue
                        
                        # Parse quick overrides to build template
                        overrides = {}
                        temp_str = fields[1][4]
                        if temp_str.strip():
                            try:
                                overrides["temperature"] = float(temp_str)
                            except ValueError:
                                pass
                        else:
                            overrides["temperature"] = None
                            
                        top_k_str = fields[2][4]
                        if top_k_str.strip():
                            try:
                                overrides["top_k"] = int(top_k_str)
                            except ValueError:
                                pass
                        else:
                            overrides["top_k"] = None
                            
                        try:
                            cloned_model = model.model_copy(update=overrides)
                            cloned_model.alias = new_alias_str
                            # Open full editor as new model, so cancel won't add it to config
                            self.edit_model_form(stdscr, new_alias_str, cloned_model, is_new=True)
                            break
                        except Exception as e:
                            self.set_status(f"Error preparing clone: {str(e)}", is_error=True)
                    else:  # Cancel
                        break
            elif ch == 27:  # Escape
                break

    def execute_clone(self, stdscr, source_model, new_alias: str, temp_str: str, top_k_str: str) -> bool:
        """Execute the cloning and insert into config. Return True on success."""
        if not new_alias or new_alias.strip() == "":
            self.set_status("Error: New alias cannot be empty!", is_error=True)
            return False
            
        new_alias = new_alias.strip()
        if new_alias in self.config.models:
            # BLOCKS! Duplicate alias must be rejected.
            self.set_status(f"Error: Alias '{new_alias}' already exists!", is_error=True)
            return False
            
        # Parse overrides
        overrides = {}
        if temp_str.strip():
            try:
                overrides["temperature"] = float(temp_str)
                if not (0.0 <= overrides["temperature"] <= 2.0):
                    self.set_status("Warning: Temperature outside typical range (0.0-2.0)", is_error=False)
            except ValueError:
                self.set_status("Warning: Invalid temperature string - ignored", is_error=False)
        else:
            overrides["temperature"] = None
            
        if top_k_str.strip():
            try:
                overrides["top_k"] = int(top_k_str)
            except ValueError:
                self.set_status("Warning: Invalid Top K string - ignored", is_error=False)
        else:
            overrides["top_k"] = None
            
        # Perform Pydantic clone
        try:
            cloned = source_model.model_copy(update=overrides)
            cloned.alias = new_alias
            self.config.models[new_alias] = cloned
            self.has_changes = True
            self.sync_models_list()
            self.set_status(f"Cloned '{source_model.alias}' to '{new_alias}'")
            return True
        except Exception as e:
            self.set_status(f"Error cloning model: {str(e)}", is_error=True)
            return False

    def show_env_vars_dialog(self, stdscr):
        """Display environment variables & API keys in a scrollable dialog overlay."""
        h, w = stdscr.getmaxyx()
        win_h = min(26, max(12, h - 4))
        win_w = min(92, max(60, w - 4))
        if win_h < 10 or win_w < 50:
            return
            
        win_y = (h - win_h) // 2
        win_x = (w - win_w) // 2
        
        win = curses.newwin(win_h, win_w, win_y, win_x)
        win.keypad(True)
        
        models_dict = self.config.models if self.config else None
        env_data = get_env_status(models_dict)
        sel = 0
        scroll = 0
        max_rows = win_h - 7  # lines available for items
        
        while True:
            self.draw_dialog_border(win, "Environment Variables & API Keys (set | grep -i api)")
            
            # Header
            header_str = f"  {'Status':<10} {'Variable Name':<24} {'Value / Masked':<18} {'Len':<5} {'Source':<20}"
            win.addstr(2, 2, header_str[:win_w-4], curses.color_pair(1) | curses.A_BOLD)
            win.addstr(3, 2, "─" * (win_w - 4), curses.A_DIM)
            
            # Rows
            for idx in range(min(max_rows, len(env_data) - scroll)):
                actual_idx = scroll + idx
                item = env_data[actual_idx]
                y = 4 + idx
                
                status_str = "[SET]" if item["is_set"] else "[NOT SET]"
                name_str = item["name"][:23]
                masked_str = item["masked"][:16]
                len_str = str(item["length"]) if item["is_set"] else "-"
                source_str = item["source"][:19]
                
                row_text = f"  {status_str:<10} {name_str:<24} {masked_str:<18} {len_str:<5} {source_str:<20}"[:win_w-4]
                
                if actual_idx == sel:
                    win.addstr(y, 2, row_text, curses.color_pair(2))
                else:
                    if item["is_set"]:
                        # Draw status in green, remainder normal
                        win.addstr(y, 2, f"  {status_str:<10} ", curses.color_pair(5) | curses.A_BOLD)
                        win.addstr(y, 14, f"{name_str:<24} {masked_str:<18} {len_str:<5} {source_str:<20}"[:win_w-16])
                    else:
                        # Draw status in dim red, remainder dim
                        win.addstr(y, 2, f"  {status_str:<10} ", curses.color_pair(4))
                        win.addstr(y, 14, f"{name_str:<24} {masked_str:<18} {len_str:<5} {source_str:<20}"[:win_w-16], curses.A_DIM)
                        
            # Fill empty list rows
            for idx in range(len(env_data), max_rows):
                win.addstr(4 + idx, 2, " " * (win_w - 4))
                
            # Summary & help
            num_set = sum(1 for e in env_data if e["is_set"])
            num_total = len(env_data)
            summary_str = f" Total: {num_total} variables ({num_set} set, {num_total - num_set} not set)"
            win.addstr(win_h - 3, 2, summary_str[:win_w-4], curses.color_pair(3))
            
            help_str = " ↑↓/PgUp/PgDn Navigate │ ESC/ENTER/Q Close"
            win.addstr(win_h - 2, 2, help_str[:win_w-4], curses.A_DIM)
            win.refresh()
            
            ch = win.getch()
            if ch in (curses.KEY_UP, ord('k'), ord('K')):
                if sel > 0:
                    sel -= 1
                    if sel < scroll:
                        scroll = sel
            elif ch in (curses.KEY_DOWN, ord('j'), ord('J')):
                if sel < len(env_data) - 1:
                    sel += 1
                    if sel >= scroll + max_rows:
                        scroll = sel - max_rows + 1
            elif ch == curses.KEY_PPAGE:
                sel = max(0, sel - max_rows)
                scroll = max(0, scroll - max_rows)
            elif ch == curses.KEY_NPAGE:
                sel = min(len(env_data) - 1, sel + max_rows)
                scroll = min(max(0, len(env_data) - max_rows), scroll + max_rows)
            elif ch == curses.KEY_HOME:
                sel = 0
                scroll = 0
            elif ch == curses.KEY_END:
                sel = max(0, len(env_data) - 1)
                scroll = max(0, len(env_data) - max_rows)
            elif ch in (27, 10, 13, ord('q'), ord('Q'), ord('e'), ord('E')):
                break

    def create_new_model(self, stdscr):
        """Show Vendor Picker then open empty model editor form."""
        h, w = stdscr.getmaxyx()
        win_h, win_w = 26, 54
        win_y = (h - win_h) // 2
        win_x = (w - win_w) // 2
        
        win = curses.newwin(win_h, win_w, win_y, win_x)
        win.keypad(True)
        self.draw_dialog_border(win, "Select Vendor Preset")
        
        # Vendor list
        v_names = vendor_names() + ["(custom)"]
        sel = 0
        scroll = 0
        max_v_show = 14
        
        while True:
            # Draw instructions
            win.addstr(2, 4, "Select a vendor preset for default values:")
            
            # Draw vendor list
            for idx in range(min(max_v_show, len(v_names) - scroll)):
                actual_idx = scroll + idx
                y = 4 + idx
                name = v_names[actual_idx]
                
                # Retrieve preset detail
                preset_info = ""
                if name in VENDOR_PRESETS:
                    p = VENDOR_PRESETS[name]
                    preset_info = f" (URL: {p.base_url[:18]}...)"
                else:
                    preset_info = " (Blank custom template)"
                    
                display_str = f"  {name:<12}{preset_info}"[:win_w-8]
                
                if actual_idx == sel:
                    win.addstr(y, 4, f"> {display_str}", curses.color_pair(2))
                else:
                    win.addstr(y, 4, f"  {display_str}")
                    
            # Fill empty list rows
            for idx in range(len(v_names), max_v_show):
                win.addstr(4 + idx, 4, " " * (win_w - 8))
                
            # Draw options
            win.addstr(win_h - 4, 4, "── Help ─────────────────────────────", curses.color_pair(3))
            win.addstr(win_h - 3, 4, "↑↓ Navigate │ ENTER Select │ ESC Cancel")
            win.refresh()
            
            ch = win.getch()
            if ch == curses.KEY_UP:
                if sel > 0:
                    sel -= 1
                    if sel < scroll:
                        scroll = sel
            elif ch == curses.KEY_DOWN:
                if sel < len(v_names) - 1:
                    sel += 1
                    if sel >= scroll + max_v_show:
                        scroll = sel - max_v_show + 1
            elif ch in (10, 13):  # Select
                selected_vendor = v_names[sel]
                self.initialize_new_model_form(stdscr, selected_vendor)
                break
            elif ch == 27:  # Cancel
                break

    def initialize_new_model_form(self, stdscr, vendor_name: str):
        """Create new model based on vendor preset and open the editor."""
        alias = f"new_model_{len(self.models_list) + 1}"
        
        if vendor_name in VENDOR_PRESETS:
            p = VENDOR_PRESETS[vendor_name]
            
            if p.default_type == "reranker":
                model = RerankerModelConfig(
                    alias=alias,
                    name="reranker-model-name",
                    base_url=p.base_url,
                    api_key=p.api_key_env
                )
            else:
                model = ChatModelConfig(
                    alias=alias,
                    name="chat-model-name",
                    base_url=p.base_url,
                    api_key=p.api_key_env,
                    vendor=p.name,
                    image_generation=p.image_support,
                    image_endpoint="/images/generations" if p.image_support else None
                )
        else:
            # Custom default template
            model = ChatModelConfig(
                alias=alias,
                name="custom-model-name",
                base_url="https://api.example.com/v1",
                api_key="API_KEY_ENV_VAR"
            )
            
        # Open main editor form
        self.edit_model_form(stdscr, alias, model, is_new=True)

    def edit_model_form(self, stdscr, initial_alias: str, model: Any, is_new: bool = False):
        """Run form editor overlay."""
        h, w = stdscr.getmaxyx()
        win_h, win_w = 22, 64
        win_y = (h - win_h) // 2
        win_x = (w - win_w) // 2
        
        win = curses.newwin(win_h, win_w, win_y, win_x)
        win.keypad(True)
        self.draw_dialog_border(win, f"Edit Model: {initial_alias}")
        
        # Load values into working buffers
        form_data = {
            "alias": initial_alias,
            "name": model.name,
            "type": model.type,
            "base_url": model.base_url,
            "api_key": model.api_key or "",
            "vendor": getattr(model, "vendor", "") or getattr(model, "detected_vendor", "") or "",
            "temperature": f"{model.temperature}" if getattr(model, "temperature", None) is not None else "",
            "top_k": f"{model.top_k}" if getattr(model, "top_k", None) is not None else "",
            "max_tokens": "", # Default blank
            "image_generation": "false",
            "image_endpoint": "",
            "image_modalities": "",
        }
        
        # Populate additional fields if chat type
        if isinstance(model, ChatModelConfig):
            form_data["image_generation"] = "true" if model.image_generation else "false"
            form_data["image_endpoint"] = model.image_endpoint or ""
            if model.image_modalities:
                form_data["image_modalities"] = ", ".join(model.image_modalities)
                
        # Form field coordinates & types
        # format: (key, label, y, x, field_width, f_type, options_list)
        fields = [
            ("alias",            "Alias:",           2,  16, 24, "text", None),
            ("name",             "Model Name:",      3,  16, 42, "text", None),
            ("type",             "Type:",            4,  16, 16, "cycle", ["chat", "reranker"]),
            
            # Endpoint section
            ("section_ep",       "── Endpoint ────────────────────────", 6, 4, 0, "header", None),
            ("base_url",         "Base URL:",        7,  16, 42, "text", None),
            ("api_key",          "API Key Env:",     8,  16, 24, "text", None),
            ("vendor",           "Vendor:",          9,  16, 16, "cycle", [""] + vendor_names()),
            
            # Parameters section
            ("section_pm",       "── Parameters ──────────────────────", 11, 4, 0, "header", None),
            ("temperature",      "Temperature:",     12, 16, 12, "text", None),
            ("top_k",            "Top K:",           13, 16, 12, "text", None),
            
            # Image Gen section
            ("section_im",       "── Image Generation ────────────────", 15, 4, 0, "header", None),
            ("image_generation", "Enabled:",         16, 16, 12, "cycle", ["true", "false"]),
            ("image_endpoint",   "Endpoint:",        17, 16, 24, "text", None),
            ("image_modalities", "Modalities:",      18, 16, 24, "text", None),
        ]
        
        # Interactive elements only (filter out headers)
        interactive_fields = [f for f in fields if f[5] != "header"]
        
        buttons = ["[ OK ]", "[ Cancel ]", "[ Apply ]"]
        focus = 0  # 0 to len(interactive_fields)-1 are fields, then buttons
        
        while True:
            # Draw headers and labels
            for f in fields:
                key, label, y, x, width, f_type, _ = f
                if f_type == "header":
                    win.addstr(y, x, label, curses.color_pair(3))
                else:
                    win.addstr(y, 4, label)
                    
            # Draw values
            for idx, f in enumerate(interactive_fields):
                key, label, y, x, width, f_type, opts = f
                val = form_data[key]
                
                # Check visibility for image generation parameters if chat is disabled or type is reranker
                if key in ("image_generation", "image_endpoint", "image_modalities") and form_data["type"] == "reranker":
                    # Gray out / hide
                    win.addstr(y, x, " " * width)
                    continue
                if key in ("image_endpoint", "image_modalities") and form_data["image_generation"] == "false":
                    # Gray out / hide
                    win.addstr(y, x, " " * width)
                    continue
                    
                if f_type == "text":
                    win.addstr(y, x, "[" + " " * (width - 2) + "]")
                    disp_val = val[:width-2]
                    if focus == idx:
                        win.addstr(y, x + 1, " " * (width - 2), curses.color_pair(2))
                        win.addstr(y, x + 1, disp_val, curses.color_pair(2))
                    else:
                        win.addstr(y, x + 1, disp_val, curses.color_pair(1))
                elif f_type == "cycle":
                    win.addstr(y, x, "< " + " " * (width - 4) + " >")
                    disp_val = val[:width-4]
                    if focus == idx:
                        win.addstr(y, x + 2, " " * (width - 4), curses.color_pair(2))
                        win.addstr(y, x + 2, disp_val, curses.color_pair(2))
                    else:
                        win.addstr(y, x + 2, disp_val, curses.color_pair(1))
                        
            # Render buttons
            for idx, btn in enumerate(buttons):
                btn_x = 6 + (idx * 16)
                btn_y = win_h - 2
                if focus == len(interactive_fields) + idx:
                    win.addstr(btn_y, btn_x, btn, curses.color_pair(2))
                else:
                    win.addstr(btn_y, btn_x, btn)
                    
            win.refresh()
            
            ch = win.getch()
            if ch == curses.KEY_UP or ch == curses.KEY_PPAGE:
                focus = (focus - 1) % (len(interactive_fields) + 3)
                # Skip invisible fields
                while focus < len(interactive_fields) and self.is_field_hidden(interactive_fields[focus][0], form_data):
                    focus = (focus - 1) % (len(interactive_fields) + 3)
            elif ch == curses.KEY_DOWN or ch == 9 or ch == curses.KEY_NPAGE:  # Down, Tab, Page Down
                focus = (focus + 1) % (len(interactive_fields) + 3)
                while focus < len(interactive_fields) and self.is_field_hidden(interactive_fields[focus][0], form_data):
                    focus = (focus + 1) % (len(interactive_fields) + 3)
            elif ch == curses.KEY_LEFT:
                if focus < len(interactive_fields):
                    key, _, _, _, _, f_type, opts = interactive_fields[focus]
                    if f_type == "cycle":
                        # Cycle left
                        curr_val = form_data[key]
                        c_idx = opts.index(curr_val)
                        form_data[key] = opts[(c_idx - 1) % len(opts)]
                        # Auto-update presets if type/vendor cycles
                        self.handle_preset_auto_pop(key, form_data)
                else:
                    # Cycle buttons
                    btn_focus = focus - len(interactive_fields)
                    focus = len(interactive_fields) + (btn_focus - 1) % 3
            elif ch == curses.KEY_RIGHT:
                if focus < len(interactive_fields):
                    key, _, _, _, _, f_type, opts = interactive_fields[focus]
                    if f_type == "cycle":
                        # Cycle right
                        curr_val = form_data[key]
                        c_idx = opts.index(curr_val)
                        form_data[key] = opts[(c_idx + 1) % len(opts)]
                        self.handle_preset_auto_pop(key, form_data)
                else:
                    # Cycle buttons
                    btn_focus = focus - len(interactive_fields)
                    focus = len(interactive_fields) + (btn_focus + 1) % 3
            elif ch in (10, 13) or (32 <= ch <= 126) or ch in (8, 127, curses.KEY_BACKSPACE):  # Enter, direct text input, backspace
                if focus < len(interactive_fields):
                    key, label, y, x, width, f_type, opts = interactive_fields[focus]
                    if f_type == "text":
                        initial_val = form_data[key]
                        if 32 <= ch <= 126:
                            initial_val = form_data[key] + chr(ch)
                        elif ch in (8, 127, curses.KEY_BACKSPACE):
                            initial_val = form_data[key][:-1]
                        new_val = self.edit_text_input(win, y, x, width, initial_val, key)
                        form_data[key] = new_val
                    elif f_type == "cycle" and ch in (10, 13):
                        # Pressing enter on cycle just goes to next value
                        curr_val = form_data[key]
                        c_idx = opts.index(curr_val)
                        form_data[key] = opts[(c_idx + 1) % len(opts)]
                        self.handle_preset_auto_pop(key, form_data)
                elif ch in (10, 13):
                    btn_idx = focus - len(interactive_fields)
                    if btn_idx == 0:  # OK
                        if self.apply_form_edits(initial_alias, form_data, is_new):
                            break
                    elif btn_idx == 1:  # Cancel
                        break
                    elif btn_idx == 2:  # Apply
                        if self.apply_form_edits(initial_alias, form_data, is_new):
                            initial_alias = form_data["alias"]
                            is_new = False
                            win.erase()
                            self.draw_dialog_border(win, f"Edit Model: {initial_alias}")
            elif ch == 27:  # Escape
                break

    def is_field_hidden(self, key: str, form_data: dict) -> bool:
        if key in ("image_generation", "image_endpoint", "image_modalities") and form_data["type"] == "reranker":
            return True
        if key in ("image_endpoint", "image_modalities") and form_data["image_generation"] == "false":
            return True
        return False

    def handle_preset_auto_pop(self, changed_key: str, form_data: dict):
        """Auto-populate fields if vendor changed or type changed."""
        if changed_key == "vendor" and form_data["vendor"] in VENDOR_PRESETS:
            p = VENDOR_PRESETS[form_data["vendor"]]
            form_data["base_url"] = p.base_url
            if p.api_key_env:
                form_data["api_key"] = p.api_key_env
            form_data["image_generation"] = "true" if p.image_support else "false"
            if p.image_support:
                form_data["image_endpoint"] = "/images/generations"
        elif changed_key == "type":
            if form_data["type"] == "reranker":
                form_data["image_generation"] = "false"
                # If switching to reranker, jina is a good default preset
                if form_data["vendor"] == "":
                    form_data["vendor"] = "jina"
                    p = VENDOR_PRESETS["jina"]
                    form_data["base_url"] = p.base_url
                    form_data["api_key"] = p.api_key_env

    def apply_form_edits(self, old_alias: str, form_data: dict, is_new: bool) -> bool:
        """Validate form data, construct model, and write to in-memory config."""
        new_alias = form_data["alias"].strip()
        
        # 1. Alias Validations (HARD BLOCKS)
        if not new_alias:
            self.set_status("Error: Alias cannot be empty!", is_error=True)
            return False
            
        if (is_new or new_alias != old_alias) and new_alias in self.config.models:
            self.set_status(f"Error: Alias '{new_alias}' already exists!", is_error=True)
            return False
            
        # 2. Extract values and validate parameters (LOOSE WARNINGS)
        temp_val = None
        if form_data["temperature"].strip():
            try:
                temp_val = float(form_data["temperature"])
                if not (0.0 <= temp_val <= 2.0):
                    self.set_status("Warning: Temperature should typically be 0.0 - 2.0.", is_error=False)
            except ValueError:
                self.set_status("Warning: Invalid Temperature representation.", is_error=False)
                
        top_k_val = None
        if form_data["top_k"].strip():
            try:
                top_k_val = int(form_data["top_k"])
            except ValueError:
                self.set_status("Warning: Invalid Top K representation.", is_error=False)

        # 3. Build Pydantic model
        try:
            m_type = form_data["type"]
            api_key = form_data["api_key"].strip() or None
            
            if m_type == "reranker":
                updated_model = RerankerModelConfig(
                    alias=new_alias,
                    name=form_data["name"].strip(),
                    base_url=form_data["base_url"].strip(),
                    api_key=api_key,
                    temperature=temp_val,
                    top_k=top_k_val
                )
            else:
                img_gen = form_data["image_generation"] == "true"
                img_end = form_data["image_endpoint"].strip() or None
                img_mods = None
                if form_data["image_modalities"].strip():
                    img_mods = [x.strip() for x in form_data["image_modalities"].split(",") if x.strip()]
                    
                vendor_val = form_data["vendor"].strip() or None
                
                updated_model = ChatModelConfig(
                    alias=new_alias,
                    name=form_data["name"].strip(),
                    base_url=form_data["base_url"].strip(),
                    api_key=api_key,
                    temperature=temp_val,
                    top_k=top_k_val,
                    vendor=vendor_val,
                    image_generation=img_gen,
                    image_endpoint=img_end,
                    image_modalities=img_mods
                )
                
            # Perform operations on config dictionary
            if not is_new and old_alias != new_alias:
                # Alias renamed: delete old key
                del self.config.models[old_alias]
                
            self.config.models[new_alias] = updated_model
            self.has_changes = True
            self.sync_models_list()
            self.set_status(f"Updated model '{new_alias}'")
            return True
            
        except Exception as e:
            self.set_status(f"Validation warning/error: {str(e)}", is_error=True)
            return False


def main(config_path: Optional[str] = None) -> int:
    """Standalone entry point for TUI config manager."""
    # If not called programmatically with a path, parse sys.argv
    if config_path is None:
        parser = argparse.ArgumentParser(description="Chatybot Curses Config Manager")
        parser.add_argument(
            "-c", "--config",
            help="Path to alternate TOML configuration file",
            default=None
        )
        args, _ = parser.parse_known_args()
        config_path = args.config
        
    tui = ConfigTUI(config_path=config_path)
    
    # Run curses wrapper
    try:
        curses.wrapper(tui.run)
        return 0
    except KeyboardInterrupt:
        return 0
    except Exception as e:
        print(f"\nFatal error in Config TUI: {str(e)}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
