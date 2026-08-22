#! /usr/bin/env python3
"""
Main Chatybot Application Class
Orchestrates all components and provides the main interface
"""

import asyncio
import os
import readline
import time
import re
import shlex
import random
import json
import copy
import signal
from datetime import datetime
from typing import Dict, Any, List, Tuple, Optional, Callable, Union
import logging
import atexit
import sys
import ctypes
import ctypes.util
import struct
from .pattern import PatternMatcher


class LoopBreak(Exception):
    """Raised to exit a foreach loop early via the 'break' keyword."""
    pass


try:
    import openai
    from openai import AsyncOpenAI
except ImportError:
    raise ImportError(
        "OpenAI SDK is not installed. Please install it with 'pip install openai'."
    )

try:
    from parsley import makeGrammar
except ImportError:
    raise ImportError(
        "Parsley is not installed. Please install it with 'pip install parsley'."
    )

from .config_manager import ConfigManager
from .logging_manager import LoggingManager
from .buffer_manager import BufferManager
from .image_generator import ImageGenerator
from .image_manager import ImageManager
from .extract_code import process_file
from .chaty_help import get_help_system
from .chatydb import (
    set_db,
    search_db,
    dblog,
    load_var,
    save_var,
    list_dbs,
    dbprint,
    SEARCHBUFFER,
)

# Global variables needed for database functionality
app = None  # Global app instance for database functions to access


