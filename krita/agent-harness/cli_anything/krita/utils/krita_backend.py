"""
Backend module that wraps the real Krita CLI.

Provides functions to locate the Krita executable and invoke it in
headless/batch mode for export, animation, scripting, and image-creation
operations.
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
# Krita discovery
# ---------------------------------------------------------------------------

_INSTALL_INSTRUCTIONS = textwrap.dedent("""\
    Krita executable not found.

    Install Krita and make sure it is on your PATH, or install it to one of
    the standard locations:

      Windows:
        - C:\\Program Files\\Krita (x64)\\bin\\krita.exe
        - C:\\Program Files (x86)\\Krita (x86)\\bin\\krita.exe
        Download from https://krita.org/en/download/

      macOS:
        brew install --cask krita
        (or download from https://krita.org/en/download/)

      Linux (Debian / Ubuntu):
        sudo apt install krita
      Linux (Flatpak):
        flatpak install flathub org.kde.krita
""")


def find_krita() -> str:
    """Locate the Krita executable on the system.

    Search order:
      1. ``KRITA_PATH`` environment variable (explicit override).
      2. ``krita`` / ``krita.exe`` on ``PATH`` (via :func:`shutil.which`).
      3. Common Windows install directories (glob-matched).
      4. Common macOS application bundle path.

    Returns:
        Absolute path to the Krita executable.

    Raises:
        RuntimeError: If Krita cannot be found, with installation
            instructions in the message.
    """
    # 1. Environment variable override
    env_path = os.environ.get("KRITA_PATH")
    if env_path and os.path.isfile(env_path):
        return os.path.abspath(env_path)

    # 2. On PATH
    which = shutil.which("krita")
    if which:
        return os.path.abspath(which)

    # 3. Windows common locations
    if platform.system() == "Windows":
        win_patterns = [
            "C:/Program Files/Krita*/bin/krita.exe",
            "C:/Program Files (x86)/Krita*/bin/krita.exe",
            "C:/Program Files/Krita*/bin/krita-*.exe",
            "C:/Program Files (x86)/Krita*/bin/krita-*.exe",
        ]
        for pattern in win_patterns:
            matches = sorted(glob.glob(pattern), reverse=True)
            if matches:
                return os.path.abspath(matches[0])

    # 4. macOS application bundle
    if platform.system() == "Darwin":
        mac_path = "/Applications/krita.app/Contents/MacOS/krita"
        if os.path.isfile(mac_path):
            return mac_path

    raise RuntimeError(_INSTALL_INSTRUCTIONS)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _run(
    args: list[str],
    *,
    timeout: int = 300,
    check: bool = False,
) -> Dict[str, Any]:
    """Run a subprocess and return a normalised result dict."""
    try:
        proc = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        result: Dict[str, Any] = {
            "ok": proc.returncode == 0,
            "returncode": proc.returncode,
            "stdout": proc.stdout.strip(),
            "stderr": proc.stderr.strip(),
            "command": args,
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
            "command": args,
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "ok": False,
            "returncode": -1,
            "stdout": "",
            "stderr": f"Krita process timed out after {timeout}s",
            "command": args,
        }


def _write_temp_script(content: str) -> str:
    """Write *content* to a temporary ``.py`` file and return its path."""
    fd, path = tempfile.mkstemp(suffix=".py", prefix="krita_script_")
    try:
        os.write(fd, content.encode("utf-8"))
    finally:
        os.close(fd)
    return path


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_version() -> str:
    """Return the Krita version string (e.g. ``"5.2.2"``)."""
    krita = find_krita()
    result = _run([krita, "--version"])
    if result["ok"] and result["stdout"]:
        # Output is typically "krita 5.2.2"
        line = result["stdout"].splitlines()[0]
        parts = line.strip().split()
        if len(parts) >= 2:
            return parts[-1]
        return line.strip()
    if result["stderr"]:
        raise RuntimeError(f"Failed to get Krita version: {result['stderr']}")
    raise RuntimeError("Failed to get Krita version (no output)")


def export_file(
    input_path: str | Path,
    output_path: str | Path,
    *,
    format: Optional[str] = None,
    timeout: int = 300,
) -> Dict[str, Any]:
    """Export *input_path* to *output_path* using Krita's CLI.

    Parameters:
        input_path: Source file (any format Krita can open).
        output_path: Destination file.  The extension determines the output
            format unless *format* is given.
        format: If provided, override the output format (e.g. ``"png"``).
            The extension of *output_path* will still be respected for the
            filename.
        timeout: Maximum seconds to wait for Krita.

    Returns:
        Result dict with keys ``ok``, ``returncode``, ``stdout``, ``stderr``,
        ``command``, and ``output_path``.
    """
    krita = find_krita()
    input_path = str(Path(input_path).resolve())
    output_path = str(Path(output_path).resolve())

    # Ensure output directory exists
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    args = [krita, "--export", "--export-filename", output_path, input_path]

    result = _run(args, timeout=timeout)
    result["output_path"] = output_path
    result["output_exists"] = os.path.isfile(output_path)
    return result


def export_animation(
    input_path: str | Path,
    output_dir: str | Path,
    *,
    format: str = "png",
    basename: str = "frame",
    first_frame: Optional[int] = None,
    last_frame: Optional[int] = None,
    timeout: int = 600,
) -> Dict[str, Any]:
    """Export animation frames from *input_path*.

    Parameters:
        input_path: Source animation file (e.g. ``.kra`` with animation data).
        output_dir: Directory to write frame files into.
        format: Frame image format (``"png"``, ``"jpg"``, ``"gif"``, etc.).
        basename: Filename prefix for each frame (e.g. ``frame0000.png``).
        first_frame: Optional first frame index to export.
        last_frame: Optional last frame index to export.
        timeout: Maximum seconds to wait for Krita.

    Returns:
        Result dict.  On success ``output_files`` lists exported frame paths.
    """
    krita = find_krita()
    input_path = str(Path(input_path).resolve())
    output_dir = str(Path(output_dir).resolve())
    os.makedirs(output_dir, exist_ok=True)

    # Build the export sequence filename pattern.
    # Krita expects the output filename to contain the base for numbering.
    export_filename = os.path.join(output_dir, f"{basename}.{format}")

    args = [
        krita,
        "--export-sequence",
        "--export-filename", export_filename,
    ]
    if first_frame is not None:
        args += ["--export-sequence-start", str(first_frame)]
    if last_frame is not None:
        args += ["--export-sequence-end", str(last_frame)]
    args.append(input_path)

    result = _run(args, timeout=timeout)

    # Collect whatever frames appeared in the output directory.
    frame_pattern = os.path.join(output_dir, f"{basename}*.{format}")
    result["output_dir"] = output_dir
    result["output_files"] = sorted(glob.glob(frame_pattern))
    return result


def run_script(
    script_content: str,
    *,
    input_path: Optional[str | Path] = None,
    timeout: int = 300,
) -> Dict[str, Any]:
    """Execute a Python script inside Krita's embedded interpreter.

    This writes *script_content* to a temporary file and invokes Krita with
    ``--script <path>``.

    Parameters:
        script_content: Python source code to run.
        input_path: Optional document to open before the script runs.
        timeout: Maximum seconds to wait.

    Returns:
        Result dict.
    """
    krita = find_krita()
    script_path = _write_temp_script(script_content)

    try:
        args = [krita, "--script", script_path]
        if input_path is not None:
            args.append(str(Path(input_path).resolve()))
        result = _run(args, timeout=timeout)
        result["script_path"] = script_path
        return result
    finally:
        # Best-effort cleanup; leave the file if removal fails so the
        # caller can inspect it.
        try:
            os.unlink(script_path)
        except OSError:
            pass


def create_new_image(
    width: int,
    height: int,
    output_path: str | Path,
    *,
    colorspace: str = "RGBA",
    depth: int = 8,
    background_color: str = "white",
    timeout: int = 300,
) -> Dict[str, Any]:
    """Create a new image of the given dimensions and save it.

    Because Krita's CLI does not expose a direct ``--new`` flag, this
    generates a small Python script and runs it with :func:`run_script`.

    Parameters:
        width: Image width in pixels.
        height: Image height in pixels.
        output_path: Where to save the resulting file.
        colorspace: Krita colour model name (``"RGBA"``, ``"GRAYA"``, etc.).
        depth: Bit depth per channel (8, 16, or 32).
        background_color: Fill colour name (``"white"``, ``"transparent"``,
            ``"black"``).
        timeout: Maximum seconds to wait.

    Returns:
        Result dict with ``output_path`` and ``output_exists`` keys.
    """
    output_path = str(Path(output_path).resolve())
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    # Map friendly depth values to Krita depth identifiers.
    depth_map = {
        8: "U8",
        16: "U16",
        32: "F32",
    }
    krita_depth = depth_map.get(depth, "U8")

    # Map background colour to RGBA tuples used in the InfoObject.
    bg_map = {
        "white": "(255, 255, 255, 255)",
        "black": "(0, 0, 0, 255)",
        "transparent": "(0, 0, 0, 0)",
    }
    bg_rgba = bg_map.get(background_color, "(255, 255, 255, 255)")

    script = textwrap.dedent(f"""\
        from krita import Krita
        import sys

        app = Krita.instance()
        doc = app.createDocument(
            {width},   # width
            {height},  # height
            "Untitled",
            "{colorspace}",
            "{krita_depth}",
            "",         # profile
            300.0,      # resolution
        )
        if doc is None:
            print("ERROR: failed to create document", file=sys.stderr)
            sys.exit(1)

        app.activeWindow().addView(doc)

        # Fill the background layer.
        root = doc.rootNode()
        first_layer = root.childNodes()[0] if root.childNodes() else None
        if first_layer is not None:
            color = app.createManagedColor("{colorspace}", "{krita_depth}", "")
            components = {bg_rgba}
            color.setComponents(list(components))
            sel = doc.selection()
            if sel is None:
                from krita import Selection
                sel = Selection()
                sel.select(0, 0, {width}, {height}, 255)
            first_layer.setPixelData(
                bytes([int(c) for c in components] * {width} * {height}),
                0, 0, {width}, {height},
            )

        doc.saveAs("{output_path.replace(chr(92), '/')}")
        doc.close()
        app.quit()
    """)

    result = run_script(script, timeout=timeout)
    result["output_path"] = output_path
    result["output_exists"] = os.path.isfile(output_path)
    return result


def batch_export(
    input_paths: list[str | Path],
    output_dir: str | Path,
    *,
    format: str = "png",
    timeout: int = 600,
) -> Dict[str, Any]:
    """Export multiple files to *output_dir* in the given *format*.

    Parameters:
        input_paths: List of source files.
        output_dir: Target directory for all exported files.
        format: Output format extension (e.g. ``"png"``, ``"jpg"``).
        timeout: Maximum seconds per file.

    Returns:
        Aggregate result dict with per-file results in ``"files"``.
    """
    output_dir = str(Path(output_dir).resolve())
    os.makedirs(output_dir, exist_ok=True)

    results: list[Dict[str, Any]] = []
    all_ok = True
    for src in input_paths:
        src = Path(src)
        dest = os.path.join(output_dir, f"{src.stem}.{format}")
        r = export_file(src, dest, timeout=timeout)
        results.append(r)
        if not r["ok"]:
            all_ok = False

    return {
        "ok": all_ok,
        "files": results,
        "output_dir": output_dir,
    }
