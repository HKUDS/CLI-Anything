"""ffmpeg subtitle renderer."""

import shutil
import subprocess
from pathlib import Path


class FfmpegSubtitleRenderer:
    """Burn ASS subtitles into a video using ffmpeg's subtitles filter."""

    def __init__(self, executable: str | None = None) -> None:
        self._executable = executable or shutil.which("ffmpeg") or "ffmpeg"

    def render(self, video_path: Path, ass_path: Path, output_path: Path, overwrite: bool) -> None:
        command = [self._executable, "-y" if overwrite else "-n", "-i", str(video_path), "-vf", f"subtitles={ass_path}", "-c:a", "copy", str(output_path)]
        completed = subprocess.run(command, capture_output=True, text=True)
        if completed.returncode != 0:
            detail = completed.stderr.strip() or "ffmpeg failed"
            raise RuntimeError(detail)
