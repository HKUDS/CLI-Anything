"""Subtitle review — script drift checks and preview-frame rendering.

`synthesize.py` and `videocaptioner_cli.py` import this module, but it was
never committed (the root .gitignore allowlist did not include
`videocaptioner/`). Behaviour follows the existing contract in
`tests/test_core.py::TestReview`.
"""

from __future__ import annotations

import difflib
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

_TIMING_RE = re.compile(r"^\s*\d{1,2}:\d{2}:\d{2}[,.]\d{1,3}\s*-->")
_TAG_RE = re.compile(r"<[^>]+>|\{[^}]*\}")
_WORD_RE = re.compile(r"[\w']+", re.UNICODE)


def _read_text(path: str) -> str:
    return Path(path).read_text(encoding="utf-8-sig", errors="replace")


def extract_subtitle_text(subtitle_path: str) -> str:
    """Return the spoken text of an .srt/.vtt/.ass file as one string."""
    raw = _read_text(subtitle_path)
    lines: list[str] = []
    if subtitle_path.lower().endswith(".ass"):
        for line in raw.splitlines():
            if line.startswith("Dialogue:"):
                parts = line.split(",", 9)
                if len(parts) == 10:
                    lines.append(parts[9].replace("\\N", " ").replace("\\n", " "))
    else:
        for line in raw.splitlines():
            s = line.strip()
            if not s or s.isdigit() or s.upper() == "WEBVTT" or _TIMING_RE.match(s):
                continue
            lines.append(s)
    return _TAG_RE.sub("", " ".join(lines))


def _tokens(text: str) -> list[str]:
    return [w.lower() for w in _WORD_RE.findall(text)]


def diff_ratio(subtitle_text: str, script_text: str) -> float:
    """Normalized word-level drift: 0.0 identical, 1.0 completely different."""
    a, b = _tokens(subtitle_text), _tokens(script_text)
    if not a and not b:
        return 0.0
    return round(1.0 - difflib.SequenceMatcher(None, a, b, autojunk=False).ratio(), 4)


def build_review_report(
    subtitle_path: str,
    script_path: str | None = None,
    max_diff_ratio: float = 0.12,
) -> dict[str, Any]:
    if not os.path.exists(subtitle_path):
        raise FileNotFoundError(f"Subtitle file not found: {subtitle_path}")
    sub_text = extract_subtitle_text(subtitle_path)
    report: dict[str, Any] = {
        "subtitle_path": subtitle_path,
        "subtitle_words": len(_tokens(sub_text)),
        "status": "pass",
    }
    if script_path:
        if not os.path.exists(script_path):
            raise FileNotFoundError(f"Script file not found: {script_path}")
        ratio = diff_ratio(sub_text, _read_text(script_path))
        report.update(
            script_path=script_path,
            diff_ratio=ratio,
            max_diff_ratio=max_diff_ratio,
            status="pass" if ratio <= max_diff_ratio else "fail",
        )
    return report


def ensure_subtitle_consistency(
    subtitle_path: str, script_path: str, max_diff_ratio: float = 0.12
) -> dict[str, Any]:
    report = build_review_report(subtitle_path, script_path, max_diff_ratio)
    if report["status"] != "pass":
        raise RuntimeError(
            f"Subtitle/script review failed: diff_ratio={report['diff_ratio']} "
            f"exceeds max_diff_ratio={max_diff_ratio}"
        )
    return report


def _escape_filter_path(path: str) -> str:
    return path.replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")


def render_preview_frame(
    video_path: str,
    subtitle_path: str,
    at: str = "00:00:05.000",
    output_path: str | None = None,
) -> str:
    """Render one frame of the video with subtitles burned in (ffmpeg)."""
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("ffmpeg not found on PATH")
    if output_path is None:
        output_path = str(Path(video_path).with_suffix("")) + "_preview.png"
    cmd = [
        ffmpeg, "-y", "-loglevel", "error", "-ss", at, "-i", video_path,
        "-vf", f"subtitles='{_escape_filter_path(subtitle_path)}'",
        "-frames:v", "1", output_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg preview failed: {result.stderr.strip()}")
    return output_path


def review_subtitles(
    subtitle_path: str,
    script_path: str | None = None,
    max_diff_ratio: float = 0.12,
    preview_video: str | None = None,
    preview_at: str | None = None,
    preview_output: str | None = None,
) -> dict[str, Any]:
    report = build_review_report(subtitle_path, script_path, max_diff_ratio)
    if preview_video:
        report["preview_frame"] = render_preview_frame(
            preview_video, subtitle_path, at=preview_at or "00:00:05.000",
            output_path=preview_output,
        )
    return report
