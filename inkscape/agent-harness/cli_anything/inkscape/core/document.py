"""Inkscape CLI - Document management module.

Handles creating, opening, saving, and inspecting SVG documents.
Maintains both a JSON project format for state tracking and
generates valid SVG files.
"""

import json
import os
from datetime import datetime
from typing import Optional, Dict, Any, List

from cli_anything.inkscape.utils.svg_utils import (
    create_svg_element, serialize_svg, write_svg_file, parse_svg_file,
    SVG_NS, INKSCAPE_NS, SODIPODI_NS, find_all_shapes, _ns,
)

# Document profiles (common canvas presets)
PROFILES = {
    "default": {"width": 1920, "height": 1080, "units": "px"},
    "a4_portrait": {"width": 210, "height": 297, "units": "mm"},
    "a4_landscape": {"width": 297, "height": 210, "units": "mm"},
    "a3_portrait": {"width": 297, "height": 420, "units": "mm"},
    "a3_landscape": {"width": 420, "height": 297, "units": "mm"},
    "letter_portrait": {"width": 8.5, "height": 11, "units": "in"},
    "letter_landscape": {"width": 11, "height": 8.5, "units": "in"},
    "hd720p": {"width": 1280, "height": 720, "units": "px"},
    "hd1080p": {"width": 1920, "height": 1080, "units": "px"},
    "4k": {"width": 3840, "height": 2160, "units": "px"},
    "icon_16": {"width": 16, "height": 16, "units": "px"},
    "icon_32": {"width": 32, "height": 32, "units": "px"},
    "icon_64": {"width": 64, "height": 64, "units": "px"},
    "icon_128": {"width": 128, "height": 128, "units": "px"},
    "icon_256": {"width": 256, "height": 256, "units": "px"},
    "icon_512": {"width": 512, "height": 512, "units": "px"},
    "instagram_square": {"width": 1080, "height": 1080, "units": "px"},
    "instagram_story": {"width": 1080, "height": 1920, "units": "px"},
    "twitter_header": {"width": 1500, "height": 500, "units": "px"},
    "youtube_thumbnail": {"width": 1280, "height": 720, "units": "px"},
    "business_card": {"width": 3.5, "height": 2, "units": "in"},
}

VALID_UNITS = ("px", "mm", "cm", "in", "pt", "pc")

PROJECT_VERSION = "1.0"


def create_document(
    name: str = "untitled",
    width: float = 1920,
    height: float = 1080,
    units: str = "px",
    profile: Optional[str] = None,
    background: str = "#ffffff",
) -> Dict[str, Any]:
    """Create a new Inkscape document (JSON project)."""
    if profile and profile in PROFILES:
        p = PROFILES[profile]
        width = p["width"]
        height = p["height"]
        units = p["units"]

    if units not in VALID_UNITS:
        raise ValueError(f"Invalid units: {units}. Use one of: {', '.join(VALID_UNITS)}")
    if width <= 0 or height <= 0:
        raise ValueError(f"Dimensions must be positive: {width}x{height}")

    viewbox = f"0 0 {width} {height}"

    project = {
        "version": PROJECT_VERSION,
        "name": name,
        "document": {
            "width": width,
            "height": height,
            "units": units,
            "viewBox": viewbox,
            "background": background,
        },
        "objects": [],
        "layers": [
            {
                "id": "layer1",
                "name": "Layer 1",
                "visible": True,
                "locked": False,
                "opacity": 1.0,
                "objects": [],
            }
        ],
        "gradients": [],
        "metadata": {
            "created": datetime.now().isoformat(),
            "modified": datetime.now().isoformat(),
            "software": "inkscape-cli 1.0",
        },
    }
    return project


def open_document(path: str) -> Dict[str, Any]:
    """Open an .inkscape-cli.json project file."""
    if not os.path.exists(path):
        raise FileNotFoundError(f"Document file not found: {path}")
    with open(path, "r") as f:
        project = json.load(f)
    if "version" not in project or "document" not in project:
        raise ValueError(f"Invalid document file: {path}")
    return project


def save_document(project: Dict[str, Any], path: str) -> str:
    """Save project to an .inkscape-cli.json file."""
    project["metadata"]["modified"] = datetime.now().isoformat()
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w") as f:
        json.dump(project, f, indent=2, default=str)
    return path


def save_svg(project: Dict[str, Any], path: str) -> str:
    """Generate and save a valid SVG file from the project state."""
    svg = project_to_svg(project)
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    write_svg_file(svg, path)
    return path


