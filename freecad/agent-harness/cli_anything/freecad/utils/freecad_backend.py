"""
Backend module that wraps the real FreeCAD headless CLI (FreeCADCmd).

Provides functions to locate the FreeCAD console executable and invoke it
in headless mode for macro execution, export, and version queries.
"""

from __future__ import annotations

import glob
import os
import platform
import shutil
import subprocess
import tempfile
import textwrap
from pathlib import Path
from typing import Any, Dict, Optional


# ---------------------------------------------------------------------------
# FreeCAD discovery
# ---------------------------------------------------------------------------

_INSTALL_INSTRUCTIONS = textwrap.dedent("""\
    FreeCAD console executable (FreeCADCmd) not found.

    Install FreeCAD and make sure FreeCADCmd is on your PATH, or install
    it to one of the standard locations:

      Windows:
        - C:\\Program Files\\FreeCAD*\\bin\\FreeCADCmd.exe
        Download from https://www.freecad.org/downloads.php

      macOS:
        brew install --cask freecad
        (or download from https://www.freecad.org/downloads.php)

      Linux (Debian / Ubuntu):
        sudo apt install freecad
      Linux (Flatpak):
        flatpak install flathub org.freecadweb.FreeCAD
      Linux (Snap):
        sudo snap install freecad
      Linux (conda-forge):
        conda install -c conda-forge freecad
""")

# Executable names to search for, in priority order
_FREECAD_CMD_NAMES = ["freecadcmd", "FreeCADCmd", "freecad", "FreeCAD"]
_FREECAD_GUI_NAMES = ["freecad", "FreeCAD", "freecadcmd", "FreeCADCmd"]


def find_freecad(gui_required: bool = False) -> str:
    """Locate the FreeCAD console executable on the system.

    Search order:
      1. ``FREECAD_PATH`` environment variable (explicit override).
      2. Known executable names on ``PATH`` (via :func:`shutil.which`).
      3. Common Windows install directories (glob-matched).
      4. Common macOS application bundle path.
      5. Common Linux paths.

    Returns
    -------
    str
        Absolute path to the FreeCAD console executable.

    Raises
    ------
    RuntimeError
        If FreeCAD cannot be found, with installation instructions in
        the message.
    """
    # 1. Environment variable override
    env_path = os.environ.get("FREECAD_PATH")
    if env_path and os.path.isfile(env_path):
        return os.path.abspath(env_path)

    names = _FREECAD_GUI_NAMES if gui_required else _FREECAD_CMD_NAMES

    # 2. On PATH
    for name in names:
        which = shutil.which(name)
        if which:
            return os.path.abspath(which)

    # 3. Windows common locations
    if platform.system() == "Windows":
        win_patterns = [
            "C:/Program Files/FreeCAD*/bin/FreeCADCmd.exe",
            "C:/Program Files (x86)/FreeCAD*/bin/FreeCADCmd.exe",
            "C:/Program Files/FreeCAD*/bin/FreeCAD.exe",
            "C:/Program Files (x86)/FreeCAD*/bin/FreeCAD.exe",
        ]
        for pattern in win_patterns:
            matches = sorted(glob.glob(pattern), reverse=True)
            if matches:
                return os.path.abspath(matches[0])

    # 4. macOS application bundle
    if platform.system() == "Darwin":
        mac_paths = [
            "/Applications/FreeCAD.app/Contents/MacOS/FreeCADCmd",
            "/Applications/FreeCAD.app/Contents/MacOS/FreeCAD",
        ]
        for mac_path in mac_paths:
            if os.path.isfile(mac_path):
                return mac_path

    # 5. Common Linux paths
    if platform.system() == "Linux":
        linux_paths = [
            "/usr/bin/freecadcmd",
            "/usr/bin/freecad",
            "/usr/local/bin/freecadcmd",
            "/usr/local/bin/freecad",
            "/snap/bin/freecad",
        ]
        for linux_path in linux_paths:
            if os.path.isfile(linux_path):
                return linux_path

    raise RuntimeError(_INSTALL_INSTRUCTIONS)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _run(
    args: list[str],
    *,
    timeout: int = 120,
    check: bool = False,
    env: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """Run a subprocess and return a normalised result dict."""
    try:
        proc_env = os.environ.copy()
        if env:
            proc_env.update(env)
        proc = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=proc_env,
        )
        result: Dict[str, Any] = {
            "ok": proc.returncode == 0,
            "returncode": proc.returncode,
            "stdout": proc.stdout.strip(),
            "stderr": proc.stderr.strip(),
            "command": " ".join(args),
        }
        if check and proc.returncode != 0:
            raise subprocess.CalledProcessError(
                proc.returncode, args, proc.stdout, proc.stderr,
            )
        return result
    except FileNotFoundError as exc:
        return {
            "ok": False,
            "returncode": -1,
            "stdout": "",
            "stderr": str(exc),
            "command": " ".join(args),
        }
    except subprocess.TimeoutExpired:
        return {
            "ok": False,
            "returncode": -1,
            "stdout": "",
            "stderr": f"FreeCAD process timed out after {timeout}s",
            "command": " ".join(args),
        }


