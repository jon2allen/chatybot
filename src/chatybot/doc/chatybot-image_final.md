# Plan: Adding Image Support to Chatybot

## Goal
Add image support to chatybot with two phases:
- **Phase 1 (Image-to-Text)**: `/imagebank1` through `/imagebank5` commands for loading images and using them in vision prompts
- **Phase 2 (Text-to-Image)**: `/imagine` command for generating images from text prompts with saving and indexing

---

## Analysis

### Current State
- **Filebank system**: 5 text-only banks (`filebank1-5`) managed in `buffer_manager.py`
- **File loading**: Uses simple `open(file_path, "r").read()` - text mode only
- **Placeholder substitution**: `{filebank1}` through `{filebank5}` replaced in prompts
- **Message format**: OpenAI-compatible `{"role": "user", "content": "text"}` JSON
- **Config**: 22 models across 8+ vendors (Mistral, Google, OpenAI, NVIDIA, OpenRouter, Bytez, PublicAI, Ollama)
- **Ollama**: Configured with `base_url: http://localhost:11434/v1`, api_key: "OLLAMA"
- **No existing image support** in codebase

### OpenAI-Compatible Image Format
```json
{
  "role": "user",
  "content": [
    {"type": "text", "text": "Describe this image"},
    {"type": "image_url", "image_url": {"url": "data:image/png;base64,<base64_data>"}}
  ]
}
```

---

## Vendor Support Analysis

### ✅ **Fully Support OpenAI Image Format**
1. **OpenAI** (`api.openai.com`) - Native support
2. **Mistral** (`mistral.ai`) - Supports OpenAI-compatible image URLs
3. **Google Gemini** (`generativelanguage.googleapis.com/v1beta/openai/`) - OpenAI-compatible endpoint
4. **OpenRouter** (`openrouter.ai`) - Supports vision models with OpenAI format
5. **PublicAI** (`api.publicai.co`) - OpenAI-compatible
6. **Bytez** (`api.bytez.com`) - OpenAI-compatible
7. **NVIDIA NIM** (`integrate.api.nvidia.com`) - Supports multimodal with OpenAI format

### ⚠️ **Requires Testing**
1. **Ollama** (`localhost:11434/v1`) - Ollama 0.17+ supports OpenAI-compatible `/chat/completions` with images
   - Requires vision-enabled model (e.g., `llava`, `bakllava`)
   - Format: `{"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,..."}}`
   - **Status**: Should work with OpenAI SDK

2. **llama.cpp** - Does NOT have built-in OpenAI-compatible server
   - Requires separate server implementation (e.g., llama.cpp with OpenAI API extension)
   - **Status**: Depends on server implementation - NOT natively supported
   - Common setup: `llama-server` with `--api` flag may support images
   - **Risk**: HIGH - may not support images without custom build

---

## Implementation Plan

### Phase 1: ImageBank Storage & Loading

#### Files to Modify

1. **`buffer_manager.py`**
   - Add `image_banks: Dict[str, str] = {f"imagebank{i}": "" for i in range(1, 6)}`
   - Add image format detection (PNG, JPG, JPEG)
   - Add base64 encoding method
   - Add `load_image_to_bank(bank_num, file_path)` with auto-detection and conversion

2. **`chatybot_app.py`**
   - Add `/imagebank1-5` command handling (mirroring `/filebank1-5`)
   - Add image display/show commands
   - Add image clear commands
   - Update placeholder substitution to handle `{imagebank1-5}`
   - Update help text

3. **`config_manager.py`** - No changes needed

4. **`chatdsl_parse.py`**
   - Add `imagebank`, `imagebank1-5` to `VALID_ESCAPE_COMMANDS`
   - May need to update tokenizer for image-specific syntax

5. **`/chat_config.toml`** - No changes needed

6. **`chatdsl_bnf.txt`** - Add imagebank references

---

### Phase 2: Message Format for LLM Communication

#### Key Challenge: OpenAI format requires `content` to be array for multimodal

Current format:
```python
messages = [{"role": "user", "content": "text string"}]
```

Required for images:
```python
messages = [{
    "role": "user", 
    "content": [
        {"type": "text", "text": "prompt text"},
        {"type": "image_url", "image_url": {"url": "data:image/png;base64,..."}}
    ]
}]
```

#### Solution Approach

**Option A: Mixed Content Type (Recommended)**
- Detect if prompt contains image placeholders
- If images present: Convert all content to array format with text and image elements
- If no images: Use simple string format (backward compatible)

**Option B: Always Use Array Format**
- Break backward compatibility
- Simpler but requires all vendors to support array format

**Option C: Separate Image-Only Mode**
- Add `/image` command that sends image separately
- Keeps text mode simple
- Less flexible

**Decision: Option A** - Best balance of compatibility and functionality

**Important Note on Message Construction:**
The current code prepends `prompt_buffer` and `file_buffer` to the prompt string before creating the message. With images, we need to handle this differently - these buffers should be part of the text element in the content array, not concatenated as strings.

**Revised approach for `chat_completion`:**
```python
# Get text prompt and image list from placeholder substitution
full_prompt, image_list = self.buffer_manager.replace_placeholders(prompt)

# Build the complete text content (including buffers)
text_content = full_prompt
if self.buffer_manager.prompt_buffer:
    text_content = self.buffer_manager.prompt_buffer + "\n\n" + text_content
if self.buffer_manager.file_buffer:
    text_content = f"File:\n{self.buffer_manager.file_buffer}\n\n{text_content}"

# Build messages
if image_list:
    # Array format for multimodal
    content_parts = [{"type": "text", "text": text_content}]
    content_parts.extend(image_list)
    messages = [{"role": "user", "content": content_parts}]
else:
    # String format for backward compatibility
    messages = [{"role": "user", "content": text_content}]
```

---

### Phase 3: Base64 Encoding & Format Detection

#### Implementation Details

```python
import base64
import magic  # python-magic library
from pathlib import Path

def detect_image_format(file_path: str) -> str:
    """Detect image MIME type using magic or file extension."""
    # Try magic library first
    try:
        import magic
        mime = magic.from_file(file_path, mime=True)
        if mime in ['image/jpeg', 'image/png']:
            return mime
    except:
        pass
    
    # Fallback to extension
    ext = Path(file_path).suffix.lower()
    if ext in ['.jpg', '.jpeg']:
        return 'image/jpeg'
    elif ext == '.png':
        return 'image/png'
    else:
        raise ValueError(f"Unsupported image format: {ext}")

def image_to_base64(file_path: str) -> str:
    """Load image and encode as base64 data URL."""
    mime_type = detect_image_format(file_path)
    with open(file_path, "rb") as f:
        data = f.read()
    return f"data:{mime_type};base64,{base64.b64encode(data).decode('utf-8')}"
```

