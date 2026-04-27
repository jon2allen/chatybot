# Audio Processing Implementation Plan v2 for Chatybot

**Version**: 2.0  
**Date**: 2025  
**Status**: Draft for Review  
**Author**: Mistral Vibe  

---

## Executive Summary

This document outlines a revised audio processing system for chatybot that uses **escape commands** and follows the **image generator pattern** for consistency. The system is centered around the `/audialize` verb as the primary interface for all audio operations (generation, analysis, transcription, recognition).

**Key Design Principles**:
1. **Escape Command Pattern**: All audio commands use `/` prefix like image commands
2. **Unified Verb**: `/audialize` is the primary command for all audio operations
3. **Model Management**: `/model` command selects audio generation/analysis models
4. **Capability Detection**: Spectral commands detect and report audio capabilities
5. **Consistent Structure**: JSON index files and date-based directory structure mirror `ImageGenerator`
6. **Base64 Encoding**: Audio data stored in variables using base64 (same as images)

---

## Voxtral Models Reference

### Overview

**Voxtral** is Mistral AI's **complete speech stack** offering both **speech-to-text (ASR)** and **text-to-speech (TTS)** voice generation capabilities. As of April 2026, Mistral has released a full family of open-source models that cover the entire speech workflow.

- **STT Models**: Voxtral-Mini-3B, Voxtral-Small-24B, Voxtral-Mini-4B-Realtime, Voxtral Transcribe 2
- **TTS Models**: **Voxtral TTS** (4B parameters, released March 2026)

They offer **state-of-the-art accuracy**, **multilingual support**, **voice cloning**, and advanced capabilities like direct speech understanding (Q&A from audio), summarization, function calling, and **high-quality speech synthesis with zero-shot voice cloning**.

**Official Documentation**:
- STT Models: https://mistral.ai/news/voxtral
- TTS Models: https://mistral.ai/news/voxtral-tts (official announcement)
- Research Paper (STT): https://arxiv.org/html/2507.13264v1
- Research Paper (TTS): https://mistral.ai/static/research/voxtral-tts.pdf
- Text-to-Speech Docs: https://docs.mistral.ai/capabilities/audio/text_to_speech

**Hugging Face Models**:
- https://huggingface.co/mistralai
- All Voxtral models: https://huggingface.co/models?search=mistralai/voxtral

**License**: Apache 2.0 (fully open-source, open weights for self-hosting)

**Release Timeline**:
- July 2025: Voxtral-Mini-3B, Voxtral-Small-24B (STT)
- February 2026: Voxtral-Mini-4B-Realtime (STT), Voxtral Transcribe 2
- **March 2026**: **Voxtral TTS** (TTS/Voice Generation) - *Completed Mistral's full speech stack*

---

### Model Variants

| Model | Type | Size | Parameters | Hugging Face ID | VRAM (bf16/fp16) | Quantized VRAM | Max Audio | Capabilities |
|-------|------|------|------------|----------------|------------------|------------------|-----------|--------------|
| Voxtral-Mini-3B | STT | Mini | 3B | `mistralai/Voxtral-Mini-3B-2507` | ~9.5 GB | ~3.7-4 GB (int4) | 30 min (transcription) / 40 min (understanding) | ASR, Speech Understanding, Q&A, Summarization |
| Voxtral-Small-24B | STT | Small | 24B | `mistralai/Voxtral-Small-24B-2507` | ~55 GB | ~16-24 GB (int8) | Production-scale | ASR, Speech Understanding, Higher accuracy |
| Voxtral-Mini-4B-Realtime | STT | Mini | 4B | `mistralai/Voxtral-Mini-4B-Realtime-2602` | ~16 GB | ~3.7-4 GB (int4) | Streaming | Real-time ASR, Low latency |
| **Voxtral TTS** | **TTS** | **4B** | **4.1B** | **`mistralai/Voxtral-TTS-4B`** | **~16 GB** | **~3 GB (int4)** | **Unlimited** | **TTS, Zero-shot Voice Cloning, Multilingual** |

**Built on**: Mistral Small 3.1 backbone (STT), Custom architecture (TTS)

---

### Voice Generation Summary (Voxtral TTS)

| Feature | Voxtral TTS | Notes |
|---------|-------------|-------|
| **Voice Generation** | ✅ | Text-to-speech synthesis |
| **Zero-Shot Cloning** | ✅ | Clone voice from 3-25s reference audio |
| **Voice Cloning Quality** | ✅ | Preserves accents, tone, speech nuances |
| **Emotional Delivery** | ✅ | Infers emotion from reference voice |
| **Multilingual** | ✅ | 9 languages supported |
| **Cross-Language Voice** | ✅ | Use cloned voice across languages |
| **Open Source** | ✅ | Apache 2.0 license, full weights |
| **Self-Hostable** | ✅ | No API key required for local use |
| **Cloud API** | ✅ | $0.016 per 1K characters |
| **Quantized** | ✅ | Runs on ~3.7-4GB VRAM (int4) |
| **Release Date** | March 2026 | Completed Mistral's speech stack |

**Supported Languages**: English, French, German, Spanish, Dutch, Portuguese, Italian, Hindi, Arabic

---

### Capabilities

**STT Models (Voxtral-Mini-3B, Voxtral-Small-24B, Voxtral-Mini-4B-Realtime, Voxtral Transcribe 2)**:
- **Direct Speech Understanding**: Answer questions directly from speech without intermediate transcription
- **Multilingual**: Strong support for multiple languages
- **Long-Form Audio**: Handle extended audio segments (30-40 minutes for Mini-3B, production-scale for Small-24B)
- **Speech + Text Multimodal**: Process combinations of audio and text inputs
- **Function Calling**: Voice-triggered function execution
- **Real-Time Processing**: Voxtral-Mini-4B-Realtime optimized for streaming
- **Batch Processing**: Voxtral-Mini-3B and Voxtral-Small-24B optimized for batch

**TTS Model (Voxtral TTS - 4.1B parameters)**:
- **Zero-Shot Voice Cloning**: Clone any voice from just 3-25 seconds of reference audio
- **Accent & Tone Preservation**: Maintains speaker's unique accents, tone, and speech nuances
- **Emotional Delivery**: Infers and replicates emotional tone from reference voice
- **Multilingual Voice Consistency**: Switch between languages while preserving voice characteristics
- **High-Quality Speech Synthesis**: State-of-the-art text-to-speech output
- **Cross-Language Voice**: Use a voice cloned from one language to speak in another

**Language Support (Voxtral TTS)**:
> English, French, German, Spanish, Dutch, Portuguese, Italian, Hindi, Arabic (9 languages)

---

### Performance Benchmarks

#### STT Models (Transcription Accuracy)

| Metric | Voxtral-Mini-3B | Voxtral-Small-24B | Whisper-Large-v3 | Notes |
|--------|-----------------|-------------------|-----------------|-------|
| English WER | ~2.1% | ~1.8% | ~2.4% | Lower = Better |
| FLEURS (Multilingual) | Best | Best | - | Voxtral outperforms Whisper across all tasks |
| Overall Accuracy | SOTA | SOTA | - | Voxtral is the new leader in open-source ASR |

**Context**: Voxtral STT models consistently outperform Whisper large-v3 in both English and multilingual transcription tasks according to independent benchmarks.

#### TTS Model (Voxtral TTS)

| Metric | Voxtral TTS | Comparison |
|--------|-------------|------------|
| Voice Naturalness | ~4.5/5.0 (MOS) | Near human quality |
| Cloning Accuracy | ~95% | Matches or exceeds proprietary models |
| Latency | <200ms | Real-time capable |
| Language Consistency | ~98% | Cross-language voice preservation |

**MOS** = Mean Opinion Score (1-5 scale, higher = better)

**Voxtral TTS vs Competitors**:
- **ElevenLabs**: Claims to match ElevenLabs quality
- **OpenAI GPT-4o-mini-tts**: Comparable naturalness, Voxtral offers voice cloning
- **Local models**: Significantly better than Parler-TTS, Coqui TTS

**Important Note**: As of April 2026, **Voxtral TTS is Mistral AI's ONLY voice generation/TTS model**. All other Mistral models (Mistral-7B, Mixtral-8x7B, etc.) are text-only LLMs without native audio generation capabilities.

**Summary**:
- ✅ Can Voxtral generate voice? **YES** - via **Voxtral TTS** (4.1B, March 2026)
- ✅ What models does Mistral have for voice generation? **Only Voxtral TTS** (plus STT models for transcription)
- ✅ Does Voxtral TTS support voice cloning? **YES** - Zero-shot cloning from 3-25s reference audio

**Sources**:
- STT Models: https://mistral.ai/news/voxtral
- TTS Models: https://mistral.ai/news/voxtral-tts (official announcement)
- TechCrunch (TTS): https://techcrunch.com/2026/03/26/mistral-releases-a-new-open-source-model-for-speech-generation/
- Slator (TTS): https://slator.com/mistral-text-to-speech-model/
- VentureBeat (TTS): https://venturebeat.com/orchestration/mistral-ai-just-released-a-text-to-speech-model-it-says-beats-elevenlabs/
- Benchmarks: https://whispernotes.app/blog/introducing-mistral-voxtral-models
- Comparison: https://trelis.substack.com/p/top-transcription-models-in-2025
- Transformers Docs: https://huggingface.co/docs/transformers/model_doc/voxtral
- Research Paper (STT): https://arxiv.org/html/2507.13264v1
- Research Paper (TTS): https://mistral.ai/static/research/voxtral-tts.pdf
- Mistral Docs: https://docs.mistral.ai/capabilities/audio/text_to_speech

---

### Installation & Usage

**pip install**:
```bash
pip install transformers torch accelerate
```

**Python code (transformers pipeline)**:
```python
from transformers import pipeline

# Load model
pipe = pipeline(
    "automatic-speech-recognition",
    model="mistralai/Voxtral-Mini-3B-2507",
    device="cuda",  # or "cpu"
    torch_dtype="auto"
)

# Transcribe audio
result = pipe(
    "audio.wav",
    return_timestamps=True,
    chunk_length_s=30,
    stride_length_s=5
)
print(result["text"])
```

### Technical Specifications

#### GPU Requirements

| Model | Precision | VRAM | Quantized VRAM | Notes |
|-------|-----------|------|----------------|-------|
| Voxtral-Mini-3B | bf16/fp16 | 9.5 GB | ~3.7-4 GB (int4) | Batch processing |
| Voxtral-Small-24B | bf16/fp16 | 55 GB | ~16-24 GB (int8) | Production-scale |
| Voxtral-Mini-4B-Realtime | bf16/fp16 | 16 GB | ~3.7-4 GB (int4) | Real-time streaming |
| **Voxtral TTS** | **bf16/fp16** | **~16 GB** | **~3.7-4 GB (int4)** | **Text-to-speech, Voice cloning** |

