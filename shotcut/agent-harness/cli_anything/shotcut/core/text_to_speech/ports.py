"""Dependency-injection ports for text-to-speech."""

from pathlib import Path
from typing import Protocol


class TextToSpeechProvider(Protocol):
    def synthesize(
        self,
        text: str,
        voice_id: str | None,
        model: str,
        output_format: str,
        voice_sample: Path | None,
        language: str,
    ) -> bytes:
        """Return synthesized audio bytes."""
