"""Subtitle/script review — drift check and preview-frame rendering.

This module backs the ``review`` CLI command and the ``review_script`` drift
check in :mod:`cli_anything.videocaptioner.core.synthesize`. It compares the
text extracted from a subtitle file against a reference script/transcript and
reports how far the two have drifted apart.
"""

from __future__ import annotations

import difflib
import re
import shutil
import subprocess

__all__ = [
    "build_review_report",
    "ensure_subtitle_consistency",
    "render_preview_frame",
    "review_subtitles",
]

TIMESTAMP_RE = re.compile(r"-->")
INDEX_RE = re.compile(r"^\d+$")
WORD_RE = re.compile(r"\w+")


def extract_subtitle_text(subtitle_path: str) -> str:
    """Extract spoken text from a subtitle file (.srt/.vtt), ignoring cue indices and timestamps."""
    texts: list[str] = []
    with open(subtitle_path, encoding="utf-8") as fh:
        for raw_line in fh:
            line = raw_line.strip()
            if not line:
                continue
            if INDEX_RE.match(line):
                continue
            if TIMESTAMP_RE.search(line):
                continue
            if line.upper() == "WEBVTT":
                continue
            texts.append(line)
    return " ".join(texts)


def _word_tokens(text: str) -> list[str]:
    return WORD_RE.findall(text.lower())


def diff_ratio(subtitle_text: str, script_text: str) -> float:
    """Word-level drift between subtitle text and reference script.

    Returns 0.0 for identical text and 1.0 for nothing in common.
    """
    a = _word_tokens(subtitle_text)
    b = _word_tokens(script_text)
    if not a and not b:
        return 0.0
    similarity = difflib.SequenceMatcher(None, a, b).ratio()
    return 1.0 - similarity


def build_review_report(
    subtitle_path: str,
    script_path: str | None = None,
    max_diff_ratio: float = 0.12,
) -> dict:
    """Compare a subtitle file against a reference script.

    Returns a report dict with ``status`` ("pass"/"fail"/"skipped"),
    ``diff_ratio``, and the paths involved.
    """
    subtitle_text = extract_subtitle_text(subtitle_path)
    report: dict = {
        "subtitle_path": subtitle_path,
        "script_path": script_path,
        "subtitle_chars": len(subtitle_text),
    }
    if script_path is None:
        report.update(
            status="skipped", diff_ratio=0.0, detail="no reference script supplied"
        )
        return report
    with open(script_path, encoding="utf-8") as fh:
        script_text = fh.read()
    ratio = diff_ratio(subtitle_text, script_text)
    report.update(
        diff_ratio=ratio,
        status="pass" if ratio <= max_diff_ratio else "fail",
        detail=(f"subtitle/script drift {ratio:.3f} (threshold {max_diff_ratio:.3f})"),
    )
    return report


def ensure_subtitle_consistency(
    subtitle_path: str,
    script_path: str | None,
    max_diff_ratio: float = 0.1,
) -> dict:
    """Raise RuntimeError if subtitle/script drift exceeds ``max_diff_ratio``.

    Returns the review report when the check passes. A ``None`` script path
    skips the check (nothing to compare against).
    """
    report = build_review_report(subtitle_path, script_path, max_diff_ratio)
    if report["status"] == "fail":
        raise RuntimeError(
            f"Subtitle/script review failed: drift {report['diff_ratio']:.3f} "
            f"exceeds maximum allowed {max_diff_ratio:.3f} "
            f"(subtitle={subtitle_path}, script={script_path})"
        )
    return report


def render_preview_frame(
    video_path: str,
    subtitle_path: str,
    at: str = "00:00:05.000",
    output_path: str | None = None,
) -> str:
    """Render one subtitled frame with ffmpeg; returns the output path."""
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        raise RuntimeError("ffmpeg not found on PATH; cannot render preview frame")
    if output_path is None:
        stem = video_path.rsplit(".", 1)[0]
        output_path = f"{stem}_preview.png"
    cmd = [
        ffmpeg,
        "-y",
        "-ss",
        at,
        "-i",
        video_path,
        "-vf",
        f"subtitles='{subtitle_path}'",
        "-frames:v",
        "1",
        output_path,
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    return output_path


def review_subtitles(
    subtitle_path: str,
    script_path: str | None = None,
    max_diff_ratio: float = 0.12,
    preview_video: str | None = None,
    preview_at: str | None = None,
    preview_output: str | None = None,
) -> dict:
    """Full review: drift report plus an optional preview frame."""
    report = build_review_report(subtitle_path, script_path, max_diff_ratio)
    if preview_video and preview_output:
        report["preview_path"] = render_preview_frame(
            preview_video,
            subtitle_path,
            at=preview_at or "00:00:05.000",
            output_path=preview_output,
        )
    return report
