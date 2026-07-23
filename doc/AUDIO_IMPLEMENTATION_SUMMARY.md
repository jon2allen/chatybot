# Audio Implementation Summary for Chatybot

**Status**: Core Infrastructure Complete  
**Version**: 1.0  
**Date**: 2025  
**Based on**: AUDIO_IMPLEMENTATION_PLAN_v2.md

---

## Overview

This document summarizes the implementation of audio transcription (STT) and text-to-speech (TTS) support for Chatybot, following the comprehensive plan outlined in AUDIO_IMPLEMENTATION_PLAN_v2.md.

## Architecture

The implementation follows a **modular architecture** that mirrors the existing image generation system, with all models defined in `chat_config.toml`:

```
src/chatybot/
├── audio_engine.py              # Main orchestrator
├── audio_provider.py            # Base provider interface and registry
├── audio_file_manager.py        # File storage, naming, index.json management
├── audio_providers/              # Provider implementations
│   ├── __init__.py
│   ├── base.py                  # Base provider class
│   └── openai_provider.py       # OpenAI STT/TTS provider
├── buffer_manager.py            # Updated with audio banks and variables
├── chatdsl_parse.py             # Updated with audio commands
├── chatybot_app.py              # Updated with audio command handlers
└── config_manager.py            # Updated with audio configuration
```

## Files Created/Modified

### New Files Created
1. **`src/chatybot/audio_provider.py`** - 370+ lines
   - `AudioCapability` enum (STT, TTS, VOICE_CLONING, MUSIC_GENERATION, etc.)
   - `AudioFormat` enum (MP3, WAV, FLAC, OGG, etc.)
   - `AudioModelConfig` dataclass for model configuration
   - `AudioProvider` abstract base class
   - `AudioModelRegistry` class for managing audio models from config
   - Global `audio_model_registry` instance

2. **`src/chatybot/audio_file_manager.py`** - 600+ lines
   - `AudioFileManager` class with date-based directory structure
   - Counter persistence via `index.json` files
   - File saving with metadata (.meta.json)
   - Support for generate (speech, sfx, music) and analyze (transcript, recognition) categories
   - Audio variable detection and base64 encoding

3. **`src/chatybot/audio_engine.py`** - 850+ lines
   - `AudioResult` dataclass for operation results
   - `AudioEngine` main orchestrator class
   - Methods: `transcribe()`, `text_to_speech()`, `generate_audio()`, `recognize_sound()`, `audialize()`
   - Capability detection, model listing, file listing

4. **`src/chatybot/audio_providers/__init__.py`** - Package initialization

5. **`src/chatybot/audio_providers/base.py`** - Base provider with aiohttp support

6. **`src/chatybot/audio_providers/openai_provider.py`** - OpenAI STT/TTS implementation

### Files Modified

1. **`src/chatybot/chat_config.toml`**
   - Added `[audio]` section with settings
   - Added audio model definitions for:
     - STT: voxtral-mini-3b, voxtral-small-24b, voxtral-mini-4b-realtime, voxtral-transcribe-2, gpt-4o-transcribe, whisper-1, canary-qwen-2.5b, firered-asr
     - TTS: voxtral-tts, gpt-4o-mini-tts, tts-1-hd, parler-tts-md-beat, coqui-tts, fish-speech-v1-5, qwen3-tts-1.7b
     - Music/SFX: stable-audio-2.5, musicgen-small, diffrhythm

2. **`src/chatybot/buffer_manager.py`**
   - Added `audio_banks` dictionary (audiobank1-5)
   - Added audio bank methods: `load_audio_to_bank()`, `clear_audio_bank()`, `show_audio_bank()`
   - Added audio variable helpers: `is_audio_variable()`, `get_audio_format_from_variable()`
   - Updated `replace_placeholders()` to handle audio banks

3. **`src/chatybot/chatdsl_parse.py`**
   - Added audio commands to `VALID_ESCAPE_COMMANDS`:
     - `audialize`, `transcribe`, `transcribemirror`
     - `audiocap`, `audiomodel`, `audiodir`, `listaudio`
     - `loadaudio`, `play`, `audiobank`
     - `audiobank1` through `audiobank5`, `audiomirror`

