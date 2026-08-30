"""Tests for Phase 2 migrated commands: image, buffer, and model parameter commands.

Validates that commands migrated to the registry produce identical behavior
to the legacy elif chain, including:
- Image: /imagesize, /imagequality, /listimages, /showimage, /imagedir, /loadimage
- Buffer: /file, /clearfile, /showfile, /filebank1-5, /imagebank1-5
- Models: /model, /temp, /top_p, /top_k, /freq_penalty, /pres_penalty,
  /reasoning, /effort, /thinking, /thoughtstyle, /seed, /stream, /listmodels,
  /system, /context_limit, /auto_truncate, /maxtokens
- i18n alias dispatch for migrated commands
"""

import pytest
from chatybot.commands.registry import registry as default_registry
from chatybot.chatybot_app import ChatybotApp


def _make_app(capsys=None):
    app = ChatybotApp()
    app.initialize()
    if capsys is not None:
        capsys.readouterr()
    return app


# ---------------------------------------------------------------------------
# Registry coverage
# ---------------------------------------------------------------------------

def test_all_migrated_commands_registered():
    expected = [
        "/echo",
        "/imagine", "/saveimage", "/imagesize", "/imagequality",
        "/imagedir", "/listimages", "/showimage", "/loadimage",
        "/file", "/clearfile", "/showfile",
        "/filebank1", "/filebank2", "/filebank3", "/filebank4", "/filebank5",
        "/imagebank1", "/imagebank2", "/imagebank3", "/imagebank4", "/imagebank5",
        "/model", "/system", "/temp", "/maxtokens", "/max_tokens",
        "/context_limit", "/auto_truncate",
        "/top_p", "/top_k", "/freq_penalty", "/pres_penalty",
        "/reasoning", "/effort", "/thinking", "/thoughtstyle",
        "/seed", "/stream", "/listmodels",
    ]
    for name in expected:
        assert default_registry.has(name), f"{name} not registered"


# ---------------------------------------------------------------------------
# Image commands
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_imagesize_no_arg(capsys):
    app = _make_app(capsys)
    await app.handle_escape_command("/imagesize")
    out = capsys.readouterr().out
    assert "Current image size:" in out


@pytest.mark.anyio
async def test_imagesize_set(capsys):
    app = _make_app(capsys)
    await app.handle_escape_command("/imagesize 512x512")
    out = capsys.readouterr().out
    assert "512x512" in out
    assert app.image_size == "512x512"
    assert app.image_size_manual is True


@pytest.mark.anyio
async def test_imagequality_no_arg(capsys):
    app = _make_app(capsys)
    await app.handle_escape_command("/imagequality")
    out = capsys.readouterr().out
    assert "Current image quality:" in out


@pytest.mark.anyio
async def test_imagequality_set(capsys):
    app = _make_app(capsys)
    await app.handle_escape_command("/imagequality hd")
    out = capsys.readouterr().out
    assert "hd" in out
    assert app.image_quality == "hd"


@pytest.mark.anyio
async def test_listimages(capsys):
    app = _make_app(capsys)
    result = await app.handle_escape_command("/listimages")
    assert result is True


@pytest.mark.anyio
async def test_showimage_no_arg(capsys):
    app = _make_app(capsys)
    await app.handle_escape_command("/showimage")
    out = capsys.readouterr().out
    assert "Usage:" in out


@pytest.mark.anyio
async def test_showimage_not_found(capsys):
    app = _make_app(capsys)
    await app.handle_escape_command("/showimage nonexistent.png")
    out = capsys.readouterr().out
    assert "Image not found" in out


@pytest.mark.anyio
async def test_imagine_no_arg(capsys):
    app = _make_app(capsys)
    await app.handle_escape_command("/imagine")
    out = capsys.readouterr().out
    assert "Usage: /imagine" in out
    assert "Current settings:" in out


@pytest.mark.anyio
async def test_loadimage_no_arg(capsys):
    app = _make_app(capsys)
    await app.handle_escape_command("/loadimage")
    out = capsys.readouterr().out
    assert "Usage: /loadimage" in out


@pytest.mark.anyio
async def test_loadimage_invalid_bank(capsys):
    app = _make_app(capsys)
    await app.handle_escape_command("/loadimage some.png badbank")
    out = capsys.readouterr().out
    assert "Invalid imagebank" in out


