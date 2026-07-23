# Profile Manager System Design

## Overview

The Profile Manager provides lifecycle management for ChatDSL profile scripts in chatybot. A profile is a plain `.chatdsl` file — no special syntax, no YAML. An optional pair of comment annotations at the top supply display metadata (`name` and `description`). All session configuration (model, tools, tracing, reasoning, temperature) is expressed using the **existing ChatDSL command set** that already works in any script.

This design builds on the **already-implemented** foundation:
- `--profile <path>` CLI argument sets `app.profile_to_load`
- `default_profile` key read from `[config]` in `tools_config.toml`
- `execute_script()` runs the `.chatdsl` body at startup

The goal is to add profile discovery, lifecycle management (create/edit/clone/delete/export/import), three curated preset templates, and a curses TUI editor — mirroring the existing `config_tui.py` pattern.

---

## Current State vs. Planned

| Capability | Status |
|---|---|
| `--profile <path>` CLI flag | ✅ Implemented (`chatybot_app.py:5158`) |
| `default_profile` from `tools_config.toml` | ✅ Implemented (`chatybot_app.py:213`) |
| Execute profile `.chatdsl` at startup | ✅ Implemented (`chatybot_app.py:5064`) |
| Profile directory & template presets | ❌ Not yet |
| `/profile` in-REPL subcommands | ❌ Not yet |
| `--profile-edit`, `--profile-list` CLI flags | ❌ Not yet |
| `profile_manager.py` module | ❌ Not yet |
| Curses TUI profile editor | ❌ Not yet |

> [!NOTE]
> `execute_script()` requires **no changes**. Profile files are valid `.chatdsl` scripts as-is. The `profile_manager.py` module only needs to scan the first few comment lines to extract display metadata.

---

## Profile File Format

A profile is a standard `.chatdsl` file. Two optional annotation comments at the top provide display metadata for `/profile list`. Everything else is ordinary ChatDSL.

```bash
# @name: Development Profile
# @description: Optimized for coding and debugging

/model devstral_1
/tool auto on
/tool on
/reasoning on
/effort medium
/trace tps on
/tool max_turns 25
```

### Annotation Comment Convention

| Annotation | Purpose | Falls back to |
|---|---|---|
| `# @name: <text>` | Display name in profile list | filename without `.chatdsl` |
| `# @description: <text>` | One-line description | empty string |

Rules:
- Annotations must appear **before any non-comment line**
- Only `@name` and `@description` are recognized; any other `# @...` comments are ignored
- If annotations are absent the file is still a valid profile — name defaults to the filename stem

### ChatDSL Settings Reference

All session settings are expressed with **existing commands**:

| Setting | ChatDSL command |
|---|---|
| Active model | `/model <alias>` |
| Tools auto mode | `/tool auto <on|off>` |
| Tools on/off | `/tool <on|off>` |
| Disable tool | `/tool disable <tool_name>` |
| TPS tracing | `/trace tps <on|off>` |
| Reasoning on/off | `/reasoning <on|off>` |
| Reasoning effort | `/effort <low|medium|high>` |
| Show/hide thinking | `/thinking <on|off>` |
| Temperature | `/temp <float>` |
| Max tool calls | `/tool max_turns <int>` |

---

## File Structure

```
~/.config/chatybot/
├── chat_config.toml       # Model definitions (existing)
├── tools_config.toml      # Tool & config settings (existing)
└── profiles/              # Profile directory (new)
    ├── coding.chatdsl     # Preset: Development
    ├── general.chatdsl    # Preset: General Assistance
    ├── explorer.chatdsl   # Preset: Read-only Explorer
    └── *.chatdsl          # User-created profiles
```

### `tools_config.toml` additions

```toml
[config]
# ... existing keys ...
default_profile = ""         # e.g. "~/.config/chatybot/profiles/coding.chatdsl"
profile_dir = "~/.config/chatybot/profiles"
enable_profile_edit = true
```

---

## Preset Templates

### 1. `coding.chatdsl` — Development Profile

```bash
# @name: Development Profile
# @description: Optimized for coding, debugging, and technical assistance

/model devstral_1
/tool auto on
/tool on
/reasoning on
/effort medium
/trace tps on
/tool max_turns 75
```

### 2. `general.chatdsl` — General Assistance

```bash
# @name: General Assistance Profile
# @description: Balanced assistance with restricted tool access

/model mistral_1
/tool off
/reasoning off
```

### 3. `explorer.chatdsl` — Read-only Explorer

```bash
# @name: Explorer Mode
# @description: Safe read-only exploration for browsing and querying

/model mistral_1
/tool disable run_command
/tool disable run_safe
/tool disable run_unsafe
/tool disable setdb
/reasoning off
```

