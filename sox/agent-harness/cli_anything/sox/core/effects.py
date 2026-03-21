"""SoX (Sound eXchange) wrapper with structured JSON output."""

import json
import os
import subprocess
import shutil
from typing import Optional, List


def _get_sox_cmd():
    """Find the sox command."""
    if shutil.which("sox"):
        return "sox"
    raise RuntimeError("SoX not found. Install with: apt install sox")


def _run_sox(args: list[str], timeout: int = 120) -> dict:
    """Run a SoX command and return structured output."""
    cmd = [_get_sox_cmd()] + args
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return {
            "status": "success" if result.returncode == 0 else "error",
            "command": " ".join(cmd),
            "returncode": result.returncode,
            "stdout": result.stdout.strip(),
            "stderr": result.stderr.strip(),
        }
    except subprocess.TimeoutExpired:
        return {
            "status": "error",
            "command": " ".join(cmd),
            "error": "Command timed out",
        }
    except Exception as e:
        return {"status": "error", "command": " ".join(cmd), "error": str(e)}


def _file_info(path: str) -> dict:
    """Get file stats."""
    if not os.path.exists(path):
        return {}
    st = os.stat(path)
    return {"path": path, "size": st.st_size, "modified": st.st_mtime}


def info(file_path: str) -> dict:
    """Get audio file info via sox --i."""
    cmd = [_get_sox_cmd(), "--i", file_path]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        output = {
            "status": "success" if result.returncode == 0 else "error",
            "command": " ".join(cmd),
            "returncode": result.returncode,
            "input": file_path,
            "raw": result.stdout.strip(),
            "stderr": result.stderr.strip(),
        }
        if result.returncode == 0:
            parsed = {}
            for line in result.stdout.strip().splitlines():
                if ":" in line:
                    key, _, val = line.partition(":")
                    parsed[key.strip()] = val.strip()
            output["info"] = parsed
    except Exception as e:
        output = {"status": "error", "command": " ".join(cmd), "error": str(e)}
    output.update(_file_info(file_path))
    return output


def convert(
    input_path: str,
    output_path: str,
    sample_rate: Optional[int] = None,
    channels: Optional[int] = None,
    bits: Optional[int] = None,
    encoding: Optional[str] = None,
) -> dict:
    """Convert audio format with options."""
    args = [input_path]
    if sample_rate:
        args.extend(["-r", str(sample_rate)])
    if channels:
        args.extend(["-c", str(channels)])
    if bits:
        args.extend(["-b", str(bits)])
    if encoding:
        args.extend(["-e", encoding])
    args.append(output_path)
    result = _run_sox(args)
    result.update({"input": input_path, "output": output_path})
    result.update(_file_info(output_path))
    return result


def trim(
    input_path: str,
    output_path: str,
    start: Optional[float] = None,
    duration: Optional[float] = None,
) -> dict:
    """Trim audio segment."""
    args = [input_path, output_path]
    if start is not None:
        args.extend(["trim", str(start)])
    if duration is not None:
        if start is not None:
            args.extend([str(duration)])
        else:
            args.extend(["trim", "0", str(duration)])
    result = _run_sox(args)
    result.update(
        {
            "input": input_path,
            "output": output_path,
            "start": start,
            "duration": duration,
        }
    )
    result.update(_file_info(output_path))
    return result


def concat(inputs: list[str], output_path: str) -> dict:
    """Concatenate audio files."""
    args = inputs + [output_path]
    result = _run_sox(args)
    result.update({"inputs": inputs, "output": output_path, "operation": "concat"})
    result.update(_file_info(output_path))
    return result


def mix(inputs: list[str], output_path: str, mix_type: str = "mix") -> dict:
    """Mix audio files together."""
    args = ["--combine", mix_type] + inputs + [output_path]
    result = _run_sox(args)
    result.update(
        {
            "inputs": inputs,
            "output": output_path,
            "operation": "mix",
            "mix_type": mix_type,
        }
    )
    result.update(_file_info(output_path))
    return result


def speed(input_path: str, output_path: str, factor: float = 1.0) -> dict:
    """Change playback speed."""
    args = [input_path, output_path, "speed", str(factor)]
    result = _run_sox(args)
    result.update({"input": input_path, "output": output_path, "factor": factor})
    result.update(_file_info(output_path))
    return result


def pitch(input_path: str, output_path: str, semitones: float = 0) -> dict:
    """Change pitch in semitones."""
    cents = semitones * 100
    args = [input_path, output_path, "pitch", str(cents)]
    result = _run_sox(args)
    result.update(
        {
            "input": input_path,
            "output": output_path,
            "semitones": semitones,
            "cents": cents,
        }
    )
    result.update(_file_info(output_path))
    return result


