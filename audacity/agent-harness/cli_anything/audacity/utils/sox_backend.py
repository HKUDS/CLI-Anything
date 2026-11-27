"""SoX backend — invoke SoX for audio processing and format conversion.

SoX (Sound eXchange) is the Swiss Army knife of audio processing.
Audacity uses it for many of its effects.

Requires: sox (system package)
    apt install sox
"""

import os
import shutil
import subprocess
import tempfile
import wave
from typing import Optional, List


def find_sox() -> str:
    """Find the SoX executable."""
    path = shutil.which("sox")
    if path:
        return path
    raise RuntimeError(
        "SoX is not installed. Install it with:\n"
        "  apt install sox   # Debian/Ubuntu"
    )


def get_version() -> str:
    """Get the installed SoX version string."""
    sox = find_sox()
    result = subprocess.run(
        [sox, "--version"],
        capture_output=True, text=True, timeout=10,
    )
    return result.stdout.strip() or result.stderr.strip()


def generate_tone(
    output_path: str,
    frequency: float = 440.0,
    duration: float = 2.0,
    sample_rate: int = 44100,
    channels: int = 2,
    timeout: int = 30,
) -> dict:
    """Generate a sine tone using SoX synth.

    Perfect for E2E testing without input files.
    """
    sox = find_sox()
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

    cmd = [
        sox, "-n",
        "-r", str(sample_rate),
        "-c", str(channels),
        output_path,
        "synth", str(duration),
        "sine", str(frequency),
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)

    if result.returncode != 0:
        raise RuntimeError(f"SoX tone generation failed: {result.stderr}")

    if not os.path.exists(output_path):
        raise RuntimeError(f"SoX produced no output: {output_path}")

    return {
        "output": os.path.abspath(output_path),
        "format": os.path.splitext(output_path)[1].lstrip("."),
        "method": "sox",
        "file_size": os.path.getsize(output_path),
        "duration": duration,
        "frequency": frequency,
    }


def apply_effect(
    input_path: str,
    output_path: str,
    effects: List[str],
    timeout: int = 30,
) -> dict:
    """Apply SoX effects to an audio file.

    Args:
        input_path: Input audio file
        output_path: Output audio file
        effects: List of SoX effect strings, e.g. ["reverb", "50", "50", "100"]
    """
    if not os.path.exists(input_path):
        raise FileNotFoundError(f"Input file not found: {input_path}")

    sox = find_sox()
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

    cmd = [sox, input_path, output_path] + effects

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)

    if result.returncode != 0:
        raise RuntimeError(f"SoX effect failed: {result.stderr}")

    if not os.path.exists(output_path):
        raise RuntimeError(f"SoX produced no output: {output_path}")

    return {
        "output": os.path.abspath(output_path),
        "format": os.path.splitext(output_path)[1].lstrip("."),
        "method": "sox",
        "file_size": os.path.getsize(output_path),
        "effects_applied": effects,
    }


def convert_format(
    input_path: str,
    output_path: str,
    sample_rate: Optional[int] = None,
    channels: Optional[int] = None,
    timeout: int = 30,
) -> dict:
    """Convert audio format using SoX."""
    if not os.path.exists(input_path):
        raise FileNotFoundError(f"Input file not found: {input_path}")

    sox = find_sox()
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

    cmd = [sox, input_path]
    if sample_rate:
        cmd.extend(["-r", str(sample_rate)])
    if channels:
        cmd.extend(["-c", str(channels)])
    cmd.append(output_path)

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)

    if result.returncode != 0:
        raise RuntimeError(f"SoX conversion failed: {result.stderr}")

    if not os.path.exists(output_path):
        raise RuntimeError(f"SoX produced no output: {output_path}")

    return {
        "output": os.path.abspath(output_path),
        "format": os.path.splitext(output_path)[1].lstrip("."),
        "method": "sox",
        "file_size": os.path.getsize(output_path),
    }


def decode_to_wav(
    input_path: str, output_path: str, channels: Optional[int] = None,
    timeout: int = 60,
) -> dict:
    """Decode any source SoX can read into a WAV file.

    SoX handles compressed inputs (MP3, FLAC, OGG, ...) and resets the
    container to RIFF/WAV so the stdlib wave reader can consume it.
    ``channels`` asks SoX to remix the source to that channel count, so a
    surround source arrives in a layout the clip renderer understands.
    """
    try:
        return convert_format(input_path, output_path, channels=channels,
                              timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"SoX timed out decoding {input_path}") from exc


def probe_duration(input_path: str, timeout: int = 15) -> float:
    """Return the duration of any source SoX can read, in seconds.

    ``soxi -D`` answers without decoding the whole file. When soxi is not
    installed (some SoX builds ship only the main binary), fall back to
    decoding a temporary WAV and counting its frames.
    """
    if not os.path.exists(input_path):
        raise FileNotFoundError(f"Input file not found: {input_path}")

    soxi = shutil.which("soxi")
    if soxi:
        try:
            result = subprocess.run(
                [soxi, "-D", input_path],
                capture_output=True, text=True, timeout=timeout,
            )
        except subprocess.TimeoutExpired:
            result = None
        if result is not None and result.returncode == 0:
            try:
                duration = float(result.stdout.strip().splitlines()[-1])
            except (IndexError, ValueError):
                duration = 0.0
            if duration > 0:
                return duration

    with tempfile.TemporaryDirectory(prefix="cli-anything-sox-") as tmp_dir:
        wav_path = os.path.join(tmp_dir, "probe.wav")
        decode_to_wav(input_path, wav_path, timeout=max(timeout, 60))
        with wave.open(wav_path, "r") as wf:
            frames = wf.getnframes()
            rate = wf.getframerate()
        if rate <= 0:
            raise RuntimeError(f"SoX produced an unreadable WAV for {input_path}")
        return frames / rate
