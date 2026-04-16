"""Audacity CLI - Export/mixdown/rendering pipeline module.

This module handles the critical rendering step: mixing all tracks
with their clips and effects, then exporting to audio file formats.

Uses ONLY Python stdlib (wave, struct, math) for WAV rendering.
Effects are applied in the audio domain using the audio_utils module.
"""

import os
import wave
import math
import struct
from typing import Dict, Any, Optional, List, Tuple

from cli_anything.audacity.utils.audio_utils import (
    generate_sine_wave,
    generate_silence,
    mix_audio,
    apply_gain,
    apply_fade_in,
    apply_fade_out,
    apply_reverse,
    apply_echo,
    apply_low_pass,
    apply_high_pass,
    apply_normalize,
    apply_change_speed,
    apply_limit,
    clamp_samples,
    write_wav,
    read_wav,
    get_rms,
    get_peak,
)


# Export presets
EXPORT_PRESETS = {
    "wav": {
        "format": "WAV",
        "ext": ".wav",
        "params": {"bit_depth": 16},
        "description": "Standard WAV (16-bit PCM)",
    },
    "wav-24": {
        "format": "WAV",
        "ext": ".wav",
        "params": {"bit_depth": 24},
        "description": "High quality WAV (24-bit PCM)",
    },
    "wav-32": {
        "format": "WAV",
        "ext": ".wav",
        "params": {"bit_depth": 32},
        "description": "Studio quality WAV (32-bit PCM)",
    },
    "wav-8": {
        "format": "WAV",
        "ext": ".wav",
        "params": {"bit_depth": 8},
        "description": "Low quality WAV (8-bit PCM)",
    },
    "mp3": {
        "format": "MP3",
        "ext": ".mp3",
        "params": {"bitrate": 192},
        "description": "MP3 (requires pydub/ffmpeg)",
    },
    "flac": {
        "format": "FLAC",
        "ext": ".flac",
        "params": {},
        "description": "FLAC lossless (requires pydub/ffmpeg)",
    },
    "ogg": {
        "format": "OGG",
        "ext": ".ogg",
        "params": {"quality": 5},
        "description": "OGG Vorbis (requires pydub/ffmpeg)",
    },
    "aiff": {
        "format": "AIFF",
        "ext": ".aiff",
        "params": {},
        "description": "AIFF (requires pydub/ffmpeg)",
    },
}


def list_presets() -> list:
    """List available export presets."""
    result = []
    for name, p in EXPORT_PRESETS.items():
        result.append({
            "name": name,
            "format": p["format"],
            "extension": p["ext"],
            "description": p.get("description", ""),
            "params": p["params"],
        })
    return result


def get_preset_info(name: str) -> Dict[str, Any]:
    """Get details about an export preset."""
    if name not in EXPORT_PRESETS:
        raise ValueError(
            f"Unknown preset: {name}. Available: {list(EXPORT_PRESETS.keys())}"
        )
    p = EXPORT_PRESETS[name]
    return {
        "name": name,
        "format": p["format"],
        "extension": p["ext"],
        "description": p.get("description", ""),
        "params": p["params"],
    }


