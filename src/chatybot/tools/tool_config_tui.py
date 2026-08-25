# src/chatybot/tools/tool_config_tui.py
"""
Curses-based terminal UI (TUI) for managing ChatyBot tools configuration.
Allows browsing, editing, cloning tools with a tool editor integration.
"""

import os
import sys
try:
    import curses
except ImportError:
    curses = None
from typing import Optional, List, Tuple, Dict, Any
from dataclasses import dataclass, field


@dataclass
class ToolConfig:
    """Represents a tool configuration from tools_config.toml."""
    name: str
    enabled: bool = True
    description: str = ""
    module: str = ""
    function: str = ""
    parameters: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    @classmethod
    def from_toml_section(cls, section: Dict[str, Any], param_sections: Optional[Dict[str, Dict[str, Any]]] = None):
        """Create ToolConfig from TOML section data."""
        params = {}
        if param_sections:
            for param_name, param_data in param_sections.items():
                if param_name.startswith(f"{section.get('name', '')}.parameters."):
                    actual_param = param_name.split(".parameters.")[1]
                    params[actual_param] = param_data
        
        return cls(
            name=section.get("name", ""),
            enabled=section.get("enabled", True),
            description=section.get("description", ""),
            module=section.get("module", ""),
            function=section.get("function", ""),
            parameters=params
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for TOML serialization."""
        return {
            "enabled": self.enabled,
            "description": self.description,
            "module": self.module,
            "function": self.function
        }


class ToolsConfig:
    """Manages the complete tools configuration."""
    
    def __init__(self, config_path: Optional[str] = None):
        self.config_path = config_path or os.path.join(os.path.dirname(__file__), "tools_config.toml")
        self.resolved_path = os.path.expanduser(self.config_path)
        self.tools: Dict[str, ToolConfig] = {}
        self.global_config: Dict[str, Any] = {}
        
    @classmethod
    def from_toml(cls, toml_path: str) -> "ToolsConfig":
        """Load tools configuration from TOML file."""
        try:
            import tomllib
        except ImportError:
            import tomli as tomllib
        
        config = cls(toml_path)
        
        try:
            with open(toml_path, 'rb') as f:
                data = tomllib.load(f)
        except FileNotFoundError:
            # Return empty config
            return config
        except Exception as e:
            raise ValueError(f"Error loading TOML: {e}")
        
        # Extract global config
        if "config" in data:
            config.global_config = data["config"]
        
        # Extract tools
        if "tools" in data:
            for tool_name, tool_data in data["tools"].items():
                # Extract parameters (they are nested in the tool_data)
                params = {}
                if "parameters" in tool_data:
                    params = tool_data["parameters"]
                else:
                    # Also check for separate parameters tables (alternative format)
                    params_key = f"tools.{tool_name}.parameters"
                    if params_key in data:
                        params = data[params_key]
                
                tool_config = ToolConfig(
                    name=tool_name,
                    enabled=tool_data.get("enabled", True),
                    description=tool_data.get("description", ""),
                    module=tool_data.get("module", ""),
                    function=tool_data.get("function", ""),
                    parameters=params
                )
                config.tools[tool_name] = tool_config
        
        return config
    
    def to_toml(self, path: Optional[str] = None) -> str:
        """Serialize configuration to TOML string."""
        lines = []
        
        # Write global config
        if self.global_config:
            lines.append("[config]")
            for key, value in self.global_config.items():
                if isinstance(value, str):
                    # Handle multiline strings
                    if '\n' in value:
                        lines.append(f'{key} = \"\"\"{value}\n\"\"\"')
                    else:
                        lines.append(f'{key} = "{value}"')
                else:
                    lines.append(f"{key} = {value}")
            lines.append("")
        
        # Write tools
        if self.tools:
            for tool_name, tool_config in self.tools.items():
                # Write tool header
                lines.append(f"[tools.{tool_name}]")
                
                # Write tool fields
                tool_dict = tool_config.to_dict()
                for key, value in tool_dict.items():
                    if isinstance(value, str):
                        # Escape quotes
                        value = value.replace('"', '\\"')
                        if '\n' in value:
                            lines.append(f'{key} = \"\"\"{value}\n\"\"\"')
                        else:
                            lines.append(f'{key} = "{value}"')
                    else:
                        lines.append(f"{key} = {str(value).lower()}")
                
                # Write parameters
                if tool_config.parameters:
                    lines.append("")
                    for param_name, param_data in tool_config.parameters.items():
                        lines.append(f"[tools.{tool_name}.parameters.{param_name}]")
                        for pkey, pvalue in param_data.items():
                            if isinstance(pvalue, str):
                                # Escape quotes
                                pvalue = pvalue.replace('"', '\\"')
                                lines.append(f'{pkey} = "{pvalue}"')
                            else:
                                lines.append(f"{pkey} = {str(pvalue).lower()}")
                        lines.append("")
                else:
                    lines.append("")
        
        return "\n".join(lines)
    
    def save(self, path: Optional[str] = None):
        """Save configuration to file."""
        save_path = path or self.resolved_path
        toml_str = self.to_toml()
        
        try:
            with open(save_path, 'w') as f:
                f.write(toml_str)
            return True
        except Exception as e:
            raise ValueError(f"Error saving TOML: {e}")
    
    def has_tool(self, tool_name: str) -> bool:
        """Check if a tool already exists in the config."""
        return tool_name in self.tools
    
    def validate_no_duplicates(self) -> bool:
        """Validate that there are no duplicate tool names. Returns True if valid."""
        seen = set()
        for tool_name in self.tools:
            if tool_name in seen:
                return False
            seen.add(tool_name)
        return True
    
    def get_tools_list(self) -> List[Tuple[str, ToolConfig]]:
        """Get sorted list of tools."""
        return sorted(self.tools.items(), key=lambda x: x[0])


class ToolConfigTUI:
    """TUI for managing ChatyBot tools."""
    
    def __init__(self, config_path: Optional[str] = None, test_mode: bool = False):
        self.config_path = config_path
        self.test_mode = test_mode
        self.config: Optional[ToolsConfig] = None
        self.tools_list: List[Tuple[str, ToolConfig]] = []
        self.filtered_list: List[Tuple[str, ToolConfig]] = []
        
        # UI State
        self.selected_idx = 0
        self.scroll_offset = 0
        self.filter_text = ""
        self.status_message = ""
        self.status_is_error = False
        self.has_changes = False
        
        # Colors
        self.colors = {}
        
    def get_test_config_path(self) -> str:
        """Get the test config path during testing phase."""
        # Check for existing test config files in various locations
        possible_paths = [
            os.path.join(os.getcwd(), "tools_config_test.toml"),  # Current dir
            os.path.join(os.getcwd(), "src", "tools_config_test.toml"),  # src dir
            os.path.join(os.getcwd(), "test_config", "tools_config_test.toml"),  # test_config dir
        ]
        
        for path in possible_paths:
            if os.path.exists(path):
                return path
        
        # Default: use test_config directory
        test_dir = os.path.join(os.getcwd(), "test_config")
        os.makedirs(test_dir, exist_ok=True)
        return os.path.join(test_dir, "tools_config_test.toml")
    
    def get_test_python_dir(self) -> str:
        """Get the test Python directory during testing phase."""
        # Check for existing test tools directories
        possible_dirs = [
            os.path.join(os.getcwd(), "test_tools"),  # Current dir
            os.path.join(os.getcwd(), "src", "test_tools"),  # src dir
        ]
        
        for dir_path in possible_dirs:
            if os.path.exists(dir_path):
                return dir_path
        
        # Default: use test_tools directory
        test_dir = os.path.join(os.getcwd(), "test_tools")
        os.makedirs(test_dir, exist_ok=True)
        return test_dir
    
    def get_actual_config_path(self) -> str:
        """Get the actual config path to use (test or real)."""
        if self.test_mode:
            return self.get_test_config_path()
        return self.config_path or self.get_test_config_path()
    
    def get_actual_python_dir(self) -> str:
        """Get the actual Python directory to use (test or real)."""
        if self.test_mode:
            return self.get_test_python_dir()
        # Default to local test directory
        return self.get_test_python_dir()
    
    def load_config(self) -> bool:
        """Load config from path or initialize a new one if not found."""
        try:
            actual_path = self.get_actual_config_path()
            
            # Ensure parent directory exists
            os.makedirs(os.path.dirname(actual_path), exist_ok=True)
            
            if not os.path.exists(actual_path):
                # Copy from default tools_config.toml if available
                default_config = os.path.join(os.path.dirname(__file__), "tools_config.toml")
                if os.path.exists(default_config):
                    import shutil
                    shutil.copy2(default_config, actual_path)
                    self.set_status(f"Initialized new config at '{actual_path}'")
                else:
                    # Create an empty config
                    self.config = ToolsConfig(actual_path)
                    self.set_status("Config file not found. Starting empty.")
                    self.sync_tools_list()
                    return True
            
            self.config = ToolsConfig.from_toml(actual_path)
            self.config.config_path = actual_path
            self.sync_tools_list()
            self.set_status(f"Loaded config from '{actual_path}'")
            return True
        except Exception as e:
            self.status_message = f"Error loading config: {str(e)}"
            self.status_is_error = True
            return False
    
    def sync_tools_list(self):
        """Sync the list helper with the config's dictionary."""
        if not self.config:
            self.tools_list = []
        else:
            self.tools_list = self.config.get_tools_list()
        self.apply_filter()
    
    def apply_filter(self):
        """Filter tools list based on filter_text."""
        if not self.filter_text:
            self.filtered_list = self.tools_list
        else:
            q = self.filter_text.lower()
            self.filtered_list = [
                (name, tool) for name, tool in self.tools_list
                if q in name.lower() or q in tool.description.lower() or q in tool.module.lower() or q in tool.function.lower()
            ]
        
        # Adjust selection if list shrank
        if self.selected_idx >= len(self.filtered_list):
            self.selected_idx = max(0, len(self.filtered_list) - 1)
        if self.selected_idx < 0:
            self.selected_idx = 0
    
    def set_status(self, msg: str, is_error: bool = False):
        self.status_message = msg
        self.status_is_error = is_error
    
    def init_colors(self, stdscr):
        """Initialize curses color pairs."""
        try:
            curses.start_color()
            curses.use_default_colors()
            curses.init_pair(1, curses.COLOR_CYAN, -1)     # Header / Values
            curses.init_pair(2, curses.COLOR_BLACK, curses.COLOR_CYAN)  # Selected row
            curses.init_pair(3, curses.COLOR_YELLOW, -1)   # Warning / Section header
            curses.init_pair(4, curses.COLOR_RED, -1)      # Error / Alert
            curses.init_pair(5, curses.COLOR_GREEN, -1)    # Success / OK
        except:
            pass
        
        self.colors = {
            "header": curses.color_pair(1),
            "value": curses.color_pair(1),
            "selected": curses.color_pair(2),
            "warning": curses.color_pair(3),
            "error": curses.color_pair(4),
            "success": curses.color_pair(5),
        }
    
    def run(self, stdscr):
        """Main entry point for the TUI."""
        # Initialize curses settings
        stdscr.keypad(True)
        curses.noecho()
        curses.cbreak()
        
        self.init_colors(stdscr)
        
        try:
            curses.curs_set(0)
        except:
            pass
        
        # Try to load config
        if not self.config:
            if not self.load_config():
                # Show error screen and wait for keypress to exit
                stdscr.clear()
                stdscr.addstr(2, 2, "Tool Config TUI Loader Error", curses.color_pair(4) | curses.A_BOLD)
                stdscr.addstr(4, 2, self.status_message)
                stdscr.addstr(6, 2, "Press any key to exit...")
                stdscr.refresh()
                stdscr.getch()
                return
        
        while True:
            self.draw_main_screen(stdscr)
            try:
                ch = stdscr.getch()
            except:
                break
            
            if self.handle_input(stdscr, ch) is False:
                break
    
    def handle_input(self, stdscr, ch):
        """Handle keyboard input. Return False to exit."""
        if ch == ord('q') or ch == ord('Q'):
            if self.has_changes:
                if self.prompt_save_changes(stdscr):
                    return False
                else:
                    return True  # User cancelled, don't exit
            else:
                return False
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
        elif ch == curses.KEY_PPAGE:  # Page Up
            max_rows = curses.LINES - 7
            self.selected_idx = max(0, self.selected_idx - max_rows)
            self.scroll_offset = max(0, self.scroll_offset - max_rows)
        elif ch == curses.KEY_NPAGE:  # Page Down
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
        elif ch == 10:  # Enter (Edit with tool_editor)
            if self.filtered_list:
                tool_name, tool_config = self.filtered_list[self.selected_idx]
                self.edit_tool(stdscr, tool_name, tool_config)
        elif ch == ord('n') or ch == ord('N'):
            self.create_new_tool(stdscr)
        elif ch == ord('c') or ch == ord('C'):
            if self.filtered_list:
                tool_name, tool_config = self.filtered_list[self.selected_idx]
                self.clone_tool_dialog(stdscr, tool_name, tool_config)
        elif ch == ord('d') or ch == ord('D'):
            if self.filtered_list:
                tool_name, tool_config = self.filtered_list[self.selected_idx]
                self.delete_tool_dialog(stdscr, tool_name, tool_config)
        elif ch == ord('s') or ch == ord('S'):
            self.save_menu_dialog(stdscr)
        elif ch == ord('t') or ch == ord('T'):
            # Toggle test mode
            self.test_mode = not self.test_mode
            self.set_status(f"Test mode: {'ON' if self.test_mode else 'OFF'}")
        elif ch == curses.KEY_RESIZE:
            stdscr.clear()
        
        return True
    
    def draw_main_screen(self, stdscr):
        """Draw the main tool listing screen."""
        stdscr.erase()
        try:
            h, w = stdscr.getmaxyx()
        except:
            return
        
        if h < 10 or w < 60:
            self.draw_too_small(stdscr, h, w)
            return
        
        # Header (2 lines)
        title = " Tool Config Manager "
        stdscr.addstr(0, 0, title, curses.color_pair(1) | curses.A_BOLD)
        
        try:
            from .. import __version__
            version_str = f"v{__version__}"
        except Exception:
            try:
                import importlib.metadata
                version_str = f"v{importlib.metadata.version('chatybot')}"
            except Exception:
                version_str = "unknown"
        
        if w - len(version_str) - 2 > 30:
            stdscr.addstr(0, w - len(version_str) - 2, version_str, curses.color_pair(3))
        
        # Status info
        file_msg = f" File: {self.get_actual_config_path()}"
        loaded_msg = f"{len(self.tools_list)} tools loaded"
        if self.filter_text:
            loaded_msg += f" ({len(self.filtered_list)} matching)"
        if self.has_changes:
            loaded_msg += " [Unsaved changes]"
        if self.test_mode:
            loaded_msg += " [TEST MODE]"
        
        stdscr.addstr(1, 0, file_msg[:w-30])
        if w - len(loaded_msg) - 2 > len(file_msg):
            stdscr.addstr(1, w - len(loaded_msg) - 2, loaded_msg, curses.A_DIM)
        
        # Divider
        stdscr.addstr(2, 0, "─" * (w - 1), curses.A_DIM)
        
        # Table Headers
        headers = f"  #   {'Tool Name':<25} {'Module':<30}"
        stdscr.addstr(3, 0, headers[:w-1], curses.A_BOLD)
        stdscr.addstr(4, 0, "  " + "─" * (w - 5), curses.A_DIM)
        
        # List Area
        list_h = h - 7  # Height remaining for list
        visible_items = self.filtered_list[self.scroll_offset : self.scroll_offset + list_h]
        
        for idx, (tool_name, tool_config) in enumerate(visible_items):
            actual_idx = self.scroll_offset + idx
            y = 5 + idx
            
            # Formatting values
            module_str = tool_config.module[:29]
            
            # Truncation limits
            name_disp = tool_name[:24]
            module_disp = module_str[:28]
            
            indicator = ">" if actual_idx == self.selected_idx else " "
            row_text = f"{indicator}{actual_idx+1:<3} {name_disp:<25} {module_disp:<30}"
            
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
            color = self.colors["error"] if self.status_is_error else self.colors["success"]
            stdscr.addstr(h - 2, 2, f" {self.status_message} "[:w-4], color | curses.A_BOLD)
        
        # Key bindings bar
        keys_bar = " ↑↓ Navigate │ ↵ Edit │ N New │ C Clone │ D Delete │ S Save │ T Toggle Test │ Q Quit │ / Filter"
        stdscr.addstr(h - 1, 0, keys_bar[:w-1], curses.color_pair(2))
        
        try:
            stdscr.refresh()
        except:
            pass
    
    def draw_too_small(self, stdscr, h, w):
        """Draw message when terminal is too small."""
        try:
            msg = "Terminal too small. Need at least 60x10."
            stdscr.addstr(h // 2, max(0, (w - len(msg)) // 2), msg)
        except:
            pass
    
    def handle_search(self, stdscr):
        """Handle search/filter input."""
        h, w = stdscr.getmaxyx()
        stdscr.move(h - 1, 0)
        stdscr.clrtoeol()
        stdscr.addstr(h - 1, 0, "Filter: ", curses.color_pair(3))
        
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
        
        curses.curs_set(0)  # Hide cursor
        self.filter_text = current_filter
        self.apply_filter()
        self.set_status("Filter updated")
    
    def edit_tool(self, stdscr, tool_name: str, tool_config: ToolConfig):
        """Launch tool_editor to edit the selected tool."""
        # Import and run tool_editor
        try:
            from .tool_editor import ToolEditorTUI, ToolDefinition, ParamType
            
            # Convert ToolConfig to ToolDefinition for the editor
            tool_def = ToolDefinition(
                name=tool_name,
                description=tool_config.description,
                module=tool_config.module,
                function=tool_config.function
            )
            
            # Convert parameters
            for param_name, param_data in tool_config.parameters.items():
                param_type_str = param_data.get("type", "string")
                try:
                    param_type = ParamType(param_type_str.upper())
                except ValueError:
                    param_type = ParamType.STRING
                
                from .tool_editor import ParameterDefinition
                param_def = ParameterDefinition(
                    name=param_name,
                    param_type=param_type,
                    description=param_data.get("description", ""),
                    optional=param_data.get("optional", False)
                )
                tool_def.parameters.append(param_def)
            
            # Create and run editor
            editor = ToolEditorTUI()
            editor.tool = tool_def
            
            # Save in-memory config (including clones) to disk before editing
            # This ensures clones are persisted before the editor modifies the file
            if self.has_changes:
                try:
                    self.save_config_to_file(stdscr)
                except Exception as e:
                    self.set_status(f"Warning: Could not save before editing: {str(e)}")
            
            # Set test mode paths
            editor.test_mode = self.test_mode
            editor.toml_save_path = self.get_actual_config_path()
            editor.python_save_dir = self.get_actual_python_dir()
            editor.skip_toml_save = True  # tool_config_tui handles TOML saving
            
            # Run the editor
            curses.endwin()  # Clean up current curses state
            try:
                # Run editor in a fresh curses session
                curses.wrapper(lambda s: editor.run(s))
            finally:
                # Reinitialize curses for our TUI
                stdscr.clear()
                self.init_colors(stdscr)
                stdscr.keypad(True)
                curses.curs_set(0)
            
            # Reload config to get any changes made by the editor
            self.load_config()
            self.has_changes = False
            
            self.set_status(f"Edited tool '{tool_name}'")
            
        except Exception as e:
            self.set_status(f"Error editing tool: {str(e)}", is_error=True)
    
    def create_new_tool(self, stdscr):
        """Create a new tool using the tool editor."""
        try:
            from .tool_editor import ToolEditorTUI, ToolDefinition
            
            # Create empty tool definition
            tool_def = ToolDefinition(
                name="new_tool",
                description="",
                module="chatybot.tools.custom",
                function="new_function"
            )
            
            # Save in-memory config before creating new tool
            if self.has_changes:
                try:
                    self.save_config_to_file(stdscr)
                except Exception as e:
                    self.set_status(f"Warning: Could not save before creating: {str(e)}")
            
            # Create and run editor
            editor = ToolEditorTUI()
            editor.tool = tool_def
            editor.test_mode = self.test_mode
            editor.toml_save_path = self.get_actual_config_path()
            editor.python_save_dir = self.get_actual_python_dir()
            editor.skip_toml_save = True  # tool_config_tui handles TOML saving
            
            curses.endwin()
            try:
                curses.wrapper(lambda s: editor.run(s))
            finally:
                stdscr.clear()
                self.init_colors(stdscr)
                stdscr.keypad(True)
                curses.curs_set(0)
            
            # Reload config to get the new tool
            self.load_config()
            self.has_changes = False
            self.set_status("Created new tool")
            
        except Exception as e:
            self.set_status(f"Error creating tool: {str(e)}", is_error=True)
    
    def clone_tool_dialog(self, stdscr, source_name: str, source_tool: ToolConfig):
        """Show dialog to clone a tool."""
        h, w = stdscr.getmaxyx()
        win_h, win_w = 12, 50
        win_y = (h - win_h) // 2
        win_x = (w - win_w) // 2
        
        win = curses.newwin(win_h, win_w, win_y, win_x)
        win.keypad(True)
        self.draw_dialog_border(win, f"Clone Tool: {source_name}")
        
        win.addstr(2, 4, f"Source tool: {source_name}")
        win.addstr(3, 4, f"Module: {source_tool.module[:30]}")
        win.addstr(4, 4, f"Function: {source_tool.function[:30]}")
        win.addstr(6, 4, "New Tool Name:")
        
        new_name = f"{source_name}_copy"
        
        # Setup form field
        field_y, field_x, field_width = 8, 4, 40
        
        while True:
            win.erase()
            self.draw_dialog_border(win, f"Clone Tool: {source_name}")
            
            win.addstr(2, 4, f"Source tool: {source_name}")
            win.addstr(3, 4, f"Module: {source_tool.module[:30]}")
            win.addstr(4, 4, f"Function: {source_tool.function[:30]}")
            win.addstr(6, 4, "New Tool Name:")
            
            # Draw input field
            win.addstr(field_y, field_x, "[" + " " * (field_width - 2) + "]")
            win.addstr(field_y, field_x + 1, new_name[:field_width-2], curses.color_pair(1))
            
            # Draw buttons
            options = ["[ Clone ]", "[ Cancel ]"]
            for idx, opt in enumerate(options):
                opt_x = 10 + (idx * 20)
                win.addstr(10, opt_x, opt)
            
            win.refresh()
            
            ch = win.getch()
            if ch in (10, 13):  # Enter - Clone
                if self.execute_clone(stdscr, source_name, source_tool, new_name):
                    break
            elif ch == 27:  # Escape - Cancel
                break
            elif ch in (8, 127, curses.KEY_BACKSPACE):
                new_name = new_name[:-1]
            elif 32 <= ch <= 126:
                new_name += chr(ch)
        
        try:
            win.clear()
            win.refresh()
        except:
            pass
    
    def execute_clone(self, stdscr, source_name: str, source_tool: ToolConfig, new_name: str) -> bool:
        """Execute the cloning and insert into config. Return True on success."""
        if not new_name or new_name.strip() == "":
            self.set_status("Error: New tool name cannot be empty!", is_error=True)
            return False
        
        new_name = new_name.strip()
        if self.config.has_tool(new_name):
            self.set_status(f"Error: Tool '{new_name}' already exists! Choose a different name.", is_error=True)
            return False
        
        # Clone the tool
        try:
            cloned_tool = ToolConfig(
                name=new_name,
                enabled=source_tool.enabled,
                description=source_tool.description,
                module=source_tool.module,
                function=source_tool.function,
                parameters=dict(source_tool.parameters)  # Deep copy
            )
            self.config.tools[new_name] = cloned_tool
            self.has_changes = True
            self.sync_tools_list()
            self.set_status(f"Cloned '{source_name}' to '{new_name}'")
            return True
        except Exception as e:
            self.set_status(f"Error cloning tool: {str(e)}", is_error=True)
            return False
    
    def delete_tool_dialog(self, stdscr, tool_name: str, tool_config: ToolConfig):
        """Show confirmation dialog for deleting a tool."""
        h, w = stdscr.getmaxyx()
        win_h, win_w = 12, 48
        win_y = (h - win_h) // 2
        win_x = (w - win_w) // 2
        
        win = curses.newwin(win_h, win_w, win_y, win_x)
        win.keypad(True)
        self.draw_dialog_border(win, "Delete Tool?")
        
        win.addstr(2, 4, "Are you sure you want to delete:")
        win.addstr(4, 6, f"Name: {tool_name}", curses.color_pair(1))
        win.addstr(5, 6, f"Description: {tool_config.description[:30]}", curses.color_pair(1))
        win.addstr(6, 6, f"Module: {tool_config.module[:30]}", curses.color_pair(1))
        win.addstr(7, 6, f"Function: {tool_config.function[:30]}", curses.color_pair(1))
        
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
                    del self.config.tools[tool_name]
                    self.has_changes = True
                    self.sync_tools_list()
                    self.set_status(f"Deleted tool '{tool_name}'")
                    break
                else:
                    break
            elif ch == 27:
                break
        
        try:
            win.clear()
            win.refresh()
        except:
            pass
    
    def draw_dialog_border(self, win, title: str):
        """Draw a bordered dialog window."""
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
        try:
            self.draw_dialog_border(win, "Save Configuration?")
            
            win.addstr(2, 4, "You have unsaved changes.")
            win.addstr(4, 4, f"Save to: {self.get_actual_config_path()}")
            
            options = ["[ Save ]", "[ Discard ]", "[ Cancel ]"]
            sel = 0
            
            while True:
                # Render options
                for idx, opt in enumerate(options):
                    opt_x = 4 + (idx * 16)
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
                    elif sel == 1:  # Discard
                        return True
                    else:  # Cancel
                        return False
                elif ch == 27:  # Escape
                    return False
        finally:
            try:
                win.clear()
                win.refresh()
            except:
                pass
    
    def save_config_as_dialog(self, stdscr) -> bool:
        """Show dialog to save config as a different file."""
        h, w = stdscr.getmaxyx()
        win_h, win_w = 8, 48
        win_y = (h - win_h) // 2
        win_x = (w - win_w) // 2
        
        win = curses.newwin(win_h, win_w, win_y, win_x)
        win.keypad(True)
        self.draw_dialog_border(win, "Save Configuration As...")
        
        win.addstr(2, 4, "Path:")
        new_path = self.edit_text_input(win, 3, 4, win_w - 8, self.get_actual_config_path(), "Path")
        
        if new_path and new_path != self.get_actual_config_path():
            # Create a temporary config object with new path
            temp_config = self.config
            temp_config.config_path = new_path
            temp_config.resolved_path = os.path.expanduser(new_path)
            try:
                temp_config.save()
                self.config_path = new_path
                self.set_status(f"Saved configuration to '{new_path}'")
                return True
            except Exception as e:
                self.set_status(f"Error saving config: {str(e)}", is_error=True)
        return False
    
    def save_menu_dialog(self, stdscr):
        """Show save menu dialog."""
        h, w = stdscr.getmaxyx()
        win_h, win_w = 8, 48
        win_y = (h - win_h) // 2
        win_x = (w - win_w) // 2
        
        win = curses.newwin(win_h, win_w, win_y, win_x)
        win.keypad(True)
        self.draw_dialog_border(win, "Save Configuration")
        
        # Display the file to overwrite, truncated if too long
        display_path = self.get_actual_config_path()
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
        """Save current configuration to file."""
        # Check for duplicate tool names before saving
        if not self.config.validate_no_duplicates():
            # Find the duplicate
            seen = set()
            for tool_name in self.config.tools:
                if tool_name in seen:
                    self.set_status(f"Error: Duplicate tool '{tool_name}' found! Cannot save.", is_error=True)
                    return
                seen.add(tool_name)
        
        try:
            self.config.save(self.get_actual_config_path())
            self.has_changes = False
            self.set_status(f"Saved configuration to '{self.get_actual_config_path()}'")
        except Exception as e:
            self.set_status(f"Error saving config: {str(e)}", is_error=True)
    
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


def main(stdscr=None):
    """Entry point for the tool config TUI."""
    if curses is None:
        print(
            "Error: 'curses' module is unavailable. "
            "On Windows, please install windows-curses ('pip install windows-curses').",
            file=sys.stderr
        )
        return 1

    # Determine if we're in test mode (check for test files)
    test_mode = os.path.exists("test_config") or os.path.exists("tools_config_test.toml")
    
    tui = ToolConfigTUI(test_mode=test_mode)
    
    if stdscr:
        tui.run(stdscr)
    else:
        curses.wrapper(tui.run)


if __name__ == "__main__":
    main()
