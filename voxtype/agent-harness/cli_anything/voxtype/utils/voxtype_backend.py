"""Backend: invokes the real voxtype binary (and ffmpeg for audio normalization).

Every operation that voxtype itself can perform is delegated to it — config
validation, transcription, meeting export, daemon control. This module only
locates the executables, builds argument lists and parses their output.
"""

import json
import os
import re
import shutil
import subprocess
from typing import Optional

VOXTYPE_INSTALL_HINT = (
    "voxtype is not installed or not on PATH. Install it with:\n"
    "  yay -S voxtype-bin            # Arch / AUR\n"
    "  See https://voxtype.io for .deb/.rpm/Nix packages\n"
    "Or point $VOXTYPE_BIN at the binary."
)

FFMPEG_INSTALL_HINT = (
    "ffmpeg is required to convert non-WAV / non-16kHz audio. Install it with:\n"
    "  pacman -S ffmpeg   # Arch\n"
    "  apt install ffmpeg # Debian/Ubuntu"
)

DEFAULT_TIMEOUT = 600


class VoxtypeError(RuntimeError):
    """voxtype exited non-zero. Carries the exit code and stderr."""

    def __init__(self, message: str, returncode: int = 1, stderr: str = "", stdout: str = ""):
        super().__init__(message)
        self.returncode = returncode
        self.stderr = stderr
        self.stdout = stdout


def find_voxtype() -> str:
    """Return the path to the voxtype executable or raise with install instructions."""
    env = os.environ.get("VOXTYPE_BIN", "").strip()
    if env:
        if os.path.isfile(env) and os.access(env, os.X_OK):
            return env
        raise RuntimeError(f"$VOXTYPE_BIN={env} is not an executable file.\n{VOXTYPE_INSTALL_HINT}")
    path = shutil.which("voxtype")
    if path:
        return path
    raise RuntimeError(VOXTYPE_INSTALL_HINT)


def find_ffmpeg() -> str:
    path = shutil.which("ffmpeg")
    if path:
        return path
    raise RuntimeError(FFMPEG_INSTALL_HINT)


def build_args(args: list[str], config_path: Optional[str] = None,
               global_flags: Optional[list[str]] = None) -> list[str]:
    """Assemble `voxtype [-c CONFIG] [global flags] <args>`."""
    cmd = [find_voxtype()]
    if config_path:
        cmd += ["-c", str(config_path)]
    if global_flags:
        cmd += list(global_flags)
    cmd += list(args)
    return cmd


def run(args: list[str], config_path: Optional[str] = None,
        global_flags: Optional[list[str]] = None, check: bool = True,
        timeout: int = DEFAULT_TIMEOUT, input_text: Optional[str] = None) -> subprocess.CompletedProcess:
    """Run voxtype and return the CompletedProcess.

    With check=True a non-zero exit raises VoxtypeError carrying voxtype's own
    error message (voxtype prints `error: ...` on stderr).
    """
    cmd = build_args(args, config_path, global_flags)
    env = dict(os.environ)
    env.setdefault("NO_COLOR", "1")
    env.setdefault("RUST_LOG", "warn")
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                              env=env, input=input_text)
    except subprocess.TimeoutExpired as e:
        raise VoxtypeError(f"voxtype timed out after {timeout}s: {' '.join(cmd)}", returncode=124) from e
    if check and proc.returncode != 0:
        msg = _error_message(proc) or f"voxtype exited with code {proc.returncode}"
        raise VoxtypeError(msg, returncode=proc.returncode, stderr=proc.stderr, stdout=proc.stdout)
    return proc


def run_json(args: list[str], config_path: Optional[str] = None,
             global_flags: Optional[list[str]] = None, timeout: int = DEFAULT_TIMEOUT):
    """Run a voxtype command that prints JSON on stdout and parse it."""
    proc = run(args, config_path, global_flags, timeout=timeout)
    text = proc.stdout.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        raise VoxtypeError(f"voxtype returned non-JSON output for {' '.join(args)}: {text[:200]!r}",
                           stdout=proc.stdout, stderr=proc.stderr) from e


def run_ndjson(args: list[str], config_path: Optional[str] = None,
               timeout: int = DEFAULT_TIMEOUT) -> tuple[list[dict], subprocess.CompletedProcess]:
    """Run a command emitting NDJSON events (e.g. setup --progress-format json)."""
    proc = run(args, config_path, check=False, timeout=timeout)
    events = []
    for line in proc.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            events.append({"event": "text", "message": line})
    if proc.returncode != 0:
        msg = _error_message(proc) or next(
            (e.get("message") for e in events if e.get("event") == "error" and e.get("message")), None
        ) or f"voxtype exited with code {proc.returncode}"
        raise VoxtypeError(msg, returncode=proc.returncode, stderr=proc.stderr, stdout=proc.stdout)
    return events, proc


def _error_message(proc: subprocess.CompletedProcess) -> str:
    """Pull voxtype's own error text out of stderr (dropping log noise)."""
    lines = [ln.rstrip() for ln in (proc.stderr or "").splitlines()]
    for i, ln in enumerate(lines):
        low = ln.lower().lstrip()
        if low.startswith("error:") or low.startswith("error "):
            text = "\n".join(l for l in lines[i:] if l.strip()).strip()
            return re.sub(r"^error:?\s*", "", text, flags=re.IGNORECASE)
    useful = [ln for ln in lines if ln.strip() and not _is_log_noise(ln)]
    if useful:
        return "\n".join(useful[-5:]).strip()
    out = [ln for ln in (proc.stdout or "").splitlines() if ln.strip()]
    return "\n".join(out[-3:]).strip()


def _is_log_noise(line: str) -> bool:
    s = line.strip()
    return (
        s.startswith("whisper_") or s.startswith("ggml_") or " INFO " in s
        or " DEBUG " in s or "\x1b[" in s
    )


def version() -> str:
    proc = run(["--version"])
    return proc.stdout.strip().split()[-1]


# ── systemd user service ───────────────────────────────────────────────

SERVICE_NAME = "voxtype"


def systemctl(action: str, check: bool = True) -> subprocess.CompletedProcess:
    exe = shutil.which("systemctl")
    if not exe:
        raise RuntimeError("systemctl not found; the voxtype daemon service requires systemd.")
    proc = subprocess.run([exe, "--user", action, SERVICE_NAME], capture_output=True, text=True, timeout=60)
    if check and proc.returncode != 0 and action not in ("is-active", "is-enabled", "status"):
        raise VoxtypeError(proc.stderr.strip() or f"systemctl --user {action} {SERVICE_NAME} failed",
                           returncode=proc.returncode, stderr=proc.stderr)
    return proc


# ── audio normalization (ffmpeg) ───────────────────────────────────────

def convert_to_wav16k(src: str, dst: str) -> dict:
    """Convert any audio file to 16 kHz mono s16le WAV with the real ffmpeg."""
    ff = find_ffmpeg()
    proc = subprocess.run(
        [ff, "-hide_banner", "-loglevel", "error", "-y", "-i", src,
         "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", dst],
        capture_output=True, text=True, timeout=DEFAULT_TIMEOUT,
    )
    if proc.returncode != 0 or not os.path.exists(dst):
        raise RuntimeError(f"ffmpeg failed to convert {src}: {proc.stderr.strip()}")
    return {"input": src, "output": dst, "method": "ffmpeg"}
