import pytest
from src.chatybot.localization import LocalizationManager
from src.chatybot.chatybot_app import ChatybotApp

def test_localization_manager_init():
    # Test valid locales and mapping
    mgr_es = LocalizationManager("spanish")
    assert mgr_es.locale == "es"
    
    mgr_it = LocalizationManager("it")
    assert mgr_it.locale == "it"

    mgr_ar = LocalizationManager("levantine")
    assert mgr_ar.locale == "ar"

    mgr_ar_alias = LocalizationManager("apc")
    assert mgr_ar_alias.locale == "ar"

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

    # Arabic resolving
    mgr_ar = LocalizationManager("ar")
    assert mgr_ar.resolve_command("/مساعدة") == "/help"
    assert mgr_ar.resolve_command("/نموذج") == "/model"
    assert mgr_ar.resolve_command("/أداة") == "/tool"

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

    # Arabic preprocessing
    mgr_ar = LocalizationManager("ar")
    script_ar = """# Test script
حط model = "devstral_1"
/نموذج devstral_1
/أداة auto on
/ترديد "marhaba"
"""
    expected_ar = """# Test script
set model = "devstral_1"
/model devstral_1
/tool auto on
/echo "marhaba"
"""
    assert mgr_ar.translate_script(script_ar) == expected_ar

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
    assert "/sesion - Administra la persistencia de sesiones, métricas, notas, exportaciones y depuración" in help_text_es
    assert "/proc - Ejecuta un procedimiento definido con defproc" in help_text_es
    
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


def test_v070_new_features_localization():
    """Verify v0.7.0+ commands, tool, parameters, and subcommands across en, es, fr, zh, it, ar."""
    # 1. English
    mgr_en = LocalizationManager("en")
    assert mgr_en.resolve_command("/context_limit") == "/context_limit"
    assert mgr_en.resolve_command("/auto_truncate") == "/auto_truncate"
    reverse_en = mgr_en.get_reverse_aliases()
    assert reverse_en.get("get_context_metrics") == "get_context_metrics"
    assert reverse_en.get("start_line") == "start_line"
    assert reverse_en.get("end_line") == "end_line"
    assert reverse_en.get("rate_limit") == "rate_limit"
    assert reverse_en.get("detail") == "detail"

    # 2. Spanish
    mgr_es = LocalizationManager("es")
    assert mgr_es.resolve_command("/limite_contexto") == "/context_limit"
    assert mgr_es.resolve_command("/auto_truncar") == "/auto_truncate"
    reverse_es = mgr_es.get_reverse_aliases()
    assert reverse_es.get("obtener_metricas_contexto") == "get_context_metrics"
    assert reverse_es.get("linea_inicio") == "start_line"
    assert reverse_es.get("linea_fin") == "end_line"
    assert reverse_es.get("limite_tasa") == "rate_limit"
    assert reverse_es.get("detalle") == "detail"

    # 3. French
    mgr_fr = LocalizationManager("fr")
    assert mgr_fr.resolve_command("/limite_contexte") == "/context_limit"
    assert mgr_fr.resolve_command("/auto_tronquer") == "/auto_truncate"
    reverse_fr = mgr_fr.get_reverse_aliases()
    assert reverse_fr.get("obtenir_metriques_contexte") == "get_context_metrics"
    assert reverse_fr.get("ligne_debut") == "start_line"
    assert reverse_fr.get("ligne_fin") == "end_line"
    assert reverse_fr.get("limite_taux") == "rate_limit"
    assert reverse_fr.get("details") == "detail"

    # 4. Chinese
    mgr_zh = LocalizationManager("zh")
    assert mgr_zh.resolve_command("/上下文限制") == "/context_limit"
    assert mgr_zh.resolve_command("/自动截断") == "/auto_truncate"
    reverse_zh = mgr_zh.get_reverse_aliases()
    assert reverse_zh.get("获取上下文指标") == "get_context_metrics"
    assert reverse_zh.get("起始行") == "start_line"
    assert reverse_zh.get("结束行") == "end_line"
    assert reverse_zh.get("速率限制") == "rate_limit"
    assert reverse_zh.get("详情") == "detail"

    # 5. Italian
    mgr_it = LocalizationManager("it")
    assert mgr_it.resolve_command("/limite_contesto") == "/context_limit"
    assert mgr_it.resolve_command("/auto_tronca") == "/auto_truncate"
    reverse_it = mgr_it.get_reverse_aliases()
    assert reverse_it.get("ottieni_metriche_contesto") == "get_context_metrics"
    assert reverse_it.get("riga_inizio") == "start_line"
    assert reverse_it.get("riga_fine") == "end_line"
    assert reverse_it.get("limite_frequenza") == "rate_limit"
    assert reverse_it.get("dettaglio") == "detail"

    # 6. Arabic
    mgr_ar = LocalizationManager("ar")
    assert mgr_ar.resolve_command("/حد_السياق") == "/context_limit"
    assert mgr_ar.resolve_command("/اقتطاع_تلقائي") == "/auto_truncate"
    reverse_ar = mgr_ar.get_reverse_aliases()
    assert reverse_ar.get("مقاييس_السياق") == "get_context_metrics"
    assert reverse_ar.get("سطر_البداية") == "start_line"
    assert reverse_ar.get("سطر_النهاية") == "end_line"
    assert reverse_ar.get("حد_المعدل") == "rate_limit"
    assert reverse_ar.get("تفاصيل") == "detail"


