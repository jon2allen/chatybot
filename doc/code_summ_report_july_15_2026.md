# CHATYBOT CLASS ANALYSIS REPORT

**Summary:**
- Total Classes: 30
- Total Methods: 253
- Classes with 0 methods: 9
- Most methods in a class: ChatybotApp (42)
- Fewest methods in a class: Token, TokenType, ChatModelConfig, ImageGenerationSettings, RerankerModelConfig, ProfileMeta (0)

**DETAILED BREAKDOWN:**

## Highly Complex Classes (20+ methods):
1. **ChatybotApp** (42 methods) - `/src/chatybot/chatybot_app.py` [line 66]
2. **ConfigTUI** (24 methods) - `/src/chatybot/config_tui.py`
3. **ToolConfigTUI** (27 methods) - `/src/chatybot/tools/tool_config_tui.py`

## Medium Complexity Classes (11-20 methods):
4. **TParser** (20 methods) - `/src/chatybot/chatdsl_parse.py`
5. **ImageGenerator** (14 methods) - `/src/chatybot/image_generator.py`
6. **CorpusManager** (16 methods) - `/src/chatybot/tinydb1/corpus_manager.py`
7. **HelpSystem** (13 methods) - `/src/chatybot/chaty_help.py`
8. **ProfileManager** (10 methods) - `/src/chatybot/profile_manager.py`

## Small Classes (7-10 methods):
9. **BufferManager** (21 methods) - `/src/chatybot/buffer_manager.py`
10. **ToolsConfig** (7 methods) - `/src/chatybot/tools/tool_config_tui.py`
11. **LoggingManager** (7 methods) - `/src/chatybot/logging_manager.py`
12. **ConfigManager** (7 methods) - `/src/chatybot/config_manager.py`
13. **ProfileEditor** (9 methods) - `/src/chatybot/profile_editor.py`

## Very Small Classes (2-6 methods):
14. **PatternMatcher** (6 methods) - `/src/chatybot/pattern.py`
15. **ImageManager** (4 methods) - `/src/chatybot/image_manager.py`
16. **ScriptVars** (4 methods) - `/src/chatybot/buffer_manager.py`
17. **Tokenizer** (2 methods) - `/src/chatybot/chatdsl_parse.py`
18. **VendorPreset** (1 method) - `/src/chatybot/vendors.py`

## Empty/Skeleton Classes (0 methods):
19. **ParseError** - `/src/chatybot/chatdsl_parse.py` (exception class)
20. **TParser** - `/src/chatybot/chatdsl_parse.py` (interface)
21. **Token** - `/src/chatybot/chatdsl_parse.py` (data class)
22. **TokenType** - `/src/chatybot/chatdsl_parse.py` (enum)
23. **ChatModelConfig** - `/src/chatybot/config_model.py` (empty subclass)
24. **ImageGenerationSettings** - `/src/chatybot/config_model.py` (empty dataclass)
25. **RerankerModelConfig** - `/src/chatybot/config_model.py` (empty subclass)
26. **ProfileMeta** - `/src/chatybot/profile_manager.py` (empty class)

## File Distribution:
- `/src/chatybot/chatybot_app.py`: 42 methods
- `/src/chatybot/tools/tool_config_tui.py`: 29 methods (ToolConfigTUI + ToolsConfig)
- `/src/chatybot/config_tui.py`: 24 methods
- `/src/chatybot/chatdsl_parse.py`: 23 methods (TParser + 3 others)

## Core Functionality Overview:
The ChatybotApp class represents the core application logic, handling UI, scripting, tools, AI integration, and monitoring features. The ConfigTUI and ToolConfigTUI classes handle user interfaces for configuration management.