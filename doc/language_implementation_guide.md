# ChatyBot Language Implementation Guide

This guide outlines the exact vocabulary requirements and files that must be modified when adding support for a new language (locale) in ChatyBot.

---

## 1. Vocabulary Requirements

When implementing a new language, you must translate the following sets of terms.

### A. Command Aliases
These map localized command names to their canonical English command verbs:
* `/help` (e.g., `/ayuda`, `/aide`, `/帮助`, `/aiuto`)
* `/model` (e.g., `/modelo`, `/modele`, `/模型`, `/modello`)
* `/tool` (e.g., `/herramienta`, `/outil`, `/工具`, `/strumento`)
* `/file` (e.g., `/archivo`, `/fichier`, `/文件`, `/file`)
* `/logging` (e.g., `/registro`, `/journal`, `/日志`, `/log`)
* `/mem` (e.g., `/memoria`, `/memoire`, `/内存`, `/memoria`)
* `/exit` (e.g., `/salir`, `/quitter`, `/退出`, `/esci`)
* `/clearfile` (e.g., `/limpiar_archivo`, `/vider_fichier`, `/清空文件`, `/svuota_file`)
* `/showfile` (e.g., `/mostrar_archivo`, `/afficher_fichier`, `/显示文件`, `/mostra_file`)
* `/multiline` (e.g., `/multilinea`, `/multiligne`, `/多行输入`, `/multilinea`)
* `/imagine` (e.g., `/imaginar`, `/imaginer`, `/生图`, `/immagina`)
* `/run` (e.g., `/ejecutar`, `/lancer`, `/运行`, `/esegui`)
* `/echo` (e.g., `/repetir`, `/echo`, `/回显`, `/eco`)

### B. Scripting Keywords
Keywords used in ChatDSL scripts:
* `set` (e.g., `establecer`, `definir`, `设置`, `imposta`)

### C. UI Elements & Prompts
Console prompts, status templates, and startup banners:
* `language_changed` - Status printed when switching locales.
* `tool_enabled` - Status printed when a tool is toggled.
* `error_file_missing` - General file reading error message.
* `script_error_header` - Syntax error traceback header.
* `native_lang_display` - Language label formatted inside the startup flower box (e.g. `Idioma: Español`).
* `chat_prompt` - Prompt prefix displayed in the interactive loop (e.g. `charla --> `).
* `active_model_info` - Startup line displaying active LLM info (e.g. `Modelo activo: {model} (alias: {alias})`).
* `goodbye_message` - Full exit message.
* `goodbye_short` - Short exit message.

### D. Help Catalog Translations
Help page categories, labels, and command summaries:
* **Headers**: `category` (Categoría), `usage` (Uso), `parameters` (Parámetros), `examples` (Ejemplos), `aliases` (Alias), `see_also` (Ver también), `no_commands`.
* **Category Names**: `file` (Archivo), `system` (Sistema), `tool` (Herramienta), `image` (Imagen), `database` (Base de datos), `rerank` (Reclasificación), `debug`, `history`, `input`, `model`, `output`, `script`, `scripting`, `utility`, `variable`.
* **Command Summaries**: A localized `short_desc` for each of the 51+ CLI commands.

---

## 2. Implementation Steps

Follow these sequential steps to add the new language to the codebase:

### Step 1: Update the Translation Catalog
Open [translations.json](file:///Users/jon2allen/github/chatybot/src/chatybot/translations.json) and add a new language block matching the language code (e.g., `"it"` or `"es"`):

```json
  "lang_code": {
    "aliases": {
      "/localized_cmd": "/english_canonical_cmd"
    },
    "keywords": {
      "localized_kw": "english_kw"
    },
    "ui": {
      "native_lang_display": "Native Display Name",
      "chat_prompt": "prompt --> ",
      "active_model_info": "...",
      "goodbye_message": "..."
    },
    "help": {
      "headers": {
        "category": "...",
        "usage": "..."
      },
      "categories": {
        "system": "..."
      },
      "commands": {
        "/help": {
          "short_desc": "..."
        }
      }
    }
  }
```

### Step 2: Register Language in LocalizationManager
Open [localization.py](file:///Users/jon2allen/github/chatybot/src/chatybot/localization.py) and update the `LANG_MAP` dictionary to bind the new locale code and English name variants to the catalog code:

```python
    LANG_MAP = {
        # Existing lang codes...
        "lang_code": "lang_code", "full_name_variant": "lang_code"
    }
```

### Step 3: Create Localized Verification Scripts
Create two verification scripts in the `test/` directory to validate the vocabulary additions:
1. `test/language_<lang>_test1.chatdsl` - Basic script validating main commands (e.g., `/model`, `/tool`).
2. `test/language_<lang>_test2.chatdsl` - Comprehensive script executing all command verbs sequentially.

### Step 4: Add Unit Tests
Open [test_localization.py](file:///Users/jon2allen/github/chatybot/test/test_localization.py) and add tests verifying:
1. The new lang code resolves correctly in `LocalizationManager`.
2. Resolving commands and preprocessing/translating localized scripts outputs the expected canonical English ChatDSL script.
