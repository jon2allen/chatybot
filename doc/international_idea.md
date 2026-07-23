# Design Proposal: Unified Localization Manager (`LocalizationManager`)

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
