#! /usr/bin/env python3
"""
OpenAI Audio Provider
Handles OpenAI STT (gpt-4o-transcribe, whisper-1) and TTS (gpt-4o-mini-tts, tts-1-hd)
"""

import aiohttp
from typing import Any, Dict, Optional, Union
import os

from chatybot.audio_providers.base import AudioProvider
from chatybot.audio_provider import AudioModelConfig


class OpenAIAudioProvider(AudioProvider):
    """
    Provider for OpenAI audio APIs (STT and TTS).
    """
    
    def __init__(self, config: AudioModelConfig):
        """Initialize the OpenAI audio provider."""
        super().__init__(config)
        
        # OpenAI-specific settings
        self.base_url = config.base_url or "https://api.openai.com/v1"
        self.api_key = os.environ.get(config.api_key_env or "OPENAI_API_KEY")
        
        if not self.api_key:
            raise ValueError(f"OpenAI API key not found. Set {config.api_key_env or 'OPENAI_API_KEY'} environment variable.")
    
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
        Perform speech-to-text using OpenAI API.
        
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
        
        url = f"{self.base_url}/audio/transcriptions"
        
        # Build request
        form_data = aiohttp.FormData()
        form_data.add_field("file", audio_bytes, filename=filename, content_type="application/octet-stream")
        form_data.add_field("model", self.config.name)
        
        # Add optional parameters
        if "language" in options and options["language"]:
            form_data.add_field("language", options["language"])
        if "prompt" in options and options["prompt"]:
            form_data.add_field("prompt", options["prompt"])
        if "temperature" in options:
            form_data.add_field("temperature", str(options["temperature"]))
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, data=form_data, headers=headers) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(f"OpenAI STT API error: {response.status} - {error_text}")
                
                result = await response.json()
                
                return {
                    "text": result.get("text", ""),
                    "language": options.get("language"),
                    "duration": None,  # Not provided by OpenAI
                }
    
    async def _text_to_speech(
        self,
        input_data: Dict[str, Any],
        options: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Generate speech using OpenAI TTS API.
        
        Args:
            input_data: Dict with 'text', 'voice', 'speed', 'format'
            options: Additional options
            
        Returns:
            Dict with 'audio' (bytes), 'format', 'sample_rate'
        """
        text = input_data.get("text", "")
        voice = input_data.get("voice", "alloy")
        speed = input_data.get("speed", 1.0)
        output_format = input_data.get("format", "mp3")
        
        if not text:
            raise ValueError("No text provided for TTS")
        
        url = f"{self.base_url}/audio/speech"
        
        request_data = {
            "model": self.config.name,
            "input": text,
            "voice": voice,
            "response_format": output_format,
        }
        
        # Add optional parameters
        if speed != 1.0:
            request_data["speed"] = speed
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=request_data, headers=headers) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(f"OpenAI TTS API error: {response.status} - {error_text}")
                
                audio_bytes = await response.read()
                
                return {
                    "audio": audio_bytes,
                    "format": output_format,
                    "sample_rate": 24000 if output_format in ["mp3", "opus", "aac", "flac"] else 16000,
                    "duration": None,  # Would need to calculate from text
                }
