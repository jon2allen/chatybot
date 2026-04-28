#! /usr/bin/env python3
"""
Mistral Audio Provider
Handles Mistral Voxtral STT and TTS via API
"""

import aiohttp
import base64
from typing import Any, Dict, Optional, Union
import os

from chatybot.audio_providers.base import AudioProvider
from chatybot.audio_provider import AudioModelConfig


class MistralAudioProvider(AudioProvider):
    """
    Provider for Mistral audio APIs (Voxtral STT and TTS).
    
    Supports:
    - STT: voxtral-mini-latest (offline batch transcription)
    - TTS: voxtral-mini-tts-2603 (text-to-speech with voice cloning)
    """
    
    def __init__(self, config: AudioModelConfig):
        """Initialize the Mistral audio provider."""
        super().__init__(config)
        
        # Mistral-specific settings
        self.base_url = config.base_url or "https://api.mistral.ai/v1"
        self.api_key = os.environ.get(config.api_key_env or "MISTRAL_API_KEY")
        
        if not self.api_key:
            raise ValueError(f"Mistral API key not found. Set {config.api_key_env or 'MISTRAL_API_KEY'} environment variable.")
        
        self.api_endpoint = config.api_endpoint or self._get_default_endpoint()
    
    def _get_default_endpoint(self) -> str:
        """Get default API endpoint based on model type."""
        if self.config.model_type == "stt":
            return "/v1/audio/transcriptions"
        elif self.config.model_type == "tts":
            return "/v1/audio/speech"
        return ""
    
    async def process(
        self,
        input_data: Union[str, bytes, Dict[str, Any]],
        options: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Process audio input based on model type.
        
        Args:
            input_data: Input data dict with keys like 'audio', 'text', 'filename'
            options: Additional options
            
        Returns:
            Result dictionary
        """
        options = options or {}
        model_type = self.config.model_type
        
        if model_type == "stt":
            return await self._transcribe(input_data, options)
        elif model_type == "tts":
            return await self._text_to_speech(input_data, options)
        else:
            raise ValueError(f"Unsupported model type: {model_type}")
    
    async def _transcribe(
        self,
        input_data: Dict[str, Any],
        options: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Perform speech-to-text using Mistral API.
        
        Mistral audio transcription uses the chat completions endpoint with input_audio content type.
        Documentation: https://platform-docs-public.pages.dev/capabilities/audio/
        
        Args:
            input_data: Dict with 'audio' (bytes) and 'filename'
            options: Options like language, diarization, timestamps
            
        Returns:
            Dict with 'text', 'language', 'duration', etc.
        """
        audio_bytes = input_data.get("audio")
        filename = input_data.get("filename", "input_audio")
        
        if not audio_bytes:
            raise ValueError("No audio data provided for transcription")
        
        # Encode audio as base64
        audio_base64 = base64.b64encode(audio_bytes).decode('utf-8')
        
        # Mistral uses chat completions endpoint for audio transcription
        # Send audio as input_audio content type in messages
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        
        # Build request body with audio as input_audio
        # Use the model alias/API model ID, not the display name
        model_name = self.config.name
        request_body = {
            "model": model_name,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_audio",
                            "input_audio": audio_base64,
                        }
                    ]
                }
            ],
            "stream": False,
        }
        
        # Add optional parameters if supported
        # Note: The chat completions API may not support all transcription options
        if "language" in options and options["language"]:
            request_body["language"] = options["language"]
        if "temperature" in options:
            request_body["temperature"] = options["temperature"]
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=request_body, headers=headers) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(f"Mistral STT API error: {response.status} - {error_text}")
                
                result = await response.json()
                
                # Extract text from chat response
                # The transcription is in choices[0].message.content
                text = ""
                if result.get("choices"):
                    text = result["choices"][0].get("message", {}).get("content", "")
                
                return {
                    "text": text,
                    "language": options.get("language"),
                    "duration": None,  # Duration not provided by this API
                    "chunks": None,
                }
    
    async def _text_to_speech(
        self,
        input_data: Dict[str, Any],
        options: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Generate speech using Mistral TTS API.
        
        API: POST /v1/audio/speech
        https://docs.mistral.ai/studio-api/audio/text_to_speech
        
        Args:
            input_data: Dict with 'text', 'voice_id', 'response_format'
            options: Additional options
            
        Returns:
            Dict with 'audio' (bytes), 'format', 'sample_rate'
        """
        text = input_data.get("text", "")
        voice_id = input_data.get("voice_id")
        response_format = input_data.get("format", "mp3")
        
        if not text:
            raise ValueError("No text provided for TTS")
        
        url = f"{self.base_url}{self.api_endpoint}"
        
        # Build request body
        request_data = {
            "model": self.config.name,
            "input": text,
            "response_format": response_format,
        }
        
        # Add voice if provided (for voice cloning)
        if voice_id:
            request_data["voice_id"] = voice_id
        
        # Add optional parameters
        if "speed" in options:
            request_data["speed"] = options["speed"]
        if "pitch" in options:
            request_data["pitch"] = options["pitch"]
        if "emotion" in options:
            request_data["emotion"] = options["emotion"]
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=request_data, headers=headers) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(f"Mistral TTS API error: {response.status} - {error_text}")
                
                result = await response.json()
                
                # Decode base64 audio data
                # Mistral returns "audio" field with base64-encoded MP3
                audio_data = result.get("audio", "")
                audio_bytes = base64.b64decode(audio_data) if audio_data else b""
                
                return {
                    "audio": audio_bytes,
                    "format": "mp3",  # Mistral TTS always returns MP3
                    "sample_rate": 24000,  # Mistral TTS uses 24kHz
                }
