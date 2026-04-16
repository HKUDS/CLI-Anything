"""Draw.io backend — invoke draw.io desktop CLI for diagram export.

The draw.io desktop app (Electron-based) supports command-line export:
    draw.io -x input.drawio -o output.png -f png
    draw.io -x input.drawio -o output.pdf -f pdf
    draw.io -x input.drawio -o output.svg -f svg

Requires: draw.io desktop app
    macOS:   brew install --cask drawio
    Linux:   snap install drawio  OR  download .deb/.AppImage
    Windows: winget install JGraph.Draw
"""

import os
import shutil
import subprocess
from typing import Optional


def find_drawio() -> str:
    """Find the draw.io CLI executable. Raises RuntimeError if not found."""
    # Common executable names across platforms
    candidates = ["draw.io", "drawio", "draw.io.exe"]

    for name in candidates:
        path = shutil.which(name)
        if path:
            return path

    # macOS app bundle path
    mac_path = "/Applications/draw.io.app/Contents/MacOS/draw.io"
    if os.path.isfile(mac_path):
        return mac_path

    raise RuntimeError(
        "draw.io desktop app is not installed. Install it with:\n"
        "  macOS:   brew install --cask drawio\n"
        "  Linux:   snap install drawio\n"
        "  Windows: winget install JGraph.Draw"
    )


def get_drawio_version() -> str:
    """Get the installed draw.io version string."""
    drawio = find_drawio()
    try:
        result = subprocess.run(
            [drawio, "--version"],
            capture_output=True, text=True, timeout=15,
        )
        output = result.stdout.strip() or result.stderr.strip()
        return output.split("\n")[0] if output else "unknown"
    except (subprocess.TimeoutExpired, OSError):
        return "unknown"


def export_diagram(
    drawio_path: str,
    output_path: str,
    fmt: str = "png",
    page_index: Optional[int] = None,
    scale: Optional[float] = None,
    width: Optional[int] = None,
    height: Optional[int] = None,
    border: int = 0,
    transparent: bool = False,
    crop: bool = False,
    overwrite: bool = False,
    timeout: int = 60,
) -> dict:
    """Export a .drawio file to PNG, PDF, SVG, or VSDX.

    Args:
        drawio_path: Path to the .drawio XML file.
        output_path: Output file path.
        fmt: Output format: png, pdf, svg, vsdx, xml.
        page_index: Page index to export (default: all pages).
        scale: Scale factor (e.g. 2.0 for 2x resolution).
        width: Output width in pixels (PNG only).
        height: Output height in pixels (PNG only).
        border: Border padding in pixels.
        transparent: Transparent background (PNG only).
        crop: Crop to diagram content.
        overwrite: Allow overwriting existing output.
        timeout: Maximum seconds.

    Returns:
        Dict with output path, format, file size, method.
    """
    if not os.path.exists(drawio_path):
        raise FileNotFoundError(f"Draw.io file not found: {drawio_path}")

    if os.path.exists(output_path) and not overwrite:
        raise FileExistsError(f"Output file exists: {output_path}")

    drawio = find_drawio()
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

    cmd = [
        drawio,
        "--export", drawio_path,
        "--output", output_path,
        "--format", fmt,
    ]

    if page_index is not None:
        cmd.extend(["--page-index", str(page_index)])
    if scale is not None:
        cmd.extend(["--scale", str(scale)])
    if width is not None:
        cmd.extend(["--width", str(width)])
    if height is not None:
        cmd.extend(["--height", str(height)])
    if border > 0:
        cmd.extend(["--border", str(border)])
    if transparent:
        cmd.append("--transparent")
    if crop:
        cmd.append("--crop")

    result = subprocess.run(
        cmd,
        capture_output=True, text=True,
        timeout=timeout,
    )

    if result.returncode != 0:
        raise RuntimeError(
            f"draw.io export failed (exit {result.returncode}):\n"
            f"  stderr: {result.stderr[-500:]}"
        )

    if not os.path.exists(output_path):
        raise RuntimeError(
            f"draw.io produced no output file.\n"
            f"  Expected: {output_path}\n"
            f"  stdout: {result.stdout[-500:]}"
        )

    return {
        "output": os.path.abspath(output_path),
        "format": fmt,
        "method": "draw.io-cli",
        "file_size": os.path.getsize(output_path),
    }
