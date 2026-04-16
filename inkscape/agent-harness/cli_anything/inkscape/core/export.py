"""Inkscape CLI - Export module.

Handles rendering SVG to PNG, exporting to PDF, and saving SVG files.
Uses Pillow for basic PNG rendering and the project's SVG generation
for SVG/PDF output.
"""

import os
import shutil
from typing import Dict, Any, List, Optional

from cli_anything.inkscape.core.document import project_to_svg, save_svg
from cli_anything.inkscape.utils.svg_utils import serialize_svg

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
    """Render the SVG document to a PNG file using Pillow.

    This renders basic shapes (rect, circle, ellipse, line, text, polygon)
    using Pillow's drawing API. For complex SVG features (filters, gradients,
    clip paths), Inkscape's CLI would be needed.
    """
    if os.path.exists(output_path) and not overwrite:
        raise FileExistsError(f"Output file already exists: {output_path}")

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

    doc = project.get("document", {})
    doc_width = int(doc.get("width", 1920))
    doc_height = int(doc.get("height", 1080))

    # Use specified dimensions or document dimensions
    img_width = width or doc_width
    img_height = height or doc_height
    bg = background or doc.get("background", "#ffffff")

    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        # If Pillow is not available, generate an SVG + Inkscape command
        svg_path = output_path.rsplit(".", 1)[0] + ".svg"
        save_svg(project, svg_path)
        inkscape_cmd = f"inkscape {svg_path} --export-filename={output_path} --export-dpi={dpi}"
        return {
            "status": "svg_generated",
            "svg_path": svg_path,
            "inkscape_command": inkscape_cmd,
            "message": "Pillow not available. Use Inkscape to render.",
        }

    # Create image
    img = Image.new("RGBA", (img_width, img_height), bg)
    draw = ImageDraw.Draw(img)

    # Scale factor if rendering at different size
    sx = img_width / doc_width if doc_width else 1
    sy = img_height / doc_height if doc_height else 1

    # Render visible objects from bottom layer to top
    for layer in project.get("layers", []):
        if not layer.get("visible", True):
            continue

        layer_obj_ids = set(layer.get("objects", []))
        for obj in project.get("objects", []):
            if obj.get("id") in layer_obj_ids or obj.get("layer") == layer.get("id"):
                _render_object(draw, obj, sx, sy)

    # Save
    img.save(output_path, "PNG")

    return {
        "output": output_path,
        "format": "png",
        "width": img_width,
        "height": img_height,
        "dpi": dpi,
        "size_bytes": os.path.getsize(output_path),
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
        import subprocess
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


# ── Internal Rendering ──────────────────────────────────────────

def _parse_color(color_str: str) -> Optional[str]:
    """Parse a CSS color string to a Pillow-compatible color string."""
    if not color_str or color_str.lower() in ("none", "transparent"):
        return None
    return color_str


def _get_style_val(obj: Dict[str, Any], key: str, default: str = "") -> str:
    """Get a style value from an object's style string."""
    from cli_anything.inkscape.utils.svg_utils import parse_style
    style = parse_style(obj.get("style", ""))
    return style.get(key, default)


def _render_object(draw, obj: Dict[str, Any], sx: float, sy: float) -> None:
    """Render a single object onto a Pillow ImageDraw canvas."""
    obj_type = obj.get("type", "")
    fill = _parse_color(_get_style_val(obj, "fill", "#0000ff"))
    stroke = _parse_color(_get_style_val(obj, "stroke", "none"))
    stroke_w = _get_style_val(obj, "stroke-width", "1")
    try:
        stroke_w = max(1, int(float(stroke_w)))
    except (ValueError, TypeError):
        stroke_w = 1

    if obj_type == "rect":
        x = float(obj.get("x", 0)) * sx
        y = float(obj.get("y", 0)) * sy
        w = float(obj.get("width", 100)) * sx
        h = float(obj.get("height", 100)) * sy
        draw.rectangle([x, y, x + w, y + h], fill=fill, outline=stroke, width=stroke_w)

    elif obj_type == "circle":
        cx = float(obj.get("cx", 50)) * sx
        cy = float(obj.get("cy", 50)) * sy
        r = float(obj.get("r", 50)) * sx
        draw.ellipse([cx - r, cy - r, cx + r, cy + r],
                     fill=fill, outline=stroke, width=stroke_w)

    elif obj_type == "ellipse":
        cx = float(obj.get("cx", 50)) * sx
        cy = float(obj.get("cy", 50)) * sy
        rx = float(obj.get("rx", 75)) * sx
        ry = float(obj.get("ry", 50)) * sy
        draw.ellipse([cx - rx, cy - ry, cx + rx, cy + ry],
                     fill=fill, outline=stroke, width=stroke_w)

    elif obj_type == "line":
        x1 = float(obj.get("x1", 0)) * sx
        y1 = float(obj.get("y1", 0)) * sy
        x2 = float(obj.get("x2", 100)) * sx
        y2 = float(obj.get("y2", 100)) * sy
        line_color = stroke or fill or "#000000"
        draw.line([x1, y1, x2, y2], fill=line_color, width=stroke_w)

    elif obj_type == "polygon":
        points_str = obj.get("points", "")
        if points_str:
            points = _parse_svg_points(points_str, sx, sy)
            if len(points) >= 2:
                draw.polygon(points, fill=fill, outline=stroke, width=stroke_w)

    elif obj_type == "text":
        x = float(obj.get("x", 0)) * sx
        y = float(obj.get("y", 50)) * sy
        text = obj.get("text", "")
        text_fill = fill or "#000000"
        font_size = int(float(obj.get("font_size", 24)) * sy)
        try:
            from PIL import ImageFont
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                                       font_size)
        except (ImportError, OSError):
            font = None
        draw.text((x, y), text, fill=text_fill, font=font)

    elif obj_type == "star" and "d" in obj:
        # Render star as polygon from path data
        _render_path_as_polygon(draw, obj.get("d", ""), fill, stroke, stroke_w, sx, sy)

    elif obj_type == "path":
        # Basic path rendering
        _render_path_as_polygon(draw, obj.get("d", ""), fill, stroke, stroke_w, sx, sy)


def _parse_svg_points(points_str: str, sx: float = 1, sy: float = 1) -> list:
    """Parse SVG points string to list of (x, y) tuples."""
    import re
    result = []
    for pair in points_str.strip().split():
        parts = pair.split(",")
        if len(parts) == 2:
            try:
                result.append((float(parts[0]) * sx, float(parts[1]) * sy))
            except ValueError:
                pass
    return result


def _render_path_as_polygon(draw, d: str, fill, stroke, stroke_w: int,
                             sx: float, sy: float) -> None:
    """Render a simple SVG path as a Pillow polygon (handles M, L, Z only)."""
    import re
    points = []
    parts = re.split(r'[MLZmlz]', d)
    for part in parts:
        part = part.strip()
        if not part:
            continue
        coords = re.split(r'[,\s]+', part)
        i = 0
        while i + 1 < len(coords):
            try:
                x = float(coords[i]) * sx
                y = float(coords[i + 1]) * sy
                points.append((x, y))
                i += 2
            except ValueError:
                i += 1

    if len(points) >= 3:
        draw.polygon(points, fill=fill, outline=stroke, width=stroke_w)
    elif len(points) == 2:
        line_color = stroke or fill or "#000000"
        draw.line([points[0], points[1]], fill=line_color, width=stroke_w)
