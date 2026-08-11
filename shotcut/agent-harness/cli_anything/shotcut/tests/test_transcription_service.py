"""Unit tests for the dependency-injected transcription service."""

from pathlib import Path

import pytest

from cli_anything.shotcut.core.transcription.adapters.json_transcription_writer import (
    JsonTranscriptionWriter,
)
from cli_anything.shotcut.core.transcription.models import (
    ProviderTranscription,
    TranscriptSegment,
    TranscriptWord,
    TranscriptionRequest,
)
from cli_anything.shotcut.core.transcription.service import TranscriptionService


class FakeWorkspace:
    def __init__(self, directory: Path) -> None:
        self.video_path = directory / "source.mp4"
        self.audio_path = directory / "audio.mp3"
        self.cleaned = False

    def cleanup(self) -> None:
        self.cleaned = True


class FakeWorkspaceProvider:
    def __init__(self, workspace: FakeWorkspace) -> None:
        self.workspace = workspace

    def create(self) -> FakeWorkspace:
        return self.workspace


class FakeDownloader:
    def __init__(self) -> None:
        self.calls = []

    def download(self, source: str, destination: Path) -> Path:
        self.calls.append((source, destination))
        destination.write_bytes(b"video")
        return destination


class FakeAudioExtractor:
    def __init__(self) -> None:
        self.calls = []

    def extract(self, video_path: Path, audio_path: Path, playback_speed: float) -> Path:
        self.calls.append((video_path, audio_path, playback_speed))
        audio_path.write_bytes(b"audio")
        return audio_path


class FakeProvider:
    model = "fake-model"

    def __init__(self) -> None:
        self.calls = []

    def transcribe(self, audio_path: Path) -> ProviderTranscription:
        self.calls.append(audio_path)
        return ProviderTranscription(
            text="hello from the fake provider",
            segments=(TranscriptSegment(0.0, 2.0, "hello from the fake provider"),),
            words=(TranscriptWord("hello", 0.0, 0.5),),
            language="en",
        )


def make_service(tmp_path: Path):
    workspace = FakeWorkspace(tmp_path)
    downloader = FakeDownloader()
    extractor = FakeAudioExtractor()
    provider = FakeProvider()
    service = TranscriptionService(
        downloader=downloader,
        audio_extractor=extractor,
        provider=provider,
        workspace_provider=FakeWorkspaceProvider(workspace),
        writer=JsonTranscriptionWriter(),
    )
    return service, workspace, downloader, extractor, provider


def test_transcribes_local_video_at_cost_saving_speed(tmp_path):
    source = tmp_path / "video.mp4"
    source.write_bytes(b"video")
    service, workspace, downloader, extractor, provider = make_service(tmp_path)

    result = service.transcribe(TranscriptionRequest(source=str(source)))

    assert result.text == "hello from the fake provider"
    assert result.segments[0].end_seconds == 4.0
    assert result.words[0].start_seconds == 0.0
    assert result.words[0].end_seconds == 1.0
    assert result.transcript_path == (tmp_path / "video.transcript.json").resolve()
    assert result.transcript_path.is_file()
    assert downloader.calls == []
    assert extractor.calls[0][2] == 2.0
    assert provider.calls == [workspace.audio_path]
    assert workspace.cleaned is True


def test_downloads_remote_video_before_transcribing(tmp_path):
    service, workspace, downloader, extractor, provider = make_service(tmp_path)

    result = service.transcribe(
        TranscriptionRequest(
            source="https://example.test/video.mp4",
            playback_speed=1.5,
            output_path=tmp_path / "transcription.json",
        )
    )

    assert result.text == "hello from the fake provider"
    assert result.transcript_path == (tmp_path / "transcription.json").resolve()
    assert downloader.calls[0][0] == "https://example.test/video.mp4"
    assert extractor.calls[0][0] == workspace.video_path
    assert extractor.calls[0][2] == 1.5


def test_cleans_up_when_provider_fails(tmp_path):
    source = tmp_path / "video.mp4"
    source.write_bytes(b"video")
    service, workspace, downloader, extractor, _ = make_service(tmp_path)

    class FailingProvider:
        model = "failing-model"

        def transcribe(self, audio_path: Path) -> ProviderTranscription:
            raise RuntimeError("provider failed")

    service = TranscriptionService(
        downloader=downloader,
        audio_extractor=extractor,
        provider=FailingProvider(),
        workspace_provider=FakeWorkspaceProvider(workspace),
        writer=JsonTranscriptionWriter(),
    )

    with pytest.raises(RuntimeError, match="provider failed"):
        service.transcribe(TranscriptionRequest(source=str(source)))

    assert workspace.cleaned is True


def test_rejects_invalid_speed(tmp_path):
    service, _, _, _, _ = make_service(tmp_path)

    with pytest.raises(ValueError, match="between 0.5 and 2.0"):
        service.transcribe(
            TranscriptionRequest(source="video.mp4", playback_speed=2.1)
        )
