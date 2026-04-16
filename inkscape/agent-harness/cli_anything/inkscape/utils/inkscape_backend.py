"""Inkscape backend — invoke Inkscape CLI for SVG export.

Requires: inkscape (system package)
    apt install inkscape
"""

import os
import shutil
import subprocess
from typing import Optional


def find_inkscape() -> str:
    """Find the Inkscape executable."""
    path = shutil.which("inkscape")
    if path:
        return path
    raise RuntimeError(
        "Inkscape is not installed. Install it with:\n"
        "  apt install inkscape   # Debian/Ubuntu"
    )


def get_version() -> str:
    """Get the installed Inkscape version string."""
    inkscape = find_inkscape()
    result = subprocess.run(
        [inkscape, "--version"],
        capture_output=True, text=True, timeout=10,
    )
    return result.stdout.strip()


def export_svg_to_png(
    svg_path: str,
    output_path: str,
    width: Optional[int] = None,
    height: Optional[int] = None,
    dpi: int = 96,
    overwrite: bool = False,
    timeout: int = 60,
) -> dict:
    """Export SVG to PNG using Inkscape."""
    if not os.path.exists(svg_path):
        raise FileNotFoundError(f"SVG file not found: {svg_path}")
    if os.path.exists(output_path) and not overwrite:
        raise FileExistsError(f"Output file exists: {output_path}")

    inkscape = find_inkscape()
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

    cmd = [inkscape, svg_path, f"--export-filename={output_path}", f"--export-dpi={dpi}"]
    if width:
        cmd.append(f"--export-width={width}")
    if height:
        cmd.append(f"--export-height={height}")

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)

    if result.returncode != 0:
        raise RuntimeError(f"Inkscape export failed: {result.stderr[-500:]}")

    if not os.path.exists(output_path):
        raise RuntimeError(f"Inkscape produced no output: {output_path}")

    return {
        "output": os.path.abspath(output_path),
        "format": "png",
        "method": "inkscape",
        "inkscape_version": get_version(),
        "file_size": os.path.getsize(output_path),
        "dpi": dpi,
    }


def export_svg_to_pdf(
    svg_path: str,
    output_path: str,
    overwrite: bool = False,
    timeout: int = 60,
) -> dict:
    """Export SVG to PDF using Inkscape."""
    if not os.path.exists(svg_path):
        raise FileNotFoundError(f"SVG file not found: {svg_path}")
    if os.path.exists(output_path) and not overwrite:
        raise FileExistsError(f"Output file exists: {output_path}")

    inkscape = find_inkscape()
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

    cmd = [inkscape, svg_path, f"--export-filename={output_path}"]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)

    if result.returncode != 0:
        raise RuntimeError(f"Inkscape PDF export failed: {result.stderr[-500:]}")

    if not os.path.exists(output_path):
        raise RuntimeError(f"Inkscape produced no output: {output_path}")

    return {
        "output": os.path.abspath(output_path),
        "format": "pdf",
        "method": "inkscape",
        "file_size": os.path.getsize(output_path),
    }


def export_svg_to_eps(
    svg_path: str,
    output_path: str,
    overwrite: bool = False,
    timeout: int = 60,
) -> dict:
    """Export SVG to EPS using Inkscape."""
    if not os.path.exists(svg_path):
        raise FileNotFoundError(f"SVG file not found: {svg_path}")
    if os.path.exists(output_path) and not overwrite:
        raise FileExistsError(f"Output file exists: {output_path}")

    inkscape = find_inkscape()
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

    cmd = [inkscape, svg_path, f"--export-filename={output_path}"]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)

    if result.returncode != 0:
        raise RuntimeError(f"Inkscape EPS export failed: {result.stderr[-500:]}")

    if not os.path.exists(output_path):
        raise RuntimeError(f"Inkscape produced no output: {output_path}")

    return {
        "output": os.path.abspath(output_path),
        "format": "eps",
        "method": "inkscape",
        "file_size": os.path.getsize(output_path),
    }
