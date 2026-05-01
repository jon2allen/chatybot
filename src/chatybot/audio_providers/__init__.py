# Audio Providers Package
# Contains implementations for different audio providers (OpenAI, Mistral, Local, etc.)

from .base import AudioProvider
from .mistral_provider import MistralAudioProvider
from .openai_provider import OpenAIAudioProvider
from .local_provider import LocalAudioProvider
from .openrouter_provider import OpenRouterAudioProvider

__all__ = ["AudioProvider", "MistralAudioProvider", "OpenAIAudioProvider", "LocalAudioProvider", "OpenRouterAudioProvider"]
