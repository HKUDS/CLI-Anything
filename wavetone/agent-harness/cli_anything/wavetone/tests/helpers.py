from __future__ import annotations

import math
import struct
import wave
from pathlib import Path


def make_wav(path: Path, freq: float = 440.0, duration: float = 0.5, sample_rate: int = 8000) -> Path:
    frames = int(duration * sample_rate)
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)
        for idx in range(frames):
            sample = int(16000 * math.sin(2 * math.pi * freq * idx / sample_rate))
            handle.writeframes(struct.pack("<h", sample))
    return path
