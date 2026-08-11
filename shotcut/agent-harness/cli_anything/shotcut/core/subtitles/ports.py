"""Dependency-injection ports for subtitle rendering."""

from pathlib import Path
from typing import Protocol


class SubtitleRenderer(Protocol):
    def render(self, video_path: Path, ass_path: Path, output_path: Path, overwrite: bool) -> None:
        """Burn an ASS subtitle file into a video."""
