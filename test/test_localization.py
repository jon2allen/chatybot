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
