"""Backend utilities — invoke the real Calibre tools as subprocesses.

This module locates calibredb, ebook-convert, and ebook-meta on the system PATH
and runs them with proper arguments. It never reimplements Calibre's logic.

Calibre is a HARD DEPENDENCY. If it is not installed, clear error messages are
shown with install instructions.
"""

import shutil
import subprocess
from typing import Any


# ── Tool discovery ─────────────────────────────────────────────────────────


def find_calibredb() -> str:
    """Return path to calibredb or raise with install instructions."""
    path = shutil.which("calibredb")
    if path:
        return path
    raise RuntimeError(
        "calibredb is not installed or not in PATH.\n\n"
        "Install Calibre:\n"
        "  Ubuntu/Debian:  sudo apt-get install calibre\n"
        "  Fedora/RHEL:    sudo dnf install calibre\n"
        "  macOS:          brew install --cask calibre\n"
        "  Windows/Other:  https://calibre-ebook.com/download\n\n"
        "After installing, ensure 'calibredb' is in your PATH."
    )


def find_ebook_convert() -> str:
    """Return path to ebook-convert or raise with install instructions."""
    path = shutil.which("ebook-convert")
    if path:
        return path
    raise RuntimeError(
        "ebook-convert is not installed or not in PATH.\n\n"
        "ebook-convert is part of Calibre.\n"
        "Install Calibre:\n"
        "  Ubuntu/Debian:  sudo apt-get install calibre\n"
        "  macOS:          brew install --cask calibre\n"
        "  Other:          https://calibre-ebook.com/download"
    )


def find_ebook_meta() -> str:
    """Return path to ebook-meta or raise with install instructions."""
    path = shutil.which("ebook-meta")
    if path:
        return path
    raise RuntimeError(
        "ebook-meta is not installed or not in PATH.\n\n"
        "ebook-meta is part of Calibre.\n"
        "Install Calibre:\n"
        "  Ubuntu/Debian:  sudo apt-get install calibre\n"
        "  macOS:          brew install --cask calibre\n"
        "  Other:          https://calibre-ebook.com/download"
    )


# ── Tool execution ─────────────────────────────────────────────────────────


def run_calibredb(
    args: list[str],
    library_path: str | None = None,
    timeout: int = 120,
) -> dict[str, Any]:
    """
    Run calibredb with the given args and optional --library-path.

    Returns dict with stdout, stderr, returncode.
    Raises RuntimeError on non-zero exit.
    """
    calibredb = find_calibredb()
    cmd = [calibredb]
    if library_path:
        cmd.extend(["--with-library", library_path])
    cmd.extend(args)

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"calibredb timed out after {timeout}s: {' '.join(cmd)}")

    if result.returncode != 0:
        raise RuntimeError(
            f"calibredb failed (exit {result.returncode}):\n"
            f"  Command: {' '.join(cmd)}\n"
            f"  stderr: {result.stderr.strip()}\n"
            f"  stdout: {result.stdout.strip()}"
        )

    return {
        "stdout": result.stdout,
        "stderr": result.stderr,
        "returncode": result.returncode,
    }


def run_ebook_convert(
    args: list[str],
    timeout: int = 300,
) -> dict[str, Any]:
    """
    Run ebook-convert with the given args.

    Returns dict with stdout, stderr, returncode.
    Raises RuntimeError on non-zero exit.
    """
    ebook_convert = find_ebook_convert()
    cmd = [ebook_convert] + args

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"ebook-convert timed out after {timeout}s")

    if result.returncode != 0:
        raise RuntimeError(
            f"ebook-convert failed (exit {result.returncode}):\n"
            f"  Command: {' '.join(cmd)}\n"
            f"  stderr: {result.stderr.strip()}\n"
            f"  stdout: {result.stdout.strip()}"
        )

    return {
        "stdout": result.stdout,
        "stderr": result.stderr,
        "returncode": result.returncode,
    }


def run_ebook_meta(
    args: list[str],
    timeout: int = 30,
) -> dict[str, Any]:
    """
    Run ebook-meta with the given args.

    Returns dict with stdout, stderr, returncode.
    Raises RuntimeError on non-zero exit.
    """
    ebook_meta = find_ebook_meta()
    cmd = [ebook_meta] + args

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"ebook-meta timed out after {timeout}s")

    if result.returncode != 0:
        raise RuntimeError(
            f"ebook-meta failed (exit {result.returncode}):\n"
            f"  Command: {' '.join(cmd)}\n"
            f"  stderr: {result.stderr.strip()}\n"
            f"  stdout: {result.stdout.strip()}"
        )

    return {
        "stdout": result.stdout,
        "stderr": result.stderr,
        "returncode": result.returncode,
    }
