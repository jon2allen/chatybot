import pytest
from src.chatybot.localization import LocalizationManager
from src.chatybot.chatybot_app import ChatybotApp

def test_localization_manager_init():
    # Test valid locales and mapping
    mgr_es = LocalizationManager("spanish")
    assert mgr_es.locale == "es"
    
    mgr_it = LocalizationManager("it")
    assert mgr_it.locale == "it"

    # Test fallback for unknown language
    mgr_unknown = LocalizationManager("german")
    assert mgr_unknown.locale == "en"

def test_resolve_command_alias():
    # Spanish resolving
    mgr_es = LocalizationManager("es")
    assert mgr_es.resolve_command("/ayuda") == "/help"
    assert mgr_es.resolve_command("/modelo") == "/model"
    assert mgr_es.resolve_command("/herramienta") == "/tool"
    assert mgr_es.resolve_command("/nonexistent") == "/nonexistent"

    # French resolving
    mgr_fr = LocalizationManager("fr")
    assert mgr_fr.resolve_command("/aide") == "/help"
    assert mgr_fr.resolve_command("/modele") == "/model"
    assert mgr_fr.resolve_command("/outil") == "/tool"

    # Chinese resolving
    mgr_zh = LocalizationManager("zh")
    assert mgr_zh.resolve_command("/帮助") == "/help"
    assert mgr_zh.resolve_command("/模型") == "/model"
    assert mgr_zh.resolve_command("/工具") == "/tool"

    # Italian resolving
    mgr_it = LocalizationManager("it")
    assert mgr_it.resolve_command("/aiuto") == "/help"
    assert mgr_it.resolve_command("/modello") == "/model"
    assert mgr_it.resolve_command("/strumento") == "/tool"

def test_translate_script_preprocessor():
    # Spanish preprocessing
    mgr_es = LocalizationManager("es")
    script_es = """# Test script
establecer model = "devstral_1"
/modelo devstral_1
/herramienta auto activar
/repetir "hola"
"""
    expected_es = """# Test script
set model = "devstral_1"
/model devstral_1
/tool auto activar
/echo "hola"
"""
    assert mgr_es.translate_script(script_es) == expected_es

    # French preprocessing
    mgr_fr = LocalizationManager("fr")
    script_fr = """# Test script
definir model = "devstral_1"
/modele devstral_1
/outil auto on
/echo "bonjour"
"""
    expected_fr = """# Test script
set model = "devstral_1"
/model devstral_1
/tool auto on
/echo "bonjour"
"""
    assert mgr_fr.translate_script(script_fr) == expected_fr

    # Chinese preprocessing
    mgr_zh = LocalizationManager("zh")
    script_zh = """# Test script
设置 model = "devstral_1"
/模型 devstral_1
/工具 auto on
/回显 "你好"
"""
    expected_zh = """# Test script
set model = "devstral_1"
/model devstral_1
/tool auto on
/echo "你好"
"""
    assert mgr_zh.translate_script(script_zh) == expected_zh

    # Italian preprocessing
    mgr_it = LocalizationManager("it")
    script_it = """# Test script
imposta model = "devstral_1"
/modello devstral_1
/strumento auto on
/eco "ciao"
"""
    expected_it = """# Test script
set model = "devstral_1"
/model devstral_1
/tool auto on
/echo "ciao"
"""
    assert mgr_it.translate_script(script_it) == expected_it

@pytest.mark.anyio
async def test_app_integration_localized_command():
    # Test that ChatybotApp correctly handles localized command strings
    app = ChatybotApp(lang="spanish")
    app.initialize()
    
    # Resolving command inside handle_escape_command
    # We test that "/ayuda" executes the help logic (we mock show_help or check it returns True)
    assert await app.handle_escape_command("/ayuda") is True
    assert await app.handle_escape_command("/modelo") is True
    assert await app.handle_escape_command("/modelo devstral_1") is True

def test_help_localization():
    from src.chatybot.chaty_help import get_help_system
    help_sys = get_help_system()
    mgr_es = LocalizationManager("spanish")
    
    # 1. Full Help List Localization
    help_text_es = help_sys.get_help_text(None, i18n=mgr_es)
    assert "SISTEMA:" in help_text_es
    assert "/ayuda - Muestra este mensaje de ayuda" in help_text_es
    assert "ARCHIVO:" in help_text_es
    assert "/archivo - Carga un archivo de texto en el búfer" in help_text_es
    
    # 2. Detailed Command Help Localization (with localized search)
    detail_es = help_sys.get_help_text("/archivo", i18n=mgr_es)
    assert "Categoría: Archivo" in detail_es
    assert "Uso: /archivo <path>" in detail_es
    assert "Carga un archivo de texto en el búfer" in detail_es
    
    # 3. Fallback: English search "/file" in Spanish mode resolves and outputs Spanish
    detail_fallback = help_sys.get_help_text("/file", i18n=mgr_es)
    assert "Categoría: Archivo" in detail_fallback
    assert "Uso: /archivo <path>" in detail_fallback
    assert "Carga un archivo de texto en el búfer" in detail_fallback

def test_cross_locale_fallback():
    # Test that English/default locale can resolve and translate Chinese commands
    mgr_en = LocalizationManager("en")
    
    # 1. Resolve Chinese command in English manager
    assert mgr_en.resolve_command("/模型") == "/model"
    assert mgr_en.resolve_command("/保存") == "/save"
    assert mgr_en.resolve_command("/回显") == "/echo"
    
    # 2. Translate Chinese command string in English manager
    assert mgr_en.translate_command_string("/模型 mistral_1") == "/model mistral_1"
    assert mgr_en.translate_command_string("/保存 file.txt") == "/save file.txt"
    assert mgr_en.translate_command_string("/回显 \"hello\"") == "/echo \"hello\""
    
    # 3. Translate script with Chinese keywords/commands in English manager
    script = "设置 model = \"mistral_1\"\n/模型 mistral_1\n/保存 file.txt"
    expected = "set model = \"mistral_1\"\n/model mistral_1\n/save file.txt"
    assert mgr_en.translate_script(script) == expected
