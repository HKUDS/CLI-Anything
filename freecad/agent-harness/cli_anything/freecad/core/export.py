"""
Export module for the FreeCAD CLI harness.

Handles rendering and exporting FreeCAD projects using the real FreeCAD
headless backend, including generating macro scripts from project JSON
state and converting to various CAD/mesh output formats.
"""

from __future__ import annotations

import os
import struct
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional

from cli_anything.freecad.utils.freecad_macro_gen import generate_macro
from cli_anything.freecad.utils import freecad_backend

# ---------------------------------------------------------------------------
# Export preset definitions
# ---------------------------------------------------------------------------

EXPORT_PRESETS: Dict[str, Dict[str, Any]] = {
    "step": {
        "format": "step",
        "description": "STEP AP214 (ISO 10303)",
    },
    "iges": {
        "format": "iges",
        "description": "IGES format",
    },
    "stl": {
        "format": "stl",
        "description": "STL mesh (3D printing)",
    },
    "stl_fine": {
        "format": "stl",
        "mesh_deviation": 0.01,
        "description": "Fine STL mesh",
    },
    "obj": {
        "format": "obj",
        "description": "Wavefront OBJ",
    },
    "brep": {
        "format": "brep",
        "description": "OpenCASCADE BREP",
    },
    "fcstd": {
        "format": "fcstd",
        "description": "Native FreeCAD document",
    },
    "dxf": {
        "format": "dxf",
        "description": "AutoCAD DXF format",
    },
    "svg": {
        "format": "svg",
        "description": "Scalable Vector Graphics",
    },
    "gltf": {
        "format": "gltf",
        "description": "GL Transmission Format",
    },
    "3mf": {
        "format": "3mf",
        "description": "3D Manufacturing Format",
    },
    "ply": {
        "format": "ply",
        "description": "Polygon File Format",
    },
    "off": {
        "format": "off",
        "description": "Object File Format",
    },
    "amf": {
        "format": "amf",
        "description": "Additive Manufacturing Format",
    },
    "pdf": {
        "format": "pdf",
        "description": "PDF via TechDraw",
    },
    "png": {
        "format": "png",
        "description": "Rendered PNG image",
    },
    "jpg": {
        "format": "jpg",
        "description": "Rendered JPG image",
    },
}

# Map format names to canonical file extensions
_FORMAT_EXTENSIONS: Dict[str, str] = {
    "step": ".step",
    "iges": ".iges",
    "stl": ".stl",
    "obj": ".obj",
    "brep": ".brep",
    "fcstd": ".FCStd",
    "dxf": ".dxf",
    "svg": ".svg",
    "gltf": ".gltf",
    "3mf": ".3mf",
    "ply": ".ply",
    "off": ".off",
    "amf": ".amf",
    "pdf": ".pdf",
    "png": ".png",
    "jpg": ".jpg",
}


# ---------------------------------------------------------------------------
# Format validation helpers
# ---------------------------------------------------------------------------


def _validate_step(path: str) -> bool:
    """Check that *path* starts with the ISO-10303-21 header marker."""
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as fh:
            header = fh.read(64)
        return header.strip().startswith("ISO-10303-21")
    except OSError:
        return False


def _validate_stl(path: str) -> bool:
    """Check for ASCII STL (``solid`` keyword) or valid binary STL header.

    A binary STL has an 80-byte header followed by a 4-byte little-endian
    triangle count.  An ASCII STL starts with the word ``solid``.
    """
    try:
        with open(path, "rb") as fh:
            head = fh.read(80)
        if not head:
            return False
        # ASCII STL check
        text_head = head.decode("ascii", errors="ignore").strip().lower()
        if text_head.startswith("solid"):
            return True
        # Binary STL: 80-byte header + 4-byte uint32 triangle count
        with open(path, "rb") as fh:
            fh.seek(80)
            count_bytes = fh.read(4)
            if len(count_bytes) == 4:
                _tri_count = struct.unpack("<I", count_bytes)[0]
                return True
        return False
    except OSError:
        return False


def _validate_iges(path: str) -> bool:
    """Check for IGES header markers in the first few lines.

    IGES files have fixed-width 80-column records.  The 73rd column of
    the first record should contain ``S`` (Start section).
    """
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as fh:
            first_line = fh.readline()
        if not first_line:
            return False
        # The 73rd character (index 72) should be 'S' for the start section
        if len(first_line) >= 73 and first_line[72] == "S":
            return True
        # Fallback: look for common IGES keywords
        upper = first_line.upper()
        return "IGES" in upper or "INITIAL GRAPHICS" in upper
    except OSError:
        return False


def _validate_dxf(path: str) -> bool:
    """Check that *path* contains DXF section markers."""
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as fh:
            header = fh.read(256)
        return "0\nSECTION" in header or "AutoCAD" in header
    except OSError:
        return False