4. **`src/chatybot/chatybot_app.py`**
   - Added `audio_engine` initialization in `__init__()` and `initialize()`
   - Added complete audio command handlers in `handle_escape_command()`:
     - `/audiobank1-5`, `/audiobank` (list/clear/show/load)
     - `/transcribe` with options parsing
     - `/transcribemirror` for variable capture
     - `/audiomirror` for audio variable capture
     - `/audialize` with action parsing
     - `/audiocap` for capability detection
     - `/audiomodel` for model listing
     - `/audiodir` for directory management
     - `/listaudio` with filtering
     - `/loadaudio` for external file loading
     - `/play` with platform-specific playback
   - Enhanced `/model` command to support audio models
   - Updated help text with audio commands
   - Added tab completion for audio commands

5. **`src/chatybot/config_manager.py`**
   - Added audio configuration loading (`audio_dir`, `audio_format`, `audio_stt_model`, `audio_tts_model`)
   - Added `get_audio_config()` and `get_audio_models_config()` methods

---

## Model Configuration (chat_config.toml)

All audio models are defined in `chat_config.toml` under `[audio.models.*]` with the following structure:

```toml
[audio.models.voxtral-mini-3b]
name = "Voxtral Mini 3B"
provider = "mistralai"
type = "stt"
description = "State-of-the-art multilingual STT"
huggingface_id = "mistralai/Voxtral-Mini-3B-2507"
requires_api_key = false
license = "Apache 2.0"
capabilities = ["stt", "transcription", "multilingual"]
max_audio_length = 40
vram_bf16 = "9.5 GB"
vram_int4 = "3.7-4 GB"
is_default = true
```

### Configured Models

#### STT Models (10 models)
- **Mistral Voxtral**: voxtral-mini-3b (default), voxtral-small-24b, voxtral-mini-4b-realtime, voxtral-transcribe-2
- **OpenAI**: gpt-4o-transcribe, whisper-1
- **Chinese**: canary-qwen-2.5b, firered-asr

#### TTS Models (8 models)
- **Mistral Voxtral**: voxtral-tts (with zero-shot voice cloning)
- **OpenAI**: gpt-4o-mini-tts, tts-1-hd
- **Local**: parler-tts-md-beat, coqui-tts
- **Chinese**: fish-speech-v1-5, qwen3-tts-1.7b

#### Music/SFX Models (3 models)
- **Stability AI**: stable-audio-2.5
- **Local**: musicgen-small, diffrhythm

---

## Commands

### Core Audio Commands

| Command | Syntax | Description |
|---------|--------|-------------|
| `/audialize` | `/audialize "<action>: <content>" [options]` | Unified audio command |
| `/transcribe` | `/transcribe <file> [options]` | Speech-to-text transcription |
| `/transcribemirror` | `/transcribemirror <var>` | Save transcription to variable |
| `/audiomirror` | `/audiomirror <var>` | Save audio to variable (base64) |
| `/audiocap` | `/audiocap` | Show audio capabilities |
| `/audiomodel` | `/audiomodel` | List available audio models |
| `/audiodir` | `/audiodir [path]` | Get/set audio directory |
| `/listaudio` | `/listaudio [filter]` | List audio files |
| `/loadaudio` | `/loadaudio <file> [var]` | Load external audio |
| `/play` | `/play <file\|var> [volume=X]` | Play audio file or variable |
| `/audiobank` | `/audiobank` | List all audio banks |
| `/audiobank1-5` | `/audiobank1 <file\|clear\|show>` | Manage audio banks |
| `/model` | `/model <audio_model_alias>` | Set active audio model |

### Action Types for `/audialize`

| Action | Aliases | Description |
|--------|---------|-------------|
| speak | tts, say | Text-to-speech |
| transcribe | stt, to_text | Speech-to-text |
| generate | sfx, sound, effect | Sound effect generation |
| music | song, compose | Music generation |
| analyze | describe | Audio description |
| recognize | classify, identify, detect | Sound recognition |
| separate | split, isolate | Source separation |

### Options (varies by action)

**STT Options:**
- `model=X` - Use specific STT model
- `language=XX` - Language hint (en, fr, de, etc.)
- `diarization=true` - Enable speaker diarization
- `timestamps=true` - Include word timestamps

**TTS Options:**
- `model=X` - Use specific TTS model
- `voice=X` - Voice name (e.g., alloy, echo, fable)
- `speed=1.0` - Speed multiplier (0.5-2.0)
- `pitch=1.0` - Pitch multiplier
- `format=mp3` - Output format

**Filter Options (for /listaudio):**
- `date=YYYY-MM-DD` - Filter by date
- `category=generate\|analyze` - Filter by category
- `subtype=speech\|sfx\|music\|transcript` - Filter by subtype
- `format=mp3\|wav\|...` - Filter by format

