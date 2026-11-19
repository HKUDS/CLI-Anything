"""Inkscape CLI - Export module.

Handles rendering SVG to PNG, exporting to PDF, and saving SVG files.
Uses the Inkscape CLI to render generated SVG for PNG and PDF output.
"""

import os
import shutil
import struct
import subprocess
import tempfile
from typing import Dict, Any, List, Optional

from cli_anything.inkscape.core.document import save_svg
from cli_anything.inkscape.utils.inkscape_backend import export_svg_to_png

# Export presets
EXPORT_PRESETS = {
    "png_web": {
        "format": "png",
        "dpi": 96,
        "description": "PNG for web (96 DPI)",
    },
    "png_print": {
        "format": "png",
        "dpi": 300,
        "description": "PNG for print (300 DPI)",
    },
    "png_hires": {
        "format": "png",
        "dpi": 600,
        "description": "High-resolution PNG (600 DPI)",
    },
    "svg": {
        "format": "svg",
        "dpi": 96,
        "description": "SVG vector format",
    },
    "pdf": {
        "format": "pdf",
        "dpi": 300,
        "description": "PDF document",
    },
    "eps": {
        "format": "eps",
        "dpi": 300,
        "description": "EPS (Encapsulated PostScript)",
    },
}

VALID_FORMATS = {"png", "svg", "pdf", "eps"}


def render_to_png(
    project: Dict[str, Any],
    output_path: str,
    width: Optional[int] = None,
    height: Optional[int] = None,
    dpi: int = 96,
    background: Optional[str] = None,
    overwrite: bool = False,
) -> Dict[str, Any]:
    """Render the generated SVG with Inkscape, preserving SVG semantics."""
    if os.path.exists(output_path) and not overwrite:
        raise FileExistsError(f"Output file already exists: {output_path}")
    if dpi <= 0 or any(value is not None and value <= 0 for value in (width, height)):
        raise ValueError("PNG dimensions and DPI must be positive")

    export_project = project
    if background is not None:
        export_project = {
            **project,
            "document": {**project.get("document", {}), "background": background},
        }

    output_directory = os.path.dirname(os.path.abspath(output_path))
    os.makedirs(output_directory, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix="cli-anything-inkscape-", dir=output_directory,
    ) as directory:
        svg_path = os.path.join(directory, "export.svg")
        png_path = os.path.join(directory, "export.png")
        save_svg(export_project, svg_path)
        try:
            result = export_svg_to_png(
                svg_path, png_path, width=width, height=height, dpi=dpi,
            )
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(
                f"Inkscape PNG export timed out after {exc.timeout} seconds"
            ) from exc
        # Read actual dimensions, including DPI/unit conversion and aspect ratios.
        with open(png_path, "rb") as image:
            header = image.read(24)
        if len(header) < 24 or header[:8] != b"\x89PNG\r\n\x1a\n" or header[12:16] != b"IHDR":
            raise RuntimeError("Inkscape did not produce a valid PNG header")
        img_width, img_height = struct.unpack(">II", header[16:24])
        os.replace(png_path, output_path)

    return {
        "output": output_path,
        "format": "png",
        "width": img_width,
        "height": img_height,
        "dpi": dpi,
        "size_bytes": result["file_size"],
        "rendered_by": "inkscape",
    }


def export_pdf(
    project: Dict[str, Any],
    output_path: str,
    overwrite: bool = False,
) -> Dict[str, Any]:
    """Export the document as PDF.

    Generates an SVG and provides an Inkscape command for PDF conversion.
    If Inkscape is available, runs it directly.
    """
    if os.path.exists(output_path) and not overwrite:
        raise FileExistsError(f"Output file already exists: {output_path}")

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

    # Generate SVG first
    svg_path = output_path.rsplit(".", 1)[0] + ".svg"
    save_svg(project, svg_path)

    inkscape_cmd = f"inkscape {svg_path} --export-filename={output_path}"

    # Try to use Inkscape if available
    if shutil.which("inkscape"):
        try:
            subprocess.run(
                ["inkscape", svg_path, f"--export-filename={output_path}"],
                check=True, capture_output=True, timeout=60,
            )
            return {
                "output": output_path,
                "format": "pdf",
                "svg_source": svg_path,
                "rendered_by": "inkscape",
            }
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
            pass

    return {
        "output": output_path,
        "format": "pdf",
        "svg_source": svg_path,
        "inkscape_command": inkscape_cmd,
        "status": "svg_generated",
        "message": "Run the inkscape command to produce PDF.",
    }


def export_svg(project: Dict[str, Any], output_path: str,
               overwrite: bool = False) -> Dict[str, Any]:
    """Export the document as a valid SVG file."""
    if os.path.exists(output_path) and not overwrite:
        raise FileExistsError(f"Output file already exists: {output_path}")

    save_svg(project, output_path)

    return {
        "output": output_path,
        "format": "svg",
        "size_bytes": os.path.getsize(output_path),
    }


def list_presets() -> List[Dict[str, Any]]:
    """List available export presets."""
    result = []
    for name, preset in EXPORT_PRESETS.items():
        result.append({
            "name": name,
            "format": preset["format"],
            "dpi": preset["dpi"],
            "description": preset["description"],
        })
    return result