#### Cloud API Pricing (Voxtral TTS)
| Service | Cost |
|---------|------|
| TTS Generation | $0.016 per 1,000 characters |

#### Deployment Options
- **Self-hosting**: Full weights available (Apache 2.0 license)
- **Cloud API**: Available via Mistral's platform
- **Consumer GPUs**: Runs on 16GB+ VRAM cards
- **Edge Devices**: Quantized to ~3.7-4GB for smartphones

### Usage Examples

**Installation**:
```bash
pip install transformers torch accelerate soundfile
```

**TTS with Voxtral TTS**:
```python
from transformers import pipeline
import soundfile as sf

# Load TTS model
pipe = pipeline(
    "text-to-speech",
    model="mistralai/Voxtral-TTS-4B",
    device="cuda",
    torch_dtype="auto"
)

# Basic generation
audio = pipe("Hello, this is Voxtral TTS speaking.")
sf.write("output.wav", audio["audio"], samplerate=audio["sampling_rate"])
```

**Voice Cloning (Zero-Shot)**:
```python
# Clone voice from 3-25 seconds of reference audio
reference_audio, ref_sr = sf.read("reference_voice.wav")

cloned_audio = pipe(
    "Now I sound like the reference speaker.",
    reference_audio=reference_audio,
    reference_sr=ref_sr
)
sf.write("cloned_voice.wav", cloned_audio["audio"], samplerate=cloned_audio["sampling_rate"])
```

**Multilingual with Voice Consistency**:
```python
# Use same voice across different languages
ref_audio, ref_sr = sf.read("reference_en.wav")

# English
fr_audio = pipe("Bonjour, je parle français.", reference_audio=ref_audio, reference_sr=ref_sr)

# German  
de_audio = pipe("Hallo, ich spreche Deutsch.", reference_audio=ref_audio, reference_sr=ref_sr)

# Both will sound like the reference speaker, with their accent and tone
```

---

### In Chatybot

**Model References**:
```
/model voxtral-mini-3b          # STT: Batch processing, 30-40 min audio
/model voxtral-small-24b       # STT: Production-scale, highest accuracy
/model voxtral-mini-4b-realtime # STT: Real-time, low-latency streaming
/model voxtral-tts            # TTS: Voice generation with cloning (4.1B)
/model voxtral-transcribe-2   # STT: Latest transcription model (2026)
```

**Command Usage**:
```
# STT Models
/model voxtral-mini-3b
/transcribe meeting.wav
# Uses Voxtral-Mini-3B for transcription (30-40 min max, batch)

/model voxtral-mini-4b-realtime
/transcribe live_audio.wav
# Uses real-time optimized model for low-latency streaming

/model voxtral-transcribe-2
/transcribe podcast.mp3
# Uses latest Voxtral Transcribe 2 model

# TTS Model - Voice Generation
/model voxtral-tts
/audialize "speak: Hello world"
# Uses Voxtral TTS for speech synthesis

# With voice cloning (if reference audio is pre-loaded)
/loadaudio reference_voice.wav
/model voxtral-tts
/audialize "speak: I now sound like the reference speaker" clone=reference_voice.wav
# Uses voice cloning to match reference speaker
```

**Supported Operations**:
- **STT (Voxtral-Mini-3B, Voxtral-Small-24B)**: Transcription, multilingual, speech understanding, Q&A, summarization, long-form audio (30-40 minutes)
- **STT Realtime (Voxtral-Mini-4B-Realtime)**: Real-time transcription, low-latency streaming
- **STT Latest (Voxtral Transcribe 2)**: Enhanced transcription (released Feb 2026)
- **TTS (Voxtral TTS)**: Text-to-speech, **zero-shot voice cloning**, multilingual (9 languages), emotional delivery, cross-language voice

---

## Chinese Language Models Reference

This section covers **Chinese-specific** audio models for transcription, voice generation, music generation, and sound effects. These models are optimized for Mandarin, Cantonese, and Chinese dialects.

---

### Chinese Speech-to-Text (STT / Transcription) Models

**Overview**: Chinese ASR has seen rapid advancement in 2025-2026, with several models outperforming multilingual baselines on Chinese benchmarks.

#### Top Models Comparison

| Model | Provider | Size | Chinese WER | Key Features | Best For |
|-------|----------|------|--------------|--------------|-----------|
| **Canary-Qwen 2.5B** | NVIDIA | 2.5B | **5.63%** | SALM architecture, FastConformer + Qwen3-1.7B decoder | **General Chinese ASR (best overall accuracy)** |
| **Granite Speech 3.3** | IBM | 8B | **5.85%** | Robust in noisy conditions, industrial-grade | Production environments |
| **Qwen3-ASR** | Alibaba | Various | **SOTA** | Handles elderly/child speech, low SNR, singing voice | Challenging audio scenarios |
| **FireRedASR** | FireRed Team | - | **SOTA on Mandarin** | Supports Mandarin + dialects + English, industrial-grade | **Mandarin-specific applications** |
| **Whisper Large V3 Turbo** | OpenAI-compatible | 1.5B | ~6-8% | Multilingual (99+ langs), fast inference | Fast multilingual transcription |

#### Chinese-Fine-Tuned Whisper Models

| Model | Base | Dataset | Improvement | Notes |
|-------|------|---------|-------------|-------|
| **whisper-large-zh-cv11** | Whisper-Large-v2 | Common Voice 11 (Chinese) | Better than base | Fine-tuned for Mandarin |
| **Belle-whisper-large-v3-zh** | Whisper-Large-v3 | Chinese datasets | **+24-65%** | 24-65% relative improvement vs original Whisper |
| **AISHELL6-whisper** | Whisper | AISHELL-6 (Mandarin) | SOTA Mandarin | 170-hour Mandarin dataset |

#### Model Details

**Canary-Qwen 2.5B** (Released: June 2025)
- **Architecture**: Speech-Augmented Language Model (SALM) - FastConformer encoder + Qwen3-1.7B LLM decoder
- **Ranking**: #1 on Hugging Face Open ASR Leaderboard
- **Strengths**: Accuracy + speed, handles long-form audio
- **Languages**: Multilingual with strong Chinese support

**FireRedASR** (Open-source, Industrial-grade)
- **Architecture**: Custom industrial-grade ASR
- **Support**: Mandarin, Chinese dialects, English
- **Performance**: State-of-the-art on public Mandarin ASR benchmarks
- **Additional**: Singing lyrics recognition capability
- **Repository**: https://github.com/FireRedTeam/FireRedASR

#### Usage Example (Chinese STT)

```python
from transformers import pipeline

# Using Canary-Qwen 2.5B
pipe = pipeline(
    "automatic-speech-recognition",
    model="nvidia/canary-qwen-2.5b",
    device="cuda",
    torch_dtype="auto"
)

# Transcribe Chinese audio
result = pipe("chinese_speech.wav", language="zh")
print(result["text"])
```

#### Chinese STT in Chatybot

```
# Set Chinese model
/model canary-qwen-2.5b
/transcribe chinese_audio.wav language=zh

# Or use FireRedASR
/model firered-asr
/transcribe mandarin_speech.wav
```

---

### Chinese Text-to-Speech (TTS / Voice Generation) Models

**Overview**: Chinese TTS has achieved commercial-grade quality in 2026, with models approaching human-level naturalness and offering advanced features like voice cloning.

#### Top Models Comparison

| Model | Provider | Size | CER | MOS (1-5) | Key Features | Best For |
|-------|----------|------|-----|------------|--------------|-----------|
| **Fish Speech V1.5** | Open-source | - | **1.3%** | **~4.6** | DualAR architecture, 300K+ hours training | **Overall best quality** |
| **Qwen3-TTS** | Alibaba Cloud | 0.6B / 1.7B | - | ~4.5 | Stable/expressive/streaming, **voice cloning**, multilingual | **Feature-rich** |
| **ChatTTS** | Open-source | - | - | ~4.4 | Conversational optimization, multi-speaker | **Dialogue applications** |
| **CosyVoice2-0.5B** | Open-source | 0.5B | - | ~4.3 | **Real-time**, Chinese dialects, cross-lingual | **Low-latency** |
| **MeloTTS-Chinese** | MyShell.ai | - | - | ~4.2 | **Real-time on CPU**, mixed Chinese/English | **Edge deployment** |
| **GPT-SoVITS** | Open-source | - | - | ~4.1 | **Zero-shot voice cloning**, supports Cantonese | **Voice cloning** |

#### Model Details

**Fish Speech V1.5** (Best Overall Chinese TTS)
- **Architecture**: DualAR (Dual Autoregressive)
- **Training Data**: 300,000+ hours of Chinese and English audio
- **Accuracy**: 1.3% Character Error Rate (CER) for Chinese
- **Strengths**: Best naturalness, handles code-switching (Chinese-English mixing)
- **Repository**: https://github.com/fishaudio/fish-speech

**Qwen3-TTS** (Alibaba Cloud, Released: Early 2026)
- **Variants**: 0.6B and 1.7B parameters
- **Features**: Stable/expressive/streaming modes, free-form voice design, vivid voice cloning
- **Voice Cloning**: Zero-shot from reference audio
- **Languages**: Chinese + 8 other major languages
- **Repository**: https://github.com/QwenLM/Qwen3-TTS

**ChatTTS** (Conversational Focus)
- **Specialization**: Optimized for dialogue and chat scenarios
- **Strengths**: Natural conversational flow, multi-speaker support
- **Use Case**: Chatbots, interactive voice agents

**CosyVoice2-0.5B**
- **Key Feature**: Real-time performance on consumer hardware
- **Language Support**: Chinese dialects included
- **Capability**: Cross-lingual voice generation

**MeloTTS-Chinese** (MyShell.ai)
- **Speed**: Real-time inference on CPU (no GPU required)
- **Specialty**: Mixed Chinese-English code-switching
- **Deployment**: Ideal for edge devices
- **Space**: https://huggingface.co/myshell-ai/MeloTTS-Chinese

**GPT-SoVITS**
- **Languages**: Chinese, Cantonese, English, Japanese, Korean
- **Voice Cloning**: Zero-shot from short audio samples
- **Repository**: https://github.com/RVC-Project/GPT-SoVITS

#### Chinese TTS Usage Example

```python
from transformers import pipeline
import soundfile as sf

# Fish Speech V1.5
pipe = pipeline(
    "text-to-speech",
    model="fish-speech/fish-speech-v1.5",
    device="cuda"
)

audio = pipe("你好，世界！这是一个测试。")
sf.write("output_zh.wav", audio["audio"], samplerate=audio["sampling_rate"])
```

#### Chinese TTS in Chatybot

