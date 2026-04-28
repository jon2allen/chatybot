#! /usr/bin/env python3
"""
OpenRouter Audio Provider
Handles OpenRouter audio APIs for STT and TTS.

OpenRouter STT: Uses /api/v1/chat/completions with input_audio content type
OpenRouter TTS: Uses /api/v1/audio/speech (compatible with OpenAI API)
"""

import aiohttp
import base64
import json
import textwrap
from typing import Any, Dict, Optional, Union
import os

from chatybot.audio_providers.base import AudioProvider
from chatybot.audio_provider import AudioModelConfig


class OpenRouterAudioProvider(AudioProvider):
    """
    Provider for OpenRouter audio APIs.
    
    OpenRouter routes to multiple LLM providers including audio models.
    STT uses chat/completions with input_audio, TTS uses audio/speech.
    """
    
    def __init__(self, config: AudioModelConfig):
        """Initialize the OpenRouter audio provider."""
        super().__init__(config)
        
        self.base_url = config.base_url or "https://openrouter.ai/api/v1"
        self.api_key = os.environ.get(config.api_key_env or "OPENROUTER_API_KEY")
        
        if not self.api_key:
            raise ValueError(f"OpenRouter API key not found. Set {config.api_key_env or 'OPENROUTER_API_KEY'} environment variable.")
        
        self.api_endpoint = config.api_endpoint or self._get_default_endpoint()
    
    def _get_default_endpoint(self) -> str:
        """Get default API endpoint based on model type."""
        if self.config.model_type == "stt":
            return "/chat/completions"
        elif self.config.model_type == "tts":
            return "/audio/speech"
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
        Perform speech-to-text using OpenRouter /api/v1/chat/completions endpoint.
        
        Uses JSON with base64-encoded audio in input_audio format.
        Format: {"model": "...", "messages": [{"role": "user", "content": [{"type": "input_audio", "input_audio": {"data": "...", "format": "..."}}]}]}
        
        Args:
            input_data: Dict with 'audio' (bytes) and 'filename'
            options: Options like temperature, max_tokens
            
        Returns:
            Dict with 'text'
        """
        audio_bytes = input_data.get("audio")
        filename = input_data.get("filename", "input_audio")
        
        if not audio_bytes:
            raise ValueError("No audio data provided for transcription")
        
        # Extract format from filename or default to mp3
        audio_format = filename.rsplit('.', 1)[-1].lower() if '.' in filename else "mp3"
        
        url = f"{self.base_url}{self.api_endpoint}"
        
        # Encode audio as base64
        audio_base64 = base64.b64encode(audio_bytes).decode('utf-8')
        
        # Build request payload for OpenRouter STT
        # Uses input_audio content type as per OpenRouter audio docs
        payload = {
            "model": self.config.name,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_audio",
                            "input_audio": {
                                "data": audio_base64,
                                "format": audio_format
                            }
                        }
                    ]
                }
            ]
        }
        
        # Add optional parameters
        if "temperature" in options:
            payload["temperature"] = options["temperature"]
        if "max_tokens" in options:
            payload["max_tokens"] = options["max_tokens"]
        if "language" in options:
            # Add as system message for language hint
            payload["messages"].insert(0, {
                "role": "system",
                "content": f"Transcribe the following audio. Language: {options['language']}"
            })
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=headers) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(f"OpenRouter STT API error {response.status}: {error_text}")
                
                result = await response.json()
                
                # Extract text from response
                # OpenRouter returns choices[].message.content for STT
                text = ""
                if "choices" in result and len(result["choices"]) > 0:
                    text = result["choices"][0]["message"].get("content", "")
                
                # Format to 80 chars per line for readability
                formatted_text = textwrap.fill(text, width=80)
                
                return {
                    "text": formatted_text,
                    "model": result.get("model"),
                    "usage": result.get("usage"),
                    "finish_reason": result.get("choices", [{}])[0].get("finish_reason"),
                }
    
    async def _text_to_speech(
        self,
        input_data: Dict[str, Any],
        options: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Generate speech using OpenRouter /api/v1/audio/speech endpoint.
        
        Compatible with OpenAI Audio Speech API format.
        
        Args:
            input_data: Dict with 'text', 'voice', 'response_format'
            options: Additional options like speed
            
        Returns:
            Dict with 'audio' (bytes), 'format'
        """
        text = input_data.get("text", "")
        voice = input_data.get("voice", options.get("voice", "alloy"))
        response_format = input_data.get("format", options.get("format", "mp3"))
        
        if not text:
            raise ValueError("No text provided for TTS")
        
        url = f"{self.base_url}{self.api_endpoint}"
        
        # Build request payload
        payload = {
            "model": self.config.name,
            "input": text,
            "voice": voice,
            "response_format": response_format,
        }
        
        # Add optional parameters
        if "speed" in options:
            payload["speed"] = options["speed"]
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=headers) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(f"OpenRouter TTS API error {response.status}: {error_text}")
                
                # TTS returns raw audio bytes
                audio_bytes = await response.read()
                
                return {
                    "audio": audio_bytes,
                    "format": response_format,
                    "voice": voice,
                    "model": self.config.name,
                }