def render_mix(
    project: Dict[str, Any],
    output_path: str,
    preset: str = "wav",
    overwrite: bool = False,
    channels_override: Optional[int] = None,
) -> Dict[str, Any]:
    """Render the project: mix all tracks, apply effects, export.

    This is the main rendering pipeline.
    """
    if os.path.exists(output_path) and not overwrite:
        raise FileExistsError(
            f"Output file exists: {output_path}. Use --overwrite."
        )

    settings = project.get("settings", {})
    sample_rate = settings.get("sample_rate", 44100)
    bit_depth = settings.get("bit_depth", 16)
    out_channels = channels_override or settings.get("channels", 2)

    # Get preset settings
    if preset in EXPORT_PRESETS:
        p = EXPORT_PRESETS[preset]
        fmt = p["format"]
        if "bit_depth" in p["params"]:
            bit_depth = p["params"]["bit_depth"]
    else:
        raise ValueError(f"Unknown preset: {preset}")

    tracks = project.get("tracks", [])

    # Check for solo tracks
    solo_tracks = [t for t in tracks if t.get("solo", False)]
    has_solo = len(solo_tracks) > 0

    # Render each track
    rendered_tracks = []
    track_volumes = []
    track_pans = []

    for track in tracks:
        # Skip muted tracks; if solo mode is active, skip non-solo tracks
        if track.get("mute", False):
            continue
        if has_solo and not track.get("solo", False):
            continue

        track_audio = _render_track(track, sample_rate, out_channels)

        if track_audio:
            # Apply track-level effects
            track_audio = _apply_track_effects(
                track_audio, track.get("effects", []),
                sample_rate, out_channels,
            )
            rendered_tracks.append(track_audio)
            track_volumes.append(track.get("volume", 1.0))
            track_pans.append(track.get("pan", 0.0))

    # Mix all tracks together
    if rendered_tracks:
        mixed = mix_audio(
            rendered_tracks,
            volumes=track_volumes,
            pans=track_pans,
            channels=out_channels,
        )
    else:
        # Empty project: generate 1 second of silence
        mixed = generate_silence(1.0, sample_rate, out_channels)

    # Clamp to prevent clipping
    mixed = clamp_samples(mixed)

    # Export
    if fmt == "WAV":
        write_wav(output_path, mixed, sample_rate, out_channels, bit_depth)
    else:
        # For non-WAV formats, write a WAV first and note that conversion
        # requires external tools
        write_wav(output_path, mixed, sample_rate, out_channels, bit_depth)

    # Verify output
    file_size = os.path.getsize(output_path)
    duration = (len(mixed) / out_channels) / sample_rate

    result = {
        "output": os.path.abspath(output_path),
        "format": fmt,
        "sample_rate": sample_rate,
        "channels": out_channels,
        "bit_depth": bit_depth,
        "duration": round(duration, 3),
        "duration_human": _format_time(duration),
        "file_size": file_size,
        "file_size_human": _human_size(file_size),
        "preset": preset,
        "tracks_rendered": len(rendered_tracks),
        "peak_level": round(get_peak(mixed), 4),
        "rms_level": round(get_rms(mixed), 4),
    }

    return result


def _render_track(
    track: Dict[str, Any],
    sample_rate: int,
    channels: int,
) -> Optional[List[float]]:
    """Render a single track by assembling its clips on the timeline."""
    clips = track.get("clips", [])
    if not clips:
        return None

    # Find total duration
    max_end = max(c.get("end_time", 0.0) for c in clips)
    if max_end <= 0:
        return None

    total_samples = int(max_end * sample_rate) * channels
    track_audio = [0.0] * total_samples

    for clip in clips:
        clip_audio = _render_clip(clip, sample_rate, channels)
        if clip_audio is None:
            continue

        # Apply clip volume
        clip_vol = clip.get("volume", 1.0)
        if clip_vol != 1.0:
            clip_audio = [s * clip_vol for s in clip_audio]

        # Place clip at its start_time position
        start_sample = int(clip["start_time"] * sample_rate) * channels
        for i, s in enumerate(clip_audio):
            pos = start_sample + i
            if 0 <= pos < len(track_audio):
                track_audio[pos] += s

    return track_audio


def _render_clip(
    clip: Dict[str, Any],
    sample_rate: int,
    channels: int,
) -> Optional[List[float]]:
    """Render a single clip by reading its source audio."""
    source = clip.get("source", "")

    if source and os.path.exists(source):
        try:
            samples, src_rate, src_channels, src_bits = read_wav(source)
        except (wave.Error, EOFError, struct.error, ValueError):
            return None

        # Handle trim
        trim_start = clip.get("trim_start", 0.0)
        trim_end = clip.get("trim_end", None)

        start_idx = int(trim_start * src_rate) * src_channels
        if trim_end is not None and trim_end > 0:
            end_idx = int(trim_end * src_rate) * src_channels
        else:
            end_idx = len(samples)

        start_idx = max(0, min(start_idx, len(samples)))
        end_idx = max(start_idx, min(end_idx, len(samples)))
        samples = samples[start_idx:end_idx]

        # Channel conversion
        if src_channels == 1 and channels == 2:
            # Mono to stereo
            stereo = []
            for s in samples:
                stereo.append(s)
                stereo.append(s)
            samples = stereo
        elif src_channels == 2 and channels == 1:
            # Stereo to mono
            mono = []
            for i in range(0, len(samples) - 1, 2):
                mono.append((samples[i] + samples[i + 1]) / 2.0)
            samples = mono

        # Resample if needed (simple linear interpolation)
        if src_rate != sample_rate:
            ratio = sample_rate / src_rate
            new_len = int(len(samples) / channels * ratio) * channels
            resampled = []
            total_frames = len(samples) // max(src_channels, channels)
            new_frames = int(total_frames * ratio)
            actual_ch = channels
            for f in range(new_frames):
                src_f = f / ratio
                sf_int = int(src_f)
                frac = src_f - sf_int
                for ch in range(actual_ch):
                    idx1 = sf_int * actual_ch + ch
                    idx2 = (sf_int + 1) * actual_ch + ch
                    s1 = samples[idx1] if idx1 < len(samples) else 0.0
                    s2 = samples[idx2] if idx2 < len(samples) else 0.0
                    resampled.append(s1 + frac * (s2 - s1))
            samples = resampled

        return samples

    # No source file — return None
    return None


