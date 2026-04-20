# Image Support Status - April 20, 2026

## Summary
Full OpenRouter image generation and vision model support implemented with multimodal chat completion.

---

## Changes Made to Support OpenRouter

### 1. Core Architecture (`src/chatybot/image_generator.py`)
- **Added `_generate_openrouter()` method** - Handles image generation via OpenRouter's `/chat/completions` endpoint
- **Added `modalities` parameter** - Passed to OpenRouter requests to specify output type (`["image"]` for Flux.2, `["image", "text"]` for others)
- **Fixed image extraction** - Now checks both `message.content` (list/string format) AND `message.images` array (Flux.2 format)
  - `message.images` takes priority to handle Flux.2's dedicated image output
  - Falls back to `message.content` parsing for models that embed images in content
- **Fixed default endpoint** - Changed from `/api/v1/chat/completions` to `/chat/completions` to avoid double path components

### 2. Application Integration (`src/chatybot/chatybot_app.py`)
- **Added `/imagine` command** - Text-to-image generation with debug output support
- **Added `/trace imagedbg` command** - Toggle for debug logging of image generation
- **Fixed multimodal message formatting** - Unpacks `replace_placeholders()` tuple to handle image banks properly
  - Previously treated tuple return as string, causing malformed prompts
  - Now correctly builds OpenAI-compatible multimodal message format:
    ```python
    {"role": "user", "content": [
        {"type": "text", "text": "..."},
        {"type": "image_url", "image_url": {"url": "data:..."}}
    ]}
    ```
- **Added `/saveimage` command** - Saves images from both:
  - `/imagine` generated images (via `last_generated_image`)
  - Vision model chat responses (via parsing JSON `choices[0].message.images`)
- **Enhanced `/mem` command** - Shows `LAST_IMAGE` base64 memory usage in KB

### 3. Buffer Management (`src/chatybot/buffer_manager.py`)
- **Added `image_banks` storage** - 5 image banks (imagebank1-5) for storing base64 image data
- **Added `load_image_to_bank()`** - Reads image file, encodes to base64 data URL
- **Added `replace_placeholders()`** - Returns tuple of `(text_prompt, image_list)` for multimodal support
  - Removes image placeholders from text
  - Returns images as OpenAI-compatible format: `{"type": "image_url", "image_url": {"url": "data:..."}}`

### 4. Configuration (`src/chatybot/chat_config.toml` and `~/.config/chatybot/chat_config.toml`)
- **Added `[image_generation]` section** - Default settings for image directory, size, quality
- **Added Flux.2 model (`flux_1`)** - `black-forest-labs/flux.2-max` with `image_modalities = ["image"]`
- **Fixed OpenRouter models** - Changed endpoint from `/api/v1/chat/completions` to `/chat/completions`
- **Added `vendor` field** - Identifies model provider for routing
- **Restored `nvidia_1`** - Vision model `nvidia/nemotron-nano-12b-v2-vl:free` (VLM, not image generation)

---

## Configuration Gotchas

### 1. Endpoint Paths
**Problem:** URL concatenation caused double `/api/v1/` 
**Fix:** Use relative endpoints without version duplication

```toml
# WRONG - causes https://openrouter.ai/api/v1/api/v1/chat/completions
image_endpoint = "/api/v1/chat/completions"

# CORRECT - base_url has /api/v1, endpoint is relative
base_url = "https://openrouter.ai/api/v1"
image_endpoint = "/chat/completions"  # Final: /api/v1/chat/completions
```

### 2. Modalities Parameter
Different models require different modalities:

```toml
# Flux.2 - Image-only output
[models.flux_1]
name = "black-forest-labs/flux.2-max"
image_modalities = ["image"]

# Gemini 2.5 Flash Image - Text + Image output
[models.openrouter_image]
name = "google/gemini-2.5-flash-image"
image_modalities = ["image", "text"]
```

### 3. Vision Models vs Image Generation Models
- **Image Generation Models** (Flux.2, Stable Diffusion): Need `image_generation = true`
- **Vision Language Models** (nvidia/nemotron-nano-12b-v2-vl): VLM only, no `image_generation` flag
  - Can understand images in chat, cannot generate images
  - Use `/chat/completions` with proper multimodal format

