"""Godot Engine backend — subprocess wrapper for the Godot binary.

Godot runs as a local binary (godot / godot.exe / Godot_v4*).
All engine operations go through command-line flags:
  --headless      No GPU / display required
  --path <dir>    Set project directory
  --script <gd>   Run a GDScript (must extend SceneTree or MainLoop)
  --export-all    Export all configured presets
  --import        Re-import project resources
  --quit          Quit after completing the command
"""

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any


# ---------- binary discovery ----------

_COMMON_NAMES = [
    "godot",
    "godot4",
    "godot.exe",
    "Godot_v4.4-stable_win64.exe",
    "Godot_v4.4-stable_linux.x86_64",
    "Godot_v4.3-stable_win64.exe",
    "Godot_v4.3-stable_linux.x86_64",
]


def find_godot_binary() -> str | None:
    """Search PATH and common locations for a Godot 4 binary.

    Returns:
        Absolute path to the binary, or None if not found.
    """
    # 1. Environment variable override
    env = os.environ.get("GODOT_BIN")
    if env and shutil.which(env):
        return shutil.which(env)

    # 2. Search PATH for common names
    for name in _COMMON_NAMES:
        path = shutil.which(name)
        if path:
            return path

    return None


def require_godot() -> str:
    """Return the Godot binary path or raise."""
    binary = find_godot_binary()
    if binary is None:
        raise RuntimeError(
            "Godot binary not found. Install Godot 4 and ensure it is on PATH, "
            "or set the GODOT_BIN environment variable."
        )
    return binary


# ---------- low-level runner ----------

def run_godot(
    args: list[str],
    project_path: str | None = None,
    headless: bool = True,
    timeout: int = 120,
    capture: bool = True,
) -> dict[str, Any]:
    """Execute the Godot binary with the given arguments.

    Args:
        args: Extra CLI flags (e.g. ['--script', 'res://tool.gd']).
        project_path: If set, adds --path <project_path>.
        headless: If True, adds --headless flag.
        timeout: Subprocess timeout in seconds.
        capture: If True, capture stdout/stderr.

    Returns:
        Dict with 'returncode', 'stdout', 'stderr' keys.

    Raises:
        RuntimeError: On binary-not-found or subprocess timeout.
    """
    binary = require_godot()
    cmd = [binary]
    if headless:
        cmd.append("--headless")
    if project_path:
        cmd.extend(["--path", str(project_path)])
    cmd.extend(args)

    try:
        result = subprocess.run(
            cmd,
            capture_output=capture,
            text=True,
            timeout=timeout,
            cwd=project_path,
        )
        return {
            "returncode": result.returncode,
            "stdout": result.stdout if capture else "",
            "stderr": result.stderr if capture else "",
        }
    except subprocess.TimeoutExpired as e:
        raise RuntimeError(
            f"Godot command timed out after {timeout}s: {' '.join(cmd)}"
        ) from e
    except FileNotFoundError as e:
        raise RuntimeError(
            f"Godot binary not found at {binary}"
        ) from e


# ---------- convenience helpers ----------

def get_version() -> dict:
    """Return Godot version info."""
    result = run_godot(["--version", "--quit"], headless=True, timeout=15)
    version_str = result["stdout"].strip().split("\n")[0] if result["stdout"] else "unknown"
    return {"version": version_str, "returncode": result["returncode"]}


def is_available() -> bool:
    """Check if Godot binary is reachable."""
    return find_godot_binary() is not None


def validate_project(project_path: str) -> bool:
    """Check if a directory is a valid Godot project (has project.godot)."""
    return Path(project_path, "project.godot").is_file()