**Dependencies to Add:**
- `python-magic` - For reliable MIME type detection (optional, can fallback to extension)
- `Pillow` - For potential format conversion (optional, for future-proofing)

**Current approach:** Use file extension only to avoid new dependencies

---

### Phase 4: Vendor Compatibility Handling

#### Detection Logic

```python
def supports_images(model_alias: str, model_config: dict) -> bool:
    """Check if the current model/vendor supports image input."""
    base_url = model_config.get("base_url", "").lower()
    model_name = model_config.get("name", "").lower()
    
    # Known non-supporting vendors
    non_supporting = []  # Populate based on testing
    
    # Known supporting vendors
    supporting = [
        "openai", "mistral", "google", "openrouter", 
        "publicai", "bytez", "nvidia", "ollama"
    ]
    
    for vendor in supporting:
        if vendor in base_url or vendor in model_name:
            return True
    
    # Check for localhost (Ollama, llama.cpp)
    if "localhost" in base_url or "127.0.0.1" in base_url:
        return True  # Assume it does, will fail gracefully
    
    return False
```

#### Fallback Strategy
- If vendor doesn't support images: Strip image content from messages, keep text only
- Or: Raise clear error message
- **Decision:** Warn user and strip images (graceful degradation)

---

## Phase 2: Text-to-Image Generation

### Overview
Text-to-image generation uses different API endpoints than chat completions. This phase adds support for generating images from text prompts and managing the resulting images.

### Text-to-Image Vendor Support

| Vendor | Endpoint | Models | Status |
|--------|----------|--------|--------|
| OpenAI | `/images/generations` | DALL-E 2, DALL-E 3 | ✅ Requires separate API key |
| Mistral | `/images/generations` | Flux-dev, Flux-schnell | ✅ OpenAI-compatible endpoint |
| Google | `/images:generate` | Imagen | ⚠️ Different endpoint format |
| Ollama | `/api/generate` | Stable Diffusion | ✅ Local, no API key |
| llama.cpp | Custom | Stable Diffusion | ⚠️ Depends on server implementation |
| OpenRouter | `/images/generations` | Various | ✅ Via OpenAI-compatible |
| Stability | `/v1/generation` | Stable Diffusion | ❌ Different API |

### New Configuration Section

Add to `chat_config.toml`:

```toml
# ============================================================================
# IMAGE GENERATION SETTINGS
# ============================================================================

[image_generation]
# Default directory for saving generated images
default_dir = "~/chatybot_images"

# Default image size - 1024x1024 is supported by ALL major image models
# DALL-E 2: 256x256, 512x512, 1024x1024
# DALL-E 3: 1024x1024, 1792x1024, 1024x1792
# Flux: 768x768, 1024x1024, 1344x768
# Stable Diffusion: 512x512, 768x768, 1024x1024
default_size = "1024x1024"

# Default quality
# DALL-E 3: "standard", "hd"
# Most other models ignore this or have their own defaults
default_quality = "standard"

# Default image vendor/model - Historical defaults 2024-2026:
# 2024: dall-e-3 (OpenAI) - Most widely available
# 2025: dall-e-3 (OpenAI) or flux-pro (Mistral)
# 2025: gemini-2.5-flash-image (Google)
# 2026: dall-e-4 (expected) or flux-pro
# Use model alias from [models] section below
# default_model = "dall-e-3"

# ============================================================================
# IMAGE GENERATION MODEL CONFIGURATIONS
# Add these to your existing [models] section
# ============================================================================

[models.dall_e_3]
name = "dall-e-3"
temperature = 0.7
base_url = "https://api.openai.com/v1"
api_key = "OPENAI_API_KEY"
# Flag: model supports image generation
image_generation = true
# Image generation endpoint (different from chat)
image_endpoint = "/images/generations"

[models.dall_e_2]
name = "dall-e-2"
temperature = 0.7
base_url = "https://api.openai.com/v1"
api_key = "OPENAI_API_KEY"
image_generation = true
image_endpoint = "/images/generations"

[models.flux_dev]
name = "flux-dev"
temperature = 0.7
base_url = "https://api.mistral.ai/v1"
api_key = "MISTRAL_API_KEY"
image_generation = true
image_endpoint = "/images/generations"

[models.flux_pro]
name = "flux-pro"
temperature = 0.7
base_url = "https://api.mistral.ai/v1"
api_key = "MISTRAL_API_KEY"
image_generation = true
image_endpoint = "/images/generations"

[models.stable_diffusion_xl]
name = "stable-diffusion-xl"
temperature = 0.7
base_url = "http://localhost:11434/api"
api_key = "OLLAMA"
image_generation = true
image_endpoint = "/generate"

# Google Imagen (uses different endpoint format)
[models.imagen_2]
name = "imagen-2"
temperature = 0.7
base_url = "https://generativelanguage.googleapis.com/v1"
api_key = "GEMINI_API_KEY"
image_generation = true
image_endpoint = "/images:generate"  # Google's custom endpoint
```

**Historical Context for Defaults (2024-2026):**

| Period | Recommended Default | Rationale |
|--------|-------------------|-----------|
| 2024 | `dall-e-3` + `1024x1024` + `standard` | Most capable OpenAI model, widely available |
| 2025 Early | `dall-e-3` | Still dominant, reliable |
| 2025 Late | `flux-pro` | Mistral's open-source alternative gaining traction |
| 2025-2026 | `dall-e-3` / `flux-pro` | Both solid choices, vendor-dependent |
| 2026+ | `dall-e-4` (expected) / `flux-pro` | Likely next-gen models |

### New Commands for Phase 2

**No `--option` flags** - Following chatybot's existing pattern (like `/temp`, `/maxtokens`):