> [!IMPORTANT]
> Model aliases (`devstral_1`, `mistral_1`) must exist in `chat_config.toml`. If the model alias is missing, the existing `/model` command handler will print a warning — no special-case code needed.
> The `/tool max_turns <int>` command does not currently exist in `chatybot_app.py`, so we will need to add a quick handler for it under the `/tool` command dispatch.

---

## CLI Interface

### New Argument Flags

```python
parser.add_argument(
    "--profile-edit",
    metavar="NAME",
    nargs="?",
    const="",           # No name = create new
    help="Open TUI profile editor. Optionally specify profile name to edit/create."
)
parser.add_argument(
    "--profile-list",
    action="store_true",
    help="List all available profiles in the profile directory"
)
```

### `--profile-list` Output Example

```
Available Profiles  (~/.config/chatybot/profiles)
──────────────────────────────────────────────────
  coding.chatdsl    Development Profile           [auto tools, TPS, reasoning]
  general.chatdsl   General Assistance Profile    [no tools, no trace]
  explorer.chatdsl  Explorer Mode                 [read-only tools]
  my_work.chatdsl   my_work                       [auto tools]

Default: coding.chatdsl
```

### `--profile-edit` Flow

```
chatybot --profile-edit              # Open TUI, create new profile
chatybot --profile-edit coding       # Open TUI, edit existing "coding" profile
chatybot --profile-edit my_profile   # Open TUI, create/edit "my_profile.chatdsl"
```

---

## In-REPL `/profile` Subcommands

Handled inside `execute_script_command()` as a new escape command. `profile` is added to `TParser.VALID_ESCAPE_COMMANDS`.

| Command | Description |
|---|---|
| `/profile list` | List profiles (same output as `--profile-list`) |
| `/profile use <name>` | Load and re-execute a profile in the current session |
| `/profile clone <src> <dst>` | Copy a profile with a new name |
| `/profile delete <name>` | Remove a profile file (prompts for confirmation) |
| `/profile export <name> <path>` | Copy profile to an arbitrary path |
| `/profile import <path>` | Copy a `.chatdsl` file into the profiles directory |
| `/profile edit [name]` | Open TUI editor |
| `/profile show [name]` | Print the raw content of a profile |

> [!NOTE]
> `/profile use <name>` passes the resolved path to the existing `execute_script()` — no new execution logic required.

---

## Implementation Modules

### 1. `profile_manager.py` (New — `src/chatybot/`)

```python
import os, re, shutil
from dataclasses import dataclass
from typing import Optional, List


@dataclass
class ProfileMeta:
    """Lightweight metadata parsed from annotation comments."""
    name: str
    description: str
    source_path: str


class ProfileManager:
    """Manages discovery, CRUD, and preset seeding for chatybot profiles."""

    def __init__(self, profile_dir: str = "~/.config/chatybot/profiles"):
        self.profile_dir = os.path.expanduser(profile_dir)

    def ensure_dir(self) -> None:
        os.makedirs(self.profile_dir, exist_ok=True)

    def seed_presets(self) -> None:
        """Write bundled preset files if they don't already exist."""
        self.ensure_dir()
        preset_src = os.path.join(os.path.dirname(__file__), "profiles")
        if os.path.isdir(preset_src):
            for fname in os.listdir(preset_src):
                if fname.endswith(".chatdsl"):
                    dst = os.path.join(self.profile_dir, fname)
                    if not os.path.exists(dst):
                        shutil.copy2(os.path.join(preset_src, fname), dst)

    def list_profiles(self) -> List[str]:
        """Return sorted list of .chatdsl filenames in profile_dir."""
        if not os.path.isdir(self.profile_dir):
            return []
        return sorted(f for f in os.listdir(self.profile_dir)
                      if f.endswith(".chatdsl"))

    def read_meta(self, name_or_path: str) -> ProfileMeta:
        """Read display metadata from annotation comments."""
        path = self._resolve_path(name_or_path)
        stem = os.path.splitext(os.path.basename(path))[0]
        meta_name = stem
        meta_desc = ""
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                if not line.startswith("#"):
                    break   # Stop at first non-comment line
                m = re.match(r"#\s*@name:\s*(.+)", line)
                if m:
                    meta_name = m.group(1).strip()
                    continue
                m = re.match(r"#\s*@description:\s*(.+)", line)
                if m:
                    meta_desc = m.group(1).strip()
        return ProfileMeta(name=meta_name, description=meta_desc, source_path=path)

    def clone_profile(self, src_name: str, dst_name: str) -> str:
        """Clone a profile under a new name."""
        src = self._resolve_path(src_name)
        fname = dst_name if dst_name.endswith(".chatdsl") else dst_name + ".chatdsl"
        dst = os.path.join(self.profile_dir, fname)
        shutil.copy2(src, dst)
        return dst

    def delete_profile(self, name: str) -> None:
        os.remove(self._resolve_path(name))

    def export_profile(self, name: str, dest_path: str) -> None:
        shutil.copy2(self._resolve_path(name), os.path.expanduser(dest_path))

    def import_profile(self, src_path: str) -> str:
        self.ensure_dir()
        fname = os.path.basename(src_path)
        if not fname.endswith(".chatdsl"):
            raise ValueError("Import source must be a .chatdsl file")
        dst = os.path.join(self.profile_dir, fname)
        shutil.copy2(os.path.expanduser(src_path), dst)
        return dst

    def _resolve_path(self, name_or_path: str) -> str:
        if os.path.isabs(name_or_path) or name_or_path.startswith("~"):
            p = os.path.expanduser(name_or_path)
        else:
            fname = name_or_path if name_or_path.endswith(".chatdsl") \
                    else name_or_path + ".chatdsl"
            p = os.path.join(self.profile_dir, fname)
        if not os.path.exists(p):
            raise FileNotFoundError(f"Profile not found: {p}")
        return p
```

