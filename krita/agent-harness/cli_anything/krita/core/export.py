"""
Export module for the Krita CLI harness.

Handles rendering and exporting images using the real Krita backend,
including building .kra files from project JSON state and converting
to various output formats.
"""

import os
import struct
import tempfile
import xml.etree.ElementTree as ET
import zlib
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from cli_anything.krita.utils.krita_backend import (
    export_animation as backend_export_animation,
    export_file,
    find_krita,
)

# ---------------------------------------------------------------------------
# Export preset definitions
# ---------------------------------------------------------------------------

EXPORT_PRESETS: Dict[str, Dict[str, Any]] = {
    "png": {
        "extension": "png",
        "description": "PNG with full alpha, compression 6",
        "mime": "image/png",
        "options": {
            "alpha": True,
            "compression": 6,
            "indexed": False,
        },
    },
    "png-web": {
        "extension": "png",
        "description": "PNG optimized for web (indexed if possible)",
        "mime": "image/png",
        "options": {
            "alpha": True,
            "compression": 9,
            "indexed": True,
        },
    },
    "jpeg": {
        "extension": "jpg",
        "description": "JPEG quality 90",
        "mime": "image/jpeg",
        "options": {
            "quality": 90,
        },
    },
    "jpeg-web": {
        "extension": "jpg",
        "description": "JPEG quality 75",
        "mime": "image/jpeg",
        "options": {
            "quality": 75,
        },
    },
    "jpeg-low": {
        "extension": "jpg",
        "description": "JPEG quality 50",
        "mime": "image/jpeg",
        "options": {
            "quality": 50,
        },
    },
    "tiff": {
        "extension": "tiff",
        "description": "TIFF uncompressed",
        "mime": "image/tiff",
        "options": {
            "compression": "none",
        },
    },
    "tiff-lzw": {
        "extension": "tiff",
        "description": "TIFF with LZW compression",
        "mime": "image/tiff",
        "options": {
            "compression": "lzw",
        },
    },
    "psd": {
        "extension": "psd",
        "description": "Photoshop PSD",
        "mime": "image/vnd.adobe.photoshop",
        "options": {},
    },
    "pdf": {
        "extension": "pdf",
        "description": "PDF export",
        "mime": "application/pdf",
        "options": {},
    },
    "svg": {
        "extension": "svg",
        "description": "SVG export",
        "mime": "image/svg+xml",
        "options": {},
    },
    "webp": {
        "extension": "webp",
        "description": "WebP quality 85",
        "mime": "image/webp",
        "options": {
            "quality": 85,
        },
    },
    "gif": {
        "extension": "gif",
        "description": "GIF (for animation)",
        "mime": "image/gif",
        "options": {},
    },
    "bmp": {
        "extension": "bmp",
        "description": "BMP uncompressed",
        "mime": "image/bmp",
        "options": {},
    },
}

# ---------------------------------------------------------------------------
# Helpers for building minimal valid PNGs
# ---------------------------------------------------------------------------


def _make_png_chunk(chunk_type: bytes, data: bytes) -> bytes:
    """Build a single PNG chunk with correct CRC."""
    chunk_body = chunk_type + data
    crc = struct.pack(">I", zlib.crc32(chunk_body) & 0xFFFFFFFF)
    length = struct.pack(">I", len(data))
    return length + chunk_body + crc


def _make_blank_png(width: int, height: int) -> bytes:
    """Create a minimal valid RGBA PNG of the given dimensions (fully transparent)."""
    png_signature = b"\x89PNG\r\n\x1a\n"

    # IHDR: width, height, bit depth 8, color type 6 (RGBA)
    ihdr_data = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    ihdr = _make_png_chunk(b"IHDR", ihdr_data)

    # IDAT: zlib-compressed scanlines (filter byte 0 + 4 zero bytes per pixel)
    raw_scanlines = b""
    for _ in range(height):
        raw_scanlines += b"\x00" + (b"\x00" * width * 4)
    compressed = zlib.compress(raw_scanlines)
    idat = _make_png_chunk(b"IDAT", compressed)

    # IEND
    iend = _make_png_chunk(b"IEND", b"")

    return png_signature + ihdr + idat + iend


# ---------------------------------------------------------------------------
# .kra file builder
# ---------------------------------------------------------------------------