| Command | Description | Example |
|---------|-------------|---------|
| `/model <alias>` | Switch to image-capable model | `/model dall-e-3` |
| `/imagesize <size>` | Set image resolution | `/imagesize 1024x1024` |
| `/imagequality <q>` | Set quality level | `/imagequality standard` |
| `/imagine <prompt>` | Generate image from text | `/imagine "sunset over mountains"` |
| `/saveimage [path]` | Save last generated image | `/saveimage mycat.png` |
| `/imagedir <path>` | Set default image directory | `/imagedir ~/my_images` |
| `/listimages` | List saved images | `/listimages` |
| `/showimage <name>` | Show image info | `/showimage 2025-01-15/prompt_001.png` |
| `/loadimage <path> <bank>` | Load image into bank | `/loadimage cat.png imagebank1` |

**Note:** `/model` already exists in chatybot. Users switch to an image-capable model, then use `/imagine`.

### File Structure

```
chatybot_images/
├── 2025-01-15/
│   ├── prompt_001.png          # Generated from: "sunset over mountains"
│   ├── prompt_002.png          # Generated from: "cyberpunk city"
│   ├── prompt_003.jpg          # Saved via /saveimage custom.jpg
│   └── index.json              # Metadata for this date's images
├── 2025-01-16/
│   ├── prompt_001.png
│   └── index.json
└── index.json                  # Master index (optional)
```

### Index File Format

`chatybot_images/2025-01-15/index.json`:
```json
{
  "date": "2025-01-15",
  "images": {
    "prompt_001.png": {
      "prompt": "sunset over mountains, digital art",
      "model": "dall-e-3",
      "size": "1024x1024",
      "timestamp": "2025-01-15T10:30:00Z",
      "quality": "standard",
      "seed": null,
      "vendor": "openai"
    },
    "prompt_002.png": {
      "prompt": "cyberpunk city at night, neon lights",
      "model": "flux-dev",
      "size": "1024x1024",
      "timestamp": "2025-01-15T11:45:00Z",
      "quality": "high",
      "seed": 123456789,
      "vendor": "mistral"
    },
    "custom.jpg": {
      "prompt": null,
      "model": null,
      "size": null,
      "timestamp": "2025-01-15T12:00:00Z",
      "quality": null,
      "seed": null,
      "vendor": null,
      "source": "external",
      "loaded_to_bank": "imagebank1"
    }
  },
  "counter": 2
}
```

### Auto-Naming Convention

```
{image_dir}/{date}/prompt_{counter}.{format}
```

- `image_dir`: From config or `/imagedir` command (default: `~/chatybot_images`)
- `date`: Current date in YYYY-MM-DD format
- `counter`: Sequential number per date (resets daily)
- `format`: Determined by model/vendor (PNG for most, JPEG optional)

### Implementation Requirements for Phase 2

#### New Dependencies
- `Pillow` - For image saving/loading (required for Phase 2)
- Optional: `requests` for non-OpenAI API vendors (already likely installed)

#### New Files

1. **`src/chatybot/image_generator.py`** - Core image generation logic

2. **`src/chatybot/image_manager.py`** - Image saving, loading, indexing

#### Modified Files (in addition to Phase 1)

1. **`chatybot_app.py`**
   - Add new commands: `/imagine`, `/saveimage`, `/imagedir`, `/listimages`, `/showimage`, `/loadimage`
   - Add image generation client setup
   - Update help text

2. **`config_manager.py`**
   - Add image generation configuration loading
   - Add `image_dir` setting
   - Add per-vendor image generation configs

3. **`buffer_manager.py`** (already modified for Phase 1)
   - No additional changes needed for Phase 2

#### New Class: ImageGenerator

