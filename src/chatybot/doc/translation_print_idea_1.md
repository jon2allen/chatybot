# Design Options: Advanced Logging and Internationalization (i18n) Printer

This document outlines three architectural options for implementing a centralized print and logging system in ChatyBot that supports advanced file logging and internationalization (i18n) while maintaining the exact look and feel of the terminal interface.

---

## Option 1: The Unified `ConsolePrinter` Wrapper (Recommended)

This approach replaces direct `print(...)` calls throughout the codebase with a custom wrapper utility class. It utilizes key-based lookups for i18n translation catalogs and handles background file logging.

### Implementation Example

```python
import logging
import os

class ConsolePrinter:
    def __init__(self, locale="en", log_file="chatybot.log"):
        self.locale = locale
        
        # Configure advanced file logging in the background
        self.logger = logging.getLogger("chatybot_file")
        self.logger.setLevel(logging.DEBUG)
        
        if log_file:
            fh = logging.FileHandler(log_file, encoding="utf-8")
            fh.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s'))
            self.logger.addHandler(fh)
            
        # Simple local translation catalog
        self.translations = {
            "en": {
                "tool_enabled": "Tool '{tool}' enabled.",
                "goodbye": "Goodbye! Thanks for chatting."
            },
            "es": {
                "tool_enabled": "Herramienta '{tool}' habilitada.",
                "goodbye": "¡Adiós! Gracias por chatear."
            }
        }

    def print(self, key_or_text: str, log_level=logging.INFO, **kwargs):
        # 1. Translate if it's a registered key, otherwise print as raw string
        locale_dict = self.translations.get(self.locale, self.translations["en"])
        template = locale_dict.get(key_or_text, key_or_text)
        formatted_msg = template.format(**kwargs)

        # 2. Output directly to console (keeps look and feel identical)
        print(formatted_msg)

        # 3. Log to file in the background with timestamp metadata
        self.logger.log(log_level, formatted_msg)
```

### Usage Pattern
```python
# Initialization
printer = ConsolePrinter(locale="es")

# Execution
printer.print("tool_enabled", tool="list_directory")
```
- **Console Output:** `Herramienta 'list_directory' habilitada.`
- **Log File Output:** `2026-07-12 13:40:02 [INFO] Herramienta 'list_directory' habilitada.`

### Pros & Cons
* **Pros:** Explicit parameters, easily formatted, zero coupling with console escape codes, and doesn't intercept other package operations.
* **Cons:** Requires refactoring existing `print()` calls in the codebase to `printer.print()`.

---

## Option 2: Customized Native Logger and Plain Formatter

This approach replaces `print()` calls with standard `logging` messages, using distinct handlers and formatters to differentiate between terminal output and debug log files.

### Implementation Example

```python
import logging
import sys

class PlainConsoleFormatter(logging.Formatter):
    """Formats console logs without metadata (INFO:, WARNING:, timestamps) to preserve UI look."""
    def format(self, record):
        return record.getMessage()

def setup_logging(locale="en"):
    logger = logging.getLogger("chatybot")
    logger.setLevel(logging.DEBUG)
    
    # 1. Console Handler (preserves terminal look and feel)
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.INFO)
    ch.setFormatter(PlainConsoleFormatter())
    logger.addHandler(ch)
    
    # 2. File Handler (advanced debugging logs)
    fh = logging.FileHandler("chatybot.log", encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
    logger.addHandler(fh)
    
    return logger
```

### Pros & Cons
* **Pros:** Standardizes on Python's built-in `logging` module; easily integrates with external tools and standard log rotation configurations.
* **Cons:** Native standard logging doesn't translate keys dynamically out-of-the-box, meaning you must wrap strings using standard libraries like `gettext` (`_("message")`).

---

## Option 3: Global System Stream Interception

This approach intercepts everything written to `sys.stdout`. It translates matching strings dynamically and writes them to a log file behind the scenes without editing any existing codebase files.

### Implementation Example

```python
import sys
import logging

class OutputIntercept:
    def __init__(self, original_stdout, translations, logger):
        self.stdout = original_stdout
        self.translations = translations
        self.logger = logger

    def write(self, message):
        if message.strip():
            # Intercept and translate string if matched in translations
            translated = self.translations.get(message.strip(), message.strip())
            output_msg = translated + ("\n" if message.endswith("\n") else "")
            
            # Print to console and file logger
            self.stdout.write(output_msg)
            self.logger.info(translated)
        else:
            self.stdout.write(message)

    def flush(self):
        self.stdout.flush()

# Activation Hook:
# sys.stdout = OutputIntercept(sys.stdout, translation_dict, file_logger)
```

### Pros & Cons
* **Pros:** Zero refactoring. Every standard python `print()` in the workspace immediately gains i18n translation and file logging automatically.
* **Cons:** Intercepting stdout is notoriously brittle when printing split/partial arguments or formatting characters dynamically, requiring complex buffer reconstruction.