---

### 2. `/profile` REPL Command Handler (`chatybot_app.py`)

```python
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
        path = pm._resolve_path(args[1])
        await self.execute_script(path)
        print(f"[profile] Applied: {args[1]}")

    elif sub == "clone" and len(args) >= 3:
        dst = pm.clone_profile(args[1], args[2])
        print(f"[profile] Cloned to {dst}")

    elif sub == "delete" and len(args) >= 2:
        confirm = input(f"Delete profile '{args[1]}'? [y/N] ").strip().lower()
        if confirm == "y":
            pm.delete_profile(args[1])
            print(f"[profile] Deleted: {args[1]}")

    elif sub == "export" and len(args) >= 3:
        pm.export_profile(args[1], args[2])
        print(f"[profile] Exported {args[1]} to {args[2]}")

    elif sub == "import" and len(args) >= 2:
        dst = pm.import_profile(args[1])
        print(f"[profile] Imported to {dst}")

    elif sub == "show" and len(args) >= 2:
        with open(pm._resolve_path(args[1])) as f:
            print(f.read())

    elif sub == "edit":
        name = args[1] if len(args) >= 2 else ""
        from .profile_editor import run_profile_editor
        run_profile_editor(name, pm, self.config_manager)

    else:
        print("Usage: /profile [list|use|clone|delete|export|import|show|edit] [args...]")
```

Wire into `execute_script_command()`:

```python
elif cmd_name == "profile":
    await self.handle_profile_command(args)
    return True
```

---

### 3. `profile_editor.py` — Curses TUI (New)

Pattern mirrors `config_tui.py`. Single `run_profile_editor(name, pm, config_manager)` entry point.

#### Screen Layout

```
┌─────────────────────────────────────────────────────────────────┐
│  CHATYBOT PROFILE EDITOR                         [Ctrl+S: Save] │
├─────────────────────────────────────────────────────────────────┤
│  File name:    [coding.chatdsl                 ]                │
│  @name:        [Development Profile            ]                │
│  @description: [Optimized for coding           ]                │
├──────────────────────────── PRESET ─────────────────────────────┤
│  [ Coding ]    [ General ]    [ Explorer ]    [ Blank ]         │
├──────────────────────────── MODEL ──────────────────────────────┤
│  /model        [devstral_1          ▼]                          │
├─────────────────────────── TOOLS ───────────────────────────────┤
│  tool:         ( ) Off  (*) Auto  ( ) On  ( ) Read-only         │
├──────────────────────────── TRACE ──────────────────────────────┤
│  [x] TPS   [ ] Agentic Loop   [ ] Raw Payload   [ ] Response    │
├─────────────────────────── REASONING ───────────────────────────┤
│  [x] Reasoning   [ ] Show Thinking                              │
│  Effort:  (*) Auto  ( ) Low  ( ) Medium  ( ) High               │
├─────────────────────────── ADVANCED ────────────────────────────┤
│  /temp:  [0.7   ]   max_turns: [25  ]                           │
├─────────────────────────── PREVIEW ─────────────────────────────┤
│  # @name: Development Profile                                   │
│  # @description: Optimized for coding                           │
│                                                                 │
│  /model devstral_1                                              │
│  /tool auto on                                                  │
│  ...                                                            │
├─────────────────────────────────────────────────────────────────┤
│  [Save]   [Apply & Exit]   [Reset]   [Cancel]                   │
└─────────────────────────────────────────────────────────────────┘
```

#### Key Bindings

| Key | Action |
|---|---|
| `↑` / `↓` | Move between fields |
| `Tab` / `Shift+Tab` | Jump to next/previous section |
| `Space` / `Enter` | Toggle checkbox / activate button |
| `Escape` | Cancel and exit |
| `Ctrl+S` | Save profile |
| `Ctrl+A` | Apply to current session (REPL-launched only) |
| `F1` | Load preset |