```python
# src/chatybot/image_generator.py
from typing import Dict, Any, Optional, Tuple
import asyncio
import aiohttp
import base64
import json
import os
from pathlib import Path
from datetime import datetime


class ImageGenerator:
    """Handles text-to-image generation across vendors."""
    
    def __init__(self, config_manager):
        self.config_manager = config_manager
        self.image_dir = os.path.expanduser("~/chatybot_images")
        self.counters = {}  # Track counter per date
        self.session = None
    
    async def generate_image(
        self,
        prompt: str,
        model: Optional[str] = None,
        size: Optional[str] = None,
        quality: Optional[str] = None,
        vendor: Optional[str] = None
    ) -> Tuple[str, str]:
        """
        Generate an image from a text prompt.
        
        Returns:
            Tuple of (file_path, image_data_base64)
        """
        # Get vendor config
        if vendor is None:
            vendor = self.config_manager.get_default_image_vendor()
        
        model_config = self.config_manager.get_image_model_config(vendor, model)
        
        # Choose the right generation method
        if "openai" in vendor.lower() or vendor == "default":
            return await self._generate_openai(prompt, model_config, size, quality)
        elif "mistral" in vendor.lower():
            return await self._generate_mistral(prompt, model_config, size, quality)
        elif "ollama" in vendor.lower():
            return await self._generate_ollama(prompt, model_config, size, quality)
        else:
            raise ValueError(f"Unsupported image vendor: {vendor}")
    
    async def _generate_openai(
        self, prompt: str, config: Dict, size: Optional[str], quality: Optional[str]
    ) -> Tuple[str, str]:
        """Generate image using OpenAI DALL-E API."""
        import openai
        
        client = openai.OpenAI(
            api_key=os.environ.get(config["api_key_env"]),
            base_url=config.get("base_url")
        )
        
        response = client.images.generate(
            model=config["model"],
            prompt=prompt,
            size=size or config.get("default_size", "1024x1024"),
            quality=quality or config.get("default_quality", "standard"),
            n=1,
            response_format="b64_json"
        )
        
        image_data = response.data[0].b64_json
        file_path = self._save_image(image_data, prompt, "openai", config["model"])
        return file_path, image_data
    
    async def _generate_ollama(
        self, prompt: str, config: Dict, size: Optional[str], quality: Optional[str]
    ) -> Tuple[str, str]:
        """Generate image using Ollama."""
        async with aiohttp.ClientSession() as session:
            payload = {
                "model": config["model"],
                "prompt": prompt,
            }
            if size:
                # Parse size like "1024x1024" -> [1024, 1024]
                w, h = size.lower().split("x")
                payload["width"] = int(w)
                payload["height"] = int(h)
            
            async with session.post(
                f"{config['base_url']}/generate",
                json=payload
            ) as resp:
                if resp.status != 200:
                    raise ValueError(f"Ollama error: {await resp.text()}")
                
                data = await resp.json()
                # Ollama returns image as base64 in 'image' field
                image_data = data["image"]
                file_path = self._save_image(image_data, prompt, "ollama", config["model"])
                return file_path, image_data
    
    def _save_image(
        self, image_data: str, prompt: str, vendor: str, model: str
    ) -> str:
        """Save image to disk with auto-naming."""
        # Ensure image directory exists
        os.makedirs(self.image_dir, exist_ok=True)
        
        # Get date and counter
        date_str = datetime.now().strftime("%Y-%m-%d")
        date_dir = os.path.join(self.image_dir, date_str)
        os.makedirs(date_dir, exist_ok=True)
        
        # Get next counter for this date
        self.counters[date_str] = self.counters.get(date_str, 0) + 1
        counter = self.counters[date_str]
        
        # Generate filename
        filename = f"prompt_{counter:03d}.png"
        file_path = os.path.join(date_dir, filename)
        
        # Decode and save
        image_bytes = base64.b64decode(image_data)
        with open(file_path, "wb") as f:
            f.write(image_bytes)
        
        # Update index
        self._update_index(date_str, filename, prompt, vendor, model)
        
        return file_path
    
    def _update_index(
        self, date_str: str, filename: str, prompt: str, vendor: str, model: str
    ) -> None:
        """Update the index.json for a date."""
        index_path = os.path.join(self.image_dir, date_str, "index.json")
        
        data = {}
        if os.path.exists(index_path):
            with open(index_path, "r") as f:
                data = json.load(f)
        
        data["date"] = date_str
        if "images" not in data:
            data["images"] = {}
        if "counter" not in data:
            data["counter"] = 0
        
        data["counter"] = self.counters.get(date_str, 0)
        data["images"][filename] = {
            "prompt": prompt,
            "model": model,
            "vendor": vendor,
            "timestamp": datetime.now().isoformat() + "Z",
            "size": None,  # Can be updated
            "quality": None,
            "seed": None
        }
        
        with open(index_path, "w") as f:
            json.dump(data, f, indent=2)
    
    def list_images(self, date: Optional[str] = None) -> Dict[str, Any]:
        """List all images, optionally filtered by date."""
        results = {}
        
        image_dir = Path(self.image_dir)
        if not image_dir.exists():
            return results
        
        for date_dir in sorted(image_dir.iterdir(), reverse=True):
            if date and date_dir.name != date:
                continue
            if not date_dir.is_dir():
                continue
            
            index_path = date_dir / "index.json"
            if index_path.exists():
                with open(index_path, "r") as f:
                    data = json.load(f)
                    results[date_dir.name] = data.get("images", {})
        
        return results
    
    def get_image_info(self, date: str, filename: str) -> Optional[Dict]:
        """Get info about a specific image."""
        index_path = Path(self.image_dir) / date / "index.json"
        if not index_path.exists():
            return None
        
        with open(index_path, "r") as f:
            data = json.load(f)
        
        return data.get("images", {}).get(filename)
```

#### New Class: ImageManager

```python
# src/chatybot/image_manager.py
import os
import base64
from pathlib import Path
from typing import Optional, Tuple


class ImageManager:
    """Manages image loading, saving, and directory operations."""
    
    def __init__(self):
        self.image_dir = os.path.expanduser("~/chatybot_images")
    
    def set_directory(self, path: str) -> None:
        """Set the default image directory."""
        self.image_dir = os.path.expanduser(path)
        os.makedirs(self.image_dir, exist_ok=True)
        print(f"Image directory set to: {self.image_dir}")
    
    def load_image_data(self, file_path: str) -> Tuple[str, str]:
        """
        Load an image from disk and return (mime_type, base64_data).
        
        Used for loading saved images into imagebanks.
        """
        from(pathlib import Path
        
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Image not found: {file_path}")
        
        # Detect format from extension
        ext = path.suffix.lower()
        if ext in ['.jpg', '.jpeg']:
            mime_type = 'image/jpeg'
        elif ext == '.png':
            mime_type = 'image/png'
        elif ext == '.webp':
            mime_type = 'image/webp'
        else:
            raise ValueError(f"Unsupported image format: {ext}")
        
        with open(file_path, "rb") as f:
            data = f.read()
        
        base64_data = base64.b64encode(data).decode('utf-8')
        return mime_type, base64_data
    
    def get_image_directory(self) -> str:
        """Get the current image directory."""
        return self.image_dir
```

---

## Detailed Changes by File

### 1. `buffer_manager.py`