class ChatybotApp:
    """Main application class for Chatybot."""

    def __init__(self, config_path: Optional[str] = None, lang: str = "en", no_tools: bool = False):
        """Initialize the Chatybot application."""
        self.no_tools: bool = no_tools
        # Initialize managers
        from .localization import LocalizationManager
        self.i18n = LocalizationManager(locale=lang)
        self.config_manager = ConfigManager(config_path=config_path)
        self.logging_manager = LoggingManager()
        self.buffer_manager = BufferManager(app=self)
        self.image_generator = ImageGenerator()
        self.image_manager = ImageManager()
        self.help_system = get_help_system()
        self.matcher = PatternMatcher(
            words=[
                "help", "prompt", "file", "showfile", "clearfile",
                "filebank", "filebank1", "filebank2", "filebank3", "filebank4", "filebank5",
                "imagebank", "imagebank1", "imagebank2", "imagebank3", "imagebank4", "imagebank5",
                "loadimage", "loadimage1", "loadimage2", "loadimage3", "loadimage4", "loadimage5",
                "listimages", "showimage", "imagedir", "imagine", "saveimage", "imagesize", "imagequality",
                "model", "listmodels", "logging", "save", "codeonly", "codeoff", "multiline",
                "system", "temp", "maxtokens", "top_p", "top_k", "freq_penalty", "pres_penalty",
                "reasoning", "effort", "thinking", "thoughtstyle", "seed", "echo", "def",
                "reloadmacros", "listmacros", "calc", "stream", "script", "source", "profile", "quit", "exit",
                "setdb", "dblist", "searchdb", "dblog", "dbprint", "documents", "rerank",
                "loadvar", "savevar", "setvar", "notemode", "mem", "dump", "trace", "debug",
                "run", "run_safe", "run_unsafe", "tool", "proc", "defproc", "endproc", "local", "foreach", "endfor", "break"
            ]
        )

        # Procedure processing system
        self.procedures: Dict[str, Dict[str, Any]] = {}
        self.proc_depth: int = 0
        self.active_proc_stack: List[Dict[str, Any]] = []

        # Image generation settings
        self.image_size = "1024x1024"
        self.image_quality = "standard"
        self.image_debug_mode = False
        self.image_size_manual = False

        # Chat state
        self.chat_history: List[Tuple[str, str]] = []
        self.input_history: List[str] = []
        self.input_history_index = -1
        self.input_history_matches: List[str] = []

        # Flags and settings
        self.code_only_flag: bool = False
        self.streaming_enabled: bool = False
        self.note_mode: bool = False
        self.reasoning_mode: bool = True
        self.reasoning_effort: Optional[str] = None
        self.show_thinking: bool = True
        # Reasoning token count from the most recent completion's usage, if the
        # provider exposes one (e.g. OpenAI completion_tokens_details.reasoning_tokens).
        # Read by /dblog --thinking. Reset to 0 each completion.
        self.last_reasoning_tokens: int = 0
        self.multi_line_mode: bool = False
        self.auto_exit_pending: bool = False
        self.script_context: bool = False
        self.thoughtstyle: str = "none"
        self.default_profile: Optional[str] = None
        
        # Context limit settings
        from .context_limit import ContextLimiter
        self.context_limiter = ContextLimiter()
        
        # Run command settings
        self.safe_mode: bool = True
        self.safe_mode_askfirst: bool = False
        self.run_timeout: int = 30
        
        # Tool mode settings
        self.mcp_manager = None
        self.tool_mode: bool = False
        self.tool_context: str = ""
        self.in_tool_loop: bool = False
        self.tool_auto: bool = False
        self.max_turns: int = 25
        self.max_tool_calls_per_turn: int = 10
        self.agentic_instructions: str = ""
        self.live_agentic_instructions: str = ""
        self.tool_timeout: int = 30
        self.rate_limit_delay: float = 0.0
        self._cached_rate_limit_delay: Optional[float] = None
        self.strip_thinking_from_filebanks: bool = True
        self.tool_overrides: Dict[str, bool] = {}
        self.default_agentic_instructions: str = (
            "IMPORTANT: You are executing in an autonomous, multi-turn tool-calling loop. "
            "Use tools ONLY when necessary to perform actions on the system or fetch external information. "
            "If the user's request can be answered directly using your general knowledge without tools, do not call any tools and answer directly in natural language. "
            "If you need to use a tool, output ONLY the single next JSON tool call "
            "block (e.g. within ```json ... ```). DO NOT describe your plan, DO NOT offer a menu of "
            "different options, and DO NOT ask the user for permission or input. Just output the tool "
            "call. Only output natural language/conversation when you have finished all tool executions "
            "and are ready to present the final result."
        )

        # Session persistence settings
        self.session_mode: str = "auto"          # "off", "on", "auto"
        self.session_dir: str = os.path.expanduser("~/.local/share/chatybot/sessions")
        self.session_strip_thinking: str = "separate" # "separate", "true", "false"
        self.active_session_id: Optional[str] = None
        self.active_session_name: Optional[str] = None
        self.session_model_alias: Optional[str] = None
        self.session_turns: List[Dict[str, Any]] = []
        self.session_created_at: Optional[str] = None
        self.session_first_prompt_slug: Optional[str] = None
        self.session_notes: Optional[str] = None

        # Trace settings
        self.trace_raw_payload: bool = False
        self.trace_tps: bool = False
        self.trace_tps_perf: bool = False
        self.trace_rerank: bool = False
        self.trace_agentic_loop: bool = False
        self.debug_payload_mode: bool = False
        self.debug_response_mode: bool = False
        self.debug_response_raw: bool = False
        self.debug_payload_data: dict = {}

        # Virtual Memory Monitoring state
        self.vmem_monitor_thread: Optional[object] = None
        self.vmem_monitor_active: bool = False
        self.vmem_log_file: Optional[str] = None

        # Seed configuration
        self.seed_config: Optional[Union[int, str, Tuple[str, int, int]]] = None

        # Control-C handling state
        self.control_c_count: int = 0
        self.interrupt_requested: bool = False

        # Top-level parameters
        self.temperature: Optional[float] = None
        self.top_p: Optional[float] = None
        self.top_k: Optional[int] = None
        self.freq_penalty: Optional[float] = None
        self.pres_penalty: Optional[float] = None

        # Semantic Reranking state
        self.rerank_documents_source = None
        self.latest_rerank_results = []

        # Macro processing state
        self.macros: Dict[str, Dict[str, Any]] = {}
        self._definition_grammar = None
        self._invocation_grammar = None

    def initialize(self) -> None:
        """Initialize the application by loading configuration and setting up history."""
        # Load environment variables from .env file if it exists
        for path in [".env", "../.env", "../../.env"]:
            if os.path.exists(path):
                try:
                    with open(path, "r") as f:
                        for line in f:
                            line = line.strip()
                            if line and not line.startswith("#") and "=" in line:
                                k, v = line.split("=", 1)
                                k = k.strip()
                                v = v.strip().strip('"\'')
                                os.environ[k] = v
                    break
                except Exception:
                    pass

        # Also load from jina_api_key.txt as fallback
        for key_file in ["jina_api_key.txt", "jina_ai_key.txt", "../jina_api_key.txt", "../jina_ai_key.txt"]:
            if os.path.exists(key_file):
                try:
                    with open(key_file, "r") as f:
                        content = f.read().strip()
                        if "JINA_API_KEY=" in content:
                            key = content.split("JINA_API_KEY=")[-1].strip().strip('"\'')
                            os.environ["JINA_API_KEY"] = key
                        elif "export " in content and "=" in content:
                            key = content.split("=")[-1].strip().strip('"\'')
                            os.environ["JINA_API_KEY"] = key
                        else:
                            os.environ["JINA_API_KEY"] = content.strip('"\'')
                    break
                except Exception:
                    pass

        # Load configuration
        self.config_manager.load_config()

        # Initialize context limit from active model if configured
        if hasattr(self, "context_limiter") and not self.context_limiter._user_set_limit:
            active_model = self.config_manager.active_model_alias
            if active_model:
                try:
                    m_cfg = self.config_manager.get_model_config(active_model)
                    if m_cfg and m_cfg.get("context_limit"):
                        self.context_limiter.set_limit(m_cfg.get("context_limit"), from_user=False)
                except Exception:
                    pass

        # Initialize MCP Client Manager unless disabled via --no-tools
        if self.no_tools:
            self.mcp_manager = None
            self.tool_mode = False
            self.tool_auto = False
        else:
            from .mcp_client import MCPClientManager
            self.mcp_manager = MCPClientManager(self.config_manager.config)

        # Load default profile from tools_config.toml under [config]
        self.default_profile = None
        user_config_path = os.path.expanduser('~/.config/chatybot/tools_config.toml')
        package_config = os.path.join(os.path.dirname(__file__), 'tools_config.toml')
        from .config_sync import sync_toml_file
        sync_toml_file(package_config, user_config_path, "tools_config.toml")
        config_path = user_config_path if os.path.exists(user_config_path) else package_config
        if os.path.exists(config_path):
            try:
                import tomllib
                with open(config_path, 'rb') as f:
                    tools_cfg = tomllib.load(f)
            except Exception:
                try:
                    import toml
                    with open(config_path, 'r') as f:
                        tools_cfg = toml.load(f)
                except Exception:
                    print("could not load tools_config.toml, continuing ")
                    tools_cfg = {}
            
            config_section = tools_cfg.get('config', {})
            self.default_profile = config_section.get('default_profile')
            self.max_turns = config_section.get('max_turns', 25)
            self.max_tool_calls_per_turn = config_section.get('max_tool_calls_per_turn', 10)
            self.profile_dir = config_section.get('profile_dir', '~/.config/chatybot/profiles')
            self.enable_profile_edit = config_section.get('enable_profile_edit', True)

            # Seed presets on first run
            from .profile_manager import ProfileManager
            try:
                ProfileManager(self.profile_dir).seed_presets()
            except Exception as e:
                print(f"Error seeding profile presets: {e}")

        # Set up input history
        self.load_input_history()

        # Set up readline for command history
        readline.set_completer(self.input_history_completer)
        readline.parse_and_bind("tab: complete")
        readline.set_completer_delims(" \t\n;") 

        # Register save and cleanup functions to be called on exit
        atexit.register(self.save_input_history)
        atexit.register(self.cleanup_mcp_sync)
        
        # Initialize macro processing system
        self.macros = {}
        
        # Load default macros for interactive use
        self.load_macros()
        
        # Set up signal handler for Control-C
        self.setup_signal_handler()

    def setup_signal_handler(self) -> None:
        """Set up signal handler for Control-C interrupts."""
        def signal_handler(sig, frame):
            if sig == signal.SIGINT:
                self.control_c_count += 1
                if self.control_c_count >= 2:
                    # Second Ctrl+C - exit program
                    print("\nExiting...")
                    self.logging_manager.stop_logging()
                    self.save_input_history()
                    self.cleanup_mcp_sync()
                    os._exit(0)
                else:
                    # First Ctrl+C - set flag for graceful interruption
                    self.interrupt_requested = True
        
        signal.signal(signal.SIGINT, signal_handler)

    def cleanup_mcp_sync(self) -> None:
        """Synchronously cleanup MCP manager and active sessions on exit."""
        if hasattr(self, "active_session_id"):
            self._release_session_lock()
        if hasattr(self, "mcp_manager") and self.mcp_manager:
            try:
                try:
                    loop = asyncio.get_running_loop()
                    loop.create_task(self.mcp_manager.shutdown())
                except RuntimeError:
                    loop = asyncio.get_event_loop()
                    loop.run_until_complete(self.mcp_manager.shutdown())
            except Exception:
                pass

    async def interruptible_sleep(self, delay: float) -> None:
        """
        Sleep for specified delay, checking interrupt_requested at head and end.
        """
        if self.interrupt_requested:
            self.interrupt_requested = False
            raise KeyboardInterrupt()

        if delay > 0:
            await asyncio.sleep(delay)

        if self.interrupt_requested:
            self.interrupt_requested = False
            raise KeyboardInterrupt()

    async def _apply_rate_limit_delay(self) -> None:
        """
        Applies rate limit sleep delay with timestamps and elapsed pause time calculation.
        """
        delay = getattr(self, 'rate_limit_delay', 0.0)
        if delay > 0.0:
            start_ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            start_time = time.perf_counter()
            print(f"[{start_ts}] Pausing for {delay}s rate limit delay...")
            await self.interruptible_sleep(delay)
            end_ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            elapsed = time.perf_counter() - start_time
            print(f"[{end_ts}] Rate limit delay completed (elapsed: {elapsed:.2f}s).")

    @property
    def definition_grammar(self):
        """Lazy-compile definition grammar on first access."""
        if getattr(self, "_definition_grammar", None) is None:
            self._definition_grammar = makeGrammar("""
        macro_def = macro_def_with_params | macro_def_no_params
        macro_def_with_params = 'def' ws ident:name ws '(' ws param_list?:params ws ')' ws '=' ws string:template -> (name, params or [], template)
        macro_def_no_params = 'def' ws ident:name ws '(' ws ')' ws '=' ws string:template -> (name, [], template)
        param_list = param:p (ws ',' ws param)*:ps -> [p] + ps
        param = variable_ref | ident
        variable_ref = '${' ident:var_name '}' -> var_name
        ident = <letter (letter | digit | '_')*>
        letter = 'a' | 'b' | 'c' | 'd' | 'e' | 'f' | 'g' | 'h' | 'i' | 'j' | 'k' | 'l' | 'm' | 'n' | 'o' | 'p' | 'q' | 'r' | 's' | 't' | 'u' | 'v' | 'w' | 'x' | 'y' | 'z' | 'A' | 'B' | 'C' | 'D' | 'E' | 'F' | 'G' | 'H' | 'I' | 'J' | 'K' | 'L' | 'M' | 'N' | 'O' | 'P' | 'Q' | 'R' | 'S' | 'T' | 'U' | 'V' | 'W' | 'X' | 'Y' | 'Z'
        digit = '0' | '1' | '2' | '3' | '4' | '5' | '6' | '7' | '8' | '9'
        string = '"' <(~'"' anything)*>:s '"' -> s
        ws = ' '*
        """, {})
        return self._definition_grammar

    @property
    def invocation_grammar(self):
        """Lazy-compile invocation grammar on first access."""
        if getattr(self, "_invocation_grammar", None) is None:
            self._invocation_grammar = makeGrammar("""
        macro_call = macro_call_with_args | macro_call_no_args
        macro_call_with_args = '%' ws ident:name ws '(' ws arg_list?:args ws ')' -> (name, args or [])
        macro_call_no_args = '%' ws ident:name ws '(' ws ')' -> (name, [])
        arg_list = arg:a (ws ',' ws arg)*:rest -> [a] + rest
        arg = variable_ref | string | version | ident | number
        variable_ref = '${' <letter (letter | digit | '_')*>:var_name '}' -> var_name
        version = <digit+ ('.' (digit | ident))+>
        number = <digit+>
        string = '"' <(~'"' anything)*>:s '"' -> s
        ident = <letter (letter | digit | '_' | ' ' | '-')*>  # Allow spaces and hyphens in identifiers for multi-word args
        letter = 'a' | 'b' | 'c' | 'd' | 'e' | 'f' | 'g' | 'h' | 'i' | 'j' | 'k' | 'l' | 'm' | 'n' | 'o' | 'p' | 'q' | 'r' | 's' | 't' | 'u' | 'v' | 'w' | 'x' | 'y' | 'z' | 'A' | 'B' | 'C' | 'D' | 'E' | 'F' | 'G' | 'H' | 'I' | 'J' | 'K' | 'L' | 'M' | 'N' | 'O' | 'P' | 'Q' | 'R' | 'S' | 'T' | 'U' | 'V' | 'W' | 'X' | 'Y' | 'Z'
        digit = '0' | '1' | '2' | '3' | '4' | '5' | '6' | '7' | '8' | '9'
        ws = ' '*
        """, {})
        return self._invocation_grammar

    def setup_macro_grammars(self):
        """No-op kept for backwards compatibility."""
        pass

    def load_macros(self, macro_file: str = "macro.chatdsl") -> None:
        """Load macro definitions from file using Parsley."""
        try:
            macro_path = os.path.join(os.getcwd(), macro_file)
            if not os.path.exists(macro_path):
                # Try in the src/chatybot directory
                macro_path = os.path.join(os.path.dirname(__file__), macro_file)
                if not os.path.exists(macro_path):
                    print(f"Macro file {macro_file} not found, starting with empty macros")
                    return
            
            with open(macro_path, 'r') as f:
                content = f.read()
            
            # Parse each line for macro definitions using Parsley
            for line in content.split('\n'):
                line = line.strip()
                if line.startswith('def ') and '=' in line:
                    try:
                        parsed = self.definition_grammar(line).macro_def()
                        name, params, template = parsed
                        self.macros[name] = {'params': params, 'template': template}
                    except Exception as e:
                        print(f"Warning: Could not parse macro definition: {line}")
                        print(f"Error: {e}")
        except Exception as e:
            print(f"Error loading macros: {e}")

    def list_macros(self, filter_term: Optional[str] = None) -> None:
        """List all loaded macros with parameter signatures and template previews."""
        if not self.macros:
            print("No macros loaded. Use '/reloadmacros' to load macro definitions.")
            return

        items = self.macros.items()
        if filter_term:
            filter_lower = filter_term.lower()
            items = [
                (k, v) for k, v in items
                if filter_lower in k.lower() or filter_lower in v.get('template', '').lower()
            ]
            if not items:
                print(f"No macros matching '{filter_term}' found.")
                return

        print(f"\nAvailable Macros ({len(items)} loaded):")
        print("─" * 80)
        print(f"  {'Macro Signature':<35} {'Template / Summary':<42}")
        print("─" * 80)

        for name, meta in sorted(items, key=lambda x: x[0]):
            params = meta.get('params', [])
            params_str = ", ".join(params) if params else ""
            sig = f"%{name}({params_str})"

            template = meta.get('template', '').replace('\n', ' ').strip()
            summary = template if len(template) <= 40 else template[:37] + "..."

            print(f"  {sig:<35} {summary:<42}")
        print()

    def expand_macro(self, macro_call: str) -> str:
        """Expand a single macro call using Parsley."""
        try:
            # Parse the macro invocation using Parsley
            parsed = self.invocation_grammar(macro_call).macro_call()
            name, args = parsed
            
            # Resolve variables in arguments
            # Note: The Parsley grammar resolves ${var} to just 'var' during parsing
            # So if an argument is in the variables dict, it came from a ${var} reference
            # If it's not in the variables dict, treat it as a literal (matches original behavior)
            resolved_args = []
            for arg in args:
                if isinstance(arg, str) and arg in self.buffer_manager.script_vars:
                    # This argument was a variable reference (from ${var} syntax)
                    # and the variable is defined, so use its value
                    resolved_args.append(self.buffer_manager.script_vars[arg])
                else:
                    # This is a literal argument (bare identifier, string, number, etc.)
                    # This matches the original proof of concept behavior where
                    # undefined variable references are treated as literals
                    resolved_args.append(arg)
            
            # Get macro definition
            if name not in self.macros:
                return f"ERROR: Macro '{name}' not defined"
            
            macro = self.macros[name]
            
            # Check argument count
            if len(resolved_args) != len(macro['params']):
                return f"ERROR: Macro '{name}' expects {len(macro['params'])} arguments, got {len(resolved_args)}"
            
            # If the template contains ${param}, convert it to {param} for python .format()
            template = macro['template']
            for param in macro['params']:
                template = template.replace(f"${{{param}}}", f"{{{param}}}")
            
            # Check if any arguments are array references
            array_args_info = {}
            for param, arg in zip(macro['params'], resolved_args):
                if isinstance(arg, list):
                    array_args_info[param] = arg

            if array_args_info:
                # We have array arguments! Find the maximum length to iterate over
                num_iterations = max(len(data) for data in array_args_info.values())
                
                expanded_runs = []
                for i in range(num_iterations):
                    iteration_mapping = {}
                    for param, arg in zip(macro['params'], resolved_args):
                        if param in array_args_info:
                            data_list = array_args_info[param]
                            val = data_list[i] if i < len(data_list) else ""
                            iteration_mapping[param] = val
                        else:
                            iteration_mapping[param] = arg
                    
                    try:
                        expanded_runs.append(template.format(**iteration_mapping))
                    except Exception as e:
                        return f"ERROR: Format error in macro '{name}' at iteration {i}: {e}"
                
                return "\n".join(expanded_runs)
            
            # Create parameter mapping
            param_mapping = {}
            for param, arg in zip(macro['params'], resolved_args):
                param_mapping[param] = arg
            
            # Format the template (no array arguments)
            try:
                expanded = template.format(**param_mapping)
                return expanded
            except Exception as e:
                return f"ERROR: Format error in macro '{name}': {e}"
                
        except Exception as e:
            return f"ERROR: Could not parse macro call '{macro_call}': {e}"

    def process_macro_line(self, line: str) -> str:
        """Process a single line, expanding any macros."""
        if line.startswith('%'):
            # This is a macro call - use Parsley to parse it
            return self.expand_macro(line.strip())
        else:
            # Regular line, check for variable substitution
            result = line
            for var_name, var_value in self.buffer_manager.script_vars.items():
                result = result.replace(f'${{{var_name}}}', var_value)
            return result

    def parse_dsl_list(self, val_str: str) -> List[str]:
        """Splits a DSL list string by top-level commas, respecting quotes and braces/brackets."""
        val_str = val_str.strip()
        if "```" in val_str:
            m = re.search(r"```(?:json)?\s*(\[.*?\])\s*```", val_str, re.DOTALL)
            if m:
                val_str = m.group(1).strip()
            else:
                val_str = re.sub(r"```(?:json)?", "", val_str).replace("```", "").strip()

        if not (val_str.startswith('[') and val_str.endswith(']')):
            raise ValueError("Array literal must start with '[' and end with ']'")
        
        content = val_str[1:-1]
        elements = []
        current_element = []
        
        in_double_quote = False
        in_single_quote = False
        escape = False
        brace_depth = 0
        bracket_depth = 0
        
        for char in content:
            if escape:
                current_element.append(char)
                escape = False
                continue
            
            if char == '\\':
                current_element.append(char)
                escape = True
                continue
            
            if char == '"' and not in_single_quote:
                in_double_quote = not in_double_quote
                current_element.append(char)
                continue
            
            if char == "'" and not in_double_quote:
                in_single_quote = not in_single_quote
                current_element.append(char)
                continue
                
            if not in_double_quote and not in_single_quote:
                if char == '{':
                    brace_depth += 1
                elif char == '}':
                    brace_depth = max(0, brace_depth - 1)
                elif char == '[':
                    bracket_depth += 1
                elif char == ']':
                    bracket_depth = max(0, bracket_depth - 1)
                elif char == ',' and brace_depth == 0 and bracket_depth == 0:
                    elements.append("".join(current_element))
                    current_element = []
                    continue
                    
            current_element.append(char)
            
        elements.append("".join(current_element))
        return elements

    def parse_array_value(self, val_str: str) -> List[str]:
        """
        Parses an array value string containing a DSL list, replacing placeholders
        within elements, and returns a list of resolved string elements.
        
        Supports element-level placeholder replacement, avoiding syntax errors
        when placeholders resolve to strings containing quotes, newlines, or leading zeros.
        """
        val_str = val_str.strip()
        if not val_str.startswith('[') and not val_str.startswith('```'):
            resolved = self.buffer_manager.replace_placeholders_legacy(val_str)
            if resolved:
                val_str = resolved.strip()

        # Parse the top-level list structure
        raw_elements = self.parse_dsl_list(val_str)
        
        # Resolve placeholders for each element
        resolved_elements = []
        for elem in raw_elements:
            elem = elem.strip()
            if not elem:
                continue
            
            # Check if it's a quoted string
            if (elem.startswith('"') and elem.endswith('"')) or (elem.startswith("'") and elem.endswith("'")):
                # Unwrap the string literal safely
                import ast
                try:
                    unwrapped = ast.literal_eval(elem)
                except Exception:
                    unwrapped = elem[1:-1]
                
                # Resolve placeholders inside the string
                resolved_val = self.resolve_placeholders_in_element(unwrapped)
                resolved_elements.append(resolved_val)
            else:
                # It's an unquoted element (placeholder, number, or bareword)
                resolved_val = self.resolve_placeholders_in_element(elem)
                resolved_elements.append(resolved_val)
                
        return resolved_elements

    def resolve_placeholders_in_element(self, elem: str) -> str:
        """Resolve all placeholders (filebanks, script variables, image banks) in a single element."""
        # 1. Image banks
        for i in range(1, 6):
            placeholder = f"{{imagebank{i}}}"
            if placeholder in elem:
                bank_name = f"imagebank{i}"
                if bank_name in self.buffer_manager.image_banks:
                    image_data = self.buffer_manager.image_banks[bank_name]
                    if image_data:
                        elem = elem.replace(placeholder, image_data)
        
        # 2. CHAT_HISTORY
        if "{CHAT_HISTORY}" in elem:
            import json
            history_json = []
            for p, r in self.chat_history:
                history_json.append({"role": "user", "content": p})
                history_json.append({"role": "assistant", "content": r})
            elem = elem.replace("{CHAT_HISTORY}", json.dumps(history_json))
            
        # 3. LAST_RESPONSE
        if "{LAST_RESPONSE}" in elem:
            if self.chat_history:
                last_turn_response = self.chat_history[-1][1]
                elem = elem.replace("{LAST_RESPONSE}", last_turn_response)
            else:
                elem = elem.replace("{LAST_RESPONSE}", "")
                
        # 4. Filebanks and script variables (via legacy replace)
        # Run up to 5 times to resolve nested/recursive placeholder references
        for _ in range(5):
            new_elem = self.buffer_manager.replace_placeholders_legacy(elem)
            if new_elem == elem:
                break
            elem = new_elem
        
        return elem

    def get_sessions_dir(self) -> str:
        """Get directory path for storing session files."""
        import sys
        if "pytest" in sys.modules or os.environ.get("PYTEST_CURRENT_TEST"):
            path = os.path.expanduser("~/.local/share/chatybot/test/sessions")
        else:
            path = self.session_dir
        os.makedirs(path, exist_ok=True)
        return path

    def _resolve_session_file(self, target: str) -> Optional[str]:
        """Find a session JSON or JSON.GZ file path by exact path, ID, or custom name."""
        sessions_dir = self.get_sessions_dir()

        # 1. Exact path / filename check
        for ext in ("", ".json", ".json.gz"):
            cand = target + ext if not target.endswith(ext) or ext == "" else target
            p = os.path.join(sessions_dir, cand) if not os.path.isabs(cand) else cand
            if os.path.isfile(p):
                return p

        # 2. Match custom_name or session_id metadata
        import gzip
        for fname in os.listdir(sessions_dir):
            if fname.endswith(".json") or fname.endswith(".json.gz"):
                fp = os.path.join(sessions_dir, fname)
                try:
                    open_fn = gzip.open if fname.endswith(".gz") else open
                    with open_fn(fp, "rt", encoding="utf-8") as sf:
                        sdata = json.load(sf)
                        if sdata.get("custom_name") == target or sdata.get("session_id") == target:
                            return fp
                except Exception:
                    pass
        return None

    def _slugify_text(self, text: str, max_words: int = 6) -> str:
        """Convert text prompt into a clean filename slug."""
        clean = re.sub(r"[^\w\s-]", "", text.strip())
        words = clean.split()[:max_words]
        slug = "_".join(words).lower()
        return slug if slug else "untitled_session"

    def _generate_session_id(self, model_alias: str) -> str:
        """Generate a unique session ID, appending a counter if the timestamp collides."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        base_id = f"{model_alias}_{timestamp}"
        sessions_dir = self.get_sessions_dir()
        candidate = base_id
        counter = 1
        while os.path.exists(os.path.join(sessions_dir, f"{candidate}.json")) or \
              os.path.exists(os.path.join(sessions_dir, f"{candidate}.json.gz")) or \
              os.path.exists(os.path.join(sessions_dir, f"{candidate}.lock")):
            candidate = f"{base_id}_{counter}"
            counter += 1
        return candidate

    def _extract_thinking_tokens(self, response_text: str) -> Tuple[Optional[str], str]:
        """Extract reasoning traces (<think>...</think>) from response text."""
        matches = re.findall(r"<think>(.*?)</think>|<thought>(.*?)</thought>", response_text, flags=re.DOTALL)
        if matches:
            thinking_parts = [(m[0] or m[1] or "").strip() for m in matches]
            thinking_content = "\n\n".join(p for p in thinking_parts if p)
            clean_text = re.sub(r"<think>.*?</think>\s*|<thought>.*?</thought>\s*", "", response_text, flags=re.DOTALL).strip()
            return (thinking_content or None), clean_text
        return None, response_text

    def _ensure_active_session(self, initial_prompt: str = ""):
        """Initialize active session state if not already started."""
        if self.session_mode == "off":
            return
        if not self.active_session_id:
            now = datetime.now()
            model_alias = getattr(self.config_manager, "active_model_alias", None) or "default"
            self.session_model_alias = model_alias
            self.active_session_id = self._generate_session_id(model_alias)
            self.session_created_at = now.isoformat()
            if initial_prompt:
                self.session_first_prompt_slug = self._slugify_text(initial_prompt)
            self._acquire_session_lock(self.active_session_id)

    def _pid_alive(self, pid: int) -> bool:
        """Check whether a process with the given PID is currently running."""
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return False
        except PermissionError:
            return True
        except OSError:
            return False
        return True

    def _session_lock_path(self, session_id: str) -> str:
        """Get the path to the lock file for a session."""
        return os.path.join(self.get_sessions_dir(), f"{session_id}.lock")

    def _acquire_session_lock(self, session_id: str) -> bool:
        """Acquire a lock file for the session. Returns True if acquired or already held."""
        lock_path = self._session_lock_path(session_id)
        if os.path.exists(lock_path):
            try:
                with open(lock_path, "r") as f:
                    pid = int(f.read().strip())
                if pid == os.getpid():
                    return True
                if self._pid_alive(pid):
                    print(f"Warning: Session '{session_id}' is in use by PID {pid}. "
                          f"Concurrent writes may cause divergent or lost history. "
                          f"Use /session start for a new session.")
                    return False
            except (ValueError, IOError):
                pass
        try:
            with open(lock_path, "w") as f:
                f.write(str(os.getpid()))
            return True
        except IOError:
            return False

    def _release_session_lock(self, session_id: Optional[str] = None) -> None:
        """Release the lock file for the given session (or the active session if None)."""
        sid = session_id or self.active_session_id
        if not sid:
            return
        lock_path = self._session_lock_path(sid)
        try:
            if os.path.exists(lock_path):
                with open(lock_path, "r") as f:
                    pid = int(f.read().strip())
                if pid == os.getpid():
                    os.remove(lock_path)
        except (ValueError, IOError, OSError):
            pass

    def save_active_session(self):
        """Save current active session state to disk atomically."""
        if self.session_mode == "off" or not self.active_session_id:
            return

        # If slug is missing or "untitled_session", try to compute from Turn 1 prompt
        if (not self.session_first_prompt_slug or self.session_first_prompt_slug == "untitled_session") and self.session_turns:
            turn1_prompt = self.session_turns[0].get("prompt", "")
            if turn1_prompt:
                self.session_first_prompt_slug = self._slugify_text(turn1_prompt)

        sessions_dir = self.get_sessions_dir()
        file_path = os.path.join(sessions_dir, f"{self.active_session_id}.json")
        tmp_path = file_path + ".tmp"

        model_alias = self.session_model_alias or "default"
        payload = {
            "session_id": self.active_session_id,
            "model_alias": model_alias,
            "created_at": self.session_created_at or datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "first_prompt_slug": self.session_first_prompt_slug or "untitled_session",
            "custom_name": self.active_session_name,
            "notes": self.session_notes[:1024] if self.session_notes else None,
            "turns": self.session_turns
        }

        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
        os.replace(tmp_path, file_path)

    def append_session_turn(self, prompt: str, response: str, agentic_loop_data: Optional[List[Dict[str, Any]]] = None):
        """Append a completed exchange turn to active session and save to disk."""
        if self.session_mode == "off":
            return

        self._ensure_active_session(prompt)
        
        thinking_text, clean_resp = self._extract_thinking_tokens(response)
        
        turn_data: Dict[str, Any] = {
            "turn_id": len(self.session_turns) + 1,
            "model_alias": getattr(self.config_manager, "active_model_alias", None) or "default",
            "prompt": prompt,
            "response": clean_resp if self.session_strip_thinking != "false" else response
        }
        if thinking_text and self.session_strip_thinking == "separate":
            turn_data["thinking"] = thinking_text
        if agentic_loop_data:
            turn_data["agentic_loop"] = agentic_loop_data

        self.session_turns.append(turn_data)
        self.save_active_session()
        self.buffer_manager.set_script_var('SESSION_NAME', self.active_session_name or self.active_session_id, allow_protected=True)

    def get_history_path(self) -> str:
        """
        Get the path to the chat history file.

        Returns:
            Path to the chat history file
        """
        import sys
        if "pytest" in sys.modules or os.environ.get("PYTEST_CURRENT_TEST"):
            path = os.path.expanduser("~/.local/share/chatybot/test")
        else:
            path = os.path.expanduser("~/.local/share/chatybot")
        os.makedirs(path, exist_ok=True)
        return os.path.join(path, ".chat_history")

    def save_input_history(self) -> None:
        """Save input history to a file before exiting."""
        if self.input_history:
            with open(self.get_history_path(), "w") as f:
                f.write("\n".join(self.input_history))

    def load_input_history(self) -> None:
        """Load input history from file."""
        try:
            with open(self.get_history_path(), "r") as f:
                self.input_history = [
                    line.strip() for line in f.readlines() if line.strip()
                ]
            # Set up readline history
            for line in self.input_history:
                readline.add_history(line)
        except FileNotFoundError:
            pass

    def input_history_completer(self, text: str, state: int) -> Optional[str]:
        """
        Completer function for readline to navigate input history.

        Args:
            text: Current input text
            state: Current state in the completion

        Returns:
            Next matching history item or None
        """
        if state == 0:
            # Filter history based on text
            self.input_history_matches = [
                h for h in self.input_history if h.startswith(text)
            ]
            self.input_history_index = 0
        else:
            self.input_history_index += 1

        if self.input_history_index < len(self.input_history_matches):
            return self.input_history_matches[self.input_history_index]
        return None

    def search_input_history(self, search_term: str) -> List[str]:
        """
        Search input history for commands containing the search term.

        Args:
            search_term: Term to search for in history

        Returns:
            List of matching history items (last 5)
        """
        if not search_term:
            return []

        # Search for items containing the search term (case insensitive)
        matches = [
            item for item in reversed(self.input_history) 
            if search_term.lower() in item.lower()
        ][:5]  # Get last 5 matches

        return list(reversed(matches))  # Return in original order (oldest first)

    async def handle_history_command(self, command: str) -> Optional[str]:
        """
        Handle the history search command (!).

        Args:
            command: The full command starting with !

        Returns:
            The selected history item or None if cancelled
        """
        if not command.startswith("!"):
            return None

        # Extract search term (everything after the !)
        search_term = command[1:].strip()

        if not search_term:
            print("Usage: ! <search_term>")
            return None

        # Search history
        matches = self.search_input_history(search_term)

        if not matches:
            print(f"No history items found containing '{search_term}'")
            return None

        # Display matches
        prompt_prefix = self.i18n.get_ui_string("chat_prompt", "chat --> ").rstrip()
        print(f"\n{prompt_prefix}! {search_term}")
        print()
        for i, match in enumerate(matches, 1):
            print(f"   {i}. {match}")

        # Get user selection
        while True:
            choice = input("pick num or q to cancel: ").strip().lower()
            
            if choice == 'q':
                return None
            
            try:
                choice_num = int(choice)
                if 1 <= choice_num <= len(matches):
                    return matches[choice_num - 1]
                else:
                    print(f"Please enter a number between 1 and {len(matches)} or 'q' to cancel.")
            except ValueError:
                print(f"Please enter a number between 1 and {len(matches)} or 'q' to cancel.")

    def get_openai_client(self, model_alias: str) -> AsyncOpenAI:
        """
        Creates an openai.AsyncOpenAI client instance based on the model's config.

        Args:
            model_alias: The model alias to get client for

        Returns:
            AsyncOpenAI client instance

        Raises:
            ValueError: If model alias is not found or API key is missing
        """
        model_config = self.config_manager.get_model_config(model_alias)

        api_key_env = model_config.get("api_key", "")
        api_key = os.environ.get(api_key_env)

        # Bypass strict API key requirement for local models/Ollama
        if not api_key:
            base_url = model_config.get("base_url", "")
            if (
                api_key_env.upper() in ["OLLAMA", "NONE", "DUMMY", "LOCAL"]
                or "localhost" in base_url
                or "127.0.0.1" in base_url
            ):
                api_key = "dummy-key-for-local"
            else:
                raise ValueError(
                    f"API key not found for model alias '{model_alias}'. "
                    f"Please set the '{api_key_env}' environment variable."
                )

        base_url = model_config.get("base_url")

        return AsyncOpenAI(api_key=api_key, base_url=base_url if base_url else None)

    async def chat_completion(self, prompt: str, stream: bool = False) -> str:
        """
        Send a prompt to the OpenAI API and return the response.

        Args:
            prompt: The prompt to send
            stream: Whether to stream the response

        Returns:
            The model's response
        """
        model_alias = self.config_manager.active_model_alias
        client = self.get_openai_client(model_alias)
        model_config = self.config_manager.get_model_config(model_alias)
        model_name = model_config["name"]
        
        if isinstance(prompt, list):
            messages = copy.deepcopy(prompt)
        else:
            stripped_prompt = prompt.lstrip()
            # Check if prompt starts with a command verb without leading '/' or quotes
            if stripped_prompt and not stripped_prompt.startswith(("/", '"', "'", "“", "‘")):
                match = re.match(r"^([a-zA-Z0-9_]+)", stripped_prompt)
                if match:
                    first_word = match.group(1)
                    # Resolve localized commands to canonical English commands before matching
                    canonical_word = first_word.lower()
                    if hasattr(self, "i18n"):
                        resolved = self.i18n.resolve_command("/" + canonical_word)
                        if resolved.startswith("/"):
                            canonical_word = resolved[1:]
                    if self.matcher.pattern.fullmatch(canonical_word):
                        print(
                            f"Error command verb at beginning:  {first_word} - use escape / sequence or use quotes around command verb to send to LLM"
                        )
                        return ""
            # Replace placeholders in the prompt - returns (text, image_list)
            full_prompt, image_list = self.buffer_manager.replace_placeholders(prompt)

            # Prepare the prompt with file buffer and prompt buffer if available
            if self.buffer_manager.prompt_buffer:
                full_prompt = self.buffer_manager.prompt_buffer + "\n\n" + full_prompt
            if self.buffer_manager.file_buffer:
                full_prompt = f"File:\n{self.buffer_manager.file_buffer}\n\n{full_prompt}"

            # Inject tool context if tool mode is enabled
            if self.tool_mode and self.tool_context:
                full_prompt = self.tool_context + "\n\n" + full_prompt

            # Add code-only instruction if flag is set
            if self.code_only_flag:
                full_prompt = (
                    "Do not explain or describe the code - generate the code requested only. "
                    + full_prompt
                )

            # Prepare messages for chat completion including past chat history
            messages = []
            if self.chat_history:
                for past_p, past_r in self.chat_history:
                    messages.append({"role": "user", "content": past_p})
                    # Strip thinking tags from past assistant responses for token efficiency
                    clean_r = re.sub(r"<think>.*?</think>\s*|<thought>.*?</thought>\s*", "", past_r, flags=re.DOTALL).strip()
                    messages.append({"role": "assistant", "content": clean_r})

            # For multimodal (vision) models, use content array with text + images
            if image_list:
                content_parts = [{"type": "text", "text": full_prompt}]
                content_parts.extend(image_list)
                messages.append({"role": "user", "content": content_parts})
            else:
                messages.append({"role": "user", "content": full_prompt})

        is_nvidia = (
            "nvidia" in model_config.get("base_url", "").lower()
            or "nvidia" in model_name.lower()
        )
        is_reasoning_model = is_nvidia or "qwen" in model_name.lower()

        current_system_message = self.config_manager.system_message
        if self.tool_mode and self.tool_context:
            if isinstance(prompt, list):
                if current_system_message:
                    current_system_message = self.tool_context + "\n\n" + current_system_message
                else:
                    current_system_message = self.tool_context

            # Append agentic prompt instruction whenever tool_mode is enabled
            instr = self.live_agentic_instructions or self.agentic_instructions or self.default_agentic_instructions
            agentic_prompt = f"\n\n{instr}"
            if current_system_message:
                current_system_message += agentic_prompt
            else:
                current_system_message = instr

        if is_reasoning_model and not self.reasoning_mode:
            if current_system_message:
                current_system_message += "\ndetailed thinking off"
            else:
                current_system_message = "detailed thinking off"

        # Handle system prompts for Gemma models
        #print("testing.... gemma4")
        
        is_gemma_4 = "gemma4" in model_name.lower()
        is_old_gemma = "gemma" in model_name.lower() and not is_gemma_4

        # Check for gemma4 thoughtstyle with reasoning off
        if (not self.reasoning_mode and self.thoughtstyle == "gemma4" and is_gemma_4):
            # Append gemma4 specific instructions to existing system prompt
            gemma4_suffix = " disable reasoning and thought. </thought off>"
            if current_system_message:
                current_system_message += gemma4_suffix
            else:
                current_system_message = "you are a helpful assitant." + gemma4_suffix
            # Prefix user prompt with <no thought>
            messages[0]["content"] = f"<no thought> {messages[0]['content']}"

        # Check for nanbeige thoughtstyle
        if self.thoughtstyle == "nanbeige":
            # Wrap user prompt with nanbeige specific formatting
            messages[0]["content"] = f"<think> </think> {messages[0]['content']} response answer only, final answer only. skip thought generation /no_think /response"

        # Check for nanbeige_code thoughtstyle
        if self.thoughtstyle == "nanbeige_code":
            # Wrap user prompt with nanbeige_code specific formatting
            messages[0]["content"] = f"<think></think> {messages[0]['content']}, no comentary or explaination. use response tokens only. code only, code only"

        if getattr(self, 'in_tool_loop', False) and messages:
            for msg in reversed(messages):
                if msg.get("role") == "user":
                    content = msg.get("content", "")
                    if isinstance(content, str) and "Do not output any more tool calls" in content:
                        break
                    reminder = "\n\n(Reminder: If you need to perform additional tool actions, output ONLY the JSON tool call(s) wrapped in ```json and ``` code fences without surrounding conversational text. If you have finished all tool executions, provide your final response in natural language.)"
                    if isinstance(content, str):
                        msg["content"] = content + reminder
                    elif isinstance(content, list):
                        msg["content"].append({"type": "text", "text": reminder})
                    break

        if is_old_gemma:
            # Fallback: Prepend system message to the user message for older Gemma models
            if current_system_message:
                messages[0]["content"] = f"{current_system_message}\n\n{messages[0]['content']}"
        else:
            # Standard behavior: Use the system role (works for gemma-4 and all non-gemma models)
            if current_system_message:
                messages.insert(0, {"role": "system", "content": current_system_message})

        # Apply context limits, auto-truncation, and warnings
        if hasattr(self, "context_limiter"):
            effective_limit = self.context_limiter.context_limit or model_config.get("context_limit")
            if effective_limit:
                total_tokens = self.context_limiter.count_tokens_messages(messages)
                if self.context_limiter.auto_truncate:
                    target_limit = int(effective_limit * (self.context_limiter.truncate_pct / 100.0))
                    if total_tokens > target_limit:
                        messages, did_truncate = self.context_limiter.truncate_messages(messages, effective_limit)
                        if did_truncate:
                            print("[Note: Earlier messages were truncated to fit the context limit.]")
                            total_tokens = self.context_limiter.count_tokens_messages(messages)
                
                warning_msg = self.context_limiter.check_warnings(total_tokens, effective_limit)
                if warning_msg:
                    print(warning_msg)

        # Prepare completion parameters
        temp = (
            self.temperature
            if self.temperature is not None
            else model_config.get("temperature", 0.7)
        )
        kwargs = {
            "model": model_name,
            "messages": messages,
            "temperature": temp,
        }

        # Add optional parameters if defined globally or in model config
        mt = (
            self.config_manager.max_tokens
            if self.config_manager.max_tokens is not None
            else model_config.get("max_tokens")
        )
        if mt is not None:
            kwargs["max_tokens"] = mt

        is_mistral = "mistral.ai" in model_config.get("base_url", "").lower()
        is_openai_official = (
            "api.openai.com" in model_config.get("base_url", "").lower()
        )
        is_google = "googleapis.com" in model_config.get("base_url", "").lower()
        is_bytez = "bytez.com" in model_config.get("base_url", "").lower()

        tp = None if self.top_p in ("off", "none", "disable", False) else (self.top_p if self.top_p is not None else model_config.get("top_p"))
        if tp is not None:
            if is_nvidia:
                kwargs.setdefault("extra_body", {}).setdefault("nvext", {})["top_p"] = (
                    tp
                )
            else:
                kwargs["top_p"] = tp

        fp = None if self.freq_penalty in ("off", "none", "disable", False) else (self.freq_penalty if self.freq_penalty is not None else model_config.get("frequency_penalty"))
        if fp is not None:
            kwargs["frequency_penalty"] = fp

        pp = None if self.pres_penalty in ("off", "none", "disable", False) else (self.pres_penalty if self.pres_penalty is not None else model_config.get("presence_penalty"))
        if pp is not None:
            kwargs["presence_penalty"] = pp

        # Add explicit reasoning control for models that support it (e.g. SiliconFlow Qwen)
        if "qwen" in model_name.lower() and not self.reasoning_mode:
            kwargs.setdefault("extra_body", {})["enable_reasoning"] = False

        # Add reasoning_effort if set (for OpenAI o1/o3, Mistral models with adjustable reasoning)
        # Supported by: OpenAI official API, OpenRouter, Mistral AI API for reasoning models
        # Mistral models: mistral-small-latest, mistral-medium-3.5 (includes mistral-medium-2604)
        # OpenAI models: o1, o3, etc.
        if self.reasoning_effort is not None:
            if is_openai_official or "openrouter" in model_config.get("base_url", "").lower():
                # OpenAI and OpenRouter support reasoning_effort at top level
                kwargs["reasoning_effort"] = self.reasoning_effort
            elif is_mistral:
                # Mistral supports reasoning_effort at top level for reasoning models
                # Check if model name suggests it's a reasoning model
                if any(x in model_name.lower() for x in ["mistral-small-latest", "mistral-medium-3.5", "mistral-medium-2604", "magistral", "devstral"]):
                    kwargs["reasoning_effort"] = self.reasoning_effort

        omit_tk = model_config.get("omit_top_k", False)
        if self.top_k in ("off", "none", "disable", False):
            tk = None
        elif self.top_k is not None:
            tk = self.top_k
        elif not omit_tk:
            tk = model_config.get("top_k")
        else:
            tk = None

        if tk is not None:
            if is_nvidia:
                kwargs.setdefault("extra_body", {}).setdefault("nvext", {})["top_k"] = (
                    tk
                )
            elif (
                not is_mistral
                and not is_openai_official
                and not is_google
                and not is_bytez
            ):
                # Mistral, OpenAI official, Google Gemini, and Bytez APIs reject top_k as an extra input.
                # Only add for other providers (OpenRouter, etc.)
                kwargs.setdefault("extra_body", {})["top_k"] = tk

        # Seed handling
        current_seed = None
        if self.seed_config is not None:
            if self.seed_config == "time":
                current_seed = int(time.time())
            elif (
                isinstance(self.seed_config, tuple) and self.seed_config[0] == "random"
            ):
                current_seed = random.randint(self.seed_config[1], self.seed_config[2])
            else:
                try:
                    current_seed = int(self.seed_config)
                except (ValueError, TypeError):
                    current_seed = None

        if current_seed is not None:
            if is_google or is_bytez:
                # Google Gemini and Bytez endpoints do not support 'seed' and reject it
                print(
                    f"Warning: Seed parameter is not supported by {'Google' if is_google else 'Bytez'} API. Skipping."
                )
            else:
                print(f"Using seed: {current_seed}")
                if is_mistral:
                    # Mistral official API expects 'random_seed' instead of 'seed'
                    kwargs.setdefault("extra_body", {})["random_seed"] = current_seed
                else:
                    kwargs["seed"] = current_seed

        try:
            start_time = time.time()

            if self.trace_raw_payload:
                payload_str = ""
                try:
                    payload_str = json.dumps(kwargs, indent=2)
                except TypeError:
                    payload_str = str(kwargs)
                payload_bytes = payload_str.encode('utf-8')
                size_bytes = len(payload_bytes)
                size_kb = size_bytes / 1024
                est_tokens = max(1, int(size_bytes / 4))
                size_info = f"Size: {size_bytes} bytes ({size_kb:.2f} KB) | Est. Tokens: ~{est_tokens} (industry avg)"

                print("Payload:")
                print("-----------------------------")
                print(payload_str)
                print("---- end of payload ---")
                print(size_info)

                log_content = f"Payload:\n---------------------\n{payload_str}\n---- end of payload ---\n{size_info}"
                self.logging_manager.log_message(log_content)


            # Capture payload for debug mode
            if self.debug_payload_mode:

                import tempfile
                import os
                import subprocess
                
                self.debug_payload_data = kwargs.copy()
                
                # Create a temporary file with the payload
                temp_file = tempfile.NamedTemporaryFile(
                    mode='w+', 
                    suffix='.json', 
                    delete=False,
                    encoding='utf-8'
                )
                
                try:
                    # Write the payload to the temp file
                    json.dump(self.debug_payload_data, temp_file, indent=2)
                    temp_file.flush()
                    
                    print(f"\nPayload captured and saved to: {temp_file.name}")
                    print("Opening in editor...")
                    
                    # Determine the editor to use
                    editor = os.environ.get('EDITOR', 'vi')
                    
                    # Open the file in the editor
                    subprocess.run([editor, temp_file.name])
                    
                    # After editing, read the modified payload
                    with open(temp_file.name, 'r', encoding='utf-8') as f:
                        modified_payload = json.load(f)
                    
                    # Update kwargs with the modified payload
                    kwargs.update(modified_payload)
                    
                    print(f"\nUsing modified payload from: {temp_file.name}")
                    
                except Exception as e:
                    print(f"Error in debug payload mode: {str(e)}")
                    self.debug_payload_mode = False
                finally:
                    # Clean up and reset debug mode
                    temp_file.close()
                    try:
                        os.unlink(temp_file.name)
                    except:
                        pass
                    self.debug_payload_mode = False

            # Clean assistant messages to ensure they are not empty (which causes API 400 error)
            cleaned_messages = []
            for msg in kwargs.get("messages", []):
                if msg.get("role") == "assistant" and not (msg.get("content") or "").strip():
                    cleaned_messages.append({"role": "assistant", "content": " "})
                else:
                    cleaned_messages.append(msg)
            kwargs["messages"] = cleaned_messages

            tps_records = []
            think_tokens_estimate = 0
            regular_tokens_estimate = 0

            if stream:
                kwargs["stream"] = True
                response = await client.chat.completions.create(**kwargs)
                
                # Reset debug response flags in streaming mode (not supported for streams)
                if self.debug_response_mode or self.debug_response_raw:
                    print("\n[DEBUG] Response debugging is only supported in non-streaming mode.")
                    self.debug_response_mode = False
                    self.debug_response_raw = False

                full_reasoning = ""
                full_content = ""
                print("Assistant: ", end="", flush=True)

                buffer = ""
                in_think_block = False
                streaming_tool_calls = {}

                async for chunk in response:
                    chunk_time = time.time()
                    if not chunk.choices:
                        continue
                    delta = chunk.choices[0].delta

                    if getattr(delta, "tool_calls", None):
                        for tc in delta.tool_calls:
                            idx = tc.index if tc.index is not None else 0
                            if idx not in streaming_tool_calls:
                                streaming_tool_calls[idx] = {
                                    "id": None,
                                    "name": "",
                                    "arguments": ""
                                }
                            if tc.id:
                                streaming_tool_calls[idx]["id"] = tc.id
                            if tc.function:
                                if tc.function.name:
                                    streaming_tool_calls[idx]["name"] += tc.function.name
                                if tc.function.arguments:
                                    streaming_tool_calls[idx]["arguments"] += tc.function.arguments

                    reasoning = getattr(
                        delta, "reasoning_content", getattr(delta, "reasoning", None)
                    )
                    if reasoning:
                        # Handle structured content in reasoning field
                        if isinstance(reasoning, list):
                            for item in reasoning:
                                if isinstance(item, dict):
                                    if item.get("type") == "text":
                                        full_content += item.get("text", "")
                                    elif item.get("type") == "thinking":
                                        thinking_text = item.get("thinking", "")
                                        if isinstance(thinking_text, list):
                                            for t in thinking_text:
                                                if isinstance(t, dict):
                                                    full_reasoning += t.get("text", "")
                                                    if self.show_thinking:
                                                        print(f"\033[90m{t.get('text', '')}\033[0m", end="", flush=True)
                                        elif isinstance(thinking_text, str):
                                            full_reasoning += thinking_text
                                            if self.show_thinking:
                                                print(f"\033[90m{thinking_text}\033[0m", end="", flush=True)
                        else:
                            full_reasoning += reasoning
                            think_tokens_estimate += 1
                            if self.trace_tps_perf:
                                tps_records.append((chunk_time, "think", 1))
                            if self.show_thinking:
                                print(f"\033[90m{reasoning}\033[0m", end="", flush=True)

                    if delta.content:
                        content = delta.content
                        # Handle Mistral's structured content (list of dicts) in streaming
                        if isinstance(content, list):
                            # Extract text from structured content with color coding
                            for item in content:
                                if isinstance(item, dict):
                                    if item.get("type") == "text":
                                        text_content = item.get("text", "")
                                        full_content += text_content
                                        print(text_content, end="", flush=True)
                                    elif item.get("type") == "thinking":
                                        thinking_text = item.get("thinking", "")
                                        if isinstance(thinking_text, list):
                                            for t in thinking_text:
                                                if isinstance(t, dict):
                                                    think_content = t.get("text", "")
                                                    full_reasoning += think_content
                                                    if self.show_thinking:
                                                        print(f"\033[90m{think_content}\033[0m", end="", flush=True)
                                        elif isinstance(thinking_text, str):
                                            full_reasoning += thinking_text
                                            if self.show_thinking:
                                                print(f"\033[90m{thinking_text}\033[0m", end="", flush=True)
                            continue  # Skip the rest of the processing for structured content
                        full_content += content

                        if in_think_block or "<think>" in content or "<thought>" in content:
                            think_tokens_estimate += 1
                            if self.trace_tps_perf:
                                tps_records.append((chunk_time, "think", 1))
                        else:
                            regular_tokens_estimate += 1
                            if self.trace_tps_perf:
                                tps_records.append((chunk_time, "regular", 1))

                        buffer += content
                        while buffer:
                            if not in_think_block:
                                think_idx = buffer.find("<think>")
                                thought_idx = buffer.find("<thought>")
                                
                                # Find the earliest opening tag
                                opening_tag = None
                                opening_idx = -1
                                if think_idx != -1 and thought_idx != -1:
                                    opening_idx = min(think_idx, thought_idx)
                                    opening_tag = "think" if think_idx < thought_idx else "thought"
                                elif think_idx != -1:
                                    opening_idx = think_idx
                                    opening_tag = "think"
                                elif thought_idx != -1:
                                    opening_idx = thought_idx
                                    opening_tag = "thought"
                                
                                if opening_idx != -1:
                                    print(buffer[:opening_idx], end="", flush=True)
                                    if self.show_thinking:
                                        if opening_tag == "think":
                                            print("\033[90m<think>", end="", flush=True)
                                        else:
                                            print("\033[90m<thought>", end="", flush=True)
                                    if opening_tag == "think":
                                        buffer = buffer[opening_idx + len("<think>") :]
                                    else:
                                        buffer = buffer[opening_idx + len("<thought>") :]
                                    in_think_block = True
                                else:
                                    match_len = 0
                                    # Check for partial <think> tag
                                    for i in range(len("<think>") - 1, 0, -1):
                                        if buffer.endswith("<think>"[:i]):
                                            match_len = i
                                            break
                                    # Check for partial <thought> tag
                                    if match_len == 0:
                                        for i in range(len("<thought>") - 1, 0, -1):
                                            if buffer.endswith("<thought>"[:i]):
                                                match_len = i
                                                break
                                    if match_len > 0:
                                        print(buffer[:-match_len], end="", flush=True)
                                        buffer = buffer[-match_len:]
                                        break
                                    else:
                                        print(buffer, end="", flush=True)
                                        buffer = ""
                            else:
                                end_idx = buffer.find("</think>")
                                end_thought_idx = buffer.find("</thought>")
                                
                                # Find the earliest closing tag
                                closing_tag = None
                                closing_idx = -1
                                if end_idx != -1 and end_thought_idx != -1:
                                    closing_idx = min(end_idx, end_thought_idx)
                                    closing_tag = "think" if end_idx < end_thought_idx else "thought"
                                elif end_idx != -1:
                                    closing_idx = end_idx
                                    closing_tag = "think"
                                elif end_thought_idx != -1:
                                    closing_idx = end_thought_idx
                                    closing_tag = "thought"
                                
                                if closing_idx != -1:
                                    if self.show_thinking:
                                        if closing_tag == "think":
                                            print(
                                                buffer[:closing_idx] + "</think>\033[0m",
                                                end="",
                                                flush=True,
                                            )
                                        else:
                                            print(
                                                buffer[:closing_idx] + "</thought>\033[0m",
                                                end="",
                                                flush=True,
                                            )
                                    if closing_tag == "think":
                                        buffer = buffer[closing_idx + len("</think>") :]
                                    else:
                                        buffer = buffer[closing_idx + len("</thought>") :]
                                    in_think_block = False
                                else:
                                    match_len = 0
                                    # Check for partial </think> tag
                                    for i in range(len("</think>") - 1, 0, -1):
                                        if buffer.endswith("</think>"[:i]):
                                            match_len = i
                                            break
                                    # Check for partial </thought> tag
                                    if match_len == 0:
                                        for i in range(len("</thought>") - 1, 0, -1):
                                            if buffer.endswith("</thought>"[:i]):
                                                match_len = i
                                                break
                                    if match_len > 0:
                                        if self.show_thinking:
                                            print(
                                                buffer[:-match_len], end="", flush=True
                                            )
                                        buffer = buffer[-match_len:]
                                        break
                                    else:
                                        if self.show_thinking:
                                            print(buffer, end="", flush=True)
                                        buffer = ""

                if buffer:
                    if in_think_block and self.show_thinking:
                        print(buffer + "\033[0m", end="", flush=True)
                    elif not in_think_block:
                        print(buffer, end="", flush=True)
                elif in_think_block and self.show_thinking:
                    print("\033[0m", end="", flush=True)
                print()  # New line after streaming
                
                if streaming_tool_calls:
                    tool_calls_list = []
                    for idx in sorted(streaming_tool_calls.keys()):
                        tc_data = streaming_tool_calls[idx]
                        tc_name = tc_data["name"]
                        tc_args = tc_data["arguments"]
                        if tc_name:
                            if "." in tc_name:
                                tc_name = tc_name.split(".")[-1]
                            if isinstance(tc_args, str):
                                try:
                                    tc_args = json.loads(tc_args)
                                except Exception:
                                    pass
                            tool_calls_list.append({
                                "tool": tc_name,
                                "arguments": tc_args
                            })
                    if tool_calls_list:
                        if len(tool_calls_list) == 1:
                            tool_json_block = f"```json\n{json.dumps(tool_calls_list[0])}\n```"
                        else:
                            tool_json_block = f"```json\n{json.dumps(tool_calls_list)}\n```"
                        print(tool_json_block)
                        if full_content:
                            full_content += "\n\n" + tool_json_block
                        else:
                            full_content = tool_json_block
                
                # Build the standardized full response
                if full_reasoning:
                    full_response = f"<think>{full_reasoning}</think>\n\n{full_content}"
                else:
                    full_response = full_content
            else:
                max_retries = 3
                retry_count = 0
                while retry_count < max_retries:
                    response = await client.chat.completions.create(**kwargs)
                    if not getattr(response, "choices", None):
                        is_transient = False
                        code = None
                        try:
                            if hasattr(response, "model_dump"):
                                err_dict = response.model_dump().get("error", {})
                                code = err_dict.get("code")
                                msg_lower = str(err_dict.get("message", "")).lower()
                                if code in (502, 503, 504, 429) or "timeout" in msg_lower or "limit" in msg_lower:
                                    is_transient = True
                        except Exception:
                            pass
                        
                        if is_transient and retry_count < max_retries - 1:
                            retry_count += 1
                            sleep_time = 2 ** retry_count
                            print(f"Transient error {code or 'timeout'} encountered. Retrying in {sleep_time}s...")
                            await asyncio.sleep(sleep_time)
                            continue
                    break

                if not getattr(response, "choices", None):
                    error_info = ""
                    try:
                        if hasattr(response, "model_dump"):
                            error_info = json.dumps(response.model_dump(), indent=2)
                        else:
                            error_info = str(response)
                    except Exception:
                        error_info = str(response)
                    raise ValueError(f"API response did not return any choices. Response details: {error_info}")
                message = response.choices[0].message
                if self.debug_response_mode:

                    print("\n--- DEBUG RESPONSE (JSON) ---")
                    try:
                        if hasattr(response, "model_dump"):
                            print(json.dumps(response.model_dump(), indent=2))
                        elif hasattr(response, "model_dump_json"):
                            print(response.model_dump_json(indent=2))
                        else:
                            print(json.dumps(response, indent=2, default=str))
                    except Exception as e:
                        print(f"Error dumping JSON: {e}")
                        print(response)
                    print("--- END DEBUG RESPONSE ---\n")
                    self.debug_response_mode = False
                elif self.debug_response_raw:
                    print("\n--- DEBUG RESPONSE (RAW) ---")
                    print(response)
                    print("--- END DEBUG RESPONSE ---\n")
                    self.debug_response_raw = False
                content = message.content or ""
                if hasattr(message, "tool_calls") and message.tool_calls:
                    tool_calls_list = []
                    for tc in message.tool_calls:
                        tc_name = tc.function.name
                        tc_args = tc.function.arguments
                        if isinstance(tc_args, str):
                            try:
                                tc_args = json.loads(tc_args)
                            except Exception:
                                pass
                        tool_calls_list.append({
                            "tool": tc_name,
                            "arguments": tc_args
                        })
                    if tool_calls_list:
                        if len(tool_calls_list) == 1:
                            content = f"```json\n{json.dumps(tool_calls_list[0])}\n```"
                        else:
                            content = f"```json\n{json.dumps(tool_calls_list)}\n```"
                reasoning = (
                    getattr(
                        message,
                        "reasoning_content",
                        getattr(message, "reasoning", None),
                    )
                    or ""
                )

                full_response = ""
                if reasoning:
                    if self.show_thinking:
                        print(f"\033[90m{reasoning}\033[0m")
                    # Standardize raw reasoning fields into standard <think> tags in history
                    full_response += f"<think>{reasoning}</think>\n\n"

                # Handle Mistral's structured content (list of dicts with type: 'thinking' or 'text')
                if isinstance(content, list):
                    # Extract text content from the list
                    text_parts = []
                    for item in content:
                        if isinstance(item, dict):
                            if item.get("type") == "text":
                                text_parts.append(item.get("text", ""))
                            elif item.get("type") == "thinking" and self.show_thinking:
                                thinking_text = item.get("thinking", "")
                                if isinstance(thinking_text, list):
                                    # Handle nested thinking list
                                    for t in thinking_text:
                                        if isinstance(t, dict):
                                            text_parts.append(t.get("text", ""))
                                elif isinstance(thinking_text, str):
                                    text_parts.append(thinking_text)
                    content = "".join(text_parts)

                full_response += content

                if not self.show_thinking:
                    print_content = re.sub(
                        r"<think>.*?</think>\s*|<thought>.*?</thought>\s*", "", content, flags=re.DOTALL
                    )
                else:
                    print_content = re.sub(
                        r"(<think>.*?</think>|<thought>.*?</thought>)",
                        r"\033[90m\1\033[0m",
                        content,
                        flags=re.DOTALL,
                    )

                if not print_content.strip() and not (reasoning and self.show_thinking):
                    print("Warning: Received an empty response from the model.")
                elif print_content.strip():
                    print(print_content)

            # Calculate and display metrics
            elapsed_time = time.time() - start_time
            print(f"\nExecution time: {elapsed_time:.2f} seconds")

            out_tokens = 0
            # Reset reasoning token count for this completion; updated below if
            # the provider exposes reasoning token usage.
            self.last_reasoning_tokens = 0
            if hasattr(response, "usage") and response.usage:
                out_tokens = response.usage.completion_tokens
                print(
                    f"Input tokens: {response.usage.prompt_tokens}, Output tokens: {out_tokens}"
                )
                # Capture reasoning token count if the provider reports it
                # (e.g. OpenAI completion_tokens_details.reasoning_tokens).
                try:
                    details = getattr(response.usage, "completion_tokens_details", None)
                    if details is not None:
                        self.last_reasoning_tokens = int(getattr(details, "reasoning_tokens", 0) or 0)
                except Exception:
                    pass

            if think_tokens_estimate + regular_tokens_estimate > 0 and out_tokens > 0:
                ratio_think = think_tokens_estimate / (
                    think_tokens_estimate + regular_tokens_estimate
                )
                think_t = int(out_tokens * ratio_think)
                reg_t = out_tokens - think_t
            else:
                think_t = think_tokens_estimate
                reg_t = regular_tokens_estimate

            if self.trace_tps:
                tps_think = think_t / elapsed_time if elapsed_time > 0 else 0
                tps_reg = reg_t / elapsed_time if elapsed_time > 0 else 0
                tps_total = (think_t + reg_t) / elapsed_time if elapsed_time > 0 else 0
                print(
                    f"TPS (Total): {tps_total:.2f} (Think: {tps_think:.2f}, Regular: {tps_reg:.2f})"
                )

            if self.trace_tps_perf and tps_records:
                buckets = {}
                for t, typ, count in tps_records:
                    sec_offset = int(t - start_time)
                    if sec_offset not in buckets:
                        buckets[sec_offset] = {"think": 0, "regular": 0}
                    buckets[sec_offset][typ] += count

                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                csv_filename = f"tps+{timestamp}.csv"
                try:
                    import csv

                    with open(csv_filename, "w", newline="") as csvfile:
                        writer = csv.writer(csvfile, quoting=csv.QUOTE_ALL)
                        writer.writerow(
                            ["Second", "Think_Tokens", "Regular_Tokens", "Total_Tokens"]
                        )
                        for sec in sorted(buckets.keys()):
                            th = buckets[sec]["think"]
                            rg = buckets[sec]["regular"]
                            writer.writerow([sec, th, rg, th + rg])
                    print(f"TPS performance saved to '{csv_filename}'")
                except Exception as e:
                    print(f"Error saving TPS performance: {e}")

            # Log user entry with datetime and model info
            if self.logging_manager.logging_active:
                current_time = self.logging_manager.format_datetime(datetime.now())
                self.logging_manager.log_message(f"Datetime: {current_time}")
                self.logging_manager.log_message(f"Model: {model_alias} ({model_name})")
                self.logging_manager.log_message(f"User: {prompt}")

            if not self.in_tool_loop:
                self.chat_history.append((prompt, full_response))
                if self.session_mode != "off":
                    self.append_session_turn(prompt, full_response)
                if self.tool_auto and self.extract_tool_calls(full_response):
                    print("Tool call detected in response. Auto-launching agentic tool loop...")
                    await self.execute_tool_loop(max_turns=self.max_turns)
                    if self.chat_history:
                        _, final_resp = self.chat_history[-1]
                        return final_resp

            # Log assistant entry with completion datetime and token count
            if self.logging_manager.logging_active:
                input_tokens = (
                    response.usage.prompt_tokens
                    if hasattr(response, "usage")
                    else "N/A"
                )
                output_tokens = (
                    response.usage.completion_tokens
                    if hasattr(response, "usage")
                    else "N/A"
                )
                self.logging_manager.log_message(
                    f"\nExecution time: {elapsed_time:.2f} seconds"
                )
                self.logging_manager.log_message(
                    f"Number of tokens: Input {input_tokens}, Output {output_tokens}"
                )
                self.logging_manager.log_message(f"Assistant: {full_response}\n")

            return full_response
        except Exception as e:
            import traceback
            traceback.print_exc()
            error_msg = f"Error during chat completion: {str(e)}"
            print(error_msg)
            if self.logging_manager.logging_active:
                self.logging_manager.log_message(error_msg)
            return f"Error: {str(e)}"

    async def execute_script_command(
        self, command: str, original_handler: Callable[[str], Union[bool, str]]
    ) -> bool:
        """
        Execute a command within a script context.

        Args:
            command: The command to execute
            original_handler: The original command handler function

        Returns:
            True if the command was handled, False otherwise
        """
        # Handle script-specific commands
        # Handle macro calls
        if command.lstrip().startswith("%"):
            try:
                expanded_command = self.process_macro_line(command)
                if expanded_command.startswith("ERROR:"):
                    print(expanded_command)
                    return True
                else:
                    # Process the expanded command as if it was typed by user
                    print(f"Expanded macro: {expanded_command}")
                    # Execute the expanded command
                    handled = await self.execute_script_command(
                        expanded_command, original_handler
                    )
                    return handled
            except Exception as e:
                print(f"Error processing macro: {e}")
                return True

        # Handle script-specific commands (supporting multiline set)
        if command.lstrip().startswith("set "):
            old_user_write = getattr(self.buffer_manager.script_vars, '_is_user_write', False)
            if hasattr(self.buffer_manager.script_vars, '_is_user_write'):
                self.buffer_manager.script_vars._is_user_write = True
            try:
                set_stripped = self.buffer_manager.replace_placeholders_legacy(command.lstrip())
                # Use regex to parse "set var = value" supporting multiline (. matches anything with re.S)
                match = re.match(r"set\s+([a-zA-Z_]\w*(?:\[\])?)\s*=\s*(.*)", set_stripped, re.S)
                if match:
                    var_name = match.group(1)
                    var_value = match.group(2).strip()
                    
                    # Handle quoted values
                    if var_value.startswith('"') or var_value.startswith("'"):
                        q = var_value[0]
                        # Search for ending quote and error on escape characters as requested
                        closing_idx = -1
                        for i in range(1, len(var_value)):
                            if var_value[i] == "\\":
                                print(f"Error: Escape character '\' is not allowed in set command for '{var_name}'.")
                                return True
                            if var_value[i] == q:
                                closing_idx = i
                                break
                        
                        if closing_idx != -1:
                            var_value = var_value[1:closing_idx]
                        else:
                            print(f"Error: No closing quote found for variable '{var_name}'.")
                            return True
                    else:
                        # Non-quoted value
                        var_value = var_value.strip()

                    # Replace variables in the value before storing (supporting subscripts and unbraced names)
                    processed_value = self.buffer_manager.replace_placeholders_legacy(var_value)
                    
                    # Check if it is an array
                    if var_name.endswith("[]"):
                        clean_var_name = var_name[:-2]
                        val_str = var_value.lstrip().lstrip('=').strip()
                        try:
                            string_list = self.parse_array_value(val_str)
                        except Exception as e:
                            print(f"Error: Invalid array format for '{clean_var_name}': {e}")
                            return True
                        
                        try:
                            self.buffer_manager.script_vars[clean_var_name] = string_list
                            print(f"Variable '{clean_var_name}' set to array.")
                        except ValueError as e:
                            print(f"Error: {e}")
                        return True
                    else:
                        try:
                            self.buffer_manager.script_vars[var_name.strip()] = processed_value
                        except ValueError as e:
                            print(f"Error: {e}")
                        return True
                else:
                    print("Invalid set command format. Usage: set <name> = <value>")
                    return True
            except Exception as e:
                print(f"Error parsing set command: {e}")
                return True
            finally:
                if hasattr(self.buffer_manager.script_vars, '_is_user_write'):
                    self.buffer_manager.script_vars._is_user_write = old_user_write

        # Handle local variable declarations
        if command.lstrip().startswith("local "):
            old_user_write = getattr(self.buffer_manager.script_vars, '_is_user_write', False)
            if hasattr(self.buffer_manager.script_vars, '_is_user_write'):
                self.buffer_manager.script_vars._is_user_write = True
            try:
                local_stripped = command.lstrip()
                match = re.match(r"local\s+([a-zA-Z_]\w*)\s*(?:=\s*(.*))?", local_stripped, re.S)
                if match:
                    var_name = match.group(1)
                    raw_val = match.group(2)
                    var_value = raw_val.strip() if raw_val is not None else ""
                    
                    if (var_value.startswith('"') and var_value.endswith('"')) or (var_value.startswith("'") and var_value.endswith("'")):
                        var_value = var_value[1:-1]
                    
                    processed_value = self.buffer_manager.replace_placeholders_legacy(var_value) if var_value else ""
                    
                    if self.active_proc_stack:
                        top_frame = self.active_proc_stack[-1]
                        saved_vars = top_frame["saved_vars"]
                        if var_name not in saved_vars:
                            exists = var_name in self.buffer_manager.script_vars
                            orig_val = self.buffer_manager.script_vars.get(var_name) if exists else None
                            saved_vars[var_name] = (exists, orig_val)
                        top_frame["local_vars"].add(var_name)
                    
                    try:
                        self.buffer_manager.script_vars[var_name] = processed_value
                    except ValueError as e:
                        print(f"Error: {e}")
                    return True
                else:
                    print("Invalid local command format. Usage: local <name> = <value>")
                    return True
            except Exception as e:
                print(f"Error parsing local command: {e}")
                return True
            finally:
                if hasattr(self.buffer_manager.script_vars, '_is_user_write'):
                    self.buffer_manager.script_vars._is_user_write = old_user_write

        # Handle macro definitions (supporting multiline def)
        if command.lstrip().startswith("def "):
            try:
                # Use Parsley to parse the macro definition
                # We need to strip leading whitespace for Parsley
                definition_line = command.lstrip()
                parsed = self.definition_grammar(definition_line).macro_def()
                name, params, template = parsed
                self.macros[name] = {'params': params, 'template': template}
                print(f"Defined macro: {name} with {len(params)} parameters")
                return True
            except Exception as e:
                # If Parsley fails, it might be because the template spans multiple lines
                # and our Parsley grammar for string is simple.
                # However, for now let's just report the error.
                print(f"Error defining macro: {e}")
                return True

        # Replace variables in the command (supporting subscripts and unbraced names)
        # We do not replace variables on the command line for /setvar and /calc as they handle substitution internally
        if command.lstrip().startswith("/setvar") or command.lstrip().startswith("/calc") or command.lstrip().startswith("/str_search"):
            processed_command = command
        else:
            processed_command = self.buffer_manager.replace_placeholders_legacy(command)
        
        # Strip whitespace for command detection (used by multiple handlers)
        stripped_command = processed_command.lstrip()

        # Handle wait command
        if stripped_command.startswith("wait "):
            try:
                _, seconds = stripped_command.split(maxsplit=1)
                await asyncio.sleep(float(seconds))
                return True
            except ValueError:
                print("Invalid wait command. Usage: wait <seconds>")
                return True

        # Handle break command (exits foreach loop early)
        if stripped_command == "break":
            raise LoopBreak()

        # Handle if-then commands
        if stripped_command.startswith("if "):
            try:
                # Use regex to split by whitespace-surrounded "then"
                if " then " in stripped_command:
                    # Find the first " then " to split correctly.
                    parts = re.split(r"\s+then\s+", stripped_command[3:], maxsplit=1)
                    if len(parts) < 2:
                        print("Invalid if command format. Usage: if <condition> then <command>")
                        return True
                    
                    condition_str = parts[0].strip()
                    then_command = parts[1].strip()
                    
                    # Strip optional outer quotes from condition
                    if condition_str.startswith('"') and condition_str.endswith('"'):
                        condition_str = condition_str[1:-1].strip()
                    elif condition_str.startswith("'") and condition_str.endswith("'"):
                        condition_str = condition_str[1:-1].strip()
                    
                    # Handle "not" prefix
                    is_negated = False
                    if condition_str.startswith("not "):
                        is_negated = True
                        condition_str = condition_str[4:].strip()
                    
                    condition_met = False
                    
                    # Check for comparison operators (order matters: >= and <= before > and <)
                    def _parse_numeric(val_str):
                        """Try to parse a string as a float. Returns (float, True) or (None, False)."""
                        try:
                            return float(val_str), True
                        except (ValueError, TypeError):
                            return None, False

                    if " >= " in condition_str:
                        left, right = condition_str.split(" >= ", 1)
                        left = left.strip().strip("\"'")
                        right = right.strip().strip("\"'")
                        left_num, left_ok = _parse_numeric(left)
                        right_num, right_ok = _parse_numeric(right)
                        if not left_ok or not right_ok:
                            print(f"Error: Cannot compare non-numeric values with >= ('{left}' and/or '{right}' are not numbers)")
                            return True
                        condition_met = (left_num >= right_num)
                    elif " <= " in condition_str:
                        left, right = condition_str.split(" <= ", 1)
                        left = left.strip().strip("\"'")
                        right = right.strip().strip("\"'")
                        left_num, left_ok = _parse_numeric(left)
                        right_num, right_ok = _parse_numeric(right)
                        if not left_ok or not right_ok:
                            print(f"Error: Cannot compare non-numeric values with <= ('{left}' and/or '{right}' are not numbers)")
                            return True
                        condition_met = (left_num <= right_num)
                    elif " > " in condition_str:
                        left, right = condition_str.split(" > ", 1)
                        left = left.strip().strip("\"'")
                        right = right.strip().strip("\"'")
                        left_num, left_ok = _parse_numeric(left)
                        right_num, right_ok = _parse_numeric(right)
                        if not left_ok or not right_ok:
                            print(f"Error: Cannot compare non-numeric values with > ('{left}' and/or '{right}' are not numbers)")
                            return True
                        condition_met = (left_num > right_num)
                    elif " < " in condition_str:
                        left, right = condition_str.split(" < ", 1)
                        left = left.strip().strip("\"'")
                        right = right.strip().strip("\"'")
                        left_num, left_ok = _parse_numeric(left)
                        right_num, right_ok = _parse_numeric(right)
                        if not left_ok or not right_ok:
                            print(f"Error: Cannot compare non-numeric values with < ('{left}' and/or '{right}' are not numbers)")
                            return True
                        condition_met = (left_num < right_num)
                    elif " == " in condition_str:
                        left, right = condition_str.split(" == ", 1)
                        # Strip operand quotes
                        left = left.strip().strip("\"'")
                        right = right.strip().strip("\"'")
                        condition_met = (left == right)
                    elif " != " in condition_str:
                        left, right = condition_str.split(" != ", 1)
                        left = left.strip().strip("\"'")
                        right = right.strip().strip("\"'")
                        condition_met = (left != right)
                    else:
                        # Truthy/Falsy check
                        val = condition_str.lower()
                        if val in ["true", "1", "yes", "on"]:
                            condition_met = True
                        elif val in ["false", "0", "no", "off", ""]:
                            condition_met = False
                        else:
                            # Direct check of variable name if it wasn't replaced
                            if condition_str in self.buffer_manager.script_vars:
                                var_val = self.buffer_manager.script_vars[condition_str].lower()
                                condition_met = var_val in ["true", "1", "yes", "on"]
                            else:
                                # Non-empty string is truthy
                                condition_met = bool(condition_str)
                    
                    if is_negated:
                        condition_met = not condition_met
                        
                    if condition_met:
                        return await self.execute_script_command(
                            then_command, original_handler
                        )
                    else:
                        return True  # Handled but skipped
            except LoopBreak:
                raise
            except Exception as e:
                print(f"Error evaluating if condition: {e}")
                return True
            
            # If we reached here without matching a 'then', it's still an if command but invalid
            print("Invalid if command: missing 'then' or incorrect format.")
            return True
        # For other commands, use the original handler
        if processed_command.startswith("/"):
            # The original_handler (handle_escape_command) is now async, so we must await it.
            result = await original_handler(processed_command)
            if result == "EXECUTE_PROMPT":
                # This means a /prompt command was executed and confirmed.
                # The prompt buffer is already set by handle_escape_command.
                # We need to trigger the chat completion here.
                # Use the prompt buffer directly, then clear it to avoid duplication
                temp_prompt = self.buffer_manager.prompt_buffer
                self.buffer_manager.prompt_buffer = ""
                response = await self.chat_completion(
                    temp_prompt, stream=self.streaming_enabled
                )
                self.logging_manager.log_message(
                    f"User: {temp_prompt}\nAssistant: {response}\n"
                )
                self.buffer_manager.prompt_buffer = (
                    ""  # Clear the buffer after execution
                )
                return True  # Handled
            return (
                result if isinstance(result, bool) else False
            )  # Return boolean indicating if handled

        # If not a command, treat as chat input
        if self.script_context:
            response = await self.chat_completion(
                processed_command, stream=self.streaming_enabled
            )
            self.logging_manager.log_message(
                f"User: {processed_command}\nAssistant: {response}\n"
            )
            return True

        # Check if input looks like a command keyword but was not recognized
        stripped = command.strip()
        script_keywords = ['set', 'if', 'wait', 'def', '%', '#', 'local', 'defproc', 'endproc', 'foreach', 'endfor']
        
        if stripped:
            first_word = stripped.split()[0] if stripped.split() else stripped
            if first_word.lower() in script_keywords:
                if first_word.lower() == 'set':
                    print("Invalid set command format. Usage: set <name> = <value>")
                elif first_word.lower() == 'if':
                    print("Invalid if command format. Usage: if <condition> then <command>")
                elif first_word.lower() == 'wait':
                    print("Invalid wait command. Usage: wait <seconds>")
                elif first_word.lower() == 'def':
                    print("Invalid def command. Usage: def <name>(<params>) <template>")
                elif first_word.lower() == 'local':
                    print("Invalid local command format. Usage: local <name> = <value>")
                elif first_word.lower() == 'defproc':
                    print("Invalid defproc command. Usage: defproc <name>(<params>)")
                elif first_word.lower() == 'endproc':
                    print("Unexpected endproc keyword.")
                elif first_word.lower() == 'foreach':
                    print("Invalid foreach command format. Usage: foreach <item_var> in <array_var>")
                elif first_word.lower() == 'endfor':
                    print("Unexpected endfor keyword.")
                elif first_word.lower() == '%':
                    print("Invalid macro call. Usage: %<macro_name>(<args>)")
                elif first_word.lower() == '#':
                    print("Invalid comment. Usage: # <comment text>")
                return True

        return False

    def split_commands(self, text: str) -> list[str]:
        """Split a command string by semicolon (;), respecting quotes and comments."""
        commands_list = []
        current_command = []
        in_quotes = False
        quote_char = None
        
        i = 0
        while i < len(text):
            char = text[i]
            
            if in_quotes:
                if char == quote_char:
                    in_quotes = False
                    quote_char = None
                    current_command.append(char)
                else:
                    current_command.append(char)
            else:
                if char == "#":
                    # Comment till end of string
                    break
                
                if char in ('"', "'"):
                    is_start_of_token = (i == 0 or text[i-1].isspace() or text[i-1] in ('=', ',', '(', '{', '[', ':', '|', '&'))
                    if is_start_of_token:
                        in_quotes = True
                        quote_char = char
                        current_command.append(char)
                    else:
                        current_command.append(char)
                elif char == ";":
                    if i + 1 < len(text) and text[i+1] == ";":
                        cmd = "".join(current_command).strip()
                        if cmd:
                            commands_list.append(cmd)
                        commands_list.append(";;")
                        current_command = []
                        i += 1
                        continue
                    else:
                        cmd = "".join(current_command).strip()
                        if cmd:
                            commands_list.append(cmd)
                        current_command = []
                else:
                    current_command.append(char)
            i += 1
            
        cmd = "".join(current_command).strip()
        if cmd:
            commands_list.append(cmd)
            
        return commands_list

    async def execute_line(self, line: str) -> None:
        """Executes a single line of input, splitting by semicolon if it starts with '/'."""
        if line.startswith("/"):
            commands = self.split_commands(line)
            for cmd in commands:
                cmd = cmd.strip()
                if not cmd:
                    continue
                if cmd.startswith("/"):
                    cmd = self.i18n.translate_command_string(cmd)
                    if not (cmd.lstrip().startswith("/setvar") or cmd.lstrip().startswith("/calc") or cmd.lstrip().startswith("/str_search")):
                        cmd = self.buffer_manager.replace_placeholders_legacy(cmd)
                    result = await self.handle_escape_command(cmd)
                    if result == "EXECUTE_PROMPT":
                        temp_prompt = self.buffer_manager.prompt_buffer
                        self.buffer_manager.prompt_buffer = ""
                        await self.chat_completion(
                            temp_prompt, stream=self.streaming_enabled
                        )
                        self.buffer_manager.prompt_buffer = ""
                else:
                    await self.chat_completion(cmd, stream=self.streaming_enabled)
        else:
            # Handle procedure definitions for interactive input
            if line.lstrip().startswith("defproc ") or line.strip() == "defproc":
                await self.get_proc_definition_input(line)
                return

            # Handle foreach loops for interactive input
            if line.lstrip().startswith("foreach ") or line.strip() == "foreach":
                await self.get_foreach_input(line)
                return

            # Handle macro definitions for regular prompts
            if line.lstrip().startswith("def "):
                try:
                    definition_line = line.lstrip()
                    parsed = self.definition_grammar(definition_line).macro_def()
                    name, params, template = parsed
                    self.macros[name] = {"params": params, "template": template}
                    print(f"Defined macro: {name} with {len(params)} parameters")
                    return
                except Exception:
                    pass

            # Handle macro expansion for regular prompts
            if line.lstrip().startswith("%"):
                expanded_prompt = self.process_macro_line(line)
                if expanded_prompt.startswith("ERROR:"):
                    print(expanded_prompt)
                    return
                else:
                    print(f"Expanded macro: {expanded_prompt}")
                    line = expanded_prompt

            await self.chat_completion(
                line, stream=self.streaming_enabled
            )

    async def get_proc_definition_input(self, header_line: str) -> None:
        """Get procedure definition input interactively from the user."""
        m = re.match(r"defproc\s+([a-zA-Z_]\w*)(?:\(([^)]*)\))?", header_line.lstrip())
        if not m:
            print("Invalid defproc format. Usage: defproc name(p1, p2)")
            return
        
        proc_name = m.group(1)
        params_str = m.group(2)
        params = [p.strip() for p in params_str.split(',')] if params_str else []
        
        print(f"Entering procedure definition for '{proc_name}'. Enter commands (type 'endproc' on a line by itself to finish):")
        body_lines = []
        while True:
            if getattr(self, 'interrupt_requested', False):
                print("\nInterrupted. Cancelling procedure definition...")
                self.control_c_count = 0
                self.interrupt_requested = False
                return
            
            try:
                line = input("(proc)> ")
            except EOFError:
                break
            
            stripped = line.strip()
            if stripped == "endproc":
                break
            if line.lstrip().startswith("defproc ") or stripped == "defproc":
                print("Error: Nested defproc is not allowed.")
                return
            body_lines.append(line)
        
        self.procedures[proc_name] = {"params": params, "body": body_lines}
        print(f"Procedure '{proc_name}' defined with params: {params}")

    def evaluate_foreach_iterable(self, expr_str: str) -> Tuple[Optional[Any], Optional[str]]:
        """
        Evaluates a foreach iterable target expression (variable name, range generator, or lines generator).
        Returns a tuple of (iterable_object_or_list, error_message).
        """
        raw_expr = expr_str.strip()

        # 1. Range Generator: range(start:end[:step]) or range(start..end) or range(count)
        m_range = re.match(r"^\s*range\s*\(\s*(.+)\s*\)\s*$", raw_expr, re.IGNORECASE)
        if m_range:
            inner_str = m_range.group(1).strip()
            resolved_inner = self.buffer_manager.replace_placeholders_legacy(inner_str)
            
            if ":" in resolved_inner or ".." in resolved_inner:
                sep = ":" if ":" in resolved_inner else ".."
                parts = [p.strip() for p in resolved_inner.split(sep)]
                try:
                    if len(parts) == 2:
                        start = int(parts[0])
                        end = int(parts[1])
                        step = 1 if start <= end else -1
                    elif len(parts) == 3 and sep == ":":
                        start = int(parts[0])
                        end = int(parts[1])
                        step = int(parts[2])
                    else:
                        return None, f"Invalid range format: '{expr_str}'"
                    
                    end_inclusive = (end + 1) if step > 0 else (end - 1)
                    return range(start, end_inclusive, step), None
                except ValueError:
                    return None, f"Invalid numeric bounds in range expression: '{expr_str}'"
            else:
                try:
                    count = int(resolved_inner)
                    if count < 1:
                        return range(0), None
                    return range(1, count + 1), None
                except ValueError:
                    return None, f"Invalid numeric count in range expression: '{expr_str}'"

        # 2. Lines Generator: lines(text_var) or lines({filebank1})
        m_lines = re.match(r"^\s*lines\s*\(\s*(.+)\s*\)\s*$", raw_expr, re.IGNORECASE)
        if m_lines:
            inner_str = m_lines.group(1).strip()
            content = None
            if inner_str in self.buffer_manager.script_vars:
                content = self.buffer_manager.script_vars[inner_str]
            elif inner_str in self.buffer_manager.file_banks:
                content = self.buffer_manager.file_banks[inner_str]
            elif inner_str == "FILE_BUFFER":
                content = self.buffer_manager.file_buffer
            else:
                content = self.buffer_manager.replace_placeholders_legacy(inner_str)

            if isinstance(content, list):
                lines_list = [line for item in content for line in str(item).splitlines()]
                return lines_list, None
            elif isinstance(content, str):
                return content.splitlines(), None
            else:
                return [], None

        # 3. Standard Array / Variable lookup: my_array
        array_data = self.buffer_manager.script_vars.get(raw_expr)
        if isinstance(array_data, str):
            try:
                array_data = self.parse_array_value(array_data)
            except Exception:
                pass

        if isinstance(array_data, list):
            return array_data, None

        return None, f"Warning: '${raw_expr}' is not a valid array or iterable for foreach loop. Skipping."

    async def get_foreach_input(self, header_line: str) -> None:
        """Get foreach loop input interactively from the user."""
        m = re.match(r"^\s*foreach\s+([a-zA-Z_]\w*)\s+in\s+(.+)$", header_line.strip())
        if not m:
            print("Invalid foreach format. Usage: foreach <item_var> in <array_var|range(...)|lines(...)>")
            return
        
        item_var = m.group(1)
        target_expr = m.group(2).strip()
        
        print(f"Entering foreach loop for '{item_var}' in '{target_expr}'. Enter commands (type 'endfor' on a line by itself to finish):")
        buffer = []
        depth = 1
        
        while True:
            if getattr(self, 'interrupt_requested', False):
                print("\nInterrupted. Cancelling foreach loop...")
                self.control_c_count = 0
                self.interrupt_requested = False
                return
            
            try:
                line = input("(for)> ")
            except EOFError:
                break
            
            stripped = line.strip()
            if stripped == "endfor":
                depth -= 1
                if depth == 0:
                    break
                buffer.append(line)
            elif re.match(r"^\s*foreach\s+([a-zA-Z_]\w*)\s+in\s+(.+)$", stripped):
                depth += 1
                buffer.append(line)
            else:
                buffer.append(line)
        
        await self.execute_foreach_block(item_var, target_expr, buffer)

    async def execute_foreach_block(self, item_var: str, target_expr: str, buffer: List[str]) -> None:
        """Executes a captured foreach loop block over an array variable or generator expression."""
        iterable, err = self.evaluate_foreach_iterable(target_expr)
        if iterable is None:
            if err:
                print(err)
            return

        exists = item_var in self.buffer_manager.script_vars
        orig_val = self.buffer_manager.script_vars.get(item_var) if exists else None
        
        old_user_write = getattr(self.buffer_manager.script_vars, '_is_user_write', False)
        if hasattr(self.buffer_manager.script_vars, '_is_user_write'):
            self.buffer_manager.script_vars._is_user_write = True

        try:
            for elem in iterable:
                val_str = str(elem) if not isinstance(elem, (str, int, float, bool)) else elem
                self.buffer_manager.set_script_var(item_var, val_str)
                try:
                    await self.execute_command_list(buffer)
                except LoopBreak:
                    break
        finally:
            old_user_write_inner = getattr(self.buffer_manager.script_vars, '_is_user_write', False)
            if hasattr(self.buffer_manager.script_vars, '_is_user_write'):
                self.buffer_manager.script_vars._is_user_write = True
            try:
                if exists:
                    self.buffer_manager.set_script_var(item_var, orig_val)
                else:
                    if item_var in self.buffer_manager.script_vars:
                        del self.buffer_manager.script_vars[item_var]
            finally:
                if hasattr(self.buffer_manager.script_vars, '_is_user_write'):
                    self.buffer_manager.script_vars._is_user_write = old_user_write_inner

    async def execute_command_list(self, commands_list: List[str]) -> None:
        """Execute a list of command lines with support for multiline blocks (foreach, defproc, multiline)."""
        old_script_context = self.script_context
        self.script_context = True

        in_multi_line = False
        multi_line_buffer = []

        in_defproc = False
        cur_proc_name = ""
        cur_proc_params = []
        cur_proc_body = []

        foreach_depth = 0
        foreach_buffer = []
        foreach_item_var = ""
        foreach_array_var = ""

        idx = 0
        try:
            while idx < len(commands_list):
                cmd = commands_list[idx]
                if not cmd.strip():
                    idx += 1
                    continue

                stripped_cmd = cmd.strip()
                lstripped_cmd = cmd.lstrip()

                # 1. Handle active foreach buffer capture
                if foreach_depth > 0:
                    m_for = re.match(r"^\s*foreach\s+([a-zA-Z_]\w*)\s+in\s+(.+)$", stripped_cmd)
                    if m_for:
                        foreach_depth += 1
                        foreach_buffer.append(cmd)
                    elif stripped_cmd == "endfor":
                        foreach_depth -= 1
                        if foreach_depth == 0:
                            await self.execute_foreach_block(foreach_item_var, foreach_array_var, foreach_buffer)
                            foreach_buffer = []
                            foreach_item_var = ""
                            foreach_array_var = ""
                        else:
                            foreach_buffer.append(cmd)
                    else:
                        foreach_buffer.append(cmd)
                    idx += 1
                    continue

                # 2. Handle active defproc buffer capture
                if in_defproc:
                    if stripped_cmd == "endproc":
                        self.procedures[cur_proc_name] = {
                            "params": cur_proc_params,
                            "body": cur_proc_body
                        }
                        print(f"Defined procedure: {cur_proc_name} with {len(cur_proc_params)} parameters")
                        in_defproc = False
                        cur_proc_name = ""
                        cur_proc_params = []
                        cur_proc_body = []
                    elif lstripped_cmd.startswith("defproc ") or stripped_cmd == "defproc":
                        print("Error: Nested defproc is not allowed.")
                        in_defproc = False
                        cur_proc_name = ""
                        cur_proc_params = []
                        cur_proc_body = []
                    else:
                        cur_proc_body.append(cmd)
                    idx += 1
                    continue

                # 3. Check for foreach start
                m_for = re.match(r"^\s*foreach\s+([a-zA-Z_]\w*)\s+in\s+(.+)$", stripped_cmd)
                if m_for:
                    foreach_item_var = m_for.group(1)
                    foreach_array_var = m_for.group(2).strip()
                    foreach_buffer = []
                    foreach_depth = 1
                    idx += 1
                    continue

                # 4. Check for defproc start
                if lstripped_cmd.startswith("defproc ") or stripped_cmd == "defproc":
                    m = re.match(r"defproc\s+([a-zA-Z_]\w*)(?:\(([^)]*)\))?", lstripped_cmd)
                    if m:
                        cur_proc_name = m.group(1)
                        params_str = m.group(2)
                        cur_proc_params = [p.strip() for p in params_str.split(',')] if params_str else []
                        cur_proc_body = []
                        in_defproc = True
                    else:
                        print("Invalid defproc format. Usage: defproc name(p1, p2)")
                    idx += 1
                    continue

                # 5. Check if we're in multi-line mode
                if (
                    self.multi_line_mode
                    and not cmd.startswith("/")
                    and not in_multi_line
                ):
                    in_multi_line = True
                    multi_line_buffer = [cmd]
                    idx += 1
                    continue

                if in_multi_line:
                    if stripped_cmd == ";;":
                        self.multi_line_mode = False
                        expanded_lines = []
                        for line in multi_line_buffer:
                            if line.lstrip().startswith("%"):
                                expanded = self.process_macro_line(line)
                                expanded_lines.append(line if expanded.startswith("ERROR:") else expanded)
                            else:
                                expanded_lines.append(line)
                        full_prompt = "\n".join(expanded_lines)
                        print(f"Executing multi-line prompt: {full_prompt[:50]}...")
                        handled = await self.execute_script_command(full_prompt, self.handle_escape_command)
                        if not handled:
                            print(f"Sending prompt to LLM: {full_prompt[:50]}...")
                            print("Prompt sent to LLM successfully")
                        in_multi_line = False
                        multi_line_buffer = []

                        # Peek ahead to burn legacy /multiline if needed
                        next_meaningful = []
                        peek_idx = idx + 1
                        while peek_idx < len(commands_list) and len(next_meaningful) < 2:
                            peek_cmd = commands_list[peek_idx]
                            if peek_cmd.strip():
                                next_meaningful.append((peek_idx, peek_cmd))
                            peek_idx += 1

                        if len(next_meaningful) >= 2:
                            idx1, cmd1 = next_meaningful[0]
                            idx2, cmd2 = next_meaningful[1]
                            if cmd1 == "/multiline" and cmd2.startswith("/"):
                                print(f"depreciated line removed: {cmd1}")
                                commands_list[idx1] = ""
                        elif len(next_meaningful) == 1:
                            idx1, cmd1 = next_meaningful[0]
                            if cmd1 == "/multiline":
                                print(f"depreciated line removed: {cmd1}")
                                commands_list[idx1] = ""

                    elif cmd.startswith("/"):
                        expanded_lines = []
                        for line in multi_line_buffer:
                            if line.lstrip().startswith("%"):
                                expanded = self.process_macro_line(line)
                                expanded_lines.append(line if expanded.startswith("ERROR:") else expanded)
                            else:
                                expanded_lines.append(line)
                        full_prompt = "\n".join(expanded_lines)
                        print(f"Executing multi-line prompt: {full_prompt[:50]}...")
                        handled = await self.execute_script_command(full_prompt, self.handle_escape_command)
                        if not handled:
                            print(f"Sending prompt to LLM: {full_prompt[:50]}...")
                            print("Prompt sent to LLM successfully")
                        print(f"Executing: {cmd}")
                        handled = await self.execute_script_command(cmd, self.handle_escape_command)
                        if not handled:
                            print(f"Unknown command in script: {cmd}")
                        in_multi_line = False
                        multi_line_buffer = []
                    else:
                        if cmd.lstrip().startswith("%"):
                            expanded_line = self.process_macro_line(cmd)
                            multi_line_buffer.append(cmd if expanded_line.startswith("ERROR:") else expanded_line)
                        else:
                            multi_line_buffer.append(cmd)
                else:
                    print(f"Executing: {cmd}")
                    handled = await self.execute_script_command(cmd, self.handle_escape_command)
                    if not handled:
                        print(f"Unknown command in script: {cmd}")

                idx += 1

            if in_defproc:
                print("Error: Unclosed defproc at end of script.")
            if foreach_depth > 0:
                print("Error: Unclosed foreach loop at end of script.")

            if in_multi_line and multi_line_buffer:
                expanded_lines = []
                for line in multi_line_buffer:
                    if line.lstrip().startswith("%"):
                        expanded = self.process_macro_line(line)
                        expanded_lines.append(line if expanded.startswith("ERROR:") else expanded)
                    else:
                        expanded_lines.append(line)
                full_prompt = "\n".join(expanded_lines)
                print(f"Executing multi-line prompt: {full_prompt[:50]}...")
                handled = await self.execute_script_command(full_prompt, self.handle_escape_command)
                if not handled:
                    print(f"Sending prompt to LLM: {full_prompt[:50]}...")
                    print("Prompt sent to LLM successfully")
        finally:
            self.script_context = old_script_context

    async def execute_script(self, script_path: str) -> None:
        """
        Execute a script file containing multiple commands.

        Args:
            script_path: Path to the script file
        """
        try:
            print("Loading script: ", script_path)
            
            # Load macros from macro.chatdsl file in the same directory as the script
            script_dir = os.path.dirname(script_path)
            macro_file = os.path.join(script_dir, "macro.chatdsl")
            if os.path.exists(macro_file):
                self.load_macros(macro_file)
                print(f"Loaded macros from {macro_file}")
            else:
                # Try default location
                self.load_macros()
            
            with open(script_path, "r") as f:
                script_content = f.read()

            # Preprocess to translate localized keywords and commands
            script_content = self.i18n.translate_script(script_content)

            # Robust command extractor supporting multiline quotes and comments
            commands_list = []
            current_command = []
            in_quotes = False
            quote_char = None
            
            lines_content = script_content.split("\n")
            for line in lines_content:
                # If we're not inside quotes, skip full line comments
                if not in_quotes and line.strip().startswith("#"):
                    continue
                
                i = 0
                while i < len(line):
                    char = line[i]
                    
                    if in_quotes:
                        if char == quote_char:
                            in_quotes = False
                            quote_char = None
                            current_command.append(char)
                        else:
                            current_command.append(char)
                    else:
                        # Outside quotes, handle comments and command separators
                        if char == "#":
                            break # End of line comment
                        
                        if char in ('"', "'"):
                            # Only start a quote if it looks like the start of a token
                            # This prevents apostrophes in words (e.g., Assyria's) from starting quotes
                            is_start_of_token = (i == 0 or line[i-1].isspace() or line[i-1] in ('=', ',', '(', '{', '[', ':', '|', '&'))
                            if is_start_of_token:
                                in_quotes = True
                                quote_char = char
                                current_command.append(char)
                            else:
                                current_command.append(char)
                        elif char == ";":
                            if i + 1 < len(line) and line[i+1] == ";":
                                # This is ';;'. Treat it as a single token.
                                cmd = "".join(current_command).strip()
                                if cmd:
                                    commands_list.append(cmd)
                                commands_list.append(";;")
                                current_command = []
                                i += 1
                                continue
                            else:
                                cmd = "".join(current_command).strip()
                                if cmd:
                                    commands_list.append(cmd)
                                current_command = []
                        else:
                            current_command.append(char)
                    i += 1
                
                if not in_quotes:
                    cmd = "".join(current_command).strip()
                    if cmd:
                        commands_list.append(cmd)
                    current_command = []
                else:
                    # Keep the newline as part of the quoted string
                    current_command.append("\n")
            
            # Catch trailing command
            cmd = "".join(current_command).strip()
            if cmd:
                commands_list.append(cmd)

            # Execute command list using execute_command_list
            await self.execute_command_list(commands_list)
            print("Script execution finished")
        except Exception as e:
            print(f"Error executing script: {str(e)}")
        finally:
            self.script_context = False

    # =========== RUN COMMAND METHODS ===========

    def check_dangerous(self, command: str) -> Optional[str]:
        """
        Check command for dangerous patterns.
        
        Args:
            command: The shell command to check
            
        Returns:
            Warning message if dangerous pattern found, None otherwise
        """
        import re
        
        DANGEROUS_PATTERNS = [
            # Recursive deletes
            (r'rm\s+-r\b', "Recursive delete (rm -r)"),
            (r'rm\s+--recursive\b', "Recursive delete (rm --recursive)"),
            (r'rm\s+-rf\b', "Recursive force delete (rm -rf)"),
            (r'rm\s+--recursive\s+--force\b', "Recursive force delete"),
            
            # System directory writes
            (r'>\s*(/dev/|/etc/|/usr/|/bin/|/sbin/|/lib/|/boot/|/var/|/opt/)', 
             "Write to critical system directory"),
            
            # Shell features that could be exploited
            (r':\s*\>\s*\S+', "Here-document"),
            (r';\s*', "Command chaining with ;"),
            (r'&&\s*', "AND-chain"),
            (r'\|\s*', "OR-chain"),
            (r'\$\(', "Command substitution"),
            (r'`[^`]+`', "Backtick command substitution"),
            
            # Dangerous commands
            (r'chmod\s+-R\b', "Recursive chmod"),
            (r'chown\s+-R\b', "Recursive chown"),
            (r'mkfs\b', "Filesystem creation"),
            (r'dd\s+if=\s*', "dd command (disk operations)"),
            (r'fdisk\b', "Partition table manipulation"),
            (r'format\b', "Disk formatting"),
            (r'partition\b', "Partition manipulation"),
            (r'mount\b', "Mount filesystems"),
            (r'umount\b', "Unmount filesystems"),
            
            # Privilege escalation
            (r'sudo\b', "Privilege escalation (sudo)"),
            (r'su\s+', "Switch user"),
        ]
        
        for pattern, description in DANGEROUS_PATTERNS:
            if re.search(pattern, command):
                return description
        
        return None

    def execute_shell_command(self, command: str, timeout: Optional[int] = None) -> None:
        """
        Execute a shell command and store output in RUN_COMPLETION and LAST_COMPLETION.
        
        SECURITY: Uses shlex.split() + shell=False to prevent injection.
        Variables are substituted in Python BEFORE shell execution.
        
        Args:
            command: The shell command to execute
            timeout: Optional timeout in seconds (defaults to self.run_timeout)
        """
        import subprocess
        import shlex
        
        if timeout is None:
            timeout = self.run_timeout
        
        # CRITICAL: Variable substitution already happened in the caller
        # So 'command' contains literal strings, not ${VAR} references
        
        # Check for dangerous patterns
        danger = self.check_dangerous(command)
        if danger:
            if self.safe_mode:
                self.buffer_manager.set_script_var('RUN_COMPLETION', 
                    f"Blocked (safe mode): {danger}", allow_protected=True)
                self.buffer_manager.set_script_var('RUN_ERROR', '', allow_protected=True)
                self.buffer_manager.set_script_var('RUN_EXIT_CODE', '-1', allow_protected=True)
                self.buffer_manager.set_script_var('LAST_COMPLETION', 
                    f"Blocked (safe mode): {danger}", allow_protected=True)
                print(f"Blocked: {danger}")
                return
            elif getattr(self, 'safe_mode_askfirst', False):
                confirm = input(f"Warning: {danger} Execute anyway? (y/N): ")
                if confirm.lower() != 'y':
                    self.buffer_manager.set_script_var('RUN_COMPLETION', "Command aborted by user", allow_protected=True)
                    self.buffer_manager.set_script_var('RUN_ERROR', '', allow_protected=True)
                    self.buffer_manager.set_script_var('RUN_EXIT_CODE', '-1', allow_protected=True)
                    self.buffer_manager.set_script_var('LAST_COMPLETION', "Command aborted by user", allow_protected=True)
                    print("Command aborted")
                    return
        
        try:
            # SAFE: No shell=True, uses shlex.split for proper tokenization
            result = subprocess.run(
                shlex.split(command),
                shell=False,  # CRITICAL: Prevents shell injection
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=timeout,
                cwd=os.getcwd()
            )
            
            # Store in buffer_manager using RUN_* variables to avoid conflicts
            self.buffer_manager.set_script_var('RUN_COMPLETION', result.stdout, allow_protected=True)
            self.buffer_manager.set_script_var('RUN_ERROR', result.stderr, allow_protected=True)
            self.buffer_manager.set_script_var('RUN_EXIT_CODE', str(result.returncode), allow_protected=True)
            
            # Also store in LAST_COMPLETION for backward compatibility
            self.buffer_manager.set_script_var('LAST_COMPLETION', result.stdout, allow_protected=True)
            
            if result.returncode != 0:
                err_text = result.stderr or result.stdout or ""
                if err_text:
                    print(err_text, end="")
                if err_text and not err_text.endswith('\n'):
                    print()
                print(f"Command exited with code {result.returncode}")
            else:
                if result.stdout:
                    print(result.stdout, end="")
                
        except subprocess.TimeoutExpired:
            error_msg = f"Error: Command timed out after {timeout}s"
            self.buffer_manager.set_script_var('RUN_COMPLETION', error_msg, allow_protected=True)
            self.buffer_manager.set_script_var('RUN_ERROR', '', allow_protected=True)
            self.buffer_manager.set_script_var('RUN_EXIT_CODE', '-2', allow_protected=True)
            self.buffer_manager.set_script_var('LAST_COMPLETION', error_msg, allow_protected=True)
            print(error_msg)
            print("Command exited with code -2")
        except FileNotFoundError as e:
            error_msg = f"Error: Command not found: {e.filename}"
            self.buffer_manager.set_script_var('RUN_COMPLETION', '', allow_protected=True)
            self.buffer_manager.set_script_var('RUN_ERROR', error_msg, allow_protected=True)
            self.buffer_manager.set_script_var('RUN_EXIT_CODE', '-1', allow_protected=True)
            self.buffer_manager.set_script_var('LAST_COMPLETION', '', allow_protected=True)
            print(error_msg)
            print("Command exited with code -1")
        except Exception as e:
            error_msg = f"Error: {e}"
            self.buffer_manager.set_script_var('RUN_COMPLETION', '', allow_protected=True)
            self.buffer_manager.set_script_var('RUN_ERROR', error_msg, allow_protected=True)
            self.buffer_manager.set_script_var('RUN_EXIT_CODE', '-1', allow_protected=True)
            self.buffer_manager.set_script_var('LAST_COMPLETION', '', allow_protected=True)
            print(error_msg)
            print("Command exited with code -1")

    def _is_permanent_capability_error(self, text: str) -> bool:
        """Check if text indicates a non-recoverable client/protocol capability failure."""
        if not text:
            return False
        text_lower = text.lower()
        capability_keywords = [
            "elicitation not supported",
            "method not found",
            "capability not supported",
            "capabilities not supported",
            "protocol error: unsupported"
        ]
        return any(keyword in text_lower for keyword in capability_keywords)

    def _format_capability_error(self, tool_name: str, raw_error: str) -> str:
        """Format permanent capability error with explicit LLM guidance."""
        guidance = (
            f"[PERMANENT CAPABILITY ERROR]: Feature not supported by client environment. "
            "DO NOT retry this tool. Select an alternative tool or complete response directly."
        )
        if raw_error:
            if "[PERMANENT CAPABILITY ERROR]" in raw_error:
                return raw_error
            return f"{raw_error.strip()}\n\n{guidance}"
        return guidance

    async def dispatch_tool(self, invocation_json: str = None) -> str:
        """
        Dispatch a tool invocation to the dispatcher.
        
        Args:
            invocation_json: JSON string containing tool invocation. If None, uses LAST_COMPLETION.
        
        Returns:
            JSON result from dispatcher or MCP server as string
        """
        import subprocess
        import tempfile
        import os
        import json
        
        # Use LAST_COMPLETION if no invocation_json provided
        if invocation_json is None:
            invocation_json = self.buffer_manager.get_script_var('LAST_COMPLETION') or ""
        
        if not invocation_json.strip():
            print("No tool invocation to dispatch")
            return ""
            
        # Extract clean tool call if possible, to be robust to conversational formatting
        tool_call = self.extract_tool_call(invocation_json)
        if tool_call:
            invocation_json = json.dumps(tool_call)
        else:
            try:
                tool_call = json.loads(invocation_json)
            except Exception:
                pass
        
        if tool_call and isinstance(tool_call, dict):
            tool_name = tool_call.get("tool", "")
            if tool_name.startswith("mcp__"):
                parts = tool_name.split("__", 2)
                if len(parts) >= 3:
                    server_name = parts[1]
                    mcp_tool_name = parts[2]
                    arguments = tool_call.get("arguments", {})
                    
                    is_enabled = self.tool_overrides.get(tool_name, True)
                    if not is_enabled:
                        err_msg = f"Error: Tool '{tool_name}' is currently disabled."
                        self.buffer_manager.set_script_var('TOOL_DISPATCH_RESULT', '')
                        self.buffer_manager.set_script_var('TOOL_DISPATCH_ERROR', err_msg)
                        self.buffer_manager.set_script_var('TOOL_DISPATCH_EXIT_CODE', '-1')
                        print(err_msg)
                        return err_msg
                    
                    print(f"Executing MCP tool '{mcp_tool_name}' on server '{server_name}'...")
                    try:
                        if not self.mcp_manager:
                            raise RuntimeError("MCP client manager is not initialized.")
                        
                        result_str = await self.mcp_manager.execute_tool(server_name, mcp_tool_name, arguments)
                        
                        if self._is_permanent_capability_error(result_str):
                            result_str = self._format_capability_error(tool_name, result_str)
                            self.tool_overrides[tool_name] = False
                            self.buffer_manager.set_script_var('TOOL_DISPATCH_RESULT', result_str)
                            self.buffer_manager.set_script_var('TOOL_DISPATCH_ERROR', result_str)
                            self.buffer_manager.set_script_var('TOOL_DISPATCH_EXIT_CODE', '1')
                        else:
                            self.buffer_manager.set_script_var('TOOL_DISPATCH_RESULT', result_str)
                            self.buffer_manager.set_script_var('TOOL_DISPATCH_ERROR', '')
                            self.buffer_manager.set_script_var('TOOL_DISPATCH_EXIT_CODE', '0')
                        print("MCP tool executed successfully")
                        return result_str
                    except Exception as e:
                        err_msg = f"MCP tool execution failed: {e}"
                        if self._is_permanent_capability_error(err_msg):
                            err_msg = self._format_capability_error(tool_name, err_msg)
                            self.tool_overrides[tool_name] = False
                        print(err_msg)
                        self.buffer_manager.set_script_var('TOOL_DISPATCH_RESULT', err_msg)
                        self.buffer_manager.set_script_var('TOOL_DISPATCH_ERROR', err_msg)
                        self.buffer_manager.set_script_var('TOOL_DISPATCH_EXIT_CODE', '1')
                        return f"Error: {err_msg}"
            elif tool_name == "get_context_metrics":
                is_enabled = self.tool_overrides.get(tool_name, True)
                if not is_enabled:
                    err_msg = f"Error: Tool '{tool_name}' is currently disabled."
                    self.buffer_manager.set_script_var('TOOL_DISPATCH_RESULT', '')
                    self.buffer_manager.set_script_var('TOOL_DISPATCH_ERROR', err_msg)
                    self.buffer_manager.set_script_var('TOOL_DISPATCH_EXIT_CODE', '-1')
                    print(err_msg)
                    return err_msg
                try:
                    from .tools.context_utils import get_context_metrics
                    args = tool_call.get("arguments", {})
                    scope = args.get("scope", "all")
                    target_var = args.get("target_variable")
                    res = get_context_metrics(scope=scope, target_variable=target_var, app=self)
                    result_str = json.dumps({"status": "success", "tool": tool_name, "result": res}, indent=2)
                    self.buffer_manager.set_script_var('TOOL_DISPATCH_RESULT', result_str)
                    self.buffer_manager.set_script_var('TOOL_DISPATCH_ERROR', '')
                    self.buffer_manager.set_script_var('TOOL_DISPATCH_EXIT_CODE', '0')
                    print("Tool dispatched successfully (in-process context_metrics)")
                    return result_str
                except Exception as e:
                    err_msg = f"Error: Context metrics tool execution failed: {e}"
                    self.buffer_manager.set_script_var('TOOL_DISPATCH_RESULT', '')
                    self.buffer_manager.set_script_var('TOOL_DISPATCH_ERROR', str(e))
                    self.buffer_manager.set_script_var('TOOL_DISPATCH_EXIT_CODE', '1')
                    return err_msg
        
        # Create a temporary file for the invocation
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', suffix='.json', delete=False) as tmp_file:
            tmp_file.write(invocation_json)
            tmp_path = tmp_file.name
        
        try:
            # Build the dispatcher command
            dispatcher_path = os.path.join(os.path.dirname(__file__), 'dispatcher.py')
            user_config_path = os.path.expanduser('~/.config/chatybot/tools_config.toml')
            package_config = os.path.join(os.path.dirname(__file__), 'tools_config.toml')
            from .config_sync import sync_toml_file
            sync_toml_file(package_config, user_config_path, "tools_config.toml")
            config_path = user_config_path if os.path.exists(user_config_path) else package_config
            
            # Check if dispatcher exists
            if not os.path.exists(dispatcher_path):
                print(f"Dispatcher not found: {dispatcher_path}")
                return ""
            
            # Run the dispatcher with overrides
            env = os.environ.copy()
            env["CHATYBOT_TOOL_OVERRIDES"] = json.dumps(self.tool_overrides)
            cmd = ['python3', dispatcher_path, tmp_path, '--config', config_path]
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.tool_timeout,
                env=env
            )
            
            # Store result in buffer_manager
            self.buffer_manager.set_script_var('TOOL_DISPATCH_RESULT', result.stdout)
            self.buffer_manager.set_script_var('TOOL_DISPATCH_ERROR', result.stderr)
            self.buffer_manager.set_script_var('TOOL_DISPATCH_EXIT_CODE', str(result.returncode))
            
            if result.returncode != 0:
                print(f"Tool dispatch failed: {result.stderr}")
                return f"Error: Tool execution failed with exit code {result.returncode}: {result.stderr or result.stdout or 'Unknown error'}"
            else:
                print(f"Tool dispatched successfully")
                if tool_call and tool_call.get('tool') == 'change_dir':
                    path = tool_call.get('arguments', {}).get('path')
                    if path:
                        try:
                            os.chdir(path)
                            print(f"Main process updated CWD to: {os.getcwd()}")
                        except Exception as e:
                            print(f"Warning: Failed to update main process CWD to {path}: {e}")

                # Automatically populate script_vars if tool call requested target_variable and tool succeeded
                try:
                    res_json = json.loads(result.stdout)
                    if isinstance(res_json, dict) and res_json.get("status") == "success":
                        inner_res = res_json.get("result", {})
                        target_var = None
                        val = None
                        if isinstance(inner_res, dict):
                            target_var = inner_res.get("target_variable")
                            val = inner_res.get("result")
                        if not target_var and tool_call and isinstance(tool_call, dict):
                            target_var = tool_call.get("arguments", {}).get("target_variable")
                        if target_var and val is not None:
                            self.buffer_manager.set_script_var(str(target_var).strip(), val, allow_protected=True)
                except Exception as e:
                    pass

                return result.stdout
            
        except Exception as e:
            print(f"Error dispatching tool: {e}")
            self.buffer_manager.set_script_var('TOOL_DISPATCH_RESULT', '')
            self.buffer_manager.set_script_var('TOOL_DISPATCH_ERROR', str(e))
            self.buffer_manager.set_script_var('TOOL_DISPATCH_EXIT_CODE', '-1')
            return f"Error: Tool dispatch failed: {str(e)}"
        finally:
            # Clean up temp file
            try:
                os.unlink(tmp_path)
            except:
                pass

    def extract_tool_call(self, text: str) -> Optional[Dict[str, Any]]:
        """
        Extract a tool call JSON block from conversational text.
        Returns a dictionary if a valid tool call is found, and None otherwise.
        """
        calls = self.extract_tool_calls(text)
        return calls[0] if calls else None

    def extract_tool_calls(self, text: str) -> List[Dict[str, Any]]:
        """
        Extract all tool call JSON blocks from conversational text.
        Supports standard JSON blocks, Gemma 4 native tool call syntax (<|tool_call>call:tool_name{...}<tool_call|>),
        FunctionGemma syntax, XML-style function/parameter syntax (<tool_call><function=name><parameter=key>val</parameter></function></tool_call>),
        unquoted keys, and single-quoted dictionaries.
        Returns a list of dictionaries for all valid tool calls found.
        """
        import json
        import re
        from typing import Any, Dict, List, Optional

        def parse_xml_param_value(val_str: str) -> Any:
            val_str = val_str.strip()
            if not val_str:
                return ""
            if val_str.lower() == "true":
                return True
            if val_str.lower() == "false":
                return False
            if val_str.lower() in ("null", "none"):
                return None
            try:
                if "." in val_str:
                    return float(val_str)
                return int(val_str)
            except ValueError:
                pass
            if (val_str.startswith("{") and val_str.endswith("}")) or (val_str.startswith("[") and val_str.endswith("]")):
                try:
                    return json.loads(val_str)
                except Exception:
                    pass
            if (val_str.startswith('"') and val_str.endswith('"')) or (val_str.startswith("'") and val_str.endswith("'")):
                return val_str[1:-1]
            return val_str

        def extract_xml_tool_calls(s: str) -> List[Dict[str, Any]]:
            xml_calls = []
            fn_block_pattern = re.compile(
                r'<function(?:[\s:=]+|[\s:=]*name\s*=\s*)["\']?([a-zA-Z0-9_\-\.]+)["\']?\s*>(.*?)</function[^>]*>',
                re.IGNORECASE | re.DOTALL
            )
            for fn_match in fn_block_pattern.finditer(s):
                tool_name = fn_match.group(1).strip()
                if "." in tool_name:
                    tool_name = tool_name.split(".")[-1]
                fn_body = fn_match.group(2)
                args = {}
                param_pattern = re.compile(
                    r'<parameter(?:[\s:=]+|[\s:=]*name\s*=\s*)["\']?([a-zA-Z0-9_\-\.]+)["\']?\s*(?:value=["\']?(.*?)["\']?)?\s*>(.*?)</parameter[^>]*>',
                    re.IGNORECASE | re.DOTALL
                )
                param_matches = list(param_pattern.finditer(fn_body))
                if param_matches:
                    for p_match in param_matches:
                        p_name = p_match.group(1).strip()
                        p_val_attr = p_match.group(2)
                        p_val_body = p_match.group(3)
                        raw_val = p_val_attr if p_val_attr is not None else p_val_body
                        args[p_name] = parse_xml_param_value(raw_val)
                else:
                    self_closing_pattern = re.compile(
                        r'<parameter(?:[\s:=]+|[\s:=]*name\s*=\s*)["\']?([a-zA-Z0-9_\-\.]+)["\']?\s+value=["\']?(.*?)["\']?\s*/>',
                        re.IGNORECASE
                    )
                    for sc_match in self_closing_pattern.finditer(fn_body):
                        p_name = sc_match.group(1).strip()
                        raw_val = sc_match.group(2)
                        args[p_name] = parse_xml_param_value(raw_val)
                xml_calls.append({"tool": tool_name, "arguments": args})
            return xml_calls

        # Clean JSON strings and helper procedures
        xml_tool_calls = extract_xml_tool_calls(text)
        tool_calls = []
        for xcall in xml_tool_calls:
            if xcall not in tool_calls:
                tool_calls.append(xcall)

        def clean_json_string(s: str) -> str:
            # Remove single line comments starting with // or #, respecting quotes across newlines
            cleaned_chars = []
            in_quote = False
            escaped = False
            i = 0
            n = len(s)
            while i < n:
                char = s[i]
                if escaped:
                    cleaned_chars.append(char)
                    escaped = False
                    i += 1
                    continue
                
                if char == '\\':
                    cleaned_chars.append(char)
                    escaped = True
                    i += 1
                    continue
                
                if char == '"':
                    in_quote = not in_quote
                    cleaned_chars.append(char)
                    i += 1
                    continue
                
                if in_quote and char == '\n':
                    cleaned_chars.append('\\')
                    cleaned_chars.append('n')
                    i += 1
                    continue
                
                if not in_quote:
                    if char == '#':
                        # Skip until next newline or end of string
                        while i < n and s[i] != '\n':
                            i += 1
                        continue
                    elif s[i:i+2] == '//':
                        # Skip until next newline or end of string
                        while i < n and s[i] != '\n':
                            i += 1
                        continue
                
                cleaned_chars.append(char)
                i += 1
                
            cleaned = "".join(cleaned_chars)
            # Remove trailing commas before closing braces/brackets
            cleaned = re.sub(r',\s*([\]}])', r'\1', cleaned)
            return cleaned

        def fix_unquoted_json(s: str) -> str:
            buf = []
            in_quote = False
            quote_char = None
            escaped = False
            i = 0
            n = len(s)
            while i < n:
                char = s[i]
                if escaped:
                    buf.append(char)
                    escaped = False
                    i += 1
                    continue
                if char == '\\':
                    buf.append(char)
                    escaped = True
                    i += 1
                    continue
                if in_quote:
                    if char == quote_char:
                        in_quote = False
                        buf.append('"')
                    elif quote_char == "'" and char == '"':
                        buf.append('\\"')
                    else:
                        buf.append(char)
                    i += 1
                    continue
                else:
                    if char in ('"', "'"):
                        in_quote = True
                        quote_char = char
                        buf.append('"')
                        i += 1
                        continue
                    else:
                        buf.append(char)
                        i += 1

            buf_str = "".join(buf)
            out = []
            in_quote = False
            escaped = False
            i = 0
            n = len(buf_str)
            while i < n:
                char = buf_str[i]
                if escaped:
                    out.append(char)
                    escaped = False
                    i += 1
                    continue
                if char == '\\':
                    out.append(char)
                    escaped = True
                    i += 1
                    continue
                if char == '"':
                    in_quote = not in_quote
                    out.append(char)
                    i += 1
                    continue

                if not in_quote:
                    if char.isalpha() or char == '_':
                        start = i
                        while i < n and (buf_str[i].isalnum() or buf_str[i] == '_'):
                            i += 1
                        ident = buf_str[start:i]
                        peek = i
                        while peek < n and buf_str[peek].isspace():
                            peek += 1
                        if peek < n and buf_str[peek] == ':':
                            out.append(f'"{ident}"')
                        else:
                            if ident == "True":
                                out.append("true")
                            elif ident == "False":
                                out.append("false")
                            elif ident == "None":
                                out.append("null")
                            else:
                                out.append(ident)
                        continue

                out.append(char)
                i += 1

            return clean_json_string("".join(out))

        def parse_json_or_dict(s: str) -> Optional[Dict[str, Any]]:
            try:
                cleaned = clean_json_string(s)
                data = json.loads(cleaned)
                if isinstance(data, dict):
                    return data
            except Exception:
                pass

            try:
                fixed = fix_unquoted_json(s)
                data = json.loads(fixed)
                if isinstance(data, dict):
                    return data
            except Exception:
                pass

            try:
                import ast
                data = ast.literal_eval(s)
                if isinstance(data, dict):
                    return data
            except Exception:
                pass

            return None

        def normalize_tool_call(data: Any) -> Optional[Dict[str, Any]]:
            if isinstance(data, dict):
                if "tool" in data:
                    tool_name = str(data["tool"])
                    if "." in tool_name:
                        tool_name = tool_name.split(".")[-1]
                    data["tool"] = tool_name
                    if "arguments" not in data:
                        data["arguments"] = {k: v for k, v in data.items() if k != "tool"}
                    return data
                elif "name" in data:
                    tool_name = str(data["name"])
                    if "." in tool_name:
                        tool_name = tool_name.split(".")[-1]
                    args = data.get("arguments") if "arguments" in data else data.get("args") if "args" in data else data.get("parameters") if "parameters" in data else {k: v for k, v in data.items() if k != "name"}
                    return {"tool": tool_name, "arguments": args}
                elif "function" in data:
                    tool_name = str(data["function"])
                    if "." in tool_name:
                        tool_name = tool_name.split(".")[-1]
                    args = data.get("arguments") if "arguments" in data else data.get("args") if "args" in data else {k: v for k, v in data.items() if k != "function"}
                    return {"tool": tool_name, "arguments": args}
            return None

        # Parse to find all tool calls in the text
        i = 0
        n = len(text)
        while i < n:
            if text[i] == '{':
                prefix = text[:i].rstrip()
                # Match tool header before '{' if present (e.g. <|tool_call>call:run_command, call:run_command, <start_function_call>call:run_command)
                header_match = re.search(
                    r'(?:<\|?tool_call\|?>|<start_function_call>|<tool_call>|\bcall:)\s*(?:call:)?\s*([a-zA-Z0-9_\-\.]+)\s*\(?\s*$',
                    prefix,
                    re.IGNORECASE
                )
                explicit_tool_name = header_match.group(1) if header_match else None

                brace_count = 1
                j = i + 1
                in_quote = False
                escaped = False
                quote_char = None
                while j < n and brace_count > 0:
                    char = text[j]
                    if escaped:
                        escaped = False
                    elif char == '\\':
                        escaped = True
                    elif char in ('"', "'"):
                        if not in_quote:
                            in_quote = True
                            quote_char = char
                        elif char == quote_char:
                            in_quote = False
                    elif not in_quote:
                        if char == '{':
                            brace_count += 1
                        elif char == '}':
                            brace_count -= 1
                    j += 1

                if brace_count == 0:
                    candidate = text[i:j]
                    if explicit_tool_name:
                        if "." in explicit_tool_name:
                            explicit_tool_name = explicit_tool_name.split(".")[-1]
                        args = parse_json_or_dict(candidate)
                        if args is None:
                            args = {}
                        tool_calls.append({"tool": explicit_tool_name, "arguments": args})
                        i = j - 1
                    else:
                        data = parse_json_or_dict(candidate)
                        if data:
                            res = normalize_tool_call(data)
                            if res:
                                tool_calls.append(res)
                                i = j - 1
                elif brace_count > 0 and j == n:
                    candidate = text[i:j].rstrip("`\n\r \t")
                    cand_in_quote = False
                    cand_escaped = False
                    cand_brace_count = 0
                    cand_quote_char = None
                    for char in candidate:
                        if cand_escaped:
                            cand_escaped = False
                        elif char == '\\':
                            cand_escaped = True
                        elif char in ('"', "'"):
                            if not cand_in_quote:
                                cand_in_quote = True
                                cand_quote_char = char
                            elif char == cand_quote_char:
                                cand_in_quote = False
                        elif not cand_in_quote:
                            if char == '{':
                                cand_brace_count += 1
                            elif char == '}':
                                cand_brace_count -= 1
                    if cand_in_quote:
                        candidate += '"'
                    if cand_brace_count > 0:
                        candidate += '}' * cand_brace_count
                    if explicit_tool_name:
                        if "." in explicit_tool_name:
                            explicit_tool_name = explicit_tool_name.split(".")[-1]
                        args = parse_json_or_dict(candidate)
                        if args is None:
                            args = {}
                        tool_calls.append({"tool": explicit_tool_name, "arguments": args})
                        i = j - 1
                    else:
                        data = parse_json_or_dict(candidate)
                        if data:
                            res = normalize_tool_call(data)
                            if res:
                                tool_calls.append(res)
                                i = j - 1
            i += 1

        return tool_calls

    async def execute_tool_loop(self, max_turns: int) -> None:
        """
        Executes the autonomous agentic tool loop (Option B - History Management).
        """
        import json
        
        # Initialize or reset the AGENTIC_LOOP script variable
        self.buffer_manager.set_script_var('AGENTIC_LOOP', [], allow_protected=True)

        if not self.chat_history:
            print("No prompt has been executed yet. Please run a prompt first.")
            return

        initial_prompt, last_completion = self.chat_history[-1]
        
        # Enable tool loop state
        self.in_tool_loop = True

        # Preserve user-set rate limits across loop initializations
        if self._cached_rate_limit_delay is not None:
            self.rate_limit_delay = self._cached_rate_limit_delay

        # Always reload and refresh the tool context when starting the loop
        context = self.generate_tool_context()
        if self._cached_rate_limit_delay is not None:
            self.rate_limit_delay = self._cached_rate_limit_delay

        if context:
            self.tool_mode = True
            self.buffer_manager.set_script_var('TOOL_CONTEXT', context)
        
        # Build the temporary history buffer starting with past turns to preserve context
        temp_history = []
        for p, r in self.chat_history[:-1]:
            temp_history.append({"role": "user", "content": p})
            temp_history.append({"role": "assistant", "content": r})
            
        temp_history.append({"role": "user", "content": initial_prompt})
        
        current_response = last_completion
        turn_count = 0
        final_natural_language_response = ""
        previous_loop_size = 0

        # If the last completion was natural language (not a tool call), request an initial tool call from the LLM
        if not self.extract_tool_call(current_response):
            print("Last completion was not a tool call. Requesting initial tool call from LLM...")
            await self._apply_rate_limit_delay()
            current_response = await self.chat_completion(temp_history, stream=self.streaming_enabled)
        
        print(f"Starting agentic tool loop (max turns: {max_turns})...")
        
        while turn_count < max_turns:
            # Check for interrupt flag from signal handler
            if self.interrupt_requested:
                print("\nControl-C received. Breaking agentic tool loop...")
                self.control_c_count = 0  # Reset counter after handling
                self.interrupt_requested = False
                break
            
            tool_calls = self.extract_tool_calls(current_response)
            if not tool_calls:
                # Terminal state reached: model produced a natural-language response instead of a JSON tool call
                final_natural_language_response = current_response
                print("Terminal state reached (natural language response). Exiting loop.")
                break
                
            # Document the tool call assistant response in temp history
            temp_history.append({"role": "assistant", "content": current_response})
            
            excess_calls = []
            if len(tool_calls) > self.max_tool_calls_per_turn:
                print(f"Warning: {len(tool_calls)} tool calls requested. Capping at {self.max_tool_calls_per_turn} parallel tool calls per turn.")
                excess_calls = tool_calls[self.max_tool_calls_per_turn:]
                tool_calls = tool_calls[:self.max_tool_calls_per_turn]

            results = []
            for tc in tool_calls:
                tool_name = tc.get("tool")
                tool_args = tc.get("arguments", {})
                print(f"[Turn {turn_count+1}/{max_turns}] LLM requested tool: {tool_name}")
                print(f"   Arguments: {json.dumps(tool_args)}")
                
                # Execute the tool and capture result
                self.buffer_manager.set_script_var('TOOL_DISPATCH_RESULT', '')
                self.buffer_manager.set_script_var('TOOL_DISPATCH_EXIT_CODE', '0')
                try:
                    # dispatch_tool writes result to TOOL_DISPATCH_RESULT and returns the stdout string
                    result_str = await self.dispatch_tool(json.dumps(tc))
                except Exception as e:
                    result_str = json.dumps({"status": "error", "message": f"Dispatch execution error: {str(e)}"})
                    self.buffer_manager.set_script_var('TOOL_DISPATCH_RESULT', result_str)
                    self.buffer_manager.set_script_var('TOOL_DISPATCH_EXIT_CODE', '1')

                if self._is_permanent_capability_error(result_str) and "[PERMANENT CAPABILITY ERROR]" not in result_str:
                    result_str = self._format_capability_error(tool_name, result_str)
                    
                print(f"Tool Result: {result_str}")
                results.append(f"Tool: {tool_name}\nArguments: {json.dumps(tool_args)}\nResult: {result_str}")

                # Monitor tool output size and issue warnings in the loop
                result_bytes = len(result_str.encode('utf-8'))
                if result_bytes > 30 * 1024:
                    result_kb = result_bytes / 1024
                    est_toks = max(1, int(result_bytes / 4))
                    if result_bytes > 50 * 1024:
                        print(f"   [WARNING] Large tool output ({result_kb:.1f} KB, ~{est_toks} tokens). Hard truncation safeguard active.")
                        from .tools.file_utils import enforce_string_payload_limits
                        result_str = enforce_string_payload_limits(result_str, tool_name)
                    else:
                        print(f"   [NOTE] Large tool output ({result_kb:.1f} KB, ~{est_toks} tokens). Monitor context budget.")

                # Extract exit code and determine status
                try:
                    exit_code_val = int(self.buffer_manager.get_script_var('TOOL_DISPATCH_EXIT_CODE') or 0)
                except ValueError:
                    exit_code_val = 1

                tool_record = {
                    "turn": turn_count + 1,
                    "tool": tool_name,
                    "arguments": tool_args,
                    "result": result_str,
                    "exit_code": exit_code_val,
                    "status": "success" if exit_code_val == 0 else "error"
                }

                current_loop = self.buffer_manager.get_script_var('AGENTIC_LOOP') or []
                if not isinstance(current_loop, list):
                    current_loop = []
                current_loop.append(tool_record)
                self.buffer_manager.set_script_var('AGENTIC_LOOP', current_loop, allow_protected=True)

                # Log intermediate tool call if logging is active
                if self.logging_manager.logging_active:
                    self.logging_manager.log_message(
                        f"[Turn {turn_count+1}] Tool Loop Execution:\n"
                        f"  Tool: {tool_name}\n"
                        f"  Arguments: {json.dumps(tool_args)}\n"
                        f"  Result: {result_str}"
                    )
            
            for tc in excess_calls:
                tool_name = tc.get("tool")
                tool_args = tc.get("arguments", {})
                err_msg = f"Error: Only max {self.max_tool_calls_per_turn} tool calls are allowed per turn. This tool call was not executed."
                print(f"[Turn {turn_count+1}/{max_turns}] Skipping tool: {tool_name} (exceeded parallel limit)")
                results.append(f"Tool: {tool_name}\nArguments: {json.dumps(tool_args)}\nResult: {err_msg}")
                
                # Extract exit code and determine status
                tool_record = {
                    "turn": turn_count + 1,
                    "tool": tool_name,
                    "arguments": tool_args,
                    "result": err_msg,
                    "exit_code": 1,
                    "status": "error"
                }
                current_loop = self.buffer_manager.get_script_var('AGENTIC_LOOP') or []
                if not isinstance(current_loop, list):
                    current_loop = []
                current_loop.append(tool_record)
                self.buffer_manager.set_script_var('AGENTIC_LOOP', current_loop, allow_protected=True)

                # Log intermediate tool call if logging is active
                if self.logging_manager.logging_active:
                    self.logging_manager.log_message(
                        f"[Turn {turn_count+1}] Tool Loop Execution (SKIPPED - EXCEEDED LIMIT):\n"
                        f"  Tool: {tool_name}\n"
                        f"  Arguments: {json.dumps(tool_args)}\n"
                        f"  Result: {err_msg}"
                    )

            # Append the tool result back to the temp history as a user message
            combined_results = "\n\n".join(results)
            temp_history.append({"role": "user", "content": f"Tool execution results:\n{combined_results}"})
            
            turn_count += 1
            await self._apply_rate_limit_delay()

            if turn_count >= max_turns:
                print(f"Reached maximum tool loop turns ({max_turns}).")
                print("[Final Turn] Requesting final summary completion...")
                temp_history.append({
                    "role": "user",
                    "content": (
                        "You have reached the maximum allowed turns in this loop. "
                        "Please summarize your findings and present the final answer to the user. "
                        "Do not output any more tool calls."
                    )
                })
                final_natural_language_response = await self.chat_completion(temp_history, stream=self.streaming_enabled)
                break
            # Request next completion from LLM using the temporary history context
            current_loop = self.buffer_manager.get_script_var('AGENTIC_LOOP') or []
            current_size_bytes = len(json.dumps(current_loop).encode('utf-8'))
            current_size_kb = current_size_bytes / 1024
            if previous_loop_size > 0:
                growth_pct = ((current_size_bytes - previous_loop_size) / previous_loop_size) * 100
                growth_str = f", growth: {growth_pct:+.1f}%"
            else:
                growth_str = ""
            print(f"[Turn {turn_count+1}/{max_turns}] Requesting next completion... (AGENTIC_LOOP size: {current_size_kb:.2f} KB{growth_str})")
            previous_loop_size = current_size_bytes
            current_response = await self.chat_completion(temp_history, stream=self.streaming_enabled)
            
        # Clean up loop state
        self.in_tool_loop = False
        
        # If final_natural_language_response is not set, fallback
        if not final_natural_language_response:
            final_natural_language_response = current_response
            
        # Update LAST_COMPLETION to the final output
        self.buffer_manager.set_script_var('LAST_COMPLETION', final_natural_language_response)
        
        # Commit ONLY the final, natural-language outcome to the main chat_history (Option B)
        self.chat_history[-1] = (initial_prompt, final_natural_language_response)
        
        # Update active session turn record with agentic loop outcome
        if self.session_mode != "off" and self.session_turns:
            agentic_trace = self.buffer_manager.script_vars.get('AGENTIC_LOOP', [])
            self.session_turns[-1]["response"] = final_natural_language_response
            if agentic_trace:
                self.session_turns[-1]["agentic_loop"] = agentic_trace
            self.save_active_session()
        
        # Log final response from inside the tool loop if logging is active
        if self.logging_manager.logging_active:
            self.logging_manager.log_message(f"Assistant (Agentic Loop Final): {final_natural_language_response}\n")
            
        print("\nAgentic Tool Loop finished.")
        print(f"Final Response:\n{final_natural_language_response}")
        
        # Automatically show trace if agentic loop tracing is enabled
        if self.trace_agentic_loop:
            self.show_agentic_loop_trace()

    def show_agentic_loop_trace(self) -> None:
        """
        Print a summary of the most recent agentic tool loop run.

        Reads the AGENTIC_LOOP script variable (a list of per-call records
        recorded by execute_tool_loop) and prints:
          - total number of tool calls
          - count of successes vs failures
          - a numbered list of calls with status (SUCCESS/FAILED) beside each
        """
        loop_data = self.buffer_manager.get_script_var('AGENTIC_LOOP')
        if not isinstance(loop_data, list) or not loop_data:
            print("No agentic loop has been run yet.")
            return

        total = len(loop_data)
        successes = sum(1 for r in loop_data if r.get("status") == "success")
        failures = total - successes

        print("\n=== AGENTIC LOOP TRACE ===")
        print(f"Total tool calls: {total}  ({successes} success, {failures} failed)")
        print("-" * 60)

        for i, rec in enumerate(loop_data, 1):
            tool_name = rec.get("tool", "unknown")
            turn = rec.get("turn", "?")
            status = rec.get("status", "error")
            status_label = "SUCCESS" if status == "success" else "FAILED"
            print(f"[{i}] Turn {turn} · {tool_name} — {status_label}")

            if status != "success":
                result = rec.get("result", "")
                if isinstance(result, str):
                    snippet = result.replace("\n", " ").strip()
                    if len(snippet) > 120:
                        snippet = snippet[:117] + "..."
                else:
                    snippet = str(result)
                if snippet:
                    print(f"      reason: {snippet}")

        print("=" * 60)

    def _load_tools_config(self) -> dict:
        """Loads and returns the TOML tool definitions configuration."""
        import os
        user_config_path = os.path.expanduser('~/.config/chatybot/tools_config.toml')
        package_config = os.path.join(os.path.dirname(__file__), 'tools_config.toml')
        from .config_sync import sync_toml_file
        sync_toml_file(package_config, user_config_path, "tools_config.toml")
        config_path = user_config_path if os.path.exists(user_config_path) else package_config
        
        try:
            import tomllib
            with open(config_path, 'rb') as f:
                return tomllib.load(f)
        except (ImportError, FileNotFoundError, Exception):
            try:
                import toml
                with open(config_path, 'r') as f:
                    return toml.load(f)
            except (ImportError, FileNotFoundError, Exception):
                return {}

    def generate_tool_context(self) -> str:
        """
        Generate tool definitions for LLM context injection.
        Reads tools_config.toml and formats tool schemas in a way the LLM can understand.
        
        Returns:
            Formatted string with tool definitions for LLM prompt
        """
        config = self._load_tools_config()
        if not config:
            print("Could not load tools_config.toml")
            return ""
        
        # Load custom agentic instructions and tool timeout if present
        config_section = config.get('config', {})
        if 'agentic_instructions' in config_section:
            self.agentic_instructions = config_section.get('agentic_instructions', '').strip()
        if 'tool_timeout' in config_section:
            try:
                self.tool_timeout = int(config_section.get('tool_timeout'))
            except (ValueError, TypeError):
                pass
        if 'rate_limit_delay' in config_section:
            try:
                toml_delay = float(config_section.get('rate_limit_delay'))
                if self._cached_rate_limit_delay is not None:
                    self.rate_limit_delay = self._cached_rate_limit_delay
                else:
                    self.rate_limit_delay = toml_delay
                    self._cached_rate_limit_delay = toml_delay
            except (ValueError, TypeError):
                pass
        if 'max_turns' in config_section:
            try:
                self.max_turns = int(config_section.get('max_turns'))
            except (ValueError, TypeError):
                pass
        if 'max_tool_calls_per_turn' in config_section:
            try:
                self.max_tool_calls_per_turn = int(config_section.get('max_tool_calls_per_turn'))
            except (ValueError, TypeError):
                pass
        if 'strip_thinking_from_filebanks' in config_section:
            val = config_section.get('strip_thinking_from_filebanks')
            if isinstance(val, bool):
                self.strip_thinking_from_filebanks = val
            elif str(val).lower() in ('true', '1', 'yes', 'on'):
                self.strip_thinking_from_filebanks = True
            elif str(val).lower() in ('false', '0', 'no', 'off'):
                self.strip_thinking_from_filebanks = False

        if 'session_mode' in config_section:
            self.session_mode = str(config_section.get('session_mode')).lower()
        if 'session_dir' in config_section:
            self.session_dir = os.path.expanduser(str(config_section.get('session_dir')))
        if 'session_strip_thinking' in config_section:
            val = str(config_section.get('session_strip_thinking')).lower()
            if val in ("separate", "true", "false"):
                self.session_strip_thinking = val
            else:
                print(f"Warning: Invalid session_strip_thinking '{val}'. Using default 'separate'.")
                self.session_strip_thinking = "separate"

        tools = config.get('tools', {})
        
        # Build tool context string
        lines = []
        lines.append("\n=== AVAILABLE TOOLS ===")
        lines.append("You have access to the following tools. Use them by outputting JSON in this format:")
        lines.append('{"tool": "tool_name", "arguments": {...}}')
        lines.append("")
        
        for tool_name, tool_meta in tools.items():
            config_enabled = tool_meta.get('enabled', False)
            is_enabled = self.tool_overrides.get(tool_name, config_enabled)
            if not is_enabled:
                continue
            
            desc = tool_meta.get('description', 'No description')
            params = tool_meta.get('parameters', {})
            
            lines.append(f"\n**{tool_name}**")
            lines.append(f"Description: {desc}")
            
            if params:
                lines.append("Parameters:")
                for param_name, param_rules in params.items():
                    param_type = param_rules.get('type', 'string')
                    param_desc = param_rules.get('description', '')
                    optional = param_rules.get('optional', False)
                    required = " (optional)" if optional else " (required)"
                    lines.append(f"  - {param_name}: {param_type}{required} - {param_desc}")
        
        # Append MCP tools to prompt context
        if self.mcp_manager and self.mcp_manager.cached_schemas:
            for server_name, tools_list in self.mcp_manager.cached_schemas.items():
                for tool in tools_list:
                    # Formatted name
                    mcp_tool_name = f"mcp__{server_name}__{tool.name}"
                    is_enabled = self.tool_overrides.get(mcp_tool_name, True)
                    if not is_enabled:
                        continue
                    
                    desc = getattr(tool, "description", "No description") or "No description"
                    lines.append(f"\n**{mcp_tool_name}**")
                    lines.append(f"Description: {desc}")
                    
                    # Extract input schema properties
                    input_schema = getattr(tool, "inputSchema", {})
                    if hasattr(input_schema, "get"):
                        properties = input_schema.get("properties", {})
                        required_list = input_schema.get("required", [])
                    else:
                        properties = {}
                        required_list = []
                    
                    if properties:
                        lines.append("Parameters:")
                        for param_name, param_meta in properties.items():
                            if hasattr(param_meta, "get"):
                                param_type = param_meta.get("type")
                                if not param_type and "anyOf" in param_meta:
                                    types = [t.get("type") for t in param_meta["anyOf"] if t.get("type") != "null" and t.get("type")]
                                    param_type = "|".join(types) if types else "string"
                                elif not param_type:
                                    param_type = "string"
                                param_desc = param_meta.get("description", "")
                            else:
                                param_type = "string"
                                param_desc = ""
                                
                            is_optional = param_name not in required_list
                            required_str = " (optional)" if is_optional else " (required)"
                            lines.append(f"  - {param_name}: {param_type}{required_str} - {param_desc}")
        
        lines.append("\n=== END TOOLS ===\n")
        if hasattr(self, "context_limiter") and self.context_limiter.context_limit:
            lim = self.context_limiter.context_limit
            lines.append(f"[CONTEXT LIMIT: You are operating under a hard input context limit of {lim:,} tokens. Keep tool calls, file reads, and responses concise to conserve context quota.]\n")
        
        context = '\n'.join(lines)
        self.tool_context = context
        return context

    async def handle_escape_command(self, command: str) -> Union[bool, str]:
        """
        Handle escape commands.

        Args:
            command: The command to handle

        Returns:
            True if the command was handled, False otherwise, or "EXECUTE_PROMPT" for prompt execution
        """
        import re
        parts = command.split(maxsplit=2)
        if self.logging_manager.logging_active:
            self.logging_manager.log_message(f"Escape command: {command}")
        raw_cmd = parts[0]
        cmd = self.i18n.resolve_command(raw_cmd.lower())

        if cmd == "/help":
            # Handle /help with optional query argument
            if len(parts) > 1:
                query = parts[1]
                print(self.help_system.get_help_text(query, i18n=self.i18n))
            else:
                print(self.help_system.get_help_text(None, i18n=self.i18n))
            return True

        elif cmd == "/trace":
            if len(parts) >= 3:
                subcmd = parts[1].lower()
                state = parts[2].lower()
                is_on = state == "on"
                if subcmd == "rawpayload":
                    self.trace_raw_payload = is_on
                    print(f"Trace rawpayload set to {is_on}")
                elif subcmd == "tps":
                    self.trace_tps = is_on
                    print(f"Trace tps set to {is_on}")
                elif subcmd == "tpsperf":
                    self.trace_tps_perf = is_on
                    print(f"Trace tpsperf set to {is_on}")
                elif subcmd == "imagedbg":
                    self.image_debug_mode = is_on
                    print(f"Trace imagedbg set to {is_on}")
                elif subcmd == "rerank":
                    self.trace_rerank = is_on
                    print(f"Trace rerank set to {is_on}")
                elif subcmd == "agentic_loop":
                    if not is_on:
                        # "off" disables automatic trace display but keeps the data
                        self.trace_agentic_loop = False
                        print("Agentic loop trace display disabled.")
                    else:
                        # "on" enables automatic trace display after each loop
                        self.trace_agentic_loop = True
                        print("Agentic loop trace display enabled.")
                else:
                    print("Unknown /trace subcommand. Use rawpayload, tps, tpsperf, imagedbg, rerank, or agentic_loop.")
            else:
                print("Usage: /trace <rawpayload|tps|tpsperf|imagedbg|rerank> <on|off>")
            return True

        elif cmd == "/debug":
            if len(parts) >= 2:
                subcmd = parts[1].lower()
                if subcmd == "payload":
                    self.debug_payload_mode = True
                    print("Debug payload mode activated. Next prompt will capture payload for editing.")
                    print("After entering your prompt, the payload will be opened in your editor.")
                elif subcmd == "response":
                    if len(parts) >= 3 and parts[2].lower() == "raw":
                        self.debug_response_raw = True
                        self.debug_response_mode = False # Mutual exclusion or should they both be true? 
                        # User said "in default it will attempt to print json dump... if it is 'response raw' it will just do a print"
                        # I'll set a specific flag for raw.
                        print("Debug response raw mode activated. Next completion will print the raw response.")
                    else:
                        self.debug_response_mode = True
                        self.debug_response_raw = False
                        print("Debug response mode activated. Next completion will print a JSON dump of the response.")
                elif subcmd == "vmem":
                    action = parts[2].lower() if len(parts) >= 3 else "status"
                    if action == "start":
                        self.start_vmem_monitoring()
                    elif action == "stop":
                        self.stop_vmem_monitoring()
                    elif action == "status":
                        self.show_vmem_status()
                    else:
                        print("Unknown vmem action. Use /debug vmem <start|stop|status>")
                else:
                    print("Unknown /debug subcommand. Use payload, response, response raw, or vmem.")
            else:
                print("Usage: /debug <payload|response [raw]|vmem [start|stop|status]>")
            return True

        elif cmd == "/prompt":
            if len(parts) < 2:
                print("Usage: /prompt <file>")
                return True

            file_path = command.split(maxsplit=1)[1].strip(" \"'")
            try:
                with open(file_path, "r") as f:
                    self.buffer_manager.prompt_buffer = f.read()
                print(f"\nPrompt loaded from '{file_path}':")
                print("-" * 40)
                print(self.buffer_manager.prompt_buffer)
                print("-" * 40)

                # Ask for confirmation only if not in script context
                if not self.script_context:
                    while True:
                        confirm = (
                            input("\nExecute this prompt? (Y/N): ").strip().lower()
                        )
                        if confirm in ["y", "yes"]:
                            print("\nExecuting prompt...")
                            # Set a flag to execute the prompt in the main loop
                            return "EXECUTE_PROMPT"
                        elif confirm in ["n", "no"]:
                            self.buffer_manager.prompt_buffer = ""
                            print("Prompt discarded.")
                            return True
                        else:
                            print("Please enter Y or N.")
                else:
                    # In script context, assume confirmation and return flag
                    return "EXECUTE_PROMPT"
            except Exception as e:
                print(f"Error reading prompt file: {str(e)}")
            return True

        elif cmd.startswith("/filebank"):
            # Handle filebank commands
            bank_num = cmd[9:]  # Extract the number after /filebank
            if not bank_num.isdigit() or int(bank_num) < 1 or int(bank_num) > 5:
                print(
                    "Invalid filebank number. Please use /filebank1 through /filebank5."
                )
                return True

            bank_num_int = int(bank_num)

            if len(parts) < 2:
                print(f"Usage: {cmd} <file> or {cmd} clear or {cmd} show [all]")
                return True

            subcommand = parts[1].lower()

            if subcommand == "clear":
                self.buffer_manager.clear_file_bank(bank_num_int)
                return True
            elif subcommand == "show":
                show_all = len(parts) > 2 and parts[2].lower() == "all"
                self.buffer_manager.show_file_bank(bank_num_int, show_all)
                return True
            else:
                # Assume it's a file path
                file_path = command.split(maxsplit=1)[1].strip(" \"'")
                try:
                    self.buffer_manager.load_file_to_bank(bank_num_int, file_path)
                except Exception as e:
                    print(f"Error reading file: {str(e)}")
                return True

        elif cmd.startswith("/imagebank"):
            # Handle imagebank commands
            bank_num = cmd[10:]  # Extract the number after /imagebank
            if not bank_num.isdigit() or int(bank_num) < 1 or int(bank_num) > 5:
                print(
                    "Invalid imagebank number. Please use /imagebank1 through /imagebank5."
                )
                return True

            bank_num_int = int(bank_num)

            if len(parts) < 2:
                print(f"Usage: {cmd} <file> or {cmd} clear or {cmd} show")
                return True

            subcommand = parts[1].lower()

            if subcommand == "clear":
                self.buffer_manager.clear_image_bank(bank_num_int)
                return True
            elif subcommand == "show":
                show_all = len(parts) > 2 and parts[2].lower() == "all"
                self.buffer_manager.show_image_bank(bank_num_int, show_all)
                return True
            else:
                # Assume it's a file path
                file_path = command.split(maxsplit=1)[1].strip(" \"'")
                try:
                    self.buffer_manager.load_image_to_bank(bank_num_int, file_path)
                except Exception as e:
                    print(f"Error reading image file: {str(e)}")
                return True

        elif cmd == "/file":
            if len(parts) < 2:
                print("Usage: /file <path>")
                return True

            file_path = command.split(maxsplit=1)[1].strip(" \"'")
            try:
                self.buffer_manager.load_file_to_buffer(file_path)
            except Exception as e:
                print(f"Error reading file: {str(e)}")
            return True

        # ================ Phase 2: Image Generation Commands ================

        elif cmd == "/imagine":
            """Generate image from text prompt."""
            if len(parts) < 2:
                print("Usage: /imagine <prompt>")
                print(f"  Current settings: size={self.image_size}, quality={self.image_quality}")
                print(f"  Current model: {self.config_manager.active_model_alias}")
                return True
            
            prompt = command.split(maxsplit=1)[1].strip()
            
            # Setup debug output if imagedbg trace is enabled
            debug_file = None
            debug_fd = None
            if self.image_debug_mode:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                debug_file = os.path.abspath(f"imagine_debug_{timestamp}.txt")
                try:
                    debug_fd = open(debug_file, "w")
                    print(f"[IMAGE_DEBUG] Started debug logging to {debug_file}")
                    debug_fd.write(f"[IMAGE_DEBUG] Started debug logging to {debug_file}\n")
                    debug_fd.write(f"[IMAGE_DEBUG] Prompt: {prompt}\n")
                    debug_fd.flush()
                except Exception as e:
                    print(f"[IMAGE_DEBUG] ERROR: Failed to open debug file: {e}")
                    debug_file = None
                    debug_fd = None
            
            try:
                # Get current model config
                model_alias = self.config_manager.active_model_alias
                if debug_file:
                    print(f"[IMAGE_DEBUG] Model alias: {model_alias}")
                    debug_fd.write(f"[IMAGE_DEBUG] Model alias: {model_alias}\n")
                try:
                    model_config = self.config_manager.get_model_config(model_alias)
                except ValueError as e:
                    print(f"Error: {str(e)}")
                    return True
                
                if debug_file:
                    print(f"[IMAGE_DEBUG] Vendor: {model_config.get('vendor')}")
                    print(f"[IMAGE_DEBUG] Model: {model_config.get('name')}")
                    debug_fd.write(f"[IMAGE_DEBUG] Vendor: {model_config.get('vendor')}\n")
                    debug_fd.write(f"[IMAGE_DEBUG] Model: {model_config.get('name')}\n")
                    debug_fd.flush()
                
                # Check if model supports image generation
                if not model_config.get("image_generation", False):
                    image_models = self.config_manager.list_image_capable_models()
                    if image_models:
                        print(f"Error: Current model '{model_alias}' does not support image generation.")
                        print(f"  Image-capable models: {', '.join(image_models)}")
                        print(f"  Switch to one of these first, e.g.: /model {image_models[0]}")
                    else:
                        print(f"Error: Current model '{model_alias}' does not support image generation.")
                        print("  No image-capable models configured in chat_config.toml")
                    return True
                
                try:
                    # Get vendor info from model config
                    vendor = model_config.get("vendor", "openai")
                    model_name = model_config.get("name", model_alias)
                    base_url = model_config.get("base_url", None)
                    api_key_env = model_config.get("api_key", "")
                    api_key = os.environ.get(api_key_env) if api_key_env else None
                    image_endpoint = model_config.get("image_endpoint", "/images/generations")
                    modalities = model_config.get("image_modalities", ["image", "text"])
                    
                    if debug_file:
                        print(f"[IMAGE_DEBUG] Starting image generation")
                        print(f"[IMAGE_DEBUG] Vendor: {vendor}, Model: {model_name}")
                        print(f"[IMAGE_DEBUG] Size: {self.image_size}, Quality: {self.image_quality}")
                        print(f"[IMAGE_DEBUG] Modalities: {modalities}")
                        debug_fd.write(f"[IMAGE_DEBUG] Starting image generation\n")
                        debug_fd.write(f"[IMAGE_DEBUG] Vendor: {vendor}, Model: {model_name}\n")
                        debug_fd.write(f"[IMAGE_DEBUG] Size: {self.image_size}, Quality: {self.image_quality}\n")
                        debug_fd.write(f"[IMAGE_DEBUG] Modalities: {modalities}\n")
                        debug_fd.flush()
                    
                    file_path, image_data = await self.image_generator.generate_image(
                        prompt,
                        vendor=vendor,
                        model_name=model_name,
                        size=self.image_size,
                        quality=self.image_quality,
                        endpoint=image_endpoint,
                        api_key=api_key,
                        base_url=base_url,
                        modalities=modalities,
                        size_manual=self.image_size_manual,
                    )
                    self.image_generator.last_generated_image = (file_path, image_data)
                    
                    if debug_file:
                        print(f"[IMAGE_DEBUG] Image generated successfully")
                        print(f"[IMAGE_DEBUG] File path: {file_path}")
                        print(f"[IMAGE_DEBUG] Image data length: {len(image_data)} bytes")
                        debug_fd.write(f"[IMAGE_DEBUG] Image generated successfully\n")
                        debug_fd.write(f"[IMAGE_DEBUG] File path: {file_path}\n")
                        debug_fd.write(f"[IMAGE_DEBUG] Image data length: {len(image_data)} bytes\n")
                        debug_fd.flush()
                    
                    print(f"Image generated and saved to: {file_path}")
                    
                except Exception as e:
                    if debug_file:
                        import traceback
                        print(f"[IMAGE_DEBUG] ERROR: {str(e)}")
                        debug_fd.write(f"[IMAGE_DEBUG] ERROR: {str(e)}\n")
                        traceback.print_exc()
                        debug_fd.write(f"[IMAGE_DEBUG] Traceback:\n")
                        traceback.print_exc(file=debug_fd)
                        debug_fd.flush()
                    print(f"Error generating image: {str(e)}")
                finally:
                    if debug_fd:
                        debug_fd.close()
                        print(f"[IMAGE_DEBUG] Debug output saved to {os.path.abspath(debug_file)}")
                        
            except Exception as e:
                if debug_fd:
                    debug_fd.close()
                if debug_file:
                    print(f"[IMAGE_DEBUG] Debug output saved to {os.path.abspath(debug_file)}")
                print(f"Error generating image: {str(e)}")
            return True

        elif cmd == "/saveimage":
            """Save the last generated image to a custom path."""
            file_path = None
            image_data = None
            
            # First try /imagine generated image
            if hasattr(self.image_generator, 'last_generated_image') and self.image_generator.last_generated_image is not None:
                file_path, image_data = self.image_generator.last_generated_image
            # Then try to extract from last chat response
            elif self.chat_history:

                last_response = self.chat_history[-1][1]
                try:
                    # Try to parse as JSON to find images
                    response_data = json.loads(last_response)
                    if response_data.get("choices"):
                        for choice in response_data["choices"]:
                            message = choice.get("message", {})
                            if message.get("images"):
                                # Get first image
                                first_image = message["images"][0]
                                if first_image.get("image_url", {}).get("url"):
                                    image_url = first_image["image_url"]["url"]
                                    if image_url.startswith("data:image"):
                                        # Extract base64 data
                                        image_data = image_url.split(",", 1)[1]
                                        break
                except (json.JSONDecodeError, KeyError, IndexError):
                    pass
                
                if image_data is None:
                    print("No image found in last chat response or /imagine output. Use /imagine to generate an image first.")
                    return True
            else:
                print("No generated image to save. Use /imagine first.")
                return True
            
            if len(parts) < 2:
                if file_path:
                    print(f"Image already saved to: {file_path}")
                else:
                    # For chat response images, we need to generate a filename
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    file_path = os.path.join("~", f"chat_response_image_{timestamp}.png")
                    print(f"Image extracted from chat response. Suggested save path: {file_path}")
                    print("Please specify a path: /saveimage <filename.png>")
                return True
            else:
                custom_path = command.split(maxsplit=1)[1].strip(" \"'")
                try:
                    import base64
                    # Expand ~ in path
                    custom_path = os.path.expanduser(custom_path)
                    os.makedirs(os.path.dirname(custom_path), exist_ok=True) if os.path.dirname(custom_path) else None
                    image_bytes = base64.b64decode(image_data)
                    with open(custom_path, "wb") as f:
                        f.write(image_bytes)
                    print(f"Image saved to: {custom_path}")
                    # Update last_generated_image so future /saveimage without args works
                    self.image_generator.last_generated_image = (custom_path, image_data)
                except Exception as e:
                    print(f"Error saving image: {str(e)}")
            return True

        elif cmd == "/imagesize":
            """Set image resolution."""
            if len(parts) < 2:
                print(f"Current image size: {self.image_size}")
                return True
            self.image_size = parts[1]
            self.image_size_manual = True
            print(f"Image size set to: {self.image_size}")
            return True

        elif cmd == "/imagequality":
            """Set image quality level."""
            if len(parts) < 2:
                print(f"Current image quality: {self.image_quality}")
                return True
            self.image_quality = parts[1]
            print(f"Image quality set to: {self.image_quality}")
            return True

        elif cmd == "/imagedir":
            """Set or get the default image directory."""
            if len(parts) < 2:
                print(f"Current image directory: {self.image_generator.get_image_directory()}")
            else:
                new_dir = command.split(maxsplit=1)[1].strip(" \"'")
                self.image_generator.set_directory(new_dir)
                self.image_manager.set_directory(new_dir)
                print(f"Image directory set to: {new_dir}")
            return True

        elif cmd == "/listimages":
            """List all saved images."""
            images = self.image_generator.list_images()
            if not images:
                print("No images found.")
                return True
            
            for date, date_images in images.items():
                print(f"\n{date}:")
                for filename, info in date_images.items():
                    prompt = info.get("prompt", "(external)")
                    if len(prompt) > 60:
                        prompt = prompt[:57] + "..."
                    model = info.get("model", "unknown")
                    vendor = info.get("vendor", "unknown")
                    print(f"  {filename:25} | {vendor:10} | {model:20} | {prompt}")
            return True

        elif cmd == "/showimage":
            """Show info about a specific image."""
            if len(parts) < 2:
                print("Usage: /showimage <date>/<filename> or /showimage <filename>")
                return True
            
            image_path = command.split(maxsplit=1)[1].strip(" \"'")
            
            # Parse date/filename
            if "/" in image_path:
                date, filename = image_path.split("/", 1)
            else:
                # Search for image across all dates
                all_images = self.image_generator.list_images()
                found = None
                for date, date_images in all_images.items():
                    if image_path in date_images:
                        found = (date, image_path)
                        break
                if not found:
                    print(f"Image not found: {image_path}")
                    return True
                date, filename = found
            
            info = self.image_generator.get_image_info(date, filename)
            if not info:
                print(f"Image not found: {image_path}")
                return True
            
            print(f"\nImage: {filename}")
            print(f"  Date: {date}")
            print(f"  Prompt: {info.get('prompt', 'N/A')}")
            print(f"  Vendor: {info.get('vendor', 'N/A')}")
            print(f"  Model: {info.get('model', 'N/A')}")
            print(f"  Timestamp: {info.get('timestamp', 'N/A')}")
            if info.get("size"):
                print(f"  Size: {info.get('size')}")
            if info.get("quality"):
                print(f"  Quality: {info.get('quality')}")
            
            file_path = os.path.join(self.image_generator.image_dir, date, filename)
            if os.path.exists(file_path):
                file_size_kb = os.path.getsize(file_path) / 1024
                print(f"  File size: {file_size_kb:.2f} KB")
            return True

        elif cmd.startswith("/loadimage"):
            """Load an image file into an image bank."""
            if len(parts) < 3:
                print("Usage: /loadimage <path> <imagebank1-5>")
                return True
            
            file_path = parts[1]
            bank_name = parts[2]
            
            # Extract bank number
            if bank_name.startswith("imagebank") and bank_name[9:].isdigit():
                bank_num = int(bank_name[9:])
            else:
                print("Invalid imagebank. Use imagebank1 through imagebank5.")
                return True
            
            try:
                mime_type, base64_data = self.image_manager.load_image_data(file_path)
                data_url = f"data:{mime_type};base64,{base64_data}"
                self.buffer_manager.image_banks[f"imagebank{bank_num}"] = data_url
                print(f"Image '{file_path}' loaded into {bank_name}.")
            except Exception as e:
                print(f"Error loading image: {str(e)}")
            return True

        elif cmd == "/clearfile":
            self.buffer_manager.clear_file_buffer()
            return True

        elif cmd == "/showfile":
            show_all = len(parts) > 1 and parts[1].lower() == "all"
            self.buffer_manager.show_file_buffer(show_all)
            return True

        elif cmd == "/model":
            is_info = False
            model_alias = None
            
            if len(parts) >= 2:
                p1 = parts[1].strip().lower()
                if p1 == "info":
                    is_info = True
                    model_alias = self.config_manager.active_model_alias
                elif len(parts) >= 3 and parts[2].strip().lower() == "info":
                    is_info = True
                    model_alias = parts[1].strip()
            
            if is_info:
                model_config = self.config_manager.get_model_config(model_alias)
                if not model_config:
                    print(f"Error: Model alias '{model_alias}' not found in configuration.")
                    return True
                
                model_name = model_config.get("name", "Unknown")
                context_window = None
                source = "Local Preset"
                
                if model_config.get("context_limit"):
                    context_window = model_config.get("context_limit")
                    source = "Config (Override)"
                else:
                    try:
                        client = self.get_openai_client(model_alias)
                        model_info = await client.models.retrieve(model_name)
                        if hasattr(model_info, "context_window"):
                            context_window = getattr(model_info, "context_window")
                            source = "API (Live)"
                        elif hasattr(model_info, "max_context_length"):
                            context_window = getattr(model_info, "max_context_length")
                            source = "API (Live)"
                        elif isinstance(model_info, dict):
                            context_window = model_info.get("context_window") or model_info.get("max_context_length")
                            source = "API (Live)"
                        elif hasattr(model_info, "extra_data") and isinstance(model_info.extra_data, dict):
                            context_window = model_info.extra_data.get("context_window") or model_info.extra_data.get("max_context_length")
                            source = "API (Live)"
                    except Exception:
                        pass
                
                if context_window is not None and not isinstance(context_window, (int, float)):
                    try:
                        context_window = int(context_window)
                    except (ValueError, TypeError):
                        context_window = None
                
                # Fallback local presets
                if not context_window:
                    presets = {
                        "gpt-4o": 128000,
                        "gpt-4o-mini": 128000,
                        "gpt-4": 8192,
                        "gpt-4-turbo": 128000,
                        "o1": 200000,
                        "o1-mini": 128000,
                        "o3-mini": 200000,
                        "claude-3-5-sonnet": 200000,
                        "claude-3-5-haiku": 200000,
                        "claude-3-opus": 200000,
                        "gemini-2.5-pro": 2097152,
                        "gemini-2.5-flash": 1048576,
                        "gemini-1.5-pro": 2097152,
                        "gemini-1.5-flash": 1048576,
                        "gemini-2.0-flash": 1048576,
                        "gemini": 1048576,
                        "mistral-large-latest": 128000,
                        "mistral-large-2512": 128000,
                        "mistral-medium-latest": 32768,
                        "mistral-small-latest": 32768,
                        "codestral-latest": 32768,
                        "devstral_1": 32768,
                        "devstral": 32768,
                        "nemotron": 128000,
                        "kimi": 262144,
                        "llama-3.3": 128000,
                        "llama-3.2": 128000,
                        "llama-3.1": 128000,
                        "llama-3": 8192,
                        "gemma-2-9b-it": 8192,
                        "gemma-2-27b-it": 8192,
                        "qwen2.5-coder-32b-instruct": 128000,
                        "deepseek-coder": 128000,
                        "deepseek-chat": 128000,
                        "deepseek-reasoner": 64000
                    }
                    for key, val in presets.items():
                        if key in model_name.lower():
                            context_window = val
                            break
                            
                print(f"\nModel Information: {model_name} (alias: {model_alias})")
                print("-" * (20 + len(model_name) + len(model_alias)))
                print(f"Provider:        {model_config.get('vendor', 'Unknown')}")
                print(f"Base URL:        {model_config.get('base_url', 'Default')}")
                
                if context_window:
                    if context_window >= 1000:
                        cw_str = f"{context_window:,} tokens ({context_window // 1000}k)"
                    else:
                        cw_str = f"{context_window} tokens"
                    print(f"Context Limit:   {cw_str} [{source}]")
                else:
                    print(f"Context Limit:   Unknown")
                
                max_tok = model_config.get("max_tokens")
                if max_tok:
                    print(f"Max Output:      {max_tok} tokens (Configured)")
                
                temp = model_config.get("temperature")
                if temp is not None:
                    print(f"Temperature:     {temp}")
                print("")
                return True

            if len(parts) < 2:
                # Show current model
                model_config = self.config_manager.get_model_config(
                    self.config_manager.active_model_alias
                )
                print(
                    f"Current model: {model_config['name']} (alias: {self.config_manager.active_model_alias})"
                )
                return True

            model_alias = parts[1]
            self.config_manager.set_active_model(model_alias)
            model_config = self.config_manager.get_model_config(model_alias)
            if hasattr(self, "context_limiter") and not self.context_limiter._user_set_limit:
                self.context_limiter.set_limit(model_config.get("context_limit"), from_user=False)
            print(f"Switched to model: {model_config['name']} (alias: {model_alias})")
            return True

        elif cmd == "/logging":
            if len(parts) < 2:
                status = "active" if self.logging_manager.logging_active else "inactive"
                hex_status = "on" if self.logging_manager.hex_mode else "off"
                print(f"Logging is {status} (hex mode: {hex_status}). Usage: /logging <start [hex]|end|hex [on|off]>")
                return True

            action = parts[1].lower()
            # parts was split with maxsplit=2, so parts[2] (if present) may hold
            # multiple space-separated sub-args. Re-split them into tokens so
            # e.g. "/logging start hex on" is parsed correctly.
            sub_args = parts[2].split() if len(parts) > 2 else []

            if action == "start":
                hex_aliases = ("hex", "raw", "on")
                hex_mode = any(a.lower() in hex_aliases for a in sub_args)
                self.logging_manager.start_logging(hex_mode=hex_mode)
            elif action in ("hex", "hexmode"):
                off_aliases = ("off", "false", "disable")
                on_aliases = ("on", "true", "enable")
                if sub_args and sub_args[0].lower() in off_aliases:
                    self.logging_manager.hex_mode = False
                    print("Logging hex mode disabled.")
                elif sub_args and sub_args[0].lower() in on_aliases:
                    self.logging_manager.hex_mode = True
                    if not self.logging_manager.logging_active:
                        self.logging_manager.start_logging(hex_mode=True)
                    else:
                        print("Logging hex mode enabled.")
                elif not sub_args:
                    # No argument: enable (preserves original toggle-on behavior)
                    self.logging_manager.hex_mode = True
                    if not self.logging_manager.logging_active:
                        self.logging_manager.start_logging(hex_mode=True)
                    else:
                        print("Logging hex mode enabled.")
                else:
                    print(f"Invalid hex mode argument '{sub_args[0]}'. Use 'on' or 'off'.")
            elif action in ("end", "stop"):
                self.logging_manager.stop_logging()
            else:
                print("Invalid logging action. Use 'start [hex]', 'hex [on|off]', or 'end'.")
            return True

        elif cmd == "/save":
            if len(parts) < 2:
                print("Usage: /save <file> [all] [nothink]")
                print("  /save file.txt - Save last response (omits thinking if /thinking is OFF)")
                print("  /save file.txt all - Save all chat history")
                print("  /save file.txt nothink - Force exclude thinking blocks")
                print("  /save file.txt withthink - Force include thinking blocks")
                return True

            # Parse parameters from the command
            # Syntax: /save <file_path> [all] [nothink] (in any order at the end)
            save_all = False
            strip_thinking = not self.show_thinking # Respect /thinking state by default
            
            words = command.split()
            # words[0] is "/save"
            # Extract any known flags at the end
            while len(words) > 2:
                last_word = words[-1].lower().strip(" \"'")
                if last_word == "all":
                    save_all = True
                    words.pop()
                elif last_word in ("nothink", "no-think", "nothinking", "no-thinking"):
                    strip_thinking = True
                    words.pop()
                elif last_word in ("withthink", "with-think", "withthinking", "with-thinking"):
                    strip_thinking = False
                    words.pop()
                else:
                    break
            
            # Reconstruct the file path
            file_path = " ".join(words[1:]).strip(" \"'")
            
            if not self.chat_history:
                print("No chat history to save.")
                return True
            
            def clean_thinking(text: str) -> str:
                import re
                return re.sub(
                    r"<think>.*?</think>\s*|<thought>.*?</thought>\s*", "", text, flags=re.DOTALL
                )
            
            try:
                directory = os.path.dirname(file_path)
                if directory and not os.path.exists(directory):
                    os.makedirs(directory, exist_ok=True)
                    print(f"Created directory path: '{directory}'")
                
                if save_all:
                    # Save all chat history
                    with open(file_path, "w") as f:
                        for i, (prompt, response) in enumerate(self.chat_history, 1):
                            res_to_save = clean_thinking(response) if strip_thinking else response
                            f.write(f"=== Conversation {i} ===\n")
                            f.write(f"PROMPT: {prompt}\n\n")
                            f.write(f"RESPONSE: {res_to_save}\n\n")
                            f.write("---\n\n")
                    print(f"All chat history ({len(self.chat_history)} conversations) saved to '{file_path}'.")
                else:
                    # Save last response only (default behavior)
                    last_response = self.chat_history[-1][1]
                    res_to_save = clean_thinking(last_response) if strip_thinking else last_response
                    with open(file_path, "w") as f:
                        f.write(res_to_save)
                    print(f"Last chat completion saved to '{file_path}'.")

                    # If note mode is on, process the file to extract code blocks
                    if self.note_mode:
                        print(f"Note mode is ON. Processing file '{file_path}'...")
                        process_file(file_path)
            except Exception as e:
                print(f"Error saving file: {str(e)}")
            return True

        elif cmd == "/session":
            if len(parts) < 2:
                print(f"Active Session ID: {self.active_session_id or 'None'}")
                print(f"Custom Name: {self.active_session_name or 'None'}")
                print(f"Session Mode: {self.session_mode}")
                print(f"Turn Count: {len(self.session_turns)}")
                print(f"Session Directory: {self.get_sessions_dir()}")
                return True

            subcmd = parts[1].lower()

            if subcmd == "start":
                if len(parts) < 3:
                    print("Usage: /session start <name>")
                    return True
                session_name = " ".join(parts[2:]).strip(" \"'")
                self._release_session_lock()
                self.chat_history.clear()
                self.session_turns.clear()
                now = datetime.now()
                model_alias = getattr(self.config_manager, "active_model_alias", None) or "default"
                self.session_model_alias = model_alias
                self.active_session_id = self._generate_session_id(model_alias)
                self.active_session_name = session_name
                self.session_created_at = now.isoformat()
                self.session_first_prompt_slug = None
                self.session_notes = None
                self.session_mode = "on" if self.session_mode == "off" else self.session_mode
                self._acquire_session_lock(self.active_session_id)
                self.save_active_session()
                self.buffer_manager.set_script_var('SESSION_NAME', session_name, allow_protected=True)
                print(f"Started new session '{session_name}' (ID: {self.active_session_id})")
                return True

            elif subcmd == "auto":
                if len(parts) < 3:
                    print(f"Auto Session Mode is currently: {'ON' if self.session_mode in ('on', 'auto') else 'OFF'}")
                    return True
                action = parts[2].lower()
                if action in ("on", "1", "true"):
                    self.session_mode = "auto"
                    print("Auto session mode enabled.")
                elif action in ("off", "0", "false"):
                    self.session_mode = "off"
                    print("Auto session mode disabled.")
                else:
                    print("Invalid action. Use 'on' or 'off'.")
                return True

            elif subcmd in ("stop", "off"):
                self._release_session_lock()
                self.session_mode = "off"
                print("Session recording paused.")
                return True

            elif subcmd == "status":
                print(f"Active Session ID: {self.active_session_id or 'None'}")
                print(f"Custom Name: {self.active_session_name or 'None'}")
                print(f"Session Mode: {self.session_mode}")
                print(f"Turn Count: {len(self.session_turns)}")
                print(f"Session Directory: {self.get_sessions_dir()}")
                if self.session_notes:
                    print(f"Notes: {self.session_notes}")
                return True

            elif subcmd == "note":
                if len(parts) < 3:
                    if self.session_notes:
                        print(f"Active Session Notes:\n{self.session_notes}")
                    else:
                        print("No notes set for active session. Usage: /session note <text>")
                    return True
                raw_note = command.split(maxsplit=2)[2] if len(command.split(maxsplit=2)) > 2 else ""
                note_text = raw_note.strip(" \"'")
                if len(note_text) > 1024:
                    print(f"Warning: Note exceeds 1024 characters ({len(note_text)} chars). Truncating...")
                    note_text = note_text[:1024]
                self._ensure_active_session()
                self.session_notes = note_text
                self.save_active_session()
                print(f"Session notes updated ({len(note_text)} chars).")
                return True

            elif subcmd == "save":
                if len(parts) >= 3:
                    custom_name = " ".join(parts[2:]).strip(" \"'")
                    self.active_session_name = custom_name
                self._ensure_active_session()
                self.save_active_session()
                print(f"Session '{self.active_session_name or self.active_session_id}' saved to disk.")
                return True

            elif subcmd == "list":
                # Parse pagination parameters
                limit = 10  # Default limit
                offset = 0
                model_filter = None

                if len(parts) >= 3:
                    param = parts[2].lower()
                    if param == "all":
                        limit = None
                    elif param.startswith("limit="):
                        try:
                            limit = int(param[6:])
                        except ValueError:
                            print("Invalid limit value. Using default limit of 10.")
                    elif param.startswith("range="):
                        try:
                            range_parts = param[6:].split(":")
                            if len(range_parts) == 2:
                                offset, limit = map(int, range_parts)
                            else:
                                offset = int(range_parts[0])
                        except ValueError:
                            print("Invalid range format. Use range=start:end. Using default limit of 10.")
                    elif param.startswith("model="):
                        model_filter = param[6:].lower()

                sessions_dir = self.get_sessions_dir()
                if not os.path.exists(sessions_dir):
                    print("No saved sessions found.")
                    return True
                files = [f for f in os.listdir(sessions_dir) if f.endswith(".json") or f.endswith(".json.gz")]
                if not files:
                    print("No saved sessions found.")
                    return True
                
                # Filter by model if specified
                if model_filter:
                    files = [f for f in files if model_filter in f.lower()]
                
                # Sort files by updated_at timestamp from session metadata
                files_with_dates = []
                import gzip
                for fname in files:
                    fpath = os.path.join(sessions_dir, fname)
                    try:
                        open_fn = gzip.open if fname.endswith(".gz") else open
                        with open_fn(fpath, "rt", encoding="utf-8") as sf:
                            sdata = json.load(sf)
                            updated_at = sdata.get("updated_at", "1970-01-01T00:00:00")
                            files_with_dates.append((fname, updated_at))
                    except Exception:
                        files_with_dates.append((fname, "1970-01-01T00:00:00"))

                # Sort by updated_at in descending order (newest first)
                files_with_dates.sort(key=lambda x: x[1], reverse=True)
                files = [fname for fname, _ in files_with_dates]
                
                # Apply pagination
                if limit is not None:
                    files = files[offset:offset+limit]
                print("\nAvailable Sessions:")
                for idx, fname in enumerate(files, 1):
                    fpath = os.path.join(sessions_dir, fname)
                    try:
                        open_fn = gzip.open if fname.endswith(".gz") else open
                        with open_fn(fpath, "rt", encoding="utf-8") as sf:
                            sdata = json.load(sf)
                            sid = sdata.get("session_id", fname)
                            cname = sdata.get("custom_name")
                            slug = sdata.get("first_prompt_slug", "")
                            turns_cnt = len(sdata.get("turns", []))
                            upd = sdata.get("updated_at", "")[:16].replace("T", " ")
                            snote = sdata.get("notes")
                            name_str = f" (Name: '{cname}')" if cname else ""
                            gz_str = " [compressed]" if fname.endswith(".gz") else ""
                            print(f"  {idx}. {sid}{name_str}{gz_str}")
                            print(f"     ├─ Prompt: \"{slug}\"")
                            if snote:
                                short_note = snote[:60] + "..." if len(snote) > 60 else snote
                                print(f"     ├─ Notes: \"{short_note}\"")
                            print(f"     └─ Turns: {turns_cnt} exchanges (Updated: {upd})")
                    except Exception:
                        print(f"  {idx}. {fname}")
                print("")
                return True

            elif subcmd == "use":
                if len(parts) < 3:
                    print("Usage: /session use <session_id|custom_name>")
                    return True
                target = " ".join(parts[2:]).strip(" \"'")
                matched_file = self._resolve_session_file(target)

                if not matched_file:
                    print(f"Error: Session '{target}' not found.")
                    return True

                import gzip
                open_fn = gzip.open if matched_file.endswith(".gz") else open
                with open_fn(matched_file, "rt", encoding="utf-8") as sf:
                    sdata = json.load(sf)
                    self._release_session_lock()
                    self.active_session_id = sdata.get("session_id")
                    self.active_session_name = sdata.get("custom_name")
                    self.session_model_alias = sdata.get("model_alias")
                    self.session_created_at = sdata.get("created_at")
                    self.session_first_prompt_slug = sdata.get("first_prompt_slug")
                    self.session_notes = sdata.get("notes")
                    self.session_turns = sdata.get("turns", [])

                    # Hydrate chat_history for LLM completion context
                    self.chat_history.clear()
                    for turn in self.session_turns:
                        self.chat_history.append((turn.get("prompt", ""), turn.get("response", "")))

                self.session_mode = "on" if self.session_mode == "off" else self.session_mode
                self._acquire_session_lock(self.active_session_id)
                self.buffer_manager.set_script_var('SESSION_NAME', self.active_session_name or self.active_session_id, allow_protected=True)
                print(f"Loaded session '{self.active_session_name or self.active_session_id}' ({len(self.session_turns)} exchanges).")
                return True

            elif subcmd == "show":
                show_thinking = False
                if len(parts) >= 3 and parts[2].lower() in ("--thinking", "-t"):
                    show_thinking = True

                if not self.session_turns:
                    print("No exchanges in active session.")
                    return True

                print("\n" + "=" * 80)
                name_str = f" (Name: {self.active_session_name})" if self.active_session_name else ""
                model_alias = self.session_model_alias or "default"
                print(f"SESSION: {self.active_session_id or 'Unsaved'}{name_str}")
                print(f"Model: {model_alias} | Created: {self.session_created_at or 'N/A'} | Total Turns: {len(self.session_turns)}")
                if self.session_notes:
                    print(f"Notes: {self.session_notes}")
                print("=" * 80 + "\n")

                for turn in self.session_turns:
                    t_id = turn.get("turn_id", 1)
                    t_model = turn.get("model_alias")
                    model_str = f" ({t_model})" if t_model else ""
                    print(f"[Turn {t_id}]{model_str}")
                    print(f"User: {turn.get('prompt')}")
                    if show_thinking and "thinking" in turn:
                        print("Thinking:")
                        for t_line in turn["thinking"].splitlines():
                            print(f"  {t_line}")
                    print(f"Assistant: {turn.get('response')}")
                    if "agentic_loop" in turn:
                        t_count = len(turn["agentic_loop"])
                        print(f"(Tools executed: {t_count})")
                    print("\n" + "-" * 80 + "\n")
                print("=" * 80 + "\n")
                return True

            elif subcmd == "export":
                if len(parts) < 3:
                    print("Usage: /session export <filepath.md> [--thinking|-t]")
                    return True
                
                show_thinking = False
                raw_args = command.split(maxsplit=2)[2] if len(command.split(maxsplit=2)) > 2 else ""
                words = raw_args.split()
                if words and words[-1].lower() in ("--thinking", "-t"):
                    show_thinking = True
                    words.pop()
                
                export_path = " ".join(words).strip(" \"'")
                if not self.session_turns:
                    print("No exchanges in active session to export.")
                    return True

                md_lines = []
                name_title = self.active_session_name or self.active_session_id or "Session Transcript"
                model_alias = self.session_model_alias or "default"
                md_lines.append(f"# Session Transcript: {name_title}\n")
                md_lines.append(f"- **Session ID**: `{self.active_session_id or 'N/A'}`")
                md_lines.append(f"- **Model**: `{model_alias}`")
                md_lines.append(f"- **Created**: {self.session_created_at or 'N/A'}")
                md_lines.append(f"- **Total Exchanges**: {len(self.session_turns)}")
                if self.session_notes:
                    md_lines.append(f"- **Notes**: {self.session_notes}")
                md_lines.append("\n---\n")

                for turn in self.session_turns:
                    t_id = turn.get("turn_id", 1)
                    t_model = turn.get("model_alias")
                    header = f"## Turn {t_id}"
                    if t_model:
                        header += f" ({t_model})"
                    md_lines.append(f"{header}\n")
                    md_lines.append("### User")
                    md_lines.append(f"{turn.get('prompt')}\n")
                    if show_thinking and "thinking" in turn:
                        md_lines.append("### Reasoning Trace")
                        for t_line in turn["thinking"].splitlines():
                            md_lines.append(f"> {t_line}")
                        md_lines.append("")
                    md_lines.append("### Assistant")
                    md_lines.append(f"{turn.get('response')}\n")
                    if "agentic_loop" in turn:
                        md_lines.append("#### Tools Executed")
                        for step in turn["agentic_loop"]:
                            if isinstance(step, dict):
                                tname = step.get("tool", "unknown_tool")
                                md_lines.append(f"- `{tname}`")
                            else:
                                md_lines.append(f"- `{step}`")
                        md_lines.append("")
                    md_lines.append("---\n")

                try:
                    with open(export_path, "w", encoding="utf-8") as f:
                        f.write("\n".join(md_lines))
                    print(f"Exported session transcript to '{export_path}'.")
                except Exception as e:
                    print(f"Error exporting session: {e}")
                return True

            elif subcmd in ("info", "stats"):
                sessions_dir = self.get_sessions_dir()
                if not os.path.exists(sessions_dir):
                    print("No session directory found.")
                    return True

                files = [f for f in os.listdir(sessions_dir) if f.endswith(".json") or f.endswith(".json.gz")]
                if not files:
                    print("No saved sessions.")
                    return True

                import gzip
                total_bytes = 0
                oldest_file = None
                newest_file = None
                oldest_mtime = float("inf")
                newest_mtime = 0
                largest_file = None
                largest_bytes = 0

                for fname in files:
                    fp = os.path.join(sessions_dir, fname)
                    sz = os.path.getsize(fp)
                    mtime = os.path.getmtime(fp)
                    total_bytes += sz
                    if mtime < oldest_mtime:
                        oldest_mtime = mtime
                        oldest_file = fname
                    if mtime > newest_mtime:
                        newest_mtime = mtime
                        newest_file = fname
                    if sz > largest_bytes:
                        largest_bytes = sz
                        largest_file = fname

                kb = total_bytes / 1024.0
                mb = kb / 1024.0
                size_str = f"{mb:.2f} MB ({kb:.1f} KB)" if mb >= 1.0 else f"{kb:.2f} KB"
                largest_kb = largest_bytes / 1024.0
                largest_mb = largest_kb / 1024.0
                largest_str = f"{largest_mb:.2f} MB" if largest_mb >= 1.0 else f"{largest_kb:.2f} KB"

                oldest_dt = datetime.fromtimestamp(oldest_mtime).strftime("%Y-%m-%d %H:%M:%S") if oldest_file else "N/A"
                newest_dt = datetime.fromtimestamp(newest_mtime).strftime("%Y-%m-%d %H:%M:%S") if newest_file else "N/A"

                print("\n" + "=" * 60)
                print("SESSION WORKSPACE METRICS")
                print("=" * 60)
                print(f"Total Sessions:   {len(files)}")
                print(f"Space Consumed:   {size_str}")
                print(f"Oldest Session:   {oldest_file or 'N/A'} ({oldest_dt})")
                print(f"Newest Session:   {newest_file or 'N/A'} ({newest_dt})")
                print(f"Largest Session:  {largest_file or 'N/A'} ({largest_str})")
                print("=" * 60 + "\n")
                return True

            elif subcmd == "delete":
                if len(parts) < 3:
                    print("Usage: /session delete <name|id|--all>")
                    return True
                target = parts[2].lower()

                if target == "--all":
                    try:
                        confirm = input("Are you sure you want to delete ALL saved sessions? (y/N): ").strip().lower()
                    except EOFError:
                        print("Delete all cancelled (non-interactive input).")
                        return True
                    if confirm in ("y", "yes"):
                        sessions_dir = self.get_sessions_dir()
                        count = 0
                        for f in os.listdir(sessions_dir):
                            if f.endswith(".json") or f.endswith(".json.gz"):
                                os.remove(os.path.join(sessions_dir, f))
                                count += 1
                            elif f.endswith(".lock"):
                                os.remove(os.path.join(sessions_dir, f))
                        self._release_session_lock()
                        self.active_session_id = None
                        self.active_session_name = None
                        self.session_turns.clear()
                        self.chat_history.clear()
                        print(f"Deleted all {count} saved sessions.")
                    else:
                        print("Delete all cancelled.")
                    return True

                matched_file = self._resolve_session_file(parts[2])
                if not matched_file:
                    print(f"Error: Session '{parts[2]}' not found.")
                    return True

                os.remove(matched_file)
                base_name = os.path.basename(matched_file)
                if self.active_session_id and (
                    base_name == f"{self.active_session_id}.json"
                    or base_name == f"{self.active_session_id}.json.gz"
                    or self.active_session_name == parts[2]
                ):
                    self._release_session_lock()
                    self.active_session_id = None
                    self.active_session_name = None
                    self.session_turns.clear()
                    self.chat_history.clear()
                print(f"Deleted session file '{base_name}'.")
                return True

            elif subcmd == "merge":
                raw_merge_args = command.split(maxsplit=2)[2] if len(command.split(maxsplit=2)) > 2 else ""
                merge_words = raw_merge_args.split()
                if len(merge_words) < 3:
                    print("Usage: /session merge <target_name> <session_a> <session_b> [session_c ...]")
                    return True

                target_name = merge_words[0].strip(" \"'")
                source_targets = merge_words[1:]
                import gzip

                merged_turns = []
                merged_models = []
                first_slug = None

                for st in source_targets:
                    sf_path = self._resolve_session_file(st)
                    if not sf_path:
                        print(f"Error: Source session '{st}' not found. Merge aborted.")
                        return True
                    open_fn = gzip.open if sf_path.endswith(".gz") else open
                    with open_fn(sf_path, "rt", encoding="utf-8") as sf:
                        sdata = json.load(sf)
                        if not first_slug:
                            first_slug = sdata.get("first_prompt_slug")
                        m_alias = sdata.get("model_alias", "default")
                        if m_alias not in merged_models:
                            merged_models.append(m_alias)
                        for turn in sdata.get("turns", []):
                            new_turn = dict(turn)
                            new_turn["turn_id"] = len(merged_turns) + 1
                            merged_turns.append(new_turn)

                now = datetime.now()
                model_alias = "_".join(merged_models)
                timestamp = now.strftime("%Y%m%d_%H%M%S")
                new_session_id = f"merged_{timestamp}"

                payload = {
                    "session_id": new_session_id,
                    "model_alias": model_alias,
                    "created_at": now.isoformat(),
                    "updated_at": now.isoformat(),
                    "first_prompt_slug": first_slug or "merged_session",
                    "custom_name": target_name,
                    "turns": merged_turns
                }

                out_path = os.path.join(self.get_sessions_dir(), f"{new_session_id}.json")
                with open(out_path, "w", encoding="utf-8") as out_f:
                    json.dump(payload, out_f, indent=2, ensure_ascii=False)

                print(f"Merged {len(source_targets)} sessions into '{target_name}' (ID: {new_session_id}) with {len(merged_turns)} exchanges.")
                return True

            elif subcmd == "compress":
                older_than_days = None
                if len(parts) >= 3 and parts[2].lower() != "all":
                    try:
                        older_than_days = float(parts[2])
                    except ValueError:
                        print("Usage: /session compress [older_than_days|all]")
                        return True

                sessions_dir = self.get_sessions_dir()
                if not os.path.exists(sessions_dir):
                    print("No sessions directory found.")
                    return True

                import gzip
                now_ts = time.time()
                count = 0
                saved_bytes = 0
                active_json = f"{self.active_session_id}.json" if self.active_session_id else None

                for fname in os.listdir(sessions_dir):
                    if fname.endswith(".json") and not fname.endswith(".json.gz"):
                        if fname == active_json:
                            continue
                        fp = os.path.join(sessions_dir, fname)
                        mtime = os.path.getmtime(fp)
                        age_days = (now_ts - mtime) / 86400.0

                        if older_than_days is None or age_days >= older_than_days:
                            gz_path = fp + ".gz"
                            orig_sz = os.path.getsize(fp)
                            with open(fp, "rb") as f_in:
                                with gzip.open(gz_path, "wb") as f_out:
                                    f_out.writelines(f_in)
                            new_sz = os.path.getsize(gz_path)
                            saved_bytes += (orig_sz - new_sz)
                            os.remove(fp)
                            count += 1

                saved_kb = saved_bytes / 1024.0
                print(f"Compressed {count} session file(s). Saved {saved_kb:.1f} KB of disk space.")
                return True

            elif subcmd == "prune":
                keep_n = None
                max_days = None
                max_size_mb = None

                for arg in parts[2:]:
                    arg_l = arg.lower()
                    if arg_l.startswith("keep="):
                        try:
                            keep_n = int(arg_l.split("=", 1)[1])
                        except ValueError:
                            pass
                    elif arg_l.startswith("days="):
                        try:
                            max_days = float(arg_l.split("=", 1)[1])
                        except ValueError:
                            pass
                    elif arg_l.startswith("size="):
                        try:
                            max_size_mb = float(arg_l.split("=", 1)[1])
                        except ValueError:
                            pass

                if keep_n is None and max_days is None and max_size_mb is None:
                    print("Usage: /session prune [keep=N] [days=D] [size=M]")
                    print("Example: /session prune keep=10 days=30 size=50")
                    return True

                sessions_dir = self.get_sessions_dir()
                if not os.path.exists(sessions_dir):
                    print("No session directory found.")
                    return True

                active_names = set()
                if self.active_session_id:
                    active_names.add(f"{self.active_session_id}.json")
                    active_names.add(f"{self.active_session_id}.json.gz")

                file_entries = []
                for fname in os.listdir(sessions_dir):
                    if fname in active_names:
                        continue
                    if fname.endswith(".json") or fname.endswith(".json.gz"):
                        fp = os.path.join(sessions_dir, fname)
                        file_entries.append({
                            "path": fp,
                            "name": fname,
                            "mtime": os.path.getmtime(fp),
                            "size": os.path.getsize(fp)
                        })

                # Sort oldest to newest
                file_entries.sort(key=lambda x: x["mtime"])
                now_ts = time.time()
                to_delete = set()

                # Filter 1: days=D
                if max_days is not None:
                    for entry in file_entries:
                        age_days = (now_ts - entry["mtime"]) / 86400.0
                        if age_days > max_days:
                            to_delete.add(entry["path"])

                # Filter 2: keep=N
                if keep_n is not None and len(file_entries) > keep_n:
                    excess = len(file_entries) - keep_n
                    for entry in file_entries[:excess]:
                        to_delete.add(entry["path"])

                # Filter 3: size=M (total workspace size cap)
                if max_size_mb is not None:
                    target_bytes = max_size_mb * 1024.0 * 1024.0
                    current_total = sum(e["size"] for e in file_entries if e["path"] not in to_delete)
                    for entry in file_entries:
                        if current_total <= target_bytes:
                            break
                        if entry["path"] not in to_delete:
                            to_delete.add(entry["path"])
                            current_total -= entry["size"]

                deleted_count = 0
                for path in to_delete:
                    try:
                        os.remove(path)
                        deleted_count += 1
                    except Exception as e:
                        print(f"Error removing {path}: {e}")

                print(f"Pruned {deleted_count} session file(s).")
                return True

            else:
                print(f"Unknown session subcommand: {subcmd}. Use start, auto, stop, status, save, list, use, show, export, info, delete, merge, compress, prune.")
                return True

        elif cmd == "/notemode":
            if len(parts) < 2:
                print(f"Note mode is currently {'ON' if self.note_mode else 'OFF'}")
                return True

            action = parts[1].lower()
            if action == "on":
                self.note_mode = True
                print(
                    "Note mode enabled. Code blocks will be extracted when using /save."
                )
            elif action == "off":
                self.note_mode = False
                print("Note mode disabled.")
            else:
                print("Invalid note mode action. Use 'on' or 'off'.")
            return True

        elif cmd == "/codeonly":
            self.code_only_flag = True
            print("Code-only mode enabled.")
            return True

        elif cmd == "/codeoff":
            self.code_only_flag = False
            print("Code-only mode disabled.")
            return True

        elif cmd == "/multiline":
            self.multi_line_mode = not self.multi_line_mode
            print(
                f"Multi-line mode {'enabled' if self.multi_line_mode else 'disabled'}. "
                f"{'Use ;; to end input' if self.multi_line_mode else ''}"
            )
            return True

        elif cmd == "/system":
            if len(parts) < 2:
                print(f"Current system message: {self.config_manager.system_message}")
                return True

            self.config_manager.system_message = command.split(maxsplit=1)[1].strip(
                " \"'"
            )
            print(f"System message updated: {self.config_manager.system_message}")
            return True

        elif cmd == "/temp":
            if len(parts) < 2:
                current_temp = (
                    self.temperature
                    if self.temperature is not None
                    else self.config_manager.get_model_config(
                        self.config_manager.active_model_alias
                    ).get("temperature", 0.7)
                )
                print(f"Current temperature: {current_temp}")
                return True

            arg = parts[1].strip().lower()
            if arg in ["default", "reset"]:
                self.temperature = None
                print("Temperature reset to model default")
                return True

            try:
                temp = float(arg)
                if not 0.0 <= temp <= 2.0:
                    raise ValueError
                self.temperature = temp
                print(f"Temperature set to {temp}")
            except ValueError:
                print(
                    "Invalid temperature value. Please provide a number between 0.0 and 2.0, or 'default'."
                )
            return True

        elif cmd == "/maxtokens":
            if len(parts) < 2:
                current_max = (
                    self.config_manager.max_tokens
                    if self.config_manager.max_tokens is not None
                    else self.config_manager.get_model_config(
                        self.config_manager.active_model_alias
                    ).get("max_tokens", "Default")
                )
                print(f"Current max tokens: {current_max}")
                return True

            try:
                max_tokens = int(parts[1])
                if max_tokens <= 0:
                    raise ValueError
                self.config_manager.max_tokens = max_tokens
                print(f"Max tokens set to {max_tokens}")
            except ValueError:
                print("Invalid max tokens value. Please provide a positive integer.")
            return True

        elif cmd == "/context_limit":
            if len(parts) < 2:
                curr = self.context_limiter.context_limit
                if curr:
                    print(f"Current context limit: {curr} tokens")
                else:
                    print("Context limit is disabled (no limit set)")
                return True

            val_str = parts[1].strip().lower()
            if val_str in ("off", "0", "none", "disable", "disabled"):
                self.context_limiter.set_limit(None, from_user=True)
                print("Context limit disabled.")
            else:
                try:
                    limit_val = int(val_str)
                    if limit_val <= 0:
                        self.context_limiter.set_limit(None, from_user=True)
                        print("Context limit disabled.")
                    else:
                        self.context_limiter.set_limit(limit_val, from_user=True)
                        print(f"Context limit set to {limit_val} tokens.")
                except ValueError:
                    print("Invalid context limit. Usage: /context_limit <tokens>|off")

            if self.tool_mode:
                context = self.generate_tool_context()
                if hasattr(self, "buffer_manager"):
                    self.buffer_manager.set_script_var('TOOL_CONTEXT', context)
            return True

        elif cmd == "/auto_truncate":
            if len(parts) < 2:
                if self.context_limiter.auto_truncate:
                    pct_str = f" ({int(self.context_limiter.truncate_pct)}%)" if self.context_limiter.truncate_pct != 100.0 else ""
                    print(f"Auto-truncation is currently enabled{pct_str}.")
                else:
                    print("Auto-truncation is currently disabled.")
                return True

            opt = parts[1].strip().lower()
            if opt in ("on", "true", "enable", "yes"):
                self.context_limiter.set_auto_truncate(True, pct=100.0)
                print("Auto-truncation enabled at 100% of context limit.")
            elif opt in ("off", "false", "disable", "no"):
                self.context_limiter.set_auto_truncate(False)
                print("Auto-truncation disabled.")
            else:
                num_str = opt.rstrip("%")
                try:
                    pct_val = float(num_str)
                    if pct_val > 100.0:
                        print("Error: Auto-truncate percentage cannot exceed 100%. Usage: /auto_truncate [on|off|10-100]")
                    elif pct_val < 10.0:
                        self.context_limiter.set_auto_truncate(False)
                        print("Auto-truncation disabled (percentage below 10%).")
                    else:
                        display_pct = int(pct_val) if pct_val.is_integer() else pct_val
                        self.context_limiter.set_auto_truncate(True, pct=pct_val)
                        print(f"Auto-truncation enabled at {display_pct}% of context limit.")
                except ValueError:
                    print("Invalid option. Usage: /auto_truncate [on|off|10-100]")
            return True

        elif cmd == "/top_p":
            if len(parts) < 2:
                if self.top_p in ("off", "none", "disable", False):
                    current_tp = "Disabled (off)"
                elif self.top_p is not None:
                    current_tp = self.top_p
                else:
                    cfg_tp = self.config_manager.get_model_config(
                        self.config_manager.active_model_alias
                    ).get("top_p", "Default")
                    current_tp = f"{cfg_tp} (model default)"
                print(f"Current top_p: {current_tp}")
                return True

            arg = parts[1].strip().lower()
            if arg in ["off", "none", "disable"]:
                self.top_p = "off"
                print("top_p disabled (will not be sent in payloads)")
            elif arg in ["default", "reset"]:
                self.top_p = None
                print("top_p reset to model default")
            else:
                try:
                    val = float(arg)
                    if not 0.0 <= val <= 1.0:
                        raise ValueError
                    self.top_p = val
                    print(f"top_p set to {val}")
                except ValueError:
                    print("Invalid top_p value. Please enter a float between 0.0 and 1.0, 'off', 'none', or 'default'.")
            return True

        elif cmd == "/top_k":
            if len(parts) < 2:
                if self.top_k in ("off", "none", "disable", False):
                    current_tk = "Disabled (off)"
                elif self.top_k is not None:
                    current_tk = self.top_k
                else:
                    cfg_tk = self.config_manager.get_model_config(
                        self.config_manager.active_model_alias
                    ).get("top_k", "Default")
                    current_tk = f"{cfg_tk} (model default)"
                print(f"Current top_k: {current_tk}")
                return True

            arg = parts[1].strip().lower()
            if arg in ["off", "none", "disable"]:
                self.top_k = "off"
                print("top_k disabled (will not be sent in payloads)")
            elif arg in ["default", "reset"]:
                self.top_k = None
                print("top_k reset to model default")
            else:
                try:
                    val = int(arg)
                    if val <= 0:
                        raise ValueError
                    self.top_k = val
                    print(f"top_k set to {val}")
                except ValueError:
                    print("Invalid top_k value. Please enter a positive integer, 'off', 'none', or 'default'.")
            return True

        elif cmd == "/freq_penalty":
            if len(parts) < 2:
                if self.freq_penalty in ("off", "none", "disable", False):
                    current_fp = "Disabled (off)"
                elif self.freq_penalty is not None:
                    current_fp = self.freq_penalty
                else:
                    cfg_fp = self.config_manager.get_model_config(
                        self.config_manager.active_model_alias
                    ).get("frequency_penalty", "Default")
                    current_fp = f"{cfg_fp} (model default)"
                print(f"Current frequency penalty: {current_fp}")
                return True

            arg = parts[1].strip().lower()
            if arg in ["off", "none", "disable"]:
                self.freq_penalty = "off"
                print("Frequency penalty disabled (will not be sent in payloads)")
            elif arg in ["default", "reset"]:
                self.freq_penalty = None
                print("Frequency penalty reset to model default")
            else:
                try:
                    val = float(arg)
                    self.freq_penalty = val
                    print(f"Frequency penalty set to {val}")
                except ValueError:
                    print("Invalid frequency penalty value. Please enter a float, 'off', 'none', or 'default'.")
            return True

        elif cmd == "/pres_penalty":
            if len(parts) < 2:
                if self.pres_penalty in ("off", "none", "disable", False):
                    current_pp = "Disabled (off)"
                elif self.pres_penalty is not None:
                    current_pp = self.pres_penalty
                else:
                    cfg_pp = self.config_manager.get_model_config(
                        self.config_manager.active_model_alias
                    ).get("presence_penalty", "Default")
                    current_pp = f"{cfg_pp} (model default)"
                print(f"Current presence penalty: {current_pp}")
                return True

            arg = parts[1].strip().lower()
            if arg in ["off", "none", "disable"]:
                self.pres_penalty = "off"
                print("Presence penalty disabled (will not be sent in payloads)")
            elif arg in ["default", "reset"]:
                self.pres_penalty = None
                print("Presence penalty reset to model default")
            else:
                try:
                    val = float(arg)
                    self.pres_penalty = val
                    print(f"Presence penalty set to {val}")
                except ValueError:
                    print("Invalid presence penalty value. Please enter a float, 'off', 'none', or 'default'.")
            return True

        elif cmd == "/reasoning":
            if len(parts) > 1 and parts[1].lower() in ["on", "off"]:
                if parts[1].lower() == "on":
                    self.reasoning_mode = True
                else:
                    self.reasoning_mode = False
                print(f"Reasoning mode is now {'ON' if self.reasoning_mode else 'OFF'}")
            else:
                print(
                    f"Reasoning mode is currently {'ON' if self.reasoning_mode else 'OFF'}"
                )
            return True

        elif cmd == "/effort":
            if len(parts) > 1:
                effort = parts[1].lower()
                if effort in ["low", "medium", "high", "none"]:
                    self.reasoning_effort = effort if effort != "none" else None
                    print(f"Reasoning effort set to {effort}")
                else:
                    print("Invalid effort level. Use: low, medium, high, or none")
            else:
                if self.reasoning_effort:
                    print(f"Reasoning effort is currently: {self.reasoning_effort}")
                else:
                    print("Reasoning effort is currently: none (not set)")
            return True

        elif cmd == "/thinking":
            if len(parts) > 1 and parts[1].lower() in ["on", "off"]:
                if parts[1].lower() == "on":
                    self.show_thinking = True
                else:
                    self.show_thinking = False
                print(
                    f"Thinking display is now {'ON' if self.show_thinking else 'OFF'}"
                )
            else:
                print(
                    f"Thinking display is currently {'ON' if self.show_thinking else 'OFF'}"
                )
            return True

        elif cmd == "/thoughtstyle":
            if len(parts) > 1:
                style = parts[1].lower()
                if style in ["none", "gemma4", "nanbeige", "nanbeige_code"]:
                    self.thoughtstyle = style
                    print(f"Thought style set to: {style}")
                else:
                    print("Invalid thought style. Use 'none', 'gemma4', 'nanbeige', or 'nanbeige_code'.")
            else:
                print(f"Current thought style: {self.thoughtstyle}")
            return True

        elif cmd == "/seed":
            if len(parts) < 2:
                print(f"Current seed setting: {self.seed_config}")
                return True

            arg = parts[1].lower()
            if arg in ["clear", "none", "off"]:
                self.seed_config = None
                print("Seed cleared.")
            elif arg == "time":
                self.seed_config = "time"
                print("Seed set to 'time' (uses Unix timestamp per completion).")
            elif arg == "random":
                if len(parts) < 3:
                    print("Usage: /seed random <min>, <max>")
                    return True
                try:
                    # Handle both "random 1,999" and "random 1, 999"
                    range_str = parts[2]
                    if "," not in range_str:
                        print("Usage: /seed random <min>, <max>")
                        return True
                    v1_str, v2_str = range_str.split(",", 1)
                    v1 = int(v1_str.strip())
                    v2 = int(v2_str.strip())
                    self.seed_config = ("random", v1, v2)
                    print(f"Seed set to random range: {v1} to {v2}")
                except ValueError:
                    print("Invalid range. Use: /seed random <min>, <max>")
            else:
                try:
                    seed_val = int(parts[1])
                    self.seed_config = seed_val
                    print(f"Seed set to fixed value: {seed_val}")
                except ValueError:
                    print(
                        "Invalid seed. Use an integer, 'time', or 'random <min>, <max>'."
                    )
            return True

        elif cmd == "/echo":
            if len(parts) < 2:
                print()
                return True
            
            try:
                text = command.split(maxsplit=1)[1]
            except IndexError:
                print()
                return True
            
            processed_text, _ = self.buffer_manager.replace_placeholders(text, include_images=False)
            
            if (processed_text.startswith('"') and processed_text.endswith('"')) or \
               (processed_text.startswith("'") and processed_text.endswith("'")):
                processed_text = processed_text[1:-1]
            
            print(processed_text)
            return True

        elif cmd == "/run":
            if len(parts) < 2:
                print("Usage: /run <command>")
                return True
            
            # Check for /run safe and /run unsafe [askfirst]
            if len(parts) >= 2 and parts[1].lower() in ("safe", "unsafe"):
                sub = parts[1].lower()
                if sub == "safe" and len(parts) == 2:
                    self.safe_mode = True
                    self.safe_mode_askfirst = False
                    print("Safe mode enabled - dangerous patterns will be blocked")
                    return True
                elif sub == "unsafe" and (len(parts) == 2 or (len(parts) == 3 and parts[2].lower().replace("_", "") == "askfirst")):
                    self.safe_mode = False
                    if len(parts) == 3 and parts[2].lower().replace("_", "") == "askfirst":
                        self.safe_mode_askfirst = True
                        print("Safe mode disabled with confirmation - dangerous commands will require confirmation (y/N)")
                    else:
                        self.safe_mode_askfirst = False
                        print("Safe mode disabled - dangerous commands allowed without confirmation")
                    return True

            # Extract the command portion (everything after "/run")
            command_str = command.split(maxsplit=1)[1]
            
            # Strip only the outermost matching quotes, preserving inner quotes
            import shlex
            stripped_command = command_str
            if len(command_str) >= 2:
                first_char = command_str[0]
                last_char = command_str[-1]
                if first_char == last_char and first_char in ('"', "'"):
                    # Check if the quotes are balanced (simple check for outermost pair)
                    # Strip the outermost pair
                    stripped_command = command_str[1:-1]
            
            # Validate quote balance before processing
            try:
                shlex.split(stripped_command)
            except ValueError as e:
                print(f"Error: {e}")
                print("Tip: Mix quotes: /run find . -name \"*.md\"")
                print("     Or: /run \"find . -name '*.md'\"")
                print("     Escape inner quotes: /run \"find . -name \\\"*.md\\\"\"")
                return True
            
            if stripped_command:
                # Perform variable substitution before execution
                # Note: We pass stripped_command, shlex.split in execute_shell_command will handle remaining quotes
                processed_cmd, _ = self.buffer_manager.replace_placeholders(stripped_command, include_images=False)
                self.execute_shell_command(processed_cmd)
            return True

        elif cmd == "/run_safe":
            self.safe_mode = True
            self.safe_mode_askfirst = False
            print("Safe mode enabled - dangerous patterns will be blocked")
            return True

        elif cmd == "/run_unsafe":
            self.safe_mode = False
            if len(parts) >= 2 and parts[1].lower().replace("_", "") == "askfirst":
                self.safe_mode_askfirst = True
                print("Safe mode disabled with confirmation - dangerous commands will require confirmation (y/N)")
            else:
                self.safe_mode_askfirst = False
                print("Safe mode disabled - dangerous commands allowed without confirmation")
            return True

        elif cmd == "/tool":
            # Handle /tool subcommands: on, off, or dispatch
            if len(parts) < 2:
                # No subcommand - dispatch tool invocation from LAST_COMPLETION
                await self.dispatch_tool()
                return True
            
            subcmd = parts[1].lower()
            
            if subcmd == "list":
                import fnmatch
                
                # Parse detail mode and glob pattern
                detail_mode = False
                glob_pattern = "*"
                if len(parts) > 2:
                    sub_parts = parts[2].strip().split()
                    if "detail" in [p.lower() for p in sub_parts]:
                        detail_mode = True
                        remaining_parts = [p for p in sub_parts if p.lower() != "detail"]
                        if remaining_parts:
                            glob_pattern = remaining_parts[0]
                    else:
                        glob_pattern = sub_parts[0]
                
                config = self._load_tools_config()
                tools = config.get('tools', {})
                
                # Filter local tools
                filtered_local = {}
                for t_name, t_meta in tools.items():
                    if fnmatch.fnmatch(t_name.lower(), glob_pattern.lower()):
                        filtered_local[t_name] = t_meta
                
                # Filter MCP tools
                filtered_mcp = {}
                if self.mcp_manager and self.mcp_manager.cached_schemas:
                    for server_name, tools_list in self.mcp_manager.cached_schemas.items():
                        matching_mcp = []
                        for tool in tools_list:
                            mcp_tool_name = f"mcp__{server_name}__{tool.name}"
                            if fnmatch.fnmatch(mcp_tool_name.lower(), glob_pattern.lower()):
                                matching_mcp.append(tool)
                        if matching_mcp:
                            filtered_mcp[server_name] = matching_mcp

                if detail_mode:
                    if glob_pattern != "*":
                        print(f"\nDetailed Tools matching '{glob_pattern}':")
                    else:
                        print("\nDetailed Tools Configuration:")

                    print("\nAvailable Local Tools:")
                    if not filtered_local:
                        print("  No local tools match pattern." if glob_pattern != "*" else "  No local tools defined in configuration.")
                    else:
                        for tool_name, tool_meta in filtered_local.items():
                            config_enabled = tool_meta.get('enabled', False)
                            is_enabled = self.tool_overrides.get(tool_name, config_enabled)
                            status = "[ON]" if is_enabled else "[OFF]"
                            desc = tool_meta.get('description', 'No description')
                            print(f"\n**{tool_name}**  {status}")
                            print(f"Description: {desc}")
                            params = tool_meta.get('parameters', {})
                            if params:
                                print("Parameters:")
                                for param_name, param_rules in params.items():
                                    param_type = param_rules.get('type', 'string')
                                    param_desc = param_rules.get('description', '')
                                    optional = param_rules.get('optional', False)
                                    required = " (optional)" if optional else " (required)"
                                    print(f"  - {param_name}: {param_type}{required} - {param_desc}")
                    
                    # Print MCP Tools if active
                    if filtered_mcp:
                        print("\nModel Context Protocol (MCP) Tools:")
                        for server_name, tools_list in filtered_mcp.items():
                            print(f"  [{server_name}]")
                            for tool in tools_list:
                                mcp_tool_name = f"mcp__{server_name}__{tool.name}"
                                is_enabled = self.tool_overrides.get(mcp_tool_name, True)
                                status = "[ON]" if is_enabled else "[OFF]"
                                desc = getattr(tool, "description", "No description") or "No description"
                                print(f"\n**{mcp_tool_name}**  {status}")
                                print(f"Description: {desc}")
                                
                                # Extract input schema properties
                                input_schema = getattr(tool, "inputSchema", {})
                                if hasattr(input_schema, "get"):
                                    properties = input_schema.get("properties", {})
                                    required_list = input_schema.get("required", [])
                                else:
                                    properties = {}
                                    required_list = []
                                
                                if properties:
                                    print("Parameters:")
                                    for param_name, param_meta in properties.items():
                                        if hasattr(param_meta, "get"):
                                            param_type = param_meta.get("type")
                                            if not param_type and "anyOf" in param_meta:
                                                types = [t.get("type") for t in param_meta["anyOf"] if t.get("type") != "null" and t.get("type")]
                                                param_type = "|".join(types) if types else "string"
                                            elif not param_type:
                                                param_type = "string"
                                            param_desc = param_meta.get("description", "")
                                        else:
                                            param_type = "string"
                                            param_desc = ""
                                            
                                        is_optional = param_name not in required_list
                                        required_str = " (optional)" if is_optional else " (required)"
                                        print(f"  - {param_name}: {param_type}{required_str} - {param_desc}")
                    elif self.mcp_manager and self.mcp_manager.cached_schemas:
                        print("\nModel Context Protocol (MCP) Tools:")
                        print("  No MCP tools match pattern.")
                else:
                    # Columnar layout for single-line view
                    if glob_pattern != "*":
                        print(f"\nAvailable Tools matching '{glob_pattern}':")
                    
                    # Print header
                    print(f"\n  {'STATUS':<6} {'TYPE':<6} {'NAME':<45} {'DESCRIPTION':<60}")
                    print(f"  {'-'*6} {'-'*6} {'-'*45} {'-'*60}")
                    
                    has_local = False
                    for tool_name, tool_meta in filtered_local.items():
                        has_local = True
                        config_enabled = tool_meta.get('enabled', False)
                        is_enabled = self.tool_overrides.get(tool_name, config_enabled)
                        status_str = "[ON]" if is_enabled else "[OFF]"
                        desc = tool_meta.get('description', 'No description').strip().replace("\n", " ")
                        print(f"  {status_str:<6} {'LOCAL':<6} {tool_name:<45} {desc[:60]:<60}")
                    
                    if not has_local and glob_pattern == "*":
                        print("  (No local tools defined)")
                        
                    has_mcp = False
                    if filtered_mcp:
                        for server_name, tools_list in filtered_mcp.items():
                            for tool in tools_list:
                                has_mcp = True
                                mcp_tool_name = f"mcp__{server_name}__{tool.name}"
                                is_enabled = self.tool_overrides.get(mcp_tool_name, True)
                                status_str = "[ON]" if is_enabled else "[OFF]"
                                desc = (getattr(tool, "description", "No description") or "No description").strip().replace("\n", " ")
                                print(f"  {status_str:<6} {'MCP':<6} {mcp_tool_name:<45} {desc[:60]:<60}")
                    
                    if not has_mcp and self.mcp_manager and self.mcp_manager.cached_schemas and glob_pattern == "*":
                        print("  (No MCP tools active)")
                print("")
                return True
            
            elif subcmd in ("enable", "disable"):
                if len(parts) < 3:
                    print(f"Usage: /tool {subcmd} <tool_name>|all|<glob_pattern>")
                    return True
                
                target = parts[2].strip()
                config = self._load_tools_config()
                tools = config.get('tools', {})
                
                target_value = (subcmd == "enable")
                
                # Collect all available tools
                all_tools = []
                for tool_name in tools.keys():
                    all_tools.append(tool_name)
                if self.mcp_manager and self.mcp_manager.cached_schemas:
                    for server_name, tools_list in self.mcp_manager.cached_schemas.items():
                        for tool in tools_list:
                            all_tools.append(f"mcp__{server_name}__{tool.name}")
                
                import fnmatch
                
                if target.lower() == "all":
                    matched_tools = all_tools
                else:
                    pattern = target.lower()
                    matched_tools = [t for t in all_tools if fnmatch.fnmatch(t.lower(), pattern)]
                    
                    # Fallback to exact case-insensitive match if target contains no glob chars and wasn't matched
                    if not matched_tools and "*" not in target and "?" not in target:
                        for t in all_tools:
                            if t.lower() == target.lower():
                                matched_tools = [t]
                                break
                
                if not matched_tools:
                    print(f"Error: No tools matched pattern '{target}'.")
                    return True
                
                for t in matched_tools:
                    self.tool_overrides[t] = target_value
                    print(f"Tool '{t}' {'enabled' if target_value else 'disabled'}.")
                
                # Regenerate tool context to update in-memory state and refresh variable context if active
                context = self.generate_tool_context()
                if self.tool_mode:
                    self.buffer_manager.set_script_var('TOOL_CONTEXT', context)
                print("Prompt context refreshed with updated tools.")
                return True
            
            elif subcmd == "on":
                # Enable tool mode - inject tool definitions into system prompt
                context = self.generate_tool_context()
                if context:
                    self.tool_mode = True
                    # Inject into current prompt context
                    self.buffer_manager.set_script_var('TOOL_CONTEXT', context)
                    print("Tool mode enabled - tool definitions loaded")
                    print(f"   {len(context.split(chr(10)))} lines of tool context available")
                else:
                    print("No tools available to load")
                return True
            
            elif subcmd == "off":
                # Disable tool mode
                self.tool_mode = False
                self.tool_context = ""
                self.buffer_manager.set_script_var('TOOL_CONTEXT', '')
                print("Tool mode disabled")
                return True
            
            elif subcmd == "auto":
                if len(parts) > 2:
                    auto_arg = parts[2].strip().lower()
                    if auto_arg == "on":
                        self.tool_auto = True
                        context = self.generate_tool_context()
                        if context:
                            self.tool_mode = True
                            self.buffer_manager.set_script_var('TOOL_CONTEXT', context)
                            print("Tool auto mode enabled - tool definitions loaded")
                        else:
                            print("Tool auto mode enabled (warning: no tools available to load)")
                    elif auto_arg == "off":
                        self.tool_auto = False
                        print("Tool auto mode disabled")
                    else:
                        print("Invalid option. Usage: /tool auto on|off")
                else:
                    state_str = "enabled" if self.tool_auto else "disabled"
                    print(f"Tool auto mode is currently {state_str}")
                return True
            
            elif subcmd == "loop":
                max_turns = self.max_turns
                # Extract all remaining arguments as lowercase strings by splitting the rest of the string
                loop_args = []
                if len(parts) > 2:
                    loop_args = [p.lower() for p in parts[2].split()]
                has_force = "force" in loop_args
                
                # Filter out 'force' to parse the turn count
                count_args = [a for a in loop_args if a != "force"]
                
                if count_args:
                    arg = count_args[0]
                    if arg == "max":
                        max_turns = 100
                    elif arg.startswith("max="):
                        try:
                            val = int(arg.split("=")[1])
                            if val > 100 and not has_force:
                                print("Warning: Loop counts greater than 100 require the 'force' flag. Capping at 100.")
                                max_turns = 100
                            else:
                                max_turns = val
                        except ValueError:
                            pass
                    else:
                        try:
                            val = int(arg)
                            if val > 100 and not has_force:
                                print("Warning: Loop counts greater than 100 require the 'force' flag. Capping at 100.")
                                max_turns = 100
                            else:
                                max_turns = val
                        except ValueError:
                            pass
                await self.execute_tool_loop(max_turns)
                return True

            elif subcmd == "max_turns":
                if len(parts) > 2:
                    try:
                        self.max_turns = int(parts[2].strip())
                        print(f"Max tool turns set to {self.max_turns}")
                    except ValueError:
                        print("Invalid turn count. Usage: /tool max_turns <int>")
                else:
                    print(f"Current max tool turns: {self.max_turns}")
                return True

            elif subcmd in ("rate_limit", "ratelimit"):
                if len(parts) > 2:
                    raw_val = parts[2].strip()
                    try:
                        val = float(raw_val)
                        if val < 0:
                            print("Error: Rate limit delay cannot be negative. Usage: /tool rate_limit <seconds>")
                        else:
                            self.rate_limit_delay = val
                            self._cached_rate_limit_delay = val
                            display_val = int(val) if val.is_integer() else val
                            print(f"rate_limit is now {display_val} seconds")
                    except ValueError:
                        print("Invalid rate limit value. Usage: /tool rate_limit <seconds>")
                else:
                    display_val = int(self.rate_limit_delay) if isinstance(self.rate_limit_delay, (int, float)) and float(self.rate_limit_delay).is_integer() else self.rate_limit_delay
                    print(f"rate_limit is currently {display_val} seconds")
                return True
            
            elif subcmd == "prompt":
                # Check if there is an argument in parts[2]
                sub_arg = ""
                if len(parts) > 2:
                    sub_arg = parts[2].strip().lower()
                
                if sub_arg in ("edit_live", "live_edit"):
                    # Open the editor to edit agentic_instructions live (stored in self.live_agentic_instructions)
                    import tempfile
                    import subprocess
                    
                    context = self.tool_context or self.generate_tool_context()
                    current_instr = self.live_agentic_instructions or self.agentic_instructions or self.default_agentic_instructions
                    
                    # Create temporary file formatted like /tool prompt
                    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False, mode="w", encoding="utf-8") as tf:
                        tf.write("=== TOOL CONTEXT INJECTED INTO PROMPT ===\n")
                        tf.write(context)
                        tf.write("\n\n=== AGENTIC LOOP SYSTEM INSTRUCTIONS ===\n")
                        tf.write("# Edit the instructions below this line. Changes are only active for this session.\n")
                        tf.write("# To clear the live override and revert to tools_config.toml, delete all instructions below this header.\n")
                        tf.write(current_instr)
                        temp_path = tf.name
                    
                    try:
                        # Determine editor
                        config = self._load_tools_config()
                        config_editor = config.get("config", {}).get("editor")
                        default_editor = "notepad.exe" if os.name == "nt" else "nano"
                        editor = config_editor or os.environ.get("EDITOR") or default_editor
                        
                        # Open the editor
                        print(f"Opening live prompt editor using '{editor}'...")
                        subprocess.run([editor, temp_path], check=True)
                        
                        # Read and parse the modified content back
                        with open(temp_path, "r", encoding="utf-8") as f:
                            saved_content = f.read()
                        
                        # Extract the instructions below the header boundary
                        marker = "=== AGENTIC LOOP SYSTEM INSTRUCTIONS ==="
                        if marker in saved_content:
                            parts_split = saved_content.split(marker, 1)
                            instr_block = parts_split[1]
                            
                            # Filter out helper comment lines starting with '#'
                            lines = instr_block.splitlines()
                            filtered_lines = []
                            for line in lines:
                                if line.strip().startswith("#"):
                                    continue
                                filtered_lines.append(line)
                            new_instr = "\n".join(filtered_lines).strip()
                        else:
                            # Fallback if marker was accidentally deleted
                            new_instr = saved_content.strip()
                        
                        if not new_instr:
                            self.live_agentic_instructions = ""
                            print("Live prompt override cleared. Reset to tools_config.toml settings.")
                        else:
                            self.live_agentic_instructions = new_instr
                            print("Active system prompt updated successfully for this session.")
                    except Exception as e:
                        print(f"Error editing live prompt: {e}")
                    finally:
                        try:
                            os.unlink(temp_path)
                        except Exception:
                            pass
                    return True
                
                # Show the prompt injected during tool operation
                context = self.tool_context or self.generate_tool_context()
                if context:
                    print("\n=== TOOL CONTEXT INJECTED INTO PROMPT ===")
                    print(context)
                    print("\n=== AGENTIC LOOP SYSTEM INSTRUCTIONS ===")
                    active_instr = self.live_agentic_instructions or self.agentic_instructions or self.default_agentic_instructions
                    if self.live_agentic_instructions:
                        print(f" [Live Edit Override Active]\n{active_instr}")
                    else:
                        print(active_instr)
                    print("=========================================\n")
                else:
                    print("No tools available or tool context could not be generated.")
                return True
            
            elif subcmd in ("translate", "convert", "parse"):
                # Translate any raw tool call format (XML, Gemma 4, JSON) into canonical JSON
                raw_text = command.split(maxsplit=2)[2].strip() if len(parts) > 2 else (self.buffer_manager.get_script_var('LAST_COMPLETION') or "")
                if not raw_text:
                    print("No text or LAST_COMPLETION available to translate.")
                    return True
                
                calls = self.extract_tool_calls(raw_text)
                if not calls:
                    print("No valid tool calls extracted from input text.")
                    return True
                
                if len(calls) == 1:
                    json_output = f"```json\n{json.dumps(calls[0], indent=2)}\n```"
                else:
                    json_output = f"```json\n{json.dumps(calls, indent=2)}\n```"
                
                print(json_output)
                self.buffer_manager.set_script_var('LAST_TOOL_TRANSLATED', json.dumps(calls), allow_protected=True)
                return True
            
            else:
                # Check if argument is a filename (ends with .json)
                arg = command.split(maxsplit=1)[1]
                if arg.endswith('.json') and os.path.exists(arg):
                    # Read JSON from file
                    try:
                        with open(arg, 'r') as f:
                            json_str = f.read()
                        await self.dispatch_tool(json_str)
                    except Exception as e:
                        print(f"Error reading file {arg}: {e}")
                else:
                    # Provide JSON directly - dispatch it
                    await self.dispatch_tool(arg)
                return True

        elif cmd == "/profile":
            import shlex
            try:
                cmd_parts = shlex.split(command)
            except ValueError:
                cmd_parts = command.split()
            await self.handle_profile_command(cmd_parts[1:])
            return True

        elif cmd == "/stream":
            self.streaming_enabled = not self.streaming_enabled
            print(
                f"Streaming responses {'enabled' if self.streaming_enabled else 'disabled'}"
            )
            return True

        elif cmd == "/listmodels":
            self.config_manager.list_models()
            return True

        elif cmd == "/env":
            filter_term = parts[1].lower() if len(parts) > 1 else None
            from .vendors import get_env_status
            
            models_dict = {}
            if self.config_manager and hasattr(self.config_manager, "config") and isinstance(self.config_manager.config, dict) and "models" in self.config_manager.config:
                models_dict = self.config_manager.config["models"]
                
            env_data = get_env_status(models_dict)
            
            if filter_term:
                if filter_term == "set":
                    env_data = [e for e in env_data if e["is_set"]]
                elif filter_term in ("unset", "missing"):
                    env_data = [e for e in env_data if not e["is_set"]]
                else:
                    env_data = [
                        e for e in env_data
                        if filter_term in e["name"].lower() or filter_term in e["source"].lower()
                    ]
            
            print("=" * 88)
            print(" ENVIRONMENT VARIABLES & API KEYS (set | grep -i api)")
            print("=" * 88)
            print(f" {'Status':<9} | {'Variable Name':<24} | {'Masked Value':<18} | {'Len':<4} | {'Source':<20}")
            print("-" * 10 + "+" + "-" * 26 + "+" + "-" * 20 + "+" + "-" * 6 + "+" + "-" * 22)
            
            if not env_data:
                print(" No matching environment variables found.")
            else:
                for item in env_data:
                    status = "[SET]" if item["is_set"] else "[NOT SET]"
                    name = item["name"]
                    masked = item["masked"]
                    len_str = str(item["length"]) if item["is_set"] else "-"
                    source = item["source"]
                    print(f" {status:<9} | {name:<24} | {masked:<18} | {len_str:>4} | {source:<20}")
                    
            print("=" * 88)
            num_set = sum(1 for e in env_data if e["is_set"])
            num_total = len(env_data)
            print(f" Total: {num_total} variables ({num_set} set, {num_total - num_set} not set)")
            print("=" * 88)
            return True

        elif cmd == "/source":
            if len(parts) < 2:
                print("Usage: /source <file>")
                return True
            file_path = command.split(maxsplit=1)[1].strip(" \"'")
            expanded_path = os.path.expanduser(file_path)
            if not os.path.exists(expanded_path):
                print(f"Error: Script file not found: {expanded_path}")
                return True
            await self.execute_script(expanded_path)
            return True

        elif cmd == "/script":
            if len(parts) < 2:
                print('Usage: /script <file> [key="value"]...')
                return True

            # Extract script path and parameters
            script_path = parts[1]
            
            # Parse parameters from the command
            import re
            param_pattern = r'(^|\s+)([a-zA-Z_]\w*)\s*=\s*("[^"]*"|\'[^\']*\'|\S+)'
            
            # Look for parameters in the original command string after the script path
            # We need to handle the case where script_path might be quoted
            remaining_command = command[len(cmd):].strip()  # Remove the "/script" part
            
            # Find the script path in the remaining command
            # Handle both quoted and unquoted script paths
            script_path_match = re.match(r'("[^"]*"|\'[^\']*\'|\S+)', remaining_command)
            if script_path_match:
                actual_script_path = script_path_match.group(1).strip('"\'')
                params_string = remaining_command[len(script_path_match.group(1)):].strip()
            else:
                actual_script_path = script_path
                params_string = ""
            
            # Extract parameters using regex
            params = {}
            for match in re.finditer(param_pattern, params_string):
                var_name = match.group(2)  # Group 2 is the variable name (group 1 is the separator)
                var_value = match.group(3).strip('"\'')  # Remove surrounding quotes
                params[var_name] = var_value
                print(f"Setting parameter {var_name} = {var_value}")
            
            # Set parameters as script variables
            old_user_write = getattr(self.buffer_manager.script_vars, '_is_user_write', False)
            if hasattr(self.buffer_manager.script_vars, '_is_user_write'):
                self.buffer_manager.script_vars._is_user_write = True
            try:
                for var_name, var_value in params.items():
                    self.buffer_manager.set_script_var(var_name, var_value)
            finally:
                if hasattr(self.buffer_manager.script_vars, '_is_user_write'):
                    self.buffer_manager.script_vars._is_user_write = old_user_write
            
            print("command /script with ", actual_script_path)
            # Execute script asynchronously so it doesn't block the main loop
            await self.execute_script(actual_script_path)
            return True

        elif cmd == "/proc":
            if len(parts) < 2:
                print('Usage: /proc <name> [key="value"]...')
                return True
            
            remaining_command = command[len(cmd):].strip()
            name_match = re.match(r'("[^"]*"|\'[^\']*\'|\S+)', remaining_command)
            if name_match:
                proc_name = name_match.group(1).strip('"\'')
                params_string = remaining_command[len(name_match.group(1)):].strip()
            else:
                proc_name = parts[1]
                params_string = ""
            
            param_pattern = r'(^|\s+)([a-zA-Z_]\w*)\s*=\s*("[^"]*"|\'[^\']*\'|\S+)'
            call_args = {}
            for match in re.finditer(param_pattern, params_string):
                var_name = match.group(2)
                var_value = match.group(3).strip('"\'')
                call_args[var_name] = var_value

            max_depth = int(self.buffer_manager.script_vars.get("PROC_MAX_DEPTH", 20))
            if self.proc_depth >= max_depth:
                print(f"Error: Maximum procedure recursion depth of {max_depth} reached.", flush=True)
                return True

            body_lines = None
            if proc_name in self.procedures:
                body_lines = self.procedures[proc_name]["body"]
            else:
                search_paths = [
                    proc_name,
                    f"{proc_name}.chatdsl",
                    os.path.join("procs", f"{proc_name}.chatdsl"),
                    os.path.expanduser(os.path.join("~/.chatybot/procs", f"{proc_name}.chatdsl"))
                ]
                found_path = None
                for path in search_paths:
                    if os.path.exists(path):
                        found_path = path
                        break
                if found_path:
                    try:
                        with open(found_path, "r", encoding="utf-8") as f:
                            content = f.read()
                        body_lines = content.split("\n")
                    except Exception as e:
                        print(f"Error reading procedure file '{found_path}': {e}")
                        return True
                else:
                    print(f"Error: Procedure '{proc_name}' not found in memory or disk.")
                    return True

            frame = {"saved_vars": {}, "local_vars": set()}
            self.active_proc_stack.append(frame)
            
            old_user_write = getattr(self.buffer_manager.script_vars, '_is_user_write', False)
            if hasattr(self.buffer_manager.script_vars, '_is_user_write'):
                self.buffer_manager.script_vars._is_user_write = True
            
            try:
                for k, v in call_args.items():
                    if k not in frame["saved_vars"]:
                        exists = k in self.buffer_manager.script_vars
                        orig_val = self.buffer_manager.script_vars.get(k) if exists else None
                        frame["saved_vars"][k] = (exists, orig_val)
                    processed_v = self.buffer_manager.replace_placeholders_legacy(v)
                    self.buffer_manager.set_script_var(k, processed_v)
            finally:
                if hasattr(self.buffer_manager.script_vars, '_is_user_write'):
                    self.buffer_manager.script_vars._is_user_write = old_user_write

            self.proc_depth += 1
            old_script_context = self.script_context
            self.script_context = True
            try:
                await self.execute_command_list(body_lines)
            except Exception as e:
                print(f"Error executing procedure '{proc_name}': {e}")
            finally:
                self.script_context = old_script_context
                self.proc_depth -= 1
                popped_frame = self.active_proc_stack.pop()
                old_user_write = getattr(self.buffer_manager.script_vars, '_is_user_write', False)
                if hasattr(self.buffer_manager.script_vars, '_is_user_write'):
                    self.buffer_manager.script_vars._is_user_write = True
                try:
                    for var_name, (exists, orig_val) in popped_frame["saved_vars"].items():
                        if exists:
                            self.buffer_manager.set_script_var(var_name, orig_val)
                        else:
                            if var_name in self.buffer_manager.script_vars:
                                del self.buffer_manager.script_vars[var_name]
                finally:
                    if hasattr(self.buffer_manager.script_vars, '_is_user_write'):
                        self.buffer_manager.script_vars._is_user_write = old_user_write

            return True

        elif cmd in ["/quit", "/exit"]:
            print(self.i18n.get_ui_string("goodbye_message", "Goodbye! Thanks for chatting."))
            self.logging_manager.stop_logging()
            self.save_input_history()
            exit(0)

        # Database commands
        elif cmd == "/setdb":
            if len(parts) < 2:
                print("Usage: /setdb <dbname>")
                return True
            dbname = parts[1].strip('"')
            set_db(dbname)
            return True
        elif cmd == "/dblist":
            list_dbs()
            return True
        elif cmd == "/searchdb":
            if len(parts) < 2:
                print("Usage: /searchdb <query>")
                return True
            # parts was split with maxsplit=2, so a multi-word query lands in
            # parts[2]. Rejoin so "/searchdb python web framework" searches for
            # the full phrase rather than just "python".
            query = parts[1] if len(parts) < 3 else f"{parts[1]} {parts[2]}"
            search_db(query.strip('"'))
            return True
        elif cmd == "/dblog":
            # /dblog logs the final answer only (legacy behavior).
            # /dblog thinking (or withthink) also persists the extracted
            # reasoning text and reasoning token count into the item's metadata.
            # Matches the bare-word convention used by /save (nothink/withthink)
            # and /logging (hex) rather than a --prefix flag.
            include_thinking = False
            if len(parts) > 1:
                flags = parts[1].lower() if len(parts) < 3 else f"{parts[1]} {parts[2]}".lower()
                include_thinking = any(w in flags for w in ("thinking", "withthink", "with-think"))
            dblog(include_thinking=include_thinking)
            return True
        elif cmd == "/dbprint":
            if len(parts) > 1:
                filename = parts[1].strip('"')
                dbprint(filename)
            else:
                dbprint()
            return True

        elif cmd == "/documents":
            doc_pattern = r'^/documents\s+(\w+)\s*=\s*(.+)$'
            match = re.match(doc_pattern, command)
            if not match:
                print("Usage: /documents db=<name> | var=<name> | var=file | filebank=<1-5> | dir=\"<path>\"")
                return True
            
            source_type = match.group(1).lower()
            identifier = match.group(2).strip(' "\'')
            
            if source_type == "db":
                db_file = os.path.expanduser(f"~/.local/share/chatybot/db/{identifier}.json")
                if not os.path.exists(db_file):
                    print(f"Warning: Database '{identifier}' does not exist or has no entries in {db_file}.")
                self.rerank_documents_source = {"type": "db", "identifier": identifier}
                print(f"Document source set to database '{identifier}'.")
            elif source_type == "var":
                if identifier == "CHAT_HISTORY":
                    self.rerank_documents_source = {"type": "var", "identifier": "CHAT_HISTORY"}
                    print("Document source set to live chat history.")
                elif identifier == "file":
                    if not self.buffer_manager.file_buffer:
                        print("Warning: No file loaded. Use /file <path> first.")
                    self.rerank_documents_source = {"type": "var", "identifier": "file"}
                    print("Document source set to file buffer.")
                else:
                    if identifier not in self.buffer_manager.script_vars:
                        print(f"Warning: Variable '${{{identifier}}}' is not currently defined. It must be set before executing /rerank.")
                    self.rerank_documents_source = {"type": "var", "identifier": identifier}
                    print(f"Document source set to variable '${{{identifier}}}'.")
            elif source_type == "filebank":
                bank_name = f"filebank{identifier}"
                if bank_name not in self.buffer_manager.file_banks:
                    print(f"Error: Invalid filebank number '{identifier}'. Use 1-5.")
                    return True
                if not self.buffer_manager.file_banks[bank_name]:
                    print(f"Warning: Filebank{identifier} is empty. Load a file first with /filebank{identifier} <path>.")
                self.rerank_documents_source = {"type": "filebank", "identifier": identifier}
                print(f"Document source set to {bank_name}.")
            elif source_type == "dir":
                if not os.path.exists(identifier) or not os.path.isdir(identifier):
                    print(f"Error: Directory '{identifier}' does not exist.")
                    return True
                self.rerank_documents_source = {"type": "dir", "identifier": identifier}
                print(f"Document source set to directory '{identifier}'.")
            else:
                print("Invalid source type. Use 'db', 'var', 'filebank', or 'dir'.")
            return True

        elif cmd == "/rerank":
            # Dynamically load env keys in case of persistent process startup without them
            for path in [".env", "../.env", "../../.env"]:
                if os.path.exists(path):
                    try:
                        with open(path, "r") as f:
                            for line in f:
                                line = line.strip()
                                if line and not line.startswith("#") and "=" in line:
                                    k, v = line.split("=", 1)
                                    k = k.strip()
                                    v = v.strip().strip('"\'')
                                    os.environ[k] = v
                        break
                    except Exception:
                        pass
            
            # Dynamic fallback to jina_api_key.txt
            for key_file in ["jina_api_key.txt", "jina_ai_key.txt", "../jina_api_key.txt", "../jina_ai_key.txt"]:
                if os.path.exists(key_file):
                    try:
                        with open(key_file, "r") as f:
                            content = f.read().strip()
                            if "JINA_API_KEY=" in content:
                                key = content.split("JINA_API_KEY=")[-1].strip().strip('"\'')
                                os.environ["JINA_API_KEY"] = key
                            elif "export " in content and "=" in content:
                                key = content.split("=")[-1].strip().strip('"\'')
                                os.environ["JINA_API_KEY"] = key
                            else:
                                os.environ["JINA_API_KEY"] = content.strip('"\'')
                        break
                    except Exception:
                        pass

            query_match = re.search(r'^/rerank\s+["\']([^"\']+)["\']', command, re.IGNORECASE)
            if not query_match:
                print('Usage: /rerank "<query>" [, top_n=<number>] [, items=<number>] [, split=<sentence|line|paragraph>] [, return=<summ|text>] [, full_doc=<true|false>]')
                return True
            
            query = query_match.group(1)
            remainder = command[query_match.end():]
            
            top_n_match = re.search(r'\btop_n\s*=\s*(\d+)', remainder, re.IGNORECASE)
            item_match = re.search(r'\bitem(s)?\s*=\s*(\d+)', remainder, re.IGNORECASE)
            split_match = re.search(r'\bsplit\s*=\s*([a-zA-Z]+)', remainder, re.IGNORECASE)
            return_match = re.search(r'\breturn\s*=\s*([a-zA-Z]+)', remainder, re.IGNORECASE)
            full_doc_match = re.search(r'\bfull_doc\s*=\s*([a-zA-Z]+)', remainder, re.IGNORECASE)
            
            top_n = int(top_n_match.group(1)) if top_n_match else 2
            item = int(item_match.group(2)) if item_match else 1
            split_mode = split_match.group(1).lower() if split_match else "sentence"
            return_type = return_match.group(1).lower() if return_match else "summ"
            full_doc = (full_doc_match.group(1).lower() == "true") if full_doc_match else False
            
            if not self.rerank_documents_source:
                print("Error: No document source specified. Set one using /documents <source> first.")
                return True
                
            rerank_model_config = None
            active_alias = self.config_manager.active_model_alias
            if active_alias:
                try:
                    active_model_config = self.config_manager.get_model_config(active_alias)
                    if active_model_config.get("type") == "reranker":
                        rerank_model_config = active_model_config
                except Exception:
                    pass
                    
            if not rerank_model_config:
                for alias, config in self.config_manager.config.get("models", {}).items():
                    if config.get("type") == "reranker":
                        rerank_model_config = config
                        break
                        
            if not rerank_model_config:
                jina_key = os.environ.get("JINA_API_KEY")
                if jina_key:
                    rerank_model_config = {
                        "name": "jina-reranker-v3",
                        "type": "reranker",
                        "base_url": "https://api.jina.ai/v1/rerank",
                        "api_key": "JINA_API_KEY"
                    }
                else:
                    print("Error: No reranker model is configured, and JINA_API_KEY environment variable is not set.")
                    return True
                    
            base_url = rerank_model_config.get("base_url", "")
            model_name = rerank_model_config.get("name", "jina-reranker-v3")
            api_key_env = rerank_model_config.get("api_key", "")
            api_key = os.environ.get(api_key_env) if api_key_env else os.environ.get("JINA_API_KEY")
            
            chunking_mode_map = {"sentence": "sentences", "line": "lines", "paragraph": "paragraphs"}
            chunking_mode = chunking_mode_map.get(split_mode, "sentences")

            if "localhost" in base_url or "127.0.0.1" in base_url:
                backend = "local"
                from urllib.parse import urlparse
                parsed = urlparse(base_url)
                host = parsed.hostname or "localhost"
                port = parsed.port or 8080
            elif base_url:
                backend = "remote"
                host = "localhost"
                port = 8080
            else:
                backend = "auto"
                host = "localhost"
                port = 8080
                
            source_type = self.rerank_documents_source["type"]
            source_id = self.rerank_documents_source["identifier"]

            from EasyRerank import EasyRanker, TextParser
            
            chunked_docs = []
            chunk_mappings = []
            pre_filtered_chunks = []
            
            if source_type == "db":
                from tinydb import TinyDB
                db_path = os.path.expanduser(f"~/.local/share/chatybot/db/{source_id}.json")
                if not os.path.exists(db_path):
                    print(f"Error: Database file not found at {db_path}.")
                    return True
                    
                try:
                    db = TinyDB(db_path)
                    if 'items' in db.tables():
                        all_items = db.table('items').all()
                    else:
                        all_items = db.all()
                    for item_doc in all_items:
                        content = item_doc.get("content") or ""
                        doc_id = item_doc.doc_id
                        name = item_doc.get("name", "N/A")
                        
                        parser = TextParser(content)
                        if split_mode == "paragraph":
                            chunks = list(parser.paragraphs())
                            join_str = "\n\n"
                        elif split_mode == "line":
                            chunks = list(parser.lines())
                            join_str = "\n"
                        else:
                            sentences = [s.strip() for line in content.split('\n') for s in re.split(r'(?<=[.!?])\s+', line) if s.strip()]
                            chunks = sentences
                            join_str = " "
                        
                        for i in range(0, len(chunks), item):
                            chunk_text = join_str.join(chunks[i:i+item])
                            if chunk_text:
                                chunked_docs.append(chunk_text)
                                chunk_mappings.append({
                                    "parent_id": doc_id,
                                    "parent_name": name,
                                    "full_text": content
                                })
                except Exception as e:
                    print(f"Error reading database {source_id}: {str(e)}")
                    return True
                    
            elif source_type == "var":
                raw_docs = []
                if source_id == "CHAT_HISTORY":
                    for turn_idx, (p, r) in enumerate(self.chat_history):
                        for text, role in [(p, "user"), (r, "assistant")]:
                            if not text:
                                continue
                            parser = TextParser(text)
                            if split_mode == "paragraph":
                                chunks = list(parser.paragraphs())
                                join_str = "\n\n"
                            elif split_mode == "line":
                                chunks = list(parser.lines())
                                join_str = "\n"
                            else:
                                sentences = [s.strip() for line in text.split('\n') for s in re.split(r'(?<=[.!?])\s+', line) if s.strip()]
                                chunks = sentences
                                join_str = " "
                                
                            for i in range(0, len(chunks), item):
                                chunk_text = join_str.join(chunks[i:i+item])
                                if chunk_text:
                                    chunked_docs.append(chunk_text)
                                    chunk_mappings.append({
                                        "role": role,
                                        "turn": turn_idx,
                                        "full_text": text
                                    })
                elif source_id == "file":
                    # Use the file buffer directly
                    var_val = self.buffer_manager.file_buffer
                    raw_docs = [var_val] if var_val else []
                else:
                    var_val = self.buffer_manager.script_vars.get(source_id, "")
                    try:
                        parsed = json.loads(var_val)
                        if isinstance(parsed, list):
                            for item_val in parsed:
                                if isinstance(item_val, dict):
                                    content = item_val.get("content") or item_val.get("text") or item_val.get("value")
                                    if content:
                                        raw_docs.append(str(content))
                                else:
                                    raw_docs.append(str(item_val))
                        elif isinstance(parsed, dict):
                            content = parsed.get("content") or parsed.get("text") or parsed.get("value")
                            raw_docs = [str(content)] if content else [str(parsed)]
                        else:
                            raw_docs = [str(parsed)]
                    except Exception:
                        raw_docs = [var_val]
                        
                    for doc_idx, doc in enumerate(raw_docs):
                        parser = TextParser(doc)
                        if split_mode == "paragraph":
                            chunks = list(parser.paragraphs())
                            join_str = "\n\n"
                        elif split_mode == "line":
                            chunks = list(parser.lines())
                            join_str = "\n"
                        else:
                            sentences = [s.strip() for line in doc.split('\n') for s in re.split(r'(?<=[.!?])\s+', line) if s.strip()]
                            chunks = sentences
                            join_str = " "
                            
                        for i in range(0, len(chunks), item):
                            chunk_text = join_str.join(chunks[i:i+item])
                            if chunk_text:
                                chunked_docs.append(chunk_text)
                                chunk_mappings.append({
                                    "doc_idx": doc_idx,
                                    "full_text": doc
                                })
                                
            elif source_type == "filebank":
                bank_name = f"filebank{source_id}"
                if bank_name in self.buffer_manager.file_banks:
                    content = self.buffer_manager.file_banks[bank_name]
                    if content:
                        parser = TextParser(content)
                        if split_mode == "paragraph":
                            chunks = list(parser.paragraphs())
                            join_str = "\n\n"
                        elif split_mode == "line":
                            chunks = list(parser.lines())
                            join_str = "\n"
                        else:
                            sentences = [s.strip() for line in content.split('\n') for s in re.split(r'(?<=[.!?])\s+', line) if s.strip()]
                            chunks = sentences
                            join_str = " "
                        
                        for i in range(0, len(chunks), item):
                            chunk_text = join_str.join(chunks[i:i+item])
                            if chunk_text:
                                chunked_docs.append(chunk_text)
                                chunk_mappings.append({
                                    "bank": bank_name,
                                    "full_text": content
                                })
                else:
                    print(f"Error: Filebank{source_id} not found.")
                    return True
            elif source_type == "dir":
                from EasyRerank import DirectoryTextProcessor
                processor = DirectoryTextProcessor(source_id)
                
                # Check for parameter overrides
                limit_batch_size_match = re.search(r'\blimit_batch_size\s*=\s*(\d+)', remainder, re.IGNORECASE)
                limit_top_n_match = re.search(r'\blimit_top_n\s*=\s*(\d+)', remainder, re.IGNORECASE)
                max_limit_match = re.search(r'\bmax_limit\s*=\s*(\d+)', remainder, re.IGNORECASE)
                
                limit_batch_size = int(limit_batch_size_match.group(1)) if limit_batch_size_match else 64
                limit_top_n = int(limit_top_n_match.group(1)) if limit_top_n_match else 3
                max_limit = int(max_limit_match.group(1)) if max_limit_match else 64
                
                print(f"Ingesting directory '{source_id}' with Batched Top-N pre-filtering (limit_batch_size={limit_batch_size}, limit_top_n={limit_top_n}, max_limit={max_limit})...")
                
                pre_filtered_chunks, reached_limit = processor.process_with_batched_top_n(
                    chunk_size=item,
                    top_n=limit_top_n,
                    max_limit=max_limit,
                    batch_size=limit_batch_size,
                    chunking_mode=chunking_mode
                )
                chunked_docs = [c['chunk'] for c in pre_filtered_chunks]
                
            print(f"Reranking documents from {source_type}='{source_id}' using {model_name}...")
            try:
                ranker = EasyRanker(
                    documents=chunked_docs,
                    backend=backend,
                    api_key=api_key,
                    host=host,
                    port=port,
                    model=model_name,
                    chunk_size=item,
                    chunking_mode=chunking_mode
                )
                if backend == "remote" and base_url and hasattr(ranker, "backend_instance") and hasattr(ranker.backend_instance, "base_url"):
                    ranker.backend_instance.base_url = base_url
                
                if self.trace_raw_payload:
                    masked_key = f"{api_key[:10]}...{api_key[-5:]}" if api_key and len(api_key) > 15 else "None"
                    payload = {
                        "model": model_name,
                        "query": query,
                        "top_n": top_n,
                        "documents": chunked_docs
                    }
                    payload_str = json.dumps(payload, indent=2)
                    payload_bytes = payload_str.encode('utf-8')
                    size_bytes = len(payload_bytes)
                    size_kb = size_bytes / 1024
                    est_tokens = max(1, int(size_bytes / 4))
                    size_info = f"Size: {size_bytes} bytes ({size_kb:.2f} KB) | Est. Tokens: ~{est_tokens} (industry avg)"

                    print("Payload:")
                    print("-----------------------------")
                    print(f"POST {base_url}")
                    print(f"Headers: {{'Authorization': 'Bearer {masked_key}', 'Content-Type': 'application/json'}}")
                    print(payload_str)
                    print("---- end of payload ---")
                    print(size_info)

                    log_content = (
                        f"Rerank Payload:\n---------------------\n"
                        f"POST {base_url}\n"
                        f"Headers: {{'Authorization': 'Bearer {masked_key}', 'Content-Type': 'application/json'}}\n"
                        f"{payload_str}\n---- end of payload ---\n{size_info}"
                    )
                    self.logging_manager.log_message(log_content)


                results = ranker.rerank(query=query, top_n=top_n, verbose=False)
                self.latest_rerank_results = results
                
                if self.debug_response_mode:
                    print("\n--- DEBUG RESPONSE (JSON) ---")
                    print(json.dumps(results, indent=2))
                    print("--- END DEBUG RESPONSE ---\n")
                    self.debug_response_mode = False
                elif self.debug_response_raw:
                    print("\n--- DEBUG RESPONSE (RAW) ---")
                    print(results)
                    print("--- END DEBUG RESPONSE ---\n")
                    self.debug_response_raw = False
                
                # Pre-resolve matching texts and references
                resolved_matches = []
                for idx, res in enumerate(results, 1):
                    score = res.get('relevance_score', 0.0)
                    
                    if source_type == "dir":
                        matched_idx = res.get('index', 0)
                        if matched_idx < len(pre_filtered_chunks):
                            source_chunk = pre_filtered_chunks[matched_idx]
                            chunk_text = source_chunk.get('chunk', '')
                            filename = source_chunk.get('filename', 'Unknown')
                            chunk_id = source_chunk.get('chunk_id', 0)
                        else:
                            chunk_text = res.get('chunk', '')
                            filename = res.get('filename', 'Unknown')
                            chunk_id = res.get('chunk_id', 0)
                        ref_line = f"File: {filename} (Chunk: {chunk_id})"
                        ref_short = f"File: {filename}"
                        
                        if full_doc:
                            file_path = os.path.join(source_id, filename)
                            if os.path.exists(file_path):
                                try:
                                    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                                        text_to_return = f.read()
                                except Exception:
                                    text_to_return = chunk_text
                            else:
                                text_to_return = chunk_text
                        else:
                            text_to_return = chunk_text
                    else:
                        chunk_text = chunked_docs[res.get('index', 0)]
                        mapping = chunk_mappings[res.get('index', 0)]
                        text_to_return = mapping.get("full_text", chunk_text) if full_doc else chunk_text
                        
                        if source_type == "db":
                            ref_line = f"DB Record: ID {mapping['parent_id']} (Name: '{mapping['parent_name']}')"
                            ref_short = f"Database Record ID {mapping['parent_id']} (Name: {mapping['parent_name']})"
                        elif source_type == "var" and source_id == "CHAT_HISTORY":
                            ref_line = f"Chat History: Turn {mapping['turn'] + 1} ({mapping['role'].capitalize()})"
                            ref_short = f"Chat Turn {mapping['turn'] + 1} ({mapping['role'].capitalize()})"
                        else:
                            ref_line = f"Variable Index: {res.get('index', 0)}"
                            ref_short = f"Variable Index {mapping.get('doc_idx', res.get('index', 0))}"
                            
                    resolved_matches.append({
                        "score": score,
                        "chunk_text": chunk_text,
                        "text_to_return": text_to_return,
                        "ref_line": ref_line,
                        "ref_short": ref_short
                    })
                
                # Construct ASCII results table (summary table)
                ascii_lines = []
                ascii_lines.append("=" * 90)
                ascii_lines.append(f" EASYRERANK RESULTS FOR QUERY: \"{query}\"")
                ascii_lines.append(f" Backend: {backend.upper()} | Model: {model_name} | Source: {source_type}={source_id}")
                ascii_lines.append("=" * 90)
                ascii_lines.append(" Rank |  Score | Source Reference & Snippet")
                ascii_lines.append("------+--------+----------------------------------------------------------------------------")
                
                if not resolved_matches:
                    ascii_lines.append("      |        | No matching results found.")
                else:
                    for idx, match in enumerate(resolved_matches, 1):
                        score = match["score"]
                        ref_line = match["ref_line"]
                        chunk_text = match["chunk_text"]
                        
                        snippet = chunk_text.replace('\n', ' ').strip()
                        if len(snippet) > 70:
                            snippet = snippet[:67] + "..."
                            
                        ascii_lines.append(f"  {idx:2d}  | {score:.4f} | {ref_line}")
                        ascii_lines.append(f"      |        | \"{snippet}\"")
                        if idx < len(resolved_matches):
                            ascii_lines.append("------+--------+----------------------------------------------------------------------------")
                ascii_lines.append("=" * 90)
                ascii_lines.append(f"Total results: {len(resolved_matches)}")
                ascii_lines.append("=" * 90)
                
                ascii_table = "\n".join(ascii_lines)
                
                # Construct raw text response (concatenated plain text)
                raw_texts = [match["text_to_return"] for match in resolved_matches]
                concatenated_text = "\n\n".join(raw_texts)
                
                # 1. Output printing
                if return_type == "text":
                    if self.trace_rerank:
                        print(ascii_table)
                        print("\n[Raw Text Output]")
                        print("-" * 30)
                    print(concatenated_text)
                else:
                    print(ascii_table)
                    
                # 2. Append to chat history
                if return_type == "text":
                    self.chat_history.append((f"[Rerank Query] {query}", concatenated_text))
                else:
                    self.chat_history.append((f"[Rerank Query] {query}", ascii_table))
                    
                # 3. Populate latest_rerank prompt variables
                rerank_blocks = []
                for idx, match in enumerate(resolved_matches, 1):
                    rerank_blocks.append(f"[Rerank Match #{idx} | {match['ref_short']} | Relevance: {match['score']:.4f}]\n{match['text_to_return']}")
                self.buffer_manager.script_vars["latest_rerank"] = "\n\n".join(rerank_blocks)
                
            except Exception as e:
                import traceback
                print(f"Error executing reranking pipeline: {str(e)}")
                traceback.print_exc()
            return True

        elif cmd == "/loadvar":
            if len(parts) < 2:
                print("Usage: /loadvar <varname> [ALL | id | range]")
                return True
            varname = parts[1].strip('"')
            extra = parts[2] if len(parts) > 2 else None
            load_var(varname, extra)
            return True
        elif cmd == "/savevar":
            if len(parts) < 3:
                print("Usage: /savevar <varname> <filename>")
                return True
            varname = parts[1].strip('"')
            filename = parts[2].strip('"')
            save_var(varname, filename)
            return True

        elif cmd == "/mem":
            subcmd = parts[1].lower() if len(parts) > 1 else ""
            detail = subcmd == "detail"
            debug = subcmd == "debug"
            self.buffer_manager.show_memory_usage(SEARCHBUFFER, detail=detail, debug=debug)
            # Also show last generated image memory usage
            if hasattr(self.image_generator, 'last_generated_image') and self.image_generator.last_generated_image is not None:
                file_path, image_data = self.image_generator.last_generated_image
                image_size_kb = len(image_data.encode('utf-8')) / 1024
                print(f"{'LAST_IMAGE':<20} {image_size_kb:>10.2f}")
                if detail:
                    print(f"  -> File path: {file_path}")
                    print(f"  -> Data size: {len(image_data)} chars")
            # Show chat history memory usage
            if self.chat_history:
                total_ch_size = sum(
                    len(p.encode('utf-8')) + len(r.encode('utf-8'))
                    for p, r in self.chat_history
                ) / 1024
                print(f"{'CHAT_HISTORY':<20} {total_ch_size:>10.2f}")
                if detail:
                    print(f"  -> Total exchanges: {len(self.chat_history)}")
                    for idx, (p, r) in enumerate(self.chat_history, 1):
                        p_size = len(p.encode('utf-8')) / 1024
                        r_size = len(r.encode('utf-8')) / 1024
                        p_snip = p.strip().replace('\n', ' ')[:40]
                        r_snip = r.strip().replace('\n', ' ')[:40]
                        print(f"    [{idx}] User: {p_size:.2f} KB | {p_snip}...")
                        print(f"        Bot:  {r_size:.2f} KB | {r_snip}...")
            return True

        elif cmd == "/dump":
            var_name = parts[1] if len(parts) > 1 else "all"
            self.buffer_manager.dump_variables(var_name, SEARCHBUFFER, self.chat_history)
            return True

        elif cmd == "/calc":
            import shlex
            rem_str = command[len(parts[0]):].strip()
            if not rem_str:
                print('Usage: /calc "<expression>" [var_name] or /calc "<expression>"')
                return True

            expr_str = ""
            var_target = "CALC"

            # Parse quoted string vs unquoted arguments
            if rem_str.startswith('"') or rem_str.startswith("'"):
                q = rem_str[0]
                end_q = rem_str.rfind(q)
                if end_q > 0:
                    expr_str = rem_str[1:end_q]
                    after_q = rem_str[end_q + 1:].strip()
                    if after_q:
                        var_target = after_q.split()[0]
                else:
                    expr_str = rem_str.strip('"\'')
            else:
                try:
                    tokens = shlex.split(rem_str)
                except Exception:
                    tokens = rem_str.split()

                if len(tokens) == 1:
                    expr_str = tokens[0]
                elif len(tokens) >= 2:
                    last = tokens[-1].strip()
                    if not any(op in last for op in "+-*/^()"):
                        var_target = last
                        expr_str = " ".join(tokens[:-1])
                    else:
                        expr_str = " ".join(tokens)

            # Perform variable substitution on the expression string
            expr_str = self.buffer_manager.replace_placeholders_legacy(expr_str, clear_unresolved=False)

            try:
                from .tools.math_utils import ensure_mathparse_patched, preprocess_multilingual_expression
                ensure_mathparse_patched()
                from mathparse import mathparse
                lang_code = {
                    "en": "ENG",
                    "es": "ESP",
                    "fr": "FRE",
                    "zh": "CHI",
                    "it": "ITA"
                }.get(self.i18n.locale, "ENG")
                expr_str = preprocess_multilingual_expression(expr_str, self.i18n.locale)
                try:
                    result = mathparse.parse(expr_str, language=lang_code)
                except Exception:
                    result = mathparse.parse(expr_str)
                if result is None:
                    print(f"Error: Could not parse math expression '{expr_str}'.")
                else:
                    # Save to target script var (allowing protected variables like CALC)
                    self.buffer_manager.set_script_var(var_target, result, allow_protected=True)
                    print(f"{var_target} = {result}")
            except Exception as e:
                print(f"Error evaluating math expression '{expr_str}': {e}")
            return True

        elif cmd == "/str_search":
            import shlex
            rem_str = command[len(parts[0]):].strip()
            if not rem_str:
                print('Usage: /str_search "<pattern>" <text_var> [flags] [var_name]')
                print('  flags: c=count (default), m=match positions, i=case-insensitive')
                print('  examples:')
                print('    /str_search "error" ${LOG}')
                print('    /str_search "error" ${LOG} i')
                print('    /str_search "error" ${LOG} ic my_count')
                print('    /str_search "error" ${LOG} m')
                return True

            # Parse arguments: pattern, text_var, flags, var_name
            pattern_str = ""
            text_var = ""
            flags_str = "c"
            var_target = "STR_SEARCH"

            try:
                tokens = shlex.split(rem_str)
            except Exception:
                tokens = rem_str.split()

            if len(tokens) < 2:
                print('Usage: /str_search "<pattern>" <text_var> [flags] [var_name]')
                return True

            pattern_str = tokens[0]
            text_var = tokens[1]

            if len(tokens) >= 3:
                candidate = tokens[2].strip()
                # If the candidate looks like flags (only contains c, m, i, g, I, C, M, G)
                valid_flags = set("cmigCMIG")
                if candidate and all(ch in valid_flags for ch in candidate):
                    flags_str = candidate
                    if len(tokens) >= 4:
                        var_target = tokens[3].strip()
                else:
                    # It's a variable name, no flags
                    var_target = candidate

            # Resolve variable substitution on pattern (supports ${var} in the pattern itself)
            pattern_str = self.buffer_manager.replace_placeholders_legacy(pattern_str, clear_unresolved=False)

            # Parse flags
            case_sensitive = "i" not in flags_str.lower()
            mode = "m" if "m" in flags_str.lower() else "c"

            # Resolve the text variable to get its value
            # text_var is a variable name like LOG or ${LOG} — look up the variable, don't resolve its value
            var_name = text_var
            if var_name.startswith("${") and var_name.endswith("}"):
                var_name = var_name[2:-1]
            text_value = self.buffer_manager.get_script_var(var_name)
            if text_value is None:
                print(f"Error: Variable '{var_name}' is not set.")
                return True
            text_value = str(text_value)

            try:
                from .tools.str_utils import str_search
                result = str_search(
                    pattern=pattern_str,
                    text=text_value,
                    mode=mode,
                    case_sensitive=case_sensitive,
                    target_variable=var_target,
                    app=self,
                )
                if result.get("status") == "error":
                    print(f"Error: {result.get('message')}")
                else:
                    print(result.get("message", ""))
            except Exception as e:
                print(f"Error in str_search: {e}")
            return True

        elif cmd == "/setvar":
            setvar_parts = command.split(maxsplit=2)
            if len(setvar_parts) < 3:
                print("Usage: /setvar <varname> <value>")
                return True
            
            old_user_write = getattr(self.buffer_manager.script_vars, '_is_user_write', False)
            if hasattr(self.buffer_manager.script_vars, '_is_user_write'):
                self.buffer_manager.script_vars._is_user_write = True
            try:
                var_name = setvar_parts[1].strip('"')
                # Use full placeholder replacement to support image banks
                value_with_images = setvar_parts[2]
                
                is_array = var_name.endswith("[]")
                clean_var_name = var_name[:-2] if is_array else var_name

                if not is_array:
                    # Handle leading '=' if user typed `/setvar var = val`
                    value_with_images = value_with_images.strip()
                    if value_with_images.startswith('='):
                        value_with_images = value_with_images[1:].strip()
                    
                    # Handle quoted values for scalar variables (matching script mode parsing)
                    if value_with_images.startswith('"') or value_with_images.startswith("'"):
                        q = value_with_images[0]
                        closing_idx = -1
                        for i in range(1, len(value_with_images)):
                            if value_with_images[i] == "\\":
                                print(f"Error: Escape character '\\' is not allowed in setvar command for '{clean_var_name}'.")
                                return True
                            if value_with_images[i] == q:
                                closing_idx = i
                                break
                        if closing_idx != -1:
                            value_with_images = value_with_images[1:closing_idx]
                        else:
                            print(f"Error: No closing quote found for variable '{clean_var_name}'.")
                            return True

                if is_array:
                    raw_val_str = value_with_images.lstrip().lstrip('=').strip()
                    val_str = raw_val_str
                    try:
                        string_list = self.parse_array_value(val_str)
                    except Exception as e:
                        print(f"Error: Invalid array format for '{clean_var_name}': {e}")
                        return True
                    
                    try:
                        self.buffer_manager.script_vars[clean_var_name] = string_list
                        print(f"Variable '{clean_var_name}' set to array.")
                    except ValueError as e:
                        print(f"Error: {e}")
                    return True

                # Check if value contains imagebank placeholders
                for i in range(1, 6):
                    bank_name = f"imagebank{i}"
                    if bank_name in self.buffer_manager.image_banks:
                        image_data = self.buffer_manager.image_banks[bank_name]
                        if image_data:
                            value_with_images = value_with_images.replace(f"{{{bank_name}}}", image_data)
                            value_with_images = value_with_images.replace(f"${{{bank_name}}}", image_data)
                        
                var_value = self.buffer_manager.replace_placeholders_legacy(value_with_images)
                
                # Check if variable already exists and contains image data or JSON
                if clean_var_name in self.buffer_manager.script_vars:
                    existing_value = self.buffer_manager.script_vars[clean_var_name]
                    if existing_value:
                        # Check if existing value is image data (starts with data:image or is base64)
                        is_existing_image = (
                            existing_value.startswith("data:image/") or 
                            (existing_value.strip().startswith("iVBOR") or  # PNG base64
                             existing_value.strip().startswith("/9j/") or   # JPEG base64
                             existing_value.strip().startswith("UklGR"))    # WebP base64
                        )
                        # Check if existing value is JSON
                        is_existing_json = existing_value.strip().startswith("{") or existing_value.strip().startswith("[")
                        
                        if is_existing_image or is_existing_json:
                            # Check if new value is also image/json - if both are, allow overwrite
                            is_new_image = (
                                var_value.startswith("data:image/") or 
                                (var_value.strip().startswith("iVBOR") or
                                 var_value.strip().startswith("/9j/") or
                                 var_value.strip().startswith("UklGR"))
                            )
                            is_new_json = var_value.strip().startswith("{") or var_value.strip().startswith("[")
                            
                            if not (is_new_image or is_new_json):
                                print(f"Warning: Variable '{clean_var_name}' already contains {'image data' if is_existing_image else 'JSON'}. Not overwritten.")
                                return True
                
                success = self.buffer_manager.set_script_var(clean_var_name, var_value)
                if not success:
                    return True
                return True
            finally:
                if hasattr(self.buffer_manager.script_vars, '_is_user_write'):
                    self.buffer_manager.script_vars._is_user_write = old_user_write

        elif cmd == "/reloadmacros":
            # Support: /reloadmacros or /reloadmacros <filename>
            parts = cmd.split()
            if len(parts) > 1:
                macro_file = parts[1]
                self.load_macros(macro_file)
                print(f"Reloaded macros from '{macro_file}'. {len(self.macros)} macros available.")
            else:
                self.load_macros()
                print(f"Reloaded macros from default file. {len(self.macros)} macros available.")
            return True

        elif cmd.startswith("/listmacros"):
            parts = cmd.split(maxsplit=1)
            filter_term = parts[1].strip() if len(parts) > 1 else None
            self.list_macros(filter_term=filter_term)
            return True

        else:
            print(f"Error: Unknown command '{cmd}'. Type /help for available commands.")
            return False

    async def handle_profile_command(self, args: list) -> None:
        from .profile_manager import ProfileManager
        pm = ProfileManager(getattr(self, 'profile_dir', '~/.config/chatybot/profiles'))
        sub = args[0].lower() if args else "list"

        if sub == "list":
            profiles = pm.list_profiles()
            if not profiles:
                print("No profiles found in", pm.profile_dir)
                return
            print(f"\nAvailable Profiles  ({pm.profile_dir})")
            print("─" * 60)
            for fname in profiles:
                try:
                    meta = pm.read_meta(fname)
                    print(f"  {fname:<30} {meta.description or meta.name}")
                except Exception:
                    print(f"  {fname}")
            print()

        elif sub == "use" and len(args) >= 2:
            try:
                path = pm._resolve_path(args[1])
                await self.execute_script(path)
                print(f"[profile] Applied: {args[1]}")
            except Exception as e:
                print(f"Error applying profile: {e}")

        elif sub == "clone" and len(args) >= 3:
            try:
                dst = pm.clone_profile(args[1], args[2])
                print(f"[profile] Cloned to {dst}")
            except Exception as e:
                print(f"Error cloning profile: {e}")

        elif sub == "delete" and len(args) >= 2:
            try:
                confirm = input(f"Delete profile '{args[1]}'? [y/N] ").strip().lower()
                if confirm == "y":
                    pm.delete_profile(args[1])
                    print(f"[profile] Deleted: {args[1]}")
            except Exception as e:
                print(f"Error deleting profile: {e}")

        elif sub == "export" and len(args) >= 3:
            try:
                pm.export_profile(args[1], args[2])
                print(f"[profile] Exported {args[1]} to {args[2]}")
            except Exception as e:
                print(f"Error exporting profile: {e}")

        elif sub == "import" and len(args) >= 2:
            try:
                dst = pm.import_profile(args[1])
                print(f"[profile] Imported to {dst}")
            except Exception as e:
                print(f"Error importing profile: {e}")

        elif sub == "show" and len(args) >= 2:
            try:
                with open(pm._resolve_path(args[1]), "r", encoding="utf-8") as f:
                    print(f.read())
            except Exception as e:
                print(f"Error showing profile: {e}")

        elif sub == "edit":
            try:
                from .profile_tui import run_profile_tui
                run_profile_tui(profile_dir=pm.profile_dir, config_manager=self.config_manager)
            except Exception as e:
                print(f"Error running profile manager: {e}")

        else:
            print("Usage: /profile [list|use|clone|delete|export|import|show|edit] [args...]")

    def start_vmem_monitoring(self) -> None:
        """Start monitoring virtual memory size of the process in a separate thread."""
        if getattr(self, 'vmem_monitor_active', False):
            print(f"Virtual memory monitoring is already active. Logging to '{self.vmem_log_file}'.")
            return

        import threading
        import time
        import os
        import sys
        import ctypes
        import ctypes.util
        from datetime import datetime

        self.vmem_monitor_active = True
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.vmem_log_file = f"chatybot.vmem.{timestamp}.log"

        def get_phys_footprint(pid: int) -> int:
            if sys.platform != "darwin":
                return 0
            try:
                libproc = ctypes.CDLL(ctypes.util.find_library("libproc") or "libproc.dylib")
                RUSAGE_INFO_V4 = 4
                buffer = (ctypes.c_byte * 1024)()
                ret = libproc.proc_pid_rusage(pid, RUSAGE_INFO_V4, ctypes.byref(buffer))
                if ret != 0:
                    return 0
                import struct
                return struct.unpack_from("Q", buffer, 72)[0]
            except Exception:
                return 0

        def monitor_loop():
            # Write a header to the log file
            try:
                with open(self.vmem_log_file, "a", encoding="utf-8") as f:
                    f.write(f"--- Virtual Memory Monitoring Started: {datetime.now()} ---\n")
                    f.write("Timestamp, VmSize (kB), VmRSS (kB), PhysFootprint (kB)\n")
            except Exception as e:
                print(f"[vmem] Error initializing log file: {e}")
                self.vmem_monitor_active = False
                return

            while self.vmem_monitor_active:
                vmsize = 0
                vmrss = 0
                phys_footprint = 0
                try:
                    with open("/proc/self/status", "r") as proc_f:
                        for line in proc_f:
                            if line.startswith("VmSize:"):
                                parts = line.split()
                                if len(parts) >= 2:
                                     vmsize = int(parts[1])
                            elif line.startswith("VmRSS:"):
                                parts = line.split()
                                if len(parts) >= 2:
                                     vmrss = int(parts[1])
                except Exception:
                    pass

                # If on non-Linux system or procFS read failed, try psutil as fallback
                if vmsize == 0:
                    try:
                        import psutil
                        process = psutil.Process()
                        info = process.memory_info()
                        vmsize = info.vms // 1024
                        vmrss = info.rss // 1024
                    except Exception:
                        pass

                if sys.platform == "darwin":
                    phys_footprint = get_phys_footprint(os.getpid()) // 1024

                # Write to special log file
                if vmsize > 0 or vmrss > 0:
                    try:
                        log_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        with open(self.vmem_log_file, "a", encoding="utf-8") as f:
                            f.write(f"{log_time}, {vmsize}, {vmrss}, {phys_footprint}\n")
                    except Exception:
                        pass

                time.sleep(1.0)

        self.vmem_monitor_thread = threading.Thread(target=monitor_loop, daemon=True)
        self.vmem_monitor_thread.start()
        print(f"Virtual memory monitoring started. Writing to '{self.vmem_log_file}' every second.")

    def stop_vmem_monitoring(self) -> None:
        """Stop virtual memory monitoring."""
        if not getattr(self, 'vmem_monitor_active', False):
            print("Virtual memory monitoring is not active.")
            return

        self.vmem_monitor_active = False
        print(f"Virtual memory monitoring stopped. Final log saved to '{self.vmem_log_file}'.")

    def show_vmem_status(self) -> None:
        """Show the current virtual memory and monitoring status."""
        active = getattr(self, 'vmem_monitor_active', False)
        vmsize = 0
        vmrss = 0
        phys_footprint = 0
        try:
            with open("/proc/self/status", "r") as proc_f:
                for line in proc_f:
                    if line.startswith("VmSize:"):
                        parts = line.split()
                        if len(parts) >= 2:
                            vmsize = int(parts[1])
                    elif line.startswith("VmRSS:"):
                        parts = line.split()
                        if len(parts) >= 2:
                            vmrss = int(parts[1])
        except Exception:
            pass

        if vmsize == 0:
            try:
                import psutil
                process = psutil.Process()
                info = process.memory_info()
                vmsize = info.vms // 1024
                vmrss = info.rss // 1024
            except Exception:
                pass

        import sys
        if sys.platform == "darwin":
            import os
            import ctypes
            import ctypes.util
            import struct
            try:
                libproc = ctypes.CDLL(ctypes.util.find_library("libproc") or "libproc.dylib")
                RUSAGE_INFO_V4 = 4
                buffer = (ctypes.c_byte * 1024)()
                ret = libproc.proc_pid_rusage(os.getpid(), RUSAGE_INFO_V4, ctypes.byref(buffer))
                if ret == 0:
                    phys_footprint = struct.unpack_from("Q", buffer, 72)[0] // 1024
            except Exception:
                pass

        print("Virtual Memory Status:")
        print(f"  Active Monitoring: {'ON' if active else 'OFF'}")
        if active:
            print(f"  Log File: {self.vmem_log_file}")
        print(f"  Current VmSize (Virtual Memory): {vmsize} kB ({vmsize / 1024:.2f} MB)")
        print(f"  Current VmRSS (Resident Physical): {vmrss} kB ({vmrss / 1024:.2f} MB)")
        if sys.platform == "darwin":
            print(f"  Current PhysFootprint (Actual Footprint): {phys_footprint} kB ({phys_footprint / 1024:.2f} MB)")

    def show_help(self) -> None:
        """Show help message with available commands."""
        print("Active escape commands:")
        print("  /help - Show this help message.")
        print("  ! <search_term> - Search command history and select from last 5 matches.")
        print("  /prompt <file> - Load a prompt from a file.")
        print("  /file <path> - Read a text file into the buffer.")
        print(
            "  /showfile [all] - Show the first 100 characters of the file buffer or the entire file if 'all' is specified."
        )
        print("  /clearfile - Clear the file buffer.")
        print(
            "  /filebank{1..5} <file> - Load a text file into filebank1 through filebank5."
        )
        print("  /filebank{1..5} clear - Clear the specified filebank.")
        print(
            "  /filebank{1..5} show [all] - Show the first 100 characters of the filebank or all if 'all' is specified."
        )
        print("  /imagebank{1..5} <file> - Load an image file into imagebank1 through imagebank5.")
        print("  /imagebank{1..5} clear - Clear the specified imagebank.")
        print("  /imagebank{1..5} show - Show info about the imagebank.")
        print("  /imagine <prompt> - Generate image from text (requires vision model)")
        print("  /imagesize <WxH> - Set image resolution (default: 1024x1024)")
        print("  /imagequality <q> - Set quality: standard, high")
        print("  /saveimage [path] - Save last generated image to custom path")
        print("  /imagedir [path] - Set/get default image save directory")
        print("  /model [alias] - Switch to a different model or show current model.")
        print("  /listmodels - List available models from toml.")
        print("  /env [filter] - Display defined API keys and environment variables (set | grep -i api).")
        print("  /logging <start [hex]|end|hex [on|off]> - Start (with optional hex mode) or stop logging.")
        print("  /save <file> [all] [nothink|withthink] - Save last completion or all history to a file (respects /thinking state by default).")
        print("  /notemode <on|off> - Toggle note mode for /save command.")
        print("  /codeonly - Set flag to generate code only without explanations.")
        print("  /codeoff - Reverse the code-only flag.")
        print("  /multiline - Toggle multi-line input mode (use ';;' to end input).")
        print("  /system <message> - Set a custom system message.")
        print("  /temp [<value>|default] - Set temperature for the current model (0.0-2.0, or 'default').")
        print("  /maxtokens <value> - Set max tokens for the current model.")
        print("  /context_limit [tokens|off] - Set or show hard input context token limit.")
        print("  /auto_truncate [on|off|10-100] - Toggle automatic truncation of oldest messages when exceeding context limit percentage.")
        print("  /top_p [<value>|off|default] - Set top_p (0.0-1.0), 'off' to disable, or 'default'.")
        print("  /top_k [<value>|off|default] - Set top_k integer, 'off' to disable, or 'default'.")
        print("  /freq_penalty [<value>|off|default] - Set frequency penalty (-2.0-2.0), 'off', or 'default'.")
        print("  /pres_penalty [<value>|off|default] - Set presence penalty (-2.0-2.0), 'off', or 'default'.")
        print(
            "  /reasoning <on|off> - Toggle reasoning (thinking) for NVIDIA and Qwen models."
        )
        print("  /effort <low|medium|high|none> - Set reasoning effort for OpenAI (o1, o3) and Mistral (mistral-small-latest, mistral-medium-3.5) models.")
        print(
            "  /thinking <on|off> - Toggle display of <think> blocks and reasoning text."
        )
        print(
            "  /thoughtstyle <none|gemma4|nanbeige|nanbeige_code> - Set prompting format for negative prompt to disable reasoning - auto."
        )
        print("  /seed <value> - Set seed (int, 'time', or 'random <min>,<max>').")
        print("  /stream - Toggle streaming responses.")
        print("  /trace <rawpayload|tps|tpsperf|imagedbg|rerank|agentic_loop> <on|off> - Debugging options")
        print("  /debug <payload|response [raw]|vmem [start|stop|status]> - Control debugging features or monitor virtual memory.")
        print("  /echo <text> - Echo text to screen with variable substitution.")
        print("  /reloadmacros [file] - Reload macro definitions from macro.chatdsl or specified file.")
        print("  /source <file> - Execute a script file in the current session without exiting.")
        print("  /profile [list|use|clone|delete|export|import|show|edit] - Manage session profiles dynamically.")
        print("  /script <file> [x=value y=value z=value] - Execute a script file with optional parameters.")
        print("  /quit | /exit - Exit the program.")
        print(
            "  /setdb <dbname> - Create or select a TinyDB database. Use 'Null' to deactivate."
        )
        print("  /dblist - List all TinyDB databases in the db directory.")
        print("  /searchdb <query> - Search all docs in the current database.")
        print("  /dblog [thinking] - Log the last chat completion to the database.")
        print("    thinking: also persist extracted reasoning text and token count.")
        print("  /dbprint - Print the entire database contents in a formatted report.")
        print(
            "  /loadvar <varname> [ALL|id|range] - Load search buffer, all docs, a doc ID, or a range (e.g. 1-5) into a variable."
        )
        print("  /savevar <varname> <filename> - Save a variable's contents to a file.")
        print("  /setvar <varname> <value> - Set a script variable. Supports {CHAT_HISTORY} and {LAST_RESPONSE} placeholders.")
        print('  /calc "<expr>" [varname] - Evaluate a math expression using mathparse and store in a variable (default CALC).')
        print('  /str_search "<pattern>" <var> [flags] [varname] - Search for substring in a text variable (flags: c=count, m=positions, i=case-insensitive).')
        print("  /documents <src>=<id> - Set the active rerank source: db=<name>, var=<name> (or CHAT_HISTORY or file), filebank=<1-5>, or dir=\"<path>\"")
        print("  /rerank \"<query>\" [, top_n=<n>] [, items=<n>] [, split=<sentence|line|paragraph>] - Semantically rerank source sentences/chunks.")
        print("  /mem [detail|debug] - Show size of buffers and script variables. Use 'detail' for element breakdowns, or 'debug' for metadata.")
        print("  /dump [varname|all] - Print content of buffers or script variables.")
        print("  /run <command> - Execute a shell command and store output in RUN_COMPLETION (and LAST_COMPLETION).")
        print("  /run_safe - Enable safe mode (block dangerous commands).")
        print("  /run_unsafe - Disable safe mode (allow dangerous commands).")
        print("  /tool [on|off|list|enable <tool>|disable <tool>|rate_limit <seconds>|prompt|loop|auto] - Manage tool mode and dispatch tool loops/invocations.")
        print("  /proc <name> [key=\"value\"]... - Execute a named procedure block.")
        print("\nScript-specific features:")
        print("  set <name> = <value> - Define a variable")
        print("  ${name} - Reference a variable")
        print("  if <condition> then <command> - Conditional execution")
        print("    Supports: if ${var} then command, if not ${var} then command")
        print('             if "${var} == value" then command, if "true" then command')
        print("             Numeric: >, <, >=, <= (both operands must be numbers)")
        print('             Example: if "${AGE}" >= 18 then /setvar status adult')
        print("  defproc <name>(<params>) ... endproc - Define a reusable procedure block")
        print("  local <name> = <value> - Declare a local procedure variable (snapshotted & restored)")
        print("  foreach <item> in <array|range(...)|lines(...)> ... endfor - Multiline loop construct")
        print("  wait <seconds> - Pause execution")
        print("  # comment - Comments in script files")
        print("\n--- Help Tips ---")
        print("Use '/help <command>' for detailed help on a specific command (e.g., '/help /file').")
        print("Use '/help <keyword>' to filter commands by keyword (e.g., '/help file' shows all file-related commands).")

    async def get_multi_line_input(self) -> str:
        """
        Get multi-line input from the user.

        Returns:
            Multi-line input as a single string
        """
        print("Multi-line mode. Enter your prompt (use ';;' on a new line to finish):")
        lines = []
        while True:
            # Check for interrupt flag during multi-line input
            if self.interrupt_requested:
                print("\nInterrupted. Returning to prompt...")
                self.control_c_count = 0
                self.interrupt_requested = False
                self.multi_line_mode = False
                return ""
            
            line = input()
            if line.strip() == ";;":
                self.multi_line_mode = False
                self.auto_exit_pending = True
                break
            # Process macro calls in each line
            if line.lstrip().startswith("%"):
                expanded = self.process_macro_line(line)
                if expanded.startswith("ERROR:"):
                    print(expanded)
                    lines.append(line)  # Keep original if error
                else:
                    lines.append(expanded)
            else:
                lines.append(line)
        return "\n".join(lines)

    async def main_loop(self) -> None:
        """Main chat loop."""
        print("===========================")
        print("Chatybot.py                ")
        print("Created by Jon Allen - 2026")
        print("Version: 0.7.3             ")
        lang_display = self.i18n.get_ui_string("native_lang_display", "Language: English")
        print(f"{lang_display:<27}")
        print("===========================")
        model_name = self.config_manager.get_model_config(self.config_manager.active_model_alias)['name']
        model_alias = self.config_manager.active_model_alias
        print(
            self.i18n.get_ui_string("active_model_info", "Active model: {model} (alias: {alias})", model=model_name, alias=model_alias)
        )

        # Load and execute profile script if specified via command line or config
        profile_path = getattr(self, 'profile_to_load', None)
        if not profile_path:
            profile_path = self.default_profile
            
        if profile_path:
            from .profile_manager import ProfileManager
            pm = ProfileManager(getattr(self, 'profile_dir', '~/.config/chatybot/profiles'))
            try:
                expanded_path = pm._resolve_path(profile_path)
            except Exception:
                expanded_path = os.path.expanduser(profile_path)

            if os.path.exists(expanded_path):
                try:
                    await self.execute_script(expanded_path)
                except Exception as e:
                    print(f"Error loading profile '{expanded_path}': {e}")
            else:
                # If specified via command line (--profile), warn the user if it doesn't exist.
                # If it's just the default config path and it doesn't exist, ignore silently as requested.
                if getattr(self, 'profile_to_load', None):
                    print(f"Warning: Profile script not found: {expanded_path}")

        # If --no-tools was passed, ensure tools start in a disabled state
        if self.no_tools:
            self.tool_mode = False
            self.tool_auto = False
            self.tool_context = ""
            self.buffer_manager.set_script_var('TOOL_CONTEXT', '')

        while True:
            try:
                # Check for interrupt flag at start of each loop iteration
                if self.interrupt_requested:
                    print("\nInterrupted. Returning to prompt...")
                    self.control_c_count = 0
                    self.interrupt_requested = False
                    continue
                
                if self.multi_line_mode:
                    prompt = await self.get_multi_line_input()
                else:
                    prompt_prefix = self.i18n.get_ui_string("chat_prompt", "chat --> ")
                    prompt = input(prompt_prefix)
                    if self.auto_exit_pending:
                        self.auto_exit_pending = False
                        if self.script_context and prompt.strip() == "/multiline":
                            print(f"depreciated line removed: {prompt.strip()}")
                            continue

                # Handle history search command (!) - must be checked before adding to history
                if prompt.startswith("!"):
                    selected_command = await self.handle_history_command(prompt)
                    if selected_command:
                        # Add the selected command to history, not the ! command
                        if selected_command.strip() and (
                            not self.input_history or selected_command != self.input_history[-1]
                        ):
                            self.input_history.append(selected_command)
                            readline.add_history(selected_command)
                        
                        # Execute the selected command
                        await self.execute_line(selected_command)
                    continue

                # Add to input history (for non-history-search commands)
                if prompt.strip() and (
                    not self.input_history or prompt != self.input_history[-1]
                ):
                    self.input_history.append(prompt)
                    readline.add_history(prompt)

                if not prompt.strip():
                    continue

                await self.execute_line(prompt)

            except KeyboardInterrupt:
                # Reset tool loop state if interrupted during tool operations
                if hasattr(self, 'in_tool_loop') and self.in_tool_loop:
                    self.in_tool_loop = False
                
                if self.control_c_count >= 2:
                    # Second Ctrl+C - exit program
                    msg = self.i18n.get_ui_string("goodbye_message", "Goodbye! Thanks for chatting.")
                    print(f"\n{msg}")
                    self.logging_manager.stop_logging()
                    self.save_input_history()
                    break
                else:
                    # First Ctrl+C - return to prompt
                    print("\nInterrupted. Returning to prompt...")
                    self.control_c_count = 0  # Reset counter after handling
                    self.interrupt_requested = False
                    continue
            except Exception as e:
                if isinstance(e, StopIteration):
                    raise
                print(f"Error: {str(e)}")

    def run(self) -> None:
        """Run the application."""
        self.initialize()
        async def start_and_loop():
            if self.mcp_manager:
                await self.mcp_manager.startup()
            try:
                await self.main_loop()
            finally:
                if self.mcp_manager:
                    await self.mcp_manager.shutdown()
        asyncio.run(start_and_loop())


def run():
    """Entry point for the application."""
    import argparse
    import sys
    import asyncio

    parser = argparse.ArgumentParser(description="Chatybot CLI")
    parser.add_argument(
        "-c", "--config",
        help="Path to alternate TOML configuration file",
        default=None
    )
    parser.add_argument(
        "--config-edit",
        action="store_true",
        help="Launch the TUI configuration manager to edit the models list"
    )
    parser.add_argument(
        "--script",
        help="Path to a ChatDSL script file to execute",
        default=None
    )
    parser.add_argument(
        "--run",
        help="Execute a single chat query / prompt directly",
        default=None
    )
    parser.add_argument(
        "--profile",
        help="Path to a ChatDSL profile script to load at startup (drops into interactive REPL)",
        default=None
    )
    parser.add_argument(
        "--profile-edit", metavar="NAME", nargs="?", const="",
        help="Open TUI profile editor. Optionally specify profile name to edit/create."
    )
    parser.add_argument(
        "--profile-list", action="store_true",
        help="List all available profiles"
    )
    parser.add_argument(
        "--lang",
        help="UI and scripting language (english/en, spanish/es, french/fr, chinese/zh, italian/it, arabic/ar)",
        default="en"
    )
    parser.add_argument(
        "--no-tools",
        action="store_true",
        help="Disable tools on startup and bypass all MCP server loading via stdio"
    )
    args, unknown = parser.parse_known_args()

    if args.config_edit:
        from .config_tui import main as tui_main
        sys.exit(tui_main(config_path=args.config))

    if args.profile_list:
        tmp = ChatybotApp(config_path=args.config, lang=args.lang, no_tools=args.no_tools)
        tmp.initialize()
        from .profile_manager import ProfileManager
        pm = ProfileManager(getattr(tmp, 'profile_dir', '~/.config/chatybot/profiles'))
        profiles = pm.list_profiles()
        if not profiles:
            print("No profiles found in", pm.profile_dir)
            sys.exit(0)
        print(f"\nAvailable Profiles  ({pm.profile_dir})")
        print("─" * 60)
        for fname in profiles:
            try:
                meta = pm.read_meta(fname)
                print(f"  {fname:<30} {meta.description or meta.name}")
            except Exception:
                print(f"  {fname}")
        print()
        sys.exit(0)

    if args.profile_edit is not None:
        tmp = ChatybotApp(config_path=args.config, lang=args.lang, no_tools=args.no_tools)
        tmp.initialize()
        from .profile_tui import run_profile_tui
        sys.exit(run_profile_tui(
            profile_dir=getattr(tmp, 'profile_dir', '~/.config/chatybot/profiles'),
            config_manager=tmp.config_manager,
            initial_profile=args.profile_edit if args.profile_edit else None
        ))

    global app
    app = ChatybotApp(config_path=args.config, lang=args.lang, no_tools=args.no_tools)
    # Also set the module-level app variable
    current_module = sys.modules[__name__]
    current_module.app = app

    if args.script:
        async def run_script():
            app.initialize()
            if app.mcp_manager:
                await app.mcp_manager.startup()
            try:
                await app.execute_script(args.script)
            finally:
                if app.mcp_manager:
                    await app.mcp_manager.shutdown()
                app.logging_manager.stop_logging()
                app.save_input_history()
        try:
            asyncio.run(run_script())
        except KeyboardInterrupt:
            msg = app.i18n.get_ui_string("goodbye_short", "Goodbye!")
            print(f"\n{msg}")
        sys.exit(0)

    elif args.run:
        async def run_query():
            app.initialize()
            if app.mcp_manager:
                await app.mcp_manager.startup()
            try:
                await app.execute_line(args.run)
            finally:
                if app.mcp_manager:
                    await app.mcp_manager.shutdown()
                app.logging_manager.stop_logging()
                app.save_input_history()
        try:
            asyncio.run(run_query())
        except KeyboardInterrupt:
            msg = app.i18n.get_ui_string("goodbye_short", "Goodbye!")
            print(f"\n{msg}")
        sys.exit(0)

    if args.profile:
        app.profile_to_load = args.profile

    app.run()


if __name__ == "__main__":
    run()
