#! /usr/bin/env python3
"""
Audio Provider Module
Base interface and registry for all audio providers (STT, TTS, Music, SFX)
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Any, Optional, List, Tuple, Union
import json
import os


class AudioCapability(Enum):
    """Audio processing capabilities."""
    STT = "stt"                  # Speech-to-Text
    TTS = "tts"                  # Text-to-Speech
    VOICE_CLONING = "voice_cloning"  # Zero-shot voice cloning
    MUSIC_GENERATION = "music_generation"
    SFX_GENERATION = "sfx_generation"
    SOUND_RECOGNITION = "sound_recognition"
    VOICE_RECOGNITION = "voice_recognition"
    SPEAKER_DIARIZATION = "speaker_diarization"
    REALTIME = "realtime"        # Real-time streaming
    MULTILINGUAL = "multilingual"


class AudioFormat(Enum):
    """Supported audio formats."""
    MP3 = "mp3"
    WAV = "wav"
    FLAC = "flac"
    OGG = "ogg"
    M4A = "m4a"
    WEBM = "webm"
    OPUS = "opus"
    AAC = "aac"
    PCM = "pcm"


class AudioType(Enum):
    """Audio content types."""
    SPEECH = "speech"
    MUSIC = "music"
    SFX = "sfx"
    AMBIENT = "ambient"


@dataclass
class AudioModelConfig:
    """Configuration for an audio model."""
    name: str
    provider: str
    model_type: str  # "stt", "tts", "music", "sfx", "recognition"
    description: str = ""
    huggingface_id: Optional[str] = None
    api_endpoint: Optional[str] = None
    api_key_env: Optional[str] = None
    base_url: Optional[str] = None
    requires_api_key: bool = True
    license: str = "proprietary"
    
    # Capabilities
    capabilities: List[AudioCapability] = field(default_factory=list)
    
    # STT-specific
    max_audio_length: Optional[float] = None  # in minutes
    max_file_size: Optional[int] = None  # in bytes
    supported_formats: List[AudioFormat] = field(default_factory=list)
    languages: List[str] = field(default_factory=list)
    
    # TTS-specific
    voices: List[str] = field(default_factory=list)
    supports_voice_cloning: bool = False
    cloning_min_audio: Optional[float] = None  # in seconds
    cloning_max_audio: Optional[float] = None  # in seconds
    
    # Resource requirements (local models)
    parameters: Optional[int] = None  # in millions
    vram_bf16: Optional[str] = None
    vram_int8: Optional[str] = None
    vram_int4: Optional[str] = None
    
    # Pricing (cloud models)
    pricing_per_1k_chars: Optional[float] = None  # for TTS
    pricing_per_minute: Optional[float] = None  # for STT
    
    # Default settings
    is_default: bool = False


class AudioProvider(ABC):
    """Abstract base class for all audio providers."""
    
    def __init__(self, config: AudioModelConfig):
        """
        Initialize the audio provider.
        
        Args:
            config: Model configuration
        """
        self.config = config
        self.provider_name = config.provider
        self.model_name = config.name
        self.model_type = config.model_type
        
    @abstractmethod
    async def process(
        self,
        input_data: Union[str, bytes, Dict[str, Any]],
        options: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Process audio input and return output.
        
        Args:
            input_data: Input data (file path, text prompt, or audio bytes)
            options: Provider-specific options
            
        Returns:
            Dictionary containing:
            - For STT: {"text": "...", "language": "...", "duration": X.X, ...}
            - For TTS: {"audio": bytes, "format": "mp3", "sample_rate": 44100, ...}
            - For generation: {"audio": bytes, "format": "...", ...}
        """
        pass
    
    def get_capabilities(self) -> List[AudioCapability]:
        """Get the capabilities of this provider."""
        return self.config.capabilities
    
    def has_capability(self, capability: AudioCapability) -> bool:
        """Check if provider has a specific capability."""
        return capability in self.get_capabilities()
    
    def get_info(self) -> Dict[str, Any]:
        """Get provider information."""
        return {
            "provider": self.provider_name,
            "model": self.model_name,
            "type": self.model_type,
            "capabilities": [c.value for c in self.get_capabilities()],
            "description": self.config.description,
            "requires_api_key": self.config.requires_api_key,
        }