**Add:**
```python
import base64
from pathlib import Path

class BufferManager:
    def __init__(self):
        # ... existing ...
        self.image_banks: Dict[str, str] = {f"imagebank{i}": "" for i in range(1, 6)}
    
    def detect_image_format(self, file_path: str) -> str:
        """Detect image MIME type from file extension."""
        ext = Path(file_path).suffix.lower()
        if ext in ['.jpg', '.jpeg']:
            return 'image/jpeg'
        elif ext == '.png':
            return 'image/png'
        else:
            raise ValueError(f"Unsupported image format: {ext}. Use .jpg, .jpeg, or .png")
    
    def load_image_to_bank(self, bank_num: int, file_path: str) -> None:
        """Load an image file into a specific image bank as base64."""
        if bank_num < 1 or bank_num > 5:
            raise ValueError("Invalid imagebank number. Please use 1 through 5.")
        
        bank_name = f"imagebank{bank_num}"
        
        # Detect format
        mime_type = self.detect_image_format(file_path)
        
        # Load and encode
        try:
            with open(file_path, "rb") as f:
                image_data = f.read()
            
            base64_data = base64.b64encode(image_data).decode('utf-8')
            data_url = f"data:{mime_type};base64,{base64_data}"
            self.image_banks[bank_name] = data_url
            print(f"Image '{file_path}' loaded into {bank_name}.")
        except Exception as e:
            print(f"Error reading image file: {str(e)}")
            raise
    
    def clear_image_bank(self, bank_num: int) -> None:
        """Clear a specific image bank."""
        if bank_num < 1 or bank_num > 5:
            raise ValueError("Invalid imagebank number. Please use 1 through 5.")
        bank_name = f"imagebank{bank_num}"
        self.image_banks[bank_name] = ""
        print(f"{bank_name} cleared.")
    
    def show_image_bank(self, bank_num: int, show_all: bool = False) -> None:
        """Show info about image bank (not the actual image)."""
        if bank_num < 1 or bank_num > 5:
            raise ValueError("Invalid imagebank number. Please use 1 through 5.")
        bank_name = f"imagebank{bank_num}"
        content = self.image_banks[bank_name]
        if not content:
            print(f"{bank_name} is empty.")
            return
        
        # Extract MIME type
        if content.startswith("data:"):
            mime_end = content.find(";")
            mime_type = content[5:mime_end] if mime_end > 0 else "unknown"
            size = len(content.split(",")[1] if "," in content else content) // 4 * 3  # Approx size
            print(f"{bank_name}: {mime_type}, ~{size // 1024}KB")
        else:
            print(f"{bank_name}: Invalid data format")
    
    def replace_placeholders(self, prompt: str, include_images: bool = True) -> Tuple[str, List[Dict]]:
        """
        Replace placeholders and return (text_prompt, image_list).
        
        Modified to handle both text filebanks and image banks.
        Returns separated text and images for proper OpenAI format.
        
        Args:
            prompt: The prompt string containing placeholders
            include_images: If True, include image banks in search (for chat completion)
                          If False, images are ignored (for echo command)
        
        Returns:
            Tuple of (text_prompt, image_list)
        """
        # First, handle text placeholders as before
        text_prompt = prompt
        for bank_name, content in self.file_banks.items():
            placeholder = f"{{{bank_name}}}"
            if placeholder in text_prompt:
                text_prompt = text_prompt.replace(placeholder, content)
        
        for var_name, var_value in self.script_vars.items():
            placeholder = f"${{{var_name}}}"
            if placeholder in text_prompt:
                text_prompt = text_prompt.replace(placeholder, str(var_value))
        
        # Collect images only if requested
        image_list = []
        if include_images:
            for bank_name, content in self.image_banks.items():
                placeholder = f"{{{bank_name}}}"
                if placeholder in prompt:
                    if content:  # Has valid image data
                        if content.startswith("data:"):
                            image_list.append({
                                "type": "image_url",
                                "image_url": {"url": content}
                            })
        
        return text_prompt, image_list

    def replace_placeholders_legacy(self, prompt: str) -> str:
        """
        Legacy method for backward compatibility.
        Replaces placeholders and returns only text (ignoring images).
        Used by /echo command and other places that don't need image handling.
        """
        text_prompt, _ = self.replace_placeholders(prompt, include_images=False)
        return text_prompt
```

### 2. `chatybot_app.py`

**Changes:**

1. **Update line 436 (in chat_completion method):**
```python
# Change from:
full_prompt = self.buffer_manager.replace_placeholders(prompt)

# To:
full_prompt, image_list = self.buffer_manager.replace_placeholders(prompt)
```

2. **Update line 1888 (in /echo command handler):**
```python
# Change from:
processed_text = self.buffer_manager.replace_placeholders(text)

# To (use legacy method):
processed_text = self.buffer_manager.replace_placeholders_legacy(text)
```

**Phase 1 Command handling (around line 1515):**
```python
elif cmd.startswith("/imagebank"):
    # Handle imagebank commands
    bank_num = cmd[10:]  # Extract the number after /imagebank
    if not bank_num.isdigit() or int(bank_num) < 1 or int(bank_num) > 5:
        print("Invalid imagebank number. Please use /imagebank1 through /imagebank5.")
        return True
    
    bank_num_int = int(bank_num)
    
    if len(parts) < 2:
        print(f"Usage: {cmd} <file> or {cmd} clear or {cmd} show [all]")
        return True
    
    subcommand = parts[1].lower()
    
    if subcommand == "clear":
        self.buffer_manager.clear_image_bank(bank_num_int)
        return True
    elif subcommand == "show":
        show_all = len(parts) > 2 and parts[2].lower() == "all"
        self.buffer_manager.show_image_bank(bank_num_int, show_all)
        return True
    else:
        # Assume it's a file path
        file_path = command.split(maxsplit=1)[1].strip(" \"'")
        try:
            self.buffer_manager.load_image_to_bank(bank_num_int, file_path)
        except Exception as e:
            print(f"Error reading image file: {str(e)}")
        return True

**Command Implementation:**
```python
# In __init__ (add these attributes):
self.image_size = "1024x1024"      # Default from config or hardcoded
self.image_quality = "standard"     # Default from config or hardcoded
self.last_generated_image = None   # Store (file_path, base64_data)

# Separate commands (consistent with /temp, /maxtokens pattern):

elif cmd == "/imagesize":
    if len(parts) < 2:
        print(f"Current image size: {self.image_size}")
        return True
    self.image_size = parts[1]
    print(f"Image size set to: {self.image_size}")
    return True

elif cmd == "/imagequality":
    if len(parts) < 2:
        print(f"Current image quality: {self.image_quality}")
        return True
    self.image_quality = parts[1]
    print(f"Image quality set to: {self.image_quality}")
    return True

elif cmd == "/imagine":
    if len(parts) < 2:
        print("Usage: /imagine <prompt>")
        print(f"  Current settings: size={self.image_size}, quality={self.image_quality}")
        print(f"  Current model: {self.config_manager.active_model_alias}")
        return True
    
    prompt = command.split(maxsplit=1)[1].strip()
    
    # Get current model config
    model_alias = self.config_manager.active_model_alias
    model_config = self.config_manager.get_model_config(model_alias)
    
    # Check if model supports image generation
    if not model_config.get("image_generation", False):
        print(f"Error: Current model '{model_alias}' does not support image generation.")
        print(f"  Switch to an image-capable model first (e.g., /model dall-e-3)")
        return True
    
    try:
        # Load image generation config
        image_endpoint = model_config.get("image_endpoint", "/images/generations")
        
        file_path, image_data = await self.image_generator.generate_image(
            prompt,
            vendor=model_config.get("vendor", "openai"),
            model=model_config["name"],
            size=self.image_size,
            quality=self.image_quality,
            endpoint=image_endpoint
        )
        self.last_generated_image = (file_path, image_data)
        print(f"Image generated and saved to: {file_path}")
    except Exception as e:
        print(f"Error generating image: {str(e)}")
    return True

