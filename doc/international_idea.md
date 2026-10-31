# Design Proposal: Unified Localization Manager (`LocalizationManager`)

**Document Version:** 1.1
**Date:** July 23, 2026 (date of the last commit touching this file: `d40bd04`, 2026-07-23 11:35 -0400)
**Status:** Implemented with deviations — validated against `localization.py`, `chaty_help.py`, `chatybot_app.py`, and `translations.json` on October 31, 2026; see Implementation Deviations and Open Items below
**Applies To:** `src/chatybot/localization.py`, `src/chatybot/chaty_help.py` (render path), `src/chatybot/translations.json`, `src/chatybot/logging_manager.py` (successor to the unified-logging half)

---

## Implementation Deviations (as-built vs. this proposal)

Validated claim-by-claim on 2026-10-31. What matches: the per-locale catalog with `aliases`/`ui`/command help, `print()` template formatting, `resolve_command` alias resolution (superset: the implementation adds a cross-locale fallback scan), the English fallback for incomplete translations, and the app integration at `chatybot_app.py:99` (`self.i18n = LocalizationManager(locale=lang)`). Notably, the per-command `long_desc` catalog key specified in the schema was only delivered on 2026-10-31 — three months after this proposal.

The deviations:

1. **The "unified localization + logging" core idea was split into two managers.** The proposal has `LocalizationManager` own a stdlib `logging.FileHandler` for background logging. The implementation contains zero logging in `localization.py` — file logging went to a separate `LoggingManager` using pyio-intercept stdout middleware (`logging_manager.py`).
2. **Help data flow is inverted.** The proposal has `HelpSystem` pull translated `short_desc`/`usage`/`long_desc` from the catalog at registration time (catalog as source of truth, constructor-injected manager). The implementation does the opposite: `chaty_help.py` holds canonical English `CommandHelp` dataclasses and the renderer overlays translations at display time; the help system is a no-arg `get_help_system()` singleton with `i18n` passed per render call. This is the "two sources of truth" tension that the Halloween proposal (§3, item A3 — message keys) recommends resolving by returning to the catalog-driven design specified here.
3. **The per-command `usage` catalog key never materialized.** Usage lines come from the English canonical text with alias substitution at render time; no catalog entry carries `usage`.
4. **The `/lang` live language-switching command was never implemented.** No `/lang` or `/language` command exists; the locale is set from configuration at startup only.
5. **The catalog schema outgrew the proposal:** `commands` became `help.commands`, and the implementation added `keywords` (sub-keyword translation via `translate_script`), `help.headers`, and `help.categories` — none of which are specified here. `set_locale` also gained `LANG_MAP` normalization ("spanish" → "es") beyond the proposal's direct key check.
6. **The proposal's schema anticipated bilingual help output** only implicitly; as-built, `format_command_detail` renders English `long_desc` followed by the localized translation (added 2026-10-31), which the proposal's single-template design did not cover.

## Open Items

1. **`/lang` live language switching** — the only unimplemented user-facing feature in this proposal; today changing language requires a config change and restart.
2. **Message-key architecture (A3)** — adopt the catalog-driven help design this proposal originally specified, or formally accept English-in-code as canonical; tracked in `doc/Halloween_proposal.md` §3.
3. **Unified-logging question** — decide whether localization should also own structured logging (as proposed here) or remain split from `LoggingManager`; the Halloween proposal §5 expands the pyio-intercept chain instead.
4. **`usage` catalog keys** — either add them or document that usage strings are English-canonical with alias substitution.

---

This document details the unified localization and logging architecture for ChatyBot. It integrates translation catalog lookups, dynamic console output, background debugging logs, command alias resolution (e.g. `/herramienta` -> `/tool`), and localized help messages into a single, cohesive system.

---

## 1. Catalog Schema (`translations.json`)
The translation catalogs are stored in a standard JSON format, broken down by locale codes. Each locale includes command aliases, command help templates, and general UI/console strings.

```json
{
  "en": {
    "aliases": {
      "/help": "/help",
      "/tool": "/tool",
      "/file": "/file",
      "/exit": "/exit"
    },
    "commands": {
      "/help": {
        "short_desc": "Show this help message",
        "usage": "/help [command|keyword]",
        "long_desc": "Display available commands. Use '/help <command>' for detailed help."
      },
      "/file": {
        "short_desc": "Load a text file into the buffer",
        "usage": "/file <path>",
        "long_desc": "Loads text from a file into the persistent file buffer."
      }
    },
    "ui": {
      "tool_enabled": "Tool '{tool}' enabled.",
      "language_changed": "Language set to: {lang}"
    }
  },
  "es": {
    "aliases": {
      "/ayuda": "/help",
      "/herramienta": "/tool",
      "/archivo": "/file",
      "/salir": "/exit"
    },
    "commands": {
      "/help": {
        "short_desc": "Mostrar este mensaje de ayuda",
        "usage": "/help [comando|palabra_clave]",
        "long_desc": "Muestra los comandos disponibles. Use '/help <comando>' para ayuda detallada."
      },
      "/file": {
        "short_desc": "Cargar un archivo de texto en el búfer",
        "usage": "/file <ruta>",
        "long_desc": "Carga el texto de un archivo en el búfer de archivos persistente."
      }
    },
    "ui": {
      "tool_enabled": "Herramienta '{tool}' habilitada.",
      "language_changed": "Idioma establecido en: {lang}"
    }
  }
}
```

