"""
ChatyBot Help System

Provides structured help for commands with:
- Keyword filtering
- Command deep-dive details
- Category organization
- Expandable for future features
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field


@dataclass
class CommandHelp:
    """Structured help information for a single command."""
    name: str
    category: str
    short_desc: str
    usage: str = ""
    long_desc: str = ""
    examples: List[str] = field(default_factory=list)
    aliases: List[str] = field(default_factory=list)
    see_also: List[str] = field(default_factory=list)
    parameters: Dict[str, str] = field(default_factory=dict)
    
    def matches_keyword(self, keyword: str) -> bool:
        """Check if this command matches the given keyword."""
        keyword_lower = keyword.lower()
        if keyword_lower in self.name.lower():
            return True
        if keyword_lower in self.short_desc.lower():
            return True
        if keyword_lower in self.long_desc.lower():
            return True
        if keyword_lower in self.category.lower():
            return True
        for alias in self.aliases:
            if keyword_lower in alias.lower():
                return True
        for example in self.examples:
            if keyword_lower in example.lower():
                return True
        return False


class HelpSystem:
    """Central help system for ChatyBot commands."""
    
    def __init__(self):
        self.commands: Dict[str, CommandHelp] = {}
        self.categories: Dict[str, List[str]] = {}
        self._initialize_commands()
    
    def _initialize_commands(self) -> None:
        """Initialize all command help entries."""
        # File management commands
        self.register_command(CommandHelp(
            name="/help",
            category="system",
            short_desc="Show this help message",
            usage="/help [command|keyword]",
            long_desc="Display available commands. Use '/help <command>' for detailed help on a specific command, or '/help <keyword>' to filter commands by keyword.",
            examples=["/help", "/help /file", "/help filebank"],
            see_also=["/listcommands"]
        ))
        
        # File commands
        self.register_command(CommandHelp(
            name="/file",
            category="file",
            short_desc="Load a text file into the buffer",
            usage="/file <path>",
            long_desc="Loads text from a file into the persistent file buffer. This content can be referenced in prompts and will be included as context for LLM calls.",
            examples=["/file prompt.txt", "/file data.json"],
            see_also=["/showfile", "/clearfile", "/filebank1", "/filebank2", "/filebank3", "/filebank4", "/filebank5"]
        ))
        
        self.register_command(CommandHelp(
            name="/showfile",
            category="file",
            short_desc="Show the file buffer content",
            usage="/showfile [all]",
            long_desc="Display the contents of the file buffer. Without 'all', shows only the first 100 characters. With 'all', shows the complete content.",
            examples=["/showfile", "/showfile all"],
            see_also=["/file", "/clearfile"]
        ))
        
        self.register_command(CommandHelp(
            name="/clearfile",
            category="file",
            short_desc="Clear the file buffer",
            usage="/clearfile",
            long_desc="Clears the file buffer in memory. This does not affect files on disk.",
            see_also=["/file", "/showfile"]
        ))
        
        # Filebank commands (1-5)
        for i in range(1, 6):
            self.register_command(CommandHelp(
                name=f"/filebank{i}",
                category="file",
                short_desc=f"Manage file bank {i}",
                usage=f"/filebank{i} <file|clear|show [all]>",
                long_desc=f"Load text from a file into file bank {i}, clear it, or show its contents. File banks are persistent text buffers that can be referenced as {{filebank{i}}} in prompts.",
                examples=[f"/filebank{i} document.txt", f"/filebank{i} clear", f"/filebank{i} show all"],
                see_also=["/file", "/showfile"]
            ))
        
        # Image bank commands (1-5)
        for i in range(1, 6):
            self.register_command(CommandHelp(
                name=f"/imagebank{i}",
                category="image",
                short_desc=f"Manage image bank {i}",
                usage=f"/imagebank{i} <file|clear|show>",
                long_desc=f"Load an image file into image bank {i}, clear it, or show info about it. Images can be referenced in prompts for vision models.",
                examples=[f"/imagebank{i} photo.jpg", f"/imagebank{i} clear", f"/imagebank{i} show"],
                see_also=["/imagine", "/imagesize", "/imagequality"]
            ))
        
        # Image commands
        self.register_command(CommandHelp(
            name="/imagine",
            category="image",
            short_desc="Generate image from text",
            usage="/imagine <prompt>",
            long_desc="Generate an image from a text prompt using a vision model.",
            examples=["/imagine a sunset over mountains", "/imagine a futuristic city"],
            see_also=["/imagesize", "/imagequality", "/saveimage"]
        ))
        
        self.register_command(CommandHelp(
            name="/imagesize",
            category="image",
            short_desc="Set image resolution",
            usage="/imagesize <WxH>",
            long_desc="Set the resolution for generated images. Default is 1024x1024.",
            examples=["/imagesize 1024x1024", "/imagesize 512x512"],
            parameters={"WxH": "Width and height in pixels (e.g., 1024x1024)"},
            see_also=["/imagine", "/imagequality"]
        ))
        
        self.register_command(CommandHelp(
            name="/imagequality",
            category="image",
            short_desc="Set image quality",
            usage="/imagequality <quality>",
            long_desc="Set the quality for generated images.",
            examples=["/imagequality standard", "/imagequality high"],
            parameters={"quality": "standard or high"},
            see_also=["/imagine", "/imagesize"]
        ))
        
        self.register_command(CommandHelp(
            name="/saveimage",
            category="image",
            short_desc="Save last generated image",
            usage="/saveimage [path]",
            long_desc="Save the last generated image to a file. If no path is specified, uses the default image save directory.",
            examples=["/saveimage output.png", "/saveimage"],
            see_also=["/imagedir"]
        ))
        
        self.register_command(CommandHelp(
            name="/imagedir",
            category="image",
            short_desc="Set/get default image save directory",
            usage="/imagedir [path]",
            long_desc="Set or display the default directory for saving generated images.",
            examples=["/imagedir ./images", "/imagedir"]
        ))
        
        # Model commands
        self.register_command(CommandHelp(
            name="/model",
            category="model",
            short_desc="Switch to a different model or show current",
            usage="/model [alias]",
            long_desc="Switch between configured AI models or display the current model. Model aliases are defined in the configuration file.",
            examples=["/model", "/model gpt-4", "/model mistral-medium"],
            see_also=["/listmodels"]
        ))
        
        self.register_command(CommandHelp(
            name="/listmodels",
            category="model",
            short_desc="List available models",
            usage="/listmodels",
            long_desc="Display all models configured in the chat_config.toml file with their aliases.",
            see_also=["/model"]
        ))
        
        self.register_command(CommandHelp(
            name="/env",
            category="model",
            short_desc="Display defined API keys and environment variables",
            usage="/env [filter]",
            long_desc="Display defined API keys and environment variables (checks all vendor templates plus active environment variables like 'set | grep -i api'). Pass an optional filter (e.g. '/env hf', '/env set', '/env missing') to filter results.",
            examples=["/env", "/env hf", "/env set", "/env api"],
            see_also=["/listmodels", "/model"]
        ))
        
        # Model parameter commands
        model_params = [
            ("temp", "temperature", "0.0-2.0", "Controls randomness in model output", ["/temp 0.7", "/temp default", "/temp"]),
            ("maxtokens", "max_tokens", "integer", "Maximum number of tokens to generate", ["/maxtokens 2048", "/maxtokens"]),
            ("top_p", "top_p", "0.0-1.0|off|default", "Nucleus sampling parameter", ["/top_p 0.9", "/top_p off", "/top_p default", "/top_p"]),
            ("top_k", "top_k", "integer|off|default", "Number of most likely tokens to consider (pass 'off' to disable)", ["/top_k 50", "/top_k off", "/top_k default", "/top_k"]),
            ("freq_penalty", "frequency_penalty", "-2.0-2.0|off|default", "Penalty for repeated tokens", ["/freq_penalty 0.5", "/freq_penalty off", "/freq_penalty default", "/freq_penalty"]),
            ("pres_penalty", "presence_penalty", "-2.0-2.0|off|default", "Penalty for new tokens based on presence", ["/pres_penalty 0.5", "/pres_penalty off", "/pres_penalty default", "/pres_penalty"]),
        ]
        
        for item in model_params:
            cmd, param, value_range, desc, examples = item
            aliases = ["/max_tokens"] if cmd == "maxtokens" else []
            self.register_command(CommandHelp(
                name=f"/{cmd}",
                category="model",
                short_desc=f"Set or toggle {param}",
                usage=f"/{cmd} [{value_range}]",
                long_desc=f"Set or disable the {param} parameter for the current model. {desc}.",
                examples=examples,
                aliases=aliases,
                parameters={"value": value_range}
            ))

        self.register_command(CommandHelp(
            name="/context_limit",
            category="model",
            short_desc="Set or show input context token limit",
            usage="/context_limit [<tokens>|off]",
            long_desc="Set a hard token limit for the input context. When set, warns when approaching the limit and triggers auto-truncation if enabled. Use 'off' or '0' to disable.",
            examples=["/context_limit", "/context_limit 4096", "/context_limit off"],
            see_also=["/auto_truncate", "/maxtokens"]
        ))

        self.register_command(CommandHelp(
            name="/auto_truncate",
            category="model",
            short_desc="Toggle automatic context truncation with optional percentage",
            usage="/auto_truncate [on|off|10-100]",
            long_desc="Enable or disable automatic truncation of oldest conversation history messages when input tokens exceed the configured context limit or a specific percentage (10% - 100%). Default 'on' is 100%. If percentage is below 10%, auto-truncation is disabled.",
            examples=["/auto_truncate", "/auto_truncate on", "/auto_truncate 80", "/auto_truncate off"],
            see_also=["/context_limit"]
        ))
        
        # Reasoning commands
        self.register_command(CommandHelp(
            name="/reasoning",
            category="model",
            short_desc="Toggle reasoning for supported models",
            usage="/reasoning <on|off>",
            long_desc="Enable or disable reasoning/thinking output for models that support it (e.g., NVIDIA, Qwen).",
            examples=["/reasoning on", "/reasoning off"],
            see_also=["/effort", "/thinking"]
        ))
        
        self.register_command(CommandHelp(
            name="/effort",
            category="model",
            short_desc="Set reasoning effort / reasoning strength",
            usage="/effort <low|medium|high|xhigh|none>",
            long_desc="Set the reasoning effort / reasoning strength level for models that support it (e.g., OpenAI o1/o3, Mistral, GLM-5.2, Meta Muse Glimmer).",
            examples=["/effort high", "/effort xhigh", "/effort none"],
            parameters={"level": "low, medium, high, xhigh, or none"}
        ))
        
        self.register_command(CommandHelp(
            name="/thinking",
            category="model",
            short_desc="Toggle display of thinking blocks",
            usage="/thinking <on|off>",
            long_desc="Enable or disable the display of <think> blocks and reasoning text in responses.",
            examples=["/thinking on", "/thinking off"]
        ))
        
        self.register_command(CommandHelp(
            name="/thoughtstyle",
            category="model",
            short_desc="Set prompting format for reasoning",
            usage="/thoughtstyle <style>",
            long_desc="Set the style for reasoning prompts to disable reasoning automatically.",
            examples=["/thoughtstyle none", "/thoughtstyle gemma4"],
            parameters={"style": "none, gemma4, nanbeige, nanbeige_code"}
        ))
        
        # Seed command
        self.register_command(CommandHelp(
            name="/seed",
            category="model",
            short_desc="Set random seed",
            usage="/seed <value>",
            long_desc="Set the random seed for reproducible outputs. Can be an integer, 'time', or 'random <min>,<max>'.",
            examples=["/seed 42", "/seed time", "/seed random 1,100"],
            parameters={"value": "integer, 'time', or 'random <min>,<max>'"}
        ))
        
        # Stream command
        self.register_command(CommandHelp(
            name="/stream",
            category="model",
            short_desc="Toggle streaming responses",
            usage="/stream",
            long_desc="Toggle between streaming (real-time) and batch (complete) response modes.",
            examples=["/stream"]
        ))
        
        # System command
        self.register_command(CommandHelp(
            name="/system",
            category="model",
            short_desc="Set a custom system message",
            usage="/system <message>",
            long_desc="Set a custom system message for LLM completion. Leave empty to reset to default.",
            examples=["/system You are a helpful assistant", "/system"]
        ))
        
        # Code mode commands
        self.register_command(CommandHelp(
            name="/codeonly",
            category="output",
            short_desc="Enable code-only mode",
            usage="/codeonly",
            long_desc="Enable code-only mode which instructs the model to generate only code without explanations or commentary.",
            see_also=["/codeoff"]
        ))
        
        self.register_command(CommandHelp(
            name="/codeoff",
            category="output",
            short_desc="Disable code-only mode",
            usage="/codeoff",
            long_desc="Disable code-only mode, allowing the model to provide explanations and commentary along with code.",
            see_also=["/codeonly"]
        ))
        
        # Multi-line command
        self.register_command(CommandHelp(
            name="/multiline",
            category="input",
            short_desc="Toggle multi-line input mode",
            usage="/multiline",
            long_desc="Toggle multi-line input mode. When enabled, use ';;' on a new line to finish input. Useful for entering long prompts.",
            examples=["/multiline", "Type your prompt here...\n;;"],
            see_also=["/prompt"]
        ))
        
        # Prompt command
        self.register_command(CommandHelp(
            name="/prompt",
            category="input",
            short_desc="Load a prompt from a file",
            usage="/prompt <file>",
            long_desc="Load prompt text from a file. The prompt will be sent to the LLM on the next interaction.",
            examples=["/prompt my_prompt.txt"],
            see_also=["/file", "/multiline"]
        ))
        
        # Logging commands
        self.register_command(CommandHelp(
            name="/logging",
            category="debug",
            short_desc="Start (with optional hex mode) or stop logging",
            usage="/logging <start [hex]|end|hex [on|off]>",
            long_desc="Start or stop logging of chat interactions to a file. Pass 'hex' (e.g. '/logging start hex' or '/logging hex on') to convert unprintable/control characters and zero-width tokens into hex escapes like [0x1B] or [U+200B].",
            examples=["/logging start", "/logging start hex", "/logging hex on", "/logging end"]
        ))
        
        # Save command
        self.register_command(CommandHelp(
            name="/save",
            category="output",
            short_desc="Save last chat completion to a file",
            usage="/save <file>",
            long_desc="Save the last chat completion response to a file. Only the most recent completion can be saved.",
            examples=["/save output.txt", "/save response.md"],
            see_also=["/notemode"]
        ))
        
        self.register_command(CommandHelp(
            name="/notemode",
            category="output",
            short_desc="Toggle note mode for /save command",
            usage="/notemode <on|off>",
            long_desc="When enabled, the /save command will save responses in a note-taking format.",
            examples=["/notemode on", "/notemode off"],
            see_also=["/save"]
        ))
        
        # Note mode command
        self.register_command(CommandHelp(
            name="/notemode",
            category="output",
            short_desc="Toggle note mode for save command",
            usage="/notemode <on|off>",
            long_desc="Toggle note mode which affects how the /save command formats saved content.",
            examples=["/notemode on", "/notemode off"]
        ))
        
        # Debug commands
        self.register_command(CommandHelp(
            name="/trace",
            category="debug",
            short_desc="Debugging options",
            usage="/trace <rawpayload|tps|tpsperf|imagedbg|rerank|agentic_loop> <on|off>",
            long_desc="Enable or disable various debugging trace options. For agentic_loop, 'on' enables automatic display of agentic tool loop trace after each loop completion (showing total calls, success/failure counts, and per-call status), and 'off' disables automatic display but preserves collected data. The trace data is always collected regardless of this setting.",
            examples=["/trace rawpayload on", "/trace tps off", "/trace agentic_loop on"],
            parameters={
                "subcommand": "rawpayload, tps, tpsperf, imagedbg, rerank, or agentic_loop",
                "state": "on or off"
            }
        ))
        
        self.register_command(CommandHelp(
            name="/debug",
            category="debug",
            short_desc="Activate debug mode or monitor virtual memory",
            usage="/debug <payload|response [raw]|vmem [start|stop|status]>",
            long_desc="Activate debug mode or manage virtual memory (vmem) monitoring. Supported options:\n"
                      "  payload       - Capture next prompt payload for manual editing before execution\n"
                      "  response      - Output a formatted JSON dump of the next completion response\n"
                      "  response raw  - Output the raw unformatted completion response\n"
                      "  vmem start    - Start background thread to log virtual memory and RSS stats every second\n"
                      "  vmem stop     - Stop the active background virtual memory monitoring thread\n"
                      "  vmem status   - Display current virtual memory and RSS usage and monitoring state",
            examples=["/debug payload", "/debug response raw", "/debug vmem start", "/debug vmem status"],
            parameters={"subcommand": "payload, response [raw], or vmem [start|stop|status]"}
        ))
        
        self.register_command(CommandHelp(
            name="/echo",
            category="utility",
            short_desc="Echo text with variable substitution",
            usage="/echo <text>",
            long_desc="Display text to the screen with variable substitution applied. Useful for testing variable values.",
            examples=["/echo Hello ${name}", "/echo Current model: {current_model}"]
        ))
        
        # Macro commands
        self.register_command(CommandHelp(
            name="/listmacros",
            category="script",
            short_desc="List loaded macros and signatures",
            usage="/listmacros [filter]",
            long_desc=(
                "List all currently loaded macros with parameter signatures and prompt previews.\n"
                "Pass an optional filter string to search macro names or prompt templates.\n\n"
                "TUTORIAL - HOW TO DEFINE AND EXECUTE MACROS:\n"
                "1. Defining Macros (in macro.chatdsl or script):\n"
                "   • No-param macro:  def build() = \"Build project with release settings\"\n"
                "   • Param macro:     def expert(type) = \"You are an expert in {type}.\"\n"
                "2. Executing Macros (in interactive prompt or script):\n"
                "   • Syntax:          %macro_name(arg1, arg2)\n"
                "   • Examples:        %regen()\n"
                "                      %expert(python)\n"
                "                      %debug_help(python, sorting arrays, IndexError)"
            ),
            examples=["/listmacros", "/listmacros debug", "/listmacros language"],
            aliases=["/macro", "macro"],
            see_also=["/reloadmacros"]
        ))

        self.register_command(CommandHelp(
            name="/reloadmacros",
            category="script",
            short_desc="Reload macro definitions",
            usage="/reloadmacros [file]",
            long_desc="Reload macro definitions from macro.chatdsl or the specified file. Macros are shortcuts for frequently used prompt text.",
            examples=["/reloadmacros", "/reloadmacros custom_macros.chatdsl"],
            see_also=["/listmacros"]
        ))
        
        # Script command
        self.register_command(CommandHelp(
            name="/script",
            category="script",
            short_desc="Execute a script file with optional parameters",
            usage="/script <file> [x=value y=value ...]",
            long_desc="Execute a script file containing multiple commands. Optionally pass parameters that can be referenced in the script.",
            examples=["/script workflow.chatdsl", "/script generate.chatdsl x=5 y=10"],
            see_also=["set", "if", "wait"]
        ))

        # Source command
        self.register_command(CommandHelp(
            name="/source",
            category="script",
            short_desc="Execute a script file in the current session",
            usage="/source <file>",
            long_desc="Execute a script file containing multiple commands in the current interactive session without exiting.",
            examples=["/source ~/.chatybot_profile", "/source load_vars.chatdsl"],
            see_also=["/script"]
        ))
        
        # Profile command
        self.register_command(CommandHelp(
            name="/profile",
            category="script",
            short_desc="Manage chat session profiles dynamically",
            usage="/profile [list|use|clone|delete|export|import|show|edit] [args...]",
            long_desc="Manage session profiles and their configurations. Supported subcommands:\n"
                      "  list                 - List all available profiles and their descriptions\n"
                      "  use <name>           - Apply/execute the specified profile script\n"
                      "  clone <src> <dst>    - Copy an existing profile to a new name\n"
                      "  delete <name>        - Delete a profile after confirmation\n"
                      "  export <name> <file> - Export a profile script to a file path\n"
                      "  import <file>        - Import a profile script from a file path\n"
                      "  show <name>          - Display the script contents of a profile\n"
                      "  edit [name]          - Launch the interactive curses profile editor",
            examples=[
                "/profile list",
                "/profile use coding",
                "/profile edit coding",
                "/profile clone general development",
                "/profile delete test_profile"
            ],
            see_also=["/source", "/script"]
        ))
        
        # Database commands
        db_commands = [
            ("setdb", "Create or select a TinyDB database", "/setdb <dbname>", "Use 'Null' to deactivate", ["/setdb mydb", "/setdb Null"]),
            ("dblist", "List all TinyDB databases", "/dblist", "", []),
            ("searchdb", "Search all docs in current database", "/searchdb <query>", "", ["/searchdb python"]),
            ("dblog", "Log last completion to database", "/dblog [thinking]", "Add 'thinking' to also persist extracted reasoning text and token count", ["/dblog", "/dblog thinking"]),
            ("dbprint", "Print entire database contents", "/dbprint", "", []),
        ]
        
        for cmd, desc, usage, long_desc, examples in db_commands:
            self.register_command(CommandHelp(
                name=f"/{cmd}",
                category="database",
                short_desc=desc,
                usage=usage,
                long_desc=long_desc,
                examples=examples
            ))
        
        # Variable commands
        self.register_command(CommandHelp(
            name="/loadvar",
            category="variable",
            short_desc="Load search buffer or docs into a variable",
            usage="/loadvar <varname> [ALL|id|range]",
            long_desc="Load content into a variable. Can load search buffer, all docs, a specific doc ID, or a range of docs.",
            examples=["/loadvar results ALL", "/loadvar doc1 5", "/loadvar pages 1-5"]
        ))
        
        self.register_command(CommandHelp(
            name="/savevar",
            category="variable",
            short_desc="Save a variable's contents to a file",
            usage="/savevar <varname> <filename>",
            long_desc="Save the contents of a script variable to a file.",
            examples=["/savevar output results.txt"]
        ))
        
        self.register_command(CommandHelp(
            name="/setvar",
            category="variable",
            short_desc="Set a script variable",
            usage="/setvar <varname> <value>",
            long_desc="Set a script variable to a string value. Surrounding quotes and leading '=' are automatically stripped. To have quotes inside quotes, alternate single and double quotes instead of escaping with '\\' (which is forbidden to prevent script parsing errors). This is for text only, not image data.",
            examples=[
                "/setvar name John",
                "/setvar count = 42",
                "/setvar quote_var 'This is an \"inner\" quote'"
            ]
        ))

        self.register_command(CommandHelp(
            name="/calc",
            category="variable",
            short_desc="Evaluate mathematical expressions using mathparse",
            usage="/calc \"<expression>\" [var_name]",
            long_desc="Parses and evaluates a math expression using mathparse. Results are saved to a protected script variable 'CALC' by default, or to a custom variable if specified.",
            examples=[
                "/calc \"Add one to ${test1}\"",
                "/calc \"2 + 10\" test1",
                "/calc \"fifty times two\""
            ]
        ))

        self.register_command(CommandHelp(
            name="/str_search",
            category="variable",
            short_desc="Search for substring patterns in a text variable",
            usage="/str_search \"<pattern>\" <text_var> [flags] [var_name]",
            long_desc="Searches for a substring pattern within a text variable. Supports case-sensitive and case-insensitive matching. "
                      "Flags: c=count (default), m=match positions, i=case-insensitive. "
                      "Results are saved to a protected script variable 'STR_SEARCH' by default, or to a custom variable if specified.",
            examples=[
                '/str_search "error" ${LOG}',
                '/str_search "error" ${LOG} i',
                '/str_search "error" ${LOG} ic my_count',
                '/str_search "error" ${LOG} m',
                '/str_search "TODO" ${CODE} i matches',
            ]
        ))
        
        self.register_command(CommandHelp(
            name="/mem",
            category="debug",
            short_desc="Show size of buffers and variables",
            usage="/mem [detail|debug]",
            long_desc="Display memory usage information including buffer sizes, LAST_RESPONSE, and script variable counts.\n\nModes:\n  /mem - Show summary of buffer and variable sizes\n  /mem detail - Show detailed breakdown of all memory elements including file banks, image banks, tool context, session info, and chat history\n  /mem debug - Show memory summary with additional technical metadata and debugging information",
            examples=["/mem", "/mem detail", "/mem debug"]
        ))
        
        self.register_command(CommandHelp(
            name="/dump",
            category="debug",
            short_desc="Print content of buffers or variables",
            usage="/dump [varname|all]",
            long_desc="Print the contents of buffers or script variables. Use 'all' to dump everything. Supports LAST_RESPONSE.",
            examples=["/dump filebank1", "/dump all", "/dump LAST_RESPONSE"]
        ))
        
        # Search command
        self.register_command(CommandHelp(
            name="!",
            category="history",
            short_desc="Search command history",
            usage="! <search_term>",
            long_desc="Search command history and select from the last 5 matches. The selected command will be executed.",
            examples=["! file", "! model"]
        ))
        
        # Quit command
        self.register_command(CommandHelp(
            name="/quit",
            category="system",
            short_desc="Exit the program",
            usage="/quit",
            long_desc="Exit ChatyBot.",
            examples=["/quit"]
        ))
        
        # Shell execution and tool extraction commands
        self.register_command(CommandHelp(
            name="/run",
            category="scripting",
            short_desc="Execute a shell command",
            usage="/run <command>",
            long_desc="Execute a shell command and store the output in RUN_COMPLETION (stdout), RUN_ERROR (stderr), RUN_EXIT_CODE (return code). Also stores in LAST_COMPLETION for backward compatibility. Supports variable substitution with ${VAR} syntax.",
            examples=["/run echo hello", "/run df -h", "/run echo ${VAR}", "/echo ${RUN_COMPLETION}"],
            see_also=["/run_safe", "/run_unsafe"]
        ))
        
        self.register_command(CommandHelp(
            name="/run_safe",
            category="scripting",
            short_desc="Enable safe mode for /run commands",
            usage="/run_safe",
            long_desc="Enable safe mode (default). In safe mode, dangerous shell commands (like rm -rf, sudo, etc.) are blocked.",
            examples=["/run_safe", "/run safe"],
            see_also=["/run_unsafe", "/run"]
        ))
        
        self.register_command(CommandHelp(
            name="/run_unsafe",
            category="scripting",
            short_desc="Disable safe mode for /run commands",
            usage="/run_unsafe [askfirst]",
            long_desc="Disable safe mode. Dangerous shell commands will be executed without confirmation. If 'askfirst' is specified (/run_unsafe askfirst or /run unsafe askfirst), dangerous commands will prompt for user confirmation (y/N) before executing.",
            examples=["/run_unsafe", "/run_unsafe askfirst", "/run unsafe", "/run unsafe askfirst"],
            see_also=["/run_safe", "/run"]
        ))
        
        self.register_command(CommandHelp(
            name="/tool",
            category="scripting",
            short_desc="Manage tool mode and dispatch tool invocations",
            usage="/tool [on|off|list|enable <tool>|disable <tool>|max_turns <int>|rate_limit <seconds>|prompt [live_edit|edit_live|restore]|loop [turns|max|max=val] [force]|auto [on|off]|<json_file.json>|<json_invocation>]",
            long_desc="Manage tool mode for LLM tool calling. When tool mode is on, tool definitions from tools_config.toml are available for the LLM to use.\n\nSubcommands:\n  /tool on - Enable tool mode, inject tool definitions into context\n  /tool off - Disable tool mode\n  /tool list - List all tools, showing enabled/disabled status and description\n  /tool enable <tool>|all - Enable a specific tool or all tools at runtime\n  /tool disable <tool>|all - Disable a specific tool or all tools at runtime\n  /tool max_turns [count] - Set or show the default maximum turns for autonomous tool loops (e.g. when triggered via '/tool auto on')\n  /tool rate_limit [seconds] - Set or show rate limit delay (seconds) between LLM calls in tool loop\n  /tool prompt [live_edit|edit_live|restore] - Show prompts injected during tool operation, open editor to live-edit system instructions, or restore prompt overrides to tools_config.toml defaults\n  /tool loop [turns|max|max=val] [force] - Start the autonomous agentic tool loop. Runs for the specified number of turns (default 25). Use 'max' or 'max=100' to set limits. Loop counts greater than 100 require the 'force' flag.\n  /tool auto [on|off] - Enable/disable auto execution of the tool loop upon detecting a tool call in any completion\n  /tool <file.json> - Dispatch tool invocation from JSON file\n  /tool [json] - Dispatch a tool invocation directly (uses LAST_COMPLETION if no argument provided)",
            examples=["/tool on", "/tool off", "/tool list", "/tool auto on", "/tool max_turns 75", "/tool rate_limit 3", "/tool enable list_directory", "/tool disable write_file", "/tool disable all", "/tool prompt", "/tool prompt live_edit", "/tool prompt restore", "/tool loop", "/tool loop 50", '/tool {"tool": "list_directory", "arguments": {"path": "."}}'],
            see_also=["/run"]
        ))

        self.register_command(CommandHelp(
            name="/session",
            category="scripting",
            short_desc="Manage session history persistence, workspace metrics, merging, pruning, and exports",
            usage="/session [start <name>|auto [on|off]|history [on|off]|stop|off|status|note <text>|save [name]|list [all|compressed|uncompressed|limit=N|range=start:end|model=M]|use <name>|show [-t]|export <file.md> [-t]|info|delete <name|id|--all>|merge <target> <s1> <s2>|compress [name|pattern|days|all]|uncompress [name|pattern|all]|prune [keep=N] [days=D] [size=M]]",
            long_desc="Manage session-based conversation persistence and workspace storage.\n\nSubcommands:\n  /session start <name> - Clear active history and start a new named session\n  /session auto [on|off] - Toggle automatic session creation & turn saving\n  /session history [on|off] - Toggle in-memory chat history collection (disables tool loops when off)\n  /session stop / off - Pause session recording\n  /session status - Show active session details and file path\n  /session note <text> - Add/update annotation note (max 1024 chars, excluded from LLM context)\n  /session save [name] - Save or update active session custom name\n  /session list [all|compressed|uncompressed|limit=N|range=start:end|model=M] - List saved sessions with prompt slugs, notes, and turn counts (default: show 10 newest)\n  /session use <name|id> - Load an existing session from disk (automatically decompresses if compressed)\n  /session show [--thinking|-t] - Display formatted view of active session\n  /session export <file.md> [--thinking|-t] - Export session transcript to Markdown\n  /session info / stats - Display workspace metrics (count, total size, oldest, newest, largest)\n  /session delete <name|id|--all> - Delete a specific session file or purge all sessions\n  /session merge <target> <s1> <s2> - Merge multiple sessions sequentially into a new session\n  /session compress [name|pattern|days|all] - Gzip compress session files by name, wildcard (e.g. mistral*), or age\n  /session uncompress [name|pattern|all] - Decompress gzip compressed session files by name, wildcard, or all\n  /session prune [keep=N] [days=D] [size=M] - Prune session files by count, age, or size quota",
            examples=["/session start refactor_parser", "/session list compressed", "/session compress mistral*", "/session compress 7", "/session uncompress *dufu*", "/session uncompress all", "/session history off", "/session note benchmark run for v2.5", "/session info", "/session delete old_session", "/session merge combined_session s1 s2", "/session prune keep=10 days=30 size=50", "/session export summary.md -t"],
            see_also=["/save", "/logging"]
        ))

        self.register_command(CommandHelp(
            name="/proc",
            category="scripting",
            short_desc="Execute a procedure defined with defproc",
            usage="/proc <name> [param1=\"val1\" param2=\"val2\"]",
            long_desc="Executes a named procedure defined via 'defproc' or loaded from a procedure script file (.chatdsl). Creates an isolated stack frame with Save/Restore local scoping for arguments and local variables.",
            examples=["/proc summarize_text text=\"${file_buffer}\"", "/proc generate_report topic=\"AI\""],
            see_also=["defproc", "local", "endproc"]
        ))

        self.register_command(CommandHelp(
            name="defproc",
            category="scripting",
            short_desc="Define a reusable procedure block",
            usage="defproc <name>(<param1>, <param2>, ...)\n  <commands>\nendproc",
            long_desc="Defines a procedure with parameter names. Can be invoked later with '/proc <name> param1=\"val\"'. Inside procedure definitions, 'local var = val' isolates local variables using virtual stack frame snapshotting.",
            examples=["defproc greet(name)\n  /echo Hello ${name}\nendproc"],
            see_also=["/proc", "endproc", "local"]
        ))

        self.register_command(CommandHelp(
            name="local",
            category="scripting",
            short_desc="Declare a local variable within a procedure",
            usage="local <name> = <value>",
            long_desc="Declares a local variable inside a procedure block. The original variable value before the procedure invocation will be snapshotted and automatically restored when the procedure exits.",
            examples=['local mode = "fast"', 'local temp_val = ${LAST_RESPONSE}'],
            see_also=["defproc", "endproc", "/proc"]
        ))

        self.register_command(CommandHelp(
            name="foreach",
            category="scripting",
            short_desc="Iterate over arrays, numeric ranges, or lines of text",
            usage="foreach <item_var> in <array_var | range(...) | lines(...)>\n  <commands>\nendfor",
            long_desc="Multiline loop construct. Iterates over elements of an array variable, a numeric generator 'range(start:end[:step])', or lines of text 'lines(text_var|filebank)'. Automatically snapshots and restores the loop variable state.",
            examples=[
                "foreach item in fruits\n  /echo Item: ${item}\nendfor",
                "foreach page in range(1:154)\n  /echo Page: ${page}\nendfor",
                "foreach line in lines({filebank1})\n  /echo Line: ${line}\nendfor"
            ],
            see_also=["endfor", "set"]
        ))
    
    def register_command(self, cmd_help: CommandHelp) -> None:
        """Register a command with the help system."""
        self.commands[cmd_help.name] = cmd_help
        if cmd_help.category not in self.categories:
            self.categories[cmd_help.category] = []
        if cmd_help.name not in self.categories[cmd_help.category]:
            self.categories[cmd_help.category].append(cmd_help.name)
    
    def get_all_commands(self) -> List[CommandHelp]:
        """Get all registered commands sorted alphabetically."""
        return sorted(self.commands.values(), key=lambda c: c.name)
    
    def get_commands_by_category(self, category: str) -> List[CommandHelp]:
        """Get all commands in a specific category."""
        if category not in self.categories:
            return []
        return [self.commands[name] for name in self.categories[category] if name in self.commands]
    
    def get_all_categories(self) -> List[str]:
        """Get all available categories sorted alphabetically."""
        return sorted(self.categories.keys())
    
    def get_command(self, name: str) -> Optional[CommandHelp]:
        """Get help for a specific command."""
        return self.commands.get(name)
    
    def filter_commands(self, keyword: str) -> List[CommandHelp]:
        """Filter commands by keyword."""
        keyword_lower = keyword.lower()
        return [cmd for cmd in self.commands.values() if cmd.matches_keyword(keyword_lower)]
    
    def format_command_list(self, commands: List[CommandHelp], i18n: Optional[Any] = None) -> str:
        """Format a list of commands for display."""
        if not commands:
            msg = "No commands found."
            if i18n:
                msg = i18n.get_help_string("headers", "no_commands", msg)
            return msg
        
        lines = []
        # Group by category for better organization
        categorized: Dict[str, List[CommandHelp]] = {}
        for cmd in commands:
            if cmd.category not in categorized:
                categorized[cmd.category] = []
            categorized[cmd.category].append(cmd)
        
        for category in sorted(categorized.keys()):
            category_commands = sorted(categorized[category], key=lambda c: c.name)
            display_category = category
            if i18n:
                display_category = i18n.get_help_string("categories", category, category)
            
            lines.append(f"\n{display_category.upper()}:")
            for cmd in category_commands:
                display_name = cmd.name
                display_desc = cmd.short_desc
                if i18n:
                    aliases = i18n.catalog.get(i18n.locale, {}).get("aliases", {})
                    for loc, canonical in aliases.items():
                        if canonical == cmd.name:
                            display_name = loc
                            break
                    cmd_info = i18n.get_help_string("commands", cmd.name, {})
                    if isinstance(cmd_info, dict):
                        display_desc = cmd_info.get("short_desc", cmd.short_desc)
                
                lines.append(f"  {display_name} - {display_desc}")
        
        return "\n".join(lines)
    
    def format_command_detail(self, cmd_help: CommandHelp, i18n: Optional[Any] = None) -> str:
        """Format detailed help for a single command."""
        lines = []
        
        lbl_category = "Category"
        lbl_usage = "Usage"
        lbl_parameters = "Parameters"
        lbl_examples = "Examples"
        lbl_aliases = "Aliases"
        lbl_see_also = "See also"
        
        display_name = cmd_help.name
        display_category = cmd_help.category
        display_short = cmd_help.short_desc
        display_long = cmd_help.long_desc
        display_usage = cmd_help.usage
        
        if i18n:
            lbl_category = i18n.get_help_string("headers", "category", lbl_category)
            lbl_usage = i18n.get_help_string("headers", "usage", lbl_usage)
            lbl_parameters = i18n.get_help_string("headers", "parameters", lbl_parameters)
            lbl_examples = i18n.get_help_string("headers", "examples", lbl_examples)
            lbl_aliases = i18n.get_help_string("headers", "aliases", lbl_aliases)
            lbl_see_also = i18n.get_help_string("headers", "see_also", lbl_see_also)
            
            aliases = i18n.catalog.get(i18n.locale, {}).get("aliases", {})
            for loc, canonical in aliases.items():
                if canonical == cmd_help.name:
                    display_name = loc
                    break
            
            display_category = i18n.get_help_string("categories", cmd_help.category, cmd_help.category)
            
            cmd_info = i18n.get_help_string("commands", cmd_help.name, {})
            if isinstance(cmd_info, dict):
                display_short = cmd_info.get("short_desc", cmd_help.short_desc)
                display_long = cmd_info.get("long_desc", cmd_help.long_desc)
            
            for loc, canonical in aliases.items():
                if canonical in display_usage:
                    display_usage = display_usage.replace(canonical, loc)
        
        lines.append(f"\n{display_name}")
        lines.append("=" * len(display_name))
        
        if display_category:
            lines.append(f"{lbl_category}: {display_category}")
        
        if display_usage:
            lines.append(f"{lbl_usage}: {display_usage}")
        
        if display_short:
            lines.append(f"\n{display_short}")
        
        if display_long:
            lines.append(f"\n{display_long}")
        
        if cmd_help.parameters:
            lines.append(f"\n{lbl_parameters}:")
            for param, desc in cmd_help.parameters.items():
                display_param_desc = desc
                if i18n:
                    cmd_info = i18n.get_help_string("commands", cmd_help.name, {})
                    if isinstance(cmd_info, dict):
                        display_param_desc = cmd_info.get("parameters", {}).get(param, desc)
                lines.append(f"  {param} - {display_param_desc}")
        
        if cmd_help.examples:
            lines.append(f"\n{lbl_examples}:")
            for example in cmd_help.examples:
                display_example = example
                if i18n:
                    aliases = i18n.catalog.get(i18n.locale, {}).get("aliases", {})
                    for loc, canonical in aliases.items():
                        if canonical in display_example:
                            display_example = display_example.replace(canonical, loc)
                lines.append(f"  {display_example}")
        
        if cmd_help.aliases:
            display_aliases = cmd_help.aliases
            if i18n:
                aliases_map = i18n.catalog.get(i18n.locale, {}).get("aliases", {})
                translated_aliases = []
                for alias in cmd_help.aliases:
                    found = False
                    for loc, canonical in aliases_map.items():
                        if canonical == alias:
                            translated_aliases.append(loc)
                            found = True
                            break
                    if not found:
                        translated_aliases.append(alias)
                display_aliases = translated_aliases
            lines.append(f"\n{lbl_aliases}: {', '.join(display_aliases)}")
        
        if cmd_help.see_also:
            display_see_also = cmd_help.see_also
            if i18n:
                aliases_map = i18n.catalog.get(i18n.locale, {}).get("aliases", {})
                translated_see_also = []
                for item in cmd_help.see_also:
                    found = False
                    for loc, canonical in aliases_map.items():
                        if canonical == item:
                            translated_see_also.append(loc)
                            found = True
                            break
                    if not found:
                        translated_see_also.append(item)
                display_see_also = translated_see_also
            lines.append(f"\n{lbl_see_also}: {', '.join(display_see_also)}")
        
        return "\n".join(lines)
    
    def get_help_text(self, query: Optional[str] = None, i18n: Optional[Any] = None) -> str:
        """
         Get help text based on query.
        
         Args:
             query: None for full help, a command name for specific help, or a keyword for filtering
             i18n: LocalizationManager instance for translating output
        
         Returns:
             Formatted help text
        """
        if query is not None and i18n is not None:
            norm = query.lower()
            if not norm.startswith("/"):
                alias_with_slash = i18n.resolve_command("/" + norm)
                if alias_with_slash.startswith("/"):
                    query = alias_with_slash
            else:
                query = i18n.resolve_command(norm)

        if query is None:
            return self.format_command_list(self.get_all_commands(), i18n=i18n)
        
        if query in self.commands:
            return self.format_command_detail(self.commands[query], i18n=i18n)

        if query.startswith('/'):
            query_without_slash = query.lstrip('/')
            if f"/{query_without_slash}" in self.commands:
                return self.format_command_detail(self.commands[f"/{query_without_slash}"], i18n=i18n)
            elif query_without_slash in self.commands:
                return self.format_command_detail(self.commands[query_without_slash], i18n=i18n)
            else:
                filtered = self.filter_commands(query)
                if not filtered:
                    msg = "No commands found matching '{query}'. Try /help for all commands."
                    if i18n:
                        msg = i18n.get_help_string("headers", "no_commands", msg)
                    return msg.format(query=query)
                return self.format_command_list(filtered, i18n=i18n)
        
        filtered = self.filter_commands(query)
        if not filtered:
            msg = "No commands found matching '{query}'. Try /help for all commands."
            if i18n:
                msg = i18n.get_help_string("headers", "no_commands", msg)
            return msg.format(query=query)
        
        return self.format_command_list(filtered, i18n=i18n)


# Global help system instance
_help_system = None


def get_help_system() -> HelpSystem:
    """Get the global help system instance."""
    global _help_system
    if _help_system is None:
        _help_system = HelpSystem()
    return _help_system


def reset_help_system() -> None:
    """Reset the global help system instance."""
    global _help_system
    _help_system = HelpSystem()


if __name__ == "__main__":
    # Test the help system
    help_sys = get_help_system()
    
    print("Testing /help system:")
    print("\n--- All commands ---")
    print(help_sys.get_help_text())
    
    print("\n--- Filter by 'file' ---")
    print(help_sys.get_help_text("file"))
    
    print("\n--- Specific command '/file' ---")
    print(help_sys.get_help_text("/file"))
