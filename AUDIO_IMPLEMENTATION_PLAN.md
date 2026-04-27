# Audio Processing Implementation Plan for Chatybot

**Version**: 1.0  
**Date**: 2025  
**Status**: Draft for Review  
**Author**: Mistral Vibe  

---

## Table of Contents
1. [Executive Summary](#executive-summary)
2. [Architecture Decision](#architecture-decision)
3. [Component Overview](#component-overview)
4. [Implementation Details](#implementation-details)
5. [Model & Provider Recommendations](#model--provider-recommendations)
6. [Integration with Chatybot](#integration-with-chatybot)
7. [Roadmap](#roadmap)
8. [Dependencies](#dependencies)
9. [Testing Strategy](#testing-strategy)
10. [Resources](#resources)

---

## Executive Summary

This document outlines a comprehensive plan for adding audio processing capabilities to chatybot, including:

- **Speech-to-Text (STT)**: Convert audio files (MP3, WAV, etc.) to text
- **Text-to-Speech (TTS)**: Generate speech audio from text
- **Music Generation**: Create music from text prompts
- **Sound Effects Generation**: Generate SFX from text descriptions
- **Sound Recognition**: Identify environmental sounds, music genres
- **Voice Recognition**: Speaker identification and diarization

### Key Finding
Uni Sonate, UniAudio 2.0, and AudioX are emerging unified models, however they are not yet production-ready. Therefore a modular architecture using specialized models is the recommended path for immediate implementation.

---

## Architecture Decision

### Recommended: Modular Architecture

```
audio/
├── audio_engine.py              # Main orchestrator
├── stt/                         # Speech-to-Text
│   ├── base.py
│   ├── openai_stt.py
│   ├── local_stt.py
│   └── assemblyai_stt.py
├── tts/                         # Text-to-Speech
│   ├── base.py
│   ├── openai_tts.py
│   ├── elevenlabs_tts.py
│   └── local_tts.py
├── music/                       # Music Generation
│   ├── base.py
│   ├── stable_audio.py
│   └── local_music.py
├── sound_fx/                    # Sound Effects
│   ├── base.py
│   └── stable_audio_fx.py
├── sound_recognition/           # Sound Recognition
│   ├── base.py
│   └── openai_recognition.py
├── voice_recognition/           # Voice/Speaker ID
│   ├── base.py
│   └── assemblyai_voice.py
└── utils/
    ├── audio_converter.py
    └── file_manager.py
```

**Rationale**:
- Immediate implementation possible
- Clear separation of concerns
- Easy to maintain and extend
- Can integrate unified models later as providers
- Matches existing chatybot patterns (ImageGenerator)

---

## Component Overview

### 1. Speech-to-Text (STT)

**Purpose**: Transcribe spoken audio to text

| Provider | Model | Max Size | Languages | Diarization | Cost |
|----------|-------|----------|-----------|-------------|------|
| OpenAI | gpt-4o-transcribe | 25MB | 100+ | ✅ | $$ |
| OpenAI | whisper-1 | 25MB | 99+ | ❌ | $ |
| AssemblyAI | Various | Large | 99+ | ✅ | $$ |
| Local | Voxtral-3B | ∞ | Multi | Limited | Free |
| Local | Canary-1B-Flash | ∞ | EN/DE/FR/ES | ❌ | Free |

**Supported Formats**: MP3, WAV, MP4, M4A, OGG, FLAC, WEBM

**API Endpoint** (OpenAI):
```
POST https://api.openai.com/v1/audio/transcriptions
File: audio file (any supported format)
Model: gpt-4o-transcribe
```

---

### 2. Text-to-Speech (TTS)

**Purpose**: Generate speech audio from text

| Provider | Model | Voices | Streaming | Cost |
|----------|-------|--------|-----------|------|
| OpenAI | gpt-4o-mini-tts | 30+ | ✅ | $$ |
| OpenAI | tts-1-hd | 13 | ✅ | $ |
| ElevenLabs | v2/v3 | 1000+ | ✅ | $$$ |
| Local | Parler-TTS | Custom | ✅ | Free |
| Local | Chatterbox | Custom | ✅ | Free |

**Supported Output Formats**: MP3 (default), WAV, Opus, AAC, FLAC, PCM

**API Endpoint** (OpenAI):
```
POST https://api.openai.com/v1/audio/speech
Body: {"model": "gpt-4o-mini-tts", "input": "text", "voice": "alloy", "response_format": "mp3"}
```

**Available Voices** (OpenAI):
alloy, echo, fable, onyx, nova, shimmer, coral, verse, ballad, ash, sage, marin, cedar + 16 new voices in 2025

---

### 3. Music Generation

**Purpose**: Create music from text prompts

| Provider | Model | Input Type | Max Length | Cost |
|----------|-------|------------|------------|------|
| Stability AI | Stable Audio 2.5 | Text | 3 min | $$$ |
| Hugging Face | MusicGen | Text/Melody | ~30s | Free |
| Hugging Face | DiffRhythm | Text | Full songs | Free |
| Adobe | Firefly | Text | Variable | $$ |
| OpenAI | (Upcoming) | Text/Audio | TBD | TBD |

**Note**: OpenAI is developing a music generator (reported Oct 2025) but no public API exists yet.

**Stability AI Endpoint**:
```
POST https://api.stability.ai/v2beta/stable-audio/generate
Body: {"prompt": "description", "output_format": "mp3"}
```

---

### 4. Sound Effects Generation

**Purpose**: Generate sound effects from text descriptions

| Provider | Model | Prompt Type | Max Length | Cost |
|----------|-------|-------------|------------|------|
| Stability AI | Stable Audio 2.5 | Text | 3 min | $$$ |
| ElevenLabs | SFX Generator | Text | Variable | $$$ |
| Adobe | Firefly | Text | Variable | $$ |

**Note**: Stable Audio 2.5 handles both music and sound effects.

---

### 5. Sound Recognition

**Purpose**: Identify environmental sounds (dog barking, car honking, rain, etc.)

| Provider | Model | Formats | Accuracy | Cost |
|----------|-------|---------|----------|------|
| OpenAI | gpt-4o-transcribe | MP3, WAV, etc. | High | $$ |
| ScreenApp | Audio Analyzer | MP3, WAV, FLAC, etc. | 98.7% | Free |
| Google | VGGish | WAV | High | Free (local) |
| Google | YAMNet | WAV | High | Free (local) |

---

### 6. Voice Recognition / Speaker Identification

**Purpose**: Identify and differentiate speakers in audio

| Provider | Model | Real-Time | Multi-Speaker | Cost |
|----------|-------|-----------|---------------|------|
| AssemblyAI | Diarization | ✅ | ✅ | $$ |
| Deepgram | Speaker ID | ✅ | ✅ | $$ |
| VOSK | Speaker ID | ✅ | ✅ | Free (local) |
| Resemble AI | Voice ID | ✅ | ✅ | $$$ |

---

## Implementation Details

### File Management

**Directory Structure**:
```
~/chatybot_audio/
├── 2025-01-15/
│   ├── stt/
│   │   └── transcript_001.txt
│   ├── tts/
│   │   └── response_001.mp3
│   ├── music/
│   │   └── composition_001.mp3
│   ├── sound_fx/
│   │   └── explosion_001.wav
│   └── index.json
└── 2025-01-16/
    └── ...
```

**Counter Persistence**: Like ImageGenerator, counters are stored in index.json per date directory to prevent filename collisions after restart.

### Audio Formatting

**Primary Formats**: MP3 (default), WAV

**Conversion Utility**: All audio files are converted to target formats using pydub/ffmpeg

**Base64 Encoding**: Audio data is stored in variables using base64 encoding (same pattern as images):
```
data:audio/mp3;base64,<base64_data>
```

---

## Model & Provider Recommendations

### For Production (Priority Order)

| Task | Primary Choice | Fallback | Notes |
|------|---------------|----------|-------|
| STT | OpenAI gpt-4o-transcribe | AssemblyAI | Best accuracy, supports diarization |
| TTS | OpenAI gpt-4o-mini-tts | ElevenLabs | Natural voices, style control |
| Music | Stability AI 2.5 | Adobe Firefly | High quality, 3min outputs |
| Sound FX | Stability AI 2.5 | ElevenLabs SFX | Same API as music |
| Sound Recognition | OpenAI gpt-4o-transcribe | ScreenApp | Multi-purpose understanding |
| Voice Recognition | AssemblyAI | Deepgram | Speaker diarization |

### For Local/Offline (Priority Order)

| Task | Recommended Model | Requirements | Notes |
|------|-------------------|--------------|-------|
| STT | Voxtral-Mini-3B | GPU (8GB VRAM) | Multilingual, accurate |
| STT | Canary-1B-Flash | GPU (4GB VRAM) | Fast, efficient |
| TTS | Parler-TTS | GPU (8GB VRAM) | High quality, customizable |
| Music | MusicGen | GPU (12GB VRAM) | Good quality, controllable |
| Sound Recognition | VGGish | CPU | Lightweight, proven |
| Voice Recognition | VOSK | CPU | Offline, real-time |

---

## Integration with Chatybot

### New Commands

| Command | Syntax | Description |
|---------|--------|-------------|
| `/stt` | `/stt <file> [language]` | Transcribe audio file |
| `/tts` | `/tts "text" [-v voice]` | Generate speech |
| `/music` | `/music "prompt"` | Generate music |
| `/sfx` | `/sfx "prompt"` | Generate sound effect |
| `/recognize` | `/recognize <file>` | Identify sounds |
| `/voices` | `/voices` | List available TTS voices |
| `/audiomirror` | `/audiomirror <var>` | Save last audio to variable |
| `/play` | `/play <file>` | Play audio file |
| `/audiodir` | `/audiodir <path>` | Set audio directory |
| `/listaudio` | `/listaudio [category]` | List audio files |
| `/audiobanks` | `/audiobanks` | List audio banks |

### DSL Integration

Add to `chatdsl_parse.py`:
```python
VALID_ESCAPE_COMMANDS = {
    ...
    "stt", "tts", "music", "sfx", "recognize",
    "voices", "audiomirror", "play", "audiodir",
    "listaudio", "audiobanks"
}
```

### BufferManager Integration

```python
# Add to buffer_manager.py
self.audio_banks: Dict[str, List[Dict]] = {}
self.script_audio_vars: Dict[str, str] = {}
```

### ConfigManager Integration

```python
# Add to config_manager.py
"audio": {
    "enabled": true,
    "stt_provider": "openai",
    "tts_provider": "openai",
    "music_provider": "stability",
    "sound_fx_provider": "stability",
    "voice_recognition_provider": "assemblyai",
    "audio_directory": "~/chatybot_audio",
    "default_tts_voice": "alloy",
    "default_audio_format": "mp3"
}
```

---

## Roadmap

### Phase 1: Core Infrastructure (1-2 weeks)
- [ ] Create `audio/` directory structure
- [ ] Implement `AudioFileManager` with counter persistence
- [ ] Implement `AudioConverter` utilities
- [ ] Create base abstract classes (STT, TTS, Music, SFX, Recognition)
- [ ] Add audio configuration to `ConfigManager`
- [ ] Add audio variables to `BufferManager`

### Phase 2: Speech-to-Text (1 week)
- [ ] Implement `OpenAISTT`
- [ ] Implement `LocalSTT` (Voxtral/Canary)
- [ ] Add `/stt` command
- [ ] Test with MP3 and WAV files

### Phase 3: Text-to-Speech (1 week)
- [ ] Implement `OpenAITTS`
- [ ] Implement `LocalTTS` (Parler-TTS)
- [ ] Add `/tts` and `/voices` commands
- [ ] Test with various voices and formats

### Phase 4: Music Generation (1 week)
- [ ] Implement `StableAudioMusic`
- [ ] Implement `LocalMusicGenerator` (MusicGen)
- [ ] Add `/music` command

### Phase 5: Sound Effects (1 week)
- [ ] Implement `StableAudioFX`
- [ ] Add `/sfx` command

### Phase 6: Sound Recognition (1 week)
- [ ] Implement `OpenAISoundRecognition`
- [ ] Add `/recognize` command

### Phase 7: Voice Recognition (1 week)
- [ ] Implement `AssemblyAIVoice`
- [ ] Add speaker identification commands

### Phase 8: Advanced Features (2 weeks)
- [ ] Audio banks support
- [ ] `/audiomirror` command
- [ ] `/play` command
- [ ] `/audiodir`, `/listaudio`, `/audiobanks` commands

### Phase 9: DSL Integration (1 week)
- [ ] Update `chatdsl_parse.py`
- [ ] Add audio command validation
- [ ] Test with ChatDSL scripts

### Phase 10: Testing & Documentation (1-2 weeks)
- [ ] Unit tests
- [ ] Integration tests
- [ ] Example ChatDSL scripts
- [ ] Documentation

---

## Dependencies

### Core Dependencies
```bash
pip install aiohttp transformers torch sentencepiece librosa soundfile pydub
```

### System Dependencies
```bash
# macOS
brew install ffmpeg

# Linux
sudo apt install ffmpeg

# Windows
# Download from https://ffmpeg.org
```

### Optional Local Models
```bash
# TTS
pip install parler-tts coqui-ai-TTS

# STT (alternative)
pip install vosk
```

---

## Testing Strategy

### Test Files Required
Create `test_audio/` directory with:
- `hello.wav` - Simple speech for STT testing
- `hello.mp3` - MP3 version for format testing
- `conversation.mp3` - Multi-speaker audio for diarization
- `music_sample.mp3` - Music for recognition testing
- `sfx_explosion.wav` - Sound effect for testing

### Unit Test Example
```python
@pytest.mark.asyncio
async def test_stt_transcription():
    engine = AudioEngine({"stt_provider": "local"})
    text, _ = await engine.transcribe("test_audio/hello.wav")
    assert "hello" in text.lower()

@pytest.mark.asyncio
async def test_tts_synthesis():
    engine = AudioEngine({"tts_provider": "openai"})
    audio = await engine.synthesize("Hello world")
    assert len(audio) > 100
```

### Integration Test Flow
```
1. /tts "Hello world" -> generates audio
2. /stt last_audio.mp3 -> transcribes back
3. Verify transcription matches original text
```

---

## Resources

### API Documentation
- [OpenAI Audio API](https://platform.openai.com/docs/guides/audio)
- [Stability AI API](https://platform.stability.ai/docs)
- [AssemblyAI API](https://www.assemblyai.com/docs)
- [ElevenLabs API](https://docs.elevenlabs.io)

### Hugging Face Models
- [STT Models](https://huggingface.co/models?pipeline_tag=automatic-speech-recognition)
- [TTS Models](https://huggingface.co/models?pipeline_tag=text-to-speech)
- [Music Models](https://huggingface.co/models?other=music-generation)
- [Audio Classification](https://huggingface.co/models?pipeline_tag=audio-classification)

### Research Papers (Unified Models)
- [UniSonate](https://arxiv.org/abs/2604.22209) - Unified speech, music, SFX
- [UniAudio 2.0](https://arxiv.org/abs/2602.04683) - Unified audio language model
- [AudioX](https://arxiv.org/abs/2503.10522) - Anything-to-audio framework

---

## Format Support Matrix

| Format | STT Input | TTS Output | Music | SFX | Recognition |
|--------|-----------|------------|-------|-----|-------------|
| MP3 | ✅ | ✅ | ✅ | ✅ | ✅ |
| WAV | ✅ | ✅ | ✅ | ✅ | ✅ |
| FLAC | ✅ | ✅ | ❌ | ✅ | ✅ |
| OGG | ✅ | ❌ | ❌ | ❌ | ✅ |
| AAC | ✅ | ✅ | ❌ | ❌ | ✅ |
| Opus | ❌ | ✅ | ❌ | ❌ | ❌ |
| PCM | ❌ | ✅ | ❌ | ❌ | ❌ |

> All formats can be auto-converted via `AudioConverter` utility

---

## Cost Comparison (2025)

| Service | Unit | Approx. Cost |
|---------|------|--------------|
| OpenAI STT | per minute | $0.006 |
| OpenAI TTS | per 1K chars | $0.015 |
| Stability AI | per generation | $0.10-0.50 |
| ElevenLabs | per 1K chars | $0.01-0.03 |
| AssemblyAI | per minute | $0.0025-0.01 |

**Local Models**: Free (hardware cost only)

---

## Performance Expectations

| Task | Cloud Latency | Local Latency |
|------|---------------|---------------|
| STT (30s audio) | 500-2000ms | 2000-5000ms |
| TTS (100 chars) | 200-500ms | 500-2000ms |
| Music (30s) | 5000-10000ms | 10000-30000ms |
| SFX (5s) | 2000-5000ms | 5000-10000ms |

---

## Example ChatDSL Script

```chatdsl
# Audio demonstration script

# Generate and play introduction
tts: Welcome to the audio demonstration.
play: last

# Generate background music
music: ambient electronic background music
play: last &

# Generate sound effect
sfx: futuristic computer beep
play: last

# Transcribe user input
stt: user_input.mp3
echo: You said: [stt]

# Conditional response
if: [stt] contains "hello"
    tts: Hello there! How can I help you today?
    play: last
endif

# List available voices
tts: Here are the available voices:
voices:
echo: [voices]
```

---

## Files to Create/Modify

### New Files (26 total)
```
audio/__init__.py
audio/audio_engine.py
audio/stt/__init__.py
audio/stt/base.py
audio/stt/openai_stt.py
audio/stt/local_stt.py
audio/tts/__init__.py
audio/tts/base.py
audio/tts/openai_tts.py
audio/tts/local_tts.py
audio/music/__init__.py
audio/music/base.py
audio/music/stable_audio.py
audio/sound_fx/__init__.py
audio/sound_fx/base.py
audio/sound_fx/stable_audio_fx.py
audio/sound_recognition/__init__.py
audio/sound_recognition/base.py
audio/sound_recognition/openai_recognition.py
audio/voice_recognition/__init__.py
audio/voice_recognition/base.py
audio/voice_recognition/assemblyai_voice.py
audio/utils/__init__.py
audio/utils/audio_converter.py
audio/utils/file_manager.py
```

### Modified Files (5 total)
```
chatybot_app.py
config_manager.py
buffer_manager.py
chatdsl_parse.py
main.py
```

---

## Conclusion

This plan provides a **comprehensive, modular, and extensible** approach to adding audio capabilities to chatybot. The architecture:

1. ✅ Follows existing patterns (like ImageGenerator)
2. ✅ Supports multiple providers and models
3. ✅ Prioritizes OpenAI-compatible APIs
4. ✅ Includes offline/local options for privacy
5. ✅ Focuses on MP3 and WAV formats
6. ✅ Can be extended with unified models in the future
7. ✅ Includes complete testing strategy

**Recommended Next Step**: Start with Phase 1-2 (STT) as it has immediate value and aligns with existing OpenAI infrastructure.

---

*Document generated based on 2024-2025 research of audio AI models, APIs, and best practices.*
