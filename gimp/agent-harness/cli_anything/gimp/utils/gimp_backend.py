"""GIMP backend — invoke GIMP in batch mode for image processing.

Uses GIMP's Script-Fu batch mode for true image processing.

Requires: gimp (system package)
    apt install gimp
"""

import os
import shutil
import subprocess
from typing import Optional


def _script_fu_escape(value: str) -> str:
    """Escape a Python string for safe use inside Script-Fu double quotes."""
    return (
        value.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\r", "\\r")
        .replace("\n", "\\n")
    )


def find_gimp() -> str:
    """Find the GIMP executable. Raises RuntimeError if not found."""
    for name in ("gimp", "gimp-2.10", "gimp-2.99"):
        path = shutil.which(name)
        if path:
            return path
    raise RuntimeError(
        "GIMP is not installed. Install it with:\n"
        "  apt install gimp   # Debian/Ubuntu"
    )


def get_version() -> str:
    """Get the installed GIMP version string."""
    gimp = find_gimp()
    result = subprocess.run(
        [gimp, "--version"],
        capture_output=True, text=True, timeout=30,
    )
    return result.stdout.strip()


def batch_script_fu(
    script: str,
    timeout: int = 120,
) -> dict:
    """Run a Script-Fu command in GIMP batch mode.

    Args:
        script: Script-Fu command string (single-quoted safe)
        timeout: Maximum seconds to wait

    Returns:
        Dict with stdout, stderr, return code
    """
    gimp = find_gimp()
    cmd = [gimp, "-i", "-b", script, "-b", "(gimp-quit 0)"]

    result = subprocess.run(
        cmd,
        capture_output=True, text=True,
        timeout=timeout,
    )

    return {
        "command": " ".join(cmd),
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }


def create_and_export(
    width: int,
    height: int,
    output_path: str,
    fill_color: str = "white",
    timeout: int = 120,
) -> dict:
    """Create a new image in GIMP and export it."""
    abs_output = os.path.abspath(output_path)
    safe_abs_output = _script_fu_escape(abs_output)
    os.makedirs(os.path.dirname(abs_output), exist_ok=True)

    ext = os.path.splitext(output_path)[1].lower()

    # Build the export command based on format
    if ext == ".png":
        export_cmd = (
            f'(file-png-save RUN-NONINTERACTIVE image layer '
            f'"{safe_abs_output}" "{safe_abs_output}" 0 9 1 1 1 1 1)'
        )
    elif ext in (".jpg", ".jpeg"):
        export_cmd = (
            f'(file-jpeg-save RUN-NONINTERACTIVE image layer '
            f'"{safe_abs_output}" "{safe_abs_output}" 0.85 0.0 0 0 "" 0 1 0 2)'
        )
    elif ext == ".bmp":
        export_cmd = (
            f'(file-bmp-save RUN-NONINTERACTIVE image layer '
            f'"{safe_abs_output}" "{safe_abs_output}" 0)'
        )
    else:
        export_cmd = (
            f'(gimp-file-overwrite RUN-NONINTERACTIVE image layer '
            f'"{safe_abs_output}" "{safe_abs_output}")'
        )

    # Color mapping
    color_map = {
        "white": "255 255 255",
        "black": "0 0 0",
        "red": "255 0 0",
        "green": "0 255 0",
        "blue": "0 0 255",
    }
    rgb = color_map.get(fill_color, "255 255 255")

    # Build Script-Fu — use plain strings, subprocess handles quoting
    script = (
        f'(let* ('
        f'(image (car (gimp-image-new {width} {height} RGB)))'
        f'(layer (car (gimp-layer-new image {width} {height} '
        f'RGB-IMAGE "BG" 100 LAYER-MODE-NORMAL)))'
        f')'
        f'(gimp-image-insert-layer image layer 0 -1)'
        f'(gimp-image-set-active-layer image layer)'
        f"(gimp-palette-set-foreground '({rgb}))"
        f'(gimp-edit-fill layer FILL-FOREGROUND)'
        f'{export_cmd}'
        f'(gimp-image-delete image))'
    )

    result = batch_script_fu(script, timeout=timeout)

    if not os.path.exists(abs_output):
        raise RuntimeError(
            f"GIMP export produced no output file.\n"
            f"  Expected: {abs_output}\n"
            f"  stderr: {result['stderr'][-500:]}\n"
            f"  stdout: {result['stdout'][-500:]}"
        )

    return {
        "output": abs_output,
        "format": ext.lstrip("."),
        "method": "gimp-batch",
        "gimp_version": get_version(),
        "file_size": os.path.getsize(abs_output),
    }


def apply_filter_and_export(
    input_path: str,
    output_path: str,
    script_fu_filter: str = "",
    timeout: int = 120,
) -> dict:
    """Load an image in GIMP, apply a Script-Fu filter, and export.

    Args:
        input_path: Path to input image
        output_path: Path for output image
        script_fu_filter: Script-Fu commands to apply (uses 'image' and 'drawable' vars)
        timeout: Max seconds
    """
    if not os.path.exists(input_path):
        raise FileNotFoundError(f"Input file not found: {input_path}")

    abs_input = os.path.abspath(input_path)
    abs_output = os.path.abspath(output_path)
    safe_abs_input = _script_fu_escape(abs_input)
    safe_abs_output = _script_fu_escape(abs_output)
    os.makedirs(os.path.dirname(abs_output), exist_ok=True)

    ext = os.path.splitext(output_path)[1].lower()
    if ext == ".png":
        export_cmd = (
            f'(file-png-save RUN-NONINTERACTIVE image drawable '
            f'"{safe_abs_output}" "{safe_abs_output}" 0 9 1 1 1 1 1)'
        )
    elif ext in (".jpg", ".jpeg"):
        export_cmd = (
            f'(file-jpeg-save RUN-NONINTERACTIVE image drawable '
            f'"{safe_abs_output}" "{safe_abs_output}" 0.85 0.0 0 0 "" 0 1 0 2)'
        )
    else:
        export_cmd = (
            f'(gimp-file-overwrite RUN-NONINTERACTIVE image drawable '
            f'"{safe_abs_output}" "{safe_abs_output}")'
        )

    script = (
        f'(let* ('
        f'(image (car (gimp-file-load RUN-NONINTERACTIVE "{safe_abs_input}" "{safe_abs_input}")))'
        f'(drawable (car (gimp-image-flatten image)))'
        f')'
        f'{script_fu_filter}'
        f'(set! drawable (car (gimp-image-flatten image)))'
        f'{export_cmd}'
        f'(gimp-image-delete image))'
    )

    result = batch_script_fu(script, timeout=timeout)

    if not os.path.exists(abs_output):
        raise RuntimeError(
            f"GIMP filter+export produced no output.\n"
            f"  stderr: {result['stderr'][-500:]}"
        )

    return {
        "output": abs_output,
        "format": ext.lstrip("."),
        "method": "gimp-batch",
        "file_size": os.path.getsize(abs_output),
    }