# ---------------------------------------------------------------------------
# Buffer commands
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_file_no_arg(capsys):
    app = _make_app(capsys)
    await app.handle_escape_command("/file")
    out = capsys.readouterr().out
    assert "Usage: /file" in out


@pytest.mark.anyio
async def test_clearfile(capsys):
    app = _make_app(capsys)
    result = await app.handle_escape_command("/clearfile")
    assert result is True


@pytest.mark.anyio
async def test_showfile(capsys):
    app = _make_app(capsys)
    result = await app.handle_escape_command("/showfile")
    assert result is True


@pytest.mark.anyio
async def test_filebank_no_arg(capsys):
    app = _make_app(capsys)
    await app.handle_escape_command("/filebank1")
    out = capsys.readouterr().out
    assert "Usage:" in out
    assert "/filebank1" in out


@pytest.mark.anyio
async def test_filebank_invalid_number(capsys):
    """Invalid filebank number should print error (falls through to legacy prefix match)."""
    app = _make_app(capsys)
    # /filebank9 is not registered in the registry (only 1-5), so it falls
    # through to the legacy chain which no longer has the prefix match.
    # It should return False (unhandled).
    result = await app.handle_escape_command("/filebank9")
    # Since the legacy prefix match was removed, this is unhandled -> False
    assert result is False


@pytest.mark.anyio
async def test_filebank_clear(capsys):
    app = _make_app(capsys)
    result = await app.handle_escape_command("/filebank1 clear")
    assert result is True


@pytest.mark.anyio
async def test_imagebank_no_arg(capsys):
    app = _make_app(capsys)
    await app.handle_escape_command("/imagebank1")
    out = capsys.readouterr().out
    assert "Usage:" in out
    assert "/imagebank1" in out


@pytest.mark.anyio
async def test_imagebank_clear(capsys):
    app = _make_app(capsys)
    result = await app.handle_escape_command("/imagebank1 clear")
    assert result is True


# ---------------------------------------------------------------------------
# Model parameter commands
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_model_no_arg(capsys):
    app = _make_app(capsys)
    await app.handle_escape_command("/model")
    out = capsys.readouterr().out
    assert "Current model:" in out


@pytest.mark.anyio
async def test_temp_no_arg(capsys):
    app = _make_app(capsys)
    await app.handle_escape_command("/temp")
    out = capsys.readouterr().out
    assert "Current temperature:" in out


@pytest.mark.anyio
async def test_temp_set(capsys):
    app = _make_app(capsys)
    await app.handle_escape_command("/temp 0.5")
    out = capsys.readouterr().out
    assert "0.5" in out
    assert app.temperature == 0.5


@pytest.mark.anyio
async def test_temp_invalid(capsys):
    app = _make_app(capsys)
    await app.handle_escape_command("/temp abc")
    out = capsys.readouterr().out
    assert "Invalid temperature" in out


@pytest.mark.anyio
async def test_temp_default(capsys):
    app = _make_app(capsys)
    app.temperature = 0.8
    await app.handle_escape_command("/temp default")
    out = capsys.readouterr().out
    assert "reset to model default" in out
    assert app.temperature is None


@pytest.mark.anyio
async def test_top_p_no_arg(capsys):
    app = _make_app(capsys)
    await app.handle_escape_command("/top_p")
    out = capsys.readouterr().out
    assert "Current top_p:" in out


@pytest.mark.anyio
async def test_top_p_set(capsys):
    app = _make_app(capsys)
    await app.handle_escape_command("/top_p 0.9")
    out = capsys.readouterr().out
    assert "0.9" in out
    assert app.top_p == 0.9


@pytest.mark.anyio
async def test_top_p_off(capsys):
    app = _make_app(capsys)
    await app.handle_escape_command("/top_p off")
    out = capsys.readouterr().out
    assert "disabled" in out
    assert app.top_p == "off"


@pytest.mark.anyio
async def test_top_k_no_arg(capsys):
    app = _make_app(capsys)
    await app.handle_escape_command("/top_k")
    out = capsys.readouterr().out
    assert "Current top_k:" in out


@pytest.mark.anyio
async def test_top_k_set(capsys):
    app = _make_app(capsys)
    await app.handle_escape_command("/top_k 40")
    out = capsys.readouterr().out
    assert "40" in out
    assert app.top_k == 40