---

## 2. Localization Class (`LocalizationManager`)
This manager centralizes all locale-specific processing: console printing, file logging, key translation, and slash-command alias mapping.

```python
import json
import os
import logging
from typing import Dict, Any

class LocalizationManager:
    def __init__(self, locale: str = "en", catalog_path: str = "translations.json", log_file: str = "chatybot.log"):
        self.locale = locale
        self.catalog_path = catalog_path
        self.catalog = self._load_catalog()
        
        # Setup background file logger
        self.logger = logging.getLogger("chatybot_file")
        self.logger.setLevel(logging.DEBUG)
        if log_file:
            fh = logging.FileHandler(log_file, encoding="utf-8")
            fh.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s'))
            self.logger.addHandler(fh)

    def _load_catalog(self) -> Dict[str, Any]:
        if os.path.exists(self.catalog_path):
            try:
                with open(self.catalog_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                print(f"Error loading translation catalog: {e}")
        return {}

    def set_locale(self, locale: str) -> bool:
        if locale in self.catalog:
            self.locale = locale
            return True
        return False

    # --- 1. Console Printing & Background Logging ---
    def print(self, key_or_text: str, log_level=logging.INFO, **kwargs):
        locale_data = self.catalog.get(self.locale, self.catalog.get("en", {}))
        ui_translations = locale_data.get("ui", {})
        
        template = ui_translations.get(key_or_text, key_or_text)
        formatted_msg = template.format(**kwargs)
        
        # Print directly to stdout preserving exact terminal styles
        print(formatted_msg)
        
        # Log to file in the background
        self.logger.log(log_level, formatted_msg)

    # --- 2. Localized Command Alias Resolver ---
    def resolve_command(self, raw_cmd: str) -> str:
        # Match case-insensitive localized slash commands
        locale_aliases = self.catalog.get(self.locale, {}).get("aliases", {})
        return locale_aliases.get(raw_cmd.lower(), raw_cmd)

    # --- 3. Help System Dictionary Provider ---
    def get_command_help(self, cmd_name: str) -> Dict[str, str]:
        locale_data = self.catalog.get(self.locale, self.catalog.get("en", {}))
        cmd_translations = locale_data.get("commands", {})
        
        # Fallback to English catalog if translations are incomplete
        fallback_data = self.catalog.get("en", {}).get("commands", {}).get(cmd_name, {})
        return cmd_translations.get(cmd_name, fallback_data)
```

---

## 3. Application Integration Workflow

### App Setup and Input Handling (`chatybot_app.py`)
```python
class ChatybotApp:
    def __init__(self):
        # 1. Initialize translation manager
        self.i18n = LocalizationManager(locale="es")
        
        # 2. Initialize Help system, passing the manager reference
        self.help_system = HelpSystem(self.i18n)

    async def handle_escape_command(self, command: str) -> bool:
        parts = command.split(maxsplit=2)
        raw_cmd = parts[0]
        
        # 3. Resolve command alias (e.g. /herramienta -> /tool)
        cmd = self.i18n.resolve_command(raw_cmd)
        
        if cmd == "/tool":
            # Command execution logic...
            self.i18n.print("tool_enabled", tool="list_directory") 
            return True
            
        elif cmd == "/lang":
            # Live language switching
            selected_lang = parts[1].strip().lower()
            if self.i18n.set_locale(selected_lang):
                self.i18n.print("language_changed", lang=selected_lang.upper())
            return True
```

### Help System Setup (`chaty_help.py`)
```python
class HelpSystem:
    def __init__(self, i18n_manager):
        self.i18n = i18n_manager
        self.commands = {}
        self.categories = {}
        self._initialize_commands()

    def _initialize_commands(self) -> None:
        # Command configurations defining canonical keys and relationships
        commands_meta = [
            ("/help", "system", ["/listcommands"]),
            ("/file", "file", ["/showfile", "/clearfile"])
        ]
        
        for name, category, see_also in commands_meta:
            # Retrieve translation dictionaries directly from the i18n manager
            help_data = self.i18n.get_command_help(name)
            
            self.register_command(CommandHelp(
                name=name,
                category=category,
                short_desc=help_data.get("short_desc", ""),
                usage=help_data.get("usage", ""),
                long_desc=help_data.get("long_desc", ""),
                see_also=see_also
            ))
```
