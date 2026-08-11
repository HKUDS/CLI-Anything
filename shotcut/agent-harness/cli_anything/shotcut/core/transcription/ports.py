"""Dependency-injection ports for transcription."""

from pathlib import Path
from typing import Protocol

from .models import ProviderTranscription, TranscriptionResult


class VideoDownloader(Protocol):
    def download(self, source: str, destination: Path) -> Path:
        """Download a remote video to destination."""


class AudioExtractor(Protocol):
    def extract(self, video_path: Path, audio_path: Path, playback_speed: float) -> Path:
        """Extract and optionally speed up audio from a video."""


class TranscriptionProvider(Protocol):
    model: str

    def transcribe(self, audio_path: Path) -> ProviderTranscription:
        """Return transcript text and provider timestamps for an audio file."""


class TranscriptionWriter(Protocol):
    def write(self, result: TranscriptionResult, output_path: Path) -> Path:
        """Persist a transcription artifact."""


class TranscriptionWorkspace(Protocol):
    video_path: Path
    audio_path: Path

    def cleanup(self) -> None:
        """Release temporary files."""


class TranscriptionWorkspaceProvider(Protocol):
    def create(self) -> TranscriptionWorkspace:
        """Create an isolated workspace for one transcription."""