elif cmd.startswith("/saveimage"):
    if not hasattr(self, 'last_generated_image') or self.last_generated_image is None:
        print("No generated image to save. Use /imagine first.")
        return True
    
    file_path, image_data = self.last_generated_image
    
    if len(parts) < 2:
        # Auto-save with default naming
        print(f"Image already saved to: {file_path}")
    else:
        # Save to custom path
        custom_path = command.split(maxsplit=1)[1].strip(" \"'")
        try:
            import base64
            image_bytes = base64.b64decode(image_data)
            with open(custom_path, "wb") as f:
                f.write(image_bytes)
            print(f"Image saved to: {custom_path}")
            # Update index to reflect new location
            # (Implementation depends on index manager)
        except Exception as e:
            print(f"Error saving image: {str(e)}")
    return True

elif cmd.startswith("/imagedir"):
    if len(parts) < 2:
        print(f"Current image directory: {self.image_generator.image_dir}")
    else:
        new_dir = command.split(maxsplit=1)[1].strip(" \"'")
        self.image_generator.set_directory(new_dir)
        self.image_manager.set_directory(new_dir)
    return True

elif cmd == "/listimages":
    images = self.image_generator.list_images()
    if not images:
        print("No images found.")
        return True
    
    for date, date_images in images.items():
        print(f"\n{date}:")
        for filename, info in date_images.items():
            prompt = info.get("prompt", "(external)")
            if len(prompt) > 60:
                prompt = prompt[:57] + "..."
            model = info.get("model", "unknown")
            vendor = info.get("vendor", "unknown")
            timestamp = info.get("timestamp", "")
            print(f"  {filename:25} | {vendor:10} | {model:15} | {prompt}")
    return True

elif cmd.startswith("/showimage"):
    if len(parts) < 2:
        print("Usage: /showimage <date>/<filename> or /showimage <filename>")
        return True
    
    image_path = command.split(maxsplit=1)[1].strip(" \"'")
    
    # Parse date/filename
    if "/" in image_path:
        date, filename = image_path.split("/", 1)
    else:
        # Search for image across all dates
        all_images = self.image_generator.list_images()
        found = None
        for date, date_images in all_images.items():
            if image_path in date_images:
                found = (date, image_path)
                break
        if not found:
            print(f"Image not found: {image_path}")
            return True
        date, filename = found
    
    info = self.image_generator.get_image_info(date, filename)
    if not info:
        print(f"Image not found: {image_path}")
        return True
    
    print(f"\nImage: {filename}")
    print(f"  Date: {date}")
    print(f"  Prompt: {info.get('prompt', 'N/A')}")
    print(f"  Vendor: {info.get('vendor', 'N/A')}")
    print(f"  Model: {info.get('model', 'N/A')}")
    print(f"  Timestamp: {info.get('timestamp', 'N/A')}")
    print(f"  Size: {info.get('size', 'N/A')}")
    print(f"  Quality: {info.get('quality', 'N/A')}")
    if info.get("seed"):
        print(f"  Seed: {info.get('seed')}")
    
    file_path = os.path.join(self.image_generator.image_dir, date, filename)
    if os.path.exists(file_path):
        import os
        size_kb = os.path.getsize(file_path) / 1024
        print(f"  File size: {size_kb:.2f} KB")
    return True

elif cmd.startswith("/loadimage"):
    if len(parts) < 3:
        print("Usage: /loadimage <path> <imagebank1-5>")
        return True
    
    file_path = parts[1]
    bank_name = parts[2]
    
    # Extract bank number
    if bank_name.startswith("imagebank") and bank_name[9:].isdigit():
        bank_num = int(bank_name[9:])
    else:
        print("Invalid imagebank. Use imagebank1 through imagebank5.")
        return True
    
    try:
        # Load the image and get its data URL
        mime_type, base64_data = self.image_manager.load_image_data(file_path)
        data_url = f"data:{mime_type};base64,{base64_data}"
        self.buffer_manager.image_banks[f"imagebank{bank_num}"] = data_url
        print(f"Image '{file_path}' loaded into {bank_name}.")
    except Exception as e:
        print(f"Error loading image: {str(e)}")
    return True
```

2. **Update matcher initialization (around line 113):**
```python
words=[
    "help", "prompt", "file", "showfile", "clearfile",
    "filebank", "filebank1", "filebank2", "filebank3", "filebank4",
    "filebank5", "imagebank", "imagebank1", "imagebank2", "imagebank3", 
    "imagebank4", "imagebank5",
    # Phase 2 commands
    "imagine", "imagesize", "imagequality", "saveimage", "imagedir", 
    "listimages", "showimage", "loadimage",
    "model", "listmodels", "logging", "save",
    # ... rest ...
]
```

3. **Update help text (around line 2046):**
```python
print("  /imagebank{1..5} <file> - Load an image file into imagebank1 through imagebank5.")
print("  /imagebank{1..5} clear - Clear the specified imagebank.")
print("  /imagebank{1..5} show [all] - Show info about the imagebank.")

# Phase 2 help text
print("  /imagine <prompt> - Generate image from text")
print("  /imagesize <size> - Set image resolution (default: 1024x1024)")
print("  /imagequality <q> - Set quality (default: standard)")
print("  /saveimage [path] - Save last generated image (auto-saves by default)")
print("  /imagedir [path] - Set/Get default image directory")
print("  /listimages - List all saved images with metadata")
print("  /showimage <path> - Show info about a specific image")
print("  /loadimage <path> <bank> - Load image into imagebank")
```

4. **Update `chat_completion` method (around line 436):**
```python
# OLD CODE:
# full_prompt = self.buffer_manager.replace_placeholders(prompt)

# NEW CODE:
# Replace placeholders in the prompt - returns (text, image_list)
full_prompt, image_list = self.buffer_manager.replace_placeholders(prompt)

# Prepare the prompt with file buffer and prompt buffer if available
if self.buffer_manager.prompt_buffer:
    full_prompt = self.buffer_manager.prompt_buffer + "\n\n" + full_prompt
if self.buffer_manager.file_buffer:
    full_prompt = f"File:\n{self.buffer_manager.file_buffer}\n\n{full_prompt}"

# Add code-only instruction if flag is set
if self.code_only_flag:
    full_prompt = (
        "Do not explain or describe the code - generate the code requested only. "
        + full_prompt
    )

# Prepare messages for chat completion
# Check if we have images to include
if image_list:
    # Use array format for content (OpenAI-compatible multimodal format)
    content_parts = [{"type": "text", "text": full_prompt}]
    content_parts.extend(image_list)
    messages = [{"role": "user", "content": content_parts}]