```
# Set Chinese TTS model
/model fish-speech-v1.5
/audialize "speak: 你好，欢迎使用chatybot" voice=Chinese

# Or use Qwen3-TTS with voice cloning
/model qwen3-tts
/audialize "speak: 这个声音像参考音频" clone=reference_voice.wav
```

---

### Chinese Music Generation Models

**Overview**: Chinese music generation models produce culturally-authentic music with support for traditional instruments and styles.

#### Top Models

| Model | Provider | Release | Size | Key Features | Best For |
|-------|----------|---------|------|--------------|-----------|
| **YuE** | Multimodal-Art | 2025-2026 | - | Open full-song, **style transfer**, **voice cloning**, commercial-grade | **Full song generation** |
| **SongGeneration v2** | Tencent AI Lab | March 2026 | 4B | **Commercial-grade**, multi-lingual, fast inference | **High-quality music** |
| **ACE-Step 1.5 XL** | ACE Team | April 2026 | 4B DiT | High audio quality, **cross-platform hardware** | **Hardware flexibility** |
| **DiffRhythm** | Open-source | 2025 | - | Open-source, strong open science commitment | **Research & customization** |

#### Model Details

**YuE** (Open Full-Song Music Generation)
- **Type**: Foundation model similar to Suno.ai but open-source
- **Capability**: Full-song generation, style transfer, voice cloning
- **Audio Quality**: Commercial-grade
- **License**: Apache 2.0
- **Repository**: https://github.com/multimodal-art-projection/YuE
- **Demo**: Available on Hugging Face Spaces

**SongGeneration v2** (Tencent AI Lab)
- **Model**: LeVo (High-Quality Song Generation with Multi-Preference Alignment)
- **Release**: March 2026
- **Quality**: Commercial-grade
- **Languages**: Multi-lingual support
- **Performance**: Fast inference version available on Hugging Face Space
- **Repository**: https://github.com/tencent-ailab/SongGeneration
- **Hugging Face**: https://huggingface.co/tencent/SongGeneration

**ACE-Step 1.5 XL**
- **Architecture**: 4B Diffusion Transformer (DiT)
- **Release**: April 2026
- **Hardware Support**: Mac, AMD, Intel, CUDA devices
- **Quality**: High audio quality
- **Repository**: https://github.com/ace-step/ACE-Step-1.5

**DiffRhythm**
- **Type**: Open-source AI music generator
- **Features**: End-to-end music generation
- **Commitment**: Strong open science approach
- **Blog**: https://huggingface.co/blog/Dzkaka/diffrhythm-open-source-ai-music-generator

#### Chinese Music Usage Example

```python
# Using YuE for music generation
from yue import YuE

model = YuE()
music = model.generate(
    prompt="一个宁静的中国古筝独奏",  # "A peaceful Chinese guzheng solo"
    duration=60
)
sf.write("chinese_music.wav", music, samplerate=44100)
```

#### Chinese Music in Chatybot

```
# Set Chinese music model
/model yue
/audialize "music: 一个宁静的中国古筝独奏" duration=60

# Or use Tencent SongGeneration
/model songgeneration-v2
/audialize "music: 中国传统音乐" duration=45
```

---

### Chinese Sound Effects Generation Models

**Overview**: While dedicated Chinese SFX models are rare, several TTS and music models support SFX generation for Chinese contexts.

#### Models for Chinese SFX

| Model | Type | Chinese Support | Key Features |
|-------|------|-----------------|--------------|
| **Qwen3-TTS** | TTS + SFX | ✅ Excellent | Free-form voice design, can generate SFX/ambient sounds |
| **Fish Speech V1.5** | Audio Generation | ✅ Strong | High-quality sound effects, multilingual |
| **Audio-Omni** | Unified | ✅ General | End-to-end audio generation and editing |
| **AudioX** | Unified | ✅ General | Text/video/image/audio conditioned generation |
| **CosyVoice2-0.5B** | TTS+SFX | ✅ Good | Real-time audio generation including SFX |

#### Commercial Options for Chinese SFX

| Provider | Model | Chinese Support | Notes |
|----------|-------|-----------------|-------|
| **Stability AI** | Stable Audio 2.5 | ✅ via prompts | Generate SFX from Chinese text prompts |
| **ElevenLabs** | SFX Generator | ✅ via prompts | Generate sound effects with Chinese context |

#### Chinese SFX Usage Example

```python
# Using Qwen3-TTS for SFX
pipe = pipeline(
    "text-to-speech",
    model="qwen/qwen3-tts-1.7b",
    device="cuda"
)

# Generate ambient sounds
sfx_audio = pipe("环境声音：下雨和雷声")  # "Ambient sounds: rain and thunder"
sf.write("rain_thunder.wav", sfx_audio["audio"], samplerate=sfx_audio["sampling_rate"])
```

---

### Chinese Model Summary Table

| Task | Best Model | Runner-Up | Professional Option |
|------|------------|-----------|-------------------|
| **Transcription** | Canary-Qwen 2.5B | FireRedASR | IBM Granite Speech 3.3 |
| **TTS (Quality)** | Fish Speech V1.5 | Qwen3-TTS | ChatTTS |
| **TTS (Speed)** | MeloTTS-Chinese | CosyVoice2 | Parler-TTS |
| **TTS (Cloning)** | GPT-SoVITS | Qwen3-TTS | - |
| **Music** | YuE | SongGeneration v2 | ACE-Step 1.5 XL |
| **SFX** | Qwen3-TTS | Fish Speech V1.5 | Stability Audio 2.5 |

---

### Complete Chinese Model Directory

#### STT Models Quick Reference
```
# Chinese models for /transcribe or /audialize "transcribe:..."
canary-qwen-2.5b        # Best overall accuracy
firered-asr            # Mandarin-optimized
granite-speech-3.3    # IBM, robust
qwen3-asr             # Alibaba, challenging audio
whisper-large-zh-cv11 # Fine-tuned Whisper
```

#### TTS Models Quick Reference
```
# Chinese models for /audialize "speak:..." or /tts
fish-speech-v1.5       # Best quality (1.3% CER)
qwen3-tts-1.7b        # Best features (cloning, streaming)
chattts               # Conversational
cosyvoice2-0.5b       # Real-time, low latency
melotts-chinese       # CPU-friendly
```

#### Music Models Quick Reference
```
# Chinese models for /audialize "music:..."
yue                    # Full-song, style transfer
tencent-songgen-v2    # Commercial-grade
ace-step-1.5-xl        # Cross-platform
```

---

## Command Architecture

### Core Escape Commands

| Command | Syntax | Description |
|---------|--------|-------------|
| `/audialize` | `/audialize <prompt> ...` | Primary audio command - generates or analyzes based on context |
| `/transcribe` | `/transcribe <file> [options]` | Dedicated speech-to-text transcription |
| `/transcribemirror` | `/transcribemirror <varname>` | Capture last transcription to variable |
| `/model` | `/model <model_name> [options]` | Select audio model for subsequent operations |
| `/audiocap` | `/audiocap` | Report available audio capabilities |
| `/audiomodel` | `/audiomodel` | List available audio models |
| `/audiodir` | `/audiodir [path]` | Get/set audio output directory |
| `/listaudio` | `/listaudio [filter]` | List generated audio files |
| `/loadaudio` | `/loadaudio <file_or_url> [varname]` | Load audio file into memory |
| `/play` | `/play <file_or_var> [volume]` | Play audio file or variable |
| `/audiobank` | `/audiobank <name> [action]` | Manage audio banks (collections) |
| `/audiomirror` | `/audiomirror <varname>` | Capture last audio to variable |

### The `/audialize` Command

**Primary verb for all audio operations** - context determines action:

```
/audialize "a hammer sound"                    # Generate sound effect
/audialize "generate: a hammer sound"           # Explicit generation
/audialize "analyze: ambient_noise.wav"         # Analyze/recognize sounds
/audialize "transcribe: speech.wav"            # Speech-to-text
/audialize "speak: Hello world"                 # Text-to-speech
/audialize "music: upbeat jazz"                 # Generate music
/audialize "describe: song.mp3"                 # Describe audio content
```

**Syntax**: `/audialize "<mode>: <prompt_or_file>" [options]`

**Modes**:
- `generate` or `sfx` - Sound effect generation (default for prompts)
- `analyze` or `recognize` - Sound recognition/classification
- `transcribe` or `stt` - Speech-to-text
- `speak` or `tts` - Text-to-speech
- `music` - Music generation
- `describe` - Audio description (metadata, features)
- `separate` - Source separation (vocals, instruments)

---

## Model Management with `/model`

### Selecting Audio Models

```
/model gpt-4o-transcribe       # OpenAI STT (transcription)
/model gpt-4o-mini-tts         # OpenAI TTS (speech synthesis)
/model stable-audio-2.5       # Stability AI (music & SFX)
/model voxtral-mini-3b         # Local STT (Mistral)
/model parler-tts-md-beat      # Local TTS (Hugging Face)
/model musicgen-small         # Local music generation
```

### Model Types

| Model Category | Models | Use Case |
|----------------|--------|----------|
| **STT (Speech-to-Text)** | gpt-4o-transcribe, whisper-1, voxtral-mini-3b, voxtral-small-24b, voxtral-mini-4b-realtime, canary-* | Audio transcription |
| **TTS (Text-to-Speech)** | gpt-4o-mini-tts, tts-1-hd, elevenlabs-*, parler-*, voxtral-tts-4b* | Speech synthesis |
| **Music/SFX** | stable-audio-2.5, musicgen, diffrhythm | Audio generation |
| **Recognition** | gpt-4o-transcribe, yamnet, vggish | Sound classification |
| **Voice ID** | assemblyai, vosk, deepgram | Speaker identification |

### Model Configuration

Models can be configured with provider-specific settings:

```
/model gpt-4o-mini-tts voice=alloy format=wav speed=1.0
/model stable-audio-2.5 duration=30 format=mp3
/model voxtral-mini-3b device=cuda language=en
```

---

## Capability Detection

### `/audiocap` Command

Reports what audio operations are available based on configured models and APIs:

```
/audiocap
```

**Output**:
```json
{
  "audio_capable": true,
  "capabilities": {
    "generate": {
      "sound_effects": true,
      "music": true,
      "speech": true,
      "models": ["stable-audio-2.5", "gpt-4o-mini-tts", "parler-tts"]
    },
    "analyze": {
      "transcription": true,
      "sound_recognition": true,
      "voice_identification": false,
      "models": ["gpt-4o-transcribe", "yamnet"]
    }
  },
  "providers": {
    "openai": {"stt": true, "tts": true, "configured": true},
    "stability": {"music": true, "sfx": true, "configured": false},
    "local": {"stt": true, "tts": true, "configured": true}
  }
}
```

### `/audiomodel` Command

Lists all available audio models:

```
/audiomodel
```

