"""Framework-neutral text-to-speech models."""

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class TextToSpeechRequest:
    """Input accepted by the text-to-speech use case."""

    text: str
    voice_id: str | None
    output_path: Path
    model: str = "eleven_multilingual_v2"
    output_format: str = "mp3_44100_128"
    voice_sample: Path | None = None
    language: str = "en"


@dataclass(frozen=True)
class TextToSpeechResult:
    """Provider-independent text-to-speech response."""

    output_path: Path
    voice_id: str | None
    model: str
    output_format: str
    character_count: int

    def to_dict(self) -> dict[str, object]:
        return {
            "output_path": str(self.output_path),
            "voice_id": self.voice_id,
            "model": self.model,
            "output_format": self.output_format,
            "character_count": self.character_count,
        }