def get_document_info(project: Dict[str, Any]) -> Dict[str, Any]:
    """Get summary information about the document."""
    doc = project.get("document", {})
    objects = project.get("objects", [])
    layers = project.get("layers", [])
    gradients = project.get("gradients", [])

    # Count objects by type
    type_counts = {}
    for obj in objects:
        t = obj.get("type", "unknown")
        type_counts[t] = type_counts.get(t, 0) + 1

    return {
        "name": project.get("name", "untitled"),
        "version": project.get("version", "unknown"),
        "document": {
            "width": doc.get("width", 0),
            "height": doc.get("height", 0),
            "units": doc.get("units", "px"),
            "viewBox": doc.get("viewBox", ""),
            "background": doc.get("background", "#ffffff"),
        },
        "counts": {
            "objects": len(objects),
            "layers": len(layers),
            "gradients": len(gradients),
        },
        "object_types": type_counts,
        "objects": [
            {
                "id": o.get("id", ""),
                "name": o.get("name", ""),
                "type": o.get("type", "unknown"),
            }
            for o in objects
        ],
        "layers": [
            {
                "id": l.get("id", ""),
                "name": l.get("name", ""),
                "visible": l.get("visible", True),
                "locked": l.get("locked", False),
                "object_count": len(l.get("objects", [])),
            }
            for l in layers
        ],
        "metadata": project.get("metadata", {}),
    }


def set_canvas_size(project: Dict[str, Any], width: float, height: float) -> Dict[str, Any]:
    """Set the canvas dimensions."""
    if width <= 0 or height <= 0:
        raise ValueError(f"Dimensions must be positive: {width}x{height}")
    old_w = project["document"]["width"]
    old_h = project["document"]["height"]
    project["document"]["width"] = width
    project["document"]["height"] = height
    project["document"]["viewBox"] = f"0 0 {width} {height}"
    return {
        "old_size": f"{old_w}x{old_h}",
        "new_size": f"{width}x{height}",
    }


def set_units(project: Dict[str, Any], units: str) -> Dict[str, Any]:
    """Set the document units."""
    if units not in VALID_UNITS:
        raise ValueError(f"Invalid units: {units}. Use one of: {', '.join(VALID_UNITS)}")
    old = project["document"]["units"]
    project["document"]["units"] = units
    return {"old_units": old, "new_units": units}


def list_profiles() -> List[Dict[str, Any]]:
    """List all available document profiles."""
    result = []
    for name, p in PROFILES.items():
        result.append({
            "name": name,
            "dimensions": f"{p['width']}x{p['height']}",
            "units": p["units"],
        })
    return result


# ── SVG Generation ──────────────────────────────────────────────

def project_to_svg(project: Dict[str, Any]):
    """Convert project JSON to an SVG ElementTree Element."""
    import xml.etree.ElementTree as ET

    doc = project.get("document", {})
    width = doc.get("width", 1920)
    height = doc.get("height", 1080)
    units = doc.get("units", "px")

    svg = create_svg_element(width=width, height=height, units=units)

    # Add background rect if not transparent
    bg = doc.get("background", "#ffffff")
    if bg and bg.lower() not in ("none", "transparent"):
        bg_rect = ET.SubElement(svg, f"{{{SVG_NS}}}rect", {
            "id": "background",
            "width": str(width),
            "height": str(height),
            "x": "0",
            "y": "0",
            "style": f"fill:{bg};stroke:none",
        })

    # Add gradient definitions
    defs = svg.find(f"{{{SVG_NS}}}defs")
    if defs is None:
        defs = ET.SubElement(svg, f"{{{SVG_NS}}}defs")

    for grad in project.get("gradients", []):
        _add_gradient_to_defs(defs, grad)

    # Add layers as <g> elements with Inkscape groupmode
    for layer in project.get("layers", []):
        layer_g = ET.SubElement(svg, f"{{{SVG_NS}}}g", {
            "id": layer.get("id", "layer1"),
            _ns("inkscape", "groupmode"): "layer",
            _ns("inkscape", "label"): layer.get("name", "Layer"),
        })
        if not layer.get("visible", True):
            layer_g.set("style", "display:none")
        elif layer.get("opacity", 1.0) < 1.0:
            layer_g.set("style", f"opacity:{layer['opacity']}")

        # Add objects belonging to this layer
        layer_obj_ids = set(layer.get("objects", []))
        for obj in project.get("objects", []):
            if obj.get("id") in layer_obj_ids or (
                obj.get("layer") == layer.get("id")
            ):
                elem = _object_to_svg_element(obj)
                if elem is not None:
                    layer_g.append(elem)

    # Add objects not in any layer directly to SVG root
    all_layer_ids = set()
    for layer in project.get("layers", []):
        all_layer_ids.update(layer.get("objects", []))
        all_layer_ids.add(layer.get("id", ""))

    for obj in project.get("objects", []):
        obj_id = obj.get("id", "")
        obj_layer = obj.get("layer", "")
        if obj_id not in all_layer_ids and obj_layer not in [l.get("id") for l in project.get("layers", [])]:
            elem = _object_to_svg_element(obj)
            if elem is not None:
                svg.append(elem)

    return svg


