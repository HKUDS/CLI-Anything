"""Models for rendering timed subtitles onto a video."""

from dataclasses import dataclass
from pathlib import Path

from ..transcription.models import TranscriptSegment, TranscriptWord


@dataclass(frozen=True)
class SubtitleRequest:
    video_path: Path
    transcript_path: Path
    output_path: Path
    overwrite: bool = False


@dataclass(frozen=True)
class SubtitleResult:
    video_path: Path
    transcript_path: Path
    output_path: Path
    subtitle_count: int

    def to_dict(self) -> dict[str, object]:
        return {
            "video_path": str(self.video_path),
            "transcript_path": str(self.transcript_path),
            "output_path": str(self.output_path),
            "subtitle_count": self.subtitle_count,
        }


@dataclass(frozen=True)
class SubtitleDocument:
    segments: tuple[TranscriptSegment, ...]
    words: tuple[TranscriptWord, ...] = ()