---

## Directory Structure

Audio files are stored following the image pattern:

```
~/chatybot_audio/
├── 2025-01-15/
│   ├── generate/
│   │   ├── speech_001.mp3          # TTS output
│   │   ├── speech_001.meta.json    # Metadata + base64
│   │   ├── sfx_001.mp3             # Sound effect
│   │   ├── sfx_001.meta.json
│   │   └── music_001.mp3            # Generated music
│   │
│   ├── analyze/
│   │   ├── transcript_001.json     # Transcription result
│   │   └── recognition_001.json    # Sound recognition result
│   │
│   └── index.json                 # Counter persistence
└── 2025-01-16/
    └── ...
```

### index.json Format
```json
{
  "date": "2025-01-15",
  "counters": {
    "generate": {"speech": 1, "sfx": 1, "music": 1},
    "analyze": {"transcript": 1}
  },
  "models_used": ["voxtral-tts", "voxtral-mini-3b"],
  "total_files": 4,
  "total_size_mb": 12.5
}
```

### Audio File Metadata (.meta.json)
```json
{
  "filename": "speech_001.mp3",
  "category": "generate",
  "subtype": "speech",
  "format": "mp3",
  "prompt": "Hello world",
  "model": "voxtral-tts",
  "provider": "mistralai",
  "sample_rate": 44100,
  "channels": 1,
  "duration": 2.5,
  "bitrate": 128000,
  "size_bytes": 320000,
  "base64": "data:audio/mp3;base64,SUQzBA...",
  "created": "2025-01-15T14:30:22Z"
}
```

---

## ChatDSL Integration

Audio commands can be used in ChatDSL scripts:

```chatdsl
# Set audio model
model voxtral-tts

# Generate speech
audialize "speak: Hello, welcome to chatybot"
audiomirror greeting

# Play greeting
play [greeting]

# Transcribe audio
transcribe user_input.wav language=en
transcribemirror user_text

echo You said: [user_text]

# Load audio into bank
audiobank1 load notification.wav

# Use audio bank in prompt
prompt Describe the sound in {audiobank1}

# Conditional audio
if: [user_text] contains "hello"
    audialize "speak: Hello there!"
    play last
endif
```

---

## Audio Variable Format

Audio data is stored in variables using **base64 encoding with MIME type prefix**, matching the image pattern:

```
data:audio/mp3;base64,SUQzBAAAAA...\
```

- **STT** (`/transcribe`, `/transcribemirror`): Produces **plain text strings**
- **TTS/Generation** (`/audialize`, `/audiomirror`): Produces **base64 data URLs**

### Variable Detection

```python
# In buffer_manager.py
buffer_manager.is_audio_variable(var_value)  # Check if starts with 'data:audio/'
buffer_manager.get_audio_format_from_variable(var_value)  # Extract 'mp3', 'wav', etc.
buffer_manager.get_audio_bytes_from_variable(var_value)  # Extract raw bytes
```

---

## Capability Detection

The `/audiocap` command reports available capabilities:

```json
{
  "audio_capable": true,
  "capabilities": {
    "stt": {
      "available": true,
      "models": ["voxtral-mini-3b", "gpt-4o-transcribe", ...],
      "realtime": true,
      "multilingual": true,
      "diarization": true
    },
    "tts": {
      "available": true,
      "models": ["voxtral-tts", "gpt-4o-mini-tts", ...],
      "voice_cloning": true,
      "multilingual": true
    },
    "music": {"available": true, "models": [...]},
    "sfx": {"available": true, "models": [...]},
    "recognition": {"available": true, "models": [...]}
  }
}
```

---

## Provider Architecture

The system uses a **provider-based architecture** for extensibility:

```python
# Base class
class AudioProvider(ABC):
    async def process(self, input_data, options) -> Dict[str, Any]: ...

# Specific implementations
class OpenAIAudioProvider(AudioProvider):
    async def process(self, input_data, options):
        if self.config.model_type == "stt":
            return await self._transcribe(input_data, options)
        elif self.config.model_type == "tts":
            return await self._text_to_speech(input_data, options)

# Future implementations
class VoxtralProvider(AudioProvider): ...
class LocalProvider(AudioProvider): ...
```

### Current Provider Status

| Provider | STT | TTS | Status |
|----------|-----|-----|--------|
| OpenAI | ✅ | ✅ | Implemented |
| Voxtral (Mistral) | ⏳ | ⏳ | Stub (needs transformers integration) |
| Local (Parler, etc.) | ⏳ | ⏳ | Stub |
| Stability AI | ⏳ | ⏳ | Not yet implemented |

