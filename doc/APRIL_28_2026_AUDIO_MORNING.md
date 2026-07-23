# Audio Implementation Fixes - April 28, 2026

## Summary
Fixed Mistral STT transcription to use the correct API endpoint (`/v1/audio/transcriptions`) with proper multipart/form-data formatting, resolving rate limit errors and hallucination issues.

---

## ✅ Fixes Implemented

### 1. Endpoint Correction
**Problem**: Using `/chat/completions` with `input_audio` caused two issues:
- Model treated transcription as conversational prompt, adding "It seems like you're asking..." filler
- Rate limit errors (429) on files > ~200KB base64

**Fix**: Switched to dedicated `/v1/audio/transcriptions` endpoint
```toml
# src/chatybot/chat_config.toml
[audio.models.voxtral-mini-latest]
api_endpoint = "/audio/transcriptions"  # Was: "/chat/completions"

[audio.models.voxtral-transcribe-2]
api_endpoint = "/audio/transcriptions"  # Was: "/v1/audio/transcriptions"
```
**Note**: Removed duplicate `/v1/` from endpoint path (base_url already includes `/v1`)

### 2. Request Format Correction
**Problem**: Tried two formats that failed:
- **JSON + raw binary concatenation** → 404 "no Route matched"
- **Single-request raw MP3** → 429 rate limit on files > ~200KB

**Fix**: Proper multipart/form-data format
```python
# src/chatybot/audio_providers/mistral_provider.py
form_data = aiohttp.FormData()
form_data.add_field('file', audio_bytes, filename=filename)
form_data.add_field('model', model_name)
# Optional params: language, diarize, timestamp_granularities[]
```
Matches Mistral's documented cURL pattern:
```bash
-F model="voxtral-mini-latest" -F file=@file.mp3
```

### 3. Sample Rate Alignment
**Problem**: MP3→WAV conversion upsampled 16kHz source to 44.1kHz, inflating file sizes unnecessarily

**Fix**: Convert at native 16kHz to preserve audio fidelity
```python
def _convert_mp3_to_wav(self, mp3_bytes: bytes, target_sample_rate: int = 16000) -> bytes:
    # Uses -ar 16000 instead of -ar 44100
```

### 4. Chunking Logic Simplification
**Problem**: Overly complex chunking with byte-level splitting, WAV header generation, and overlap

**Fix**: Removed chunking entirely (dedicated endpoint handles complete files)
- Single request per file
- No need for: `_transcribe_chunked()`, `_make_wav_header()`, chunk overlap logic
- Cleaner, more reliable code

---

## ❌ What Didn't Work (And Why)

### Attempt 1: JSON + Binary Concatenation
```python
json_header = b'{"model": "voxtral-mini-latest"}'
body = json_header + audio_bytes
headers = {"Content-Type": "application/json"}
```
**Result**: 404 - `{"message":"no Route matched with those values"}`
**Why**: Mistral's `/v1/audio/transcriptions` expects multipart, not this hybrid format

### Attempt 2: `/chat/completions` with base64
```python
request_body = {
    "model": "voxtral-mini-latest",
    "messages": [{"role": "user", "content": [{"type": "input_audio", "input_audio": base64}]}]
}
```
**Result**: Two issues:
1. **Hallucination**: Model continued generating conversational text after transcription
2. **Rate limit (429)**: Files > ~200KB base64 triggered threshold
**Why**: `/chat/completions` is a conversational endpoint, not pure STT. It applies LLM generation logic to audio input.

### Attempt 3: `/v1/audio/transcriptions` with double `/v1/` path
```toml
base_url = "https://api.mistral.ai/v1"
api_endpoint = "/v1/audio/transcriptions"
# Resulting URL: https://api.mistral.ai/v1/v1/audio/transcriptions
```
**Result**: 404 - `{"message":"no Route matched with those values"}`
**Why**: URL construction created invalid path with duplicate `/v1/`

### Attempt 4: WAV Conversion at 44.1kHz
```python
ffmpeg -i input.mp3 -ar 44100 -acodec pcm_s16le
```
**Result**: File size exploded (57KB MP3 → 312KB WAV)
**Why**: 16kHz → 44.1kHz upsampling multiplied raw size by ~5.5x, triggering rate limits

### Attempt 5: Base64 Chunking with 150KB Target
```python
MAX_BASE64_CHUNK = 150 * 1024
# Split at byte boundaries, add WAV headers, overlap 0.5s
```
**Result**: Trailing chunks produced hallucinations
**Why**: Partial audio frames at chunk boundaries created invalid audio that model misinterpreted

---

## 📊 Configuration Changes

### Modified Files
| File | Change |
|------|--------|
| `src/chatybot/chat_config.toml` | Updated `api_endpoint = "/audio/transcriptions"` for voxtral models |
| `src/chatybot/audio_providers/mistral_provider.py` | Simplified to multipart form, removed chunking, 16kHz conversion |
| `~/.config/chatybot/chat_config.toml` | Synced with source config |

### Removed Complexity
- ~150 lines of chunking logic (splitting, WAV headers, overlap)
- `MAX_BASE64_CHUNK` constant (no longer needed)
- `CHUNK_THRESHOLD` constant (no longer needed)
- `_transcribe_chunked()` method
- `_transcribe_chunk()` method  
- `_make_wav_header()` method

---

## ✅ Verification

Expected behavior after fix:
```bash
chat --> /model voxtral-transcribe-2
Model set to: voxtral-transcribe-2 (voxtral-mini-latest) [audio]

chat --> /transcribe test_audio/sample_01.mp3
Transcription: CONCORD RETURNED TO ITS PLACE AMIDST THE TENTS
Saved: /Users/jon2allen/chatybot_audio/2026-04-28/analyze/transcript_00x.json
Model: voxtral-mini-latest | Language: auto | Duration: X.Xs
```

- ✅ No rate limit errors (429)
- ✅ No routing errors (404)  
- ✅ No hallucinated conversational filler
- ✅ Clean, accurate transcription

---

## 🎯 Key Lessons

1. **Use dedicated endpoints**: `/v1/audio/transcriptions` for STT, not `/chat/completions`
2. **Follow API format exactly**: Mistral requires multipart/form-data, not JSON+binary
3. **Preserve audio characteristics**: Match source sample rate (16kHz for LibriSpeech)
4. **Simplify**: Dedicated endpoint handles complete files; no chunking needed
5. **Watch URL construction**: Avoid duplicate path segments

---

*Date: April 28, 2026*  
*Branch: audio*