**Output**:
```json
{
  "models": [
    {
      "name": "gpt-4o-transcribe",
      "type": "stt",
      "provider": "openai",
      "description": "Speech-to-text with speaker diarization",
      "configured": true,
      "formats": ["mp3", "wav", "m4a", "ogg", "flac", "webm"]
    },
    {
      "name": "gpt-4o-mini-tts",
      "type": "tts",
      "provider": "openai",
      "description": "Text-to-speech with style control",
      "configured": true,
      "voices": 30,
      "formats": ["mp3", "wav", "opus", "aac", "flac", "pcm"]
    },
    {
      "name": "stable-audio-2.5",
      "type": "generation",
      "provider": "stability",
      "description": "Music and sound effect generation",
      "configured": false,
      "max_duration": 180
    }
  ]
}
```

---

## Directory Structure (Matching Image Pattern)

### Audio File Organization

```
~/chatybot_audio/
├── 2025-01-15/
│   ├── generate/
│   │   ├── sfx_001.mp3          # Sound effects
│   │   ├── music_001.mp3         # Generated music
│   │   └── speech_001.wav        # Generated speech
│   ├── analyze/
│   │   └── transcript_001.json   # Transcription results
│   ├── recognize/
│   │   └── recognition_001.json  # Sound recognition results
│   └── index.json                # Date-level index
└── 2025-01-16/
    └── ...
```

### Index Files (JSON)

Each date directory contains an `index.json` that tracks counters and metadata:

**`~/chatybot_audio/2025-01-15/index.json`**:
```json
{
  "date": "2025-01-15",
  "counters": {
    "generate": {
      "sfx": 1,
      "music": 1,
      "speech": 1
    },
    "analyze": {
      "transcript": 1,
      "recognition": 0
    }
  },
  "models_used": ["stable-audio-2.5", "gpt-4o-transcribe"],
  "total_files": 4,
  "total_size_mb": 12.5
}
```

### Per-File Metadata

Each generated file has a companion `.meta.json`:

**`~/chatybot_audio/2025-01-15/generate/sfx_001.meta.json`**:
```json
{
  "filename": "sfx_001.mp3",
  "category": "generate",
  "subtype": "sfx",
  "prompt": "a hammer sound",
  "model": "stable-audio-2.5",
  "provider": "stability",
  "format": "mp3",
  "duration": 2.5,
  "sample_rate": 44100,
  "channels": 2,
  "bitrate": 128000,
  "size_bytes": 320000,
  "created": "2025-01-15T14:30:22Z",
  "base64": "data:audio/mp3;base64,SUQzBA..."
}
```

> **Note**: The `base64` field contains the client-side base64-encoded version of the raw bytes returned from the API. The API itself returns raw binary data (not base64), which chatybot converts to base64 for JSON storage.

---

## The `/transcribe` Command - Dedicated STT

### Overview

`/transcribe` is a dedicated command for **speech-to-text transcription**, providing a simple, focused interface for converting spoken audio to text. It serves as a convenient shortcut for the most common audio operation.

**Note**: `/transcribe` is functionally equivalent to `/audialize "transcribe: <file>"` but provides a cleaner syntax for this specific use case.

### Syntax

```
/transcribe <file> [options]
```

### Usage Examples

```
# Basic transcription
/transcribe speech.wav

# Transcribe with specific model
/transcribe meeting.mp3 model=gpt-4o-transcribe

# Transcribe with language hint
/transcribe french_audio.mp3 language=fr

# Transcribe with diarization (speaker identification)
/transcribe conversation.mp3 diarization=true

# Transcribe with word timestamps
/transcribe speech.wav timestamps=true

# Transcribe from URL
/transcribe https://example.com/speech.mp3

# Transcribe and save to variable
/transcribe speech.wav
transcribemirror my_text
```

### Options

| Option | Values | Default | Description |
|--------|--------|---------|-------------|
| `model` | Model name | Current STT model | Override active STT model |
| `language` | Language code | Auto-detect | Hint for language (en, fr, de, etc.) |
| `diarization` | true, false | false | Enable speaker diarization |
| `timestamps` | true, false | false | Include word-level timestamps |
| `format` | json, text, srt | json | Output format |
| `output` | filename | Auto-generated | Output file for JSON/SRT |

### Output

**Console Output**:
```
Transcription: The quick brown fox jumps over the lazy dog.
Model: gpt-4o-transcribe | Language: en | Duration: 3.2s | Speakers: 1
```

