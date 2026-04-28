#! /usr/bin/env python3
"""
Base Audio Provider
Abstract base for all audio provider implementations
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Union
import aiohttp

from chatybot.audio_provider import AudioModelConfig, AudioProvider as BaseAudioProvider


class AudioProvider(BaseAudioProvider):
    """
    Base class for audio providers.
    Extends the abstract base from audio_provider module.
    """
    
    def __init__(self, config: AudioModelConfig):
        """
        Initialize the audio provider.
        
        Args:
            config: Model configuration
        """
        super().__init__(config)
        self.session: Optional[aiohttp.ClientSession] = None
        self.api_key: Optional[str] = None
        
        # Load API key from environment if configured
        if config.api_key_env and config.requires_api_key:
            import os
            self.api_key = os.environ.get(config.api_key_env)
    
    async def get_session(self) -> aiohttp.ClientSession:
        """Get or create an aiohttp session."""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()
        return self.session
    
    async def close(self) -> None:
        """Close the session."""
        if self.session and not self.session.closed:
            await self.session.close()
            self.session = None
    
    @abstractmethod
    async def process(
        self,
        input_data: Union[str, bytes, Dict[str, Any]],
        options: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Process audio input and return output.
        Must be implemented by subclasses.
        
        Args:
            input_data: Input data (file path, text prompt, or audio bytes)
            options: Provider-specific options
            
        Returns:
            Dictionary with results
        """
        pass
    
    def _get_api_key(self) -> Optional[str]:
        """
        Get the API key, trying multiple sources.
        
        Returns:
            API key string or None
        """
        return self.api_key
    
    def _get_headers(self) -> Dict[str, str]:
        """
        Get default headers for API requests.
        
        Returns:
            Dictionary of headers
        """
        headers = {
            "Content-Type": "application/json",
        }
        
        # Add Authorization header if API key is available
        api_key = self._get_api_key()
        if api_key:
            # Different providers use different header formats
            if self.config.provider == "openai":
                headers["Authorization"] = f"Bearer {api_key}"
            elif self.config.provider == "mistralai":
                headers["Authorization"] = f"Bearer {api_key}"
            elif self.config.provider == "stability":
                headers["Authorization"] = f"Bearer {api_key}"
            else:
                headers["Authorization"] = f"Bearer {api_key}"
        
        return headers
