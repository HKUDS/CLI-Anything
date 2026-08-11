"""ffmpeg-based audio extraction adapter."""

import shutil
import subprocess
from pathlib import Path


class FfmpegAudioExtractor:
    def __init__(self, executable: str | None = None, timeout_seconds: float = 300.0) -> None:
        self._executable = executable or shutil.which("ffmpeg")
        self._timeout_seconds = timeout_seconds
        if self._executable is None:
            raise FileNotFoundError("ffmpeg is required for transcription")

    def extract(self, video_path: Path, audio_path: Path, playback_speed: float) -> Path:
        result = subprocess.run(
            [
                self._executable,
                "-y",
                "-i",
                str(video_path),
                "-vn",
                "-af",
                f"atempo={playback_speed:g}",
                "-acodec",
                "libmp3lame",
                str(audio_path),
            ],
            capture_output=True,
            text=True,
            timeout=self._timeout_seconds,
        )
        if result.returncode != 0:
            detail = result.stderr.strip() or "ffmpeg failed to extract audio"
            raise RuntimeError(detail)
        return audio_path