def _add_gradient_to_defs(defs, grad: Dict[str, Any]) -> None:
    """Add a gradient definition to the <defs> element."""
    import xml.etree.ElementTree as ET

    grad_type = grad.get("type", "linear")
    grad_id = grad.get("id", "gradient1")

    if grad_type == "linear":
        elem = ET.SubElement(defs, f"{{{SVG_NS}}}linearGradient", {
            "id": grad_id,
            "x1": str(grad.get("x1", 0)),
            "y1": str(grad.get("y1", 0)),
            "x2": str(grad.get("x2", 1)),
            "y2": str(grad.get("y2", 0)),
            "gradientUnits": grad.get("gradientUnits", "objectBoundingBox"),
        })
    else:
        elem = ET.SubElement(defs, f"{{{SVG_NS}}}radialGradient", {
            "id": grad_id,
            "cx": str(grad.get("cx", 0.5)),
            "cy": str(grad.get("cy", 0.5)),
            "r": str(grad.get("r", 0.5)),
            "fx": str(grad.get("fx", grad.get("cx", 0.5))),
            "fy": str(grad.get("fy", grad.get("cy", 0.5))),
            "gradientUnits": grad.get("gradientUnits", "objectBoundingBox"),
        })

    for stop in grad.get("stops", []):
        ET.SubElement(elem, f"{{{SVG_NS}}}stop", {
            "offset": str(stop.get("offset", 0)),
            "style": f"stop-color:{stop.get('color', '#000000')};stop-opacity:{stop.get('opacity', 1)}",
        })


def _object_to_svg_element(obj: Dict[str, Any]):
    """Convert a JSON object dict to an SVG element."""
    import xml.etree.ElementTree as ET

    obj_type = obj.get("type", "")
    obj_id = obj.get("id", "")
    style = obj.get("style", "")
    transform = obj.get("transform", "")

    attribs = {"id": obj_id}
    if style:
        attribs["style"] = style
    if transform:
        attribs["transform"] = transform

    tag = None

    if obj_type == "rect":
        tag = f"{{{SVG_NS}}}rect"
        for attr in ("x", "y", "width", "height", "rx", "ry"):
            if attr in obj:
                attribs[attr] = str(obj[attr])

    elif obj_type == "circle":
        tag = f"{{{SVG_NS}}}circle"
        for attr in ("cx", "cy", "r"):
            if attr in obj:
                attribs[attr] = str(obj[attr])

    elif obj_type == "ellipse":
        tag = f"{{{SVG_NS}}}ellipse"
        for attr in ("cx", "cy", "rx", "ry"):
            if attr in obj:
                attribs[attr] = str(obj[attr])

    elif obj_type == "line":
        tag = f"{{{SVG_NS}}}line"
        for attr in ("x1", "y1", "x2", "y2"):
            if attr in obj:
                attribs[attr] = str(obj[attr])

    elif obj_type == "polygon":
        tag = f"{{{SVG_NS}}}polygon"
        if "points" in obj:
            attribs["points"] = obj["points"]

    elif obj_type == "polyline":
        tag = f"{{{SVG_NS}}}polyline"
        if "points" in obj:
            attribs["points"] = obj["points"]

    elif obj_type == "path":
        tag = f"{{{SVG_NS}}}path"
        if "d" in obj:
            attribs["d"] = obj["d"]

    elif obj_type == "text":
        tag = f"{{{SVG_NS}}}text"
        for attr in ("x", "y"):
            if attr in obj:
                attribs[attr] = str(obj[attr])
        elem = ET.Element(tag, attribs)
        elem.text = obj.get("text", "")
        return elem

    elif obj_type == "image":
        tag = f"{{{SVG_NS}}}image"
        for attr in ("x", "y", "width", "height"):
            if attr in obj:
                attribs[attr] = str(obj[attr])
        if "href" in obj:
            attribs[f"{{{INKSCAPE_NS}}}href"] = obj["href"]
            attribs["href"] = obj["href"]

    elif obj_type == "star":
        # Stars are represented as paths in SVG
        tag = f"{{{SVG_NS}}}path"
        if "d" in obj:
            attribs["d"] = obj["d"]
        attribs[_ns("sodipodi", "type")] = "star"

    else:
        return None

    if tag is None:
        return None

    return ET.Element(tag, attribs)
