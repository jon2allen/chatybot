# src/chatybot/tools/tool_editor.py
"""
Split-panel pycurses TUI for creating ChatyBot tools.
Enforces existing JSON tool call format and generates TOML config + Python stub.
User writes the function logic, not the boilerplate.

Usage:
    python3 -m chatybot.tools.tool_editor
    or
    ./bin/tool_editor
"""

import os
import curses
import datetime
import shutil
from dataclasses import dataclass, field
from typing import List, Optional
from enum import Enum


class ParamType(Enum):
    """Supported parameter types matching existing tool definitions."""
    STRING = "string"
    NUMBER = "number"
    BOOLEAN = "boolean"


@dataclass
class ParameterDefinition:
    """Definition of a tool parameter."""
    name: str
    param_type: ParamType
    description: str = ""
    optional: bool = False


@dataclass
class ToolDefinition:
    """Complete tool definition for generation."""
    name: str = ""
    description: str = ""
    module: str = "chatybot.tools.custom"
    function: str = ""
    parameters: List[ParameterDefinition] = field(default_factory=list)
    code_stub: str = ""

    def get_function_signature(self) -> str:
        """Generate Python function signature from parameters with proper type hints."""
        type_map = {
            ParamType.STRING: "str",
            ParamType.NUMBER: "float",
            ParamType.BOOLEAN: "bool"
        }
        
        final_params = []
        for p in self.parameters:
            type_hint = type_map[p.param_type]
            
            if p.optional:
                default = "None"
                if p.param_type == ParamType.BOOLEAN:
                    default = "False"
                elif p.param_type == ParamType.NUMBER:
                    default = "0"
                final_params.append(f"{p.name}: {type_hint} = {default}")
            else:
                final_params.append(f"{p.name}: {type_hint}")
        
        return f"{self.function}({', '.join(final_params)})"

    def get_json_example(self) -> str:
        """Generate example JSON tool call matching existing format."""
        import json
        args = {}
        for p in self.parameters:
            if p.param_type == ParamType.STRING:
                args[p.name] = "value"
            elif p.param_type == ParamType.NUMBER:
                args[p.name] = 0
            elif p.param_type == ParamType.BOOLEAN:
                args[p.name] = False
        
        return json.dumps({"tool": self.name, "arguments": args}, indent=2)

    def generate_toml(self) -> str:
        """Generate TOML configuration matching existing tools_config.toml format."""
        lines = []
        lines.append(f"[tools.{self.name}]")
        lines.append("enabled = true")
        lines.append(f'description = """{self.description}"""')
        lines.append(f'module = "{self.module}"')
        lines.append(f'function = "{self.function}"')
        lines.append("")
        
        for p in self.parameters:
            lines.append(f"[tools.{self.name}.parameters.{p.name}]")
            lines.append(f'type = "{p.param_type.value}"')
            lines.append(f'description = "{p.description}"')
            lines.append(f"optional = {str(p.optional).lower()}")
            lines.append("")
        
        return "\n".join(lines)

    def generate_python_stub(self) -> str:
        """Generate Python function stub with proper imports and structure."""
        type_map = {
            ParamType.STRING: "str",
            ParamType.NUMBER: "float",
            ParamType.BOOLEAN: "bool"
        }
        
        param_docs = []
        for p in self.parameters:
            python_type = type_map[p.param_type]
            optional_str = " (optional)" if p.optional else ""
            param_docs.append(f"        {p.name} ({python_type}{optional_str}): {p.description}")
        
        params_available = ", ".join(p.name for p in self.parameters) if self.parameters else "None"
        
        return f'''import json
from typing import Any, Optional


def {self.get_function_signature()} -> Any:
    """{self.description}

    Args:
{chr(10).join(param_docs)}

    Returns:
        Any: Result that will be JSON-serialized and returned to the LLM
    """
    # TODO: Implement your tool logic here
    # The following variables are available:
    # {params_available}
    
    # Example: return {{'result': 'success', 'data': processed_data}}
    
    result = "Implement me!"
    return result
'''


