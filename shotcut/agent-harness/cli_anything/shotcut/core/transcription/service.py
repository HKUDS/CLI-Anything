"""Transcription application service."""

from pathlib import Path
from dataclasses import replace

from .models import TranscriptSegment, TranscriptionRequest, TranscriptionResult
from .ports import (
    AudioExtractor,
    TranscriptionProvider,
    TranscriptionWorkspaceProvider,
    TranscriptionWriter,
    VideoDownloader,
)


class TranscriptionService:
    """Coordinate source acquisition, audio preparation, and transcription."""

    def __init__(
        self,
        downloader: VideoDownloader,
        audio_extractor: AudioExtractor,
        provider: TranscriptionProvider,
        workspace_provider: TranscriptionWorkspaceProvider,
        writer: TranscriptionWriter,
    ) -> None:
        self._downloader = downloader
        self._audio_extractor = audio_extractor
        self._provider = provider
        self._workspace_provider = workspace_provider
        self._writer = writer

    def transcribe(self, request: TranscriptionRequest) -> TranscriptionResult:
        self._validate_request(request)
        workspace = self._workspace_provider.create()

        try:
            video_path = self._resolve_video(request.source, workspace.video_path)
            self._audio_extractor.extract(
                video_path,
                workspace.audio_path,
                request.playback_speed,
            )
            provider_result = self._provider.transcribe(workspace.audio_path)
            result = TranscriptionResult(
                text=provider_result.text,
                source=request.source,
                model=self._provider.model,
                playback_speed=request.playback_speed,
                segments=self._restore_video_timestamps(
                    provider_result.segments,
                    request.playback_speed,
                ),
                language=provider_result.language,
            )
            transcript_path = request.output_path or self._default_output_path(
                request.source, video_path
            )
            written_path = self._writer.write(result, transcript_path)
            return replace(result, transcript_path=written_path)
        finally:
            workspace.cleanup()

    def _resolve_video(self, source: str, destination: Path) -> Path:
        if source.startswith(("http://", "https://")):
            return self._downloader.download(source, destination)

        video_path = Path(source).expanduser().resolve()
        if not video_path.is_file():
            raise FileNotFoundError(f"Video file not found: {video_path}")
        return video_path

    @staticmethod
    def _default_output_path(source: str, video_path: Path) -> Path:
        if source.startswith(("http://", "https://")):
            return Path.cwd() / "transcription.json"
        return video_path.with_suffix(".transcript.json")

    @staticmethod
    def _restore_video_timestamps(
        segments: tuple[TranscriptSegment, ...], playback_speed: float
    ) -> tuple[TranscriptSegment, ...]:
        return tuple(
            TranscriptSegment(
                start_seconds=segment.start_seconds / playback_speed,
                end_seconds=segment.end_seconds / playback_speed,
                text=segment.text,
                score=segment.score,
                speaker_id=segment.speaker_id,
            )
            for segment in segments
        )

    @staticmethod
    def _validate_request(request: TranscriptionRequest) -> None:
        if not request.source.strip():
            raise ValueError("Transcription source cannot be empty")
        if not 0.5 <= request.playback_speed <= 2.0:
            raise ValueError("Playback speed must be between 0.5 and 2.0")