else:
    # Use simple string format (backward compatible with all vendors)
    messages = [{"role": "user", "content": full_prompt}]
```

### 3. `chatdsl_parse.py`

**Update VALID_ESCAPE_COMMANDS (around line 168):**
```python
VALID_ESCAPE_COMMANDS: Set[str] = {
    "help", "prompt", "file", "showfile", "clearfile", "filebank",
    "model", "listmodels", "logging", "save", "codeonly", "codeoff",
    "system", "temp", "maxtokens", "top_p", "top_k", "freq_penalty",
    "pres_penalty", "reasoning", "seed", "stream", "script", "quit",
    "setdb", "dblist", "searchdb", "dblog", "dbprint", "loadvar",
    "savevar", "setvar", "notemode", "mem", "dump", "trace", "thinking",
    "filebank1", "filebank2", "filebank3", "filebank4", "filebank5",
    "imagebank", "imagebank1", "imagebank2", "imagebank3", "imagebank4", "imagebank5",
    # Phase 2 commands
    "imagine", "imagesize", "imagequality", "saveimage", "imagedir", 
    "listimages", "showimage", "loadimage",
    "multiline", "echo", "thoughtstyle", "def"
}
```

### 4. `chatdsl_bnf.txt`

**Update grammar rules:**
```bnf
<variable-reference> ::= "{" "filebank" <digit_1_5> "}"
                      | "{" "imagebank" <digit_1_5> "}"
                      | "$" "{" <identifier> "}"
```

### 5. New Files for Phase 2

**`src/chatybot/image_generator.py`**
- See implementation details above
- Core image generation logic
- Vendor-specific generation methods
- Image saving and indexing

**`src/chatybot/image_manager.py`**
- Image loading/saving utilities
- Directory management
- Base64 encoding/decoding for images

---

## Testing Plan

### Unit Tests Needed
1. **Image loading**: Test JPG, PNG detection and base64 encoding
2. **Placeholder substitution**: Test mixed text+image prompts
3. **Message format**: Verify OpenAI-compatible array format
4. **Command handling**: Test all `/imagebankN` commands
5. **Backward compatibility**: Ensure existing filebank still works

### Vendor Testing
1. **Ollama**: Test with vision model (llava, bakllava)
2. **Mistral**: Test with mistral-large (vision capable)
3. **Google**: Test with gemini-2.5-flash (vision capable)
4. **OpenAI**: Test with gpt-4o (vision capable)
5. **llama.cpp**: Test if compatible server available

### Test Script
```python
# test_image Support.py
import base64
from buffer_manager import BufferManager

bm = BufferManager()

# Test loading
bm.load_image_to_bank(1, "test.png")
assert "imagebank1" in bm.image_banks
assert bm.image_banks["imagebank1"].startswith("data:image/png;base64,")

# Test placeholder substitution
text, images = bm.replace_placeholders("Describe {imagebank1}")
assert len(images) == 1
assert images[0]["type"] == "image_url"