class AudioModelRegistry:
    """Registry for all available audio models."""
    
    def __init__(self):
        self.models: Dict[str, AudioModelConfig] = {}
        self.providers: Dict[str, Dict[str, AudioModelConfig]] = {}
        self._initialized = False
        
    def initialize(self, config: Dict[str, Any]) -> None:
        """
        Initialize the registry from chat_config.toml audio section.
        
        Args:
            config: The full configuration dictionary from chat_config.toml
        """
        if self._initialized:
            return
            
        audio_config = config.get("audio", {})
        models_config = audio_config.get("models", {})
        
        for model_alias, model_settings in models_config.items():
            model = self._create_model_config(model_alias, model_settings)
            self.models[model_alias] = model
            
            # Group by provider
            if model.provider not in self.providers:
                self.providers[model.provider] = {}
            self.providers[model.provider][model_alias] = model
            
        self._initialized = True
        
    def _create_model_config(self, alias: str, settings: Dict[str, Any]) -> AudioModelConfig:
        """Create an AudioModelConfig from TOML settings."""
        capabilities = []
        if "capabilities" in settings:
            for cap in settings["capabilities"]:
                try:
                    capabilities.append(AudioCapability[cap.upper()])
                except KeyError:
                    pass  # Ignore unknown capabilities
        
        supported_formats = []
        if "supported_formats" in settings:
            for fmt in settings["supported_formats"]:
                try:
                    supported_formats.append(AudioFormat[fmt.upper()])
                except KeyError:
                    pass
        
        return AudioModelConfig(
            name=settings.get("name", alias),
            provider=settings.get("provider", "unknown"),
            model_type=settings.get("type", "unknown"),
            description=settings.get("description", ""),
            huggingface_id=settings.get("huggingface_id"),
            api_endpoint=settings.get("api_endpoint"),
            api_key_env=settings.get("api_key_env"),
            base_url=settings.get("base_url"),
            requires_api_key=settings.get("requires_api_key", True),
            license=settings.get("license", "proprietary"),
            capabilities=capabilities,
            max_audio_length=settings.get("max_audio_length"),
            max_file_size=settings.get("max_file_size"),
            supported_formats=supported_formats,
            languages=settings.get("languages", []),
            voices=settings.get("voices", []),
            supports_voice_cloning=settings.get("supports_voice_cloning", False),
            cloning_min_audio=settings.get("cloning_min_audio"),
            cloning_max_audio=settings.get("cloning_max_audio"),
            parameters=settings.get("parameters"),
            vram_bf16=settings.get("vram_bf16"),
            vram_int8=settings.get("vram_int8"),
            vram_int4=settings.get("vram_int4"),
            pricing_per_1k_chars=settings.get("pricing_per_1k_chars"),
            pricing_per_minute=settings.get("pricing_per_minute"),
            is_default=settings.get("is_default", False),
        )
    
    def get_model(self, alias: str) -> Optional[AudioModelConfig]:
        """Get a model configuration by alias."""
        return self.models.get(alias)
    
    def list_models(
        self,
        model_type: Optional[str] = None,
        provider: Optional[str] = None,
        capability: Optional[AudioCapability] = None
    ) -> List[Dict[str, Any]]:
        """
        List available models with optional filtering.
        
        Args:
            model_type: Filter by model type (stt, tts, etc.)
            provider: Filter by provider
            capability: Filter by capability
            
        Returns:
            List of model info dictionaries
        """
        results = []
        for alias, config in self.models.items():
            if model_type and config.model_type != model_type:
                continue
            if provider and config.provider != provider:
                continue
            if capability and capability not in config.capabilities:
                continue
            results.append({
                "alias": alias,
                "name": config.name,
                "provider": config.provider,
                "type": config.model_type,
                "description": config.description,
                "capabilities": [c.value for c in config.capabilities],
                "requires_api_key": config.requires_api_key,
                "is_default": config.is_default,
            })
        return results
    
    def get_default_model(self, model_type: str) -> Optional[AudioModelConfig]:
        """Get the default model for a given type."""
        for alias, config in self.models.items():
            if config.model_type == model_type and config.is_default:
                return config
        
        # Fallback: return first model of the type
        for alias, config in self.models.items():
            if config.model_type == model_type:
                return config
        return None
    
    def get_capabilities(self) -> Dict[str, Any]:
        """Get a summary of all available capabilities."""
        capabilities = {
            "stt": {
                "available": False,
                "models": [],
                "realtime": False,
                "multilingual": False,
                "diarization": False,
            },
            "tts": {
                "available": False,
                "models": [],
                "voice_cloning": False,
                "multilingual": False,
            },
            "music": {
                "available": False,
                "models": [],
            },
            "sfx": {
                "available": False,
                "models": [],
            },
            "recognition": {
                "available": False,
                "models": [],
                "sound_recognition": False,
                "voice_recognition": False,
            },
        }
        
        for alias, config in self.models.items():
            for cap in config.capabilities:
                cap_str = cap.value
                if cap_str in capabilities:
                    capabilities[cap_str]["available"] = True
                    if alias not in capabilities[cap_str]["models"]:
                        capabilities[cap_str]["models"].append(alias)
                
                # Check for specific features
                if cap == AudioCapability.REALTIME:
                    capabilities["stt"]["realtime"] = True
                if cap == AudioCapability.MULTILINGUAL:
                    if config.model_type == "stt":
                        capabilities["stt"]["multilingual"] = True
                    if config.model_type == "tts":
                        capabilities["tts"]["multilingual"] = True
                if cap == AudioCapability.SPEAKER_DIARIZATION:
                    capabilities["stt"]["diarization"] = True
                if cap == AudioCapability.VOICE_CLONING:
                    capabilities["tts"]["voice_cloning"] = True
        
        return capabilities


# Global registry instance
audio_model_registry = AudioModelRegistry()
