import subprocess, os
from typing import Optional, List


def run(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, stderr=subprocess.STDOUT)


def convert(input_file: str, output_file: str) -> dict:
    result = run(["ffmpeg", "-y", "-i", input_file, output_file])
    return {
        "success": result.returncode == 0,
        "output": output_file,
        "log": result.stdout[-500:],
    }


def extract_audio(input_file: str, output_file: str) -> dict:
    result = run(
        ["ffmpeg", "-y", "-i", input_file, "-vn", "-acodec", "copy", output_file]
    )
    return {
        "success": result.returncode == 0,
        "output": output_file,
        "log": result.stdout[-500:],
    }


def trim(input_file: str, output_file: str, start: str, duration: str) -> dict:
    result = run(
        [
            "ffmpeg",
            "-y",
            "-ss",
            start,
            "-t",
            duration,
            "-i",
            input_file,
            "-c",
            "copy",
            output_file,
        ]
    )
    return {
        "success": result.returncode == 0,
        "output": output_file,
        "start": start,
        "duration": duration,
        "log": result.stdout[-500:],
    }


def concat(inputs: list[str], output: str) -> dict:
    list_file = "/tmp/ffmpeg_concat.txt"
    with open(list_file, "w") as f:
        for inp in inputs:
            f.write(f"file '{inp}'\n")
    result = run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            list_file,
            "-c",
            "copy",
            output,
        ]
    )
    return {
        "success": result.returncode == 0,
        "output": output,
        "log": result.stdout[-500:],
    }


def scale(input_file: str, output_file: str, width: int, height: int) -> dict:
    result = run(
        [
            "ffmpeg",
            "-y",
            "-i",
            input_file,
            "-vf",
            f"scale={width}:{height}",
            output_file,
        ]
    )
    return {
        "success": result.returncode == 0,
        "output": output_file,
        "width": width,
        "height": height,
        "log": result.stdout[-500:],
    }


def thumbnail(input_file: str, output_file: str, time: str) -> dict:
    result = run(
        ["ffmpeg", "-y", "-i", input_file, "-ss", time, "-frames:v", "1", output_file]
    )
    return {
        "success": result.returncode == 0,
        "output": output_file,
        "time": time,
        "log": result.stdout[-500:],
    }


def info(file: str) -> dict:
    result = run(
        [
            "ffprobe",
            "-v",
            "quiet",
            "-print_format",
            "json",
            "-show_format",
            "-show_streams",
            file,
        ]
    )
    if result.returncode != 0:
        return {"error": result.stdout}
    import json

    try:
        return json.loads(result.stdout)
    except:
        return {"raw": result.stdout[:1000]}
