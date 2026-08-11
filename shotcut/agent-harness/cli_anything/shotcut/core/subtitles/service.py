"""Subtitle generation and rendering application service."""

import json
import tempfile
from pathlib import Path

from ..transcription.models import TranscriptSegment
from .models import SubtitleDocument, SubtitleRequest, SubtitleResult
from .ports import SubtitleRenderer


class SubtitleService:
    """Read timestamped transcript segments and burn them into a video."""

    def __init__(self, renderer: SubtitleRenderer) -> None:
        self._renderer = renderer

    def add_subtitles(self, request: SubtitleRequest) -> SubtitleResult:
        video_path = self._existing_file(request.video_path, "Video")
        transcript_path = self._existing_file(request.transcript_path, "Transcript")
        document = self._load_document(transcript_path)
        output_path = request.output_path.expanduser().resolve()
        if output_path.exists() and not request.overwrite:
            raise FileExistsError(f"Output file already exists: {output_path}")
        if not output_path.parent.is_dir():
            raise FileNotFoundError(f"Output directory not found: {output_path.parent}")

        with tempfile.TemporaryDirectory(prefix="shotcut-subtitles-") as directory:
            ass_path = Path(directory) / "subtitles.ass"
            ass_path.write_text(self._to_ass(document), encoding="utf-8")
            self._renderer.render(video_path, ass_path, output_path, request.overwrite)

        return SubtitleResult(video_path, transcript_path, output_path, len(document.segments))

    @staticmethod
    def _existing_file(path: Path, label: str) -> Path:
        resolved = path.expanduser().resolve()
        if not resolved.is_file():
            raise FileNotFoundError(f"{label} file not found: {resolved}")
        return resolved

    @classmethod
    def _load_document(cls, path: Path) -> SubtitleDocument:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as error:
            raise ValueError(f"Invalid transcript JSON: {path}") from error
        segments = []
        for index, item in enumerate(payload.get("segments", [])):
            try:
                start = float(item["start_seconds"])
                end = float(item["end_seconds"])
                text = str(item["text"]).strip()
            except (KeyError, TypeError, ValueError) as error:
                raise ValueError(f"Invalid transcript segment at index {index}") from error
            if start < 0 or end <= start or not text:
                raise ValueError(f"Invalid transcript segment at index {index}")
            segments.append(TranscriptSegment(start, end, text))
        if not segments:
            raise ValueError(f"Transcript contains no subtitle segments: {path}")
        return SubtitleDocument(tuple(segments))

    @classmethod
    def _to_ass(cls, document: SubtitleDocument) -> str:
        lines = [
            "[Script Info]",
            "ScriptType: v4.00+",
            "PlayResX: 1920",
            "PlayResY: 1080",
            "ScaledBorderAndShadow: yes",
            "",
            "[V4+ Styles]",
            "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
            "Style: Default,Arial,64,&H00FFFFFF,&H00FFFFFF,&H00000000,&H99000000,-1,0,0,0,100,100,0,0,1,3,1,2,80,80,100,1",
            "",
            "[Events]",
            "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
        ]
        lines.extend(
            f"Dialogue: 0,{cls._time(segment.start_seconds)},{cls._time(segment.end_seconds)},Default,,0,0,0,,{cls._escape(segment.text)}"
            for segment in document.segments
        )
        return "\n".join(lines) + "\n"

    @staticmethod
    def _time(seconds: float) -> str:
        total_centiseconds = round(seconds * 100)
        hours, remainder = divmod(total_centiseconds, 360000)
        minutes, remainder = divmod(remainder, 6000)
        whole_seconds, centiseconds = divmod(remainder, 100)
        return f"{hours}:{minutes:02d}:{whole_seconds:02d}.{centiseconds:02d}"

    @staticmethod
    def _escape(text: str) -> str:
        return text.replace("\\", r"\\").replace("{", r"\{").replace("}", r"\}").replace("\n", r"\N")
