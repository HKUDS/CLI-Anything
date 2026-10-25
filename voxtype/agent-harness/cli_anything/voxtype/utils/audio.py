"""WAV inspection helpers (stdlib only) and measurement used for verification."""

import array
import math
import os
import wave

VOXTYPE_SAMPLE_RATE = 16000


def probe_wav(path: str) -> dict:
    """Return basic properties of a PCM WAV file. Raises ValueError if not a WAV."""
    if not os.path.exists(path):
        raise FileNotFoundError(f"Audio file not found: {path}")
    try:
        with wave.open(path, "rb") as w:
            frames = w.getnframes()
            rate = w.getframerate()
            return {
                "path": os.path.abspath(path),
                "sample_rate": rate,
                "channels": w.getnchannels(),
                "sample_width": w.getsampwidth(),
                "frames": frames,
                "duration_secs": round(frames / rate, 3) if rate else 0.0,
            }
    except (wave.Error, EOFError) as e:
        raise ValueError(f"Not a PCM WAV file: {path} ({e})") from e


def is_voxtype_native(info: dict) -> bool:
    """voxtype reads any PCM WAV, but 16 kHz mono s16 needs no resampling."""
    return (info["sample_rate"] == VOXTYPE_SAMPLE_RATE and info["channels"] == 1
            and info["sample_width"] == 2)


def needs_conversion(path: str) -> bool:
    """True when the file is not a WAV voxtype can read directly."""
    try:
        info = probe_wav(path)
    except ValueError:
        return True
    return info["sample_width"] not in (1, 2, 3, 4)


def rms_dbfs(path: str) -> float:
    """RMS level of a 16-bit WAV in dBFS (-inf for digital silence)."""
    with wave.open(path, "rb") as w:
        if w.getsampwidth() != 2:
            raise ValueError("rms_dbfs supports 16-bit PCM only")
        data = array.array("h", w.readframes(w.getnframes()))
    if not data:
        return float("-inf")
    mean_sq = sum(s * s for s in data) / len(data)
    if mean_sq == 0:
        return float("-inf")
    return 20 * math.log10(math.sqrt(mean_sq) / 32768.0)


def write_tone(path: str, freq: float = 440.0, secs: float = 1.0,
               rate: int = VOXTYPE_SAMPLE_RATE, amplitude: float = 0.3) -> str:
    """Write a mono 16-bit sine tone (used for synthetic tests)."""
    n = int(secs * rate)
    samples = array.array("h", (int(amplitude * 32767 * math.sin(2 * math.pi * freq * i / rate))
                                for i in range(n)))
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(samples.tobytes())
    return path


def write_silence(path: str, secs: float = 1.0, rate: int = VOXTYPE_SAMPLE_RATE) -> str:
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(b"\x00\x00" * int(secs * rate))
    return path
