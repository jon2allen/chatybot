# Chatybot Command Architecture & Modularization Blueprint

## 1. Executive Summary & Problem Context

`ChatybotApp` in [`src/chatybot/chatybot_app.py`](file:///Users/jon2allen/github/chatybot/src/chatybot/chatybot_app.py) currently operates as a monolithic "God Object" spanning **8,250 lines of code**. At its center is `handle_escape_command()` (starting at line 4190), an `if/elif` chain spanning over **3,700 lines** that dispatches more than 60 slash commands (`/model`, `/imagine`, `/session`, `/filebank*`, `/tools`, `/proc`, etc.).

### Critical Pain Points in the Current Architecture
1. **High Cognitive & Maintenance Load:** Finding, updating, or debugging any single command requires navigating thousands of lines of unrelated logic.
2. **Fragile Control Signal (`EXECUTE_PROMPT` Sentinel):** `handle_escape_command()` returns `Union[bool, str]` where `"EXECUTE_PROMPT"` is returned as a raw string sentinel to signal the caller to run the prompt. Any caller using standard boolean checks (`if result:`) suffers subtle control-flow bugs.
3. **Scattered Metadata:** Help strings and syntax descriptions live separately in the 1,002-line [`chaty_help.py`](file:///Users/jon2allen/github/chatybot/src/chatybot/chaty_help.py), leading to documentation drift when command arguments or behavior change.
4. **Difficult Unit Testing:** Testing a single command like `/seed` or `/imagesize` requires instantiating the entire interactive `ChatybotApp` runtime with all its dependencies.
5. **No Easy Extensibility:** Adding a new command requires touching `chatybot_app.py`, `chaty_help.py`, and tokenizers/parsers in multiple places.

---

## 2. Comprehensive Modularization Options

Below are the six architectural strategies evaluated for refactoring Chatybot's command structure, ordered from least to most invasive.

---

### Option 1: In-Place Dispatch Table (Minimal Refactor)

Replace the 3,700-line `if/elif` chain with an internal mapping dictionary inside `ChatybotApp`, mapping command strings directly to methods on `self`.

#### Implementation Pattern
```python
# src/chatybot/chatybot_app.py
class ChatybotApp:
    def __init__(self, ...):
        ...
        self._command_handlers: dict[str, Callable] = {
            "/model": self.cmd_model,
            "/imagine": self.cmd_imagine,
            "/session": self.cmd_session,
            # ... 60+ entries
        }

    async def handle_escape_command(self, command: str) -> Union[bool, str]:
        parts = command.split(maxsplit=2)
        cmd_name = self.i18n.resolve_command(parts[0].lower())
        handler = self._command_handlers.get(cmd_name)
        if not handler:
            return False
        return await handler(parts)
```

* **Pros:** Minimal diff; lowest risk; preserves existing behavior completely; quick to implement mechanically.
* **Cons:** All 60+ command methods remain inside `chatybot_app.py`, keeping the 8,000+ line monolith largely intact; does not fix doc drift or test isolation.
* **Estimated Effort:** ~1 day.

---

### Option 2: Domain-Grouped Handler Modules

Extract commands out of `chatybot_app.py` into dedicated modules grouped by functional domain. Each module exports handler functions and a `register(registry, app)` function.

#### Directory Layout
```text
src/chatybot/commands/
├── __init__.py
├── image.py          # /imagine, /saveimage, /imagesize, /imagequality, /listimages...
├── model_params.py   # /model, /temp, /top_p, /thinking, /reasoning, /sysprompt...
├── session.py        # /session, /save, /history, /turns...
├── buffer.py         # /filebank*, /imagebank*, /vars, /loadvar, /savevar...
├── tools.py          # /tools, /mcp, /rerank, /run...
└── debug.py          # /trace, /debug, /dump, /echo, /mem...
```

#### Implementation Pattern
```python
# src/chatybot/commands/image.py
async def cmd_imagine(app: "ChatybotApp", parts: list[str]) -> Union[bool, str]:
    # Image generation logic
    ...

def register(registry: dict, app: "ChatybotApp"):
    registry["/imagine"] = lambda parts: cmd_imagine(app, parts)
```

* **Pros:** Drastically reduces `chatybot_app.py` size; files are logically organized by feature area; easy to locate code.
* **Cons:** Still tightly coupled if passing full `app` reference; requires manual registration boilerplate per module; doesn't solve documentation synchronization.
* **Estimated Effort:** ~3–4 days.

---

### Option 3: Class-Based Command Pattern (`BaseCommand` / `Protocol`)

Every command is modeled as a standalone class implementing an abstract interface. Metadata (help text, aliases, argument specs) and execution lifecycle methods are co-located in the class.

#### Implementation Pattern
```python
from abc import ABC, abstractmethod
from typing import Optional
from dataclasses import dataclass
from enum import Enum

class CommandAction(Enum):
    HANDLED = "handled"
    PASSTHROUGH = "passthrough"
    EXECUTE_PROMPT = "execute_prompt"
    EXIT = "exit"

@dataclass
class CommandResult:
    action: CommandAction
    message: Optional[str] = None
    prompt: Optional[str] = None

class BaseCommand(ABC):
    name: str
    aliases: list[str] = []
    description: str = ""
    arg_spec: str = ""

    @abstractmethod
    async def execute(self, ctx: "CommandContext", args: list[str]) -> CommandResult:
        pass
```

* **Pros:** Strong typing; completely eliminates the `EXECUTE_PROMPT` string sentinel bug; self-documenting; enables pre/post execution hooks and arg validation; high testability.
* **Cons:** Higher boilerplate for simple 2-line commands (e.g. `/seed 42`); 60+ individual classes can feel verbose.
* **Estimated Effort:** ~5–7 days.

---

### Option 4: Decorator-Based Registry (`@command`)

Commands are defined as standalone async functions registered via an expressive `@command` decorator. Handlers live in domain modules, and registration happens automatically or during module loading.

#### Implementation Pattern
```python
# src/chatybot/commands/model.py
from chatybot.commands.registry import command, CommandResult

@command("/model", aliases=["/m"], help="Switch or view active chat model", args="[alias]")
async def cmd_model(ctx: "CommandContext", args: list[str]) -> CommandResult:
    if not args:
        ctx.ui.print_info(f"Current model: {ctx.config.current_model}")
        return CommandResult.handled()
    ctx.set_model(args[0])
    return CommandResult.handled()
```

* **Pros:** Lowest boilerplate; Pythonic; co-locates help and aliases with the implementation; easy to read and maintain; clean O(1) registry dispatch.
* **Cons:** Requires clear module-loading semantics; global registry state needs careful design for multi-instance testing.
* **Estimated Effort:** ~3–4 days.

---

### Option 5: Structured Argument Parsing Pipeline (`argparse` / Subcommand Trees)

Treat slash commands as full CLI subcommands with formalized argument parsers (using `argparse` or custom sub-parsers).

#### Implementation Pattern
```python
class ImagineCommand:
    name = "/imagine"
    def __init__(self):
        self.parser = argparse.ArgumentParser(prog="/imagine", exit_on_error=False)
        self.parser.add_argument("--steps", type=int, default=20)
        self.parser.add_argument("--size", default="1024x1024")
        self.parser.add_argument("prompt", nargs="+")

    async def execute(self, ctx: "CommandContext", raw_args: str) -> CommandResult:
        parsed = self.parser.parse_args(shlex.split(raw_args))
        # Typed, validated fields: parsed.steps, parsed.size, parsed.prompt
```

* **Pros:** Standardizes flag parsing (`--flag`, `-f`); auto-validates integer/string/path arguments; auto-generates detailed syntax help and error messages.
* **Cons:** Slower migration due to custom ChatDSL string conventions; high overhead for commands without flags.
* **Estimated Effort:** ~5–8 days.

---

### Option 6: Plugin / Entry-Point / Event Bus System

Decouple commands entirely into plugins discovered via Python package metadata (`importlib.metadata.entry_points`) or an async Event Bus. Commands can be installed as independent packages (`pip install chatybot-plugin-voice`).

#### Implementation Pattern
```python
# Core discovers external plugins
def load_installed_plugins(app):
    for ep in importlib.metadata.entry_points(group="chatybot.commands"):
        plugin = ep.load()
        plugin.register(app.command_registry)
```

* **Pros:** Maximum extensibility; user-created commands; strict decoupling.
* **Cons:** Significant architectural overhead; requires a frozen, public API (`CommandContext` stability); premature optimization if third-party plugins are not an immediate requirement.
* **Estimated Effort:** ~2–3 weeks.

---

## 3. Comparative Decision Matrix

| Dimension | Opt 1: Dispatch Table | Opt 2: Domain Modules | Opt 3: Command Classes | Opt 4: Decorator Registry | Opt 5: Argparse Trees | Opt 6: Plugin System |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Monolith Reduction** | ❌ None | ✅ High | ✅ High | ✅ High | ✅ High | ✅ Very High |
| **Boilerplate Level** | Low | Medium | High | **Minimal** | High | High |
| **Fixes `EXECUTE_PROMPT` Bug** | ❌ No | ⚠️ Partial | ✅ **Yes** | ✅ **Yes** | ✅ **Yes** | ✅ **Yes** |
| **Co-located Documentation** | ❌ No | ❌ No | ✅ Yes | ✅ **Yes** | ✅ Yes | ✅ Yes |
| **Testability (Mocking Context)** | ❌ Hard | ⚠️ Medium | ✅ **Easy** | ✅ **Easy** | ✅ **Easy** | ✅ Very Easy |
| **Implementation Risk / Effort** | 1 Day | 3–4 Days | 5–7 Days | **3–4 Days** | 5–8 Days | 2–3 Weeks |

---

## 4. Final Recommendation: The "Sweet Spot" Architecture

The optimal architecture is a **Hybrid of Option 2 (Domain Modules), Option 4 (Decorator Registry), and Option 3 (Typed Command Results with a Focused Context).**

### Why this combination is the Sweet Spot:
1. **Zero Boilerplate:** Writing a new command is as simple as adding `@command(...)` above an `async def`.
2. **Eliminates `EXECUTE_PROMPT` Sentinel Bug:** All handlers return a strongly-typed `CommandResult`.
3. **Single Source of Truth:** Help text, aliases, and argument specifications live with the code, allowing [`chaty_help.py`](file:///Users/jon2allen/github/chatybot/src/chatybot/chaty_help.py) to be deprecated or auto-generated.
4. **Focused `CommandContext`:** Handlers receive a clean interface exposing only what they need (session, buffers, config, UI output) rather than the entire 8,250-line `ChatybotApp`.

---

## 5. Detailed Implementation Blueprint for the Sweet Spot

### 5.1 Target Directory Structure
```text
src/chatybot/
├── chatybot_app.py             # Shrinks from 8,250 -> ~1,500 lines (core loop & glue)
└── commands/
    ├── __init__.py             # Auto-imports all domain modules to trigger registration
    ├── registry.py             # CommandRegistry, @command decorator, CommandResult
    ├── context.py              # CommandContext protocol / dataclass
    │
    ├── models.py               # /model, /vendor, /temp, /top_p, /thinking, /listmodels...
    ├── session.py              # /session, /save, /history, /turns, /export...
    ├── image.py                # /imagine, /saveimage, /imagesize, /imagequality...
    ├── buffer.py               # /filebank*, /imagebank*, /vars, /loadvar, /set...
    ├── tools.py                # /tools, /mcp, /rerank, /run, /run_safe...
    ├── db.py                   # /setdb, /dblist, /searchdb, /dblog...
    ├── proc_macros.py          # /proc, /reloadmacros, /calc, /source, /script...
    └── debug.py                # /trace, /debug, /dump, /echo, /mem...
```

---

### 5.2 Core Types: `context.py` & `registry.py`

#### A. `src/chatybot/commands/context.py`
```python
from dataclasses import dataclass
from typing import Any, Protocol, Optional
from chatybot.buffer_manager import BufferManager
from chatybot.config_manager import ConfigManager
from chatybot.session_interface import BaseSessionStore

class UIProtocol(Protocol):
    def print_info(self, msg: str) -> None: ...
    def print_error(self, msg: str) -> None: ...
    def print_warning(self, msg: str) -> None: ...
    def print_success(self, msg: str) -> None: ...

@dataclass
class CommandContext:
    """Clean interface provided to all command handlers."""
    config_manager: ConfigManager
    buffer_manager: BufferManager
    session_store: Optional[BaseSessionStore]
    ui: UIProtocol
    app: Any  # Reference to app for complex operations during phased migration
    
    @property
    def config(self):
        return self.config_manager.config
```

#### B. `src/chatybot/commands/registry.py`
```python
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Awaitable, Optional, Dict, List, Set

class CommandAction(Enum):
    HANDLED = "handled"
    EXECUTE_PROMPT = "execute_prompt"
    EXIT = "exit"
    ERROR = "error"

@dataclass
class CommandResult:
    action: CommandAction
    message: Optional[str] = None
    prompt_to_execute: Optional[str] = None

    @classmethod
    def ok(cls, msg: Optional[str] = None) -> "CommandResult":
        return cls(action=CommandAction.HANDLED, message=msg)

    @classmethod
    def execute_prompt(cls, prompt: str) -> "CommandResult":
        return cls(action=CommandAction.EXECUTE_PROMPT, prompt_to_execute=prompt)

    @classmethod
    def error(cls, msg: Optional[str] = None) -> "CommandResult":
        return cls(action=CommandAction.ERROR, message=msg)

    @classmethod
    def exit(cls) -> "CommandResult":
        return cls(action=CommandAction.EXIT)


@dataclass
class CommandSpec:
    name: str
    handler: Callable[["CommandContext", List[str]], Awaitable[CommandResult]]
    help: str = ""
    args: str = ""
    category: str = "general"
    aliases: List[str] = field(default_factory=list)


class CommandRegistry:
    def __init__(self):
        self._commands: Dict[str, CommandSpec] = {}
        self._aliases: Dict[str, str] = {}

    def register(
        self,
        name: str,
        handler: Callable,
        help: str = "",
        args: str = "",
        category: str = "general",
        aliases: Optional[List[str]] = None,
    ):
        aliases = aliases or []
        spec = CommandSpec(
            name=name,
            handler=handler,
            help=help,
            args=args,
            category=category,
            aliases=aliases,
        )
        self._commands[name] = spec
        for alias in aliases:
            self._aliases[alias] = name

    async def dispatch(self, ctx: "CommandContext", raw_command: str) -> CommandResult:
        parts = raw_command.strip().split()
        if not parts:
            return CommandResult.ok()

        cmd_name = parts[0].lower()
        args = parts[1:]

        # Resolve alias if present
        primary_name = self._aliases.get(cmd_name, cmd_name)
        spec = self._commands.get(primary_name)

        if not spec:
            ctx.ui.print_error(f"Unknown command: {cmd_name}. Type /help for available commands.")
            return CommandResult.error(f"Unknown command {cmd_name}")

        try:
            return await spec.handler(ctx, args)
        except Exception as e:
            ctx.ui.print_error(f"Error executing {cmd_name}: {str(e)}")
            return CommandResult.error(str(e))

    def get_all_specs(self) -> List[CommandSpec]:
        return list(self._commands.values())


# Global default registry instance
registry = CommandRegistry()

def command(
    name: str,
    *,
    help: str = "",
    args: str = "",
    category: str = "general",
    aliases: Optional[List[str]] = None,
):
    """Decorator to register a command handler."""
    def decorator(fn: Callable):
        registry.register(
            name=name,
            handler=fn,
            help=help,
            args=args,
            category=category,
            aliases=aliases,
        )
        return fn
    return decorator
```

---

### 5.3 Domain Module Examples

#### Example 1: `src/chatybot/commands/models.py`
```python
from chatybot.commands.registry import command, CommandResult
from chatybot.commands.context import CommandContext

@command("/model", aliases=["/m"], help="Switch active model or list presets", args="[alias]", category="models")
async def cmd_model(ctx: CommandContext, args: list[str]) -> CommandResult:
    if not args:
        ctx.ui.print_info(f"Active model: {ctx.config.model_name}")
        return CommandResult.ok()

    target = args[0]
    # Model switching logic
    ctx.ui.print_success(f"Switched model to {target}")
    return CommandResult.ok()

@command("/temp", help="Set generation temperature", args="<0.0 - 2.0>", category="models")
async def cmd_temp(ctx: CommandContext, args: list[str]) -> CommandResult:
    if not args:
        ctx.ui.print_info(f"Current temperature: {ctx.config.temperature}")
        return CommandResult.ok()
    try:
        val = float(args[0])
        ctx.config.temperature = val
        ctx.ui.print_success(f"Temperature set to {val}")
        return CommandResult.ok()
    except ValueError:
        return CommandResult.error("Temperature must be a valid float.")
```

#### Example 2: `src/chatybot/commands/session.py` (Handling Subcommands)
```python
from chatybot.commands.registry import command, CommandResult
from chatybot.commands.context import CommandContext

@command("/session", help="Session management commands", args="<list|new|export|delete> [name]", category="session")
async def cmd_session(ctx: CommandContext, args: list[str]) -> CommandResult:
    sub = args[0].lower() if args else "list"
    sub_args = args[1:]

    subcommands = {
        "list": _sub_list,
        "new": _sub_new,
        "export": _sub_export,
    }

    handler = subcommands.get(sub)
    if not handler:
        return CommandResult.error(f"Unknown session action: {sub}. Valid: {', '.join(subcommands.keys())}")

    return await handler(ctx, sub_args)

async def _sub_list(ctx: CommandContext, args: list[str]) -> CommandResult:
    # List sessions from session store
    ctx.ui.print_info("Active sessions:")
    return CommandResult.ok()

async def _sub_new(ctx: CommandContext, args: list[str]) -> CommandResult:
    name = args[0] if args else "default"
    ctx.ui.print_success(f"Created session: {name}")
    return CommandResult.ok()

async def _sub_export(ctx: CommandContext, args: list[str]) -> CommandResult:
    return CommandResult.ok("Session exported.")
```

---

### 5.4 How Easy is it to Add New Features?

| Operation | Action Required |
| :--- | :--- |
| **Add a standalone command** | Open the matching `commands/*.py` file, add a 5-line `@command` decorated function. Done. |
| **Add a subcommand** (`/db query`) | Add a function in `commands/db.py` inside the subcommand router map. Done. |
| **Add an alias** (`/g` for `/generate`) | Add `aliases=["/g"]` in the `@command` decorator. Done. |
| **Update documentation** | Edit `help="..."` and `args="..."` in the decorator. Documentation updates automatically. |
| **Write a unit test** | Call `await cmd_model(mock_context, ["gpt-4o"])` with standard pytest assertions. |

---

## 6. Phased Migration Plan

To safely refactor without breaking existing workflows or freezing development:

### Phase 1: Core Foundation & Bug Patches
1. Fix known bugs: Add missing `import shutil` and fix `process_macro_line` in [`chatybot_app.py`](file:///Users/jon2allen/github/chatybot/src/chatybot/chatybot_app.py).
2. Create `src/chatybot/commands/registry.py` and `src/chatybot/commands/context.py`.
3. Wire `CommandRegistry.dispatch()` into `ChatybotApp.handle_escape_command()` as a fallback delegator.

### Phase 2: Migrate High-Volume Leaf Domains
1. Migrate `commands/image.py` (lines 4216–4776, ~550 lines extracted).
2. Migrate `commands/models.py` (~400 lines extracted).
3. Migrate `commands/buffer.py` (/filebank, /imagebank, /vars).

### Phase 3: Migrate Complex State Domains
1. Migrate `commands/session.py` (pluggable session integration).
2. Migrate `commands/tools.py` and `commands/proc_macros.py`.

### Phase 4: Deprecate Monolithic Handler & Unified Help
1. Delete the legacy 3,700-line `elif` chain.
2. Auto-generate `/help` output directly from `registry.get_all_specs()`, deprecating manual dictionaries in `chaty_help.py`.
3. Sync valid command tokens in `chatdsl_parse.py` directly from `registry._commands.keys()`.