class ToolEditorTUI:
    """Split-panel TUI for tool creation with live preview."""

    def __init__(self):
        self.tool = ToolDefinition()
        self.focus_field: Optional[str] = None
        self.focus_param_idx: Optional[int] = None
        self.focus_panel: str = "form"
        self.focus_action: Optional[str] = None  # "add" or "remove" for parameter buttons
        self.status_message: str = "Enter tool details"
        self.status_error: bool = False
        
        # Field definitions for the form
        self.form_fields = [
            ("name", "Tool Name:", 0),
            ("description", "Description:", 1),
            ("module", "Module:", 2),
            ("function", "Function:", 3),
        ]
        
        self.colors = {}
        self.dim_attr = 0
        
        # Parameter editing state
        self.new_param_name: str = ""
        self.new_param_type: ParamType = ParamType.STRING
        self.new_param_desc: str = ""
        self.new_param_optional: bool = False
        
        # Test mode and custom save paths
        self.test_mode: bool = False
        self.toml_save_path: Optional[str] = None
        self.python_save_dir: Optional[str] = None
        self.skip_toml_save: bool = False  # When True, don't save TOML (managed by caller)

    def init_colors(self, stdscr):
        """Initialize curses color pairs."""
        try:
            curses.start_color()
            curses.use_default_colors()
        except:
            pass
        
        try:
            curses.init_pair(1, curses.COLOR_CYAN, -1)
            curses.init_pair(2, curses.COLOR_BLACK, curses.COLOR_CYAN)
            curses.init_pair(3, curses.COLOR_YELLOW, -1)
            curses.init_pair(4, curses.COLOR_RED, -1)
            curses.init_pair(5, curses.COLOR_GREEN, -1)
        except:
            pass
        
        self.dim_attr = curses.A_DIM if hasattr(curses, 'A_DIM') else 0
        
        self.colors = {
            "header": curses.color_pair(1) if hasattr(curses, 'color_pair') else 0,
            "value": curses.color_pair(1) if hasattr(curses, 'color_pair') else 0,
            "selected": curses.color_pair(2) if hasattr(curses, 'color_pair') else 0,
            "warning": curses.color_pair(3) if hasattr(curses, 'color_pair') else 0,
            "error": curses.color_pair(4) if hasattr(curses, 'color_pair') else 0,
            "success": curses.color_pair(5) if hasattr(curses, 'color_pair') else 0,
        }

    def run(self, stdscr):
        """Main entry point for the TUI."""
        self.init_colors(stdscr)
        # MUST enable keypad for arrow keys to work
        stdscr.keypad(True)
        try:
            curses.curs_set(0)
        except:
            pass
        
        while True:
            self.draw(stdscr)
            try:
                ch = stdscr.getch()
            except:
                break
            if self.handle_input(stdscr, ch) is False:
                break

    def draw(self, stdscr):
        """Draw the complete split-panel interface."""
        try:
            stdscr.erase()
        except:
            stdscr.clear()
            return
        
        try:
            h, w = stdscr.getmaxyx()
        except:
            return
        
        if h < 10 or w < 60:
            self.draw_too_small(stdscr, h, w)
            return
        
        # Split point - 50% of width
        split_x = w // 2
        
        # Draw header
        self.draw_header(stdscr, w)
        
        # Draw form panel (left)
        self.draw_form_panel(stdscr, 0, 2, h - 4, split_x - 1)
        
        # Draw divider
        try:
            for y in range(2, h - 2):
                stdscr.addch(y, split_x, ord('|'))
        except:
            pass
        
        # Draw preview panel (right)
        self.draw_preview_panel(stdscr, split_x + 1, 2, h - 4, w - split_x - 2)
        
        # Draw status bar
        self.draw_status_bar(stdscr, w)
        
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

    def draw_header(self, stdscr, w):
        """Draw the header bar."""
        title = " TOOL EDITOR "
        try:
            stdscr.addstr(0, 0, title)
        except:
            pass
        try:
            stdscr.addstr(1, 0, "-" * w)
        except:
            pass

    def draw_status_bar(self, stdscr, w):
        """Draw the status bar at the bottom."""
        try:
            h = stdscr.getmaxyx()[0]
        except:
            return
        status_y = h - 1
        
        try:
            stdscr.addstr(status_y - 1, 0, "-" * w)
        except:
            pass
        
        color = self.colors["error"] if self.status_error else self.colors["success"]
        status_text = f" {self.status_message} "
        try:
            stdscr.addstr(status_y, 0, status_text[:w-1], color)
        except:
            try:
                stdscr.addstr(status_y, 0, status_text[:w-1])
            except:
                pass
        
        hints = "TAB=Switch | Arrows=Nav | ENTER=Select | + Add | - Remove | ESC=Menu | q=Quit"
        hint_x = w - len(hints)
        try:
            stdscr.addstr(status_y, max(0, hint_x), hints, self.dim_attr)
        except:
            pass

    def draw_form_panel(self, stdscr, x, y, height, width):
        """Draw the form panel on the left."""
        # Panel title with * for active panel
        if self.focus_panel == "form":
            try:
                stdscr.addstr(y, x + 2, "*FORM", curses.A_BOLD)
            except:
                pass
        else:
            try:
                stdscr.addstr(y, x + 2, " FORM")
            except:
                pass
        
        content_y = y + 2
        
        for field_key, label, field_idx in self.form_fields:
            field_y = content_y + field_idx * 2
            if field_y >= y + height - 3:
                break
            
            is_focused = self.focus_field == field_key and self.focus_panel == "form"
            
            # Draw label with focus indicator
            if is_focused:
                try:
                    stdscr.addstr(field_y, x + 2, "> " + label, curses.A_BOLD)
                except:
                    pass
            else:
                try:
                    stdscr.addstr(field_y, x + 2, "  " + label)
                except:
                    pass
            
            value = getattr(self.tool, field_key, "")
            
            input_x = x + 2 + len(label) + 3  # +3 for prefix + space
            input_width = max(10, width - len(label) - 8)
            
            # Draw input box
            try:
                stdscr.addstr(field_y, input_x - 1, "[")
                stdscr.addstr(field_y, input_x + input_width, "]")
            except:
                pass
            
            # Draw value
            disp_value = value[:input_width]
            try:
                if is_focused:
                    stdscr.addstr(field_y, input_x, disp_value, curses.A_BOLD)
                else:
                    stdscr.addstr(field_y, input_x, disp_value)
            except:
                pass
            
            # Fill empty space
            try:
                if len(disp_value) < input_width:
                    stdscr.addstr(field_y, input_x + len(disp_value), " " * (input_width - len(disp_value)))
            except:
                pass
        
        param_y = content_y + len(self.form_fields) * 2 + 1
        if param_y < y + height - 5:
            try:
                stdscr.addstr(param_y, x + 2, " Parameters:", curses.A_BOLD)
            except:
                pass
            param_y += 1
            
            # Show parameter count
            try:
                stdscr.addstr(param_y, x + 2, f"  ({len(self.tool.parameters)} defined)")
            except:
                pass
            param_y += 1
            
            for idx, param in enumerate(self.tool.parameters):
                if param_y >= y + height - 6:
                    break
                
                is_focused = (self.focus_param_idx == idx and 
                           self.focus_field == "parameters" and 
                           self.focus_panel == "form")
                
                type_str = param.param_type.value
                opt_str = " (optional)" if param.optional else " (required)"
                param_display = f"{param.name:15s}  Type:{type_str:8s}{opt_str}"
                
                if is_focused:
                    try:
                        stdscr.addstr(param_y, x + 2, "=>", curses.A_BOLD)
                        stdscr.addstr(param_y, x + 5, param_display, curses.A_BOLD)
                    except:
                        pass
                else:
                    try:
                        stdscr.addstr(param_y, x + 2, "  ")
                        stdscr.addstr(param_y, x + 5, param_display)
                    except:
                        pass
                
                param_y += 1
            
            if param_y < y + height - 4:
                # Show instructions
                try:
                    stdscr.addstr(param_y, x + 2, " ")
                except:
                    pass
                param_y += 1
                
                # Draw [+Add] button
                if param_y < y + height - 3:
                    if self.focus_action == "add":
                        try:
                            stdscr.addstr(param_y, x + 2, "> [+Add]", curses.A_BOLD)
                            stdscr.addstr(param_y, x + 10, " Add new parameter")
                        except:
                            pass
                    else:
                        try:
                            stdscr.addstr(param_y, x + 2, "  [+Add]")
                            stdscr.addstr(param_y, x + 10, " Add new parameter")
                        except:
                            pass
                    param_y += 1
                
                # Draw [-Rem] button
                if self.tool.parameters and param_y < y + height - 3:
                    if self.focus_action == "remove":
                        try:
                            stdscr.addstr(param_y, x + 2, "> [-Rem]", curses.A_BOLD)
                            stdscr.addstr(param_y, x + 10, " Remove selected")
                        except:
                            pass
                    else:
                        try:
                            stdscr.addstr(param_y, x + 2, "  [-Rem]")
                            stdscr.addstr(param_y, x + 10, " Remove selected")
                        except:
                            pass
                    param_y += 1
                
                # Help text
                if param_y < y + height - 1:
                    try:
                        stdscr.addstr(param_y, x + 2, " ")
                    except:
                        pass
                    param_y += 1
        
        # Status line at bottom of panel - shows what ENTER will do
        if self.focus_panel == "form" and height > 0:
            try:
                status_x = x + 2
                if self.focus_action == "add":
                    stdscr.addstr(y + height - 1, status_x, "ENTER = Add new parameter", curses.A_BOLD)
                elif self.focus_action == "remove":
                    stdscr.addstr(y + height - 1, status_x, "ENTER = Remove selected parameter", curses.A_BOLD)
                elif self.focus_field and self.focus_field != "parameters":
                    stdscr.addstr(y + height - 1, status_x, f"ENTER = Edit {self.focus_field}", curses.A_BOLD)
                elif self.focus_field == "parameters" and self.focus_param_idx is not None:
                    stdscr.addstr(y + height - 1, status_x, f"ENTER = Edit parameter: {self.tool.parameters[self.focus_param_idx].name}", curses.A_BOLD)
                else:
                    stdscr.addstr(y + height - 1, status_x, "ENTER = Edit selected field", curses.A_BOLD)
            except:
                pass

    def draw_preview_panel(self, stdscr, x, y, height, width):
        """Draw the preview panel on the right."""
        # Panel title with * for active panel
        if self.focus_panel == "preview":
            try:
                stdscr.addstr(y, x + 2, "*LIVE PREVIEW", curses.A_BOLD)
            except:
                pass
        else:
            try:
                stdscr.addstr(y, x + 2, " LIVE PREVIEW")
            except:
                pass
        
        tabs = ["TOML Config", "JSON Example"]
        tab_width = max(1, width // len(tabs))
        
        for idx, tab in enumerate(tabs):
            tab_x = x + 2 + idx * tab_width
            try:
                stdscr.addstr(y + 1, tab_x, f"[{tab}]")
            except:
                pass
        
        content_y = y + 3
        content_height = max(1, height - 4)
        
        # Show TOML preview
        toml_preview = self.tool.generate_toml()
        toml_lines = toml_preview.split('\n')
        
        for line_idx, line in enumerate(toml_lines[:content_height]):
            display_y = content_y + line_idx
            if display_y >= y + height - 1:
                break
            
            color = 0
            if line.startswith('['):
                color = self.colors["header"]
            elif '=' in line:
                color = self.colors["value"]
            
            try:
                stdscr.addstr(display_y, x + 2, line[:max(1, width-4)], color)
            except:
                try:
                    stdscr.addstr(display_y, x + 2, line[:max(1, width-4)])
                except:
                    pass
        
        # Show JSON example at bottom
        if content_y + len(toml_lines) + 2 < y + height - 1:
            json_y = content_y + len(toml_lines) + 1
            json_preview = self.tool.get_json_example()
            try:
                stdscr.addstr(json_y, x + 2, "JSON Tool Call:")
            except:
                pass
            json_y += 1
            for line in json_preview.split('\n'):
                if json_y >= y + height - 1:
                    break
                try:
                    stdscr.addstr(json_y, x + 2, line[:max(1, width-4)], self.colors["value"])
                except:
                    try:
                        stdscr.addstr(json_y, x + 2, line[:max(1, width-4)])
                    except:
                        pass
                json_y += 1

    def handle_input(self, stdscr, ch):
        """Handle keyboard input. Returns False to exit."""
        # Quit
        if ch == ord('q') or ch == ord('Q'):
            return False
        
        # Escape - open menu
        elif ch == 27:
            self.show_main_menu(stdscr)
            return True
        
        # Tab - switch between form and preview panels
        elif ch == 9:
            self.focus_panel = "preview" if self.focus_panel == "form" else "form"
            self.focus_field = None
            self.focus_param_idx = None
            self.focus_action = None
            self.status_message = "Use TAB to switch panels, arrows to navigate"
            self.status_error = False
        
        # Arrow keys for navigation (these require keypad=True)
        elif ch == curses.KEY_UP:
            self.handle_up()
        elif ch == curses.KEY_DOWN:
            self.handle_down()
        
        # Enter - edit/save
        elif ch == 10 or ch == 13:
            self.handle_enter(stdscr)
        
        # Backspace/Delete
        elif ch == curses.KEY_BACKSPACE or ch in (8, 127):
            self.handle_backspace()
        
        # Plus key - add parameter
        elif ch == ord('+') or ch == 43:
            if self.focus_field == "parameters" or self.focus_action == "add":
                self.add_parameter(stdscr)
        
        # Minus key - remove parameter
        elif ch == ord('-') or ch == 45:
            if self.focus_param_idx is not None or self.focus_action == "remove":
                self.remove_parameter()
        
        return True

    def handle_up(self):
        """Handle up arrow key."""
        if self.focus_panel == "form":
            if self.focus_action:
                # Currently focused on add/remove button
                if self.focus_action == "remove":
                    self.focus_action = "add"
                elif self.focus_action == "add":
                    if self.tool.parameters:
                        self.focus_action = None
                        self.focus_field = "parameters"
                        self.focus_param_idx = len(self.tool.parameters) - 1
                    else:
                        self.focus_action = None
                        self.focus_field = self.form_fields[-1][0]
            elif self.focus_field == "parameters" and self.focus_param_idx is not None:
                # Move up through parameters
                if self.focus_param_idx > 0:
                    self.focus_param_idx -= 1
                else:
                    # At first parameter, move to last form field
                    self.focus_field = self.form_fields[-1][0]
                    self.focus_param_idx = None
                    self.focus_action = None
            elif self.focus_field:
                current_idx = None
                for idx, (key, _, _) in enumerate(self.form_fields):
                    if key == self.focus_field:
                        current_idx = idx
                        break
                
                if current_idx is not None and current_idx > 0:
                    self.focus_field = self.form_fields[current_idx - 1][0]
                    self.focus_param_idx = None
                    self.focus_action = None
                elif current_idx == 0:
                    self.focus_field = self.form_fields[-1][0]
                    self.focus_param_idx = None
                    self.focus_action = None
            else:
                self.focus_field = self.form_fields[0][0]
                self.focus_action = None

    def handle_down(self):
        """Handle down arrow key."""
        if self.focus_panel == "form":
            if self.focus_action:
                # Currently focused on add/remove button
                if self.focus_action == "add":
                    if self.tool.parameters:
                        self.focus_action = None
                        self.focus_field = "parameters"
                        self.focus_param_idx = 0
                    else:
                        pass  # Stay on add
                elif self.focus_action == "remove":
                    if self.tool.parameters:
                        self.focus_action = None
                        self.focus_field = "parameters"
                        self.focus_param_idx = 0
                    else:
                        self.focus_action = "add"
            elif self.focus_field:
                current_idx = None
                for idx, (key, _, _) in enumerate(self.form_fields):
                    if key == self.focus_field:
                        current_idx = idx
                        break
                
                if current_idx is not None and current_idx < len(self.form_fields) - 1:
                    self.focus_field = self.form_fields[current_idx + 1][0]
                    self.focus_param_idx = None
                    self.focus_action = None
                else:
                    # At last form field, move to parameters or add button
                    if self.tool.parameters:
                        self.focus_field = "parameters"
                        self.focus_param_idx = 0
                        self.focus_action = None
                    else:
                        self.focus_field = None
                        self.focus_param_idx = None
                        self.focus_action = "add"
            else:
                self.focus_field = self.form_fields[0][0]
                self.focus_action = None

    def handle_enter(self, stdscr):
        """Handle Enter key - edit focused field or execute action."""
        if self.focus_panel == "form":
            if self.focus_action == "add":
                self.add_parameter(stdscr)
            elif self.focus_action == "remove":
                self.remove_parameter()
            elif self.focus_field and self.focus_field != "parameters":
                self.edit_field(stdscr, self.focus_field)
            elif self.focus_field == "parameters" and self.focus_param_idx is not None:
                self.edit_parameter(stdscr, self.focus_param_idx)
        elif self.focus_panel == "preview":
            self.save_files(stdscr)

    def edit_field(self, stdscr, field_key):
        """Edit a form field with a text input dialog."""
        current_value = getattr(self.tool, field_key, "")
        new_value = self.show_text_input_dialog(
            stdscr, 
            f"Edit {field_key.replace('_', ' ').title()}", 
            current_value
        )
        if new_value is not None:
            setattr(self.tool, field_key, new_value)
            self.status_message = f"Updated {field_key}"
            self.status_error = False

    def edit_parameter(self, stdscr, param_idx):
        """Edit an existing parameter."""
        param = self.tool.parameters[param_idx]
        self.new_param_name = param.name
        self.new_param_type = param.param_type
        self.new_param_desc = param.description
        self.new_param_optional = param.optional
        self.show_parameter_editor(stdscr, is_edit=True, param_idx=param_idx)

    def add_parameter(self, stdscr):
        """Add a new parameter."""
        self.new_param_name = ""
        self.new_param_type = ParamType.STRING
        self.new_param_desc = ""
        self.new_param_optional = False
        self.show_parameter_editor(stdscr, is_edit=False)

    def show_parameter_editor(self, stdscr, is_edit=False, param_idx=None):
        """Show dialog for editing/adding a parameter."""
        try:
            h, w = stdscr.getmaxyx()
        except:
            return
        dialog_h, dialog_w = 14, 50
        dialog_y = max(0, (h - dialog_h) // 2)
        dialog_x = max(0, (w - dialog_w) // 2)
        
        win = curses.newwin(dialog_h, dialog_w, dialog_y, dialog_x)
        win.keypad(True)  # Must enable for arrow keys
        
        title = "Edit Parameter" if is_edit else "Add Parameter"
        focus = 0
        
        while True:
            try:
                win.erase()
            except:
                win.clear()
            self.draw_dialog_border(win, title)
            
            try:
                win.addstr(2, 4, f"Name: [{self.new_param_name}]")
                type_options = ["string", "number", "boolean"]
                current_type_idx = type_options.index(self.new_param_type.value)
                win.addstr(4, 4, f"Type: <{type_options[current_type_idx]}>")
                win.addstr(6, 4, f"Description: [{self.new_param_desc}]")
                opt_str = "Yes" if self.new_param_optional else "No"
                win.addstr(8, 4, f"Optional: <{opt_str}>")
                win.addstr(10, 12, "[ Save ]")
                win.addstr(10, 22, "[ Cancel ]")
            except:
                pass
            
            # Draw focus
            if focus == 0:
                try:
                    win.addstr(2, 4, f"> Name: [{self.new_param_name}]", self.colors["selected"])
                except:
                    pass
            elif focus == 1:
                try:
                    win.addstr(4, 4, f"> Type: <{type_options[current_type_idx]}>", self.colors["selected"])
                except:
                    pass
            elif focus == 2:
                try:
                    win.addstr(6, 4, f"> Description: [{self.new_param_desc}]", self.colors["selected"])
                except:
                    pass
            elif focus == 3:
                try:
                    win.addstr(8, 4, f"> Optional: <{opt_str}>", self.colors["selected"])
                except:
                    pass
            elif focus == 4:
                try:
                    win.addstr(10, 12, "> [ Save ]", self.colors["selected"])
                except:
                    pass
            elif focus == 5:
                try:
                    win.addstr(10, 22, "> [ Cancel ]", self.colors["selected"])
                except:
                    pass
            
            try:
                win.refresh()
            except:
                pass
            
            try:
                ch = win.getch()
            except:
                break
            
            if ch == 27:
                break
            elif ch == curses.KEY_UP:
                focus = (focus - 1) % 6
            elif ch == curses.KEY_DOWN:
                focus = (focus + 1) % 6
            elif ch == curses.KEY_LEFT:
                if focus == 1:  # Type field - cycle left
                    current_type_idx = (current_type_idx - 1) % len(type_options)
                    self.new_param_type = ParamType(type_options[current_type_idx])
                elif focus == 3:  # Optional field - toggle
                    self.new_param_optional = not self.new_param_optional
            elif ch == curses.KEY_RIGHT:
                if focus == 1:  # Type field - cycle right
                    current_type_idx = (current_type_idx + 1) % len(type_options)
                    self.new_param_type = ParamType(type_options[current_type_idx])
                elif focus == 3:  # Optional field - toggle
                    self.new_param_optional = not self.new_param_optional
            elif ch in (10, 13):
                if focus == 4:
                    if self.new_param_name.strip():
                        param = ParameterDefinition(
                            name=self.new_param_name.strip(),
                            param_type=self.new_param_type,
                            description=self.new_param_desc.strip(),
                            optional=self.new_param_optional
                        )
                        if is_edit and param_idx is not None:
                            self.tool.parameters[param_idx] = param
                        else:
                            self.tool.parameters.append(param)
                        self.status_message = f"Parameter {'updated' if is_edit else 'added'}"
                        self.status_error = False
                        break
                elif focus == 5:
                    break
            elif 32 <= ch <= 126:
                if focus == 0:
                    self.new_param_name += chr(ch)
                elif focus == 2:
                    self.new_param_desc += chr(ch)
            elif ch in (8, 127) or (hasattr(curses, 'KEY_BACKSPACE') and ch == curses.KEY_BACKSPACE):
                if focus == 0:
                    self.new_param_name = self.new_param_name[:-1]
                elif focus == 2:
                    self.new_param_desc = self.new_param_desc[:-1]
        
        try:
            win.clear()
        except:
            pass
        try:
            win.refresh()
        except:
            pass

    def remove_parameter(self):
        """Remove the currently focused parameter."""
        if (self.focus_param_idx is not None and 
            0 <= self.focus_param_idx < len(self.tool.parameters)):
            removed = self.tool.parameters.pop(self.focus_param_idx)
            self.status_message = f"Removed parameter '{removed.name}'"
            self.status_error = False
            if self.focus_param_idx >= len(self.tool.parameters):
                self.focus_param_idx = max(0, len(self.tool.parameters) - 1)

    def handle_backspace(self):
        """Handle backspace for focused field."""
        if self.focus_panel == "form" and self.focus_field and self.focus_field != "parameters":
            current_value = getattr(self.tool, self.focus_field, "")
            setattr(self.tool, self.focus_field, current_value[:-1])

    def show_text_input_dialog(self, stdscr, title, initial_value=""):
        """Show a text input dialog."""
        try:
            h, w = stdscr.getmaxyx()
        except:
            return None
        dialog_h, dialog_w = 8, 60
        dialog_y = max(0, (h - dialog_h) // 2)
        dialog_x = max(0, (w - dialog_w) // 2)
        
        win = curses.newwin(dialog_h, dialog_w, dialog_y, dialog_x)
        win.keypad(True)  # Must enable for arrow keys
        try:
            curses.curs_set(1)
        except:
            pass
        
        value = initial_value
        cursor_pos = len(value)
        
        while True:
            try:
                win.erase()
            except:
                win.clear()
            self.draw_dialog_border(win, title)
            
            try:
                win.addstr(3, 4, "Value: [")
                win.addstr(3, 11, " " * max(0, dialog_w - 16))
                win.addstr(3, max(4, dialog_w - 5), "]")
                win.addstr(3, 12, value[:max(0, dialog_w-18)])
            except:
                pass
            
            try:
                win.move(3, max(12, 12 + min(cursor_pos, len(value))))
            except:
                pass
            
            try:
                win.refresh()
            except:
                pass
            
            try:
                ch = win.getch()
            except:
                break
            
            if ch in (10, 13):
                break
            elif ch == 27:
                value = None
                break
            elif ch in (8, 127, curses.KEY_BACKSPACE):
                if cursor_pos > 0:
                    value = value[:cursor_pos - 1] + value[cursor_pos:]
                    cursor_pos -= 1
            elif ch == curses.KEY_LEFT:
                cursor_pos = max(0, cursor_pos - 1)
            elif ch == curses.KEY_RIGHT:
                cursor_pos = min(len(value), cursor_pos + 1)
            elif 32 <= ch <= 126:
                value = value[:cursor_pos] + chr(ch) + value[cursor_pos:]
                cursor_pos += 1
        
        try:
            curses.curs_set(0)
        except:
            pass
        try:
            win.clear()
        except:
            pass
        try:
            win.refresh()
        except:
            pass
        return value

    def draw_dialog_border(self, win, title):
        """Draw a bordered dialog window."""
        try:
            h, w = win.getmaxyx()
            win.border()
            win.addstr(0, max(0, (w - len(title)) // 2), title)
        except:
            pass

    def show_save_confirmation_popup(self, stdscr, toml_path, py_path, backup_path=None):
        """Show a popup in the middle of the screen with save locations."""
        try:
            h, w = stdscr.getmaxyx()
        except:
            return
        
        # Calculate popup size based on content
        dialog_h, dialog_w = 8, 60
        dialog_y = max(0, (h - dialog_h) // 2)
        dialog_x = max(0, (w - dialog_w) // 2)
        
        win = curses.newwin(dialog_h, dialog_w, dialog_y, dialog_x)
        
        try:
            win.erase()
            self.draw_dialog_border(win, " Files Saved Successfully ")
            
            # Display the save locations
            win.addstr(2, 4, f"TOML: {toml_path}")
            win.addstr(3, 4, f"Python: {py_path}")
            if backup_path:
                win.addstr(4, 4, f"Backup: {backup_path}")
            win.addstr(6, 4, "[ Press any key to continue ]")
            
            win.refresh()
            
            # Wait for any key press
            win.getch()
            
        except Exception:
            pass
        finally:
            try:
                win.clear()
                win.refresh()
            except:
                pass

    def check_tool_exists(self, toml_path: str) -> bool:
        """Check if tool already exists in TOML file."""
        try:
            import tomllib
        except ImportError:
            import tomli as tomllib
        
        try:
            with open(toml_path, 'rb') as f:
                data = tomllib.load(f)
            if 'tools' in data:
                return self.tool.name in data['tools']
        except FileNotFoundError:
            return False
        except Exception:
            return False
        return False
    
    def save_files(self, stdscr):
        """Save TOML config and Python stub to config directory."""
        if self.skip_toml_save:
            # TOML saving is handled by the caller (tool_config_tui)
            # Only save Python file
            self.save_python_file(stdscr)
            return
        
        # Determine TOML path
        if self.toml_save_path and self.test_mode:
            toml_path = self.toml_save_path
        else:
            config_dir = os.path.expanduser("~/.config/chatybot")
            os.makedirs(config_dir, exist_ok=True)
            toml_path = os.path.join(config_dir, "tools_config.toml")
        
        # Check for duplicate tool name
        if self.check_tool_exists(toml_path):
            self.status_message = f"Error: Tool '{self.tool.name}' already exists! Choose a different name."
            self.status_error = True
            return
        
        if not self.tool.name.strip():
            self.status_message = "Error: Tool name is required"
            self.status_error = True
            return
        
        if not self.tool.function.strip():
            self.status_message = "Error: Function name is required"
            self.status_error = True
            return
        
        # Validate tool name
        safe_name = self.tool.name.replace('_', '').replace('.', '')
        if not safe_name.isalnum():
            self.status_message = "Error: Tool name must be alphanumeric with underscores/dots"
            self.status_error = True
            return
        
        # Save TOML to config directory
        toml_content = self.tool.generate_toml()
        config_dir = os.path.dirname(toml_path)
        
        # Create backup (gold copy) before editing
        backup_path = None
        if os.path.exists(toml_path):
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_dir = os.path.dirname(toml_path)
            os.makedirs(backup_dir, exist_ok=True)
            backup_path = os.path.join(backup_dir, f"tools_config.toml.bak.{timestamp}")
            shutil.copy2(toml_path, backup_path)
        
        # Save TOML - append mode for all cases now
        with open(toml_path, "a") as f:
            if f.tell() == 0:
                # File is empty, write header
                f.write("[config]\n")
                f.write("tool_timeout = 60\n\n")
            f.write(f"{toml_content}\n")
        
        # Save Python stub
        self.save_python_file(stdscr)
        
        # Show popup with save locations and backup info
        self.show_save_confirmation_popup(stdscr, toml_path, self.get_python_path(), backup_path)
        
        self.status_message = f"Saved TOML to {toml_path} | Python to {self.get_python_path()}"
        if backup_path:
            self.status_message += f" | Backup: {backup_path}"
        self.status_error = False
    
    def save_python_file(self, stdscr):
        """Save Python stub file."""
        py_content = self.tool.generate_python_stub()
        
        # Use custom Python save directory if set
        if self.python_save_dir and self.test_mode:
            python_dir = self.python_save_dir
        else:
            # Get project root
            project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            # Create custom tools module file
            src_tools_dir = os.path.join(project_root, "src", "chatybot", "tools")
            os.makedirs(src_tools_dir, exist_ok=True)
            python_dir = src_tools_dir
        
        # Save Python file with tool name
        os.makedirs(python_dir, exist_ok=True)
        py_filename = f"{self.tool.name}.py"
        py_path = os.path.join(python_dir, py_filename)
        
        with open(py_path, "w") as f:
            f.write(py_content)
        
        return py_path
    
    def get_python_path(self) -> str:
        """Get the Python file path that will be/was saved."""
        if self.python_save_dir and self.test_mode:
            python_dir = self.python_save_dir
        else:
            project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            src_tools_dir = os.path.join(project_root, "src", "chatybot", "tools")
            python_dir = src_tools_dir
        
        os.makedirs(python_dir, exist_ok=True)
        py_filename = f"{self.tool.name}.py"
        return os.path.join(python_dir, py_filename)

    def show_main_menu(self, stdscr):
        """Show main menu dialog."""
        try:
            h, w = stdscr.getmaxyx()
        except:
            return True
        menu_h, menu_w = 10, 40
        menu_y = max(0, (h - menu_h) // 2)
        menu_x = max(0, (w - menu_w) // 2)
        
        win = curses.newwin(menu_h, menu_w, menu_y, menu_x)
        win.keypad(True)  # Must enable for arrow keys
        
        options = ["Continue", "Save Files", "New Tool", "Exit"]
        selected = 0
        
        while True:
            try:
                win.erase()
            except:
                win.clear()
            self.draw_dialog_border(win, "Menu")
            
            for idx, opt in enumerate(options):
                prefix = "> " if idx == selected else "  "
                try:
                    win.addstr(2 + idx * 2, 4, prefix + opt)
                except:
                    pass
            
            try:
                win.refresh()
            except:
                pass
            
            try:
                ch = win.getch()
            except:
                break
            
            if ch == 27:
                break
            elif ch == curses.KEY_UP:
                selected = (selected - 1) % len(options)
            elif ch == curses.KEY_DOWN:
                selected = (selected + 1) % len(options)
            elif ch in (10, 13):
                if selected == 0:
                    break
                elif selected == 1:
                    self.save_files(stdscr)
                    break
                elif selected == 2:
                    self.tool = ToolDefinition()
                    self.focus_field = None
                    self.focus_param_idx = None
                    self.status_message = "New tool started"
                    self.status_error = False
                    break
                elif selected == 3:
                    return False
        
        try:
            win.clear()
        except:
            pass
        try:
            win.refresh()
        except:
            pass
        return True


def main(stdscr):
    """Entry point for curses wrapper."""
    editor = ToolEditorTUI()
    editor.run(stdscr)


if __name__ == "__main__":
    curses.wrapper(main)