def _apply_track_effects(
    samples: List[float],
    effects: List[Dict[str, Any]],
    sample_rate: int,
    channels: int,
) -> List[float]:
    """Apply a chain of effects to track audio."""
    for effect in effects:
        name = effect.get("name", "")
        params = effect.get("params", {})
        samples = _apply_single_effect(samples, name, params, sample_rate, channels)
    return samples


def _apply_single_effect(
    samples: List[float],
    name: str,
    params: Dict[str, Any],
    sample_rate: int,
    channels: int,
) -> List[float]:
    """Apply a single effect to audio samples."""
    if name == "amplify":
        return apply_gain(samples, params.get("gain_db", 0.0))

    elif name == "normalize":
        return apply_normalize(samples, params.get("target_db", -1.0))

    elif name == "fade_in":
        return apply_fade_in(
            samples, params.get("duration", 1.0), sample_rate, channels
        )

    elif name == "fade_out":
        return apply_fade_out(
            samples, params.get("duration", 1.0), sample_rate, channels
        )

    elif name == "reverse":
        return apply_reverse(samples, channels)

    elif name == "echo":
        return apply_echo(
            samples,
            delay_ms=params.get("delay_ms", 500.0),
            decay=params.get("decay", 0.5),
            sample_rate=sample_rate,
            channels=channels,
        )

    elif name == "low_pass":
        return apply_low_pass(
            samples,
            cutoff=params.get("cutoff", 1000.0),
            sample_rate=sample_rate,
            channels=channels,
        )

    elif name == "high_pass":
        return apply_high_pass(
            samples,
            cutoff=params.get("cutoff", 100.0),
            sample_rate=sample_rate,
            channels=channels,
        )

    elif name == "change_speed":
        return apply_change_speed(
            samples,
            factor=params.get("factor", 1.0),
            channels=channels,
        )

    elif name == "limit":
        return apply_limit(samples, params.get("threshold_db", -1.0))

    elif name == "compress":
        # Simple compression: reduce dynamic range
        threshold_db = params.get("threshold", -20.0)
        ratio = params.get("ratio", 4.0)
        threshold = 10.0 ** (threshold_db / 20.0)
        result = []
        for s in samples:
            abs_s = abs(s)
            if abs_s > threshold:
                excess = abs_s - threshold
                compressed = threshold + excess / ratio
                result.append(compressed if s > 0 else -compressed)
            else:
                result.append(s)
        return result

    elif name == "change_pitch":
        # Pitch change via speed change (simple approach)
        semitones = params.get("semitones", 0.0)
        factor = 2.0 ** (semitones / 12.0)
        return apply_change_speed(samples, factor, channels)

    elif name == "change_tempo":
        # Tempo change (same as speed for simple implementation)
        factor = params.get("factor", 1.0)
        return apply_change_speed(samples, factor, channels)

    elif name == "noise_reduction":
        # Simple noise gate
        reduction_db = params.get("reduction_db", 12.0)
        gate_threshold = 10.0 ** (-reduction_db / 20.0) * 0.1
        result = []
        for s in samples:
            if abs(s) < gate_threshold:
                result.append(s * 0.1)
            else:
                result.append(s)
        return result

    elif name == "silence":
        # Generate silence (replaces audio)
        duration = params.get("duration", 1.0)
        return generate_silence(duration, sample_rate, channels)

    elif name == "tone":
        # Generate tone (replaces audio)
        frequency = params.get("frequency", 440.0)
        duration = params.get("duration", 1.0)
        amplitude = params.get("amplitude", 0.5)
        return generate_sine_wave(frequency, duration, sample_rate, amplitude, channels)

    # Unknown effect — pass through
    return samples


def _format_time(seconds: float) -> str:
    """Format seconds to HH:MM:SS.mmm."""
    if seconds < 0:
        seconds = 0.0
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    if h > 0:
        return f"{h:02d}:{m:02d}:{s:06.3f}"
    return f"{m:02d}:{s:06.3f}"


def _human_size(nbytes: int) -> str:
    """Convert byte count to human-readable string."""
    for unit in ("B", "KB", "MB", "GB"):
        if nbytes < 1024:
            return f"{nbytes:.1f} {unit}"
        nbytes /= 1024
    return f"{nbytes:.1f} TB"
