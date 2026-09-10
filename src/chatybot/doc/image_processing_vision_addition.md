# Vision/Image Interpretation Additions

## 🎯 NEW SECTION: Image Interpretation with Vision Models

### Overview

While the previous sections focused on **image generation** (text-to-image), this section covers **image interpretation** (image-to-text), which allows you to analyze, describe, and understand the content of images using AI vision models.

Both OpenAI and OpenRouter support vision capabilities through their chat completions APIs, enabling you to:
- Describe what's in an image
- Answer questions about an image
- Extract text from images (OCR)
- Analyze and classify image content

---

## 📖 Vision API Quick Reference

### Supported Operations

| Operation | OpenAI Models | OpenRouter Models | Example Use Case |
|-----------|---------------|-------------------|-----------------|
| Describe image | gpt-4o, gpt-4o-mini, gpt-4-vision | google/gemini-2.5-flash-image, openai/gpt-4o, anthropic/claude-3-* | "Describe this image" |
| Answer questions | Same as above | Same as above | "What color is the car?" |
| Extract text | Same as above | Same as above | OCR from receipts |
| Classify content | Same as above | Same as above | "Is this NSFW?" |
| Multi-image analysis | Same as above | Same as above | "Compare these two images" |

---

## 🔹 OpenAI Vision API (2025)

### Endpoint
```
POST https://api.openai.com/v1/chat/completions
```

### Image Input Format

Images can be provided in two ways:
1. **Public URL**: `{"type": "image_url", "image_url": {"url": "https://example.com/image.jpg"}}`
2. **Base64 Data URL**: `{"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,/9j/4AAQ..."}}`

### Basic Image Description Example

```python
import base64
from openai import OpenAI

# Initialize client
client = OpenAI()

# Encode image to base64
def encode_image(image_path):
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')

# Describe a JPEG image
image_path = "photo.jpg"
base64_image = encode_image(image_path)

response = client.chat.completions.create(
    model="gpt-4o",
    messages=[
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "Describe what is in this image"},
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{base64_image}"
                    }
                }
            ]
        }
    ],
    max_tokens=1000
)

print(response.choices[0].message.content)
```

### Supported Vision Models

| Model | Max Images | Max Tokens | Best For |
|-------|------------|------------|----------|
| gpt-4o | 10 | 128,000 | Highest quality, multimodal |
| gpt-4o-mini | 10 | 128,000 | Cost-effective, fast |
| gpt-4-vision-preview | 4 | 16,384 | Legacy vision model |

### JPEG vs PNG

Both JPEG and PNG are supported. Use the appropriate MIME type:
- JPEG: `data:image/jpeg;base64,...`
- PNG: `data:image/png;base64,...`

**Pro Tip:** JPEG is generally preferred for photographs, PNG for images with transparency or text.

### Handling Multiple Images

```python
# Compare two images
base64_image1 = encode_image("image1.jpg")
base64_image2 = encode_image("image2.jpg")

response = client.chat.completions.create(
    model="gpt-4o",
    messages=[
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "What are the differences between these two images?"},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image1}"}},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image2}"}}
            ]
        }
    ]
)
```

### cURL Example

```bash
#!/bin/bash
# Encode image (macOS)
IMAGE_B64=$(base64 image.jpg | tr -d '\n')

curl https://api.openai.com/v1/chat/completions \
  -H "Authorization: Bearer $OPENAI_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-4o",
    "messages": [{
      "role": "user",
      "content": [
        {"type": "text", "text": "Describe this image"},
        {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,'"$IMAGE_B64"'"}}
      ]
    }],
    "max_tokens": 1000
  }'
```

---

## 🔹 OpenRouter Vision API (2025)

### Endpoint
```
POST https://openrouter.ai/api/v1/chat/completions
```

### Key Differences from OpenAI

1. **Requires `modalities` parameter**: Must explicitly declare supported modalities
2. **Unified API**: Same endpoint for all vendors (OpenAI, Google, Anthropic, etc.)
3. **Model prefix**: Models are identified with vendor prefix (e.g., `openai/gpt-4o`, `google/gemini-2.5-flash-image`)

### Basic Image Description Example

```python
import aiohttp
import base64
import json

# Encode image
def encode_image(image_path):
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')

async def describe_image_openrouter(api_key, image_path, model="openai/gpt-4o"):
    base64_image = encode_image(image_path)
    
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Describe what is in this image"},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{base64_image}"
                        }
                    }
                ]
            }
        ],
        "modalities": ["image", "text"]  # CRITICAL for OpenRouter
    }
    
    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=payload, headers=headers) as response:
            if response.status != 200:
                error = await response.text()
                raise Exception(f"API Error: {response.status} - {error}")
            
            data = await response.json()
            return data["choices"][0]["message"]["content"]

# Usage
# description = await describe_image_openrouter("your_api_key", "photo.jpg")
```

