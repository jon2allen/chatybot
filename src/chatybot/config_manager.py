#! /usr/bin/env python3
"""
Configuration Manager Module
Handles loading and managing application configuration
"""

import os
import tomllib
from typing import Dict, Any, Optional, List


class ConfigManager:
    """Manages application configuration from TOML files."""
    
    def __init__(self):
        self.config: Dict[str, Any] = {}
        self.default_model_alias: Optional[str] = None
        self.active_model_alias: Optional[str] = None
        self.active_model_type: Optional[str] = None  # 'text' or 'audio'
        self.system_message: str = "You are a helpful assistant."
        self.max_tokens: Optional[int] = None
        self.top_p: Optional[float] = None
        self.top_k: Optional[int] = None
        self.freq_penalty: Optional[float] = None
        self.pres_penalty: Optional[float] = None
    
    def load_config(self) -> None:
        """
        Load the configuration from chat_config.toml.
        """
        config_path = os.path.expanduser("~/.config/chatybot/chat_config.toml")
        
        # Create the config directory if it doesn't exist
        os.makedirs(os.path.dirname(config_path), exist_ok=True)
        
        # Check if config exists in ~/.config, otherwise try local and copy
        if not os.path.exists(config_path):
            local_config = os.path.join(os.path.dirname(__file__), "chat_config.toml")
            if os.path.exists(local_config):
                import shutil
                shutil.copy2(local_config, config_path)
                print(f"Copied local '{local_config}' to '{config_path}'")
            else:
                raise FileNotFoundError(f"Configuration file not found. Please create '{config_path}'.")
        
        try:
            with open(config_path, "rb") as f:
                self.config = tomllib.load(f)
        except tomllib.TOMLDecodeError:
            raise ValueError(f"Invalid TOML format in '{config_path}'.")
        
        # Set the default model alias to the first model in the config
        self.default_model_alias = next(iter(self.config["models"]))
        self.active_model_alias = self.default_model_alias
        self.active_model_type = "text"  # Default to text model type
        
        # Load system message if specified in config
        if "system_message" in self.config:
            self.system_message = self.config["system_message"]
        
        # Load max tokens if specified in config
        if "max_tokens" in self.config:
            self.max_tokens = self.config["max_tokens"]
        
        # Load other parameters if specified in config
        if "top_p" in self.config:
            self.top_p = self.config["top_p"]
        if "top_k" in self.config:
            self.top_k = self.config["top_k"]
        if "frequency_penalty" in self.config:
            self.freq_penalty = self.config["frequency_penalty"]
        if "presence_penalty" in self.config:
            self.pres_penalty = self.config["presence_penalty"]
        
        # Image generation settings
        self.image_dir = os.path.expanduser("~/chatybot_images")
        self.image_size = "1024x1024"
        self.image_quality = "standard"
        
        if "image_generation" in self.config:
            image_config = self.config["image_generation"]
            if "default_dir" in image_config:
                self.image_dir = os.path.expanduser(image_config["default_dir"])
            if "default_size" in image_config:
                self.image_size = image_config["default_size"]
            if "default_quality" in image_config:
                self.image_quality = image_config["default_quality"]
        
        # Audio settings
        self.audio_dir = os.path.expanduser("~/chatybot_audio")
        self.audio_format = "mp3"
        self.audio_stt_model = None
        self.audio_tts_model = None
        
        # Load audio config if available
        if "audio" in self.config:
            audio_config = self.config["audio"]
            if "default_dir" in audio_config:
                self.audio_dir = os.path.expanduser(audio_config["default_dir"])
            if "default_format" in audio_config:
                self.audio_format = audio_config["default_format"]
            if "default_stt_model" in audio_config:
                self.audio_stt_model = audio_config["default_stt_model"]
            if "default_tts_model" in audio_config:
                self.audio_tts_model = audio_config["default_tts_model"]
    
    def get_model_config(self, model_alias: str) -> Dict[str, Any]:
        """
        Get configuration for a specific model.
        
        Args:
            model_alias: The alias of the model to get configuration for
            
        Returns:
            Dictionary containing the model configuration
            
        Raises:
            ValueError: If the model alias is not found
        """
        model_config = self.config["models"].get(model_alias)
        if not model_config:
            raise ValueError(f"Model alias '{model_alias}' not found in configuration.")
        return model_config
    
    def set_active_model(self, model_alias: str, model_type: Optional[str] = None) -> None:
        """
        Set the active model alias and type.
        
        Args:
            model_alias: The alias of the model to set as active
            model_type: The type of model ('text' or 'audio')
            
        Raises:
            ValueError: If the model alias is not found
        """
        # Only validate text models (audio models are validated separately)
        if model_type == "text" or model_type is None:
            model_config = self.config["models"].get(model_alias)
            if not model_config:
                raise ValueError(f"Model alias '{model_alias}' not found in configuration.")
        self.active_model_alias = model_alias
        self.active_model_type = model_type
    
    def list_models(self, include_audio: bool = True) -> None:
        """
        List all available models with their details in a formatted table.
        
        Args:
            include_audio: Whether to include audio models in the listing
        """
        print("\nAvailable Models:")
        
        # Calculate column widths for text models
        alias_width = max(len("Alias"), max(len(alias) for alias in self.config["models"]))
        name_width = max(len("Model Name"), max(len(config["name"]) for config in self.config["models"].values()))
        url_width = max(len("Base URL"), max(len(config.get("base_url", "Default OpenAI URL")) for config in self.config["models"].values()))
        
        # Print header for text models
        header = f"{'Alias':<{alias_width}} {'Model Name':<{name_width}} {'Base URL':<{url_width}} {'Temp':<6} {'MaxT':<6} {'TopP':<6} {'TopK':<6} {'FreqP':<6} {'PresP':<6}"
        print(header)
        print("-" * len(header))
        
        # Print text models
        for alias, config in self.config["models"].items():
            base_url = config.get("base_url", "Default OpenAI URL")
            temp = config.get("temperature", 0.7)
            max_tokens = config.get("max_tokens", "Default")
            top_p = config.get("top_p", "Def")
            top_k = config.get("top_k", "Def")
            freq_p = config.get("frequency_penalty", "Def")
            pres_p = config.get("presence_penalty", "Def")
            print(f"{alias:<{alias_width}} {config['name']:<{name_width}} {base_url:<{url_width}} {temp:<6.2f} {str(max_tokens):<6} {str(top_p):<6} {str(top_k):<6} {str(freq_p):<6} {str(pres_p):<6}")
        
        # Print audio models if requested and available
        if include_audio and "audio" in self.config and "models" in self.config["audio"]:
            audio_models = self.config["audio"]["models"]
            if audio_models:
                print(f"\nAudio Models ({len(audio_models)}):")
                a_alias_width = max(len("Alias"), max(len(alias) for alias in audio_models)) if audio_models else 10
                a_name_width = max(len("Model Name"), max(len(m.get("name", "")) for m in audio_models.values())) if audio_models else 20
                a_type_width = max(len("Type"), max(len(m.get("type", "")) for m in audio_models.values())) if audio_models else 10
                a_provider_width = max(len("Provider"), max(len(m.get("provider", "")) for m in audio_models.values())) if audio_models else 15
                
                a_header = f"{'Alias':<{a_alias_width}} {'Model Name':<{a_name_width}} {'Type':<{a_type_width}} {'Provider':<{a_provider_width}} {'License':<12}"
                print(a_header)
                print("-" * len(a_header))
                
                for alias, config in audio_models.items():
                    name = config.get("name", alias)
                    model_type = config.get("type", "unknown")
                    provider = config.get("provider", "unknown")
                    license_val = config.get("license", "unknown")
                    print(f"{alias:<{a_alias_width}} {name:<{a_name_width}} {model_type:<{a_type_width}} {provider:<{a_provider_width}} {license_val:<12}")
        
        print()
    
    def list_image_capable_models(self) -> List[str]:
        """
        List all models that support image generation.
        
        Returns:
            List of model aliases that have image_generation enabled
        """
        image_models = []
        for alias, config in self.config.get("models", {}).items():
            if config.get("image_generation", False):
                image_models.append(alias)
        return image_models
    
    def get_image_config(self) -> Dict[str, Any]:
        """
        Get image generation configuration.
        
        Returns:
            Dictionary with image generation settings
        """
        return self.config.get("image_generation", {})
    
    def get_audio_config(self) -> Dict[str, Any]:
        """
        Get audio configuration.
        
        Returns:
            Dictionary with audio settings
        """
        return self.config.get("audio", {})
    
    def get_audio_models_config(self) -> Dict[str, Any]:
        """
        Get audio models configuration.
        
        Returns:
            Dictionary of audio models from config
        """
        audio_config = self.get_audio_config()
        return audio_config.get("models", {})