@pytest.mark.anyio
async def test_freq_penalty_no_arg(capsys):
    app = _make_app(capsys)
    await app.handle_escape_command("/freq_penalty")
    out = capsys.readouterr().out
    assert "Current frequency penalty:" in out


@pytest.mark.anyio
async def test_freq_penalty_set(capsys):
    app = _make_app(capsys)
    await app.handle_escape_command("/freq_penalty 0.5")
    out = capsys.readouterr().out
    assert "0.5" in out
    assert app.freq_penalty == 0.5


@pytest.mark.anyio
async def test_pres_penalty_no_arg(capsys):
    app = _make_app(capsys)
    await app.handle_escape_command("/pres_penalty")
    out = capsys.readouterr().out
    assert "Current presence penalty:" in out


@pytest.mark.anyio
async def test_pres_penalty_set(capsys):
    app = _make_app(capsys)
    await app.handle_escape_command("/pres_penalty 0.3")
    out = capsys.readouterr().out
    assert "0.3" in out
    assert app.pres_penalty == 0.3


@pytest.mark.anyio
async def test_reasoning_toggle(capsys):
    app = _make_app(capsys)
    app.reasoning_mode = False
    await app.handle_escape_command("/reasoning on")
    out = capsys.readouterr().out
    assert "ON" in out
    assert app.reasoning_mode is True

    await app.handle_escape_command("/reasoning off")
    out = capsys.readouterr().out
    assert "OFF" in out
    assert app.reasoning_mode is False


@pytest.mark.anyio
async def test_reasoning_status(capsys):
    app = _make_app(capsys)
    app.reasoning_mode = True
    await app.handle_escape_command("/reasoning")
    out = capsys.readouterr().out
    assert "currently" in out.lower()
    assert "ON" in out


@pytest.mark.anyio
async def test_thinking_toggle(capsys):
    app = _make_app(capsys)
    app.show_thinking = False
    await app.handle_escape_command("/thinking on")
    out = capsys.readouterr().out
    assert "ON" in out
    assert app.show_thinking is True


@pytest.mark.anyio
async def test_thoughtstyle_set(capsys):
    app = _make_app(capsys)
    await app.handle_escape_command("/thoughtstyle gemma4")
    out = capsys.readouterr().out
    assert "gemma4" in out
    assert app.thoughtstyle == "gemma4"


@pytest.mark.anyio
async def test_thoughtstyle_invalid(capsys):
    app = _make_app(capsys)
    await app.handle_escape_command("/thoughtstyle bogus")
    out = capsys.readouterr().out
    assert "Invalid thought style" in out


@pytest.mark.anyio
async def test_seed_no_arg(capsys):
    app = _make_app(capsys)
    await app.handle_escape_command("/seed")
    out = capsys.readouterr().out
    assert "Current seed setting:" in out


@pytest.mark.anyio
async def test_seed_set_int(capsys):
    app = _make_app(capsys)
    await app.handle_escape_command("/seed 42")
    out = capsys.readouterr().out
    assert "42" in out
    assert app.seed_config == 42


@pytest.mark.anyio
async def test_seed_clear(capsys):
    app = _make_app(capsys)
    app.seed_config = 42
    await app.handle_escape_command("/seed clear")
    out = capsys.readouterr().out
    assert "cleared" in out
    assert app.seed_config is None


@pytest.mark.anyio
async def test_seed_time(capsys):
    app = _make_app(capsys)
    await app.handle_escape_command("/seed time")
    out = capsys.readouterr().out
    assert "time" in out
    assert app.seed_config == "time"


@pytest.mark.anyio
async def test_seed_random(capsys):
    app = _make_app(capsys)
    await app.handle_escape_command("/seed random 1,999")
    out = capsys.readouterr().out
    assert "random range" in out
    assert app.seed_config == ("random", 1, 999)


@pytest.mark.anyio
async def test_seed_invalid(capsys):
    app = _make_app(capsys)
    await app.handle_escape_command("/seed abc")
    out = capsys.readouterr().out
    assert "Invalid seed" in out


@pytest.mark.anyio
async def test_stream_toggle(capsys):
    app = _make_app(capsys)
    initial = app.streaming_enabled
    await app.handle_escape_command("/stream")
    out = capsys.readouterr().out
    assert app.streaming_enabled == (not initial)
    assert "Streaming responses" in out


