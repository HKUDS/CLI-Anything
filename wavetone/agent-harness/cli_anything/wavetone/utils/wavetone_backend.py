"""Backend wrapper for the real WaveTone 2.61 executable."""

from __future__ import annotations

import os
import platform
import subprocess
import time
from pathlib import Path
from typing import Any

from cli_anything.wavetone.core.project import SUPPORTED_AUDIO_EXTENSIONS, normalize_audio_path


REQUIRED_DATA_FILES = [
    "awlib.dll",
    "bass.dll",
    "bassflac.dll",
    "basswma.dll",
    "basswv.dll",
    "bass_aac.dll",
    "bass_alac.dll",
    "bass_ape.dll",
    "bass_tta.dll",
    "asdecoder.exe",
]


def default_candidates() -> list[Path]:
    candidates: list[Path] = []
    env_exe = os.environ.get("WAVETONE_EXE")
    if env_exe:
        candidates.append(Path(env_exe))
    env_home = os.environ.get("WAVETONE_HOME")
    if env_home:
        candidates.append(Path(env_home) / "wavetone.exe")
        candidates.append(Path(env_home) / "WaveTone.exe")
    home = Path.home()
    candidates.extend(
        [
            home / "Desktop" / "wavetone2.6.1" / "wavetone.exe",
            home / "Downloads" / "wavetone2.6.1" / "wavetone.exe",
            Path("C:/Program Files/WaveTone/wavetone.exe"),
            Path("C:/Program Files (x86)/WaveTone/wavetone.exe"),
        ]
    )
    return candidates


def find_wavetone(executable: str | Path | None = None) -> Path:
    candidates = [Path(executable)] if executable else default_candidates()
    checked: list[str] = []
    for candidate in candidates:
        path = candidate.expanduser()
        checked.append(str(path))
        if path.exists() and path.is_file():
            return path.resolve()
    raise FileNotFoundError(
        "WaveTone executable not found. Set WAVETONE_EXE to wavetone.exe or "
        "WAVETONE_HOME to the extracted WaveTone directory. Checked: "
        + "; ".join(checked)
    )


def doctor(executable: str | Path | None = None) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    try:
        exe = find_wavetone(executable)
        root = exe.parent
        checks.append({"name": "wavetone executable", "ok": True, "path": str(exe)})
    except FileNotFoundError as exc:
        return {
            "ready": False,
            "platform": platform.system(),
            "checks": [{"name": "wavetone executable", "ok": False, "error": str(exc)}],
        }

    data_dir = root / "data"
    checks.append({"name": "data directory", "ok": data_dir.is_dir(), "path": str(data_dir)})
    for filename in REQUIRED_DATA_FILES:
        path = data_dir / filename
        checks.append({"name": f"data/{filename}", "ok": path.is_file(), "path": str(path)})
    help_dir = root / "wthelp"
    checks.append({"name": "help directory", "ok": help_dir.is_dir(), "path": str(help_dir)})
    checks.append(
        {
            "name": "windows host",
            "ok": platform.system().lower() == "windows",
            "platform": platform.platform(),
        }
    )
    return {
        "ready": all(check["ok"] for check in checks),
        "platform": platform.system(),
        "root": str(root),
        "checks": checks,
    }


def launch_wavetone(
    audio_path: str | Path | None = None,
    executable: str | Path | None = None,
    wait_seconds: float = 0.0,
    terminate: bool = False,
) -> dict[str, Any]:
    if platform.system().lower() != "windows":
        raise RuntimeError("WaveTone launch requires Windows")

    exe = find_wavetone(executable)
    args = [str(exe)]
    audio: Path | None = None
    if audio_path:
        audio = normalize_audio_path(audio_path)
        args.append(str(audio))

    process = subprocess.Popen(args, cwd=str(exe.parent))
    if wait_seconds > 0:
        time.sleep(wait_seconds)
    polled = process.poll()
    running_after_wait = polled is None
    exit_code = polled
    terminated = False
    if terminate and running_after_wait:
        process.terminate()
        try:
            process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=3)
        terminated = True
        exit_code = process.returncode

    return {
        "backend": "wavetone.exe",
        "executable": str(exe),
        "cwd": str(exe.parent),
        "pid": process.pid,
        "args": args,
        "audio_path": str(audio) if audio else None,
        "running_after_wait": running_after_wait,
        "terminated": terminated,
        "exit_code": exit_code,
        "note": "WaveTone analysis and export dialogs are GUI driven in version 2.61.",
    }


def supported_formats() -> dict[str, Any]:
    return {
        "extensions": sorted(SUPPORTED_AUDIO_EXTENSIONS),
        "from_readme": [
            "WAVE",
            "AIFF",
            "MP3",
            "WMA",
            "AAC",
            "Vorbis",
            "FLAC",
            "WavPack",
            "Monkey's Audio",
            "ALAC",
            "TTA",
        ],
    }
