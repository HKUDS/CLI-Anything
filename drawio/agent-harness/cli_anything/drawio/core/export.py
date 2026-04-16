"""Export/render operations: export diagrams to PNG, PDF, SVG."""

import os
import shutil
import tempfile
from typing import Optional

from ..utils import drawio_xml
from ..utils import drawio_backend
from .session import Session


# Export format configurations
EXPORT_FORMATS = {
    "png": {"ext": ".png", "description": "PNG image (raster)"},
    "pdf": {"ext": ".pdf", "description": "PDF document"},
    "svg": {"ext": ".svg", "description": "SVG vector image"},
    "vsdx": {"ext": ".vsdx", "description": "Microsoft Visio format"},
    "xml": {"ext": ".xml", "description": "Uncompressed draw.io XML"},
}


def list_formats() -> list[dict]:
    """List all available export formats."""
    return [
        {"name": name, **info}
        for name, info in sorted(EXPORT_FORMATS.items())
    ]


def render(session: Session, output_path: str,
           fmt: str = "png",
           page_index: Optional[int] = None,
           scale: Optional[float] = None,
           width: Optional[int] = None,
           height: Optional[int] = None,
           transparent: bool = False,
           crop: bool = False,
           overwrite: bool = False) -> dict:
    """Export the current project to a file.

    This works by:
    1. Saving the project to a temporary .drawio file
    2. Invoking draw.io CLI to render/export

    Args:
        session: Active session with an open project.
        output_path: Path for the output file.
        fmt: Export format (png, pdf, svg, vsdx, xml).
        page_index: Page index to export (default: first page).
        scale: Scale factor for PNG export.
        width: Output width in pixels (PNG only).
        height: Output height in pixels (PNG only).
        transparent: Transparent background (PNG only).
        crop: Crop to content.
        overwrite: Overwrite existing output.

    Returns:
        Dict with export results.
    """
    if not session.is_open:
        raise RuntimeError("No project is open")

    if fmt not in EXPORT_FORMATS:
        available = ", ".join(sorted(EXPORT_FORMATS.keys()))
        raise ValueError(f"Unknown format: {fmt!r}. Available: {available}")

    output_path = os.path.abspath(output_path)
    if os.path.exists(output_path) and not overwrite:
        raise FileExistsError(
            f"Output file already exists: {output_path}. Use --overwrite to replace."
        )

    # For XML format, just save the drawio XML directly
    if fmt == "xml":
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        drawio_xml.write_drawio(session.root, output_path)
        return {
            "action": "export",
            "output": output_path,
            "format": "xml",
            "method": "direct-write",
            "file_size": os.path.getsize(output_path),
        }

    # Save to temp file, then invoke draw.io CLI
    with tempfile.NamedTemporaryFile(suffix=".drawio", delete=False, mode="wb") as f:
        temp_path = f.name
        drawio_xml.write_drawio(session.root, temp_path)

    try:
        result = drawio_backend.export_diagram(
            drawio_path=temp_path,
            output_path=output_path,
            fmt=fmt,
            page_index=page_index,
            scale=scale,
            width=width,
            height=height,
            transparent=transparent,
            crop=crop,
            overwrite=True,  # We already checked above
        )
        result["action"] = "export"
        return result
    finally:
        os.unlink(temp_path)


def render_or_save(session: Session, output_path: str,
                   fmt: str = "png", **kwargs) -> dict:
    """Export with fallback: if draw.io CLI is not available, save the .drawio
    file and provide instructions for manual export.
    """
    try:
        return render(session, output_path, fmt, **kwargs)
    except RuntimeError as e:
        if "not installed" not in str(e):
            raise
        # Fallback: save .drawio and generate instructions
        drawio_path = os.path.splitext(output_path)[0] + ".drawio"
        drawio_xml.write_drawio(session.root, drawio_path)
        return {
            "action": "export_fallback",
            "drawio_file": os.path.abspath(drawio_path),
            "target_output": output_path,
            "target_format": fmt,
            "note": "draw.io CLI not found. Open the .drawio file in draw.io to export manually.",
            "install_hint": str(e),
        }
