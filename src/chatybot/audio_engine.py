#! /usr/bin/env python3
"""
Audio Engine Module
Main orchestrator for all audio operations (STT, TTS, Music, SFX)
"""

import asyncio
import base64
import json
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from chatybot.audio_provider import (
    AudioCapability,
    AudioFormat,
    AudioModelConfig,
    AudioModelRegistry,
    AudioProvider,
    AudioType,
    audio_model_registry,
)
from chatybot.audio_file_manager import AudioFileManager


@dataclass
class AudioResult:
    """Result from an audio operation."""
    success: bool
    file_path: Optional[str] = None
    base64_data: Optional[str] = None
    text: Optional[str] = None
    audio_bytes: Optional[bytes] = None
    format: Optional[str] = None
    model: Optional[str] = None
    provider: Optional[str] = None
    duration: Optional[float] = None
    language: Optional[str] = None
    error: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class AudioEngine:
    """
    Main orchestrator for audio operations.
    Manages providers, file storage, and command execution.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None, config_manager: Any = None):
        """
        Initialize the AudioEngine.
        
        Args:
            config: Configuration dictionary from chat_config.toml
            config_manager: Reference to ConfigManager
        """
        self.config = config or {}
        self.config_manager = config_manager
        
        # Initialize components
        self.file_manager = AudioFileManager(config_manager=config_manager)
        self.registry = audio_model_registry
        
        # Set up audio directory from config
        audio_config = self.config.get("audio", {})
        audio_dir = audio_config.get("default_dir", "~/chatybot_audio")
        self.file_manager.set_directory(audio_dir)
        
        # State
        self.current_model_alias: Optional[str] = None
        self.current_provider: Optional[AudioProvider] = None
        self.last_result: Optional[AudioResult] = None
        self.last_generated_audio: Optional[Tuple[str, str]] = None  # (file_path, base64)
        self.last_transcription: Optional[str] = None
        
        # Initialize registry with config
        if self.config:
            self.registry.initialize(self.config)
        
        # Provider instances cache
        self._provider_cache: Dict[str, AudioProvider] = {}
        
        # Load default models
        self._load_default_models()
    
    def _load_default_models(self) -> None:
        """Load default model settings from config."""
        audio_config = self.config.get("audio", {})
        
        # Set default STT model if configured
        default_stt = audio_config.get("default_stt_model")
        if default_stt and self.registry.get_model(default_stt):
            self.set_model(default_stt)
    
    def set_model(self, model_alias: str) -> bool:
        """
        Set the active audio model by alias.
        
        Args:
            model_alias: The model alias from config
            
        Returns:
            True if model was set successfully, False otherwise
        """
        model_config = self.registry.get_model(model_alias)
        if not model_config:
            print(f"Error: Model '{model_alias}' not found.")
            return False
        
        self.current_model_alias = model_alias
        
        # Clear cached provider for this model type
        if model_config.model_type in self._provider_cache:
            del self._provider_cache[model_config.model_type]
        
        print(f"Audio model set to: {model_alias} ({model_config.name})")
        return True
    
    def get_current_model(self) -> Optional[AudioModelConfig]:
        """Get the current model configuration."""
        if not self.current_model_alias:
            return None
        return self.registry.get_model(self.current_model_alias)
    
    def _get_provider(self, model_type: str) -> Optional[AudioProvider]:
        """
        Get a provider instance for the given model type.
        Uses cached instance or creates a new one.
        
        Args:
            model_type: The type of provider needed (stt, tts, etc.)
            
        Returns:
            AudioProvider instance or None
        """
        # Get current model
        current_model = self.get_current_model()
        if not current_model:
            # Try to get default model for this type
            current_model = self.registry.get_default_model(model_type)
        
        if not current_model:
            return None
        
        # Check cache
        cache_key = f"{current_model.provider}_{current_model.name}"
        if cache_key in self._provider_cache:
            return self._provider_cache[cache_key]
        
        # Create provider instance based on type
        provider = self._create_provider(current_model)
        if provider:
            self._provider_cache[cache_key] = provider
        
        return provider
    
    def _create_provider(self, model_config: AudioModelConfig) -> Optional[AudioProvider]:
        """
        Create a provider instance from model config.
        This will be extended with specific provider implementations.
        
        Args:
            model_config: The model configuration
            
        Returns:
            AudioProvider instance or None if not supported
        """
        # This base implementation returns None
        # Specific providers (OpenAI, Mistral, Voxtral, etc.) will be implemented separately
        try:
            if model_config.provider == "openai":
                from .audio_providers.openai_provider import OpenAIAudioProvider
                return OpenAIAudioProvider(model_config)
            elif model_config.provider == "mistralai":
                # Check if it's an API model (requires API key) or local model (has huggingface_id)
                if model_config.requires_api_key:
                    from .audio_providers.mistral_provider import MistralAudioProvider
                    return MistralAudioProvider(model_config)
                else:
                    # Local Mistral model (HuggingFace)
                    from .audio_providers.local_provider import LocalAudioProvider
                    return LocalAudioProvider(model_config)
            elif model_config.provider == "openrouter":
                # OpenRouter models (routes to various providers)
                from .audio_providers.openrouter_provider import OpenRouterAudioProvider
                return OpenRouterAudioProvider(model_config)
            elif model_config.provider == "local" or model_config.huggingface_id:
                # Local models (HuggingFace) - use local provider
                from .audio_providers.local_provider import LocalAudioProvider
                return LocalAudioProvider(model_config)
        except ImportError as e:
            print(f"Warning: Could not import provider for {model_config.provider}: {e}")
        
        return None
    
    async def transcribe(
        self,
        audio_input: Union[str, bytes],
        model_alias: Optional[str] = None,
        language: Optional[str] = None,
        diarization: bool = False,
        timestamps: bool = False,
        **kwargs
    ) -> AudioResult:
        """
        Perform speech-to-text transcription.
        
        Args:
            audio_input: File path or audio bytes
            model_alias: Specific model to use (overrides current)
            language: Language hint
            diarization: Enable speaker diarization
            timestamps: Include word-level timestamps
            **kwargs: Additional provider-specific options
            
        Returns:
            AudioResult with transcription text and metadata
        """
        result = AudioResult(success=False)
        
        try:
            # Set model if specified
            if model_alias:
                self.set_model(model_alias)
            
            current_model = self.get_current_model()
            if not current_model:
                current_model = self.registry.get_default_model("stt")
            
            if not current_model:
                result.error = "No STT model available. Please configure an STT model."
                return result
            
            # Create provider
            provider = self._create_provider(current_model)
            if not provider:
                result.error = f"No provider available for model: {current_model.name}"
                return result
            
            # Prepare input
            if isinstance(audio_input, str) and os.path.exists(audio_input):
                # File path - load it
                with open(audio_input, "rb") as f:
                    audio_bytes = f.read()
                input_data = {
                    "audio": audio_bytes,
                    "filename": os.path.basename(audio_input),
                }
            elif isinstance(audio_input, bytes):
                input_data = {"audio": audio_input, "filename": "input_audio"}
            else:
                input_data = {"audio_file": audio_input}  # Assume it's a file path
            
            # Add options
            options = {
                "language": language,
                "diarization": diarization,
                "timestamps": timestamps,
                **kwargs
            }
            
            # Process with provider
            provider_result = await provider.process(input_data, options)
            
            # Extract results
            result.success = True
            result.text = provider_result.get("text", "")
            result.model = current_model.name
            result.provider = current_model.provider
            result.language = provider_result.get("language")
            result.duration = provider_result.get("duration")
            result.metadata = {
                "speakers": provider_result.get("speakers"),
                "word_timestamps": provider_result.get("word_timestamps"),
                "diarization": diarization,
            }
            
            # Save transcription to file
            input_filename = input_data.get("filename", "unknown")
            file_path = self.file_manager.save_transcription(
                text=result.text or "",
                input_file=input_filename,
                model=current_model.name,
                provider=current_model.provider,
                language=result.language,
                duration=result.duration,
                speakers=provider_result.get("speakers"),
                word_timestamps=provider_result.get("word_timestamps"),
                diarization=diarization
            )
            result.file_path = file_path
            
            # Store last transcription
            self.last_transcription = result.text
            self.last_result = result
            
        except Exception as e:
            result.error = f"Transcription error: {str(e)}"
            print(f"Error during transcription: {str(e)}")
        
        return result
    
    async def text_to_speech(
        self,
        text: str,
        model_alias: Optional[str] = None,
        voice: Optional[str] = None,
        speed: float = 1.0,
        pitch: float = 1.0,
        reference_audio: Optional[Union[str, bytes]] = None,
        output_format: str = "mp3",
        **kwargs
    ) -> AudioResult:
        """
        Generate speech from text (TTS).
        
        Args:
            text: Text to synthesize
            model_alias: Specific model to use (overrides current)
            voice: Voice name/ID
            speed: Speech speed multiplier
            pitch: Pitch multiplier
            reference_audio: Reference audio for voice cloning
            output_format: Output format (mp3, wav, etc.)
            **kwargs: Additional provider-specific options
            
        Returns:
            AudioResult with audio file path and base64 data
        """
        result = AudioResult(success=False)
        
        try:
            if not text or text.strip() == "":
                result.error = "Text cannot be empty"
                return result
            
            # Set model if specified
            if model_alias:
                self.set_model(model_alias)
            
            current_model = self.get_current_model()
            if not current_model:
                current_model = self.registry.get_default_model("tts")
            
            if not current_model:
                result.error = "No TTS model available. Please configure a TTS model."
                return result
            
            # Check if model supports TTS
            if AudioCapability.TTS not in current_model.capabilities:
                result.error = f"Model '{current_model.name}' does not support TTS"
                return result
            
            # Create provider
            provider = self._create_provider(current_model)
            if not provider:
                result.error = f"No provider available for model: {current_model.name}"
                return result
            
            # Prepare input
            input_data = {
                "text": text,
                "voice": voice,
                "speed": speed,
                "pitch": pitch,
                "format": output_format,
            }
            
            # Handle voice cloning
            if reference_audio:
                if current_model.supports_voice_cloning:
                    if isinstance(reference_audio, str) and os.path.exists(reference_audio):
                        with open(reference_audio, "rb") as f:
                            ref_bytes = f.read()
                        input_data["reference_audio"] = ref_bytes
                    elif isinstance(reference_audio, bytes):
                        input_data["reference_audio"] = reference_audio
            
            # Add additional kwargs
            input_data.update(kwargs)
            
            # Process with provider
            provider_result = await provider.process(input_data)
            
            # Extract results
            audio_bytes = provider_result.get("audio")
            if not audio_bytes:
                result.error = "No audio generated"
                return result
            
            result.success = True
            result.audio_bytes = audio_bytes
            result.text = text
            result.model = current_model.name
            result.provider = current_model.provider
            result.format = provider_result.get("format", output_format)
            result.duration = provider_result.get("duration")
            result.sample_rate = provider_result.get("sample_rate", 44100)
            
            # Save to file
            file_path, base64_data = self.file_manager.save_audio_file(
                audio_bytes=audio_bytes,
                category="generate",
                subtype="speech",
                format=result.format or output_format,
                prompt=text[:100],  # Store first 100 chars of prompt
                model=current_model.name,
                provider=current_model.provider,
                sample_rate=result.sample_rate or 44100,
                duration=result.duration,
                extra_metadata={
                    "voice": voice,
                    "speed": speed,
                    "pitch": pitch,
                }
            )
            
            result.file_path = file_path
            result.base64_data = base64_data
            
            # Store last generated
            self.last_generated_audio = (file_path, base64_data)
            self.last_result = result
            
        except Exception as e:
            result.error = f"TTS error: {str(e)}"
            print(f"Error during TTS: {str(e)}")
        
        return result
    
    async def generate_audio(
        self,
        prompt: str,
        audio_type: str = "sfx",
        model_alias: Optional[str] = None,
        duration: Optional[float] = None,
        output_format: str = "mp3",
        **kwargs
    ) -> AudioResult:
        """
        Generate audio (music or sound effects) from a text prompt.
        
        Args:
            prompt: Text description of the audio to generate
            audio_type: Type of audio (sfx, music, ambient)
            model_alias: Specific model to use
            duration: Duration in seconds
            output_format: Output format
            **kwargs: Additional options
            
        Returns:
            AudioResult with generated audio
        """
        result = AudioResult(success=False)
        
        try:
            if not prompt or prompt.strip() == "":
                result.error = "Prompt cannot be empty"
                return result
            
            # Set model if specified
            if model_alias:
                self.set_model(model_alias)
            
            # Determine model type based on audio type
            model_type_map = {
                "sfx": "sfx",
                "sound": "sfx",
                "music": "music",
                "ambient": "music",
            }
            target_type = model_type_map.get(audio_type, "sfx")
            
            current_model = self.get_current_model()
            if not current_model:
                current_model = self.registry.get_default_model(target_type)
            
            if not current_model:
                result.error = f"No {target_type} generation model available"
                return result
            
            # Create provider
            provider = self._create_provider(current_model)
            if not provider:
                result.error = f"No provider available for model: {current_model.name}"
                return result
            
            # Prepare input
            input_data = {
                "prompt": prompt,
                "type": audio_type,
                "duration": duration,
                "format": output_format,
            }
            input_data.update(kwargs)
            
            # Process with provider
            provider_result = await provider.process(input_data)
            
            # Extract results
            audio_bytes = provider_result.get("audio")
            if not audio_bytes:
                result.error = "No audio generated"
                return result
            
            result.success = True
            result.audio_bytes = audio_bytes
            result.model = current_model.name
            result.provider = current_model.provider
            result.format = provider_result.get("format", output_format)
            result.duration = provider_result.get("duration")
            result.sample_rate = provider_result.get("sample_rate", 44100)
            
            # Determine subtype for file naming
            subtype = self.file_manager.SUBTYPE_MAP.get(audio_type, audio_type)
            
            # Save to file
            file_path, base64_data = self.file_manager.save_audio_file(
                audio_bytes=audio_bytes,
                category="generate",
                subtype=subtype,
                format=result.format or output_format,
                prompt=prompt,
                model=current_model.name,
                provider=current_model.provider,
                duration=result.duration,
                extra_metadata={
                    "type": audio_type,
                }
            )
            
            result.file_path = file_path
            result.base64_data = base64_data
            
            # Store last generated
            self.last_generated_audio = (file_path, base64_data)
            self.last_result = result
            
        except Exception as e:
            result.error = f"Audio generation error: {str(e)}"
            print(f"Error during audio generation: {str(e)}")
        
        return result
    
    async def recognize_sound(
        self,
        audio_input: Union[str, bytes],
        model_alias: Optional[str] = None,
        detection_type: str = "environmental",
        **kwargs
    ) -> AudioResult:
        """
        Perform sound recognition on an audio file.
        
        Args:
            audio_input: File path or audio bytes
            model_alias: Specific model to use
            detection_type: Type of detection (environmental, music, speech)
            **kwargs: Additional options
            
        Returns:
            AudioResult with recognition results
        """
        result = AudioResult(success=False)
        
        try:
            # Set model if specified
            if model_alias:
                self.set_model(model_alias)
            
            current_model = self.get_current_model()
            if not current_model:
                current_model = self.registry.get_default_model("recognition")
            
            if not current_model:
                result.error = "No sound recognition model available"
                return result
            
            # Create provider
            provider = self._create_provider(current_model)
            if not provider:
                result.error = f"No provider available for model: {current_model.name}"
                return result
            
            # Prepare input
            if isinstance(audio_input, str) and os.path.exists(audio_input):
                with open(audio_input, "rb") as f:
                    audio_bytes = f.read()
                input_data = {"audio": audio_bytes, "filename": os.path.basename(audio_input)}
            elif isinstance(audio_input, bytes):
                input_data = {"audio": audio_input, "filename": "input_audio"}
            else:
                input_data = {"audio_file": audio_input}
            
            input_data["detection_type"] = detection_type
            input_data.update(kwargs)
            
            # Process with provider
            provider_result = await provider.process(input_data)
            
            # Extract results
            sounds = provider_result.get("sounds", [])
            categories = provider_result.get("categories", {})
            
            result.success = True
            result.metadata = {
                "sounds": sounds,
                "categories": categories,
                "detection_type": detection_type,
            }
            result.model = current_model.name
            result.provider = current_model.provider
            result.duration = provider_result.get("duration")
            
            # Save recognition to file
            input_filename = input_data.get("filename", "unknown")
            file_path = self.file_manager.save_recognition(
                sounds=sounds,
                categories=categories,
                input_file=input_filename,
                model=current_model.name,
                provider=current_model.provider,
                detection_type=detection_type,
                duration=result.duration
            )
            result.file_path = file_path
            self.last_result = result
            
        except Exception as e:
            result.error = f"Sound recognition error: {str(e)}"
            print(f"Error during sound recognition: {str(e)}")
        
        return result
    
    async def audialize(
        self,
        action: str,
        content: str,
        options: Optional[Dict[str, Any]] = None
    ) -> AudioResult:
        """
        Unified audialize command handler.
        Routes to the appropriate operation based on the action.
        
        Args:
            action: Action type (speak, transcribe, generate, sfx, music, recognize, analyze)
            content: Content (text prompt or file path)
            options: Additional options
            
        Returns:
            AudioResult from the operation
        """
        options = options or {}
        action_lower = action.lower()
        
        # Determine action from aliases
        action_map = {
            "speak": "tts",
            "tts": "tts",
            "say": "tts",
            "transcribe": "stt",
            "stt": "stt",
            "to_text": "stt",
            "generate": "generate",
            "sfx": "generate",
            "sound": "generate",
            "effect": "generate",
            "music": "generate",
            "song": "generate",
            "compose": "generate",
            "recognize": "recognize",
            "analyze": "recognize",
            "classify": "recognize",
            "identify": "recognize",
            "detect": "recognize",
            "describe": "recognize",
        }
        
        target_action = action_map.get(action_lower, action_lower)
        
        if target_action == "tts":
            return await self.text_to_speech(content, **options)
        elif target_action == "stt":
            return await self.transcribe(content, **options)
        elif target_action == "generate":
            audio_type = "sfx"
            if action_lower in ("music", "song", "compose"):
                audio_type = "music"
            return await self.generate_audio(content, audio_type=audio_type, **options)
        elif target_action == "recognize":
            return await self.recognize_sound(content, **options)
        else:
            # Default behavior based on content
            if os.path.exists(content):
                # Assume it's an audio file to analyze
                return await self.recognize_sound(content, **options)
            else:
                # Assume it's a prompt to generate
                return await self.generate_audio(content, audio_type="sfx", **options)
    
    def list_audio_files(
        self,
        date_filter: Optional[str] = None,
        category_filter: Optional[str] = None,
        subtype_filter: Optional[str] = None,
        format_filter: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        List audio files with optional filtering.
        
        Args:
            date_filter: Filter by date
            category_filter: Filter by category
            subtype_filter: Filter by subtype
            format_filter: Filter by format
            
        Returns:
            List of file metadata dictionaries
        """
        return self.file_manager.list_files(
            date_filter=date_filter,
            category_filter=category_filter,
            subtype_filter=subtype_filter,
            format_filter=format_filter
        )
    
    def set_audio_directory(self, path: str) -> None:
        """Set the audio output directory."""
        self.file_manager.set_directory(path)
        # Update config if we have access
        if self.config_manager and hasattr(self.config_manager, 'audio_dir'):
            self.config_manager.audio_dir = path
    
    def get_capabilities(self) -> Dict[str, Any]:
        """Get audio capabilities summary."""
        return self.registry.get_capabilities()
    
    def list_models(
        self,
        model_type: Optional[str] = None,
        provider: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        List available audio models with optional filtering.
        
        Args:
            model_type: Filter by model type
            provider: Filter by provider
            
        Returns:
            List of model info dictionaries
        """
        return self.registry.list_models(model_type=model_type, provider=provider)
    
    def get_model_info(self, model_alias: str) -> Optional[Dict[str, Any]]:
        """Get detailed information about a specific model."""
        model_config = self.registry.get_model(model_alias)
        if not model_config:
            return None
        
        return {
            "alias": model_alias,
            "name": model_config.name,
            "provider": model_config.provider,
            "type": model_config.model_type,
            "description": model_config.description,
            "capabilities": [c.value for c in model_config.capabilities],
            "requires_api_key": model_config.requires_api_key,
            "license": model_config.license,
            "voices": model_config.voices,
            "languages": model_config.languages,
            "supports_voice_cloning": model_config.supports_voice_cloning,
            "cloning_min_audio": model_config.cloning_min_audio,
            "cloning_max_audio": model_config.cloning_max_audio,
            "max_audio_length": model_config.max_audio_length,
            "max_file_size": model_config.max_file_size,
            "supported_formats": [f.value for f in model_config.supported_formats],
            "vram_bf16": model_config.vram_bf16,
            "vram_int8": model_config.vram_int8,
            "vram_int4": model_config.vram_int4,
            "parameters": model_config.parameters,
            "pricing_per_1k_chars": model_config.pricing_per_1k_chars,
            "pricing_per_minute": model_config.pricing_per_minute,
        }


# Global engine instance
audio_engine: Optional[AudioEngine] = None


def get_audio_engine(config: Optional[Dict[str, Any]] = None, config_manager: Any = None) -> AudioEngine:
    """Get or create the global audio engine instance."""
    global audio_engine
    if audio_engine is None:
        audio_engine = AudioEngine(config, config_manager)
    return audio_engine
