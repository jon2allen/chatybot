# Chatybot Config TUI — Curses Design

> A terminal UI for managing `chat_config.toml` using Python `curses`.
> Supports browsing, editing, cloning, and deleting model configurations
> with built-in knowledge of common vendors, endpoints, and API key patterns.

---

## Design Decisions

| #  | Question                        | Decision                                                                 |
|----|--------------------------------|--------------------------------------------------------------------------|
| 1  | Entry point                    | `chatybot --config-edit` flag + `chatybot-config` console_script alias   |
| 2  | External dependencies          | Zero — stdlib `curses` only + existing `config_model.py`                 |
| 3  | Validation enforcement         | Loose — warn on invalid values (yellow status bar) but allow save        |
| 4  | Vendor preset location         | Separate `src/chatybot/vendors.py` module for easy additions             |

---

## Screen 1 — Main Model List

The primary view. Models are listed in a scrollable table with the active
row highlighted. A status bar at the bottom shows available key bindings.

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│  Chatybot Config Manager                              config_editor branch     │
│  File: ~/.config/chatybot/chat_config.toml            29 models loaded         │
│ ├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                │
│  #   Alias                  Model Name                       Vendor    Temp    │
│  ─── ────────────────────── ──────────────────────────────── ──────── ─────    │
│  1   mistral_1              mistral-large-2512               mistral   0.70    │
│  2   devstral_1             devstral-2512                    —         0.70    │
│  3   mistral_35             mistral-medium-2604              —         0.20    │
│ >4   gemini_flash           gemini-2.5-flash                 google    0.00  ◀ │
│  5   gemini_pro             gemini-2.5-pro                   google    0.00    │
│  6   gemma_3                gemma-3-27b-it                   —         0.20    │
│  7   openai_gpt4            gpt-4o                           openai    0.10    │
│  8   mistral_pixtral        mistralai/pixtral-large-2411     —         —       │
│  9   openrouter_image       google/gemini-2.5-flash-image    openrtr   0.00    │
│  10  flux_1                 black-forest-labs/flux.2-klein…  openrtr   0.00    │
│  11  nova_2                 amazon/nova-2-lite-v1:free       —         0.90    │
│  12  elephant               inclusionai/ling-2.6-flash:free  —         0.10    │
│  13  nvidia_1               nvidia/nemotron-nano-12b-v2-vl…  openrtr   0.70    │
│  ·                                                                             │
│  ·   (scroll for 16 more)                                                      │
│  ·                                                                             │
│                                                                                │
├─────────────────────────────────────────────────────────────────────────────────┤
│ ↑↓ Navigate  │ ENTER Edit  │ N New  │ C Clone  │ D Delete  │ S Save  │ Q Quit │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### Key Bindings — Main List

| Key         | Action                                      |
|-------------|---------------------------------------------|
| `↑` / `k`   | Move selection up                           |
| `↓` / `j`   | Move selection down                         |
| `PgUp`       | Scroll up one page                          |
| `PgDn`       | Scroll down one page                        |
| `Home`       | Jump to first model                         |
| `End`        | Jump to last model                          |
| `Enter`      | Open model editor window                    |
| `N`          | New model (opens editor with vendor picker) |
| `C`          | Clone selected model (opens clone dialog)   |
| `D`          | Delete selected model (confirmation)        |
| `S`          | Save config to file                         |
| `/`          | Search/filter models by name or alias       |
| `Q`          | Quit (prompts if unsaved changes)           |

---

## Screen 2 — Model Editor Window

