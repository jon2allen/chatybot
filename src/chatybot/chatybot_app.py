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
from datetime import datetime
from typing import Dict, Any, List, Tuple, Optional, Callable, Union
import logging
import atexit
from .pattern import PatternMatcher


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
from EasyRerank import EasyRanker, TextParser
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

    def __init__(self, config_path: Optional[str] = None):
        """Initialize the Chatybot application."""
        # Initialize managers
        self.config_manager = ConfigManager(config_path=config_path)
        self.logging_manager = LoggingManager()
        self.buffer_manager = BufferManager(app=self)
        self.image_generator = ImageGenerator()
        self.image_manager = ImageManager()
        self.help_system = get_help_system()

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
        self.multi_line_mode: bool = False
        self.auto_exit_pending: bool = False
        self.script_context: bool = False
        self.thoughtstyle: str = "none"
        self.default_profile: Optional[str] = None
        
        # Run command settings
        self.safe_mode: bool = True
        self.run_timeout: int = 30
        
        # Tool mode settings
        self.tool_mode: bool = False
        self.tool_context: str = ""
        self.in_tool_loop: bool = False
        self.tool_auto: bool = False
        self.max_turns: int = 25
        self.max_tool_calls_per_turn: int = 10
        self.agentic_instructions: str = ""
        self.tool_timeout: int = 30
        self.rate_limit_delay: float = 0.0
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

        # Trace settings
        self.trace_raw_payload: bool = False
        self.trace_tps: bool = False
        self.trace_tps_perf: bool = False
        self.trace_rerank: bool = False
        self.debug_payload_mode: bool = False
        self.debug_response_mode: bool = False
        self.debug_response_raw: bool = False
        self.debug_payload_data: dict = {}

        # Seed configuration
        self.seed_config: Optional[Union[int, str, Tuple[str, int, int]]] = None

        # Top-level parameters
        self.temperature: Optional[float] = None
        self.top_p: Optional[float] = None
        self.top_k: Optional[int] = None
        self.freq_penalty: Optional[float] = None
        self.pres_penalty: Optional[float] = None

        # Semantic Reranking state
        self.rerank_documents_source = None
        self.latest_rerank_results = []

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

        # Load default profile from tools_config.toml under [config]
        self.default_profile = None
        user_config_path = os.path.expanduser('~/.config/chatybot/tools_config.toml')
        config_path = user_config_path if os.path.exists(user_config_path) else os.path.join(os.path.dirname(__file__), 'tools_config.toml')
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

        # Set up input history
        self.load_input_history()

        # Set up readline for command history
        readline.set_completer(self.input_history_completer)
        readline.parse_and_bind("tab: complete")
        readline.set_completer_delims(" \t\n;") 
        self.matcher =  PatternMatcher(
                 words=[
                    "help", "prompt", "file", "showfile", "clearfile",
                    "filebank", "filebank1", "filebank2", "filebank3", "filebank4",
                    "filebank5", "imagebank", "imagebank1", "imagebank2", "imagebank3",
                    "imagebank4", "imagebank5", "model", "listmodels", "logging", "save",
                    "codeonly", "codeoff", "multiline", "system", "temp", "maxtokens",
                    "top_p", "top_k", "freq_penalty", "pres_penalty", "reasoning", "effort", "seed",
                    "stream", "script", "source", "quit", "setdb", "dblist",
                    "searchdb", "dblog", "dbprint", "loadvar", "savevar",
                    "setvar", "notemode", "mem", "dump", "trace",
                    "thinking", "echo", "def", "reloadmacros",
                    "imagine", "imagesize", "imagequality", "saveimage", "imagedir",
                    "listimages", "showimage", "loadimage", "documents", "rerank",
                    "run", "run_safe", "run_unsafe", "tool"
                    ]

                 )

        # Register save function to be called on exit
        atexit.register(self.save_input_history)
        
        # Initialize macro processing system
        self.macros = {}
        self.setup_macro_grammars()
        
        # Load default macros for interactive use
        self.load_macros()

    def setup_macro_grammars(self):
        """Set up Parsley grammars for macro processing."""
        # Grammar for macro definitions using Parsley
        self.definition_grammar = makeGrammar("""
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
        
        # Grammar for macro invocations using Parsley
        self.invocation_grammar = makeGrammar("""
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
        print(f"\nchat --> ! {search_term}")
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
            if self.matcher.matches(prompt[:12]):
               print( "Error command verb at beginning:  " + prompt[:9] + " - use escape / sequence")
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

            # Prepare messages for chat completion
            # For multimodal (vision) models, use content array with text + images
            if image_list:
                content_parts = [{"type": "text", "text": full_prompt}]
                content_parts.extend(image_list)
                messages = [{"role": "user", "content": content_parts}]
            else:
                messages = [{"role": "user", "content": full_prompt}]

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
            instr = self.agentic_instructions or self.default_agentic_instructions
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
                    reminder = "\n\n(Reminder: You are in a tool loop. You MUST output ONLY the JSON tool call(s) wrapped in ```json and ``` code fences. Do NOT write any conversational text, descriptions, or explanations before or after the JSON block.)"
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

        tp = self.top_p if self.top_p is not None else model_config.get("top_p")
        if tp is not None:
            if is_nvidia:
                kwargs.setdefault("extra_body", {}).setdefault("nvext", {})["top_p"] = (
                    tp
                )
            else:
                kwargs["top_p"] = tp

        fp = (
            self.freq_penalty
            if self.freq_penalty is not None
            else model_config.get("frequency_penalty")
        )
        if fp is not None:
            kwargs["frequency_penalty"] = fp

        pp = (
            self.pres_penalty
            if self.pres_penalty is not None
            else model_config.get("presence_penalty")
        )
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

        tk = self.top_k if self.top_k is not None else model_config.get("top_k")
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

                import re

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
            if hasattr(response, "usage") and response.usage:
                out_tokens = response.usage.completion_tokens
                print(
                    f"Input tokens: {response.usage.prompt_tokens}, Output tokens: {out_tokens}"
                )

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
            try:
                set_stripped = command.lstrip()
                # Use regex to parse "set var = value" supporting multiline (. matches anything with re.S)
                match = re.match(r"set\s+(\w+(?:\[\])?)\s*=\s*(.*)", set_stripped, re.S)
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
                        
                        self.buffer_manager.script_vars[clean_var_name] = string_list
                        print(f"Variable '{clean_var_name}' set to array.")
                        return True
                    else:
                        self.buffer_manager.script_vars[var_name.strip()] = processed_value
                        return True
                else:
                    print("Invalid set command format. Usage: set <name> = <value>")
                    return True
            except Exception as e:
                print(f"Error parsing set command: {e}")
                return True

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
        # We do not replace variables on the command line for /setvar as it handles substitution internally (avoiding splitting elements with commas)
        if command.lstrip().startswith("/setvar"):
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
                    
                    # Check for comparison operators
                    if " == " in condition_str:
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
                    if not cmd.lstrip().startswith("/setvar"):
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

            # Execute each command
            self.script_context = True
            multi_line_buffer = []
            in_multi_line = False

            idx = 0
            while idx < len(commands_list):
                cmd = commands_list[idx]
                if not cmd.strip():
                    idx += 1
                    continue

                # Check if we're in multi-line mode and not processing an escaped command
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
                    if cmd.strip() == ";;":
                        # End of multi-line input, process it
                        self.multi_line_mode = False  # The absolute rule for the new behavior
                        # First, expand any macros in the buffer
                        expanded_lines = []
                        for line in multi_line_buffer:
                            if line.lstrip().startswith("%"):
                                # Expand macro calls immediately
                                expanded = self.process_macro_line(line)
                                if expanded.startswith("ERROR:"):
                                    print(expanded)
                                    expanded_lines.append(line)  # Keep original if error
                                else:
                                    expanded_lines.append(expanded)
                            else:
                                # Keep regular lines as-is
                                expanded_lines.append(line)
                        
                        # Join the processed lines and send to LLM
                        full_prompt = "\n".join(expanded_lines)
                        print(f"Executing multi-line prompt: {full_prompt[:50]}...")
                        handled = await self.execute_script_command(
                            full_prompt, self.handle_escape_command
                        )
                        if not handled:
                            # This is not a command, it's a regular prompt for the LLM
                            # The execute_script_command returns False for regular text
                            print(f"Sending prompt to LLM: {full_prompt[:50]}...")
                            # Here we would normally send to LLM
                            # For now, just indicate success
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
                        # Escaped command in the middle of multi-line - process the buffer first
                        # First, expand any macros in the buffer
                        expanded_lines = []
                        for line in multi_line_buffer:
                            if line.lstrip().startswith("%"):
                                # Expand macro calls immediately
                                expanded = self.process_macro_line(line)
                                if expanded.startswith("ERROR:"):
                                    print(expanded)
                                    expanded_lines.append(line)  # Keep original if error
                                else:
                                    expanded_lines.append(expanded)
                            else:
                                # Keep regular lines as-is
                                expanded_lines.append(line)
                        
                        # Join the processed lines and send to LLM
                        full_prompt = "\n".join(expanded_lines)
                        print(f"Executing multi-line prompt: {full_prompt[:50]}...")
                        handled = await self.execute_script_command(
                            full_prompt, self.handle_escape_command
                        )
                        if not handled:
                            # This is not a command, it's a regular prompt for the LLM
                            # The execute_script_command returns False for regular text
                            print(f"Sending prompt to LLM: {full_prompt[:50]}...")
                            # Here we would normally send to LLM
                            # For now, just indicate success
                            print("Prompt sent to LLM successfully")

                        # Then process the escaped command
                        print(f"Executing: {cmd}")
                        handled = await self.execute_script_command(
                            cmd, self.handle_escape_command
                        )
                        if not handled:
                            print(f"Unknown command in script: {cmd}")
                        in_multi_line = False
                        multi_line_buffer = []
                    else:
                        # Continue building multi-line input
                        # Expand macros in individual lines before adding to buffer
                        if cmd.lstrip().startswith("%"):
                            expanded_line = self.process_macro_line(cmd)
                            if expanded_line.startswith("ERROR:"):
                                print(expanded_line)
                                multi_line_buffer.append(cmd)  # Keep original if error
                            else:
                                multi_line_buffer.append(expanded_line)
                        else:
                            multi_line_buffer.append(cmd)
                else:
                    print(f"Executing: {cmd}")
                    handled = await self.execute_script_command(
                        cmd, self.handle_escape_command
                    )
                    if not handled:
                        print(f"Unknown command in script: {cmd}")

                idx += 1

            print("Script execution finished")

            # If we ended while in multi-line mode, process what we have
            if in_multi_line and multi_line_buffer:
                # First, expand any macros in the buffer
                expanded_lines = []
                for line in multi_line_buffer:
                    if line.lstrip().startswith("%"):
                        # Expand macro calls immediately
                        expanded = self.process_macro_line(line)
                        if expanded.startswith("ERROR:"):
                            print(expanded)
                            expanded_lines.append(line)  # Keep original if error
                        else:
                            expanded_lines.append(expanded)
                    else:
                        # Keep regular lines as-is
                        expanded_lines.append(line)
                
                # Join the processed lines and send to LLM
                full_prompt = "\n".join(expanded_lines)
                print(f"Executing multi-line prompt: {full_prompt[:50]}...")
                handled = await self.execute_script_command(
                    full_prompt, self.handle_escape_command
                )
                if not handled:
                    # This is not a command, it's a regular prompt for the LLM
                    # The execute_script_command returns False for regular text
                    print(f"Sending prompt to LLM: {full_prompt[:50]}...")
                    # Here we would normally send to LLM
                    # For now, just indicate success
                    print("Prompt sent to LLM successfully")

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
                    f"Blocked (safe mode): {danger}")
                self.buffer_manager.set_script_var('RUN_ERROR', '')
                self.buffer_manager.set_script_var('RUN_EXIT_CODE', '-1')
                self.buffer_manager.set_script_var('LAST_COMPLETION', 
                    f"Blocked (safe mode): {danger}")
                print(f"Blocked: {danger}")
                return
            else:
                confirm = input(f"Warning: {danger} Execute anyway? (y/N): ")
                if confirm.lower() != 'y':
                    self.buffer_manager.set_script_var('RUN_COMPLETION', "Command aborted by user")
                    self.buffer_manager.set_script_var('RUN_ERROR', '')
                    self.buffer_manager.set_script_var('RUN_EXIT_CODE', '-1')
                    self.buffer_manager.set_script_var('LAST_COMPLETION', "Command aborted by user")
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
            self.buffer_manager.set_script_var('RUN_COMPLETION', result.stdout)
            self.buffer_manager.set_script_var('RUN_ERROR', result.stderr)
            self.buffer_manager.set_script_var('RUN_EXIT_CODE', str(result.returncode))
            
            # Also store in LAST_COMPLETION for backward compatibility
            self.buffer_manager.set_script_var('LAST_COMPLETION', result.stdout)
            
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
            self.buffer_manager.set_script_var('RUN_COMPLETION', error_msg)
            self.buffer_manager.set_script_var('RUN_ERROR', '')
            self.buffer_manager.set_script_var('RUN_EXIT_CODE', '-2')
            self.buffer_manager.set_script_var('LAST_COMPLETION', error_msg)
            print(error_msg)
            print("Command exited with code -2")
        except FileNotFoundError as e:
            error_msg = f"Error: Command not found: {e.filename}"
            self.buffer_manager.set_script_var('RUN_COMPLETION', '')
            self.buffer_manager.set_script_var('RUN_ERROR', error_msg)
            self.buffer_manager.set_script_var('RUN_EXIT_CODE', '-1')
            self.buffer_manager.set_script_var('LAST_COMPLETION', '')
            print(error_msg)
            print("Command exited with code -1")
        except Exception as e:
            error_msg = f"Error: {e}"
            self.buffer_manager.set_script_var('RUN_COMPLETION', '')
            self.buffer_manager.set_script_var('RUN_ERROR', error_msg)
            self.buffer_manager.set_script_var('RUN_EXIT_CODE', '-1')
            self.buffer_manager.set_script_var('LAST_COMPLETION', '')
            print(error_msg)
            print("Command exited with code -1")

    def dispatch_tool(self, invocation_json: str = None) -> str:
        """
        Dispatch a tool invocation to the dispatcher.
        
        Args:
            invocation_json: JSON string containing tool invocation. If None, uses LAST_COMPLETION.
        
        Returns:
            JSON result from dispatcher as string
        """
        import subprocess
        import tempfile
        import os
        
        # Use LAST_COMPLETION if no invocation_json provided
        if invocation_json is None:
            invocation_json = self.buffer_manager.get_script_var('LAST_COMPLETION') or ""
        
        if not invocation_json.strip():
            print("No tool invocation to dispatch")
            return ""
            
        # Extract clean tool call if possible, to be robust to conversational formatting
        import json
        tool_call = self.extract_tool_call(invocation_json)
        if tool_call:
            invocation_json = json.dumps(tool_call)
        
        # Create a temporary file for the invocation
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as tmp_file:
            tmp_file.write(invocation_json)
            tmp_path = tmp_file.name
        
        try:
            # Build the dispatcher command
            dispatcher_path = os.path.join(os.path.dirname(__file__), 'dispatcher.py')
            user_config_path = os.path.expanduser('~/.config/chatybot/tools_config.toml')
            if not os.path.exists(user_config_path):
                package_config = os.path.join(os.path.dirname(__file__), 'tools_config.toml')
                if os.path.exists(package_config):
                    import shutil
                    os.makedirs(os.path.dirname(user_config_path), exist_ok=True)
                    shutil.copy2(package_config, user_config_path)
            config_path = user_config_path if os.path.exists(user_config_path) else os.path.join(os.path.dirname(__file__), 'tools_config.toml')
            
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
        Returns a list of dictionaries for all valid tool calls found.
        """
        import json
        import re

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

        def normalize_tool_call(data: Any) -> Optional[Dict[str, Any]]:
            if isinstance(data, dict) and "tool" in data:
                tool_name = str(data["tool"])
                if "." in tool_name:
                    tool_name = tool_name.split(".")[-1]
                data["tool"] = tool_name
                return data
            return None

        # Parse to find all balanced JSON objects { ... } in the text
        tool_calls = []
        i = 0
        n = len(text)
        while i < n:
            if text[i] == '{':
                brace_count = 1
                j = i + 1
                in_quote = False
                escaped = False
                while j < n and brace_count > 0:
                    char = text[j]
                    if escaped:
                        escaped = False
                    elif char == '\\':
                        escaped = True
                    elif char == '"':
                        in_quote = not in_quote
                    elif not in_quote:
                        if char == '{':
                            brace_count += 1
                        elif char == '}':
                            brace_count -= 1
                    j += 1
                
                if brace_count == 0:
                    candidate = text[i:j]
                    try:
                        cleaned = clean_json_string(candidate)
                        data = json.loads(cleaned)
                        res = normalize_tool_call(data)
                        if res:
                            tool_calls.append(res)
                            # Move index to the end of this parsed block
                            i = j - 1
                    except Exception:
                        pass
                elif brace_count > 0 and j == n:
                    candidate = text[i:j].rstrip("`\n\r \t")
                    cand_in_quote = False
                    cand_escaped = False
                    cand_brace_count = 0
                    for char in candidate:
                        if cand_escaped:
                            cand_escaped = False
                        elif char == '\\':
                            cand_escaped = True
                        elif char == '"':
                            cand_in_quote = not cand_in_quote
                        elif not cand_in_quote:
                            if char == '{':
                                cand_brace_count += 1
                            elif char == '}':
                                cand_brace_count -= 1
                    if cand_in_quote:
                        candidate += '"'
                    if cand_brace_count > 0:
                        candidate += '}' * cand_brace_count
                    try:
                        cleaned = clean_json_string(candidate)
                        data = json.loads(cleaned)
                        res = normalize_tool_call(data)
                        if res:
                            tool_calls.append(res)
                            # Move index to the end of this parsed block
                            i = j - 1
                    except Exception:
                        pass
            i += 1
            
        return tool_calls

    async def execute_tool_loop(self, max_turns: int) -> None:
        """
        Executes the autonomous agentic tool loop (Option B - History Management).
        """
        import json
        
        # Initialize or reset the AGENTIC_LOOP script variable
        self.buffer_manager.set_script_var('AGENTIC_LOOP', [])

        if not self.chat_history:
            print("No prompt has been executed yet. Please run a prompt first.")
            return

        initial_prompt, last_completion = self.chat_history[-1]
        
        # Enable tool loop state
        self.in_tool_loop = True

        # Always reload and refresh the tool context when starting the loop
        context = self.generate_tool_context()
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

        # If the last completion was natural language (not a tool call), request an initial tool call from the LLM
        if not self.extract_tool_call(current_response):
            print("Last completion was not a tool call. Requesting initial tool call from LLM...")
            if getattr(self, 'rate_limit_delay', 0.0) > 0.0:
                print(f"Pausing for {self.rate_limit_delay}s rate limit delay...")
                await asyncio.sleep(self.rate_limit_delay)
            current_response = await self.chat_completion(temp_history, stream=self.streaming_enabled)
        
        print(f"Starting agentic tool loop (max turns: {max_turns})...")
        
        while turn_count < max_turns:
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
                    result_str = self.dispatch_tool(json.dumps(tc))
                except Exception as e:
                    result_str = json.dumps({"status": "error", "message": f"Dispatch execution error: {str(e)}"})
                    self.buffer_manager.set_script_var('TOOL_DISPATCH_RESULT', result_str)
                    self.buffer_manager.set_script_var('TOOL_DISPATCH_EXIT_CODE', '1')
                    
                print(f"Tool Result: {result_str}")
                results.append(f"Tool: {tool_name}\nArguments: {json.dumps(tool_args)}\nResult: {result_str}")

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
                self.buffer_manager.set_script_var('AGENTIC_LOOP', current_loop)

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
                self.buffer_manager.set_script_var('AGENTIC_LOOP', current_loop)

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
            if getattr(self, 'rate_limit_delay', 0.0) > 0.0:
                print(f"Pausing for {self.rate_limit_delay}s rate limit delay...")
                await asyncio.sleep(self.rate_limit_delay)

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
            print(f"[Turn {turn_count+1}/{max_turns}] Requesting next completion...")
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
        
        # Log final response from inside the tool loop if logging is active
        if self.logging_manager.logging_active:
            self.logging_manager.log_message(f"Assistant (Agentic Loop Final): {final_natural_language_response}\n")
            
        print("\nAgentic Tool Loop finished.")
        print(f"Final Response:\n{final_natural_language_response}")

    def _load_tools_config(self) -> dict:
        """Loads and returns the TOML tool definitions configuration."""
        import os
        user_config_path = os.path.expanduser('~/.config/chatybot/tools_config.toml')
        if not os.path.exists(user_config_path):
            package_config = os.path.join(os.path.dirname(__file__), 'tools_config.toml')
            if os.path.exists(package_config):
                import shutil
                os.makedirs(os.path.dirname(user_config_path), exist_ok=True)
                shutil.copy2(package_config, user_config_path)
        config_path = user_config_path if os.path.exists(user_config_path) else os.path.join(os.path.dirname(__file__), 'tools_config.toml')
        
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
                self.rate_limit_delay = float(config_section.get('rate_limit_delay'))
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

        tools = config.get('tools', {})
        if not tools:
            return ""
        
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
        
        lines.append("\n=== END TOOLS ===\n")
        
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
        cmd = parts[0].lower()

        if cmd == "/help":
            # Handle /help with optional query argument
            if len(parts) > 1:
                query = parts[1]
                print(self.help_system.get_help_text(query))
            else:
                self.show_help()
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
                else:
                    print("Unknown /trace subcommand. Use rawpayload, tps, tpsperf, imagedbg, or rerank.")
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
                else:
                    print("Unknown /debug subcommand. Use payload, response, or response raw.")
            else:
                print("Usage: /debug <payload|response [raw]>")
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
            print(f"Switched to model: {model_config['name']} (alias: {model_alias})")
            return True

        elif cmd == "/logging":
            if len(parts) < 2:
                print("Usage: /logging <start|end>")
                return True

            action = parts[1].lower()
            if action == "start":
                self.logging_manager.start_logging()
            elif action == "end":
                self.logging_manager.stop_logging()
            else:
                print("Invalid logging action. Use 'start' or 'end'.")
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

            try:
                temp = float(parts[1])
                if not 0.0 <= temp <= 2.0:
                    raise ValueError
                self.temperature = temp
                print(f"Temperature set to {temp}")
            except ValueError:
                print(
                    "Invalid temperature value. Please provide a number between 0.0 and 2.0."
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

        elif cmd == "/top_p":
            if len(parts) < 2:
                current_tp = (
                    self.top_p
                    if self.top_p is not None
                    else self.config_manager.get_model_config(
                        self.config_manager.active_model_alias
                    ).get("top_p", "Default")
                )
                print(f"Current top_p: {current_tp}")
                return True
            try:
                val = float(parts[1])
                self.top_p = val
                print(f"top_p set to {val}")
            except ValueError:
                print("Invalid top_p value. Please enter a float.")
            return True

        elif cmd == "/top_k":
            if len(parts) < 2:
                current_tk = (
                    self.top_k
                    if self.top_k is not None
                    else self.config_manager.get_model_config(
                        self.config_manager.active_model_alias
                    ).get("top_k", "Default")
                )
                print(f"Current top_k: {current_tk}")
                return True
            try:
                val = int(parts[1])
                self.top_k = val
                print(f"top_k set to {val}")
            except ValueError:
                print("Invalid top_k value. Please enter an integer.")
            return True

        elif cmd == "/freq_penalty":
            if len(parts) < 2:
                current_fp = (
                    self.freq_penalty
                    if self.freq_penalty is not None
                    else self.config_manager.get_model_config(
                        self.config_manager.active_model_alias
                    ).get("frequency_penalty", "Default")
                )
                print(f"Current frequency penalty: {current_fp}")
                return True
            try:
                val = float(parts[1])
                self.freq_penalty = val
                print(f"Frequency penalty set to {val}")
            except ValueError:
                print("Invalid frequency penalty value. Please enter a float.")
            return True

        elif cmd == "/pres_penalty":
            if len(parts) < 2:
                current_pp = (
                    self.pres_penalty
                    if self.pres_penalty is not None
                    else self.config_manager.get_model_config(
                        self.config_manager.active_model_alias
                    ).get("presence_penalty", "Default")
                )
                print(f"Current presence penalty: {current_pp}")
                return True
            try:
                val = float(parts[1])
                self.pres_penalty = val
                print(f"Presence penalty set to {val}")
            except ValueError:
                print("Invalid presence penalty value. Please enter a float.")
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
            print("Safe mode enabled - dangerous patterns require confirmation")
            return True

        elif cmd == "/run_unsafe":
            self.safe_mode = False
            print("Safe mode disabled - dangerous commands allowed without confirmation")
            return True

        elif cmd == "/tool":
            # Handle /tool subcommands: on, off, or dispatch
            if len(parts) < 2:
                # No subcommand - dispatch tool invocation from LAST_COMPLETION
                self.dispatch_tool()
                return True
            
            subcmd = parts[1].lower()
            
            if subcmd == "list":
                config = self._load_tools_config()
                tools = config.get('tools', {})
                if not tools:
                    print("No tools defined in configuration.")
                    return True
                print("\nAvailable Tools:")
                for tool_name, tool_meta in tools.items():
                    config_enabled = tool_meta.get('enabled', False)
                    is_enabled = self.tool_overrides.get(tool_name, config_enabled)
                    status = "[ON] " if is_enabled else "[OFF]"
                    desc = tool_meta.get('description', 'No description')
                    print(f"  {status}  {tool_name:<16} - {desc}")
                print("")
                return True
            
            elif subcmd in ("enable", "disable"):
                if len(parts) < 3:
                    print(f"Usage: /tool {subcmd} <tool_name>|all")
                    return True
                
                target = parts[2].strip()
                config = self._load_tools_config()
                tools = config.get('tools', {})
                
                target_value = (subcmd == "enable")
                
                if target.lower() == "all":
                    for tool_name in tools.keys():
                        self.tool_overrides[tool_name] = target_value
                    print(f"All tools {'enabled' if target_value else 'disabled'}.")
                else:
                    if target not in tools:
                        # Check case-insensitive
                        matched_tool = None
                        for t in tools.keys():
                            if t.lower() == target.lower():
                                matched_tool = t
                                break
                        if matched_tool:
                            target = matched_tool
                        else:
                            print(f"Error: Tool '{target}' not found in configuration.")
                            return True
                    
                    self.tool_overrides[target] = target_value
                    print(f"Tool '{target}' {'enabled' if target_value else 'disabled'}.")
                
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
            
            elif subcmd == "prompt":
                # Show the prompt injected during tool operation
                context = self.tool_context or self.generate_tool_context()
                if context:
                    print("\n=== TOOL CONTEXT INJECTED INTO PROMPT ===")
                    print(context)
                    print("\n=== AGENTIC LOOP SYSTEM INSTRUCTIONS ===")
                    print(self.agentic_instructions or self.default_agentic_instructions)
                    print("=========================================\n")
                else:
                    print("No tools available or tool context could not be generated.")
                return True
            
            else:
                # Check if argument is a filename (ends with .json)
                arg = command.split(maxsplit=1)[1]
                if arg.endswith('.json') and os.path.exists(arg):
                    # Read JSON from file
                    try:
                        with open(arg, 'r') as f:
                            json_str = f.read()
                        self.dispatch_tool(json_str)
                    except Exception as e:
                        print(f"Error reading file {arg}: {e}")
                else:
                    # Provide JSON directly - dispatch it
                    self.dispatch_tool(arg)
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
                print('Usage: /script <file> [x="value"] [y="value"] [z="value"]')
                return True

            # Extract script path and parameters
            script_path = parts[1]
            
            # Parse parameters from the command
            import re
            param_pattern = r'(^|\s+)([xyz])\s*=\s*("[^"]*"|\'[^\']*\'|\S+)'
            
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
            for var_name, var_value in params.items():
                self.buffer_manager.set_script_var(var_name, var_value)
            
            print("command /script with ", actual_script_path)
            # Execute script asynchronously so it doesn't block the main loop
            await self.execute_script(actual_script_path)
            return True

        elif cmd in ["/quit", "/exit"]:
            print("Goodbye! Thanks for chatting.")
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
            query = parts[1].strip('"')
            search_db(query)
            return True
        elif cmd == "/dblog":
            dblog()
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

        elif cmd == "/setvar":
            if len(parts) < 3:
                print("Usage: /setvar <varname> <value>")
                return True
            var_name = parts[1].strip('"')
            # Use full placeholder replacement to support image banks
            value_with_images = parts[2]
            
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
                val_str = value_with_images.lstrip().lstrip('=').strip()
                try:
                    string_list = self.parse_array_value(val_str)
                except Exception as e:
                    print(f"Error: Invalid array format for '{clean_var_name}': {e}")
                    return True
                
                self.buffer_manager.set_script_var(clean_var_name, string_list)
                print(f"Variable '{clean_var_name}' set to array.")
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
            
            self.buffer_manager.set_script_var(clean_var_name, var_value)
            return True

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

        return False

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
        print("  /logging <start|end> - Start or stop logging.")
        print("  /save <file> [all] [nothink|withthink] - Save last completion or all history to a file (respects /thinking state by default).")
        print("  /notemode <on|off> - Toggle note mode for /save command.")
        print("  /codeonly - Set flag to generate code only without explanations.")
        print("  /codeoff - Reverse the code-only flag.")
        print("  /multiline - Toggle multi-line input mode (use ';;' to end input).")
        print("  /system <message> - Set a custom system message.")
        print("  /temp <value> - Set temperature for the current model (0.0-2.0).")
        print("  /maxtokens <value> - Set max tokens for the current model.")
        print("  /top_p <value> - Set top_p for the current model (0.0-1.0).")
        print("  /top_k <value> - Set top_k for the current model.")
        print("  /freq_penalty <value> - Set frequency penalty (-2.0-2.0).")
        print("  /pres_penalty <value> - Set presence penalty (-2.0-2.0).")
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
        print("  /trace <rawpayload|tps|tpsperf|imagedbg|rerank> <on|off> - Debugging options")
        print("  /debug <payload|response [raw]> - Activate debug mode for the next prompt.")
        print("  /echo <text> - Echo text to screen with variable substitution.")
        print("  /reloadmacros [file] - Reload macro definitions from macro.chatdsl or specified file.")
        print("  /source <file> - Execute a script file in the current session without exiting.")
        print("  /script <file> [x=value y=value z=value] - Execute a script file with optional parameters.")
        print("  /quit | /exit - Exit the program.")
        print(
            "  /setdb <dbname> - Create or select a TinyDB database. Use 'Null' to deactivate."
        )
        print("  /dblist - List all TinyDB databases in the db directory.")
        print("  /searchdb <query> - Search all docs in the current database.")
        print("  /dblog - Log the last chat completion to the database.")
        print("  /dbprint - Print the entire database contents in a formatted report.")
        print(
            "  /loadvar <varname> [ALL|id|range] - Load search buffer, all docs, a doc ID, or a range (e.g. 1-5) into a variable."
        )
        print("  /savevar <varname> <filename> - Save a variable's contents to a file.")
        print("  /setvar <varname> <value> - Set a script variable. Supports {CHAT_HISTORY} and {LAST_RESPONSE} placeholders.")
        print("  /documents <src>=<id> - Set the active rerank source: db=<name>, var=<name> (or CHAT_HISTORY or file), filebank=<1-5>, or dir=\"<path>\"")
        print("  /rerank \"<query>\" [, top_n=<n>] [, items=<n>] [, split=<sentence|line|paragraph>] - Semantically rerank source sentences/chunks.")
        print("  /mem [detail|debug] - Show size of buffers and script variables. Use 'detail' for element breakdowns, or 'debug' for metadata.")
        print("  /dump [varname|all] - Print content of buffers or script variables.")
        print("  /run <command> - Execute a shell command and store output in RUN_COMPLETION (and LAST_COMPLETION).")
        print("  /run_safe - Enable safe mode (block dangerous commands).")
        print("  /run_unsafe - Disable safe mode (allow dangerous commands).")
        print("  /tool [on|off|list|enable <tool>|disable <tool>|prompt|loop|auto] - Manage tool mode and dispatch tool loops/invocations.")
        print("\nScript-specific features:")
        print("  set <name> = <value> - Define a variable")
        print("  ${name} - Reference a variable")
        print("  if <condition> then <command> - Conditional execution")
        print("    Supports: if ${var} then command, if not ${var} then command")
        print('             if "${var} == value" then command, if "true" then command')
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
        print("Created by Jon Allen - 2025")
        print("Version: 0.6.2             ")
        print("===========================")
        print(
            f"Active model: {self.config_manager.get_model_config(self.config_manager.active_model_alias)['name']} (alias: {self.config_manager.active_model_alias})"
        )

        # Load and execute profile script if specified via command line or config
        profile_path = getattr(self, 'profile_to_load', None)
        if not profile_path:
            profile_path = self.default_profile
            
        if profile_path:
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

        while True:
            try:
                if self.multi_line_mode:
                    prompt = await self.get_multi_line_input()
                else:
                    prompt = input("chat --> ")
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
                print("\nGoodbye! Thanks for chatting.")
                self.logging_manager.stop_logging()
                self.save_input_history()
                break
            except Exception as e:
                print(f"Error: {str(e)}")

    def run(self) -> None:
        """Run the application."""
        self.initialize()
        asyncio.run(self.main_loop())


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
    args, unknown = parser.parse_known_args()

    if args.config_edit:
        from .config_tui import main as tui_main
        sys.exit(tui_main(config_path=args.config))

    global app
    app = ChatybotApp(config_path=args.config)
    # Also set the module-level app variable
    current_module = sys.modules[__name__]
    current_module.app = app

    if args.script:
        async def run_script():
            app.initialize()
            await app.execute_script(args.script)
            app.logging_manager.stop_logging()
            app.save_input_history()
        try:
            asyncio.run(run_script())
        except KeyboardInterrupt:
            print("\nGoodbye!")
        sys.exit(0)

    elif args.run:
        async def run_query():
            app.initialize()
            await app.execute_line(args.run)
            app.logging_manager.stop_logging()
            app.save_input_history()
        try:
            asyncio.run(run_query())
        except KeyboardInterrupt:
            print("\nGoodbye!")
        sys.exit(0)

    if args.profile:
        app.profile_to_load = args.profile

    app.run()


if __name__ == "__main__":
    run()