def _build_maindoc_xml(project: dict) -> bytes:
    """Build maindoc.xml content from project state."""
    image_props = project.get("image", {})
    width = image_props.get("width", 1920)
    height = image_props.get("height", 1080)
    colorspace = image_props.get("colorspace", "RGBA")
    color_depth = image_props.get("color_depth", "U8")
    name = image_props.get("name", "Untitled")
    resolution = image_props.get("resolution", 72.0)

    doc = ET.Element("DOC")
    doc.set("xmlns", "http://www.calligra.org/DTD/krita")
    doc.set("editor", "CLI-Anything Krita Harness")
    doc.set("syntaxVersion", "2.0")

    image_el = ET.SubElement(doc, "IMAGE")
    image_el.set("name", name)
    image_el.set("width", str(width))
    image_el.set("height", str(height))
    image_el.set("colorspacename", colorspace)
    image_el.set("x-res", str(resolution))
    image_el.set("y-res", str(resolution))
    image_el.set("mime", "application/x-kra")

    layers_el = ET.SubElement(image_el, "layers")

    layers = project.get("layers", [])
    if not layers:
        # Create a default paint layer
        layers = [
            {
                "name": "Background",
                "type": "paintlayer",
                "visible": True,
                "opacity": 255,
                "uuid": "00000000-0000-0000-0000-000000000001",
            }
        ]

    for layer in layers:
        layer_type = layer.get("type", "paintlayer")
        if layer_type != "paintlayer":
            continue
        layer_el = ET.SubElement(layers_el, "layer")
        layer_el.set("name", layer.get("name", "Layer"))
        layer_el.set("nodetype", "paintlayer")
        layer_el.set("visible", "1" if layer.get("visible", True) else "0")
        layer_el.set("opacity", str(layer.get("opacity", 255)))
        layer_el.set("colorspacename", colorspace)
        layer_el.set("filename", _layer_filename(layer.get("name", "Layer")))
        uuid_val = layer.get("uuid", "")
        if uuid_val:
            layer_el.set("uuid", str(uuid_val))

    tree = ET.ElementTree(doc)
    from io import BytesIO

    buf = BytesIO()
    tree.write(buf, encoding="UTF-8", xml_declaration=True)
    return buf.getvalue()


def _build_documentinfo_xml(project: dict) -> bytes:
    """Build documentinfo.xml with Dublin Core metadata."""
    image_props = project.get("image", {})
    name = image_props.get("name", "Untitled")
    author = project.get("author", "CLI-Anything")

    doc = ET.Element("document-info")
    doc.set("xmlns", "http://www.calligra.org/DTD/document-info")

    about = ET.SubElement(doc, "about")
    title_el = ET.SubElement(about, "title")
    title_el.text = name
    creator_el = ET.SubElement(about, "creator")
    creator_el.text = author
    date_el = ET.SubElement(about, "date")
    date_el.text = datetime.now(timezone.utc).isoformat()

    tree = ET.ElementTree(doc)
    from io import BytesIO

    buf = BytesIO()
    tree.write(buf, encoding="UTF-8", xml_declaration=True)
    return buf.getvalue()


def _layer_filename(layer_name: str) -> str:
    """Derive a safe filename for a layer inside the .kra archive."""
    safe = "".join(c if c.isalnum() or c in ("_", "-") else "_" for c in layer_name)
    return safe