#### Model Dropdown

Populated from `config_manager.config["models"].keys()` — same live source as `config_tui.py`, no stale aliases.

#### Generated Output

The TUI writes a plain `.chatdsl` file — no special format:

```bash
# @name: Development Profile
# @description: Optimized for coding

/model devstral_1
/tool auto on
/tool on
/reasoning on
/effort medium
/trace tps on
/tool max_turns 25
```

---

### 4. Preset Files — `src/chatybot/profiles/`

Preset `.chatdsl` files ship as package data. At first run, `ProfileManager.seed_presets()` copies missing presets into `~/.config/chatybot/profiles/`. Existing user files are never overwritten.

```toml
# pyproject.toml addition
[tool.setuptools.package-data]
"chatybot" = ["*.toml", "*.chatdsl", "profiles/*.chatdsl"]
```

---

## `chatybot_app.py` Changes

### `initialize()` — read new config keys

```python
# After line 213, alongside existing default_profile read:
self.profile_dir = config_section.get('profile_dir', '~/.config/chatybot/profiles')
self.enable_profile_edit = config_section.get('enable_profile_edit', True)

# Seed presets on first run
from .profile_manager import ProfileManager
ProfileManager(self.profile_dir).seed_presets()
```

### `run()` — new CLI flags dispatch

```python
parser.add_argument(
    "--profile-edit", metavar="NAME", nargs="?", const="",
    help="Open TUI profile editor. Optionally specify profile name to edit/create."
)
parser.add_argument(
    "--profile-list", action="store_true",
    help="List all available profiles"
)

# Dispatch (before app.run()):
if args.profile_list:
    tmp = ChatybotApp(config_path=args.config)
    tmp.initialize()
    from .profile_manager import ProfileManager
    pm = ProfileManager(getattr(tmp, 'profile_dir', '~/.config/chatybot/profiles'))
    asyncio.run(_print_profile_list(pm))
    sys.exit(0)

if args.profile_edit is not None:
    tmp = ChatybotApp(config_path=args.config)
    tmp.initialize()
    from .profile_editor import run_profile_editor
    from .profile_manager import ProfileManager
    pm = ProfileManager(getattr(tmp, 'profile_dir', '~/.config/chatybot/profiles'))
    sys.exit(run_profile_editor(args.profile_edit, pm, tmp.config_manager))
```

---

## `chatdsl_parse.py` Change

Add `profile` to `TParser.VALID_ESCAPE_COMMANDS`:

```python
"run", "run_safe", "run_unsafe", "tool", "profile"
```

---

## Testing Plan

### Unit Tests (`test/test_profile_manager.py`)

| Test | What it covers |
|---|---|
| `test_read_meta_full` | Both `@name` and `@description` parsed |
| `test_read_meta_name_only` | Only `@name` present |
| `test_read_meta_none` | No annotations — name falls back to filename stem |
| `test_read_meta_stops_at_code` | Annotation scan stops at first non-comment line |
| `test_list_profiles` | Returns sorted `.chatdsl` filenames |
| `test_clone_profile` | Cloned file exists and content matches |
| `test_delete_profile` | File removed after delete |
| `test_export_import_roundtrip` | Export then import yields identical file |
| `test_seed_presets_idempotent` | Re-seeding doesn't overwrite existing files |
| `test_resolve_path_by_alias` | `coding` resolves to `coding.chatdsl` |
| `test_resolve_path_not_found` | Raises `FileNotFoundError` for unknown name |

### Integration Tests

| Test | What it covers |
|---|---|
| `test_profile_use_executes_script` | `/profile use coding` calls `execute_script()` with correct path |
| `test_profile_clone_repl` | `/profile clone coding my_coding` creates file |
| `test_profile_delete_repl` | `/profile delete` with confirmation removes file |
| `test_default_profile_loads_on_startup` | `default_profile` in config triggers profile at launch |
| `test_profile_list_cli` | `--profile-list` exits 0, prints profile names |

---

## Implementation Order

1. `src/chatybot/profiles/` — write the three preset `.chatdsl` files
2. `pyproject.toml` — add `profiles/*.chatdsl` to package data
3. `profile_manager.py` — `ProfileMeta`, `ProfileManager`, `read_meta`, CRUD
4. `tools_config.toml` — add `profile_dir`, `enable_profile_edit` keys
5. `chatybot_app.py` — read new config keys + call `seed_presets()` in `initialize()`
6. `chatdsl_parse.py` — add `profile` to `VALID_ESCAPE_COMMANDS`
7. `chatybot_app.py` — `handle_profile_command()` + wire into `execute_script_command()`
8. `chatybot_app.py` — `--profile-edit` / `--profile-list` CLI flags
9. `profile_editor.py` — curses TUI
10. Unit + integration tests
