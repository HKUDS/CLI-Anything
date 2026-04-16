"""SoX backend — invoke SoX for audio processing and format conversion.

SoX (Sound eXchange) is the Swiss Army knife of audio processing.
Audacity uses it for many of its effects.

Requires: sox (system package)
    apt install sox
"""

import os
import shutil
import subprocess
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