### Supported Vision Models on OpenRouter

| Model ID | Provider | Type | Modalities |
|----------|----------|------|------------|
| openai/gpt-4o | OpenAI | Multi-modal | ["image", "text"] |
| openai/gpt-4o-mini | OpenAI | Multi-modal | ["image", "text"] |
| openai/gpt-4-vision-preview | OpenAI | Multi-modal | ["image", "text"] |
| google/gemini-2.5-flash-image | Google | Multi-modal | ["image", "text"] |
| google/gemini-1.5-flash | Google | Multi-modal | ["image", "text"] |
| google/gemini-1.5-pro | Google | Multi-modal | ["image", "text"] |
| anthropic/claude-3-5-sonnet-20250620 | Anthropic | Multi-modal | ["image", "text"] |
| anthropic/claude-3-haiku-20240307 | Anthropic | Multi-modal | ["image", "text"] |
| anthropic/claude-3-opus-20240229 | Anthropic | Multi-modal | ["image", "text"] |
| meta/llama-3.2-vision | Meta | Multi-modal | ["image", "text"] |
| mistral/mistral-large-2407 | Mistral | Multi-modal | ["image", "text"] |

### cURL Example

```bash
#!/bin/bash
# Detect OS
if [[ "$OSTYPE" == "darwin"* ]]; then
  # macOS
  IMAGE_B64=$(base64 image.jpg | tr -d '\n')
else
  # Linux
  IMAGE_B64=$(base64 -w 0 image.jpg)
fi

curl https://openrouter.ai/api/v1/chat/completions \
  -H "Authorization: Bearer $OPENROUTER_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "openai/gpt-4o",
    "messages": [{
      "role": "user",
      "content": [
        {"type": "text", "text": "Describe this image"},
        {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,'"$IMAGE_B64"'"}}
      ]
    }],
    "modalities": ["image", "text"]
  }'
```

---

## 🎯 Practical Vision Examples

### Example 1: Simple Image Description

**Prompt:** "Describe what is in this image"

**Python (OpenAI):**
```python
response = client.chat.completions.create(
    model="gpt-4o",
    messages=[{
        "role": "user",
        "content": [
            {"type": "text", "text": "Describe what is in this image"},
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}
        ]
    }]
)
```

**Python (OpenRouter):**
```python
payload = {
    "model": "openai/gpt-4o",
    "messages": [{
        "role": "user",
        "content": [
            {"type": "text", "text": "Describe what is in this image"},
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}
        ]
    }],
    "modalities": ["image", "text"]
}
```

### Example 2: Detailed Analysis

**Prompt:** "Analyze this image in detail. Identify all objects, their colors, positions, and any text present."

### Example 3: Question Answering

**Prompt:** "What is the main subject of this photograph?"

### Example 4: Text Extraction (OCR)

**Prompt:** "Extract all text from this image"

### Example 5: Multi-Image Comparison

**Prompt:** "What are the differences between these two images?"

---

## 🔧 Handling JPEG Images Specifically

### JPEG Best Practices

1. **Quality**: Use high-quality JPEGs (质量 90+) for best results
2. **Size**: Most vision models support up to 2048x2048 pixels
3. **Color Space**: RGB is recommended (not CMYK)
4. **Compression**: Avoid excessive compression as it degrades detail

### JPEG with OpenAI

```python
# JPEG-specific example with size info
def describe_jpeg_openai(client, image_path):
    base64_image = encode_image(image_path)
    
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Describe this JPEG image in detail"},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{base64_image}"
                        }
                    }
                ]
            }
        ],
        max_tokens=2000,
        temperature=0.7
    )
    return response.choices[0].message.content
```

### JPEG with OpenRouter

```python
# JPEG-specific example with OpenRouter
async def describe_jpeg_openrouter(api_key, image_path):
    base64_image = encode_image(image_path)
    
    payload = {
        "model": "google/gemini-2.5-flash-image",
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Analyze this JPEG photograph"},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{base64_image}"
                        }
                    }
                ]
            }
        ],
        "modalities": ["image", "text"]
    }
    
    # Send request and return response
    # ... (use aiohttp as shown in previous examples)
```

---

## ⚠️ Common Errors and Solutions

### Error 1: Base64 Decoding Failed

**Symptoms:**
```
"Base64 decoding failed for..."
```

**Causes:**
- Newlines in base64 string
- Invalid characters
- File path passed instead of content

**Solution:**
```bash
# macOS: Remove newlines
base64 image.jpg | tr -d '\n'

# Linux: Use -w 0
base64 -w 0 image.jpg
```