def tempo(input_path: str, output_path: str, factor: float = 1.0) -> dict:
    """Change tempo without pitch."""
    args = [input_path, output_path, "tempo", str(factor)]
    result = _run_sox(args)
    result.update({"input": input_path, "output": output_path, "factor": factor})
    result.update(_file_info(output_path))
    return result


def volume(input_path: str, output_path: str, gain: float = 0) -> dict:
    """Adjust volume in dB."""
    args = [input_path, output_path, "vol", f"{gain}dB"]
    result = _run_sox(args)
    result.update({"input": input_path, "output": output_path, "gain_db": gain})
    result.update(_file_info(output_path))
    return result


def normalize(input_path: str, output_path: str) -> dict:
    """Normalize audio levels."""
    args = [input_path, output_path, "norm"]
    result = _run_sox(args)
    result.update(
        {"input": input_path, "output": output_path, "operation": "normalize"}
    )
    result.update(_file_info(output_path))
    return result


def reverse(input_path: str, output_path: str) -> dict:
    """Reverse audio."""
    args = [input_path, output_path, "reverse"]
    result = _run_sox(args)
    result.update({"input": input_path, "output": output_path, "operation": "reverse"})
    result.update(_file_info(output_path))
    return result


def fade(
    input_path: str,
    output_path: str,
    fade_type: str = "t",
    fade_in: float = 0,
    fade_out: float = 0,
) -> dict:
    """Apply fade in/out."""
    args = [input_path, output_path, "fade", fade_type]
    if fade_in > 0:
        args.append(str(fade_in))
    if fade_out > 0:
        args.extend(["-0", str(fade_out)])
    result = _run_sox(args)
    result.update(
        {
            "input": input_path,
            "output": output_path,
            "fade_type": fade_type,
            "fade_in": fade_in,
            "fade_out": fade_out,
        }
    )
    result.update(_file_info(output_path))
    return result


def silence(
    input_path: str, output_path: str, threshold: float = 1, duration: float = 0.1
) -> dict:
    """Remove silence from audio."""
    args = [
        input_path,
        output_path,
        "silence",
        "1",
        str(duration),
        f"{threshold}%",
        "-1",
        str(duration),
        f"{threshold}%",
    ]
    result = _run_sox(args)
    result.update(
        {
            "input": input_path,
            "output": output_path,
            "threshold": threshold,
            "duration": duration,
        }
    )
    result.update(_file_info(output_path))
    return result


def stat(file_path: str) -> dict:
    """Get detailed audio statistics."""
    cmd = [_get_sox_cmd(), file_path, "-n", "stat"]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        output = {
            "status": "success" if result.returncode == 0 else "error",
            "command": " ".join(cmd),
            "input": file_path,
            "raw": result.stderr.strip(),
        }
        if result.returncode == 0:
            parsed = {}
            for line in result.stderr.strip().splitlines():
                if ":" in line:
                    key, _, val = line.partition(":")
                    parsed[key.strip()] = val.strip()
            output["statistics"] = parsed
    except Exception as e:
        output = {"status": "error", "command": " ".join(cmd), "error": str(e)}
    output.update(_file_info(file_path))
    return output


def spectrogram(
    input_path: str, output_path: str, width: int = 800, height: int = 400
) -> dict:
    """Generate a spectrogram image."""
    args = [
        input_path,
        "-n",
        "spectrogram",
        "-o",
        output_path,
        "-x",
        str(width),
        "-y",
        str(height),
    ]
    result = _run_sox(args)
    result.update(
        {"input": input_path, "output": output_path, "width": width, "height": height}
    )
    result.update(_file_info(output_path))
    return result


def synth(
    output_path: str,
    synth_type: str = "sine",
    frequency: float = 440,
    duration: float = 3,
) -> dict:
    """Generate test tone."""
    args = [
        "-n",
        "-r",
        "44100",
        "-c",
        "2",
        output_path,
        "synth",
        str(duration),
        synth_type,
        str(frequency),
    ]
    result = _run_sox(args)
    result.update(
        {
            "output": output_path,
            "type": synth_type,
            "frequency": frequency,
            "duration": duration,
        }
    )
    result.update(_file_info(output_path))
    return result


def effects_list() -> dict:
    """List available SoX effects."""
    cmd = [_get_sox_cmd(), "--help", "effect"]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        output = {
            "status": "success" if result.returncode == 0 else "error",
            "command": " ".join(cmd),
            "raw": result.stdout.strip(),
        }
        if result.returncode == 0:
            effects = []
            for line in result.stdout.strip().splitlines():
                stripped = line.strip()
                if (
                    stripped
                    and not stripped.startswith("(")
                    and " " not in stripped.split()[0]
                ):
                    effects.append(stripped.split()[0])
            output["effects"] = effects
    except Exception as e:
        output = {"status": "error", "command": " ".join(cmd), "error": str(e)}
    return output
