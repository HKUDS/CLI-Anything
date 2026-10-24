"""Build VLC command-line fragments from a job spec.

Pure functions — no subprocess, no VLC required. These construct the ``--sout``
streaming-output chains and the snapshot arguments that ``utils/vlc_backend.py`` feeds
to the real ``vlc`` binary.

VLC expects its *own* codec identifiers inside ``transcode{...}`` (e.g. ``s16l`` for PCM
WAV, ``mp4a`` for AAC). To keep the agent interface human-friendly, this module maps
common user-facing names (``wav``, ``aac``, ``h264`` …) to the canonical VLC names and
maps an output *format* to the matching ``mux``. Unknown values raise ``ValueError`` so
the agent gets an actionable error instead of a silent empty output file.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

# Friendly audio codec name -> VLC codec name.
AUDIO_CODEC_ALIASES: Dict[str, Optional[str]] = {
    "wav": "s16l",
    "pcm": "s16l",
    "pcm_s16le": "s16l",
    "mp3": "mp3",
    "aac": "mp4a",
    "ac3": "a52",
    "eac3": "eac3",
    "flac": "flac",
    "opus": "opus",
    "vorbis": "vorbis",
    "ogg": "vorbis",
    "mp2": "mp2",
    "none": None,
    "copy": None,
}

# Friendly video codec name -> VLC codec name.
VIDEO_CODEC_ALIASES: Dict[str, Optional[str]] = {
    "h264": "h264",
    "x264": "h264",
    "hevc": "hevc",
    "h265": "hevc",
    "av1": "av1",
    "mpeg4": "mp4v",
    "mp4v": "mp4v",
    "mp4": "mp4v",
    "mpeg2": "mp2v",
    "mpeg2video": "mp2v",
    "vp8": "VP8",
    "vp9": "VP9",
    "theora": "theora",
    "none": None,
    "copy": None,
}

# Output format -> VLC mux name.
MUX_BY_FORMAT: Dict[str, str] = {
    "wav": "wav",
    "mp3": "mp3",
    "mp2": "ts",
    "aac": "mp4",
    "m4a": "mp4",
    "m4v": "mp4",
    "mp4": "mp4",
    "mov": "mp4",
    "flac": "flac",
    "opus": "ogg",
    "ogg": "ogg",
    "ogv": "ogg",
    "ac3": "ts",
    "eac3": "ts",
    "mkv": "mkv",
    "webm": "webm",
    "avi": "avi",
    "ts": "ts",
    "ps": "ps",
    "flv": "flv",
}

# Raw VLC names we accept verbatim (so advanced users can pass VLC-native ids).
_KNOWN_VLC_AUDIO = {"s16l", "mp3", "mp4a", "a52", "eac3", "flac", "opus", "vorbis", "mp2"}
_KNOWN_VLC_VIDEO = {"h264", "hevc", "av1", "mp4v", "mp2v", "VP8", "VP9", "theora"}


def resolve_audio_codec(name: Optional[str]) -> Optional[str]:
    if name is None:
        return None
    key = str(name).strip().lower()
    if key in AUDIO_CODEC_ALIASES:
        return AUDIO_CODEC_ALIASES[key]
    if key in _KNOWN_VLC_AUDIO:
        return key
    raise ValueError(
        f"Unknown audio codec '{name}'. Known: "
        + ", ".join(sorted(AUDIO_CODEC_ALIASES))
        + f". (VLC-native ids also allowed: {', '.join(sorted(_KNOWN_VLC_AUDIO))})"
    )


def resolve_video_codec(name: Optional[str]) -> Optional[str]:
    if name is None:
        return None
    key = str(name).strip().lower()
    if key in VIDEO_CODEC_ALIASES:
        return VIDEO_CODEC_ALIASES[key]
    if key in _KNOWN_VLC_VIDEO:
        return key
    raise ValueError(
        f"Unknown video codec '{name}'. Known: "
        + ", ".join(sorted(VIDEO_CODEC_ALIASES))
        + f". (VLC-native ids also allowed: {', '.join(sorted(_KNOWN_VLC_VIDEO))})"
    )


def resolve_mux(fmt: str) -> str:
    key = str(fmt).strip().lower()
    if key in MUX_BY_FORMAT:
        return MUX_BY_FORMAT[key]
    return key  # allow VLC-native mux names directly


def _transcode_block(job: Dict[str, Any]) -> str:
    """Return the ``transcode{...}`` fragment (possibly empty)."""
    t = job.get("transcode", {}) or {}
    params: List[str] = []
    # ``copy`` / ``none`` resolve to None — drop the param rather than emitting
    # a literal ``vcodec=None`` / ``acodec=None`` that VLC cannot parse.
    vcodec = resolve_video_codec(t["vcodec"]) if t.get("vcodec") else None
    if vcodec:
        params.append(f"vcodec={vcodec}")
    acodec = resolve_audio_codec(t["acodec"]) if t.get("acodec") else None
    if acodec:
        params.append(f"acodec={acodec}")
    if t.get("vbitrate"):
        params.append(f"vb={int(t['vbitrate'])}")
    if t.get("abitrate"):
        params.append(f"ab={int(t['abitrate'])}")
    scale = t.get("scale")
    if scale not in (None, 1.0, 1):
        params.append(f"scale={scale}")
    if t.get("width"):
        params.append(f"width={int(t['width'])}")
    if t.get("height"):
        params.append(f"height={int(t['height'])}")
    if t.get("fps"):
        params.append(f"fps={t['fps']}")
    if t.get("channels"):
        params.append(f"channels={int(t['channels'])}")
    if t.get("samplerate"):
        params.append(f"samplerate={int(t['samplerate'])}")
    # A lone scalar `extra` is one option, not one character per option: `extend` on a
    # string would splice "soverlay" into the chain as s,o,v,e,r,l,a,y.
    extra = t.get("extra")
    if isinstance(extra, str):
        extra = [extra]
    params.extend(str(item) for item in (extra or []))
    return "transcode{" + ",".join(params) + "}"


def build_transcode_sout(job: Dict[str, Any]) -> str:
    """Build a file-to-file transcode ``--sout`` chain.

    Example: ``#transcode{vcodec=mp4v,acodec=mp3,vb=800,ab=128}:std{access=file,mux=mp4,dst='out.mp4'}``
    """
    out = job.get("output", {}) or {}
    dst = (out.get("path") or "").replace("\\", "/")
    # `get("format", "mp4")` returns None when the key is present but null, which
    # resolved to the literal mux `none` instead of the MP4 default.
    mux = resolve_mux(out.get("format") or "mp4")
    std = f"std{{access=file,mux={mux},dst='{dst}'}}"
    return f"#{_transcode_block(job)}:{std}"


def _coerce_port(value: Any) -> int:
    """Coerce a stream port to a valid port number, defaulting when unset.

    ``int(None)`` raised TypeError and ``int("abc")`` / ``int(1e309)`` raised
    ValueError / OverflowError — all of which escaped as tracebacks instead of the
    structured error the CLI promises. Out-of-range values are rejected for the same
    reason: VLC cannot bind them.
    """
    if value is None or value == "":
        return 1234  # documented default
    try:
        port = int(value)
    except (TypeError, ValueError, OverflowError):
        raise ValueError(
            f"stream.port must be an integer between 1 and 65535, got {value!r}"
        )
    if not 1 <= port <= 65535:
        raise ValueError(f"stream.port must be between 1 and 65535, got {port}")
    return port


def build_stream_sout(job: Dict[str, Any]) -> str:
    """Build a network-stream ``--sout`` chain from ``job['stream']``."""
    s = job.get("stream") or {}
    proto = (s.get("protocol") or "rtp").lower()
    # `get(k, default)` returns the stored null, which used to reach the chain as
    # `dst=None` and crash on `int(None)`; a null means "unset", not "None".
    dst = s.get("dst") or "127.0.0.1"
    port = _coerce_port(s.get("port"))
    mux = resolve_mux(s.get("mux") or "ts")  # null mux -> "none" via get()'s default

    if proto == "rtp":
        dest = f"rtp{{dst={dst},port={port},mux={mux}}}"
    elif proto == "udp":
        dest = f"udp{{dst={dst},port={port},mux={mux}}}"
    elif proto == "http":
        dest = f"standard{{access=http,mux={mux},dst={dst}:{port}}}"
    else:
        dest = f"standard{{access={proto},mux={mux},dst={dst}:{port}}}"

    return f"#{_transcode_block(job)}:{dest}"


def build_snapshot_args(job: Dict[str, Any], scene_prefix: Optional[str] = None) -> List[str]:
    """Build VLC arguments to extract a still frame via the scene video filter.

    ``scene_prefix`` overrides VLC's scene filename prefix (default ``scene``). The
    backend passes a unique prefix per invocation so that output can be attributed to
    that run alone, even when the snapshot directory is reused — see
    ``utils/vlc_backend.run_snapshot``.
    """
    snap = job.get("snapshot") or {}
    path = (snap.get("path") or "").replace("\\", "/")
    # A zero/negative ratio used to be silently replaced by 1, so the run captured a
    # different frame cadence than the saved spec asked for; reject it instead.
    raw_ratio = snap.get("ratio")
    if raw_ratio is None:
        raw_ratio = 1
    try:
        ratio = int(raw_ratio)
    except (TypeError, ValueError):
        raise ValueError(f"snapshot.ratio must be an integer, got {raw_ratio!r}")
    if ratio < 1:
        raise ValueError(f"snapshot.ratio must be >= 1, got {ratio}")
    prefix = scene_prefix if scene_prefix is not None else (snap.get("prefix") or "scene")
    args = [
        "--video-filter=scene",
        f"--scene-path={path}",
        f"--scene-prefix={prefix}",
        f"--scene-ratio={ratio}",
        "--scene-format=png",
        "--no-audio",
        "--play-and-exit",
    ]
    # A loaded snapshot may omit `time` entirely. Without both a seek and a run-time
    # bound the scene filter captures frames all the way to EOF (or the backend
    # timeout) instead of a single still, so normalise to the CLI's 1-second default.
    seek = snap.get("time")
    seek = 1.0 if seek is None else float(seek)
    args.append(f"--start-time={seek}")
    args.append("--run-time=0.1")
    return args