def _write_temp_script(content: str) -> str:
    """Write *content* to a temporary ``.py`` file and return its path."""
    fd, path = tempfile.mkstemp(suffix=".py", prefix="freecad_macro_")
    try:
        os.write(fd, content.encode("utf-8"))
    finally:
        os.close(fd)
    return path


def _is_gui_wrapper_script(path: str) -> bool:
    """Return True when *path* looks like the local GUI-launch wrapper.

    On this machine the `freecad` command is a shell wrapper that dispatches to
    either the GUI binary or `freecadcmd`. When a Python script path is passed,
    the wrapper defaults to console mode unless we explicitly ask for the GUI
    binary.
    """
    try:
        resolved = Path(path).resolve()
        if not resolved.is_file():
            return False
        head = resolved.read_bytes()[:4096]
    except OSError:
        return False
    return b"SCRIPT_MODE" in head and b"xvfb-run" in head and b"freecadcmd" in head


def _macro_command(freecad: str, script_path: str, *, gui_required: bool) -> list[str]:
    """Build the argv used to execute a FreeCAD macro script."""
    if gui_required and _is_gui_wrapper_script(freecad):
        return [freecad, "freecad", script_path]
    return [freecad, script_path]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def get_version() -> str:
    """Return the FreeCAD version string (e.g. ``"0.21.2"``).

    Runs ``FreeCADCmd --version`` and parses the output.

    Returns
    -------
    str
        Version string extracted from FreeCAD's output.

    Raises
    ------
    RuntimeError
        If the version cannot be determined.
    """
    freecad = find_freecad()
    result = _run([freecad, "--version"])
    if result["ok"] and result["stdout"]:
        # Output is typically "FreeCAD 0.21.2" or similar
        for line in result["stdout"].splitlines():
            line = line.strip()
            if not line:
                continue
            # Try to extract version number
            parts = line.split()
            for part in parts:
                # Look for something that looks like a version number
                if any(c.isdigit() for c in part) and "." in part:
                    return part.strip(",").strip()
            # Fallback: return the whole first line
            return line
    if result["stderr"]:
        raise RuntimeError(f"Failed to get FreeCAD version: {result['stderr']}")
    raise RuntimeError("Failed to get FreeCAD version (no output)")


def run_macro(
    script_path: str,
    timeout: int = 120,
    gui_required: bool = False,
    env: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """Execute a FreeCAD Python macro script headlessly.

    Parameters
    ----------
    script_path : str
        Path to the ``.py`` macro file to execute.
    timeout : int
        Maximum seconds to wait for execution.

    Returns
    -------
    dict
        ``{"command": str, "returncode": int, "stdout": str, "stderr": str}``
    """
    freecad = find_freecad(gui_required=gui_required)
    script_path = str(Path(script_path).resolve())

    result = _run(_macro_command(freecad, script_path, gui_required=gui_required), timeout=timeout, env=env)

    return {
        "command": result["command"],
        "returncode": result["returncode"],
        "stdout": result["stdout"],
        "stderr": result["stderr"],
    }


def run_macro_content(
    script_content: str,
    timeout: int = 120,
    gui_required: bool = False,
    env: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """Execute macro content by writing it to a temp file first."""
    script_path = _write_temp_script(script_content)
    try:
        return run_macro(
            script_path,
            timeout=timeout,
            gui_required=gui_required,
            env=env,
        )
    finally:
        try:
            os.unlink(script_path)
        except OSError:
            pass


def export_headless(
    macro_content: str,
    output_path: str,
    timeout: int = 120,
) -> Dict[str, Any]:
    """Write a macro to a temp file, execute it, and verify the output.

    This is a convenience wrapper that combines writing a macro script
    to a temporary file, executing it via :func:`run_macro`, and verifying
    that the expected output file was created.

    Parameters
    ----------
    macro_content : str
        Complete Python macro script content.
    output_path : str
        Expected output file path (the macro should write to this path).
    timeout : int
        Maximum seconds to wait for execution.

    Returns
    -------
    dict
        ``{"output": str, "format": str, "method": "freecad-headless",
        "file_size": int}``

    Raises
    ------
    RuntimeError
        If the macro execution fails (non-zero exit code) or the output
        file is not created.
    """
    output_path = os.path.abspath(output_path)
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

    result = run_macro_content(macro_content, timeout=timeout)

    if result["returncode"] != 0:
        raise RuntimeError(
            f"FreeCAD macro execution failed (exit code {result['returncode']}). "
            f"stderr: {result['stderr']}"
        )

    if not os.path.isfile(output_path):
        raise RuntimeError(
            f"FreeCAD macro completed but output file was not created: "
            f"{output_path}. stdout: {result['stdout']}"
        )

    ext = Path(output_path).suffix.lstrip(".")
    file_size = os.path.getsize(output_path)

    return {
        "output": output_path,
        "format": ext,
        "method": "freecad-headless",
        "file_size": file_size,
    }