---

## Dependencies

### Python Packages
```bash
pip install aiohttp  # Already in requirements
```

### Local Model Requirements
```bash
# Voxtral STT (transformers)
pip install transformers torch sentencepiece accelerate

# Voxtral TTS (transformers)
pip install transformers torch sentencepiece accelerate soundfile

# Parler-TTS
pip install parler-tts

# MusicGen
pip install audiocraft
```

### System Dependencies
```bash
# macOS
brew install ffmpeg

# Linux
sudo apt install ffmpeg

# For audio playback (platform-specific)
# macOS: Built-in (afplay)
# Linux: mpg123, aplay, paplay, mpv, or vlc
# Windows: Windows Media Player (built-in)
```

---

## Environment Variables

Set API keys for cloud providers:

```bash
# OpenAI
export OPENAI_API_KEY="sk-..."

# Stability AI
export STABILITY_API_KEY="sk-..."
```

---

## Next Steps (To Complete Implementation)

### High Priority
1. **Implement VoxtralProvider** - Integrate Hugging Face transformers for local Voxtral models
2. **Implement LocalProvider** - Integrate Parler-TTS, MusicGen, etc.
3. **Implement StabilityAudioProvider** - Stable Audio 2.5 integration
4. **Add format conversion** - Use pydub/ffmpeg for format conversion in `AudioFileManager`
5. **Add audio analysis** - Extract duration, sample_rate from audio files

### Medium Priority
1. **Real-time streaming** - Support for `/model voxtral-mini-4b-realtime`
2. **Voice cloning** - Full implementation for Voxtral TTS
3. **Speaker diarization** - For models that support it
4. **Audio effects** - Volume, pitch, speed adjustment
5. **Audio chaining** - Pipe operations (e.g., generate then recognize)

### Low Priority
1. **Multi-track composition** - Mix multiple audio tracks
2. **Real-time microphone input** - `/audialize "listen"` and `/audialize "stop"`
3. **Audio filters** - Reverb, echo, noise reduction
4. **WebSocket streaming** - For real-time transcription
5. **Batch processing** - Process multiple files at once

---

## Testing

To test the implementation:

```bash
# Start chatybot
python -m chatybot.chatybot_app

# Test commands
/audiocap
/audiomodel

# Set a TTS model (if OpenAI API key is configured)
/model gpt-4o-mini-tts
/audialize "speak: Hello world" voice=alloy

# Transcribe an audio file (if available)
/transcribe test_audio.wav

# List audio files
/listaudio
```

---

## Files to Sync to Git

```bash
# New files
src/chatybot/audio_provider.py
src/chatybot/audio_file_manager.py
src/chatybot/audio_engine.py
src/chatybot/audio_providers/__init__.py
src/chatybot/audio_providers/base.py
src/chatybot/audio_providers/openai_provider.py

# Modified files
src/chatybot/chat_config.toml
src/chatybot/buffer_manager.py
src/chatybot/chatdsl_parse.py
src/chatybot/chatybot_app.py
src/chatybot/config_manager.py
```

---

## Notes

1. **All models are defined in `chat_config.toml`** as requested
2. **Pattern matches image system** - Same directory structure, counter persistence, base64 encoding
3. **Escape commands** - All audio commands use `/` prefix
4. **Unified verb** - `/audialize` is the primary command for all audio operations
5. **Base64 encoding** - Audio data stored as `data:audio/<format>;base64,...`
6. **Dual variable types** - STT produces text, TTS/Generation produces base64

---

## Summary

The **core infrastructure for audio support** in Chatybot is now complete:

✅ **Audio Engine** - Main orchestrator with STT, TTS, generation, recognition  
✅ **Audio Providers** - Base class and OpenAI implementation  
✅ **Audio File Manager** - Storage with counter persistence, metadata, base64  
✅ **Model Registry** - All models defined in chat_config.toml  
✅ **Command Integration** - All escape commands implemented in chatybot_app.py  
✅ **DSL Integration** - Commands and variables work in ChatDSL scripts  
✅ **Audio Banks** - audiobank1-5 for storing audio data  
✅ **Audio Variables** - Base64-encoded audio in script variables  

**Remaining**: Implement specific providers (Voxtral, Local, Stability) and add format conversion.

---

*Implementation based on AUDIO_IMPLEMENTATION_PLAN_v2.md*
*All models are configured in chat_config.toml as specified*