# Test clearing
bm.clear_image_bank(1)
assert bm.image_banks["imagebank1"] == ""
```

---

## Risks & Mitigations

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Vendor doesn't support images | Medium | High | Graceful degradation - strip images, warn user |
| Image too large for model | Medium | Medium | Add size validation, warn user |
| Base64 encoding memory issues | Low | Medium | Add size limits (e.g., 10MB max) |
| Breaking backward compatibility | Low | High | Use Option A (mixed format), thorough testing |
| llama.cpp compatibility | High | High | Document limitation, test with common setups |
| New dependencies (python-magic) | Low | Low | Use file extension fallback, make optional |

---

## Dependencies

### Required (already available)
- `base64` - Standard library ✓
- `pathlib` - Standard library ✓

### Optional (for enhanced features)
- `python-magic` - Better MIME type detection (fallback: file extension)
- `Pillow` - Future: Format conversion, resizing

**Decision:** No new required dependencies. Use file extension for format detection.

---

## Compatibility Summary

| Vendor | OpenAI-Compatible | Vision Support | Image Support Status |
|--------|-------------------|----------------|---------------------|
| OpenAI | ✅ Yes | ✅ Yes | ✅ Works |
| Mistral | ✅ Yes | ✅ Yes | ✅ Works |
| Google Gemini | ✅ Yes | ✅ Yes | ✅ Works |
| OpenRouter | ✅ Yes | ✅ Some models | ✅ Works (with vision models) |
| PublicAI | ✅ Yes | ✅ Some models | ✅ Works (with vision models) |
| Bytez | ✅ Yes | ✅ Some models | ✅ Works (with vision models) |
| NVIDIA NIM | ✅ Yes | ✅ Yes | ✅ Works |
| Ollama | ✅ Yes | ✅ Some models | ⚠️ Works (needs vision model) |
| llama.cpp | ⚠️ Depends | ⚠️ Depends | ❌ Uncertain (needs testing) |

---

## Recommendations

1. **Implement Option A** (mixed content type) for maximum compatibility
2. **No new required dependencies** - use file extension for MIME type
3. **Add size validation** - limit images to 10MB, warn on larger files
4. **Graceful degradation** - if vendor doesn't support images, strip them and warn
5. **Test with Ollama** - has vision models available (llava, bakllava), good test case
6. **Document llama.cpp limitation** - may not work without custom server implementation
7. **Add to config_manager** - optional `max_image_size` setting
8. **Add image format size display** - useful for users to know how large their image data is

## Vendor Compatibility Testing Matrix

| Vendor | Model to Test | Vision Model Available? | Expected Result |
|--------|---------------|------------------------|-----------------|
| OpenAI | gpt-4o | ✅ Yes | ✅ Should work |
| Mistral | mistral-large-2512 | ✅ Yes | ✅ Should work |
| Google | gemini-2.5-flash | ✅ Yes | ✅ Should work |
| OpenRouter | meta-llama/llama-3.3-70b-instruct | ⚠️ Check vision | ⚠️ Depends on model |
| PublicAI | utter-project/EuroLLM-22B | ❌ Likely not | ❌ May fail gracefully |
| Bytez | Qwen/Qwen2.5-3B | ⚠️ Check vision | ⚠️ Depends on model |
| NVIDIA | nvidia/nemotron-nano-12b-v2-vl | ✅ Yes | ✅ Should work |
| Ollama | llava | ✅ Yes | ✅ Should work with llava model |
| llama.cpp | Custom vision model | ⚠️ Unlikely | ❌ Probably fails |

---

## Phase Summary

### Phase 1: Image-to-Text (Vision)
**Status:** Primary focus, ready for implementation

- Load images into memory banks
- Use images in chat prompts
- Vision models analyze and describe images
- No image saving required
- ~295 lines of code
- **No new dependencies**

### Phase 2: Text-to-Image (Generation)
**Status:** Optional enhancement, requires additional dependencies

- Generate images from text prompts
- Save generated images with auto-naming
- Index images with prompts for review
- Support multiple vendors (OpenAI, Mistral, Ollama)
- Requires: `Pillow`, `aiohttp`
- ~400 lines of code (new files + modifications)

---

## Files to Create/Modify Summary

### Phase 1 Files
| File | Action | Type | Lines |
|------|--------|------|-------|
| `buffer_manager.py` | Modify | Core - image bank storage | ~80 |
| `chatybot_app.py` | Modify | Command handling | ~50 |
| `chatdsl_parse.py` | Modify | Parser | ~10 |
| `chatdsl_bnf.txt` | Modify | Grammar | ~5 |

### Phase 2 Files
| File | Action | Type | Lines |
|------|--------|------|-------|
| `image_generator.py` | Create | Image generation logic | ~200 |
| `image_manager.py` | Create | Image save/load/index | ~100 |
| `chatybot_app.py` | Modify | Add generation commands | ~80 |
| `config_manager.py` | Modify | Image config loading | ~40 |
| `chat_config.toml` | Modify | Add image generation section | ~20 |

### Shared Files
| File | Action | Type | Lines |
|------|--------|------|-------|
| `test_image_support.py` | Create | Tests | ~150 |
| `README.md` | Modify | Documentation | ~100 |

**Phase 1 Total:** ~295 lines
**Phase 2 Total:** ~440 lines  
**Combined Total:** ~735 lines

---

## Estimated Effort

### Phase 1
| Task | Complexity | Lines | Testing |
|------|------------|-------|---------|
| buffer_manager.py | Medium | ~80 | Unit tests |
| chatybot_app.py | Medium | ~50 | Integration |
| chatdsl_parse.py | Low | ~10 | Parser tests |
| chatdsl_bnf.txt | Low | ~5 | Grammar tests |
| Documentation | Low | ~50 | Manual |
| Test creation | Medium | ~100 | New tests |
| **Phase 1 Total** | | **~295** | |

### Phase 2
| Task | Complexity | Lines | Testing |
|------|------------|-------|---------|
| image_generator.py | High | ~200 | Integration |
| image_manager.py | Medium | ~100 | Unit tests |
| chatybot_app.py additions | Medium | ~80 | Integration |
| config_manager.py | Medium | ~40 | Unit tests |
| chat_config.toml | Low | ~20 | Manual |
| Tests | Medium | ~100 | New tests |
| **Phase 2 Total** | | **~440** | |

### Combined
| Phase | Complexity | Lines | Dependencies |
|-------|------------|-------|--------------|
| Phase 1 (Vision) | Medium | ~295 | None (stdlib only) |
| Phase 2 (Generation) | High | ~440 | Pillow, aiohttp |
| **Both** | | **~735** | **Pillow, aiohttp** |

---

## Final Recommendations

### Implementation Order

**Priority 1 - Phase 1 (Vision):**
1. `buffer_manager.py` - Add image banks
2. `chatybot_app.py` - Add `/imagebank1-5` commands and message format handling
3. `chatdsl_parse.py` - Add command recognition
4. `chatdsl_bnf.txt` - Update grammar
5. Testing and validation

**Priority 2 - Phase 2 (Generation) - Optional:**
1. `image_generator.py` - Core generation logic
2. `image_manager.py` - Save/load/index utilities
3. `config_manager.py` - Image config support
4. `chat_config.toml` - Generation settings
5. `chatybot_app.py` - Add `/imagine`, `/saveimage`, `/imagedir`, `/listimages`, `/showimage`, `/loadimage`
6. Testing with multiple vendors

### Suggested First Implementation
Start with **Phase 1 only** because:
- No new dependencies required
- Simpler scope (~295 lines)
- Provides immediate value (vision support)
- Tests image-to-text workflow
- Phase 2 can be added later without breaking changes

### Directory Structure for Development
```
chatybot/
├── src/chatybot/
│   ├── buffer_manager.py      # Phase 1: Add image_banks
│   ├── chatybot_app.py        # Phase 1 & 2: Add commands
│   ├── config_manager.py      # Phase 2: Add image config
│   ├── chatdsl_parse.py       # Phase 1: Add commands to VALID_ESCAPE_COMMANDS
│   ├── chatdsl_bnf.txt        # Phase 1: Update grammar
│   ├── image_generator.py     # Phase 2: NEW - generation logic
│   └── image_manager.py       # Phase 2: NEW - save/load/index
├── chat_config.toml          # Phase 2: Add [image_generation] section
└── tests/
    └── test_image_support.py  # NEW - tests for both phases
```

---

## Usage Flow Examples

### Phase 1: Image-to-Text
```
/user loads an image
  → /imagebank1 vacation.jpg
  → Image loaded into imagebank1 as base64 data URL

/user references in prompt
  → "Describe {imagebank1}"
  → Message sent with OpenAI multimodal format
  → Vision model returns text description
```

### Phase 2: Text-to-Image + Review Workflow
```
# User sets up defaults (optional - code has hardcoded defaults)
  → /model dall-e-3
  → /imagesize 1024x1024
  → /imagequality standard

/user generates image
  → /imagine "sunset over mountains, digital art"
  → Image generated via DALL-E API
  → Auto-saved to ~/chatybot_images/2025-01-15/prompt_001.png
  → Index updated with prompt and metadata

/user reviews images
  → /listimages
  → Shows all images with prompts
  → /showimage 2025-01-15/prompt_001.png
  → Displays full metadata

/user loads for further iteration
  → /loadimage 2025-01-15/prompt_001.png imagebank1
  → Image loaded into imagebank1
  → /imagine "same scene but with a river in foreground, reference {imagebank1}"
  → New image generated with reference
```

---

**Plan complete. Ready for implementation approval.**