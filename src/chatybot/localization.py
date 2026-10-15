import json
import os
from typing import Any, ClassVar


class LocalizationManager:
    """Manages system command aliases, script keywords, and UI strings across multiple languages."""
    
    LANG_MAP: ClassVar[dict[str, str]] = {
        "en": "en", "english": "en",
        "es": "es", "spanish": "es",
        "fr": "fr", "french": "fr",
        "zh": "zh", "chinese": "zh",
        "it": "it", "italian": "it",
        "ar": "ar", "arabic": "ar", "levantine": "ar", "apc": "ar", "ajp": "ar"
    }

    AFFIRMATIVES: ClassVar[dict[str, set[str]]] = {
        "en": {"y", "yes", "true", "1"},
        "es": {"s", "si", "sí", "y", "yes", "true", "1"},
        "fr": {"o", "oui", "y", "yes", "true", "1"},
        "it": {"s", "si", "sì", "y", "yes", "true", "1"},
        "zh": {"y", "yes", "是", "好", "确定", "确认", "对", "1"},
        "ar": {"y", "yes", "ن", "نعم", "أجل", "اي", "أي", "1"},
    }

    CHOICE_LETTERS: ClassVar[dict[str, tuple[str, str]]] = {
        "en": ("y", "N"),
        "es": ("s", "N"),
        "fr": ("o", "N"),
        "it": ("s", "N"),
        "zh": ("y", "N"),
        "ar": ("y", "N"),
    }

    def __init__(self, locale: str = "en"):
        self.locale = self.LANG_MAP.get(locale.lower(), "en")
        self.catalog = self._load_catalog()

    def is_affirmative(self, response: str) -> bool:
        """Check if a response string represents an affirmative confirmation in the active or any locale."""
        if not response:
            return False
        cleaned = response.strip().lower()
        # 1. Check active locale
        loc_set = self.AFFIRMATIVES.get(self.locale, set())
        if cleaned in loc_set:
            return True
        # 2. Check baseline English
        if cleaned in self.AFFIRMATIVES.get("en", set()):
            return True
        # 3. Check all other locales as universal fallback
        for aff_set in self.AFFIRMATIVES.values():
            if cleaned in aff_set:
                return True
        return False

    def get_prompt_choice_letters(self) -> tuple[str, str]:
        """Return the localized (affirmative, negative) choice letters, e.g. ('y', 'N') or ('s', 'N')."""
        return self.CHOICE_LETTERS.get(self.locale, ("y", "N"))

    def _load_catalog(self) -> dict[str, Any]:
        catalog_path = os.path.join(os.path.dirname(__file__), "translations.json")
        if os.path.exists(catalog_path):
            try:
                with open(catalog_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                print(f"Error loading translations: {e}")
        return {}

    def set_locale(self, locale: str) -> bool:
        norm = self.LANG_MAP.get(locale.lower())
        if norm and norm in self.catalog:
            self.locale = norm
            return True
        return False

    def get_ui_string(self, key: str, default: str | None = None, **kwargs) -> str:
        locale_data = self.catalog.get(self.locale, self.catalog.get("en", {}))
        template = locale_data.get("ui", {}).get(key, default or key)
        try:
            return template.format(**kwargs)
        except Exception:
            return template

    def get_help_string(self, section: str, key: str, default: str | None = None) -> str:
        locale_data = self.catalog.get(self.locale, self.catalog.get("en", {}))
        help_data = locale_data.get("help", {})
        val = help_data.get(section, {}).get(key, default)
        if val is None:
            # Fallback to English
            en_data = self.catalog.get("en", {}).get("help", {})
            val = en_data.get(section, {}).get(key, default or key)
        return val

    def print(self, key: str, default: str | None = None, **kwargs) -> None:
        print(self.get_ui_string(key, default, **kwargs))

    def resolve_command(self, raw_cmd: str) -> str:
        """Resolve a localized slash command alias back to the canonical English command."""
        cmd_lower = raw_cmd.lower()
        # First check the current locale
        locale_aliases = {k.lower(): v for k, v in self.catalog.get(self.locale, {}).get("aliases", {}).items()}
        if cmd_lower in locale_aliases:
            return locale_aliases[cmd_lower]
        # Fallback to checking all locales
        for data in self.catalog.values():
            aliases = {k.lower(): v for k, v in data.get("aliases", {}).items()}
            if cmd_lower in aliases:
                return aliases[cmd_lower]
        return raw_cmd

    def get_reverse_aliases(self) -> dict[str, str]:
        """Return a mapping of localized commands and keywords to their English equivalents."""
        reverse_map = {}
        
        # 1. Add all translations from all locales as a baseline/fallback
        for data in self.catalog.values():
            keywords = data.get("keywords", {})
            for localized, canonical in keywords.items():
                reverse_map[localized.lower()] = canonical
            aliases = data.get("aliases", {})
            for localized, canonical in aliases.items():
                if localized != canonical:
                    reverse_map[localized.lower()] = canonical
                    
        # 2. Override with current locale's specific definitions to preserve priority
        locale_data = self.catalog.get(self.locale, {})
        keywords = locale_data.get("keywords", {})
        for localized, canonical in keywords.items():
            reverse_map[localized.lower()] = canonical
        aliases = locale_data.get("aliases", {})
        for localized, canonical in aliases.items():
            if localized != canonical:
                reverse_map[localized.lower()] = canonical
                
        return reverse_map

    def translate_script(self, script_content: str) -> str:
        """Preprocessing step: translates localized keywords and command verbs into canonical English."""
        reverse_map = self.get_reverse_aliases()
        if not reverse_map:
            return script_content

        translated_lines = []
        lines = script_content.split("\n")
        
        for line in lines:
            stripped = line.lstrip()
            # Skip comments and empty lines
            if not stripped or stripped.startswith("#"):
                translated_lines.append(line)
                continue

            # 1. Translate keywords at start of line (e.g. "establecer var = val" -> "set var = val")
            for localized_kw, canonical_kw in reverse_map.items():
                if not localized_kw.startswith("/"):
                    # Check for exact word start
                    if stripped.startswith(localized_kw + " ") or stripped == localized_kw:
                        line = line.replace(localized_kw, canonical_kw, 1)
                        break

            # 2. Translate slash commands (e.g. "/ayuda" -> "/help")
            words = line.split(maxsplit=1)
            first_word = words[0]
            if first_word.startswith("/"):
                canonical_cmd = self.resolve_command(first_word)
                if canonical_cmd != first_word:
                    line = line.replace(first_word, canonical_cmd, 1)

            translated_lines.append(line)

        return "\n".join(translated_lines)

    def translate_command_string(self, cmd_str: str) -> str:
        """Translates a command string (command verb and its arguments) into canonical English."""
        parts = cmd_str.split(maxsplit=1)
        if not parts:
            return cmd_str
            
        first_word = parts[0]
        if first_word.startswith("/"):
            first_word = self.resolve_command(first_word)
        else:
            reverse_map = self.get_reverse_aliases()
            if first_word.lower() in reverse_map:
                first_word = reverse_map[first_word.lower()]
                
        if len(parts) > 1:
            args = parts[1]
            keywords_map = {}
            for data in self.catalog.values():
                keywords_map.update(data.get("keywords", {}))
            keywords_map.update(self.catalog.get(self.locale, {}).get("keywords", {}))
            
            import re
            pattern = re.compile(r'("[^"\\]*(?:\\.[^"\\]*)*"|\'[^\'\\]*(?:\\.[^\'\\]*)*\'|\S+)')
            tokens = pattern.findall(args)
            translated_tokens = []
            for token in tokens:
                if (token.startswith('"') and token.endswith('"')) or (token.startswith("'") and token.endswith("'")):
                    translated_tokens.append(token)
                else:
                    token_lower = token.lower()
                    if token_lower in keywords_map:
                        translated_tokens.append(keywords_map[token_lower])
                    elif "=" in token:
                        k_part, v_part = token.split("=", 1)
                        k_lower = k_part.lower()
                        v_lower = v_part.lower()
                        k_trans = keywords_map.get(k_lower, k_part)
                        v_trans = keywords_map.get(v_lower, v_part)
                        translated_tokens.append(f"{k_trans}={v_trans}")
                    else:
                        translated_tokens.append(token)
            
            return f"{first_word} {' '.join(translated_tokens)}"
        else:
            return first_word
