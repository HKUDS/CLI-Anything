"""Unit tests for the dependency-injected text-to-speech service."""

from pathlib import Path

import pytest

from cli_anything.shotcut.core.text_to_speech.models import TextToSpeechRequest
from cli_anything.shotcut.core.text_to_speech.service import TextToSpeechService


class FakeProvider:
    def __init__(self) -> None:
        self.calls = []

    def synthesize(self, text, voice_id, model, output_format, voice_sample, language):
        self.calls.append(
            (text, voice_id, model, output_format, voice_sample, language)
        )
        return b"fake audio"


def test_synthesizes_and_writes_audio(tmp_path: Path):
    provider = FakeProvider()
    service = TextToSpeechService(provider)
    output_path = tmp_path / "nested" / "speech.mp3"

    result = service.synthesize(
        TextToSpeechRequest(
            text="Hello from a test",
            voice_id="voice123",
            output_path=output_path,
        )
    )

    assert result.output_path == output_path.resolve()
    assert result.character_count == len("Hello from a test")
    assert output_path.read_bytes() == b"fake audio"
    assert provider.calls == [
        (
            "Hello from a test",
            "voice123",
            "eleven_multilingual_v2",
            "mp3_44100_128",
            None,
            "en",
        )
    ]


def test_rejects_empty_text(tmp_path: Path):
    service = TextToSpeechService(FakeProvider())

    with pytest.raises(ValueError, match="cannot be empty"):
        service.synthesize(
            TextToSpeechRequest(
                text=" ",
                voice_id="voice123",
                output_path=tmp_path / "speech.mp3",
            )
        )
