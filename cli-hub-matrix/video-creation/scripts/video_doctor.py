#!/usr/bin/env python3
"""Investigate video-creation artifacts and report evidence for agent review.

This helper is intentionally non-binary. It reports facts and investigation
signals; it does not decide whether a video passes. A nonzero exit means the
doctor could not run, not that the artifact is bad.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


DEFAULT_FLAG_TERMS = [
    "MISSION SUBTITLE",
    "MISSION LOG",
    "DEBUG",
    "TODO",
]

SOURCE_TEXT_TERMS = [
    "hardcoded subtitle",
    "hardcoded subtitles",
    "source subtitle",
    "source subtitles",
    "burned subtitle",
    "burned subtitles",
    "broadcast graphic",
    "broadcast graphics",
    "lower third",
    "ticker",
    "watermark",
    "platform ui",
    "logo bug",
    "chinese subtitle",
    "caption collision",
]

SOURCE_TEXT_MITIGATION_TERMS = [
    "safe zone",
    "safe-zone",
    "crop",
    "cropped",
    "mask",
    "masked",
    "blur",
    "blurred",
    "replace",
    "replaced",
    "avoid",
    "avoided",
    "upper",
    "side",
    "acceptable",
    "intentional",
]

AUDIO_ROLE_VALUES = [
    "silent_or_mute",
    "ambience_keep",
    "dialogue_keep",
    "music_only",
    "mixed_music_speech",
    "needs_separation",
    "unknown",
]

AUDIO_ROLE_FIELDS = [
    "audio_role",
    "audio_class",
    "source_audio_role",
    "source_audio_class",
]

AUDIO_OVERLAP_POLICY_FIELDS = [
    "overlap_policy",
    "new_music_overlap_policy",
    "source_audio_policy",
    "narration_overlap_policy",
    "audio_policy",
]

SOURCE_AUDIO_CONFLICT_TERMS = [
    "under the music",
    "under music",
    "under the score",
    "under score",
    "under narration",
    "under the narration",
    "source texture",
    "source-audio texture",
    "source audio texture",
    "retain all source audio",
    "retained source audio",
    "mixed audibly",
    "audible under",
]

SOURCE_AUDIO_RESOLUTION_TERMS = [
    "mute",
    "muted",
    "duck",
    "ducked",
    "sidechain",
    "side-chain",
    "separate",
    "separated",
    "separation",
    "demucs",
    "spleeter",
    "uvr",
    "isolate",
    "vocal",
    "vocals",
    "accompaniment",
    "instrumental",
    "keep source only",
    "source-only",
    "no new music",
]

SRT_TIME = re.compile(
    r"(?P<start>\d\d:\d\d:\d\d[,.]\d{3})\s*-->\s*(?P<end>\d\d:\d\d:\d\d[,.]\d{3})"
)


def as_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def as_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def parse_rate(value: str | None) -> float | None:
    if not value or value == "0/0":
        return None
    if "/" in value:
        num, den = value.split("/", 1)
        try:
            den_f = float(den)
            return float(num) / den_f if den_f else None
        except ValueError:
            return None
    return as_float(value)


def ensure_tool(name: str) -> None:
    if shutil.which(name) is None:
        raise RuntimeError(f"{name} not found on PATH")


def run(cmd: list[str], *, capture: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, text=True, capture_output=capture, check=False)


def run_bytes(cmd: list[str]) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(cmd, capture_output=True, check=False)


def run_checked(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    proc = run(cmd)
    if proc.returncode != 0:
        detail = proc.stderr.strip() or proc.stdout.strip() or "command failed"
        raise RuntimeError(detail)
    return proc


def run_ffprobe(path: Path) -> dict[str, Any]:
    ensure_tool("ffprobe")
    proc = run_checked(
        [
            "ffprobe",
            "-v",
            "error",
            "-print_format",
            "json",
            "-show_format",
            "-show_streams",
            str(path),
        ]
    )
    return json.loads(proc.stdout)


def media_summary(path: Path, raw: dict[str, Any]) -> dict[str, Any]:
    fmt = raw.get("format", {})
    video_streams: list[dict[str, Any]] = []
    audio_streams: list[dict[str, Any]] = []
    for stream in raw.get("streams", []):
        if stream.get("codec_type") == "video":
            video_streams.append(
                {
                    "index": stream.get("index"),
                    "codec": stream.get("codec_name"),
                    "profile": stream.get("profile"),
                    "width": stream.get("width"),
                    "height": stream.get("height"),
                    "pix_fmt": stream.get("pix_fmt"),
                    "duration": as_float(stream.get("duration")),
                    "nb_frames": stream.get("nb_frames"),
                    "avg_frame_rate": stream.get("avg_frame_rate"),
                    "avg_fps": parse_rate(stream.get("avg_frame_rate")),
                    "r_frame_rate": stream.get("r_frame_rate"),
                    "sample_aspect_ratio": stream.get("sample_aspect_ratio"),
                    "display_aspect_ratio": stream.get("display_aspect_ratio"),
                    "field_order": stream.get("field_order"),
                    "color_range": stream.get("color_range"),
                    "color_space": stream.get("color_space"),
                    "color_transfer": stream.get("color_transfer"),
                    "color_primaries": stream.get("color_primaries"),
                    "bit_rate": as_float(stream.get("bit_rate")),
                }
            )
        elif stream.get("codec_type") == "audio":
            audio_streams.append(
                {
                    "index": stream.get("index"),
                    "codec": stream.get("codec_name"),
                    "profile": stream.get("profile"),
                    "sample_rate": as_float(stream.get("sample_rate")),
                    "channels": stream.get("channels"),
                    "channel_layout": stream.get("channel_layout"),
                    "duration": as_float(stream.get("duration")),
                    "bit_rate": as_float(stream.get("bit_rate")),
                }
            )
    return {
        "file": str(path),
        "size_bytes": path.stat().st_size,
        "format": fmt.get("format_name"),
        "duration": as_float(fmt.get("duration")),
        "bit_rate": as_float(fmt.get("bit_rate")),
        "video_streams": video_streams,
        "audio_streams": audio_streams,
    }


def compact_media(path: Path | None) -> dict[str, Any] | None:
    if path is None:
        return None
    raw = run_ffprobe(path)
    summary = media_summary(path, raw)
    video = summary["video_streams"][0] if summary["video_streams"] else {}
    return {
        "path": str(path),
        "duration": summary.get("duration"),
        "width": video.get("width"),
        "height": video.get("height"),
        "fps": video.get("avg_fps"),
        "audio_streams": len(summary["audio_streams"]),
        "video_streams": len(summary["video_streams"]),
    }


def signal(
    topic: str,
    message: str,
    *,
    level: str = "review",
    evidence: dict[str, Any] | None = None,
    investigate: str | None = None,
) -> dict[str, Any]:
    item: dict[str, Any] = {"level": level, "topic": topic, "message": message}
    if evidence:
        item["evidence"] = evidence
    if investigate:
        item["investigate"] = investigate
    return item


def language_counts(text: str) -> dict[str, int]:
    latin = len(re.findall(r"[A-Za-z]", text))
    cjk = len(re.findall(r"[\u3400-\u9fff\u3040-\u30ff\uac00-\ud7af]", text))
    return {
        "latin_letters": latin,
        "cjk_chars": cjk,
        "visible_chars": len([char for char in text if not char.isspace()]),
    }


def merge_intervals(intervals: list[tuple[float, float]], duration: float | None = None) -> list[tuple[float, float]]:
    clipped: list[tuple[float, float]] = []
    for start, end in intervals:
        if duration is not None:
            start = max(0.0, min(duration, start))
            end = max(0.0, min(duration, end))
        if end > start:
            clipped.append((start, end))
    clipped.sort()
    merged: list[tuple[float, float]] = []
    for start, end in clipped:
        if not merged or start > merged[-1][1] + 0.05:
            merged.append((start, end))
        else:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
    return merged


def coverage_seconds(intervals: list[tuple[float, float]], duration: float | None = None) -> float:
    return sum(end - start for start, end in merge_intervals(intervals, duration))


def sampled_frame_hashes(
    media: Path,
    *,
    start: float = 0.0,
    length: float | None = None,
    fps: str = "1/2",
    width: int = 32,
    height: int = 18,
) -> list[str]:
    ensure_tool("ffmpeg")
    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-ss",
        f"{start:.3f}",
        "-i",
        str(media),
    ]
    if length is not None:
        cmd += ["-t", f"{length:.3f}"]
    cmd += [
        "-an",
        "-vf",
        f"fps={fps},scale={width}:{height}:flags=fast_bilinear,format=gray",
        "-f",
        "rawvideo",
        "-",
    ]
    proc = run_bytes(cmd)
    if proc.returncode != 0:
        detail = proc.stderr.decode("utf-8", errors="replace").strip() or "ffmpeg raw frame sampling failed"
        raise RuntimeError(detail)
    frame_size = width * height
    hashes: list[str] = []
    for offset in range(0, len(proc.stdout), frame_size):
        frame = proc.stdout[offset : offset + frame_size]
        if len(frame) != frame_size:
            continue
        avg = sum(frame) / frame_size
        value = 0
        for pix in frame:
            value = (value << 1) | int(pix >= avg)
        hashes.append(f"{value:0{frame_size // 4}x}")
    return hashes


def hamming_distance_hex(left: str, right: str) -> int:
    return (int(left, 16) ^ int(right, 16)).bit_count()


def visual_diversity_summary(hashes: list[str], threshold: int = 36) -> dict[str, Any]:
    groups: list[str] = []
    for item in hashes:
        if not any(hamming_distance_hex(item, existing) <= threshold for existing in groups):
            groups.append(item)
    samples = len(hashes)
    unique_groups = len(groups)
    return {
        "samples": samples,
        "unique_groups": unique_groups,
        "unique_ratio": round(unique_groups / samples, 3) if samples else None,
        "near_duplicate_threshold": threshold,
    }


def parse_time(value: str) -> float:
    value = value.strip().replace(",", ".")
    parts = value.split(":")
    if len(parts) == 3:
        hours, minutes, seconds = parts
        return int(hours) * 3600 + int(minutes) * 60 + float(seconds)
    if len(parts) == 2:
        minutes, seconds = parts
        return int(minutes) * 60 + float(seconds)
    return float(value)


def clean_text(text: str) -> str:
    text = re.sub(r"\{\\.*?\}", "", text)
    text = re.sub(r"<[^>]+>", "", text)
    text = text.replace("\\N", " ").replace("\\n", " ")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def parse_srt(text: str) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    blocks = re.split(r"\n\s*\n", text.strip(), flags=re.MULTILINE)
    for block in blocks:
        lines = [line.strip("\ufeff") for line in block.splitlines() if line.strip()]
        time_index = next((i for i, line in enumerate(lines) if SRT_TIME.search(line)), None)
        if time_index is None:
            continue
        match = SRT_TIME.search(lines[time_index])
        if not match:
            continue
        entries.append(
            {
                "start": parse_time(match.group("start")),
                "end": parse_time(match.group("end")),
                "text": clean_text(" ".join(lines[time_index + 1 :])),
                "style": "",
            }
        )
    return entries


def parse_ass(text: str) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    in_events = False
    fields: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if line.lower() == "[events]":
            in_events = True
            continue
        if in_events and line.startswith("[") and line.endswith("]"):
            in_events = False
        if not in_events:
            continue
        if line.lower().startswith("format:"):
            fields = [part.strip().lower() for part in line.split(":", 1)[1].split(",")]
            continue
        if line.lower().startswith("dialogue:"):
            payload = line.split(":", 1)[1].lstrip()
            if not fields:
                continue
            parts = payload.split(",", maxsplit=len(fields) - 1)
            if len(parts) != len(fields):
                continue
            row = dict(zip(fields, parts))
            try:
                start = parse_time(row["start"])
                end = parse_time(row["end"])
            except (KeyError, ValueError):
                continue
            entries.append(
                {
                    "start": start,
                    "end": end,
                    "text": clean_text(row.get("text", "")),
                    "style": row.get("style") or "",
                }
            )
    return entries


def parse_ass_metadata(text: str) -> dict[str, Any]:
    metadata: dict[str, Any] = {"playres_x": None, "playres_y": None, "styles": {}}
    in_styles = False
    style_fields: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        lower = line.lower()
        if lower.startswith("playresx:"):
            metadata["playres_x"] = as_int(as_float(line.split(":", 1)[1].strip()))
        elif lower.startswith("playresy:"):
            metadata["playres_y"] = as_int(as_float(line.split(":", 1)[1].strip()))
        if lower == "[v4+ styles]":
            in_styles = True
            continue
        if in_styles and line.startswith("[") and line.endswith("]"):
            in_styles = False
        if not in_styles:
            continue
        if lower.startswith("format:"):
            style_fields = [part.strip().lower() for part in line.split(":", 1)[1].split(",")]
            continue
        if lower.startswith("style:") and style_fields:
            payload = line.split(":", 1)[1].lstrip()
            parts = payload.split(",", maxsplit=len(style_fields) - 1)
            if len(parts) != len(style_fields):
                continue
            row = dict(zip(style_fields, parts))
            name = row.get("name")
            if not name:
                continue
            metadata["styles"][name] = {
                "fontname": row.get("fontname"),
                "fontsize": as_float(row.get("fontsize")),
                "bold": row.get("bold"),
                "alignment": row.get("alignment"),
                "borderstyle": row.get("borderstyle"),
                "outline": as_float(row.get("outline")),
                "shadow": as_float(row.get("shadow")),
                "primary_colour": row.get("primarycolour"),
                "back_colour": row.get("backcolour"),
                "margin_l": row.get("marginl"),
                "margin_r": row.get("marginr"),
                "margin_v": row.get("marginv"),
            }
    return metadata


def parse_captions(path: Path, text: str) -> list[dict[str, Any]]:
    suffix = path.suffix.lower()
    if suffix == ".srt":
        return parse_srt(text)
    if suffix in {".ass", ".ssa"}:
        return parse_ass(text)
    srt_entries = parse_srt(text)
    return srt_entries if srt_entries else parse_ass(text)


def caption_doctor(args: argparse.Namespace) -> dict[str, Any]:
    text = args.captions.read_text(encoding="utf-8-sig")
    entries = parse_captions(args.captions, text)
    metadata = parse_ass_metadata(text)
    media = compact_media(args.media) if args.media else None
    narration = compact_media(args.narration) if args.narration else None
    voice_styles = {style.lower() for style in args.voice_style}
    output_language = (args.output_language or "").strip().lower()
    signals: list[dict[str, Any]] = []

    if not entries:
        signals.append(
            signal(
                "caption_parse",
                "No timed caption entries were parsed.",
                level="strong_signal",
                investigate="Check file format, encoding, and whether captions are generated elsewhere.",
            )
        )

    all_caption_text = " ".join(str(entry.get("text") or "") for entry in entries)
    caption_language = language_counts(all_caption_text)
    if output_language in {"en", "eng", "english"} and caption_language["cjk_chars"] > 0:
        signals.append(
            signal(
                "caption_language",
                "Caption text includes CJK characters while English output was requested.",
                evidence=caption_language,
                investigate="Confirm whether these are intentional names/source translations or leaked source/instruction language.",
            )
        )

    duration = as_float(args.duration)
    if duration is None and media:
        duration = as_float(media.get("duration"))

    playres_x = metadata.get("playres_x")
    playres_y = metadata.get("playres_y")
    media_w = media.get("width") if media else None
    media_h = media.get("height") if media else None
    if media_w and media_h and playres_x and playres_y:
        if playres_x != media_w or playres_y != media_h:
            signals.append(
                signal(
                    "caption_resolution",
                    "ASS PlayRes differs from the final media dimensions.",
                    level="strong_signal",
                    evidence={
                        "playres": f"{playres_x}x{playres_y}",
                        "media": f"{media_w}x{media_h}",
                    },
                    investigate=(
                        "Inspect caption-heavy frames at final size; resize styles or justify "
                        "why effective text remains readable."
                    ),
                )
            )
        for style_name, style in metadata.get("styles", {}).items():
            font_size = as_float(style.get("fontsize"))
            if not font_size:
                continue
            effective = font_size * float(media_h) / float(playres_y)
            if style_name.lower() in voice_styles and effective < 32:
                signals.append(
                    signal(
                        "caption_readability",
                        "A voice-caption style scales to a small effective font size.",
                        evidence={"style": style_name, "effective_px": round(effective, 1)},
                        investigate="Review the final frame on the target display size.",
                    )
                )
            font_name = str(style.get("fontname") or "").strip().lower()
            outline = as_float(style.get("outline")) or 0.0
            borderstyle = str(style.get("borderstyle") or "")
            if style_name.lower() in voice_styles and font_name in {"arial", "dejavu sans", "sans-serif"}:
                signals.append(
                    signal(
                        "caption_style",
                        "A voice-caption style uses a generic fallback-looking font.",
                        evidence={
                            "style": style_name,
                            "font": style.get("fontname"),
                            "borderstyle": borderstyle,
                            "outline": outline,
                        },
                        investigate=(
                            "Inspect caption-heavy frames for genre fit; choose an intentional "
                            "font/style or document why this fallback is acceptable."
                        ),
                    )
                )
            if style_name.lower() in voice_styles and borderstyle != "3" and outline >= 2.0:
                signals.append(
                    signal(
                        "caption_style",
                        "A voice-caption style appears to rely on a thick outline instead of a designed plate/shadow.",
                        evidence={"style": style_name, "outline": outline, "borderstyle": borderstyle},
                        investigate="Check whether captions look like default subtitles pasted over the video.",
                    )
                )

    previous_end = -1.0
    overlap_count = 0
    end_after_media: list[int] = []
    empty_count = 0
    flagged_terms: list[dict[str, Any]] = []
    normalized_counts: dict[str, int] = {}
    voice_entries: list[dict[str, Any]] = []

    for idx, entry in enumerate(entries):
        start = float(entry["start"])
        end = float(entry["end"])
        text_value = str(entry.get("text") or "")
        if end <= start:
            signals.append(
                signal(
                    "caption_timing",
                    "Caption entry has non-positive duration.",
                    level="strong_signal",
                    evidence={"entry": idx, "start": start, "end": end},
                    investigate="Fix or regenerate the timed-caption source.",
                )
            )
        if start < previous_end - 0.05:
            overlap_count += 1
        previous_end = max(previous_end, end)
        if duration is not None and end > duration + 0.25:
            end_after_media.append(idx)
        if not text_value:
            empty_count += 1
        upper = text_value.upper()
        for term in args.flag_term:
            if term.upper() in upper:
                flagged_terms.append({"entry": idx, "term": term, "text": text_value[:80]})
        normalized = re.sub(r"[^A-Z0-9]+", " ", upper).strip()
        if normalized:
            normalized_counts[normalized] = normalized_counts.get(normalized, 0) + 1
        style = str(entry.get("style") or "")
        if not style or style.lower() in voice_styles:
            voice_entries.append(entry)

    if overlap_count:
        signals.append(
            signal(
                "caption_timing",
                "Some caption entries overlap previous entries.",
                evidence={"overlap_count": overlap_count},
                investigate="Decide whether overlaps are intentional title/callout layering or stale subtitles.",
            )
        )
    if end_after_media:
        signals.append(
            signal(
                "caption_timing",
                "Some captions extend beyond the media duration.",
                level="strong_signal",
                evidence={"entries": end_after_media[:10], "count": len(end_after_media)},
                investigate="Check whether captions were authored against a different master.",
            )
        )
    if empty_count:
        signals.append(
            signal(
                "caption_text",
                "Some timed entries have no visible text after cleanup.",
                evidence={"count": empty_count},
                investigate="Inspect ASS overrides or blank placeholder entries.",
            )
        )
    if flagged_terms:
        signals.append(
            signal(
                "caption_text",
                "Potential debug or placeholder terms appear in captions.",
                evidence={"matches": flagged_terms[:10], "count": len(flagged_terms)},
                investigate="Confirm whether these terms are intended viewer-facing copy.",
            )
        )
    repeated = [
        {"text": key, "count": count}
        for key, count in normalized_counts.items()
        if count >= 3 and count / max(len(entries), 1) >= 0.5
    ]
    if repeated:
        signals.append(
            signal(
                "caption_text",
                "Persistent repeated caption text may indicate a stuck label.",
                evidence={"repeated": repeated[:10]},
                investigate="Inspect contact sheets for stale subtitles or debug labels.",
            )
        )

    voice_summary: dict[str, Any] | None = None
    if voice_entries:
        voice_first = min(float(entry["start"]) for entry in voice_entries)
        voice_last = max(float(entry["end"]) for entry in voice_entries)
        voice_intervals = [(float(entry["start"]), float(entry["end"])) for entry in voice_entries]
        voice_media_coverage = None
        post_caption_tail = None
        if duration is not None and duration > 0:
            covered = coverage_seconds(voice_intervals, duration)
            voice_media_coverage = covered / duration
            post_caption_tail = max(0.0, duration - voice_last)
        voice_summary = {
            "entries": len(voice_entries),
            "first_start": voice_first,
            "last_end": voice_last,
            "span": voice_last - voice_first,
            "media_coverage_ratio": round(voice_media_coverage, 3) if voice_media_coverage is not None else None,
            "post_caption_tail_seconds": round(post_caption_tail, 3) if post_caption_tail is not None else None,
        }
        if args.expect_authored_coverage and duration is not None and post_caption_tail is not None:
            tail_threshold = max(args.post_caption_tail_signal, duration * 0.12)
            if post_caption_tail > tail_threshold:
                signals.append(
                    signal(
                        "caption_media_coverage",
                        "The planned authored-caption coverage leaves a large gap before media end.",
                        level="strong_signal",
                        evidence={
                            "media_duration": round(duration, 3),
                            "voice_last_end": round(voice_last, 3),
                            "post_caption_tail_seconds": round(post_caption_tail, 3),
                            "media_coverage_ratio": round(voice_media_coverage or 0.0, 3),
                        },
                        investigate=(
                            "Because authored coverage was requested for this doctor run, inspect the tail; "
                            "add authored language coverage or shorten/restructure the ending."
                        ),
                    )
                )
            if (
                voice_media_coverage is not None
                and duration >= 30
                and voice_media_coverage < args.voice_media_coverage_signal
            ):
                signals.append(
                    signal(
                        "caption_media_coverage",
                        "Voice-style caption coverage is low relative to the final media duration.",
                        evidence={
                            "media_duration": round(duration, 3),
                            "media_coverage_ratio": round(voice_media_coverage, 3),
                            "threshold": args.voice_media_coverage_signal,
                        },
                        investigate="Check whether the video relies on source-only content where the brief expects authored narration/intertitles.",
                    )
                )
        narration_duration = as_float(narration.get("duration")) if narration else None
        if narration_duration is not None:
            if (
                args.expect_authored_coverage
                and duration is not None
                and duration - narration_duration > args.narration_media_tail_signal
            ):
                signals.append(
                    signal(
                        "narration_media_coverage",
                        "Narration audio coverage leaves a large gap before media end in an authored-coverage review.",
                        evidence={
                            "media_duration": round(duration, 3),
                            "narration_duration": round(narration_duration, 3),
                            "post_narration_tail_seconds": round(duration - narration_duration, 3),
                        },
                        investigate="Inspect whether the ending has authored intertitles, intended source-only material, or an unintended coverage gap.",
                    )
                )
            if voice_last > narration_duration + args.voice_after_narration_signal:
                signals.append(
                    signal(
                        "caption_voice_alignment",
                        "Voice-style captions extend well beyond the narration audio.",
                        level="strong_signal",
                        evidence={
                            "voice_last_end": round(voice_last, 3),
                            "narration_duration": round(narration_duration, 3),
                        },
                        investigate=(
                            "Check whether these are narration subtitles or hand-timed story "
                            "summaries; align against the final voice track."
                        ),
                    )
                )
            if narration_duration > 10 and (voice_last - voice_first) < narration_duration * 0.45:
                signals.append(
                    signal(
                        "caption_voice_alignment",
                        "Voice-style caption coverage is much shorter than narration.",
                        evidence={
                            "voice_span": round(voice_last - voice_first, 3),
                            "narration_duration": round(narration_duration, 3),
                        },
                        investigate="Check for missing subtitles or wrong voice-style names.",
                    )
                )
    elif narration:
        signals.append(
            signal(
                "caption_voice_alignment",
                "Narration audio was supplied, but no voice-style caption entries were found.",
                evidence={"voice_styles": sorted(args.voice_style)},
                investigate="Confirm style naming or whether subtitles were authored in another layer.",
            )
        )

    review_dir_summary = None
    if args.review_dir:
        images = []
        if args.review_dir.exists():
            images = [
                item.name
                for item in args.review_dir.iterdir()
                if item.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}
            ]
        review_dir_summary = {
            "path": str(args.review_dir),
            "exists": args.review_dir.exists(),
            "images": len(images),
        }
        if not args.review_dir.exists() or not images:
            signals.append(
                signal(
                    "review_assets",
                    "Review-frame directory is missing or has no image frames.",
                    evidence=review_dir_summary,
                    investigate="Generate caption-heavy frames from the exact promoted final.",
                )
            )

    return {
        "doctor": "captions",
        "artifact": str(args.captions),
        "summary": {
            "entries": len(entries),
            "first_start": entries[0]["start"] if entries else None,
            "last_end": entries[-1]["end"] if entries else None,
            "ass_metadata": metadata,
            "media": media,
            "narration": narration,
            "voice_styles": sorted(args.voice_style),
            "output_language": args.output_language,
            "caption_language_counts": caption_language,
            "voice_caption_summary": voice_summary,
            "review_dir": review_dir_summary,
        },
        "signals": signals,
        "agent_instruction": (
            "Use these signals to choose what to inspect next. Do not treat this "
            "report as a pass/fail verdict. Use --expect-authored-coverage only "
            "when the brief expects narration or intertitles to carry the story."
        ),
    }


def load_manifest(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ("sources", "music_sources", "items"):
            if isinstance(data.get(key), list):
                return data[key]
    raise ValueError("manifest must be a list or contain sources/music_sources/items")


def get_source_path(item: dict[str, Any]) -> str | None:
    for key in ("local_file", "file", "path", "filename"):
        value = item.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def get_ranges(item: dict[str, Any]) -> list[dict[str, Any]]:
    for key in ("selected_ranges", "used_ranges", "ranges", "clips"):
        value = item.get(key)
        if isinstance(value, list):
            return [v for v in value if isinstance(v, dict)]
    return []


def resolve_path(value: str, root: Path, manifest_dir: Path) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    root_candidate = root / path
    if root_candidate.exists():
        return root_candidate
    return manifest_dir / path


def range_value(item: dict[str, Any], *names: str) -> float | None:
    for name in names:
        if name in item:
            return as_float(item[name])
    return None


def manifest_text_blob(*items: Any) -> str:
    parts: list[str] = []
    for item in items:
        if item is None:
            continue
        if isinstance(item, dict):
            parts.append(manifest_text_blob(*item.values()))
        elif isinstance(item, list):
            parts.append(manifest_text_blob(*item))
        else:
            parts.append(str(item))
    return " ".join(part for part in parts if part).lower()


def has_any_term(text: str, terms: list[str]) -> bool:
    return any(term in text for term in terms)


def first_manifest_value(item: dict[str, Any], names: list[str]) -> Any:
    for name in names:
        value = item.get(name)
        if value not in (None, ""):
            return value
    return None


def normalize_audio_role(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip().lower().replace("-", "_").replace(" ", "_")
    aliases = {
        "mute": "silent_or_mute",
        "muted": "silent_or_mute",
        "silent": "silent_or_mute",
        "no_audio": "silent_or_mute",
        "ambience": "ambience_keep",
        "ambient": "ambience_keep",
        "nat_sound": "ambience_keep",
        "natural_sound": "ambience_keep",
        "dialogue": "dialogue_keep",
        "speech": "dialogue_keep",
        "voice": "dialogue_keep",
        "source_music": "music_only",
        "music": "music_only",
        "mixed": "mixed_music_speech",
        "mixed_speech_music": "mixed_music_speech",
        "speech_music": "mixed_music_speech",
    }
    return aliases.get(text, text)


def source_audio_metadata(item: dict[str, Any], selected: dict[str, Any] | None = None) -> dict[str, Any]:
    selected = selected or {}
    role = normalize_audio_role(
        first_manifest_value(selected, AUDIO_ROLE_FIELDS)
        or first_manifest_value(item, AUDIO_ROLE_FIELDS)
    )
    policy = (
        first_manifest_value(selected, AUDIO_OVERLAP_POLICY_FIELDS)
        or first_manifest_value(item, AUDIO_OVERLAP_POLICY_FIELDS)
    )
    speech_needed = first_manifest_value(selected, ["speech_needed", "dialogue_needed", "voice_needed"])
    source_music_present = first_manifest_value(
        selected,
        ["source_music_present", "music_present", "bgm_present"],
    ) or first_manifest_value(item, ["source_music_present", "music_present", "bgm_present"])
    separation_tool = first_manifest_value(selected, ["separation_tool", "source_separation_tool"]) or first_manifest_value(
        item,
        ["separation_tool", "source_separation_tool"],
    )
    return {
        "audio_role": role,
        "overlap_policy": str(policy).strip() if policy not in (None, "") else None,
        "speech_needed": speech_needed,
        "source_music_present": source_music_present,
        "separation_tool": separation_tool,
    }


def parse_time_ranges_from_text(text: str) -> list[tuple[float, float]]:
    ranges: list[tuple[float, float]] = []
    for match in re.finditer(
        r"(?<![\d.])(\d+(?:\.\d+)?)\s*(?:-|–|—|to)\s*(\d+(?:\.\d+)?)\s*s\b",
        text,
        flags=re.IGNORECASE,
    ):
        start = float(match.group(1))
        end = float(match.group(2))
        if end > start:
            ranges.append((start, end))
    return ranges


def selected_timeline_range(selected: dict[str, Any]) -> tuple[float, float] | None:
    start = range_value(
        selected,
        "timeline_start",
        "final_start",
        "edit_start",
        "out_start",
        "placement_start",
    )
    end = range_value(
        selected,
        "timeline_end",
        "final_end",
        "edit_end",
        "out_end",
        "placement_end",
    )
    if start is not None and end is not None and end > start:
        return start, end
    start = range_value(selected, "timeline_start", "final_start", "edit_start", "out_start", "placement_start")
    duration = range_value(selected, "duration", "timeline_duration", "edit_duration")
    if start is not None and duration is not None and duration > 0:
        return start, start + duration
    return None


def sources_doctor(args: argparse.Namespace) -> dict[str, Any]:
    items = load_manifest(args.manifest)
    entries: list[dict[str, Any]] = []
    signals: list[dict[str, Any]] = []

    for idx, item in enumerate(items):
        source_id = str(item.get("id") or item.get("name") or f"source_{idx}")
        local_value = get_source_path(item)
        entry: dict[str, Any] = {"id": source_id}
        if not local_value:
            signals.append(
                signal(
                    "source_manifest",
                    "Source entry has no local file/path field.",
                    level="strong_signal",
                    evidence={"id": source_id},
                    investigate="Record the downloaded or generated file used by the edit.",
                )
            )
            entries.append(entry)
            continue

        path = resolve_path(local_value, args.root, args.manifest.parent)
        entry["path"] = str(path)
        if not path.exists():
            signals.append(
                signal(
                    "source_manifest",
                    "Referenced source file does not exist.",
                    level="strong_signal",
                    evidence={"id": source_id, "path": str(path)},
                    investigate="Check stale paths or whether the file was generated elsewhere.",
                )
            )
            entries.append(entry)
            continue

        try:
            compact = compact_media(path)
        except Exception as exc:  # noqa: BLE001 - diagnostic report
            compact = {"probe_error": str(exc)}
            signals.append(
                signal(
                    "source_probe",
                    "Source media probe did not complete.",
                    evidence={"id": source_id, "error": str(exc)},
                    investigate="Probe manually with ffprobe and check file integrity.",
                )
            )
        if compact:
            entry.update(compact)
            width = compact.get("width")
            height = compact.get("height")
            if width is not None and height is not None and (width < 1280 or height < 720):
                signals.append(
                    signal(
                        "source_quality",
                        "Source resolution is below 720p.",
                        evidence={"id": source_id, "resolution": f"{width}x{height}"},
                        investigate="Inspect whether this source can carry the intended shot role.",
                    )
                )

        if not (item.get("platform_url") or item.get("url") or item.get("source_url")):
            signals.append(
                signal(
                    "source_provenance",
                    "Source entry lacks platform/source URL evidence.",
                    evidence={"id": source_id},
                    investigate="Record origin URL or explain why the asset is local/generated.",
                )
            )
        if not item.get("evidence_level"):
            signals.append(
                signal(
                    "source_provenance",
                    "Source entry lacks evidence_level.",
                    evidence={"id": source_id},
                    investigate="Classify direct platform, verified transport, weak mirror, or generated/local.",
                )
            )
        if not (item.get("license") or item.get("rights_notes")):
            signals.append(
                signal(
                    "source_rights",
                    "Source entry lacks license or rights notes.",
                    evidence={"id": source_id},
                    investigate="Add usable rights notes before promotion or ask the user.",
                )
            )

        ranges = get_ranges(item)
        entry["selected_ranges"] = len(ranges)
        entry["audio_streams"] = entry.get("audio_streams", 0)
        if not ranges:
            signals.append(
                signal(
                    "source_selection",
                    "Source entry has no selected ranges.",
                    evidence={"id": source_id},
                    investigate="Record which ranges are actually used and their story roles.",
                )
            )
        duration = as_float(entry.get("duration"))
        missing_risk_note_ranges: list[dict[str, Any]] = []
        unmitigated_source_text_ranges: list[dict[str, Any]] = []
        missing_audio_role_ranges: list[dict[str, Any]] = []
        risky_audio_policy_ranges: list[dict[str, Any]] = []
        for ridx, selected in enumerate(ranges):
            start = range_value(selected, "start", "in", "start_time")
            end = range_value(selected, "end", "out", "end_time")
            if start is None or end is None:
                signals.append(
                    signal(
                        "source_selection",
                        "Selected range lacks numeric start/end.",
                        evidence={"id": source_id, "range": ridx},
                        investigate="Normalize selected range metadata.",
                    )
                )
                continue
            if end <= start:
                signals.append(
                    signal(
                        "source_selection",
                        "Selected range has end <= start.",
                        level="strong_signal",
                        evidence={"id": source_id, "range": ridx, "start": start, "end": end},
                        investigate="Fix range timing before using this source.",
                    )
                )
            if duration is not None and end > duration + 0.25:
                signals.append(
                    signal(
                        "source_selection",
                        "Selected range ends after source duration.",
                        level="strong_signal",
                        evidence={
                            "id": source_id,
                            "range": ridx,
                            "end": end,
                            "duration": duration,
                        },
                        investigate="Check whether the manifest references the wrong source file.",
                    )
                )
            if not (selected.get("role") or selected.get("shot_role")):
                signals.append(
                    signal(
                        "source_selection",
                        "Selected range lacks a story role.",
                        evidence={"id": source_id, "range": ridx},
                        investigate="Explain why this shot belongs in the edit.",
                    )
                )
            if not any(
                key in selected
                for key in (
                    "risk",
                    "risks",
                    "quality_notes",
                    "source_text",
                    "visible_text",
                    "watermark",
                    "subtitles",
                )
            ):
                missing_risk_note_ranges.append({"range": ridx, "start": start, "end": end})
            risk_text = manifest_text_blob(
                selected.get("risk"),
                selected.get("risks"),
                selected.get("quality_notes"),
                selected.get("source_text"),
                selected.get("watermark"),
                selected.get("subtitles"),
                selected.get("visible_text"),
                item.get("quality_caveat"),
                item.get("source_text"),
                item.get("watermark"),
                item.get("subtitles"),
                item.get("visible_text"),
            )
            if has_any_term(risk_text, SOURCE_TEXT_TERMS) and not has_any_term(
                risk_text, SOURCE_TEXT_MITIGATION_TERMS
            ):
                unmitigated_source_text_ranges.append({"range": ridx, "start": start, "end": end})
            audio_meta = source_audio_metadata(item, selected)
            audio_role = audio_meta["audio_role"]
            policy_text = manifest_text_blob(audio_meta["overlap_policy"], selected, item)
            if entry.get("audio_streams") and not audio_role:
                missing_audio_role_ranges.append({"range": ridx, "start": start, "end": end})
            elif audio_role and audio_role not in AUDIO_ROLE_VALUES:
                signals.append(
                    signal(
                        "source_audio_role",
                        "Selected range uses a non-standard audio role.",
                        evidence={"id": source_id, "range": ridx, "audio_role": audio_role},
                        investigate=(
                            "Normalize to silent_or_mute, ambience_keep, dialogue_keep, music_only, "
                            "mixed_music_speech, needs_separation, or unknown."
                        ),
                    )
                )
            if audio_role in {"dialogue_keep", "music_only", "mixed_music_speech", "needs_separation"} and not audio_meta[
                "overlap_policy"
            ]:
                risky_audio_policy_ranges.append(
                    {"range": ridx, "start": start, "end": end, "audio_role": audio_role}
                )
            if audio_role in {"mixed_music_speech", "needs_separation"} and not (
                audio_meta["separation_tool"] or has_any_term(policy_text, SOURCE_AUDIO_RESOLUTION_TERMS)
            ):
                signals.append(
                    signal(
                        "source_audio_overlap",
                        "Mixed speech/music source audio lacks a separation or replacement plan.",
                        level="strong_signal",
                        evidence={"id": source_id, "range": ridx, "audio_role": audio_role},
                        investigate=(
                            "Use source separation, keep the source speech as foreground, mute the source, "
                            "or choose a cleaner range before adding narration or a new music bed."
                        ),
                    )
                )
            if has_any_term(policy_text, SOURCE_AUDIO_CONFLICT_TERMS) and not has_any_term(
                policy_text, SOURCE_AUDIO_RESOLUTION_TERMS
            ):
                signals.append(
                    signal(
                        "source_audio_overlap",
                        "Source-audio text suggests overlap with music or narration without a clear mitigation.",
                        evidence={"id": source_id, "range": ridx},
                        investigate=(
                            "Decide whether source audio is muted, ducked, isolated, source-only, or truly ambience-only."
                        ),
                    )
                )
        if missing_risk_note_ranges:
            signals.append(
                signal(
                    "source_range_review",
                    "Some selected ranges lack source-text/watermark/quality risk notes.",
                    evidence={
                        "id": source_id,
                        "count": len(missing_risk_note_ranges),
                        "sample": missing_risk_note_ranges[:8],
                    },
                    investigate=(
                        "Review selected-range contact sheets for hardcoded subtitles, broadcast graphics, "
                        "watermarks, platform UI, and caption-safe-zone risks."
                    ),
                )
            )
        if unmitigated_source_text_ranges:
            signals.append(
                signal(
                    "source_text_occupancy",
                    "Some selected ranges mention source subtitles, broadcast graphics, watermark, or platform UI without mitigation notes.",
                    evidence={
                        "id": source_id,
                        "count": len(unmitigated_source_text_ranges),
                        "sample": unmitigated_source_text_ranges[:8],
                    },
                    investigate="Record safe zone, crop/mask/blur, replacement, or reason the source text is acceptable.",
                )
            )
        if missing_audio_role_ranges:
            signals.append(
                signal(
                    "source_audio_role",
                    "Some selected ranges with audio streams lack source-audio role metadata.",
                    evidence={
                        "id": source_id,
                        "count": len(missing_audio_role_ranges),
                        "sample": missing_audio_role_ranges[:8],
                    },
                    investigate=(
                        "Classify each selected range as silent_or_mute, ambience_keep, dialogue_keep, "
                        "music_only, mixed_music_speech, or needs_separation before mixing."
                    ),
                )
            )
        if risky_audio_policy_ranges:
            signals.append(
                signal(
                    "source_audio_overlap",
                    "Some selected ranges have foreground speech/music roles but no overlap policy.",
                    evidence={
                        "id": source_id,
                        "count": len(risky_audio_policy_ranges),
                        "sample": risky_audio_policy_ranges[:8],
                    },
                    investigate=(
                        "Record whether new narration/music is absent, ducked, source-only, muted, or separated in those windows."
                    ),
                )
            )
        entries.append(entry)

    return {
        "doctor": "sources",
        "artifact": str(args.manifest),
        "summary": {"entries": entries, "root": str(args.root)},
        "signals": signals,
        "agent_instruction": (
            "Use this as a provenance and source-selection investigation, not as a license verdict."
        ),
    }


def calc_time(duration: float, expr: str) -> float:
    if expr == "first":
        return 0.5 if duration > 1 else 0
    if expr == "middle":
        return duration / 2
    if expr == "last":
        return duration - 0.25 if duration > 0.5 else 0
    if expr == "tail_start":
        return max(duration - 10, 0)
    if expr == "dense_start":
        return duration * 0.8
    if expr == "tail_len":
        return 10 if duration > 10 else duration
    if expr == "dense_len":
        return duration * 0.2 if duration > 5 else duration
    return 0


def frames_doctor(args: argparse.Namespace) -> dict[str, Any]:
    ensure_tool("ffmpeg")
    ensure_tool("ffprobe")
    args.out_dir.mkdir(parents=True, exist_ok=True)
    media = compact_media(args.media)
    duration = as_float(media.get("duration")) if media else None
    if duration is None or duration <= 0:
        raise RuntimeError("could not read positive media duration")

    times = {
        "first": calc_time(duration, "first"),
        "middle": calc_time(duration, "middle"),
        "last": calc_time(duration, "last"),
        "tail_start": calc_time(duration, "tail_start"),
        "tail_len": calc_time(duration, "tail_len"),
        "dense_start": calc_time(duration, "dense_start"),
        "dense_len": calc_time(duration, "dense_len"),
    }

    outputs: dict[str, str] = {}
    for name in ("first", "middle", "last"):
        out = args.out_dir / f"{name}.jpg"
        run_checked(
            [
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-ss",
                f"{times[name]:.3f}",
                "-i",
                str(args.media),
                "-frames:v",
                "1",
                "-q:v",
                "2",
                str(out),
            ]
        )
        outputs[name] = str(out)

    contact = args.out_dir / f"contact_every_{args.interval}s.jpg"
    run_checked(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(args.media),
            "-vf",
            f"fps=1/{args.interval},scale=320:-1:flags=lanczos,tile=5x5",
            "-frames:v",
            "1",
            str(contact),
        ]
    )
    outputs["contact"] = str(contact)

    tail = args.out_dir / "tail_10s_contact.jpg"
    run_checked(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-ss",
            f"{times['tail_start']:.3f}",
            "-i",
            str(args.media),
            "-t",
            f"{times['tail_len']:.3f}",
            "-vf",
            "fps=1,scale=320:-1:flags=lanczos,tile=5x5",
            "-frames:v",
            "1",
            str(tail),
        ]
    )
    outputs["tail_10s"] = str(tail)

    final_act_fraction = max(0.05, min(0.5, float(args.final_act_fraction)))
    times["dense_start"] = duration * (1.0 - final_act_fraction)
    times["dense_len"] = duration * final_act_fraction

    dense = args.out_dir / "final_act_dense.jpg"
    run_checked(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-ss",
            f"{times['dense_start']:.3f}",
            "-i",
            str(args.media),
            "-t",
            f"{times['dense_len']:.3f}",
            "-vf",
            "fps=2,scale=320:-1:flags=lanczos,tile=5x5",
            "-frames:v",
            "1",
            str(dense),
        ]
    )
    outputs["final_act_dense"] = str(dense)

    diversity: dict[str, Any] = {}
    signals = [
        signal(
            "manual_review",
            "Review frames were generated from the exact media path.",
            level="info",
            investigate=(
                "Inspect these images for topic clarity, subtitle collisions, unreadable text, "
                "black/frozen frames, wrong crops, and final-act payoff."
            ),
        ),
        signal(
            "final_act_payoff",
            "A dense final-act contact sheet was generated for ending/payoff review.",
            level="info",
            evidence={
                "image": str(dense),
                "start": round(times["dense_start"], 3),
                "fraction": final_act_fraction,
            },
            investigate=(
                "Decide whether the ending is a climax, payoff, useful recap, hook, or deliberate unresolved ending "
                "appropriate to the genre; motion alone is not enough."
            ),
        ),
    ]
    try:
        overview_hashes = sampled_frame_hashes(
            args.media,
            start=0.0,
            length=duration,
            fps=f"1/{args.interval}",
        )
        final_hashes = sampled_frame_hashes(
            args.media,
            start=times["dense_start"],
            length=times["dense_len"],
            fps="2",
        )
        overview_diversity = visual_diversity_summary(overview_hashes)
        final_diversity = visual_diversity_summary(final_hashes)
        diversity = {"overview": overview_diversity, "final_act": final_diversity}
        if (
            overview_diversity["samples"] >= 8
            and overview_diversity["unique_ratio"] is not None
            and overview_diversity["unique_ratio"] < 0.45
        ):
            signals.append(
                signal(
                    "visual_diversity",
                    "Sampled frames have low perceptual diversity.",
                    evidence=overview_diversity,
                    investigate="Inspect the contact sheet for repeated screens/cards or accidental static structure.",
                )
            )
        if (
            final_diversity["samples"] >= 8
            and final_diversity["unique_ratio"] is not None
            and final_diversity["unique_ratio"] < 0.45
        ):
            signals.append(
                signal(
                    "final_act_visual_diversity",
                    "The final-act sample has low perceptual diversity.",
                    evidence=final_diversity,
                    investigate="Check whether the ending is an intentional hold/payoff or accidental repetition.",
                )
            )
    except Exception as exc:  # noqa: BLE001 - diagnostic signal only
        signals.append(
            signal(
                "visual_diversity",
                "Perceptual diversity sampling did not complete.",
                evidence={"error": str(exc)},
                investigate="Use the generated contact sheets for manual repetition review.",
            )
        )

    return {
        "doctor": "frames",
        "artifact": str(args.media),
        "summary": {
            "media": media,
            "out_dir": str(args.out_dir),
            "times": {key: round(value, 3) for key, value in times.items()},
            "outputs": outputs,
            "visual_diversity": diversity,
        },
        "signals": signals,
        "agent_instruction": "The frames are evidence for visual review; inspect them directly.",
    }


def tail_doctor(args: argparse.Namespace) -> dict[str, Any]:
    ensure_tool("ffmpeg")
    ensure_tool("ffprobe")
    args.out_dir.mkdir(parents=True, exist_ok=True)
    media = compact_media(args.media)
    duration = as_float(media.get("duration")) if media else None
    if duration is None or duration <= 0:
        raise RuntimeError("could not read positive media duration")
    start = max(duration - args.tail_seconds, 0)
    length = duration - start

    black_log = args.out_dir / "blackdetect.log"
    freeze_log = args.out_dir / "freezedetect.log"
    framemd5 = args.out_dir / "tail_framemd5.txt"
    contact = args.out_dir / "tail_contact.jpg"

    proc = run(
        [
            "ffmpeg",
            "-hide_banner",
            "-ss",
            f"{start:.3f}",
            "-i",
            str(args.media),
            "-t",
            f"{length:.3f}",
            "-vf",
            "blackdetect=d=0.15:pic_th=0.98",
            "-an",
            "-f",
            "null",
            "-",
        ]
    )
    black_log.write_text(proc.stdout + proc.stderr, encoding="utf-8")

    proc = run(
        [
            "ffmpeg",
            "-hide_banner",
            "-ss",
            f"{start:.3f}",
            "-i",
            str(args.media),
            "-t",
            f"{length:.3f}",
            "-vf",
            "freezedetect=n=0.003:d=1.0",
            "-an",
            "-f",
            "null",
            "-",
        ]
    )
    freeze_log.write_text(proc.stdout + proc.stderr, encoding="utf-8")

    run_checked(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-ss",
            f"{start:.3f}",
            "-i",
            str(args.media),
            "-t",
            f"{length:.3f}",
            "-an",
            "-vf",
            "fps=1",
            "-f",
            "framemd5",
            str(framemd5),
        ]
    )
    run_checked(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-ss",
            f"{start:.3f}",
            "-i",
            str(args.media),
            "-t",
            f"{length:.3f}",
            "-vf",
            "fps=1,scale=320:-1:flags=lanczos,tile=5x5",
            "-frames:v",
            "1",
            str(contact),
        ]
    )

    hashes = [
        line.split(",")[-1].strip()
        for line in framemd5.read_text(encoding="utf-8").splitlines()
        if line and not line.startswith("#")
    ]
    signals: list[dict[str, Any]] = []
    black_text = black_log.read_text(encoding="utf-8", errors="replace")
    freeze_text = freeze_log.read_text(encoding="utf-8", errors="replace")
    if "black_start" in black_text:
        signals.append(
            signal(
                "tail_visual",
                "Blackdetect reported black frames in the inspected tail.",
                evidence={"log": str(black_log)},
                investigate="Open the tail contact sheet and decide whether the black segment is intentional.",
            )
        )
    if "freeze_start" in freeze_text:
        signals.append(
            signal(
                "tail_visual",
                "Freezedetect reported a frozen segment in the inspected tail.",
                evidence={"log": str(freeze_log)},
                investigate="Check whether the final shot is intentionally held or an accidental freeze.",
            )
        )
    if len(hashes) >= 3 and len(set(hashes)) <= 1:
        signals.append(
            signal(
                "tail_visual",
                "Sampled tail frame hashes are static.",
                evidence={"sampled_frames": len(hashes), "unique_hashes": len(set(hashes))},
                investigate="Inspect whether the video has a frozen or audio-only ending.",
            )
        )

    return {
        "doctor": "tail",
        "artifact": str(args.media),
        "summary": {
            "media": media,
            "tail_start": round(start, 3),
            "tail_length": round(length, 3),
            "sampled_frames": len(hashes),
            "unique_frame_hashes": len(set(hashes)),
            "logs": {
                "blackdetect": str(black_log),
                "freezedetect": str(freeze_log),
                "framemd5": str(framemd5),
                "contact": str(contact),
            },
        },
        "signals": signals,
        "agent_instruction": "Use tail signals to guide visual/audio inspection; do not use them as verdicts.",
    }


def lint_doctor(args: argparse.Namespace) -> dict[str, Any]:
    signals: list[dict[str, Any]] = []
    logs: list[dict[str, Any]] = []
    total_warnings = 0
    total_errors = 0
    warning_lines: list[str] = []
    error_lines: list[str] = []

    for path in args.logs:
        text = path.read_text(encoding="utf-8", errors="replace")
        lower = text.lower()
        lines = text.splitlines()
        warning_sample = [
            line.strip()
            for line in lines
            if ("⚠" in line or "warning" in line.lower())
            and not (
                "⚠" not in line
                and re.search(r"\b\d+\s+warning(?:s|\(s\))?\b", line.lower())
            )
        ]
        error_sample = [
            line.strip()
            for line in lines
            if ("✖" in line or "error" in line.lower())
            and not (
                "✖" not in line
                and re.search(r"\b\d+\s+error(?:s|\(s\))?\b", line.lower())
            )
        ]
        warnings = len(warning_sample)
        errors = len(error_sample)
        total_warnings += warnings
        total_errors += errors
        warning_lines.extend(warning_sample)
        error_lines.extend(error_sample)
        logs.append({"path": str(path), "warnings": warnings, "errors": errors})
        if "continuing render despite lint issues" in lower:
            signals.append(
                signal(
                    "lint_disposition",
                    "Render continued despite lint issues.",
                    level="strong_signal",
                    evidence={"log": str(path)},
                    investigate="Record why continuing was acceptable, or revise/split/fix the composition and rerun lint.",
                )
            )
        for term in ("composition_file_too_large", "timeline_track_too_dense"):
            if term in lower:
                signals.append(
                    signal(
                        "lint_structure",
                        f"Lint reported {term}.",
                        evidence={"log": str(path), "term": term},
                        investigate="Split dense compositions or document why the warning is acceptable for this render.",
                    )
                )

    disposition = None
    if args.disposition:
        if args.disposition.exists():
            disposition_text = args.disposition.read_text(encoding="utf-8", errors="replace").lower()
            disposition = {"path": str(args.disposition), "exists": True}
            if not any(term in disposition_text for term in ("fixed", "revised", "accepted", "intentional", "blocked")):
                signals.append(
                    signal(
                        "lint_disposition",
                        "Lint disposition file exists but does not clearly say fixed, revised, accepted, intentional, or blocked.",
                        evidence=disposition,
                        investigate="Write a concise warning-by-warning disposition before promotion.",
                    )
                )
        else:
            disposition = {"path": str(args.disposition), "exists": False}
    if (total_warnings or total_errors) and (not disposition or not disposition.get("exists")):
        signals.append(
            signal(
                "lint_disposition",
                "Lint warnings/errors exist without a disposition file.",
                level="strong_signal",
                evidence={"warnings": total_warnings, "errors": total_errors},
                investigate="Fix the lint issues or save a warning disposition before promoting the final.",
            )
        )
    if total_errors:
        signals.append(
            signal(
                "lint_errors",
                "Lint reported errors.",
                level="strong_signal",
                evidence={"errors": total_errors, "sample": error_lines[:8]},
                investigate="Treat lint errors as blockers unless the renderer/linter bug is documented.",
            )
        )
    elif total_warnings:
        signals.append(
            signal(
                "lint_warnings",
                "Lint reported warnings.",
                evidence={"warnings": total_warnings, "sample": warning_lines[:8]},
                investigate="Warnings are not automatic failures, but they must be inspected and dispositioned.",
            )
        )

    return {
        "doctor": "lint",
        "artifact": ", ".join(str(path) for path in args.logs),
        "summary": {
            "logs": logs,
            "total_warnings": total_warnings,
            "total_errors": total_errors,
            "disposition": disposition,
        },
        "signals": signals,
        "agent_instruction": (
            "Use lint signals to decide whether to fix, split, accept with reason, or block; "
            "do not silently continue from lint warnings."
        ),
    }


def parse_volumedetect(text: str) -> dict[str, float | None]:
    result: dict[str, float | None] = {"mean_volume_db": None, "max_volume_db": None}
    mean = re.search(r"mean_volume:\s*(-?\d+(?:\.\d+)?)\s*dB", text)
    peak = re.search(r"max_volume:\s*(-?\d+(?:\.\d+)?)\s*dB", text)
    if mean:
        result["mean_volume_db"] = float(mean.group(1))
    if peak:
        result["max_volume_db"] = float(peak.group(1))
    return result


def parse_ebur128(text: str) -> dict[str, float | None]:
    result: dict[str, float | None] = {
        "integrated_lufs": None,
        "lra_lu": None,
        "true_peak_dbfs": None,
    }
    summaries = [match.start() for match in re.finditer(r"Integrated loudness:", text)]
    if summaries:
        tail = text[summaries[-1] :]
    else:
        tail = text
    integrated = re.search(r"I:\s*(-?\d+(?:\.\d+)?)\s*LUFS", tail)
    lra = re.search(r"LRA:\s*(-?\d+(?:\.\d+)?)\s*LU", tail)
    true_peak = re.search(r"Peak:\s*(-?\d+(?:\.\d+)?)\s*dBFS", tail)
    if integrated:
        result["integrated_lufs"] = float(integrated.group(1))
    if lra:
        result["lra_lu"] = float(lra.group(1))
    if true_peak:
        result["true_peak_dbfs"] = float(true_peak.group(1))
    return result


PROCEDURAL_AUDIO_PATTERNS = [
    (r"\bnp\.sin\b|\bnumpy\b", "numpy_synthesis"),
    (r"\brng\.normal\b|\bstandard_normal\b|\brandom\.normal\b", "random_noise"),
    (r"\bAudioArrayClip\b", "audio_array_clip"),
    (r"\bwave\.open\b", "wave_writer"),
    (r"\banoisesrc\b|\baevalsrc\b", "ffmpeg_synthetic_source"),
    (r"\bprocedural (?:score|music|audio|bed|stem)", "procedural_claim"),
    (r"\briser\b|\bsub drop\b|\bimpact hit\b|\bui tick\b", "sfx_claim"),
]


def scan_audio_artifacts(paths: list[Path], *, max_bytes: int = 512_000) -> dict[str, Any]:
    files: list[dict[str, Any]] = []
    totals: dict[str, int] = {}
    suffixes = {".py", ".md", ".json", ".html", ".txt", ".log", ".mlt"}
    expanded: list[Path] = []
    for path in paths:
        if path.is_dir():
            for child in path.rglob("*"):
                if child.is_file() and child.suffix.lower() in suffixes:
                    expanded.append(child)
        elif path.is_file():
            expanded.append(path)
    for path in sorted(set(expanded)):
        try:
            if path.stat().st_size > max_bytes:
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        matches: dict[str, int] = {}
        for pattern, name in PROCEDURAL_AUDIO_PATTERNS:
            count = len(re.findall(pattern, text, flags=re.IGNORECASE))
            if count:
                matches[name] = count
                totals[name] = totals.get(name, 0) + count
        if matches:
            files.append({"path": str(path), "matches": matches})
    return {"files": files[:80], "total_files_with_matches": len(files), "totals": totals}


def ffmpeg_filter_report(media: Path, audio_filter: str) -> subprocess.CompletedProcess[str]:
    return run(
        [
            "ffmpeg",
            "-hide_banner",
            "-i",
            str(media),
            "-vn",
            "-af",
            audio_filter,
            "-f",
            "null",
            "-",
        ]
    )


def export_audio_snippet(media: Path, out: Path, start: float, duration: float) -> None:
    run_checked(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-ss",
            f"{max(0.0, start):.3f}",
            "-i",
            str(media),
            "-t",
            f"{max(0.1, duration):.3f}",
            "-vn",
            "-ac",
            "2",
            "-ar",
            "48000",
            "-c:a",
            "pcm_s16le",
            str(out),
        ]
    )


def manifest_audio_overlap_review(
    manifests: list[Path],
    *,
    root: Path,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[tuple[float, float]]]:
    signals: list[dict[str, Any]] = []
    entries: list[dict[str, Any]] = []
    snippet_ranges: list[tuple[float, float]] = []

    for manifest in manifests:
        try:
            items = load_manifest(manifest)
        except Exception as exc:  # noqa: BLE001 - diagnostic report
            signals.append(
                signal(
                    "source_audio_manifest",
                    "Audio overlap manifest could not be read.",
                    evidence={"manifest": str(manifest), "error": str(exc)},
                    investigate="Fix JSON shape or pass the intended sources/music manifest.",
                )
            )
            continue

        for idx, item in enumerate(items):
            source_id = str(item.get("id") or item.get("name") or f"source_{idx}")
            role_value = str(item.get("role") or item.get("type") or "").lower()
            role_text = manifest_text_blob(item.get("role"), item.get("type"))
            local_value = get_source_path(item)
            compact: dict[str, Any] | None = None
            if local_value:
                path = resolve_path(local_value, root, manifest.parent)
                if path.exists():
                    try:
                        compact = compact_media(path)
                    except Exception:  # noqa: BLE001 - optional evidence only
                        compact = None

            ranges = get_ranges(item)
            if not ranges:
                ranges = [{}]
            for ridx, selected in enumerate(ranges):
                audio_meta = source_audio_metadata(item, selected)
                text_blob = manifest_text_blob(item, selected)
                timeline = selected_timeline_range(selected)
                if timeline is None:
                    parsed = parse_time_ranges_from_text(text_blob)
                    timeline = parsed[0] if parsed else None

                is_source_audio = (
                    role_value.startswith("source")
                    or "source_audio" in role_text
                    or "ambience" in role_text
                    or "dialogue" in role_text
                    or bool(audio_meta["audio_role"])
                )
                has_overlap_smell = has_any_term(text_blob, SOURCE_AUDIO_CONFLICT_TERMS)
                if is_source_audio or has_overlap_smell:
                    entries.append(
                        {
                            "manifest": str(manifest),
                            "id": source_id,
                            "range": ridx if selected else None,
                            "role": item.get("role"),
                            "audio_role": audio_meta["audio_role"],
                            "overlap_policy": audio_meta["overlap_policy"],
                            "timeline_range": list(timeline) if timeline else None,
                            "audio_streams": compact.get("audio_streams") if compact else None,
                        }
                    )
                if timeline and (is_source_audio or has_overlap_smell):
                    snippet_ranges.append(timeline)
                if compact and compact.get("audio_streams") and is_source_audio and not audio_meta["audio_role"]:
                    signals.append(
                        signal(
                            "source_audio_role",
                            "Manifest source-audio entry lacks audio_role metadata.",
                            evidence={"manifest": str(manifest), "id": source_id},
                            investigate=(
                                "Classify it before mixing: silent_or_mute, ambience_keep, dialogue_keep, "
                                "music_only, mixed_music_speech, or needs_separation."
                            ),
                        )
                    )

                if audio_meta["audio_role"] in {"music_only", "dialogue_keep", "mixed_music_speech", "needs_separation"} and not audio_meta[
                    "overlap_policy"
                ]:
                    signals.append(
                        signal(
                            "source_audio_overlap",
                            "Source audio has a foreground speech/music role but no overlap policy.",
                            evidence={
                                "manifest": str(manifest),
                                "id": source_id,
                                "audio_role": audio_meta["audio_role"],
                                "timeline_range": list(timeline) if timeline else None,
                            },
                            investigate=(
                                "Decide whether source audio is source-only, muted, ducked, separated, "
                                "or kept as foreground while new narration/music exits."
                            ),
                        )
                    )

                if has_overlap_smell and not has_any_term(
                    text_blob,
                    SOURCE_AUDIO_RESOLUTION_TERMS,
                ):
                    signals.append(
                        signal(
                            "source_audio_overlap",
                            "Manifest text suggests source audio is mixed under music or narration without a mitigation.",
                            evidence={
                                "manifest": str(manifest),
                                "id": source_id,
                                "timeline_range": list(timeline) if timeline else None,
                            },
                            investigate=(
                                "Verify this is true ambience with no music/speech, or revise to mute, duck, separate, "
                                "or keep source audio as the only foreground audio."
                            ),
                        )
                    )

    return entries, signals, snippet_ranges


def sound_design_overlap_review(paths: list[Path]) -> tuple[list[dict[str, Any]], list[tuple[float, float]]]:
    signals: list[dict[str, Any]] = []
    snippet_ranges: list[tuple[float, float]] = []
    for path in paths:
        if not path.exists():
            signals.append(
                signal(
                    "sound_design",
                    "Referenced sound design file does not exist.",
                    evidence={"path": str(path)},
                    investigate="Pass the current sound_design.md for audio-overlap review.",
                )
            )
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        lower = text.lower()
        for line in lower.splitlines():
            if has_any_term(line, SOURCE_AUDIO_CONFLICT_TERMS) or (
                "source audio" in line and ("music" in line or "narration" in line or "dialogue" in line)
            ):
                snippet_ranges.extend(parse_time_ranges_from_text(line))
        if "source audio policy" not in lower and ("source audio" in lower or "source-audio" in lower):
            signals.append(
                signal(
                    "source_audio_policy",
                    "Sound design mentions source audio but lacks a clear Source Audio Policy section/table.",
                    evidence={"path": str(path)},
                    investigate=(
                        "Add a table with time range, source file, audio_role, keep reason, overlap policy, processing, and review snippet."
                    ),
                )
            )
        if has_any_term(lower, SOURCE_AUDIO_CONFLICT_TERMS) and not has_any_term(lower, SOURCE_AUDIO_RESOLUTION_TERMS):
            signals.append(
                signal(
                    "source_audio_overlap",
                    "Sound design suggests source audio is layered under music or narration without clear mitigation.",
                    evidence={"path": str(path)},
                    investigate=(
                        "Do not stack source music/speech with new music/narration. Mute, duck, isolate, or make source audio foreground."
                    ),
                )
            )
    return signals, snippet_ranges


def audio_doctor(args: argparse.Namespace) -> dict[str, Any]:
    ensure_tool("ffmpeg")
    ensure_tool("ffprobe")
    raw = run_ffprobe(args.media)
    summary = media_summary(args.media, raw)
    signals: list[dict[str, Any]] = []
    logs: dict[str, str] = {}
    snippets: dict[str, str] = {}
    audio_streams = summary.get("audio_streams") or []
    duration = as_float(summary.get("duration")) or 0.0
    if not audio_streams:
        signals.append(
            signal(
                "audio_stream",
                "No audio stream found.",
                level="strong_signal",
                investigate="Confirm whether the brief allowed a silent video; otherwise remux or rebuild audio.",
            )
        )
        return {
            "doctor": "audio",
            "artifact": str(args.media),
            "summary": {"media": summary, "logs": logs, "snippets": snippets},
            "signals": signals,
            "agent_instruction": "No audio was available to investigate.",
        }

    out_dir = args.out_dir
    if out_dir:
        out_dir.mkdir(parents=True, exist_ok=True)

    vol_proc = ffmpeg_filter_report(args.media, "volumedetect")
    full_volume = parse_volumedetect(vol_proc.stderr + vol_proc.stdout)
    if out_dir:
        log = out_dir / "audio_volumedetect.log"
        log.write_text(vol_proc.stdout + vol_proc.stderr, encoding="utf-8")
        logs["volumedetect"] = str(log)

    high_proc = ffmpeg_filter_report(args.media, "highpass=f=6000,volumedetect")
    high_volume = parse_volumedetect(high_proc.stderr + high_proc.stdout)
    if out_dir:
        log = out_dir / "audio_highpass_6000_volumedetect.log"
        log.write_text(high_proc.stdout + high_proc.stderr, encoding="utf-8")
        logs["highpass_6000_volumedetect"] = str(log)

    low_proc = ffmpeg_filter_report(args.media, "lowpass=f=140,volumedetect")
    low_volume = parse_volumedetect(low_proc.stderr + low_proc.stdout)
    if out_dir:
        log = out_dir / "audio_lowpass_140_volumedetect.log"
        log.write_text(low_proc.stdout + low_proc.stderr, encoding="utf-8")
        logs["lowpass_140_volumedetect"] = str(log)

    ebu_proc = ffmpeg_filter_report(args.media, "ebur128=peak=true")
    loudness = parse_ebur128(ebu_proc.stderr + ebu_proc.stdout)
    if out_dir:
        log = out_dir / "audio_ebur128.log"
        log.write_text(ebu_proc.stdout + ebu_proc.stderr, encoding="utf-8")
        logs["ebur128"] = str(log)

    high_delta = None
    if full_volume["mean_volume_db"] is not None and high_volume["mean_volume_db"] is not None:
        high_delta = high_volume["mean_volume_db"] - full_volume["mean_volume_db"]
    low_delta = None
    if full_volume["mean_volume_db"] is not None and low_volume["mean_volume_db"] is not None:
        low_delta = low_volume["mean_volume_db"] - full_volume["mean_volume_db"]

    if full_volume["max_volume_db"] is not None and full_volume["max_volume_db"] > -1.0:
        signals.append(
            signal(
                "audio_headroom",
                "Peak level is very close to clipping.",
                evidence={"max_volume_db": full_volume["max_volume_db"]},
                investigate="Listen around loud hits and consider lowering/limiting the mix with more headroom.",
            )
        )
    if loudness["integrated_lufs"] is not None and not (-28 <= loudness["integrated_lufs"] <= -12):
        signals.append(
            signal(
                "audio_loudness",
                "Integrated loudness is outside a broad review range for edited video.",
                evidence={"integrated_lufs": loudness["integrated_lufs"]},
                investigate="Check whether the target platform/genre justifies this level.",
            )
        )
    if loudness["lra_lu"] is not None and loudness["lra_lu"] < 3.0 and duration >= 45:
        signals.append(
            signal(
                "audio_dynamics",
                "Loudness range is very low for a medium/long polished edit.",
                evidence={"lra_lu": loudness["lra_lu"], "duration": duration},
                investigate="Listen for a flat bed; revise section dynamics if the genre needs a stronger arc.",
            )
        )
    if high_delta is not None and high_delta > -14:
        signals.append(
            signal(
                "audio_high_band",
                "High-frequency band is relatively strong compared with the full mix.",
                evidence={"highpass_6000_mean_minus_full_mean_db": round(high_delta, 2)},
                investigate="Listen for hiss, sizzle, harsh UI ticks, codec artifacts, or noisy risers.",
            )
        )
    if low_delta is not None and low_delta > -5 and duration >= 45:
        signals.append(
            signal(
                "audio_low_band",
                "Low-frequency band dominates the mix.",
                evidence={"lowpass_140_mean_minus_full_mean_db": round(low_delta, 2)},
                investigate="Listen for sub-pulse monotony or repeated boom hits replacing real music.",
            )
        )

    scan_paths = args.scan_path or []
    artifact_scan = scan_audio_artifacts(scan_paths) if scan_paths else {"files": [], "total_files_with_matches": 0, "totals": {}}
    totals = artifact_scan.get("totals", {})
    if totals:
        level = "strong_signal" if duration >= 45 and any(key in totals for key in ("random_noise", "procedural_claim")) else "review"
        signals.append(
            signal(
                "procedural_audio_artifacts",
                "Text artifacts suggest procedural or synthetic audio was used.",
                level=level,
                evidence={"totals": totals, "matched_files": artifact_scan.get("total_files_with_matches")},
                investigate=(
                    "Confirm whether generated stems are only short SFX/accent layers or whether they became the main music bed. "
                    "For polished long videos, prefer AI-generated music or downloaded relevant/authorized music as the main bed."
                ),
            )
        )

    source_audio_review_entries: list[dict[str, Any]] = []
    source_audio_snippet_ranges: list[tuple[float, float]] = []
    manifest_paths = list(args.sources_manifest or []) + list(args.music_manifest or [])
    if manifest_paths:
        root = args.root or Path.cwd()
        entries, manifest_signals, ranges = manifest_audio_overlap_review(manifest_paths, root=root)
        source_audio_review_entries.extend(entries)
        source_audio_snippet_ranges.extend(ranges)
        signals.extend(manifest_signals)
    if args.sound_design:
        sound_signals, ranges = sound_design_overlap_review(list(args.sound_design))
        source_audio_snippet_ranges.extend(ranges)
        signals.extend(sound_signals)

    if out_dir and source_audio_snippet_ranges and duration > 0:
        seen: set[tuple[int, int]] = set()
        for index, (start, end) in enumerate(source_audio_snippet_ranges, 1):
            start = max(0.0, min(start, max(duration - 0.1, 0.0)))
            length = max(0.1, min(end - start, args.snippet_seconds, duration - start))
            key = (round(start * 10), round(length * 10))
            if key in seen:
                continue
            seen.add(key)
            out = out_dir / f"source_overlap_{index:02d}_{start:.1f}s.wav"
            export_audio_snippet(args.media, out, start, length)
            snippets[f"source_overlap_{index:02d}_{start:.1f}s"] = str(out)
        if seen:
            signals.append(
                signal(
                    "source_audio_overlap_listening",
                    "Audio snippets were exported around documented source-audio overlap windows.",
                    level="info",
                    evidence={
                        key: value
                        for key, value in snippets.items()
                        if key.startswith("source_overlap_")
                    },
                    investigate=(
                        "Listen for stacked music beds, source commentary under new narration, or ambience that is actually speech/music."
                    ),
                )
            )

    if out_dir and duration > 0:
        points = {
            "opening": 0.0,
            "middle": max(0.0, duration / 2 - args.snippet_seconds / 2),
            "ending": max(0.0, duration - args.snippet_seconds),
        }
        if args.snippet_at:
            for index, start in enumerate(args.snippet_at, 1):
                points[f"custom_{index:02d}_{start:.1f}s"] = max(0.0, start)
        for name, start in points.items():
            out = out_dir / f"{name}.wav"
            export_audio_snippet(args.media, out, start, min(args.snippet_seconds, max(duration - start, 0.1)))
            snippets[name] = str(out)
        signals.append(
            signal(
                "listening_pass",
                "Audio snippets were exported for manual listening.",
                level="info",
                evidence=snippets,
                investigate="Listen to the snippets before promotion; technical metrics cannot judge taste or harshness.",
            )
        )

    return {
        "doctor": "audio",
        "artifact": str(args.media),
        "summary": {
            "media": summary,
            "full_volume": full_volume,
            "highpass_6000_volume": high_volume,
            "lowpass_140_volume": low_volume,
            "band_deltas_db": {
                "highpass_6000_mean_minus_full_mean": high_delta,
                "lowpass_140_mean_minus_full_mean": low_delta,
            },
            "loudness": loudness,
            "procedural_artifact_scan": artifact_scan,
            "source_audio_overlap_review": source_audio_review_entries,
            "logs": logs,
            "snippets": snippets,
        },
        "signals": signals,
        "agent_instruction": (
            "Use audio signals to guide listening and mix review; do not treat this report as a pass/fail verdict. "
            "If procedural audio is the main bed in a polished long video, consider AI-generated music or downloaded relevant/authorized music instead. "
            "If source audio overlaps new music or narration, confirm it is intentional ambience or revise with mute/duck/source-only/separation."
        ),
    }


def probe_doctor(args: argparse.Namespace) -> dict[str, Any]:
    raw = run_ffprobe(args.media)
    summary = media_summary(args.media, raw)
    if args.raw:
        summary["raw_ffprobe"] = raw
    return {
        "doctor": "probe",
        "artifact": str(args.media),
        "summary": summary,
        "signals": [],
        "agent_instruction": "Compare these media facts to the brief and render reports.",
    }


def print_human(report: dict[str, Any]) -> None:
    print(f"doctor: {report['doctor']}")
    print(f"artifact: {report['artifact']}")
    print("summary:")
    print(json.dumps(report["summary"], indent=2, sort_keys=True))
    signals = report.get("signals") or []
    print(f"signals: {len(signals)}")
    for item in signals:
        print(f"- [{item.get('level')}] {item.get('topic')}: {item.get('message')}")
        if item.get("evidence"):
            print(f"  evidence: {json.dumps(item['evidence'], sort_keys=True)}")
        if item.get("investigate"):
            print(f"  investigate: {item['investigate']}")
    print(f"agent_instruction: {report['agent_instruction']}")


def add_common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--json", action="store_true", help="print JSON report")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    probe = sub.add_parser("probe", help="summarize a media file with ffprobe")
    probe.add_argument("media", type=Path)
    probe.add_argument("--raw", action="store_true", help="include raw ffprobe JSON")
    add_common(probe)

    captions = sub.add_parser("captions", help="investigate SRT/ASS caption timing and metadata")
    captions.add_argument("captions", type=Path)
    captions.add_argument("--duration", type=float, help="media duration in seconds")
    captions.add_argument("--media", type=Path, help="final rendered media file")
    captions.add_argument("--narration", type=Path, help="narration audio file")
    captions.add_argument(
        "--output-language",
        help="expected authored viewer-facing language, e.g. English or Chinese",
    )
    captions.add_argument(
        "--voice-style",
        action="append",
        default=[],
        help="ASS style name used for voice subtitles; repeatable",
    )
    captions.add_argument(
        "--flag-term",
        action="append",
        default=[],
        help="viewer-facing term to flag for review; repeatable",
    )
    captions.add_argument(
        "--voice-after-narration-signal",
        type=float,
        default=2.0,
        help="seconds after narration before the doctor emits an investigation signal",
    )
    captions.add_argument(
        "--post-caption-tail-signal",
        type=float,
        default=10.0,
        help="seconds of media after the last voice caption before emitting an authored-coverage signal",
    )
    captions.add_argument(
        "--voice-media-coverage-signal",
        type=float,
        default=0.75,
        help="voice-caption coverage ratio below which the doctor emits an authored-coverage signal",
    )
    captions.add_argument(
        "--narration-media-tail-signal",
        type=float,
        default=12.0,
        help="seconds of media after narration duration before emitting an authored-coverage signal",
    )
    captions.add_argument(
        "--expect-authored-coverage",
        action="store_true",
        help=(
            "emit media-coverage signals when the brief expects narration/intertitles "
            "to carry the story; omit for spot captions or intentionally partial captions"
        ),
    )
    captions.add_argument("--review-dir", type=Path, help="directory of final-path review frames")
    add_common(captions)

    sources = sub.add_parser("sources", help="investigate a sources/music_sources manifest")
    sources.add_argument("manifest", type=Path)
    sources.add_argument("--root", type=Path, default=Path.cwd())
    add_common(sources)

    frames = sub.add_parser("frames", help="generate review frames/contact sheets")
    frames.add_argument("media", type=Path)
    frames.add_argument("out_dir", type=Path)
    frames.add_argument("--interval", type=int, default=2)
    frames.add_argument(
        "--final-act-fraction",
        type=float,
        default=0.2,
        help="fraction of the ending to sample for dense final-act review; default 0.2",
    )
    add_common(frames)

    tail = sub.add_parser("tail", help="investigate the final video tail")
    tail.add_argument("media", type=Path)
    tail.add_argument("out_dir", type=Path)
    tail.add_argument("--tail-seconds", type=float, default=10.0)
    add_common(tail)

    audio = sub.add_parser("audio", help="investigate final audio quality signals")
    audio.add_argument("media", type=Path)
    audio.add_argument("out_dir", type=Path, nargs="?", help="optional directory for logs and listening snippets")
    audio.add_argument(
        "--scan-path",
        type=Path,
        action="append",
        default=[],
        help="script/manifest/project path to scan for procedural-audio evidence; repeatable",
    )
    audio.add_argument(
        "--sources-manifest",
        type=Path,
        action="append",
        default=[],
        help="sources.json to inspect for source-audio roles and overlap policies; repeatable",
    )
    audio.add_argument(
        "--music-manifest",
        type=Path,
        action="append",
        default=[],
        help="music_sources.json to inspect for source-audio/new-music overlap; repeatable",
    )
    audio.add_argument(
        "--sound-design",
        type=Path,
        action="append",
        default=[],
        help="sound_design.md to inspect for source-audio policy and overlap language; repeatable",
    )
    audio.add_argument("--root", type=Path, default=Path.cwd(), help="root for resolving manifest paths")
    audio.add_argument("--snippet-seconds", type=float, default=5.0)
    audio.add_argument(
        "--snippet-at",
        type=float,
        action="append",
        default=[],
        help="additional snippet start time in seconds; repeatable",
    )
    add_common(audio)

    lint = sub.add_parser("lint", help="investigate renderer/linter logs and warning disposition")
    lint.add_argument("logs", type=Path, nargs="+")
    lint.add_argument("--disposition", type=Path, help="file documenting warning/error disposition")
    add_common(lint)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    for attr in ("media", "captions", "manifest"):
        path = getattr(args, attr, None)
        if path is not None and not path.exists():
            print(f"error: file not found: {path}", file=sys.stderr)
            return 2
    for path in getattr(args, "logs", []) or []:
        if not path.exists():
            print(f"error: file not found: {path}", file=sys.stderr)
            return 2
    if getattr(args, "voice_style", None) == []:
        args.voice_style = ["Caption", "Narration", "Subtitle"]
    if getattr(args, "flag_term", None) == []:
        args.flag_term = DEFAULT_FLAG_TERMS.copy()

    try:
        if args.command == "probe":
            report = probe_doctor(args)
        elif args.command == "captions":
            report = caption_doctor(args)
        elif args.command == "sources":
            report = sources_doctor(args)
        elif args.command == "frames":
            report = frames_doctor(args)
        elif args.command == "tail":
            report = tail_doctor(args)
        elif args.command == "audio":
            report = audio_doctor(args)
        elif args.command == "lint":
            report = lint_doctor(args)
        else:
            raise RuntimeError(f"unknown command: {args.command}")
    except Exception as exc:  # noqa: BLE001 - command-line diagnostic
        print(f"error: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print_human(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
