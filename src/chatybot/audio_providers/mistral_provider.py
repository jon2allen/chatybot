#! /usr/bin/env python3
"""
Mistral Audio Provider
Handles Mistral Voxtral STT and TTS via API
"""

import aiohttp
import base64
import json
import struct
import subprocess
import tempfile
import textwrap
from typing import Any, Dict, Optional, Union
import os

from chatybot.audio_providers.base import AudioProvider
from chatybot.audio_provider import AudioModelConfig


class MistralAudioProvider(AudioProvider):
    """
    Provider for Mistral audio APIs (Voxtral STT and TTS).

    STT uses the dedicated /v1/audio/transcriptions endpoint with raw binary upload.
    TTS uses /v1/audio/speech with JSON.
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
        Perform speech-to-text using Mistral /v1/audio/transcriptions endpoint.
        
        Sends as multipart/form-data with 'file' and 'model' fields.
        Pattern: -F model="voxtral-mini-latest" -F file=@file.mp3
        
        Args:
            input_data: Dict with 'audio' (bytes) and 'filename'
            options: Options like language, diarize, timestamp_granularities
            
        Returns:
            Dict with 'text', 'language', 'duration'
        """
        audio_bytes = input_data.get("audio")
        filename = input_data.get("filename", "input_audio")
        
        if not audio_bytes:
            raise ValueError("No audio data provided for transcription")
        
        url = f"{self.base_url}{self.api_endpoint}"
        
        model_name = self.config.name
        
        # Build multipart form data (Mistral requires this format)
        form_data = aiohttp.FormData()
        form_data.add_field('file', audio_bytes, filename=filename)
        form_data.add_field('model', model_name)
        
        # Add optional parameters
        if "language" in options and options["language"]:
            form_data.add_field('language', options["language"])
        if "diarize" in options:
            form_data.add_field('diarize', str(options["diarize"]).lower())
        if "timestamp_granularities" in options:
            granularities = options["timestamp_granularities"]
            if isinstance(granularities, list):
                for g in granularities:
                    form_data.add_field('timestamp_granularities[]', g)
            else:
                form_data.add_field('timestamp_granularities[]', granularities)
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            # No Content-Type header - aiohttp.FormData sets it automatically
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, data=form_data, headers=headers) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(f"Mistral STT API error: {response.status} - {error_text}")
                
                result = await response.json()
                text = result.get("text", "")
                
                # Format to 80 chars per line for easy reading
                formatted_text = textwrap.fill(text, width=80)
                
                return {
                    "text": formatted_text,
                    "language": result.get("language"),
                    "duration": result.get("duration"),
                    "chunks": 1,
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
                audio_data = result.get("audio", "")
                audio_bytes = base64.b64decode(audio_data) if audio_data else b""
                
                return {
                    "audio": audio_bytes,
                    "format": "mp3",  # Mistral TTS always returns MP3
                    "sample_rate": 24000,  # Mistral TTS uses 24kHz
                }