### 4. Image Bank Placeholder Handling
Placeholders like `{imagebank1}` are removed from text and converted to image attachments. The prompt:
```
what type of boat is this in picture {imagebank1}
```
Becomes message:
```json
{"content": [
  {"type": "text", "text": "what type of boat is this in picture"},
  {"type": "image_url", "image_url": {"url": "data:image/png;base64,..."}}
]}
```

### 5. NVIDIA Model Configuration
The nvidia_1 model was changed from its original vision-only config. Restored version:
```toml
[models.nvidia_1]
name = "nvidia/nemotron-nano-12b-v2-vl:free"
temperature = 0.7
top_k = 1
base_url = "https://openrouter.ai/api/v1"
api_key = "OPENROUTER_API_KEY"
image_endpoint = "/chat/completions"
vendor = "openrouter"
```
Note: No `image_generation = true` since this is a VLM, not an image generator.

---

## Technical Implementation Details

### Image Generation Flow

```
User: /imagine "a bluejay bird"
    ↓
chatybot_app.py: parse command
    ↓
image_generator.generate_image()
    ↓
_generate_openrouter()
    - Builds request: {"model": "...", "messages": [...], "modalities": [...]}
    - Sends to: https://openrouter.ai/api/v1/chat/completions
    ↓
Response parsing:
    - Checks response.choices[0].message.images[] first (Flux.2 format)
    - Falls back to response.choices[0].message.content (Gemini format)
    - Extracts base64 from data URL
    ↓
_save_image()
    - Saves to: ~/chatybot_images/YYYY-MM-DD/prompt_XXX.png
    - Stores in: self.last_generated_image = (file_path, base64_data)
    ↓
Prints: "Image generated and saved to: /path/to/image.png"
```

### Vision Model Flow (Image Understanding)

```
User: /imagebank1 boat.png
    ↓
buffer_manager.load_image_to_bank()
    - Reads file, encodes to base64 data URL
    - Stores in: image_banks["imagebank1"] = "data:image/png;base64,..."

User: what type of boat is this in picture {imagebank1}
    ↓
chat_completion()
    ↓
replace_placeholders(prompt) → (text_prompt, image_list)
    - text_prompt: "what type of boat is this in picture" (placeholder removed)
    - image_list: [{"type": "image_url", "image_url": {"url": "data:..."}}]
    ↓
Build messages:
    {"role": "user", "content": [
        {"type": "text", "text": "what type of boat is this in picture"},
        {"type": "image_url", "image_url": {"url": "data:..."}}
    ]}
    ↓
Send to OpenRouter → Model analyzes image and responds
```

### Debug Output (`/trace imagedbg on`)
When enabled, `/imagine` creates `imagine_debug_YYYYMMDD_HHMMSS.txt` with:
- Model alias, vendor, name
- Size, quality, modalities
- File path and image data length
- Full API request/response (if errors occur)

Output is also printed to stdout with `[IMAGE_DEBUG]` prefix.

---

## Known Issues & Workarounds

1. **Rate Limits (429)** - OpenRouter has API limits. Wait or use different model.
2. **Model Availability** - Some models (Flux.2) may require Pro tier on OpenRouter.
3. **OPENROUTER_API_KEY** - Must be set in environment for OpenRouter models.
4. **Image Size** - Default 1024x1024 works with all major image models.

---

## Files Modified

- `src/chatybot/image_generator.py` - Core image generation logic
- `src/chatybot/chatybot_app.py` - Commands, multimodal message formatting
- `src/chatybot/buffer_manager.py` - Image bank management, placeholder replacement
- `src/chatybot/chat_config.toml` - Model configurations
- `~/.config/chatybot/chat_config.toml` - User-specific model configurations

---

## Testing Checklist

- [x] `/imagine` generates images with Flux.2
- [x] `/imagine` generates images with Gemini 2.5 Flash Image
- [x] `/trace imagedbg on` creates debug file
- [x] `/saveimage` saves /imagine output
- [x] `/saveimage` saves vision model responses
- [x] `/imagebank1 image.png` + VLM + `{imagebank1}` works
- [x] `/mem` shows LAST_IMAGE memory usage
- [x] NVIDIA VLM processes image placeholders correctly