A floating window overlaid on the main list. Fields are displayed in a
form layout. The cursor moves between fields with `Tab` / `Shift+Tab`.
Editable fields show the current value inline. Dropdown-style fields
(vendor, type) cycle through known values with `←` / `→`.

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│  Chatybot Config Manager                              config_editor branch     │
│  File: ~/.co┌──────────────────────────────────────────────────┐els loaded     │
├─────────────│          Edit Model: gemini_flash                │───────────────┤
│             ├──────────────────────────────────────────────────┤               │
│  #   Alias  │                                                  │    Temp       │
│  ─── ────── │  Alias:       [gemini_flash                   ]  │── ─────       │
│  1   mistra │  Model Name:  [gemini-2.5-flash                ] │    0.70       │
│  2   devstr │  Type:        < chat ▸                    ▼      │    0.70       │
│  3   mistra │                                                  │    0.20       │
│ >4   gemini │  ── Endpoint ──────────────────────────────      │    0.00  ◀    │
│  5   gemini │  Base URL:    [https://generativelanguage.go...] │    0.00       │
│  6   gemma_ │  API Key Env: [GEMINI_API_KEY                 ]  │    0.20       │
│  7   openai │  Vendor:      < google ▸                  ▼      │    0.10       │
│  8   mistra │                                                  │    —          │
│  9   openro │  ── Parameters ────────────────────────────      │    0.00       │
│  10  flux_1 │  Temperature: [0.00                           ]  │    0.00       │
│  11  nova_2 │  Top K:       [1                              ]  │    0.90       │
│  12  elepha │  Max Tokens:  [                              —]  │    0.10       │
│  13  nvidia │  Top P:       [                              —]  │    0.70       │
│             │  Freq Penalty:[                              —]  │               │
│             │  Pres Penalty:[                              —]  │               │
│             │                                                  │               │
│             │  ── Image Generation ──────────────────────       │               │
│             │  Enabled:     < true ▸                    ▼      │               │
│             │  Endpoint:    [/images/generations             ]  │               │
│             │  Modalities:  [                              —]  │               │
│             │                                                  │               │
│             │  [  OK  ]    [ Cancel ]    [ Apply ]             │               │
│             ├──────────────────────────────────────────────────┤               │
├─────────────└──────────────────────────────────────────────────┘───────────────┤
│ TAB Next Field │ S-TAB Prev │ ←→ Cycle Option │ ENTER Confirm │ ESC Cancel    │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### Field Types

| Field          | Input Type       | Notes                                    |
|----------------|------------------|------------------------------------------|
| Alias          | Text input       | Must be unique, valid Python identifier  |
| Model Name     | Text input       | Free-form API model identifier           |
| Type           | Cycle selector   | `chat` / `reranker`                      |
| Base URL       | Text input       | Auto-suggests from vendor presets        |
| API Key Env    | Text input       | Auto-suggests from vendor presets        |
| Vendor         | Cycle selector   | Known vendors (see below)                |
| Temperature    | Numeric input    | 0.0 – 2.0, step 0.1                     |
| Top K          | Numeric input    | Integer, nullable                        |
| Max Tokens     | Numeric input    | Integer, nullable                        |
| Top P          | Numeric input    | 0.0 – 1.0, nullable                     |
| Freq Penalty   | Numeric input    | -2.0 – 2.0, nullable                    |
| Pres Penalty   | Numeric input    | -2.0 – 2.0, nullable                    |
| Img Enabled    | Cycle selector   | `true` / `false`                         |
| Img Endpoint   | Text input       | Path component, e.g. `/images/generations` |
| Modalities     | Text input       | Comma-separated list or `—` for none    |

---

## Screen 3 — Clone Dialog

A compact floating dialog. Pre-fills all values from the source model.
The user only needs to change the alias (required) and optionally tweak
fields before confirming.

```
          ┌──────────────────────────────────────────────┐
          │         Clone Model: mistral_1               │
          ├──────────────────────────────────────────────┤
          │                                              │
          │  Source:    mistral_1  (mistral-large-2512)   │
          │                                              │
          │  New Alias: [mistral_1_lowtemp            ]  │
          │                                              │
          │  ── Quick Overrides ──────────────────────   │
          │  Temperature: [0.10                       ]  │
          │  Top K:       [1                          ]  │
          │  Max Tokens:  [                          —]  │
          │                                              │
          │  [ Clone ]     [ Edit Full ]    [ Cancel ]   │
          │                                              │
          └──────────────────────────────────────────────┘
```

### Clone Workflow

1. User presses `C` on a model in the main list.
2. Clone dialog opens with the source model's values pre-filled.
3. User enters a new alias (required, must be unique).
4. User optionally adjusts temperature / top_k / max_tokens.
5. **Clone** — creates the model and returns to the main list.
6. **Edit Full** — creates the model and immediately opens the full editor.
7. **Cancel** — discards and returns to the main list.

---

## Screen 4 — Delete Confirmation

A small confirmation dialog. Shows the alias and model name for clarity.

```
          ┌──────────────────────────────────────────────┐
          │            ⚠  Delete Model?                  │
          ├──────────────────────────────────────────────┤
          │                                              │
          │  Are you sure you want to delete:            │
          │                                              │
          │    Alias:  nvidia_1                          │
          │    Model:  nvidia/nemotron-nano-12b-v2-vl…   │
          │    Type:   chat                              │
          │                                              │
          │  This action cannot be undone until you       │
          │  save the configuration file.                │
          │                                              │
          │       [ Yes, Delete ]      [ Cancel ]        │
          │                                              │
          └──────────────────────────────────────────────┘
```

---

## Screen 5 — Vendor / Endpoint Picker

When creating a **new model** (`N`) or editing the **Vendor** field,
a picker window offers known vendor presets. Selecting a vendor
auto-populates the Base URL and API Key Env fields.

```
          ┌──────────────────────────────────────────────┐
          │         Select Vendor Preset                 │
          ├──────────────────────────────────────────────┤
          │                                              │
          │  >  mistral                                  │
          │        URL: https://api.mistral.ai/v1        │
          │        Key: MISTRAL_API_KEY                  │
          │                                              │
          │     google                                   │
          │        URL: https://generativelanguage.go…   │
          │        Key: GEMINI_API_KEY                   │
          │                                              │
          │     openai                                   │
          │        URL: https://api.openai.com/v1        │
          │        Key: OPENAI_API_KEY                   │
          │                                              │
          │     openrouter                               │
          │        URL: https://openrouter.ai/api/v1     │
          │        Key: OPENROUTER_API_KEY               │
          │                                              │
          │     nvidia                                   │
          │        URL: https://integrate.api.nvidia.…   │
          │        Key: NVIDIA_API                       │
          │                                              │
          │     publicai                                  │
          │        URL: https://api.publicai.co/v1       │
          │        Key: SWISS_API_KEY                    │
          │                                              │
          │     bytez                                    │
          │        URL: https://api.bytez.com/models/…   │
          │        Key: BYTEZ_API_KEY                    │
          │                                              │
          │     ollama (local)                           │
          │        URL: http://localhost:11434/v1         │
          │        Key: (none)                           │
          │                                              │
          │     llama_cpp (local)                        │
          │        URL: http://localhost:8080/v1         │
          │        Key: (none)                           │
          │                                              │
          │     jina (reranker)                          │
          │        URL: https://api.jina.ai/v1/rerank    │
          │        Key: JINA_API_KEY                     │
          │                                              │
          │     (custom)                                 │
          │                                              │
          │  [ Select ]           [ Cancel ]             │
          └──────────────────────────────────────────────┘
```

---

## Screen 6 — Save Confirmation / Unsaved Changes

Shown when the user presses `Q` with unsaved changes, or after `S`.

```
          ┌──────────────────────────────────────────────┐
          │            Save Configuration?               │
          ├──────────────────────────────────────────────┤
          │                                              │
          │  You have unsaved changes (3 modifications). │
          │                                              │
          │  Save to:                                    │
          │  ~/.config/chatybot/chat_config.toml          │
          │                                              │
          │  [ Save ]   [ Save As… ]   [ Discard ]       │
          │                                              │
          └──────────────────────────────────────────────┘
```

The **Save As…** option opens a text input for a custom output path,
enabling writing to alternative files (e.g. `test_config.toml`).

---

## Screen 7 — Search / Filter Bar

Pressing `/` on the main list activates a search bar at the bottom.
Typing filters the model list in real-time (fuzzy match on alias + name).

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│  Chatybot Config Manager                              config_editor branch     │
│  File: ~/.config/chatybot/chat_config.toml            29 models loaded         │
│ ├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                │
│  #   Alias                  Model Name                       Vendor    Temp    │
│  ─── ────────────────────── ──────────────────────────────── ──────── ─────    │
│ >1   nvidia_1               nvidia/nemotron-nano-12b-v2-vl…  openrtr   0.70    │
│  2   nvidia_mistral_nemo…   mistralai/mistral-nemotron       nvidia    0.70    │
│  3   nvidia_mistral_smal…   mistralai/mistral-small-4-119…   nvidia    0.10    │
│  4   nemotron_super_49b     nvidia/llama-3.3-nemotron-su…    nvidia    0.50    │
│                                                                                │
│                                                                                │
│                                                                                │
│                           4 of 29 models shown                                 │
│                                                                                │
├─────────────────────────────────────────────────────────────────────────────────┤
│ Filter: nvidia█                                              ESC Clear  │ ↵ Go │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## Window Layout Strategy

```
┌─────────────────────────────────────────────┐
│              HEADER (2 lines)               │  File path, model count
├─────────────────────────────────────────────┤
│                                             │
│          MAIN PAD (scrollable)              │  Model list table
│                                             │
│     ┌────────────────────────────┐          │
│     │    FLOATING WINDOW         │          │  Editor / Clone / Delete
│     │    (centered overlay)      │          │  dialogs rendered on top
│     │                            │          │
│     └────────────────────────────┘          │
│                                             │
├─────────────────────────────────────────────┤
│           STATUS BAR (1 line)               │  Key hints, filter bar
└─────────────────────────────────────────────┘
```

### Curses Window Hierarchy

```
stdscr
├── header_win        (newwin, 2 lines, full width)
├── list_pad          (newpad, N lines, scrollable)
├── status_win        (newwin, 1 line, full width, bottom)
│
├── editor_win        (newwin, centered, ~30×54)    ← overlay
├── clone_win         (newwin, centered, ~16×48)    ← overlay
├── delete_win        (newwin, centered, ~14×48)    ← overlay
├── vendor_win        (newwin, centered, ~38×48)    ← overlay
└── save_win          (newwin, centered, ~10×48)    ← overlay
```

---

## Vendor Presets — `src/chatybot/vendors.py`

Vendor presets live in a **separate module** (`vendors.py`) so that adding
a new provider is a single-file edit with no TUI or model code changes.

The TUI imports `VENDOR_PRESETS` from this module for the vendor picker
and auto-population of Base URL / API Key fields. **Presets are defaults
only — every field is fully overridable by the user.** For example, a
`llama_cpp` model could have image support enabled if the user's local
server supports it.

| Vendor       | Default Base URL                                            | Default API Key Env | Img Default |
|-------------|-------------------------------------------------------------|---------------------|-------------|
| `mistral`    | `https://api.mistral.ai/v1`                                | `MISTRAL_API_KEY`   | on          |
| `google`     | `https://generativelanguage.googleapis.com/v1beta/openai/`  | `GEMINI_API_KEY`    | on          |
| `openai`     | `https://api.openai.com/v1`                                | `OPENAI_API_KEY`    | on          |
| `openrouter` | `https://openrouter.ai/api/v1`                             | `OPENROUTER_API_KEY`| off         |
| `nvidia`     | `https://integrate.api.nvidia.com/v1`                      | `NVIDIA_API`        | off         |
| `publicai`   | `https://api.publicai.co/v1`                               | `SWISS_API_KEY`     | off         |
| `bytez`      | `https://api.bytez.com/models/v2/openai/v1`                | `BYTEZ_API_KEY`     | off         |
| `ollama`     | `http://localhost:11434/v1`                                | `(none)`            | off         |
| `llama_cpp`  | `http://localhost:8080/v1`                                 | `(none)`            | off         |
| `jina`       | `https://api.jina.ai/v1/rerank`                            | `JINA_API_KEY`      | off         |

### `vendors.py` Module Sketch

```python
# src/chatybot/vendors.py
"""Vendor preset definitions for the Config TUI and model creation."""

from dataclasses import dataclass
from typing import Optional

@dataclass(frozen=True)
class VendorPreset:
    name: str
    base_url: str
    api_key_env: Optional[str] = None
    image_support: bool = False
    default_type: str = "chat"       # "chat" or "reranker"

VENDOR_PRESETS: dict[str, VendorPreset] = {
    "mistral":    VendorPreset("mistral",    "https://api.mistral.ai/v1",
                               "MISTRAL_API_KEY", image_support=True),
    "google":     VendorPreset("google",     "https://generativelanguage.googleapis.com/v1beta/openai/",
                               "GEMINI_API_KEY", image_support=True),
    "openai":     VendorPreset("openai",     "https://api.openai.com/v1",
                               "OPENAI_API_KEY", image_support=True),
    "openrouter": VendorPreset("openrouter", "https://openrouter.ai/api/v1",
                               "OPENROUTER_API_KEY"),
    "nvidia":     VendorPreset("nvidia",     "https://integrate.api.nvidia.com/v1",
                               "NVIDIA_API"),
    "publicai":   VendorPreset("publicai",   "https://api.publicai.co/v1",
                               "SWISS_API_KEY"),
    "bytez":      VendorPreset("bytez",      "https://api.bytez.com/models/v2/openai/v1",
                               "BYTEZ_API_KEY"),
    "ollama":     VendorPreset("ollama",     "http://localhost:11434/v1"),
    "llama_cpp":  VendorPreset("llama_cpp",  "http://localhost:8080/v1"),
    "jina":       VendorPreset("jina",       "https://api.jina.ai/v1/rerank",
                               "JINA_API_KEY", default_type="reranker"),
}

def vendor_names() -> list[str]:
    """Ordered list of vendor names for the TUI picker."""
    return list(VENDOR_PRESETS.keys())
```

---

## Integration with ChatConfig Model

The TUI operates entirely on the in-memory `ChatConfig` Pydantic model:

```
                    ┌─────────────────┐
                    │  chat_config    │
                    │    .toml        │
                    └────────┬────────┘
                             │ ChatConfig.from_toml()
                             ▼
                    ┌─────────────────┐
                    │   ChatConfig    │  ← Pydantic v2 model
                    │   (in memory)   │     validates all edits
                    └────────┬────────┘
                             │
              ┌──────────────┼──────────────┐
              │              │              │
              ▼              ▼              ▼
        ┌──────────┐  ┌──────────┐  ┌──────────┐
        │ Browse   │  │ Edit     │  │ Clone    │
        │ models   │  │ fields   │  │ model    │
        │ (list)   │  │ (window) │  │ (dialog) │
        └──────────┘  └──────────┘  └──────────┘
              │              │              │
              └──────────────┼──────────────┘
                             │ cfg.to_toml(path)
                             ▼
                    ┌─────────────────┐
                    │  output.toml    │
                    └─────────────────┘
```

### Key Operations Mapped to ChatConfig

| TUI Action        | ChatConfig Method / Pattern                              |
|-------------------|----------------------------------------------------------|
| Load file         | `ChatConfig.from_toml(path)`                             |
| Browse models     | Iterate `cfg.models.items()`                             |
| Edit a field      | `cfg.models[alias].field = new_value`                    |
| Clone a model     | `cfg.models[new_alias] = src.model_copy(update={...})`   |
| Delete a model    | `del cfg.models[alias]`                                  |
| Add new model     | `cfg.models[alias] = ChatModelConfig(...)`               |
| Save to file      | `cfg.to_toml(path)`                                      |
| Filter/search     | List comprehension on `cfg.models`                       |
| Vendor lookup     | `from .vendors import VENDOR_PRESETS`                    |

---

## Implementation Notes

### Module Layout

```
src/chatybot/
├── config_model.py      # Pydantic schema (existing)
├── config_tui.py        # Curses TUI — main module
└── vendors.py           # Vendor presets (new)
```

### Entry Points

Two ways to launch — both invoke the same `config_tui.main()` function:

1. **Flag on main app**: `chatybot --config-edit`
   - Parsed in `chatybot_app.py` via argparse
   - If `--config-edit` is set, launch TUI instead of chat REPL
   - Inherits `-c` / `--config` for the file path

2. **Standalone alias**: `chatybot-config`
   - Registered in `pyproject.toml` as a separate console_script
   - Equivalent to `chatybot --config-edit`

```toml
# pyproject.toml
[project.scripts]
chatybot = "chatybot.main:run"
chatybot-config = "chatybot.config_tui:main"
```

### Dependencies

Zero external — only stdlib `curses` + existing project modules:
- `config_model.py` — load, validate, serialize
- `vendors.py` — vendor preset lookups

### Validation Philosophy — Loose Enforcement

The TUI validates edits through Pydantic but does **not block** the user:

| Situation                     | Behavior                                          |
|-------------------------------|---------------------------------------------------|
| Invalid temperature (e.g. 5.0)| Yellow warning in status bar, field still accepted |
| Missing required field        | Yellow warning, save proceeds with raw value       |
| Duplicate alias on clone      | Red error, **blocks** (alias must be unique)       |
| Unknown vendor string         | No warning — free-form vendor is allowed           |
| Malformed base_url            | Yellow warning, not blocked                        |

The status bar shows warnings like:
```
⚠ Temperature 5.0 outside typical range (0.0–2.0) — saved anyway
```

This "warn but don't block" approach allows power users to experiment
with non-standard values while still providing helpful guardrails.

### Color Scheme

Use `curses.init_pair()` for consistent visual language:
- **Header**: cyan on black
- **Selected row**: reverse video
- **Warnings**: yellow text
- **Errors** (blocking): red text
- **Section headers**: yellow/bold
- **Form labels**: white, **form values**: cyan

### Resize Handling

`curses.KEY_RESIZE` re-calculates all window positions and redraws.
Floating windows re-center automatically.
