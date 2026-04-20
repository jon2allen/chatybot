#! /usr/bin/env python3
"""
Image Generator Module
Handles text-to-image generation across different vendors
"""

import base64
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, Tuple, List
import aiohttp


class ImageGenerator:
    """Handles text-to-image generation across vendors."""
    
    def __init__(self, config_manager: Any = None):
        """
        Initialize the image generator.
        
        Args:
            config_manager: Optional reference to ConfigManager for settings
        """
        self.config_manager = config_manager
        self.image_dir = os.path.expanduser("~/chatybot_images")
        self.counters: Dict[str, int] = {}  # Track counter per date
        self.session: Optional[aiohttp.ClientSession] = None
        
        # Per-session state
        self.last_generated_image: Optional[Tuple[str, str]] = None  # (file_path, base64_data)
    
    def set_directory(self, path: str) -> None:
        """Set the default image save directory."""
        self.image_dir = os.path.expanduser(path)
        os.makedirs(self.image_dir, exist_ok=True)
    
    def get_image_directory(self) -> str:
        """Get the current image directory."""
        return self.image_dir
    
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
            vendor: The vendor to use (openai, mistral, ollama, etc.)
            model_name: The model name
            size: Image size (e.g., "1024x1024")
            quality: Quality level (e.g., "standard", "high")
            endpoint: API endpoint for image generation
            api_key: API key for authentication
            base_url: Base URL for the API
            modalities: List of modalities for the model (e.g., ["image", "text"] or ["image"])
            
        Returns:
            Tuple of (file_path, base64_data)
            
        Raises:
            ValueError: If vendor is unsupported or generation fails
        """
        # Determine vendor from input or defaults
        if vendor is None:
            vendor = "openai"  # Default
        
        vendor_lower = vendor.lower()
        endpoint_lower = endpoint.lower() if endpoint else ""
        
        # Choose the right generation method
        # OpenRouter uses chat/completions with modalities for image generation
        if "openrouter" in vendor_lower or endpoint_lower in ["/api/v1/chat/completions", "/chat/completions"]:
            return await self._generate_openrouter(
                prompt, model_name, size, quality, endpoint, api_key, base_url, modalities
            )
        elif "openai" in vendor_lower or vendor_lower == "default":
            return await self._generate_openai(
                prompt, model_name, size, quality, endpoint, api_key, base_url
            )
        elif "mistral" in vendor_lower:
            return await self._generate_mistral(
                prompt, model_name, size, quality, endpoint, api_key, base_url
            )
        elif "ollama" in vendor_lower:
            return await self._generate_ollama(
                prompt, model_name, size, quality, endpoint, api_key, base_url
            )
        elif "nvidia" in vendor_lower:
            return await self._generate_openai(
                prompt, model_name, size, quality, endpoint, api_key, base_url
            )
        elif "publicai" in vendor_lower:
            return await self._generate_openai(
                prompt, model_name, size, quality, endpoint, api_key, base_url
            )
        elif "bytez" in vendor_lower:
            return await self._generate_openai(
                prompt, model_name, size, quality, endpoint, api_key, base_url
            )
        else:
            raise ValueError(f"Unsupported image vendor: {vendor}")
    
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
        """
        Generate image using OpenAI-compatible API (OpenAI, Mistral, NVIDIA, etc.).
        """
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
            file_path = self._save_image(image_data, prompt, vendor="openai", model=effective_model, size=effective_size, quality=effective_quality)
            return file_path, image_data
            
        except Exception as e:
            raise ValueError(f"OpenAI image generation failed: {str(e)}")
    
    async def _generate_mistral(
        self,
        prompt: str,
        model_name: Optional[str],
        size: Optional[str],
        quality: Optional[str],
        endpoint: Optional[str],
        api_key: Optional[str],
        base_url: Optional[str],
    ) -> Tuple[str, str]:
        """
        Generate image using Mistral's image API.
        Mistral uses OpenAI-compatible format for images.
        """
        # Mistral uses the same OpenAI-compatible API
        return await self._generate_openai(
            prompt, model_name, size, quality, endpoint, api_key, base_url
        )

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
        """
        Generate image using OpenRouter's API with direct HTTP calls.
        OpenRouter uses /chat/completions for image generation with modalities.
        Requires models like: google/gemini-2.5-flash-image
        """
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
        
        # Build request body for OpenRouter
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
        # Note: OpenRouter uses image_config, not standard OpenAI parameters
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
                    # OpenRouter returns images in choices[0].message.content OR choices[0].message.images
                    if data.get("choices") and len(data["choices"]) > 0:
                        message = data["choices"][0].get("message", {})
                        content = message.get("content", "")
                        
                        # Check images array first (Flux.2 and some other models use this)
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
                        
                        if isinstance(content, list):
                            # Multi-modal response with text and image parts
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
    
    async def _generate_ollama(
        self,
        prompt: str,
        model_name: Optional[str],
        size: Optional[str],
        quality: Optional[str],
        endpoint: Optional[str],
        api_key: Optional[str],
        base_url: Optional[str],
    ) -> Tuple[str, str]:
        """
        Generate image using Ollama's local API.
        """
        effective_base_url = base_url or "http://localhost:11434"
        effective_model = model_name or "stable-diffusion"
        effective_endpoint = endpoint or "/api/generate"
        
        # Parse size
        width, height = 1024, 1024
        if size:
            try:
                w, h = size.lower().split("x")
                width = int(w)
                height = int(h)
            except (ValueError, AttributeError):
                pass
        
        payload = {
            "model": effective_model,
            "prompt": prompt,
            "width": width,
            "height": height,
        }
        
        if quality:
            payload["quality"] = quality
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{effective_base_url}{effective_endpoint}",
                    json=payload
                ) as resp:
                    if resp.status != 200:
                        error_text = await resp.text()
                        raise ValueError(f"Ollama error ({resp.status}): {error_text}")
                    
                    data = await resp.json()
                    
                    # Ollama returns image as base64 in 'image' field
                    if "image" in data:
                        image_data = data["image"]
                        file_path = self._save_image(
                            image_data, prompt, vendor="ollama", 
                            model=effective_model, size=size, quality=quality
                        )
                        return file_path, image_data
                    else:
                        raise ValueError(f"Unexpected response from Ollama: {data}")
                        
        except Exception as e:
            raise ValueError(f"Ollama image generation failed: {str(e)}")
    
    def _save_image(
        self,
        image_data: str,
        prompt: str,
        vendor: str,
        model: str,
        size: Optional[str] = None,
        quality: Optional[str] = None,
    ) -> str:
        """
        Save image to disk with auto-naming convention.
        
        Args:
            image_data: Base64 encoded image data
            prompt: The text prompt used to generate the image
            vendor: The vendor/model family
            model: The specific model name
            size: Image size
            quality: Quality setting
            
        Returns:
            Path to the saved image file
        """
        # Ensure image directory exists
        os.makedirs(self.image_dir, exist_ok=True)
        
        # Get date and counter
        date_str = datetime.now().strftime("%Y-%m-%d")
        date_dir = os.path.join(self.image_dir, date_str)
        os.makedirs(date_dir, exist_ok=True)
        
        # Get next counter for this date
        self.counters[date_str] = self.counters.get(date_str, 0) + 1
        counter = self.counters[date_str]
        
        # Determine file format based on vendor
        # Most image models produce PNG by default
        format_ext = ".png"
        mime_type = "image/png"
        
        # Generate filename
        filename = f"prompt_{counter:03d}{format_ext}"
        file_path = os.path.join(date_dir, filename)
        
        # Decode and save
        image_bytes = base64.b64decode(image_data)
        with open(file_path, "wb") as f:
            f.write(image_bytes)
        
        # Update index
        self._update_index(date_str, filename, prompt, vendor, model, size, quality)
        
        # Store for potential Retrieval
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
        if "counter" not in data:
            data["counter"] = 0
        
        data["counter"] = self.counters.get(date_str, 0)
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
        """
        List all images, optionally filtered by date.
        
        Args:
            date: Optional date filter (YYYY-MM-DD format)
            
        Returns:
            Dictionary mapping dates to image metadata
        """
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
        """
        Get info about a specific image.
        
        Args:
            date: Date in YYYY-MM-DD format
            filename: The filename of the image
            
        Returns:
            Dictionary with image metadata, or None if not found
        """
        index_path = Path(self.image_dir) / date / "index.json"
        if not index_path.exists():
            return None
        
        with open(index_path, "r") as f:
            data = json.load(f)
        
        return data.get("images", {}).get(filename)
    
    def delete_image(self, date: str, filename: str, delete_file: bool = True) -> bool:
        """
        Delete an image from the index and optionally from disk.
        
        Args:
            date: Date in YYYY-MM-DD format
            filename: The filename of the image
            delete_file: If True, also delete the actual image file
            
        Returns:
            True if successful, False otherwise
        """
        index_path = Path(self.image_dir) / date / "index.json"
        if not index_path.exists():
            return False
        
        with open(index_path, "r") as f:
            data = json.load(f)
        
        if date not in data.get("images", {}):
            return False
        
        del data["images"][filename]
        
        with open(index_path, "w") as f:
            json.dump(data, f, indent=2)
        
        if delete_file:
            file_path = Path(self.image_dir) / date / filename
            if file_path.exists():
                file_path.unlink()
        
        return True
