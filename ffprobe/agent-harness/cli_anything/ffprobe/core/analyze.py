"""FFprobe analysis core — structured media file probing."""

import subprocess
import json
import os
from typing import Any, Dict, List, Optional


def _run_ffprobe(args: List[str], timeout: int = 60) -> Dict[str, Any]:
    """Run ffprobe with given args and return parsed JSON or raw output."""
    cmd = ["ffprobe", "-v", "quiet"] + args
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        if result.returncode != 0:
            stderr = result.stderr.strip()
            raise RuntimeError(f"ffprobe failed (exit {result.returncode}): {stderr}")
        return {"ok": True, "stdout": result.stdout, "stderr": result.stderr}
    except FileNotFoundError:
        raise RuntimeError("ffprobe not found. Install ffmpeg: apt install ffmpeg")
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"ffprobe timed out after {timeout}s")


def _probe_json(
    file: str, extra_show: Optional[List[str]] = None, timeout: int = 60
) -> Dict[str, Any]:
    """Run ffprobe with JSON output and return parsed dict."""
    if not os.path.isfile(file):
        raise FileNotFoundError(f"File not found: {file}")
    shows = ["-show_format", "-show_streams"]
    if extra_show:
        shows.extend(extra_show)
    args = ["-print_format", "json"] + shows + [file]
    res = _run_ffprobe(args, timeout=timeout)
    try:
        return json.loads(res["stdout"])
    except json.JSONDecodeError:
        raise RuntimeError("Failed to parse ffprobe JSON output")


def analyze_info(file: str) -> Dict[str, Any]:
    """Full probe with JSON output — format, streams, all metadata."""
    return _probe_json(file)


def analyze_streams(file: str) -> List[Dict[str, Any]]:
    """List streams only."""
    data = _probe_json(file)
    return data.get("streams", [])


def analyze_format(file: str) -> Dict[str, Any]:
    """Show container format info."""
    data = _probe_json(file)
    return data.get("format", {})


def analyze_codec(file: str) -> List[Dict[str, Any]]:
    """Show codec details for all streams."""
    streams = analyze_streams(file)
    result = []
    for s in streams:
        result.append(
            {
                "index": s.get("index"),
                "codec_name": s.get("codec_name"),
                "codec_long_name": s.get("codec_long_name"),
                "codec_type": s.get("codec_type"),
                "codec_tag_string": s.get("codec_tag_string"),
                "profile": s.get("profile"),
                "level": s.get("level"),
                "pix_fmt": s.get("pix_fmt"),
                "sample_rate": s.get("sample_rate"),
                "channels": s.get("channels"),
                "bit_rate": s.get("bit_rate"),
                "width": s.get("width"),
                "height": s.get("height"),
                "r_frame_rate": s.get("r_frame_rate"),
            }
        )
    return result


def analyze_chapters(file: str) -> List[Dict[str, Any]]:
    """List chapters."""
    data = _probe_json(file, extra_show=["-show_chapters"])
    chapters = data.get("chapters", [])
    result = []
    for ch in chapters:
        result.append(
            {
                "id": ch.get("id"),
                "time_base": ch.get("time_base"),
                "start": ch.get("start"),
                "start_time": ch.get("start_time"),
                "end": ch.get("end"),
                "end_time": ch.get("end_time"),
                "title": ch.get("tags", {}).get("title", ""),
            }
        )
    return result


def analyze_packets(file: str, count: int = 50) -> List[Dict[str, Any]]:
    """Show packet info with optional limit."""
    if not os.path.isfile(file):
        raise FileNotFoundError(f"File not found: {file}")
    args = [
        "-print_format",
        "json",
        "-show_packets",
        "-read_intervals",
        f"%+#{count}",
        file,
    ]
    res = _run_ffprobe(args, timeout=120)
    try:
        data = json.loads(res["stdout"])
    except json.JSONDecodeError:
        raise RuntimeError("Failed to parse packet JSON output")
    return data.get("packets", [])


def analyze_frames(file: str, count: int = 50) -> List[Dict[str, Any]]:
    """Show frame info with optional limit."""
    if not os.path.isfile(file):
        raise FileNotFoundError(f"File not found: {file}")
    args = [
        "-print_format",
        "json",
        "-show_frames",
        "-read_intervals",
        f"%+#{count}",
        file,
    ]
    res = _run_ffprobe(args, timeout=120)
    try:
        data = json.loads(res["stdout"])
    except json.JSONDecodeError:
        raise RuntimeError("Failed to parse frame JSON output")
    return data.get("frames", [])


def analyze_thumbnails(file: str) -> List[Dict[str, Any]]:
    """Extract thumbnail timestamps by finding keyframes in video streams."""
    if not os.path.isfile(file):
        raise FileNotFoundError(f"File not found: {file}")
    args = [
        "-print_format",
        "json",
        "-show_frames",
        "-select_streams",
        "v:0",
        "-show_entries",
        "frame=pict_type,pts_time,key_frame",
        file,
    ]
    res = _run_ffprobe(args, timeout=120)
    try:
        data = json.loads(res["stdout"])
    except json.JSONDecodeError:
        raise RuntimeError("Failed to parse frame JSON output")
    frames = data.get("frames", [])
    thumbnails = []
    for f in frames:
        if f.get("key_frame") == 1 or f.get("pict_type") == "I":
            thumbnails.append(
                {
                    "pts_time": f.get("pts_time"),
                    "pict_type": f.get("pict_type"),
                    "key_frame": f.get("key_frame"),
                }
            )
    return thumbnails


def batch_analyze(files: List[str]) -> List[Dict[str, Any]]:
    """Analyze multiple files, returning results per file."""
    results = []
    for f in files:
        try:
            info = analyze_info(f)
            results.append(
                {
                    "file": f,
                    "ok": True,
                    "format": info.get("format", {}),
                    "stream_count": len(info.get("streams", [])),
                }
            )
        except Exception as e:
            results.append({"file": f, "ok": False, "error": str(e)})
    return results


def compare(file1: str, file2: str) -> Dict[str, Any]:
    """Compare two media files side by side."""
    data1 = _probe_json(file1)
    data2 = _probe_json(file2)
    fmt1 = data1.get("format", {})
    fmt2 = data2.get("format", {})
    streams1 = data1.get("streams", [])
    streams2 = data2.get("streams", [])

    def _stream_summary(streams):
        return [
            {"type": s.get("codec_type"), "codec": s.get("codec_name")} for s in streams
        ]

    comparison = {
        "file1": {
            "path": file1,
            "format_name": fmt1.get("format_name"),
            "duration": fmt1.get("duration"),
            "size": fmt1.get("size"),
            "bit_rate": fmt1.get("bit_rate"),
            "streams": _stream_summary(streams1),
        },
        "file2": {
            "path": file2,
            "format_name": fmt2.get("format_name"),
            "duration": fmt2.get("duration"),
            "size": fmt2.get("size"),
            "bit_rate": fmt2.get("bit_rate"),
            "streams": _stream_summary(streams2),
        },
    }
    return comparison
