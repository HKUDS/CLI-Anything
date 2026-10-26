"""Discovery and argv-only execution of the real fzf binary."""

from __future__ import annotations

import hashlib
import os
import re
import shutil
import signal
import subprocess
import time
from pathlib import Path
from typing import Any

from cli_anything.fzf.core.errors import BackendError


EXPECTED_VERSION = "0.74.5"
EXPECTED_REVISION = "c0a193e0"
DEFAULT_TIMEOUT = 30.0


def resolve_backend(override: str | None = None) -> Path:
    """Resolve an executable fzf path without invoking it."""

    requested = override or os.environ.get("CLI_ANYTHING_FZF_BACKEND")
    located = requested or shutil.which("fzf")
    if not located:
        raise BackendError(
            "backend_not_found",
            "fzf was not found; install fzf 0.74.5 or pass --backend PATH",
            exit_code=127,
        )
    path = Path(located).expanduser()
    if not path.exists() or not path.is_file():
        raise BackendError("backend_not_found", f"fzf backend does not exist: {path}", exit_code=127)
    if not os.access(path, os.X_OK):
        raise BackendError("backend_not_executable", f"fzf backend is not executable: {path}", exit_code=126)
    return path.absolute()


def file_sha256(path: Path) -> str:
    """Hash an executable without loading it all into memory."""

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def base_identity(path: Path) -> dict[str, Any]:
    """Return non-executing backend identity suitable for dry-run."""

    realpath = path.resolve(strict=True)
    stat = realpath.stat()
    return {
        "path": str(path),
        "realpath": str(realpath),
        "sha256": file_sha256(realpath),
        "size": stat.st_size,
        "expected_version": EXPECTED_VERSION,
        "expected_revision": EXPECTED_REVISION,
        "version": None,
        "revision": None,
        "version_verified": False,
        "compatible": None,
    }


def minimal_environment(*, interactive: bool = False) -> dict[str, str]:
    """Construct a small environment that does not inherit ambient FZF state."""

    env = {
        "PATH": "/usr/bin:/bin",
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
    }
    if interactive:
        term = os.environ.get("TERM", "xterm-256color")
        if re.fullmatch(r"[A-Za-z0-9_.+-]{1,64}", term):
            env["TERM"] = term
        else:
            env["TERM"] = "xterm-256color"
    return env


def _terminate_group(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is not None:
        return
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    try:
        process.wait(timeout=1.0)
        return
    except subprocess.TimeoutExpired:
        pass
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        return
    process.wait(timeout=1.0)


def run_captured(
    argv: list[str],
    *,
    input_bytes: bytes = b"",
    env: dict[str, str] | None = None,
    timeout: float = DEFAULT_TIMEOUT,
) -> dict[str, Any]:
    """Run a bounded backend operation with exact byte capture."""

    started = time.monotonic()
    process = subprocess.Popen(
        argv,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env or minimal_environment(),
        start_new_session=True,
    )
    try:
        stdout, stderr = process.communicate(input=input_bytes, timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        _terminate_group(process)
        raise BackendError(
            "backend_timeout",
            f"fzf exceeded the {timeout:g}s timeout",
            exit_code=124,
            details={"timeout_seconds": timeout},
        ) from exc
    return {
        "argv": argv,
        "exit_code": process.returncode,
        "stdout": stdout,
        "stderr": stderr,
        "duration_ms": round((time.monotonic() - started) * 1000, 3),
    }


def probe_backend(
    override: str | None = None,
    *,
    allow_version_mismatch: bool = False,
    timeout: float = 5.0,
) -> dict[str, Any]:
    """Invoke `fzf --version` and enforce the compatibility tuple."""

    path = resolve_backend(override)
    identity = base_identity(path)
    result = run_captured([str(path), "--version"], timeout=timeout)
    text = result["stdout"].decode("utf-8", "replace").strip()
    match = re.fullmatch(r"(\S+)(?: \(([^)]+)\))?", text)
    if result["exit_code"] != 0 or not match:
        raise BackendError(
            "backend_version_unreadable",
            "Could not parse fzf --version output",
            details={"exit_code": result["exit_code"], "output": text},
        )
    version, revision = match.groups()
    compatible = version == EXPECTED_VERSION
    identity.update(
        {
            "version": version,
            "revision": revision,
            "version_verified": True,
            "compatible": compatible,
            "version_output": text,
        }
    )
    if not compatible and not allow_version_mismatch:
        raise BackendError(
            "backend_version_mismatch",
            f"Expected fzf {EXPECTED_VERSION}, found {version}",
            details={"expected": EXPECTED_VERSION, "actual": version, "path": str(path)},
        )
    return identity


def get_backend_document(
    kind: str,
    override: str | None = None,
    *,
    allow_version_mismatch: bool = False,
    timeout: float = 10.0,
) -> tuple[dict[str, Any], bytes]:
    """Retrieve help or rendered man text from the real backend."""

    if kind not in {"help", "man"}:
        raise ValueError(kind)
    identity = probe_backend(override, allow_version_mismatch=allow_version_mismatch)
    path = identity["path"]
    env = minimal_environment()
    env.update({"MANPAGER": "cat", "PAGER": "cat", "GROFF_NO_SGR": "1"})
    result = run_captured([path, f"--{kind}"], env=env, timeout=timeout)
    if result["exit_code"] != 0:
        raise BackendError(
            "backend_introspection_failed",
            f"fzf --{kind} failed",
            details={
                "exit_code": result["exit_code"],
                "stderr": result["stderr"].decode("utf-8", "replace"),
            },
        )
    return identity, result["stdout"]


def terminate_process_group(process: subprocess.Popen[bytes]) -> None:
    """Public cancellation helper used by interactive sessions."""

    _terminate_group(process)
