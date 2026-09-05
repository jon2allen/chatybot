try:
    import curses
except ImportError:
    curses = None
import os
import re
import sys
from typing import Optional, List, Dict, Any

class ProfileEditor:
    def __init__(self, name: str, pm: Any, config_manager: Any):
        self.pm = pm
        self.config_manager = config_manager
        
        # Load models list
        self.models_list = list(config_manager.config.get("models", {}).keys())
        if not self.models_list:
            self.models_list = ["devstral_1", "mistral_1"]
            
        # Parse or initialize profile state
        self.filename = name
        if self.filename and not self.filename.endswith(".chatdsl"):
            self.filename += ".chatdsl"
            
        self.profile_name = ""
        self.description = ""
        self.selected_model = self.models_list[0]
        self.tool_mode = "auto"  # off, auto, on
        self.trace_tps = False
        self.trace_agentic_loop = False
        self.trace_raw_payload = False
        self.trace_rerank = False
        self.trace_tps_perf = False
        self.trace_imagedbg = False
        self.reasoning = False
        self.show_thinking = False
        self.reasoning_effort = "none"  # none, low, medium, high
        self.temperature = "0.7"
        self.max_turns = "25"
        self.auto_truncate = False
        self.truncate_pct = "100"
        self.disabled_tools = []
        
        self.is_new = True
        self.loaded_filepath = None
        
        if name:
            try:
                path = pm._resolve_path(name)
                self.loaded_filepath = path
                self.filename = os.path.basename(path)
                self.is_new = False
                self.load_from_file(path)
            except Exception:
                pass

        # Navigation state
        # Fields list: (field_id, label, type)
        # Type can be: 'text', 'radio', 'checkbox', 'select', 'button'
        self.fields = [
            ("filename", "File name:    ", "text"),
            ("profile_name", "@name:        ", "text"),
            ("description", "@description: ", "text"),
            # Presets
            ("preset_coding", "[ Coding ]", "button"),
            ("preset_general", "[ General ]", "button"),
            ("preset_explorer", "[ Explorer ]", "button"),
            ("preset_blank", "[ Blank ]", "button"),
            # Model
            ("model", "/model:       ", "select"),
            # Tools
            ("tool_off", "Off", "radio_tool"),
            ("tool_auto", "Auto", "radio_tool"),
            ("tool_on", "On", "radio_tool"),
            # Traces
            ("trace_tps", "TPS", "checkbox"),
            ("trace_agentic_loop", "Agentic Loop", "checkbox"),
            ("trace_raw_payload", "Raw Payload", "checkbox"),
            ("trace_rerank", "Rerank", "checkbox"),
            ("trace_tps_perf", "TPS Perf", "checkbox"),
            ("trace_imagedbg", "ImageDbg", "checkbox"),
            # Reasoning
            ("reasoning", "Reasoning", "checkbox"),
            ("show_thinking", "Show Thinking", "checkbox"),
            ("effort_none", "None", "radio_effort"),
            ("effort_low", "Low", "radio_effort"),
            ("effort_medium", "Medium", "radio_effort"),
            ("effort_high", "High", "radio_effort"),
            # Advanced
            ("temperature", "/temp:        ", "text"),
            ("max_turns", "max_turns:    ", "text"),
            # Actions
            ("action_save", "[Save]", "button"),
            ("action_reset", "[Reset]", "button"),
            ("action_cancel", "[Cancel]", "button"),
        ]
        
        self.current_field_idx = 0
        self.status_message = ""
        self.status_is_error = False

    def load_from_file(self, path: str) -> None:
        try:
            meta = self.pm.read_meta(path)
            self.profile_name = meta.name
            self.description = meta.description
        except Exception:
            pass
            
        # Parse commands to populate form
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                parts = line.split()
                cmd = parts[0].lower()
                
                if cmd == "/model" and len(parts) >= 2:
                    self.selected_model = parts[1]
                elif cmd == "/tool" and len(parts) >= 2:
                    sub = parts[1].lower()
                    if sub == "off":
                        self.tool_mode = "off"
                    elif sub == "on":
                        self.tool_mode = "on"
                    elif sub == "auto":
                        if len(parts) >= 3 and parts[2].lower() == "off":
                            self.tool_mode = "off"
                        else:
                            self.tool_mode = "auto"
                    elif sub == "disable" and len(parts) >= 3:
                        self.disabled_tools.append(parts[2])
                    elif sub == "max_turns" and len(parts) >= 3:
                        self.max_turns = parts[2]
                elif cmd == "/reasoning" and len(parts) >= 2:
                    self.reasoning = parts[1].lower() == "on"
                elif cmd == "/thinking" and len(parts) >= 2:
                    self.show_thinking = parts[1].lower() == "on"
                elif cmd == "/effort" and len(parts) >= 2:
                    self.reasoning_effort = parts[1].lower()
                elif cmd == "/temp" and len(parts) >= 2:
                    self.temperature = parts[1]
                elif cmd == "/trace" and len(parts) >= 3:
                    sub = parts[1].lower()
                    state = parts[2].lower() == "on"
                    if sub == "tps":
                        self.trace_tps = state
                    elif sub == "agentic_loop":
                        self.trace_agentic_loop = state
                    elif sub == "rawpayload":
                        self.trace_raw_payload = state
                    elif sub == "rerank":
                        self.trace_rerank = state
                    elif sub == "tpsperf":
                        self.trace_tps_perf = state
                    elif sub == "imagedbg":
                        self.trace_imagedbg = state
                elif cmd == "/auto_truncate" and len(parts) >= 2:
                    sub = parts[1].lower()
                    if sub in ("off", "0", "false"):
                        self.auto_truncate = False
                    elif sub in ("on", "1", "true"):
                        self.auto_truncate = True
                        self.truncate_pct = "100"
                    else:
                        self.auto_truncate = True
                        self.truncate_pct = sub

    def generate_chatdsl(self) -> str:
        lines = []
        if self.profile_name:
            lines.append(f"# @name: {self.profile_name}")
        if self.description:
            lines.append(f"# @description: {self.description}")
        if self.profile_name or self.description:
            lines.append("")
            
        lines.append(f"/model {self.selected_model}")
        
        if self.tool_mode == "auto":
            lines.append("/tool auto on")
            lines.append("/tool on")
        elif self.tool_mode == "on":
            lines.append("/tool auto off")
            lines.append("/tool on")
        else:
            lines.append("/tool off")
            
        for t in self.disabled_tools:
            lines.append(f"/tool disable {t}")
            
        if self.trace_tps:
            lines.append("/trace tps on")
        if self.trace_agentic_loop:
            lines.append("/trace agentic_loop on")
        if self.trace_raw_payload:
            lines.append("/trace rawpayload on")
        if self.trace_rerank:
            lines.append("/trace rerank on")
        if self.trace_tps_perf:
            lines.append("/trace tpsperf on")
        if self.trace_imagedbg:
            lines.append("/trace imagedbg on")
            
        lines.append(f"/reasoning {'on' if self.reasoning else 'off'}")
        lines.append(f"/thinking {'on' if self.show_thinking else 'off'}")
        
        if self.reasoning_effort != "none":
            lines.append(f"/effort {self.reasoning_effort}")
            
        if self.temperature:
            lines.append(f"/temp {self.temperature}")
            
        if self.max_turns:
            lines.append(f"/tool max_turns {self.max_turns}")
            
        if self.auto_truncate:
            if self.truncate_pct and str(self.truncate_pct) != "100":
                lines.append(f"/auto_truncate {self.truncate_pct}")
            else:
                lines.append("/auto_truncate on")
        else:
            lines.append("/auto_truncate off")
            
        return "\n".join(lines) + "\n"

    def apply_preset(self, preset_name: str) -> None:
        self.disabled_tools = []
        if preset_name == "coding":
            self.profile_name = "Development Profile"
            self.description = "Optimized for coding, debugging, and technical assistance"
            self.selected_model = "devstral_1" if "devstral_1" in self.models_list else self.models_list[0]
            self.tool_mode = "auto"
            self.trace_tps = True
            self.trace_agentic_loop = False
            self.trace_raw_payload = False
            self.trace_rerank = False
            self.trace_tps_perf = False
            self.reasoning = True
            self.show_thinking = False
            self.reasoning_effort = "medium"
            self.temperature = "0.7"
            self.max_turns = "75"
        elif preset_name == "general":
            self.profile_name = "General Assistance Profile"
            self.description = "Balanced assistance with restricted tool access"
            self.selected_model = "mistral_1" if "mistral_1" in self.models_list else self.models_list[0]
            self.tool_mode = "off"
            self.trace_tps = False
            self.trace_agentic_loop = False
            self.trace_raw_payload = False
            self.trace_rerank = False
            self.trace_tps_perf = False
            self.reasoning = False
            self.show_thinking = False
            self.reasoning_effort = "none"
            self.temperature = "0.7"
            self.max_turns = "25"
        elif preset_name == "explorer":
            self.profile_name = "Explorer Mode"
            self.description = "Safe read-only exploration for browsing and querying"
            self.selected_model = "mistral_1" if "mistral_1" in self.models_list else self.models_list[0]
            self.tool_mode = "auto"
            self.disabled_tools = ["run_command", "run_safe", "run_unsafe", "setdb"]
            self.trace_tps = False
            self.trace_agentic_loop = False
            self.trace_raw_payload = False
            self.trace_rerank = False
            self.trace_tps_perf = False
            self.reasoning = False
            self.show_thinking = False
            self.reasoning_effort = "none"
            self.temperature = "0.7"
            self.max_turns = "25"
        elif preset_name == "blank":
            self.profile_name = ""
            self.description = ""
            self.selected_model = self.models_list[0]
            self.tool_mode = "off"
            self.trace_tps = False
            self.trace_agentic_loop = False
            self.trace_raw_payload = False
            self.trace_rerank = False
            self.trace_tps_perf = False
            self.reasoning = False
            self.show_thinking = False
            self.reasoning_effort = "none"
            self.temperature = "0.7"
            self.max_turns = "25"

    def run(self, stdscr) -> int:
        curses.use_default_colors()
        curses.curs_set(0)
        
        # Color pairs
        curses.init_pair(1, curses.COLOR_BLACK, curses.COLOR_CYAN)    # Header
        curses.init_pair(2, curses.COLOR_CYAN, -1)                   # Active selection
        curses.init_pair(3, curses.COLOR_YELLOW, -1)                 # Group titles
        curses.init_pair(4, curses.COLOR_RED, -1)                    # Error
        curses.init_pair(5, curses.COLOR_GREEN, -1)                  # Success
        curses.init_pair(6, curses.COLOR_BLACK, curses.COLOR_WHITE)  # Text field focus

        while True:
            self.draw(stdscr)
            ch = stdscr.getch()
            
            if ch == 27:  # ESC
                return 1
                
            elif ch in (curses.KEY_UP, curses.KEY_BTAB):
                self.current_field_idx = (self.current_field_idx - 1) % len(self.fields)
                
            elif ch in (curses.KEY_DOWN, 9):  # Tab or Down
                self.current_field_idx = (self.current_field_idx + 1) % len(self.fields)
                
            elif ch == 10 or ch == ord(' '):  # Enter or Space
                field_id, _, field_type = self.fields[self.current_field_idx]
                
                if field_type == "button":
                    if field_id.startswith("preset_"):
                        preset_name = field_id.split("_")[1]
                        self.apply_preset(preset_name)
                    elif field_id == "action_save":
                        if self.save():
                            return 0
                    elif field_id == "action_reset":
                        if self.loaded_filepath:
                            self.load_from_file(self.loaded_filepath)
                        else:
                            self.apply_preset("blank")
                    elif field_id == "action_cancel":
                        return 1
                        
                elif field_type == "checkbox":
                    setattr(self, field_id, not getattr(self, field_id))
                    
                elif field_type == "radio_tool":
                    self.tool_mode = field_id.split("_")[1]
                    
                elif field_type == "radio_effort":
                    self.reasoning_effort = field_id.split("_")[1]
                    
                elif field_type == "select":
                    # Toggle next model
                    curr_idx = self.models_list.index(self.selected_model)
                    self.selected_model = self.models_list[(curr_idx + 1) % len(self.models_list)]
                    
                elif field_type == "text":
                    self.edit_text(stdscr, field_id)
                    
            elif ch == 19:  # Ctrl+S
                if self.save():
                    return 0
                    
            elif ch == 1:  # Ctrl+A
                # Save and apply
                if self.save():
                    return 2

    def edit_text(self, stdscr, field_id: str) -> None:
        curses.curs_set(1)
        val = getattr(self, field_id)
        
        # Determine cursor position on screen
        # We'll just read simple input line using a curses-friendly block
        stdscr.addstr(curses.LINES - 2, 2, f"Editing {field_id}: ", curses.color_pair(3))
        stdscr.refresh()
        
        curses.echo()
        # Create a small window or input capture
        # To avoid blocking curses loop awkwardly, just use a simple string input
        try:
            # Move cursor to input area
            stdscr.move(curses.LINES - 2, 12 + len(field_id))
            input_bytes = stdscr.getstr()
            new_val = input_bytes.decode('utf-8').strip()
            if new_val:
                setattr(self, field_id, new_val)
        except Exception:
            pass
            
        curses.noecho()
        curses.curs_set(0)
        stdscr.move(curses.LINES - 2, 0)
        stdscr.clrtoeol()

    def save(self) -> bool:
        if not self.filename:
            self.status_message = "Error: File name cannot be empty"
            self.status_is_error = True
            return False
            
        if not self.filename.endswith(".chatdsl"):
            self.filename += ".chatdsl"
            
        try:
            self.pm.ensure_dir()
            path = os.path.join(self.pm.profile_dir, self.filename)
            content = self.generate_chatdsl()
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            self.status_message = f"Saved: {self.filename}"
            self.status_is_error = False
            return True
        except Exception as e:
            self.status_message = f"Error saving: {e}"
            self.status_is_error = True
            return False

    def draw(self, stdscr) -> None:
        stdscr.erase()
        h, w = stdscr.getmaxyx()
        
        # Draw header
        stdscr.addstr(0, 0, " CHATYBOT PROFILE EDITOR".ljust(w - 20), curses.color_pair(1) | curses.A_BOLD)
        stdscr.addstr(0, w - 20, " [Ctrl+S: Save/Exit]", curses.color_pair(1))
        
        # Left panel: form
        col_w = w // 2 - 2
        
        # Section titles and coordinates
        stdscr.addstr(2, 2, " PROFILE DETAILS", curses.color_pair(3) | curses.A_BOLD)
        stdscr.addstr(3, 2, "File name:    ")
        stdscr.addstr(4, 2, "@name:        ")
        stdscr.addstr(5, 2, "@description: ")
        
        stdscr.addstr(7, 2, " PRESETS", curses.color_pair(3) | curses.A_BOLD)
        
        stdscr.addstr(10, 2, " MODEL SELECTION", curses.color_pair(3) | curses.A_BOLD)
        stdscr.addstr(11, 2, "/model:       ")
        
        stdscr.addstr(13, 2, " TOOLS CONFIGURATION", curses.color_pair(3) | curses.A_BOLD)
        stdscr.addstr(14, 2, "tool auto:    ")
        
        stdscr.addstr(16, 2, " DEBUG / TRACING", curses.color_pair(3) | curses.A_BOLD)
        
        stdscr.addstr(19, 2, " REASONING / THINKING", curses.color_pair(3) | curses.A_BOLD)
        stdscr.addstr(22, 2, "Effort:       ")
        
        stdscr.addstr(24, 2, " ADVANCED OPTIONS", curses.color_pair(3) | curses.A_BOLD)
        stdscr.addstr(25, 2, "/temp:        ")
        stdscr.addstr(25, col_w // 2 + 2, "max_turns:    ")

        # Render field values
        for idx, (fid, label, ftype) in enumerate(self.fields):
            is_active = (idx == self.current_field_idx)
            style = curses.color_pair(2) if is_active else curses.A_NORMAL
            if is_active and ftype == "text":
                style = curses.color_pair(6)
                
            if fid == "filename":
                stdscr.addstr(3, 16, self.filename.ljust(col_w - 16)[:col_w-17], style)
            elif fid == "profile_name":
                stdscr.addstr(4, 16, self.profile_name.ljust(col_w - 16)[:col_w-17], style)
            elif fid == "description":
                stdscr.addstr(5, 16, self.description.ljust(col_w - 16)[:col_w-17], style)
                
            elif fid == "preset_coding":
                stdscr.addstr(8, 2, "[ Coding ]", style)
            elif fid == "preset_general":
                stdscr.addstr(8, 14, "[ General ]", style)
            elif fid == "preset_explorer":
                stdscr.addstr(8, 27, "[ Explorer ]", style)
            elif fid == "preset_blank":
                stdscr.addstr(8, 41, "[ Blank ]", style)
                
            elif fid == "model":
                stdscr.addstr(11, 16, f"[{self.selected_model}]".ljust(col_w - 16), style)
                
            elif fid == "tool_off":
                opt_style = style if self.tool_mode == "off" else (curses.color_pair(2) if is_active else curses.A_NORMAL)
                marker = "(*)" if self.tool_mode == "off" else "( )"
                stdscr.addstr(14, 16, f"{marker} Off", opt_style)
            elif fid == "tool_auto":
                opt_style = style if self.tool_mode == "auto" else (curses.color_pair(2) if is_active else curses.A_NORMAL)
                marker = "(*)" if self.tool_mode == "auto" else "( )"
                stdscr.addstr(14, 25, f"{marker} Auto", opt_style)
            elif fid == "tool_on":
                opt_style = style if self.tool_mode == "on" else (curses.color_pair(2) if is_active else curses.A_NORMAL)
                marker = "(*)" if self.tool_mode == "on" else "( )"
                stdscr.addstr(14, 35, f"{marker} On", opt_style)
                
            elif fid == "trace_tps":
                marker = "[x]" if self.trace_tps else "[ ]"
                stdscr.addstr(17, 2, f"{marker} TPS", style)
            elif fid == "trace_agentic_loop":
                marker = "[x]" if self.trace_agentic_loop else "[ ]"
                stdscr.addstr(17, 12, f"{marker} Loop", style)
            elif fid == "trace_raw_payload":
                marker = "[x]" if self.trace_raw_payload else "[ ]"
                stdscr.addstr(17, 22, f"{marker} RawPayload", style)
            elif fid == "trace_rerank":
                marker = "[x]" if self.trace_rerank else "[ ]"
                stdscr.addstr(17, 38, f"{marker} Rerank", style)
            elif fid == "trace_tps_perf":
                marker = "[x]" if self.trace_tps_perf else "[ ]"
                stdscr.addstr(17, 50, f"{marker} TPSPerf", style)
            elif fid == "trace_imagedbg":
                marker = "[x]" if self.trace_imagedbg else "[ ]"
                stdscr.addstr(17, 62, f"{marker} ImageDbg", style)
                
            elif fid == "reasoning":
                marker = "[x]" if self.reasoning else "[ ]"
                stdscr.addstr(20, 2, f"{marker} Reasoning Mode ON", style)
            elif fid == "show_thinking":
                marker = "[x]" if self.show_thinking else "[ ]"
                stdscr.addstr(20, 25, f"{marker} Show Thinking", style)
                
            elif fid == "effort_none":
                opt_style = style if self.reasoning_effort == "none" else (curses.color_pair(2) if is_active else curses.A_NORMAL)
                marker = "(*)" if self.reasoning_effort == "none" else "( )"
                stdscr.addstr(22, 16, f"{marker} None", opt_style)
            elif fid == "effort_low":
                opt_style = style if self.reasoning_effort == "low" else (curses.color_pair(2) if is_active else curses.A_NORMAL)
                marker = "(*)" if self.reasoning_effort == "low" else "( )"
                stdscr.addstr(22, 25, f"{marker} Low", opt_style)
            elif fid == "effort_medium":
                opt_style = style if self.reasoning_effort == "medium" else (curses.color_pair(2) if is_active else curses.A_NORMAL)
                marker = "(*)" if self.reasoning_effort == "medium" else "( )"
                stdscr.addstr(22, 33, f"{marker} Med", opt_style)
            elif fid == "effort_high":
                opt_style = style if self.reasoning_effort == "high" else (curses.color_pair(2) if is_active else curses.A_NORMAL)
                marker = "(*)" if self.reasoning_effort == "high" else "( )"
                stdscr.addstr(22, 41, f"{marker} High", opt_style)
                
            elif fid == "temperature":
                stdscr.addstr(25, 10, self.temperature.ljust(8)[:8], style)
            elif fid == "max_turns":
                stdscr.addstr(25, col_w // 2 + 14, self.max_turns.ljust(8)[:8], style)
                
            elif fid == "action_save":
                stdscr.addstr(27, 2, "[Save]", style)
            elif fid == "action_reset":
                stdscr.addstr(27, 12, "[Reset]", style)
            elif fid == "action_cancel":
                stdscr.addstr(27, 23, "[Cancel]", style)

        # Right panel: preview
        preview_x = col_w + 3
        stdscr.addstr(2, preview_x, " CHATDSL PREVIEW", curses.color_pair(3) | curses.A_BOLD)
        preview_text = self.generate_chatdsl()
        for r_idx, line in enumerate(preview_text.splitlines()[:23]):
            if preview_x + len(line) < w:
                stdscr.addstr(3 + r_idx, preview_x, line[:w-preview_x-1])

        # Border separator
        for r in range(1, h - 3):
            if preview_x - 2 < w:
                stdscr.addstr(r, preview_x - 2, "│")
                
        # Status line
        status_y = h - 3
        if self.status_message:
            s_style = curses.color_pair(4) if self.status_is_error else curses.color_pair(5)
            stdscr.addstr(status_y, 2, self.status_message[:w-4], s_style | curses.A_BOLD)
            
        # Help tips footer
        stdscr.addstr(h - 2, 2, "Tab/Arrows: Navigate  |  Space/Enter: Edit/Select  |  ESC: Exit Editor", curses.A_DIM)
        
        stdscr.refresh()

def run_profile_editor(name: str, pm: Any, config_manager: Any) -> int:
    """Wrapper function to execute curses TUI."""
    if curses is None:
        print(
            "Error: 'curses' module is unavailable. "
            "On Windows, please install windows-curses ('pip install windows-curses').",
            file=sys.stderr
        )
        return 1

    editor = ProfileEditor(name, pm, config_manager)
    try:
        res = curses.wrapper(editor.run)
        return res
    except KeyboardInterrupt:
        return 1
    except Exception as e:
        print(f"\nFatal error in Profile Editor: {str(e)}", file=sys.stderr)
        return 1
