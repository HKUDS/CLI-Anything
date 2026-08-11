"""Text-to-speech application service."""

from pathlib import Path

from .models import TextToSpeechRequest, TextToSpeechResult
from .ports import TextToSpeechProvider


class TextToSpeechService:
    """Coordinate synthesis and persistence without knowing the provider."""

    def __init__(self, provider: TextToSpeechProvider) -> None:
        self._provider = provider

    def synthesize(self, request: TextToSpeechRequest) -> TextToSpeechResult:
        self._validate_request(request)
        audio = self._provider.synthesize(
            request.text,
            request.voice_id,
            request.model,
            request.output_format,
            request.voice_sample,
            request.language,
        )
        output_path = request.output_path.expanduser().resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(audio)
        return TextToSpeechResult(
            output_path=output_path,
            voice_id=request.voice_id,
            model=request.model,
            output_format=request.output_format,
            character_count=len(request.text),
        )

    @staticmethod
    def _validate_request(request: TextToSpeechRequest) -> None:
        if not request.text.strip():
            raise ValueError("Text-to-speech text cannot be empty")
        if not request.output_path.name:
            raise ValueError("Text-to-speech output path must include a filename")