### Error 2: Invalid MIME Type

**Symptoms:**
```
"Unsupported image format"
```

**Causes:**
- Wrong MIME type specified (e.g., using png for jpeg)

**Solution:**
- JPEG: `data:image/jpeg;base64,...`
- PNG: `data:image/png;base64,...`

### Error 3: Image Too Large

**Symptoms:**
```
"Image size exceeds limit"
```

**Solution:**
- Resize to maximum 2048x2048 pixels
- Reduce file size under 20MB

### Error 4: Missing Modalities (OpenRouter)

**Symptoms:**
```
"modalities parameter required"
```

**Solution:**
Add `"modalities": ["image", "text"]` to your payload

### Error 5: Unsupported Model

**Symptoms:**
```
"Model not found"
```

**Solution:**
Check [OpenAI Models](https://platform.openai.com/docs/models) or [OpenRouter Models](https://openrouter.ai/models) for current model names

---

## 📊 Performance Comparison

### Accuracy (Image Description)

| Model | Detail | Context Understanding | Speed | Cost |
|-------|--------|---------------------|-------|------|
| gpt-4o | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | $$$$ |
| gpt-4o-mini | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | $$ |
| gemini-2.5-flash-image | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | $ |
| claud-3-5-sonnet | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | $$$ |

### Token Usage

**Important:** Vision models count both input tokens (text + image) and output tokens
- Images are converted to tokens based on resolution
- A 1024x1024 image ≈ 256 tokens
- Higher resolution = more tokens = higher cost

---

## 🎓 Best Practices

### 1. Preprocess Your Images
```python
from PIL import Image
import io

def preprocess_image(image_path, max_size=(1024, 1024)):
    """Resize and optimize image for vision APIs"""
    with Image.open(image_path) as img:
        # Convert to RGB if needed
        if img.mode != 'RGB':
            img = img.convert('RGB')
        
        # Resize if too large
        if img.size[0] > max_size[0] or img.size[1] > max_size[1]:
            img.thumbnail(max_size, Image.Resampling.LANCZOS)
        
        # Save to bytes
        buffer = io.BytesIO()
        img.save(buffer, format='JPEG', quality=90)
        return buffer.getvalue()
```

### 2. Use Context in Prompts

**Bad:**
```
"Describe this image"
```

**Better:**
```
"You are an art historian. Describe this JPEG photograph in detail, including subject matter, artistic style, color palette, and emotional tone."
```

### 3. Handle Errors Gracefully

```python
import time
from openai import RateLimitError

max_retries = 3
retry_delay = 2

for attempt in range(max_retries):
    try:
        response = client.chat.completions.create(...)
        break
    except RateLimitError:
        if attempt < max_retries - 1:
            time.sleep(retry_delay * (attempt + 1))
            continue
        else:
            raise
    except Exception as e:
        print(f"Error: {e}")
        break
```

### 4. Batch Processing

```python
import asyncio

async def batch_describe(images, model="gpt-4o"):
    """Describe multiple images concurrently"""
    tasks = []
    for img_path in images:
        task = asyncio.create_task(describe_single_image(img_path, model))
        tasks.append(task)
    return await asyncio.gather(*tasks)
```

---

## 🔗 Quick Reference: Common Vision Tasks

| Task | OpenAI Model | OpenRouter Model | Prompt Example |
|------|--------------|-------------------|----------------|
| General description | gpt-4o | openai/gpt-4o | "Describe this image" |
| Detailed analysis | gpt-4o | anthropic/claude-3-opus | "Analyze this image in detail" |
| OCR/Text extraction | gpt-4o | google/gemini-2.5-flash-image | "Extract all text from this image" |
| Object detection | gpt-4o | openai/gpt-4o-mini | "List all objects in this image" |
| Count items | gpt-4o | meta/llama-3.2-vision | "How many people are in this photo?" |
| Color analysis | gpt-4o | anthropic/claude-3-5-sonnet | "What are the predominant colors?" |
| Scene classification | gpt-4o | google/gemini-2.5-flash-image | "Where was this photo taken?" |
| Comparison | gpt-4o | openai/gpt-4o | "What are the differences between these images?" |

---

## 📚 Resources

- [OpenAI Vision Documentation](https://platform.openai.com/docs/guides/vision)
- [OpenRouter Vision Documentation](https://openrouter.ai/docs/guides/overview/multimodal/images)
- [OpenAI Models](https://platform.openai.com/docs/models)
- [OpenRouter Models](https://openrouter.ai/models)
- [Vision API Examples](https://github.com/openai/openai-cookbook/blob/main/examples/vision/readme.md)