def build_kra_from_project(project: dict, output_path: str) -> str:
    """
    Build a minimal valid .kra file (ZIP archive) from the project JSON state.

    Creates:
    - mimetype (first entry, uncompressed): ``application/x-kra``
    - maindoc.xml with image properties and layer stack
    - documentinfo.xml with Dublin Core metadata
    - A blank RGBA PNG for each paint layer under ``<image_name>/layers/``

    Parameters
    ----------
    project : dict
        The project JSON state containing image properties and layers.
    output_path : str
        Destination path for the ``.kra`` file.

    Returns
    -------
    str
        Absolute path to the created ``.kra`` file.
    """
    output_path = os.path.abspath(output_path)
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    image_props = project.get("image", {})
    width = image_props.get("width", 1920)
    height = image_props.get("height", 1080)
    image_name = image_props.get("name", "Untitled")

    layers = project.get("layers", [])
    if not layers:
        layers = [
            {
                "name": "Background",
                "type": "paintlayer",
                "visible": True,
                "opacity": 255,
            }
        ]

    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_STORED) as zf:
        # mimetype must be the first entry, uncompressed
        zf.writestr("mimetype", "application/x-kra", compress_type=zipfile.ZIP_STORED)

        # maindoc.xml
        zf.writestr("maindoc.xml", _build_maindoc_xml(project))

        # documentinfo.xml
        zf.writestr("documentinfo.xml", _build_documentinfo_xml(project))

        # Blank pixel layer PNGs
        blank_png = _make_blank_png(width, height)
        for layer in layers:
            if layer.get("type", "paintlayer") != "paintlayer":
                continue
            layer_name = layer.get("name", "Layer")
            filename = _layer_filename(layer_name)
            layer_path = f"{image_name}/layers/{filename}"
            zf.writestr(layer_path, blank_png)

    return output_path


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def export_image(
    project: dict,
    output_path: str,
    preset: str = "png",
    overwrite: bool = False,
    **kwargs: Any,
) -> Dict[str, Any]:
    """
    Export a project to an image file.

    1. Builds a ``.kra`` file from the project JSON state.
    2. Calls the Krita backend to convert to the target format.

    Parameters
    ----------
    project : dict
        The project JSON state.
    output_path : str
        Destination file path for the exported image.
    preset : str
        Name of an export preset (see ``EXPORT_PRESETS``).
    overwrite : bool
        If *False* (default), raise ``FileExistsError`` when *output_path*
        already exists.
    **kwargs
        Extra options forwarded to the backend export call.

    Returns
    -------
    dict
        ``{"output_path": str, "file_size": int, "format": str, "method": str}``

    Raises
    ------
    FileExistsError
        If *output_path* exists and *overwrite* is False.
    ValueError
        If *preset* is not a known preset name.
    """
    output_path = os.path.abspath(output_path)

    if not overwrite and os.path.exists(output_path):
        raise FileExistsError(
            f"Output file already exists: {output_path}. "
            "Set overwrite=True to replace it."
        )

    if preset not in EXPORT_PRESETS:
        raise ValueError(
            f"Unknown export preset '{preset}'. "
            f"Available presets: {', '.join(sorted(EXPORT_PRESETS))}"
        )

    preset_config = EXPORT_PRESETS[preset]
    export_options = {**preset_config.get("options", {}), **kwargs}

    # Build a temporary .kra from the project state
    tmp_dir = tempfile.mkdtemp(prefix="krita_export_")
    kra_path = os.path.join(tmp_dir, "project.kra")
    build_kra_from_project(project, kra_path)

    # Use the Krita backend to export
    method = "krita_backend"
    try:
        export_file(
            input_path=kra_path,
            output_path=output_path,
            export_options=export_options,
        )
    except Exception:
        # Re-raise so callers can handle backend failures
        raise

    file_size = os.path.getsize(output_path) if os.path.exists(output_path) else 0

    return {
        "output_path": output_path,
        "file_size": file_size,
        "format": preset_config["extension"],
        "method": method,
    }


def export_animation(
    project: dict,
    output_dir: str,
    preset: str = "png",
    frame_range: Optional[Tuple[int, int]] = None,
    basename: str = "frame",
) -> Dict[str, Any]:
    """
    Export animation frames using the Krita backend.

    Parameters
    ----------
    project : dict
        The project JSON state.
    output_dir : str
        Directory to write frame files into.
    preset : str
        Export preset name.
    frame_range : tuple[int, int] | None
        Optional ``(start, end)`` frame range. ``None`` exports all frames.
    basename : str
        Base filename for exported frames (e.g. ``frame`` -> ``frame_0001.png``).

    Returns
    -------
    dict
        ``{"frame_count": int, "output_dir": str, "format": str}``
    """
    output_dir = os.path.abspath(output_dir)
    os.makedirs(output_dir, exist_ok=True)

    if preset not in EXPORT_PRESETS:
        raise ValueError(
            f"Unknown export preset '{preset}'. "
            f"Available presets: {', '.join(sorted(EXPORT_PRESETS))}"
        )

    preset_config = EXPORT_PRESETS[preset]

    # Build temporary .kra
    tmp_dir = tempfile.mkdtemp(prefix="krita_anim_export_")
    kra_path = os.path.join(tmp_dir, "project.kra")
    build_kra_from_project(project, kra_path)

    result = backend_export_animation(
        input_path=kra_path,
        output_dir=output_dir,
        frame_range=frame_range,
        basename=basename,
        export_options=preset_config.get("options", {}),
    )

    frame_count = result.get("frame_count", 0) if isinstance(result, dict) else 0

    return {
        "frame_count": frame_count,
        "output_dir": output_dir,
        "format": preset_config["extension"],
    }


def list_presets() -> List[Dict[str, str]]:
    """
    Return a list of available export presets with descriptions.

    Returns
    -------
    list[dict]
        Each entry has ``name``, ``extension``, and ``description`` keys.
    """
    return [
        {
            "name": name,
            "extension": cfg["extension"],
            "description": cfg["description"],
        }
        for name, cfg in EXPORT_PRESETS.items()
    ]


def get_supported_formats() -> List[str]:
    """
    Return a sorted list of all supported export format extensions.

    Returns
    -------
    list[str]
        Unique format extensions (e.g. ``["bmp", "gif", "jpg", ...]``).
    """
    formats = sorted({cfg["extension"] for cfg in EXPORT_PRESETS.values()})
    return formats