@pytest.mark.anyio
async def test_listmodels(capsys):
    app = _make_app(capsys)
    result = await app.handle_escape_command("/listmodels")
    assert result is True


@pytest.mark.anyio
async def test_system_no_arg(capsys):
    app = _make_app(capsys)
    await app.handle_escape_command("/system")
    out = capsys.readouterr().out
    assert "Current system message:" in out


@pytest.mark.anyio
async def test_system_set(capsys):
    app = _make_app(capsys)
    await app.handle_escape_command("/system You are helpful")
    out = capsys.readouterr().out
    assert "System message updated" in out
    assert "You are helpful" in app.config_manager.system_message


@pytest.mark.anyio
async def test_context_limit_no_arg(capsys):
    app = _make_app(capsys)
    await app.handle_escape_command("/context_limit")
    out = capsys.readouterr().out
    assert "Context limit" in out


@pytest.mark.anyio
async def test_context_limit_set(capsys):
    app = _make_app(capsys)
    await app.handle_escape_command("/context_limit 8192")
    out = capsys.readouterr().out
    assert "8192" in out


@pytest.mark.anyio
async def test_context_limit_off(capsys):
    app = _make_app(capsys)
    await app.handle_escape_command("/context_limit off")
    out = capsys.readouterr().out
    assert "disabled" in out


@pytest.mark.anyio
async def test_auto_truncate_no_arg(capsys):
    app = _make_app(capsys)
    await app.handle_escape_command("/auto_truncate")
    out = capsys.readouterr().out
    assert "Auto-truncation" in out


@pytest.mark.anyio
async def test_auto_truncate_on(capsys):
    app = _make_app(capsys)
    await app.handle_escape_command("/auto_truncate on")
    out = capsys.readouterr().out
    assert "enabled" in out


@pytest.mark.anyio
async def test_auto_truncate_off(capsys):
    app = _make_app(capsys)
    await app.handle_escape_command("/auto_truncate off")
    out = capsys.readouterr().out
    assert "disabled" in out


@pytest.mark.anyio
async def test_maxtokens_no_arg(capsys):
    app = _make_app(capsys)
    await app.handle_escape_command("/maxtokens")
    out = capsys.readouterr().out
    assert "Current max tokens:" in out


@pytest.mark.anyio
async def test_maxtokens_set(capsys):
    app = _make_app(capsys)
    await app.handle_escape_command("/maxtokens 4096")
    out = capsys.readouterr().out
    assert "4096" in out
    assert app.config_manager.max_tokens == 4096


@pytest.mark.anyio
async def test_max_tokens_alias(capsys):
    """Both /maxtokens and /max_tokens should work."""
    app = _make_app(capsys)
    await app.handle_escape_command("/max_tokens 2048")
    out = capsys.readouterr().out
    assert "2048" in out
    assert app.config_manager.max_tokens == 2048


# ---------------------------------------------------------------------------
# i18n alias dispatch for migrated commands
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_model_spanish_alias(capsys):
    app = ChatybotApp(lang="spanish")
    app.initialize()
    capsys.readouterr()
    result = await app.handle_escape_command("/modelo")
    assert result is True
    out = capsys.readouterr().out
    assert "Current model:" in out or "modelo" in out.lower()


@pytest.mark.anyio
async def test_temp_spanish_alias(capsys):
    """Spanish alias /temperatura does not exist; /temp is canonical in all locales.
    Verify /temp dispatches correctly in Spanish mode."""
    app = ChatybotApp(lang="spanish")
    app.initialize()
    capsys.readouterr()
    await app.handle_escape_command("/temp")
    out = capsys.readouterr().out
    assert "Current temperature:" in out


@pytest.mark.anyio
async def test_filebank_spanish_alias(capsys):
    app = ChatybotApp(lang="spanish")
    app.initialize()
    capsys.readouterr()
    await app.handle_escape_command("/banco_arch1")
    out = capsys.readouterr().out
    assert "Usage:" in out


@pytest.mark.anyio
async def test_stream_spanish_alias(capsys):
    """Spanish alias /flujo does not exist; /stream is canonical in all locales.
    Verify /stream toggles correctly in Spanish mode."""
    app = ChatybotApp(lang="spanish")
    app.initialize()
    capsys.readouterr()
    initial = app.streaming_enabled
    await app.handle_escape_command("/stream")
    assert app.streaming_enabled == (not initial)
