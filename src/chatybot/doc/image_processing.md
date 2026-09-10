# Image Processing with AI: A Practical Guide to OpenAI and OpenRouter APIs

*Understanding the architecture behind Chatybot's image generation and vision capabilities*

---

## Table of Contents

1. [Introduction to AI Image Processing](#introduction-to-ai-image-processing)
2. [The Two Main Approaches](#the-two-main-approaches)
3. [Vision/Image Interpretation with Vision Models](#visionimage-interpretation-with-vision-models)
4. [OpenAI Image Generation Deep Dive](#openai-image-generation-deep-dive)
5. [OpenRouter: The Multi-Model Gateway](#openrouter-the-multi-model-gateway)
6. [Building Your Own Image Generator](#building-your-own-image-generator)
7. [Advanced Topics](#advanced-topics)
8. [Best Practices and Tips](#best-practices-and-tips)
9. [Conclusion](#conclusion)

---

## Introduction to AI Image Processing

In 2024-2025, AI image processing has evolved into a dual capability: **generation** (text-to-image) and **interpretation** (image-to-text). Whether you're building a creative tool, a chat application, or just experimenting, understanding both directions is essential.

**Why This Matters:**
- **Image Generation:** Create visual content from text descriptions
- **Image Interpretation:** Understand, describe, and extract information from images
- **Multi-modal AI:** Combine text and images for richer interactions
- Multiple vendors offer different capabilities and pricing
- Integration is simpler than you might think

The Chatybot project implemented comprehensive image processing supporting multiple vendors, with special attention to both OpenAI's API and OpenRouter's unique approach for both generation and vision tasks.

---

## The Two Main Approaches

### Approach 1: Traditional Image Generation (OpenAI Style)

Most image models follow OpenAI's pattern:
```
POST /images/generations
{
  "model": "dall-e-3",
  "prompt": "A sunset over mountains",
  "size": "1024x1024",
  "quality": "standard",
  "n": 1
}
```

**Characteristics:**
- Dedicated endpoint for image generation
- Returns base64-encoded image or URL
- Simple, direct approach
- Used by: OpenAI, Mistral, Google (OpenAI-compatible)

### Approach 2: Chat-Based Image Generation & Interpretation

Both OpenAI and OpenRouter use the chat completions endpoint for vision tasks:
```
POST /chat/completions
{
  "model": "gpt-4o",
  "messages": [{
    "role": "user",
    "content": [
      {"type": "text", "text": "Describe this image"},
      {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,..."}}
    ]
  }],
  "modalities": ["image", "text"]  // Required for OpenRouter
}
```

**Characteristics:**
- Uses standard chat API
- Supports both generation AND interpretation
- Requires `modalities` parameter for OpenRouter
- More flexible for multi-modal interactions

---

## Vision/Image Interpretation with Vision Models

### Overview

While the previous sections focused on **image generation** (text-to-image), this section covers **image interpretation** (image-to-text), which allows you to analyze, describe, and understand the content of images using AI vision models.

Both OpenAI and OpenRouter support vision capabilities through their chat completions APIs, enabling you to:
- Describe what's in an image
- Answer questions about an image
- Extract text from images (OCR)
- Analyze and classify image content
- Compare multiple images

### Supported Operations

| Operation | OpenAI Models | OpenRouter Models | Example Use Case |
|-----------|---------------|-------------------|-----------------|
| Describe image | gpt-4o, gpt-4o-mini, gpt-4-vision | google/gemini-2.5-flash-image, openai/gpt-4o, anthropic/claude-3-* | "Describe this image" |
| Answer questions | Same as above | Same as above | "What color is the car?" |
| Extract text | Same as above | Same as above | OCR from receipts |
| Classify content | Same as above | Same as above | "Is this NSFW?" |
| Multi-image analysis | Same as above | Same as above | "Compare these two images" |

---

### 🔹 OpenAI Vision API (2025)

#### Endpoint
```
POST https://api.openai.com/v1/chat/completions
```

#### Image Input Format

Images can be provided in two ways:
1. **Public URL**: `{"type": "image_url", "image_url": {"url": "https://example.com/image.jpg"}}`
2. **Base64 Data URL**: `{"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,/9j/4AAQ..."}}`

#### Basic Image Description Example

```python
import base64
from openai import OpenAI

# Initialize client
client = OpenAI()

# Encode image to base64
def encode_image(image_path):
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')

# Describe a JPEG image - YOUR EXACT USE CASE
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

#### Supported Vision Models

| Model | Max Images | Max Tokens | Best For |
|-------|------------|------------|----------|
| gpt-4o | 10 | 128,000 | Highest quality, multimodal |
| gpt-4o-mini | 10 | 128,000 | Cost-effective, fast |
| gpt-4-vision-preview | 4 | 16,384 | Legacy vision model |

#### JPEG vs PNG

Both JPEG and PNG are supported. Use the appropriate MIME type:
- JPEG: `data:image/jpeg;base64,...`
- PNG: `data:image/png;base64,...`

**Pro Tip:** JPEG is generally preferred for photographs due to smaller file size. PNG is better for images with transparency or text.

#### Handling Multiple Images

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

#### cURL Example

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

### 🔹 OpenRouter Vision API (2025)

#### Endpoint
```
POST https://openrouter.ai/api/v1/chat/completions
```

#### Key Differences from OpenAI

1. **Requires `modalities` parameter**: Must explicitly declare supported modalities
2. **Unified API**: Same endpoint for all vendors (OpenAI, Google, Anthropic, etc.)
3. **Model prefix**: Models are identified with vendor prefix (e.g., `openai/gpt-4o`, `google/gemini-2.5-flash-image`)

#### Basic Image Description Example

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

#### Supported Vision Models on OpenRouter

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

#### cURL Example

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

### 🎯 cURL Examples for Vision Models

Here are ready-to-use cURL commands for each major vision-capable model. All examples use your exact use case - describing a JPEG image.

#### **OpenAI - GPT-4o**
```bash
#!/bin/bash
# macOS
IMAGE_B64=$(base64 image.jpg | tr -d '\n')

curl https://api.openai.com/v1/chat/completions \
  -H "Authorization: Bearer $OPENAI_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-4o",
    "messages": [{
      "role": "user",
      "content": [
        {"type": "text", "text": "Describe what is in this image"},
        {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,'"$IMAGE_B64"'"}}
      ]
    }],
    "max_tokens": 1000
  }'
```

#### **OpenAI - GPT-4o-mini** (Faster, Cheaper)
```bash
#!/bin/bash
IMAGE_B64=$(base64 image.jpg | tr -d '\n')

curl https://api.openai.com/v1/chat/completions \
  -H "Authorization: Bearer $OPENAI_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-4o-mini",
    "messages": [{
      "role": "user",
      "content": [
        {"type": "text", "text": "Describe what is in this image"},
        {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,'"$IMAGE_B64"'"}}
      ]
    }],
    "max_tokens": 1000
  }'
```

#### **OpenAI - GPT-4 Vision Preview** (Legacy)
```bash
#!/bin/bash
IMAGE_B64=$(base64 image.jpg | tr -d '\n')

curl https://api.openai.com/v1/chat/completions \
  -H "Authorization: Bearer $OPENAI_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-4-vision-preview",
    "messages": [{
      "role": "user",
      "content": [
        {"type": "text", "text": "Describe what is in this image"},
        {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,'"$IMAGE_B64"'"}}
      ]
    }],
    "max_tokens": 1000
  }'
```

---

#### **OpenRouter - OpenAI GPT-4o**
```bash
#!/bin/bash
IMAGE_B64=$(base64 image.jpg | tr -d '\n')

curl https://openrouter.ai/api/v1/chat/completions \
  -H "Authorization: Bearer $OPENROUTER_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "openai/gpt-4o",
    "messages": [{
      "role": "user",
      "content": [
        {"type": "text", "text": "Describe what is in this image"},
        {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,'"$IMAGE_B64"'"}}
      ]
    }],
    "modalities": ["image", "text"]
  }'
```

#### **OpenRouter - Google Gemini 2.5 Flash Image**
```bash
#!/bin/bash
IMAGE_B64=$(base64 image.jpg | tr -d '\n')

curl https://openrouter.ai/api/v1/chat/completions \
  -H "Authorization: Bearer $OPENROUTER_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "google/gemini-2.5-flash-image",
    "messages": [{
      "role": "user",
      "content": [
        {"type": "text", "text": "Describe what is in this image"},
        {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,'"$IMAGE_B64"'"}}
      ]
    }],
    "modalities": ["image", "text"]
  }'
```

#### **OpenRouter - Google Gemini 1.5 Flash**
```bash
#!/bin/bash
IMAGE_B64=$(base64 image.jpg | tr -d '\n')

curl https://openrouter.ai/api/v1/chat/completions \
  -H "Authorization: Bearer $OPENROUTER_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "google/gemini-1.5-flash",
    "messages": [{
      "role": "user",
      "content": [
        {"type": "text", "text": "Describe what is in this image"},
        {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,'"$IMAGE_B64"'"}}
      ]
    }],
    "modalities": ["image", "text"]
  }'
```

#### **OpenRouter - Anthropic Claude 3.5 Sonnet**
```bash
#!/bin/bash
IMAGE_B64=$(base64 image.jpg | tr -d '\n')

curl https://openrouter.ai/api/v1/chat/completions \
  -H "Authorization: Bearer $OPENROUTER_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "anthropic/claude-3-5-sonnet-20250620",
    "messages": [{
      "role": "user",
      "content": [
        {"type": "text", "text": "Describe what is in this image"},
        {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,'"$IMAGE_B64"'"}}
      ]
    }],
    "modalities": ["image", "text"],
    "max_tokens": 1024
  }'
```

#### **OpenRouter - Anthropic Claude 3 Haiku** (Fast & Cheap)
```bash
#!/bin/bash
IMAGE_B64=$(base64 image.jpg | tr -d '\n')

curl https://openrouter.ai/api/v1/chat/completions \
  -H "Authorization: Bearer $OPENROUTER_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "anthropic/claude-3-haiku-20240307",
    "messages": [{
      "role": "user",
      "content": [
        {"type": "text", "text": "Describe what is in this image"},
        {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,'"$IMAGE_B64"'"}}
      ]
    }],
    "modalities": ["image", "text"]
  }'
```

#### **OpenRouter - Anthropic Claude 3 Opus** (Premium Quality)
```bash
#!/bin/bash
IMAGE_B64=$(base64 image.jpg | tr -d '\n')

curl https://openrouter.ai/api/v1/chat/completions \
  -H "Authorization: Bearer $OPENROUTER_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "anthropic/claude-3-opus-20240229",
    "messages": [{
      "role": "user",
      "content": [
        {"type": "text", "text": "Describe what is in this image"},
        {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,'"$IMAGE_B64"'"}}
      ]
    }],
    "modalities": ["image", "text"],
    "max_tokens": 2000
  }'
```

#### **OpenRouter - Meta Llama 3.2 Vision**
```bash
#!/bin/bash
IMAGE_B64=$(base64 image.jpg | tr -d '\n')

curl https://openrouter.ai/api/v1/chat/completions \
  -H "Authorization: Bearer $OPENROUTER_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "meta/llama-3.2-vision",
    "messages": [{
      "role": "user",
      "content": [
        {"type": "text", "text": "Describe what is in this image"},
        {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,'"$IMAGE_B64"'"}}
      ]
    }],
    "modalities": ["image", "text"]
  }'
```

#### **OpenRouter - Mistral Large 2407**
```bash
#!/bin/bash
IMAGE_B64=$(base64 image.jpg | tr -d '\n')

curl https://openrouter.ai/api/v1/chat/completions \
  -H "Authorization: Bearer $OPENROUTER_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "mistral/mistral-large-2407",
    "messages": [{
      "role": "user",
      "content": [
        {"type": "text", "text": "Describe what is in this image"},
        {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,'"$IMAGE_B64"'"}}
      ]
    }],
    "modalities": ["image", "text"]
  }'
```

---

### 💡 Cross-Platform Helper Script

Save this as `describe_image.sh`:

```bash
#!/bin/bash
# Universal image description script
# Usage: ./describe_image.sh <model> <image_file>
# Example: ./describe_image.sh gpt-4o photo.jpg

if [ -z "$1" ] || [ -z "$2" ]; then
  echo "Usage: $0 <model> <image_file>"
  echo ""
  echo "Supported models:"
  echo "  OpenAI: gpt-4o, gpt-4o-mini, gpt-4-vision-preview"
  echo "  OpenRouter: openai/gpt-4o, google/gemini-2.5-flash-image, anthropic/claude-3-5-sonnet-20250620, etc."
  exit 1
fi

MODEL=$1
IMAGE_FILE=$2

# Check file exists
if [ ! -f "$IMAGE_FILE" ]; then
  echo "Error: File '$IMAGE_FILE' not found."
  exit 1
fi

# Encode based on OS
if [[ "$OSTYPE" == "darwin"* ]]; then
  IMAGE_B64=$(base64 "$IMAGE_FILE" | tr -d '\n')
else
  IMAGE_B64=$(base64 -w 0 "$IMAGE_FILE")
fi

# Determine API and endpoint
if [[ "$MODEL" == openai/* ]] || [[ "$MODEL" == google/* ]] || [[ "$MODEL" == anthropic/* ]] || [[ "$MODEL" == meta/* ]] || [[ "$MODEL" == mistral/* ]]; then
  API_URL="https://openrouter.ai/api/v1/chat/completions"
  API_KEY_VAR="OPENROUTER_API_KEY"
  MODALITIES='"modalities": ["image", "text"]'
else
  API_URL="https://api.openai.com/v1/chat/completions"
  API_KEY_VAR="OPENAI_API_KEY"
  MODALITIES=""
fi

# Build curl command
echo "Describing image with model: $MODEL"
curl "$API_URL" \
  -H "Authorization: Bearer ${!API_KEY_VAR}" \
  -H "Content-Type: application/json" \
  -d @- << EOF
{
  "model": "$MODEL",
  "messages": [{
    "role": "user",
    "content": [
      {"type": "text", "text": "Describe what is in this image"},
      {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,$IMAGE_B64"}}
    ]
  }],
  $MODALITIES
  "max_tokens": 1000
}
EOF
```

Make it executable:
```bash
chmod +x describe_image.sh
```

Usage:
```bash
# OpenAI
./describe_image.sh gpt-4o my_photo.jpg

# OpenRouter
./describe_image.sh openai/gpt-4o my_photo.jpg
./describe_image.sh google/gemini-2.5-flash-image my_photo.jpg
./describe_image.sh anthropic/claude-3-5-sonnet-20250620 my_photo.jpg
```

---

### 🎯 Practical Vision Examples

#### Example 1: Simple Image Description

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

#### Example 2: Detailed Analysis

**Prompt:** "Analyze this image in detail. Identify all objects, their colors, positions, and any text present."

#### Example 3: Question Answering

**Prompt:** "What is the main subject of this photograph?"

#### Example 4: Text Extraction (OCR)

**Prompt:** "Extract all text from this image"

#### Example 5: Multi-Image Comparison

**Prompt:** "What are the differences between these two images?"

---

### 🔧 Common Errors and Solutions

#### Error 1: Base64 Decoding Failed

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

#### Error 2: Invalid MIME Type

**Symptoms:**
```
"Unsupported image format"
```

**Causes:**
- Wrong MIME type specified (e.g., using png for jpeg)

**Solution:**
- JPEG: `data:image/jpeg;base64,...`
- PNG: `data:image/png;base64,...`

#### Error 3: Image Too Large

**Symptoms:**
```
"Image size exceeds limit"
```

**Solution:**
- Resize to maximum 2048x2048 pixels
- Reduce file size under 20MB

#### Error 4: Missing Modalities (OpenRouter)

**Symptoms:**
```
"modalities parameter required"
```

**Solution:**
Add `"modalities": ["image", "text"]` to your payload

---

## OpenAI Image Generation Deep Dive

### The Basics

OpenAI's image generation API (`/images/generations`) is the gold standard. Here's how it works:

```python
import os
import base64
from openai import OpenAI

# Initialize the client
client = OpenAI(
    api_key=os.environ.get('OPENAI_API_KEY'),
    base_url="https://api.openai.com/v1"
)

# Generate an image
response = client.images.generate(
    model="dall-e-3",
    prompt="A peaceful lake with mountains in the background, sunset lighting",
    size="1024x1024",
    quality="standard",
    n=1,
    response_format="b64_json"  # Get base64 data directly
)

# Extract and save the image
image_data = response.data[0].b64_json
image_bytes = base64.b64decode(image_data)

with open("generated_image.png", "wb") as f:
    f.write(image_bytes)

print("Image saved to generated_image.png")
```

### Supported Models and Sizes

| Model | Recommended Size | Quality Options |
|-------|------------------|------------------|
| dall-e-2 | 1024x1024, 512x512, 256x256 | standard, high |
| dall-e-3 | 1024x1024, 1024x1792, 1792x1024 | standard, high |

**Pro Tip:** Use 1024x1024 for maximum compatibility across all models.

### Response Format Options

- `b64_json`: Returns base64-encoded image data (best for programmatic use)
- `url`: Returns a URL to the generated image (expires after ~1 hour)

### Error Handling

```python
from openai import APIError

try:
    response = client.images.generate(
        model="dall-e-3",
        prompt="Your prompt here",
        size="1024x1024"
    )
except APIError as e:
    print(f"OpenAI API Error: {e}")
    if e.code == "invalid_api_key":
        print("Check your API key!")
    elif e.code == "rate_limit_exceeded":
        print("Too many requests. Try again later or increase your rate limit.")
except Exception as e:
    print(f"Unexpected error: {e}")
```

---

## OpenRouter: The Multi-Model Gateway

### Why OpenRouter?

OpenRouter is more than just a proxy—it's a unified API that gives you access to **hundreds of models** from different providers:

- Google's Florence 2 and Imagen
- Black Forest Labs' Flux
- Stability AI's SDXL
- Amazon's Titan
- And many, many more

**Key Advantage:** One API key, one endpoint, access to everything.

### Authentication

```python
import os
import aiohttp
import json

OPENROUTER_API_KEY = os.environ.get('OPENROUTER_API_KEY')
BASE_URL = "https://openrouter.ai/api/v1"

headers = {
    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
    "Content-Type": "application/json"
}
```

### Image Generation via Chat Completions

This is where OpenRouter differs from traditional approaches:

```python
import aiohttp
import asyncio

async def generate_with_openrouter(prompt: str, model: str = "google/gemini-2.5-flash-image"):
    """
    Generate an image using OpenRouter's chat completions endpoint.
    
    Args:
        prompt: The text description of the image you want
        model: The model identifier from OpenRouter
    
    Returns:
        Base64 encoded image data
    """
    url = "https://openrouter.ai/api/v1/chat/completions"
    
    # CRITICAL: Must specify modalities for image models
    payload = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": prompt
            }
        ],
        "modalities": ["image", "text"]  # This tells OpenRouter we want image output
    }
    
    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=payload, headers=headers) as response:
            if response.status != 200:
                error_data = await response.text()
                raise Exception(f"API Error: {response.status} - {error_data}")
            
            data = await response.json()
            
            # Extract image from response
            # Different models return images in different formats
            if data.get("choices") and len(data["choices"]) > 0:
                message = data["choices"][0]["message"]
                content = message.get("content", "")
                
                # Check for images in content (Flux.2 and similar)
                images = message.get("images", [])
                if images:
                    for image_item in images:
                        if isinstance(image_item, dict):
                            image_url = image_item.get("image_url", {}).get("url", "")
                            if image_url.startswith("data:"):
                                # Extract base64 data
                                return image_url.split(",")[1]
                
                # Check for multi-modal content array
                if isinstance(content, list):
                    for item in content:
                        if isinstance(item, dict) and item.get("type") == "image_url":
                            image_url = item.get("image_url", {}).get("url", "")
                            if image_url.startswith("data:"):
                                return image_url.split(",")[1]
                
                # Check for single image URL string
                if isinstance(content, str) and content.startswith("data:"):
                    return content.split(",")[1]
            
            raise Exception(f"No image data found in response: {data}")

# Usage
# image_data = asyncio.run(generate_with_openrouter("A beautiful sunset"))
```

### Understanding Modalities

The `modalities` parameter is **critical** for OpenRouter image generation:

```python
# For image-only models (like Flux.2)
modalities = ["image"]  # Model can only generate images

# For multi-modal models (like gemini-2.5-flash-image)
modalities = ["image", "text"]  # Model can generate both

# For text-only models
modalities = ["text"]  # Model can only generate text
```

**Common Image Models on OpenRouter:**

| Model ID | Type | Modalities |
|----------|------|-------------|
| `google/gemini-2.5-flash-image` | Multi-modal | ["image", "text"] |
| `black-forest-labs/flux.2-max` | Image-only | ["image"] |
| `stabilityai/sdxl-turbo` | Image-only | ["image"] |
| `amazon/titan-image-generator-v2` | Image-only | ["image"] |

### Image Configuration

OpenRouter uses `image_config` instead of OpenAI's `size` and `quality` parameters:

```python
payload = {
    "model": "google/gemini-2.5-flash-image",
    "messages": [{"role": "user", "content": prompt}],
    "modalities": ["image", "text"],
    "image_config": {
        "aspect_ratio": "1:1",  # or "16:9", "4:5", etc.
        "image_size": "1024x1024"
    }
}
```

**Pro Tip:** Not all models support `image_config`. Check the model documentation on OpenRouter's website.

### Rate Limits and Pricing

OpenRouter uses a **ranking system**:
- Free tier: Access to many free models
- Paid tier: Higher rate limits, access to premium models
- Each model has its own pricing and rate limits

Check your usage at: https://openrouter.ai/keys

---

## Building Your Own Image Generator

Let's build a complete, production-ready image generator like the one in Chatybot:

### Step 1: The Base Class

```python
#!/usr/bin/env python3
"""
Image Generator Module - Foundation for multi-vendor image generation
"""

import os
import base64
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, Tuple, List
import aiohttp


class ImageGenerator:
    """Handles text-to-image generation across multiple vendors."""
    
    def __init__(self, config_manager=None):
        """
        Initialize the image generator.
        
        Args:
            config_manager: Optional configuration manager for settings
        """
        self.config_manager = config_manager
        self.image_dir = os.path.expanduser("~/chatybot_images")
        self.counters: Dict[str, int] = {}  # Track counter per date
        self.session: Optional[aiohttp.ClientSession] = None
        self.last_generated_image: Optional[Tuple[str, str]] = None
    
    def set_directory(self, path: str) -> None:
        """Set the default image save directory."""
        self.image_dir = os.path.expanduser(path)
        os.makedirs(self.image_dir, exist_ok=True)
    
    async def generate_image(
        self,
        prompt: str,
        vendor: Optional[str] = None,
        model_name: Optional[str] = None,
        size: Optional[str] = None,
        quality: Optional[str] = None,
        endpoint: Optional[str] = None,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        modalities: Optional[list] = None,
    ) -> Tuple[str, str]:
        """
        Generate an image from a text prompt.
        
        Args:
            prompt: The text prompt for image generation
            vendor: The vendor to use (openai, openrouter, mistral, etc.)
            model_name: The specific model name
            size: Image size (e.g., "1024x1024")
            quality: Quality level
            endpoint: API endpoint for image generation
            api_key: API key for authentication
            base_url: Base URL for the API
            modalities: List of modalities for the model
        
        Returns:
            Tuple of (file_path, base64_data)
        """
        # Default to OpenAI if vendor not specified
        if vendor is None:
            vendor = "openai"
        
        vendor_lower = vendor.lower()
        endpoint_lower = endpoint.lower() if endpoint else ""
        
        # Route to the appropriate generation method
        if "openrouter" in vendor_lower or endpoint_lower in ["/api/v1/chat/completions", "/chat/completions"]:
            return await self._generate_openrouter(
                prompt, model_name, size, quality, endpoint, api_key, base_url, modalities
            )
        elif "openai" in vendor_lower or vendor_lower == "default":
            return await self._generate_openai(
                prompt, model_name, size, quality, endpoint, api_key, base_url
            )
        elif "mistral" in vendor_lower:
            # Mistral uses OpenAI-compatible format
            return await self._generate_openai(
                prompt, model_name, size, quality, endpoint, api_key, base_url
            )
        else:
            raise ValueError(f"Unsupported image vendor: {vendor}")
```

### Step 2: OpenAI Implementation

```python
    async def _generate_openai(
        self,
        prompt: str,
        model_name: Optional[str],
        size: Optional[str],
        quality: Optional[str],
        endpoint: Optional[str],
        api_key: Optional[str],
        base_url: Optional[str],
    ) -> Tuple[str, str]:
        """Generate image using OpenAI-compatible API."""
        import openai
        
        # Use provided values or defaults
        effective_base_url = base_url or "https://api.openai.com/v1"
        effective_api_key = api_key or os.environ.get("OPENAI_API_KEY", "")
        effective_model = model_name or "dall-e-3"
        effective_size = size or "1024x1024"
        effective_quality = quality or "standard"
        effective_endpoint = endpoint or "/images/generations"
        
        # Create client
        client = openai.OpenAI(
            api_key=effective_api_key,
            base_url=effective_base_url
        )
        
        try:
            response = client.images.generate(
                model=effective_model,
                prompt=prompt,
                size=effective_size,
                quality=effective_quality,
                n=1,
                response_format="b64_json"
            )
            
            image_data = response.data[0].b64_json
            file_path = self._save_image(
                image_data, prompt, 
                vendor="openai", 
                model=effective_model, 
                size=effective_size, 
                quality=effective_quality
            )
            return file_path, image_data
            
        except Exception as e:
            raise ValueError(f"OpenAI image generation failed: {str(e)}")
```

### Step 3: OpenRouter Implementation

```python
    async def _generate_openrouter(
        self,
        prompt: str,
        model_name: Optional[str],
        size: Optional[str],
        quality: Optional[str],
        endpoint: Optional[str],
        api_key: Optional[str],
        base_url: Optional[str],
        modalities: Optional[list] = None,
    ) -> Tuple[str, str]:
        """Generate image using OpenRouter's API."""
        # Use provided values or defaults
        effective_base_url = base_url or "https://openrouter.ai/api/v1"
        effective_api_key = api_key or os.environ.get("OPENROUTER_API_KEY", "")
        effective_model = model_name or "google/gemini-2.5-flash-image"
        effective_endpoint = endpoint or "/chat/completions"
        
        # Parse size
        width, height = 1024, 1024
        if size:
            try:
                w, h = size.lower().split("x")
                width = int(w)
                height = int(h)
            except (ValueError, AttributeError):
                pass
        
        # Build request body
        # Use configured modalities, default to ["image", "text"] for backward compatibility
        effective_modalities = modalities or ["image", "text"]
        
        request_body = {
            "model": effective_model,
            "messages": [
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "modalities": effective_modalities
        }
        
        # Add image_config only if size is specified
        if size:
            if width == height:
                aspect_ratio = "1:1"
            elif width > height:
                aspect_ratio = f"{width}:{height}"
            else:
                aspect_ratio = f"{height}:{width}"
            request_body["image_config"] = {
                "aspect_ratio": aspect_ratio,
                "image_size": size
            }
        
        try:
            async with aiohttp.ClientSession() as session:
                headers = {
                    "Authorization": f"Bearer {effective_api_key}",
                    "Content-Type": "application/json"
                }
                
                async with session.post(
                    f"{effective_base_url}{effective_endpoint}",
                    json=request_body,
                    headers=headers
                ) as resp:
                    if resp.status != 200:
                        error_text = await resp.text()
                        raise ValueError(f"OpenRouter API error ({resp.status}): {error_text}")
                    
                    data = await resp.json()
                    
                    # Extract image from response
                    # Different models return images in different locations
                    if data.get("choices") and len(data["choices"]) > 0:
                        message = data["choices"][0].get("message", {})
                        content = message.get("content", "")
                        
                        # Check images array first (Flux.2 and similar)
                        images = message.get("images", [])
                        if images and len(images) > 0:
                            for image_item in images:
                                if isinstance(image_item, dict):
                                    image_url = image_item.get("image_url", {}).get("url", "")
                                    if image_url and image_url.startswith("data:"):
                                        image_data = image_url.split(",")[1]
                                        file_path = self._save_image(
                                            image_data, prompt, vendor="openrouter",
                                            model=effective_model, size=size, quality=quality
                                        )
                                        return file_path, image_data
                        
                        # Check for multi-modal content array
                        if isinstance(content, list):
                            for item in content:
                                if isinstance(item, dict) and item.get("type") == "image_url":
                                    image_url = item.get("image_url", {}).get("url", "")
                                    if image_url.startswith("data:"):
                                        image_data = image_url.split(",")[1]
                                        file_path = self._save_image(
                                            image_data, prompt, vendor="openrouter",
                                            model=effective_model, size=size, quality=quality
                                        )
                                        return file_path, image_data
                        
                        # Check for single string content
                        elif isinstance(content, str) and content.startswith("data:"):
                            image_data = content.split(",")[1]
                            file_path = self._save_image(
                                image_data, prompt, vendor="openrouter",
                                model=effective_model, size=size, quality=quality
                            )
                            return file_path, image_data
                    
                    raise ValueError(f"No image data found in OpenRouter response: {data}")
        
        except Exception as e:
            raise ValueError(f"OpenRouter image generation failed: {str(e)}")
```

### Step 4: Saving and Managing Images

```python
    def _save_image(
        self,
        image_data: str,
        prompt: str,
        vendor: str,
        model: str,
        size: Optional[str] = None,
        quality: Optional[str] = None,
    ) -> str:
        """Save image to disk with auto-naming convention."""
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
        
        # Update index for tracking
        self._update_index(date_str, filename, prompt, vendor, model, size, quality)
        
        # Store for potential retrieval
        self.last_generated_image = (file_path, image_data)
        
        return file_path
    
    def _update_index(
        self,
        date_str: str,
        filename: str,
        prompt: str,
        vendor: str,
        model: str,
        size: Optional[str] = None,
        quality: Optional[str] = None,
    ) -> None:
        """Update the index.json for a date."""
        index_path = os.path.join(self.image_dir, date_str, "index.json")
        
        data: Dict[str, Any] = {}
        if os.path.exists(index_path):
            with open(index_path, "r") as f:
                data = json.load(f)
        
        data["date"] = date_str
        if "images" not in data:
            data["images"] = {}
        
        data["images"][filename] = {
            "prompt": prompt,
            "model": model,
            "vendor": vendor,
            "timestamp": datetime.now().isoformat() + "Z",
            "size": size,
            "quality": quality,
        }
        
        with open(index_path, "w") as f:
            json.dump(data, f, indent=2)
    
    def list_images(self, date: Optional[str] = None) -> Dict[str, Any]:
        """List all images, optionally filtered by date."""
        results: Dict[str, Any] = {}
        
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
    
    def get_image_info(self, date: str, filename: str) -> Optional[Dict[str, Any]]:
        """Get info about a specific image."""
        index_path = Path(self.image_dir) / date / "index.json"
        if not index_path.exists():
            return None
        
        with open(index_path, "r") as f:
            data = json.load(f)
        
        return data.get("images", {}).get(filename)
```

### Step 5: Handling Image Banks (For Multi-Modal Chat)

This is crucial for using images in chat prompts:

```python
class BufferManager:
    """Manages file buffers, file banks, script variables, and image banks."""
    
    def __init__(self):
        self.file_buffer: str = ""
        self.prompt_buffer: str = ""
        self.file_banks: Dict[str, str] = {f"filebank{i}": "" for i in range(1, 6)}
        self.image_banks: Dict[str, str] = {f"imagebank{i}": "" for i in range(1, 6)}
        self.script_vars: Dict[str, str] = {}
    
    def detect_image_format(self, file_path: str) -> str:
        """Detect image MIME type from file extension."""
        ext = Path(file_path).suffix.lower()
        if ext in ['.jpg', '.jpeg']:
            return 'image/jpeg'
        elif ext == '.png':
            return 'image/png'
        else:
            raise ValueError(f"Unsupported image format: {ext}")
    
    def load_image_to_bank(self, bank_num: int, file_path: str) -> None:
        """Load an image file into a specific image bank as base64 data URL."""
        if bank_num < 1 or bank_num > 5:
            raise ValueError("Invalid imagebank number. Please use 1 through 5.")
        
        bank_name = f"imagebank{bank_num}"
        mime_type = self.detect_image_format(file_path)
        
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
    
    def replace_placeholders(self, prompt: str, include_images: bool = True) -> Tuple[str, List[Dict]]:
        """
        Replace placeholders in the prompt.
        For image banks, returns separated text and images for OpenAI multimodal format.
        
        Args:
            prompt: The prompt string containing placeholders
            include_images: If True, include image banks in search
        
        Returns:
            Tuple of (text_prompt, image_list) where:
            - text_prompt: Prompt with filebank and script var placeholders replaced
            - image_list: List of image content dicts for OpenAI format
        """
        # First, handle text placeholders (filebanks and script vars)
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
                if placeholder in text_prompt:
                    if content:  # Has valid image data
                        if content.startswith("data:"):
                            image_list.append({
                                "type": "image_url",
                                "image_url": {"url": content}
                            })
                        # Remove the placeholder from text
                        text_prompt = text_prompt.replace(placeholder, "")
        
        # Clean up whitespace
        text_prompt = text_prompt.strip()
        while "  " in text_prompt:
            text_prompt = text_prompt.replace("  ", " ")
        
        return text_prompt, image_list
```

---

## Advanced Topics

### Multi-Modal Chat with Images

Using images in chat completion requests:

```python
async def chat_with_image(client, prompt: str, image_data: str):
    """
    Send a chat completion request with both text and image.
    
    Args:
        client: OpenAI AsyncOpenAI client
        prompt: The text prompt
        image_data: Base64 encoded image data
    """
    # Create the content array with both text and image
    content_parts = [
        {"type": "text", "text": prompt},
        {
            "type": "image_url",
            "image_url": {"url": f"data:image/png;base64,{image_data}"}
        }
    ]
    
    messages = [
        {"role": "user", "content": content_parts}
    ]
    
    response = await client.chat.completions.create(
        model="gpt-4o",  # Use a vision model
        messages=messages,
        max_tokens=1000
    )
    
    return response.choices[0].message.content
```

### Batch Image Generation

```python
async def batch_generate(prompts: List[str], model: str = "dall-e-3") -> List[str]:
    """Generate multiple images from a list of prompts."""
    import openai
    
    client = openai.AsyncOpenAI()
    results = []
    
    for i, prompt in enumerate(prompts):
        print(f"Generating image {i+1}/{len(prompts)}: {prompt[:50]}...")
        
        try:
            response = await client.images.generate(
                model=model,
                prompt=prompt,
                size="1024x1024",
                quality="standard",
                n=1,
                response_format="b64_json"
            )
            
            image_data = response.data[0].b64_json
            results.append(image_data)
            
        except Exception as e:
            print(f"Failed to generate image {i+1}: {e}")
            results.append(None)
    
    return results
```

### Image-to-Image (Variations)

```python
async def create_variation(client, image_path: str, n: int = 1):
    """Create variations of an existing image."""
    # Load and encode the image
    with open(image_path, "rb") as f:
        image_bytes = f.read()
    
    import base64
    image_b64 = base64.b64encode(image_bytes).decode('utf-8')
    
    response = await client.images.create_variation(
        image=image_b64,
        n=n,
        size="1024x1024",
        response_format="b64_json"
    )
    
    return [data.b64_json for data in response.data]
```

### Debugging and Error Handling

```python
class ImageGenerationError(Exception):
    """Custom exception for image generation errors."""
    pass

def log_image_request(prompt: str, model: str, size: str) -> None:
    """Log image generation requests for debugging."""
    timestamp = datetime.now().isoformat()
    log_entry = f"[{timestamp}] Image request: model={model}, size={size}, prompt={prompt[:100]}...\n"
    
    with open("image_generation.log", "a") as f:
        f.write(log_entry)

async def safe_generate_image(prompt: str, **kwargs) -> Optional[Tuple[str, str]]:
    """Wrapper for safe image generation with logging."""
    try:
        log_image_request(prompt, kwargs.get("model_name", "unknown"), kwargs.get("size", "1024x1024"))
        
        generator = ImageGenerator()
        file_path, image_data = await generator.generate_image(prompt, **kwargs)
        
        # Log success
        with open("image_generation.log", "a") as f:
            f.write(f"[{datetime.now().isoformat()}] SUCCESS: {file_path}\n")
        
        return file_path, image_data
        
    except Exception as e:
        # Log failure
        with open("image_generation.log", "a") as f:
            f.write(f"[{datetime.now().isoformat()}] FAILED: {str(e)}\n")
        
        print(f"Image generation failed: {e}")
        return None
```

---

## Best Practices and Tips

### 1. Always Use Environment Variables for API Keys

**Bad:**
```python
client = OpenAI(api_key="sk-abc123...")  # Hardcoded key
```

**Good:**
```python
client = OpenAI(api_key=os.environ.get('OPENAI_API_KEY'))
```

Use a `.env` file:
```bash
OPENAI_API_KEY=sk-abc123...
OPENROUTER_API_KEY=sk_or_abc123...
```

### 2. Handle Rate Limits Gracefully

```python
import time
from openai import RateLimitError

async def generate_with_retry(prompt: str, max_retries: int = 3) -> Optional[str]:
    """Generate image with automatic retry on rate limits."""
    for attempt in range(max_retries):
        try:
            response = await client.images.generate(
                model="dall-e-3",
                prompt=prompt,
                size="1024x1024"
            )
            return response.data[0].b64_json
            
        except RateLimitError:
            if attempt < max_retries - 1:
                wait_time = 2 ** attempt  # Exponential backoff
                print(f"Rate limited. Retrying in {wait_time} seconds...")
                time.sleep(wait_time)
            else:
                print("Rate limit exceeded after all retries.")
                return None
```

### 3. Optimize Your Prompts

**Image prompt best practices:**

| Do | Don't |
|----|-------|
| Be specific and descriptive | Use vague terms |
| "A red sports car on a winding road through the Swiss Alps" | "A nice picture" |
| Mention style and lighting | Assume the model knows what you want |
| "Photorealistic, golden hour lighting, cinematic composition" | "Good quality" |
| Use artist references | Use copyrighted character names |
| "In the style of Monet" | "Disney's Mickey Mouse" |

### 4. Organize Your Generated Images

The file structure matters:
```
chatybot_images/
├── 2025-01-15/
│   ├── index.json          # Metadata about all images this day
│   ├── prompt_001.png
│   ├── prompt_002.png
│   └── prompt_003.png
└── 2025-01-16/
    ├── index.json
    └── prompt_001.png
```

### 5. Test with Different Models

Each model has different strengths:

| Model | Strengths | Best For |
|-------|-----------|----------|
| dall-e-3 | Text understanding, complex prompts | Detailed scenes, conceptual art |
| flux.2 | High quality, artistic | Professional artwork, illustrations |
| sdxl-turbo | Fast generation | Quick prototyping |
| gemini-2.5-flash-image | Multi-modal, text+image | Chat applications |

---

## Specific Things About OpenRouter

### 1. Model Discovery

OpenRouter has **thousands of models**. Use their API to discover image-capable ones:

```python
async def get_image_models():
    """Get list of all image-capable models from OpenRouter."""
    url = "https://openrouter.ai/api/v1/models"
    
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            data = await response.json()
            
            image_models = []
            for model in data.get("data", []):
                # Check if model supports image generation
                if "image" in model.get("modalities", []):
                    image_models.append({
                        "id": model["id"],
                        "name": model.get("name", model["id"]),
                        "description": model.get("description", ""),
                        "pricing": model.get("pricing", {}),
                        "context_length": model.get("context_length", 0)
                    })
            
            return image_models
```

### 2. Model Pricing

OpenRouter uses a transparent pricing system. Always check:

```python
async def get_model_pricing(model_id: str) -> Optional[Dict]:
    """Get pricing information for a specific model."""
    url = f"https://openrouter.ai/api/v1/models/{model_id}"
    
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            if response.status == 200:
                data = await response.json()
                return data.get("pricing", {})
            return None
```

### 3. Free Models

OpenRouter offers many free models. Some popular free image models:

- `black-forest-labs/flux.2-max:free`
- `stabilityai/sdxl-turbo:free`
- `amazon/titan-image-generator-v2:free`
- `google/gemini-2.5-flash-image:free`

**Note:** Free models often have higher rate limits but may have usage caps.

### 4. Custom Routs

OpenRouter allows you to create **custom routs**—groups of models with fallback logic:

```python
# Example of using a custom rout
async def generate_with_rout(rout_id: str, prompt: str):
    """Use a custom OpenRouter rout for image generation."""
    url = "https://openrouter.ai/api/v1/chat/completions"
    
    payload = {
        "rout": rout_id,  # Use rout instead of model
        "messages": [{"role": "user", "content": prompt}],
        "modalities": ["image", "text"]
    }
    
    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=payload, headers=headers) as response:
            return await response.json()
```

### 5. Site URL and Referrers

OpenRouter allows you to set a site URL for analytics:

```python
payload = {
    "model": "google/gemini-2.5-flash-image",
    "messages": [{"role": "user", "content": prompt}],
    "modalities": ["image", "text"],
    "site_url": "https://myapp.com"  # Optional: for analytics
}
```

### 6. Streaming Support

OpenRouter supports streaming for image generation:

```python
async def generate_image_stream(prompt: str):
    """Generate image with streaming (if supported by model)."""
    url = "https://openrouter.ai/api/v1/chat/completions"
    
    payload = {
        "model": "google/gemini-2.5-flash-image",
        "messages": [{"role": "user", "content": prompt}],
        "modalities": ["image", "text"],
        "stream": True
    }
    
    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=payload, headers=headers) as response:
            if response.status == 200:
                async for line in response.content:
                    if line:
                        # Process streaming data
                        data = json.loads(line)
                        # Handle partial image data if available
                        yield data
```

**Note:** Not all image models support streaming. Check the model documentation.

---

## Conclusion

Image processing with AI APIs has never been more accessible. Whether you're using OpenAI's dedicated endpoints or OpenRouter's flexible multi-model approach, the patterns are similar and the integration is straightforward.

**Key Takeaways:**

1. **Two Domains:** Image generation (text-to-image) and image interpretation (image-to-text)
2. **OpenAI API** is the standard for image generation; their vision models support interpretation
3. **OpenRouter** provides access to hundreds of models through a single API
4. **Modalities** are crucial for OpenRouter
5. **Always handle errors** - APIs fail, rate limits happen
6. **Organize your code** - Use classes and methods for different vendors
7. **Manage images** - Save with metadata, support retrieval
8. **Consider multi-modal** - Images can be used in chat, not just generated

The Chatybot project demonstrates a production-ready approach with:
- Multi-vendor support
- Image banking for multi-modal chat
- Comprehensive error handling
- Debugging capabilities
- File organization and metadata tracking

As AI continues to evolve, image processing will become even more powerful and accessible. The skills you've learned here will serve you well in building the next generation of AI-powered applications.

---

*Happy coding! 🎨*

---

### Additional Resources

- [OpenAI Vision Documentation](https://platform.openai.com/docs/guides/vision)
- [OpenAI Image Generation Documentation](https://platform.openai.com/docs/guides/images)
- [OpenRouter Documentation](https://openrouter.ai/docs)
- [OpenRouter Model List](https://openrouter.ai/models)
- [Chatybot GitHub](https://github.com/jon2allen/chatybot)

### Sample Commands from Chatybot

```
/imagine A beautiful sunset over the ocean with a sailboat
/saveimage my_sunset.png
/imagesize 1024x1024
/imagequality high
/imagedir ~/my_images
/listimages
/showimage 2025-01-15/prompt_001.png
/imagebank1 load my_image.jpg
/loadimage 1 my_image.jpg
```
