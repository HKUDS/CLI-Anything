"""Real ffmpeg/ffprobe integration for the platform-independent probe command.

Requires ffmpeg and ffprobe on PATH. No macOS hardware encoder or standalone
quietshrink compressor is used: fixtures are tiny, synthetic FFV1 videos.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


def _resolve_cli() -> list[str]:
    installed = shutil.which("cli-anything-quietshrink")
    if installed:
        return [installed]
    if os.environ.get("CLI_ANYTHING_FORCE_INSTALLED") == "1":
        pytest.fail("Install the quietshrink harness and add its executable to PATH")
    return [sys.executable, "-m", "cli_anything.quietshrink.quietshrink_cli"]


@pytest.mark.parametrize(
    ("audio_codec", "audio_first"),
    [("pcm_s16le", True), ("flac", True), ("pcm_s16le", False)],
)
def test_probe_finds_video_regardless_of_audio_codec_and_stream_order(
    tmp_path: Path, audio_codec: str, audio_first: bool,
) -> None:
    ffmpeg = shutil.which("ffmpeg")
    ffprobe = shutil.which("ffprobe")
    assert ffmpeg and ffprobe, "Install ffmpeg (including ffprobe) to run probe E2E tests"
    sample = tmp_path / "audio-video.mkv"
    streams = ["0:a:0", "1:v:0"] if audio_first else ["1:v:0", "0:a:0"]
    generated = subprocess.run(
        [ffmpeg, "-v", "error", "-f", "lavfi", "-i", "anullsrc=r=8000:cl=mono",
         "-f", "lavfi", "-i", "color=c=black:s=32x24:r=5",
         "-map", streams[0], "-map", streams[1], "-t", "0.4",
         "-c:a", audio_codec, "-c:v", "ffv1", "-threads", "1", str(sample)],
        capture_output=True, text=True, timeout=30,
    )
    assert generated.returncode == 0, generated.stderr
    # Confirm the fixture actually exercises the requested stream order.
    raw = subprocess.run(
        [ffprobe, "-v", "error", "-show_entries", "stream=codec_type",
         "-of", "json", str(sample)],
        capture_output=True, text=True, timeout=10, check=True,
    )
    assert json.loads(raw.stdout)["streams"][0]["codec_type"] == (
        "audio" if audio_first else "video"
    )

    result = subprocess.run(
        [*_resolve_cli(), "probe", str(sample), "--json"],
        capture_output=True, text=True, timeout=10,
    )
    assert result.returncode == 0, result.stderr
    metadata = json.loads(result.stdout)
    assert metadata["codec"] == "ffv1"
    assert metadata["width"] == 32
    assert metadata["height"] == 24
    assert metadata["framerate"] not in (None, "0/0")
    assert 0 < metadata["duration_seconds"] < 1
    assert metadata["size_bytes"] == sample.stat().st_size
