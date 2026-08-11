"""CLI wiring tests for transcription."""

import json

from click.testing import CliRunner

from cli_anything.shotcut import shotcut_cli
from cli_anything.shotcut.core.transcription.models import TranscriptionResult


def test_media_transcribe_outputs_json(monkeypatch, tmp_path):
    source = tmp_path / "video.mp4"
    source.write_bytes(b"video")
    captured = {}

    class FakeService:
        def __init__(self, **dependencies):
            captured["dependencies"] = dependencies

        def transcribe(self, request):
            captured["request"] = request
            return TranscriptionResult(
                text="a transcript",
                source=request.source,
                model="fake-model",
                playback_speed=request.playback_speed,
            )

    monkeypatch.setattr(shotcut_cli, "TranscriptionService", FakeService)
    monkeypatch.setenv("MISTRAL_API_KEY", "test-key")

    result = CliRunner().invoke(
        shotcut_cli.cli,
        ["--json", "media", "transcribe", str(source)],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["text"] == "a transcript"
    assert captured["request"].playback_speed == 2.0
    assert captured["request"].source == str(source)