def _validate_svg(path: str) -> bool:
    """Check that *path* contains SVG or XML markers."""
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as fh:
            header = fh.read(256)
        return "<svg" in header.lower() or "<?xml" in header.lower()
    except OSError:
        return False


def _validate_pdf(path: str) -> bool:
    """Check that *path* starts with the ``%PDF-`` header."""
    try:
        with open(path, "rb") as fh:
            header = fh.read(8)
        return header.startswith(b"%PDF-")
    except OSError:
        return False


def _validate_gltf(path: str) -> bool:
    """Check for glTF binary magic bytes or JSON with ``asset`` key."""
    try:
        with open(path, "rb") as fh:
            magic = fh.read(4)
        # Binary glTF magic: "glTF"
        if magic == b"glTF":
            return True
        # JSON-based glTF
        with open(path, "r", encoding="utf-8", errors="ignore") as fh:
            header = fh.read(512)
        return '"asset"' in header
    except OSError:
        return False


def _validate_3mf(path: str) -> bool:
    """Check that *path* is a ZIP archive containing ``3D/3dmodel.model``."""
    try:
        if not zipfile.is_zipfile(path):
            return False
        with zipfile.ZipFile(path, "r") as zf:
            return "3D/3dmodel.model" in zf.namelist()
    except (OSError, zipfile.BadZipFile):
        return False


_FORMAT_VALIDATORS: Dict[str, Any] = {
    "step": _validate_step,
    "iges": _validate_iges,
    "stl": _validate_stl,
    "dxf": _validate_dxf,
    "svg": _validate_svg,
    "pdf": _validate_pdf,
    "gltf": _validate_gltf,
    "3mf": _validate_3mf,
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def export_project(
    project: dict,
    output_path: str,
    preset: str = "step",
    overwrite: bool = False,
) -> Dict[str, Any]:
    """Export a FreeCAD project to a CAD/mesh file.

    1. Generates a FreeCAD macro script via :func:`generate_macro`.
    2. Calls :func:`freecad_backend.run_macro` to execute it headlessly.
    3. Verifies the output file exists and has the correct format.

    Parameters
    ----------
    project : dict
        The project JSON state containing parts, bodies, and placements.
    output_path : str
        Destination file path for the exported geometry.
    preset : str
        Name of an export preset (see ``EXPORT_PRESETS``).
    overwrite : bool
        If *False* (default), raise ``FileExistsError`` when *output_path*
        already exists.

    Returns
    -------
    dict
        ``{"output": str, "format": str, "file_size": int,
        "method": "freecad-headless"}``

    Raises
    ------
    FileExistsError
        If *output_path* exists and *overwrite* is False.
    ValueError
        If *preset* is not a known preset name.
    RuntimeError
        If the macro execution fails or the output file is missing/invalid.
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
    export_format = preset_config["format"]

    # Ensure output directory exists
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

    # Generate the FreeCAD macro script
    macro_content = generate_macro(project, output_path, export_format=export_format)

    # Execute via the headless backend
    result = freecad_backend.export_headless(
        macro_content, output_path, timeout=120,
    )

    # Verify the output file
    if not os.path.isfile(output_path):
        raise RuntimeError(
            f"Export failed: output file was not created at {output_path}. "
            f"Backend result: {result}"
        )

    # Run format-specific validation if available
    validator = _FORMAT_VALIDATORS.get(export_format)
    if validator and not validator(output_path):
        raise RuntimeError(
            f"Export produced an invalid {export_format.upper()} file at "
            f"{output_path}. The file header does not match the expected format."
        )

    ext = _FORMAT_EXTENSIONS.get(export_format, f".{export_format}")
    file_size = os.path.getsize(output_path)

    return {
        "output": output_path,
        "format": ext.lstrip("."),
        "file_size": file_size,
        "method": "freecad-headless",
    }


def get_export_info(project: dict) -> Dict[str, Any]:
    """Return a summary of what will be exported from *project*.

    Parameters
    ----------
    project : dict
        The project JSON state.

    Returns
    -------
    dict
        Summary with keys ``part_count``, ``body_count``,
        ``boolean_op_count``, ``available_presets``, and ``part_names``.
    """
    parts = project.get("parts", [])
    bodies = project.get("bodies", [])
    boolean_ops = project.get("boolean_ops", [])

    part_names = [p.get("name", "Unnamed") for p in parts]

    return {
        "part_count": len(parts),
        "body_count": len(bodies),
        "boolean_op_count": len(boolean_ops),
        "part_names": part_names,
        "available_presets": list(EXPORT_PRESETS.keys()),
    }


def list_presets() -> List[Dict[str, str]]:
    """Return a list of available export presets with descriptions.

    Returns
    -------
    list[dict]
        Each entry has ``name``, ``format``, and ``description`` keys.
    """
    return [
        {
            "name": name,
            "format": cfg["format"],
            "description": cfg["description"],
        }
        for name, cfg in EXPORT_PRESETS.items()
    ]
