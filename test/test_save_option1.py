"""
Tests for Option 1 of the /save command:
- Default saves output only (thinking tags like <think>, <thought>, <thinking> stripped)
- Stripping occurs regardless of app.show_thinking state
- Flags 'withthink' / 'raw' preserve thinking tags
- Flags 'nothink' / 'clean' explicitly strip thinking tags
- 'all' flag respects stripping / withthink modifier
- Multilingual keywords (e.g. conpensar, sanspenser, 含思考, etc.) supported
"""

import os
import pytest
from chatybot.chatybot_app import ChatybotApp


def _make_app(capsys=None):
    app = ChatybotApp()
    app.initialize()
    if capsys is not None:
        capsys.readouterr()
    return app


@pytest.mark.anyio
async def test_save_default_strips_thinking(tmp_path, capsys):
    app = _make_app(capsys)
    # Even if show_thinking is True, /save should default to stripping thinking blocks
    app.show_thinking = True
    app.chat_history = [
        ("What is 2+2?", "<think>Let me calculate: 2 plus 2 equals 4.</think>4"),
    ]

    target_file = str(tmp_path / "output_clean.txt")
    result = await app.handle_escape_command(f"/save {target_file}")
    assert result is True

    assert os.path.exists(target_file)
    with open(target_file, "r") as f:
        content = f.read()

    assert content == "4"
    assert "<think>" not in content
    assert "calculate" not in content


@pytest.mark.anyio
async def test_save_strips_thought_and_thinking_tags(tmp_path, capsys):
    app = _make_app(capsys)
    app.show_thinking = True
    app.chat_history = [
        ("Test tags", "<thought>\nInternal thought\n</thought>\n<thinking>More thinking</thinking>\nFinal Answer"),
    ]

    target_file = str(tmp_path / "output_tags.txt")
    result = await app.handle_escape_command(f"/save {target_file}")
    assert result is True

    with open(target_file, "r") as f:
        content = f.read()

    assert content == "Final Answer"
    assert "<thought>" not in content
    assert "<thinking>" not in content


@pytest.mark.anyio
async def test_save_withthink_and_raw_preserves_thinking(tmp_path, capsys):
    app = _make_app(capsys)
    app.show_thinking = False
    app.chat_history = [
        ("Solve problem", "<think>Detailed step by step reasoning</think>Solution"),
    ]

    # Test withthink
    target_withthink = str(tmp_path / "output_withthink.txt")
    result = await app.handle_escape_command(f"/save {target_withthink} withthink")
    assert result is True
    with open(target_withthink, "r") as f:
        content = f.read()
    assert "<think>Detailed step by step reasoning</think>Solution" == content

    # Test raw
    target_raw = str(tmp_path / "output_raw.txt")
    result = await app.handle_escape_command(f"/save {target_raw} raw")
    assert result is True
    with open(target_raw, "r") as f:
        content = f.read()
    assert "<think>Detailed step by step reasoning</think>Solution" == content


@pytest.mark.anyio
async def test_save_nothink_and_clean_explicit_flags(tmp_path, capsys):
    app = _make_app(capsys)
    app.chat_history = [
        ("Query", "<think>Deep thoughts</think>Response text"),
    ]

    # nothink
    target_nothink = str(tmp_path / "output_nothink.txt")
    result = await app.handle_escape_command(f"/save {target_nothink} nothink")
    assert result is True
    with open(target_nothink, "r") as f:
        content = f.read()
    assert content == "Response text"

    # clean
    target_clean = str(tmp_path / "output_clean2.txt")
    result = await app.handle_escape_command(f"/save {target_clean} clean")
    assert result is True
    with open(target_clean, "r") as f:
        content = f.read()
    assert content == "Response text"


@pytest.mark.anyio
async def test_save_all_default_and_withthink(tmp_path, capsys):
    app = _make_app(capsys)
    app.chat_history = [
        ("Q1", "<think>T1</think>A1"),
        ("Q2", "<thought>T2</thought>A2"),
    ]

    # Save all by default: omits thinking
    target_all_default = str(tmp_path / "all_default.txt")
    result = await app.handle_escape_command(f"/save {target_all_default} all")
    assert result is True
    with open(target_all_default, "r") as f:
        content = f.read()
    assert "A1" in content and "A2" in content
    assert "<think>" not in content
    assert "<thought>" not in content

    # Save all withthink
    target_all_withthink = str(tmp_path / "all_withthink.txt")
    result = await app.handle_escape_command(f"/save {target_all_withthink} all withthink")
    assert result is True
    with open(target_all_withthink, "r") as f:
        content = f.read()
    assert "<think>T1</think>A1" in content
    assert "<thought>T2</thought>A2" in content


@pytest.mark.anyio
async def test_save_multilingual_modifiers(tmp_path, capsys):
    app = _make_app(capsys)
    app.chat_history = [
        ("Hola", "<think>Razonamiento interno</think>Hola mundo"),
    ]

    # conpensar (Spanish withthink)
    target_es = str(tmp_path / "es_withthink.txt")
    await app.handle_escape_command(f"/save {target_es} conpensar")
    with open(target_es, "r") as f:
        assert "<think>Razonamiento interno</think>Hola mundo" == f.read()

    # sinpensar (Spanish nothink)
    target_es_clean = str(tmp_path / "es_clean.txt")
    await app.handle_escape_command(f"/save {target_es_clean} sinpensar")
    with open(target_es_clean, "r") as f:
        assert f.read() == "Hola mundo"

    # 含思考 (Chinese withthink)
    target_zh = str(tmp_path / "zh_withthink.txt")
    await app.handle_escape_command(f"/save {target_zh} 含思考")
    with open(target_zh, "r") as f:
        assert "<think>Razonamiento interno</think>Hola mundo" == f.read()

    # 无思考 (Chinese nothink)
    target_zh_clean = str(tmp_path / "zh_clean.txt")
    await app.handle_escape_command(f"/save {target_zh_clean} 无思考")
    with open(target_zh_clean, "r") as f:
        assert f.read() == "Hola mundo"