def test_v075_features_localization():
    """Verify v0.7.5 /max_tokens and /effort alias resolution across all supported languages."""
    locales_and_effort = {
        "en": ("/effort", "/effort"),
        "es": ("/esfuerzo", "/effort"),
        "fr": ("/effort", "/effort"),
        "zh": ("/推理强度", "/effort"),
        "it": ("/sforzo", "/effort"),
        "ar": ("/جهد", "/effort"),
    }
    locales_and_maxtokens = {
        "en": ("/max_tokens", "/maxtokens"),
        "es": ("/max_tokens", "/maxtokens"),
        "fr": ("/max_jetons", "/maxtokens"),
        "zh": ("/最大Token", "/maxtokens"),
        "it": ("/max_token", "/maxtokens"),
        "ar": ("/أقصى_توكن", "/maxtokens"),
    }

    for loc, (cmd, expected) in locales_and_effort.items():
        mgr = LocalizationManager(loc)
        assert mgr.resolve_command(cmd) == expected, f"Failed for {loc} effort alias {cmd}"

    for loc, (cmd, expected) in locales_and_maxtokens.items():
        mgr = LocalizationManager(loc)
        assert mgr.resolve_command(cmd) == expected, f"Failed for {loc} max_tokens alias {cmd}"


def test_v077_history_keyword_localization():
    """Verify v0.7.7 history keyword mapping across all supported languages."""
    locales_and_history_kws = {
        "en": ["history"],
        "es": ["history", "historial", "historia"],
        "fr": ["history", "historique"],
        "zh": ["history", "历史", "历史记录"],
        "it": ["history", "cronologia", "storia"],
        "ar": ["history", "تاريخ", "سجل"],
    }

    for loc, kws in locales_and_history_kws.items():
        mgr = LocalizationManager(loc)
        rev = mgr.get_reverse_aliases()
        for kw in kws:
            assert rev.get(kw.lower()) == "history", f"Failed for {loc} keyword {kw}"


def test_session_extended_localization():
    """Verify session subcommands and key=value parameter translations across languages."""
    # Spanish
    mgr_es = LocalizationManager("es")
    assert mgr_es.translate_command_string("/sesion descomprimir todo") == "/session uncompress all"
    assert mgr_es.translate_command_string("/sesion listar estado=comprimido") == "/session list status=compressed"
    assert mgr_es.translate_command_string("/sesion depurar mantener=5 dias=30") == "/session prune keep=5 days=30"

    # French
    mgr_fr = LocalizationManager("fr")
    assert mgr_fr.translate_command_string("/session decompresser tous") == "/session uncompress all"
    assert mgr_fr.translate_command_string("/session purger garder=10 jours=60") == "/session prune keep=10 days=60"

    # Chinese
    mgr_zh = LocalizationManager("zh")
    assert mgr_zh.translate_command_string("/会话 解压 全部") == "/session uncompress all"
    assert mgr_zh.translate_command_string("/会话 列表 状态=已压缩") == "/session list status=compressed"
    assert mgr_zh.translate_command_string("/会话 清理 保留=5 天数=14") == "/session prune keep=5 days=14"

    # Italian
    mgr_it = LocalizationManager("it")
    assert mgr_it.translate_command_string("/sessione decomprimi tutti") == "/session uncompress all"
    assert mgr_it.translate_command_string("/sessione pulisci mantieni=3 giorni=7") == "/session prune keep=3 days=7"

    # Arabic
    mgr_ar = LocalizationManager("ar")
    assert mgr_ar.translate_command_string("/جلسة فك_الضغط الكل") == "/session uncompress all"
    assert mgr_ar.translate_command_string("/جلسة عرض وضع=مضغوط") == "/session list status=compressed"
    assert mgr_ar.translate_command_string("/جلسة تنظيف ابقاء=5 ايام=30") == "/session prune keep=5 days=30"


def test_tool_prompt_localization():
    """Verify /tool prompt live_edit and restore translations across all supported languages."""
    test_cases = [
        ("es", "/herramienta prompt restaurar", "/tool prompt restore"),
        ("es", "/herramienta prompt edicion_en_vivo", "/tool prompt live_edit"),
        ("fr", "/outil prompt restaurer", "/tool prompt restore"),
        ("fr", "/outil prompt edition_direct", "/tool prompt live_edit"),
        ("zh", "/工具 prompt 恢复", "/tool prompt restore"),
        ("zh", "/工具 prompt 实时编辑", "/tool prompt live_edit"),
        ("it", "/strumento prompt ripristina", "/tool prompt restore"),
        ("it", "/strumento prompt modifica_live", "/tool prompt live_edit"),
        ("ar", "/أداة prompt استعادة", "/tool prompt restore"),
        ("ar", "/أداة prompt تعديل_مباشر", "/tool prompt live_edit"),
    ]

    for loc, localized_input, expected_cmd in test_cases:
        mgr = LocalizationManager(loc)
        translated = mgr.translate_command_string(localized_input)
        assert translated == expected_cmd, f"Failed for {loc}: '{localized_input}' -> '{translated}', expected '{expected_cmd}'"




