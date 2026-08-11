"""Framework-neutral transcription models."""

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class TranscriptSegment:
    start_seconds: float
    end_seconds: float
    text: str
    score: float | None = None
    speaker_id: str | None = None

    def to_dict(self) -> dict[str, object]:
        result: dict[str, object] = {
            "start_seconds": self.start_seconds,
            "end_seconds": self.end_seconds,
            "text": self.text,
        }
        if self.score is not None:
            result["score"] = self.score
        if self.speaker_id is not None:
            result["speaker_id"] = self.speaker_id
        return result


@dataclass(frozen=True)
class ProviderTranscription:
    text: str
    segments: tuple[TranscriptSegment, ...] = ()
    language: str | None = None


@dataclass(frozen=True)
class TranscriptionRequest:
    """Input accepted by the transcription use case."""

    source: str
    playback_speed: float = 2.0
    output_path: Path | None = None


@dataclass(frozen=True)
class TranscriptionResult:
    """Provider-independent transcription response."""

    text: str
    source: str
    model: str
    playback_speed: float
    segments: tuple[TranscriptSegment, ...] = ()
    language: str | None = None
    transcript_path: Path | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "text": self.text,
            "source": self.source,
            "model": self.model,
            "playback_speed": self.playback_speed,
            "language": self.language,
            "segments": [segment.to_dict() for segment in self.segments],
        }
        if self.transcript_path is not None:
            result["transcript_path"] = str(self.transcript_path)
        return result