**Default JSON File** (`~/chatybot_audio/2025-01-15/analyze/transcript_001.json`):
See [Transcription Output](#transcription-output) section for format details.

### `/transcribemirror` Command

Captures the last transcription result into a variable:

```
/transcribe speech.wav
/transcribemirror my_text
# my_text now contains: "The quick brown fox jumps over the lazy dog."
```

### Comparison: `/transcribe` vs `/audialize "transcribe: ..."`

| Feature | `/transcribe <file>` | `/audialize "transcribe: <file>"` |
|---------|--------------------|-----------------------------------|
| Syntax | Simpler | More explicit |
| Default model | Current STT model | Current audio model (if set) |
| Output | Text + JSON | Text + JSON |
| Use case | Quick transcription | Part of complex audio pipeline |

Both commands ultimately call the same underlying transcription logic.

---

# The `/audialize` Command - Full Specification

### Command Format

```
/audialize "<action>: <content>" [options]
```

Where:
- `<action>` determines the operation type
- `<content>` is either a text prompt or file path
- `[options]` are key=value pairs

### Action Types

#### 1. Generation Actions

| Action | Aliases | Example | Output |
|--------|---------|---------|--------|
| `generate` | `create`, `make` | `/audialize "generate: a hammer sound"` | SFX audio file |
| `sfx` | `sound`, `effect` | `/audialize "sfx: robot laser"` | SFX audio file |
| `music` | `song`, `compose` | `/audialize "music: upbeat jazz solo"` | Music audio file |
| `speak` | `tts`, `say` | `/audialize "speak: Hello world"` | Speech audio file |

#### 2. Analysis Actions

| Action | Aliases | Example | Output |
|--------|---------|---------|--------|
| `transcribe` | `stt`, `to_text` | `/audialize "transcribe: speech.wav"` | Text + JSON |
| `analyze` | `describe`, `classify` | `/audialize "analyze: ambient.wav"` | JSON description |
| `recognize` | `identify`, `detect` | `/audialize "recognize: soundscape.mp3"` | Sound labels |
| `separate` | `split`, `isolate` | `/audialize "separate: song.mp3"` | Multiple audio files |

#### 3. Default Behavior (No Action Specified)

When no action is specified, `/audialize` interprets based on input:

```
/audialize "a hammer sound"              # → generate SFX (prompt looks like description)
/audialize "Hello world"                  # → generate TTS (text without file extension)
/audialize "audio_file.wav"               # → analyze/describe (file reference)
/audialize "transcribe this.wav"          # → transcribe (word "transcribe" in input)
```

### Options

Global options (apply to all actions):

| Option | Values | Default | Description |
|--------|--------|---------|-------------|
| `model` | Model name | Current model | Override active model |
| `format` | mp3, wav, flac, etc. | mp3 | Output format |
| `output` | filename | Auto-generated | Output filename |
| `dir` | Path | Current audiodir | Output directory |
| `overwrite` | true, false | false | Overwrite existing |

Action-specific options:

| Action | Options |
|--------|---------|
| `generate`/`sfx`/`music` | `duration=30` (seconds), `style=...`, `temperature=0.7` |
| `speak`/`tts` | `voice=alloy`, `speed=1.0`, `pitch=1.0` |
| `transcribe` | `language=en`, `diarization=true`, `timestamp=true` |
| `analyze` | `type=sound` (sound, music, speech), `detail=high` |

### Examples

```
# Generate sound effect with specific model and format
/audialize "sfx: a hammer hitting metal" model=stable-audio-2.5 format=wav

# Transcribe with diarization
/audialize "transcribe: meeting.mp3" diarization=true language=en

# Generate speech with specific voice
/audialize "speak: The quick brown fox" voice=alloy speed=0.9

# Analyze audio file
/audialize "analyze: ambient.wav" type=sound detail=high

# Generate music with duration
/audialize "music: relaxing piano" duration=60 model=stable-audio-2.5

# Use current model (previously set with /model)
/model gpt-4o-mini-tts
/audialize "Hello there"
```

### Output

Successful `/audialize` commands:
1. Generate audio file with sequential naming
2. Print result summary
3. Store metadata in JSON
4. Optionally store base64 in variable if using `/audialize` with var assignment

**Example output**:
```
Generated: ~/chatybot_audio/2025-01-15/generate/sfx_001.mp3
Model: stable-audio-2.5 | Duration: 2.5s | Format: mp3 | Size: 320KB
Prompt: a hammer sound
```

---

## Audio Banks

### Concept

Audio banks are named collections of audio files that can be referenced by name in scripts. Similar to image banks but for audio.

### Commands

| Command | Syntax | Description |
|---------|--------|-------------|
| `/audiobank` | `/audiobank` | List all audio banks |
| `/audiobank <name>` | `/audiobank ambient` | List files in bank |
| `/audiobank <name> load <file>` | `/audiobank ambient load forest.wav` | Add to bank |
| `/audiobank <name> remove <file>` | `/audiobank ambient remove forest.wav` | Remove from bank |
| `/audiobank <name> clear` | `/audiobank ambient clear` | Empty bank |

### Bank Storage

Audio banks are stored in `BufferManager`:

```python
self.audio_banks = {
    "ambient": [
        {"name": "forest.wav", "path": "~/chatybot_audio/2025-01-15/.../forest.wav", "base64": "..."},
        {"name": "rain.wav", "path": "...", "base64": "..."}
    ],
    "sfx": [...],
    "music": [...]
}
```

### Bank Usage in Scripts

```chatdsl
# Load files into bank
audiobank ambient load forest.wav
audiobank ambient load rain.wav

# Reference bank audio in audialize
audialize "analyze: [ambient:forest.wav]"

# Play from bank
play ambient:forest.wav
```

---

## Variable Integration

### Audio in Variables

Audio data is stored in script variables using **base64 encoding with MIME type prefix**, matching the image variable pattern:

```
/audialize "sfx: hammer sound"
audiomirror hammer_sound

# hammer_sound now contains: data:audio/mp3;base64,SUQzBA...

/audialize "speak: Hello world"
audiomirror greeting
# greeting contains: data:audio/mp3;base64,VjU7RA... (format from /model or default)
```

**Format**: `data:audio/<format>;base64,<base64_encoded_bytes>`

### `/audiomirror` Command

Captures the last generated or loaded audio into a variable:

```
/audialize "speak: Important message"
/audiomirror notification
# notification variable now contains the audio in base64 format

/transcribe speech.wav
/transcribemirror my_text
# my_text variable contains plain text (not base64)
```

### Variable Detection

Variables containing audio data are automatically detected by checking for the `data:audio/` prefix:

```python
# In buffer_manager.py
def is_audio_variable(var_name):
    value = self.script_vars.get(var_name, "")
    return value.startswith("data:audio/")

def get_audio_format(var_name):
    """Extract format from audio variable."""
    value = self.script_vars.get(var_name, "")
    if value.startswith("data:audio/"):
        # Format is between "data:audio/" and ";base64,"
        parts = value.split(";")
        if len(parts) >= 1:
            return parts[0].replace("data:audio/", "")
    return None
```

### Transcription Variables

**Important distinction**: Transcription results (`/transcribe`, `/audialize "transcribe:..."`) produce **text strings**, not audio data:

```
/transcribe speech.wav
/transcribemirror my_text
# my_text = "The quick brown fox..." (plain text)

/audialize "sfx: beep"
/audiomirror my_audio
# my_audio = "data:audio/mp3;base64,..." (base64 encoded audio)
```

### Example: Audio in Chat Flow

```
User: Generate a notification sound
/audialize "sfx: notification beep"
/audiomirror beep

User: Play it
/play [beep]

User: What is that?
/audialize "analyze: [beep]"
```

---

## Directory Management

### `/audiodir` Command

Get or set the audio output directory:

```
/audiodir                    # Show current directory
/audiodir ~/custom_audio    # Set custom directory
/audiodir                   # Show: Current audio directory: ~/custom_audio
```

### `/listaudio` Command

List audio files with filtering:

```
/listaudio                    # All audio files
/listaudio generate           # Only generated files
/listaudio 2025-01-15         # Files from specific date
/listaudio sfx                # Only SFX files
/listaudio *.mp3              # Filter by extension
```

**Output**:
```
Audio Files in ~/chatybot_audio:
┌─────────────┬──────────┬─────────┬─────────┬─────────────┐
│ Date        │ Category  │ Type    │ Format  │ Filename    │
├─────────────┼──────────┼─────────┼─────────┼─────────────┤
│ 2025-01-15  │ generate  │ sfx     │ mp3     │ sfx_001.mp3 │
│ 2025-01-15  │ generate  │ music   │ mp3     │ music_001.mp3│
│ 2025-01-15  │ analyze   │ transcript│ json   │ transcript_001.json│
└─────────────┴──────────┴─────────┴─────────┴─────────────┘
Total: 3 files, 15.2 MB
```

### `/loadaudio` Command

Load external audio files into the system:

```
/loadaudio ambience.mp3                    # Load to current dir
/loadaudio https://example.com/sound.wav  # Load from URL
/loadaudio speech.wav message             # Load to variable 'message'
```

---

## Playback with `/play`

### Basic Playback

```
/play sfx_001.mp3
/play ~/chatybot_audio/2025-01-15/generate/sfx_001.mp3
/play [hammer_sound]       # Play from variable
```

### Volume Control

```
/play sfx_001.mp3 volume=50    # 0-100
/play [beep] volume=0.5         # 0.0-1.0
```

### Background Playback

```
/play background_music.mp3 &    # Play in background
/play sfx_001.mp3 &             # Non-blocking play
```

---

## JSON Output Patterns

### Transcription Output

**`~/chatybot_audio/2025-01-15/analyze/transcript_001.json`**:
```json
{
  "type": "transcription",
  "input_file": "speech.wav",
  "model": "gpt-4o-transcribe",
  "text": "The quick brown fox jumps over the lazy dog.",
  "language": "en",
  "duration": 3.2,
  "speakers": [
    {"id": "spk_0", "text": "The quick brown fox jumps over the lazy dog.", "start": 0.0, "end": 3.2}
  ],
  "word_timestamps": [
    {"word": "The", "start": 0.0, "end": 0.2},
    {"word": "quick", "start": 0.2, "end": 0.5},
    ...
  ],
  "created": "2025-01-15T14:35:00Z"
}
```

### Sound Recognition Output

**`~/chatybot_audio/2025-01-15/analyze/recognition_001.json`**:
```json
{
  "type": "sound_recognition",
  "input_file": "ambient.wav",
  "model": "gpt-4o-transcribe",
  "detection_type": "environmental",
  "sounds": [
    {"label": "rain", "confidence": 0.98, "start": 0.0, "end": 10.0},
    {"label": "thunder", "confidence": 0.87, "start": 3.2, "end": 3.8},
    {"label": "bird_chirping", "confidence": 0.92, "start": 5.0, "end": 10.0}
  ],
  "categories": {
    "nature": 0.95,
    "weather": 0.98,
    "animals": 0.92
  },
  "created": "2025-01-15T14:40:00Z"
}
```

### Audio Description Output

**`~/chatybot_audio/2025-01-15/analyze/describe_001.json`**:
```json
{
  "type": "audio_description",
  "input_file": "song.mp3",
  "model": "gpt-4o-transcribe",
  "format": "mp3",
  "duration": 180.5,
  "sample_rate": 44100,
  "channels": 2,
  "bitrate": 192000,
  "genre": "jazz",
  "genre_confidence": 0.89,
  "mood": "upbeat",
  "mood_confidence": 0.85,
  "tempo": 120,
  "key": "C major",
  "instruments": ["piano", "saxophone", "drums", "bass"],
  "vocals": false,
  "parts": [
    {"type": "intro", "start": 0.0, "end": 8.0},
    {"type": "verse", "start": 8.0, "end": 24.0},
    {"type": "chorus", "start": 24.0, "end": 40.0}
  ],
  "created": "2025-01-15T14:45:00Z"
}
```

---

## Model Configuration Files

### Audio Model Definitions

**`config/audio_models.toml`** (similar to image model configs):

```toml
[models]

# OpenAI Models
[models.openai]
stt = ["gpt-4o-transcribe", "whisper-1"]
tts = ["gpt-4o-mini-tts", "tts-1", "tts-1-hd"]

[models.stability]
generation = ["stable-audio-2.5", "stable-audio-2.0"]

[models.local]
stt = ["voxtral-mini-3b", "voxtral-small-24b", "voxtral-mini-4b-realtime", "voxtral-transcribe-2", "canary-1b-flash", "distil-whisper"]
tts = ["parler-tts-md-beat", "parler-tts-small", "coqui-tts", "voxtral-tts"]
music = ["musicgen-small", "musicgen-medium", "diffrhythm"]

# Model capabilities
[capabilities]
"gpt-4o-transcribe" = ["stt", "transcription", "sound_recognition"]
"gpt-4o-mini-tts" = ["tts", "speech_synthesis"]
"stable-audio-2.5" = ["music_generation", "sound_effect_generation"]
"voxtral-mini-3b" = ["stt", "transcription", "speech_understanding", "qa", "summarization"]
"voxtral-small-24b" = ["stt", "transcription", "speech_understanding", "qa", "summarization"]
"voxtral-mini-4b-realtime" = ["stt", "transcription", "realtime"]
"voxtral-transcribe-2" = ["stt", "transcription", "speaker_diarization"]
"voxtral-tts" = ["tts", "speech_synthesis", "voice_cloning", "zero_shot_cloning", "multilingual"]
"parler-tts-md-beat" = ["tts"]
```

### Model Metadata

Each model has associated metadata:

```toml
[model."gpt-4o-transcribe"]
name = "GPT-4o Transcribe"
provider = "openai"
type = "stt"
description = "Advanced speech-to-text with speaker diarization"
max_file_size = "25MB"
supported_formats = ["mp3", "wav", "m4a", "ogg", "flac", "webm"]
languages = 100+
requires_api_key = true
default = true

[model."stable-audio-2.5"]
name = "Stable Audio 2.5"
provider = "stability"
type = "generation"
description = "High-quality music and sound effect generation"
max_duration = 180
requires_api_key = true
default = false

[model."voxtral-mini-3b"]
name = "Voxtral Mini 3B"
provider = "mistralai"
type = "stt"
description = "State-of-the-art multilingual speech-to-text with speech understanding"
parameters = 3000000000
huggingface_id = "mistralai/Voxtral-Mini-3B-2507"
backbone = "Mistral Small 3.1"
max_audio_length_transcription = "30 minutes"
max_audio_length_understanding = "40 minutes"
vram_bf16 = "9.5 GB"
vram_int4 = "3.7-4 GB"
requires_api_key = false
license = "Apache 2.0"
capabilities = ["asr", "speech_understanding", "qa", "summarization", "multilingual"]
default = false

[model."voxtral-small-24b"]
name = "Voxtral Small 24B"
provider = "mistralai"
type = "stt"
description = "Production-scale state-of-the-art speech-to-text with highest accuracy"
parameters = 24000000000
huggingface_id = "mistralai/Voxtral-Small-24B-2507"
backbone = "Mistral Small 3.1"
vram_bf16 = "55 GB"
vram_int8 = "16-24 GB"
requires_api_key = false
license = "Apache 2.0"
capabilities = ["asr", "speech_understanding", "qa", "summarization", "multilingual"]
default = false

[model."voxtral-mini-4b-realtime"]
name = "Voxtral Mini 4B Realtime"
provider = "mistralai"
type = "stt"
description = "Real-time optimized speech-to-text with low latency for streaming"
parameters = 4000000000
huggingface_id = "mistralai/Voxtral-Mini-4B-Realtime-2602"
backbone = "Mistral Small 3.1"
streaming = true
vram_bf16 = "16 GB"
vram_int4 = "3.7-4 GB"
requires_api_key = false
license = "Apache 2.0"
capabilities = ["asr", "realtime", "streaming", "low_latency"]
default = false

[model."voxtral-tts"]
name = "Voxtral TTS"
provider = "mistralai"
type = "tts"
description = "State-of-the-art text-to-speech model with zero-shot voice cloning"
parameters = 4100000000
release_date = "March 2026"
huggingface_id = "mistralai/Voxtral-TTS-4B"
vram_bf16 = "16 GB"
vram_int4 = "3.7-4 GB"
requires_api_key = false
license = "Apache 2.0"
languages = ["en", "fr", "de", "es", "nl", "pt", "it", "hi", "ar"]
capabilities = ["tts", "speech_synthesis", "voice_cloning", "zero_shot_cloning", "multilingual", "emotional_delivery", "cross_language_voice"]
cloning_min_audio = "3 seconds"
cloning_max_audio = "25 seconds"
cloud_pricing = "$0.016 per 1K characters"
default = false

[model."voxtral-transcribe-2"]
name = "Voxtral Transcribe 2"
provider = "mistralai"
type = "stt"
description = "Latest transcription model with enhanced accuracy"
release_date = "February 2026"
requires_api_key = false
license = "Apache 2.0"
capabilities = ["stt", "transcription", "speaker_diarization"]
default = false
```

---

## State Management

### AudioEngine State

Similar to `ImageGenerator`, `AudioEngine` maintains:

```python
class AudioEngine:
    def __init__(self, config_manager):
        self.config_manager = config_manager
        self.audio_dir = os.path.expanduser("~/chatybot_audio")
        self.counters = {}  # Loaded from index.json files
        self.current_model = None
        self.models = AudioModelRegistry()
        self.last_generated = None  # (category, file_path)
        self.audio_banks = {}  # Managed via BufferManager
```

### Counter Loading (Prevent Overwrite on Restart)

Like `ImageGenerator._load_existing_counters()`:

```python
def _load_existing_counters(self):
    """Load counters from existing index.json files."""
    image_dir = Path(self.audio_dir)
    if not image_dir.exists():
        return
    
    for date_dir in image_dir.iterdir():
        if not date_dir.is_dir():
            continue
        index_path = date_dir / "index.json"
        if index_path.exists():
            try:
                with open(index_path, "r") as f:
                    data = json.load(f)
                if "counters" in data:
                    for category, subcounters in data["counters"].items():
                        if category not in self.counters:
                            self.counters[category] = {}
                        self.counters[category].update(subcounters)
            except (json.JSONDecodeError, IOError):
                pass
```

---

## DSL Integration

### ChatDSL Audio Commands

Audio commands can be used directly in ChatDSL scripts:

```chatdsl
# Set up audio model
model gpt-4o-mini-tts

# Generate introduction
audialize "speak: Welcome to our audio demonstration"
audiomirror intro

# Generate background music
audialize "music: ambient electronic" duration=120
play last &

# Generate sound effect
audialize "sfx: magic sparkle"
play last

# Transcribe user input (assuming user_input.wav exists)
audialize "transcribe: user_input.wav"
echo You said: [transcribe]

# Conditional audio
if: [transcribe] contains "hello"
    audialize "speak: Hello there!"
    play last
endif

# Use audio banks
audiobank sfx load magic_sparkle.wav
audiobank sfx load explosion.wav

# Play from bank
play sfx:magic_sparkle

# Simple transcription with dedicated command
transcribe user_input.wav

# Transcription with variable capture
transcribe interview.mp3
transcribemirror interview_text

echo Interview says: [interview_text]
```

### Valid Escape Commands for chatdsl_parse.py

```python
VALID_ESCAPE_COMMANDS = {
    # Existing commands...
    
    # Audio commands
    "audialize",      # Primary audio command (all operations)
    "transcribe",     # Dedicated speech-to-text
    "transcribemirror", # Capture transcription to variable
    "model",          # Model selection (audio and image)
    "audiocap",       # Audio capability detection
    "audiomodel",    # Audio model listing
    "audiodir",       # Audio directory management
    "listaudio",      # List audio files
    "loadaudio",      # Load audio files
    "play",           # Audio playback
    "audiobank",      # Audio bank management
    "audiomirror",    # Audio variable capture
}
```

---

## Error Handling & Validation

### Audio File Validation

Before processing, validate:

1. **File exists** (for input operations)
2. **Format supported** by selected model
3. **Size within limits** (25MB for OpenAI, etc.)
4. **Directory writable** (for output)

### Capability Checking

Before executing `/audialize`, check if the requested operation is available:

```python
def can_audialize(action: str) -> bool:
    capabilities = get_audio_capabilities()
    
    action_map = {
        "generate": "generate",
        "sfx": "generate",
        "music": "generate",
        "speak": "generate",
        "tts": "generate",
        "transcribe": "analyze",
        "stt": "analyze",
        "analyze": "analyze",
        "recognize": "analyze",
        "describe": "analyze"
    }
    
    category = action_map.get(action, action)
    return capabilities.get(category, {}).get("available", False)
```

---

## Example Session

```
user> /audiocap
{
  "audio_capable": true,
  "capabilities": {
    "generate": {"sound_effects": true, "music": true, "speech": true},
    "analyze": {"transcription": true, "sound_recognition": true}
  }
}

user> /audiomodel
[
  {"name": "gpt-4o-transcribe", "type": "stt", "provider": "openai"},
  {"name": "gpt-4o-mini-tts", "type": "tts", "provider": "openai"},
  {"name": "stable-audio-2.5", "type": "generation", "provider": "stability"}
]

user> /model gpt-4o-mini-tts
Model set to: gpt-4o-mini-tts (Text-to-Speech)

user> /model gpt-4o-mini-tts
Model set to: gpt-4o-mini-tts (Text-to-Speech)

user> /audialize "speak: The quick brown fox jumps over the lazy dog"
Generated: ~/chatybot_audio/2025-01-15/generate/speech_001.mp3
Model: gpt-4o-mini-tts | Voice: alloy | Format: mp3 | Duration: 2.8s

user> /play speech_001.mp3
Playing: speech_001.mp3

user> /audiomirror greeting
Variable 'greeting' set to audio data

# Using dedicated /transcribe command
user> /transcribe speech_001.mp3
Transcription: The quick brown fox jumps over the lazy dog.
Saved: ~/chatybot_audio/2025-01-15/analyze/transcript_001.json

user> /transcribemirror my_text
Variable 'my_text' set to transcription

user> /audialize "transcribe: speech_001.mp3"
Transcription: The quick brown fox jumps over the lazy dog.
Saved: ~/chatybot_audio/2025-01-15/analyze/transcript_002.json

user> /audialize "sfx: sci-fi laser"
Generated: ~/chatybot_audio/2025-01-15/generate/sfx_001.mp3
Model: stable-audio-2.5 | Duration: 1.2s | Format: mp3

user> /model stable-audio-2.5
Model set to: stable-audio-2.5 (Audio Generation)

user> /audialize "music: upbeat electronic dance music" duration=60
Generated: ~/chatybot_audio/2025-01-15/generate/music_001.mp3
Model: stable-audio-2.5 | Duration: 60.0s | Format: mp3

user> /listaudio
Audio Files in ~/chatybot_audio/2025-01-15:
  generate/sfx_001.mp3 (1.2s, stable-audio-2.5)
  generate/speech_001.mp3 (2.8s, gpt-4o-mini-tts)
  generate/music_001.mp3 (60.0s, stable-audio-2.5)
  analyze/transcript_001.json
Total: 4 files
```

---

## Security & Safety Considerations

### API Key Management

- API keys stored in config, never logged
- Keys are masked in output: `API Key: sk-*****`
- Rate limiting handled gracefully with retries

### File System Security

- Output directory validated before use
- Symlink attacks prevented
- Filename sanitization applied

### Content Moderation

- Respect provider content policies
- Warn on potentially problematic prompts
- Allow local override for private instances

---

## Detailed Implementation Breakdown

This section provides a step-by-step breakdown for implementing each audio capability category.

---

### 1. Transcription (STT - Speech-to-Text)

**Purpose**: Convert spoken audio to text

#### Data Flow
```
User Command → Audio File → API Call → Text Result → Variable/JSON Storage
```

#### Step-by-Step Implementation

**Step 1: Command Parsing**
```python
# /transcribe speech.wav
# /transcribe speech.wav model=gpt-4o-transcribe language=en
# /audialize "transcribe: speech.wav"
```

**Step 2: Validate Input**
- Check file exists
- Verify format is supported (MP3, WAV, M4A, OGG, FLAC, WEBM)
- Check file size (OpenAI limit: 25MB)

**Step 3: Select Model**
- Use `/model` command to set active STT model, or default to config
- Supported models: `gpt-4o-transcribe`, `whisper-1`, `voxtral-mini-3b`, `assemblyai`, etc.

**Step 4: API Call**
- **OpenAI**: `POST /v1/audio/transcriptions` with file upload
- **AssemblyAI**: `POST /v1/transcript` with file upload
- **Local**: Run `transformers` pipeline with loaded model

**Step 5: Process Response**
- Extract text from JSON response (`response["text"]` for OpenAI)
- Handle speaker diarization if enabled
- Handle word timestamps if enabled

**Step 6: Storage**
- Save transcription to JSON file in `~/chatybot_audio/YYYY-MM-DD/analyze/transcript_NNN.json`
- Optionally capture to variable via `/transcribemirror` (plain text)
- Update index.json counters

**Step 7: Output**
```
Transcription: [text]
Model: [model_name] | Language: [language] | Duration: [X.X]s | Speakers: [N]
Saved: [filepath]
```

#### Provider-Specific Details

| Provider | Endpoint | Input | Output | Requirements | Models |
|----------|----------|-------|--------|--------------|--------|
| OpenAI | `/v1/audio/transcriptions` | File upload | JSON with `text` | API key | gpt-4o-transcribe, whisper-1 |
| AssemblyAI | `/v1/transcript` | File upload | JSON with `text`, `words[]` | API key | Various |
| Voxtral (local) | `transformers` pipeline | File path | Text | GPU (9.5-55GB VRAM) | Voxtral-Mini-3B, Voxtral-Small-24B, Voxtral-Mini-4B-Realtime |
| Canary (local) | `transformers` pipeline | File path | Text | GPU (4GB VRAM) | Canary-1B-Flash |

#### Example JSON Output Format
```json
{
  "type": "transcription",
  "input_file": "speech.wav",
  "model": "gpt-4o-transcribe",
  "text": "The quick brown fox jumps over the lazy dog.",
  "language": "en",
  "duration": 3.2,
  "speakers": null,
  "word_timestamps": null,
  "created": "2025-01-15T14:35:00Z"
}
```

#### Error Handling
- File not found → `Error: File not found: [path]`
- Unsupported format → `Error: Format [ext] not supported by model [name]`
- File too large → `Error: File size [X]MB exceeds limit of [Y]MB`
- API error → `Error: [provider] API returned [status]: [message]`

---

### 2. Voice Generation (TTS - Text-to-Speech)

**Purpose**: Generate spoken audio from text

#### Data Flow
```
User Text → API Call → Audio Bytes → File Storage → Optional Variable Storage
```

#### Step-by-Step Implementation

**Step 1: Command Parsing**
```python
# /audialize "speak: Hello world"
# /audialize "speak: Hello world" voice=alloy speed=1.0
# /tts "Hello world" -v alloy
```

**Step 2: Validate Input**
- Check text is not empty
- Validate voice parameter (if provided) against available voices
- Validate speed parameter (0.5-2.0 range)

**Step 3: Select Model**
- Use `/model` command or default to config
- Supported models: `gpt-4o-mini-tts`, `tts-1`, `tts-1-hd`, `parler-tts-md-beat`, etc.

**Step 4: API Call**
- **OpenAI**: `POST /v1/audio/speech` with JSON body
- **ElevenLabs**: `POST /v1/text-to-speech/[voice_id]` with JSON body
- **Local**: Run `ParlerTTS` inference

**Step 5: Process Response**
- Read raw bytes from response
- Determine format from headers or config (MP3, WAV, etc.)
- Optionally convert to target format using pydub/ffmpeg

**Step 6: Storage**
- Save audio to file in `~/chatybot_audio/YYYY-MM-DD/generate/speech_NNN.[format]`
- Generate accompanying `.meta.json` with metadata
- Optionally capture to variable via `/audiomirror` (base64 format)
- Update index.json counters

**Step 7: Output**
```
Generated: [filepath]
Model: [model_name] | Voice: [voice] | Format: [format] | Duration: [X.X]s | Size: [X]KB
```

#### Provider-Specific Details

| Provider | Endpoint | Input | Output | Requirements |
|----------|----------|-------|--------|--------------|
| OpenAI | `/v1/audio/speech` | JSON `{model, input, voice, response_format}` | Raw bytes (MP3/WAV/Opus/AAC/FLAC/PCM) | API key |
| ElevenLabs | `/v1/text-to-speech/[voice_id]` | JSON `{text, model_id, voice_settings}` | Raw bytes (MP3) | API key |
| Parler-TTS (local) | Local inference | Text, voice description | Numpy array | GPU (8GB VRAM) |
| Coqui TTS (local) | Local inference | Text | Raw bytes | GPU optional |

#### Voice Options by Provider

**OpenAI (30+ voices)**:
- alloy, echo, fable, onyx, nova, shimmer (v1)
- coral, verse, ballad, ash, sage, marin, cedar (v1)
- amuch, aster, brook, clover, dan, elan, marilyn, meadow, jazz, rio (2025 additions)

**ElevenLabs (1000+ voices)**:
- Use voice ID from `/v1/voices` endpoint
- Supports custom cloned voices

**Local (Parler-TTS)**:
- No predefined voices - use descriptive text
- Example prompts: "A deep authoritative voice", "A cheerful energetic voice"

#### Example Command Flow
```
/model gpt-4o-mini-tts
/audialize "speak: The quick brown fox jumps over the lazy dog" voice=alloy
# → Generates: ~/chatybot_audio/2025-01-15/generate/speech_001.mp3
/audiomirror greeting
# → Variable 'greeting' = "data:audio/mp3;base64,VjU7RA..."
```

#### Error Handling
- Empty text → `Error: Text cannot be empty`
- Invalid voice → `Error: Voice [name] not found for provider [provider]`
- Invalid speed → `Error: Speed must be between 0.5 and 2.0`
- API error → `Error: [provider] API returned [status]: [message]`

---

### 3. Sound Effects

#### 3A. Sound Effect Generation

**Purpose**: Create sound effects from text descriptions

#### Data Flow
```
Text Prompt → API Call → Audio Bytes → File Storage → Optional Variable Storage
```

#### Step-by-Step Implementation

**Step 1: Command Parsing**
```python
# /audialize "sfx: hammer hitting metal"
# /audialize "generate: laser sound"
# /audialize "a hammer sound"  # Implicit SFX mode
```

**Step 2: Validate Input**
- Check prompt is not empty
- Validate duration parameter (if provided, max varies by provider)

**Step 3: Select Model**
- Use `/model` command or default to config
- Supported models: `stable-audio-2.5`, `musicgen-small`, etc.

**Step 4: API Call**
- **Stability AI**: `POST /v2beta/stable-audio/generate` with JSON `{prompt, output_format}`
- **Local (MusicGen)**: Generate with `text` prompt

**Step 5: Process Response**
- **Stability AI**: May return URL - download to get bytes, or get bytes directly
- Convert to target format if needed
- Extract duration from metadata

**Step 6: Storage**
- Save audio to file in `~/chatybot_audio/YYYY-MM-DD/generate/sfx_NNN.[format]`
- Generate `.meta.json` with prompt, model, category=generate, subtype=sfx
- Optionally capture to variable via `/audiomirror` (base64)
- Update index.json counters

**Step 7: Output**
```
Generated: [filepath]
Model: [model_name] | Type: sound_effect | Format: [format] | Duration: [X.X]s
Prompt: [prompt]
```

#### Provider-Specific Details

| Provider | Endpoint | Input | Output | Requirements | Max Duration |
|----------|----------|-------|--------|--------------|---------------|
| Stability AI | `/v2beta/stable-audio/generate` | JSON `{prompt, output_format}` | URL or bytes | API key | 95s (text), 180s (audio-to-audio) |
| Stability AI | `/v1/audio-to-audio` | JSON + audio file | Raw bytes | API key | 95s |
| MusicGen (local) | `transformers` pipeline | Text prompt | Raw bytes | GPU (12GB VRAM) | ~30s |
| DiffRhythm (local) | Local inference | Text prompt | Raw bytes | GPU (8GB VRAM) | Full songs |

#### Example Command Flow
```
/model stable-audio-2.5
/audialize "sfx: futuristic computer beep" duration=2.5
# → Generates: ~/chatybot_audio/2025-01-15/generate/sfx_001.mp3
/audiomirror beep_sound
# → Variable 'beep_sound' = "data:audio/mp3;base64,SUQzBA..."
```

---

#### 3B. Sound Effect / Sound Recognition

**Purpose**: Identify environmental sounds, music, speech vs non-speech

#### Data Flow
```
Audio File → API Call → Sound Labels → JSON Storage → Optional Variable Storage
```

#### Step-by-Step Implementation

**Step 1: Command Parsing**
```python
# /audialize "recognize: ambient.wav"
# /audialize "analyze: forest_sounds.mp3"
```

**Step 2: Validate Input**
- Check file exists
- Verify format is supported

**Step 3: Select Model/Model**
- Use `/model` command or default to config
- Supported models: `gpt-4o-transcribe`, `yamnet`, `vggish`, `screenapp`

**Step 4: API Call**
- **OpenAI**: `POST /v1/audio/transcriptions` (yes, same endpoint for sound recognition)
- **ScreenApp**: `POST` to audio analyzer endpoint
- **Local (YAMNet/VGGish)**: Run `tf.keras` inference

**Step 5: Process Response**
- Extract sound labels with confidence scores
- Optionally extract timestamps for each detected sound
- Categorize sounds (nature, vehicles, music, speech, etc.)

**Step 6: Storage**
- Save results to JSON file in `~/chatybot_audio/YYYY-MM-DD/recognize/recognition_NNN.json`
- Optionally capture to variable via `/audiomirror` (base64 of input audio) or return text labels
- Update index.json counters

**Step 7: Output**
```
Recognized Sounds:
  - rain (98.7% confidence, 0.0-10.0s)
  - thunder (87.2% confidence, 3.2-3.8s)
  - bird_chirping (92.1% confidence, 5.0-10.0s)
Categories: nature (95%), weather (98%), animals (92%)
Model: [model_name] | Input: [filename] | Duration: [X.X]s
Saved: [filepath]
```

#### Provider-Specific Details

| Provider | Endpoint | Input | Output | Requirements | Accuracy |
|----------|----------|-------|--------|--------------|----------|
| OpenAI | `/v1/audio/transcriptions` | File upload | JSON with `text` (interpreted as sound labels) | API key | High |
| ScreenApp | Audio Analyzer API | File upload | JSON with labels | None (free) | 98.7% |
| YAMNet (local) | Local inference | Audio array | Class labels | TensorFlow | High |
| VGGish (local) | Local inference | Audio array | Embeddings for classification | TensorFlow | High |

#### Example JSON Output Format
```json
{
  "type": "sound_recognition",
  "input_file": "ambient.wav",
  "model": "gpt-4o-transcribe",
  "detection_type": "environmental",
  "sounds": [
    {"label": "rain", "confidence": 0.987, "start": 0.0, "end": 10.0},
    {"label": "thunder", "confidence": 0.872, "start": 3.2, "end": 3.8}
  ],
  "categories": {
    "nature": 0.95,
    "weather": 0.98,
    "animals": 0.92
  },
  "created": "2025-01-15T14:40:00Z"
}
```

---

### 4. Music

#### 4A. Music Generation

**Purpose**: Create music from text descriptions

#### Data Flow
```
Text Prompt → API Call → Audio Bytes → File Storage → Optional Variable Storage
```

#### Step-by-Step Implementation

**Step 1: Command Parsing**
```python
# /audialize "music: upbeat jazz solo"
# /audialize "generate: relaxing piano music"
# /audialize "music: electronic dance" duration=60
```

**Step 2: Validate Input**
- Check prompt is not empty
- Validate duration (max depends on provider: 180s for Stability, ~30s for MusicGen)

**Step 3: Select Model**
- Use `/model` command or default to config
- Supported models: `stable-audio-2.5`, `musicgen-small`, `musicgen-medium`, `diffrhythm`

**Step 4: API Call**
- **Stability AI**: `POST /v2beta/stable-audio/generate` with JSON `{prompt, output_format}`
- **Local (MusicGen)**: Generate with `text` description

**Step 5: Process Response**
- **Stability AI**: Typically returns URL - download to get bytes
- Extract or estimate duration
- Validate output format

**Step 6: Storage**
- Save audio to file in `~/chatybot_audio/YYYY-MM-DD/generate/music_NNN.[format]`
- Generate `.meta.json` with prompt, model, category=generate, subtype=music
- Optionally capture to variable via `/audiomirror` (base64)
- Update index.json counters

**Step 7: Output**
```
Generated: [filepath]
Model: [model_name] | Type: music | Format: [format] | Duration: [X.X]s
Prompt: [prompt]
```

#### Provider-Specific Details

| Provider | Endpoint | Input | Output | Requirements | Max Duration |
|----------|----------|-------|--------|--------------|---------------|
| Stability AI | `/v2beta/stable-audio/generate` | JSON `{prompt, output_format}` | URL or bytes | API key | 95s (text-to-music) |
| Stability AI | `/v1/audio-to-audio` | JSON + audio reference | Raw bytes | API key | 180s (audio-to-audio) |
| MusicGen (local) | `transformers` pipeline | Text prompt | Raw bytes | GPU (12GB VRAM) | ~30s |
| DiffRhythm (local) | Local inference | Text prompt | Raw bytes | GPU (8GB VRAM) | Full songs |

#### Example Command Flow
```
/model stable-audio-2.5
/audialize "music: ambient electronic background" duration=120
# → Generates: ~/chatybot_audio/2025-01-15/generate/music_001.mp3
/audiomirror background_music
# → Variable 'background_music' = "data:audio/mp3;base64,..."
/play [background_music] &
```

---

#### 4B. Music Identification

**Purpose**: Identify music genre, mood, instruments, structure from audio

#### Data Flow
```
Audio File → API Call → Music Metadata → JSON Storage → Optional Variable Storage
```

#### Step-by-Step Implementation

**Step 1: Command Parsing**
```python
# /audialize "describe: song.mp3"
# /audialize "analyze: music.wav" type=music
```

**Step 2: Validate Input**
- Check file exists
- Verify it's a music file (not speech-only)

**Step 3: Select Model**
- Use `/model` command or default to music analysis model
- Supported models: `gpt-4o-transcribe`, custom local models

**Step 4: API Call**
- **OpenAI**: `POST /v1/audio/transcriptions` with music description prompt
- **Local**: Run custom music analysis model (VGGish adapted, or dedicated music tagger)

**Step 5: Process Response**
- Extract genre, mood, tempo, key
- Identify instruments
- Segment structure (intro, verse, chorus, etc.)
- Detect vocals vs instrumental

**Step 6: Storage**
- Save results to JSON file in `~/chatybot_audio/YYYY-MM-DD/analyze/music_NNN.json`
- Update index.json counters

**Step 7: Output**
```
Music Analysis:
  Genre: jazz (89% confidence)
  Mood: upbeat (85% confidence)
  Tempo: 120 BPM
  Key: C major
  Instruments: piano, saxophone, drums, bass
  Vocals: No
  Structure: intro (0-8s), verse (8-24s), chorus (24-40s),...
Model: [model_name] | Input: [filename]
Saved: [filepath]
```

#### Provider-Specific Details

| Provider | Endpoint | Input | Output | Requirements |
|----------|----------|-------|--------|--------------|
| OpenAI | `/v1/audio/transcriptions` | File + description prompt | JSON with text description | API key |
| AcousticBrainz | API | Audio file | JSON with music features | None |
| Essentia (local) | Local analysis | Audio file | JSON with detailed features | None |
| VGGish (local) | Local inference | Audio array | Embeddings for classification | TensorFlow |

#### Example JSON Output Format
```json
{
  "type": "music_analysis",
  "input_file": "song.mp3",
  "model": "gpt-4o-transcribe",
  "format": "mp3",
  "duration": 180.5,
  "sample_rate": 44100,
  "genre": "jazz",
  "genre_confidence": 0.89,
  "mood": "upbeat",
  "mood_confidence": 0.85,
  "tempo": 120,
  "key": "C major",
  "instruments": ["piano", "saxophone", "drums", "bass"],
  "vocals": false,
  "parts": [
    {"type": "intro", "start": 0.0, "end": 8.0},
    {"type": "verse", "start": 8.0, "end": 24.0},
    {"type": "chorus", "start": 24.0, "end": 40.0}
  ],
  "created": "2025-01-15T14:45:00Z"
}
```

---

### Shared Infrastructure Components

All audio capabilities share the following infrastructure:

1. **AudioEngine** - Main orchestrator class
2. **AudioFileManager** - Handles file storage, naming, index.json management
3. **AudioModelRegistry** - Manages available models, capabilities, defaults
4. **AudioProvider Interface** - Abstract base for all providers
5. **BufferManager Integration** - Audio banks and variables
6. **ConfigManager Integration** - Audio settings and API keys

---

## Comparison: Image vs Audio Commands

| Image Command | Audio Equivalent | Purpose |
|---------------|-----------------|---------|
| `/imagine` | `/audialize` | Generation |
| `/imagesize` | N/A (audio has duration) | Size setting |
| `/imagequality` | N/A (audio has bitrate) | Quality setting |
| `/saveimage` | `/audialize` (saves automatically) | Save output |
| `/imagedir` | `/audiodir` | Set output directory |
| `/listimages` | `/listaudio` | List files |
| `/showimage` | `/play` | Display/play output |
| `/loadimage` | `/loadaudio` | Load external file |
| `/imagebank1-5` | `/audiobank` | Bank management |
| N/A | `/model` | Model selection |
| N/A | `/audiocap` | Capability detection |
| N/A | `/audiomodel` | Model listing |
| N/A | `/audiomirror` | Audio variable capture |
| N/A | `/transcribe` | Dedicated STT |
| N/A | `/transcribemirror` | Transcription variable capture |

---

## Future Extensions

### Audio Filters & Effects

```
/audialize "speak: Hello" effect=reverb
/audialize "music: piano" effect=pitch_shift+2
/audialize "speech.wav" effect=noise_reduction
```

### Audio Chaining

```
# Generate and immediately process
audialize "speak:Input text" | transcribe

# Chain operations
audialize "generate: drum beat" then "analyze: last"
```

### Multi-Track Composition

```
audialize "music: bass line" track=bass
audialize "music: melody" track=melody
audialize "music: drums" track=drums
/audialize "mix: all tracks"
```

### Real-Time Audio

```
/audialize "listen"                  # Start recording
/audialize "stop"                   # Stop and process
/audialize "stream: microphone"      # Stream from mic
```

---

## API Response Formats

### Audio Data Return Types

Based on 2025 API specifications, audio APIs return data in the following formats:

| Provider | Endpoint | Response Format | Notes |
|----------|----------|-----------------|-------|
| OpenAI | TTS (`/v1/audio/speech`) | **Raw bytes** | Binary audio file (MP3/WAV/etc.) in response body. Not base64-encoded by default. |
| OpenAI | STT (`/v1/audio/transcriptions`) | **JSON** | Returns `{"text": "..."}` - text only, not audio bytes |
| OpenAI | Realtime API | **Base64 chunks** | WebSocket sends `response.output_audio.delta` as base64-encoded chunks |
| Stability AI | Stable Audio | **Raw bytes** | Binary audio file. Input accepts base64 data URIs. |
| ElevenLabs | TTS | **Raw bytes** | Binary audio output. Input accepts base64-encoded audio for voice references. |
| ElevenLabs | STT | **JSON** | Returns transcription text with `is_base64_encoded` flag |
| AssemblyAI | Transcription | **JSON** | Always returns JSON with text, never audio bytes |
| Local Models | Various | **Raw bytes** | Binary output from model inference |

### Client-Side Base64 Handling

**Pattern used in chatybot**: Audio data is **converted to base64 on the client side** for storage in variables and JSON metadata, following the same pattern as images:

```python
# For variable storage
audio_bytes = response.content  # From API
base64_audio = f"data:audio/{format};base64,{base64.b64encode(audio_bytes).decode('utf-8')}"

# For JSON metadata
{
  "filename": "speech_001.mp3",
  "format": "mp3",
  "duration": 2.8,
  "base64": "data:audio/mp3;base64,SUQzBA..."
}
```

### Implementation Guidance

1. **Generation APIs (TTS, Music, SFX)**: Expect raw bytes, convert to base64 for storage
2. **Recognition APIs (STT, Classification)**: Expect JSON with text results
3. **Input to APIs**: Some accept base64-encoded data (check provider docs)
4. **Storage**: Use base64 prefix notation: `data:audio/<format>;base64,<data>`

### Response Format Details by Provider

#### OpenAI Audio API

**TTS (`POST /v1/audio/speech`)**:
- Response: Raw binary audio (MP3, WAV, etc.)
- Content-Type: `audio/mpeg` (MP3) or `audio/wav` (WAV)
- Client must read as bytes and optionally encode to base64

**STT (`POST /v1/audio/transcriptions`)**:
- Response: JSON with transcription text
- No audio bytes returned (input was audio, output is text)

#### Stability AI Stable Audio

**Generation (`POST /v2beta/stable-audio/generate`)**:
- Response: Typically a URL to download the generated audio
- Client downloads URL to get raw bytes, then encodes to base64
- Alternative: Some endpoints may return bytes directly

#### ElevenLabs

**TTS**:
- Response: Raw bytes (MP3 format typically)
- Input for voice cloning: Must be base64-encoded
- Some responses include `is_base64_encoded` boolean flag

**STT**:
- Response: JSON with transcription
- May include base64-encoded audio references

#### AssemblyAI

**Transcription**:
- Response: Always JSON with `text`, `words`, `confidence`, etc.
- Never returns audio bytes (transcription service only)
- Accepts audio input as bytes or base64-encoded

### Summary: Keys Points for Chatybot Implementation

1. **APIs return raw bytes for generation** (TTS, Music, SFX) - chatybot converts to base64 for storage
2. **APIs return JSON for analysis** (STT, Recognition) - no audio bytes in response
3. **Base64 is client-side only** - used for variable storage and JSON metadata, matching image pattern
4. **Input flexibility** - Some APIs accept base64-encoded input, but this is provider-specific
5. **Format**: Always use `data:audio/<format>;base64,<data>` prefix pattern

---

## Implementation Notes (For Future Development)

### Core Components

1. **AudioEngine** - Main orchestrator (like ImageGenerator)
2. **AudioModelRegistry** - Manages available models and capabilities
3. **AudioFileManager** - Handles file storage with counter persistence
4. **AudioProvider** interface - Base class for all audio providers

### Provider Classes

```
AudioProvider (ABC)
├── OpenAIProvider
│   ├── OpenAISTT
│   ├── OpenAITTS
│   └── OpenAIAudioAnalysis
├── StabilityProvider
│   └── StabilityAudioGeneration
├── LocalProvider
│   ├── LocalSTT
│   ├── LocalTTS
│   └── LocalMusic
└── AssemblyAIProvider
    ├── AssemblyAISTT
    └── AssemblyAIVoice
```

### Command Handler Structure

```python
class AudioCommandHandler:
    def __init__(self, audio_engine, buffer_manager):
        self.engine = audio_engine
        self.buffer = buffer_manager
        
    async def handle_audialize(self, args):
        # Parse action and content
        # Validate capabilities
        # Execute operation
        # Return result
        pass
    
    async def handle_model(self, args):
        # Set active audio model
        pass
        
    async def handle_audiocap(self, args):
        # Return capabilities
        pass
    
    # ... other handlers
```

---

## Summary of Changes from v1

| Aspect | v1 | v2 |
|--------|----|----|
| Primary command | Multiple commands | Single `/audialize` verb |
| Model selection | Per-operation | `/model` command |
| Capability detection | N/A | `/audiocap` command |
| Directory structure | Custom | Matches image pattern |
| File naming | Custom | Matches image pattern |
| JSON metadata | Basic | Comprehensive |
| Variable handling | Separate | Integrated like images |
| Bank management | Separate commands | `/audiobank` command |

---

## Conclusion

This revised plan (v2) presents a **unified, consistent audio processing system** for chatybot that:

1. ✅ Uses **escape commands** like the image system
2. ✅ Centers on **`/audialize`** as the primary verb
3. ✅ Uses **`/model`** for audio model selection
4. ✅ Provides **`/audiocap`** for capability detection
5. ✅ Follows **image generator patterns** (JSON, directory structure)
6. ✅ Stores audio in **base64-encoded variables**
7. ✅ Supports **audio banks** like image banks
8. ✅ Integrates seamlessly with **ChatDSL scripts**

The design is **cohesive, extensible, and consistent** with existing chatybot patterns while providing comprehensive audio capabilities.

---

**Note**: This is a **draft plan only**. No code implementation or file modifications have been made.

*Document generated based on 2024-2025 research of audio AI models, APIs, and best practices.*
