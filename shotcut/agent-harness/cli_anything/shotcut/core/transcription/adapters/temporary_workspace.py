"""Temporary workspace adapter."""

import shutil
import tempfile
from pathlib import Path


class TemporaryWorkspace:
    def __init__(self, directory: Path) -> None:
        self._directory = directory
        self.video_path = directory / "source.mp4"
        self.audio_path = directory / "transcription.mp3"

    def cleanup(self) -> None:
        shutil.rmtree(self._directory, ignore_errors=True)


class TemporaryWorkspaceProvider:
    def create(self) -> TemporaryWorkspace:
        directory = Path(tempfile.mkdtemp(prefix="shotcut-transcription-"))
        return TemporaryWorkspace(directory)
