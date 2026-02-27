#! /usr/bin/env python3
"""
Configuration Manager Module
Handles loading and managing application configuration
"""

import os
import tomllib
from typing import Dict, Any, Optional


class ConfigManager:
    """Manages application configuration from TOML files."""
    
    def __init__(self):
        self.config: Dict[str, Any] = {}
        self.default_model_alias: Optional[str] = None
        self.active_model_alias: Optional[str] = None
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
    
    def set_active_model(self, model_alias: str) -> None:
        """
        Set the active model alias.
        
        Args:
            model_alias: The alias of the model to set as active
            
        Raises:
            ValueError: If the model alias is not found
        """
        if model_alias not in self.config["models"]:
            raise ValueError(f"Model alias '{model_alias}' not found in configuration.")
        self.active_model_alias = model_alias
    
    def list_models(self) -> None:
        """
        List all available models with their details in a formatted table.
        """
        print("\nAvailable Models:")
        
        # Calculate column widths
        alias_width = max(len("Alias"), max(len(alias) for alias in self.config["models"]))
        name_width = max(len("Model Name"), max(len(config["name"]) for config in self.config["models"].values()))
        url_width = max(len("Base URL"), max(len(config.get("base_url", "Default OpenAI URL")) for config in self.config["models"].values()))
        
        # Print header
        header = "{'Alias':<{}} {'Model Name':<{}} {'Base URL':<{}} {'Temp':<6} {'MaxT':<6} {'TopP':<6} {'TopK':<6} {'FreqP':<6} {'PresP':<6}}".format(alias_width, name_width, url_width)
        print(header)
        print("-" * len(header))
        
        # Print models
        for alias, config in self.config["models"].items():
            base_url = config.get("base_url", "Default OpenAI URL")
            temp = config.get("temperature", 0.7)
            max_tokens = config.get("max_tokens", "Default")
            top_p = config.get("top_p", "Def")
            top_k = config.get("top_k", "Def")
            freq_p = config.get("frequency_penalty", "Def")
            pres_p = config.get("presence_penalty", "Def")
            print(f"{alias:<{alias_width}} {config['name']:<{name_width}} {base_url:<{url_width}} {temp:<6.2f} {str(max_tokens):<6} {str(top_p):<6} {str(top_k):<6} {str(freq_p):<6} {str(pres_p):<6}")
        
        print()
