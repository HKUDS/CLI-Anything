"""Text-to-speech provider adapters."""

from .elevenlabs_provider import ElevenLabsTextToSpeech
from .xtts_provider import XTTSVoiceProvider

__all__ = ["ElevenLabsTextToSpeech", "XTTSVoiceProvider"]
