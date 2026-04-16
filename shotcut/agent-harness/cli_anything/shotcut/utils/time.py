"""Timecode utilities for MLT frame/time conversions."""

import re
from typing import Union

# Default profile settings
DEFAULT_FPS_NUM = 30000
DEFAULT_FPS_DEN = 1001  # 29.97 fps


def fps_float(fps_num: int = DEFAULT_FPS_NUM, fps_den: int = DEFAULT_FPS_DEN) -> float:
    """Get floating-point FPS from numerator/denominator."""
    return fps_num / fps_den


def timecode_to_frames(tc: str, fps_num: int = DEFAULT_FPS_NUM,
                       fps_den: int = DEFAULT_FPS_DEN) -> int:
    """Convert timecode string to frame number.

    Accepts:
        - "HH:MM:SS.mmm" (e.g., "00:01:30.500")
        - "HH:MM:SS:FF" (e.g., "00:01:30:15")
        - "SS.mmm" (e.g., "90.5")
        - Plain integer (frame number as string)
    """
    tc = tc.strip()

    # Plain frame number
    if re.match(r'^\d+$', tc):
        return int(tc)

    # Seconds with optional milliseconds
    if re.match(r'^\d+\.\d+$', tc):
        seconds = float(tc)
        return round(seconds * fps_num / fps_den)

    # HH:MM:SS:FF (frame-based timecode)
    m = re.match(r'^(\d+):(\d{2}):(\d{2}):(\d+)$', tc)
    if m:
        h, mi, s, f = int(m.group(1)), int(m.group(2)), int(m.group(3)), int(m.group(4))
        fps = fps_num / fps_den
        total_seconds = h * 3600 + mi * 60 + s
        return round(total_seconds * fps) + f

    # HH:MM:SS.mmm (time-based timecode)
    m = re.match(r'^(\d+):(\d{2}):(\d{2})\.(\d+)$', tc)
    if m:
        h, mi, s = int(m.group(1)), int(m.group(2)), int(m.group(3))
        ms_str = m.group(4).ljust(3, '0')[:3]
        ms = int(ms_str)
        total_seconds = h * 3600 + mi * 60 + s + ms / 1000.0
        return round(total_seconds * fps_num / fps_den)

    # HH:MM:SS (no fractional part)
    m = re.match(r'^(\d+):(\d{2}):(\d{2})$', tc)
    if m:
        h, mi, s = int(m.group(1)), int(m.group(2)), int(m.group(3))
        total_seconds = h * 3600 + mi * 60 + s
        return round(total_seconds * fps_num / fps_den)

    raise ValueError(f"Invalid timecode format: {tc!r}")


def frames_to_timecode(frames: int, fps_num: int = DEFAULT_FPS_NUM,
                       fps_den: int = DEFAULT_FPS_DEN) -> str:
    """Convert frame number to HH:MM:SS.mmm timecode string."""
    if frames < 0:
        frames = 0
    # Use integer arithmetic to avoid floating-point drift:
    # total_ms = frames * den * 1000 / num (integer division with rounding)
    total_ms = round(frames * fps_den * 1000 / fps_num)
    h = total_ms // 3600000
    total_ms -= h * 3600000
    m = total_ms // 60000
    total_ms -= m * 60000
    s = total_ms // 1000
    ms = total_ms - s * 1000
    return f"{h:02d}:{m:02d}:{s:02d}.{ms:03d}"


def frames_to_seconds(frames: int, fps_num: int = DEFAULT_FPS_NUM,
                      fps_den: int = DEFAULT_FPS_DEN) -> float:
    """Convert frame count to seconds."""
    return frames * fps_den / fps_num


def seconds_to_frames(seconds: float, fps_num: int = DEFAULT_FPS_NUM,
                      fps_den: int = DEFAULT_FPS_DEN) -> int:
    """Convert seconds to frame count."""
    return int(seconds * fps_num / fps_den)


def parse_time_input(value: str, fps_num: int = DEFAULT_FPS_NUM,
                     fps_den: int = DEFAULT_FPS_DEN) -> int:
    """Parse any time input format and return frames. This is the main entry point."""
    return timecode_to_frames(value, fps_num, fps_den)


def format_duration(frames: int, fps_num: int = DEFAULT_FPS_NUM,
                    fps_den: int = DEFAULT_FPS_DEN) -> str:
    """Format a duration in frames as a human-readable string."""
    tc = frames_to_timecode(frames, fps_num, fps_den)
    secs = frames_to_seconds(frames, fps_num, fps_den)
    if secs < 1:
        return f"{frames} frames"
    return tc
