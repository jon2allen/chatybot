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
        
        # Model parameter commands
        model_params = [
            ("temp", "temperature", "0.0-2.0", "Controls randomness in model output"),
            ("maxtokens", "max_tokens", "integer", "Maximum number of tokens to generate"),
            ("top_p", "top_p", "0.0-1.0", "Nucleus sampling parameter"),
            ("top_k", "top_k", "integer", "Number of most likely tokens to consider"),
            ("freq_penalty", "frequency_penalty", "-2.0-2.0", "Penalty for repeated tokens"),
            ("pres_penalty", "presence_penalty", "-2.0-2.0", "Penalty for new tokens based on presence"),
        ]
        
        for cmd, param, value_range, desc in model_params:
            self.register_command(CommandHelp(
                name=f"/{cmd}",
                category="model",
                short_desc=f"Set {param}",
                usage=f"/{cmd} [{value_range}]",
                long_desc=f"Set the {param} parameter for the current model. {desc}.",
                examples=[f"/{cmd} 0.7", f"/{cmd}"],
                parameters={"value": value_range}
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
            short_desc="Set reasoning effort",
            usage="/effort <low|medium|high|none>",
            long_desc="Set the reasoning effort level for models that support it (e.g., OpenAI o1/o3, Mistral).",
            examples=["/effort high", "/effort none"],
            parameters={"level": "low, medium, high, or none"}
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
            short_desc="Start or stop logging",
            usage="/logging <start|end>",
            long_desc="Start or stop logging of chat interactions to a file.",
            examples=["/logging start", "/logging end"]
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
            usage="/trace <rawpayload|tps|tpsperf|imagedbg> <on|off>",
            long_desc="Enable or disable various debugging trace options.",
            examples=["/trace rawpayload on", "/trace tps off"],
            parameters={
                "subcommand": "rawpayload, tps, tpsperf, or imagedbg",
                "state": "on or off"
            }
        ))
        
        self.register_command(CommandHelp(
            name="/debug",
            category="debug",
            short_desc="Activate debug mode",
            usage="/debug <payload|response [raw]>",
            long_desc="Activate debug mode for the next prompt. 'payload' captures the request payload, 'response raw' prints the raw response.",
            examples=["/debug payload", "/debug response raw"],
            parameters={"subcommand": "payload or response [raw]"}
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
            name="/reloadmacros",
            category="script",
            short_desc="Reload macro definitions",
            usage="/reloadmacros [file]",
            long_desc="Reload macro definitions from macro.chatdsl or the specified file. Macros are shortcuts for frequently used text.",
            examples=["/reloadmacros", "/reloadmacros custom_macros.chatdsl"],
            see_also=["/macro"]
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
        
        # Database commands
        db_commands = [
            ("setdb", "Create or select a TinyDB database", "/setdb <dbname>", "Use 'Null' to deactivate", ["/setdb mydb", "/setdb Null"]),
            ("dblist", "List all TinyDB databases", "/dblist", "", []),
            ("searchdb", "Search all docs in current database", "/searchdb <query>", "", ["/searchdb python"]),
            ("dblog", "Log last completion to database", "/dblog", "", []),
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
            long_desc="Set a script variable to a string value. This is for text only, not image data.",
            examples=["/setvar name John", "/setvar count 42"]
        ))
        
        self.register_command(CommandHelp(
            name="/mem",
            category="debug",
            short_desc="Show size of buffers and variables",
            usage="/mem",
            long_desc="Display memory usage information including buffer sizes, LAST_RESPONSE, and script variable counts.",
            examples=["/mem"]
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
            long_desc="Enable safe mode (default). In safe mode, dangerous shell commands (like rm -rf, sudo, etc.) are blocked or require explicit user confirmation.",
            examples=["/run_safe"],
            see_also=["/run_unsafe", "/run"]
        ))
        
        self.register_command(CommandHelp(
            name="/run_unsafe",
            category="scripting",
            short_desc="Disable safe mode for /run commands",
            usage="/run_unsafe",
            long_desc="Disable safe mode. Dangerous shell commands will be allowed without confirmation. Use with caution!",
            examples=["/run_unsafe"],
            see_also=["/run_safe", "/run"]
        ))
        
        self.register_command(CommandHelp(
            name="/tool",
            category="scripting",
            short_desc="Manage tool mode and dispatch tool invocations",
            usage="/tool [on|off|<json_file.json>|<json_invocation>]",
            long_desc="Manage tool mode for LLM tool calling. When tool mode is on, tool definitions from tools_config.toml are available for the LLM to use.\n\nSubcommands:\n  /tool on - Enable tool mode, inject tool definitions into context\n  /tool off - Disable tool mode\n  /tool <file.json> - Dispatch tool invocation from JSON file\n  /tool [json] - Dispatch a tool invocation directly (uses LAST_COMPLETION if no argument provided)",
            examples=["/tool on", "/tool off", "/tool", "/tool find1.json", "/tool {\"tool\": \"list_directory\", \"arguments\": {\"path\": \".\"}}"],
            see_also=["/run"]
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
    
    def format_command_list(self, commands: List[CommandHelp]) -> str:
        """Format a list of commands for display."""
        if not commands:
            return "No commands found."
        
        lines = []
        # Group by category for better organization
        categorized: Dict[str, List[CommandHelp]] = {}
        for cmd in commands:
            if cmd.category not in categorized:
                categorized[cmd.category] = []
            categorized[cmd.category].append(cmd)
        
        for category in sorted(categorized.keys()):
            category_commands = sorted(categorized[category], key=lambda c: c.name)
            if category:
                lines.append(f"\n{category.upper()}:")
            for cmd in category_commands:
                lines.append(f"  {cmd.name} - {cmd.short_desc}")
        
        return "\n".join(lines)
    
    def format_command_detail(self, cmd_help: CommandHelp) -> str:
        """Format detailed help for a single command."""
        lines = []
        lines.append(f"\n{cmd_help.name}")
        lines.append("=" * len(cmd_help.name))
        
        if cmd_help.category:
            lines.append(f"Category: {cmd_help.category}")
        
        if cmd_help.usage:
            lines.append(f"Usage: {cmd_help.usage}")
        
        if cmd_help.short_desc:
            lines.append(f"\n{cmd_help.short_desc}")
        
        if cmd_help.long_desc:
            lines.append(f"\n{cmd_help.long_desc}")
        
        if cmd_help.parameters:
            lines.append(f"\nParameters:")
            for param, desc in cmd_help.parameters.items():
                lines.append(f"  {param} - {desc}")
        
        if cmd_help.examples:
            lines.append(f"\nExamples:")
            for example in cmd_help.examples:
                lines.append(f"  {example}")
        
        if cmd_help.aliases:
            lines.append(f"\nAliases: {', '.join(cmd_help.aliases)}")
        
        if cmd_help.see_also:
            lines.append(f"\nSee also: {', '.join(cmd_help.see_also)}")
        
        return "\n".join(lines)
    
    def get_help_text(self, query: Optional[str] = None) -> str:
        """
        Get help text based on query.
        
        Args:
            query: None for full help, a command name for specific help, or a keyword for filtering
        
        Returns:
            Formatted help text
        """
        if query is None:
            # Full help - return all commands
            return self.format_command_list(self.get_all_commands())
        
        # If query starts with '/', treat it as a specific command request
        if query.startswith('/'):
            if query in self.commands:
                return self.format_command_detail(self.commands[query])
            else:
                # Try without leading slash
                query_without_slash = query.lstrip('/')
                if f"/{query_without_slash}" in self.commands:
                    return self.format_command_detail(self.commands[f"/{query_without_slash}"])
                else:
                    # Filter by keyword if not found as command
                    filtered = self.filter_commands(query)
                    if not filtered:
                        return f"No commands found matching '{query}'. Try /help for all commands."
                    return self.format_command_list(filtered)
        
        # Query doesn't start with '/', treat as keyword filter
        filtered = self.filter_commands(query)
        if not filtered:
            return f"No commands found matching '{query}'. Try /help for all commands."
        
        return self.format_command_list(filtered)


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
